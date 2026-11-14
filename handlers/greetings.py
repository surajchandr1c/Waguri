import logging
import re
from telegram import Message, Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
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


async def handle_greeting_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Respond to users who send greetings like 'Hii', 'hy', 'hyy', 'hello', 'hlw', 'hi', or 'hey' with:
    'Hii {user name}'
    Active in any channel, group, supergroup, or chat where Waguri is present.
    """
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # Skip if message contains a link (handled by anti-link moderation)
    if detect_link(message)[0]:
        return

    text = message.text or message.caption
    if not is_greeting(text):
        return

    user_name = get_user_display_name(update)
    greeting_text = f"Hii {user_name}"

    chat_title = chat.title or "Chat"
    logger.info(
        "[GREETING] Group/Channel: '%s' (ID: %s) | User: %s | Text: '%s' | Action: Sent '%s'",
        chat_title,
        chat.id,
        user_name,
        text.strip(),
        greeting_text,
    )

    try:
        await message.reply_text(greeting_text)
    except Exception as exc:
        logger.error(
            "[GREETING ERROR] Failed to send greeting message in '%s' (ID: %s): %s",
            chat_title,
            chat.id,
            exc,
        )


async def greeting_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle greeting commands like /hello, /hi, /hlw, /hii."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    user_name = get_user_display_name(update)
    greeting_text = f"Hii {user_name}"

    chat_title = chat.title or "Chat"
    logger.info(
        "[GREETING COMMAND] Group/Channel: '%s' (ID: %s) | User: %s | Action: Sent '%s'",
        chat_title,
        chat.id,
        user_name,
        greeting_text,
    )

    try:
        await message.reply_text(greeting_text)
    except Exception as exc:
        logger.error(
            "[GREETING COMMAND ERROR] Failed to send reply in '%s' (ID: %s): %s",
            chat_title,
            chat.id,
            exc,
        )


def register_greeting_handlers(application: Application) -> None:
    """Register greeting command handlers and message filters."""
    # Greeting commands (/hello, /hi, /hii, /hlw, /hy, /hyy, /hey) registered in group 0
    application.add_handler(
        CommandHandler(["hello", "hi", "hii", "hlw", "hy", "hyy", "hey"], greeting_command),
        group=0,
    )

    # Greeting message listener registered in group 3
    application.add_handler(
        MessageHandler(
            filters.TEXT & (~filters.COMMAND),
            handle_greeting_message,
        ),
        group=3,
    )
