import logging
import time
from telegram import Chat, User
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
import config
from config import ADMIN_CACHE_TTL_SECONDS, BOT_OWNER_IDS

logger = logging.getLogger("Waguri.AdminCheck")

# In-memory cache for group administrators:
# chat_id -> (timestamp, set_of_admin_user_ids, owner_user_id)
_admin_cache: dict[int, tuple[float, set[int], int | None]] = {}

# In-memory cache for bot permissions:
# chat_id -> (timestamp, can_delete_messages, can_restrict_members)
_bot_perm_cache: dict[int, tuple[float, bool, bool]] = {}
ADMIN_CACHE_MAX_SIZE = 2000


def is_bot_owner(user_id: int | None) -> bool:
    """Check if the given Telegram user is a super-admin / bot owner configured in BOT_OWNER_IDS."""
    if not user_id:
        return False
    owners = getattr(config, "BOT_OWNER_IDS", set())
    return user_id in owners


async def get_group_admins(chat_id: int, bot) -> tuple[set[int], int | None]:
    """
    Retrieve and cache group administrator and owner user IDs.
    Returns (set_of_admin_and_owner_user_ids, owner_user_id).
    """
    now = time.time()
    if len(_admin_cache) >= ADMIN_CACHE_MAX_SIZE:
        expired = [cached_id for cached_id, (cached_at, _, _) in _admin_cache.items()
                   if now - cached_at >= ADMIN_CACHE_TTL_SECONDS]
        for cached_id in expired[:500]:
            _admin_cache.pop(cached_id, None)
    if chat_id in _admin_cache:
        cached_time, admin_ids, owner_id = _admin_cache[chat_id]
        if now - cached_time < ADMIN_CACHE_TTL_SECONDS:
            return admin_ids, owner_id

    try:
        admins = await bot.get_chat_administrators(chat_id=chat_id)
        admin_ids: set[int] = set()
        owner_id: int | None = None
        bot_can_delete = False
        bot_can_restrict = False

        for admin in admins:
            admin_ids.add(admin.user.id)
            if admin.status == ChatMemberStatus.OWNER:
                owner_id = admin.user.id

            if admin.user.id == bot.id:
                bot_can_delete = getattr(admin, "can_delete_messages", False)
                bot_can_restrict = getattr(admin, "can_restrict_members", False)

        _admin_cache[chat_id] = (now, admin_ids, owner_id)
        _bot_perm_cache[chat_id] = (now, bot_can_delete, bot_can_restrict)
        return admin_ids, owner_id
    except TelegramError as exc:
        logger.warning(
            "[ADMIN CACHE] Could not fetch administrator list for group %s: %s. Failing safely.",
            chat_id,
            exc,
        )
        if chat_id in _admin_cache:
            return _admin_cache[chat_id][1], _admin_cache[chat_id][2]
        return set(), None


async def is_sender_admin_or_owner(
    chat: Chat, user: User | None, sender_chat: Chat | None, bot
) -> bool:
    """
    Determine whether the sender is exempt from moderation actions and authorized for admin actions.
    Exempt entities:
      - The bot itself (Waguri)
      - The group owner
      - Group administrators
      - Anonymous group administrators and linked channels (sender_chat)
    Fails safely (returns True) if user status cannot be verified.
    """
    # 1. Never moderate the bot itself
    if user and user.id == bot.id:
        return True

    # 2. Anonymous group administrators send on behalf of the group/channel
    if sender_chat:
        return True

    # 3. If user object is missing, fail safely
    if not user:
        return True

    try:
        admin_ids, _ = await get_group_admins(chat.id, bot)
        if user.id in admin_ids:
            return True

        # Fallback to direct get_chat_member
        member = await bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            admin_ids.add(user.id)
            return True
        return False
    except Exception as exc:
        logger.warning(
            "[ADMIN CHECK] Could not verify membership for user %s in group '%s' (ID: %s): %s. "
            "Failing safely (keeping message).",
            user.id,
            chat.title,
            chat.id,
            exc,
        )
        return True


async def is_group_owner(chat: Chat, user: User | None, bot) -> bool:
    """Check if the user is the creator/owner of the group."""
    if not user:
        return False
    try:
        _, owner_id = await get_group_admins(chat.id, bot)
        if owner_id and user.id == owner_id:
            return True
        member = await bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def check_bot_permissions(
    chat: Chat, bot, need_delete: bool = True, need_restrict: bool = False
) -> tuple[bool, bool]:
    """Verify that Waguri has required permissions in the group."""
    now = time.time()
    chat_id = chat.id
    chat_title = chat.title or "Unnamed Group"

    if chat_id in _bot_perm_cache:
        cached_time, can_delete, can_restrict = _bot_perm_cache[chat_id]
        if now - cached_time < ADMIN_CACHE_TTL_SECONDS:
            if (need_delete and not can_delete) or (need_restrict and not can_restrict):
                _log_missing_permissions(chat_title, chat_id, need_delete, need_restrict, can_delete, can_restrict)
            return can_delete, can_restrict

    try:
        admins = await bot.get_chat_administrators(chat_id=chat_id)
        can_delete = False
        can_restrict = False
        for admin in admins:
            if admin.user.id == bot.id:
                can_delete = getattr(admin, "can_delete_messages", False)
                can_restrict = getattr(admin, "can_restrict_members", False)
                break

        _bot_perm_cache[chat_id] = (now, can_delete, can_restrict)
        if (need_delete and not can_delete) or (need_restrict and not can_restrict):
            _log_missing_permissions(chat_title, chat_id, need_delete, need_restrict, can_delete, can_restrict)
        return can_delete, can_restrict
    except TelegramError as exc:
        logger.warning(
            "[PERMISSION CHECK] Could not fetch bot permissions in group '%s' (ID: %s): %s",
            chat_title,
            chat_id,
            exc,
        )
        if chat_id in _bot_perm_cache:
            return _bot_perm_cache[chat_id][1], _bot_perm_cache[chat_id][2]
        return False, False
    except Exception as exc:
        logger.warning(
            "[PERMISSION CHECK ERROR] Could not verify bot permissions in group '%s' (ID: %s): %s",
            chat_title,
            chat_id,
            exc,
        )
        return False, False


def _log_missing_permissions(
    chat_title: str,
    chat_id: int,
    need_delete: bool,
    need_restrict: bool,
    has_delete: bool,
    has_restrict: bool,
) -> None:
    """Log specific actionable warning messages for missing bot permissions."""
    if need_delete and not has_delete:
        logger.warning(
            "[PERMISSION WARNING] Waguri lacks 'Delete Messages' permission in group '%s' (ID: %s).\n"
            "  >>> Fix: Open Group Settings -> Administrators -> Waguri -> Enable 'Delete Messages'.",
            chat_title,
            chat_id,
        )
    if need_restrict and not has_restrict:
        logger.warning(
            "[PERMISSION WARNING] Waguri lacks 'Restrict Members' permission in group '%s' (ID: %s).\n"
            "  >>> Fix: Open Group Settings -> Administrators -> Waguri -> Enable 'Ban Users / Restrict Members'.",
            chat_title,
            chat_id,
        )


def invalidate_cache(chat_id: int | None = None) -> None:
    """Invalidate cached administrator and permission records for a group or all groups."""
    if chat_id is None:
        _admin_cache.clear()
        _bot_perm_cache.clear()
    else:
        _admin_cache.pop(chat_id, None)
        _bot_perm_cache.pop(chat_id, None)


async def verify_group_or_channel_admin(update, bot) -> bool:
    """Validate that a command is issued in an authorized group or channel by an admin."""
    message = getattr(update, "effective_message", None)
    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)

    if not message or not chat:
        return False

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        await message.reply_text("This command can only be used in a group or channel.")
        return False

    sender_chat = getattr(message, "sender_chat", None)
    is_admin = await is_sender_admin_or_owner(chat, user, sender_chat, bot)
    if not is_admin:
        await message.reply_text("You need administrator privileges to use this command.")
        return False

    return True
