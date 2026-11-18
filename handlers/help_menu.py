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
    "🛡️ <b>Group Management & GC Messaging (Admin Only):</b>\n"
    "• /setgcmsg &lt;text&gt; - Set custom GC greeting message\n"
    "• /resetgcmsg - Reset GC greeting message to default\n"
    "• /gcmsg - View current GC greeting message status\n"
    "• /settings - Interactive moderation configuration dashboard\n"
    "• /features - View status of all features in current group\n"
    "• /enable &lt;feature&gt; - Enable a moderation feature\n"
    "• /disable &lt;feature&gt; - Disable a moderation feature\n"
    "• /stats - View moderation statistics for this chat\n"
    "• /logs - Review recent moderation audit logs\n"
    "• /id - View chat and user IDs\n\n"
    "<i>Note: Regular group members have no access to edit or configure GC messaging.</i>\n\n"
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
    "• /antispam [on|off] - Toggle repeated-message spam detection\n\n"
    "💼 <b>Personal Auto-Reply (Telegram Business Secretary):</b>\n"
    "• /personal - Open personal auto-reply settings dashboard\n"
    "• /autoreply_on - Enable personal auto-reply\n"
    "• /autoreply_off - Disable personal auto-reply\n"
    "• /setmessage &lt;text&gt; - Set personal first-reply message (1-time initial setup)\n"
    "• /preview - Preview your auto-reply message\n"
    "• /mystatus - View auto-reply and connection status\n"
    "• /resetmessage - Reset reply template (Admin only once configured)\n"
    "• /exclude_user &lt;id|@user&gt; - Exclude user from auto-replies\n"
    "• /include_user &lt;id|@user&gt; - Re-allow excluded user\n"
    "• /business_stats - View secretary delivery & usage statistics\n\n"
    "<i>Note: Users can configure their personal first-reply message once. After initial setup, only administrators can edit or change the message.</i>\n\n"
    "✨ <b>Supported Placeholders:</b>\n"
    "• <code>{first_name}</code> - Sender's first name\n"
    "• <code>{last_name}</code> - Sender's last name\n"
    "• <code>{full_name}</code> - Sender's full name\n"
    "• <code>{username}</code> - Sender's @username\n"
    "• <code>{time}</code> - Time sent (HH:MM UTC)\n"
    "• <code>{date}</code> - Date sent (YYYY-MM-DD)\n\n"
    "⚡ <b>Advanced Features:</b>\n"
    "• <b>First-Time Sender Only:</b> Automatically replies only to first-time contacts\n"
    "• <b>Cooldown Mode:</b> Configurable interval between replies to repeat senders\n"
    "• <b>Daily Limits:</b> Configurable daily reply caps (25 to 500 replies/day)\n"
    "• <b>Reply Delay:</b> Configurable delay (0s to 15s) before sending\n"
    "• <b>Exclusion List:</b> Prevent specific users or @usernames from receiving replies"
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
