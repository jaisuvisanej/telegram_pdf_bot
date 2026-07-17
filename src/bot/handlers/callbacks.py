import logging
from typing import Any
from telegram import Update
from telegram.ext import ContextTypes

from src.database.connection import AsyncSessionLocal
from src.services.user_service import UserService
from src.services.study_service import StudyService
from src.bot.keyboards.inline import (
    get_pdf_menu_keyboard, get_library_keyboard, 
    get_delete_confirmation_keyboard, get_quiz_navigation_keyboard,
    get_quiz_result_keyboard, get_welcome_keyboard, get_settings_keyboard,
    get_quiz_limit_keyboard, get_study_material_keyboard
)
from src.models.schemas import UserSettingUpdate

logger = logging.getLogger(__name__)
user_service = UserService()
study_service = StudyService()

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatches inline query actions to their appropriate handlers."""
    query = update.callback_query
    if not query:
        return
        
    await query.answer()  # Acknowledge Telegram callback receipt
    
    data = query.data
    user_id = query.from_user.id
    
    async with AsyncSessionLocal() as session:
        try:
            if data == "help_guide":
                help_text = (
                    "📖 *How to use TestYourself AI:*\n\n"
                    "1. Upload a PDF document directly by dragging/attaching it here.\n"
                    "2. Wait a few moments while I extract and index the contents.\n"
                    "3. Open /menu to select your PDF and start generating materials!\n"
                    "4. Chat with the active PDF by typing a regular question."
                )
                await query.edit_message_text(text=help_text, parse_mode="Markdown")
                
            elif data == "my_library":
                pdfs = await study_service.list_user_pdfs(session, user_id)
                if not pdfs:
                    await query.edit_message_text(
                        text="📂 *Your Library is Empty.*\n\nPlease send a PDF file directly to this chat!",
                        parse_mode="Markdown"
                    )
                else:
                    await query.edit_message_text(
                        text="📂 *Select a PDF from your library:*",
                        reply_markup=get_library_keyboard(pdfs),
                        parse_mode="Markdown"
                    )
                    
            elif data == "upload_info":
                await query.edit_message_text(
                    text="📥 *How to upload:*\n\nSimply select the paperclip attachment icon, choose a PDF file (under 10MB) from your device, and send it here.",
                    parse_mode="Markdown"
                )
                
            elif data == "settings_menu":
                user = await user_service.get_or_create_user(session, user_id)
                limit = user.settings.max_questions_limit if user.settings else 5
                preferred_language = user.settings.preferred_language if user.settings else "Auto"
                
                settings_text = (
                    f"⚙️ *Settings Menu*\n\n"
                    f"📝 *Question Limit:* `{limit}` (Max: 50)\n"
                    f"🌐 *Preferred Language:* `{preferred_language}`\n\n"
                    f"Use the buttons below to adjust the question limit for MCQs, Flashcards, Q&As, and Interview prep."
                )
                await query.edit_message_text(
                    text=settings_text,
                    reply_markup=get_settings_keyboard(limit, preferred_language),
                    parse_mode="Markdown"
                )

            elif data.startswith("settings_change_"):
                val_str = data.split("_")[2]
                user = await user_service.get_or_create_user(session, user_id)
                current_limit = user.settings.max_questions_limit if user.settings else 5
                preferred_language = user.settings.preferred_language if user.settings else "Auto"
                
                if val_str.startswith("+") or val_str.startswith("-"):
                    delta = int(val_str)
                    new_limit = current_limit + delta
                else:
                    new_limit = int(val_str)
                
                new_limit = max(1, min(50, new_limit))
                
                await user_service.update_user_settings(
                    session,
                    telegram_id=user_id,
                    settings_data=UserSettingUpdate(
                        preferred_language=preferred_language,
                        max_questions_limit=new_limit,
                        current_pdf_id=user.settings.current_pdf_id if user.settings else None
                    )
                )
                
                settings_text = (
                    f"⚙️ *Settings Menu*\n\n"
                    f"📝 *Question Limit:* `{new_limit}` (Max: 50)\n"
                    f"🌐 *Preferred Language:* `{preferred_language}`\n\n"
                    f"Use the buttons below to adjust the question limit for MCQs, Flashcards, Q&As, and Interview prep."
                )
                await query.edit_message_text(
                    text=settings_text,
                    reply_markup=get_settings_keyboard(new_limit, preferred_language),
                    parse_mode="Markdown"
                )

            elif data.startswith("settings_lang_"):
                new_lang = data.split("_")[2]
                user = await user_service.get_or_create_user(session, user_id)
                current_limit = user.settings.max_questions_limit if user.settings else 5
                
                await user_service.update_user_settings(
                    session,
                    telegram_id=user_id,
                    settings_data=UserSettingUpdate(
                        preferred_language=new_lang,
                        max_questions_limit=current_limit,
                        current_pdf_id=user.settings.current_pdf_id if user.settings else None
                    )
                )
                
                settings_text = (
                    f"⚙️ *Settings Menu*\n\n"
                    f"📝 *Question Limit:* `{current_limit}` (Max: 50)\n"
                    f"🌐 *Preferred Language:* `{new_lang}`\n\n"
                    f"Use the buttons below to adjust the question limit for MCQs, Flashcards, Q&As, and Interview prep."
                )
                await query.edit_message_text(
                    text=settings_text,
                    reply_markup=get_settings_keyboard(current_limit, new_lang),
                    parse_mode="Markdown"
                )

            elif data == "back_to_welcome":
                welcome_text = (
                    f"👋 *Welcome!* to *TestYourself AI*\n\n"
                    f"I am your personal AI study assistant. Here's how you can study with me:\n\n"
                    f"1️⃣ *Upload a PDF* document (up to 10MB).\n"
                    f"2️⃣ I will process it and index it into my search engine.\n"
                    f"3️⃣ Choose what to generate: Summaries, MCQs, Flashcards, or Q&As!\n"
                    f"4️⃣ Send me a direct question to *Chat with your PDF* using RAG technology!\n\n"
                    f"👇 Use the menu below to explore options or simply *send me a PDF* now!"
                )
                await query.edit_message_text(
                    text=welcome_text,
                    reply_markup=get_welcome_keyboard(),
                    parse_mode="Markdown"
                )

            elif data.startswith("select_pdf_"):
                pdf_id = int(data.split("_")[2])
                pdf = await study_service.get_pdf(session, pdf_id)
                if not pdf:
                    await query.edit_message_text("⚠️ PDF not found.")
                    return
                    
                # Set active PDF in DB settings
                user = await user_service.get_or_create_user(session, user_id)
                await user_service.update_user_settings(
                    session, user_id, 
                    UserSettingUpdate(
                        preferred_language=user.settings.preferred_language,
                        max_questions_limit=user.settings.max_questions_limit,
                        current_pdf_id=pdf_id
                    )
                )
                
                menu_text = (
                    f"📖 *Active PDF: {pdf.file_name}*\n"
                    f"📄 Pages: {pdf.page_count} | Size: {pdf.file_size / (1024*1024):.2f} MB\n\n"
                    f"Select a feature below to begin studying!"
                )
                await query.edit_message_text(
                    text=menu_text,
                    reply_markup=get_pdf_menu_keyboard(pdf_id),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("summary_"):
                pdf_id = int(data.split("_")[1])
                await query.edit_message_text("⚡ *Generating overall summary, key topics, and simplified definitions...*")
                
                res = await study_service.generate_summary(session, pdf_id)
                
                summary_formatted = (
                    f"📄 *Overall Summary:*\n{res.summary}\n\n"
                    f"🎯 *Important Topics:*\n{res.important_topics}\n\n"
                    f"👦 *Explain Like I'm 10:*\n_{res.explain_like_10}_"
                )
                
                await query.edit_message_text(
                    text=summary_formatted,
                    reply_markup=get_pdf_menu_keyboard(pdf_id),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("flashcards_"):
                pdf_id = int(data.split("_")[1])
                await query.edit_message_text("⚡ *Compiling interactive flashcards...*")
                
                flashcards = await study_service.generate_questions(session, pdf_id, "FLASHCARD")
                
                fc_text = "🧠 *Flashcards:*\n\n"
                for i, fc in enumerate(flashcards):
                    fc_text += f"🃏 *Card {i+1}*\n*Q:* {fc['front']}\n*A:* _{fc['back']}_\n\n"
                    
                await query.edit_message_text(
                    text=fc_text,
                    reply_markup=get_study_material_keyboard(pdf_id, "FLASHCARD"),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("qa_"):
                pdf_id = int(data.split("_")[1])
                await query.edit_message_text("⚡ *Formulating conceptual study questions...*")
                
                items = await study_service.generate_questions(session, pdf_id, "QA")
                
                qa_text = "❓ *Conceptual Q&A:*\n\n"
                for i, item in enumerate(items):
                    qa_text += f"*{i+1}. Question:* {item['question']}\n*Answer:* {item['answer']}\n\n"
                    
                await query.edit_message_text(
                    text=qa_text,
                    reply_markup=get_study_material_keyboard(pdf_id, "QA"),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("interview_"):
                pdf_id = int(data.split("_")[1])
                await query.edit_message_text("⚡ *Writing interview training questions...*")
                
                questions = await study_service.generate_questions(session, pdf_id, "INTERVIEW")
                
                iv_text = "🎯 *Interview Prep Questions:*\n\n"
                for i, q in enumerate(questions):
                    iv_text += f"💼 *Q{i+1}:* {q['question']}\n*Ideal Response:* _{q['ideal_answer']}_\n\n"
                    
                await query.edit_message_text(
                    text=iv_text,
                    reply_markup=get_study_material_keyboard(pdf_id, "INTERVIEW"),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("chat_pdf_"):
                pdf_id = int(data.split("_")[2])
                from src.bot.keyboards.inline import get_chat_pdf_keyboard
                chat_instruction = (
                    f"💬 *Chat with PDF Mode*\n\n"
                    f"Send any question directly as a text message in the chat. I will search the document and answer you using RAG Q&A!\n\n"
                    f"_Note: I automatically support English, Tamil script, and Tanglish (e.g. 'solunga')._"
                )
                await query.edit_message_text(
                    text=chat_instruction,
                    reply_markup=get_chat_pdf_keyboard(pdf_id),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("clear_chat_"):
                pdf_id = int(data.split("_")[2])
                await study_service.clear_chat_history(session, user_id, pdf_id)
                from src.bot.keyboards.inline import get_chat_pdf_keyboard
                await query.edit_message_text(
                    text="🧹 *Chat context cleared successfully.* All previous history has been deleted.\n\nSend a new question directly as a message to begin a fresh conversation!",
                    reply_markup=get_chat_pdf_keyboard(pdf_id),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("pdfexport_"):
                parts = data.split("_")
                pdf_id = int(parts[1])
                q_type = parts[2]
                
                await query.answer("Generating PDF document...")
                
                pdf = await study_service.get_pdf(session, pdf_id)
                if not pdf:
                    await query.edit_message_text("⚠️ PDF not found.")
                    return
                    
                user = await user_service.get_or_create_user(session, user_id)
                preferred_lang = user.settings.preferred_language if user.settings else "English"
                allow_tamil = (preferred_lang == "Tamil")
                
                study_repo = study_service.study_repo
                from src.utils.pdf_generator import generate_study_pdf, generate_combined_study_pdf
                
                if q_type == "ALL":
                    sections = {}
                    mcqs = await study_repo.get_questions(session, pdf_id, "MCQ")
                    flashcards = await study_repo.get_questions(session, pdf_id, "FLASHCARD")
                    qas = await study_repo.get_questions(session, pdf_id, "QA")
                    interviews = await study_repo.get_questions(session, pdf_id, "INTERVIEW")
                    
                    if mcqs:
                        sections["MCQ"] = mcqs[0].content
                    if flashcards:
                        sections["FLASHCARD"] = flashcards[0].content
                    if qas:
                        sections["QA"] = qas[0].content
                    if interviews:
                        sections["INTERVIEW"] = interviews[0].content
                        
                    pdf_buffer = generate_combined_study_pdf(pdf.file_name, sections, allow_tamil=allow_tamil)
                    filename = f"{pdf.file_name.replace('.pdf', '')}_study_guide.pdf"
                    caption = f"Here is your complete study guide for *{pdf.file_name}*! 📦"
                else:
                    cached = await study_repo.get_questions(session, pdf_id, q_type)
                    if not cached:
                        await query.edit_message_text(f"⚠️ No generated {q_type} materials found.")
                        return
                    items = cached[0].content
                    pdf_buffer = generate_study_pdf(pdf.file_name, q_type, items, allow_tamil=allow_tamil)
                    filename = f"{pdf.file_name.replace('.pdf', '')}_{q_type.lower()}_study_sheet.pdf"
                    caption = f"Here is your generated {q_type} PDF study sheet! 📚"
                
                # Send document to user
                await context.bot.send_document(
                    chat_id=user_id,
                    document=pdf_buffer,
                    filename=filename,
                    caption=caption
                )
                
            elif data.startswith("delete_confirm_"):
                pdf_id = int(data.split("_")[2])
                pdf = await study_service.get_pdf(session, pdf_id)
                if not pdf:
                    await query.edit_message_text("⚠️ PDF not found.")
                    return
                await query.edit_message_text(
                    text=f"🚨 *Are you sure you want to permanently delete: {pdf.file_name}?*",
                    reply_markup=get_delete_confirmation_keyboard(pdf_id),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("delete_yes_"):
                pdf_id = int(data.split("_")[2])
                success = await study_service.delete_pdf(session, pdf_id)
                if success:
                    # Clear selected pdf context if we just deleted the active one
                    settings = await user_service.get_user_settings(session, user_id)
                    if settings and settings.current_pdf_id == pdf_id:
                        await user_service.update_user_settings(
                            session, user_id,
                            UserSettingUpdate(preferred_language="English", max_questions_limit=5, current_pdf_id=None)
                        )
                    await query.edit_message_text(
                        text="🗑️ *PDF and associated indices deleted successfully.*",
                        reply_markup=get_library_keyboard(await study_service.list_user_pdfs(session, user_id)),
                        parse_mode="Markdown"
                    )
                else:
                    await query.edit_message_text("❌ Failed to delete document from the storage.")
                    
            elif data.startswith("mcqs_"):
                pdf_id = int(data.split("_")[1])
                
                prompt_text = (
                    "❓ *How many questions would you like to generate for this MCQ Quiz?*\n\n"
                    "Select a count limit from the options below (Maximum: 50):"
                )
                await query.edit_message_text(
                    text=prompt_text,
                    reply_markup=get_quiz_limit_keyboard(pdf_id),
                    parse_mode="Markdown"
                )
                
            elif data.startswith("mcqstart_"):
                parts = data.split("_")
                pdf_id = int(parts[1])
                count = int(parts[2])
                
                await query.edit_message_text(f"⚡ *Composing {count} multiple choice quiz questions...*")
                
                # Update user settings limit contextually
                user = await user_service.get_or_create_user(session, user_id)
                await user_service.update_user_settings(
                    session, user_id,
                    UserSettingUpdate(
                        preferred_language=user.settings.preferred_language if user.settings else "English",
                        max_questions_limit=count,
                        current_pdf_id=pdf_id
                    )
                )
                
                # Retrieve or generate MCQs (will dynamically fetch using updated settings count limit)
                mcqs = await study_service.generate_questions(session, pdf_id, "MCQ")
                
                if not mcqs:
                    await query.edit_message_text("⚠️ No questions were generated. Try again.")
                    return
                    
                # Renders the first MCQ slide
                await render_quiz_slide(query, pdf_id, mcqs, 0)
                
            elif data.startswith("quiz_nav_"):
                parts = data.split("_")
                pdf_id = int(parts[2])
                target_idx = int(parts[3])
                
                mcqs = await study_service.generate_questions(session, pdf_id, "MCQ")
                await render_quiz_slide(query, pdf_id, mcqs, target_idx)
                
            elif data.startswith("quiz_reveal_"):
                parts = data.split("_")
                pdf_id = int(parts[2])
                idx = int(parts[3])
                
                mcqs = await study_service.generate_questions(session, pdf_id, "MCQ")
                await render_quiz_answer(query, pdf_id, mcqs, idx)
                
            elif data.startswith("quiz_select_"):
                parts = data.split("_")
                pdf_id = int(parts[2])
                idx = int(parts[3])
                chosen_idx = int(parts[4])
                
                mcqs = await study_service.generate_questions(session, pdf_id, "MCQ")
                await render_quiz_selection_result(query, pdf_id, mcqs, idx, chosen_idx)
                
        except Exception as e:
            logger.error(f"Callback error for user {user_id} on action {data}: {e}")
            await query.edit_message_text(
                text="⚠️ *An unexpected error occurred.* Please try again.",
                reply_markup=get_library_keyboard(await study_service.list_user_pdfs(session, user_id)) if data != "my_library" else None,
                parse_mode="Markdown"
            )

async def render_quiz_slide(query: Any, pdf_id: int, mcqs: list, idx: int) -> None:
    """Renders the question and options for an MCQ slide."""
    mcq = mcqs[idx]
    
    options_text = ""
    prefixes = ["A", "B", "C", "D"]
    for i, option in enumerate(mcq["options"]):
        options_text += f"*️⃣ *{prefixes[i]}.* {option}\n"
        
    slide_text = (
        f"📝 *Quiz Question {idx+1} of {len(mcqs)}*\n\n"
        f"❓ *{mcq['question']}*\n\n"
        f"{options_text}"
    )
    
    await query.edit_message_text(
        text=slide_text,
        reply_markup=get_quiz_navigation_keyboard(pdf_id, idx, len(mcqs)),
        parse_mode="Markdown"
    )

async def render_quiz_answer(query: Any, pdf_id: int, mcqs: list, idx: int) -> None:
    """Reveals the correct answer key and logical explanation for an MCQ slide."""
    mcq = mcqs[idx]
    prefixes = ["A", "B", "C", "D"]
    correct_char = prefixes[mcq["correct_option"]]
    correct_val = mcq["options"][mcq["correct_option"]]
    
    options_text = ""
    for i, option in enumerate(mcq["options"]):
        if i == mcq["correct_option"]:
            options_text += f"✅ *{prefixes[i]}. {option}*  (Correct)\n"
        else:
            options_text += f"◽ {prefixes[i]}. {option}\n"
            
    reveal_text = (
        f"📝 *Quiz Question {idx+1} of {len(mcqs)}*\n\n"
        f"❓ *{mcq['question']}*\n\n"
        f"{options_text}\n"
        f"🎯 *Correct Answer:* {correct_char} ({correct_val})\n\n"
        f"💡 *Explanation:*\n_{mcq['explanation']}_"
    )
    
    await query.edit_message_text(
        text=reveal_text,
        reply_markup=get_quiz_navigation_keyboard(pdf_id, idx, len(mcqs)),
        parse_mode="Markdown"
    )

async def render_quiz_selection_result(query: Any, pdf_id: int, mcqs: list, idx: int, chosen_idx: int) -> None:
    """Renders the question, highlights correctness of choice, and reveals explanation."""
    mcq = mcqs[idx]
    prefixes = ["A", "B", "C", "D"]
    
    correct_idx = mcq["correct_option"]
    is_correct = (chosen_idx == correct_idx)
    
    feedback_banner = f"✅ *Correct! You chose {prefixes[chosen_idx]}.*" if is_correct else f"❌ *Incorrect! You chose {prefixes[chosen_idx]}.*"
    
    options_text = ""
    for i, option in enumerate(mcq["options"]):
        if i == correct_idx:
            options_text += f"✅ *{prefixes[i]}. {option}*  (Correct)\n"
        elif i == chosen_idx:
            options_text += f"❌ *{prefixes[i]}. {option}*  (Your Choice)\n"
        else:
            options_text += f"◽ {prefixes[i]}. {option}\n"
            
    result_text = (
        f"📝 *Quiz Question {idx+1} of {len(mcqs)}*\n\n"
        f"❓ *{mcq['question']}*\n\n"
        f"{options_text}\n"
        f"{feedback_banner}\n"
        f"🎯 *Correct Answer:* {prefixes[correct_idx]} ({mcq['options'][correct_idx]})\n\n"
        f"💡 *Explanation:*\n_{mcq['explanation']}_"
    )
    
    await query.edit_message_text(
        text=result_text,
        reply_markup=get_quiz_result_keyboard(pdf_id, idx, len(mcqs)),
        parse_mode="Markdown"
    )
