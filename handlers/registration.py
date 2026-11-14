import logging
from telegram import ChatMember, Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import Application, ChatMemberHandler, ContextTypes

from config import GROUP_WELCOME_MSG
from database import register_or_update_chat, set_chat_active
from handlers.admin_check import invalidate_cache

logger = logging.getLogger("Waguri.Registration")


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle bot membership transitions (added, promoted, demoted, kicked, left)
    for groups, supergroups, and channels.
    """
    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return

    chat = my_chat_member.chat
    old_member = my_chat_member.old_chat_member
    new_member = my_chat_member.new_chat_member

    old_status = old_member.status
    new_status = new_member.status
    chat_type = chat.type
    chat_title = chat.title or "Unnamed Chat"

    logger.info(
        "[MEMBERSHIP UPDATE] Chat: '%s' (ID: %s, Type: %s) | Status transition: %s -> %s",
        chat_title,
        chat.id,
        chat_type,
        old_status,
        new_status,
    )

    # Invalidate cached admin list whenever the bot's own status changes
    invalidate_cache(chat.id)

    # -------------------------------------------------------------------------
    # Case 1: Bot was removed / kicked / left the chat
    # -------------------------------------------------------------------------
    if new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        logger.info(
            "[BOT REMOVED] Marked chat '%s' (ID: %s) as inactive in database.",
            chat_title,
            chat.id,
        )
        set_chat_active(chat.id, is_active=False)
        return

    # -------------------------------------------------------------------------
    # Case 2: Bot added to a group or supergroup
    # -------------------------------------------------------------------------
    if chat_type in (ChatType.GROUP, ChatType.SUPERGROUP):
        was_not_member = old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
        is_now_member = new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)

        if was_not_member and is_now_member:
            # Register group in DB with default settings and active status
            register_or_update_chat(chat.id, chat_title, chat_type, is_active=True)
            logger.info(
                "[GROUP REGISTERED] Initialized default moderation config for group '%s' (ID: %s).",
                chat_title,
                chat.id,
            )

            # Send introduction greeting to the group
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=GROUP_WELCOME_MSG,
                )
                logger.info("[WELCOME SENT] Dispatched welcome greeting to group '%s' (ID: %s).", chat_title, chat.id)
            except TelegramError as exc:
                logger.warning(
                    "[WELCOME FAILED] Could not send welcome greeting to group '%s' (ID: %s): %s",
                    chat_title,
                    chat.id,
                    exc,
                )
        elif is_now_member:
            # Bot promoted to administrator or permissions updated
            register_or_update_chat(chat.id, chat_title, chat_type, is_active=True)
            logger.info(
                "[GROUP PERMISSIONS UPDATED] Updated status for group '%s' (ID: %s) to %s.",
                chat_title,
                chat.id,
                new_status,
            )

    # -------------------------------------------------------------------------
    # Case 3: Bot added to a channel
    # -------------------------------------------------------------------------
    elif chat_type == ChatType.CHANNEL:
        if new_status == ChatMemberStatus.ADMINISTRATOR:
            register_or_update_chat(chat.id, chat_title, "channel", is_active=True)
            logger.info(
                "[CHANNEL REGISTERED] Initialized default moderation config for channel '%s' (ID: %s).",
                chat_title,
                chat.id,
            )


def register_registration_handlers(application: Application) -> None:
    """Register the ChatMemberHandler for tracking bot addition and removal."""
    application.add_handler(
        ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER),
        group=0,
    )
