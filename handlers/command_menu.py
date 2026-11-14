import logging
from telegram import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeDefault,
    MenuButtonCommands,
)
from telegram.ext import Application

logger = logging.getLogger("Waguri.CommandMenu")

# General commands available to all users (private chats and default scope)
DEFAULT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Start Waguri"),
    BotCommand("help", "View this help menu"),
    BotCommand("about", "About Waguri"),
    BotCommand("contact", "Contact support (@lucky_paji)"),
]

# Admin moderation commands displayed to group administrators
ADMIN_COMMANDS: list[BotCommand] = [
    BotCommand("settings", "Interactive moderation configuration dashboard"),
    BotCommand("features", "View status of all features in current group"),
    BotCommand("enable", "Enable a moderation feature"),
    BotCommand("disable", "Disable a moderation feature"),
    BotCommand("stats", "View moderation statistics for this chat"),
    BotCommand("logs", "Review recent moderation audit logs"),
    BotCommand("id", "View chat and user IDs"),
    BotCommand("whitelist", "Manage allowed domains"),
    BotCommand("blacklist", "Manage blocked patterns"),
    BotCommand("warnings", "View member warnings"),
    BotCommand("resetwarnings", "Clear user warnings"),
    BotCommand("mute", "Mute user (e.g. 10m, 2h, 1d)"),
    BotCommand("unmute", "Restore member messaging permissions"),
    BotCommand("ban", "Ban member from group"),
    BotCommand("unban", "Unban member"),
    BotCommand("antlink", "Toggle anti-link protection"),
    BotCommand("antibiolink", "Toggle bio link protection"),
    BotCommand("cleanservice", "Clean service messages (joins, leaves)"),
    BotCommand("antispam", "Toggle repeated-message spam detection"),
]


async def setup_command_menu(application: Application) -> None:
    """
    Synchronize Telegram bot command menus and menu buttons on startup.
    Registers:
      1. Default command menu (BotCommandScopeDefault)
      2. Group administrator command menu (BotCommandScopeAllChatAdministrators)
      3. Menu button (MenuButtonCommands)
    """
    bot = application.bot

    # 1. Register default commands for all users
    try:
        await bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeDefault())
        logger.info(
            "Default command menu registered successfully (%d commands).",
            len(DEFAULT_COMMANDS),
        )
    except Exception as exc:
        logger.error("Failed to register default command menu: %s", exc)

    # 2. Register group administrator commands
    try:
        await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeAllChatAdministrators())
        logger.info(
            "Group administrator command menu registered successfully (%d commands).",
            len(ADMIN_COMMANDS),
        )
    except Exception as exc:
        logger.error("Failed to register administrator command menu: %s", exc)

    # 3. Configure Telegram chat menu button
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Telegram chat menu button configured to open commands menu.")
    except Exception as exc:
        logger.error("Failed to configure chat menu button: %s", exc)
