import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_db
from src.services.study_service import StudyService
from src.backend.routers.pdfs import get_current_user_id
from src.models.schemas import SummaryResponse, AskQuestionRequest, AskQuestionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/study", tags=["Study & AI"])

study_service = StudyService()

async def verify_pdf_ownership(pdf_id: int, user_id: int, session: AsyncSession) -> None:
    """Verifies that the PDF exists and is owned by the current user."""
    pdf = await study_service.get_pdf(session, pdf_id)
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF document not found."
        )
    if pdf.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You do not own this study document."
        )

@router.get("/summary/{pdf_id}", response_model=SummaryResponse)
async def get_pdf_summary(
    pdf_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Generates (or returns cached) overall summary, key topics, and simplified descriptions."""
    await verify_pdf_ownership(pdf_id, user_id, session)
    try:
        return await study_service.generate_summary(session, pdf_id)
    except Exception as e:
        logger.error(f"Error generating summary for PDF {pdf_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary using AI."
        )

@router.get("/questions/{pdf_id}", response_model=List[Dict[str, Any]])
async def get_pdf_questions(
    pdf_id: int,
    type: str = Query(..., description="Type of questions to generate: MCQ, FLASHCARD, QA, INTERVIEW"),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Generates study materials (MCQs, QA, Flashcards, or Interview Questions) based on PDF text."""
    await verify_pdf_ownership(pdf_id, user_id, session)
    question_type = type.upper()
    if question_type not in ["MCQ", "FLASHCARD", "QA", "INTERVIEW"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question type. Choose from: MCQ, FLASHCARD, QA, INTERVIEW"
        )
    try:
        return await study_service.generate_questions(session, pdf_id, question_type)
    except Exception as e:
        logger.error(f"Error generating {question_type} questions for PDF {pdf_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate study materials."
        )

@router.post("/chat/{pdf_id}", response_model=AskQuestionResponse)
async def chat_with_pdf(
    pdf_id: int,
    request: AskQuestionRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Queries the PDF vector database (RAG) and returns an AI response citing source pages."""
    await verify_pdf_ownership(pdf_id, user_id, session)
    try:
        return await study_service.ask_question(
            session=session,
            user_id=user_id,
            pdf_id=pdf_id,
            question=request.question
        )
    except Exception as e:
        logger.error(f"Error executing RAG search for PDF {pdf_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete PDF query session."
        )

@router.delete("/chat/{pdf_id}", status_code=status.HTTP_200_OK)
async def clear_chat_session(
    pdf_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Clears the active chat dialogue history for the target document."""
    await verify_pdf_ownership(pdf_id, user_id, session)
    try:
        await study_service.clear_chat_history(session, user_id, pdf_id)
        return {"message": "Chat history cleared successfully."}
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear conversation logs."
        )
