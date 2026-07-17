import logging
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_db
from src.services.study_service import StudyService
from src.services.user_service import UserService
from src.models.schemas import UploadedPDFResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pdfs", tags=["PDFs"])

study_service = StudyService()
user_service = UserService()

async def get_current_user_id(
    x_telegram_user_id: int = Header(..., alias="X-Telegram-User-Id", description="Telegram User ID for session context"),
    session: AsyncSession = Depends(get_db)
) -> int:
    """Dependency to validate the presence of a Telegram user in headers and auto-register them."""
    try:
        # Auto-create user profile in DB to handle foreign keys gracefully
        await user_service.get_or_create_user(session, telegram_id=x_telegram_user_id)
        return x_telegram_user_id
    except Exception as e:
        logger.error(f"Error resolving user {x_telegram_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to authenticate or establish user profile context."
        )

@router.post("/upload", response_model=UploadedPDFResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(..., description="The PDF study document to upload"),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Uploads a PDF, extracts text, indexes it in FAISS vector store, and saves records."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF files are accepted."
        )
        
    try:
        file_bytes = await file.read()
        
        # Pre-validate file size to save system memory/processing spikes
        from src.config.settings import settings
        if len(file_bytes) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
            )
            
        pdf_response = await study_service.upload_pdf(
            session=session,
            user_id=user_id,
            file_name=file.filename,
            file_bytes=file_bytes
        )
        return pdf_response
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error handling PDF upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while processing PDF."
        )

@router.get("", response_model=List[UploadedPDFResponse])
async def list_pdfs(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Retrieves all PDFs uploaded by the authenticated user."""
    pdfs = await study_service.list_user_pdfs(session, user_id)
    return [UploadedPDFResponse.model_validate(p) for p in pdfs]

@router.delete("/{pdf_id}", status_code=status.HTTP_200_OK)
async def delete_pdf(
    pdf_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db)
):
    """Deletes the PDF metadata, binary file, and FAISS indices if owned by user."""
    pdf = await study_service.get_pdf(session, pdf_id)
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found."
        )
        
    if pdf.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this file."
        )
        
    success = await study_service.delete_pdf(session, pdf_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete PDF from database."
        )
        
    return {"message": f"Successfully deleted PDF ID {pdf_id}."}
