import logging
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from handlers.anti_link import detect_link, process_link_message
from handlers.help_menu import interactive_help_command
from handlers.private_dashboard import build_private_start_markup

logger = logging.getLogger("Waguri.Commands")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.
    In private chats: Opens the private management dashboard with 8 interactive inline buttons.
    In groups/supergroups: Preserves the exact required greeting message.
    """
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # In private chat, display the rich private dashboard (or personal auto-reply if deep-linked)
    if chat.type == ChatType.PRIVATE:
        if context.args and context.args[0] == "personal":
            from handlers.personal_autoreply import personal_command
            await personal_command(update, context)
            return
        bot_username = context.bot.username or "Ms_Waguri_bot"
        text, markup = build_private_start_markup(bot_username)
        await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    # In groups/supergroups, check if /start contains an unauthorized link
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        has_link, link_type = detect_link(message)
        if has_link:
            await process_link_message(update, context, link_type)
            return

    # Exact required welcome message for groups
    await message.reply_text("Hi, welcome. I am Waguri. How can I help you")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command by opening the interactive Help & Commands launcher."""
    await interactive_help_command(update, context)


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /about command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "Waguri (@Ms_Waguri_bot) is an advanced Telegram group and channel moderation bot built with Python.\n\n"
            "Features include Abuse Detection & Auto-Moderation, automatic anti-link protection with whitelisting, repeated message spam detection, "
            "progressive warnings, temporary restrictions, flood control, media filters, and group greetings."
        )


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /contact command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "For inquiries or support regarding Waguri, please reach out to the bot administrator @lucky_paji."
        )


def register_command_handlers(application: Application) -> None:
    """Register all bot command handlers on the application."""
    application.add_handler(CommandHandler("start", start), group=0)
    application.add_handler(CommandHandler("help", help_command), group=0)
    application.add_handler(CommandHandler("about", about_command), group=0)
    application.add_handler(CommandHandler("contact", contact_command), group=0)
