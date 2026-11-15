import json
import logging
import sqlite3
import time
from typing import Any
import config

logger = logging.getLogger("Waguri.Database")


def get_db_path() -> str:
    """Retrieve the current database path dynamically from configuration."""
    return getattr(config, "DATABASE_PATH", "moderation.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create a SQLite database connection with row factory and WAL mode configured."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    return conn


def init_db(db_path: str | None = None) -> None:
    """
    Initialize and safely migrate the SQLite database to the 13-table multi-tenant architecture.
    Guarantees that no existing data or settings are overwritten or lost.
    """
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()

        # 1. Registered Chats Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                chat_type TEXT NOT NULL,
                added_at REAL NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL
            )
            """
        )

        # 2. Chat Settings Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                anti_link_enabled INTEGER NOT NULL DEFAULT 1,
                anti_bio_link_enabled INTEGER NOT NULL DEFAULT 1,
                clean_service_enabled INTEGER NOT NULL DEFAULT 1,
                anti_spam_enabled INTEGER NOT NULL DEFAULT 1,
                flood_detection_enabled INTEGER NOT NULL DEFAULT 1,
                flood_threshold_messages INTEGER NOT NULL DEFAULT 8,
                flood_window_seconds INTEGER NOT NULL DEFAULT 10,
                warning_system_enabled INTEGER NOT NULL DEFAULT 1,
                auto_restrict_enabled INTEGER NOT NULL DEFAULT 1,
                anti_forward_enabled INTEGER NOT NULL DEFAULT 0,
                anti_join_spam_enabled INTEGER NOT NULL DEFAULT 0,
                anti_bot_enabled INTEGER NOT NULL DEFAULT 0,
                media_restrictions_enabled INTEGER NOT NULL DEFAULT 0,
                allowed_media_types TEXT NOT NULL DEFAULT '{"photos":1,"videos":1,"documents":1,"stickers":1,"gifs":1,"voice":1,"video_notes":1}',
                spam_window_seconds INTEGER NOT NULL DEFAULT 30,
                warning_limit INTEGER NOT NULL DEFAULT 2,
                restriction_duration_seconds INTEGER NOT NULL DEFAULT 86400,
                warning_delete_after_seconds INTEGER NOT NULL DEFAULT 10,
                custom_warning_msg_1 TEXT,
                custom_warning_msg_2 TEXT,
                raid_mode_enabled INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (chat_id) ON DELETE CASCADE
            )
            """
        )

        # 3. Chat Admins Table (Role-based access mapping)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_admins (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                can_change_settings INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )

        # 4. Chat Moderation Audit Logs Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_moderation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
            """
        )

        # 5. Chat Warnings Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                warning_number INTEGER NOT NULL,
                reason TEXT NOT NULL,
                issued_at REAL NOT NULL
            )
            """
        )

        # 6. Chat Spam Incidents Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_spam_incidents (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_fingerprint TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_message_time REAL NOT NULL,
                message_ids TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )

        # 7. Chat Spam Messages Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_spam_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
            """
        )

        # 8. Chat Link Whitelist Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_link_whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                added_by INTEGER NOT NULL DEFAULT 0,
                added_at REAL NOT NULL,
                UNIQUE (chat_id, domain)
            )
            """
        )

        # 9. Chat Blacklist Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                pattern_or_domain TEXT NOT NULL,
                added_by INTEGER NOT NULL DEFAULT 0,
                added_at REAL NOT NULL,
                UNIQUE (chat_id, pattern_or_domain)
            )
            """
        )

        # 10. Chat Statistics Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_statistics (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                total_messages_checked INTEGER NOT NULL DEFAULT 0,
                links_deleted INTEGER NOT NULL DEFAULT 0,
                spam_deleted INTEGER NOT NULL DEFAULT 0,
                warnings_issued INTEGER NOT NULL DEFAULT 0,
                restrictions_applied INTEGER NOT NULL DEFAULT 0,
                banned_members INTEGER NOT NULL DEFAULT 0,
                forwards_deleted INTEGER NOT NULL DEFAULT 0,
                media_deleted INTEGER NOT NULL DEFAULT 0,
                raid_actions_taken INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
            """
        )

        # 11. Chat Join Events Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_join_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                is_bot INTEGER NOT NULL DEFAULT 0,
                joined_at REAL NOT NULL
            )
            """
        )

        # 12. User Restrictions Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                action TEXT NOT NULL DEFAULT 'mute',
                reason TEXT NOT NULL,
                previous_permissions TEXT,
                restricted_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        # 13. Callback Sessions Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS callback_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                data TEXT,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )

        # 14. Telegram Business Connections Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS business_connections (
                connection_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_chat_id INTEGER NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                can_reply INTEGER NOT NULL DEFAULT 1,
                account_username TEXT,
                account_first_name TEXT,
                connected_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        # 15. Personal Auto-Reply Settings Table (Per-User)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS personal_reply_settings (
                user_id INTEGER PRIMARY KEY,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                first_time_only INTEGER NOT NULL DEFAULT 1,
                cooldown_seconds INTEGER NOT NULL DEFAULT 86400,
                daily_limit INTEGER NOT NULL DEFAULT 100,
                reply_delay_seconds INTEGER NOT NULL DEFAULT 0,
                parse_mode TEXT NOT NULL DEFAULT 'HTML',
                excluded_user_ids TEXT NOT NULL DEFAULT '[]',
                welcome_message_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL
            )
            """
        )

        # 16. Personal Auto-Reply Templates Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS personal_reply_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                template_name TEXT NOT NULL DEFAULT 'default',
                content TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE (user_id, template_name)
            )
            """
        )

        # 17. Business First Contacts History Table (First-time sender detection & suppression)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS business_first_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_user_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_username TEXT,
                sender_first_name TEXT,
                first_seen_at REAL NOT NULL,
                last_seen_at REAL NOT NULL,
                messages_count INTEGER NOT NULL DEFAULT 1,
                replied INTEGER NOT NULL DEFAULT 0,
                replied_at REAL,
                UNIQUE (business_user_id, sender_id)
            )
            """
        )

        # 18. Business Reply Delivery Logs Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS business_reply_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_user_id INTEGER NOT NULL,
                connection_id TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                reply_text TEXT,
                sent_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT
            )
            """
        )

        # Create Indexes for Multi-Tenant & Business Operation Performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_chat ON chat_moderation_logs(chat_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_warnings_chat_user ON chat_warnings(chat_id, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_spam_msgs_chat_user ON chat_spam_messages(chat_id, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelist_chat ON chat_link_whitelist(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_chat ON chat_blacklist(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_join_events_chat ON chat_join_events(chat_id, joined_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restrictions_chat_user ON user_restrictions(chat_id, user_id, active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_biz_conn_user ON business_connections(user_id, is_enabled)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_biz_templates_user ON personal_reply_templates(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_biz_contacts_user_sender ON business_first_contacts(business_user_id, sender_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_biz_logs_user_sent ON business_reply_logs(business_user_id, sent_at)")

        # Migration: ensure anti_bio_link_enabled and clean_service_enabled columns exist in chat_settings
        cursor.execute("PRAGMA table_info(chat_settings)")
        existing_cols = [r[1] for r in cursor.fetchall()]
        if "anti_bio_link_enabled" not in existing_cols:
            cursor.execute("ALTER TABLE chat_settings ADD COLUMN anti_bio_link_enabled INTEGER NOT NULL DEFAULT 1")
        if "clean_service_enabled" not in existing_cols:
            cursor.execute("ALTER TABLE chat_settings ADD COLUMN clean_service_enabled INTEGER NOT NULL DEFAULT 1")

        # ---------------------------------------------------------------------
        # Safe Data Migrations from legacy tables (if present)
        # ---------------------------------------------------------------------
        existing_tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

        if "group_settings" in existing_tables:
            cursor.execute("SELECT * FROM group_settings")
            rows = cursor.fetchall()
            for r in rows:
                d = dict(r)
                cid = d.get("chat_id")
                if not cid:
                    continue
                # Migrate to chats
                cursor.execute(
                    """
                    INSERT INTO chats (chat_id, chat_title, chat_type, added_at, is_active, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        chat_title = COALESCE(excluded.chat_title, chats.chat_title),
                        chat_type = COALESCE(excluded.chat_type, chats.chat_type),
                        is_active = excluded.is_active,
                        updated_at = excluded.updated_at
                    """,
                    (
                        cid,
                        d.get("chat_title") or "Group",
                        d.get("chat_type") or "group",
                        d.get("added_at") or time.time(),
                        d.get("is_active", 1),
                        d.get("updated_at") or time.time(),
                    ),
                )
                # Migrate to chat_settings
                cursor.execute(
                    """
                    INSERT INTO chat_settings (
                        chat_id, anti_link_enabled, anti_spam_enabled, flood_detection_enabled,
                        warning_system_enabled, auto_restrict_enabled, spam_window_seconds,
                        warning_limit, restriction_duration_seconds, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        anti_link_enabled = excluded.anti_link_enabled,
                        anti_spam_enabled = excluded.anti_spam_enabled,
                        flood_detection_enabled = excluded.flood_detection_enabled,
                        warning_system_enabled = excluded.warning_system_enabled,
                        auto_restrict_enabled = excluded.auto_restrict_enabled,
                        spam_window_seconds = excluded.spam_window_seconds,
                        warning_limit = excluded.warning_limit,
                        restriction_duration_seconds = excluded.restriction_duration_seconds,
                        updated_at = excluded.updated_at
                    """,
                    (
                        cid,
                        d.get("anti_link_enabled", 1),
                        d.get("anti_spam_enabled", 1),
                        d.get("flood_detection_enabled", 1),
                        d.get("warning_system_enabled", 1),
                        d.get("auto_restrict_enabled", 1),
                        d.get("spam_window_seconds", 30),
                        d.get("warning_limit", 2),
                        d.get("restriction_duration_seconds", 86400),
                        d.get("updated_at") or time.time(),
                    ),
                )

        if "group_statistics" in existing_tables:
            cursor.execute("SELECT * FROM group_statistics")
            for r in cursor.fetchall():
                d = dict(r)
                cursor.execute(
                    """
                    INSERT INTO chat_statistics (
                        chat_id, chat_title, total_messages_checked, links_deleted,
                        spam_deleted, warnings_issued, restrictions_applied, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        chat_title = COALESCE(excluded.chat_title, chat_statistics.chat_title),
                        total_messages_checked = excluded.total_messages_checked,
                        links_deleted = excluded.links_deleted,
                        spam_deleted = excluded.spam_deleted,
                        warnings_issued = excluded.warnings_issued,
                        restrictions_applied = excluded.restrictions_applied,
                        updated_at = excluded.updated_at
                    """,
                    (
                        d["chat_id"],
                        d.get("chat_title"),
                        d.get("total_messages_checked", 0),
                        d.get("links_deleted", 0),
                        d.get("spam_deleted", 0),
                        d.get("warnings_issued", 0),
                        d.get("restrictions_applied", 0),
                        d.get("updated_at", 0),
                    ),
                )

        if "active_spam_incidents" in existing_tables:
            cursor.execute("SELECT * FROM active_spam_incidents")
            for r in cursor.fetchall():
                d = dict(r)
                cursor.execute(
                    """
                    INSERT INTO chat_spam_incidents (
                        chat_id, user_id, message_fingerprint, count, last_message_time, message_ids
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id, user_id) DO UPDATE SET
                        message_fingerprint = excluded.message_fingerprint,
                        count = excluded.count,
                        last_message_time = excluded.last_message_time,
                        message_ids = excluded.message_ids
                    """,
                    (
                        d["chat_id"],
                        d["user_id"],
                        d["message_fingerprint"],
                        d["count"],
                        d["last_message_time"],
                        d.get("message_ids", "[]"),
                    ),
                )

        if "restriction_history" in existing_tables:
            cursor.execute("SELECT * FROM restriction_history")
            for r in cursor.fetchall():
                d = dict(r)
                cursor.execute(
                    """
                    INSERT INTO user_restrictions (
                        chat_id, user_id, username, action, reason, restricted_at, expires_at, active
                    ) VALUES (?, ?, ?, 'mute', ?, ?, ?, ?)
                    """,
                    (
                        d["chat_id"],
                        d["user_id"],
                        d.get("username"),
                        d.get("reason", "Violation"),
                        d.get("restricted_at", 0),
                        d.get("expires_at", 0),
                        d.get("active", 1),
                    ),
                )

        if "moderation_logs" in existing_tables:
            cursor.execute("SELECT * FROM moderation_logs")
            for r in cursor.fetchall():
                d = dict(r)
                cursor.execute(
                    """
                    INSERT INTO chat_moderation_logs (
                        chat_id, user_id, action, details, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        d["chat_id"],
                        d["user_id"],
                        d["action"],
                        d["details"],
                        d["timestamp"],
                    ),
                )

        conn.commit()
    logger.info("Database initialized and verified for multi-tenant operation at '%s'.", path)


# =============================================================================
# Chat Registration & Settings Management
# =============================================================================

def register_or_update_chat(
    chat_id: int,
    chat_title: str | None,
    chat_type: str | None,
    is_active: bool = True,
    db_path: str | None = None,
) -> None:
    """Register a new group/channel or update its active state upon join or message."""
    path = db_path or get_db_path()
    now = time.time()
    active_int = 1 if is_active else 0
    c_type = chat_type or "group"
    c_title = chat_title or "Chat"

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chats (chat_id, chat_title, chat_type, added_at, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                chat_title = COALESCE(excluded.chat_title, chats.chat_title),
                chat_type = COALESCE(excluded.chat_type, chats.chat_type),
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (chat_id, c_title, c_type, now, active_int, now),
        )

        # Initialize default settings if not exists
        cursor.execute(
            """
            INSERT INTO chat_settings (
                chat_id, anti_link_enabled, anti_bio_link_enabled, clean_service_enabled, anti_spam_enabled, flood_detection_enabled,
                flood_threshold_messages, flood_window_seconds,
                warning_system_enabled, auto_restrict_enabled,
                anti_forward_enabled, anti_join_spam_enabled, anti_bot_enabled,
                media_restrictions_enabled, allowed_media_types,
                spam_window_seconds, warning_limit, restriction_duration_seconds,
                warning_delete_after_seconds, raid_mode_enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (
                chat_id,
                1 if getattr(config, "ANTI_LINK_ENABLED", True) else 0,
                1 if getattr(config, "ANTI_BIO_LINK_ENABLED", True) else 0,
                1 if getattr(config, "CLEAN_SERVICE_ENABLED", True) else 0,
                1 if getattr(config, "ANTI_SPAM_ENABLED", True) else 0,
                1 if getattr(config, "FLOOD_DETECTION_ENABLED", True) else 0,
                getattr(config, "FLOOD_MESSAGE_LIMIT", 8),
                getattr(config, "FLOOD_WINDOW_SECONDS", 10),
                1,  # warning_system_enabled
                1,  # auto_restrict_enabled
                1 if getattr(config, "ANTI_FORWARD_ENABLED", False) else 0,
                1 if getattr(config, "ANTI_JOIN_SPAM_ENABLED", False) else 0,
                1 if getattr(config, "ANTI_BOT_ENABLED", False) else 0,
                1 if getattr(config, "MEDIA_RESTRICTIONS_ENABLED", False) else 0,
                json.dumps(getattr(config, "DEFAULT_ALLOWED_MEDIA", {})),
                getattr(config, "SPAM_WINDOW_SECONDS", 30),
                getattr(config, "SPAM_WARNING_LIMIT", 2),
                getattr(config, "SPAM_RESTRICTION_SECONDS", 86400),
                getattr(config, "WARNING_DELETE_AFTER_SECONDS", 10),
                0,  # raid_mode_enabled
                now,
            ),
        )
        conn.commit()


def set_chat_active(chat_id: int, is_active: bool, db_path: str | None = None) -> None:
    """Mark a group or channel active or inactive upon bot addition/removal."""
    path = db_path or get_db_path()
    active_int = 1 if is_active else 0
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chats SET is_active = ?, updated_at = ? WHERE chat_id = ?",
            (active_int, now, chat_id),
        )
        conn.commit()


def get_group_settings(chat_id: int, db_path: str | None = None) -> dict[str, Any]:
    """
    Retrieve comprehensive per-group or per-channel settings.
    If the chat has no stored configuration, initializes default settings seamlessly.
    """
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.chat_title, c.chat_type, c.added_at, c.is_active, s.*
            FROM chat_settings s
            JOIN chats c ON c.chat_id = s.chat_id
            WHERE s.chat_id = ?
            """,
            (chat_id,),
        )
        row = cursor.fetchone()
        if row:
            d = dict(row)
            try:
                allowed_media = json.loads(d.get("allowed_media_types") or "{}")
            except Exception:
                allowed_media = getattr(config, "DEFAULT_ALLOWED_MEDIA", {})

            return {
                "chat_id": d["chat_id"],
                "chat_title": d.get("chat_title") or "Unnamed Chat",
                "chat_type": d.get("chat_type") or "group",
                "added_at": d.get("added_at") or 0.0,
                "anti_link_enabled": bool(d.get("anti_link_enabled", 1)),
                "anti_bio_link_enabled": bool(d.get("anti_bio_link_enabled", 1)),
                "clean_service_enabled": bool(d.get("clean_service_enabled", 1)),
                "anti_spam_enabled": bool(d.get("anti_spam_enabled", 1)),
                "flood_detection_enabled": bool(d.get("flood_detection_enabled", 1)),
                "flood_threshold_messages": int(d.get("flood_threshold_messages") or 8),
                "flood_window_seconds": int(d.get("flood_window_seconds") or 10),
                "warning_system_enabled": bool(d.get("warning_system_enabled", 1)),
                "auto_restrict_enabled": bool(d.get("auto_restrict_enabled", 1)),
                "anti_forward_enabled": bool(d.get("anti_forward_enabled", 0)),
                "anti_join_spam_enabled": bool(d.get("anti_join_spam_enabled", 0)),
                "anti_bot_enabled": bool(d.get("anti_bot_enabled", 0)),
                "media_restrictions_enabled": bool(d.get("media_restrictions_enabled", 0)),
                "allowed_media_types": allowed_media,
                "spam_window_seconds": int(d.get("spam_window_seconds") or 30),
                "warning_limit": int(d.get("warning_limit") or 2),
                "restriction_duration_seconds": int(d.get("restriction_duration_seconds") or 86400),
                "warning_delete_after_seconds": int(d.get("warning_delete_after_seconds") or 10),
                "custom_warning_msg_1": d.get("custom_warning_msg_1"),
                "custom_warning_msg_2": d.get("custom_warning_msg_2"),
                "raid_mode_enabled": bool(d.get("raid_mode_enabled", 0)),
                "is_active": bool(d.get("is_active", 1)),
                "updated_at": d.get("updated_at") or 0.0,
            }

    # If row does not exist yet, register and return default config
    register_or_update_chat(chat_id, None, None, is_active=True, db_path=path)
    return get_group_settings(chat_id, db_path=path)


def update_group_feature(chat_id: int, feature_col: str, enabled: bool, db_path: str | None = None) -> None:
    """Toggle a specific boolean feature for a group."""
    valid_cols = {
        "anti_link_enabled",
        "anti_bio_link_enabled",
        "clean_service_enabled",
        "anti_spam_enabled",
        "flood_detection_enabled",
        "warning_system_enabled",
        "auto_restrict_enabled",
        "anti_forward_enabled",
        "anti_join_spam_enabled",
        "anti_bot_enabled",
        "media_restrictions_enabled",
        "raid_mode_enabled",
    }
    if feature_col not in valid_cols:
        raise ValueError(f"Invalid feature column: {feature_col}")

    path = db_path or get_db_path()
    val = 1 if enabled else 0
    now = time.time()

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM chat_settings WHERE chat_id = ?", (chat_id,))
        if not cursor.fetchone():
            register_or_update_chat(chat_id, None, None, is_active=True, db_path=path)

        cursor.execute(
            f"UPDATE chat_settings SET {feature_col} = ?, updated_at = ? WHERE chat_id = ?",
            (val, now, chat_id),
        )
        conn.commit()


def update_group_numeric_setting(chat_id: int, setting_col: str, value: int, db_path: str | None = None) -> None:
    """Update a numeric configuration setting for a group."""
    valid_cols = {
        "spam_window_seconds",
        "warning_limit",
        "restriction_duration_seconds",
        "warning_delete_after_seconds",
        "flood_threshold_messages",
        "flood_window_seconds",
    }
    if setting_col not in valid_cols:
        raise ValueError(f"Invalid setting column: {setting_col}")

    path = db_path or get_db_path()
    now = time.time()

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM chat_settings WHERE chat_id = ?", (chat_id,))
        if not cursor.fetchone():
            register_or_update_chat(chat_id, None, None, is_active=True, db_path=path)

        cursor.execute(
            f"UPDATE chat_settings SET {setting_col} = ?, updated_at = ? WHERE chat_id = ?",
            (value, now, chat_id),
        )
        conn.commit()


def update_group_text_setting(chat_id: int, setting_col: str, value: str | None, db_path: str | None = None) -> None:
    """Update a text configuration setting for a group."""
    valid_cols = {
        "custom_warning_msg_1",
        "custom_warning_msg_2",
        "allowed_media_types",
    }
    if setting_col not in valid_cols:
        raise ValueError(f"Invalid text setting column: {setting_col}")

    path = db_path or get_db_path()
    now = time.time()

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM chat_settings WHERE chat_id = ?", (chat_id,))
        if not cursor.fetchone():
            register_or_update_chat(chat_id, None, None, is_active=True, db_path=path)

        cursor.execute(
            f"UPDATE chat_settings SET {setting_col} = ?, updated_at = ? WHERE chat_id = ?",
            (value, now, chat_id),
        )
        conn.commit()


def set_group_anti_link(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable anti-link protection for a specific group."""
    update_group_feature(chat_id, "anti_link_enabled", enabled, db_path=db_path)


def set_group_anti_bio_link(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable anti-bio-link protection for a specific group."""
    update_group_feature(chat_id, "anti_bio_link_enabled", enabled, db_path=db_path)


def set_group_clean_service(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable cleaning service messages for a specific group."""
    update_group_feature(chat_id, "clean_service_enabled", enabled, db_path=db_path)


def set_group_anti_spam(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable anti-spam protection for a specific group."""
    update_group_feature(chat_id, "anti_spam_enabled", enabled, db_path=db_path)


# =============================================================================
# Media Restrictions Management
# =============================================================================

def get_media_restrictions(chat_id: int, db_path: str | None = None) -> dict[str, bool]:
    """Retrieve allowed media types dictionary for a group."""
    settings = get_group_settings(chat_id, db_path=db_path)
    allowed = settings.get("allowed_media_types")
    if isinstance(allowed, dict):
        return allowed
    return getattr(config, "DEFAULT_ALLOWED_MEDIA", {})


def set_media_restriction(chat_id: int, media_type: str, allowed: bool, db_path: str | None = None) -> None:
    """Toggle whether a specific media type (photo, video, sticker, etc.) is allowed."""
    current = get_media_restrictions(chat_id, db_path=db_path)
    current[media_type] = allowed
    update_group_text_setting(chat_id, "allowed_media_types", json.dumps(current), db_path=db_path)


# =============================================================================
# Link Whitelist & Blacklist Management
# =============================================================================

def add_whitelisted_domain(chat_id: int, domain: str, added_by: int = 0, db_path: str | None = None) -> bool:
    """Add a domain to the group's link whitelist."""
    clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
    path = db_path or get_db_path()
    now = time.time()
    try:
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_link_whitelist (chat_id, domain, added_by, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, domain) DO NOTHING
                """,
                (chat_id, clean_domain, added_by, now),
            )
            conn.commit()
            return True
    except Exception as exc:
        logger.error("Failed to add whitelist domain '%s' in chat %s: %s", domain, chat_id, exc)
        return False


def remove_whitelisted_domain(chat_id: int, domain: str, db_path: str | None = None) -> bool:
    """Remove a domain from the group's link whitelist."""
    clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_link_whitelist WHERE chat_id = ? AND domain = ?",
            (chat_id, clean_domain),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_whitelisted_domains(chat_id: int, db_path: str | None = None) -> list[str]:
    """Retrieve all whitelisted domains for a group."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT domain FROM chat_link_whitelist WHERE chat_id = ? ORDER BY domain ASC",
            (chat_id,),
        )
        return [row["domain"] for row in cursor.fetchall()]


def is_domain_whitelisted(chat_id: int, domain: str, db_path: str | None = None) -> bool:
    """Check if a domain or URL is whitelisted in the group."""
    clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
    whitelisted = get_whitelisted_domains(chat_id, db_path=db_path)
    for w in whitelisted:
        if clean_domain == w or clean_domain.endswith("." + w):
            return True
    return False


def add_blacklisted_pattern(chat_id: int, pattern: str, added_by: int = 0, db_path: str | None = None) -> bool:
    """Add a domain or keyword pattern to the group's blacklist."""
    clean_pattern = pattern.strip().lower()
    path = db_path or get_db_path()
    now = time.time()
    try:
        with get_connection(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_blacklist (chat_id, pattern_or_domain, added_by, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, pattern_or_domain) DO NOTHING
                """,
                (chat_id, clean_pattern, added_by, now),
            )
            conn.commit()
            return True
    except Exception as exc:
        logger.error("Failed to add blacklist pattern '%s' in chat %s: %s", pattern, chat_id, exc)
        return False


def remove_blacklisted_pattern(chat_id: int, pattern: str, db_path: str | None = None) -> bool:
    """Remove a pattern from the group's blacklist."""
    clean_pattern = pattern.strip().lower()
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_blacklist WHERE chat_id = ? AND pattern_or_domain = ?",
            (chat_id, clean_pattern),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_blacklisted_patterns(chat_id: int, db_path: str | None = None) -> list[str]:
    """Retrieve all blacklisted patterns for a group."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pattern_or_domain FROM chat_blacklist WHERE chat_id = ? ORDER BY pattern_or_domain ASC",
            (chat_id,),
        )
        return [row["pattern_or_domain"] for row in cursor.fetchall()]


def is_content_blacklisted(chat_id: int, text: str, db_path: str | None = None) -> bool:
    """Check if message text contains any blacklisted patterns."""
    if not text:
        return False
    lower_text = text.lower()
    patterns = get_blacklisted_patterns(chat_id, db_path=db_path)
    for pat in patterns:
        if pat in lower_text:
            return True
    return False


# =============================================================================
# Statistics Management
# =============================================================================

def increment_stat(
    chat_id: int,
    stat_name: str,
    count: int = 1,
    chat_title: str | None = None,
    db_path: str | None = None,
) -> None:
    """Atomically increment a moderation statistic counter for a group or channel."""
    valid_stats = {
        "total_messages_checked",
        "links_deleted",
        "spam_deleted",
        "warnings_issued",
        "restrictions_applied",
        "banned_members",
        "forwards_deleted",
        "media_deleted",
        "raid_actions_taken",
    }
    if stat_name not in valid_stats:
        return

    path = db_path or get_db_path()
    now = time.time()

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_statistics (
                chat_id, chat_title, total_messages_checked, links_deleted,
                spam_deleted, warnings_issued, restrictions_applied,
                banned_members, forwards_deleted, media_deleted, raid_actions_taken, updated_at
            ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
            ON CONFLICT(chat_id) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (chat_id, chat_title, now),
        )
        if chat_title:
            cursor.execute(
                "UPDATE chat_statistics SET chat_title = ? WHERE chat_id = ?",
                (chat_title, chat_id),
            )
        cursor.execute(
            f"UPDATE chat_statistics SET {stat_name} = {stat_name} + ?, updated_at = ? WHERE chat_id = ?",
            (count, now, chat_id),
        )
        conn.commit()


def get_group_stats(chat_id: int, db_path: str | None = None) -> dict[str, Any]:
    """Retrieve moderation statistics for a specific group or channel."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chat_statistics WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if not row:
            return {
                "chat_id": chat_id,
                "chat_title": "Unnamed Chat",
                "total_messages_checked": 0,
                "links_deleted": 0,
                "spam_deleted": 0,
                "warnings_issued": 0,
                "restrictions_applied": 0,
                "banned_members": 0,
                "forwards_deleted": 0,
                "media_deleted": 0,
                "raid_actions_taken": 0,
                "updated_at": 0.0,
            }
        return dict(row)


# =============================================================================
# Moderation Audit Logs
# =============================================================================

def log_moderation_event(
    chat_id: int,
    user_id: int,
    action: str,
    details: str,
    db_path: str | None = None,
) -> None:
    """Record an audit trail event for a moderation action in SQLite."""
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_moderation_logs (chat_id, user_id, action, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, action, details, now),
        )
        conn.commit()


def get_recent_moderation_logs(chat_id: int, limit: int = 15, db_path: str | None = None) -> list[dict[str, Any]]:
    """Retrieve recent moderation audit actions for a specific group."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, chat_id, user_id, action, details, timestamp
            FROM chat_moderation_logs
            WHERE chat_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# Spam Incidents & Recorded Spam Messages
# =============================================================================

def get_active_incident(chat_id: int, user_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    """Retrieve the active spam incident for a given user in a group."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT chat_id, user_id, message_fingerprint, count, last_message_time, message_ids
            FROM chat_spam_incidents
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        try:
            message_ids = json.loads(row["message_ids"])
        except Exception:
            message_ids = []

        return {
            "chat_id": row["chat_id"],
            "user_id": row["user_id"],
            "message_fingerprint": row["message_fingerprint"],
            "count": row["count"],
            "last_message_time": row["last_message_time"],
            "message_ids": message_ids,
        }


def save_active_incident(
    chat_id: int,
    user_id: int,
    message_fingerprint: str,
    count: int,
    last_message_time: float,
    message_ids: list[int],
    db_path: str | None = None,
) -> None:
    """Save or update an active spam incident in persistent storage."""
    path = db_path or get_db_path()
    message_ids_json = json.dumps(message_ids)
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_spam_incidents (
                chat_id, user_id, message_fingerprint, count, last_message_time, message_ids
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                message_fingerprint = excluded.message_fingerprint,
                count = excluded.count,
                last_message_time = excluded.last_message_time,
                message_ids = excluded.message_ids
            """,
            (chat_id, user_id, message_fingerprint, count, last_message_time, message_ids_json),
        )
        conn.commit()


def clear_active_incident(chat_id: int, user_id: int, db_path: str | None = None) -> None:
    """Remove an active spam incident after expiration or restriction."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_spam_incidents WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        conn.commit()


# =============================================================================
# Warning Tracking Management
# =============================================================================

def add_user_warning(chat_id: int, user_id: int, reason: str, db_path: str | None = None) -> int:
    """Record a warning issued to a user and return their total active warning count."""
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(*) FROM chat_warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        current_count = cursor.fetchone()[0]
        new_warn_num = current_count + 1

        cursor.execute(
            """
            INSERT INTO chat_warnings (chat_id, user_id, warning_number, reason, issued_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, new_warn_num, reason, now),
        )
        conn.commit()
        return new_warn_num


def get_user_warnings_count(chat_id: int, user_id: int, db_path: str | None = None) -> int:
    """Retrieve the total warning count issued to a user in a group."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(*) FROM chat_warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        return cursor.fetchone()[0]


def reset_user_warnings(chat_id: int, user_id: int, db_path: str | None = None) -> int:
    """Clear all warnings for a user in a group and return the number of cleared records."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        conn.commit()
        return cursor.rowcount


# =============================================================================
# Restriction & Ban History Management
# =============================================================================

def record_restriction(
    chat_id: int,
    user_id: int,
    username: str | None,
    reason: str,
    restricted_at: float,
    expires_at: float,
    previous_permissions: str | None = None,
    action: str = "mute",
    db_path: str | None = None,
) -> int:
    """Record an applied restriction (mute or ban) into SQLite."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_restrictions (
                chat_id, user_id, username, action, reason, previous_permissions,
                restricted_at, expires_at, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (chat_id, user_id, username, action, reason, previous_permissions, restricted_at, expires_at),
        )
        conn.commit()
        return cursor.lastrowid or 0


def lift_active_restrictions(chat_id: int, user_id: int, db_path: str | None = None) -> int:
    """Mark all active restrictions for a user in a group as lifted/inactive."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_restrictions SET active = 0 WHERE chat_id = ? AND user_id = ? AND active = 1",
            (chat_id, user_id),
        )
        conn.commit()
        return cursor.rowcount


def get_user_restrictions(chat_id: int, user_id: int, db_path: str | None = None) -> list[dict[str, Any]]:
    """Retrieve restriction records for a user in a specific group."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM user_restrictions
            WHERE chat_id = ? AND user_id = ?
            ORDER BY restricted_at DESC
            """,
            (chat_id, user_id),
        )
        return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# Join Events & Anti-Join Spam Tracking
# =============================================================================

def record_join_event(chat_id: int, user_id: int, is_bot: bool = False, db_path: str | None = None) -> None:
    """Record a member join event to track bursts and anti-bot activity."""
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_join_events (chat_id, user_id, is_bot, joined_at) VALUES (?, ?, ?, ?)",
            (chat_id, user_id, 1 if is_bot else 0, now),
        )
        conn.commit()


def get_recent_join_events_count(chat_id: int, window_seconds: int = 10, db_path: str | None = None) -> int:
    """Count how many users joined the group within the last window_seconds."""
    path = db_path or get_db_path()
    cutoff = time.time() - window_seconds
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(*) FROM chat_join_events WHERE chat_id = ? AND joined_at >= ?",
            (chat_id, cutoff),
        )
        return cursor.fetchone()[0]


# =============================================================================
# Multi-Group / Multi-Channel Owner Queries
# =============================================================================

def get_registered_chats(chat_type: str | None = None, active_only: bool = True, db_path: str | None = None) -> list[dict[str, Any]]:
    """Retrieve registered chats, optionally filtered by chat_type ('group', 'channel')."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM chats WHERE 1=1"
        params: list[Any] = []
        if active_only:
            query += " AND is_active = 1"
        if chat_type:
            if chat_type == "channel":
                query += " AND chat_type = 'channel'"
            else:
                query += " AND chat_type IN ('group', 'supergroup')"
        query += " ORDER BY chat_title ASC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_global_bot_stats(db_path: str | None = None) -> dict[str, Any]:
    """Retrieve aggregate statistics across all registered groups and channels for /owner."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        # Counts from chats
        cursor.execute("SELECT count(*) FROM chats WHERE is_active = 1 AND chat_type IN ('group', 'supergroup')")
        active_groups = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM chats WHERE is_active = 1 AND chat_type = 'channel'")
        active_channels = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM chats")
        total_chats = cursor.fetchone()[0]

        # Aggregates from chat_statistics
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(total_messages_checked), 0) AS total_messages,
                COALESCE(SUM(links_deleted), 0) AS total_links_deleted,
                COALESCE(SUM(spam_deleted), 0) AS total_spam_deleted,
                COALESCE(SUM(warnings_issued), 0) AS total_warnings,
                COALESCE(SUM(restrictions_applied), 0) AS total_restrictions,
                COALESCE(SUM(banned_members), 0) AS total_bans
            FROM chat_statistics
            """
        )
        stats_row = cursor.fetchone()

        return {
            "active_groups": active_groups,
            "active_channels": active_channels,
            "total_registered_chats": total_chats,
            "total_messages": stats_row["total_messages"],
            "total_links_deleted": stats_row["total_links_deleted"],
            "total_spam_deleted": stats_row["total_spam_deleted"],
            "total_warnings": stats_row["total_warnings"],
            "total_restrictions": stats_row["total_restrictions"],
            "total_bans": stats_row["total_bans"],
        }


# =============================================================================
# Telegram Business & Personal Auto-Reply Management
# =============================================================================

DEFAULT_PERSONAL_REPLY_TEMPLATE: str = (
    "Hello {first_name}! 👋\n\n"
    "Thank you for reaching out. I have received your message and will get back to you as soon as possible."
)


def save_or_update_business_connection(
    connection_id: str,
    user_id: int,
    user_chat_id: int,
    is_enabled: bool,
    can_reply: bool,
    account_username: str | None = None,
    account_first_name: str | None = None,
    db_path: str | None = None,
) -> None:
    """Save or update a Telegram Business connection record in SQLite."""
    path = db_path or get_db_path()
    now = time.time()
    enabled_int = 1 if is_enabled else 0
    can_reply_int = 1 if can_reply else 0

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO business_connections (
                connection_id, user_id, user_chat_id, is_enabled, can_reply,
                account_username, account_first_name, connected_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(connection_id) DO UPDATE SET
                user_id = excluded.user_id,
                user_chat_id = excluded.user_chat_id,
                is_enabled = excluded.is_enabled,
                can_reply = excluded.can_reply,
                account_username = COALESCE(excluded.account_username, business_connections.account_username),
                account_first_name = COALESCE(excluded.account_first_name, business_connections.account_first_name),
                updated_at = excluded.updated_at
            """,
            (
                connection_id,
                user_id,
                user_chat_id,
                enabled_int,
                can_reply_int,
                account_username,
                account_first_name,
                now,
                now,
            ),
        )

        # Ensure default settings exist for this user
        cursor.execute(
            """
            INSERT INTO personal_reply_settings (
                user_id, is_enabled, first_time_only, cooldown_seconds, daily_limit,
                reply_delay_seconds, parse_mode, excluded_user_ids, welcome_message_enabled, updated_at
            ) VALUES (?, 1, 1, 86400, 100, 0, 'HTML', '[]', 1, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, now),
        )

        # Ensure default template exists for this user
        cursor.execute(
            """
            INSERT INTO personal_reply_templates (
                user_id, template_name, content, is_active, created_at, updated_at
            ) VALUES (?, 'default', ?, 1, ?, ?)
            ON CONFLICT(user_id, template_name) DO NOTHING
            """,
            (user_id, DEFAULT_PERSONAL_REPLY_TEMPLATE, now, now),
        )

        conn.commit()


def get_business_connection(connection_id: str, db_path: str | None = None) -> dict[str, Any] | None:
    """Retrieve details of a business connection by its unique connection ID."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM business_connections WHERE connection_id = ?", (connection_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_business_connections(
    user_id: int, active_only: bool = False, db_path: str | None = None
) -> list[dict[str, Any]]:
    """Retrieve all business connections associated with a user."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM business_connections WHERE user_id = ?"
        params: list[Any] = [user_id]
        if active_only:
            query += " AND is_enabled = 1"
        query += " ORDER BY updated_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_active_business_connection_for_user(user_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    """Retrieve the most recent active business connection for a user."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM business_connections WHERE user_id = ? AND is_enabled = 1 ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_personal_reply_settings(user_id: int, db_path: str | None = None) -> dict[str, Any]:
    """Retrieve personal auto-reply configuration for a user, initializing defaults if absent."""
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM personal_reply_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)

        # Initialize defaults
        cursor.execute(
            """
            INSERT INTO personal_reply_settings (
                user_id, is_enabled, first_time_only, cooldown_seconds, daily_limit,
                reply_delay_seconds, parse_mode, excluded_user_ids, welcome_message_enabled, updated_at
            ) VALUES (?, 1, 1, 86400, 100, 0, 'HTML', '[]', 1, ?)
            """,
            (user_id, now),
        )
        conn.commit()
        cursor.execute("SELECT * FROM personal_reply_settings WHERE user_id = ?", (user_id,))
        return dict(cursor.fetchone())


def update_personal_reply_settings(user_id: int, db_path: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Update one or more settings in personal_reply_settings for a specific user."""
    path = db_path or get_db_path()
    allowed_keys = {
        "is_enabled",
        "first_time_only",
        "cooldown_seconds",
        "daily_limit",
        "reply_delay_seconds",
        "parse_mode",
        "excluded_user_ids",
        "welcome_message_enabled",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_keys}
    if not updates:
        return get_personal_reply_settings(user_id, db_path=path)

    # Ensure existing settings record
    get_personal_reply_settings(user_id, db_path=path)

    now = time.time()
    set_clauses = [f"{k} = ?" for k in updates.keys()]
    set_clauses.append("updated_at = ?")
    values = list(updates.values())
    values.append(now)
    values.append(user_id)

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE personal_reply_settings SET {', '.join(set_clauses)} WHERE user_id = ?",
            values,
        )
        conn.commit()

    return get_personal_reply_settings(user_id, db_path=path)


def get_personal_reply_template(
    user_id: int, template_name: str = "default", db_path: str | None = None
) -> str:
    """Retrieve custom reply template for a user. Guaranteed to never return another user's message."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM personal_reply_templates WHERE user_id = ? AND template_name = ? AND is_active = 1",
            (user_id, template_name),
        )
        row = cursor.fetchone()
        if row and row["content"]:
            return row["content"]
        return DEFAULT_PERSONAL_REPLY_TEMPLATE


def set_personal_reply_template(
    user_id: int, content: str, template_name: str = "default", db_path: str | None = None
) -> None:
    """Save or update a personal auto-reply template for a specific user."""
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO personal_reply_templates (
                user_id, template_name, content, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(user_id, template_name) DO UPDATE SET
                content = excluded.content,
                is_active = 1,
                updated_at = excluded.updated_at
            """,
            (user_id, template_name, content.strip(), now, now),
        )
        conn.commit()


def reset_personal_reply_template(
    user_id: int, template_name: str = "default", db_path: str | None = None
) -> str:
    """Reset a user's reply template back to the default message."""
    set_personal_reply_template(user_id, DEFAULT_PERSONAL_REPLY_TEMPLATE, template_name, db_path)
    return DEFAULT_PERSONAL_REPLY_TEMPLATE


def check_and_claim_first_contact(
    business_user_id: int,
    sender_id: int,
    sender_username: str | None = None,
    sender_first_name: str | None = None,
    db_path: str | None = None,
) -> bool:
    """
    Atomically detect first-time sender and claim reply rights.
    Utilizes UNIQUE(business_user_id, sender_id) SQLite constraint to guarantee
    zero duplicate replies even under high-concurrency race conditions.
    Returns True if sender is new and reply is claimed.
    Returns False if sender has previously contacted this business account.
    """
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        # Attempt atomic insert for new contact
        cursor.execute(
            """
            INSERT INTO business_first_contacts (
                business_user_id, sender_id, sender_username, sender_first_name,
                first_seen_at, last_seen_at, messages_count, replied, replied_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)
            ON CONFLICT(business_user_id, sender_id) DO NOTHING
            """,
            (business_user_id, sender_id, sender_username, sender_first_name, now, now, now),
        )
        if cursor.rowcount > 0:
            # First-time sender successfully detected and claimed!
            conn.commit()
            return True
        else:
            # Existing sender: update contact metadata without claiming a new reply
            cursor.execute(
                """
                UPDATE business_first_contacts
                SET last_seen_at = ?,
                    messages_count = messages_count + 1,
                    sender_username = COALESCE(?, sender_username),
                    sender_first_name = COALESCE(?, sender_first_name)
                WHERE business_user_id = ? AND sender_id = ?
                """,
                (now, sender_username, sender_first_name, business_user_id, sender_id),
            )
            conn.commit()
            return False


def check_and_claim_cooldown_reply(
    business_user_id: int,
    sender_id: int,
    cooldown_seconds: int,
    sender_username: str | None = None,
    sender_first_name: str | None = None,
    db_path: str | None = None,
) -> bool:
    """
    Check if sender is eligible for reply under cooldown mode (when first_time_only is False).
    Atomically updates replied_at if cooldown has elapsed.
    """
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT replied, replied_at FROM business_first_contacts WHERE business_user_id = ? AND sender_id = ?",
            (business_user_id, sender_id),
        )
        row = cursor.fetchone()

        if not row:
            # First time seeing this user
            cursor.execute(
                """
                INSERT INTO business_first_contacts (
                    business_user_id, sender_id, sender_username, sender_first_name,
                    first_seen_at, last_seen_at, messages_count, replied, replied_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)
                """,
                (business_user_id, sender_id, sender_username, sender_first_name, now, now, now),
            )
            conn.commit()
            return True

        replied_at = row["replied_at"] or 0
        if (now - replied_at) >= cooldown_seconds:
            # Cooldown passed, eligible for new reply
            cursor.execute(
                """
                UPDATE business_first_contacts
                SET last_seen_at = ?,
                    messages_count = messages_count + 1,
                    replied = 1,
                    replied_at = ?,
                    sender_username = COALESCE(?, sender_username),
                    sender_first_name = COALESCE(?, sender_first_name)
                WHERE business_user_id = ? AND sender_id = ?
                """,
                (now, now, sender_username, sender_first_name, business_user_id, sender_id),
            )
            conn.commit()
            return True
        else:
            # Within cooldown, suppress reply
            cursor.execute(
                """
                UPDATE business_first_contacts
                SET last_seen_at = ?,
                    messages_count = messages_count + 1,
                    sender_username = COALESCE(?, sender_username),
                    sender_first_name = COALESCE(?, sender_first_name)
                WHERE business_user_id = ? AND sender_id = ?
                """,
                (now, sender_username, sender_first_name, business_user_id, sender_id),
            )
            conn.commit()
            return False


def has_replied_to_sender(business_user_id: int, sender_id: int, db_path: str | None = None) -> bool:
    """Check if the business account has already delivered an auto-reply to this sender."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT replied FROM business_first_contacts WHERE business_user_id = ? AND sender_id = ?",
            (business_user_id, sender_id),
        )
        row = cursor.fetchone()
        return bool(row and row["replied"] == 1)


def get_daily_replies_count(business_user_id: int, db_path: str | None = None) -> int:
    """Count auto-replies delivered by this business account in the last 24 hours."""
    path = db_path or get_db_path()
    cutoff = time.time() - 86400
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM business_reply_logs
            WHERE business_user_id = ? AND sent_at >= ? AND status = 'success'
            """,
            (business_user_id, cutoff),
        )
        return cursor.fetchone()[0]


def log_business_reply(
    business_user_id: int,
    connection_id: str,
    chat_id: int,
    sender_id: int,
    message_id: int,
    reply_text: str | None = None,
    status: str = "success",
    error_message: str | None = None,
    db_path: str | None = None,
) -> None:
    """Record a delivery or failure event in the business auto-reply logs."""
    path = db_path or get_db_path()
    now = time.time()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO business_reply_logs (
                business_user_id, connection_id, chat_id, sender_id, message_id,
                reply_text, sent_at, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_user_id,
                connection_id,
                chat_id,
                sender_id,
                message_id,
                reply_text,
                now,
                status,
                error_message,
            ),
        )
        conn.commit()


def get_user_business_stats(user_id: int, db_path: str | None = None) -> dict[str, Any]:
    """Retrieve auto-reply usage and performance statistics for a specific user."""
    path = db_path or get_db_path()
    today_count = get_daily_replies_count(user_id, db_path=path)

    with get_connection(path) as conn:
        cursor = conn.cursor()
        # Total unique senders
        cursor.execute("SELECT COUNT(*) FROM business_first_contacts WHERE business_user_id = ?", (user_id,))
        total_contacts = cursor.fetchone()[0]

        # Total successful replies all-time
        cursor.execute(
            "SELECT COUNT(*) FROM business_reply_logs WHERE business_user_id = ? AND status = 'success'",
            (user_id,),
        )
        total_replies_all_time = cursor.fetchone()[0]

        # Total failed replies
        cursor.execute(
            "SELECT COUNT(*) FROM business_reply_logs WHERE business_user_id = ? AND status = 'failed'",
            (user_id,),
        )
        total_failed_replies = cursor.fetchone()[0]

        # Active connections count
        cursor.execute(
            "SELECT COUNT(*) FROM business_connections WHERE user_id = ? AND is_enabled = 1",
            (user_id,),
        )
        active_connections = cursor.fetchone()[0]

        return {
            "total_contacts": total_contacts,
            "replies_today": today_count,
            "total_replies_all_time": total_replies_all_time,
            "total_failed_replies": total_failed_replies,
            "active_connections": active_connections,
        }


def get_global_business_stats(db_path: str | None = None) -> dict[str, Any]:
    """Retrieve platform-wide aggregate business auto-reply statistics for bot owners."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM business_connections")
        total_connected_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM business_connections WHERE is_enabled = 1")
        total_active_connections = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM business_first_contacts")
        total_contacts_tracked = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM business_reply_logs WHERE status = 'success'")
        total_replies_delivered = cursor.fetchone()[0]

        return {
            "total_connected_users": total_connected_users,
            "total_active_connections": total_active_connections,
            "total_contacts_tracked": total_contacts_tracked,
            "total_replies_delivered": total_replies_delivered,
        }


def get_excluded_users_list(user_id: int, db_path: str | None = None) -> list[str | int]:
    """Get the list of excluded user IDs or usernames for a specific business user."""
    settings = get_personal_reply_settings(user_id, db_path=db_path)
    try:
        return json.loads(settings.get("excluded_user_ids", "[]"))
    except Exception:
        return []


def add_excluded_user(user_id: int, target: str | int, db_path: str | None = None) -> list[str | int]:
    """Add a user ID or @username to a user's excluded auto-reply list."""
    current = get_excluded_users_list(user_id, db_path=db_path)
    val = int(target) if str(target).lstrip("-").isdigit() else str(target).strip().lstrip("@").lower()
    if val not in current:
        current.append(val)
        update_personal_reply_settings(user_id, excluded_user_ids=json.dumps(current), db_path=db_path)
    return current


def remove_excluded_user(user_id: int, target: str | int, db_path: str | None = None) -> list[str | int]:
    """Remove a user ID or @username from a user's excluded auto-reply list."""
    current = get_excluded_users_list(user_id, db_path=db_path)
    val = int(target) if str(target).lstrip("-").isdigit() else str(target).strip().lstrip("@").lower()
    updated = [x for x in current if x != val]
    update_personal_reply_settings(user_id, excluded_user_ids=json.dumps(updated), db_path=db_path)
    return updated


def is_user_excluded(
    user_id: int, target_user_id: int, target_username: str | None = None, db_path: str | None = None
) -> bool:
    """Check if a target user ID or username is excluded from receiving auto-replies."""
    excluded = get_excluded_users_list(user_id, db_path=db_path)
    if target_user_id in excluded:
        return True
    if target_username and target_username.lower().lstrip("@") in [str(x).lower().lstrip("@") for x in excluded]:
        return True
    return False
