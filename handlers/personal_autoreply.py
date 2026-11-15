import asyncio
from datetime import datetime, timezone
import html
import json
import logging
import time
from typing import Any

from telegram import (
    BusinessConnection,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    BusinessConnectionHandler,
    BusinessMessagesDeletedHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_OWNER_IDS
from database import (
    DEFAULT_PERSONAL_REPLY_TEMPLATE,
    add_excluded_user,
    check_and_claim_cooldown_reply,
    check_and_claim_first_contact,
    get_active_business_connection_for_user,
    get_business_connection,
    get_daily_replies_count,
    get_excluded_users_list,
    get_global_business_stats,
    get_personal_reply_settings,
    get_personal_reply_template,
    get_user_business_connections,
    get_user_business_stats,
    is_user_excluded,
    log_business_reply,
    remove_excluded_user,
    reset_personal_reply_template,
    save_or_update_business_connection,
    set_personal_reply_template,
    update_personal_reply_settings,
)
from handlers.admin_check import is_bot_owner

logger = logging.getLogger("Waguri.PersonalAutoReply")


def connection_can_reply(connection: Any) -> bool:
    """Safely check if a Telegram Business Connection has reply permission."""
    if hasattr(connection, "rights") and connection.rights is not None:
        return bool(getattr(connection.rights, "can_reply", True))
    if hasattr(connection, "can_reply"):
        return bool(getattr(connection, "can_reply", True))
    return True


def render_personal_template(template: str, sender: User) -> str:
    """
    Render custom message template variables safely with sender metadata:
      {first_name} -> sender first name
      {last_name}  -> sender last name (or empty)
      {full_name}  -> sender full name
      {username}   -> sender @username (or first name)
      {time}       -> current UTC time
      {date}       -> current UTC date
    """
    first_name = sender.first_name or "there"
    last_name = sender.last_name or ""
    full_name = sender.full_name or first_name
    username = f"@{sender.username}" if sender.username else first_name

    now_utc = datetime.now(timezone.utc)
    time_str = now_utc.strftime("%H:%M UTC")
    date_str = now_utc.strftime("%Y-%m-%d")

    rendered = template
    replacements = {
        "{first_name}": first_name,
        "{last_name}": last_name,
        "{full_name}": full_name,
        "{username}": username,
        "{time}": time_str,
        "{date}": date_str,
    }
    for placeholder, val in replacements.items():
        rendered = rendered.replace(placeholder, val)
    return rendered


def format_cooldown_label(seconds: int) -> str:
    """Format seconds into readable cooldown label (e.g., '1 hour', '24 hours')."""
    if seconds <= 0:
        return "None (Instant)"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} min{'s' if mins != 1 else ''}"
    hours = seconds // 3600
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''}"


def build_personal_settings_markup(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Build the interactive user dashboard message text and inline keyboard."""
    conn = get_active_business_connection_for_user(user_id)
    settings = get_personal_reply_settings(user_id)
    stats = get_user_business_stats(user_id)
    template = get_personal_reply_template(user_id)

    is_enabled = bool(settings.get("is_enabled", 1))
    first_time_only = bool(settings.get("first_time_only", 1))
    cooldown = settings.get("cooldown_seconds", 86400)
    daily_limit = settings.get("daily_limit", 100)
    delay = settings.get("reply_delay_seconds", 0)
    excluded = get_excluded_users_list(user_id)

    if conn:
        status_str = "🟢 Active" if conn.get("is_enabled") else "🔴 Disconnected"
        can_reply_str = "✅ Yes" if conn.get("can_reply") else "⚠️ No (Permission missing)"
        conn_id_display = f"<code>{conn.get('connection_id')}</code>"
        account_name = html.escape(conn.get("account_first_name") or f"Account {user_id}")
        if conn.get("account_username"):
            account_name += f" (@{conn.get('account_username')})"
    else:
        status_str = "⚪ Not Connected"
        can_reply_str = "—"
        conn_id_display = "<i>None (Connect in Telegram Settings)</i>"
        account_name = "<i>None</i>"

    # Truncate preview if long
    preview_snippet = template if len(template) <= 180 else template[:175] + "..."

    text = (
        "💼 <b>Personal Auto-Reply Dashboard</b>\n\n"
        f"<b>Connected Account:</b> {account_name}\n"
        f"<b>Connection ID:</b> {conn_id_display}\n"
        f"<b>Connection Status:</b> {status_str}\n"
        f"<b>Can Reply Permission:</b> {can_reply_str}\n\n"
        "⚙️ <b>Auto-Reply Settings:</b>\n"
        f"• Status: <b>{'🟢 ENABLED' if is_enabled else '🔴 DISABLED'}</b>\n"
        f"• Mode: <b>{'1️⃣ First-time Senders Only' if first_time_only else f'⏱️ Cooldown ({format_cooldown_label(cooldown)})'}</b>\n"
        f"• Daily Limit: <b>{daily_limit} replies</b> (Sent today: {stats.get('replies_today', 0)})\n"
        f"• Reply Delay: <b>{delay}s</b>\n"
        f"• Excluded Senders: <b>{len(excluded)}</b>\n\n"
        "📝 <b>Saved Reply Message:</b>\n"
        f"<blockquote>{html.escape(preview_snippet)}</blockquote>\n\n"
        "<i>Use the controls below to configure your personal auto-reply:</i>"
    )

    toggle_btn_text = "🔴 Disable Auto-Reply" if is_enabled else "🟢 Enable Auto-Reply"
    toggle_btn_data = "biz:set_enabled:0" if is_enabled else "biz:set_enabled:1"

    mode_btn_text = "Mode: 1️⃣ First-Time Only" if first_time_only else "Mode: ⏱️ Cooldown"
    next_mode_val = 0 if first_time_only else 1

    keyboard = [
        [
            InlineKeyboardButton(toggle_btn_text, callback_data=toggle_btn_data),
        ],
        [
            InlineKeyboardButton("✍️ Edit Message", callback_data="biz:edit_msg"),
            InlineKeyboardButton("👁️ Preview", callback_data="biz:preview"),
        ],
        [
            InlineKeyboardButton(mode_btn_text, callback_data=f"biz:set_first_time:{next_mode_val}"),
            InlineKeyboardButton("⏱️ Cooldown ▾", callback_data="biz:menu:cooldown"),
        ],
        [
            InlineKeyboardButton("⏳ Delay ▾", callback_data="biz:menu:delay"),
            InlineKeyboardButton("📊 Daily Limit ▾", callback_data="biz:menu:limit"),
        ],
        [
            InlineKeyboardButton("🚫 Excluded List", callback_data="biz:menu:excluded"),
            InlineKeyboardButton("🔄 Reset Message", callback_data="biz:menu:reset_msg"),
        ],
        [
            InlineKeyboardButton("📈 My Statistics", callback_data="biz:stats"),
            InlineKeyboardButton("ℹ️ How to Connect", callback_data="biz:guide"),
        ],
    ]

    return text, InlineKeyboardMarkup(keyboard)


# =============================================================================
# Telegram Business Event Handlers
# =============================================================================

async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle business_connection updates sent by Telegram when a user connects,
    disconnects, or modifies bot rights in Telegram Business Secretary Mode.
    """
    bc: BusinessConnection = update.business_connection
    if not bc:
        return

    user = bc.user
    user_id = user.id if user else bc.user_chat_id
    user_chat_id = bc.user_chat_id
    conn_id = bc.id
    is_enabled = bool(bc.is_enabled)
    can_reply = connection_can_reply(bc)
    username = user.username if user else None
    first_name = user.first_name if user else None

    # Persist connection state to database
    save_or_update_business_connection(
        connection_id=conn_id,
        user_id=user_id,
        user_chat_id=user_chat_id,
        is_enabled=is_enabled,
        can_reply=can_reply,
        account_username=username,
        account_first_name=first_name,
    )

    logger.info(
        "[BUSINESS CONNECTION UPDATE] Connection: %s | User: %s (ID: %d) | Enabled: %s | Can Reply: %s",
        conn_id,
        first_name,
        user_id,
        is_enabled,
        can_reply,
    )

    # Check settings for optional welcome notification
    settings = get_personal_reply_settings(user_id)
    if not settings.get("welcome_message_enabled", 1):
        return

    # Notify the user in their private chat
    if is_enabled:
        rights_badge = "✅ Reply permission granted" if can_reply else "⚠️ Missing 'Reply to messages' permission"
        msg = (
            "🎉 <b>Telegram Business Connected!</b>\n\n"
            f"Your personal account <b>{html.escape(first_name or 'Business')}</b> has connected "
            "Waguri in Secretary Mode.\n\n"
            f"• <b>Connection ID:</b> <code>{conn_id}</code>\n"
            f"• <b>Permission:</b> {rights_badge}\n\n"
            "By default, your auto-reply is set to reply to <b>first-time senders only</b>.\n\n"
            "Use /personal to configure your reply message, preview it, or adjust advanced settings."
        )
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Open Settings", callback_data="biz:main"),
                InlineKeyboardButton("👁️ Preview Reply", callback_data="biz:preview"),
            ]
        ]
        try:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.warning("[BUSINESS NOTIFY ERROR] Could not notify user %d: %s", user_id, exc)
    else:
        msg = (
            "⚠️ <b>Telegram Business Disconnected</b>\n\n"
            f"Your Telegram Business connection (<code>{conn_id}</code>) was disconnected or disabled.\n\n"
            "Auto-replies are paused. To resume, reconnect Waguri in Telegram Business Settings."
        )
        try:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text=msg,
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.warning("[BUSINESS NOTIFY ERROR] Could not notify user %d: %s", user_id, exc)


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle business_message updates. Dispatches personal auto-reply to incoming private
    messages for connected business accounts with first-time sender detection.
    """
    message: Message = update.business_message
    if not message or not message.business_connection_id:
        return

    conn_id = message.business_connection_id
    chat = message.chat
    sender = message.from_user

    # In a business chat, sender must exist
    if not sender:
        return

    # Never auto-reply to bots
    if sender.is_bot:
        return

    # Retrieve connection details
    conn = get_business_connection(conn_id)
    if not conn:
        # Fallback: Query Telegram directly to fetch connection if not yet saved
        try:
            tg_bc = await context.bot.get_business_connection(conn_id)
            if tg_bc:
                user = tg_bc.user
                u_id = user.id if user else tg_bc.user_chat_id
                save_or_update_business_connection(
                    connection_id=conn_id,
                    user_id=u_id,
                    user_chat_id=tg_bc.user_chat_id,
                    is_enabled=tg_bc.is_enabled,
                    can_reply=connection_can_reply(tg_bc),
                    account_username=user.username if user else None,
                    account_first_name=user.first_name if user else None,
                )
                conn = get_business_connection(conn_id)
        except Exception as exc:
            logger.warning("[BUSINESS CONNECTION LOOKUP FAILED] Connection %s: %s", conn_id, exc)

    if not conn:
        logger.debug("[BUSINESS MESSAGE IGNORED] Unknown connection ID: %s", conn_id)
        return

    # Check connection active status
    if not conn.get("is_enabled"):
        logger.debug("[BUSINESS MESSAGE IGNORED] Connection %s is disabled.", conn_id)
        return

    business_user_id = conn["user_id"]

    # CRITICAL: Never auto-reply if the message was sent by the business account owner!
    if sender.id == business_user_id:
        logger.debug(
            "[BUSINESS MESSAGE IGNORED] Message sent by account owner %d in chat %d.",
            business_user_id,
            chat.id,
        )
        return

    # Check can_reply permission
    if not conn.get("can_reply"):
        logger.warning(
            "[BUSINESS PERMISSION DENIED] Bot lacks can_reply right for connection %s (user %d)",
            conn_id,
            business_user_id,
        )
        return

    # Fetch user settings
    settings = get_personal_reply_settings(business_user_id)
    if not settings.get("is_enabled", 1):
        logger.debug("[BUSINESS MESSAGE IGNORED] User %d has auto-reply DISABLED.", business_user_id)
        return

    # Excluded users check
    if is_user_excluded(business_user_id, sender.id, sender.username):
        logger.info(
            "[BUSINESS EXCLUDED] Sender %s (ID: %d) is excluded by user %d.",
            sender.first_name,
            sender.id,
            business_user_id,
        )
        return

    # Daily reply limit check
    daily_limit = settings.get("daily_limit", 100)
    replies_today = get_daily_replies_count(business_user_id)
    if replies_today >= daily_limit:
        logger.warning(
            "[BUSINESS DAILY LIMIT REACHED] User %d reached daily limit (%d/%d).",
            business_user_id,
            replies_today,
            daily_limit,
        )
        return

    # First-time sender detection or Cooldown evaluation
    first_time_only = bool(settings.get("first_time_only", 1))
    if first_time_only:
        should_reply = check_and_claim_first_contact(
            business_user_id=business_user_id,
            sender_id=sender.id,
            sender_username=sender.username,
            sender_first_name=sender.first_name,
        )
        if not should_reply:
            logger.info(
                "[BUSINESS REPEAT SENDER] Repeat message from %s (ID: %d) to user %d - reply suppressed.",
                sender.first_name,
                sender.id,
                business_user_id,
            )
            return
    else:
        cooldown = settings.get("cooldown_seconds", 86400)
        should_reply = check_and_claim_cooldown_reply(
            business_user_id=business_user_id,
            sender_id=sender.id,
            cooldown_seconds=cooldown,
            sender_username=sender.username,
            sender_first_name=sender.first_name,
        )
        if not should_reply:
            logger.info(
                "[BUSINESS COOLDOWN ACTIVE] Cooldown active for sender %s (ID: %d) to user %d - reply suppressed.",
                sender.first_name,
                sender.id,
                business_user_id,
            )
            return

    # Optional reply delay configuration
    delay = settings.get("reply_delay_seconds", 0)
    if delay > 0:
        await asyncio.sleep(min(delay, 30))

    # Retrieve and render user-specific template
    raw_template = get_personal_reply_template(business_user_id)
    rendered_text = render_personal_template(raw_template, sender)

    # Parse mode
    parse_mode_str = settings.get("parse_mode", "HTML")
    pm = ParseMode.HTML if parse_mode_str == "HTML" else None

    # Send the automatic reply using business_connection_id
    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=rendered_text,
            business_connection_id=conn_id,
            parse_mode=pm,
        )
        log_business_reply(
            business_user_id=business_user_id,
            connection_id=conn_id,
            chat_id=chat.id,
            sender_id=sender.id,
            message_id=message.message_id,
            reply_text=rendered_text,
            status="success",
        )
        logger.info(
            "[BUSINESS AUTOREPLY DELIVERED] User: %d | Sender: %s (ID: %d) | Connection: %s",
            business_user_id,
            sender.first_name,
            sender.id,
            conn_id,
        )
    except BadRequest as b_err:
        # If parsing failed due to formatting in template, retry as plain text
        if "parse" in str(b_err).lower() or "entities" in str(b_err).lower():
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=rendered_text,
                    business_connection_id=conn_id,
                    parse_mode=None,
                )
                log_business_reply(
                    business_user_id=business_user_id,
                    connection_id=conn_id,
                    chat_id=chat.id,
                    sender_id=sender.id,
                    message_id=message.message_id,
                    reply_text=rendered_text,
                    status="success",
                )
                logger.info(
                    "[BUSINESS AUTOREPLY DELIVERED (PLAIN)] User: %d | Sender: %s (ID: %d) | Fallback",
                    business_user_id,
                    sender.first_name,
                    sender.id,
                )
                return
            except Exception as e2:
                log_business_reply(
                    business_user_id=business_user_id,
                    connection_id=conn_id,
                    chat_id=chat.id,
                    sender_id=sender.id,
                    message_id=message.message_id,
                    reply_text=rendered_text,
                    status="failed",
                    error_message=str(e2),
                )
                logger.error("[BUSINESS AUTOREPLY FALLBACK FAILED] %s", e2)
        else:
            log_business_reply(
                business_user_id=business_user_id,
                connection_id=conn_id,
                chat_id=chat.id,
                sender_id=sender.id,
                message_id=message.message_id,
                reply_text=rendered_text,
                status="failed",
                error_message=str(b_err),
            )
            logger.error("[BUSINESS AUTOREPLY BAD REQUEST] %s", b_err)
    except Forbidden as f_err:
        log_business_reply(
            business_user_id=business_user_id,
            connection_id=conn_id,
            chat_id=chat.id,
            sender_id=sender.id,
            message_id=message.message_id,
            reply_text=rendered_text,
            status="failed",
            error_message=str(f_err),
        )
        logger.warning("[BUSINESS AUTOREPLY FORBIDDEN] %s", f_err)
    except Exception as exc:
        log_business_reply(
            business_user_id=business_user_id,
            connection_id=conn_id,
            chat_id=chat.id,
            sender_id=sender.id,
            message_id=message.message_id,
            reply_text=rendered_text,
            status="failed",
            error_message=str(exc),
        )
        logger.error("[BUSINESS AUTOREPLY UNEXPECTED ERROR] %s", exc)


async def handle_edited_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edited_business_message updates. Edits do not trigger new auto-replies."""
    msg: Message = update.edited_business_message
    if not msg:
        return
    logger.debug(
        "[BUSINESS MESSAGE EDITED] Chat: %d | Msg: %d | Connection: %s",
        msg.chat.id,
        msg.message_id,
        msg.business_connection_id,
    )


async def handle_deleted_business_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle deleted_business_messages updates safely without crashing."""
    del_msgs = update.deleted_business_messages
    if not del_msgs:
        return
    logger.debug(
        "[BUSINESS MESSAGES DELETED] Chat: %d | Count: %d | Connection: %s",
        del_msgs.chat.id,
        len(del_msgs.message_ids),
        del_msgs.business_connection_id,
    )


# =============================================================================
# User Dashboard & Commands
# =============================================================================

async def personal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /personal command to open the personal auto-reply dashboard."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    # In groups/supergroups, redirect user to private chat for privacy
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username or "Ms_Waguri_bot"
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⚙️ Open Personal Dashboard (PM)",
                        url=f"https://t.me/{bot_username}?start=personal",
                    )
                ]
            ]
        )
        await message.reply_text(
            "🔒 <b>Personal Auto-Reply Dashboard</b>\n\n"
            "To protect your privacy and settings, please configure your Personal Auto-Reply in private chat.",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )
        return

    # In private chat, display the interactive settings dashboard
    text, markup = build_personal_settings_markup(user.id)
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def autoreply_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /autoreply_on command."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    update_personal_reply_settings(user.id, is_enabled=1)
    conn = get_active_business_connection_for_user(user.id)

    if conn and conn.get("is_enabled"):
        await message.reply_text(
            "🟢 <b>Personal Auto-Reply has been ENABLED!</b>\n\n"
            "Incoming first-time senders will automatically receive your saved message.\n\n"
            "Use /preview to check your reply or /personal to adjust settings.",
            parse_mode=ParseMode.HTML,
        )
    else:
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username or "Ms_Waguri_bot"
        await message.reply_text(
            "🟢 <b>Personal Auto-Reply ENABLED</b>\n\n"
            "⚠️ <i>Your Telegram Business account is not connected yet!</i>\n\n"
            "<b>To connect:</b>\n"
            f"1. Open Telegram Settings → <b>Telegram Business</b> → <b>Chatbots</b>\n"
            f"2. Add <b>@{bot_username}</b> and enable <i>Reply to messages</i>\n\n"
            "Once connected, auto-replies will start functioning immediately.",
            parse_mode=ParseMode.HTML,
        )


async def autoreply_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /autoreply_off command."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    update_personal_reply_settings(user.id, is_enabled=0)
    await message.reply_text(
        "🔴 <b>Personal Auto-Reply has been DISABLED.</b>\n\n"
        "No automatic replies will be sent to incoming senders.\n\n"
        "Use /autoreply_on or /personal to re-enable at any time.",
        parse_mode=ParseMode.HTML,
    )


async def setmessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /setmessage command to write and save a custom auto-reply."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    # Check if text was passed as command arguments
    raw_args = ""
    if context.args:
        raw_args = " ".join(context.args).strip()
    elif message.text:
        parts = message.text.split(None, 1)
        if len(parts) > 1:
            raw_args = parts[1].strip()

    if raw_args:
        # Validate formatting by test rendering
        dummy_sender = User(id=1, first_name="Alex", is_bot=False, last_name="Taylor", username="alextaylor")
        rendered = render_personal_template(raw_args, dummy_sender)

        # Save to database
        set_personal_reply_template(user.id, raw_args)

        # Clear any pending prompt state
        context.user_data.pop("awaiting_personal_reply_msg", None)

        preview_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("👁️ Preview Full Reply", callback_data="biz:preview"),
                    InlineKeyboardButton("⚙️ Open Settings", callback_data="biz:main"),
                ]
            ]
        )
        await message.reply_text(
            "✅ <b>Personal Auto-Reply Message Saved!</b>\n\n"
            "<b>Your new message:</b>\n"
            f"<blockquote>{html.escape(raw_args)}</blockquote>\n\n"
            "Use /preview to view how incoming contacts will see it.",
            reply_markup=preview_markup,
            parse_mode=ParseMode.HTML,
        )
        return

    # Prompt user for input
    context.user_data["awaiting_personal_reply_msg"] = True
    await message.reply_text(
        "✍️ <b>Set Your Personal Auto-Reply Message</b>\n\n"
        "Please send your message now, or run:\n"
        "<code>/setmessage &lt;your message text&gt;</code>\n\n"
        "<b>Available Dynamic Variables:</b>\n"
        "• <code>{first_name}</code> - Sender's first name\n"
        "• <code>{last_name}</code> - Sender's last name\n"
        "• <code>{full_name}</code> - Sender's full name\n"
        "• <code>{username}</code> - Sender's @username\n"
        "• <code>{time}</code> - Time sent (HH:MM UTC)\n"
        "• <code>{date}</code> - Date sent (YYYY-MM-DD)\n\n"
        "<i>HTML tags (<b>bold</b>, <i>italic</i>, <code>code</code>, <a href='...'>links</a>) are supported.</i>",
        parse_mode=ParseMode.HTML,
    )


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /preview command to preview the saved auto-reply message."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    template = get_personal_reply_template(user.id)
    dummy_sender = User(id=999888, first_name="Alex", is_bot=False, last_name="Taylor", username="alextaylor")
    rendered = render_personal_template(template, dummy_sender)

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✍️ Edit Message", callback_data="biz:edit_msg"),
                InlineKeyboardButton("⚙️ Settings", callback_data="biz:main"),
            ]
        ]
    )

    text = (
        "👁️ <b>Auto-Reply Message Preview</b>\n\n"
        "Here is what an incoming sender (e.g. Alex Taylor) will receive:\n\n"
        "──────────────────────\n"
        f"{rendered}\n"
        "──────────────────────\n\n"
        "<b>Raw Saved Template:</b>\n"
        f"<code>{html.escape(template)}</code>"
    )

    try:
        await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception:
        # Fallback without HTML rendering if custom template contains invalid entities
        fallback_text = (
            "👁️ <b>Auto-Reply Message Preview</b>\n\n"
            "──────────────────────\n"
            f"{html.escape(rendered)}\n"
            "──────────────────────"
        )
        await message.reply_text(fallback_text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def mystatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /mystatus command to display connection and auto-reply status."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    conn = get_active_business_connection_for_user(user.id)
    settings = get_personal_reply_settings(user.id)
    stats = get_user_business_stats(user.id)

    is_enabled = bool(settings.get("is_enabled", 1))
    first_time_only = bool(settings.get("first_time_only", 1))
    daily_limit = settings.get("daily_limit", 100)
    cooldown = settings.get("cooldown_seconds", 86400)

    if conn:
        conn_status = "🟢 Connected & Active" if conn.get("is_enabled") else "🔴 Disconnected"
        can_reply_status = "✅ Granted" if conn.get("can_reply") else "⚠️ Revoked / Missing"
        conn_id = conn.get("connection_id")
        acct_str = html.escape(conn.get("account_first_name") or "Your Account")
        if conn.get("account_username"):
            acct_str += f" (@{conn.get('account_username')})"
    else:
        conn_status = "⚪ Not Connected"
        can_reply_status = "—"
        conn_id = "None"
        acct_str = "None"

    text = (
        "📊 <b>Personal Auto-Reply Status Report</b>\n\n"
        f"<b>User:</b> {html.escape(user.first_name)} (ID: <code>{user.id}</code>)\n"
        f"<b>Business Account:</b> {acct_str}\n"
        f"<b>Connection ID:</b> <code>{conn_id}</code>\n"
        f"<b>Connection Status:</b> {conn_status}\n"
        f"<b>Reply Rights:</b> {can_reply_status}\n\n"
        "⚡ <b>Configuration:</b>\n"
        f"• Auto-Reply: <b>{'🟢 ENABLED' if is_enabled else '🔴 DISABLED'}</b>\n"
        f"• Filter Mode: <b>{'1️⃣ First-time Senders Only' if first_time_only else f'⏱️ Cooldown ({format_cooldown_label(cooldown)})'}</b>\n"
        f"• Daily Limit: <b>{daily_limit} replies</b>\n\n"
        "📈 <b>Delivery Statistics:</b>\n"
        f"• Unique Senders Tracked: <b>{stats.get('total_contacts', 0)}</b>\n"
        f"• Replies Sent Today: <b>{stats.get('replies_today', 0)} / {daily_limit}</b>\n"
        f"• All-Time Deliveries: <b>{stats.get('total_replies_all_time', 0)}</b>\n"
        f"• Failed Deliveries: <b>{stats.get('total_failed_replies', 0)}</b>"
    )

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔴 Disable" if is_enabled else "🟢 Enable",
                    callback_data=f"biz:set_enabled:{0 if is_enabled else 1}",
                ),
                InlineKeyboardButton("⚙️ Full Dashboard", callback_data="biz:main"),
            ],
            [
                InlineKeyboardButton("👁️ Preview Message", callback_data="biz:preview"),
            ],
        ]
    )

    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def resetmessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /resetmessage command to restore the default auto-reply template."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    reset_personal_reply_template(user.id)
    await message.reply_text(
        "🔄 <b>Auto-Reply Message Reset</b>\n\n"
        "Your reply message has been reset to the default template:\n\n"
        f"<blockquote>{html.escape(DEFAULT_PERSONAL_REPLY_TEMPLATE)}</blockquote>\n\n"
        "Use /preview to check it or /setmessage to customize.",
        parse_mode=ParseMode.HTML,
    )


async def exclude_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /exclude_user <id_or_username> to prevent auto-replying to specific people."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    target = " ".join(context.args).strip() if context.args else ""
    if not target:
        excluded = get_excluded_users_list(user.id)
        if not excluded:
            await message.reply_text(
                "ℹ️ <b>Excluded List</b>\n\n"
                "No users or usernames are currently excluded.\n\n"
                "To exclude someone from receiving auto-replies, send:\n"
                "<code>/exclude_user &lt;user_id or @username&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            items = "\n".join([f"• <code>{x}</code>" for x in excluded])
            await message.reply_text(
                f"🚫 <b>Excluded Users ({len(excluded)}):</b>\n\n{items}\n\n"
                "To exclude another: <code>/exclude_user &lt;id|@username&gt;</code>\n"
                "To remove an exclusion: <code>/include_user &lt;id|@username&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    updated_list = add_excluded_user(user.id, target)
    await message.reply_text(
        f"🚫 <b>Excluded:</b> <code>{html.escape(target)}</code>\n\n"
        "This sender will not receive automatic replies from your account.\n\n"
        f"Total excluded: {len(updated_list)}",
        parse_mode=ParseMode.HTML,
    )


async def include_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /include_user <id_or_username> to re-allow auto-replies for someone."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    target = " ".join(context.args).strip() if context.args else ""
    if not target:
        await message.reply_text(
            "<b>Usage:</b> <code>/include_user &lt;user_id or @username&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    updated_list = remove_excluded_user(user.id, target)
    await message.reply_text(
        f"✅ <b>Removed from exclusion:</b> <code>{html.escape(target)}</code>\n\n"
        f"Remaining excluded senders: {len(updated_list)}",
        parse_mode=ParseMode.HTML,
    )


async def business_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot Owner Command: /business_stats to view global platform-wide statistics."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_bot_owner(user.id):
        return

    stats = get_global_business_stats()
    text = (
        "💼 <b>Global Business Auto-Reply Statistics</b>\n\n"
        f"• Connected Users: <b>{stats['total_connected_users']}</b>\n"
        f"• Active Business Connections: <b>{stats['total_active_connections']}</b>\n"
        f"• Senders Tracked: <b>{stats['total_contacts_tracked']}</b>\n"
        f"• Successful Auto-Replies Delivered: <b>{stats['total_replies_delivered']}</b>"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


# =============================================================================
# Private Text Message Listener (Interactive Prompt Capture)
# =============================================================================

async def handle_private_reply_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Capture custom auto-reply text sent by the user in private chat
    when they are in 'awaiting_personal_reply_msg' state.
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user or chat.type != ChatType.PRIVATE:
        return

    if not context.user_data.get("awaiting_personal_reply_msg"):
        return

    text = message.text or message.caption
    if not text:
        return

    # Clear state
    context.user_data["awaiting_personal_reply_msg"] = False

    # Save new template
    set_personal_reply_template(user.id, text)

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👁️ Preview Reply", callback_data="biz:preview"),
                InlineKeyboardButton("⚙️ Open Settings", callback_data="biz:main"),
            ]
        ]
    )

    await message.reply_text(
        "✅ <b>Custom Auto-Reply Saved!</b>\n\n"
        "<b>Saved Message:</b>\n"
        f"<blockquote>{html.escape(text)}</blockquote>\n\n"
        "Use /preview to view how incoming senders will see it.",
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


# =============================================================================
# Interactive Callback Query Handler (biz:*)
# =============================================================================

async def personal_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks for personal auto-reply configuration."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    data = query.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    # 1. Main Dashboard
    if action == "main":
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    # 2. Toggle Auto-Reply (Enable/Disable)
    elif action == "set_enabled":
        val = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        update_personal_reply_settings(user.id, is_enabled=val)
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer("Auto-reply enabled!" if val else "Auto-reply disabled!")
        return

    # 3. Toggle Mode (First-Time Only vs Cooldown)
    elif action == "set_first_time":
        val = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        update_personal_reply_settings(user.id, first_time_only=val)
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer("Set to First-Time Only mode!" if val else "Set to Cooldown mode!")
        return

    # 4. Preview Message
    elif action == "preview":
        template = get_personal_reply_template(user.id)
        dummy_sender = User(id=999888, first_name="Alex", is_bot=False, last_name="Taylor", username="alextaylor")
        rendered = render_personal_template(template, dummy_sender)

        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✍️ Edit Message", callback_data="biz:edit_msg"),
                    InlineKeyboardButton("🔙 Back", callback_data="biz:main"),
                ]
            ]
        )
        text = (
            "👁️ <b>Auto-Reply Message Preview</b>\n\n"
            "Here is what an incoming sender (e.g. Alex Taylor) will receive:\n\n"
            "──────────────────────\n"
            f"{rendered}\n"
            "──────────────────────\n\n"
            "<b>Raw Saved Template:</b>\n"
            f"<code>{html.escape(template)}</code>"
        )
        try:
            await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        except Exception:
            fallback = (
                "👁️ <b>Auto-Reply Message Preview</b>\n\n"
                "──────────────────────\n"
                f"{html.escape(rendered)}\n"
                "──────────────────────"
            )
            await query.edit_message_text(fallback, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    # 5. Prompt Edit Message
    elif action == "edit_msg":
        context.user_data["awaiting_personal_reply_msg"] = True
        cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="biz:main")]])
        await query.edit_message_text(
            "✍️ <b>Edit Your Auto-Reply Message</b>\n\n"
            "Please type and send your reply message in this chat, or send:\n"
            "<code>/setmessage &lt;your message&gt;</code>\n\n"
            "<b>Dynamic Variables Available:</b>\n"
            "• <code>{first_name}</code> - Sender's first name\n"
            "• <code>{last_name}</code> - Sender's last name\n"
            "• <code>{full_name}</code> - Sender's full name\n"
            "• <code>{username}</code> - Sender's @username\n"
            "• <code>{time}</code> - Time sent (HH:MM UTC)\n"
            "• <code>{date}</code> - Date sent (YYYY-MM-DD)\n\n"
            "<i>HTML formatting is supported.</i>",
            reply_markup=cancel_markup,
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    # 6. Cooldown Submenu
    elif action == "menu" and len(parts) > 2 and parts[2] == "cooldown":
        settings = get_personal_reply_settings(user.id)
        current_cd = settings.get("cooldown_seconds", 86400)
        options = [
            ("1 Hour", 3600),
            ("6 Hours", 21600),
            ("12 Hours", 43200),
            ("24 Hours", 86400),
            ("48 Hours", 172800),
        ]
        buttons = []
        for label, sec in options:
            badge = " ✅" if current_cd == sec else ""
            buttons.append([InlineKeyboardButton(f"{label}{badge}", callback_data=f"biz:set_cd:{sec}")])
        buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="biz:main")])
        await query.edit_message_text(
            "⏱️ <b>Select Cooldown Period</b>\n\n"
            "When 'First-Time Only' mode is disabled, cooldown controls how frequently "
            "the same sender can receive an automatic reply.\n\n"
            f"Current cooldown: <b>{format_cooldown_label(current_cd)}</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    # 7. Set Cooldown Value
    elif action == "set_cd" and len(parts) > 2:
        sec = int(parts[2]) if parts[2].isdigit() else 86400
        # Automatically disable first_time_only when setting explicit cooldown
        update_personal_reply_settings(user.id, cooldown_seconds=sec, first_time_only=0)
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Cooldown updated to {format_cooldown_label(sec)}!")
        return

    # 8. Reply Delay Submenu
    elif action == "menu" and len(parts) > 2 and parts[2] == "delay":
        settings = get_personal_reply_settings(user.id)
        current_delay = settings.get("reply_delay_seconds", 0)
        delays = [0, 2, 5, 10, 15]
        buttons = []
        for d in delays:
            badge = " ✅" if current_delay == d else ""
            lbl = "Instant (0s)" if d == 0 else f"{d} seconds"
            buttons.append([InlineKeyboardButton(f"{lbl}{badge}", callback_data=f"biz:set_delay:{d}")])
        buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="biz:main")])
        await query.edit_message_text(
            "⏳ <b>Configure Reply Delay</b>\n\n"
            "Add a brief delay before sending the automatic reply to look natural.\n\n"
            f"Current delay: <b>{current_delay}s</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    # 9. Set Delay Value
    elif action == "set_delay" and len(parts) > 2:
        sec = int(parts[2]) if parts[2].isdigit() else 0
        update_personal_reply_settings(user.id, reply_delay_seconds=sec)
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Reply delay set to {sec}s!")
        return

    # 10. Daily Limit Submenu
    elif action == "menu" and len(parts) > 2 and parts[2] == "limit":
        settings = get_personal_reply_settings(user.id)
        current_limit = settings.get("daily_limit", 100)
        limits = [25, 50, 100, 250, 500]
        buttons = []
        for lmt in limits:
            badge = " ✅" if current_limit == lmt else ""
            buttons.append([InlineKeyboardButton(f"{lmt} replies/day{badge}", callback_data=f"biz:set_limit:{lmt}")])
        buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="biz:main")])
        await query.edit_message_text(
            "📊 <b>Configure Per-User Daily Reply Limit</b>\n\n"
            "Prevents runaway message loops or rate limits.\n\n"
            f"Current limit: <b>{current_limit} replies / 24h</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    # 11. Set Limit Value
    elif action == "set_limit" and len(parts) > 2:
        lmt = int(parts[2]) if parts[2].isdigit() else 100
        update_personal_reply_settings(user.id, daily_limit=lmt)
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Daily limit updated to {lmt}!")
        return

    # 12. Excluded Users Submenu
    elif action == "menu" and len(parts) > 2 and parts[2] == "excluded":
        excluded = get_excluded_users_list(user.id)
        if excluded:
            items = "\n".join([f"• <code>{x}</code>" for x in excluded])
            body = f"<b>Currently Excluded Senders ({len(excluded)}):</b>\n\n{items}"
        else:
            body = "<i>No senders are currently excluded.</i>"

        text = (
            "🚫 <b>Excluded Senders & Chats</b>\n\n"
            f"{body}\n\n"
            "To exclude someone, send:\n"
            "<code>/exclude_user &lt;id_or_@username&gt;</code>\n\n"
            "To remove an exclusion, send:\n"
            "<code>/include_user &lt;id_or_@username&gt;</code>"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="biz:main")]])
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    # 13. Reset Message Confirmation
    elif action == "menu" and len(parts) > 2 and parts[2] == "reset_msg":
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⚠️ Yes, Reset to Default", callback_data="biz:confirm_reset"),
                    InlineKeyboardButton("🔙 Cancel", callback_data="biz:main"),
                ]
            ]
        )
        await query.edit_message_text(
            "🔄 <b>Confirm Reset Message</b>\n\n"
            "Are you sure you want to reset your auto-reply back to the standard default message?\n\n"
            f"<b>Default Message:</b>\n<blockquote>{html.escape(DEFAULT_PERSONAL_REPLY_TEMPLATE)}</blockquote>",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    # 14. Confirm Reset
    elif action == "confirm_reset":
        reset_personal_reply_template(user.id)
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer("Reply message reset to default!")
        return

    # 15. Statistics View
    elif action == "stats":
        stats = get_user_business_stats(user.id)
        conn = get_active_business_connection_for_user(user.id)
        settings = get_personal_reply_settings(user.id)

        conn_status = "🟢 Connected" if (conn and conn.get("is_enabled")) else "⚪ Inactive"

        text = (
            "📈 <b>My Auto-Reply Statistics</b>\n\n"
            f"<b>Connection Status:</b> {conn_status}\n"
            f"<b>Auto-Reply:</b> {'🟢 Enabled' if settings.get('is_enabled', 1) else '🔴 Disabled'}\n"
            f"• Senders Tracked: <b>{stats.get('total_contacts', 0)}</b>\n"
            f"• Replies Sent Today: <b>{stats.get('replies_today', 0)} / {settings.get('daily_limit', 100)}</b>\n"
            f"• All-Time Deliveries: <b>{stats.get('total_replies_all_time', 0)}</b>\n"
            f"• Failed Deliveries: <b>{stats.get('total_failed_replies', 0)}</b>"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="biz:main")]])
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    # 16. How to Connect Guide
    elif action == "guide":
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username or "Ms_Waguri_bot"
        text = (
            "ℹ️ <b>How to Connect Telegram Business Mode</b>\n\n"
            "Follow these steps to connect your Telegram account:\n\n"
            "1. Open <b>Telegram Settings</b>.\n"
            "2. Navigate to <b>Telegram Business</b> (requires Telegram Business / Premium).\n"
            "3. Tap on <b>Chatbots</b> (or <b>Business Bots</b>).\n"
            f"4. Search for and select <b>@{bot_username}</b>.\n"
            "5. Turn on <b>'Reply to messages'</b> permission.\n"
            "6. Tap <b>Save / Done</b>.\n\n"
            "Telegram will immediately connect your account in Secretary Mode and Waguri will handle "
            "incoming private messages automatically!"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="biz:main")]])
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return


# =============================================================================
# Handler Registration
# =============================================================================

def register_personal_autoreply_handlers(application: Application) -> None:
    """Register all Telegram Business and Personal Auto-Reply handlers."""
    # 1. Telegram Business Connection updates
    application.add_handler(BusinessConnectionHandler(handle_business_connection))

    # 2. Telegram Business Message updates
    application.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message))

    # 3. Edited & Deleted Business Message updates
    application.add_handler(
        MessageHandler(filters.UpdateType.EDITED_BUSINESS_MESSAGE, handle_edited_business_message)
    )
    application.add_handler(BusinessMessagesDeletedHandler(handle_deleted_business_messages))

    # 4. User Dashboard & Configuration Commands (Group 0)
    application.add_handler(CommandHandler("personal", personal_command), group=0)
    application.add_handler(CommandHandler("autoreply_on", autoreply_on_command), group=0)
    application.add_handler(CommandHandler("autoreply_off", autoreply_off_command), group=0)
    application.add_handler(CommandHandler("setmessage", setmessage_command), group=0)
    application.add_handler(CommandHandler("preview", preview_command), group=0)
    application.add_handler(CommandHandler("mystatus", mystatus_command), group=0)
    application.add_handler(CommandHandler("resetmessage", resetmessage_command), group=0)
    application.add_handler(CommandHandler("exclude_user", exclude_user_command), group=0)
    application.add_handler(CommandHandler("include_user", include_user_command), group=0)
    application.add_handler(CommandHandler("business_stats", business_stats_command), group=0)

    # 5. Interactive Callback Handler for Personal Dashboard (biz:*)
    application.add_handler(CallbackQueryHandler(personal_callback_handler, pattern=r"^biz:"), group=0)

    # 6. Private text message listener for interactive reply message typing
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & (~filters.COMMAND),
            handle_private_reply_message_input,
        ),
        group=0,
    )
