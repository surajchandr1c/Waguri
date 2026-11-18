import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from database import claim_scheduled_job, get_db, get_next_sequence, get_db_path, release_scheduled_job

_tables_initialized = False

def get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

def init_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    db = get_db()
    db["scheduled_promotions"].create_index("id", unique=True)
    db["scheduled_promotions"].create_index("status")
    db["promotion_send_logs"].create_index("id", unique=True)
    db["promotion_send_logs"].create_index("promotion_id")
    _tables_initialized = True

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
    db = get_db()
    cursor = db["chats"].find(
        {"is_active": 1, "chat_type": {"$in": ["group", "supergroup"]}},
        {"_id": 0, "chat_id": 1, "chat_title": 1, "chat_type": 1}
    ).sort("chat_title", 1)
    return list(cursor)

def broadcast_promotion(promotion_id: int) -> dict:
    init_tables()
    db = get_db()
    item = db["scheduled_promotions"].find_one({"id": promotion_id})
    if not item:
        return {"success": False, "error": "Promotion not found"}

    item.pop("_id", None)
    all_gcs = get_active_group_chats()

    # Determine target GCs
    targets = []
    if item.get("target_type") == "selected" and item.get("target_chat_ids"):
        try:
            raw_ids = item["target_chat_ids"]
            selected_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
            targets = [g for g in all_gcs if g["chat_id"] in selected_ids]
        except Exception:
            targets = all_gcs
    else:
        targets = all_gcs

    if not targets:
        # Fallback to any active chats
        cursor = db["chats"].find({"is_active": 1}, {"_id": 0, "chat_id": 1, "chat_title": 1, "chat_type": 1}).limit(5)
        targets = list(cursor)

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        chat_id = gc["chat_id"]
        chat_title = gc.get("chat_title") or f"Chat {chat_id}"

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

        log_id = get_next_sequence("promotion_send_logs", db=db)
        db["promotion_send_logs"].insert_one({
            "id": log_id,
            "promotion_id": promotion_id,
            "chat_id": chat_id,
            "chat_title": chat_title,
            "sent_at": now_iso,
            "status": status,
            "details": details,
        })

        results.append({
            "chat_id": chat_id,
            "chat_title": chat_title,
            "ok": is_ok,
            "details": details
        })

    # Update promotion metadata
    new_total = (item.get("total_delivered") or 0) + success_count
    db["scheduled_promotions"].update_one(
        {"id": promotion_id},
        {
            "$set": {
                "last_sent_at": now_iso,
                "total_delivered": new_total,
                "updated_at": now_iso,
            }
        }
    )

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

def compute_next_datetime(base_dt_str: str, interval_str: str) -> str:
    base_dt = parse_dt(base_dt_str) or datetime.now()
    delta = parse_interval_to_timedelta(interval_str)
    next_dt = base_dt + delta
    now = datetime.now()
    while next_dt <= now:
        next_dt += delta
    return next_dt.strftime("%Y-%m-%dT%H:%M:%S")

def process_due_promotions():
    init_tables()
    db = get_db()
    cursor = db["scheduled_promotions"].find({"status": "active"})
    active_items = []
    for doc in cursor:
        d = dict(doc)
        d.pop("_id", None)
        active_items.append(d)

    now = datetime.now()
    results = []

    for item in active_items:
        interval_str = item.get("repeat_interval", "daily")
        interval_delta = parse_interval_to_timedelta(interval_str)

        sched_dt = parse_dt(item.get("scheduled_time")) or now
        last_sent_dt = parse_dt(item.get("last_sent_at"))

        # 1. Has scheduled time arrived?
        if now < sched_dt:
            continue

        # 2. Strict gap check
        if last_sent_dt:
            min_cooldown_seconds = max(10, interval_delta.total_seconds() - 15)
            if (now - last_sent_dt).total_seconds() < min_cooldown_seconds:
                continue

        lease_id = claim_scheduled_job("scheduled_promotions", item["id"], item.get("scheduled_time"))
        if not lease_id:
            continue

        try:
            res = broadcast_promotion(item["id"])
            results.append({"id": item["id"], "result": res})

            update_fields = {"updated_at": datetime.now().isoformat()}
            if item.get("schedule_type") == "recurring":
                update_fields["scheduled_time"] = (
                    datetime.now() + interval_delta
                ).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                update_fields["status"] = "completed"
            db["scheduled_promotions"].update_one(
                {"id": item["id"], "dispatch_lease_id": lease_id},
                {
                    "$set": update_fields,
                    "$unset": {"dispatch_lease_id": "", "dispatch_lease_until": ""},
                },
            )
        except Exception:
            release_scheduled_job("scheduled_promotions", item["id"], lease_id)
            raise

    return results

def list_all():
    init_tables()
    db = get_db()
    promotions = []
    for doc in db["scheduled_promotions"].find().sort("id", -1):
        d = dict(doc)
        d.pop("_id", None)
        promotions.append(d)

    logs = []
    for doc in db["promotion_send_logs"].find().sort("id", -1).limit(50):
        d = dict(doc)
        d.pop("_id", None)
        logs.append(d)

    # Available Group Chats
    chats = []
    for doc in db["chats"].find({"is_active": 1}).sort("chat_title", 1):
        d = dict(doc)
        d.pop("_id", None)
        chats.append(d)

    return {
        "promotions": promotions,
        "logs": logs,
        "chats": chats,
        "total_gcs": len([c for c in chats if c.get("chat_type") in ("group", "supergroup")]),
        "server_time": datetime.now().isoformat(),
    }

def add_promotion(data: dict):
    init_tables()
    db = get_db()

    title = data.get("title", "").strip() or "GC Promotional Announcement"
    message = data.get("message", "").strip()
    link_url = data.get("link_url", "").strip()
    button_text = data.get("button_text", "").strip() or "Visit Website"
    target_type = data.get("target_type", "all_gc")
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    schedule_type = data.get("schedule_type", "once")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "none")

    new_id = get_next_sequence("scheduled_promotions", db=db)
    now_iso = datetime.now().isoformat()

    db["scheduled_promotions"].insert_one({
        "id": new_id,
        "title": title,
        "message": message,
        "link_url": link_url,
        "button_text": button_text,
        "target_type": target_type,
        "target_chat_ids": target_chat_ids,
        "schedule_type": schedule_type,
        "scheduled_time": scheduled_time,
        "repeat_interval": repeat_interval,
        "status": "active",
        "total_delivered": 0,
        "last_sent_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    return {"success": True, "id": new_id, "message": "Promotional broadcast scheduled successfully"}

def delete_promotion(promotion_id: int):
    init_tables()
    db = get_db()
    db["scheduled_promotions"].delete_one({"id": promotion_id})
    db["promotion_send_logs"].delete_many({"promotion_id": promotion_id})
    return {"success": True, "message": f"Deleted promotion {promotion_id}"}

def toggle_status(promotion_id: int, new_status: str):
    init_tables()
    db = get_db()
    now_iso = datetime.now().isoformat()
    db["scheduled_promotions"].update_one(
        {"id": promotion_id},
        {"$set": {"status": new_status, "updated_at": now_iso}}
    )
    return {"success": True, "status": new_status}

def edit_promotion(promotion_id: int, data: dict):
    init_tables()
    db = get_db()
    existing = db["scheduled_promotions"].find_one({"id": promotion_id})
    if not existing:
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
    now_iso = datetime.now().isoformat()

    db["scheduled_promotions"].update_one(
        {"id": promotion_id},
        {
            "$set": {
                "title": title,
                "message": message,
                "link_url": link_url,
                "button_text": button_text,
                "target_type": target_type,
                "target_chat_ids": target_chat_ids,
                "schedule_type": schedule_type,
                "scheduled_time": scheduled_time,
                "repeat_interval": repeat_interval,
                "status": status,
                "updated_at": now_iso,
            }
        }
    )

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
