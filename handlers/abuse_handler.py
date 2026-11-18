"""
Abuse Detection & Auto-Moderation Telegram Handler for Waguri Bot.

Provides:
- Automatic message & media caption inspection for groups
- Detection and deletion of sexual vulgarity, threats, assault slurs, and bypass variants
- Support for edited messages (UpdateType.EDITED_MESSAGE)
- Persistent warning system with configurable auto-expiry
- Escalating temporary mute punishment on repeat offenses
- Rate-limited auto-cleaning warning notifications
- Comprehensive /abuse administrator command suite
- Server-side RBAC and administrator exemptions
"""

import asyncio
from datetime import datetime, timezone
import html
import logging
import re
import time
from typing import Dict, Optional, Set, Tuple

from telegram import Chat, ChatPermissions, Message, Update, User
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import (
    add_abuse_custom_keyword,
    add_user_abuse_warning,
    get_abuse_custom_keywords,
    get_abuse_moderation_logs,
    get_abuse_settings,
    get_group_settings,
    get_group_stats,
    get_user_abuse_warnings,
    get_user_abuse_warnings_count,
    increment_stat,
    log_moderation_event,
    record_restriction,
    remove_abuse_custom_keyword,
    reset_user_abuse_warnings,
    update_abuse_settings,
    update_group_feature,
)
from handlers.admin_check import check_bot_permissions, is_sender_admin_or_owner
from moderation.abuse import AbuseAction, get_abuse_detector

logger = logging.getLogger("Waguri.AbuseHandler")

# Permissions for muting a member
MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

# Concurrency locks: (chat_id, user_id) -> asyncio.Lock
_user_locks: Dict[Tuple[int, int], asyncio.Lock] = {}

# Processed message cache to prevent duplicate processing / double warnings: (chat_id, message_id, text_sig) -> timestamp
_processed_messages: Dict[Tuple[int, int, str], float] = {}
PROCESSED_MSG_TTL = 300.0  # 5 minutes


def _get_user_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    """Retrieve or initialize concurrency lock for a user in a chat."""
    key = (chat_id, user_id)
    if key not in _user_locks:
        _user_locks[key] = asyncio.Lock()
    return _user_locks[key]


def _is_message_already_processed(chat_id: int, message_id: int, text: str = "") -> bool:
    """Check and record whether a message with given text has already been processed."""
    now = time.time()
    text_sig = str(hash(text[:100])) if text else ""
    key = (chat_id, message_id, text_sig)

    # Clean old cache entries occasionally
    if len(_processed_messages) > 1000:
        cutoff = now - PROCESSED_MSG_TTL
        keys_to_del = [k for k, t in _processed_messages.items() if t < cutoff]
        for k in keys_to_del:
            _processed_messages.pop(k, None)

    if key in _processed_messages:
        return True

    _processed_messages[key] = now
    return False


async def schedule_warning_cleanup(message: Message, delay_seconds: int = 10) -> None:
    """Asynchronously delete an automated warning notification to keep chat clean."""
    if delay_seconds <= 0:
        return
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception as exc:
        logger.debug("[ABUSE CLEANUP] Could not delete warning message: %s", exc)


def format_duration(seconds: int) -> str:
    """Format seconds into human readable duration string."""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        return f"{seconds // 60} minute(s)"
    elif seconds < 86400:
        return f"{seconds // 3600} hour(s)"
    else:
        return f"{seconds // 86400} day(s)"


# =============================================================================
# Core Message Moderation Handler
# =============================================================================

async def handle_abuse_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Inspect incoming group messages and media captions for abusive language, threats,
    harassment, and bypass attempts. Deletes violating messages and issues progressive warnings.
    """
    message = update.effective_message
    chat = update.effective_chat
    sender = update.effective_user

    if not message or not chat:
        return

    # Restrict to groups and supergroups
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Extract text content from message or media caption
    text = (message.text or "") or (message.caption or "")
    if not text or not text.strip():
        return

    # Check and update processed message cache to prevent duplicate triggers
    if _is_message_already_processed(chat.id, message.message_id, text):
        return

    # Load group moderation settings
    settings = get_group_settings(chat.id)
    if not settings.get("is_active", True):
        return

    if not settings.get("abuse_detection_enabled", True):
        return

    # 1. Administrator & Owner Exemption Checks
    sender_chat = getattr(message, "sender_chat", None)
    is_admin = await is_sender_admin_or_owner(chat, sender, sender_chat, context.bot)
    exempt_admins = settings.get("abuse_exempt_admins", False)
    if is_admin and exempt_admins:
        logger.info("[ABUSE SKIPPED] Admin %s is exempt by group settings.", sender.id if sender else 0)
        return

    # 2. Check trusted user exemptions
    trusted_users = settings.get("abuse_trusted_users") or []
    if sender and sender.id in trusted_users:
        return

    # Retrieve custom blocked and allowed keywords
    blocked_words, allowed_words = get_abuse_custom_keywords(chat.id)

    # 3. Evaluate content through AbuseDetector
    detector = get_abuse_detector()
    result = detector.check_message(
        text=text,
        custom_blocked_words=blocked_words,
        custom_allowed_words=allowed_words,
        settings=settings,
    )

    if not result.is_abusive:
        return

    # Acquire concurrency lock for user in chat
    user_id = sender.id if sender else 0
    lock = _get_user_lock(chat.id, user_id)

    async with lock:
        # 4. Delete the violating message
        chat_title = chat.title or "Unnamed Group"
        try:
            await message.delete()
            increment_stat(chat.id, "abuse_deleted", count=1, chat_title=chat_title)
            increment_stat(chat.id, "total_messages_checked", count=1, chat_title=chat_title)
            log_moderation_event(
                chat.id,
                user_id,
                "ABUSE_DELETED",
                f"Msg ID: {message.message_id}, Score: {result.score}, Cat: {result.category}, Reason: {result.reason}",
            )
            logger.info(
                "[ABUSE DELETED] Chat: '%s' (%s) | User: %s (%s) | Category: %s | Score: %d | Matches: %s",
                chat_title,
                chat.id,
                sender.first_name if sender else "Unknown",
                user_id,
                result.category,
                result.score,
                result.matched_terms,
            )
        except (Forbidden, BadRequest) as exc:
            logger.error("[ABUSE DELETE ERROR] Could not delete message %s: %s. Waguri needs 'Delete Messages' admin permission.", message.message_id, exc)
            return

        # 5. Warning & Escalation System (1 warning -> 2nd time mute according to set time)
        if not settings.get("abuse_warning_system", True):
            return

        # Record warning in database
        warn_limit = int(settings.get("abuse_warning_limit") or 1)
        warn_num = add_user_abuse_warning(
            chat_id=chat.id,
            user_id=user_id,
            reason=result.reason,
            score=result.score,
            category=result.category,
            message_id=message.message_id,
        )
        increment_stat(chat.id, "warnings_issued", count=1, chat_title=chat_title)

        sender_mention = (
            f"<a href=\"tg://user?id={sender.id}\">{html.escape(sender.first_name or 'Member')}</a>"
            if sender
            else "Member"
        )
        cat_display = result.category.replace("_", " ").title()

        mute_base_mins = int(settings.get("abuse_mute_duration_minutes") or 30)
        mute_duration_sec = mute_base_mins * 60
        duration_str = format_duration(mute_duration_sec)

        # User requirement:
        # 1st time: give the user a warning
        # 2nd time: mute the user according to the set time
        should_mute = (warn_num >= 2) or (warn_num > warn_limit)

        if not should_mute:
            # 1st Violation: Issue Warning Notice
            warn_msg_text = (
                f"🚨 <b>Abuse Moderation Warning [1/2]</b>\n\n"
                f"👤 <b>Member:</b> {sender_mention}\n"
                f"🚫 <b>Violation:</b> {cat_display} is strictly prohibited in this group.\n"
                f"⚠️ <i>Your message was removed. If you send abusive language a 2nd time, you will be muted for {duration_str}.</i>"
            )
            try:
                sent_warn = await context.bot.send_message(
                    chat_id=chat.id,
                    text=warn_msg_text,
                    parse_mode=ParseMode.HTML,
                )
                cleanup_sec = int(settings.get("warning_delete_after_seconds") or 10)
                asyncio.create_task(schedule_warning_cleanup(sent_warn, cleanup_sec))
            except Exception as exc:
                logger.debug("[ABUSE WARN SEND ERROR] Could not send warning: %s", exc)

        else:
            # 2nd Violation (or above): Mute user according to set time
            if is_admin:
                admin_warn_text = (
                    f"⚠️ <b>Abuse Warning [{warn_num}]</b>\n\n"
                    f"👤 <b>Member:</b> {sender_mention} (Admin)\n"
                    f"🚫 <i>Abusive message deleted. Note: Group administrators cannot be muted by Telegram, but violations are logged.</i>"
                )
                try:
                    sent_notice = await context.bot.send_message(
                        chat_id=chat.id,
                        text=admin_warn_text,
                        parse_mode=ParseMode.HTML,
                    )
                    asyncio.create_task(schedule_warning_cleanup(sent_notice, 10))
                except Exception:
                    pass
            else:
                until_date = int(time.time()) + mute_duration_sec
                try:
                    await context.bot.restrict_chat_member(
                        chat_id=chat.id,
                        user_id=user_id,
                        permissions=MUTE_PERMISSIONS,
                        until_date=until_date,
                    )
                    record_restriction(
                        chat_id=chat.id,
                        user_id=user_id,
                        username=sender.username if sender else None,
                        reason=f"Abuse detection: {result.reason} (Violation #{warn_num})",
                        restricted_at=time.time(),
                        expires_at=until_date,
                        action="mute",
                    )
                    increment_stat(chat.id, "restrictions_applied", count=1, chat_title=chat_title)
                    log_moderation_event(
                        chat.id,
                        user_id,
                        "ABUSE_MUTED",
                        f"Muted for {duration_str} following violation #{warn_num} ({cat_display})",
                    )

                    mute_msg_text = (
                        f"⛔️ <b>Member Muted for Abusive Language</b>\n\n"
                        f"👤 <b>Member:</b> {sender_mention}\n"
                        f"⏱ <b>Mute Duration:</b> {duration_str}\n"
                        f"🚫 <b>Reason:</b> 2nd abuse violation ({cat_display}).\n"
                        f"<i>Messaging permissions will be restored automatically after {duration_str}.</i>"
                    )
                    sent_mute = await context.bot.send_message(
                        chat_id=chat.id,
                        text=mute_msg_text,
                        parse_mode=ParseMode.HTML,
                    )
                    asyncio.create_task(schedule_warning_cleanup(sent_mute, 15))
                except Exception as exc:
                    logger.error("[ABUSE MUTE FAILED] Could not mute user %s: %s", user_id, exc)

        return


# =============================================================================
# Administrator Commands: /abuse Suite
# =============================================================================

async def abuse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comprehensive /abuse command dispatcher for group administrators.

    Commands:
      /abuse on                 - Enable Abuse moderation
      /abuse off                - Disable Abuse moderation
      /abuse status             - View current status and detection settings
      /abuse words              - List custom blocked and allowed words
      /abuse addword <words>    - Add custom blocked word(s) (comma-separated supported)
      /abuse removeword <words> - Remove custom keyword(s) (comma-separated supported)
      /abuse warnings [@user|id]- Check user's abuse warnings
      /abuse reset [@user|id]   - Reset user's abuse warnings
      /abuse settings           - View / adjust Abuse sensitivity and limits
      /abuse logs               - Review recent Abuse moderation logs
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat:
        return

    # Command can only be run in groups
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text("The /abuse command can only be used in a group or supergroup.")
        return

    # Verify administrator or owner privileges
    sender_chat = getattr(message, "sender_chat", None)
    is_admin = await is_sender_admin_or_owner(chat, user, sender_chat, context.bot)
    if not is_admin:
        await message.reply_text("❌ <b>Access Denied:</b> You need administrator privileges to manage Abuse moderation.", parse_mode=ParseMode.HTML)
        return

    args = context.args or []
    if not args:
        # Show help summary
        help_text = (
            "🚨 <b>Waguri Abuse Moderation Commands</b>\n\n"
            "• <code>/abuse on</code> - Enable Abuse detection\n"
            "• <code>/abuse off</code> - Disable Abuse detection\n"
            "• <code>/abuse mute &lt;mins&gt;</code> - Set temporary mute duration (e.g. 30)\n"
            "• <code>/abuse limit &lt;number&gt;</code> - Set warnings before mute (e.g. 1)\n"
            "• <code>/abuse status</code> - Check system status & statistics\n"
            "• <code>/abuse words</code> - View custom blocked/allowed keywords\n"
            "• <code>/abuse addword &lt;word1, word2, ...&gt;</code> - Add custom blocked keyword(s)\n"
            "• <code>/abuse removeword &lt;word1, word2, ...&gt;</code> - Remove custom keyword(s)\n"
            "• <code>/abuse warnings [@user|id]</code> - Check member warnings\n"
            "• <code>/abuse reset [@user|id]</code> - Clear member warnings\n"
            "• <code>/abuse settings</code> - View sensitivity & mute configuration\n"
            "• <code>/abuse logs</code> - Review recent abuse violation logs\n\n"
            "<i>Only authorized group administrators can change these settings.</i>"
        )
        await message.reply_text(help_text, parse_mode=ParseMode.HTML)
        return

    subcmd = args[0].lower()

    # 1. /abuse on
    if subcmd == "on":
        update_abuse_settings(chat.id, abuse_detection_enabled=True)
        update_group_feature(chat.id, "abuse_detection_enabled", True)
        log_moderation_event(chat.id, user.id if user else 0, "ABUSE_ENABLED", "Enabled by administrator")
        await message.reply_text("🟢 <b>Abuse Detection & Auto-Moderation is now ENABLED.</b>\nInappropriate language, sexual harassment, threats, and obfuscations will be removed automatically.", parse_mode=ParseMode.HTML)
        return

    # 2. /abuse off
    elif subcmd == "off":
        update_abuse_settings(chat.id, abuse_detection_enabled=False)
        update_group_feature(chat.id, "abuse_detection_enabled", False)
        log_moderation_event(chat.id, user.id if user else 0, "ABUSE_DISABLED", "Disabled by administrator")
        await message.reply_text("🔴 <b>Abuse Detection & Auto-Moderation is now DISABLED.</b>", parse_mode=ParseMode.HTML)
        return

    # 3. /abuse status
    elif subcmd == "status":
        settings = get_abuse_settings(chat.id)
        stats = get_group_stats(chat.id)
        blocked_words, allowed_words = get_abuse_custom_keywords(chat.id)

        status_icon = "🟢 ON" if settings["abuse_detection_enabled"] else "🔴 OFF"
        bypass_icon = "🟢 ON" if settings["abuse_bypass_detection"] else "🔴 OFF"
        warn_icon = "🟢 ON" if settings["abuse_warning_system"] else "🔴 OFF"

        status_text = (
            f"🚨 <b>Abuse Moderation Status</b>\n"
            f"👥 <b>Group:</b> {html.escape(chat.title or 'Group')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Status:</b> {status_icon}\n"
            f"• <b>Bypass & Leet Shield:</b> {bypass_icon}\n"
            f"• <b>Warning System:</b> {warn_icon}\n"
            f"• <b>Warning Threshold:</b> <code>{settings['abuse_warning_limit']} warnings</code>\n"
            f"• <b>Mute Duration:</b> <code>{settings['abuse_mute_duration_minutes']} minutes</code>\n"
            f"• <b>Warning Expiry:</b> <code>{settings['abuse_warning_expiry_hours']} hours</code>\n"
            f"• <b>Custom Blocked Words:</b> <code>{len(blocked_words)}</code>\n"
            f"• <b>Custom Allowed Words:</b> <code>{len(allowed_words)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Abuse Messages Deleted:</b> <code>{stats.get('abuse_deleted', 0)}</code>\n"
            f"⚠️ <b>Total Warnings Issued:</b> <code>{stats.get('warnings_issued', 0)}</code>"
        )
        await message.reply_text(status_text, parse_mode=ParseMode.HTML)
        return

    # 4. /abuse words
    elif subcmd == "words":
        blocked_words, allowed_words = get_abuse_custom_keywords(chat.id)
        blocked_display = ", ".join(f"<code>{html.escape(w)}</code>" for w in blocked_words) if blocked_words else "<i>None</i>"
        allowed_display = ", ".join(f"<code>{html.escape(w)}</code>" for w in allowed_words) if allowed_words else "<i>None</i>"

        words_text = (
            f"📝 <b>Abuse Custom Keywords</b>\n\n"
            f"🚫 <b>Blocked Keywords ({len(blocked_words)}):</b>\n{blocked_display}\n\n"
            f"✅ <b>Whitelisted Keywords ({len(allowed_words)}):</b>\n{allowed_display}\n\n"
            f"<i>To add words:</i> <code>/abuse addword &lt;word1, word2, ...&gt;</code>\n"
            f"<i>To remove words:</i> <code>/abuse removeword &lt;word1, word2, ...&gt;</code>"
        )
        await message.reply_text(words_text, parse_mode=ParseMode.HTML)
        return

    # 5. /abuse addword <word1, word2, ...>
    elif subcmd == "addword":
        if len(args) < 2:
            await message.reply_text(
                "Usage: <code>/abuse addword &lt;word&gt;</code> or separated by commas: <code>/abuse addword badword1, badword2, badword3</code>",
                parse_mode=ParseMode.HTML
            )
            return
        raw_text = " ".join(args[1:])
        words = [w.strip().lower() for w in raw_text.split(",") if w.strip()]
        if not words:
            await message.reply_text("Usage: <code>/abuse addword &lt;word1, word2, ...&gt;</code>", parse_mode=ParseMode.HTML)
            return

        unique_words = list(dict.fromkeys(words))
        added = []
        too_short = []
        failed = []

        for word in unique_words:
            if len(word) < 2:
                too_short.append(word)
                continue
            success = add_abuse_custom_keyword(chat.id, word, is_blocked=True)
            if success:
                log_moderation_event(chat.id, user.id if user else 0, "ABUSE_WORD_ADDED", f"Added blocked word '{word}'")
                added.append(word)
            else:
                failed.append(word)

        response_lines = []
        if added:
            if len(added) == 1:
                response_lines.append(f"✅ Added <code>{html.escape(added[0])}</code> to custom blocked keywords for this group.")
            else:
                added_str = ", ".join(f"<code>{html.escape(w)}</code>" for w in added)
                response_lines.append(f"✅ Added {len(added)} custom blocked keywords:\n{added_str}")
        if too_short:
            response_lines.append(f"⚠️ Skipped (must be ≥2 characters): {', '.join(f'<code>{html.escape(w)}</code>' for w in too_short)}")
        if failed:
            response_lines.append(f"❌ Failed to add: {', '.join(f'<code>{html.escape(w)}</code>' for w in failed)}")

        await message.reply_text("\n\n".join(response_lines) if response_lines else "No valid keywords provided.", parse_mode=ParseMode.HTML)
        return

    # 6. /abuse removeword <word1, word2, ...>
    elif subcmd == "removeword":
        if len(args) < 2:
            await message.reply_text(
                "Usage: <code>/abuse removeword &lt;word&gt;</code> or separated by commas: <code>/abuse removeword word1, word2</code>",
                parse_mode=ParseMode.HTML
            )
            return
        raw_text = " ".join(args[1:])
        words = [w.strip().lower() for w in raw_text.split(",") if w.strip()]
        if not words:
            await message.reply_text("Usage: <code>/abuse removeword &lt;word1, word2, ...&gt;</code>", parse_mode=ParseMode.HTML)
            return

        unique_words = list(dict.fromkeys(words))
        removed = []
        not_found = []

        for word in unique_words:
            success = remove_abuse_custom_keyword(chat.id, word)
            if success:
                log_moderation_event(chat.id, user.id if user else 0, "ABUSE_WORD_REMOVED", f"Removed keyword '{word}'")
                removed.append(word)
            else:
                not_found.append(word)

        response_lines = []
        if removed:
            if len(removed) == 1:
                response_lines.append(f"🗑 Removed <code>{html.escape(removed[0])}</code> from custom keywords.")
            else:
                removed_str = ", ".join(f"<code>{html.escape(w)}</code>" for w in removed)
                response_lines.append(f"🗑 Removed {len(removed)} custom keywords:\n{removed_str}")
        if not_found:
            not_found_str = ", ".join(f"<code>{html.escape(w)}</code>" for w in not_found)
            response_lines.append(f"⚠️ Not found in custom keywords: {not_found_str}")

        await message.reply_text("\n\n".join(response_lines), parse_mode=ParseMode.HTML)
        return

    # 7. /abuse warnings [@user|user_id]
    elif subcmd == "warnings":
        target_user = None
        # Check reply
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
        elif len(args) >= 2:
            arg = args[1].lstrip("@")
            if arg.isdigit():
                try:
                    chat_member = await context.bot.get_chat_member(chat.id, int(arg))
                    target_user = chat_member.user
                except Exception:
                    pass

        if not target_user:
            await message.reply_text("Please reply to a member's message or specify user ID: <code>/abuse warnings &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
            return

        settings = get_abuse_settings(chat.id)
        expiry_hours = settings.get("abuse_warning_expiry_hours", 24)
        warn_limit = settings.get("abuse_warning_limit", 3)
        warn_list = get_user_abuse_warnings(chat.id, target_user.id, expiry_hours=expiry_hours)

        target_name = html.escape(target_user.first_name or "Member")
        if not warn_list:
            await message.reply_text(f"✅ Member <b>{target_name}</b> (ID: <code>{target_user.id}</code>) has <b>0</b> active abuse warnings.", parse_mode=ParseMode.HTML)
            return

        lines = [f"⚠️ <b>Abuse Warnings for {target_name}</b> (ID: <code>{target_user.id}</code>):"]
        lines.append(f"<b>Active Warnings:</b> {len(warn_list)} / {warn_limit} (Expiry: {expiry_hours}h)\n")
        for w in warn_list[:5]:
            dt = datetime.fromtimestamp(w["issued_at"], tz=timezone.utc).strftime("%m-%d %H:%M")
            lines.append(f"• <b>[{dt}]</b> #{w['warning_number']} ({w['abuse_category']}): <i>{html.escape(w['reason'])}</i>")

        lines.append("\n<i>To clear warnings:</i> <code>/abuse reset " + str(target_user.id) + "</code>")
        await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # 8. /abuse reset [@user|user_id]
    elif subcmd == "reset":
        target_user = None
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
        elif len(args) >= 2:
            arg = args[1].lstrip("@")
            if arg.isdigit():
                try:
                    chat_member = await context.bot.get_chat_member(chat.id, int(arg))
                    target_user = chat_member.user
                except Exception:
                    pass

        if not target_user:
            await message.reply_text("Please reply to a member's message or specify user ID: <code>/abuse reset &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
            return

        cleared_count = reset_user_abuse_warnings(chat.id, target_user.id)
        log_moderation_event(chat.id, user.id if user else 0, "ABUSE_RESET", f"Reset warnings for user {target_user.id} (cleared {cleared_count})")
        target_name = html.escape(target_user.first_name or "Member")
        await message.reply_text(
            f"🔄 <b>Warnings Cleared:</b> Reset <b>{cleared_count}</b> active abuse warning(s) for <b>{target_name}</b> (ID: <code>{target_user.id}</code>).",
            parse_mode=ParseMode.HTML,
        )
        return

    # 9. /abuse settings
    elif subcmd == "settings":
        settings = get_abuse_settings(chat.id)
        text = (
            f"⚙️ <b>Abuse Moderation Configuration</b>\n\n"
            f"• <b>Abuse Shield:</b> {'ON 🟢' if settings['abuse_detection_enabled'] else 'OFF 🔴'}\n"
            f"• <b>Sexual Language:</b> {'ON 🟢' if settings['abuse_sexual_language'] else 'OFF 🔴'}\n"
            f"• <b>General Abuse:</b> {'ON 🟢' if settings['abuse_general_language'] else 'OFF 🔴'}\n"
            f"• <b>Hindi/Hinglish:</b> {'ON 🟢' if settings['abuse_hindi_hinglish'] else 'OFF 🔴'}\n"
            f"• <b>Harassment:</b> {'ON 🟢' if settings['abuse_harassment'] else 'OFF 🔴'}\n"
            f"• <b>Threats:</b> {'ON 🟢' if settings['abuse_threats'] else 'OFF 🔴'}\n"
            f"• <b>Bypass Detection:</b> {'ON 🟢' if settings['abuse_bypass_detection'] else 'OFF 🔴'}\n"
            f"• <b>Warning System:</b> {'ON 🟢' if settings['abuse_warning_system'] else 'OFF 🔴'}\n"
            f"• <b>Warning Threshold:</b> <code>{settings['abuse_warning_limit']} warnings</code>\n"
            f"• <b>Mute Duration:</b> <code>{settings['abuse_mute_duration_minutes']} minutes</code>\n"
            f"• <b>Warning Expiry:</b> <code>{settings['abuse_warning_expiry_hours']} hours</code>\n\n"
            f"<i>Use <code>/settings</code> to open the interactive inline configuration panel.</i>"
        )
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    # 10. /abuse mute <minutes>
    elif subcmd == "mute":
        if len(args) < 2 or not args[1].isdigit():
            await message.reply_text("Usage: <code>/abuse mute &lt;minutes&gt;</code> (e.g. <code>/abuse mute 30</code>)", parse_mode=ParseMode.HTML)
            return
        mins = max(1, min(1440, int(args[1])))
        update_abuse_settings(chat.id, abuse_mute_duration_minutes=mins)
        log_moderation_event(chat.id, user.id if user else 0, "ABUSE_MUTE_SET", f"Set abuse mute duration to {mins}m")
        await message.reply_text(f"⏱ <b>Abuse Mute Duration Updated:</b> Repeat violators will be muted for <b>{mins} minutes</b>.", parse_mode=ParseMode.HTML)
        return

    # 11. /abuse limit <number>
    elif subcmd in ("limit", "warnlimit"):
        if len(args) < 2 or not args[1].isdigit():
            await message.reply_text("Usage: <code>/abuse limit &lt;number&gt;</code> (e.g. <code>/abuse limit 1</code>)", parse_mode=ParseMode.HTML)
            return
        limit = max(1, min(10, int(args[1])))
        update_abuse_settings(chat.id, abuse_warning_limit=limit)
        log_moderation_event(chat.id, user.id if user else 0, "ABUSE_LIMIT_SET", f"Set warning limit to {limit}")
        await message.reply_text(f"⚠️ <b>Abuse Warning Limit Updated:</b> Members receive <b>{limit} warning(s)</b> before being muted.", parse_mode=ParseMode.HTML)
        return

    # 12. /abuse logs
    elif subcmd == "logs":
        logs = get_abuse_moderation_logs(chat.id, limit=8)
        if not logs:
            await message.reply_text("📋 <b>Abuse Moderation Logs</b>\n\nNo abuse moderation events recorded yet for this group.", parse_mode=ParseMode.HTML)
            return

        lines = ["📋 <b>Recent Abuse Moderation Audit Logs</b>\n"]
        for entry in logs:
            dt = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc).strftime("%m-%d %H:%M")
            action = html.escape(entry["action"])
            details = html.escape(entry["details"])
            uid = entry["user_id"]
            lines.append(f"• <b>[{dt}]</b> {action} | User: <code>{uid}</code>\n  <i>{details}</i>")

        await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    else:
        await message.reply_text(
            f"Unknown sub-command '<code>{html.escape(subcmd)}</code>'. Run <code>/abuse</code> for available commands.",
            parse_mode=ParseMode.HTML,
        )


def register_abuse_handlers(application: Application) -> None:
    """Register all Abuse moderation message filters and administrator commands."""
    # Group 0: /abuse command suite for group administrators
    application.add_handler(CommandHandler("abuse", abuse_command), group=0)

    # Group -1: Abuse auto-moderation on regular messages (text & captions)
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            handle_abuse_message,
        ),
        group=-1,
    )

    # Group -1: Abuse auto-moderation on edited messages (text & captions)
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION) & filters.UpdateType.EDITED_MESSAGE & ~filters.COMMAND,
            handle_abuse_message,
        ),
        group=-1,
    )
