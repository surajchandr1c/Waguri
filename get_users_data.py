import json
import os
import sys
import time

from database import get_db, get_db_path

def fetch_all():
    db = get_db()

    # Query all active collections
    def get_docs(collection_name, filter_q=None, sort_field=None, sort_dir=-1, limit=0):
        cur = db[collection_name].find(filter_q or {})
        if sort_field:
            cur = cur.sort(sort_field, sort_dir)
        if limit > 0:
            cur = cur.limit(limit)
        results = []
        for doc in cur:
            d = dict(doc)
            d.pop("_id", None)
            results.append(d)
        return results

    # STRICT FILTERING: Only return active users, channels, and group chats
    business_connections = get_docs("business_connections", {"is_enabled": 1})
    chats = get_docs("chats", {"is_active": 1})
    active_chat_ids = {c["chat_id"] for c in chats}

    personal_reply_settings = get_docs("personal_reply_settings", {"is_enabled": 1})
    personal_reply_templates = get_docs("personal_reply_templates", {"is_active": 1})

    business_first_contacts = get_docs("business_first_contacts", sort_field="first_seen_at", sort_dir=-1)
    business_reply_logs = get_docs("business_reply_logs", sort_field="sent_at", sort_dir=-1)

    chat_settings = [cs for cs in get_docs("chat_settings") if cs.get("chat_id") in active_chat_ids]
    chat_statistics = [cs for cs in get_docs("chat_statistics") if cs.get("chat_id") in active_chat_ids]
    chat_warnings = [cw for cw in get_docs("chat_warnings", sort_field="id", sort_dir=-1) if cw.get("chat_id") in active_chat_ids]
    chat_moderation_logs = [cml for cml in get_docs("chat_moderation_logs", sort_field="timestamp", sort_dir=-1) if cml.get("chat_id") in active_chat_ids]
    chat_join_events = [cje for cje in get_docs("chat_join_events", sort_field="joined_at", sort_dir=-1) if cje.get("chat_id") in active_chat_ids]
    active_spam_incidents = [asi for asi in get_docs("chat_spam_incidents", sort_field="last_message_time", sort_dir=-1) if asi.get("chat_id") in active_chat_ids]

    total_spam_incidents = db["chat_spam_incidents"].count_documents({})
    daily_moderation_stats = get_docs("daily_moderation_stats", sort_field="stat_date", sort_dir=-1)
    daily_stats_history = get_docs("daily_stats_history", sort_field="stat_date", sort_dir=-1)

    # Collection counts
    collection_names = [
        "chats", "chat_settings", "chat_admins", "chat_moderation_logs",
        "chat_warnings", "chat_spam_incidents", "chat_spam_messages",
        "chat_link_whitelist", "chat_blacklist", "chat_statistics",
        "chat_join_events", "user_restrictions", "business_connections",
        "personal_reply_settings", "personal_reply_templates",
        "business_first_contacts", "business_reply_logs",
        "scheduled_promotions", "promotion_send_logs",
        "shayari_content", "scheduled_shayari", "shayari_send_logs",
        "scheduled_stickers", "sticker_send_logs", "admins"
    ]
    table_counts = {}
    for col_name in collection_names:
        table_counts[col_name] = db[col_name].count_documents({})

    unique_user_ids = {bc["user_id"] for bc in business_connections if bc.get("is_enabled")}

    # Calculate real links deleted and messages deleted sums
    total_links_deleted = 0
    total_spam_deleted = 0
    total_abuse_deleted = 0
    total_messages_checked = 0
    total_warnings_issued = len(chat_warnings)
    for stat in chat_statistics:
        total_links_deleted += stat.get("links_deleted") or 0
        total_spam_deleted += stat.get("spam_deleted") or 0
        total_abuse_deleted += stat.get("abuse_deleted") or 0
        total_messages_checked += stat.get("total_messages_checked") or 0

    data = {
        "db_info": {
            "path": get_db_path(),
            "modified_time": time.time(),
            "engine": "MongoDB Atlas",
        },
        "table_counts": table_counts,
        "unique_users_count": len(unique_user_ids),
        "total_messages_checked": total_messages_checked,
        "total_links_deleted": total_links_deleted,
        "total_spam_deleted": total_spam_deleted,
        "total_abuse_deleted": total_abuse_deleted,
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
    print(json.dumps(data))

def remove_entity(entity_type: str, entity_id_str: str):
    try:
        entity_id = int(entity_id_str)
    except ValueError:
        print(json.dumps({"error": f"Invalid ID: {entity_id_str}"}))
        return

    db = get_db()
    removed_records = 0
    clean_type = entity_type.lower().strip()

    if clean_type in ("user", "business_user", "tenant"):
        res1 = db["business_connections"].update_many({"user_id": entity_id}, {"$set": {"is_enabled": 0}})
        removed_records += res1.modified_count
        res2 = db["personal_reply_settings"].update_many({"user_id": entity_id}, {"$set": {"is_enabled": 0}})
        removed_records += res2.modified_count
        db["chat_warnings"].delete_many({"user_id": entity_id})
        db["chat_join_events"].delete_many({"user_id": entity_id})
    elif clean_type in ("gc", "group", "supergroup", "channel", "chat"):
        res1 = db["chats"].update_many({"chat_id": entity_id}, {"$set": {"is_active": 0}})
        removed_records += res1.modified_count
        if removed_records == 0:
            neg_id = -abs(entity_id)
            res2 = db["chats"].update_many({"chat_id": neg_id}, {"$set": {"is_active": 0}})
            removed_records += res2.modified_count

    print(json.dumps({
        "success": True,
        "type": clean_type,
        "id": entity_id,
        "records_updated": removed_records,
        "message": f"Successfully removed bot from {clean_type} {entity_id} and purged data from active views."
    }))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        import schemas

        if cmd == "--remove" and len(sys.argv) >= 3:
            remove_entity(sys.argv[2], sys.argv[3])
        elif cmd == "--settings-get":
            print(json.dumps(schemas.get_system_settings()))
        elif cmd == "--settings-save":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(schemas.save_system_settings(json.loads(raw))))
        elif cmd == "--overview":
            print(json.dumps(schemas.get_overview_telemetry()))
        elif cmd == "--chat-add":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(schemas.create_or_save_chat(json.loads(raw))))
        elif cmd == "--chat-edit" and len(sys.argv) > 2:
            cid = int(sys.argv[2])
            raw = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(schemas.update_chat_settings_doc(cid, json.loads(raw))))
        elif cmd == "--chat-delete" and len(sys.argv) > 2:
            print(json.dumps(schemas.delete_or_deactivate_chat(int(sys.argv[2]))))
        elif cmd == "--user-add":
            raw = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            print(json.dumps(schemas.create_or_save_user(json.loads(raw))))
        elif cmd == "--user-edit" and len(sys.argv) > 2:
            uid = int(sys.argv[2])
            raw = sys.argv[3] if len(sys.argv) > 3 else sys.stdin.read()
            print(json.dumps(schemas.update_user_reply_settings(uid, json.loads(raw))))
        elif cmd == "--user-delete" and len(sys.argv) > 2:
            print(json.dumps(schemas.delete_or_deactivate_user(int(sys.argv[2]))))
        else:
            fetch_all()
    else:
        fetch_all()
