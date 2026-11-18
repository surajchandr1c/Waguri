import os
import sys
import json
import sqlite3
import random
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
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
        "tags": "Motivation, Hardwork"
    },
    # Jokes
    {
        "category": "joke",
        "content": "Teacher: 1 se 10 tak ginti sunao.\nPappu: 1, 2, 3, 4, 5, 7, 8, 9, 10.\nTeacher: 6 kahan gaya?\nPappu: Ji wo kal news mein bataya tha ki 6 log theek ho kar ghar chale gaye!",
        "author": "Pappu Jokes",
        "language": "Hinglish",
        "tags": "Comedy, Laughs, School"
    },
    {
        "category": "joke",
        "content": "Doctor: Aapka vajan 10 kilo badh gaya hai, exercise shuru karo.\nPatient: Kaunsi exercise doctor sahab?\nDoctor: Mundi daayein se baayein hilana, jab koi khana offer kare!",
        "author": "Desi Humor",
        "language": "Hinglish",
        "tags": "Doctor, Funny, Sarcasm"
    },
    # Memes / Media
    {
        "category": "meme",
        "content": "Programmer at 3:00 AM:\n'Why isn't this code working?'\n\nProgrammer at 3:05 AM:\n'Why IS this code working?!'",
        "author": "Dev Memes",
        "language": "English",
        "tags": "Tech, Relatable, Coding"
    },
    {
        "category": "meme",
        "content": "Me: 'I will go to sleep early tonight.'\nMy brain at 2:00 AM: 'Do penguins have knees?'",
        "author": "Late Night Thoughts",
        "language": "English",
        "tags": "Meme, Sleep, Relatable"
    },
    # Savage Roasts / Banter
    {
        "category": "roast",
        "content": "You bring everyone so much joy and happiness... especially when you leave the group chat.",
        "author": "Savage Bot",
        "language": "English",
        "tags": "Sarcasm, Roast, Banter"
    },
    {
        "category": "roast",
        "content": "I'd agree with you, but then we would both be completely wrong.",
        "author": "Banter King",
        "language": "English",
        "tags": "Savage, Comeback, Sarcasm"
    },
    {
        "category": "roast",
        "content": "Bhai tu chup hi raha kar, jab tu bolta hai toh lagta hai dimaag 2G network par chal raha hai.",
        "author": "Desi Roast",
        "language": "Hinglish",
        "tags": "Desi, Funny, Roast"
    },
    # Poems
    {
        "category": "poem",
        "content": "वो अफ़्साना जिसे अंजाम तक लाना न हो मुमकिन,\nउसे इक ख़ूबसूरत मोड़ देकर छोड़ना अच्छा।\nतअ'ल्लुक़ बोझ बन जाए तो उस का तोड़ना अच्छा।",
        "author": "Sahir Ludhianvi",
        "language": "Urdu / Hindi",
        "tags": "Poetry, Deep, Life"
    },
    {
        "category": "poem",
        "content": "Two roads diverged in a wood, and I—\nI took the one less traveled by,\nAnd that has made all the difference.",
        "author": "Robert Frost",
        "language": "English",
        "tags": "Classic, Life, Choices"
    },
    # Pickup Lines
    {
        "category": "pickup_line",
        "content": "Are you a magician? Because whenever I look at you, everyone else in the room disappears.",
        "author": "Smooth Operator",
        "language": "English",
        "tags": "Flirty, Cute, Romantic"
    },
    {
        "category": "pickup_line",
        "content": "Kya aapka naam Google hai? Kyunki jo bhi dhoondh raha tha, sab aapme mil gaya.",
        "author": "Desi Romance",
        "language": "Hinglish",
        "tags": "Desi, Flirty, Fun"
    },
    {
        "category": "pickup_line",
        "content": "Are you Wi-Fi? Because I'm definitely feeling a strong connection here.",
        "author": "Tech Romance",
        "language": "English",
        "tags": "Cheesy, Witty, Fun"
    }
]

def init_tables():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shayari_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        author TEXT,
        language TEXT DEFAULT 'Hindi / English',
        media_url TEXT,
        tags TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_shayari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'all',
        content_id INTEGER,
        custom_text TEXT,
        target_type TEXT DEFAULT 'all_gc',
        target_chat_ids TEXT,
        schedule_type TEXT DEFAULT 'recurring',
        scheduled_time TEXT NOT NULL,
        repeat_interval TEXT DEFAULT 'daily',
        status TEXT DEFAULT 'active',
        total_delivered INTEGER DEFAULT 0,
        last_sent_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS shayari_send_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheduled_id INTEGER,
        content_id INTEGER,
        category TEXT,
        chat_id INTEGER NOT NULL,
        chat_title TEXT NOT NULL,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'success',
        details TEXT
    )
    """)

    # Seed initial items if empty
    cur.execute("SELECT COUNT(*) FROM shayari_content")
    count = cur.fetchone()[0]
    if count == 0:
        for seed in DEFAULT_SEEDS:
            cur.execute("""
            INSERT INTO shayari_content (category, content, author, language, media_url, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                seed["category"],
                seed["content"],
                seed.get("author", "Anonymous"),
                seed.get("language", "Hindi / English"),
                seed.get("media_url", ""),
                seed.get("tags", "")
            ))
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
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM scheduled_shayari WHERE id = ? LIMIT 1", (scheduled_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Scheduled item not found"}

    item = dict(row)
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
        cur.execute("SELECT * FROM shayari_content WHERE id = ? LIMIT 1", (content_id,))
        c_row = cur.fetchone()
        if c_row:
            c_dict = dict(c_row)
            content_to_send = c_dict["content"]
            author_to_send = c_dict.get("author", "Anonymous")
            actual_category = c_dict.get("category", category)
    else:
        # Rotate from category
        if category == "all" or not category:
            cur.execute("SELECT * FROM shayari_content ORDER BY RANDOM() LIMIT 1")
        else:
            cur.execute("SELECT * FROM shayari_content WHERE category = ? ORDER BY RANDOM() LIMIT 1", (category,))
        c_row = cur.fetchone()
        if c_row:
            c_dict = dict(c_row)
            content_to_send = c_dict["content"]
            author_to_send = c_dict.get("author", "Anonymous")
            actual_category = c_dict.get("category", category)
            content_id = c_dict["id"]

    if not content_to_send:
        conn.close()
        return {"success": False, "error": "No content available to send"}

    message_text = format_shayari_message(actual_category, content_to_send, author_to_send)

    all_gcs = get_active_group_chats()
    target_type = item.get("target_type", "all_gc")
    targets = []
    if target_type == "selected" and item.get("target_chat_ids"):
        try:
            sel_ids = json.loads(item["target_chat_ids"])
            targets = [g for g in all_gcs if g["chat_id"] in sel_ids]
        except Exception:
            targets = all_gcs
    else:
        targets = all_gcs

    if not targets:
        cur.execute("SELECT chat_id, chat_title, chat_type FROM chats WHERE is_active = 1 LIMIT 5")
        targets = [dict(r) for r in cur.fetchall()]

    now_iso = datetime.now().isoformat()
    success_count = 0
    fail_count = 0
    results = []

    for gc in targets:
        cid = gc["chat_id"]
        title = gc["chat_title"]
        res = send_telegram_message(cid, message_text)
        is_ok = res.get("ok", False)
        status = "success" if is_ok else "failed"
        details = "Delivered to GC" if is_ok else res.get("description", res.get("error", "Failed"))

        if is_ok:
            success_count += 1
        else:
            fail_count += 1

        cur.execute("""
        INSERT INTO shayari_send_logs (scheduled_id, content_id, category, chat_id, chat_title, sent_at, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (scheduled_id, content_id, actual_category, cid, title, now_iso, status, details))

        results.append({"chat_id": cid, "chat_title": title, "ok": is_ok, "details": details})

    new_total = (item.get("total_delivered") or 0) + success_count
    cur.execute("""
    UPDATE scheduled_shayari
    SET last_sent_at = ?, total_delivered = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (now_iso, new_total, scheduled_id))

    conn.commit()
    conn.close()

    return {
        "success": success_count > 0,
        "scheduled_id": scheduled_id,
        "total_targets": len(targets),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
        "sent_at": now_iso
    }

def process_due_shayari():
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M")

    cur.execute("""
    SELECT * FROM scheduled_shayari
    WHERE status = 'active' AND scheduled_time <= ?
    """, (now_iso,))

    due_items = [dict(r) for r in cur.fetchall()]
    conn.close()

    results = []
    for item in due_items:
        last_sent = item.get("last_sent_at")
        if last_sent and last_sent[:16] >= item["scheduled_time"][:16]:
            continue

        send_res = broadcast_scheduled_shayari(item["id"])
        results.append({"id": item["id"], "result": send_res})

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        if item.get("schedule_type") == "recurring":
            interval = item.get("repeat_interval", "daily")
            next_time_str = compute_next_datetime(item["scheduled_time"], interval)

            cur.execute("""
            UPDATE scheduled_shayari
            SET scheduled_time = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (next_time_str, item["id"]))
        else:
            cur.execute("""
            UPDATE scheduled_shayari
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (item["id"],))

        conn.commit()
        conn.close()

    return results

def list_all():
    init_tables()
    try:
        process_due_shayari()
    except Exception:
        pass

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM shayari_content ORDER BY id DESC")
    items = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM scheduled_shayari ORDER BY id DESC")
    scheduled_items = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM shayari_send_logs ORDER BY id DESC LIMIT 50")
    logs = [dict(r) for r in cur.fetchall()]

    # Available Group Chats
    chats = get_active_group_chats()

    conn.close()

    category_counts = {}
    for item in items:
        cat = item.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "items": items,
        "scheduled_shayari": scheduled_items,
        "logs": logs,
        "total_count": len(items),
        "category_counts": category_counts,
        "chats": chats,
        "total_gcs": len(chats),
        "server_time": datetime.now().isoformat(),
    }

def add_item(data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    category = data.get("category", "shayari").lower().strip()
    content = data.get("content", "").strip()
    author = data.get("author", "").strip() or "Anonymous"
    language = data.get("language", "Hinglish").strip()
    media_url = data.get("media_url", "").strip()
    tags = data.get("tags", "").strip()

    if not content:
        conn.close()
        return {"success": False, "error": "Content cannot be empty"}

    cur.execute("""
    INSERT INTO shayari_content (category, content, author, language, media_url, tags)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (category, content, author, language, media_url, tags))

    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "id": new_id, "message": "Content added successfully"}

def edit_item(item_id: int, data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM shayari_content WHERE id = ?", (item_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": f"Content item #{item_id} not found"}

    category = data.get("category", "shayari").lower().strip()
    content = data.get("content", "").strip()
    author = data.get("author", "").strip() or "Anonymous"
    language = data.get("language", "Hinglish").strip()
    media_url = data.get("media_url", "").strip()
    tags = data.get("tags", "").strip()

    if not content:
        conn.close()
        return {"success": False, "error": "Content cannot be empty"}

    cur.execute("""
    UPDATE shayari_content
    SET category = ?, content = ?, author = ?, language = ?, media_url = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (category, content, author, language, media_url, tags, item_id))

    conn.commit()
    conn.close()
    return {"success": True, "id": item_id, "message": "Content updated successfully"}

def delete_item(item_id: int):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM shayari_content WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Deleted item {item_id}"}

def add_scheduled_shayari(data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    title = data.get("title", "").strip() or "Daily Shayari Broadcast"
    category = data.get("category", "all").strip().lower()
    content_id = data.get("content_id")
    if content_id is not None and content_id != "":
        content_id = int(content_id)
    else:
        content_id = None
    custom_text = data.get("custom_text", "").strip() or None
    target_type = data.get("target_type", "all_gc")
    target_chat_ids = json.dumps(data.get("target_chat_ids", []))
    schedule_type = data.get("schedule_type", "recurring")
    scheduled_time = data.get("scheduled_time", "").strip() or datetime.now().strftime("%Y-%m-%dT%H:%M")
    repeat_interval = data.get("repeat_interval", "daily")

    cur.execute("""
    INSERT INTO scheduled_shayari (title, category, content_id, custom_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (title, category, content_id, custom_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval))

    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "id": new_id, "message": "Scheduled Shayari broadcast created successfully"}

def edit_scheduled_shayari(scheduled_id: int, data: dict):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM scheduled_shayari WHERE id = ?", (scheduled_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": f"Scheduled broadcast #{scheduled_id} not found"}

    title = data.get("title", "").strip() or "Daily Shayari Broadcast"
    category = data.get("category", "all").strip().lower()
    content_id = data.get("content_id")
    if content_id is not None and content_id != "":
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

    cur.execute("""
    UPDATE scheduled_shayari
    SET title = ?, category = ?, content_id = ?, custom_text = ?, target_type = ?,
        target_chat_ids = ?, schedule_type = ?, scheduled_time = ?, repeat_interval = ?, status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (title, category, content_id, custom_text, target_type, target_chat_ids,
          schedule_type, scheduled_time, repeat_interval, status, scheduled_id))

    conn.commit()
    conn.close()
    return {"success": True, "id": scheduled_id, "message": "Scheduled Shayari broadcast updated successfully"}

def delete_scheduled_shayari(scheduled_id: int):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM scheduled_shayari WHERE id = ?", (scheduled_id,))
    cur.execute("DELETE FROM shayari_send_logs WHERE scheduled_id = ?", (scheduled_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Deleted scheduled broadcast {scheduled_id}"}

def toggle_scheduled_status(scheduled_id: int, new_status: str):
    init_tables()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE scheduled_shayari SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, scheduled_id))
    conn.commit()
    conn.close()
    return {"success": True, "status": new_status}

def broadcast_content(item_id: int, chat_id: str = "all_gc") -> dict:
    """Send shayari, quote, joke, or poem directly to Group Chats via Telegram Bot API"""
    init_tables()
    token = get_bot_token()
    if not token:
        return {"success": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM shayari_content WHERE id = ? LIMIT 1", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Content item not found"}

    item = dict(row)
    telegram_text = format_shayari_message(item["category"], item["content"], item.get("author"))

    all_gcs = get_active_group_chats()
    conn.close()

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
        title = gc["chat_title"]
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
