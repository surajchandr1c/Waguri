import logging
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import ContextTypes

logger = logging.getLogger("Waguri.ErrorHandler")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log any errors caused by updates without crashing the bot."""
    if isinstance(context.error, Conflict):
        logger.error(
            "Conflict error: Another instance of this bot is already running with this token. "
            "Please terminate all other running bot instances."
        )
        return
    if isinstance(context.error, TimedOut):
        logger.warning(
            "Telegram API request timed out while handling an update: %s",
            context.error,
        )
        return

    if isinstance(context.error, NetworkError):
        logger.warning(
            "Telegram network error while handling an update: %s",
            context.error,
        )
        return

    logger.error("Exception while handling an update:", exc_info=context.error)
