import html
import logging
import re
from telegram import Message, Update, User
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from database import (
    get_group_greeting_enabled,
    get_group_greeting_message,
    set_group_greeting_message,
)
from handlers.admin_check import is_sender_admin_or_owner
from handlers.anti_link import detect_link

logger = logging.getLogger("Waguri.Greetings")

# Regex to detect greeting messages: "Hii", "hy", "hyy", "hello", "hlw", "hi", "hey", etc.
GREETING_PATTERN = re.compile(
    r"^\s*(?:hi+|hy+|he+y+|hlw|hlo|he+l+o+)(?:\s+(?:all|everyone|waguri|bot|guys|there))?[!.,?\s\U00010000-\U0010ffff\u2600-\u27bf]*$",
    re.IGNORECASE,
)


def is_greeting(text: str | None) -> bool:
    """Determine whether the message text matches a greeting (Hii, hy, hyy, hello, hlw, hi, hey, etc.)."""
    if not text:
        return False
    return bool(GREETING_PATTERN.match(text))


def get_user_display_name(update: Update) -> str:
    """Extract the best display name for the user."""
    user = update.effective_user
    if user and getattr(user, "first_name", None) and isinstance(user.first_name, str):
        return user.first_name
    if user and getattr(user, "username", None) and isinstance(user.username, str):
        return user.username
    message = update.effective_message
    if message and isinstance(getattr(message, "author_signature", None), str) and message.author_signature:
        return message.author_signature
    if message and getattr(message, "sender_chat", None) and isinstance(getattr(message.sender_chat, "title", None), str):
        return message.sender_chat.title
    return "there"


def render_group_greeting_template(template: str, user: User | None, user_name: str, chat_title: str) -> str:
    """Render custom GC greeting template variables."""
    first_name = user.first_name if user and user.first_name else user_name
    last_name = user.last_name if user and user.last_name else ""
    username = f"@{user.username}" if user and user.username else user_name

    rendered = template
    replacements = {
        "{user}": user_name,
        "{first_name}": first_name,
        "{last_name}": last_name,
        "{username}": username,
        "{chat}": chat_title,
        "{title}": chat_title,
    }
    for placeholder, val in replacements.items():
        rendered = rendered.replace(placeholder, val)
    return rendered


async def _send_greeting_reply(
    message: Message, chat, user: User | None, user_name: str, source_label: str, extra_detail: str = ""
) -> None:
    """Consolidated helper to format, dispatch, and log group chat greeting replies."""
    chat_title = chat.title or "Group"

    # Check if group greetings are enabled
    if not get_group_greeting_enabled(chat.id):
        logger.debug("[%s] Greetings disabled in group '%s' (ID: %s).", source_label, chat_title, chat.id)
        return

    # Check if a custom greeting message is configured by the group admin
    custom_tpl = get_group_greeting_message(chat.id)
    if custom_tpl:
        greeting_text = render_group_greeting_template(custom_tpl, user, user_name, chat_title)
    else:
        greeting_text = f"Hii {user_name}"

    detail_str = f" | {extra_detail}" if extra_detail else ""
    logger.info(
        "[%s] Group: '%s' (ID: %s) | User: %s%s | Action: Sent '%s'",
        source_label,
        chat_title,
        chat.id,
        user_name,
        detail_str,
        greeting_text,
    )
    try:
        await message.reply_text(greeting_text)
    except Exception as exc:
        logger.error(
            "[%s ERROR] Failed to send greeting in '%s' (ID: %s): %s",
            source_label,
            chat_title,
            chat.id,
            exc,
        )


async def handle_greeting_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Respond to users who send greetings in group chats like 'Hii', 'hy', 'hyy', 'hello', 'hlw', 'hi', or 'hey'.
    Strictly restricted to Group and Supergroup chats. Personal chats are handled separately.
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat:
        return

    # Strictly for Group Chats only - separate from Personal / DM
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Skip if message contains a link (handled by anti-link moderation)
    if detect_link(message)[0]:
        return

    text = message.text or message.caption
    if not is_greeting(text):
        return

    user_name = get_user_display_name(update)
    await _send_greeting_reply(message, chat, user, user_name, "GREETING", f"Text: '{text.strip()}'")


async def greeting_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle greeting commands like /hello, /hi, /hlw, /hii."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat:
        return

    # In private chat, send friendly bot greeting
    if chat.type == ChatType.PRIVATE:
        await message.reply_text(
            "👋 <b>Hello!</b> I am Waguri, your Telegram moderation and management assistant.\n\n"
            "• Use /help to explore all features and commands\n"
            "• Use /personal to configure your personal auto-reply secretary",
            parse_mode=ParseMode.HTML,
        )
        return

    # In groups/supergroups, send group greeting
    user_name = get_user_display_name(update)
    await _send_greeting_reply(message, chat, user, user_name, "GREETING COMMAND")


# =============================================================================
# GC Messaging Configuration Commands (Strictly Admin Only)
# =============================================================================

async def setgcmsg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /setgcmsg <text> to set custom GC greeting/reply message.
    Strictly restricted to group administrators. Regular users receive zero access.
    """
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
        await message.reply_text(
            "❌ <b>Access Denied</b>: Only group administrators can edit GC messaging. Regular members do not have access to configure group messages.",
            parse_mode=ParseMode.HTML,
        )
        return

    raw_args = ""
    if context.args:
        raw_args = " ".join(context.args).strip()
    elif message.text:
        parts = message.text.split(None, 1)
        if len(parts) > 1:
            raw_args = parts[1].strip()

    if not raw_args:
        current = get_group_greeting_message(chat.id)
        current_disp = f"<blockquote>{html.escape(current)}</blockquote>" if current else "<i>Default (Hii {user})</i>"
        await message.reply_text(
            "✍️ <b>Set Group Greeting / Reply Message</b>\n\n"
            f"<b>Current GC Message:</b>\n{current_disp}\n\n"
            "<b>Usage:</b> <code>/setgcmsg &lt;your greeting message&gt;</code>\n\n"
            "<b>Supported Placeholders:</b>\n"
            "• <code>{user}</code> or <code>{first_name}</code> - Sender's name\n"
            "• <code>{last_name}</code> - Sender's last name\n"
            "• <code>{username}</code> - Sender's @username\n"
            "• <code>{chat}</code> - Group name\n\n"
            "<i>Example:</i> <code>/setgcmsg Welcome {user} to {chat}! Have a great time!</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    set_group_greeting_message(chat.id, raw_args)
    await message.reply_text(
        "✅ <b>GC Reply Message Updated!</b>\n\n"
        f"<b>New Group Reply Message:</b>\n<blockquote>{html.escape(raw_args)}</blockquote>\n\n"
        "Waguri will now use this reply for greetings in this group.",
        parse_mode=ParseMode.HTML,
    )


async def resetgcmsg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /resetgcmsg to restore default group greeting (Hii {user}).
    Strictly restricted to group administrators.
    """
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
        await message.reply_text(
            "❌ <b>Access Denied</b>: Only group administrators can edit GC messaging.",
            parse_mode=ParseMode.HTML,
        )
        return

    set_group_greeting_message(chat.id, None)
    await message.reply_text(
        "🔄 <b>GC Reply Message Reset</b>\n\n"
        "Group greeting message has been reset to default (<code>Hii {user}</code>).",
        parse_mode=ParseMode.HTML,
    )


async def gcmsg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /gcmsg to view current GC reply message.
    Strictly restricted to group administrators.
    """
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
        await message.reply_text(
            "❌ <b>Access Denied</b>: Only group administrators can view or edit GC messaging settings.",
            parse_mode=ParseMode.HTML,
        )
        return

    current = get_group_greeting_message(chat.id)
    if current:
        msg_text = f"<blockquote>{html.escape(current)}</blockquote>"
    else:
        msg_text = "<i>Default: Hii {user}</i>"

    await message.reply_text(
        "👥 <b>Group Chat (GC) Messaging Status</b>\n\n"
        f"<b>Current Greeting Reply:</b>\n{msg_text}\n\n"
        "<b>Admin Management Commands:</b>\n"
        "• <code>/setgcmsg &lt;text&gt;</code> - Edit GC greeting message\n"
        "• <code>/resetgcmsg</code> - Reset GC message to default\n\n"
        "<i>Regular group members cannot edit or change GC messaging.</i>",
        parse_mode=ParseMode.HTML,
    )


def register_greeting_handlers(application: Application) -> None:
    """Register greeting command handlers, admin GC message controls, and message filters."""
    # Greeting commands (/hello, /hi, /hii, /hlw, /hy, /hyy, /hey) registered in group 0
    application.add_handler(
        CommandHandler(["hello", "hi", "hii", "hlw", "hy", "hyy", "hey"], greeting_command),
        group=0,
    )

    # GC Admin Commands (Group Chat message management)
    application.add_handler(CommandHandler(["setgcmsg", "setgc"], setgcmsg_command), group=0)
    application.add_handler(CommandHandler(["resetgcmsg", "resetgc"], resetgcmsg_command), group=0)
    application.add_handler(CommandHandler("gcmsg", gcmsg_command), group=0)

    # Greeting message listener registered in group 3 (strictly group/supergroup)
    application.add_handler(
        MessageHandler(
            (filters.ChatType.GROUPS) & filters.TEXT & (~filters.COMMAND),
            handle_greeting_message,
        ),
        group=3,
    )
