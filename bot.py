import sys
import threading
import time
from telegram import Update
from telegram.error import Conflict, InvalidToken, NetworkError, TimedOut
from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest

from config import (
    TELEGRAM_BOOTSTRAP_RETRIES,
    TELEGRAM_CONNECT_TIMEOUT,
    TELEGRAM_GET_UPDATES_TIMEOUT,
    TELEGRAM_POOL_TIMEOUT,
    TELEGRAM_PROXY_URL,
    TELEGRAM_READ_TIMEOUT,
    TELEGRAM_WRITE_TIMEOUT,
    get_bot_token,
    logger,
    validate_token,
)
from database import init_db
from handlers import (
    about_command,
    antibiolink_command,
    antispam_command,
    antlink_command,
    autoreply_off_command,
    autoreply_on_command,
    ban_command,
    blacklist_command,
    build_main_help_markup,
    build_personal_settings_markup,
    business_stats_command,
    check_bot_permissions,
    cleanservice_command,
    compute_message_fingerprint,
    contact_command,
    detect_link,
    disable_command,
    enable_command,
    error_handler,
    exclude_user_command,
    features_command,
    greeting_command,
    handle_anti_forward,
    handle_anti_spam,
    handle_business_connection,
    handle_business_message,
    handle_channel_post,
    handle_deleted_business_messages,
    handle_edited_business_message,
    handle_greeting_message,
    handle_group_message,
    handle_media_restrictions,
    handle_my_chat_member,
    handle_new_chat_members,
    handle_private_reply_message_input,
    handle_service_message,
    help_callback_handler,
    help_command,
    id_command,
    include_user_command,
    interactive_help_command,
    is_bot_owner,
    is_greeting,
    is_group_owner,
    is_sender_admin_or_owner,
    logs_command,
    mute_command,
    mystatus_command,
    owner_command,
    personal_callback_handler,
    personal_command,
    preview_command,
    process_link_message,
    raid_command,
    register_all_handlers,
    register_personal_autoreply_handlers,
    resetmessage_command,
    resetwarnings_command,
    restrict_user_24h,
    setmessage_command,
    settings_callback_handler,
    settings_command,
    setup_command_menu,
    start,
    stats_command,
    unban_command,
    unmute_command,
    warnings_command,
    whitelist_command,
)

# Export handlers for backward compatibility
__all__ = [
    "start",
    "help_command",
    "interactive_help_command",
    "help_callback_handler",
    "build_main_help_markup",
    "about_command",
    "contact_command",
    "settings_command",
    "settings_callback_handler",
    "features_command",
    "enable_command",
    "disable_command",
    "stats_command",
    "logs_command",
    "antlink_command",
    "antibiolink_command",
    "cleanservice_command",
    "antispam_command",
    "warnings_command",
    "resetwarnings_command",
    "mute_command",
    "unmute_command",
    "ban_command",
    "unban_command",
    "whitelist_command",
    "blacklist_command",
    "raid_command",
    "owner_command",
    "id_command",
    "handle_group_message",
    "handle_channel_post",
    "handle_my_chat_member",
    "handle_media_restrictions",
    "handle_anti_forward",
    "handle_new_chat_members",
    "handle_service_message",
    "process_link_message",
    "detect_link",
    "is_sender_admin_or_owner",
    "is_group_owner",
    "is_bot_owner",
    "check_bot_permissions",
    "handle_greeting_message",
    "greeting_command",
    "is_greeting",
    "handle_anti_spam",
    "compute_message_fingerprint",
    "restrict_user_24h",
    "personal_command",
    "autoreply_on_command",
    "autoreply_off_command",
    "setmessage_command",
    "preview_command",
    "mystatus_command",
    "resetmessage_command",
    "exclude_user_command",
    "include_user_command",
    "business_stats_command",
    "handle_business_connection",
    "handle_business_message",
    "handle_edited_business_message",
    "handle_deleted_business_messages",
    "personal_callback_handler",
    "build_personal_settings_markup",
    "register_personal_autoreply_handlers",
    "setup_command_menu",
    "error_handler",
    "validate_token",
    "main",
]


def main() -> None:
    """Initialize and run the Waguri Telegram bot."""
    token = get_bot_token()
    logger.info("Bot token verified and loaded successfully.")

    # Initialize SQLite database for persistent multi-tenant moderation records & group settings
    try:
        init_db()
    except Exception as exc:
        logger.error("Failed to initialize moderation database: %s", exc)
        sys.exit(1)

    try:
        # Build custom HTTPXRequest with increased timeouts and optional proxy to prevent TimedOut errors
        request = HTTPXRequest(
            connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
            read_timeout=TELEGRAM_READ_TIMEOUT,
            write_timeout=TELEGRAM_WRITE_TIMEOUT,
            pool_timeout=TELEGRAM_POOL_TIMEOUT,
            proxy=TELEGRAM_PROXY_URL,
        )

        # Build the Application with custom request settings and post_init
        application = (
            ApplicationBuilder()
            .token(token)
            .request(request)
            .post_init(setup_command_menu)
            .build()
        )

        # Register all features (commands, admin commands, anti-link, anti-spam, media, raid, error handling)
        register_all_handlers(application)

        # Start silent background scheduler thread for frontend-configured due promotions, stickers, and shayari
        def schedule_worker():
            time.sleep(5)  # initial delay
            while True:
                try:
                    from promotions_manager import process_due_promotions
                    process_due_promotions()
                except Exception as e:
                    logger.debug("Background promotion check: %s", e)

                try:
                    from stickers_manager import process_due_stickers
                    process_due_stickers()
                except Exception as e:
                    logger.debug("Background sticker check: %s", e)

                try:
                    from shayari_manager import process_due_shayari
                    process_due_shayari()
                except Exception as e:
                    logger.debug("Background shayari check: %s", e)

                time.sleep(15)

        sched_thread = threading.Thread(target=schedule_worker, daemon=True)
        sched_thread.start()

        # Run the bot in polling mode with bootstrap retries, drop_pending_updates, and all update types
        logger.info("Waguri bot is running in polling mode. Press Ctrl+C to stop.")
        application.run_polling(
            timeout=TELEGRAM_GET_UPDATES_TIMEOUT,
            bootstrap_retries=TELEGRAM_BOOTSTRAP_RETRIES,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
    except Conflict:
        logger.error(
            "Conflict error: Another instance of this bot is already running. "
            "Please terminate all other running bot instances before starting Waguri."
        )
        sys.exit(1)
    except InvalidToken:
        logger.error(
            "The Telegram server rejected the token. "
            "Please verify that the token in .env matches the one provided by @BotFather."
        )
        sys.exit(1)
    except (TimedOut, NetworkError) as exc:
        logger.error(
            "Network timeout or connection error while communicating with Telegram: %s. "
            "Check your internet connection or configure TELEGRAM_PROXY_URL in .env if Telegram is restricted.",
            exc,
        )
        sys.exit(1)
    except Exception as exc:
        logger.error("An unexpected error occurred while running the bot: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
