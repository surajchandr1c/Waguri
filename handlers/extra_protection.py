import asyncio
import html
import logging
import time
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from database import (
    add_user_warning,
    get_group_settings,
    get_recent_join_events_count,
    get_user_warnings_count,
    increment_stat,
    log_moderation_event,
    record_join_event,
    record_restriction,
    update_group_feature,
)
from handlers.admin_check import check_bot_permissions, is_sender_admin_or_owner
from handlers.anti_link import (
    check_user_bio_link,
    dispatch_bio_link_violation,
    schedule_warning_cleanup,
)

logger = logging.getLogger("Waguri.ExtraProtection")


async def handle_anti_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect and remove forwarded messages when anti-forward protection is enabled."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Check if message is a forward
    is_forwarded = bool(
        message.forward_date
        or getattr(message, "forward_origin", None)
        or getattr(message, "forward_from", None)
        or getattr(message, "forward_from_chat", None)
    )
    if not is_forwarded:
        return

    settings = get_group_settings(chat.id)
    if not settings.get("is_active", True) or not settings.get("anti_forward_enabled", False):
        return

    sender = update.effective_user
    sender_chat = getattr(message, "sender_chat", None)
    is_protected = await is_sender_admin_or_owner(chat, sender, sender_chat, context.bot)
    if is_protected:
        return

    can_delete, _ = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=False)
    if can_delete:
        try:
            await message.delete()
            increment_stat(chat.id, "forwards_deleted", count=1, chat_title=chat.title)
            log_moderation_event(
                chat.id,
                sender.id if sender else 0,
                "FORWARD_DELETED",
                f"Deleted forwarded message ID {message.message_id}",
            )
            logger.info("[ANTI-FORWARD] Deleted forwarded message from user %s in chat %s", sender.id if sender else 0, chat.id)
        except Exception as exc:
            logger.error("[ANTI-FORWARD ERROR] Could not delete message %s in chat %s: %s", message.message_id, chat.id, exc)


async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monitor member join events for bot additions and join bursts."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    new_members = message.new_chat_members
    if not new_members:
        return

    settings = get_group_settings(chat.id)
    chat_title = chat.title or "Unnamed Group"

    for member in new_members:
        # Never track Waguri itself here (handled by registration)
        if member.id == context.bot.id:
            continue

        # Record join event
        record_join_event(chat.id, member.id, is_bot=member.is_bot)

        # 1. Anti-Bot Protection
        if member.is_bot and settings.get("anti_bot_enabled", False):
            adder = message.from_user
            is_adder_admin = await is_sender_admin_or_owner(chat, adder, None, context.bot)
            if not is_adder_admin:
                can_delete, can_restrict = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=True)
                if can_delete:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                if can_restrict:
                    try:
                        await context.bot.ban_chat_member(chat_id=chat.id, user_id=member.id)
                        await context.bot.unban_chat_member(chat_id=chat.id, user_id=member.id)
                        increment_stat(chat.id, "banned_members", count=1, chat_title=chat_title)
                        log_moderation_event(chat.id, member.id, "BOT_REMOVED", f"Removed unauthorized bot @{member.username}")
                        await context.bot.send_message(
                            chat_id=chat.id,
                            text=f"🤖 <b>Anti-Bot:</b> Removed unauthorized bot <code>@{html.escape(member.username or str(member.id))}</code> added by non-admin.",
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception as exc:
                        logger.error("Could not remove bot %s: %s", member.id, exc)

        # 2. Anti-Join Spam / Burst Detection
        if settings.get("anti_join_spam_enabled", False):
            burst_count = get_recent_join_events_count(chat.id, window_seconds=10)
            if burst_count >= 5:
                logger.warning("[JOIN BURST] Detected %d member joins within 10s in group '%s' (ID: %s)", burst_count, chat_title, chat.id)
                try:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=f"⚠️ <b>Join Burst Alert:</b> {burst_count} new accounts joined within 10 seconds. Administrators please monitor group activity.",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass

        # 3. Anti-Bio-Link Check for New Members
        if settings.get("anti_bio_link_enabled", True) and not member.is_bot:
            has_bio_link, bio_url = await check_user_bio_link(member.id, context.bot)
            if has_bio_link:
                can_del, _ = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=False)
                if can_del:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                add_user_warning(chat.id, member.id, f"Bio Link on Join: {bio_url}")
                increment_stat(chat.id, "warnings_issued", count=1, chat_title=chat_title)
                log_moderation_event(chat.id, member.id, "BIO_LINK_JOIN", f"Member joined with bio link: {bio_url}")
                if await dispatch_bio_link_violation(chat, member, bio_url, context, settings, on_join=True):
                    continue


async def handle_service_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Telegram service messages (chat service):
    - Automatically delete service messages (joins, leaves, pins, video chats, etc.) when clean_service_enabled is active.
    - Check if joining members have links in their bio, remove join message, and issue warning.
    - Execute anti-bot and anti-join burst monitoring.
    """
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Process new chat members if present
    if message.new_chat_members:
        await handle_new_chat_members(update, context)

    # Clean service message if enabled
    settings = get_group_settings(chat.id)
    if settings.get("clean_service_enabled", True):
        can_delete, _ = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=False)
        if can_delete:
            try:
                await message.delete()
                logger.info("[CLEAN SERVICE] Group: '%s' (ID: %s) | Deleted service message ID %s", chat.title, chat.id, message.message_id)
            except Exception as exc:
                logger.debug("[CLEAN SERVICE] Could not delete service message %s: %s", message.message_id, exc)


async def raid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle emergency raid protection mode for the group (/raid [on|off])."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text("This command can only be used in a group or supergroup.")
        return

    sender_chat = getattr(message, "sender_chat", None)
    is_admin = await is_sender_admin_or_owner(chat, user, sender_chat, context.bot)
    if not is_admin:
        await message.reply_text("You need administrator privileges to use this command.")
        return

    settings = get_group_settings(chat.id)
    current_status = settings.get("raid_mode_enabled", False)

    args = context.args or []
    if not args:
        status_text = "🚨 ACTIVE (LOCKDOWN)" if current_status else "⚪ INACTIVE (NORMAL)"
        await message.reply_text(
            f"🛡️ <b>Raid Emergency Mode:</b> {status_text}\n\n"
            "• <code>/raid on</code> - Enable emergency lockdown mode\n"
            "• <code>/raid off</code> - Disable emergency lockdown mode",
            parse_mode=ParseMode.HTML,
        )
        return

    action = args[0].lower()
    if action in ("on", "enable", "start", "1"):
        update_group_feature(chat.id, "raid_mode_enabled", True)
        increment_stat(chat.id, "raid_actions_taken", count=1, chat_title=chat.title)
        log_moderation_event(chat.id, user.id if user else 0, "RAID_MODE_ON", "Emergency Raid Mode enabled by admin")
        await message.reply_text(
            "🚨 <b>Emergency Raid Mode has been ENABLED!</b>\n\n"
            "High-alert monitoring is active. All join activity is being logged and flagged.\n"
            "To restore normal mode, send <code>/raid off</code>.",
            parse_mode=ParseMode.HTML,
        )
    elif action in ("off", "disable", "stop", "0"):
        update_group_feature(chat.id, "raid_mode_enabled", False)
        log_moderation_event(chat.id, user.id if user else 0, "RAID_MODE_OFF", "Emergency Raid Mode disabled by admin")
        await message.reply_text(
            "✅ <b>Emergency Raid Mode has been DISABLED.</b> Normal group moderation restored.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply_text("Usage: <code>/raid on</code> or <code>/raid off</code>", parse_mode=ParseMode.HTML)


def register_extra_protection_handlers(application: Application) -> None:
    """Register anti-forward, service message cleaner, and raid command handlers."""
    application.add_handler(CommandHandler("raid", raid_command), group=0)
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.ALL, handle_service_message), group=0)
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.FORWARDED, handle_anti_forward), group=3)
