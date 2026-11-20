import logging
from telegram import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    MenuButtonCommands,
)
from telegram.ext import Application

logger = logging.getLogger("Waguri.CommandMenu")

# Default commands fallback
DEFAULT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Start Waguri"),
    BotCommand("help", "View help and commands"),
    BotCommand("about", "About Waguri"),
    BotCommand("contact", "Contact support (@lucky_paji)"),
]

# Commands available to users in private chats
PRIVATE_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Start Waguri and open dashboard"),
    BotCommand("help", "View help menu"),
    BotCommand("about", "About Waguri"),
    BotCommand("contact", "Contact support (@lucky_paji)"),
]

# Commands available to regular members in group chats
GROUP_MEMBER_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Waguri group introduction"),
    BotCommand("help", "View bot commands"),
    BotCommand("about", "About Waguri"),
    BotCommand("contact", "Contact support"),
]

# Admin commands displayed to group administrators (Moderation & Group Management)
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
    BotCommand("abuse", "Abuse Detection & Auto-Moderation System"),
]


async def setup_command_menu(application: Application) -> None:
    """
    Synchronize Telegram bot command menus and menu buttons on startup.
    Registers:
      1. Default command menu (BotCommandScopeDefault)
      2. Private chats command menu (BotCommandScopeAllPrivateChats)
      3. Group chats member command menu (BotCommandScopeAllGroupChats)
      4. Group administrator command menu (BotCommandScopeAllChatAdministrators)
      5. Menu button (MenuButtonCommands)
    """
    bot = application.bot

    # 1. Register default commands
    try:
        await bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeDefault())
        logger.info("Default command menu registered (%d commands).", len(DEFAULT_COMMANDS))
    except Exception as exc:
        logger.error("Failed to register default command menu: %s", exc)

    # 2. Register private chat commands
    try:
        await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        logger.info("Private chat command menu registered (%d commands).", len(PRIVATE_COMMANDS))
    except Exception as exc:
        logger.error("Failed to register private chat command menu: %s", exc)

    # 3. Register group member commands
    try:
        await bot.set_my_commands(GROUP_MEMBER_COMMANDS, scope=BotCommandScopeAllGroupChats())
        logger.info("Group member command menu registered (%d commands).", len(GROUP_MEMBER_COMMANDS))
    except Exception as exc:
        logger.error("Failed to register group member command menu: %s", exc)

    # 4. Register admin commands
    try:
        await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeAllChatAdministrators())
        logger.info("Group administrator command menu registered (%d commands).", len(ADMIN_COMMANDS))
    except Exception as exc:
        logger.error("Failed to register admin command menu: %s", exc)

    # 5. Set persistent menu button
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Chat menu button synchronized.")
    except Exception as exc:
        logger.error("Failed to synchronize chat menu button: %s", exc)
