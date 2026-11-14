from telegram.ext import Application
from handlers.commands import (
    about_command,
    contact_command,
    help_command,
    register_command_handlers,
    start,
)
from handlers.private_dashboard import (
    build_private_start_markup,
    handle_private_callback,
    register_private_dashboard_handlers,
)
from handlers.admin_commands import (
    antibiolink_command,
    antlink_command,
    antispam_command,
    ban_command,
    cleanservice_command,
    id_command,
    logs_command,
    mute_command,
    register_admin_command_handlers,
    resetwarnings_command,
    unban_command,
    unmute_command,
    warnings_command,
)
from handlers.admin_check import (
    check_bot_permissions,
    invalidate_cache,
    is_bot_owner,
    is_group_owner,
    is_sender_admin_or_owner,
)
from handlers.anti_link import (
    blacklist_command,
    check_user_bio_link,
    detect_link,
    extract_all_links,
    handle_channel_post,
    handle_group_message,
    invalidate_bio_cache,
    process_link_message,
    register_anti_link_handlers,
    whitelist_command,
)
from handlers.anti_spam import (
    compute_message_fingerprint,
    handle_anti_spam,
    register_anti_spam_handlers,
    restrict_user_24h,
)
from handlers.media_protection import (
    handle_media_restrictions,
    identify_media_type,
    register_media_protection_handlers,
)
from handlers.extra_protection import (
    handle_anti_forward,
    handle_new_chat_members,
    handle_service_message,
    raid_command,
    register_extra_protection_handlers,
)
from handlers.greetings import (
    greeting_command,
    handle_greeting_message,
    is_greeting,
    register_greeting_handlers,
)
from handlers.settings_panel import (
    build_main_settings_markup,
    register_settings_handlers,
    settings_callback_handler,
    settings_command,
)
from handlers.feature_commands import (
    disable_command,
    enable_command,
    features_command,
    register_feature_command_handlers,
    stats_command,
)
from handlers.registration import (
    handle_my_chat_member,
    register_registration_handlers,
)
from handlers.bot_owner import (
    owner_command,
    register_bot_owner_handlers,
)
from handlers.help_menu import (
    build_command_options_markup,
    build_main_help_markup,
    help_callback_handler,
    interactive_help_command,
    register_help_menu_handlers,
)
from handlers.command_menu import setup_command_menu
from handlers.error_handler import error_handler


def register_all_handlers(application: Application) -> None:
    """Register all command, admin moderation, anti-link, anti-spam, greeting, and error handlers."""
    # Group 0: Bot membership updates (join/leave tracking)
    register_registration_handlers(application)

    # Group 0: General User Commands (/start, /help, /about, /contact)
    register_command_handlers(application)

    # Group 0: Interactive Help & Commands Menu (cmd:*)
    register_help_menu_handlers(application)

    # Group 0: Private Owner Dashboard callbacks (pvt:*)
    register_private_dashboard_handlers(application)

    # Group 0: Interactive Settings Panel (/settings and inline callbacks cfg:*)
    register_settings_handlers(application)

    # Group 0: Feature Control & Statistics Commands (/features, /enable, /disable, /stats)
    register_feature_command_handlers(application)

    # Group 0: Administrator Moderation Commands (/antlink, /antispam, /warnings, /resetwarnings, /mute, /unmute, /ban, /unban, /logs, /id)
    register_admin_command_handlers(application)

    # Group 0: Whitelist & Blacklist Commands (/whitelist, /blacklist)
    register_anti_link_handlers(application)

    # Group 0: Raid Emergency Mode & Join Monitoring (/raid, NEW_CHAT_MEMBERS)
    register_extra_protection_handlers(application)

    # Group 0: Super-Admin Bot Owner Control Panel (/owner)
    register_bot_owner_handlers(application)

    # Group 1: Automatic Anti-Link Protection (Groups and Channels) - handlers are registered inside register_anti_link_handlers
    # Group 2: Automatic Repeated Message Spam & Flood Detection (Groups)
    register_anti_spam_handlers(application)

    # Group 3: Media Restrictions & Anti-Forward Filters
    register_media_protection_handlers(application)

    # Group 4: User Greetings ("hii", "hlw", "hello")
    register_greeting_handlers(application)

    # Global Error Handler
    application.add_error_handler(error_handler)
