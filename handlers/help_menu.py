import html
import logging
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

logger = logging.getLogger("Waguri.HelpMenu")


# =============================================================================
# Full Bot Commands & Features Text
# =============================================================================

HELP_COMMANDS_TEXT = (
    "🤖 <b>Waguri Bot Commands & Help</b>\n\n"
    "<b>General Commands:</b>\n"
    "• /start - Start Waguri\n"
    "• /help - View this help menu\n"
    "• /about - About Waguri\n"
    "• /contact - Contact support (@lucky_paji)\n\n"
    "🛡️ <b>Group Management & Controls (Admin Only):</b>\n"
    "• /settings - Interactive moderation configuration dashboard\n"
    "• /features - View status of all features in current group\n"
    "• /enable &lt;feature&gt; - Enable a moderation feature\n"
    "• /disable &lt;feature&gt; - Disable a moderation feature\n"
    "• /stats - View moderation statistics for this chat\n"
    "• /logs - Review recent moderation audit logs\n"
    "• /id - View chat and user IDs\n\n"
    "⚡️ <b>Moderation & Penalties:</b>\n"
    "• /whitelist [add|remove|list] &lt;domain&gt; - Manage allowed domains\n"
    "• /blacklist [add|remove|list] &lt;pattern&gt; - Manage blocked patterns\n"
    "• /warnings [reply|id] - View member warnings\n"
    "• /resetwarnings [reply|id] - Clear user warnings\n"
    "• /mute [reply|id] [time] - Mute user (e.g. 10m, 2h, 1d)\n"
    "• /unmute [reply|id] - Restore member messaging permissions\n"
    "• /ban [reply|id] - Ban member from group\n"
    "• /unban [reply|id] - Unban member\n"
    "• /antlink [on|off] - Toggle anti-link protection\n"
    "• /antibiolink [on|off] - Toggle bio link protection\n"
    "• /cleanservice [on|off] - Clean service messages (joins, leaves, pins)\n"
    "• /antispam [on|off] - Toggle repeated-message spam detection\n"
    "• /abuse [on|off|status|words|addword|removeword|warnings|reset|settings|logs] - Advanced Abuse Detection & Auto-Moderation System"
)


# =============================================================================
# Markup Builders for Help & Commands
# =============================================================================

def build_main_help_markup(chat_id: int = 0, is_private: bool = False) -> tuple[str, InlineKeyboardMarkup | None]:
    """
    Construct the Help & Commands menu text and optional navigation markup.
    Does not attach inline command buttons.
    """
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Main Menu", callback_data="pvt:main")]]) if is_private else None
    return HELP_COMMANDS_TEXT, markup


# =============================================================================
# Callback Handler for Navigation
# =============================================================================

async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline navigation button clicks from the help menu."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "cmd":
        return

    target_chat_id = int(parts[1])
    action_type = parts[2]

    # Return to Main Help Menu or Close
    if action_type == "main":
        text, markup = build_main_help_markup(target_chat_id, is_private=False)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action_type == "close":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("Help menu closed.")
        await query.answer()
        return


# =============================================================================
# Command Handler & Registration
# =============================================================================

async def interactive_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help by displaying all bot commands directly in chat without inline buttons."""
    message = update.effective_message
    if not message:
        return

    await message.reply_text(HELP_COMMANDS_TEXT, parse_mode=ParseMode.HTML)


def register_help_menu_handlers(application: Application) -> None:
    """Register cmd:* callback handlers for help menu."""
    application.add_handler(CallbackQueryHandler(help_callback_handler, pattern=r"^cmd:"), group=0)
