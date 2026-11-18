from datetime import datetime, timezone
import html
import logging
from telegram import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from database import (
    get_abuse_custom_keywords,
    get_abuse_moderation_logs,
    get_group_settings,
    get_group_stats,
    get_recent_moderation_logs,
    get_whitelisted_domains,
    update_abuse_settings,
    update_group_feature,
    update_group_numeric_setting,
)
from handlers.admin_check import is_sender_admin_or_owner

logger = logging.getLogger("Waguri.SettingsPanel")


def build_main_settings_markup(chat_id: int, settings: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Construct the main moderation panel text and interactive inline keyboard."""
    chat_title = html.escape(settings.get("chat_title") or "Current Group")
    link_status = "ON 🟢" if settings["anti_link_enabled"] else "OFF 🔴"
    spam_status = "ON 🟢" if settings["anti_spam_enabled"] else "OFF 🔴"
    flood_status = "ON 🟢" if settings["flood_detection_enabled"] else "OFF 🔴"
    warn_status = "ON 🟢" if settings["warning_system_enabled"] else "OFF 🔴"
    restr_status = "ON 🟢" if settings["auto_restrict_enabled"] else "OFF 🔴"

    fwd_status = "ON 🟢" if settings.get("anti_forward_enabled", False) else "OFF 🔴"
    join_status = "ON 🟢" if settings.get("anti_join_spam_enabled", False) else "OFF 🔴"
    bot_status = "ON 🟢" if settings.get("anti_bot_enabled", False) else "OFF 🔴"
    media_status = "ON 🟢" if settings.get("media_restrictions_enabled", False) else "OFF 🔴"
    abuse_status = "ON 🟢" if settings.get("abuse_detection_enabled", True) else "OFF 🔴"

    text = (
        f"⚙️ <b>WAGURI GROUP MANAGEMENT</b>\n\n"
        f"👥 <b>Group:</b> {chat_title}\n"
        f"🆔 <b>ID:</b> <code>{chat_id}</code>\n\n"
        f"<b>Moderation Controls:</b>\n"
        f"Tap any button below to toggle protection or adjust settings:"
    )

    keyboard = [
        # Abuse & Anti-Link Protection Toggles
        [
            InlineKeyboardButton(f"🚨 Abuse Shield: {abuse_status}", callback_data=f"cfg:{chat_id}:toggle_abuse"),
            InlineKeyboardButton("🛡️ Abuse Settings", callback_data=f"cfg:{chat_id}:menu_abuse"),
        ],
        [
            InlineKeyboardButton(f"🔗 Anti-Link: {link_status}", callback_data=f"cfg:{chat_id}:toggle_link"),
            InlineKeyboardButton(f"🛡️ Anti-Spam: {spam_status}", callback_data=f"cfg:{chat_id}:toggle_spam"),
        ],
        [
            InlineKeyboardButton(f"🌊 Flood: {flood_status}", callback_data=f"cfg:{chat_id}:toggle_flood"),
            InlineKeyboardButton(f"⚠️ Warnings: {warn_status}", callback_data=f"cfg:{chat_id}:toggle_warn"),
        ],
        [
            InlineKeyboardButton(f"⛔ Auto-Restrict: {restr_status}", callback_data=f"cfg:{chat_id}:toggle_restr"),
            InlineKeyboardButton(f"⏩ Anti-Forward: {fwd_status}", callback_data=f"cfg:{chat_id}:toggle_fwd"),
        ],
        [
            InlineKeyboardButton(f"🚪 Anti-Join Spam: {join_status}", callback_data=f"cfg:{chat_id}:toggle_join"),
            InlineKeyboardButton(f"🤖 Anti-Bot: {bot_status}", callback_data=f"cfg:{chat_id}:toggle_bot"),
        ],
        [
            InlineKeyboardButton(f"📸 Media Filter: {media_status}", callback_data=f"cfg:{chat_id}:toggle_media"),
            InlineKeyboardButton("🌐 Link Whitelist", callback_data=f"cfg:{chat_id}:menu_whitelist"),
        ],
        # Configuration & Sub-menus
        [
            InlineKeyboardButton(f"⏱ Spam ({settings['spam_window_seconds']}s)", callback_data=f"cfg:{chat_id}:menu_spam"),
            InlineKeyboardButton(f"🔢 Warn Limit ({settings['warning_limit']})", callback_data=f"cfg:{chat_id}:menu_warn"),
        ],
        [
            InlineKeyboardButton("📊 Group Statistics", callback_data=f"cfg:{chat_id}:menu_stats"),
            InlineKeyboardButton("📋 Moderation Logs", callback_data=f"cfg:{chat_id}:menu_logs"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"cfg:{chat_id}:refresh"),
            InlineKeyboardButton("❌ Close", callback_data=f"cfg:{chat_id}:close"),
        ],
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_spam_settings_markup(chat_id: int, settings: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu to configure rolling spam detection window."""
    current_window = settings.get("spam_window_seconds", 30)
    text = (
        f"⏱ <b>Spam Window Configuration</b>\n\n"
        f"<b>Current Window:</b> <code>{current_window} seconds</code>\n\n"
        f"Identical messages sent within this time window by the same user will trigger the progressive warning sequence.\n\n"
        f"Select a new window duration:"
    )

    windows = [15, 30, 45, 60, 120]
    keyboard = []
    row = []
    for w in windows:
        label = f"• {w}s •" if w == current_window else f"{w}s"
        row.append(InlineKeyboardButton(label, callback_data=f"cfg:{chat_id}:set_win:{w}"))
    keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Panel", callback_data=f"cfg:{chat_id}:main")])

    return text, InlineKeyboardMarkup(keyboard)


def build_warning_settings_markup(chat_id: int, settings: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu to configure warning threshold limit."""
    current_limit = settings.get("warning_limit", 2)
    text = (
        f"⚠️ <b>Warning Threshold Configuration</b>\n\n"
        f"<b>Current Warning Limit:</b> <code>{current_limit}</code>\n\n"
        f"Number of progressive warnings before the user receives an automatic 24-hour restriction.\n\n"
        f"Select warning threshold:"
    )

    limits = [1, 2, 3, 4, 5]
    keyboard = []
    row = []
    for lim in limits:
        label = f"• {lim} •" if lim == current_limit else str(lim)
        row.append(InlineKeyboardButton(label, callback_data=f"cfg:{chat_id}:set_lim:{lim}"))
    keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Panel", callback_data=f"cfg:{chat_id}:main")])

    return text, InlineKeyboardMarkup(keyboard)


def build_whitelist_markup(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu displaying whitelisted domains for this group."""
    domains = get_whitelisted_domains(chat_id)
    if not domains:
        text = (
            "🌐 <b>Link Whitelist</b>\n\n"
            "No domains are currently whitelisted for this group.\n"
            "All links from regular members will be blocked.\n\n"
            "<i>To allow specific websites, run:</i>\n"
            "<code>/whitelist add example.com</code>"
        )
    else:
        text = (
            f"🌐 <b>Whitelisted Domains ({len(domains)})</b>\n\n"
            f"Messages containing links to these domains are permitted:\n"
        )
        for d in domains:
            text += f"• <code>{html.escape(d)}</code>\n"
        text += "\n<i>To remove a domain, run:</i> <code>/whitelist remove &lt;domain&gt;</code>"

    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Main Panel", callback_data=f"cfg:{chat_id}:main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_stats_markup(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu displaying live moderation metrics."""
    stats = get_group_stats(chat_id)
    chat_title = html.escape(stats.get("chat_title") or "Current Group")

    text = (
        f"📊 <b>Moderation Statistics</b>\n"
        f"👥 <b>Group:</b> {chat_title}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 <b>Messages Checked:</b> {stats['total_messages_checked']}\n"
        f"🔗 <b>Links Deleted:</b> {stats['links_deleted']}\n"
        f"🚫 <b>Spam Messages Deleted:</b> {stats['spam_deleted']}\n"
        f"⚠️ <b>Warnings Issued:</b> {stats['warnings_issued']}\n"
        f"⛔️ <b>Restrictions Applied:</b> {stats['restrictions_applied']}\n"
        f"🔨 <b>Members Banned:</b> {stats.get('banned_members', 0)}\n"
        f"⏩ <b>Forwards Deleted:</b> {stats.get('forwards_deleted', 0)}\n"
        f"📸 <b>Restricted Media Deleted:</b> {stats.get('media_deleted', 0)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>All statistics are strictly isolated to this chat.</i>"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data=f"cfg:{chat_id}:menu_stats")],
        [InlineKeyboardButton("⬅️ Back to Main Panel", callback_data=f"cfg:{chat_id}:main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_logs_markup(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu displaying recent moderation audit logs."""
    logs = get_recent_moderation_logs(chat_id, limit=8)
    if not logs:
        text = (
            "📋 <b>Recent Moderation Audit Logs</b>\n\n"
            "No moderation actions have been recorded yet for this group."
        )
    else:
        text = "📋 <b>Recent Moderation Audit Logs</b>\n\n"
        for entry in logs:
            dt = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc).strftime("%m-%d %H:%M")
            action = html.escape(entry["action"])
            details = html.escape(entry["details"])
            uid = entry["user_id"]
            text += f"• <b>[{dt}]</b> {action} | User: <code>{uid}</code>\n  <i>{details}</i>\n"

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Logs", callback_data=f"cfg:{chat_id}:menu_logs")],
        [InlineKeyboardButton("⬅️ Back to Main Panel", callback_data=f"cfg:{chat_id}:main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


# =============================================================================
# Abuse Settings Sub-Menus
# =============================================================================

def build_abuse_settings_markup(chat_id: int, settings: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu to configure detailed Abuse detection categories and controls."""
    chat_title = html.escape(settings.get("chat_title") or "Current Group")
    abuse_on = "ON 🟢" if settings.get("abuse_detection_enabled", True) else "OFF 🔴"
    sexual_on = "ON 🟢" if settings.get("abuse_sexual_language", True) else "OFF 🔴"
    general_on = "ON 🟢" if settings.get("abuse_general_language", True) else "OFF 🔴"
    hindi_on = "ON 🟢" if settings.get("abuse_hindi_hinglish", True) else "OFF 🔴"
    harass_on = "ON 🟢" if settings.get("abuse_harassment", True) else "OFF 🔴"
    threat_on = "ON 🟢" if settings.get("abuse_threats", True) else "OFF 🔴"
    bypass_on = "ON 🟢" if settings.get("abuse_bypass_detection", True) else "OFF 🔴"
    warn_on = "ON 🟢" if settings.get("abuse_warning_system", True) else "OFF 🔴"
    mute_mins = settings.get("abuse_mute_duration_minutes", 30)
    warn_lim = settings.get("abuse_warning_limit", 3)

    text = (
        f"🚨 <b>Abuse Moderation Controls</b>\n\n"
        f"👥 <b>Group:</b> {chat_title}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
        f"Tap any category below to enable/disable protection or adjust thresholds:"
    )

    keyboard = [
        [
            InlineKeyboardButton(f"🚨 Master Shield: {abuse_on}", callback_data=f"cfg:{chat_id}:toggle_abuse"),
        ],
        [
            InlineKeyboardButton(f"🔞 Sexual: {sexual_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_sexual"),
            InlineKeyboardButton(f"🤬 General: {general_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_general"),
        ],
        [
            InlineKeyboardButton(f"🇮🇳 Hindi: {hindi_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_hindi"),
            InlineKeyboardButton(f"🛑 Harassment: {harass_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_harass"),
        ],
        [
            InlineKeyboardButton(f"🔪 Threats: {threat_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_threat"),
            InlineKeyboardButton(f"🛡 Bypass Shield: {bypass_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_bypass"),
        ],
        [
            InlineKeyboardButton(f"⚠️ Warnings: {warn_on}", callback_data=f"cfg:{chat_id}:toggle_abuse_warn"),
            InlineKeyboardButton(f"⏱ Mute ({mute_mins}m)", callback_data=f"cfg:{chat_id}:menu_abuse_mute"),
        ],
        [
            InlineKeyboardButton("📝 Custom Keywords", callback_data=f"cfg:{chat_id}:menu_abuse_words"),
            InlineKeyboardButton("📋 Abuse Logs", callback_data=f"cfg:{chat_id}:menu_abuse_logs"),
        ],
        [
            InlineKeyboardButton("⬅️ Back to Main Panel", callback_data=f"cfg:{chat_id}:main"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_abuse_mute_markup(chat_id: int, settings: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu to choose default mute duration on repeat abuse offenses."""
    cur_mute = settings.get("abuse_mute_duration_minutes", 30)
    text = (
        f"⏱ <b>Abuse Temporary Mute Duration</b>\n\n"
        f"<b>Current Mute Duration:</b> <code>{cur_mute} minutes</code>\n\n"
        f"When a member exceeds the warning threshold for abusive messages, "
        f"they will be restricted from messaging for this duration.\n\n"
        f"Select a new mute duration:"
    )
    durations = [15, 30, 60, 120, 1440]
    keyboard = []
    row = []
    for d in durations:
        label = f"{d}m" if d < 60 else (f"{d//60}h" if d < 1440 else "24h")
        btn_text = f"✅ {label}" if d == cur_mute else label
        row.append(InlineKeyboardButton(btn_text, callback_data=f"cfg:{chat_id}:set_abuse_mute:{d}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Abuse Settings", callback_data=f"cfg:{chat_id}:menu_abuse")])
    return text, InlineKeyboardMarkup(keyboard)


def build_abuse_words_markup(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu displaying custom blocked and whitelisted keywords for Abuse moderation."""
    blocked, allowed = get_abuse_custom_keywords(chat_id)
    text = f"📝 <b>Custom Abuse Keywords</b>\n\n"
    if not blocked and not allowed:
        text += "No custom keywords configured for this group.\n\n"
    else:
        text += f"🚫 <b>Blocked Keywords ({len(blocked)}):</b>\n"
        if blocked:
            for b in blocked[:10]:
                text += f"• <code>{html.escape(b)}</code>\n"
        else:
            text += "<i>None</i>\n"

        text += f"\n✅ <b>Whitelisted Keywords ({len(allowed)}):</b>\n"
        if allowed:
            for a in allowed[:10]:
                text += f"• <code>{html.escape(a)}</code>\n"
        else:
            text += "<i>None</i>\n"

    text += "\n<i>To manage words, use:</i>\n<code>/abuse addword &lt;word&gt;</code>\n<code>/abuse removeword &lt;word&gt;</code>"
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Abuse Settings", callback_data=f"cfg:{chat_id}:menu_abuse")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_abuse_logs_markup(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Sub-menu displaying recent abuse moderation actions."""
    logs = get_abuse_moderation_logs(chat_id, limit=8)
    if not logs:
        text = "📋 <b>Recent Abuse Moderation Logs</b>\n\nNo abuse moderation actions recorded yet for this group."
    else:
        text = "📋 <b>Recent Abuse Moderation Logs</b>\n\n"
        for entry in logs:
            dt = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc).strftime("%m-%d %H:%M")
            action = html.escape(entry["action"])
            details = html.escape(entry["details"])
            uid = entry["user_id"]
            text += f"• <b>[{dt}]</b> {action} | User: <code>{uid}</code>\n  <i>{details}</i>\n"

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Logs", callback_data=f"cfg:{chat_id}:menu_abuse_logs")],
        [InlineKeyboardButton("⬅️ Back to Abuse Settings", callback_data=f"cfg:{chat_id}:menu_abuse")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings by displaying the interactive moderation dashboard."""
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
        await message.reply_text("You need administrator privileges to use this command.")
        return

    settings = get_group_settings(chat.id)
    text, markup = build_main_settings_markup(chat.id, settings)
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline button taps for the moderation dashboard with server-side RBAC."""
    query = update.callback_query
    if not query or not query.data:
        return

    parts = query.data.split(":")
    if len(parts) < 3 or parts[0] != "cfg":
        return

    target_chat_id = int(parts[1])
    action = parts[2]

    # Re-verify administrator privileges server-side on EVERY callback
    user = update.effective_user
    chat = update.effective_chat or query.message.chat if query.message else None

    if not chat or chat.id != target_chat_id:
        try:
            chat = await context.bot.get_chat(target_chat_id)
        except Exception:
            chat = None

    if chat:
        is_admin = await is_sender_admin_or_owner(chat, user, None, context.bot)
        if not is_admin:
            await query.answer("⛔ Access denied: Administrator rights required.", show_alert=True)
            return
    else:
        await query.answer("⛔ Unable to verify chat permissions.", show_alert=True)
        return

    settings = get_group_settings(target_chat_id)

    # -------------------------------------------------------------------------
    # Actions & Toggles
    # -------------------------------------------------------------------------
    if action == "close":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("Settings panel closed.")
        await query.answer()
        return

    elif action == "toggle_link":
        new_val = not settings["anti_link_enabled"]
        update_group_feature(target_chat_id, "anti_link_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Anti-Link is now {status_str}")

    elif action == "toggle_spam":
        new_val = not settings["anti_spam_enabled"]
        update_group_feature(target_chat_id, "anti_spam_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Anti-Spam is now {status_str}")

    elif action == "toggle_flood":
        new_val = not settings["flood_detection_enabled"]
        update_group_feature(target_chat_id, "flood_detection_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Flood Protection is now {status_str}")

    elif action == "toggle_warn":
        new_val = not settings["warning_system_enabled"]
        update_group_feature(target_chat_id, "warning_system_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Warning System is now {status_str}")

    elif action == "toggle_restr":
        new_val = not settings["auto_restrict_enabled"]
        update_group_feature(target_chat_id, "auto_restrict_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Auto-Restriction is now {status_str}")

    elif action == "toggle_fwd":
        new_val = not settings.get("anti_forward_enabled", False)
        update_group_feature(target_chat_id, "anti_forward_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Anti-Forward is now {status_str}")

    elif action == "toggle_join":
        new_val = not settings.get("anti_join_spam_enabled", False)
        update_group_feature(target_chat_id, "anti_join_spam_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Anti-Join Spam is now {status_str}")

    elif action == "toggle_bot":
        new_val = not settings.get("anti_bot_enabled", False)
        update_group_feature(target_chat_id, "anti_bot_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Anti-Bot Protection is now {status_str}")

    elif action == "toggle_media":
        new_val = not settings.get("media_restrictions_enabled", False)
        update_group_feature(target_chat_id, "media_restrictions_enabled", new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Media Filter is now {status_str}")

    elif action == "toggle_abuse":
        new_val = not settings.get("abuse_detection_enabled", True)
        update_group_feature(target_chat_id, "abuse_detection_enabled", new_val)
        update_abuse_settings(target_chat_id, abuse_detection_enabled=new_val)
        status_str = "ENABLED" if new_val else "DISABLED"
        await query.answer(f"Abuse Shield is now {status_str}")

    elif action == "toggle_abuse_sexual":
        new_val = not settings.get("abuse_sexual_language", True)
        update_abuse_settings(target_chat_id, abuse_sexual_language=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Sexual Language Filter {'ENABLED' if new_val else 'DISABLED'}")
        return

    elif action == "toggle_abuse_general":
        new_val = not settings.get("abuse_general_language", True)
        update_abuse_settings(target_chat_id, abuse_general_language=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"General Abuse Filter {'ENABLED' if new_val else 'DISABLED'}")
        return

    elif action == "toggle_abuse_hindi":
        new_val = not settings.get("abuse_hindi_hinglish", True)
        update_abuse_settings(target_chat_id, abuse_hindi_hinglish=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Hindi/Hinglish Filter {'ENABLED' if new_val else 'DISABLED'}")
        return

    elif action == "toggle_abuse_harass":
        new_val = not settings.get("abuse_harassment", True)
        update_abuse_settings(target_chat_id, abuse_harassment=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Harassment Filter {'ENABLED' if new_val else 'DISABLED'}")
        return

    elif action == "toggle_abuse_threat":
        new_val = not settings.get("abuse_threats", True)
        update_abuse_settings(target_chat_id, abuse_threats=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Threat Detection {'ENABLED' if new_val else 'DISABLED'}")
        return

    elif action == "toggle_abuse_bypass":
        new_val = not settings.get("abuse_bypass_detection", True)
        update_abuse_settings(target_chat_id, abuse_bypass_detection=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Bypass Shield {'ENABLED' if new_val else 'DISABLED'}")
        return

    elif action == "toggle_abuse_warn":
        new_val = not settings.get("abuse_warning_system", True)
        update_abuse_settings(target_chat_id, abuse_warning_system=new_val)
        fresh_settings = get_group_settings(target_chat_id)
        text, markup = build_abuse_settings_markup(target_chat_id, fresh_settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Abuse Warning System {'ENABLED' if new_val else 'DISABLED'}")
        return

    # Sub-menus
    elif action == "menu_abuse":
        text, markup = build_abuse_settings_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "menu_abuse_mute":
        text, markup = build_abuse_mute_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "set_abuse_mute" and len(parts) >= 4:
        mute_m = int(parts[3])
        update_abuse_settings(target_chat_id, abuse_mute_duration_minutes=mute_m)
        settings["abuse_mute_duration_minutes"] = mute_m
        text, markup = build_abuse_mute_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Abuse mute duration set to {mute_m} minutes.")
        return

    elif action == "menu_abuse_words":
        text, markup = build_abuse_words_markup(target_chat_id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "menu_abuse_logs":
        text, markup = build_abuse_logs_markup(target_chat_id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return
    elif action == "menu_spam":
        text, markup = build_spam_settings_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "set_win" and len(parts) >= 4:
        win_secs = int(parts[3])
        update_group_numeric_setting(target_chat_id, "spam_window_seconds", win_secs)
        settings["spam_window_seconds"] = win_secs
        text, markup = build_spam_settings_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Spam window updated to {win_secs}s")
        return

    elif action == "menu_warn":
        text, markup = build_warning_settings_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "set_lim" and len(parts) >= 4:
        lim = int(parts[3])
        update_group_numeric_setting(target_chat_id, "warning_limit", lim)
        settings["warning_limit"] = lim
        text, markup = build_warning_settings_markup(target_chat_id, settings)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Warning limit set to {lim}")
        return

    elif action == "menu_whitelist":
        text, markup = build_whitelist_markup(target_chat_id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "menu_stats":
        text, markup = build_stats_markup(target_chat_id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "menu_logs":
        text, markup = build_logs_markup(target_chat_id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action in ("main", "refresh"):
        await query.answer("Settings refreshed.")

    # Refresh and show updated main panel
    fresh_settings = get_group_settings(target_chat_id)
    text, markup = build_main_settings_markup(target_chat_id, fresh_settings)
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception:
        pass


def register_settings_handlers(application: Application) -> None:
    """Register /settings command and inline callback handlers."""
    application.add_handler(CommandHandler("settings", settings_command), group=0)
    application.add_handler(CallbackQueryHandler(settings_callback_handler, pattern=r"^cfg:"), group=0)
