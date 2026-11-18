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
    CREATE TABLE IF NOT EXISTS scheduled_stickers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL DEFAULT 0,
        chat_title TEXT NOT NULL DEFAULT '',
        sticker_url TEXT NOT NULL,
        sticker_name TEXT,
        target_type TEXT DEFAULT 'single',
        target_chat_ids TEXT,
        schedule_type TEXT DEFAULT 'once',
        scheduled_time TEXT NOT NULL,
        repeat_interval TEXT DEFAULT 'none',
        status TEXT DEFAULT 'active',
        last_sent_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sticker_send_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheduled_id INTEGER,
        chat_id INTEGER NOT NULL,
        chat_title TEXT NOT NULL,
        sticker_url TEXT NOT NULL,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'success',
        details TEXT
    )
    """)
    # Migration check for target_type and target_chat_ids
    cur.execute("PRAGMA table_info(scheduled_stickers)")
    cols = [r[1] for r in cur.fetchall()]
    if "target_type" not in cols:
        try:
            cur.execute("ALTER TABLE scheduled_stickers ADD COLUMN target_type TEXT DEFAULT 'single'")
        except Exception:
            pass
    if "target_chat_ids" not in cols:
        try:
            cur.execute("ALTER TABLE scheduled_stickers ADD COLUMN target_chat_ids TEXT")
        except Exception:
            pass

    conn.commit()
    conn.close()

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

def get_active_group_chats():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT chat_id, chat_title, chat_type FROM chats WHERE is_active = 1 AND chat_type IN ('group', 'supergroup') ORDER BY chat_title ASC")
    chats = [dict(r) for r in cur.fetchall()]
    conn.close()
    return chats

def resolve_sticker_identifier(sticker_input: str) -> str:
    """
    If the user inputs a t.me/addstickers/PackName link,
    query Telegram Bot API to get the first sticker file_id from that pack.
    Otherwise return the input as-is (e.g. file_id or web URL).
    """
    clean = sticker_input.strip()
    pack_name = None

    if "addstickers/" in clean:
        parts = clean.split("addstickers/")
        if len(parts) > 1:
            pack_name = parts[1].split("?")[0].split("/")[0].strip()
    elif clean.startswith("t.me/"):
        parts = clean.split("t.me/")
        if len(parts) > 1:
            pack_name = parts[1].split("?")[0].split("/")[0].strip()

    token = get_bot_token()
    if pack_name and token:
        try:
            url = f"https://api.telegram.org/bot{token}/getStickerSet?name={urllib.parse.quote(pack_name)}"
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read().decode("utf-8"))
            if data.get("ok") and data.get("result", {}).get("stickers"):
                return data["result"]["stickers"][0]["file_id"]
        except Exception:
            pass

    return clean

def process_due_stickers():
    """Check for active stickers whose scheduled_time <= now and trigger delivery"""
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M")

    cur.execute("""
    SELECT * FROM scheduled_stickers
    WHERE status = 'active' AND scheduled_time <= ?
    """, (now_iso,))

    due_items = [dict(r) for r in cur.fetchall()]
    conn.close()

    results = []
    for item in due_items:
        last_sent = item.get("last_sent_at")
        if last_sent and last_sent[:16] >= item["scheduled_time"][:16]:
            continue

        send_res = send_now(item["id"])
        results.append({"id": item["id"], "result": send_res})

        # Advance scheduled_time or mark completed
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        if item.get("schedule_type") == "recurring":
            interval = item.get("repeat_interval", "daily")
            next_time_str = compute_next_datetime(item["scheduled_time"], interval)

            cur.execute("""
            UPDATE scheduled_stickers
            SET scheduled_time = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (next_time_str, item["id"]))
        else:
            cur.execute("""
            UPDATE scheduled_stickers
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (item["id"],))

        conn.commit()
        conn.close()

    return results

def list_all():
    init_tables()
    try:
        process_due_stickers()
    except Exception:
        pass

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM scheduled_stickers ORDER BY id DESC")
    stickers = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM sticker_send_logs ORDER BY id DESC LIMIT 50")
    logs = [dict(r) for r in cur.fetchall()]

    # Available Group Chats
    chats = get_active_group_chats()

    conn.close()

    return {
        "scheduled_stickers": stickers,
        "logs": logs,
        "chats": chats,
        "total_gcs": len(chats),
        "server_time": datetime.now().isoformat(),
    }

def add_sticker(data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    target_type = data.get("target_type", "single")
    chat_id = int(data.get("chat_id") or 0)
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    sticker_url = data.get("sticker_url", "").strip()
    sticker_name = data.get("sticker_name", "").strip() or "GC Sticker Broadcast"
    schedule_type = data.get("schedule_type", "once")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "none")
    chat_title = data.get("chat_title", "").strip()

    if target_type == "all_gc":
        chat_title = "All Group Chats"
    elif not chat_title and chat_id:
        cur.execute("SELECT chat_title FROM chats WHERE chat_id = ? LIMIT 1", (chat_id,))
        row = cur.fetchone()
        chat_title = row[0] if row else f"Group {chat_id}"

    resolved_id = resolve_sticker_identifier(sticker_url)

    cur.execute("""
    INSERT INTO scheduled_stickers (chat_id, chat_title, sticker_url, sticker_name, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (chat_id, chat_title, resolved_id, sticker_name, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval))

    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "id": new_id, "message": "Scheduled sticker saved successfully"}

def edit_sticker(sticker_id: int, data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM scheduled_stickers WHERE id = ?", (sticker_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": f"Scheduled sticker #{sticker_id} not found"}

    target_type = data.get("target_type", "single")
    chat_id = int(data.get("chat_id") or 0)
    chat_title = data.get("chat_title", "").strip()
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    sticker_url = data.get("sticker_url", "").strip()
    sticker_name = data.get("sticker_name", "").strip() or "GC Sticker Broadcast"
    schedule_type = data.get("schedule_type", "once")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "none")
    status = data.get("status", "active")

    if target_type == "all_gc":
        chat_title = "All Group Chats"
    elif not chat_title and chat_id:
        cur.execute("SELECT chat_title FROM chats WHERE chat_id = ? LIMIT 1", (chat_id,))
        row = cur.fetchone()
        chat_title = row[0] if row else f"Group {chat_id}"

    resolved_id = resolve_sticker_identifier(sticker_url) if sticker_url else sticker_url

    cur.execute("""
    UPDATE scheduled_stickers
    SET target_type = ?, chat_id = ?, chat_title = ?, target_chat_ids = ?,
        sticker_url = ?, sticker_name = ?, schedule_type = ?, scheduled_time = ?,
        repeat_interval = ?, status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (target_type, chat_id, chat_title, target_chat_ids, resolved_id, sticker_name,
          schedule_type, scheduled_time, repeat_interval, status, sticker_id))

    conn.commit()
    conn.close()
    return {"success": True, "id": sticker_id, "message": "Scheduled sticker updated successfully"}

def delete_sticker(sticker_id: int):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM scheduled_stickers WHERE id = ?", (sticker_id,))
    cur.execute("DELETE FROM sticker_send_logs WHERE scheduled_id = ?", (sticker_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Deleted scheduled sticker {sticker_id}"}

def toggle_status(sticker_id: int, new_status: str):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE scheduled_stickers SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, sticker_id))
    conn.commit()
    conn.close()
    return {"success": True, "status": new_status}

def send_sticker_api(chat_id: int, sticker_input: str) -> dict:
    """Send sticker directly to Telegram group chat using Bot API"""
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    resolved_sticker = resolve_sticker_identifier(sticker_input)

    api_url = f"https://api.telegram.org/bot{token}/sendSticker"
    payload = json.dumps({
        "chat_id": chat_id,
        "sticker": resolved_sticker
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return json.loads(err_body)
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_now(sticker_id: int):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM scheduled_stickers WHERE id = ? LIMIT 1", (sticker_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        return {"success": False, "error": "Scheduled sticker not found"}

    item = dict(item)
    all_gcs = get_active_group_chats()

    target_type = item.get("target_type") or "single"
    targets = []
    if target_type == "all_gc" or item.get("chat_id") == 0:
        targets = all_gcs
    elif target_type == "selected" and item.get("target_chat_ids"):
        try:
            sel_ids = json.loads(item["target_chat_ids"])
            targets = [g for g in all_gcs if g["chat_id"] in sel_ids]
        except Exception:
            targets = all_gcs
    else:
        cid = item.get("chat_id")
        title = item.get("chat_title") or f"Group {cid}"
        targets = [{"chat_id": cid, "chat_title": title}]

    if not targets:
        targets = all_gcs

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        cid = gc["chat_id"]
        title = gc["chat_title"]
        result = send_sticker_api(cid, item["sticker_url"])
        is_ok = result.get("ok", False)
        status = "success" if is_ok else "failed"
        details = "Sticker delivered to group chat successfully" if is_ok else result.get("description", result.get("error", "Unknown error"))

        if is_ok:
            success_count += 1
        else:
            fail_count += 1

        cur.execute("""
        INSERT INTO sticker_send_logs (scheduled_id, chat_id, chat_title, sticker_url, sent_at, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sticker_id, cid, title, item["sticker_url"], now_iso, status, details))

        results.append({"chat_id": cid, "chat_title": title, "ok": is_ok, "details": details})

    if success_count > 0:
        cur.execute("UPDATE scheduled_stickers SET last_sent_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (now_iso, sticker_id))

    conn.commit()
    conn.close()

    return {
        "success": success_count > 0,
        "total_targets": len(targets),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
        "sent_at": now_iso
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--list":
            print(json.dumps(list_all()))
        elif cmd == "--add":
            raw_input = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(add_sticker(json.loads(raw_input))))
        elif cmd == "--edit" and len(sys.argv) > 2:
            raw_input = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(edit_sticker(int(sys.argv[2]), json.loads(raw_input))))
        elif cmd == "--delete" and len(sys.argv) > 2:
            print(json.dumps(delete_sticker(int(sys.argv[2]))))
        elif cmd == "--toggle" and len(sys.argv) > 3:
            print(json.dumps(toggle_status(int(sys.argv[2]), sys.argv[3])))
        elif cmd == "--send-now" and len(sys.argv) > 2:
            print(json.dumps(send_now(int(sys.argv[2]))))
    else:
        print(json.dumps(list_all()))
