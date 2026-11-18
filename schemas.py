"""
MongoDB Schema Definitions, Validation, and Unified CRUD Operations for Waguri Bot.

Covers:
1. Promotions (scheduled_promotions, promotion_send_logs)
2. Stickers (scheduled_stickers, sticker_send_logs)
3. Shayari (shayari_content, scheduled_shayari, shayari_send_logs)
4. Users (business_connections, personal_reply_settings, personal_reply_templates, business_first_contacts)
5. Chats (chats, chat_settings, chat_statistics, chat_moderation_logs, chat_warnings)
6. Overview (daily_moderation_stats, telemetry aggregator)
7. Settings (system_settings, global emergency overrides, moderation defaults)
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
import config
from database import get_db, get_next_sequence, get_db_path

logger = logging.getLogger("Waguri.Schemas")

# =============================================================================
# 1. Formal MongoDB JSON Schema Specifications ($jsonSchema)
# =============================================================================

PROMOTIONS_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["id", "title", "message", "status", "scheduled_time"],
    "properties": {
        "id": {"bsonType": "number", "description": "Auto-incrementing unique integer ID"},
        "title": {"bsonType": "string", "description": "Promotion announcement title"},
        "message": {"bsonType": "string", "description": "Main promotion text content"},
        "link_url": {"bsonType": ["string", "null"], "description": "Optional inline button target URL"},
        "button_text": {"bsonType": ["string", "null"], "description": "Inline button CTA label"},
        "target_type": {"enum": ["all_gc", "selected"], "description": "Target group selection strategy"},
        "target_chat_ids": {"bsonType": "string", "description": "JSON serialized array of target chat IDs"},
        "schedule_type": {"enum": ["once", "recurring"], "description": "Dispatch schedule mode"},
        "scheduled_time": {"bsonType": "string", "description": "ISO timestamp for scheduled broadcast"},
        "repeat_interval": {"bsonType": "string", "description": "Recurrence cadence"},
        "status": {"enum": ["active", "paused", "completed"], "description": "Operational status"},
        "total_delivered": {"bsonType": "number", "description": "Cumulative delivery count"},
        "last_sent_at": {"bsonType": ["string", "null"], "description": "ISO timestamp of last execution"},
        "created_at": {"bsonType": "string"},
        "updated_at": {"bsonType": "string"},
    },
}

STICKERS_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["id", "sticker_url", "status", "repeat_interval"],
    "properties": {
        "id": {"bsonType": "number", "description": "Unique integer ID"},
        "chat_id": {"bsonType": "number", "description": "Target single chat ID or 0 for broadcast"},
        "chat_title": {"bsonType": "string", "description": "Target title label"},
        "sticker_url": {"bsonType": "string", "description": "Telegram sticker pack link, set, or file_id"},
        "sticker_name": {"bsonType": "string", "description": "Human-friendly label"},
        "target_type": {"enum": ["all_gc", "selected", "single"], "description": "Target audience"},
        "target_chat_ids": {"bsonType": "string", "description": "JSON array of selected chat IDs"},
        "schedule_type": {"enum": ["once", "recurring"], "description": "Recurrence behavior"},
        "scheduled_time": {"bsonType": "string", "description": "Next due ISO timestamp"},
        "repeat_interval": {"bsonType": "string", "description": "Cadence, e.g. 3min, 5min, daily"},
        "status": {"enum": ["active", "paused", "completed"]},
        "sticker_pack_name": {"bsonType": ["string", "null"], "description": "Extracted pack slug"},
        "current_index": {"bsonType": "number", "description": "Sticker index within pack"},
        "created_at": {"bsonType": "string"},
        "updated_at": {"bsonType": "string"},
    },
}

SHAYARI_CONTENT_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["id", "category", "content"],
    "properties": {
        "id": {"bsonType": "number"},
        "category": {"enum": ["shayari", "quote", "joke", "meme", "roast", "poem", "pickup_line", "all"]},
        "content": {"bsonType": "string"},
        "author": {"bsonType": ["string", "null"]},
        "language": {"bsonType": ["string", "null"]},
        "media_url": {"bsonType": ["string", "null"]},
        "tags": {"bsonType": ["string", "null"]},
        "created_at": {"bsonType": "string"},
        "updated_at": {"bsonType": "string"},
    },
}

USERS_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["user_id", "is_enabled"],
    "properties": {
        "user_id": {"bsonType": "number", "description": "Telegram numeric User ID"},
        "connection_id": {"bsonType": "string", "description": "Telegram Business connection token"},
        "user_chat_id": {"bsonType": "number"},
        "is_enabled": {"bsonType": "number"},
        "can_reply": {"bsonType": "number"},
        "account_username": {"bsonType": ["string", "null"]},
        "account_first_name": {"bsonType": ["string", "null"]},
        "connected_at": {"bsonType": "number"},
        "updated_at": {"bsonType": "number"},
    },
}

CHATS_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["chat_id", "is_active"],
    "properties": {
        "chat_id": {"bsonType": "number", "description": "Telegram group/supergroup/channel ID"},
        "chat_title": {"bsonType": "string"},
        "chat_type": {"enum": ["group", "supergroup", "channel"]},
        "added_at": {"bsonType": "number"},
        "is_active": {"bsonType": "number"},
        "updated_at": {"bsonType": "number"},
    },
}

SYSTEM_SETTINGS_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["_id"],
    "properties": {
        "_id": {"bsonType": "string"},
        "anti_link_enabled": {"bsonType": "bool"},
        "anti_bio_link_enabled": {"bsonType": "bool"},
        "clean_service_enabled": {"bsonType": "bool"},
        "anti_spam_enabled": {"bsonType": "bool"},
        "flood_detection_enabled": {"bsonType": "bool"},
        "flood_message_limit": {"bsonType": "number"},
        "flood_window_seconds": {"bsonType": "number"},
        "spam_window_seconds": {"bsonType": "number"},
        "spam_warning_limit": {"bsonType": "number"},
        "spam_restriction_seconds": {"bsonType": "number"},
        "warning_delete_after_seconds": {"bsonType": "number"},
        "abuse_detection_enabled": {"bsonType": "bool"},
        "abuse_sexual_language": {"bsonType": "bool"},
        "abuse_general_language": {"bsonType": "bool"},
        "abuse_hindi_hinglish": {"bsonType": "bool"},
        "abuse_harassment": {"bsonType": "bool"},
        "abuse_threats": {"bsonType": "bool"},
        "abuse_bypass_detection": {"bsonType": "bool"},
        "abuse_warning_system": {"bsonType": "bool"},
        "abuse_warning_limit": {"bsonType": "number"},
        "abuse_mute_duration_minutes": {"bsonType": "number"},
        "global_emergency_overrides": {"bsonType": "object"},
        "updated_at": {"bsonType": "string"},
    },
}

ADMINS_JSON_SCHEMA = {
    "bsonType": "object",
    "required": ["email", "passwordHash", "role", "isActive"],
    "properties": {
        "email": {"bsonType": "string", "description": "Admin email address (unique)"},
        "passwordHash": {"bsonType": "string", "description": "Bcrypt hashed password"},
        "role": {"enum": ["admin", "superadmin"], "description": "Admin access role"},
        "isActive": {"bsonType": "bool", "description": "Account activation status"},
        "createdAt": {"bsonType": "string", "description": "Creation ISO timestamp"},
        "updatedAt": {"bsonType": "string", "description": "Last update ISO timestamp"},
        "lastLoginAt": {"bsonType": ["string", "null"], "description": "Last successful login ISO timestamp"},
    },
}

ALL_COLLECTION_SCHEMAS = {
    "scheduled_promotions": PROMOTIONS_JSON_SCHEMA,
    "scheduled_stickers": STICKERS_JSON_SCHEMA,
    "shayari_content": SHAYARI_CONTENT_JSON_SCHEMA,
    "business_connections": USERS_JSON_SCHEMA,
    "chats": CHATS_JSON_SCHEMA,
    "system_settings": SYSTEM_SETTINGS_JSON_SCHEMA,
    "admins": ADMINS_JSON_SCHEMA,
}


def apply_mongo_schema_validators(db: Database | None = None) -> Dict[str, bool]:
    """Apply schema validation rules to MongoDB Atlas collections."""
    target_db = db or get_db()
    existing_collections = set(target_db.list_collection_names())
    results: Dict[str, bool] = {}

    for col_name, schema in ALL_COLLECTION_SCHEMAS.items():
        try:
            if col_name not in existing_collections:
                target_db.create_collection(
                    col_name,
                    validator={"$jsonSchema": schema},
                    validationLevel="moderate",
                )
                results[col_name] = True
            else:
                target_db.command({
                    "collMod": col_name,
                    "validator": {"$jsonSchema": schema},
                    "validationLevel": "moderate",
                })
                results[col_name] = True
        except Exception as exc:
            logger.warning("Schema validator notice for %s: %s", col_name, exc)
            results[col_name] = False

    return results


# =============================================================================
# 2. Python-Level Schema Validation & Normalization Models
# =============================================================================

class SchemaValidator:
    """Validates and normalizes data payloads before persisting to MongoDB."""

    @staticmethod
    def sanitize_string(val: Any, default: str = "") -> str:
        if val is None:
            return default
        return str(val).strip()

    @staticmethod
    def sanitize_int(val: Any, default: int = 0) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def sanitize_bool(val: Any, default: bool = False) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return default

    @classmethod
    def validate_promotion(cls, data: Dict[str, Any], is_edit: bool = False) -> Dict[str, Any]:
        title = cls.sanitize_string(data.get("title"), "GC Promotional Announcement")
        message = cls.sanitize_string(data.get("message"))
        if not message:
            raise ValueError("Promotion 'message' is required and cannot be empty.")

        link_url = cls.sanitize_string(data.get("link_url"))
        button_text = cls.sanitize_string(data.get("button_text"), "Visit Website")
        target_type = cls.sanitize_string(data.get("target_type"), "all_gc")
        if target_type not in ("all_gc", "selected"):
            target_type = "all_gc"

        raw_ids = data.get("target_chat_ids", [])
        if isinstance(raw_ids, str):
            try:
                target_chat_ids = json.loads(raw_ids)
            except Exception:
                target_chat_ids = []
        elif isinstance(raw_ids, list):
            target_chat_ids = [cls.sanitize_int(x) for x in raw_ids if x is not None]
        else:
            target_chat_ids = []

        schedule_type = cls.sanitize_string(data.get("schedule_type"), "once")
        if schedule_type not in ("once", "recurring"):
            schedule_type = "once"

        scheduled_time = cls.sanitize_string(
            data.get("scheduled_time"), datetime.now().strftime("%Y-%m-%dT%H:%M")
        )
        repeat_interval = cls.sanitize_string(
            data.get("repeat_interval"), "none" if schedule_type == "once" else "daily"
        )
        status = cls.sanitize_string(data.get("status"), "active")
        if status not in ("active", "paused", "completed"):
            status = "active"

        now_iso = datetime.now().isoformat()
        clean = {
            "title": title,
            "message": message,
            "link_url": link_url or None,
            "button_text": button_text,
            "target_type": target_type,
            "target_chat_ids": json.dumps(target_chat_ids),
            "schedule_type": schedule_type,
            "scheduled_time": scheduled_time,
            "repeat_interval": repeat_interval,
            "status": status,
            "updated_at": now_iso,
        }
        if not is_edit:
            clean["total_delivered"] = 0
            clean["last_sent_at"] = None
            clean["created_at"] = now_iso

        return clean

    @classmethod
    def validate_sticker(cls, data: Dict[str, Any], is_edit: bool = False) -> Dict[str, Any]:
        sticker_url = cls.sanitize_string(data.get("sticker_url"))
        if not sticker_url:
            raise ValueError("Sticker 'sticker_url' is required.")

        sticker_name = cls.sanitize_string(data.get("sticker_name"), "GC Sticker Broadcast")
        target_type = cls.sanitize_string(data.get("target_type"), "all_gc")
        if target_type not in ("all_gc", "selected", "single"):
            target_type = "all_gc"

        chat_id = cls.sanitize_int(data.get("chat_id"), 0)
        chat_title = cls.sanitize_string(data.get("chat_title"), "All Group Chats" if target_type == "all_gc" else "")

        raw_ids = data.get("target_chat_ids", [])
        if isinstance(raw_ids, str):
            try:
                target_chat_ids = json.loads(raw_ids)
            except Exception:
                target_chat_ids = []
        elif isinstance(raw_ids, list):
            target_chat_ids = [cls.sanitize_int(x) for x in raw_ids if x is not None]
        else:
            target_chat_ids = []

        repeat_interval = cls.sanitize_string(data.get("repeat_interval"), "3min")
        scheduled_time = cls.sanitize_string(
            data.get("scheduled_time"), datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        )
        status = cls.sanitize_string(data.get("status"), "active")
        if status not in ("active", "paused", "completed"):
            status = "active"

        now_iso = datetime.now().isoformat()
        clean = {
            "chat_id": chat_id,
            "chat_title": chat_title,
            "sticker_url": sticker_url,
            "sticker_name": sticker_name,
            "target_type": target_type,
            "target_chat_ids": json.dumps(target_chat_ids),
            "schedule_type": "recurring",
            "scheduled_time": scheduled_time,
            "repeat_interval": repeat_interval,
            "status": status,
            "updated_at": now_iso,
        }
        if not is_edit:
            clean["current_index"] = 0
            clean["created_at"] = now_iso
            clean["last_sent_at"] = None

        return clean

    @classmethod
    def validate_shayari(cls, data: Dict[str, Any], is_edit: bool = False) -> Dict[str, Any]:
        content = cls.sanitize_string(data.get("content"))
        if not content:
            raise ValueError("Shayari/Quote 'content' is required.")

        category = cls.sanitize_string(data.get("category"), "shayari").lower()
        valid_cats = {"shayari", "quote", "joke", "meme", "roast", "poem", "pickup_line"}
        if category not in valid_cats:
            category = "shayari"

        author = cls.sanitize_string(data.get("author"), "Anonymous")
        language = cls.sanitize_string(data.get("language"), "Hindi / English")
        media_url = cls.sanitize_string(data.get("media_url"))
        tags = cls.sanitize_string(data.get("tags"))
        now_iso = datetime.now().isoformat()

        clean = {
            "category": category,
            "content": content,
            "author": author,
            "language": language,
            "media_url": media_url,
            "tags": tags,
            "updated_at": now_iso,
        }
        if not is_edit:
            clean["created_at"] = now_iso

        return clean

    @classmethod
    def validate_chat(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        chat_id = cls.sanitize_int(data.get("chat_id"))
        if not chat_id:
            raise ValueError("Chat 'chat_id' is required.")

        chat_title = cls.sanitize_string(data.get("chat_title"), f"Chat {chat_id}")
        chat_type = cls.sanitize_string(data.get("chat_type"), "group").lower()
        if chat_type not in ("group", "supergroup", "channel"):
            chat_type = "group"

        is_active = 1 if cls.sanitize_bool(data.get("is_active", True)) else 0
        now = time.time()

        return {
            "chat_id": chat_id,
            "chat_title": chat_title,
            "chat_type": chat_type,
            "is_active": is_active,
            "updated_at": now,
        }

    @classmethod
    def validate_user(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        user_id = cls.sanitize_int(data.get("user_id"))
        if not user_id:
            raise ValueError("User 'user_id' is required.")

        connection_id = cls.sanitize_string(data.get("connection_id"), f"conn_{user_id}_{int(time.time())}")
        user_chat_id = cls.sanitize_int(data.get("user_chat_id"), user_id)
        is_enabled = 1 if cls.sanitize_bool(data.get("is_enabled", True)) else 0
        can_reply = 1 if cls.sanitize_bool(data.get("can_reply", True)) else 0
        account_username = cls.sanitize_string(data.get("account_username")) or None
        account_first_name = cls.sanitize_string(data.get("account_first_name")) or None
        now = time.time()

        return {
            "user_id": user_id,
            "connection_id": connection_id,
            "user_chat_id": user_chat_id,
            "is_enabled": is_enabled,
            "can_reply": can_reply,
            "account_username": account_username,
            "account_first_name": account_first_name,
            "updated_at": now,
        }

    @classmethod
    def validate_system_settings(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "_id": "global_config",
            "anti_link_enabled": cls.sanitize_bool(data.get("anti_link_enabled", True)),
            "anti_bio_link_enabled": cls.sanitize_bool(data.get("anti_bio_link_enabled", True)),
            "clean_service_enabled": cls.sanitize_bool(data.get("clean_service_enabled", True)),
            "anti_spam_enabled": cls.sanitize_bool(data.get("anti_spam_enabled", True)),
            "flood_detection_enabled": cls.sanitize_bool(data.get("flood_detection_enabled", True)),
            "flood_message_limit": max(3, cls.sanitize_int(data.get("flood_message_limit", 8))),
            "flood_window_seconds": max(3, cls.sanitize_int(data.get("flood_window_seconds", 10))),
            "spam_window_seconds": max(5, cls.sanitize_int(data.get("spam_window_seconds", 30))),
            "spam_warning_limit": max(1, cls.sanitize_int(data.get("spam_warning_limit", 2))),
            "spam_restriction_seconds": max(60, cls.sanitize_int(data.get("spam_restriction_seconds", 86400))),
            "warning_delete_after_seconds": max(3, cls.sanitize_int(data.get("warning_delete_after_seconds", 10))),
            "abuse_detection_enabled": cls.sanitize_bool(data.get("abuse_detection_enabled", True)),
            "abuse_sexual_language": cls.sanitize_bool(data.get("abuse_sexual_language", True)),
            "abuse_general_language": cls.sanitize_bool(data.get("abuse_general_language", True)),
            "abuse_hindi_hinglish": cls.sanitize_bool(data.get("abuse_hindi_hinglish", True)),
            "abuse_harassment": cls.sanitize_bool(data.get("abuse_harassment", True)),
            "abuse_threats": cls.sanitize_bool(data.get("abuse_threats", True)),
            "abuse_bypass_detection": cls.sanitize_bool(data.get("abuse_bypass_detection", True)),
            "abuse_warning_system": cls.sanitize_bool(data.get("abuse_warning_system", True)),
            "abuse_warning_limit": max(1, cls.sanitize_int(data.get("abuse_warning_limit", 3))),
            "abuse_mute_duration_minutes": max(5, cls.sanitize_int(data.get("abuse_mute_duration_minutes", 30))),
            "global_emergency_overrides": data.get("global_emergency_overrides", {}),
            "updated_at": datetime.now().isoformat(),
        }


# =============================================================================
# 3. High-Level MongoDB CRUD Features: Add, Edit, Save, Delete
# =============================================================================

# ----------------- PROMOTIONS CRUD -----------------

def create_promotion(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate, assign auto-increment ID, and save promotion to MongoDB."""
    db = get_db()
    clean = SchemaValidator.validate_promotion(data, is_edit=False)
    new_id = get_next_sequence("scheduled_promotions", db=db)
    clean["id"] = new_id
    db["scheduled_promotions"].insert_one(clean)
    clean.pop("_id", None)
    return {"success": True, "id": new_id, "promotion": clean}


def update_promotion(promotion_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and edit an existing promotion in MongoDB."""
    db = get_db()
    existing = db["scheduled_promotions"].find_one({"id": promotion_id})
    if not existing:
        return {"success": False, "error": f"Promotion #{promotion_id} not found"}

    clean = SchemaValidator.validate_promotion(data, is_edit=True)
    db["scheduled_promotions"].update_one({"id": promotion_id}, {"$set": clean})
    clean["id"] = promotion_id
    return {"success": True, "id": promotion_id, "promotion": clean}


def delete_promotion(promotion_id: int) -> Dict[str, Any]:
    """Delete a promotion and its dispatch audit logs from MongoDB."""
    db = get_db()
    res1 = db["scheduled_promotions"].delete_one({"id": promotion_id})
    res2 = db["promotion_send_logs"].delete_many({"promotion_id": promotion_id})
    return {
        "success": True,
        "deleted_count": res1.deleted_count,
        "logs_purged": res2.deleted_count,
        "message": f"Promotion #{promotion_id} successfully deleted from MongoDB."
    }


# ----------------- STICKERS CRUD -----------------

def create_sticker(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate, assign auto-increment ID, and save sticker broadcast to MongoDB."""
    db = get_db()
    clean = SchemaValidator.validate_sticker(data, is_edit=False)
    new_id = get_next_sequence("scheduled_stickers", db=db)
    clean["id"] = new_id
    db["scheduled_stickers"].insert_one(clean)
    clean.pop("_id", None)
    return {"success": True, "id": new_id, "sticker": clean}


def update_sticker(sticker_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and update a sticker broadcast configuration in MongoDB."""
    db = get_db()
    existing = db["scheduled_stickers"].find_one({"id": sticker_id})
    if not existing:
        return {"success": False, "error": f"Sticker #{sticker_id} not found"}

    clean = SchemaValidator.validate_sticker(data, is_edit=True)
    db["scheduled_stickers"].update_one({"id": sticker_id}, {"$set": clean})
    clean["id"] = sticker_id
    return {"success": True, "id": sticker_id, "sticker": clean}


def delete_sticker(sticker_id: int) -> Dict[str, Any]:
    """Delete a sticker broadcast schedule and associated logs from MongoDB."""
    db = get_db()
    res1 = db["scheduled_stickers"].delete_one({"id": sticker_id})
    res2 = db["sticker_send_logs"].delete_many({"scheduled_id": sticker_id})
    return {
        "success": True,
        "deleted_count": res1.deleted_count,
        "logs_purged": res2.deleted_count,
        "message": f"Sticker schedule #{sticker_id} successfully deleted from MongoDB."
    }


# ----------------- SHAYARI CRUD -----------------

def create_shayari(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and insert a new shayari or quote into MongoDB."""
    db = get_db()
    clean = SchemaValidator.validate_shayari(data, is_edit=False)
    new_id = get_next_sequence("shayari_content", db=db)
    clean["id"] = new_id
    db["shayari_content"].insert_one(clean)
    clean.pop("_id", None)
    return {"success": True, "id": new_id, "item": clean}


def update_shayari(item_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and update an existing shayari or quote item in MongoDB."""
    db = get_db()
    existing = db["shayari_content"].find_one({"id": item_id})
    if not existing:
        return {"success": False, "error": f"Content item #{item_id} not found"}

    clean = SchemaValidator.validate_shayari(data, is_edit=True)
    db["shayari_content"].update_one({"id": item_id}, {"$set": clean})
    clean["id"] = item_id
    return {"success": True, "id": item_id, "item": clean}


def delete_shayari(item_id: int) -> Dict[str, Any]:
    """Delete a shayari content record from MongoDB."""
    db = get_db()
    res = db["shayari_content"].delete_one({"id": item_id})
    return {
        "success": True,
        "deleted_count": res.deleted_count,
        "message": f"Shayari item #{item_id} successfully deleted."
    }


# ----------------- CHATS CRUD -----------------

def create_or_save_chat(data: Dict[str, Any]) -> Dict[str, Any]:
    """Register or save chat details and initialize default settings in MongoDB."""
    db = get_db()
    clean = SchemaValidator.validate_chat(data)
    chat_id = clean["chat_id"]

    db["chats"].update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "chat_title": clean["chat_title"],
                "chat_type": clean["chat_type"],
                "is_active": clean["is_active"],
                "updated_at": clean["updated_at"],
            },
            "$setOnInsert": {
                "added_at": clean["updated_at"],
            },
        },
        upsert=True,
    )

    # Initialize default settings if absent
    if not db["chat_settings"].find_one({"chat_id": chat_id}):
        from database import register_or_update_chat
        register_or_update_chat(chat_id, clean["chat_title"], clean["chat_type"], is_active=bool(clean["is_active"]))

    clean.pop("_id", None)
    return {"success": True, "chat_id": chat_id, "chat": clean}


def update_chat_settings_doc(chat_id: int, settings_data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit and save detailed moderation configuration for a chat in MongoDB."""
    db = get_db()
    now = time.time()
    clean_updates: Dict[str, Any] = {"updated_at": now}

    bool_fields = [
        "anti_link_enabled", "anti_bio_link_enabled", "clean_service_enabled",
        "anti_spam_enabled", "flood_detection_enabled", "warning_system_enabled",
        "auto_restrict_enabled", "anti_forward_enabled", "anti_join_spam_enabled",
        "anti_bot_enabled", "media_restrictions_enabled", "raid_mode_enabled", "greeting_enabled"
    ]
    for bf in bool_fields:
        if bf in settings_data:
            clean_updates[bf] = 1 if SchemaValidator.sanitize_bool(settings_data[bf]) else 0

    num_fields = [
        "flood_threshold_messages", "flood_window_seconds", "spam_window_seconds",
        "warning_limit", "restriction_duration_seconds", "warning_delete_after_seconds"
    ]
    for nf in num_fields:
        if nf in settings_data:
            clean_updates[nf] = SchemaValidator.sanitize_int(settings_data[nf])

    if "flood_message_limit" in settings_data:
        clean_updates["flood_threshold_messages"] = SchemaValidator.sanitize_int(settings_data["flood_message_limit"])
        clean_updates["flood_message_limit"] = clean_updates["flood_threshold_messages"]

    text_fields = ["custom_warning_msg_1", "custom_warning_msg_2", "custom_greeting_msg"]
    for tf in text_fields:
        if tf in settings_data:
            clean_updates[tf] = SchemaValidator.sanitize_string(settings_data[tf]) or None

    db["chat_settings"].update_one(
        {"chat_id": chat_id},
        {"$set": clean_updates},
        upsert=True,
    )
    return {"success": True, "chat_id": chat_id, "settings": clean_updates}


def delete_or_deactivate_chat(chat_id: int) -> Dict[str, Any]:
    """Deactivate or remove a group/channel from active operations in MongoDB."""
    db = get_db()
    res = db["chats"].update_one(
        {"chat_id": chat_id},
        {"$set": {"is_active": 0, "updated_at": time.time()}},
    )
    return {
        "success": True,
        "chat_id": chat_id,
        "modified": res.modified_count,
        "message": f"Chat #{chat_id} deactivated in MongoDB."
    }


# ----------------- USERS CRUD -----------------

def create_or_save_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Register or save user details and business connection in MongoDB."""
    db = get_db()
    clean = SchemaValidator.validate_user(data)
    user_id = clean["user_id"]

    db["business_connections"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "connection_id": clean["connection_id"],
                "user_chat_id": clean["user_chat_id"],
                "is_enabled": clean["is_enabled"],
                "can_reply": clean["can_reply"],
                "account_username": clean["account_username"],
                "account_first_name": clean["account_first_name"],
                "updated_at": clean["updated_at"],
            },
            "$setOnInsert": {
                "connected_at": clean["updated_at"],
            },
        },
        upsert=True,
    )
    return {"success": True, "user_id": user_id, "user": clean}


def update_user_reply_settings(user_id: int, settings_data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit personal auto-reply preferences and templates for a user in MongoDB."""
    from database import update_personal_reply_settings, set_personal_reply_template
    res = update_personal_reply_settings(user_id, **settings_data)

    if "template" in settings_data:
        set_personal_reply_template(user_id, settings_data["template"])

    return {"success": True, "user_id": user_id, "settings": res}


def delete_or_deactivate_user(user_id: int) -> Dict[str, Any]:
    """Disable business connections and purge active records for a user."""
    db = get_db()
    res1 = db["business_connections"].update_many({"user_id": user_id}, {"$set": {"is_enabled": 0}})
    res2 = db["personal_reply_settings"].update_many({"user_id": user_id}, {"$set": {"is_enabled": 0}})
    db["chat_warnings"].delete_many({"user_id": user_id})
    return {
        "success": True,
        "user_id": user_id,
        "disabled_connections": res1.modified_count,
        "disabled_settings": res2.modified_count,
        "message": f"User #{user_id} removed from active operations in MongoDB."
    }


# ----------------- SYSTEM SETTINGS CRUD -----------------

def get_system_settings() -> Dict[str, Any]:
    """Retrieve global system configuration from MongoDB with fallback to defaults."""
    db = get_db()
    doc = db["system_settings"].find_one({"_id": "global_config"})
    if doc:
        d = dict(doc)
        d.pop("_id", None)
        return d

    # Return defaults from config.py and insert into MongoDB
    defaults = {
        "_id": "global_config",
        "anti_link_enabled": getattr(config, "ANTI_LINK_ENABLED", True),
        "anti_bio_link_enabled": getattr(config, "ANTI_BIO_LINK_ENABLED", True),
        "clean_service_enabled": getattr(config, "CLEAN_SERVICE_ENABLED", True),
        "anti_spam_enabled": getattr(config, "ANTI_SPAM_ENABLED", True),
        "flood_detection_enabled": getattr(config, "FLOOD_DETECTION_ENABLED", True),
        "flood_message_limit": getattr(config, "FLOOD_MESSAGE_LIMIT", 8),
        "flood_window_seconds": getattr(config, "FLOOD_WINDOW_SECONDS", 10),
        "spam_window_seconds": getattr(config, "SPAM_WINDOW_SECONDS", 30),
        "spam_warning_limit": getattr(config, "SPAM_WARNING_LIMIT", 2),
        "spam_restriction_seconds": getattr(config, "SPAM_RESTRICTION_SECONDS", 86400),
        "warning_delete_after_seconds": getattr(config, "WARNING_DELETE_AFTER_SECONDS", 10),
        "abuse_detection_enabled": True,
        "abuse_sexual_language": True,
        "abuse_general_language": True,
        "abuse_hindi_hinglish": True,
        "abuse_harassment": True,
        "abuse_threats": True,
        "abuse_bypass_detection": True,
        "abuse_warning_system": True,
        "abuse_warning_limit": 3,
        "abuse_mute_duration_minutes": 30,
        "global_emergency_overrides": getattr(config, "GLOBAL_EMERGENCY_OVERRIDES", {}),
        "updated_at": datetime.now().isoformat(),
    }
    db["system_settings"].insert_one(defaults)
    defaults.pop("_id", None)
    return defaults


def save_system_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate, edit, and persist global system settings in MongoDB."""
    db = get_db()
    clean = SchemaValidator.validate_system_settings(data)
    db["system_settings"].update_one(
        {"_id": "global_config"},
        {"$set": clean},
        upsert=True,
    )
    clean.pop("_id", None)
    return {"success": True, "settings": clean, "message": "System settings saved successfully in MongoDB."}


# ----------------- OVERVIEW TELEMETRY SCHEMA -----------------

def get_overview_telemetry() -> Dict[str, Any]:
    """Aggregate real-time metrics across all MongoDB collections for the Dashboard Overview."""
    db = get_db()

    total_chats = db["chats"].count_documents({"is_active": 1})
    total_gcs = db["chats"].count_documents({"is_active": 1, "chat_type": {"$in": ["group", "supergroup"]}})
    total_channels = db["chats"].count_documents({"is_active": 1, "chat_type": "channel"})
    total_users = len(db["business_connections"].distinct("user_id", {"is_enabled": 1}))
    total_promotions = db["scheduled_promotions"].count_documents({})
    active_promotions = db["scheduled_promotions"].count_documents({"status": "active"})
    total_stickers = db["scheduled_stickers"].count_documents({})
    active_stickers = db["scheduled_stickers"].count_documents({"status": "active"})
    total_shayari = db["shayari_content"].count_documents({})
    active_shayari_schedules = db["scheduled_shayari"].count_documents({"status": "active"})

    # Stat sums
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_messages": {"$sum": "$total_messages_checked"},
                "links_deleted": {"$sum": "$links_deleted"},
                "spam_deleted": {"$sum": "$spam_deleted"},
                "warnings_issued": {"$sum": "$warnings_issued"},
                "restrictions_applied": {"$sum": "$restrictions_applied"},
            }
        }
    ]
    agg = list(db["chat_statistics"].aggregate(pipeline))
    stats = agg[0] if agg else {}

    return {
        "database": {
            "engine": "MongoDB Atlas",
            "db_name": getattr(config, "MONGODB_DB_NAME", "waguri_db"),
            "status": "connected",
        },
        "overview": {
            "total_users": total_users,
            "total_active_chats": total_chats,
            "total_group_chats": total_gcs,
            "total_channels": total_channels,
            "total_messages_checked": int(stats.get("total_messages") or 0),
            "links_deleted": int(stats.get("links_deleted") or 0),
            "spam_deleted": int(stats.get("spam_deleted") or 0),
            "warnings_issued": int(stats.get("warnings_issued") or 0),
            "restrictions_applied": int(stats.get("restrictions_applied") or 0),
        },
        "schedules": {
            "promotions": {"total": total_promotions, "active": active_promotions},
            "stickers": {"total": total_stickers, "active": active_stickers},
            "shayari": {"total_content": total_shayari, "active_schedules": active_shayari_schedules},
        },
        "server_time": datetime.now().isoformat(),
    }
