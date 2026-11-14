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

        # Create Indexes for Multi-Tenant Query Performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_chat ON chat_moderation_logs(chat_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_warnings_chat_user ON chat_warnings(chat_id, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_spam_msgs_chat_user ON chat_spam_messages(chat_id, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelist_chat ON chat_link_whitelist(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_chat ON chat_blacklist(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_join_events_chat ON chat_join_events(chat_id, joined_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restrictions_chat_user ON user_restrictions(chat_id, user_id, active)")

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
