import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from database import claim_scheduled_job, get_db, get_next_sequence, get_db_path, release_scheduled_job

_STICKER_PACK_CACHE: dict[str, tuple[float, list[str]]] = {}
_tables_initialized = False

def get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

def init_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    db = get_db()
    db["scheduled_stickers"].create_index("id", unique=True)
    db["scheduled_stickers"].create_index("status")
    db["sticker_send_logs"].create_index("id", unique=True)
    db["sticker_send_logs"].create_index("scheduled_id")
    _tables_initialized = True

def parse_interval_to_timedelta(interval: str) -> timedelta:
    if not interval:
        return timedelta(minutes=3)
    s = str(interval).strip().lower().replace(" ", "")

    for suffix in ["minutes", "minute", "mins", "min", "m"]:
        if s.endswith(suffix):
            val_str = s[:-len(suffix)]
            try:
                return timedelta(minutes=int(val_str))
            except ValueError:
                pass

    for suffix in ["hours", "hour", "hrs", "hr", "h"]:
        if s.endswith(suffix):
            val_str = s[:-len(suffix)]
            try:
                return timedelta(hours=int(val_str))
            except ValueError:
                pass

    for suffix in ["seconds", "second", "secs", "sec", "s"]:
        if s.endswith(suffix):
            val_str = s[:-len(suffix)]
            try:
                return timedelta(seconds=max(10, int(val_str)))
            except ValueError:
                pass

    if s == "daily" or s == "day":
        return timedelta(days=1)

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
    db = get_db()
    cursor = db["chats"].find(
        {"is_active": 1, "chat_type": {"$in": ["group", "supergroup"]}},
        {"_id": 0, "chat_id": 1, "chat_title": 1, "chat_type": 1}
    ).sort("chat_title", 1)
    return list(cursor)

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

def resolve_next_sticker(sticker_id: int, item: dict, db=None) -> tuple[str, str]:
    """
    Cycles to the next sticker in the pack so a different sticker is sent every interval.
    If it's a single sticker file_id, returns it directly.
    """
    target_db = db if db is not None else get_db()
    raw_url = item.get("sticker_url") or ""
    pack_name = item.get("sticker_pack_name") or extract_pack_name(raw_url)

    if pack_name:
        file_ids = get_pack_stickers(pack_name)
        if file_ids:
            curr_idx = item.get("current_index") or 0
            selected_file_id = file_ids[curr_idx % len(file_ids)]
            next_idx = (curr_idx + 1) % len(file_ids)

            target_db["scheduled_stickers"].update_one(
                {"id": sticker_id},
                {"$set": {"current_index": next_idx, "sticker_pack_name": pack_name}}
            )

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
    db = get_db()
    item = db["scheduled_stickers"].find_one({"id": sticker_id})
    if not item:
        return {"success": False, "error": "Scheduled sticker not found"}

    item = dict(item)
    item.pop("_id", None)
    all_gcs = get_active_group_chats()

    target_type = item.get("target_type") or "all_gc"
    targets = []
    if target_type == "all_gc" or item.get("chat_id") == 0:
        targets = all_gcs
    elif target_type == "selected" and item.get("target_chat_ids"):
        try:
            raw_ids = item["target_chat_ids"]
            sel_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
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
    sticker_to_send, pack_note = resolve_next_sticker(sticker_id, item, db=db)

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        cid = gc["chat_id"]
        title = gc.get("chat_title") or f"Group {cid}"
        result = send_sticker_api(cid, sticker_to_send)
        is_ok = result.get("ok", False)
        status = "success" if is_ok else "failed"
        details = f"{pack_note} delivered" if is_ok else result.get("description", result.get("error", "Unknown error"))

        if is_ok:
            success_count += 1
        else:
            fail_count += 1

        log_id = get_next_sequence("sticker_send_logs", db=db)
        db["sticker_send_logs"].insert_one({
            "id": log_id,
            "scheduled_id": sticker_id,
            "chat_id": cid,
            "chat_title": title,
            "sticker_url": sticker_to_send,
            "sent_at": now_iso,
            "status": status,
            "details": details,
        })

        results.append({"chat_id": cid, "chat_title": title, "ok": is_ok, "details": details})

    if success_count > 0:
        db["scheduled_stickers"].update_one(
            {"id": sticker_id},
            {"$set": {"last_sent_at": now_iso, "updated_at": now_iso}}
        )

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
    db = get_db()
    cursor = db["scheduled_stickers"].find({"status": "active"})
    active_items = []
    for doc in cursor:
        d = dict(doc)
        d.pop("_id", None)
        active_items.append(d)

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

        # 2. Strict time gap check
        if last_sent_dt:
            min_cooldown_seconds = max(10, interval_delta.total_seconds() - 15)
            elapsed_seconds = (now - last_sent_dt).total_seconds()
            if elapsed_seconds < min_cooldown_seconds:
                continue

        lease_id = claim_scheduled_job("scheduled_stickers", item["id"], item.get("scheduled_time"))
        if not lease_id:
            continue

        try:
            send_res = send_now(item["id"])
            results.append({"id": item["id"], "result": send_res})

            next_dt_str = (datetime.now() + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")
            db["scheduled_stickers"].update_one(
                {"id": item["id"], "dispatch_lease_id": lease_id},
                {
                    "$set": {
                        "scheduled_time": next_dt_str,
                        "updated_at": datetime.now().isoformat(),
                    },
                    "$unset": {"dispatch_lease_id": "", "dispatch_lease_until": ""},
                },
            )
        except Exception:
            release_scheduled_job("scheduled_stickers", item["id"], lease_id)
            raise

    return results

def list_all():
    init_tables()
    db = get_db()
    stickers = []
    for doc in db["scheduled_stickers"].find().sort("id", -1):
        d = dict(doc)
        d.pop("_id", None)
        stickers.append(d)

    logs = []
    for doc in db["sticker_send_logs"].find().sort("id", -1).limit(50):
        d = dict(doc)
        d.pop("_id", None)
        logs.append(d)

    chats = get_active_group_chats()

    return {
        "scheduled_stickers": stickers,
        "logs": logs,
        "chats": chats,
        "total_gcs": len(chats),
        "server_time": datetime.now().isoformat(),
    }

def add_sticker(data: dict):
    init_tables()
    db = get_db()

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
        chat_row = db["chats"].find_one({"chat_id": chat_id})
        chat_title = chat_row.get("chat_title") if chat_row else f"Group {chat_id}"

    pack_name = extract_pack_name(sticker_url)

    interval_delta = parse_interval_to_timedelta(repeat_interval)
    now_dt = datetime.now()
    next_time_str = (now_dt + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")

    new_id = get_next_sequence("scheduled_stickers", db=db)
    now_iso = now_dt.isoformat()

    db["scheduled_stickers"].insert_one({
        "id": new_id,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "sticker_url": sticker_url,
        "sticker_name": sticker_name,
        "target_type": target_type,
        "target_chat_ids": target_chat_ids,
        "schedule_type": "recurring",
        "scheduled_time": next_time_str,
        "repeat_interval": repeat_interval,
        "status": "active",
        "sticker_pack_name": pack_name,
        "current_index": 0,
        "created_at": now_iso,
        "updated_at": now_iso,
    })

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
    db = get_db()
    existing = db["scheduled_stickers"].find_one({"id": sticker_id})
    if not existing:
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
        chat_row = db["chats"].find_one({"chat_id": chat_id})
        chat_title = chat_row.get("chat_title") if chat_row else f"Group {chat_id}"

    pack_name = extract_pack_name(sticker_url)
    interval_delta = parse_interval_to_timedelta(repeat_interval)
    next_time_str = (datetime.now() + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")
    now_iso = datetime.now().isoformat()

    db["scheduled_stickers"].update_one(
        {"id": sticker_id},
        {
            "$set": {
                "target_type": target_type,
                "chat_id": chat_id,
                "chat_title": chat_title,
                "target_chat_ids": target_chat_ids,
                "sticker_url": sticker_url,
                "sticker_name": sticker_name,
                "repeat_interval": repeat_interval,
                "status": status,
                "sticker_pack_name": pack_name,
                "scheduled_time": next_time_str,
                "updated_at": now_iso,
            }
        }
    )

    return {"success": True, "id": sticker_id, "message": "Scheduled sticker updated successfully"}

def delete_sticker(sticker_id: int):
    init_tables()
    db = get_db()
    db["scheduled_stickers"].delete_one({"id": sticker_id})
    db["sticker_send_logs"].delete_many({"scheduled_id": sticker_id})
    return {"success": True, "message": f"Deleted scheduled sticker {sticker_id}"}

def toggle_status(sticker_id: int, new_status: str):
    init_tables()
    db = get_db()
    now_iso = datetime.now().isoformat()

    if new_status == 'active':
        row = db["scheduled_stickers"].find_one({"id": sticker_id})
        interval = row.get("repeat_interval", "3min") if row else "3min"
        interval_delta = parse_interval_to_timedelta(interval)
        next_time_str = (datetime.now() + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")

        db["scheduled_stickers"].update_one(
            {"id": sticker_id},
            {"$set": {"status": "active", "scheduled_time": next_time_str, "updated_at": now_iso}}
        )
    else:
        db["scheduled_stickers"].update_one(
            {"id": sticker_id},
            {"$set": {"status": new_status, "updated_at": now_iso}}
        )

    return {"success": True, "status": new_status}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--list":
            print(json.dumps(list_all()))
        elif cmd == "--add":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(add_sticker(json.loads(raw))))
        elif cmd == "--edit" and len(sys.argv) > 2:
            raw = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(edit_sticker(int(sys.argv[2]), json.loads(raw))))
        elif cmd == "--delete" and len(sys.argv) > 2:
            print(json.dumps(delete_sticker(int(sys.argv[2]))))
        elif cmd == "--toggle" and len(sys.argv) > 3:
            print(json.dumps(toggle_status(int(sys.argv[2]), sys.argv[3])))
        elif cmd == "--send-now" and len(sys.argv) > 2:
            print(json.dumps(send_now(int(sys.argv[2]))))
    else:
        print(json.dumps(list_all()))
