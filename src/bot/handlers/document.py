import logging
import os
import tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from src.database.connection import AsyncSessionLocal
from src.services.user_service import UserService
from src.services.study_service import StudyService
from src.bot.keyboards.inline import get_pdf_menu_keyboard, get_pdf_export_keyboard
from src.models.schemas import UserSettingUpdate

logger = logging.getLogger(__name__)
user_service = UserService()
study_service = StudyService()

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming document uploads, validating size and format, extracting text, and indexing."""
    msg = update.message
    doc = msg.document
    
    if not doc:
        return

    # Check extension
    if not doc.file_name.lower().endswith(".pdf"):
        await msg.reply_text("❌ *Unsupported file format.* Please send only PDF files.", parse_mode="Markdown")
        return

    # Check size limit (10MB)
    from src.config.settings import settings
    if doc.file_size > settings.max_file_size_bytes:
        await msg.reply_text(
            f"❌ *File too large.* The maximum size allowed is {settings.MAX_FILE_SIZE_MB}MB.",
            parse_mode="Markdown"
        )
        return

    status_msg = await msg.reply_text("📥 *Downloading file from Telegram...*", parse_mode="Markdown")
    
    # Download file using a temporary file
    temp_dir = tempfile.gettempdir()
    temp_path = Path(temp_dir) / doc.file_name
    
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(str(temp_path))
        
        await status_msg.edit_text("⚙️ *Extracting text & page structures...*", parse_mode="Markdown")
        
        # Read file bytes
        with open(temp_path, "rb") as f:
            file_bytes = f.read()
            
        async with AsyncSessionLocal() as session:
            # Resolve user context
            user = await user_service.get_or_create_user(
                session, 
                telegram_id=msg.from_user.id,
                username=msg.from_user.username,
                first_name=msg.from_user.first_name
            )
            
            await status_msg.edit_text("🔍 *Building AI search vectors (FAISS)...*", parse_mode="Markdown")
            
            # Process upload (runs extractor & FAISS engine)
            pdf_response = await study_service.upload_pdf(
                session=session,
                user_id=msg.from_user.id,
                file_name=doc.file_name,
                file_bytes=file_bytes
            )
            
            # Automatically set this PDF as active for RAG chatting
            settings_data = UserSettingUpdate(
                preferred_language=user.settings.preferred_language,
                max_questions_limit=user.settings.max_questions_limit,
                current_pdf_id=pdf_response.id
            )
            await user_service.update_user_settings(session, telegram_id=msg.from_user.id, settings_data=settings_data)

            success_text = (
                f"✅ *Upload complete!* Indexed `{pdf_response.file_name}`\n"
                f"📄 Pages: {pdf_response.page_count} | Size: {pdf_response.file_size / (1024*1024):.2f} MB\n\n"
                f"💡 *Document context set.* You can now chat directly by sending a message, or select study options below:"
            )
            
            await status_msg.delete()  # Clean progress msg
            await msg.reply_text(
                text=success_text,
                reply_markup=get_pdf_menu_keyboard(pdf_response.id),
                parse_mode="Markdown"
            )
            
    except ValueError as e:
        logger.warning(f"Validation error handling PDF upload for user {msg.from_user.id}: {e}")
        await status_msg.edit_text(f"❌ *Failed to process PDF:* {str(e)}")
    except Exception as e:
        logger.exception(f"Error handling PDF upload for user {msg.from_user.id}")
        await status_msg.edit_text("⚠️ *Failed to process PDF.* Please make sure it is not encrypted or corrupted.")
    finally:
        # Cleanup temp file
        if temp_path.exists():
            try:
                os.unlink(temp_path)
            except Exception:
                pass

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles chat dialogues. If a PDF is active, routes as a RAG query. Otherwise guides the user."""
    msg = update.message
    user_text = msg.text
    
    # Ignore commands
    if user_text.startswith("/"):
        return
        
    async with AsyncSessionLocal() as session:
        try:
            # Fetch user setting
            settings = await user_service.get_user_settings(session, msg.from_user.id)
            
            if not settings or not settings.current_pdf_id:
                # Direct user to upload or configure
                await msg.reply_text(
                    "💡 *No active document selected.*\n\n"
                    "Select an uploaded file from /menu or upload a new PDF to start chatting!",
                    parse_mode="Markdown"
                )
                return

            pdf_id = settings.current_pdf_id
            pdf = await study_service.get_pdf(session, pdf_id)
            
            if not pdf:
                # PDF was probably deleted, reset setting
                await user_service.update_user_settings(
                    session, msg.from_user.id,
                    UserSettingUpdate(preferred_language="English", max_questions_limit=5, current_pdf_id=None)
                )
                await msg.reply_text("⚠️ Your active PDF record was not found. Please upload it again or check /menu.")
                return

            if user_text.strip().lower() == "pdf":
                study_repo = study_service.study_repo
                mcqs = await study_repo.get_questions(session, pdf_id, "MCQ")
                flashcards = await study_repo.get_questions(session, pdf_id, "FLASHCARD")
                qas = await study_repo.get_questions(session, pdf_id, "QA")
                interviews = await study_repo.get_questions(session, pdf_id, "INTERVIEW")
                
                if not (mcqs or flashcards or qas or interviews):
                    await msg.reply_text(
                        f"💡 *No study materials generated yet for {pdf.file_name}.*\n\n"
                        f"Go to /menu, select the PDF, and generate an MCQ Quiz, Flashcards, or Q&A first!",
                        parse_mode="Markdown"
                    )
                    return
                    
                keyboard = get_pdf_export_keyboard(
                    pdf_id=pdf_id,
                    has_mcq=bool(mcqs),
                    has_flashcard=bool(flashcards),
                    has_qa=bool(qas),
                    has_interview=bool(interviews)
                )
                
                export_prompt = (
                    f"📂 *Export Study Materials to PDF*\n\n"
                    f"Choose which of the generated study sheets for *{pdf.file_name}* you want to download as a styled PDF:"
                )
                await msg.reply_text(
                    text=export_prompt,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                return

            # Indicated typing to keep bot organic
            await context.bot.send_chat_action(chat_id=msg.chat_id, action="typing")
            
            # Query RAG
            response = await study_service.ask_question(
                session=session,
                user_id=msg.from_user.id,
                pdf_id=pdf_id,
                question=user_text
            )
            
            # Construct response message citing sources
            reply_text = response.answer
            
            if response.sources:
                citations = ", ".join(str(src["page_number"]) for src in response.sources)
                reply_text += f"\n\n📖 _[References: Page(s) {citations}]_"

            await msg.reply_text(text=reply_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error handling message for user {msg.from_user.id}: {e}")
            await msg.reply_text("⚠️ An error occurred while generating a response. Please try again.")
