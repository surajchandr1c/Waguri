import asyncio
import html
import logging
import os
import time
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from database import get_db_path, get_global_bot_stats, get_registered_chats
from handlers.admin_check import is_bot_owner

logger = logging.getLogger("Waguri.BotOwner")


def format_uptime(seconds: float) -> str:
    """Format seconds into human-readable uptime string."""
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Super-admin bot owner dashboard (/owner)."""
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    # Restrict to configured BOT_OWNER_IDS
    if not is_bot_owner(user.id):
        await message.reply_text("⛔ You are not authorized to access bot-owner controls.")
        logger.warning("[UNAUTHORIZED BOT OWNER] User %s attempted /owner", user.id)
        return

    args = context.args or []

    # -------------------------------------------------------------------------
    # Sub-command: /owner broadcast <text>
    # -------------------------------------------------------------------------
    if args and args[0].lower() == "broadcast":
        if len(args) < 2:
            await message.reply_text("Usage: <code>/owner broadcast &lt;message text&gt;</code>", parse_mode=ParseMode.HTML)
            return

        broadcast_text = "📢 <b>Service Announcement from Waguri:</b>\n\n" + " ".join(args[1:])
        chats = get_registered_chats(active_only=True)
        status_msg = await message.reply_text(f"⏳ Broadcasting announcement to {len(chats)} active chats...")

        sent_count = 0
        fail_count = 0

        for c in chats:
            cid = c["chat_id"]
            try:
                await context.bot.send_message(chat_id=cid, text=broadcast_text, parse_mode=ParseMode.HTML)
                sent_count += 1
                # Rate-limiting sleep to prevent hitting Telegram API limits (max 30 msgs/sec)
                await asyncio.sleep(0.05)
            except TelegramError:
                fail_count += 1

        await status_msg.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n\n"
            f"• Successfully delivered: <b>{sent_count}</b>\n"
            f"• Failed/Blocked: <b>{fail_count}</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    # -------------------------------------------------------------------------
    # Sub-command: /owner emergency <feature> [on|off]
    # -------------------------------------------------------------------------
    if args and args[0].lower() == "emergency":
        if len(args) < 2:
            current_overrides = config.GLOBAL_EMERGENCY_OVERRIDES
            await message.reply_text(
                f"🚨 <b>Global Emergency Overrides:</b> <code>{current_overrides}</code>\n\n"
                "Usage: <code>/owner emergency &lt;feature&gt; [on|off]</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        feature_name = args[1].lower()
        if len(args) >= 3:
            enable_val = args[2].lower() in ("on", "true", "1")
            config.GLOBAL_EMERGENCY_OVERRIDES[feature_name] = enable_val
            await message.reply_text(
                f"🚨 Set global emergency override for <code>{feature_name}</code> to <b>{enable_val}</b>.",
                parse_mode=ParseMode.HTML,
            )
        else:
            config.GLOBAL_EMERGENCY_OVERRIDES.pop(feature_name, None)
            await message.reply_text(
                f"✅ Removed global emergency override for <code>{feature_name}</code>.",
                parse_mode=ParseMode.HTML,
            )
        return

    # -------------------------------------------------------------------------
    # Main /owner Status View
    # -------------------------------------------------------------------------
    stats = get_global_bot_stats()
    uptime_str = format_uptime(time.time() - getattr(config, "BOT_START_TIME", time.time()))
    db_file = get_db_path()
    db_size_kb = os.path.getsize(db_file) // 1024 if os.path.exists(db_file) else 0

    overrides_text = ", ".join(f"{k}={v}" for k, v in config.GLOBAL_EMERGENCY_OVERRIDES.items()) or "None"

    text = (
        "👑 <b>Waguri Super-Admin Owner Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Bot Uptime:</b> {uptime_str}\n"
        f"💾 <b>Database:</b> <code>{db_file}</code> ({db_size_kb} KB)\n"
        f"🚨 <b>Emergency Overrides:</b> <code>{overrides_text}</code>\n\n"
        "🌐 <b>Platform Scale:</b>\n"
        f"• Active Groups: <b>{stats['active_groups']}</b>\n"
        f"• Active Channels: <b>{stats['active_channels']}</b>\n"
        f"• Total Registered Chats: <b>{stats['total_registered_chats']}</b>\n\n"
        "📊 <b>Global Activity Metrics:</b>\n"
        f"• Total Messages Checked: <b>{stats['total_messages']}</b>\n"
        f"• Links Deleted: <b>{stats['total_links_deleted']}</b>\n"
        f"• Spam Messages Deleted: <b>{stats['total_spam_deleted']}</b>\n"
        f"• Warnings Issued: <b>{stats['total_warnings']}</b>\n"
        f"• Restrictions Applied: <b>{stats['total_restrictions']}</b>\n"
        f"• Members Banned: <b>{stats['total_bans']}</b>\n\n"
        "<b>Available Owner Commands:</b>\n"
        "• <code>/owner broadcast &lt;text&gt;</code> - Rate-limited announcement\n"
        "• <code>/owner emergency &lt;feature&gt; [on|off]</code> - Global override"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


def register_bot_owner_handlers(application: Application) -> None:
    """Register super-admin owner commands."""
    application.add_handler(CommandHandler("owner", owner_command), group=0)
