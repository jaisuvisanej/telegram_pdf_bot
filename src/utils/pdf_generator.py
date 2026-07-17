import io
import os
from typing import List, Dict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Attempt to register Nirmala font for Tamil/Indic Unicode support
FONT_NAME = "Helvetica"
try:
    font_path = "C:/Windows/Fonts/Nirmala.ttc"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Nirmala', font_path))
        FONT_NAME = "Nirmala"
except Exception:
    pass

def clean_text_for_pdf(text: str, allow_tamil: bool = False) -> str:
    """Replaces common emojis with text equivalents and sanitizes Unicode script characters to prevent crashes."""
    if not text:
        return ""
    replacements = {
        "✅": "[Correct]",
        "❌": "[Incorrect]",
        "❓": "Question: ",
        "🎯": "Target: ",
        "💡": "Explanation: ",
        "🃏": "Card: ",
        "📝": "Quiz: ",
        "💼": "Interview: ",
        "📖": "Book: ",
        "🧠": "Flashcard: ",
        "⚡": "Fast: ",
        "📦": "Package: ",
        "🇦": "A",
        "🇧": "B",
        "🇨": "C",
        "🇩": "D",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    if allow_tamil:
        # Keep ASCII characters, Tamil Unicode block (0x0B80 - 0x0BFF), and standard punctuation
        return "".join(c for c in text if ord(c) < 128 or (0x0B80 <= ord(c) <= 0x0BFF) or c in "‘’“”–—\n")
    else:
        return "".join(c for c in text if ord(c) < 128 or c in "‘’“”–—\n")

def generate_study_pdf(pdf_title: str, question_type: str, items: List[Dict], allow_tamil: bool = False) -> io.BytesIO:
    """Generates a styled, multi-page PDF document containing generated questions, answers, and explanations."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=54, 
        leftMargin=54, 
        topMargin=54, 
        bottomMargin=54
    )
    story = []
    
    styles = getSampleStyleSheet()
    
    # Define custom styles to prevent collisions
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName=FONT_NAME,
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=8
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=24
    )
    
    question_style = ParagraphStyle(
        'QStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=10,
        spaceAfter=6
    )
    
    option_style = ParagraphStyle(
        'OptStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#4A5568"),
        leftIndent=15,
        spaceAfter=4
    )
    
    answer_style = ParagraphStyle(
        'AnsStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#2F855A"),
        leftIndent=15,
        spaceAfter=4
    )
    
    explanation_style = ParagraphStyle(
        'ExpStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#718096"),
        leftIndent=15,
        spaceAfter=12
    )
    
    # Header block
    cleaned_doc_title = clean_text_for_pdf(pdf_title, allow_tamil)
    story.append(Paragraph(f"{question_type} Study Sheet", title_style))
    story.append(Paragraph(f"Reference Document: {cleaned_doc_title}", subtitle_style))
    story.append(Spacer(1, 10))
    
    prefixes = ["A", "B", "C", "D"]
    
    for idx, item in enumerate(items):
        if question_type == "MCQ":
            q_text = clean_text_for_pdf(item.get('question', ''), allow_tamil)
            story.append(Paragraph(f"<b>Q{idx+1}: {q_text}</b>", question_style))
            
            opts = item.get('options', [])
            correct_idx = item.get('correct_option', 0)
            
            for o_idx, opt in enumerate(opts):
                cleaned_opt = clean_text_for_pdf(opt, allow_tamil)
                if o_idx == correct_idx:
                    story.append(Paragraph(f"[x] {prefixes[o_idx]}. {cleaned_opt} (Correct Answer)", answer_style))
                else:
                    story.append(Paragraph(f"[ ] {prefixes[o_idx]}. {cleaned_opt}", option_style))
                    
            exp = item.get('explanation', '')
            if exp:
                cleaned_exp = clean_text_for_pdf(exp, allow_tamil)
                story.append(Paragraph(f"<i>Explanation:</i> {cleaned_exp}", explanation_style))
                
        elif question_type == "FLASHCARD":
            front = clean_text_for_pdf(item.get('front', ''), allow_tamil)
            back = clean_text_for_pdf(item.get('back', ''), allow_tamil)
            story.append(Paragraph(f"<b>Card {idx+1} Front:</b> {front}", question_style))
            story.append(Paragraph(f"<b>Back:</b> {back}", explanation_style))
            
        elif question_type == "QA":
            q_text = clean_text_for_pdf(item.get('question', ''), allow_tamil)
            ans_text = clean_text_for_pdf(item.get('answer', ''), allow_tamil)
            story.append(Paragraph(f"<b>Q{idx+1}: {q_text}</b>", question_style))
            story.append(Paragraph(f"<b>Answer:</b> {ans_text}", explanation_style))
            
        elif question_type == "INTERVIEW":
            q_text = clean_text_for_pdf(item.get('question', ''), allow_tamil)
            ans_text = clean_text_for_pdf(item.get('ideal_answer', ''), allow_tamil)
            story.append(Paragraph(f"<b>Q{idx+1}: {q_text}</b>", question_style))
            story.append(Paragraph(f"<b>Ideal Response:</b> {ans_text}", explanation_style))
            
        story.append(Spacer(1, 5))
        
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_combined_study_pdf(pdf_title: str, sections_dict: Dict[str, List[Dict]], allow_tamil: bool = False) -> io.BytesIO:
    """Generates an all-in-one PDF compiling all available generated material types."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=54, 
        leftMargin=54, 
        topMargin=54, 
        bottomMargin=54
    )
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitleAll',
        parent=styles['Heading1'],
        fontName=FONT_NAME,
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#2C3E50"),
        spaceAfter=8
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitleAll',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#7F8C8D"),
        spaceAfter=24
    )
    
    section_style = ParagraphStyle(
        'SecTitleAll',
        parent=styles['Heading2'],
        fontName=FONT_NAME,
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#2980B9"),
        spaceBefore=18,
        spaceAfter=8
    )
    
    question_style = ParagraphStyle(
        'QStyleAll',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2C3E50"),
        spaceBefore=10,
        spaceAfter=6
    )
    
    option_style = ParagraphStyle(
        'OptStyleAll',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#34495E"),
        leftIndent=15,
        spaceAfter=4
    )
    
    answer_style = ParagraphStyle(
        'AnsStyleAll',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#27AE60"),
        leftIndent=15,
        spaceAfter=4
    )
    
    explanation_style = ParagraphStyle(
        'ExpStyleAll',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#7F8C8D"),
        leftIndent=15,
        spaceAfter=12
    )
    
    cleaned_doc_title = clean_text_for_pdf(pdf_title, allow_tamil)
    story.append(Paragraph("Complete Study Guide", title_style))
    story.append(Paragraph(f"Reference Document: {cleaned_doc_title}", subtitle_style))
    story.append(Spacer(1, 10))
    
    prefixes = ["A", "B", "C", "D"]
    
    for q_type, items in sections_dict.items():
        if not items:
            continue
            
        story.append(Paragraph(f"{q_type} Section", section_style))
        story.append(Spacer(1, 5))
        
        for idx, item in enumerate(items):
            if q_type == "MCQ":
                q_text = clean_text_for_pdf(item.get('question', ''), allow_tamil)
                story.append(Paragraph(f"<b>Q{idx+1}: {q_text}</b>", question_style))
                
                opts = item.get('options', [])
                correct_idx = item.get('correct_option', 0)
                
                for o_idx, opt in enumerate(opts):
                    cleaned_opt = clean_text_for_pdf(opt, allow_tamil)
                    if o_idx == correct_idx:
                        story.append(Paragraph(f"[x] {prefixes[o_idx]}. {cleaned_opt} (Correct Answer)", answer_style))
                    else:
                        story.append(Paragraph(f"[ ] {prefixes[o_idx]}. {cleaned_opt}", option_style))
                        
                exp = item.get('explanation', '')
                if exp:
                    cleaned_exp = clean_text_for_pdf(exp, allow_tamil)
                    story.append(Paragraph(f"<i>Explanation:</i> {cleaned_exp}", explanation_style))
                    
            elif q_type == "FLASHCARD":
                front = clean_text_for_pdf(item.get('front', ''), allow_tamil)
                back = clean_text_for_pdf(item.get('back', ''), allow_tamil)
                story.append(Paragraph(f"<b>Card {idx+1} Front:</b> {front}", question_style))
                story.append(Paragraph(f"<b>Back:</b> {back}", explanation_style))
                
            elif q_type == "QA":
                q_text = clean_text_for_pdf(item.get('question', ''), allow_tamil)
                ans_text = clean_text_for_pdf(item.get('answer', ''), allow_tamil)
                story.append(Paragraph(f"<b>Q{idx+1}: {q_text}</b>", question_style))
                story.append(Paragraph(f"<b>Answer:</b> {ans_text}", explanation_style))
                
            elif q_type == "INTERVIEW":
                q_text = clean_text_for_pdf(item.get('question', ''), allow_tamil)
                ans_text = clean_text_for_pdf(item.get('ideal_answer', ''), allow_tamil)
                story.append(Paragraph(f"<b>Q{idx+1}: {q_text}</b>", question_style))
                story.append(Paragraph(f"<b>Ideal Response:</b> {ans_text}", explanation_style))
                
            story.append(Spacer(1, 5))
            
        story.append(Spacer(1, 15))
        
    doc.build(story)
    buffer.seek(0)
    return buffer
