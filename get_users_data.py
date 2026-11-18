import sqlite3
import json
import os
import sys

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

def fetch_all():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(json.dumps({"error": f"Database not found at {db_path}"}))
        return

    file_size_kb = round(os.path.getsize(db_path) / 1024, 2)
    modified_time = os.path.getmtime(db_path)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def query_rows(sql, params=()):
        try:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            return []

    # STRICT FILTERING: Only return active users, channels, and group chats
    # Exclude disabled business connections (is_enabled=0) and inactive chats (is_active=0)
    business_connections = query_rows("SELECT * FROM business_connections WHERE is_enabled = 1")
    active_user_ids = {bc["user_id"] for bc in business_connections}

    chats = query_rows("SELECT * FROM chats WHERE is_active = 1")
    active_chat_ids = {c["chat_id"] for c in chats}

    personal_reply_settings = query_rows("SELECT * FROM personal_reply_settings WHERE is_enabled = 1")
    personal_reply_templates = query_rows("SELECT * FROM personal_reply_templates WHERE is_active = 1")

    business_first_contacts = query_rows(
        "SELECT * FROM business_first_contacts ORDER BY first_seen_at DESC"
    )
    business_reply_logs = query_rows(
        "SELECT * FROM business_reply_logs ORDER BY sent_at DESC"
    )

    chat_settings = query_rows(
        "SELECT cs.* FROM chat_settings cs JOIN chats c ON cs.chat_id = c.chat_id WHERE c.is_active = 1"
    )
    chat_statistics = query_rows(
        "SELECT cs.* FROM chat_statistics cs JOIN chats c ON cs.chat_id = c.chat_id WHERE c.is_active = 1"
    )
    chat_warnings = query_rows(
        "SELECT cw.* FROM chat_warnings cw JOIN chats c ON cw.chat_id = c.chat_id WHERE c.is_active = 1 ORDER BY cw.id DESC"
    )
    chat_moderation_logs = query_rows(
        "SELECT cml.* FROM chat_moderation_logs cml JOIN chats c ON cml.chat_id = c.chat_id WHERE c.is_active = 1 ORDER BY cml.id DESC"
    )
    chat_join_events = query_rows(
        "SELECT cje.* FROM chat_join_events cje JOIN chats c ON cje.chat_id = c.chat_id WHERE c.is_active = 1 ORDER BY cje.id DESC"
    )
    active_spam_incidents = query_rows(
        "SELECT asi.* FROM active_spam_incidents asi JOIN chats c ON asi.chat_id = c.chat_id WHERE c.is_active = 1 ORDER BY asi.last_message_time DESC"
    )

    cur.execute("SELECT count(*) FROM chat_spam_incidents")
    total_spam_incidents = cur.fetchone()[0]

    daily_moderation_stats = query_rows("SELECT * FROM daily_moderation_stats ORDER BY stat_date DESC")
    daily_stats_history = query_rows("SELECT * FROM daily_stats_history ORDER BY stat_date DESC")

    # Table counts
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_table_names = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]
    table_counts = {}
    for tbl in all_table_names:
        try:
            cur.execute(f'SELECT count(*) FROM "{tbl}"')
            table_counts[tbl] = cur.fetchone()[0]
        except Exception:
            table_counts[tbl] = 0

    # Only accounts that actually connected/added the bot on personal direct messages
    unique_user_ids = {bc["user_id"] for bc in business_connections if bc.get("is_enabled")}

    # Calculate real links deleted and messages deleted sums
    total_links_deleted = 0
    total_spam_deleted = 0
    total_messages_checked = 0
    total_warnings_issued = len(chat_warnings)
    for stat in chat_statistics:
        total_links_deleted += stat.get("links_deleted") or 0
        total_spam_deleted += stat.get("spam_deleted") or 0
        total_messages_checked += stat.get("total_messages_checked") or 0

    if daily_moderation_stats:
        d_today = daily_moderation_stats[0]
        daily_links = d_today.get("links_deleted", 0)
        daily_msgs = d_today.get("messages_deleted", 0)
        daily_blocked = d_today.get("users_blocked", 0)
    else:
        daily_links = total_links_deleted
        daily_msgs = total_spam_deleted
        daily_blocked = len({w["user_id"] for w in chat_warnings if w.get("warning_number", 0) >= 2})

    data = {
        "db_info": {
            "path": db_path,
            "size_kb": file_size_kb,
            "modified_time": modified_time,
            "wal_mode": True,
        },
        "table_counts": table_counts,
        "unique_users_count": len(unique_user_ids),
        "total_messages_checked": total_messages_checked,
        "total_links_deleted": total_links_deleted,
        "total_spam_deleted": total_spam_deleted,
        "total_warnings_issued": total_warnings_issued,
        "total_spam_incidents": total_spam_incidents,
        "business_connections": business_connections,
        "personal_reply_settings": personal_reply_settings,
        "personal_reply_templates": personal_reply_templates,
        "business_first_contacts": business_first_contacts,
        "business_reply_logs": business_reply_logs,
        "chats": chats,
        "chat_settings": chat_settings,
        "chat_statistics": chat_statistics,
        "chat_warnings": chat_warnings,
        "chat_moderation_logs": chat_moderation_logs,
        "chat_join_events": chat_join_events,
        "active_spam_incidents": active_spam_incidents,
        "daily_moderation_stats": daily_moderation_stats,
        "daily_stats_history": daily_stats_history,
    }
    conn.close()
    print(json.dumps(data))

def remove_entity(entity_type: str, entity_id_str: str):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(json.dumps({"error": f"Database not found at {db_path}"}))
        return

    try:
        entity_id = int(entity_id_str)
    except ValueError:
        print(json.dumps({"error": f"Invalid ID: {entity_id_str}"}))
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")

    removed_records = 0
    clean_type = entity_type.lower().strip()

    if clean_type in ("user", "business_user", "tenant"):
        cur.execute("UPDATE business_connections SET is_enabled = 0 WHERE user_id = ?", (entity_id,))
        removed_records += cur.rowcount
        cur.execute("UPDATE personal_reply_settings SET is_enabled = 0 WHERE user_id = ?", (entity_id,))
        cur.execute("DELETE FROM chat_warnings WHERE user_id = ?", (entity_id,))
        cur.execute("DELETE FROM chat_join_events WHERE user_id = ?", (entity_id,))
        conn.commit()
    elif clean_type in ("gc", "group", "supergroup", "channel", "chat"):
        cur.execute("UPDATE chats SET is_active = 0 WHERE chat_id = ?", (entity_id,))
        removed_records += cur.rowcount
        if cur.rowcount == 0:
            neg_id = -abs(entity_id)
            cur.execute("UPDATE chats SET is_active = 0 WHERE chat_id = ?", (neg_id,))
            removed_records += cur.rowcount
        conn.commit()

    conn.close()
    print(json.dumps({
        "success": True,
        "type": clean_type,
        "id": entity_id,
        "records_updated": removed_records,
        "message": f"Successfully removed bot from {clean_type} {entity_id} and purged data from active views."
    }))

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--remove":
        remove_entity(sys.argv[2], sys.argv[3])
    else:
        fetch_all()
