import html
import logging
from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from database import get_group_settings, get_group_stats, update_group_feature
from handlers.admin_check import is_sender_admin_or_owner, verify_group_or_channel_admin

logger = logging.getLogger("Waguri.FeatureCommands")

FEATURE_MAP = {
    # Anti-Link
    "antilink": ("anti_link_enabled", "Anti-Link Protection"),
    "anti-link": ("anti_link_enabled", "Anti-Link Protection"),
    "anti_link": ("anti_link_enabled", "Anti-Link Protection"),
    "link": ("anti_link_enabled", "Anti-Link Protection"),
    # Anti-Bio-Link
    "antibiolink": ("anti_bio_link_enabled", "Anti-Bio-Link Protection"),
    "anti-bio-link": ("anti_bio_link_enabled", "Anti-Bio-Link Protection"),
    "anti_bio_link": ("anti_bio_link_enabled", "Anti-Bio-Link Protection"),
    "biolink": ("anti_bio_link_enabled", "Anti-Bio-Link Protection"),
    "bio_link": ("anti_bio_link_enabled", "Anti-Bio-Link Protection"),
    "bio": ("anti_bio_link_enabled", "Anti-Bio-Link Protection"),
    # Clean Service Messages
    "cleanservice": ("clean_service_enabled", "Clean Service Messages"),
    "clean_service": ("clean_service_enabled", "Clean Service Messages"),
    "clean-service": ("clean_service_enabled", "Clean Service Messages"),
    "antiservice": ("clean_service_enabled", "Clean Service Messages"),
    "anti_service": ("clean_service_enabled", "Clean Service Messages"),
    "anti-service": ("clean_service_enabled", "Clean Service Messages"),
    "service": ("clean_service_enabled", "Clean Service Messages"),
    # Anti-Spam
    "antispam": ("anti_spam_enabled", "Anti-Spam Protection"),
    "anti-spam": ("anti_spam_enabled", "Anti-Spam Protection"),
    "anti_spam": ("anti_spam_enabled", "Anti-Spam Protection"),
    "spam": ("anti_spam_enabled", "Anti-Spam Protection"),
    # Flood Detection
    "flood": ("flood_detection_enabled", "Flood Detection"),
    "antiflood": ("flood_detection_enabled", "Flood Detection"),
    "anti-flood": ("flood_detection_enabled", "Flood Detection"),
    "flood_detection": ("flood_detection_enabled", "Flood Detection"),
    # Warnings
    "warnings": ("warning_system_enabled", "Warning System"),
    "warning": ("warning_system_enabled", "Warning System"),
    "warning_system": ("warning_system_enabled", "Warning System"),
    # Auto-Restriction
    "autorestrict": ("auto_restrict_enabled", "Auto-Restriction"),
    "auto-restrict": ("auto_restrict_enabled", "Auto-Restriction"),
    "auto_restrict": ("auto_restrict_enabled", "Auto-Restriction"),
    "restrict": ("auto_restrict_enabled", "Auto-Restriction"),
    # Anti-Forward
    "antiforward": ("anti_forward_enabled", "Anti-Forward Protection"),
    "anti-forward": ("anti_forward_enabled", "Anti-Forward Protection"),
    "anti_forward": ("anti_forward_enabled", "Anti-Forward Protection"),
    "forward": ("anti_forward_enabled", "Anti-Forward Protection"),
    "forwards": ("anti_forward_enabled", "Anti-Forward Protection"),
    # Anti-Join Spam
    "antijoin": ("anti_join_spam_enabled", "Anti-Join Spam Protection"),
    "anti-join": ("anti_join_spam_enabled", "Anti-Join Spam Protection"),
    "anti_join_spam": ("anti_join_spam_enabled", "Anti-Join Spam Protection"),
    "join_spam": ("anti_join_spam_enabled", "Anti-Join Spam Protection"),
    # Anti-Bot
    "antibot": ("anti_bot_enabled", "Anti-Bot Protection"),
    "anti-bot": ("anti_bot_enabled", "Anti-Bot Protection"),
    "anti_bot": ("anti_bot_enabled", "Anti-Bot Protection"),
    # Media Restrictions
    "media": ("media_restrictions_enabled", "Media Restrictions Filter"),
    "media_restrictions": ("media_restrictions_enabled", "Media Restrictions Filter"),
    "media_filter": ("media_restrictions_enabled", "Media Restrictions Filter"),
    # Raid Mode
    "raid": ("raid_mode_enabled", "Emergency Raid Mode"),
    "raid_mode": ("raid_mode_enabled", "Emergency Raid Mode"),
    # Abuse Detection & Auto-Moderation System
    "abuse": ("abuse_detection_enabled", "Abuse Detection"),
    "abuse_detection": ("abuse_detection_enabled", "Abuse Detection"),
    "antiabuse": ("abuse_detection_enabled", "Abuse Detection"),
    "anti-abuse": ("abuse_detection_enabled", "Abuse Detection"),
}


async def features_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View status of all moderation features for the current group."""
    if not await verify_group_or_channel_admin(update, context.bot):
        return

    message = update.effective_message
    chat = update.effective_chat
    settings = get_group_settings(chat.id)
    chat_title = html.escape(chat.title or "Unnamed Chat")

    abuse_status = "✅ Enabled" if settings.get("abuse_detection_enabled", True) else "❌ Disabled"
    anti_link_status = "✅ Enabled" if settings["anti_link_enabled"] else "❌ Disabled"
    anti_bio_link_status = "✅ Enabled" if settings.get("anti_bio_link_enabled", True) else "❌ Disabled"
    clean_service_status = "✅ Enabled" if settings.get("clean_service_enabled", True) else "❌ Disabled"
    anti_spam_status = "✅ Enabled" if settings["anti_spam_enabled"] else "❌ Disabled"
    flood_status = "✅ Enabled" if settings["flood_detection_enabled"] else "❌ Disabled"
    warnings_status = "✅ Enabled" if settings["warning_system_enabled"] else "❌ Disabled"
    autorestrict_status = "✅ Enabled" if settings["auto_restrict_enabled"] else "❌ Disabled"
    fwd_status = "✅ Enabled" if settings.get("anti_forward_enabled", False) else "❌ Disabled"
    join_status = "✅ Enabled" if settings.get("anti_join_spam_enabled", False) else "❌ Disabled"
    bot_status = "✅ Enabled" if settings.get("anti_bot_enabled", False) else "❌ Disabled"
    media_status = "✅ Enabled" if settings.get("media_restrictions_enabled", False) else "❌ Disabled"
    raid_status = "🚨 ACTIVE" if settings.get("raid_mode_enabled", False) else "⚪ Inactive"

    abuse_warn_limit = settings.get("abuse_warning_limit", 3)
    abuse_mute_mins = settings.get("abuse_mute_duration_minutes", 30)

    text = (
        f"⚙️ <b>Moderation Features for {chat_title}</b>\n\n"
        f"• <b>Abuse Shield:</b> {abuse_status}\n"
        f"• <b>Anti-Link Protection:</b> {anti_link_status}\n"
        f"• <b>Anti-Bio-Link Protection:</b> {anti_bio_link_status}\n"
        f"• <b>Clean Service Messages:</b> {clean_service_status}\n"
        f"• <b>Anti-Spam Protection:</b> {anti_spam_status}\n"
        f"• <b>Flood Detection:</b> {flood_status}\n"
        f"• <b>Warning System:</b> {warnings_status}\n"
        f"• <b>Auto-Restriction:</b> {autorestrict_status}\n"
        f"• <b>Anti-Forward:</b> {fwd_status}\n"
        f"• <b>Anti-Join Spam:</b> {join_status}\n"
        f"• <b>Anti-Bot:</b> {bot_status}\n"
        f"• <b>Media Filter:</b> {media_status}\n"
        f"• <b>Raid Lockdown Mode:</b> {raid_status}\n\n"
        f"🚨 <b>Abuse Warnings Limit:</b> {abuse_warn_limit} (Mute: {abuse_mute_mins}m)\n"
        f"⏱ <b>Spam Window:</b> {settings['spam_window_seconds']}s\n"
        f"⚠️ <b>Warning Limit:</b> {settings['warning_limit']}\n"
        f"⏳ <b>Restriction Duration:</b> {settings['restriction_duration_seconds'] // 3600}h\n\n"
        f"<i>To toggle features: <code>/enable &lt;feature&gt;</code> or <code>/disable &lt;feature&gt;</code>, or run <code>/settings</code>.</i>"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


async def _toggle_feature(update: Update, context: ContextTypes.DEFAULT_TYPE, enable: bool) -> None:
    """Internal helper to toggle a specific moderation feature on or off."""
    if not await verify_group_or_channel_admin(update, context.bot):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    action_verb = "enable" if enable else "disable"
    action_label = "enabled" if enable else "disabled"
    action_icon = "✅" if enable else "❌"

    if not context.args:
        if enable:
            usage_body = (
                "⚠️ <b>Please specify a feature to enable.</b>\n\n"
                "<b>Usage:</b> <code>/enable &lt;feature&gt;</code>\n"
                "<b>Available features:</b>\n"
                "• <code>abuse</code> - Abuse Detection & Auto-Moderation\n"
                "• <code>antilink</code> - Anti-link protection\n"
                "• <code>antispam</code> - Anti-spam protection\n"
                "• <code>flood</code> - Flood rate detection\n"
                "• <code>warnings</code> - Warning system\n"
                "• <code>autorestrict</code> - 24-hour auto-restriction\n"
                "• <code>antiforward</code> - Anti-forward protection\n"
                "• <code>antijoin</code> - Anti-join spam burst alert\n"
                "• <code>antibot</code> - Anti-bot protection\n"
                "• <code>media</code> - Prohibited media filter\n"
                "• <code>raid</code> - Emergency raid lockdown mode"
            )
        else:
            usage_body = (
                "⚠️ <b>Please specify a feature to disable.</b>\n\n"
                "<b>Usage:</b> <code>/disable &lt;feature&gt;</code>\n"
                "<b>Available features:</b>\n"
                "• <code>abuse</code>, <code>antilink</code>, <code>antispam</code>, <code>flood</code>, "
                "<code>warnings</code>, <code>autorestrict</code>, <code>antiforward</code>, "
                "<code>antijoin</code>, <code>antibot</code>, <code>media</code>, <code>raid</code>."
            )
        await message.reply_text(usage_body, parse_mode=ParseMode.HTML)
        return

    feature_key = context.args[0].strip().lower()
    mapping = FEATURE_MAP.get(feature_key)
    if not mapping:
        await message.reply_text(
            f"❌ Unknown feature '<code>{html.escape(feature_key)}</code>'.\n\n"
            "Valid options: <code>antilink</code>, <code>antispam</code>, <code>flood</code>, "
            "<code>warnings</code>, <code>autorestrict</code>, <code>antiforward</code>, "
            "<code>antijoin</code>, <code>antibot</code>, <code>media</code>, <code>raid</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    col_name, display_name = mapping
    update_group_feature(chat.id, col_name, enable)
    logger.info("Admin %s %sd '%s' in chat %s (%s)", user.id if user else "chat", action_verb, col_name, chat.id, chat.title)

    await message.reply_text(
        f"{action_icon} <b>{display_name}</b> has been <b>{action_label}</b> for this group.",
        parse_mode=ParseMode.HTML,
    )


async def enable_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable a specific moderation feature for the current group."""
    await _toggle_feature(update, context, enable=True)


async def disable_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable a specific moderation feature for the current group."""
    await _toggle_feature(update, context, enable=False)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display isolated moderation statistics for the current group or channel."""
    if not await verify_group_or_channel_admin(update, context.bot):
        return

    message = update.effective_message
    chat = update.effective_chat
    stats = get_group_stats(chat.id)
    chat_title = html.escape(chat.title or stats.get("chat_title") or "Unnamed Chat")

    text = (
        f"📊 <b>Moderation Statistics</b>\n"
        f"📍 <b>Chat:</b> {chat_title}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 <b>Messages Checked:</b> {stats['total_messages_checked']}\n"
        f"🚨 <b>Abuse Messages Deleted:</b> {stats.get('abuse_deleted', 0)}\n"
        f"🔗 <b>Links Deleted:</b> {stats['links_deleted']}\n"
        f"🚫 <b>Spam Messages Deleted:</b> {stats['spam_deleted']}\n"
        f"⚠️ <b>Warnings Issued:</b> {stats['warnings_issued']}\n"
        f"⛔️ <b>Restrictions Applied:</b> {stats['restrictions_applied']}\n"
        f"🔨 <b>Members Banned:</b> {stats.get('banned_members', 0)}\n"
        f"⏩ <b>Forwards Deleted:</b> {stats.get('forwards_deleted', 0)}\n"
        f"📸 <b>Restricted Media Deleted:</b> {stats.get('media_deleted', 0)}\n"
        f"🚨 <b>Raid Actions:</b> {stats.get('raid_actions_taken', 0)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>All statistics are strictly isolated to this chat.</i>"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


def register_feature_command_handlers(application: Application) -> None:
    """Register /features, /enable, /disable, and /stats command handlers."""
    application.add_handler(CommandHandler("features", features_command), group=0)
    application.add_handler(CommandHandler("enable", enable_command), group=0)
    application.add_handler(CommandHandler("disable", disable_command), group=0)
    application.add_handler(CommandHandler("stats", stats_command), group=0)
