import logging
import sys
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)

from src.config.settings import settings
from src.config.logging_config import setup_logging
from src.bot.handlers.commands import start_command, help_command, menu_command, reset_command, settings_command
from src.bot.handlers.document import handle_document, handle_text_message
from src.bot.handlers.callbacks import handle_callback_query
from src.bot.handlers.error import error_handler

# Boot logging configuration
setup_logging()
logger = logging.getLogger(__name__)

def run_bot() -> None:
    """Configures and runs the Telegram Bot application in polling mode."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not configured! Exiting...")
        sys.exit(1)
        
    logger.info("Initializing Telegram Bot...")
    
    # Create Telegram Application with concurrent update task handling
    builder = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).concurrent_updates(True)
    if settings.TELEGRAM_API_URL:
        builder.base_url(settings.TELEGRAM_API_URL)
        logger.info(f"Using custom Telegram API URL: {settings.TELEGRAM_API_URL}")
    if settings.TELEGRAM_FILE_URL:
        builder.base_file_url(settings.TELEGRAM_FILE_URL)
        logger.info(f"Using custom Telegram File API URL: {settings.TELEGRAM_FILE_URL}")
    application = builder.build()
    
    # Register global error handler
    application.add_error_handler(error_handler)
    
    # 1. Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("history", menu_command))  # Map history to same library view
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("deletepdf", menu_command)) # Deletion starts in menu/library
    
    # 2. Callback Query Handler (inline keyboards)
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # 3. Message Handlers
    # Catch PDF uploads
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    # Catch text messages for RAG chatting (excluding commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    logger.info("Telegram Bot starts polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C). Exiting gracefully.")
