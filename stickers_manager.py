import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

_STICKER_PACK_CACHE: dict[str, tuple[float, list[str]]] = {}

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
        target_type TEXT DEFAULT 'all_gc',
        target_chat_ids TEXT,
        schedule_type TEXT DEFAULT 'recurring',
        scheduled_time TEXT NOT NULL,
        repeat_interval TEXT DEFAULT '3min',
        status TEXT DEFAULT 'active',
        last_sent_at TEXT,
        sticker_pack_name TEXT,
        current_index INTEGER DEFAULT 0,
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

    cur.execute("PRAGMA table_info(scheduled_stickers)")
    cols = [r[1] for r in cur.fetchall()]
    if "target_type" not in cols:
        try:
            cur.execute("ALTER TABLE scheduled_stickers ADD COLUMN target_type TEXT DEFAULT 'all_gc'")
        except Exception:
            pass
    if "target_chat_ids" not in cols:
        try:
            cur.execute("ALTER TABLE scheduled_stickers ADD COLUMN target_chat_ids TEXT")
        except Exception:
            pass
    if "sticker_pack_name" not in cols:
        try:
            cur.execute("ALTER TABLE scheduled_stickers ADD COLUMN sticker_pack_name TEXT")
        except Exception:
            pass
    if "current_index" not in cols:
        try:
            cur.execute("ALTER TABLE scheduled_stickers ADD COLUMN current_index INTEGER DEFAULT 0")
        except Exception:
            pass

    conn.commit()
    conn.close()

def parse_interval_to_timedelta(interval: str) -> timedelta:
    if not interval or interval == "none":
        return timedelta(minutes=3)
    s = str(interval).strip().lower().replace(" ", "")
    if s in ("daily", "day"):
        return timedelta(days=1)
    if s in ("weekly", "week"):
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
        return timedelta(minutes=3)

def parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def get_active_group_chats():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT chat_id, chat_title, chat_type FROM chats WHERE is_active = 1 AND chat_type IN ('group', 'supergroup') ORDER BY chat_title ASC")
    chats = [dict(r) for r in cur.fetchall()]
    conn.close()
    return chats

def extract_pack_name(input_str: str) -> str | None:
    """Extract sticker pack name from link or identifier"""
    if not input_str:
        return None
    s = str(input_str).strip()
    if "addstickers/" in s:
        parts = s.split("addstickers/")
        if len(parts) > 1:
            return parts[1].split("?")[0].split("/")[0].strip()
    if "set=" in s:
        parts = s.split("set=")
        if len(parts) > 1:
            return parts[1].split("&")[0].strip()
    if not any(c in s for c in ['/', ':', ' ', '?', '=']) and len(s) < 64:
        return s
    return None

def get_pack_stickers(pack_name: str) -> list[str]:
    """Retrieve all sticker file_ids belonging to a sticker set from Telegram API"""
    if not pack_name:
        return []

    now = time.time()
    if pack_name in _STICKER_PACK_CACHE:
        ts, stickers = _STICKER_PACK_CACHE[pack_name]
        if now - ts < 300:  # 5 min cache
            return stickers

    token = get_bot_token()
    if not token:
        return []

    try:
        url = f"https://api.telegram.org/bot{token}/getStickerSet?name={urllib.parse.quote(pack_name)}"
        req = urllib.request.Request(url, headers={"User-Agent": "WaguriBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                raw_stickers = data.get("result", {}).get("stickers", [])
                file_ids = [s["file_id"] for s in raw_stickers if "file_id" in s]
                if file_ids:
                    _STICKER_PACK_CACHE[pack_name] = (now, file_ids)
                    return file_ids
    except Exception:
        pass

    return []

def resolve_next_sticker(sticker_id: int, cur: sqlite3.Cursor, item: dict) -> tuple[str, str]:
    """
    Cycles to the next sticker in the pack so a different sticker is sent every interval.
    If it's a single sticker file_id, returns it directly.
    """
    raw_url = item.get("sticker_url") or ""
    pack_name = item.get("sticker_pack_name") or extract_pack_name(raw_url)

    if pack_name:
        file_ids = get_pack_stickers(pack_name)
        if file_ids:
            curr_idx = item.get("current_index") or 0
            selected_file_id = file_ids[curr_idx % len(file_ids)]
            next_idx = (curr_idx + 1) % len(file_ids)

            cur.execute("""
            UPDATE scheduled_stickers
            SET current_index = ?, sticker_pack_name = ?
            WHERE id = ?
            """, (next_idx, pack_name, sticker_id))

            note = f"Sticker #{curr_idx % len(file_ids) + 1} of {len(file_ids)} from pack '{pack_name}'"
            return selected_file_id, note

    return raw_url, "Direct sticker"

def send_sticker_api(chat_id: int, sticker_input: str) -> dict:
    """Send sticker directly to Telegram group chat using Bot API"""
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    api_url = f"https://api.telegram.org/bot{token}/sendSticker"
    payload = json.dumps({
        "chat_id": chat_id,
        "sticker": sticker_input
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
    """
    Dispatches the next sticker to target group chat(s),
    cycling to a different sticker each time if a pack is configured.
    """
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

    target_type = item.get("target_type") or "all_gc"
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

    # Determine which sticker to send for this interval cycle
    sticker_to_send, pack_note = resolve_next_sticker(sticker_id, cur, item)

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        cid = gc["chat_id"]
        title = gc["chat_title"]
        result = send_sticker_api(cid, sticker_to_send)
        is_ok = result.get("ok", False)
        status = "success" if is_ok else "failed"
        details = f"{pack_note} delivered" if is_ok else result.get("description", result.get("error", "Unknown error"))

        if is_ok:
            success_count += 1
        else:
            fail_count += 1

        cur.execute("""
        INSERT INTO sticker_send_logs (scheduled_id, chat_id, chat_title, sticker_url, sent_at, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sticker_id, cid, title, sticker_to_send, now_iso, status, details))

        results.append({"chat_id": cid, "chat_title": title, "ok": is_ok, "details": details})

    if success_count > 0:
        cur.execute("""
        UPDATE scheduled_stickers
        SET last_sent_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (now_iso, sticker_id))

    conn.commit()
    conn.close()

    return {
        "success": success_count > 0,
        "total_targets": len(targets),
        "success_count": success_count,
        "fail_count": fail_count,
        "sticker_sent": sticker_to_send,
        "details": pack_note,
        "results": results,
        "sent_at": now_iso
    }

def process_due_stickers():
    """
    Silent background checker: triggers stickers that are active and due,
    strictly respecting the exact time gap (e.g. 3 min, 5 min, 10 min).
    """
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM scheduled_stickers WHERE status = 'active'")
    active_items = [dict(r) for r in cur.fetchall()]
    conn.close()

    now = datetime.now()
    results = []

    for item in active_items:
        interval_str = item.get("repeat_interval", "3min")
        interval_delta = parse_interval_to_timedelta(interval_str)

        sched_time_str = item.get("scheduled_time")
        sched_dt = parse_dt(sched_time_str) or now

        last_sent_str = item.get("last_sent_at")
        last_sent_dt = parse_dt(last_sent_str)

        # 1. Has the scheduled time arrived?
        if now < sched_dt:
            continue

        # 2. Strict time gap check: ensure at least (interval - 15 seconds) has elapsed since last delivery
        if last_sent_dt:
            min_cooldown_seconds = max(10, interval_delta.total_seconds() - 15)
            elapsed_seconds = (now - last_sent_dt).total_seconds()
            if elapsed_seconds < min_cooldown_seconds:
                continue

        # Send sticker now (automatically advances to the next sticker in the pack)
        send_res = send_now(item["id"])
        results.append({"id": item["id"], "result": send_res})

        # Calculate exact next send time: from now + interval_delta!
        next_dt = datetime.now() + interval_delta
        next_dt_str = next_dt.strftime("%Y-%m-%dT%H:%M:%S")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
        UPDATE scheduled_stickers
        SET scheduled_time = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (next_dt_str, item["id"]))
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

    target_type = data.get("target_type", "all_gc")
    chat_id = int(data.get("chat_id") or 0)
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    sticker_url = data.get("sticker_url", "").strip()
    sticker_name = data.get("sticker_name", "").strip() or "GC Sticker Broadcast"
    repeat_interval = data.get("repeat_interval", "3min")
    chat_title = data.get("chat_title", "").strip()

    if target_type == "all_gc":
        chat_title = "All Group Chats"
    elif not chat_title and chat_id:
        cur.execute("SELECT chat_title FROM chats WHERE chat_id = ? LIMIT 1", (chat_id,))
        row = cur.fetchone()
        chat_title = row[0] if row else f"Group {chat_id}"

    pack_name = extract_pack_name(sticker_url)

    interval_delta = parse_interval_to_timedelta(repeat_interval)
    now_dt = datetime.now()
    # Next send scheduled for exactly now + interval_delta
    next_time_str = (now_dt + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")

    cur.execute("""
    INSERT INTO scheduled_stickers (
        chat_id, chat_title, sticker_url, sticker_name, target_type, target_chat_ids,
        schedule_type, scheduled_time, repeat_interval, status, sticker_pack_name, current_index
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 0)
    """, (chat_id, chat_title, sticker_url, sticker_name, target_type, target_chat_ids,
          'recurring', next_time_str, repeat_interval, pack_name))

    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Automatically send the first sticker right away when activated
    try:
        send_now(new_id)
    except Exception:
        pass

    return {
        "success": True,
        "id": new_id,
        "message": f"Sticker activated! First sticker sent now; next sticker will send in {repeat_interval}."
    }

def edit_sticker(sticker_id: int, data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM scheduled_stickers WHERE id = ?", (sticker_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": f"Scheduled sticker #{sticker_id} not found"}

    target_type = data.get("target_type", "all_gc")
    chat_id = int(data.get("chat_id") or 0)
    chat_title = data.get("chat_title", "").strip()
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    sticker_url = data.get("sticker_url", "").strip()
    sticker_name = data.get("sticker_name", "").strip() or "GC Sticker Broadcast"
    repeat_interval = data.get("repeat_interval", "3min")
    status = data.get("status", "active")

    if target_type == "all_gc":
        chat_title = "All Group Chats"
    elif not chat_title and chat_id:
        cur.execute("SELECT chat_title FROM chats WHERE chat_id = ? LIMIT 1", (chat_id,))
        row = cur.fetchone()
        chat_title = row[0] if row else f"Group {chat_id}"

    pack_name = extract_pack_name(sticker_url)
    interval_delta = parse_interval_to_timedelta(repeat_interval)
    next_time_str = (datetime.now() + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")

    cur.execute("""
    UPDATE scheduled_stickers
    SET target_type = ?, chat_id = ?, chat_title = ?, target_chat_ids = ?,
        sticker_url = ?, sticker_name = ?, repeat_interval = ?, status = ?,
        sticker_pack_name = ?, scheduled_time = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (target_type, chat_id, chat_title, target_chat_ids, sticker_url, sticker_name,
          repeat_interval, status, pack_name, next_time_str, sticker_id))

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

    if new_status == 'active':
        cur.execute("SELECT repeat_interval FROM scheduled_stickers WHERE id = ?", (sticker_id,))
        row = cur.fetchone()
        interval = row[0] if row else "3min"
        interval_delta = parse_interval_to_timedelta(interval)

        # Set next send time to exactly now + interval_delta
        next_time_str = (datetime.now() + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")

        cur.execute("""
        UPDATE scheduled_stickers
        SET status = 'active', scheduled_time = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (next_time_str, sticker_id))
        conn.commit()
        conn.close()

        # Send first sticker immediately upon activation
        try:
            send_now(sticker_id)
        except Exception:
            pass

        return {
            "success": True,
            "status": "active",
            "message": f"Sticker activated! First sticker sent now; next will send in {interval}."
        }
    else:
        cur.execute("""
        UPDATE scheduled_stickers
        SET status = 'paused', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (sticker_id,))
        conn.commit()
        conn.close()
        return {"success": True, "status": "paused", "message": "Sticker paused"}

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
