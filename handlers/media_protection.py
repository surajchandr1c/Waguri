import logging
from telegram import Message, Update
from telegram.constants import ChatType
from telegram.error import BadRequest, Forbidden
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from database import get_group_settings, get_media_restrictions, increment_stat, log_moderation_event
from handlers.admin_check import check_bot_permissions, is_sender_admin_or_owner

logger = logging.getLogger("Waguri.MediaProtection")


def identify_media_type(message: Message) -> str | None:
    """Identify the category of media contained in the message."""
    if message.photo:
        return "photos"
    if message.video:
        return "videos"
    if message.document:
        return "documents"
    if message.sticker:
        return "stickers"
    if message.animation:
        return "gifs"
    if message.voice:
        return "voice"
    if message.video_note:
        return "video_notes"
    return None


async def handle_media_restrictions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect and restrict prohibited media types based on per-group configuration."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    media_type = identify_media_type(message)
    if not media_type:
        return

    settings = get_group_settings(chat.id)
    if not settings.get("is_active", True) or not settings.get("media_restrictions_enabled", False):
        return

    # Check sender exemption
    sender = update.effective_user
    sender_chat = getattr(message, "sender_chat", None)
    is_protected = await is_sender_admin_or_owner(chat, sender, sender_chat, context.bot)
    if is_protected:
        return

    # Check if this media type is permitted
    allowed_types = settings.get("allowed_media_types", {})
    is_allowed = allowed_types.get(media_type, True)
    if is_allowed:
        return

    # Prohibited media detected
    chat_title = chat.title or "Unnamed Group"
    user_info = f"@{sender.username} (ID: {sender.id})" if sender and sender.username else f"User {sender.id if sender else 'Unknown'}"

    logger.info(
        "[MEDIA RESTRICTED] Group '%s' (ID: %s) | User: %s | Prohibited Media: %s",
        chat_title,
        chat.id,
        user_info,
        media_type,
    )

    can_delete, _ = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=False)
    if can_delete:
        try:
            await message.delete()
            increment_stat(chat.id, "media_deleted", count=1, chat_title=chat_title)
            log_moderation_event(
                chat.id,
                sender.id if sender else 0,
                "MEDIA_DELETED",
                f"Deleted prohibited media: {media_type}",
            )
        except Exception as exc:
            logger.error("[MEDIA DELETE ERROR] Could not delete message %s in %s: %s", message.message_id, chat.id, exc)


def register_media_protection_handlers(application: Application) -> None:
    """Register media restrictions handler in group 3."""
    media_filter = (
        filters.PHOTO
        | filters.VIDEO
        | filters.Document.ALL
        | filters.Sticker.ALL
        | filters.ANIMATION
        | filters.VOICE
        | filters.VIDEO_NOTE
    )
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & media_filter, handle_media_restrictions),
        group=3,
    )
