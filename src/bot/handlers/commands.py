import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.database.connection import AsyncSessionLocal
from src.services.user_service import UserService
from src.services.study_service import StudyService
from src.bot.keyboards.inline import get_welcome_keyboard, get_library_keyboard, get_settings_keyboard
from src.models.schemas import UserSettingUpdate

logger = logging.getLogger(__name__)
user_service = UserService()
study_service = StudyService()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets the user, registers them in the database, and displays initial options."""
    telegram_user = update.effective_user
    if not telegram_user:
        return

    welcome_text = (
        f"👋 *Welcome, {telegram_user.first_name}!* to *TestYourself AI*\n\n"
        f"I am your personal AI study assistant. Here's how you can study with me:\n\n"
        f"1️⃣ *Upload a PDF* document (up to 10MB).\n"
        f"2️⃣ I will process it and index it into my search engine.\n"
        f"3️⃣ Choose what to generate: Summaries, MCQs, Flashcards, or Q&As!\n"
        f"4️⃣ Send me a direct question to *Chat with your PDF* using RAG technology!\n\n"
        f"👇 Use the menu below to explore options or simply *send me a PDF* now!"
    )
    
    async with AsyncSessionLocal() as session:
        try:
            await user_service.get_or_create_user(
                session, 
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name
            )
        except Exception as e:
            logger.error(f"Error registering user {telegram_user.id}: {e}")

    await update.message.reply_text(
        text=welcome_text,
        reply_markup=get_welcome_keyboard(),
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user guides and list of commands."""
    help_text = (
        "🤖 *TestYourself AI - Help Guide*\n\n"
        "Here are the available commands:\n"
        "🔹 `/start` - Restart the bot and show greeting\n"
        "🔹 `/menu` - Open your PDF library & main study options\n"
        "🔹 `/history` - View your uploaded documents\n"
        "🔹 `/reset` - Unselect active PDF (chat with no document context)\n"
        "🔹 `/help` - Show this guide\n\n"
        "📖 *How to Study:*\n"
        "1. Send a PDF file directly to this chat.\n"
        "2. Wait for confirmation of index completion.\n"
        "3. Select a PDF from your library to access generated tools (Summaries, Flashcards, Quiz).\n"
        "4. When a PDF is active, typing a normal message in chat will perform a smart search over the PDF pages."
    )
    await update.message.reply_text(text=help_text, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists the user's PDF library, letting them pick an active document."""
    telegram_user = update.effective_user
    if not telegram_user:
        return

    async with AsyncSessionLocal() as session:
        try:
            # Register user if not exists
            await user_service.get_or_create_user(
                session, telegram_id=telegram_user.id, username=telegram_user.username, first_name=telegram_user.first_name
            )
            pdfs = await study_service.list_user_pdfs(session, telegram_user.id)
            
            if not pdfs:
                await update.message.reply_text(
                    "📂 *Your Library is Empty.*\n\n"
                    "Please upload a PDF file first to start learning!",
                    parse_mode="Markdown"
                )
                return

            await update.message.reply_text(
                "📂 *Select a PDF from your library:*",
                reply_markup=get_library_keyboard(pdfs),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error loading menu: {e}")
            await update.message.reply_text("⚠️ An error occurred while retrieving your document list.")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears active PDF context from the user settings."""
    telegram_user = update.effective_user
    if not telegram_user:
        return

    async with AsyncSessionLocal() as session:
        try:
            settings = await user_service.get_user_settings(session, telegram_user.id)
            if settings and settings.current_pdf_id:
                await user_service.update_user_settings(
                    session, 
                    telegram_id=telegram_user.id,
                    settings_data=UserSettingUpdate(
                        preferred_language=settings.preferred_language,
                        max_questions_limit=settings.max_questions_limit,
                        current_pdf_id=None
                    )
                )
                await update.message.reply_text("🔄 *Active document context cleared.* You can now select another document.")
            else:
                await update.message.reply_text("💡 No active PDF selected currently. Select one from /menu.")
        except Exception as e:
            logger.error(f"Error resetting context: {e}")
            await update.message.reply_text("⚠️ Failed to reset document selection.")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user settings menu."""
    telegram_user = update.effective_user
    if not telegram_user:
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await user_service.get_or_create_user(
                session, 
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name
            )
            limit = user.settings.max_questions_limit if user.settings else 5
            preferred_language = user.settings.preferred_language if user.settings else "Auto"
            
            settings_text = (
                f"⚙️ *Settings Menu*\n\n"
                f"📝 *Question Limit:* `{limit}` (Max: 50)\n"
                f"🌐 *Preferred Language:* `{preferred_language}`\n\n"
                f"Use the buttons below to adjust the question limit for MCQs, Flashcards, Q&As, and Interview prep."
            )
            
            await update.message.reply_text(
                text=settings_text,
                reply_markup=get_settings_keyboard(limit, preferred_language),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            await update.message.reply_text("⚠️ An error occurred while retrieving your settings.")
