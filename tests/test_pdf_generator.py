import pytest
import io
from src.utils.pdf_generator import clean_text_for_pdf, generate_study_pdf, generate_combined_study_pdf

def test_clean_text_for_pdf():
    # Test emoji replacements and basic text filtering
    assert "[Correct] A" in clean_text_for_pdf("✅ A")
    assert "[Incorrect] B" in clean_text_for_pdf("❌ B")
    # Test non-BMP unicode character removal
    assert "Hello" in clean_text_for_pdf("Hello 🚀")
    
    # Test Tamil language script preservation/removal
    tamil_phrase = "தமிழ்"
    assert clean_text_for_pdf(tamil_phrase, allow_tamil=True) == tamil_phrase
    assert clean_text_for_pdf(tamil_phrase, allow_tamil=False) == ""

def test_generate_study_pdf():
    items = [
        {
            "question": "What is the capital of France?",
            "options": ["London", "Berlin", "Paris", "Rome"],
            "correct_option": 2,
            "explanation": "Paris is the capital."
        }
    ]
    
    # English Generation
    pdf_buffer = generate_study_pdf("Geography Quiz", "MCQ", items, allow_tamil=False)
    assert isinstance(pdf_buffer, io.BytesIO)
    pdf_data = pdf_buffer.getvalue()
    assert pdf_data.startswith(b"%PDF")
    
    # Tamil Generation (using Nirmala font registration fallback)
    tamil_items = [
        {
            "question": "பிரான்சின் தலைநகரம் எது?",
            "options": ["லண்டன்", "பெர்லின்", "பாரிஸ்", "ரோம்"],
            "correct_option": 2,
            "explanation": "பாரிஸ் தலைநகரம் ஆகும்."
        }
    ]
    pdf_buffer_ta = generate_study_pdf("புவியியல் வினாடி வினா", "MCQ", tamil_items, allow_tamil=True)
    assert isinstance(pdf_buffer_ta, io.BytesIO)
    pdf_data_ta = pdf_buffer_ta.getvalue()
    assert pdf_data_ta.startswith(b"%PDF")

def test_generate_combined_study_pdf():
    sections = {
        "MCQ": [
            {
                "question": "What is 2+2?",
                "options": ["3", "4", "5", "6"],
                "correct_option": 1,
                "explanation": "2+2 equals 4."
            }
        ],
        "FLASHCARD": [
            {
                "front": "Term",
                "back": "Definition"
            }
        ]
    }
    
    pdf_buffer = generate_combined_study_pdf("Math & Definitions", sections, allow_tamil=False)
    assert isinstance(pdf_buffer, io.BytesIO)
    pdf_data = pdf_buffer.getvalue()
    assert pdf_data.startswith(b"%PDF")
