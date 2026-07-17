from typing import List, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard showing primary options for new users."""
    keyboard = [
        [
            InlineKeyboardButton("📖 Help & Guides", callback_data="help_guide"),
            InlineKeyboardButton("📂 My Library", callback_data="my_library")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_pdf_menu_keyboard(pdf_id: int) -> InlineKeyboardMarkup:
    """Returns the study interactive menu keyboard for a specific PDF."""
    keyboard = [
        [
            InlineKeyboardButton("📄 Summary", callback_data=f"summary_{pdf_id}"),
            InlineKeyboardButton("🧠 Flashcards", callback_data=f"flashcards_{pdf_id}")
        ],
        [
            InlineKeyboardButton("📝 MCQ Quiz", callback_data=f"mcqs_{pdf_id}"),
            InlineKeyboardButton("❓ Conceptual Q&A", callback_data=f"qa_{pdf_id}")
        ],
        [
            InlineKeyboardButton("🎯 Interview Prep", callback_data=f"interview_{pdf_id}"),
            InlineKeyboardButton("💬 Chat with PDF", callback_data=f"chat_pdf_{pdf_id}")
        ],
        [
            InlineKeyboardButton("🗑️ Delete PDF", callback_data=f"delete_confirm_{pdf_id}"),
            InlineKeyboardButton("📂 My Library", callback_data="my_library")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_chat_pdf_keyboard(pdf_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard layout for the active PDF chat window."""
    keyboard = [
        [
            InlineKeyboardButton("🧹 Clear Chat History", callback_data=f"clear_chat_{pdf_id}"),
            InlineKeyboardButton("↩️ Back to Study Menu", callback_data=f"select_pdf_{pdf_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_library_keyboard(pdfs: List[Any]) -> InlineKeyboardMarkup:
    """Returns a keyboard listing all user PDFs for easy selection."""
    keyboard = []
    
    # List each PDF as a button
    for pdf in pdfs:
        # Trim names if too long
        display_name = pdf.file_name if len(pdf.file_name) <= 25 else f"{pdf.file_name[:22]}..."
        keyboard.append([InlineKeyboardButton(f"📄 {display_name}", callback_data=f"select_pdf_{pdf.id}")])
        
    # Actions row
    keyboard.append([
        InlineKeyboardButton("➕ Upload Info", callback_data="upload_info"),
        InlineKeyboardButton("🔄 Refresh", callback_data="my_library")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_delete_confirmation_keyboard(pdf_id: int) -> InlineKeyboardMarkup:
    """Returns yes/no delete confirmation buttons."""
    keyboard = [
        [
            InlineKeyboardButton("❌ Yes, Delete File", callback_data=f"delete_yes_{pdf_id}"),
            InlineKeyboardButton("↩️ Cancel", callback_data=f"select_pdf_{pdf_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quiz_navigation_keyboard(pdf_id: int, current_idx: int, total: int) -> InlineKeyboardMarkup:
    """Keyboard to navigate MCQs, select options, or Reveal Answers."""
    keyboard = [
        [
            InlineKeyboardButton("🇦", callback_data=f"quiz_select_{pdf_id}_{current_idx}_0"),
            InlineKeyboardButton("🇧", callback_data=f"quiz_select_{pdf_id}_{current_idx}_1"),
            InlineKeyboardButton("🇨", callback_data=f"quiz_select_{pdf_id}_{current_idx}_2"),
            InlineKeyboardButton("🇩", callback_data=f"quiz_select_{pdf_id}_{current_idx}_3"),
        ],
        [
            InlineKeyboardButton("👁️ Reveal Answer & Explanation", callback_data=f"quiz_reveal_{pdf_id}_{current_idx}")
        ],
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"quiz_nav_{pdf_id}_{current_idx-1}") if current_idx > 0 else InlineKeyboardButton("⏹️ Start", callback_data="dummy"),
            InlineKeyboardButton(f"{current_idx+1}/{total}", callback_data="dummy"),
            InlineKeyboardButton("Next ➡️", callback_data=f"quiz_nav_{pdf_id}_{current_idx+1}") if current_idx < total - 1 else InlineKeyboardButton("⏹️ End", callback_data=f"select_pdf_{pdf_id}")
        ],
        [
            InlineKeyboardButton("↩️ Back to Study Menu", callback_data=f"select_pdf_{pdf_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quiz_result_keyboard(pdf_id: int, current_idx: int, total: int) -> InlineKeyboardMarkup:
    """Keyboard to navigate MCQs after an option has been selected (shows no option buttons)."""
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"quiz_nav_{pdf_id}_{current_idx-1}") if current_idx > 0 else InlineKeyboardButton("⏹️ Start", callback_data="dummy"),
            InlineKeyboardButton(f"{current_idx+1}/{total}", callback_data="dummy"),
            InlineKeyboardButton("Next ➡️", callback_data=f"quiz_nav_{pdf_id}_{current_idx+1}") if current_idx < total - 1 else InlineKeyboardButton("⏹️ End", callback_data=f"select_pdf_{pdf_id}")
        ],
        [
            InlineKeyboardButton("📥 Download MCQs as PDF", callback_data=f"pdfexport_{pdf_id}_MCQ")
        ],
        [
            InlineKeyboardButton("↩️ Back to Study Menu", callback_data=f"select_pdf_{pdf_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(limit: int, preferred_language: str = "Auto") -> InlineKeyboardMarkup:
    """Returns a keyboard allowing users to adjust their question limit (1-50) and language."""
    auto_label = "🤖 Auto (Detect) ✅" if preferred_language == "Auto" else "🤖 Auto (Detect)"
    en_label = "🇬🇧 English ✅" if preferred_language == "English" else "🇬🇧 English"
    ta_label = "🇮🇳 Tamil (தமிழ்) ✅" if preferred_language == "Tamil" else "🇮🇳 Tamil (தமிழ்)"
    
    keyboard = [
        [
            InlineKeyboardButton("➖ 5", callback_data="settings_change_-5"),
            InlineKeyboardButton("➖ 1", callback_data="settings_change_-1"),
            InlineKeyboardButton(f"Count: {limit}", callback_data="dummy"),
            InlineKeyboardButton("➕ 1", callback_data="settings_change_+1"),
            InlineKeyboardButton("➕ 5", callback_data="settings_change_+5"),
        ],
        [
            InlineKeyboardButton("Set 5", callback_data="settings_change_5"),
            InlineKeyboardButton("Set 10", callback_data="settings_change_10"),
            InlineKeyboardButton("Set 20", callback_data="settings_change_20"),
            InlineKeyboardButton("Set Max (50)", callback_data="settings_change_50"),
        ],
        [
            InlineKeyboardButton(auto_label, callback_data="settings_lang_Auto"),
        ],
        [
            InlineKeyboardButton(en_label, callback_data="settings_lang_English"),
            InlineKeyboardButton(ta_label, callback_data="settings_lang_Tamil"),
        ],
        [
            InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_welcome")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quiz_limit_keyboard(pdf_id: int) -> InlineKeyboardMarkup:
    """Returns a keyboard allowing users to select the number of questions to generate for a quiz."""
    keyboard = [
        [
            InlineKeyboardButton("5", callback_data=f"mcqstart_{pdf_id}_5"),
            InlineKeyboardButton("10", callback_data=f"mcqstart_{pdf_id}_10"),
            InlineKeyboardButton("15", callback_data=f"mcqstart_{pdf_id}_15"),
            InlineKeyboardButton("20", callback_data=f"mcqstart_{pdf_id}_20"),
        ],
        [
            InlineKeyboardButton("25", callback_data=f"mcqstart_{pdf_id}_25"),
            InlineKeyboardButton("30", callback_data=f"mcqstart_{pdf_id}_30"),
            InlineKeyboardButton("40", callback_data=f"mcqstart_{pdf_id}_40"),
            InlineKeyboardButton("50", callback_data=f"mcqstart_{pdf_id}_50"),
        ],
        [
            InlineKeyboardButton("↩️ Back to Study Menu", callback_data=f"select_pdf_{pdf_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_pdf_export_keyboard(pdf_id: int, has_mcq: bool, has_flashcard: bool, has_qa: bool, has_interview: bool) -> InlineKeyboardMarkup:
    """Returns a keyboard allowing users to download generated study sheets as PDFs."""
    keyboard = []
    
    if has_mcq:
        keyboard.append([InlineKeyboardButton("📝 Download MCQ PDF", callback_data=f"pdfexport_{pdf_id}_MCQ")])
    if has_flashcard:
        keyboard.append([InlineKeyboardButton("🧠 Download Flashcards PDF", callback_data=f"pdfexport_{pdf_id}_FLASHCARD")])
    if has_qa:
        keyboard.append([InlineKeyboardButton("❓ Download Q&A PDF", callback_data=f"pdfexport_{pdf_id}_QA")])
    if has_interview:
        keyboard.append([InlineKeyboardButton("💼 Download Interview Prep PDF", callback_data=f"pdfexport_{pdf_id}_INTERVIEW")])
        
    # Also add "Download All-in-One PDF" if more than one exists
    if sum([has_mcq, has_flashcard, has_qa, has_interview]) > 1:
        keyboard.append([InlineKeyboardButton("📦 Download All-in-One PDF", callback_data=f"pdfexport_{pdf_id}_ALL")])
        
    keyboard.append([InlineKeyboardButton("↩️ Back to Study Menu", callback_data=f"select_pdf_{pdf_id}")])
    
    return InlineKeyboardMarkup(keyboard)

def get_study_material_keyboard(pdf_id: int, question_type: str) -> InlineKeyboardMarkup:
    """Returns a keyboard for study material output with a download button."""
    keyboard = [
        [
            InlineKeyboardButton("📥 Download as PDF", callback_data=f"pdfexport_{pdf_id}_{question_type}")
        ],
        [
            InlineKeyboardButton("↩️ Back to Study Menu", callback_data=f"select_pdf_{pdf_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
