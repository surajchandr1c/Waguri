from datetime import datetime, timezone
import html
import logging
import re
import time
from telegram import ChatPermissions, Message, Update, User
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from database import (
    clear_active_incident,
    get_active_incident,
    get_group_settings,
    get_recent_moderation_logs,
    get_user_restrictions,
    get_user_warnings_count,
    increment_stat,
    lift_active_restrictions,
    log_moderation_event,
    record_restriction,
    reset_user_warnings,
    set_group_anti_bio_link,
    set_group_anti_link,
    set_group_anti_spam,
    set_group_clean_service,
)
from handlers.admin_check import check_bot_permissions, is_sender_admin_or_owner

logger = logging.getLogger("Waguri.AdminCommands")


NO_SEND_PERMISSIONS = ChatPermissions(
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

UNRESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


def parse_duration(arg: str | None) -> tuple[int, str]:
    """
    Parse duration string like '10m', '2h', '1d', '30s'.
    Returns (duration_in_seconds, human_readable_string).
    Defaults to 24 hours (86400s) if omitted or invalid.
    """
    if not arg or not arg.strip():
        return 86400, "24 hours"

    arg = arg.strip().lower()
    match = re.match(r"^(\d+)\s*([smhd]?)$", arg)
    if not match:
        return 86400, "24 hours"

    val = int(match.group(1))
    unit = match.group(2) or "m"

    if unit == "s":
        seconds = max(30, min(val, 365 * 86400))
        return seconds, f"{seconds} seconds"
    elif unit == "m":
        seconds = max(30, min(val * 60, 365 * 86400))
        return seconds, f"{val} minute(s)"
    elif unit == "h":
        seconds = max(30, min(val * 3600, 365 * 86400))
        return seconds, f"{val} hour(s)"
    elif unit == "d":
        seconds = max(30, min(val * 86400, 365 * 86400))
        return seconds, f"{val} day(s)"

    return 86400, "24 hours"


async def verify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Verify that the sender is an authorized administrator in the group.
    Notifies the user and returns False if unauthorized.
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat:
        return False

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text("This command can only be used in a group or supergroup.")
        return False

    sender_chat = getattr(message, "sender_chat", None)
    is_admin = await is_sender_admin_or_owner(chat, user, sender_chat, context.bot)

    if not is_admin:
        await message.reply_text("You need administrator privileges to use this command.")
        logger.warning(
            "[UNAUTHORIZED ACCESS] User %s attempted admin command '%s' in group '%s' (ID: %s)",
            user.id if user else "Unknown",
            message.text,
            chat.title,
            chat.id,
        )
        return False

    return True


def resolve_target_user(
    message: Message,
    args: list[str] | None = None,
) -> tuple[int | None, str, User | None, str | None]:
    """
    Extract target user id, display name, User object (if reply), and secondary argument
    from a replied message or command line arguments.
    Returns (target_user_id, target_name, target_user, extra_arg).
    """
    args = args or []
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        name = u.first_name or u.username or str(u.id)
        extra = args[0] if args else None
        return u.id, name, u, extra
    elif args and args[0].isdigit():
        uid = int(args[0])
        name = f"User {uid}"
        extra = args[1] if len(args) > 1 else None
        return uid, name, None, extra
    return None, "Unknown", None, None


async def _check_target_punishable(
    chat_id: int, target_user_id: int, bot, action_verb: str, message: Message
) -> bool:
    """Check if target user is Waguri or an administrator/owner and thus exempt from penalties."""
    if target_user_id == bot.id:
        await message.reply_text(f"⛔ You cannot {action_verb} Waguri.")
        return False

    try:
        target_member = await bot.get_chat_member(chat_id=chat_id, user_id=target_user_id)
        if target_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await message.reply_text(f"⛔ You cannot {action_verb} a group administrator or owner.")
            return False
    except Exception:
        pass

    return True


async def _toggle_group_setting(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    setting_key: str,
    feature_title: str,
    setter_func,
    cmd_name: str,
    on_desc: str | None = None,
    off_desc: str | None = None,
    icon: str = "🛡️",
) -> None:
    """Consolidated helper to toggle a binary group moderation setting on or off."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    args = context.args

    settings = get_group_settings(chat.id)
    current_status = settings.get(setting_key, True)

    on_label = on_desc or f"Enable {feature_title.lower()} protection"
    off_label = off_desc or f"Disable {feature_title.lower()} protection"

    if not args:
        status_text = "ENABLED" if current_status else "DISABLED"
        display_name = f"{feature_title} Protection" if "Protection" not in feature_title and "Messages" not in feature_title else feature_title
        await message.reply_text(
            f"{icon} {display_name} is currently: **{status_text}** in this group.\n\n"
            "To change setting:\n"
            f"• `/{cmd_name} on` - {on_label}\n"
            f"• `/{cmd_name} off` - {off_label}",
            parse_mode="Markdown",
        )
        return

    action = args[0].lower()
    display_suffix = " protection" if "Protection" not in feature_title and "Messages" not in feature_title else ""
    if action in ("on", "enable", "true", "1"):
        setter_func(chat.id, True)
        log_moderation_event(chat.id, update.effective_user.id, "CONFIG_CHANGE", f"{feature_title} ENABLED")
        await message.reply_text(f"✅ {feature_title}{display_suffix} has been **ENABLED** for this group.", parse_mode="Markdown")
        logger.info("[CONFIG] %s ENABLED in group '%s' (ID: %s)", feature_title, chat.title, chat.id)
    elif action in ("off", "disable", "false", "0"):
        setter_func(chat.id, False)
        log_moderation_event(chat.id, update.effective_user.id, "CONFIG_CHANGE", f"{feature_title} DISABLED")
        await message.reply_text(f"❌ {feature_title}{display_suffix} has been **DISABLED** for this group.", parse_mode="Markdown")
        logger.info("[CONFIG] %s DISABLED in group '%s' (ID: %s)", feature_title, chat.title, chat.id)
    else:
        await message.reply_text(f"ℹ️ Invalid option. Use `/{cmd_name} on` or `/{cmd_name} off`.", parse_mode="Markdown")


async def antlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable, disable, or check anti-link protection status in the group."""
    await _toggle_group_setting(
        update, context, "anti_link_enabled", "Anti-Link", set_group_anti_link, "antlink",
        on_desc="Enable anti-link protection", off_desc="Disable anti-link protection", icon="🛡️",
    )


async def antibiolink_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable, disable, or check anti-bio-link protection status in the group."""
    await _toggle_group_setting(
        update, context, "anti_bio_link_enabled", "Anti-Bio-Link", set_group_anti_bio_link, "antibiolink",
        on_desc="Enable anti-bio-link protection", off_desc="Disable anti-bio-link protection", icon="🛡️",
    )


async def cleanservice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable, disable, or check clean service messages status in the group."""
    await _toggle_group_setting(
        update, context, "clean_service_enabled", "Clean Service Messages", set_group_clean_service, "cleanservice",
        on_desc="Enable automatic removal of service messages (joins, leaves, pins)",
        off_desc="Disable automatic removal of service messages",
        icon="🧹",
    )


async def antispam_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable, disable, or check anti-spam protection status in the group."""
    await _toggle_group_setting(
        update, context, "anti_spam_enabled", "Anti-Spam", set_group_anti_spam, "antispam",
        on_desc="Enable anti-spam protection", off_desc="Disable anti-spam protection", icon="🛡️",
    )


async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inspect active warnings and restriction history for a specific member."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    target_user_id, target_name, _, _ = resolve_target_user(message, context.args)

    if not target_user_id:
        await message.reply_text(
            "ℹ️ How to view user warnings:\n"
            "• Reply to their message: `/warnings`\n"
            "• Or specify user ID: `/warnings <user_id>`",
            parse_mode="Markdown",
        )
        return

    active_incident = get_active_incident(chat.id, target_user_id)
    historical_restrictions = get_user_restrictions(chat.id, target_user_id)
    total_db_warnings = get_user_warnings_count(chat.id, target_user_id)

    lines = [f"📊 **Warning Status for {target_name}** (`{target_user_id}`)\n"]

    if active_incident and active_incident["count"] > 1:
        warn_count = active_incident["count"] - 1
        lines.append(f"⚠️ **Active Spam Warnings:** {warn_count}/2")
        lines.append(f"⏱ **Last Violation:** {int(time.time() - active_incident['last_message_time'])}s ago")
    else:
        lines.append("✅ **Active Spam Warnings:** 0 (Clean)")

    lines.append(f"📝 **Total Recorded Violations:** {total_db_warnings}")

    if historical_restrictions:
        lines.append(f"\n📜 **Past Restrictions ({len(historical_restrictions)}):**")
        for r in historical_restrictions[:3]:
            dt = datetime.fromtimestamp(r["restricted_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"• `{dt}` - {r['action'].upper()} - {r['reason']}")
    else:
        lines.append("📜 **Restriction History:** None")

    await message.reply_text("\n".join(lines), parse_mode="Markdown")


async def resetwarnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all warnings and active spam incidents for a member."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    target_user_id, target_name, _, _ = resolve_target_user(message, context.args)

    if not target_user_id:
        await message.reply_text(
            "ℹ️ How to reset user warnings:\n"
            "• Reply to their message: `/resetwarnings`\n"
            "• Or specify user ID: `/resetwarnings <user_id>`",
            parse_mode="Markdown",
        )
        return

    reset_user_warnings(chat.id, target_user_id)
    clear_active_incident(chat.id, target_user_id)
    log_moderation_event(chat.id, update.effective_user.id, "RESET_WARNINGS", f"User: {target_user_id}")

    await message.reply_text(
        f"✅ <b>Warnings Reset:</b> All warnings for <b>{html.escape(target_name)}</b> have been cleared.",
        parse_mode=ParseMode.HTML,
    )


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Temporarily mute a user (/mute [duration] by reply, or /mute <user_id> [duration])."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    target_user_id, target_name, target_user, duration_arg = resolve_target_user(message, context.args)

    if not target_user_id:
        await message.reply_text(
            "ℹ️ How to mute a user:\n"
            "• Reply to their message: `/mute [10m|2h|1d]`\n"
            "• Or specify user ID: `/mute <user_id> [10m|2h|1d]`",
            parse_mode="Markdown",
        )
        return

    if not await _check_target_punishable(chat.id, target_user_id, context.bot, "mute", message):
        return

    _, can_restrict = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
    if not can_restrict:
        await message.reply_text(
            "⚠️ Waguri lacks 'Restrict Members' administrator permission.\n"
            "Please enable 'Ban Users / Restrict Members' in group settings."
        )
        return

    duration_seconds, duration_label = parse_duration(duration_arg)
    until_date = int(time.time()) + duration_seconds

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_user_id,
            permissions=NO_SEND_PERMISSIONS,
            until_date=until_date,
        )

        record_restriction(
            chat_id=chat.id,
            user_id=target_user_id,
            username=getattr(target_user, "username", None) if target_user else None,
            reason=f"Manual mute by admin ({duration_label})",
            restricted_at=time.time(),
            expires_at=time.time() + duration_seconds,
            action="mute",
        )
        increment_stat(chat.id, "restrictions_applied", count=1, chat_title=chat.title)
        log_moderation_event(chat.id, update.effective_user.id, "MUTE", f"User: {target_user_id}, Duration: {duration_label}")

        await message.reply_text(
            f"🔇 **{target_name}** has been muted for **{duration_label}**.",
            parse_mode="Markdown",
        )
        logger.info(
            "[MANUAL MUTE] Group: '%s' (ID: %s) | User: %s muted for %s",
            chat.title,
            chat.id,
            target_user_id,
            duration_label,
        )
    except (Forbidden, BadRequest) as exc:
        await message.reply_text(f"⚠️ Telegram API Error: {exc}")
        logger.error("[MUTE FAILED] Could not mute user %s: %s", target_user_id, exc)


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove restrictions and unmute a user."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    target_user_id, target_name, _, _ = resolve_target_user(message, context.args)

    if not target_user_id:
        await message.reply_text(
            "ℹ️ How to unmute a user:\n"
            "• Reply to their message: `/unmute`\n"
            "• Or specify user ID: `/unmute <user_id>`",
            parse_mode="Markdown",
        )
        return

    _, can_restrict = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
    if not can_restrict:
        await message.reply_text(
            "⚠️ Waguri lacks 'Restrict Members' administrator permission.\n"
            "Please enable 'Ban Users / Restrict Members' in group settings."
        )
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_user_id,
            permissions=UNRESTRICTED_PERMISSIONS,
        )

        lift_active_restrictions(chat.id, target_user_id)
        clear_active_incident(chat.id, target_user_id)
        log_moderation_event(chat.id, update.effective_user.id, "UNMUTE", f"User: {target_user_id}")

        await message.reply_text(
            f"🔊 **{target_name}** has been unmuted. Normal permissions restored.",
            parse_mode="Markdown",
        )
        logger.info(
            "[MANUAL UNMUTE] Group: '%s' (ID: %s) | User: %s unmuted",
            chat.title,
            chat.id,
            target_user_id,
        )
    except (Forbidden, BadRequest) as exc:
        await message.reply_text(f"⚠️ Telegram API Error: {exc}")
        logger.error("[UNMUTE FAILED] Could not unmute user %s: %s", target_user_id, exc)


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user from the group (/ban by reply or /ban <user_id>)."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    target_user_id, target_name, target_user, _ = resolve_target_user(message, context.args)

    if not target_user_id:
        await message.reply_text(
            "ℹ️ How to ban a user:\n"
            "• Reply to their message: `/ban`\n"
            "• Or specify user ID: `/ban <user_id>`",
            parse_mode="Markdown",
        )
        return

    if not await _check_target_punishable(chat.id, target_user_id, context.bot, "ban", message):
        return

    _, can_restrict = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
    if not can_restrict:
        await message.reply_text("⚠️ Waguri lacks 'Ban Users' administrator permission.")
        return

    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user_id)
        record_restriction(
            chat_id=chat.id,
            user_id=target_user_id,
            username=getattr(target_user, "username", None) if target_user else None,
            reason="Manual ban by admin",
            restricted_at=time.time(),
            expires_at=0,
            action="ban",
        )
        increment_stat(chat.id, "banned_members", count=1, chat_title=chat.title)
        log_moderation_event(chat.id, update.effective_user.id, "BAN", f"User: {target_user_id}")

        await message.reply_text(f"🔨 <b>{html.escape(target_name)}</b> has been banned from the group.", parse_mode=ParseMode.HTML)
    except (Forbidden, BadRequest) as exc:
        await message.reply_text(f"⚠️ Telegram API Error: {exc}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a previously banned user (/unban <user_id>)."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat
    target_user_id, _, _, _ = resolve_target_user(message, context.args)

    if not target_user_id:
        await message.reply_text("Usage: <code>/unban &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    try:
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target_user_id, only_if_banned=True)
        lift_active_restrictions(chat.id, target_user_id)
        log_moderation_event(chat.id, update.effective_user.id, "UNBAN", f"User: {target_user_id}")
        await message.reply_text(f"✅ User ID <code>{target_user_id}</code> has been unbanned.", parse_mode=ParseMode.HTML)
    except (Forbidden, BadRequest) as exc:
        await message.reply_text(f"⚠️ Telegram API Error: {exc}")
    except (Forbidden, BadRequest) as exc:
        await message.reply_text(f"⚠️ Telegram API Error: {exc}")


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display recent moderation audit logs for the current group."""
    if not await verify_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat

    logs = get_recent_moderation_logs(chat.id, limit=10)
    if not logs:
        await message.reply_text("📋 No moderation audit events recorded yet for this group.")
        return

    lines = [f"📋 <b>Recent Moderation Audit Logs ({html.escape(chat.title or 'Group')})</b>\n"]
    for entry in logs:
        dt = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        action = html.escape(entry["action"])
        details = html.escape(entry["details"])
        uid = entry["user_id"]
        lines.append(f"• <code>[{dt}]</code> <b>{action}</b> (User: <code>{uid}</code>)\n  <i>{details}</i>")

    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return relevant group and user IDs."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    chat_title = chat.title or "Private Chat"
    user_name = user.full_name or user.first_name or "Unknown"

    lines = [
        "📋 **ID Information**",
        f"• **Chat Title:** `{chat_title}`",
        f"• **Chat ID:** `{chat.id}`",
        f"• **Chat Type:** `{chat.type}`",
        f"• **Your Name:** `{user_name}`",
        f"• **Your User ID:** `{user.id}`",
    ]

    if user.username:
        lines.append(f"• **Your Username:** `@{user.username}`")

    if message.reply_to_message:
        replied = message.reply_to_message
        r_user = replied.from_user
        lines.append("\n📬 **Replied Message Details**")
        lines.append(f"• **Message ID:** `{replied.message_id}`")
        if r_user:
            r_name = r_user.full_name or r_user.first_name or "Unknown"
            lines.append(f"• **Sender Name:** `{r_name}`")
            lines.append(f"• **Sender ID:** `{r_user.id}`")
            if r_user.username:
                lines.append(f"• **Sender Username:** `@{r_user.username}`")

    await message.reply_text("\n".join(lines), parse_mode="Markdown")


def register_admin_command_handlers(application: Application) -> None:
    """Register all administrator moderation commands on the application."""
    application.add_handler(CommandHandler("antlink", antlink_command), group=0)
    application.add_handler(CommandHandler("antibiolink", antibiolink_command), group=0)
    application.add_handler(CommandHandler(["cleanservice", "antiservice"], cleanservice_command), group=0)
    application.add_handler(CommandHandler("antispam", antispam_command), group=0)
    application.add_handler(CommandHandler("warnings", warnings_command), group=0)
    application.add_handler(CommandHandler("resetwarnings", resetwarnings_command), group=0)
    application.add_handler(CommandHandler("mute", mute_command), group=0)
    application.add_handler(CommandHandler("unmute", unmute_command), group=0)
    application.add_handler(CommandHandler("ban", ban_command), group=0)
    application.add_handler(CommandHandler("unban", unban_command), group=0)
    application.add_handler(CommandHandler("logs", logs_command), group=0)
    application.add_handler(CommandHandler("id", id_command), group=0)
