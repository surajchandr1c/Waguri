from datetime import datetime, timezone
import html
import logging
import time
from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from config import BOT_OWNER_IDS, DEFAULT_ALLOWED_MEDIA
from database import (
    add_blacklisted_pattern,
    add_whitelisted_domain,
    clear_active_incident,
    get_active_incident,
    get_blacklisted_patterns,
    get_group_settings,
    get_group_stats,
    get_recent_moderation_logs,
    get_user_restrictions,
    get_user_warnings_count,
    get_whitelisted_domains,
    increment_stat,
    log_moderation_event,
    record_restriction,
    reset_user_warnings,
    set_group_anti_link,
    set_group_anti_spam,
    update_group_feature,
)
from handlers.admin_check import check_bot_permissions, is_bot_owner, is_sender_admin_or_owner
from handlers.settings_panel import build_main_settings_markup

logger = logging.getLogger("Waguri.HelpMenu")


# =============================================================================
# Markup Builders for Interactive Help & Commands
# =============================================================================

def build_main_help_markup(chat_id: int, is_private: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """
    Construct the interactive Help & Commands menu.
    Allows users to click any command to execute it or inspect its sub-options.
    """
    text = (
        "🤖 <b>Waguri Bot Commands & Help</b>\n\n"
        "<b>General Commands:</b>\n"
        "• /start - Start Waguri\n"
        "• /help - View this help menu\n"
        "• /about - About Waguri\n"
        "• /contact - Contact support (@lucky_paji)\n\n"
        "🛡️ <b>Group Management Commands:</b>\n"
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
        "• /antispam [on|off] - Toggle repeated-message spam detection"
    )

    keyboard = [
        # General Information Commands
        [
            InlineKeyboardButton("ℹ️ /about", callback_data=f"cmd:{chat_id}:run:about"),
            InlineKeyboardButton("💬 /contact", callback_data=f"cmd:{chat_id}:run:contact"),
            InlineKeyboardButton("🆔 /id", callback_data=f"cmd:{chat_id}:run:id"),
        ],
        # Group Management & Statistics
        [
            InlineKeyboardButton("⚙️ /settings", callback_data=f"cmd:{chat_id}:run:settings"),
            InlineKeyboardButton("⚡ /features", callback_data=f"cmd:{chat_id}:run:features"),
            InlineKeyboardButton("📊 /stats", callback_data=f"cmd:{chat_id}:run:stats"),
            InlineKeyboardButton("📋 /logs", callback_data=f"cmd:{chat_id}:run:logs"),
        ],
        # Commands with Options (Toggles)
        [
            InlineKeyboardButton("🔗 /antlink ▾", callback_data=f"cmd:{chat_id}:opt:antlink"),
            InlineKeyboardButton("👤 /antibiolink ▾", callback_data=f"cmd:{chat_id}:opt:antibiolink"),
            InlineKeyboardButton("🧹 /cleanservice ▾", callback_data=f"cmd:{chat_id}:opt:cleanservice"),
            InlineKeyboardButton("🛡️ /antispam ▾", callback_data=f"cmd:{chat_id}:opt:antispam"),
        ],
        # Feature Enable / Disable
        [
            InlineKeyboardButton("✅ /enable ▾", callback_data=f"cmd:{chat_id}:opt:enable"),
            InlineKeyboardButton("❌ /disable ▾", callback_data=f"cmd:{chat_id}:opt:disable"),
        ],
        # Whitelist & Blacklist
        [
            InlineKeyboardButton("🌐 /whitelist ▾", callback_data=f"cmd:{chat_id}:opt:whitelist"),
            InlineKeyboardButton("🚫 /blacklist ▾", callback_data=f"cmd:{chat_id}:opt:blacklist"),
        ],
        # Moderation Actions
        [
            InlineKeyboardButton("🔇 /mute ▾", callback_data=f"cmd:{chat_id}:opt:mute"),
            InlineKeyboardButton("🔊 /unmute", callback_data=f"cmd:{chat_id}:run:unmute"),
            InlineKeyboardButton("⚠️ /warnings", callback_data=f"cmd:{chat_id}:run:warnings"),
        ],
        [
            InlineKeyboardButton("🔨 /ban", callback_data=f"cmd:{chat_id}:run:ban"),
            InlineKeyboardButton("🔓 /unban", callback_data=f"cmd:{chat_id}:run:unban"),
            InlineKeyboardButton("🔄 /resetwarnings", callback_data=f"cmd:{chat_id}:run:resetwarnings"),
        ],
    ]

    if is_private:
        keyboard.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="pvt:main")])
    else:
        keyboard.append([InlineKeyboardButton("❌ Close Help Menu", callback_data=f"cmd:{chat_id}:close")])

    return text, InlineKeyboardMarkup(keyboard)


def build_command_options_markup(chat_id: int, command_name: str, is_private: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """
    Construct sub-option selection menus for commands with arguments/options.
    """
    keyboard = []

    # -------------------------------------------------------------------------
    # Options for /antlink
    # -------------------------------------------------------------------------
    if command_name == "antlink":
        text = (
            "🔗 <b>Command Options: /antlink</b>\n\n"
            "Anti-Link Protection automatically deletes unauthorized URLs and links sent by regular members.\n\n"
            "Select an option to execute:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🟢 Enable (/antlink on)", callback_data=f"cmd:{chat_id}:exec:antlink:on"),
                InlineKeyboardButton("🔴 Disable (/antlink off)", callback_data=f"cmd:{chat_id}:exec:antlink:off"),
            ],
            [
                InlineKeyboardButton("ℹ️ View Status (/antlink)", callback_data=f"cmd:{chat_id}:run:antlink_status"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /antibiolink
    # -------------------------------------------------------------------------
    elif command_name == "antibiolink":
        text = (
            "👤 <b>Command Options: /antibiolink</b>\n\n"
            "Anti-Bio-Link Protection automatically deletes messages from members who have links in their Telegram bio and issues a warning.\n\n"
            "Select an option to execute:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🟢 Enable (/antibiolink on)", callback_data=f"cmd:{chat_id}:exec:antibiolink:on"),
                InlineKeyboardButton("🔴 Disable (/antibiolink off)", callback_data=f"cmd:{chat_id}:exec:antibiolink:off"),
            ],
            [
                InlineKeyboardButton("ℹ️ View Status (/antibiolink)", callback_data=f"cmd:{chat_id}:run:antibiolink_status"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /cleanservice
    # -------------------------------------------------------------------------
    elif command_name == "cleanservice":
        text = (
            "🧹 <b>Command Options: /cleanservice</b>\n\n"
            "Clean Service Messages automatically deletes chat status updates such as member joins, leaves, pins, and video chats.\n\n"
            "Select an option to execute:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🟢 Enable (/cleanservice on)", callback_data=f"cmd:{chat_id}:exec:cleanservice:on"),
                InlineKeyboardButton("🔴 Disable (/cleanservice off)", callback_data=f"cmd:{chat_id}:exec:cleanservice:off"),
            ],
            [
                InlineKeyboardButton("ℹ️ View Status (/cleanservice)", callback_data=f"cmd:{chat_id}:run:cleanservice_status"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /antispam
    # -------------------------------------------------------------------------
    elif command_name == "antispam":
        text = (
            "🛡️ <b>Command Options: /antispam</b>\n\n"
            "Anti-Spam Protection detects repeated messages within rolling 30 seconds and applies progressive warnings.\n\n"
            "Select an option to execute:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🟢 Enable (/antispam on)", callback_data=f"cmd:{chat_id}:exec:antispam:on"),
                InlineKeyboardButton("🔴 Disable (/antispam off)", callback_data=f"cmd:{chat_id}:exec:antispam:off"),
            ],
            [
                InlineKeyboardButton("ℹ️ View Status (/antispam)", callback_data=f"cmd:{chat_id}:run:antispam_status"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /raid
    # -------------------------------------------------------------------------
    elif command_name == "raid":
        text = (
            "🚨 <b>Command Options: /raid</b>\n\n"
            "Raid Emergency Mode places the group in high-alert lockdown during coordinated spam attacks.\n\n"
            "Select an option to execute:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🚨 Enable Lockdown (/raid on)", callback_data=f"cmd:{chat_id}:exec:raid:on"),
                InlineKeyboardButton("⚪ Normal Mode (/raid off)", callback_data=f"cmd:{chat_id}:exec:raid:off"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /enable
    # -------------------------------------------------------------------------
    elif command_name == "enable":
        text = (
            "✅ <b>Command Options: /enable &lt;feature&gt;</b>\n\n"
            "Select which moderation feature you want to <b>enable</b> for this group:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔗 antilink", callback_data=f"cmd:{chat_id}:exec:enable:antilink"),
                InlineKeyboardButton("🛡️ antispam", callback_data=f"cmd:{chat_id}:exec:enable:antispam"),
            ],
            [
                InlineKeyboardButton("🌊 flood", callback_data=f"cmd:{chat_id}:exec:enable:flood"),
                InlineKeyboardButton("⚠️ warnings", callback_data=f"cmd:{chat_id}:exec:enable:warnings"),
            ],
            [
                InlineKeyboardButton("⛔ autorestrict", callback_data=f"cmd:{chat_id}:exec:enable:autorestrict"),
                InlineKeyboardButton("⏩ antiforward", callback_data=f"cmd:{chat_id}:exec:enable:antiforward"),
            ],
            [
                InlineKeyboardButton("🚪 antijoin", callback_data=f"cmd:{chat_id}:exec:enable:antijoin"),
                InlineKeyboardButton("🤖 antibot", callback_data=f"cmd:{chat_id}:exec:enable:antibot"),
            ],
            [
                InlineKeyboardButton("📸 media", callback_data=f"cmd:{chat_id}:exec:enable:media"),
                InlineKeyboardButton("🚨 raid", callback_data=f"cmd:{chat_id}:exec:enable:raid"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /disable
    # -------------------------------------------------------------------------
    elif command_name == "disable":
        text = (
            "❌ <b>Command Options: /disable &lt;feature&gt;</b>\n\n"
            "Select which moderation feature you want to <b>disable</b> for this group:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔗 antilink", callback_data=f"cmd:{chat_id}:exec:disable:antilink"),
                InlineKeyboardButton("🛡️ antispam", callback_data=f"cmd:{chat_id}:exec:disable:antispam"),
            ],
            [
                InlineKeyboardButton("🌊 flood", callback_data=f"cmd:{chat_id}:exec:disable:flood"),
                InlineKeyboardButton("⚠️ warnings", callback_data=f"cmd:{chat_id}:exec:disable:warnings"),
            ],
            [
                InlineKeyboardButton("⛔ autorestrict", callback_data=f"cmd:{chat_id}:exec:disable:autorestrict"),
                InlineKeyboardButton("⏩ antiforward", callback_data=f"cmd:{chat_id}:exec:disable:antiforward"),
            ],
            [
                InlineKeyboardButton("🚪 antijoin", callback_data=f"cmd:{chat_id}:exec:disable:antijoin"),
                InlineKeyboardButton("🤖 antibot", callback_data=f"cmd:{chat_id}:exec:disable:antibot"),
            ],
            [
                InlineKeyboardButton("📸 media", callback_data=f"cmd:{chat_id}:exec:disable:media"),
                InlineKeyboardButton("🚨 raid", callback_data=f"cmd:{chat_id}:exec:disable:raid"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /whitelist
    # -------------------------------------------------------------------------
    elif command_name == "whitelist":
        text = (
            "🌐 <b>Command Options: /whitelist</b>\n\n"
            "Manage permitted domains that will bypass automatic anti-link deletion.\n\n"
            "Select an action:"
        )
        keyboard = [
            [InlineKeyboardButton("📋 View Whitelist (/whitelist list)", callback_data=f"cmd:{chat_id}:exec:whitelist:list")],
            [
                InlineKeyboardButton("➕ Allow google.com", callback_data=f"cmd:{chat_id}:exec:whitelist:add_google"),
                InlineKeyboardButton("➕ Allow youtube.com", callback_data=f"cmd:{chat_id}:exec:whitelist:add_youtube"),
            ],
            [
                InlineKeyboardButton("➕ Allow t.me", callback_data=f"cmd:{chat_id}:exec:whitelist:add_tme"),
                InlineKeyboardButton("➕ Allow github.com", callback_data=f"cmd:{chat_id}:exec:whitelist:add_github"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /blacklist
    # -------------------------------------------------------------------------
    elif command_name == "blacklist":
        text = (
            "🚫 <b>Command Options: /blacklist</b>\n\n"
            "Manage blacklisted phrases, keywords, or phishing domains that are deleted instantly.\n\n"
            "Select an action:"
        )
        keyboard = [
            [InlineKeyboardButton("📋 View Blacklist (/blacklist list)", callback_data=f"cmd:{chat_id}:exec:blacklist:list")],
            [
                InlineKeyboardButton("➕ Block 'free crypto'", callback_data=f"cmd:{chat_id}:exec:blacklist:add_crypto"),
                InlineKeyboardButton("➕ Block 'invest now'", callback_data=f"cmd:{chat_id}:exec:blacklist:add_invest"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    # -------------------------------------------------------------------------
    # Options for /mute
    # -------------------------------------------------------------------------
    elif command_name == "mute":
        text = (
            "🔇 <b>Command Options: /mute &lt;duration&gt;</b>\n\n"
            "Temporarily restrict a user from sending messages.\n\n"
            "<i>Note: If you replied to a member's message, clicking any preset duration will mute that member immediately.</i>\n\n"
            "Select duration preset:"
        )
        keyboard = [
            [
                InlineKeyboardButton("⏱ 10 Minutes", callback_data=f"cmd:{chat_id}:exec:mute:10m"),
                InlineKeyboardButton("⏱ 1 Hour", callback_data=f"cmd:{chat_id}:exec:mute:1h"),
            ],
            [
                InlineKeyboardButton("⏱ 2 Hours", callback_data=f"cmd:{chat_id}:exec:mute:2h"),
                InlineKeyboardButton("⏱ 24 Hours", callback_data=f"cmd:{chat_id}:exec:mute:1d"),
            ],
            [
                InlineKeyboardButton("⏱ 7 Days", callback_data=f"cmd:{chat_id}:exec:mute:7d"),
            ],
            [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")],
        ]

    else:
        text = f"⚙️ <b>Command Options: /{html.escape(command_name)}</b>"
        keyboard = [[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{chat_id}:main")]]

    return text, InlineKeyboardMarkup(keyboard)


# =============================================================================
# Callback Handler for Interactive Commands
# =============================================================================

async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline button clicks from the interactive Help & Commands menu."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "cmd":
        return

    target_chat_id = int(parts[1])
    action_type = parts[2]
    user = update.effective_user
    chat = update.effective_chat or (query.message.chat if query.message else None)

    # -------------------------------------------------------------------------
    # Navigation: Return to Main Help Menu or Close
    # -------------------------------------------------------------------------
    if action_type == "main":
        is_private = (chat.type == ChatType.PRIVATE) if chat else False
        text, markup = build_main_help_markup(target_chat_id, is_private=is_private)
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

    # -------------------------------------------------------------------------
    # Open Sub-Options Menu for Commands with Arguments/Options
    # -------------------------------------------------------------------------
    elif action_type == "opt" and len(parts) >= 4:
        cmd_name = parts[3]

        # In private chat, redirect group commands cleanly
        if chat and chat.type == ChatType.PRIVATE and target_chat_id >= 0:
            text = (
                "ℹ️ <b>Group Moderation Command</b>\n\n"
                f"The <code>/{html.escape(cmd_name)}</code> command configures group protection settings.\n\n"
                "• To manage your groups from private chat, tap <b>👥 My Groups</b>.\n"
                "• Or run this command directly inside your group where Waguri is an administrator."
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 My Groups", callback_data="pvt:my_groups")],
                [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")],
            ])
            await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            await query.answer("Group moderation command")
            return

        # Server-side admin check before opening moderation options in groups
        if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            is_admin = (user and is_bot_owner(user.id)) or await is_sender_admin_or_owner(chat, user, None, context.bot)
            if not is_admin:
                await query.answer("⛔ You need administrator privileges to view moderation options.", show_alert=True)
                return

        is_private = (chat.type == ChatType.PRIVATE) if chat else False
        text, markup = build_command_options_markup(target_chat_id, cmd_name, is_private=is_private)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer(f"Opened /{cmd_name} options")
        return

    # -------------------------------------------------------------------------
    # Execute Direct Commands Without Options
    # -------------------------------------------------------------------------
    elif action_type == "run" and len(parts) >= 4:
        cmd_name = parts[3]

        if cmd_name == "about":
            text = (
                "ℹ️ <b>About Waguri</b>\n\n"
                "Waguri (@Ms_Waguri_bot) is an advanced Telegram group and channel moderation platform.\n\n"
                "It empowers communities with automated protection against spam, links, flood bursts, "
                "malicious bots, forwards, and raids while keeping every group strictly isolated."
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
            await query.answer("Executed /about")
            return

        elif cmd_name == "contact":
            text = (
                "💬 <b>Contact Support</b>\n\n"
                "For inquiries, support, or partnership requests regarding Waguri, please reach out to the bot "
                "administrator <b>@lucky_paji</b>."
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
            await query.answer("Executed /contact")
            return

        elif cmd_name == "id":
            c_title = html.escape(chat.title or "Private Chat") if chat else "Private"
            c_id = chat.id if chat else target_chat_id
            c_type = chat.type if chat else "private"
            u_name = html.escape(user.full_name or "Unknown")
            u_id = user.id
            u_handle = f"@{user.username}" if user.username else "None"

            text = (
                "📋 <b>ID Information</b>\n\n"
                f"• <b>Chat:</b> {c_title}\n"
                f"• <b>Chat ID:</b> <code>{c_id}</code>\n"
                f"• <b>Chat Type:</b> <code>{c_type}</code>\n"
                f"• <b>Your Name:</b> {u_name}\n"
                f"• <b>Your User ID:</b> <code>{u_id}</code>\n"
                f"• <b>Your Username:</b> {u_handle}"
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
            await query.answer("Executed /id")
            return

        # In private chat, redirect group commands cleanly
        if chat and chat.type == ChatType.PRIVATE and target_chat_id >= 0:
            if cmd_name in (
                "settings", "features", "stats", "logs", "antlink_status", "antispam_status",
                "unmute", "ban", "unban", "warnings", "resetwarnings"
            ):
                text = (
                    "ℹ️ <b>Group Moderation Command</b>\n\n"
                    f"The <code>/{html.escape(cmd_name)}</code> command configures group protection settings.\n\n"
                    "• To manage your groups from private chat, tap <b>👥 My Groups</b>.\n"
                    "• Or run this command directly inside your group where Waguri is an administrator."
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 My Groups", callback_data="pvt:my_groups")],
                    [InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")],
                ])
                await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
                await query.answer("Group moderation command")
                return

        # Verification check for admin-only commands in groups
        if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            is_admin = (user and is_bot_owner(user.id)) or await is_sender_admin_or_owner(chat, user, None, context.bot)
            if not is_admin:
                await query.answer("⛔ You need administrator privileges to use this command.", show_alert=True)
                return

        if cmd_name == "settings":
            settings = get_group_settings(target_chat_id)
            text, markup = build_main_settings_markup(target_chat_id, settings)
            await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
            await query.answer("Opened /settings")
            return

        elif cmd_name == "features":
            settings = get_group_settings(target_chat_id)
            c_title = html.escape(chat.title or settings.get("chat_title") or "Group") if chat else "Group"
            link_st = "✅ Enabled" if settings["anti_link_enabled"] else "❌ Disabled"
            spam_st = "✅ Enabled" if settings["anti_spam_enabled"] else "❌ Disabled"
            flood_st = "✅ Enabled" if settings["flood_detection_enabled"] else "❌ Disabled"
            warn_st = "✅ Enabled" if settings["warning_system_enabled"] else "❌ Disabled"
            restr_st = "✅ Enabled" if settings["auto_restrict_enabled"] else "❌ Disabled"
            fwd_st = "✅ Enabled" if settings.get("anti_forward_enabled", False) else "❌ Disabled"
            raid_st = "🚨 Active" if settings.get("raid_mode_enabled", False) else "⚪ Inactive"

            text = (
                f"⚙️ <b>Feature Status: {c_title}</b>\n\n"
                f"• Anti-Link: {link_st}\n"
                f"• Anti-Spam: {spam_st}\n"
                f"• Flood Detection: {flood_st}\n"
                f"• Warning System: {warn_st}\n"
                f"• Auto-Restriction: {restr_st}\n"
                f"• Anti-Forward: {fwd_st}\n"
                f"• Raid Lockdown: {raid_st}\n\n"
                f"⏱ Spam Window: <code>{settings['spam_window_seconds']}s</code>\n"
                f"⚠️ Warning Limit: <code>{settings['warning_limit']}</code>"
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
            await query.answer("Executed /features")
            return

        elif cmd_name == "stats":
            stats = get_group_stats(target_chat_id)
            c_title = html.escape(chat.title or stats.get("chat_title") or "Group") if chat else "Group"
            text = (
                f"📊 <b>Moderation Statistics: {c_title}</b>\n"
                f"🆔 <b>Chat ID:</b> <code>{target_chat_id}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔍 Messages Checked: <b>{stats['total_messages_checked']}</b>\n"
                f"🔗 Links Deleted: <b>{stats['links_deleted']}</b>\n"
                f"🚫 Spam Deleted: <b>{stats['spam_deleted']}</b>\n"
                f"⚠️ Warnings Issued: <b>{stats['warnings_issued']}</b>\n"
                f"⛔️ Restrictions: <b>{stats['restrictions_applied']}</b>\n"
                f"🔨 Members Banned: <b>{stats.get('banned_members', 0)}</b>\n"
                f"⏩ Forwards Deleted: <b>{stats.get('forwards_deleted', 0)}</b>"
            )
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
            await query.answer("Executed /stats")
            return

        elif cmd_name == "logs":
            logs = get_recent_moderation_logs(target_chat_id, limit=8)
            if not logs:
                text = "📋 <b>Recent Moderation Audit Logs</b>\n\nNo moderation actions have been recorded yet for this group."
            else:
                text = "📋 <b>Recent Moderation Audit Logs</b>\n\n"
                for entry in logs:
                    dt = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc).strftime("%m-%d %H:%M")
                    action = html.escape(entry["action"])
                    details = html.escape(entry["details"])
                    uid = entry["user_id"]
                    text += f"• <code>[{dt}]</code> <b>{action}</b> (User: <code>{uid}</code>)\n  <i>{details}</i>\n"

            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
            await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
            await query.answer("Executed /logs")
            return

        elif cmd_name == "antlink_status":
            st = get_group_settings(target_chat_id)["anti_link_enabled"]
            status_text = "ENABLED 🟢" if st else "DISABLED 🔴"
            await query.answer(f"Anti-Link is currently {status_text}", show_alert=True)
            return

        elif cmd_name == "antibiolink_status":
            st = get_group_settings(target_chat_id).get("anti_bio_link_enabled", True)
            status_text = "ENABLED 🟢" if st else "DISABLED 🔴"
            await query.answer(f"Anti-Bio-Link is currently {status_text}", show_alert=True)
            return

        elif cmd_name == "cleanservice_status":
            st = get_group_settings(target_chat_id).get("clean_service_enabled", True)
            status_text = "ENABLED 🟢" if st else "DISABLED 🔴"
            await query.answer(f"Clean Service Messages is currently {status_text}", show_alert=True)
            return

        elif cmd_name == "antispam_status":
            st = get_group_settings(target_chat_id)["anti_spam_enabled"]
            status_text = "ENABLED 🟢" if st else "DISABLED 🔴"
            await query.answer(f"Anti-Spam is currently {status_text}", show_alert=True)
            return

        elif cmd_name in ("unmute", "ban", "unban", "warnings", "resetwarnings"):
            # Check if clicked query message is a reply to someone
            replied = query.message.reply_to_message if query.message else None
            if not replied or not replied.from_user:
                text = (
                    f"ℹ️ <b>How to use /{html.escape(cmd_name)}:</b>\n\n"
                    f"To perform this moderation action on a member:\n"
                    f"• Reply to the member's message with <code>/{html.escape(cmd_name)}</code>\n"
                    f"• Or run <code>/{html.escape(cmd_name)} &lt;user_id&gt;</code> in the chat."
                )
                back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
                await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
                await query.answer(f"Usage for /{cmd_name}")
                return

            target_user = replied.from_user
            t_name = html.escape(target_user.first_name or str(target_user.id))

            if cmd_name == "warnings":
                active_incident = get_active_incident(chat.id, target_user.id)
                historical_restrictions = get_user_restrictions(chat.id, target_user.id)
                total_db_warnings = get_user_warnings_count(chat.id, target_user.id)

                warn_lines = [f"📊 <b>Warning Status for {t_name}</b> (<code>{target_user.id}</code>)\n"]
                if active_incident and active_incident["count"] > 1:
                    warn_count = active_incident["count"] - 1
                    warn_lines.append(f"⚠️ <b>Active Spam Warnings:</b> {warn_count}/2")
                else:
                    warn_lines.append("✅ <b>Active Spam Warnings:</b> 0 (Clean)")
                warn_lines.append(f"📝 <b>Total Recorded Violations:</b> {total_db_warnings}")
                if historical_restrictions:
                    warn_lines.append(f"\n📜 <b>Past Restrictions ({len(historical_restrictions)}):</b>")
                    for r in historical_restrictions[:3]:
                        dt = datetime.fromtimestamp(r["restricted_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                        warn_lines.append(f"• <code>{dt}</code> - {r['action'].upper()} - {html.escape(r['reason'])}")
                else:
                    warn_lines.append("📜 <b>Restriction History:</b> None")

                back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])
                await query.edit_message_text("\n".join(warn_lines), reply_markup=back_kb, parse_mode=ParseMode.HTML)
                await query.answer(f"Warnings for {t_name}")
                return

            elif cmd_name == "unmute":
                can_del, can_restr = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
                if can_restr:
                    unrestricted = ChatPermissions(
                        can_send_messages=True, can_send_audios=True, can_send_documents=True,
                        can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                        can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                        can_add_web_page_previews=True,
                    )
                    await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_user.id, permissions=unrestricted)
                    log_moderation_event(chat.id, user.id, "UNMUTE", f"User: {target_user.id}")
                    await query.edit_message_text(f"🔊 <b>{t_name}</b> has been unmuted.", parse_mode=ParseMode.HTML)
                    await query.answer("User unmuted.")
                else:
                    await query.answer("⚠️ Bot lacks Restrict Members permission.", show_alert=True)
                return

            elif cmd_name == "ban":
                can_del, can_restr = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
                if can_restr:
                    await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user.id)
                    increment_stat(chat.id, "banned_members", count=1)
                    log_moderation_event(chat.id, user.id, "BAN", f"User: {target_user.id}")
                    await query.edit_message_text(f"🔨 <b>{t_name}</b> has been banned from the group.", parse_mode=ParseMode.HTML)
                    await query.answer("User banned.")
                else:
                    await query.answer("⚠️ Bot lacks Ban Users permission.", show_alert=True)
                return

            elif cmd_name == "unban":
                await context.bot.unban_chat_member(chat_id=chat.id, user_id=target_user.id, only_if_banned=True)
                log_moderation_event(chat.id, user.id, "UNBAN", f"User: {target_user.id}")
                await query.edit_message_text(f"✅ <b>{t_name}</b> has been unbanned.", parse_mode=ParseMode.HTML)
                await query.answer("User unbanned.")
                return

            elif cmd_name == "resetwarnings":
                reset_user_warnings(chat.id, target_user.id)
                clear_active_incident(chat.id, target_user.id)
                log_moderation_event(chat.id, user.id, "RESET_WARNINGS", f"User: {target_user.id}")
                await query.edit_message_text(f"✅ All warnings cleared for <b>{t_name}</b>.", parse_mode=ParseMode.HTML)
                await query.answer("Warnings reset.")
                return

    # -------------------------------------------------------------------------
    # Execute Option Actions (Sub-Command Selections)
    # -------------------------------------------------------------------------
    elif action_type == "exec" and len(parts) >= 5:
        cmd_name = parts[3]
        sub_arg = parts[4]

        # Verify admin permissions
        if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            is_admin = (user and is_bot_owner(user.id)) or await is_sender_admin_or_owner(chat, user, None, context.bot)
            if not is_admin:
                await query.answer("⛔ You need administrator privileges to use this command.", show_alert=True)
                return

        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Commands", callback_data=f"cmd:{target_chat_id}:main")]])

        # /antlink on|off
        if cmd_name == "antlink":
            val = (sub_arg == "on")
            set_group_anti_link(target_chat_id, val)
            log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Anti-Link set to {sub_arg.upper()}")
            st_text = "ENABLED" if val else "DISABLED"
            await query.edit_message_text(
                f"✅ <b>Anti-Link Protection</b> has been <b>{st_text}</b> for this group.",
                reply_markup=back_kb,
                parse_mode=ParseMode.HTML,
            )
            await query.answer(f"Anti-Link {st_text}")
            return

        # /antibiolink on|off
        elif cmd_name == "antibiolink":
            val = (sub_arg == "on")
            from database import set_group_anti_bio_link
            set_group_anti_bio_link(target_chat_id, val)
            log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Anti-Bio-Link set to {sub_arg.upper()}")
            st_text = "ENABLED" if val else "DISABLED"
            await query.edit_message_text(
                f"✅ <b>Anti-Bio-Link Protection</b> has been <b>{st_text}</b> for this group.",
                reply_markup=back_kb,
                parse_mode=ParseMode.HTML,
            )
            await query.answer(f"Anti-Bio-Link {st_text}")
            return

        # /cleanservice on|off
        elif cmd_name == "cleanservice":
            val = (sub_arg == "on")
            from database import set_group_clean_service
            set_group_clean_service(target_chat_id, val)
            log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Clean Service set to {sub_arg.upper()}")
            st_text = "ENABLED" if val else "DISABLED"
            await query.edit_message_text(
                f"✅ <b>Clean Service Messages</b> has been <b>{st_text}</b> for this group.",
                reply_markup=back_kb,
                parse_mode=ParseMode.HTML,
            )
            await query.answer(f"Clean Service {st_text}")
            return

        # /antispam on|off
        elif cmd_name == "antispam":
            val = (sub_arg == "on")
            set_group_anti_spam(target_chat_id, val)
            log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Anti-Spam set to {sub_arg.upper()}")
            st_text = "ENABLED" if val else "DISABLED"
            await query.edit_message_text(
                f"✅ <b>Anti-Spam Protection</b> has been <b>{st_text}</b> for this group.",
                reply_markup=back_kb,
                parse_mode=ParseMode.HTML,
            )
            await query.answer(f"Anti-Spam {st_text}")
            return

        # /raid on|off
        elif cmd_name == "raid":
            val = (sub_arg == "on")
            update_group_feature(target_chat_id, "raid_mode_enabled", val)
            log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Raid Mode set to {sub_arg.upper()}")
            if val:
                await query.edit_message_text(
                    "🚨 <b>Emergency Raid Mode has been ENABLED!</b>\n\nHigh-alert lockdown active. Use <code>/raid off</code> to restore normal mode.",
                    reply_markup=back_kb,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await query.edit_message_text(
                    "✅ <b>Emergency Raid Mode has been DISABLED.</b> Normal group moderation restored.",
                    reply_markup=back_kb,
                    parse_mode=ParseMode.HTML,
                )
            await query.answer(f"Raid mode {sub_arg}")
            return

        # /enable <feature>
        elif cmd_name == "enable":
            feat_col_map = {
                "antilink": "anti_link_enabled",
                "antispam": "anti_spam_enabled",
                "flood": "flood_detection_enabled",
                "warnings": "warning_system_enabled",
                "autorestrict": "auto_restrict_enabled",
                "antiforward": "anti_forward_enabled",
                "antijoin": "anti_join_spam_enabled",
                "antibot": "anti_bot_enabled",
                "media": "media_restrictions_enabled",
                "raid": "raid_mode_enabled",
            }
            col = feat_col_map.get(sub_arg)
            if col:
                update_group_feature(target_chat_id, col, True)
                log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Enabled {sub_arg}")
                await query.edit_message_text(
                    f"✅ <b>{html.escape(sub_arg.title())} Protection</b> has been <b>enabled</b> for this group.",
                    reply_markup=back_kb,
                    parse_mode=ParseMode.HTML,
                )
                await query.answer(f"Enabled {sub_arg}")
            return

        # /disable <feature>
        elif cmd_name == "disable":
            feat_col_map = {
                "antilink": "anti_link_enabled",
                "antispam": "anti_spam_enabled",
                "flood": "flood_detection_enabled",
                "warnings": "warning_system_enabled",
                "autorestrict": "auto_restrict_enabled",
                "antiforward": "anti_forward_enabled",
                "antijoin": "anti_join_spam_enabled",
                "antibot": "anti_bot_enabled",
                "media": "media_restrictions_enabled",
                "raid": "raid_mode_enabled",
            }
            col = feat_col_map.get(sub_arg)
            if col:
                update_group_feature(target_chat_id, col, False)
                log_moderation_event(target_chat_id, user.id, "CONFIG_CHANGE", f"Disabled {sub_arg}")
                await query.edit_message_text(
                    f"❌ <b>{html.escape(sub_arg.title())} Protection</b> has been <b>disabled</b> for this group.",
                    reply_markup=back_kb,
                    parse_mode=ParseMode.HTML,
                )
                await query.answer(f"Disabled {sub_arg}")
            return

        # /whitelist options
        elif cmd_name == "whitelist":
            if sub_arg == "list":
                domains = get_whitelisted_domains(target_chat_id)
                if not domains:
                    text = "🌐 <b>Link Whitelist</b>\n\nNo domains are currently whitelisted for this group."
                else:
                    text = f"🌐 <b>Whitelisted Domains ({len(domains)}):</b>\n\n"
                    for d in domains:
                        text += f"• <code>{html.escape(d)}</code>\n"
                await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
                await query.answer()
                return
            elif sub_arg.startswith("add_"):
                domain_map = {
                    "add_google": "google.com",
                    "add_youtube": "youtube.com",
                    "add_tme": "t.me",
                    "add_github": "github.com",
                }
                dom = domain_map.get(sub_arg)
                if dom:
                    add_whitelisted_domain(target_chat_id, dom, added_by=user.id)
                    log_moderation_event(target_chat_id, user.id, "WHITELIST_ADD", f"Added: {dom}")
                    await query.edit_message_text(
                        f"✅ Domain <code>{html.escape(dom)}</code> added to whitelist.",
                        reply_markup=back_kb,
                        parse_mode=ParseMode.HTML,
                    )
                    await query.answer(f"Added {dom}")
                return

        # /blacklist options
        elif cmd_name == "blacklist":
            if sub_arg == "list":
                patterns = get_blacklisted_patterns(target_chat_id)
                if not patterns:
                    text = "🚫 <b>Content Blacklist</b>\n\nNo patterns are currently blacklisted."
                else:
                    text = f"🚫 <b>Blacklisted Patterns ({len(patterns)}):</b>\n\n"
                    for p in patterns:
                        text += f"• <code>{html.escape(p)}</code>\n"
                await query.edit_message_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
                await query.answer()
                return
            elif sub_arg.startswith("add_"):
                pattern_map = {
                    "add_crypto": "free crypto",
                    "add_invest": "invest now",
                }
                pat = pattern_map.get(sub_arg)
                if pat:
                    add_blacklisted_pattern(target_chat_id, pat, added_by=user.id)
                    log_moderation_event(target_chat_id, user.id, "BLACKLIST_ADD", f"Added: {pat}")
                    await query.edit_message_text(
                        f"✅ Pattern <code>{html.escape(pat)}</code> added to blacklist.",
                        reply_markup=back_kb,
                        parse_mode=ParseMode.HTML,
                    )
                    await query.answer(f"Added {pat}")
                return

        # /mute <duration>
        elif cmd_name == "mute":
            replied = query.message.reply_to_message if query.message else None
            duration_seconds = {
                "10m": 600,
                "1h": 3600,
                "2h": 7200,
                "1d": 86400,
                "7d": 604800,
            }.get(sub_arg, 86400)

            if replied and replied.from_user:
                target_user = replied.from_user
                t_name = html.escape(target_user.first_name or str(target_user.id))
                can_del, can_restr = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
                if can_restr:
                    no_send = ChatPermissions(
                        can_send_messages=False, can_send_audios=False, can_send_documents=False,
                        can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
                        can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
                        can_add_web_page_previews=False,
                    )
                    await context.bot.restrict_chat_member(
                        chat_id=chat.id,
                        user_id=target_user.id,
                        permissions=no_send,
                        until_date=int(time.time()) + duration_seconds,
                    )
                    record_restriction(
                        chat_id=chat.id, user_id=target_user.id, username=target_user.username,
                        reason=f"Muted via help menu ({sub_arg})", restricted_at=time.time(),
                        expires_at=time.time() + duration_seconds,
                    )
                    increment_stat(chat.id, "restrictions_applied", count=1)
                    log_moderation_event(chat.id, user.id, "MUTE", f"User: {target_user.id}, Duration: {sub_arg}")
                    await query.edit_message_text(f"🔇 <b>{t_name}</b> has been muted for <b>{sub_arg}</b>.", parse_mode=ParseMode.HTML)
                    await query.answer(f"Muted for {sub_arg}")
                else:
                    await query.answer("⚠️ Bot lacks Restrict Members permission.", show_alert=True)
            else:
                await query.answer(
                    f"ℹ️ Selected duration: {sub_arg}.\nTo mute someone, reply to their message with /mute {sub_arg} or run /mute <user_id> {sub_arg}",
                    show_alert=True,
                )
            return


# =============================================================================
# Command Handler & Registration
# =============================================================================

async def interactive_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help by displaying the interactive Help & Commands menu with clickable buttons."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    is_private = (chat.type == ChatType.PRIVATE)
    text, markup = build_main_help_markup(chat.id, is_private=is_private)
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


def register_help_menu_handlers(application: Application) -> None:
    """Register /help command and cmd:* callback handlers."""
    application.add_handler(CommandHandler("help", interactive_help_command), group=0)
    application.add_handler(CallbackQueryHandler(help_callback_handler, pattern=r"^cmd:"), group=0)
