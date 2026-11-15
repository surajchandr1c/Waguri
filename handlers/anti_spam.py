import asyncio
from collections import deque
from datetime import datetime, timezone
import hashlib
import logging
import time
from telegram import Chat, ChatPermissions, Message, Update, User
from telegram.constants import ChatType
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from config import (
    ANTI_SPAM_ENABLED,
    FLOOD_DETECTION_ENABLED,
    FLOOD_MESSAGE_LIMIT,
    FLOOD_WINDOW_SECONDS,
    RESTRICTION_MSG,
    SPAM_RESTRICTION_SECONDS,
    SPAM_WINDOW_SECONDS,
    WARNING_DELETE_AFTER_SECONDS,
    WARNING_MSG_1,
    WARNING_MSG_2,
)
from database import (
    add_user_warning,
    clear_active_incident,
    get_active_incident,
    get_group_settings,
    increment_stat,
    log_moderation_event,
    record_restriction,
    save_active_incident,
)
from handlers.admin_check import check_bot_permissions, is_sender_admin_or_owner
from handlers.admin_commands import NO_SEND_PERMISSIONS
from handlers.anti_link import schedule_warning_cleanup

logger = logging.getLogger("Waguri.AntiSpam")

# Per-user async locks to prevent race conditions on simultaneous messages: (chat_id, user_id) -> Lock
_user_locks: dict[tuple[int, int], asyncio.Lock] = {}

# Deduplication ring buffer for update IDs
_processed_updates: deque[int] = deque(maxlen=2000)

# Flood detection in-memory timestamps: (chat_id, user_id) -> list of timestamps
_flood_tracker: dict[tuple[int, int], list[float]] = {}


def reset_anti_spam_state() -> None:
    """Clear in-memory deduplication and flood tracking state."""
    _processed_updates.clear()
    _flood_tracker.clear()
    _user_locks.clear()


def get_user_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    """Retrieve or create an asyncio.Lock for a specific user in a group."""
    key = (chat_id, user_id)
    if key not in _user_locks:
        _user_locks[key] = asyncio.Lock()
    return _user_locks[key]


def compute_message_fingerprint(text: str | None) -> str:
    """
    Compute a consistent cryptographic fingerprint for normalized message content.
    Normalizes whitespace (collapses runs of whitespace, strips edges) and converts to lowercase.
    """
    if not text:
        return ""
    normalized = " ".join(text.strip().split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check_flood_rate(
    chat_id: int,
    user_id: int,
    user_info: str,
    chat_title: str,
    window_seconds: int = 10,
    threshold_messages: int = 8,
) -> None:
    """
    Flood detection: Track rapid message sending rate within a short window.
    Logged for detection only (does not automatically punish).
    """
    now = time.time()
    key = (chat_id, user_id)
    timestamps = _flood_tracker.get(key, [])
    # Keep only timestamps within window_seconds
    timestamps = [t for t in timestamps if now - t <= window_seconds]
    timestamps.append(now)
    _flood_tracker[key] = timestamps

    if len(timestamps) >= threshold_messages:
        logger.warning(
            "[FLOOD DETECTED] User %s in group '%s' (ID: %s) sent %d messages within %ds (Threshold: %d). "
            "Action: Detection logged only.",
            user_info,
            chat_title,
            chat_id,
            len(timestamps),
            window_seconds,
            threshold_messages,
        )


async def delete_spam_messages_batch(chat_id: int, message_ids: list[int], bot: Application.bot) -> tuple[int, int]:
    """Delete a collection of spam messages previously recorded for an incident."""
    deleted_count = 0
    total_attempted = len(message_ids)

    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted_count += 1
        except Exception as exc:
            logger.debug(
                "[SPAM CLEANUP] Could not delete historical message %s in chat %s: %s",
                msg_id,
                chat_id,
                exc,
            )

    return deleted_count, total_attempted


async def restrict_user_24h(chat: Chat, user: User, bot: Application.bot, duration_seconds: int = 86400) -> bool:
    """Restrict a member from sending messages for the specified duration (default 24h)."""
    until_date = int(time.time()) + duration_seconds
    try:
        await bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=NO_SEND_PERMISSIONS,
            until_date=until_date,
        )
        return True
    except (Forbidden, BadRequest) as exc:
        logger.error(
            "[RESTRICTION PERMISSION ERROR] Group '%s' (ID: %s) | User ID %s: %s. "
            "Ensure Waguri has 'Restrict Members' permission.",
            chat.title,
            chat.id,
            user.id,
            exc,
        )
        return False
    except TelegramError as exc:
        logger.error(
            "[RESTRICTION TELEGRAM ERROR] Group '%s' (ID: %s) | User ID %s: %s",
            chat.title,
            chat.id,
            user.id,
            exc,
        )
        return False
    except Exception as exc:
        logger.error(
            "[RESTRICTION UNEXPECTED ERROR] Group '%s' (ID: %s) | User ID %s: %s",
            chat.title,
            chat.id,
            user.id,
            exc,
        )
        return False


async def handle_anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages to detect, warn, and restrict repeated-message spam."""
    # Deduplicate updates to prevent double processing
    if update.update_id in _processed_updates:
        return
    _processed_updates.append(update.update_id)

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    # Strictly limit anti-spam moderation to groups and supergroups
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Check per-group setting
    settings = get_group_settings(chat.id)
    if not settings.get("is_active", True) or not settings.get("anti_spam_enabled", True):
        return

    text = message.text or message.caption
    if not text or not text.strip():
        return

    sender_chat = getattr(message, "sender_chat", None)

    # Check administrator and owner exemption
    is_protected = await is_sender_admin_or_owner(chat, user, sender_chat, context.bot)
    if is_protected:
        return

    chat_id = chat.id
    user_id = user.id
    chat_title = chat.title or "Unnamed Group"
    user_info = f"@{user.username} (ID: {user_id})" if user.username else f"User ID {user_id}"

    # Per-group configuration parameters
    spam_window = settings.get("spam_window_seconds", SPAM_WINDOW_SECONDS)
    warning_system_enabled = settings.get("warning_system_enabled", True)
    auto_restrict_enabled = settings.get("auto_restrict_enabled", True)
    restriction_duration = settings.get("restriction_duration_seconds", SPAM_RESTRICTION_SECONDS)
    cleanup_delay = settings.get("warning_delete_after_seconds", WARNING_DELETE_AFTER_SECONDS)

    # Flood detection (logged only, non-punitive)
    if settings.get("flood_detection_enabled", True):
        flood_win = settings.get("flood_window_seconds", FLOOD_WINDOW_SECONDS)
        flood_thresh = settings.get("flood_threshold_messages", FLOOD_MESSAGE_LIMIT)
        check_flood_rate(chat_id, user_id, user_info, chat_title, flood_win, flood_thresh)

    message_fingerprint = compute_message_fingerprint(text)
    now = time.time()

    # Synchronize processing per user in the group to eliminate race conditions
    async with get_user_lock(chat_id, user_id):
        incident = get_active_incident(chat_id, user_id)

        # Check rolling window and message fingerprint match
        if incident:
            is_expired = (now - incident["last_message_time"]) > spam_window
            is_different = incident["message_fingerprint"] != message_fingerprint

            if is_expired or is_different:
                # Reset incident: either time expired or user sent a different, unrelated message
                clear_active_incident(chat_id, user_id)
                incident = None

        if incident is None:
            # ---------------------------------------------------------
            # 1st identical message: Allow message, no warning issued
            # ---------------------------------------------------------
            save_active_incident(
                chat_id=chat_id,
                user_id=user_id,
                message_fingerprint=message_fingerprint,
                count=1,
                last_message_time=now,
                message_ids=[message.message_id],
            )
            logger.info(
                "[SPAM TRACK] Group: '%s' (ID: %s) | User: %s | Message ID: %s | 1st message allowed (no warning)",
                chat_title,
                chat_id,
                user_info,
                message.message_id,
            )
            return

        # User sent identical message within active window
        new_count = incident["count"] + 1
        recorded_msg_ids: list[int] = list(incident.get("message_ids", []))
        recorded_msg_ids.append(message.message_id)

        # Audit check bot permissions
        can_delete, can_restrict = await check_bot_permissions(
            chat, context.bot, need_delete=True, need_restrict=(new_count >= 4)
        )

        if new_count == 2:
            # ---------------------------------------------------------
            # 2nd identical message: Delete + Warning 1
            # ---------------------------------------------------------
            if can_delete:
                try:
                    await message.delete()
                    increment_stat(chat_id, "spam_deleted", count=1, chat_title=chat_title)
                except Exception as exc:
                    logger.error("[SPAM DELETE ERROR] Could not delete 2nd message ID %s: %s", message.message_id, exc)

            save_active_incident(
                chat_id=chat_id,
                user_id=user_id,
                message_fingerprint=message_fingerprint,
                count=2,
                last_message_time=now,
                message_ids=recorded_msg_ids,
            )
            log_moderation_event(chat_id, user_id, "WARNING_1", f"Message ID: {message.message_id}")
            add_user_warning(chat_id, user_id, "Spam Warning 1/2")

            if warning_system_enabled:
                increment_stat(chat_id, "warnings_issued", count=1, chat_title=chat_title)
                warn_text = settings.get("custom_warning_msg_1") or WARNING_MSG_1
                try:
                    warn_msg = await context.bot.send_message(chat_id=chat_id, text=warn_text)
                    asyncio.create_task(schedule_warning_cleanup(warn_msg, delay_seconds=cleanup_delay))
                except Exception as exc:
                    logger.error("[WARNING 1 SEND ERROR] Failed to send Warning 1 in chat %s: %s", chat_id, exc)

            logger.info(
                "[SPAM WARNING 1/2] Group: '%s' (ID: %s) | User: %s | Message ID %s deleted | Warning 1 issued",
                chat_title,
                chat_id,
                user_info,
                message.message_id,
            )

        elif new_count == 3:
            # ---------------------------------------------------------
            # 3rd identical message: Delete + Warning 2
            # ---------------------------------------------------------
            if can_delete:
                try:
                    await message.delete()
                    increment_stat(chat_id, "spam_deleted", count=1, chat_title=chat_title)
                except Exception as exc:
                    logger.error("[SPAM DELETE ERROR] Could not delete 3rd message ID %s: %s", message.message_id, exc)

            save_active_incident(
                chat_id=chat_id,
                user_id=user_id,
                message_fingerprint=message_fingerprint,
                count=3,
                last_message_time=now,
                message_ids=recorded_msg_ids,
            )
            log_moderation_event(chat_id, user_id, "WARNING_2", f"Message ID: {message.message_id}")
            add_user_warning(chat_id, user_id, "Spam Warning 2/2")

            if warning_system_enabled:
                increment_stat(chat_id, "warnings_issued", count=1, chat_title=chat_title)
                warn_text = settings.get("custom_warning_msg_2") or WARNING_MSG_2
                try:
                    warn_msg = await context.bot.send_message(chat_id=chat_id, text=warn_text)
                    asyncio.create_task(schedule_warning_cleanup(warn_msg, delay_seconds=cleanup_delay))
                except Exception as exc:
                    logger.error("[WARNING 2 SEND ERROR] Failed to send Warning 2 in chat %s: %s", chat_id, exc)

            logger.info(
                "[SPAM WARNING 2/2] Group: '%s' (ID: %s) | User: %s | Message ID %s deleted | Warning 2 issued",
                chat_title,
                chat_id,
                user_info,
                message.message_id,
            )

        elif new_count >= 4:
            # ---------------------------------------------------------
            # 4th identical message: Delete 4th + Delete all spam + 24h Restriction
            # ---------------------------------------------------------
            # 1. Delete 4th message
            spam_deleted_this_round = 0
            if can_delete:
                try:
                    await message.delete()
                    spam_deleted_this_round += 1
                except Exception as exc:
                    logger.error("[SPAM DELETE ERROR] Could not delete 4th message ID %s: %s", message.message_id, exc)

            # 2. Delete all recorded spam messages from active incident (excluding 4th which is already deleted)
            prior_msg_ids = [m for m in recorded_msg_ids if m != message.message_id]
            deleted_count, total_attempted = await delete_spam_messages_batch(chat_id, prior_msg_ids, context.bot)
            spam_deleted_this_round += deleted_count
            increment_stat(chat_id, "spam_deleted", count=spam_deleted_this_round, chat_title=chat_title)

            # 3. Apply restriction (default 24 hours or configured duration)
            expires_at = now + restriction_duration
            restricted_success = False

            if auto_restrict_enabled:
                if can_restrict:
                    restricted_success = await restrict_user_24h(chat, user, context.bot, restriction_duration)
                    if restricted_success:
                        increment_stat(chat_id, "restrictions_applied", count=1, chat_title=chat_title)
                else:
                    logger.warning(
                        "[RESTRICTION SKIPPED] Cannot restrict user %s in '%s' due to missing permission.",
                        user_info,
                        chat_title,
                    )

                # 4. Notify group
                try:
                    await context.bot.send_message(chat_id=chat_id, text=RESTRICTION_MSG)
                except Exception as exc:
                    logger.error("[RESTRICTION MSG ERROR] Could not send restriction notice in %s: %s", chat_id, exc)

                # 5. Record restriction in history
                record_restriction(
                    chat_id=chat_id,
                    user_id=user_id,
                    username=user.username,
                    reason="Repeated message spam violation",
                    restricted_at=now,
                    expires_at=expires_at,
                )

            # Clear active incident for fresh reset
            clear_active_incident(chat_id, user_id)

            exp_str = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(
                "[USER RESTRICTED] Group: '%s' (ID: %s) | User: %s | Action: Restricted for %ds (Expires: %s) | "
                "Spam cleanup: Removed %d/%d prior messages | Status: %s",
                chat_title,
                chat_id,
                user_info,
                restriction_duration,
                exp_str,
                deleted_count,
                total_attempted,
                "Success" if restricted_success else "Permission Failed or Disabled",
            )


def register_anti_spam_handlers(application: Application) -> None:
    """Register anti-spam message handler on the application."""
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION),
            handle_anti_spam,
        ),
        group=2,
    )
