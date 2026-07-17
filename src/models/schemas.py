from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

class UserSettingBase(BaseModel):
    preferred_language: str = "Auto"
    max_questions_limit: int = 5
    current_pdf_id: Optional[int] = None

class UserSettingUpdate(UserSettingBase):
    pass

class UserSettingResponse(UserSettingBase):
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None

class UserResponse(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    settings: Optional[UserSettingResponse] = None

    model_config = ConfigDict(from_attributes=True)

class UploadedPDFResponse(BaseModel):
    id: int
    user_id: int
    file_name: str
    file_path: str
    file_size: int
    page_count: int
    char_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatHistoryCreate(BaseModel):
    pdf_id: Optional[int] = None
    role: str = Field(..., pattern="^(user|model)$")
    content: str

class ChatHistoryResponse(BaseModel):
    id: int
    user_id: int
    pdf_id: Optional[int]
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class GeneratedQuestionResponse(BaseModel):
    id: int
    pdf_id: int
    question_type: str
    content: List[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class GeneratedSummaryResponse(BaseModel):
    id: int
    pdf_id: int
    summary_text: str
    important_topics: str
    explain_like_10: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AskQuestionRequest(BaseModel):
    question: str

class AskQuestionResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] = []

class SummaryResponse(BaseModel):
    summary: str = Field(..., description="A detailed summary of the main points and thesis of the document.")
    important_topics: str = Field(..., description="Bullet points of the most critical concepts or topics.")
    explain_like_10: str = Field(..., description="An explanation of the document's core concept simplified as if for a 10-year-old child.")

class MCQItem(BaseModel):
    question: str = Field(..., description="The multiple choice question")
    options: List[str] = Field(..., description="Exactly 4 options")
    correct_option: int = Field(..., description="0-indexed index of the correct option (0, 1, 2, or 3)")
    explanation: str = Field(..., description="Brief explanation of why the option is correct")

class MCQList(BaseModel):
    questions: List[MCQItem]

class FlashcardItem(BaseModel):
    front: str = Field(..., description="The front side of the flashcard containing a key term, question, or formula")
    back: str = Field(..., description="The back side of the flashcard containing the definition, answer, or explanation")

class FlashcardList(BaseModel):
    flashcards: List[FlashcardItem]

class QAItem(BaseModel):
    question: str = Field(..., description="Conceptual question based on the text")
    answer: str = Field(..., description="Detailed comprehensive answer based on the text")

class QAList(BaseModel):
    items: List[QAItem]

class InterviewItem(BaseModel):
    question: str = Field(..., description="Tough/insightful interview question based on the concepts")
    ideal_answer: str = Field(..., description="A model response showing complete technical understanding")

class InterviewList(BaseModel):
    questions: List[InterviewItem]
