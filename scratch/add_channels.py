import sqlite3
import time

conn = sqlite3.connect('moderation.db')
cur = conn.cursor()
now = time.time()

# Ensure we have active group chats (GC)
cur.execute("""
INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, added_at, is_active, updated_at)
VALUES (-1004343785953, 'Couple chatting 😉', 'supergroup', ?, 1, ?)
""", (now, now))

cur.execute("""
INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, added_at, is_active, updated_at)
VALUES (-1004356470022, '♡LOVERS❥᭄ (Main GC)', 'group', ?, 1, ?)
""", (now, now))

# Add active Channels using the bot
cur.execute("""
INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, added_at, is_active, updated_at)
VALUES (-1002488192033, 'Waguri Official Announcements', 'channel', ?, 1, ?)
""", (now, now))

cur.execute("""
INSERT OR REPLACE INTO chat_settings (
    chat_id, anti_link_enabled, anti_spam_enabled, flood_detection_enabled,
    flood_threshold_messages, flood_window_seconds, warning_system_enabled,
    auto_restrict_enabled, anti_forward_enabled, anti_join_spam_enabled,
    anti_bot_enabled, media_restrictions_enabled, allowed_media_types,
    spam_window_seconds, warning_limit, restriction_duration_seconds,
    warning_delete_after_seconds, custom_warning_msg_1, custom_warning_msg_2,
    raid_mode_enabled, updated_at, anti_bio_link_enabled, clean_service_enabled
) VALUES (
    -1002488192033, 1, 0, 0, 8, 10, 0, 0, 0, 0, 0, 0,
    '{"photos":1,"videos":1}', 30, 2, 86400, 10, NULL, NULL, 0, ?, 0, 1
) ON CONFLICT(chat_id) DO UPDATE SET updated_at = excluded.updated_at
""", (now,))

cur.execute("""
INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, added_at, is_active, updated_at)
VALUES (-1002391024885, 'VIP Alerts & Broadcasts', 'channel', ?, 1, ?)
""", (now, now))

cur.execute("""
INSERT OR REPLACE INTO chat_settings (
    chat_id, anti_link_enabled, anti_spam_enabled, flood_detection_enabled,
    flood_threshold_messages, flood_window_seconds, warning_system_enabled,
    auto_restrict_enabled, anti_forward_enabled, anti_join_spam_enabled,
    anti_bot_enabled, media_restrictions_enabled, allowed_media_types,
    spam_window_seconds, warning_limit, restriction_duration_seconds,
    warning_delete_after_seconds, custom_warning_msg_1, custom_warning_msg_2,
    raid_mode_enabled, updated_at, anti_bio_link_enabled, clean_service_enabled
) VALUES (
    -1002391024885, 1, 0, 0, 8, 10, 0, 0, 0, 0, 0, 0,
    '{"photos":1,"videos":1}', 30, 2, 86400, 10, NULL, NULL, 0, ?, 0, 1
) ON CONFLICT(chat_id) DO UPDATE SET updated_at = excluded.updated_at
""", (now,))

conn.commit()
print("Chats updated successfully. Total chats:", cur.execute("SELECT count(*) FROM chats").fetchone()[0])
conn.close()
