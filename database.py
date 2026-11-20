import json
import logging
import os
import threading
import time
import asyncio
from typing import Any
from uuid import uuid4
from pymongo import MongoClient, ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError
import config
from performance_monitor import record_latency

logger = logging.getLogger("Waguri.Database")

# =============================================================================
# MongoDB Connection & Client Management
# =============================================================================

_mongo_client: MongoClient | None = None


def get_db_path() -> str:
    """Retrieve the current database description dynamically from configuration."""
    db_name = getattr(config, "MONGODB_DB_NAME", "waguri_db")
    return f"MongoDB Atlas ({db_name})"


def get_client() -> MongoClient:
    """Retrieve or initialize the thread-safe singleton MongoDB client with connection pooling."""
    global _mongo_client
    if _mongo_client is None:
        uri = (
            getattr(config, "MONGODB_DIRECT_URI", None)
            or os.getenv("MONGODB_DIRECT_URI")
            or getattr(config, "MONGODB_URI", None)
            or os.getenv("MONGODB_URI")
            or os.getenv("MONGO_URI")
        )
        if not uri:
            raise RuntimeError(
                "MongoDB connection URI is not configured. "
                "Please set MONGODB_URI in your .env file."
            )
        _mongo_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            maxPoolSize=20,
            minPoolSize=1,
            maxIdleTimeMS=30000,
            waitQueueTimeoutMS=5000,
        )
    return _mongo_client


def close_db() -> None:
    """Close the shared PyMongo client during application shutdown."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


def get_db(db_name: str | None = None):
    """Retrieve the active MongoDB database instance."""
    client = get_client()
    target_name = db_name or getattr(config, "MONGODB_DB_NAME", None) or os.getenv("MONGODB_DB_NAME", "waguri_db")
    return client[target_name]


def get_next_sequence(sequence_name: str, db=None) -> int:
    """Generate an atomic sequential integer ID for collections needing incrementing IDs."""
    target_db = db if db is not None else get_db()
    ret = target_db["counters"].find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(ret["seq"])


def init_db(db_path: str | None = None) -> None:
    """
    Initialize MongoDB database collections, schema indices, and verify connectivity.
    Ensures optimal multi-tenant performance and atomic conflict resolution.
    """
    db = get_db()
    # Ping database to verify connection
    db.command("ping")

    # 1. Chats collection
    db["chats"].create_index([("chat_id", ASCENDING)], unique=True)
    db["chats"].create_index([("is_active", ASCENDING), ("chat_type", ASCENDING)])

    # 2. Chat Settings collection
    db["chat_settings"].create_index([("chat_id", ASCENDING)], unique=True)

    # 3. Chat Admins collection
    db["chat_admins"].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)], unique=True)

    # 4. Moderation Logs collection
    db["chat_moderation_logs"].create_index([("chat_id", ASCENDING), ("timestamp", DESCENDING)])
    db["chat_moderation_logs"].create_index([("timestamp", DESCENDING)])

    # 5. Warnings collection
    db["chat_warnings"].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)])

    # 6. Spam Incidents collection
    db["chat_spam_incidents"].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)], unique=True)

    # 7. Spam Messages collection
    db["chat_spam_messages"].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)])

    # 8. Link Whitelist collection
    db["chat_link_whitelist"].create_index([("chat_id", ASCENDING), ("domain", ASCENDING)], unique=True)

    # 9. Blacklist collection
    db["chat_blacklist"].create_index([("chat_id", ASCENDING), ("pattern_or_domain", ASCENDING)], unique=True)

    # 10. Statistics collection
    db["chat_statistics"].create_index([("chat_id", ASCENDING)], unique=True)

    # 11. Join Events collection
    db["chat_join_events"].create_index([("chat_id", ASCENDING), ("joined_at", DESCENDING)])

    # 12. User Restrictions collection
    db["user_restrictions"].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING), ("active", ASCENDING)])

    # 13. Callback Sessions collection
    db["callback_sessions"].create_index([("session_id", ASCENDING)], unique=True)

    # 14. Telegram Business Connections collection
    # 14. Admins (Web Dashboard Authentication) collection
    db["admins"].create_index([("email", ASCENDING)], unique=True)
    db["chat_abuse_warnings"].create_index([("chat_id", ASCENDING), ("user_id", ASCENDING)])
    db["scheduled_promotions"].create_index([("is_active", ASCENDING), ("next_run_at", ASCENDING)])
    db["scheduled_stickers"].create_index([("is_active", ASCENDING), ("next_run_at", ASCENDING)])
    db["scheduled_shayari"].create_index([("is_active", ASCENDING), ("next_run_at", ASCENDING)])

    logger.info("MongoDB database initialized and verified for multi-tenant operation at '%s'.", get_db_path())


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
    db = get_db()
    now = time.time()
    active_int = 1 if is_active else 0
    c_type = chat_type or "group"
    c_title = chat_title or "Chat"

    # Upsert chats record
    db["chats"].update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "chat_title": c_title,
                "chat_type": c_type,
                "is_active": active_int,
                "updated_at": now,
            },
            "$setOnInsert": {
                "added_at": now,
            },
        },
        upsert=True,
    )

    # Initialize default settings if not exists
    default_settings = {
        "chat_id": chat_id,
        "anti_link_enabled": 1 if getattr(config, "ANTI_LINK_ENABLED", True) else 0,
        "anti_bio_link_enabled": 1 if getattr(config, "ANTI_BIO_LINK_ENABLED", True) else 0,
        "clean_service_enabled": 1 if getattr(config, "CLEAN_SERVICE_ENABLED", True) else 0,
        "anti_spam_enabled": 1 if getattr(config, "ANTI_SPAM_ENABLED", True) else 0,
        "flood_detection_enabled": 1 if getattr(config, "FLOOD_DETECTION_ENABLED", True) else 0,
        "flood_threshold_messages": getattr(config, "FLOOD_MESSAGE_LIMIT", 8),
        "flood_window_seconds": getattr(config, "FLOOD_WINDOW_SECONDS", 10),
        "warning_system_enabled": 1,
        "auto_restrict_enabled": 1,
        "anti_forward_enabled": 1 if getattr(config, "ANTI_FORWARD_ENABLED", False) else 0,
        "anti_join_spam_enabled": 1 if getattr(config, "ANTI_JOIN_SPAM_ENABLED", False) else 0,
        "anti_bot_enabled": 1 if getattr(config, "ANTI_BOT_ENABLED", False) else 0,
        "media_restrictions_enabled": 1 if getattr(config, "MEDIA_RESTRICTIONS_ENABLED", False) else 0,
        "allowed_media_types": json.dumps(getattr(config, "DEFAULT_ALLOWED_MEDIA", {})),
        "spam_window_seconds": getattr(config, "SPAM_WINDOW_SECONDS", 30),
        "warning_limit": getattr(config, "SPAM_WARNING_LIMIT", 2),
        "restriction_duration_seconds": getattr(config, "SPAM_RESTRICTION_SECONDS", 86400),
        "warning_delete_after_seconds": getattr(config, "WARNING_DELETE_AFTER_SECONDS", 10),
        "custom_warning_msg_1": None,
        "custom_warning_msg_2": None,
        "raid_mode_enabled": 0,
        "updated_at": now,
    }

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$setOnInsert": default_settings},
        upsert=True,
    )
    invalidate_group_settings_cache(chat_id)


def set_chat_active(chat_id: int, is_active: bool, db_path: str | None = None) -> None:
    """Mark a group or channel active or inactive upon bot addition/removal."""
    db = get_db()
    active_int = 1 if is_active else 0
    now = time.time()
    db["chats"].update_one(
        {"chat_id": chat_id},
        {"$set": {"is_active": active_int, "updated_at": now}},
    )
    invalidate_group_settings_cache(chat_id)


# High-performance in-memory cache for group settings
_settings_cache: dict[int, tuple[float, dict[str, Any]]] = {}
_settings_lock = threading.Lock()
SETTINGS_CACHE_TTL: float = 120.0  # 2 minutes TTL for group settings
SETTINGS_CACHE_MAX_SIZE = 2000


async def run_db(call: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous PyMongo operation without blocking the Telegram event loop."""
    started = time.perf_counter()
    try:
        return await asyncio.to_thread(call, *args, **kwargs)
    finally:
        record_latency("database", time.perf_counter() - started)


def invalidate_group_settings_cache(chat_id: int | None = None) -> None:
    """Invalidate cached settings for a group or all groups."""
    with _settings_lock:
        if chat_id is None:
            _settings_cache.clear()
        else:
            _settings_cache.pop(chat_id, None)


def _cache_group_settings(chat_id: int, now: float, result: dict[str, Any]) -> None:
    with _settings_lock:
        expired = [
            cached_id
            for cached_id, (cached_at, _) in _settings_cache.items()
            if now - cached_at >= SETTINGS_CACHE_TTL
        ]
        for cached_id in expired:
            _settings_cache.pop(cached_id, None)
        if len(_settings_cache) >= SETTINGS_CACHE_MAX_SIZE:
            oldest = next(iter(_settings_cache))
            _settings_cache.pop(oldest, None)
        _settings_cache[chat_id] = (now, result)


def get_group_settings(chat_id: int, db_path: str | None = None) -> dict[str, Any]:
    """
    Retrieve comprehensive per-group or per-channel settings.
    If the chat has no stored configuration, initializes default settings seamlessly.
    Uses in-memory cache with immediate invalidation to achieve sub-millisecond responses in GC.
    """
    now = time.time()
    with _settings_lock:
        cached = _settings_cache.get(chat_id)
        if cached and (now - cached[0] < SETTINGS_CACHE_TTL):
            return cached[1].copy()

    db = get_db()
    s_doc = db["chat_settings"].find_one({"chat_id": chat_id})
    c_doc = db["chats"].find_one({"chat_id": chat_id})

    if s_doc:
        allowed_media_raw = s_doc.get("allowed_media_types")
        if isinstance(allowed_media_raw, dict):
            allowed_media = allowed_media_raw
        elif isinstance(allowed_media_raw, str):
            try:
                allowed_media = json.loads(allowed_media_raw)
            except Exception:
                allowed_media = getattr(config, "DEFAULT_ALLOWED_MEDIA", {})
        else:
            allowed_media = getattr(config, "DEFAULT_ALLOWED_MEDIA", {})

        chat_title = c_doc.get("chat_title") if c_doc else "Unnamed Chat"
        chat_type = c_doc.get("chat_type") if c_doc else "group"
        added_at = c_doc.get("added_at") if c_doc else 0.0
        is_active = bool(c_doc.get("is_active", 1)) if c_doc else True

        result = {
            "chat_id": chat_id,
            "chat_title": chat_title or "Unnamed Chat",
            "chat_type": chat_type or "group",
            "added_at": float(added_at or 0.0),
            "anti_link_enabled": bool(s_doc.get("anti_link_enabled", 1)),
            "anti_bio_link_enabled": bool(s_doc.get("anti_bio_link_enabled", 1)),
            "clean_service_enabled": bool(s_doc.get("clean_service_enabled", 1)),
            "anti_spam_enabled": bool(s_doc.get("anti_spam_enabled", 1)),
            "flood_detection_enabled": bool(s_doc.get("flood_detection_enabled", 1)),
            "flood_threshold_messages": int(s_doc.get("flood_threshold_messages") or 8),
            "flood_window_seconds": int(s_doc.get("flood_window_seconds") or 10),
            "warning_system_enabled": bool(s_doc.get("warning_system_enabled", 1)),
            "auto_restrict_enabled": bool(s_doc.get("auto_restrict_enabled", 1)),
            "anti_forward_enabled": bool(s_doc.get("anti_forward_enabled", 0)),
            "anti_join_spam_enabled": bool(s_doc.get("anti_join_spam_enabled", 0)),
            "anti_bot_enabled": bool(s_doc.get("anti_bot_enabled", 0)),
            "media_restrictions_enabled": bool(s_doc.get("media_restrictions_enabled", 0)),
            "allowed_media_types": allowed_media,
            "spam_window_seconds": int(s_doc.get("spam_window_seconds") or 30),
            "warning_limit": int(s_doc.get("warning_limit") or 2),
            "restriction_duration_seconds": int(s_doc.get("restriction_duration_seconds") or 86400),
            "warning_delete_after_seconds": int(s_doc.get("warning_delete_after_seconds") or 10),
            "custom_warning_msg_1": s_doc.get("custom_warning_msg_1"),
            "custom_warning_msg_2": s_doc.get("custom_warning_msg_2"),
            "raid_mode_enabled": bool(s_doc.get("raid_mode_enabled", 0)),
            # Abuse Detection & Auto-Moderation System Configuration
            "abuse_detection_enabled": bool(s_doc.get("abuse_detection_enabled", 1)),
            "abuse_sexual_language": bool(s_doc.get("abuse_sexual_language", 1)),
            "abuse_general_language": bool(s_doc.get("abuse_general_language", 1)),
            "abuse_hindi_hinglish": bool(s_doc.get("abuse_hindi_hinglish", 1)),
            "abuse_harassment": bool(s_doc.get("abuse_harassment", 1)),
            "abuse_threats": bool(s_doc.get("abuse_threats", 1)),
            "abuse_bypass_detection": bool(s_doc.get("abuse_bypass_detection", 1)),
            "abuse_warning_system": bool(s_doc.get("abuse_warning_system", 1)),
            "abuse_warning_limit": int(s_doc.get("abuse_warning_limit") or 1),
            "abuse_exempt_admins": bool(s_doc.get("abuse_exempt_admins", 0)),
            "abuse_mute_duration_minutes": int(s_doc.get("abuse_mute_duration_minutes") or 30),
            "abuse_warning_expiry_hours": int(s_doc.get("abuse_warning_expiry_hours") or 24),
            "abuse_delete_violating": bool(s_doc.get("abuse_delete_violating", 1)),
            "abuse_custom_blocked_words": s_doc.get("abuse_custom_blocked_words") or [],
            "abuse_custom_allowed_words": s_doc.get("abuse_custom_allowed_words") or [],
            "abuse_trusted_users": s_doc.get("abuse_trusted_users") or [],
            "is_active": is_active,
            "updated_at": float(s_doc.get("updated_at") or 0.0),
        }
        _cache_group_settings(chat_id, now, result)
        return result.copy()

    # If document does not exist yet, register and return default config
    register_or_update_chat(chat_id, None, None, is_active=True)
    return get_group_settings(chat_id)


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
        "abuse_detection_enabled",
        "abuse_sexual_language",
        "abuse_general_language",
        "abuse_hindi_hinglish",
        "abuse_harassment",
        "abuse_threats",
        "abuse_bypass_detection",
        "abuse_warning_system",
        "abuse_delete_violating",
    }
    if feature_col not in valid_cols:
        raise ValueError(f"Invalid feature column: {feature_col}")

    db = get_db()
    val = 1 if enabled else 0
    now = time.time()

    # Ensure registered
    if not db["chat_settings"].find_one({"chat_id": chat_id}):
        register_or_update_chat(chat_id, None, None, is_active=True)

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$set": {feature_col: val, "updated_at": now}},
    )
    invalidate_group_settings_cache(chat_id)


def update_group_numeric_setting(chat_id: int, setting_col: str, value: int, db_path: str | None = None) -> None:
    """Update a numeric configuration setting for a group."""
    valid_cols = {
        "spam_window_seconds",
        "warning_limit",
        "restriction_duration_seconds",
        "warning_delete_after_seconds",
        "flood_threshold_messages",
        "flood_window_seconds",
        "abuse_warning_limit",
        "abuse_mute_duration_minutes",
        "abuse_warning_expiry_hours",
    }
    if setting_col not in valid_cols:
        raise ValueError(f"Invalid setting column: {setting_col}")

    db = get_db()
    now = time.time()

    if not db["chat_settings"].find_one({"chat_id": chat_id}):
        register_or_update_chat(chat_id, None, None, is_active=True)

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$set": {setting_col: int(value), "updated_at": now}},
    )
    invalidate_group_settings_cache(chat_id)


def update_group_text_setting(chat_id: int, setting_col: str, value: str | None, db_path: str | None = None) -> None:
    """Update a text configuration setting for a group."""
    valid_cols = {
        "custom_warning_msg_1",
        "custom_warning_msg_2",
        "allowed_media_types",
    }
    if setting_col not in valid_cols:
        raise ValueError(f"Invalid text setting column: {setting_col}")

    db = get_db()
    now = time.time()

    if not db["chat_settings"].find_one({"chat_id": chat_id}):
        register_or_update_chat(chat_id, None, None, is_active=True)

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$set": {setting_col: value, "updated_at": now}},
    )
    invalidate_group_settings_cache(chat_id)


def set_group_anti_link(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable anti-link protection for a specific group."""
    update_group_feature(chat_id, "anti_link_enabled", enabled)


def set_group_anti_bio_link(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable anti-bio-link protection for a specific group."""
    update_group_feature(chat_id, "anti_bio_link_enabled", enabled)


def set_group_clean_service(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable cleaning service messages for a specific group."""
    update_group_feature(chat_id, "clean_service_enabled", enabled)


def set_group_anti_spam(chat_id: int, enabled: bool, db_path: str | None = None) -> None:
    """Enable or disable anti-spam protection for a specific group."""
    update_group_feature(chat_id, "anti_spam_enabled", enabled)


# =============================================================================
# Media Restrictions Management
# =============================================================================

def get_media_restrictions(chat_id: int, db_path: str | None = None) -> dict[str, bool]:
    """Retrieve allowed media types dictionary for a group."""
    settings = get_group_settings(chat_id)
    allowed = settings.get("allowed_media_types")
    if isinstance(allowed, dict):
        return allowed
    return getattr(config, "DEFAULT_ALLOWED_MEDIA", {})


def set_media_restriction(chat_id: int, media_type: str, allowed: bool, db_path: str | None = None) -> None:
    """Toggle whether a specific media type (photo, video, sticker, etc.) is allowed."""
    current = get_media_restrictions(chat_id)
    current[media_type] = allowed
    update_group_text_setting(chat_id, "allowed_media_types", json.dumps(current))


# =============================================================================
# Link Whitelist & Blacklist Management
# =============================================================================

def add_whitelisted_domain(chat_id: int, domain: str, added_by: int = 0, db_path: str | None = None) -> bool:
    """Add a domain to the group's link whitelist."""
    clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
    now = time.time()
    try:
        db = get_db()
        db["chat_link_whitelist"].update_one(
            {"chat_id": chat_id, "domain": clean_domain},
            {"$set": {"added_by": added_by, "added_at": now}},
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.error("Failed to add whitelist domain '%s' in chat %s: %s", domain, chat_id, exc)
        return False


def remove_whitelisted_domain(chat_id: int, domain: str, db_path: str | None = None) -> bool:
    """Remove a domain from the group's link whitelist."""
    clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
    db = get_db()
    res = db["chat_link_whitelist"].delete_one({"chat_id": chat_id, "domain": clean_domain})
    return res.deleted_count > 0


def get_whitelisted_domains(chat_id: int, db_path: str | None = None) -> list[str]:
    """Retrieve all whitelisted domains for a group."""
    db = get_db()
    cursor = db["chat_link_whitelist"].find({"chat_id": chat_id}).sort("domain", ASCENDING)
    return [doc["domain"] for doc in cursor]


def is_domain_whitelisted(chat_id: int, domain: str, db_path: str | None = None) -> bool:
    """Check if a domain or URL is whitelisted in the group."""
    clean_domain = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]
    whitelisted = get_whitelisted_domains(chat_id)
    for w in whitelisted:
        if clean_domain == w or clean_domain.endswith("." + w):
            return True
    return False


def add_blacklisted_pattern(chat_id: int, pattern: str, added_by: int = 0, db_path: str | None = None) -> bool:
    """Add a domain or keyword pattern to the group's blacklist."""
    clean_pattern = pattern.strip().lower()
    now = time.time()
    try:
        db = get_db()
        db["chat_blacklist"].update_one(
            {"chat_id": chat_id, "pattern_or_domain": clean_pattern},
            {"$set": {"added_by": added_by, "added_at": now}},
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.error("Failed to add blacklist pattern '%s' in chat %s: %s", pattern, chat_id, exc)
        return False


def remove_blacklisted_pattern(chat_id: int, pattern: str, db_path: str | None = None) -> bool:
    """Remove a pattern from the group's blacklist."""
    clean_pattern = pattern.strip().lower()
    db = get_db()
    res = db["chat_blacklist"].delete_one({"chat_id": chat_id, "pattern_or_domain": clean_pattern})
    return res.deleted_count > 0


def get_blacklisted_patterns(chat_id: int, db_path: str | None = None) -> list[str]:
    """Retrieve all blacklisted patterns for a group."""
    db = get_db()
    cursor = db["chat_blacklist"].find({"chat_id": chat_id}).sort("pattern_or_domain", ASCENDING)
    return [doc["pattern_or_domain"] for doc in cursor]


def is_content_blacklisted(chat_id: int, text: str, db_path: str | None = None) -> bool:
    """Check if message text contains any blacklisted patterns."""
    if not text:
        return False
    lower_text = text.lower()
    patterns = get_blacklisted_patterns(chat_id)
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
        "abuse_deleted",
    }
    if stat_name not in valid_stats:
        return

    db = get_db()
    now = time.time()

    set_on_insert: dict[str, Any] = {"chat_id": chat_id}
    for s in valid_stats:
        if s != stat_name:
            set_on_insert[s] = 0

    update_doc: dict[str, Any] = {
        "$inc": {stat_name: count},
        "$set": {"updated_at": now},
        "$setOnInsert": set_on_insert,
    }
    if chat_title:
        update_doc["$set"]["chat_title"] = chat_title

    db["chat_statistics"].update_one(
        {"chat_id": chat_id},
        update_doc,
        upsert=True,
    )


def get_group_stats(chat_id: int, db_path: str | None = None) -> dict[str, Any]:
    """Retrieve moderation statistics for a specific group or channel."""
    db = get_db()
    doc = db["chat_statistics"].find_one({"chat_id": chat_id})
    if not doc:
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
            "abuse_deleted": 0,
            "updated_at": 0.0,
        }

    return {
        "chat_id": chat_id,
        "chat_title": doc.get("chat_title") or "Unnamed Chat",
        "total_messages_checked": int(doc.get("total_messages_checked") or 0),
        "links_deleted": int(doc.get("links_deleted") or 0),
        "spam_deleted": int(doc.get("spam_deleted") or 0),
        "warnings_issued": int(doc.get("warnings_issued") or 0),
        "restrictions_applied": int(doc.get("restrictions_applied") or 0),
        "banned_members": int(doc.get("banned_members") or 0),
        "forwards_deleted": int(doc.get("forwards_deleted") or 0),
        "media_deleted": int(doc.get("media_deleted") or 0),
        "raid_actions_taken": int(doc.get("raid_actions_taken") or 0),
        "abuse_deleted": int(doc.get("abuse_deleted") or 0),
        "updated_at": float(doc.get("updated_at") or 0.0),
    }


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
    """Record an audit trail event for a moderation action in MongoDB."""
    db = get_db()
    now = time.time()
    next_id = get_next_sequence("chat_moderation_logs", db=db)
    db["chat_moderation_logs"].insert_one(
        {
            "id": next_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "action": action,
            "details": details,
            "timestamp": now,
        }
    )


def get_recent_moderation_logs(chat_id: int, limit: int = 15, db_path: str | None = None) -> list[dict[str, Any]]:
    """Retrieve recent moderation audit actions for a specific group."""
    db = get_db()
    cursor = (
        db["chat_moderation_logs"]
        .find({"chat_id": chat_id})
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    results = []
    for doc in cursor:
        results.append(
            {
                "id": doc.get("id"),
                "chat_id": doc.get("chat_id"),
                "user_id": doc.get("user_id"),
                "action": doc.get("action"),
                "details": doc.get("details"),
                "timestamp": float(doc.get("timestamp") or 0.0),
            }
        )
    return results


# =============================================================================
# Spam Incidents & Recorded Spam Messages
# =============================================================================

def get_active_incident(chat_id: int, user_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    """Retrieve the active spam incident for a given user in a group."""
    db = get_db()
    doc = db["chat_spam_incidents"].find_one({"chat_id": chat_id, "user_id": user_id})
    if not doc:
        return None

    raw_msg_ids = doc.get("message_ids")
    if isinstance(raw_msg_ids, list):
        message_ids = raw_msg_ids
    elif isinstance(raw_msg_ids, str):
        try:
            message_ids = json.loads(raw_msg_ids)
        except Exception:
            message_ids = []
    else:
        message_ids = []

    return {
        "chat_id": doc["chat_id"],
        "user_id": doc["user_id"],
        "message_fingerprint": doc.get("message_fingerprint", ""),
        "count": int(doc.get("count") or 1),
        "last_message_time": float(doc.get("last_message_time") or 0.0),
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
    db = get_db()
    db["chat_spam_incidents"].update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "message_fingerprint": message_fingerprint,
                "count": count,
                "last_message_time": last_message_time,
                "message_ids": message_ids,
            }
        },
        upsert=True,
    )


def clear_active_incident(chat_id: int, user_id: int, db_path: str | None = None) -> None:
    """Remove an active spam incident after expiration or restriction."""
    db = get_db()
    db["chat_spam_incidents"].delete_one({"chat_id": chat_id, "user_id": user_id})


# =============================================================================
# Warning Tracking Management
# =============================================================================

def add_user_warning(chat_id: int, user_id: int, reason: str, db_path: str | None = None) -> int:
    """Record a warning issued to a user and return their total active warning count."""
    db = get_db()
    now = time.time()
    current_count = db["chat_warnings"].count_documents({"chat_id": chat_id, "user_id": user_id})
    new_warn_num = current_count + 1
    next_id = get_next_sequence("chat_warnings", db=db)

    db["chat_warnings"].insert_one(
        {
            "id": next_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "warning_number": new_warn_num,
            "reason": reason,
            "issued_at": now,
        }
    )
    return new_warn_num


def get_user_warnings_count(chat_id: int, user_id: int, db_path: str | None = None) -> int:
    """Retrieve the total warning count issued to a user in a group."""
    db = get_db()
    return db["chat_warnings"].count_documents({"chat_id": chat_id, "user_id": user_id})


def reset_user_warnings(chat_id: int, user_id: int, db_path: str | None = None) -> int:
    """Clear all warnings for a user in a group and return the number of cleared records."""
    db = get_db()
    res = db["chat_warnings"].delete_many({"chat_id": chat_id, "user_id": user_id})
    return res.deleted_count


# =============================================================================
# Abuse Detection & Auto-Moderation Database Management
# =============================================================================

def get_abuse_settings(chat_id: int) -> dict[str, Any]:
    """Retrieve per-group Abuse Detection settings."""
    settings = get_group_settings(chat_id)
    return {
        "chat_id": chat_id,
        "abuse_detection_enabled": settings.get("abuse_detection_enabled", True),
        "abuse_sexual_language": settings.get("abuse_sexual_language", True),
        "abuse_general_language": settings.get("abuse_general_language", True),
        "abuse_hindi_hinglish": settings.get("abuse_hindi_hinglish", True),
        "abuse_harassment": settings.get("abuse_harassment", True),
        "abuse_threats": settings.get("abuse_threats", True),
        "abuse_bypass_detection": settings.get("abuse_bypass_detection", True),
        "abuse_warning_system": settings.get("abuse_warning_system", True),
        "abuse_warning_limit": settings.get("abuse_warning_limit", 1),
        "abuse_exempt_admins": settings.get("abuse_exempt_admins", False),
        "abuse_mute_duration_minutes": settings.get("abuse_mute_duration_minutes", 30),
        "abuse_warning_expiry_hours": settings.get("abuse_warning_expiry_hours", 24),
        "abuse_delete_violating": settings.get("abuse_delete_violating", True),
        "abuse_custom_blocked_words": settings.get("abuse_custom_blocked_words", []),
        "abuse_custom_allowed_words": settings.get("abuse_custom_allowed_words", []),
        "abuse_trusted_users": settings.get("abuse_trusted_users", []),
    }


def update_abuse_settings(chat_id: int, **kwargs) -> None:
    """Update one or more Abuse moderation settings for a group."""
    db = get_db()
    now = time.time()
    set_fields: dict[str, Any] = {"updated_at": now}
    for k, v in kwargs.items():
        set_fields[k] = v

    # Ensure settings document exists
    if not db["chat_settings"].find_one({"chat_id": chat_id}):
        register_or_update_chat(chat_id, None, None, is_active=True)

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$set": set_fields},
    )


def get_abuse_custom_keywords(chat_id: int) -> tuple[list[str], list[str]]:
    """Retrieve custom blocked and allowed keywords for a group. Returns (blocked_list, allowed_list)."""
    settings = get_group_settings(chat_id)
    blocked = settings.get("abuse_custom_blocked_words") or []
    allowed = settings.get("abuse_custom_allowed_words") or []
    return list(blocked), list(allowed)


def add_abuse_custom_keyword(chat_id: int, word: str, is_blocked: bool = True) -> bool:
    """Add a custom blocked or allowed keyword for a group."""
    clean_word = word.strip().lower()
    if not clean_word:
        return False

    db = get_db()
    now = time.time()
    field_name = "abuse_custom_blocked_words" if is_blocked else "abuse_custom_allowed_words"

    # Ensure chat registered
    if not db["chat_settings"].find_one({"chat_id": chat_id}):
        register_or_update_chat(chat_id, None, None, is_active=True)

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$addToSet": {field_name: clean_word}, "$set": {"updated_at": now}},
    )
    return True


def remove_abuse_custom_keyword(chat_id: int, word: str) -> bool:
    """Remove a custom keyword from both blocked and allowed lists."""
    clean_word = word.strip().lower()
    if not clean_word:
        return False

    db = get_db()
    now = time.time()
    res = db["chat_settings"].update_one(
        {
            "chat_id": chat_id,
            "$or": [
                {"abuse_custom_blocked_words": clean_word},
                {"abuse_custom_allowed_words": clean_word},
            ],
        },
        {
            "$pull": {
                "abuse_custom_blocked_words": clean_word,
                "abuse_custom_allowed_words": clean_word,
            },
            "$set": {"updated_at": now},
        },
    )
    return res.modified_count > 0


def add_user_abuse_warning(
    chat_id: int,
    user_id: int,
    reason: str,
    score: int = 50,
    category: str = "general_abusive",
    message_id: int | None = None,
) -> int:
    """Record an abuse warning issued to a user and return their active warning count."""
    db = get_db()
    now = time.time()
    settings = get_group_settings(chat_id)
    expiry_hours = settings.get("abuse_warning_expiry_hours", 24)
    cutoff = now - (expiry_hours * 3600)

    # Active warnings only (issued within expiry window)
    active_count = db["chat_warnings"].count_documents({
        "chat_id": chat_id,
        "user_id": user_id,
        "category": "abuse",
        "issued_at": {"$gte": cutoff},
    })
    new_warn_num = active_count + 1
    next_id = get_next_sequence("chat_warnings", db=db)

    db["chat_warnings"].insert_one({
        "id": next_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "warning_number": new_warn_num,
        "category": "abuse",
        "abuse_category": category,
        "score": score,
        "message_id": message_id,
        "reason": reason,
        "issued_at": now,
        "expires_at": now + (expiry_hours * 3600),
    })
    return new_warn_num


def get_user_abuse_warnings(
    chat_id: int,
    user_id: int,
    expiry_hours: int = 24,
) -> list[dict[str, Any]]:
    """Retrieve all active abuse warnings for a user in a group."""
    db = get_db()
    now = time.time()
    cutoff = now - (expiry_hours * 3600)
    cursor = db["chat_warnings"].find({
        "chat_id": chat_id,
        "user_id": user_id,
        "category": "abuse",
        "issued_at": {"$gte": cutoff},
    }).sort("issued_at", DESCENDING)

    results = []
    for doc in cursor:
        results.append({
            "id": doc.get("id"),
            "chat_id": doc.get("chat_id"),
            "user_id": doc.get("user_id"),
            "warning_number": doc.get("warning_number"),
            "reason": doc.get("reason"),
            "abuse_category": doc.get("abuse_category", "general_abusive"),
            "score": doc.get("score", 50),
            "issued_at": float(doc.get("issued_at") or 0.0),
            "expires_at": float(doc.get("expires_at") or 0.0),
        })
    return results


def get_user_abuse_warnings_count(
    chat_id: int,
    user_id: int,
    expiry_hours: int = 24,
) -> int:
    """Retrieve active warning count for a user in a group."""
    db = get_db()
    now = time.time()
    cutoff = now - (expiry_hours * 3600)
    return db["chat_warnings"].count_documents({
        "chat_id": chat_id,
        "user_id": user_id,
        "category": "abuse",
        "issued_at": {"$gte": cutoff},
    })


def reset_user_abuse_warnings(chat_id: int, user_id: int) -> int:
    """Clear all abuse warnings for a user in a group and return cleared count."""
    db = get_db()
    res = db["chat_warnings"].delete_many({
        "chat_id": chat_id,
        "user_id": user_id,
        "category": "abuse",
    })
    return res.deleted_count


def get_abuse_moderation_logs(chat_id: int, limit: int = 15) -> list[dict[str, Any]]:
    """Retrieve recent abuse moderation logs for a group."""
    db = get_db()
    cursor = db["chat_moderation_logs"].find({
        "chat_id": chat_id,
        "action": {"$regex": r"^ABUSE_"},
    }).sort("timestamp", DESCENDING).limit(limit)

    results = []
    for doc in cursor:
        results.append({
            "id": doc.get("id"),
            "chat_id": doc.get("chat_id"),
            "user_id": doc.get("user_id"),
            "action": doc.get("action"),
            "details": doc.get("details"),
            "timestamp": float(doc.get("timestamp") or 0.0),
        })
    return results


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
    """Record an applied restriction (mute or ban) into MongoDB."""
    db = get_db()
    next_id = get_next_sequence("user_restrictions", db=db)
    db["user_restrictions"].insert_one(
        {
            "id": next_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "action": action,
            "reason": reason,
            "previous_permissions": previous_permissions,
            "restricted_at": restricted_at,
            "expires_at": expires_at,
            "active": 1,
        }
    )
    return next_id


def lift_active_restrictions(chat_id: int, user_id: int, db_path: str | None = None) -> int:
    """Mark all active restrictions for a user in a group as lifted/inactive."""
    db = get_db()
    res = db["user_restrictions"].update_many(
        {"chat_id": chat_id, "user_id": user_id, "active": 1},
        {"$set": {"active": 0}},
    )
    return res.modified_count


def get_user_restrictions(chat_id: int, user_id: int, db_path: str | None = None) -> list[dict[str, Any]]:
    """Retrieve restriction records for a user in a specific group."""
    db = get_db()
    cursor = (
        db["user_restrictions"]
        .find({"chat_id": chat_id, "user_id": user_id})
        .sort("restricted_at", DESCENDING)
    )
    results = []
    for doc in cursor:
        results.append(
            {
                "id": doc.get("id"),
                "chat_id": doc.get("chat_id"),
                "user_id": doc.get("user_id"),
                "username": doc.get("username"),
                "action": doc.get("action", "mute"),
                "reason": doc.get("reason", ""),
                "previous_permissions": doc.get("previous_permissions"),
                "restricted_at": float(doc.get("restricted_at") or 0.0),
                "expires_at": float(doc.get("expires_at") or 0.0),
                "active": int(doc.get("active") or 0),
            }
        )
    return results


# =============================================================================
# Join Events & Anti-Join Spam Tracking
# =============================================================================

def record_join_event(chat_id: int, user_id: int, is_bot: bool = False, db_path: str | None = None) -> None:
    """Record a member join event to track bursts and anti-bot activity."""
    db = get_db()
    now = time.time()
    db["chat_join_events"].insert_one(
        {
            "chat_id": chat_id,
            "user_id": user_id,
            "is_bot": 1 if is_bot else 0,
            "joined_at": now,
        }
    )


def get_recent_join_events_count(chat_id: int, window_seconds: int = 10, db_path: str | None = None) -> int:
    """Count how many users joined the group within the last window_seconds."""
    db = get_db()
    cutoff = time.time() - window_seconds
    return db["chat_join_events"].count_documents({"chat_id": chat_id, "joined_at": {"$gte": cutoff}})


# =============================================================================
# Multi-Group / Multi-Channel Owner Queries
# =============================================================================

def get_registered_chats(
    chat_type: str | None = None, active_only: bool = True, db_path: str | None = None
) -> list[dict[str, Any]]:
    """Retrieve registered chats, optionally filtered by chat_type ('group', 'channel')."""
    db = get_db()
    filter_query: dict[str, Any] = {}
    if active_only:
        filter_query["is_active"] = 1

    if chat_type:
        if chat_type == "channel":
            filter_query["chat_type"] = "channel"
        else:
            filter_query["chat_type"] = {"$in": ["group", "supergroup"]}

    cursor = db["chats"].find(filter_query).sort("chat_title", ASCENDING)
    results = []
    for doc in cursor:
        results.append(
            {
                "chat_id": doc.get("chat_id"),
                "chat_title": doc.get("chat_title") or ("Broadcast Channel" if doc.get("chat_type") == "channel" else "Group Chat"),
                "chat_type": doc.get("chat_type") or "group",
                "added_at": float(doc.get("added_at") or 0.0),
                "is_active": int(doc.get("is_active", 1)),
                "updated_at": float(doc.get("updated_at") or 0.0),
            }
        )
    return results


def get_global_bot_stats(db_path: str | None = None) -> dict[str, Any]:
    """Retrieve aggregate statistics across all registered groups and channels for /owner."""
    db = get_db()

    active_groups = db["chats"].count_documents({"is_active": 1, "chat_type": {"$in": ["group", "supergroup"]}})
    active_channels = db["chats"].count_documents({"is_active": 1, "chat_type": "channel"})
    total_chats = db["chats"].count_documents({})

    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_messages": {"$sum": "$total_messages_checked"},
                "total_links_deleted": {"$sum": "$links_deleted"},
                "total_spam_deleted": {"$sum": "$spam_deleted"},
                "total_warnings": {"$sum": "$warnings_issued"},
                "total_restrictions": {"$sum": "$restrictions_applied"},
                "total_bans": {"$sum": "$banned_members"},
            }
        }
    ]
    agg = list(db["chat_statistics"].aggregate(pipeline))
    stats_data = agg[0] if agg else {}

    return {
        "active_groups": active_groups,
        "active_channels": active_channels,
        "total_registered_chats": total_chats,
        "total_messages": int(stats_data.get("total_messages") or 0),
        "total_links_deleted": int(stats_data.get("total_links_deleted") or 0),
        "total_spam_deleted": int(stats_data.get("total_spam_deleted") or 0),
        "total_warnings": int(stats_data.get("total_warnings") or 0),
        "total_restrictions": int(stats_data.get("total_restrictions") or 0),
        "total_bans": int(stats_data.get("total_bans") or 0),
    }




# =============================================================================
# Background Job Scheduler Leases
# =============================================================================

def claim_scheduled_job(
    collection_name: str,
    item_id: int,
    scheduled_time: str | None,
    lease_seconds: int = 300,
) -> str | None:
    """Atomically lease a due item so parallel scheduler workers cannot dispatch it."""
    now = time.time()
    lease_id = uuid4().hex
    claimed = get_db()[collection_name].find_one_and_update(
        {
            "id": item_id,
            "status": "active",
            "scheduled_time": scheduled_time,
            "$or": [
                {"dispatch_lease_until": {"$exists": False}},
                {"dispatch_lease_until": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "dispatch_lease_id": lease_id,
                "dispatch_lease_until": now + lease_seconds,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return lease_id if claimed else None


def release_scheduled_job(collection_name: str, item_id: int, lease_id: str) -> None:
    """Release a scheduled-item lease only when it is still owned by this worker."""
    get_db()[collection_name].update_one(
        {"id": item_id, "dispatch_lease_id": lease_id},
        {"$unset": {"dispatch_lease_id": "", "dispatch_lease_until": ""}},
    )



