import os
import sys
import json
import random
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from database import get_db, get_next_sequence, get_db_path

def get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

DEFAULT_SEEDS = [
    # Shayari
    {
        "category": "shayari",
        "content": "हज़ारों ख़्वाहिशें ऐसी कि हर ख़्वाहिश पे दम निकले,\nबहुत निकले मिरे अरमान लेकिन फिर भी कम निकले।",
        "author": "Mirza Ghalib",
        "language": "Hindi / Urdu",
        "tags": "Classic, Romantic, Soulful"
    },
    {
        "category": "shayari",
        "content": "कुछ तो मजबूरियाँ रही होंगी,\nयूँ ही कोई बेवफ़ा नहीं होता।\nजी बहुत चाहता है सच बोलें,\nक्या करें हौसला नहीं होता।",
        "author": "Bashir Badr",
        "language": "Hindi / Urdu",
        "tags": "Emotional, Love, Life"
    },
    {
        "category": "shayari",
        "content": "तेरी उम्मीद तेरा इंतज़ार करते हैं,\nऐ सनम हम तो सिर्फ़ तुमसे प्यार करते हैं।\nएक बार मुस्कुरा कर देख लो हमें,\nहम अपनी पूरी ज़िन्दगी तुम्हारे नाम करते हैं।",
        "author": "Anonymous",
        "language": "Hindi",
        "tags": "Romantic, Love, Dosti"
    },
    # Quotes
    {
        "category": "quote",
        "content": "The secret of getting ahead is getting started. The secret of getting started is breaking your complex overwhelming tasks into small manageable tasks.",
        "author": "Mark Twain",
        "language": "English",
        "tags": "Motivation, Success"
    },
    {
        "category": "quote",
        "content": "Your time is limited, so don't waste it living someone else's life. Have the courage to follow your heart and intuition.",
        "author": "Steve Jobs",
        "language": "English",
        "tags": "Inspiration, Wisdom"
    },
    {
        "category": "quote",
        "content": "मंज़िल उन्हीं को मिलती है, जिनके सपनों में जान होती है,\nपंख से कुछ नहीं होता, हौसलों से उड़ान होती है।",
        "author": "Anonymous",
        "language": "Hindi",
        "tags": "Motivation, Ambition"
    },
    # Jokes
    {
        "category": "joke",
        "content": "टीचर: बताओ न्यूटन का चौथा नियम क्या है?\nछात्र: जब परीक्षा सर पर हो, तब दिमाग़ का काम करना बंद हो जाना ही चौथा नियम है! 😂",
        "author": "Classroom Fun",
        "language": "Hindi",
        "tags": "Student, Exam, Laugh"
    },
    {
        "category": "joke",
        "content": "Doctor: How is your headache now?\nPatient: Doctor, she went to her mother's house yesterday! 🤣",
        "author": "Classic Wit",
        "language": "English",
        "tags": "Marriage, Laugh, Funny"
    },
    # Poems
    {
        "category": "poem",
        "content": "लहरों से डर कर नौका पार नहीं होती,\nकोशिश करने वालों की कभी हार नहीं होती।\nनन्हीं चींटी जब दाना लेकर चलती है,\nचढ़ती दीवारों पर, सौ बार फिसलती है।\nमन का विश्वास रगों में साहस भरता है,\nचढ़कर गिरना, गिरकर चढ़ना न अखरता है।\nआख़िर उसकी मेहनत बेकार नहीं होती,\nकोशिश करने वालों की कभी हार नहीं होती।",
        "author": "Harivansh Rai Bachchan",
        "language": "Hindi",
        "tags": "Courage, Perseverance, Classic"
    },
    # Memes / Banter
    {
        "category": "meme",
        "content": "Me: Tomorrow I will wake up at 5 AM and completely fix my entire life.\nAlarm at 5 AM: *rings*\nMe: Who made this ridiculous plan anyway? 😴🛌",
        "author": "Relatable Internet",
        "language": "English",
        "tags": "Sleep, Procrastination, Relatable"
    },
    # Roast / Savage
    {
        "category": "roast",
        "content": "आइना भी जब तुम्हारी शक्ल देखता है,\nतो सोचता है कि काश मैं चश्मा होता ताकि धुंधला देख पाता! 🔥😎",
        "author": "Friendly Banter",
        "language": "Hindi",
        "tags": "Banter, Savage, Fun"
    },
    # Pickup Line
    {
        "category": "pickup_line",
        "content": "Are you a magician? Because whenever I look around this whole group chat, everyone disappears and there's only you. ✨",
        "author": "Smooth Operator",
        "language": "English",
        "tags": "Cheesy, Witty, Fun"
    }
]

def init_tables():
    db = get_db()
    db["shayari_content"].create_index("id", unique=True)
    db["shayari_content"].create_index("category")
    db["scheduled_shayari"].create_index("id", unique=True)
    db["scheduled_shayari"].create_index("status")
    db["shayari_send_logs"].create_index("id", unique=True)
    db["shayari_send_logs"].create_index("scheduled_id")

    # Seed initial items if empty
    if db["shayari_content"].count_documents({}) == 0:
        now_iso = datetime.now().isoformat()
        for seed in DEFAULT_SEEDS:
            new_id = get_next_sequence("shayari_content", db=db)
            db["shayari_content"].insert_one({
                "id": new_id,
                "category": seed["category"],
                "content": seed["content"],
                "author": seed.get("author", "Anonymous"),
                "language": seed.get("language", "Hindi / English"),
                "media_url": seed.get("media_url", ""),
                "tags": seed.get("tags", ""),
                "created_at": now_iso,
                "updated_at": now_iso,
            })

def parse_interval_to_timedelta(interval: str) -> timedelta:
    if not interval or interval == "none":
        return timedelta(minutes=30)
    s = str(interval).strip().lower().replace(" ", "")
    if s == "daily" or s == "day":
        return timedelta(days=1)
    if s == "weekly" or s == "week":
        return timedelta(days=7)

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

def get_active_group_chats():
    db = get_db()
    cursor = db["chats"].find(
        {"is_active": 1, "chat_type": {"$in": ["group", "supergroup"]}},
        {"_id": 0, "chat_id": 1, "chat_title": 1, "chat_type": 1}
    ).sort("chat_title", 1)
    return list(cursor)

def format_shayari_message(category: str, content: str, author: str = None) -> str:
    cat_headers = {
        "shayari": "📜 Shayari (शायरी)",
        "quote": "💡 Thought of the Day (अनमोल विचार)",
        "joke": "😂 Daily Joke (हँसी के फुहारे)",
        "meme": "🎭 Meme Alert (मीम)",
        "roast": "🔥 Savage Roast / Banter",
        "poem": "✍️ Poetry & Verse (कविता)",
        "pickup_line": "✨ Smooth Pickup Line",
    }
    header = cat_headers.get(category.lower(), "📜 Special Post")
    author_line = f"\n\n— {author}" if author and author != "Anonymous" else ""
    return f"{header}\n\n{content}{author_line}\n\n🤖 @Ms_Waguri_bot"

def send_telegram_message(chat_id: int, text: str) -> dict:
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False
    }

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return json.loads(err_body)
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def broadcast_scheduled_shayari(scheduled_id: int) -> dict:
    init_tables()
    db = get_db()
    row = db["scheduled_shayari"].find_one({"id": scheduled_id})
    if not row:
        return {"success": False, "error": "Scheduled item not found"}

    item = dict(row)
    item.pop("_id", None)
    category = item.get("category", "all")
    content_id = item.get("content_id")
    custom_text = item.get("custom_text")

    content_to_send = ""
    author_to_send = "Anonymous"
    actual_category = category

    if custom_text and custom_text.strip():
        content_to_send = custom_text.strip()
        author_to_send = "Admin"
    elif content_id:
        c_row = db["shayari_content"].find_one({"id": content_id})
        if c_row:
            content_to_send = c_row["content"]
            author_to_send = c_row.get("author", "Anonymous")
            actual_category = c_row.get("category", category)
    else:
        # Rotate from category
        match_query = {} if (category == "all" or not category) else {"category": category}
        pipeline = [{"$match": match_query}, {"$sample": {"size": 1}}]
        samples = list(db["shayari_content"].aggregate(pipeline))
        if samples:
            c_dict = samples[0]
            content_to_send = c_dict["content"]
            author_to_send = c_dict.get("author", "Anonymous")
            actual_category = c_dict.get("category", category)
            content_id = c_dict["id"]

    if not content_to_send:
        return {"success": False, "error": "No content available to send"}

    message_text = format_shayari_message(actual_category, content_to_send, author_to_send)

    all_gcs = get_active_group_chats()
    target_type = item.get("target_type", "all_gc")
    targets = []
    if target_type == "selected" and item.get("target_chat_ids"):
        try:
            raw_ids = item["target_chat_ids"]
            sel_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
            targets = [g for g in all_gcs if g["chat_id"] in sel_ids]
        except Exception:
            targets = all_gcs
    else:
        targets = all_gcs

    if not targets:
        cursor = db["chats"].find({"is_active": 1}, {"_id": 0, "chat_id": 1, "chat_title": 1, "chat_type": 1}).limit(5)
        targets = list(cursor)

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        cid = gc["chat_id"]
        title = gc.get("chat_title") or f"Chat {cid}"
        res = send_telegram_message(cid, message_text)
        is_ok = res.get("ok", False)
        status = "success" if is_ok else "failed"
        details = "Delivered to GC" if is_ok else res.get("description", res.get("error", "Failed"))

        if is_ok:
            success_count += 1
        else:
            fail_count += 1

        log_id = get_next_sequence("shayari_send_logs", db=db)
        db["shayari_send_logs"].insert_one({
            "id": log_id,
            "scheduled_id": scheduled_id,
            "content_id": content_id,
            "category": actual_category,
            "chat_id": cid,
            "chat_title": title,
            "sent_at": now_iso,
            "status": status,
            "details": details,
        })

        results.append({"chat_id": cid, "chat_title": title, "ok": is_ok, "details": details})

    new_total = (item.get("total_delivered") or 0) + success_count
    db["scheduled_shayari"].update_one(
        {"id": scheduled_id},
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
        "scheduled_id": scheduled_id,
        "total_targets": len(targets),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
        "sent_at": now_iso,
    }

def process_due_shayari():
    init_tables()
    db = get_db()
    cursor = db["scheduled_shayari"].find({"status": "active"})
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

        res = broadcast_scheduled_shayari(item["id"])
        results.append({"id": item["id"], "result": res})

        # Recurrence handling
        if item.get("schedule_type") == "recurring":
            next_time_str = (datetime.now() + interval_delta).strftime("%Y-%m-%dT%H:%M:%S")
            db["scheduled_shayari"].update_one(
                {"id": item["id"]},
                {"$set": {"scheduled_time": next_time_str, "updated_at": datetime.now().isoformat()}}
            )
        else:
            db["scheduled_shayari"].update_one(
                {"id": item["id"]},
                {"$set": {"status": "completed", "updated_at": datetime.now().isoformat()}}
            )

    return results

def list_all():
    init_tables()
    try:
        process_due_shayari()
    except Exception:
        pass

    db = get_db()
    content_list = []
    for doc in db["shayari_content"].find().sort("id", -1):
        d = dict(doc)
        d.pop("_id", None)
        content_list.append(d)

    schedules = []
    for doc in db["scheduled_shayari"].find().sort("id", -1):
        d = dict(doc)
        d.pop("_id", None)
        schedules.append(d)

    logs = []
    for doc in db["shayari_send_logs"].find().sort("id", -1).limit(50):
        d = dict(doc)
        d.pop("_id", None)
        logs.append(d)

    chats = []
    for doc in db["chats"].find({"is_active": 1}).sort("chat_title", 1):
        d = dict(doc)
        d.pop("_id", None)
        chats.append(d)

    return {
        "content_items": content_list,
        "scheduled": schedules,
        "logs": logs,
        "chats": chats,
        "total_content": len(content_list),
        "total_gcs": len([c for c in chats if c.get("chat_type") in ("group", "supergroup")]),
        "server_time": datetime.now().isoformat(),
    }

def add_item(data: dict):
    init_tables()
    db = get_db()
    cat = data.get("category", "shayari").strip() or "shayari"
    content = data.get("content", "").strip()
    author = data.get("author", "").strip() or "Anonymous"
    lang = data.get("language", "Hindi / English").strip()
    media_url = data.get("media_url", "").strip()
    tags = data.get("tags", "").strip()
    now_iso = datetime.now().isoformat()

    new_id = get_next_sequence("shayari_content", db=db)
    db["shayari_content"].insert_one({
        "id": new_id,
        "category": cat,
        "content": content,
        "author": author,
        "language": lang,
        "media_url": media_url,
        "tags": tags,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    return {"success": True, "id": new_id, "message": "Content item added successfully"}

def edit_item(item_id: int, data: dict):
    init_tables()
    db = get_db()
    existing = db["shayari_content"].find_one({"id": item_id})
    if not existing:
        return {"success": False, "error": f"Content item #{item_id} not found"}

    cat = data.get("category", "shayari").strip() or "shayari"
    content = data.get("content", "").strip()
    author = data.get("author", "").strip() or "Anonymous"
    lang = data.get("language", "Hindi / English").strip()
    media_url = data.get("media_url", "").strip()
    tags = data.get("tags", "").strip()
    now_iso = datetime.now().isoformat()

    db["shayari_content"].update_one(
        {"id": item_id},
        {
            "$set": {
                "category": cat,
                "content": content,
                "author": author,
                "language": lang,
                "media_url": media_url,
                "tags": tags,
                "updated_at": now_iso,
            }
        }
    )
    return {"success": True, "id": item_id, "message": "Content item updated successfully"}

def delete_item(item_id: int):
    init_tables()
    db = get_db()
    db["shayari_content"].delete_one({"id": item_id})
    return {"success": True, "message": f"Deleted content item {item_id}"}

def add_scheduled_shayari(data: dict):
    init_tables()
    db = get_db()
    title = data.get("title", "").strip() or "Daily Shayari Broadcast"
    category = data.get("category", "all").strip() or "all"
    content_id = data.get("content_id")
    if content_id is not None and str(content_id).strip() != "":
        content_id = int(content_id)
    else:
        content_id = None

    custom_text = data.get("custom_text", "").strip() or None
    target_type = data.get("target_type", "all_gc")
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    schedule_type = data.get("schedule_type", "recurring")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "daily")
    now_iso = datetime.now().isoformat()

    new_id = get_next_sequence("scheduled_shayari", db=db)
    db["scheduled_shayari"].insert_one({
        "id": new_id,
        "title": title,
        "category": category,
        "content_id": content_id,
        "custom_text": custom_text,
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
    return {"success": True, "id": new_id, "message": "Scheduled Shayari broadcast created successfully"}

def edit_scheduled_shayari(scheduled_id: int, data: dict):
    init_tables()
    db = get_db()
    existing = db["scheduled_shayari"].find_one({"id": scheduled_id})
    if not existing:
        return {"success": False, "error": f"Scheduled broadcast #{scheduled_id} not found"}

    title = data.get("title", "").strip() or "Daily Shayari Broadcast"
    category = data.get("category", "all").strip() or "all"
    content_id = data.get("content_id")
    if content_id is not None and str(content_id).strip() != "":
        content_id = int(content_id)
    else:
        content_id = None

    custom_text = data.get("custom_text", "").strip() or None
    target_type = data.get("target_type", "all_gc")
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    schedule_type = data.get("schedule_type", "recurring")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "daily")
    status = data.get("status", "active")
    now_iso = datetime.now().isoformat()

    db["scheduled_shayari"].update_one(
        {"id": scheduled_id},
        {
            "$set": {
                "title": title,
                "category": category,
                "content_id": content_id,
                "custom_text": custom_text,
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
    return {"success": True, "id": scheduled_id, "message": "Scheduled Shayari broadcast updated successfully"}

def delete_scheduled_shayari(scheduled_id: int):
    init_tables()
    db = get_db()
    db["scheduled_shayari"].delete_one({"id": scheduled_id})
    db["shayari_send_logs"].delete_many({"scheduled_id": scheduled_id})
    return {"success": True, "message": f"Deleted scheduled broadcast {scheduled_id}"}

def toggle_scheduled_status(scheduled_id: int, new_status: str):
    init_tables()
    db = get_db()
    now_iso = datetime.now().isoformat()
    db["scheduled_shayari"].update_one(
        {"id": scheduled_id},
        {"$set": {"status": new_status, "updated_at": now_iso}}
    )
    return {"success": True, "status": new_status}

def broadcast_content(item_id: int, chat_id: str = "all_gc") -> dict:
    """Send shayari, quote, joke, or poem directly to Group Chats via Telegram Bot API"""
    init_tables()
    token = get_bot_token()
    if not token:
        return {"success": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    db = get_db()
    row = db["shayari_content"].find_one({"id": item_id})
    if not row:
        return {"success": False, "error": "Content item not found"}

    item = dict(row)
    telegram_text = format_shayari_message(item["category"], item["content"], item.get("author"))

    all_gcs = get_active_group_chats()
    if chat_id == "all_gc" or not chat_id:
        targets = all_gcs
    else:
        try:
            target_id = int(chat_id)
            targets = [g for g in all_gcs if g["chat_id"] == target_id]
            if not targets:
                targets = [{"chat_id": target_id, "chat_title": f"Chat {target_id}"}]
        except Exception:
            targets = all_gcs

    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        cid = gc["chat_id"]
        title = gc.get("chat_title") or f"Chat {cid}"
        res = send_telegram_message(cid, telegram_text)
        is_ok = res.get("ok", False)
        if is_ok:
            success_count += 1
            results.append({"chat_id": cid, "chat_title": title, "ok": True})
        else:
            fail_count += 1
            results.append({"chat_id": cid, "chat_title": title, "ok": False, "error": res.get("description", res.get("error"))})

    return {
        "success": success_count > 0,
        "total_targets": len(targets),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--list":
            print(json.dumps(list_all()))
        elif cmd == "--add":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(add_item(json.loads(raw))))
        elif cmd == "--edit-item" and len(sys.argv) > 2:
            raw = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(edit_item(int(sys.argv[2]), json.loads(raw))))
        elif cmd == "--delete" and len(sys.argv) > 2:
            print(json.dumps(delete_item(int(sys.argv[2]))))
        elif cmd == "--broadcast" and len(sys.argv) > 2:
            chat_target = sys.argv[3] if len(sys.argv) > 3 else "all_gc"
            print(json.dumps(broadcast_content(int(sys.argv[2]), chat_target)))
        elif cmd == "--add-schedule":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(add_scheduled_shayari(json.loads(raw))))
        elif cmd == "--edit-schedule" and len(sys.argv) > 2:
            raw = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(edit_scheduled_shayari(int(sys.argv[2]), json.loads(raw))))
        elif cmd == "--delete-schedule" and len(sys.argv) > 2:
            print(json.dumps(delete_scheduled_shayari(int(sys.argv[2]))))
        elif cmd == "--toggle-schedule" and len(sys.argv) > 3:
            print(json.dumps(toggle_scheduled_status(int(sys.argv[2]), sys.argv[3])))
        elif cmd == "--broadcast-schedule" and len(sys.argv) > 2:
            print(json.dumps(broadcast_scheduled_shayari(int(sys.argv[2]))))
    else:
        print(json.dumps(list_all()))
