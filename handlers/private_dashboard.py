import html
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from config import BOT_OWNER_IDS
from database import get_group_settings, get_group_stats, get_registered_chats
from handlers.admin_check import is_sender_admin_or_owner

logger = logging.getLogger("Waguri.PrivateDashboard")


def build_private_start_markup(bot_username: str = "Ms_Waguri_bot") -> tuple[str, InlineKeyboardMarkup]:
    """Construct the private dashboard welcome message and 8 required inline buttons."""
    text = (
        "👑 <b>Welcome to Waguri Management Platform!</b>\n\n"
        "Waguri is an advanced multi-group and multi-channel Telegram moderation and management bot.\n\n"
        "<b>Key Features:</b>\n"
        "• 🔗 Automatic Anti-Link & Whitelist Protection\n"
        "• 🛡️ Anti-Spam (Progressive Warnings & 24h Mute)\n"
        "• 🌊 Flood & Burst Message Detection\n"
        "• 🚫 Anti-Forward & Anti-Bot Protection\n"
        "• 📸 Granular Media Restrictions\n"
        "• 🚨 Emergency Raid Protection\n"
        "• 📊 Real-Time Statistics & Audit Logs\n\n"
        "<i>Select an option below to manage your chats or learn more:</i>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Waguri to Group",
                url=f"https://t.me/{bot_username}?startgroup=true",
            ),
            InlineKeyboardButton(
                "📢 Add Waguri to Channel",
                url=f"https://t.me/{bot_username}?startchannel=true",
            ),
        ],
        [
            InlineKeyboardButton("👥 My Groups", callback_data="pvt:my_groups"),
            InlineKeyboardButton("📢 My Channels", callback_data="pvt:my_channels"),
        ],
        [
            InlineKeyboardButton("📖 Help & Commands", callback_data="pvt:help"),
            InlineKeyboardButton("ℹ️ About Waguri", callback_data="pvt:about"),
        ],
        [
            InlineKeyboardButton("💬 Contact Support", callback_data="pvt:contact"),
            InlineKeyboardButton("⚡ Bot Features", callback_data="pvt:features"),
        ],
        [
            InlineKeyboardButton("💼 Personal Auto-Reply", callback_data="pvt:personal"),
        ],
    ]

    return text, InlineKeyboardMarkup(keyboard)


async def handle_private_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle navigation callbacks within the private dashboard."""
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    data = query.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "main":
        bot_user = await context.bot.get_me()
        text, markup = build_private_start_markup(bot_user.username or "Ms_Waguri_bot")
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "personal":
        from handlers.personal_autoreply import build_personal_settings_markup
        text, markup = build_personal_settings_markup(user.id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "my_groups":
        # Find all registered groups where this user is verified server-side as admin/owner
        registered = get_registered_chats(chat_type="group", active_only=True)
        admin_groups = []

        for chat_row in registered:
            cid = chat_row["chat_id"]
            try:
                member = await context.bot.get_chat_member(chat_id=cid, user_id=user.id)
                if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                    admin_groups.append((cid, chat_row.get("chat_title") or f"Group {cid}"))
            except Exception:
                continue

        if not admin_groups:
            text = (
                "👥 <b>My Administered Groups</b>\n\n"
                "You do not administer any registered groups yet.\n\n"
                "To get started, add @Ms_Waguri_bot to your group and promote it to administrator!"
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        "➕ Add Waguri to Group",
                        url=f"https://t.me/{context.bot.username}?startgroup=true",
                    )
                ],
                [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")],
            ]
        else:
            text = (
                f"👥 <b>Your Administered Groups ({len(admin_groups)})</b>\n\n"
                "Select a group below to view its moderation settings and statistics:"
            )
            keyboard = []
            for cid, title in admin_groups:
                keyboard.append([InlineKeyboardButton(f"⚙️ {title}", callback_data=f"pvt:view_group:{cid}")])
            keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "my_channels":
        registered = get_registered_chats(chat_type="channel", active_only=True)
        admin_channels = []

        for chat_row in registered:
            cid = chat_row["chat_id"]
            try:
                member = await context.bot.get_chat_member(chat_id=cid, user_id=user.id)
                if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                    admin_channels.append((cid, chat_row.get("chat_title") or f"Channel {cid}"))
            except Exception:
                continue

        if not admin_channels:
            text = (
                "📢 <b>My Administered Channels</b>\n\n"
                "You do not administer any registered channels yet.\n\n"
                "Add @Ms_Waguri_bot to your channel as an administrator to enable anti-link protection!"
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📢 Add Waguri to Channel",
                        url=f"https://t.me/{context.bot.username}?startchannel=true",
                    )
                ],
                [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")],
            ]
        else:
            text = (
                f"📢 <b>Your Administered Channels ({len(admin_channels)})</b>\n\n"
                "Select a channel below to view its moderation settings and statistics:"
            )
            keyboard = []
            for cid, title in admin_channels:
                keyboard.append([InlineKeyboardButton(f"📢 {title}", callback_data=f"pvt:view_group:{cid}")])
            keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "view_group" and len(parts) >= 3:
        target_cid = int(parts[2])
        # Server-side verification: Re-verify that user is admin in target_cid
        try:
            member = await context.bot.get_chat_member(chat_id=target_cid, user_id=user.id)
            if member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                await query.answer("⛔ Access denied: You are not an administrator of this chat.", show_alert=True)
                return
        except Exception:
            await query.answer("⛔ Could not verify administrative rights in this chat.", show_alert=True)
            return

        settings = get_group_settings(target_cid)
        stats = get_group_stats(target_cid)
        chat_title = html.escape(settings.get("chat_title") or str(target_cid))

        link_st = "🟢 ON" if settings["anti_link_enabled"] else "🔴 OFF"
        spam_st = "🟢 ON" if settings["anti_spam_enabled"] else "🔴 OFF"
        flood_st = "🟢 ON" if settings["flood_detection_enabled"] else "🔴 OFF"
        warn_st = "🟢 ON" if settings["warning_system_enabled"] else "🔴 OFF"
        restr_st = "🟢 ON" if settings["auto_restrict_enabled"] else "🔴 OFF"
        fwd_st = "🟢 ON" if settings["anti_forward_enabled"] else "🔴 OFF"
        raid_st = "🚨 ACTIVE" if settings["raid_mode_enabled"] else "⚪ Normal"

        text = (
            f"⚙️ <b>Management Summary: {chat_title}</b>\n"
            f"🆔 <b>ID:</b> <code>{target_cid}</code> | <b>Type:</b> {settings['chat_type']}\n\n"
            f"<b>Protection Status:</b>\n"
            f"• Anti-Link: {link_st}\n"
            f"• Anti-Spam: {spam_st}\n"
            f"• Flood Detection: {flood_st}\n"
            f"• Warning System: {warn_st}\n"
            f"• Auto-Restriction: {restr_st}\n"
            f"• Anti-Forward: {fwd_st}\n"
            f"• Raid Emergency Mode: {raid_st}\n\n"
            f"<b>Statistics:</b>\n"
            f"• Messages Checked: {stats['total_messages_checked']}\n"
            f"• Links Deleted: {stats['links_deleted']}\n"
            f"• Spam Deleted: {stats['spam_deleted']}\n"
            f"• Warnings: {stats['warnings_issued']} | Restrictions: {stats['restrictions_applied']}\n\n"
            f"<i>To configure toggles, run <code>/settings</code> directly inside the group.</i>"
        )

        keyboard = [
            [InlineKeyboardButton("⬅️ Back to My Chats", callback_data="pvt:my_groups")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="pvt:main")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "help":
        from handlers.help_menu import build_main_help_markup
        text, markup = build_main_help_markup(0, is_private=True)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "about":
        text = (
            "ℹ️ <b>About Waguri</b>\n\n"
            "Waguri (@Ms_Waguri_bot) is an advanced, enterprise-grade Telegram group and channel "
            "moderation platform built with Python.\n\n"
            "It empowers communities with automated protection against spam, links, flood bursts, "
            "malicious bots, forwards, and raids while keeping every group strictly isolated."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "contact":
        text = (
            "💬 <b>Contact Support</b>\n\n"
            "For inquiries, support, or partnership requests regarding Waguri, please reach out to the bot "
            "administrator <b>@lucky_paji</b>."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif action == "features":
        text = (
            "⚡ <b>Waguri Feature Overview</b>\n\n"
            "• <b>Anti-Link Protection:</b> Deletes unauthorized URLs, Telegram invites, deep links, and caption links with whitelist support.\n"
            "• <b>Anti-Spam System:</b> 4-stage progressive sequence (allow $\\rightarrow$ warn 1 $\\rightarrow$ warn 2 $\\rightarrow$ 24h mute + cleanup).\n"
            "• <b>Flood Protection:</b> Monitors high-frequency burst messaging to keep chats peaceful.\n"
            "• <b>Media Restrictions:</b> Selectively allow or block photos, videos, documents, stickers, and voice notes.\n"
            "• <b>Anti-Forward & Anti-Bot:</b> Blocks forwarded channel spam and suspicious bot additions.\n"
            "• <b>Raid Mode:</b> One-click emergency lockdown during coordinated attacks."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="pvt:main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        await query.answer()
        return


def register_private_dashboard_handlers(application: Application) -> None:
    """Register callbacks for the private owner dashboard."""
    application.add_handler(CallbackQueryHandler(handle_private_callback, pattern=r"^pvt:"), group=0)
