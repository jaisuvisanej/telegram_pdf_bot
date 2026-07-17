import logging
from telegram.ext import ContextTypes
from telegram.error import NetworkError, TimedOut, Forbidden

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error occurring in the telegram application."""
    error = context.error
    if not error:
        return

    if isinstance(error, (NetworkError, TimedOut)):
        # Network errors are common and usually temporary (timeouts, read errors, etc.)
        # Logging them as warnings instead of errors keeps the logs cleaner.
        logger.warning("Telegram network/timeout issue: %s", error)
    elif isinstance(error, Forbidden):
        # Forbidden error is raised when the bot is blocked by the user
        logger.warning("Telegram Bot is blocked/forbidden: %s", error)
    else:
        # Unexpected errors get logged with full traceback
        logger.error("Exception while handling an update:", exc_info=error)
