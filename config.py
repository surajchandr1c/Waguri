import logging
import os
import re
import sys
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure centralized logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("Waguri")

# ==========================================
# Network & Timeout Configuration Defaults
# ==========================================
# Increase default HTTPXRequest timeouts to prevent telegram.error.TimedOut
# on slow, high-latency, or throttled network connections.
TELEGRAM_CONNECT_TIMEOUT: float = float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "30.0"))
TELEGRAM_READ_TIMEOUT: float = float(os.getenv("TELEGRAM_READ_TIMEOUT", "30.0"))
TELEGRAM_WRITE_TIMEOUT: float = float(os.getenv("TELEGRAM_WRITE_TIMEOUT", "30.0"))
TELEGRAM_POOL_TIMEOUT: float = float(os.getenv("TELEGRAM_POOL_TIMEOUT", "10.0"))
TELEGRAM_GET_UPDATES_TIMEOUT: int = int(os.getenv("TELEGRAM_GET_UPDATES_TIMEOUT", "30"))
TELEGRAM_BOOTSTRAP_RETRIES: int = int(os.getenv("TELEGRAM_BOOTSTRAP_RETRIES", "5"))
TELEGRAM_PROXY_URL: str | None = (
    os.getenv("TELEGRAM_PROXY_URL")
    or os.getenv("HTTPS_PROXY")
    or os.getenv("HTTP_PROXY")
    or None
)

# ==========================================
# Bot Startup & Uptime Tracking
# ==========================================
BOT_START_TIME: float = time.time()

# ==========================================
# Super-Admin / Bot Owner Configuration
# ==========================================
def parse_owner_ids() -> set[int]:
    """Parse comma-separated Telegram User IDs of bot super-owners."""
    raw = os.getenv("BOT_OWNER_IDS", "")
    owners: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if item.isdigit():
            owners.add(int(item))
    return owners

BOT_OWNER_IDS: set[int] = parse_owner_ids()

# Global emergency feature overrides (does not modify group preferences)
# e.g., {"anti_link": False} to temporarily suspend a feature globally during API maintenance
GLOBAL_EMERGENCY_OVERRIDES: dict[str, bool] = {}

# ==========================================
# Group Moderation Configuration Defaults
# ==========================================
ANTI_LINK_ENABLED: bool = True
ANTI_BIO_LINK_ENABLED: bool = True
BIO_CACHE_TTL_SECONDS: int = 300
CLEAN_SERVICE_ENABLED: bool = True
ANTI_SPAM_ENABLED: bool = True
SPAM_WINDOW_SECONDS: int = 30
SPAM_WARNING_LIMIT: int = 2
SPAM_RESTRICTION_SECONDS: int = 86400  # Exactly 24 hours
WARNING_DELETE_AFTER_SECONDS: int = 10

# Part 7 Flood Protection Defaults
FLOOD_DETECTION_ENABLED: bool = True
FLOOD_WINDOW_SECONDS: int = 10
FLOOD_MESSAGE_LIMIT: int = 8

# Part 8 Additional Moderation Defaults
ANTI_FORWARD_ENABLED: bool = False
ANTI_JOIN_SPAM_ENABLED: bool = False
ANTI_BOT_ENABLED: bool = False
MEDIA_RESTRICTIONS_ENABLED: bool = False
DEFAULT_ALLOWED_MEDIA: dict[str, bool] = {
    "photos": True,
    "videos": True,
    "documents": True,
    "stickers": True,
    "gifs": True,
    "voice": True,
    "video_notes": True,
}

ADMIN_CACHE_TTL_SECONDS: int = 120  # Cache admin status for 2 minutes to reduce API load
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "moderation.db")

# Exact warning and restriction messages
WARNING_MSG_1: str = (
    "⚠️ Warning 1/2: Please don't spam the group. Repeated messages are not allowed. "
    "One more violation may result in a temporary restriction."
)
WARNING_MSG_2: str = (
    "⚠️ Warning 2/2: This is your second spam warning. Stop repeating the same message "
    "or you will be restricted for 24 hours."
)
RESTRICTION_MSG: str = (
    "🚫 You have been restricted for 24 hours because of repeated spam messages. "
    "Your spam messages have been removed."
)

GROUP_WELCOME_MSG: str = (
    "👋 Hello! I am Waguri.\n\n"
    "Thank you for adding me to your group.\n\n"
    "I can help protect your group from spam and unwanted links.\n\n"
    "To configure me, use /settings.\n\n"
    "Please make me an administrator and grant the required permissions."
)


def validate_token(token: str) -> bool:
    """Validate that the token matches the expected Telegram Bot API format."""
    token_pattern = re.compile(r"^\d+:[A-Za-z0-9_-]{35}$")
    if token_pattern.match(token):
        return True

    # Check for common copy-paste mistakes to provide helpful feedback
    if re.search(r"\d{1,2}:\d{2}\s*(?:AM|PM)?$", token, re.IGNORECASE):
        logger.error(
            "The token contains a message timestamp (e.g., '12:05 AM') accidentally copied from Telegram. "
            "Please remove the timestamp."
        )
    if ":" not in token:
        logger.error(
            "The token is missing the numeric bot ID and colon (e.g., '1234567890:'). "
            "A complete Telegram bot token looks like '1234567890:AAE0dSMNopthg8_...'"
        )

    return False


def get_bot_token() -> str:
    """Retrieve and validate the Telegram Bot Token from the environment."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token or not token.strip() or token.strip() == "your_telegram_bot_token_here":
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. Please add your bot token to the .env file."
        )
        sys.exit(1)

    clean_token = token.strip().strip("\"'")

    if not validate_token(clean_token):
        logger.error(
            "Invalid Telegram bot token format. "
            "Check your .env file and ensure you copied the full token from @BotFather."
        )
        sys.exit(1)

    return clean_token
