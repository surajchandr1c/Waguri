import html
import logging
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger("Waguri.Greetings")


def is_greeting(text: str | None) -> bool:
    """Legacy helper retained for backward compatibility."""
    return False


async def greeting_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle explicit greeting commands like /hello, /hi, /hlw, /hii."""
    message = update.effective_message
    if not message:
        return

    await message.reply_text(
        "👋 <b>Hello!</b> I am Waguri, your Telegram moderation and management assistant.\n\n"
        "• Use /help to explore all available features and commands.",
        parse_mode=ParseMode.HTML,
    )


def register_greeting_handlers(application: Application) -> None:
    """Register explicit greeting command handlers."""
    application.add_handler(
        CommandHandler(["hello", "hi", "hii", "hlw", "hy", "hyy", "hey"], greeting_command),
        group=0,
    )
