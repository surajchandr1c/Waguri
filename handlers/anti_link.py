import asyncio
import html
import logging
import re
import time
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType, MessageEntityType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from database import (
    add_blacklisted_pattern,
    add_user_warning,
    add_whitelisted_domain,
    get_blacklisted_patterns,
    get_group_settings,
    get_user_warnings_count,
    get_whitelisted_domains,
    increment_stat,
    is_content_blacklisted,
    is_domain_whitelisted,
    log_moderation_event,
    record_restriction,
    remove_blacklisted_pattern,
    remove_whitelisted_domain,
    run_db,
)
from handlers.admin_check import (
    check_bot_permissions,
    is_sender_admin_or_owner,
    verify_group_or_channel_admin,
)

logger = logging.getLogger("Waguri.AntiLink")

# Comprehensive URL detection regex pattern for text and media captions
URL_REGEX = re.compile(
    r"(?:"
    r"https?://[^\s<>\"\'\)]+|"  # http:// or https://
    r"ftp://[^\s<>\"\'\)]+|"  # ftp://
    r"tg://[^\s<>\"\'\)]+|"  # tg:// deep links
    r"www\.[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*[^\s<>\"\'\)]*|"  # www.domain...
    r"(?:t|telegram)\.me/[^\s<>\"\'\)]+|"  # t.me/... or telegram.me/...
    r"(?:t|telegram)\.dog/[^\s<>\"\'\)]+|"  # telegram.dog/...
    r"\b(?:[a-zA-Z0-9-]+\.)+"  # domain label(s)
    r"(?:com|net|org|edu|gov|mil|int|biz|info|name|pro|aero|coop|museum|"
    r"io|ai|co|xyz|me|app|dev|tech|site|online|live|shop|club|store|top|vip|"
    r"space|link|agency|world|today|news|cc|tv|ru|ua|uk|us|in|de|fr|cn|br|au|ca|nl|"
    r"eu|es|it|ch|se|no|fi|pl|cz|gr|tr|za|mx|ar|kr|jp|id|vn|ph|th|my|sg|hk|tw|ng|eg|sa|ae|pk|bd)"  # TLDs
    r"(?::\d+)?(?:/[^\s<>\"\'\)]*)?"  # Optional port and path/parameters
    r")",
    re.IGNORECASE,
)

# In-memory cache for user bio link checks: user_id -> (has_bio_link: bool, bio_url: str, cached_at: float)
_user_bio_cache: dict[int, tuple[bool, str, float]] = {}
BIO_CACHE_CLEAN_TTL = 300.0  # 5 minutes for clean bios
BIO_CACHE_VIOLATION_TTL = 60.0  # 1 minute for users with links (re-checked sooner once removed)
BIO_CACHE_MAX_SIZE = 2000


def invalidate_bio_cache(user_id: int | None = None) -> None:
    """Clear the bio cache for a specific user or entirely."""
    global _user_bio_cache
    if user_id is not None:
        _user_bio_cache.pop(user_id, None)
    else:
        _user_bio_cache.clear()


async def check_user_bio_link(user_id: int, bot: Application.bot) -> tuple[bool, str]:
    """
    Check whether a user's Telegram bio contains any links or URLs.
    Uses caching to avoid excessive Telegram API get_chat requests.
    Returns (has_link: bool, url_found: str).
    """
    now = time.time()
    if len(_user_bio_cache) >= BIO_CACHE_MAX_SIZE:
        expired = [
            cached_user_id
            for cached_user_id, (_, _, cached_at) in _user_bio_cache.items()
            if now - cached_at >= BIO_CACHE_CLEAN_TTL
        ]
        for cached_user_id in expired[:500]:
            _user_bio_cache.pop(cached_user_id, None)
    cached = _user_bio_cache.get(user_id)
    if cached:
        has_link, url, cached_at = cached
        ttl = BIO_CACHE_VIOLATION_TTL if has_link else BIO_CACHE_CLEAN_TTL
        if now - cached_at < ttl:
            return has_link, url

    try:
        chat_full = await bot.get_chat(user_id)
        bio = getattr(chat_full, "bio", None) or ""
        urls = URL_REGEX.findall(bio)
        if urls:
            found_url = urls[0]
            _user_bio_cache[user_id] = (True, found_url, now)
            return True, found_url

        _user_bio_cache[user_id] = (False, "", now)
        return False, ""
    except Exception as exc:
        logger.debug("[BIO CHECK] Could not retrieve bio for user %s: %s", user_id, exc)
        return False, ""


async def schedule_warning_cleanup(warning_message: Message, delay_seconds: int = 10) -> None:
    """Asynchronously delete a warning message after delay_seconds to keep the chat clean."""
    if delay_seconds <= 0:
        return
    await asyncio.sleep(delay_seconds)
    try:
        await warning_message.delete()
    except Exception as exc:
        logger.debug("[WARNING CLEANUP] Could not delete warning message: %s", exc)


async def dispatch_bio_link_violation(
    chat: Chat,
    sender: User,
    bio_url: str,
    context: ContextTypes.DEFAULT_TYPE,
    settings: dict,
    on_join: bool = False,
) -> bool:
    """
    Handle warning issuance or 24h restriction when a bio link is detected.
    Returns True if user was restricted, False otherwise.
    """
    user_name = html.escape(sender.first_name or sender.username or str(sender.id))
    cleanup_delay = settings.get("warning_delete_after_seconds", 10)
    chat_title = chat.title or "Unnamed Group"

    warnings_count = get_user_warnings_count(chat.id, sender.id)
    warning_limit = settings.get("warning_limit", 2)
    if settings.get("auto_restrict_enabled", True) and warnings_count >= warning_limit:
        _, can_restrict = await check_bot_permissions(chat, context.bot, need_delete=False, need_restrict=True)
        if can_restrict:
            from handlers.anti_spam import restrict_user_24h
            restr_duration = settings.get("restriction_duration_seconds", 86400)
            await restrict_user_24h(chat, sender, context.bot, duration_seconds=restr_duration)
            increment_stat(chat.id, "restrictions_applied", count=1, chat_title=chat_title)
            reason_suffix = " on join" if on_join else ""
            record_restriction(
                chat.id,
                sender.id,
                sender.username,
                f"Bio link warning limit reached{reason_suffix}",
                time.time(),
                time.time() + restr_duration,
            )
            log_moderation_event(
                chat.id,
                sender.id,
                "USER_RESTRICTED",
                f"Restricted{' on join' if on_join else ''} for {restr_duration}s due to repeated bio link violations",
            )
            restr_text = (
                f"🚫 <b>User Restricted:</b> <a href=\"tg://user?id={sender.id}\">{user_name}</a> "
                f"has been restricted from sending messages for {restr_duration // 3600} hours "
                "due to repeated bio link violations."
            )
            try:
                r_msg = await context.bot.send_message(
                    chat_id=chat.id,
                    text=restr_text,
                    parse_mode=ParseMode.HTML,
                )
                asyncio.create_task(schedule_warning_cleanup(r_msg, delay_seconds=cleanup_delay))
            except Exception:
                pass
            return True

    removal_notice = "" if on_join else "Your message has been removed. "
    warn_text = (
        f"⚠️ <b>Bio Link Warning:</b> <a href=\"tg://user?id={sender.id}\">{user_name}</a>, "
        f"links in your profile bio (<code>{html.escape(bio_url)}</code>) are not allowed in this group. "
        f"{removal_notice}Please remove the link from your bio."
    )
    try:
        warn_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=warn_text,
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(schedule_warning_cleanup(warn_msg, delay_seconds=cleanup_delay))
    except Exception as warn_exc:
        logger.error("[BIO LINK WARN ERROR] Failed to send warning in chat %s: %s", chat.id, warn_exc)
    return False


def extract_all_links(message: Message | None) -> list[str]:
    """Extract all individual URL instances from message text, captions, and entities."""
    if not message:
        return []
    urls: list[str] = []

    # 1. Entities in text
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_LINK and entity.url:
                urls.append(entity.url)
            elif entity.type == MessageEntityType.URL and message.text:
                urls.append(message.text[entity.offset : entity.offset + entity.length])

    # 2. Entities in media caption
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == MessageEntityType.TEXT_LINK and entity.url:
                urls.append(entity.url)
            elif entity.type == MessageEntityType.URL and message.caption:
                urls.append(message.caption[entity.offset : entity.offset + entity.length])

    # 3. Regex matches
    if message.text:
        urls.extend(URL_REGEX.findall(message.text))
    if message.caption:
        urls.extend(URL_REGEX.findall(message.caption))

    return list(set(urls))


def detect_link(message: Message | None) -> tuple[bool, str]:
    """
    Detect whether a message contains any URL or link.
    Inspects Telegram message entities (URL and TEXT_LINK) as well as text regex
    across message text and media captions.
    Returns (True, description) or (False, "").
    """
    if not message:
        return False, ""

    # 1. Check message entities in text
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_LINK:
                return True, f"Hidden clickable link (TEXT_LINK: {entity.url})"
            if entity.type == MessageEntityType.URL:
                url_text = ""
                if message.text:
                    url_text = message.text[entity.offset : entity.offset + entity.length]
                return True, f"Telegram URL entity ({url_text or 'URL'})"

    # 2. Check caption entities in media
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == MessageEntityType.TEXT_LINK:
                return True, f"Caption hidden clickable link (TEXT_LINK: {entity.url})"
            if entity.type == MessageEntityType.URL:
                url_text = ""
                if message.caption:
                    url_text = message.caption[entity.offset : entity.offset + entity.length]
                return True, f"Caption Telegram URL entity ({url_text or 'URL'})"

    # 3. Text-based regex search in message text
    if message.text:
        match = URL_REGEX.search(message.text)
        if match:
            return True, f"Text URL pattern ({match.group(0)})"

    # 4. Text-based regex search in media caption
    if message.caption:
        match = URL_REGEX.search(message.caption)
        if match:
            return True, f"Caption URL pattern ({match.group(0)})"

    return False, ""


async def process_link_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, link_type: str
) -> None:
    """Execute link deletion in groups while protecting administrators, respecting whitelists, and logging details."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    sender = update.effective_user
    sender_chat = getattr(message, "sender_chat", None)

    if sender:
        sender_info = f"@{sender.username} (ID: {sender.id})" if sender.username else f"User ID {sender.id}"
    elif sender_chat:
        sender_info = f"Chat/Channel '{sender_chat.title}' (ID: {sender_chat.id})"
    else:
        sender_info = "Unknown Sender"

    chat_title = chat.title or "Unnamed Group"
    chat_id = chat.id

    # 1. Administrator & Owner Protection
    is_protected = await is_sender_admin_or_owner(chat, sender, sender_chat, context.bot)
    if is_protected:
        logger.info(
            "[LINK ALLOWED] Group: '%s' (ID: %s) | Sender: %s (Administrator/Owner) | Action: Kept message",
            chat_title,
            chat_id,
            sender_info,
        )
        return

    # 2. Check Whitelist: If all links are whitelisted, allow message
    extracted_urls = extract_all_links(message)
    if extracted_urls:
        all_whitelisted = all(is_domain_whitelisted(chat_id, u) for u in extracted_urls)
        if all_whitelisted:
            logger.info(
                "[LINK WHITELISTED] Group: '%s' (ID: %s) | Sender: %s | URLs: %s allowed",
                chat_title,
                chat_id,
                sender_info,
                extracted_urls,
            )
            return

    logger.info(
        "[LINK DETECTED] Group: '%s' (ID: %s) | Sender: %s | Type: %s",
        chat_title,
        chat_id,
        sender_info,
        link_type,
    )

    # 3. Check Bot Permissions
    can_delete, _ = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=False)
    if not can_delete:
        logger.warning(
            "[DELETE SKIPPED] Group: '%s' (ID: %s) | Sender: %s | Reason: Missing Delete Messages permission",
            chat_title,
            chat_id,
            sender_info,
        )
        return

    # 4. Delete the message containing the link
    try:
        await message.delete()
        increment_stat(chat_id, "links_deleted", count=1, chat_title=chat_title)
        log_moderation_event(
            chat_id,
            sender.id if sender else 0,
            "LINK_DELETED",
            f"Message ID: {message.message_id}, Type: {link_type}",
        )
        logger.info(
            "[MESSAGE DELETED] Group: '%s' (ID: %s) | Sender: %s | Status: Successfully deleted message containing link",
            chat_title,
            chat_id,
            sender_info,
        )
    except (Forbidden, BadRequest) as exc:
        logger.error(
            "[PERMISSION ERROR] Group: '%s' (ID: %s) | Failed to delete message: %s. "
            "Please ensure Waguri has 'Delete Messages' permission enabled.",
            chat_title,
            chat_id,
            exc,
        )
    except Exception as exc:
        logger.error(
            "[UNEXPECTED ERROR] Group: '%s' (ID: %s) | Exception while deleting message: %s",
            chat_title,
            chat_id,
            exc,
        )


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle group and supergroup messages to automatically detect and delete links & blacklisted content."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    await run_db(increment_stat, chat.id, "total_messages_checked", count=1, chat_title=chat.title)

    # Check blacklist first
    text_content = (message.text or "") + " " + (message.caption or "")
    if is_content_blacklisted(chat.id, text_content):
        sender = update.effective_user
        sender_chat = getattr(message, "sender_chat", None)
        is_admin = await is_sender_admin_or_owner(chat, sender, sender_chat, context.bot)
        if not is_admin:
            can_delete, _ = await check_bot_permissions(chat, context.bot, need_delete=True, need_restrict=False)
            if can_delete:
                try:
                    await message.delete()
                    increment_stat(chat.id, "links_deleted", count=1, chat_title=chat.title)
                    log_moderation_event(chat.id, sender.id if sender else 0, "BLACKLIST_DELETED", "Blacklisted pattern matched")
                    return
                except Exception:
                    pass

    # Check per-group setting
    settings = await run_db(get_group_settings, chat.id)
    if not settings.get("is_active", True):
        return

    sender = update.effective_user
    sender_chat = getattr(message, "sender_chat", None)

    # -------------------------------------------------------------------------
    # Feature: Anti-Bio-Link Protection
    # If the user has any link/URL in their profile bio, delete their message
    # and issue a warning to the user.
    # -------------------------------------------------------------------------
    if (
        settings.get("anti_bio_link_enabled", True)
        and sender
        and not getattr(sender, "is_bot", False)
        and sender.id not in (777000, 1087968824)
    ):
        is_admin = await is_sender_admin_or_owner(chat, sender, sender_chat, context.bot)
        if not is_admin:
            has_bio_link, bio_url = await check_user_bio_link(sender.id, context.bot)
            if has_bio_link:
                # Check whitelist: if the bio URL domain is whitelisted, allow it
                if not is_domain_whitelisted(chat.id, bio_url):
                    can_delete, _ = await check_bot_permissions(
                        chat, context.bot, need_delete=True, need_restrict=False
                    )
                    if can_delete:
                        try:
                            await message.delete()
                            increment_stat(chat.id, "links_deleted", count=1, chat_title=chat.title)
                            increment_stat(chat.id, "warnings_issued", count=1, chat_title=chat.title)
                            add_user_warning(chat.id, sender.id, f"Bio Link: {bio_url}")
                            log_moderation_event(
                                chat.id,
                                sender.id,
                                "BIO_LINK_DELETED",
                                f"Message ID: {message.message_id}, Bio link: {bio_url}",
                            )
                            logger.info(
                                "[BIO LINK DETECTED] Group: '%s' (ID: %s) | Sender: %s (ID: %s) | Bio URL: %s | Message %s deleted",
                                chat.title,
                                chat.id,
                                sender.first_name,
                                sender.id,
                                bio_url,
                                message.message_id,
                            )
                            await dispatch_bio_link_violation(chat, sender, bio_url, context, settings, on_join=False)
                            return
                        except Exception as exc:
                            logger.error(
                                "[BIO LINK ERROR] Failed to delete message %s in chat %s: %s",
                                message.message_id,
                                chat.id,
                                exc,
                            )
                        return

    # Check regular anti-link enabled
    if not settings.get("anti_link_enabled", True):
        return

    # Detect whether message has any link
    has_link, link_type = detect_link(message)
    if not has_link:
        return

    await process_link_message(update, context, link_type)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle channel posts to automatically detect and delete links with whitelist support.
    Channels do NOT support user warnings or restrictions; only offending posts are deleted.
    """
    message = update.channel_post or update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type != ChatType.CHANNEL:
        return

    increment_stat(chat.id, "total_messages_checked", count=1, chat_title=chat.title)

    # Check per-channel setting
    settings = get_group_settings(chat.id)
    if not settings.get("is_active", True) or not settings.get("anti_link_enabled", True):
        return

    # Detect whether post has any link
    has_link, link_type = detect_link(message)
    if not has_link:
        return

    # Check whitelist for channel
    extracted_urls = extract_all_links(message)
    if extracted_urls:
        if all(is_domain_whitelisted(chat.id, u) for u in extracted_urls):
            return

    chat_title = chat.title or "Unnamed Channel"
    chat_id = chat.id

    logger.info(
        "[CHANNEL LINK DETECTED] Channel: '%s' (ID: %s) | Post ID: %s | Type: %s",
        chat_title,
        chat_id,
        message.message_id,
        link_type,
    )

    try:
        await message.delete()
        increment_stat(chat_id, "links_deleted", count=1, chat_title=chat_title)
        log_moderation_event(
            chat_id,
            0,
            "CHANNEL_LINK_DELETED",
            f"Post ID: {message.message_id}, Type: {link_type}",
        )
        logger.info(
            "[CHANNEL POST DELETED] Channel: '%s' (ID: %s) | Post ID %s successfully deleted.",
            chat_title,
            chat_id,
            message.message_id,
        )
    except (Forbidden, BadRequest) as exc:
        logger.error(
            "[CHANNEL PERMISSION ERROR] Channel: '%s' (ID: %s) | Could not delete post: %s.",
            chat_title,
            chat_id,
            exc,
        )
    except Exception as exc:
        logger.error(
            "[CHANNEL DELETE ERROR] Channel: '%s' (ID: %s) | Error deleting post: %s",
            chat_title,
            chat_id,
            exc,
        )


# =============================================================================
# Whitelist & Blacklist Commands
# =============================================================================

async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage the per-group link whitelist (/whitelist add <domain>, /whitelist remove <domain>, /whitelist list)."""
    if not await verify_group_or_channel_admin(update, context.bot):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    args = context.args or []
    if not args or args[0].lower() in ("list", "show"):
        domains = get_whitelisted_domains(chat.id)
        if not domains:
            await message.reply_text(
                "🌐 <b>Link Whitelist</b>\n\nNo domains are currently whitelisted for this group.\n\n"
                "<i>To add a domain:</i> <code>/whitelist add example.com</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            text = f"🌐 <b>Whitelisted Domains ({len(domains)}):</b>\n\n"
            for d in domains:
                text += f"• <code>{html.escape(d)}</code>\n"
            text += "\n<i>To remove:</i> <code>/whitelist remove &lt;domain&gt;</code>"
            await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    action = args[0].lower()
    if action == "add" and len(args) >= 2:
        domain = args[1].strip()
        added = add_whitelisted_domain(chat.id, domain, added_by=user.id if user else 0)
        if added:
            log_moderation_event(chat.id, user.id if user else 0, "WHITELIST_ADD", f"Added: {domain}")
            await message.reply_text(f"✅ Domain <code>{html.escape(domain)}</code> added to whitelist.", parse_mode=ParseMode.HTML)
        else:
            await message.reply_text(f"ℹ️ Domain <code>{html.escape(domain)}</code> is already whitelisted.", parse_mode=ParseMode.HTML)
    elif action in ("remove", "delete", "rm") and len(args) >= 2:
        domain = args[1].strip()
        removed = remove_whitelisted_domain(chat.id, domain)
        if removed:
            log_moderation_event(chat.id, user.id if user else 0, "WHITELIST_REMOVE", f"Removed: {domain}")
            await message.reply_text(f"❌ Domain <code>{html.escape(domain)}</code> removed from whitelist.", parse_mode=ParseMode.HTML)
        else:
            await message.reply_text(f"ℹ️ Domain <code>{html.escape(domain)}</code> was not found in the whitelist.", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(
            "<b>Usage:</b>\n"
            "• <code>/whitelist add &lt;domain&gt;</code> - Add domain (e.g. <code>/whitelist add google.com</code>)\n"
            "• <code>/whitelist remove &lt;domain&gt;</code> - Remove domain\n"
            "• <code>/whitelist list</code> - View whitelisted domains",
            parse_mode=ParseMode.HTML,
        )


async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage the per-group content blacklist (/blacklist add <pattern>, /blacklist remove <pattern>, /blacklist list)."""
    if not await verify_group_or_channel_admin(update, context.bot):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    args = context.args or []
    if not args or args[0].lower() in ("list", "show"):
        patterns = get_blacklisted_patterns(chat.id)
        if not patterns:
            await message.reply_text(
                "🚫 <b>Content Blacklist</b>\n\nNo patterns or keywords are currently blacklisted.\n\n"
                "<i>To add a pattern:</i> <code>/blacklist add &lt;word&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            text = f"🚫 <b>Blacklisted Patterns ({len(patterns)}):</b>\n\n"
            for p in patterns:
                text += f"• <code>{html.escape(p)}</code>\n"
            text += "\n<i>To remove:</i> <code>/blacklist remove &lt;word&gt;</code>"
            await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    action = args[0].lower()
    if action == "add" and len(args) >= 2:
        pattern = " ".join(args[1:]).strip()
        added = add_blacklisted_pattern(chat.id, pattern, added_by=user.id if user else 0)
        if added:
            log_moderation_event(chat.id, user.id if user else 0, "BLACKLIST_ADD", f"Added: {pattern}")
            await message.reply_text(f"✅ Pattern <code>{html.escape(pattern)}</code> added to blacklist.", parse_mode=ParseMode.HTML)
        else:
            await message.reply_text("ℹ️ Pattern is already blacklisted.", parse_mode=ParseMode.HTML)
    elif action in ("remove", "delete", "rm") and len(args) >= 2:
        pattern = " ".join(args[1:]).strip()
        removed = remove_blacklisted_pattern(chat.id, pattern)
        if removed:
            log_moderation_event(chat.id, user.id if user else 0, "BLACKLIST_REMOVE", f"Removed: {pattern}")
            await message.reply_text(f"❌ Pattern <code>{html.escape(pattern)}</code> removed from blacklist.", parse_mode=ParseMode.HTML)
        else:
            await message.reply_text("ℹ️ Pattern was not found in the blacklist.", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(
            "<b>Usage:</b>\n"
            "• <code>/blacklist add &lt;pattern&gt;</code> - Add word or domain to blacklist\n"
            "• <code>/blacklist remove &lt;pattern&gt;</code> - Remove from blacklist\n"
            "• <code>/blacklist list</code> - View blacklisted patterns",
            parse_mode=ParseMode.HTML,
        )


def register_anti_link_handlers(application: Application) -> None:
    """Register automatic anti-link handlers for both groups and channels, plus whitelist/blacklist commands."""
    # Whitelist and Blacklist Commands (Group 0)
    application.add_handler(CommandHandler("whitelist", whitelist_command), group=0)
    application.add_handler(CommandHandler("blacklist", blacklist_command), group=0)

    # Group messages (Group 1)
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (~filters.COMMAND & ~filters.StatusUpdate.ALL),
            handle_group_message,
        ),
        group=1,
    )
    # Channel posts (Group 1)
    application.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION),
            handle_channel_post,
        ),
        group=1,
    )
