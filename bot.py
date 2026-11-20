import sys
import threading
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
from database import close_db, init_db
from scheduler_daemon import run_scheduler_loop
from handlers import (
    about_command,
    abuse_command,
    antibiolink_command,
    antispam_command,
    antlink_command,
    ban_command,
    blacklist_command,
    build_main_help_markup,
    check_bot_permissions,
    cleanservice_command,
    compute_message_fingerprint,
    contact_command,
    detect_link,
    disable_command,
    enable_command,
    error_handler,
    features_command,
    greeting_command,
    handle_abuse_message,
    handle_anti_forward,
    handle_anti_spam,
    handle_channel_post,
    handle_group_message,
    handle_media_restrictions,
    handle_my_chat_member,
    handle_new_chat_members,
    handle_service_message,
    help_callback_handler,
    help_command,
    id_command,
    interactive_help_command,
    is_bot_owner,
    is_greeting,
    is_group_owner,
    is_sender_admin_or_owner,
    logs_command,
    mute_command,
    owner_command,
    process_link_message,
    raid_command,
    register_all_handlers,
    resetwarnings_command,
    restrict_user_24h,
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
    "abuse_command",
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
    "handle_abuse_message",
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
    "greeting_command",
    "is_greeting",
    "handle_anti_spam",
    "compute_message_fingerprint",
    "restrict_user_24h",
    "setup_command_menu",
    "error_handler",
    "validate_token",
    "main",
]


_scheduler_stop_event = threading.Event()


async def shutdown_resources(application) -> None:
    """Stop background work and release shared database resources."""
    _scheduler_stop_event.set()
    close_db()


def main() -> None:
    """Initialize and run the Waguri Telegram bot."""
    _scheduler_stop_event.clear()
    token = get_bot_token()
    logger.info("Bot token verified and loaded successfully.")

    # Initialize MongoDB database for persistent multi-tenant moderation records & group settings
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
            connection_pool_size=32,
            proxy=TELEGRAM_PROXY_URL,
        )

        # Build the Application with custom request settings and post_init
        application = (
            ApplicationBuilder()
            .token(token)
            .request(request)
            .post_init(setup_command_menu)
            .post_shutdown(shutdown_resources)
            .build()
        )

        # Register all features (commands, admin commands, anti-link, anti-spam, media, raid, error handling)
        register_all_handlers(application)

        sched_thread = threading.Thread(
            target=run_scheduler_loop,
            args=(_scheduler_stop_event,),
            name="waguri-scheduler",
            daemon=True,
        )
        sched_thread.start()

        # Run the bot in polling mode with bootstrap retries, drop_pending_updates, and all update types
        logger.info("Waguri bot is running in polling mode. Press Ctrl+C to stop.")
        application.run_polling(
            timeout=TELEGRAM_GET_UPDATES_TIMEOUT,
            bootstrap_retries=TELEGRAM_BOOTSTRAP_RETRIES,
            drop_pending_updates=True,
            allowed_updates=[
                Update.MESSAGE,
                Update.EDITED_MESSAGE,
                Update.CHANNEL_POST,
                Update.EDITED_CHANNEL_POST,
                Update.CALLBACK_QUERY,
                Update.MY_CHAT_MEMBER,
            ],
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
