import sqlite3
import json

conn = sqlite3.connect("moderation.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

summary = {}
for t in tables:
    cur.execute(f'SELECT * FROM "{t}"')
    rows = [dict(r) for r in cur.fetchall()]
    summary[t] = rows

print(json.dumps({
    "business_connections": summary.get("business_connections", []),
    "personal_reply_settings": summary.get("personal_reply_settings", []),
    "personal_reply_templates": summary.get("personal_reply_templates", []),
    "business_first_contacts": summary.get("business_first_contacts", []),
    "business_reply_logs": summary.get("business_reply_logs", []),
    "chats": summary.get("chats", []),
    "chat_settings": summary.get("chat_settings", []),
    "chat_statistics": summary.get("chat_statistics", []),
    "chat_warnings": summary.get("chat_warnings", []),
    "chat_moderation_logs": summary.get("chat_moderation_logs", []),
    "chat_join_events_count": len(summary.get("chat_join_events", [])),
    "chat_join_events_sample": summary.get("chat_join_events", [])[:5],
    "active_spam_incidents_count": len(summary.get("active_spam_incidents", [])),
    "active_spam_incidents_sample": summary.get("active_spam_incidents", [])[:5],
    "daily_moderation_stats": summary.get("daily_moderation_stats", []),
    "daily_stats_history": summary.get("daily_stats_history", []),
}, indent=2, default=str))
