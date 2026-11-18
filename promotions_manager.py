import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_db_path():
    candidates = [
        os.path.join(os.path.dirname(__file__), "moderation.db"),
        os.path.join(os.getcwd(), "moderation.db"),
        os.path.join(os.getcwd(), "..", "moderation.db"),
        r"c:\Users\Suraj\Desktop\New folder\bot\moderation.db",
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return "moderation.db"

def get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

def init_tables():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        link_url TEXT,
        button_text TEXT DEFAULT 'Visit Website',
        target_type TEXT DEFAULT 'all_gc',
        target_chat_ids TEXT,
        schedule_type TEXT DEFAULT 'once',
        scheduled_time TEXT NOT NULL,
        repeat_interval TEXT DEFAULT 'none',
        status TEXT DEFAULT 'active',
        total_delivered INTEGER DEFAULT 0,
        last_sent_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS promotion_send_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promotion_id INTEGER,
        chat_id INTEGER NOT NULL,
        chat_title TEXT NOT NULL,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'success',
        details TEXT
    )
    """)
    conn.commit()
    conn.close()

def send_telegram_message(chat_id: int, text: str, link_url: str = None, button_text: str = None) -> dict:
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }

    # Add inline button link if link_url provided
    if link_url and link_url.strip():
        url = link_url.strip()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("t.me/"):
            url = f"https://{url}"
        label = (button_text or "Visit Website").strip()
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": label, "url": url}]]
        }

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return json.loads(err_body)
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_active_group_chats():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT chat_id, chat_title, chat_type FROM chats WHERE is_active = 1 AND chat_type IN ('group', 'supergroup') ORDER BY chat_title ASC")
    chats = [dict(r) for r in cur.fetchall()]
    conn.close()
    return chats

def broadcast_promotion(promotion_id: int) -> dict:
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM scheduled_promotions WHERE id = ? LIMIT 1", (promotion_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        return {"success": False, "error": "Promotion not found"}

    item = dict(item)
    all_gcs = get_active_group_chats()

    # Determine target GCs
    targets = []
    if item.get("target_type") == "selected" and item.get("target_chat_ids"):
        try:
            selected_ids = json.loads(item["target_chat_ids"])
            targets = [g for g in all_gcs if g["chat_id"] in selected_ids]
        except Exception:
            targets = all_gcs
    else:
        targets = all_gcs

    if not targets:
        # Fallback to any active chats
        cur.execute("SELECT chat_id, chat_title, chat_type FROM chats WHERE is_active = 1 LIMIT 5")
        targets = [dict(r) for r in cur.fetchall()]

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        chat_id = gc["chat_id"]
        chat_title = gc["chat_title"]

        res = send_telegram_message(
            chat_id=chat_id,
            text=item["message"],
            link_url=item.get("link_url"),
            button_text=item.get("button_text")
        )

        is_ok = res.get("ok", False)
        status = "success" if is_ok else "failed"
        details = "Delivered to GC" if is_ok else res.get("description", res.get("error", "Failed"))

        if is_ok:
            success_count += 1
        else:
            fail_count += 1

        cur.execute("""
        INSERT INTO promotion_send_logs (promotion_id, chat_id, chat_title, sent_at, status, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (promotion_id, chat_id, chat_title, now_iso, status, details))

        results.append({
            "chat_id": chat_id,
            "chat_title": chat_title,
            "ok": is_ok,
            "details": details
        })

    # Update promotion metadata
    new_total = (item.get("total_delivered") or 0) + success_count
    cur.execute("""
    UPDATE scheduled_promotions
    SET last_sent_at = ?, total_delivered = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (now_iso, new_total, promotion_id))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "promotion_id": promotion_id,
        "total_targets": len(targets),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
        "sent_at": now_iso
    }

def parse_interval_to_timedelta(interval: str) -> timedelta:
    if not interval or interval == "none":
        return timedelta(minutes=30)
    s = str(interval).strip().lower().replace(" ", "")
    if s == "daily" or s == "day":
        return timedelta(days=1)
    if s == "weekly" or s == "week":
        return timedelta(days=7)

    # Check minute suffixes
    for suffix in ["minutes", "minute", "mins", "min", "m"]:
        if s.endswith(suffix):
            val_str = s[:-len(suffix)]
            try:
                return timedelta(minutes=int(val_str))
            except ValueError:
                pass

    # Check hour suffixes
    for suffix in ["hours", "hour", "hrs", "hr", "h"]:
        if s.endswith(suffix):
            val_str = s[:-len(suffix)]
            try:
                return timedelta(hours=int(val_str))
            except ValueError:
                pass

    # Check day suffixes
    for suffix in ["days", "day", "d"]:
        if s.endswith(suffix):
            val_str = s[:-len(suffix)]
            try:
                return timedelta(days=int(val_str))
            except ValueError:
                pass

    try:
        val = int(s)
        return timedelta(minutes=val)
    except ValueError:
        return timedelta(minutes=30)

def compute_next_datetime(base_dt_str: str, interval_str: str) -> str:
    try:
        base_dt = datetime.fromisoformat(base_dt_str)
    except Exception:
        base_dt = datetime.now()
    delta = parse_interval_to_timedelta(interval_str)
    next_dt = base_dt + delta
    now = datetime.now()
    while next_dt <= now:
        next_dt += delta
    return next_dt.strftime("%Y-%m-%dT%H:%M")

def process_due_promotions():
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M")

    cur.execute("""
    SELECT * FROM scheduled_promotions
    WHERE status = 'active' AND scheduled_time <= ?
    """, (now_iso,))

    due_items = [dict(r) for r in cur.fetchall()]
    conn.close()

    for item in due_items:
        last_sent = item.get("last_sent_at")
        if last_sent and last_sent[:16] >= item["scheduled_time"][:16]:
            continue

        broadcast_promotion(item["id"])

        # Recurrence handling
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        if item.get("schedule_type") == "recurring":
            interval = item.get("repeat_interval", "daily")
            next_time_str = compute_next_datetime(item["scheduled_time"], interval)

            cur.execute("""
            UPDATE scheduled_promotions
            SET scheduled_time = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (next_time_str, item["id"]))
        else:
            cur.execute("""
            UPDATE scheduled_promotions
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (item["id"],))

        conn.commit()
        conn.close()

def list_all():
    init_tables()
    try:
        process_due_promotions()
    except Exception as e:
        pass

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM scheduled_promotions ORDER BY id DESC")
    promotions = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM promotion_send_logs ORDER BY id DESC LIMIT 50")
    logs = [dict(r) for r in cur.fetchall()]

    # Available Group Chats
    cur.execute("SELECT chat_id, chat_title, chat_type FROM chats WHERE is_active = 1 ORDER BY chat_title ASC")
    chats = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        "promotions": promotions,
        "logs": logs,
        "chats": chats,
        "total_gcs": len([c for c in chats if c["chat_type"] in ("group", "supergroup")]),
        "server_time": datetime.now().isoformat(),
    }

def add_promotion(data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    title = data.get("title", "").strip() or "GC Promotional Announcement"
    message = data.get("message", "").strip()
    link_url = data.get("link_url", "").strip()
    button_text = data.get("button_text", "").strip() or "Visit Website"
    target_type = data.get("target_type", "all_gc")
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    schedule_type = data.get("schedule_type", "once")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "none")

    cur.execute("""
    INSERT INTO scheduled_promotions (title, message, link_url, button_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (title, message, link_url, button_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval))

    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "id": new_id, "message": "Promotional broadcast scheduled successfully"}

def delete_promotion(promotion_id: int):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM scheduled_promotions WHERE id = ?", (promotion_id,))
    cur.execute("DELETE FROM promotion_send_logs WHERE promotion_id = ?", (promotion_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Deleted promotion {promotion_id}"}

def toggle_status(promotion_id: int, new_status: str):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE scheduled_promotions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, promotion_id))
    conn.commit()
    conn.close()
    return {"success": True, "status": new_status}

def edit_promotion(promotion_id: int, data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM scheduled_promotions WHERE id = ?", (promotion_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": f"Promotion #{promotion_id} not found"}

    title = data.get("title", "").strip() or "GC Promotional Announcement"
    message = data.get("message", "").strip()
    link_url = data.get("link_url", "").strip()
    button_text = data.get("button_text", "").strip() or "Visit Website"
    target_type = data.get("target_type", "all_gc")
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    schedule_type = data.get("schedule_type", "once")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "none")
    status = data.get("status", "active")

    cur.execute("""
    UPDATE scheduled_promotions
    SET title = ?, message = ?, link_url = ?, button_text = ?, target_type = ?,
        target_chat_ids = ?, schedule_type = ?, scheduled_time = ?, repeat_interval = ?, status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (title, message, link_url, button_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval, status, promotion_id))

    conn.commit()
    conn.close()
    return {"success": True, "id": promotion_id, "message": "Promotion updated successfully"}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--list":
            print(json.dumps(list_all()))
        elif cmd == "--add":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(add_promotion(json.loads(raw))))
        elif cmd == "--edit" and len(sys.argv) > 2:
            raw = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(edit_promotion(int(sys.argv[2]), json.loads(raw))))
        elif cmd == "--delete" and len(sys.argv) > 2:
            print(json.dumps(delete_promotion(int(sys.argv[2]))))
        elif cmd == "--toggle" and len(sys.argv) > 3:
            print(json.dumps(toggle_status(int(sys.argv[2]), sys.argv[3])))
        elif cmd == "--broadcast" and len(sys.argv) > 2:
            print(json.dumps(broadcast_promotion(int(sys.argv[2]))))
    else:
        print(json.dumps(list_all()))
