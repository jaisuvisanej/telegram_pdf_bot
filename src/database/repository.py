import logging
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import User, UserSetting, UploadedPDF, ChatHistory, GeneratedQuestion, GeneratedSummary
from src.models.schemas import UserCreate, UserSettingUpdate

logger = logging.getLogger(__name__)

class UserRepository:
    """Repository managing User and UserSetting data transactions."""

    async def get_user(self, session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Fetches a user profile by Telegram User ID, eagerly loading settings."""
        result = await session.execute(
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(User.settings))
        )
        return result.scalar_one_or_none()

    async def get_or_create_user(
        self, session: AsyncSession, user_data: UserCreate
    ) -> User:
        """
        Retrieves a user by telegram_id, or creates a new user with default settings.
        """
        user = await self.get_user(session, user_data.telegram_id)
        if user:
            # Update username and first_name if changed
            if user.username != user_data.username or user.first_name != user_data.first_name:
                user.username = user_data.username
                user.first_name = user_data.first_name
                await session.commit()
            return user

        # Create new user
        logger.info(f"Creating new user in DB: {user_data.telegram_id}")
        user = User(
            telegram_id=user_data.telegram_id,
            username=user_data.username,
            first_name=user_data.first_name
        )
        session.add(user)
        await session.flush()  # Ensure user is written to establish foreign keys

        # Attach default settings
        settings = UserSetting(
            user_id=user_data.telegram_id,
            preferred_language="English",
            max_questions_limit=5
        )
        session.add(settings)
        await session.commit()
        
        # Reload to get full relations
        return await self.get_user(session, user_data.telegram_id)

    async def update_settings(
        self, session: AsyncSession, telegram_id: int, settings_data: UserSettingUpdate
    ) -> Optional[UserSetting]:
        """Updates user configuration settings."""
        result = await session.execute(
            select(UserSetting).where(UserSetting.user_id == telegram_id)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Fallback: create if missing
            settings = UserSetting(user_id=telegram_id)
            session.add(settings)
            
        settings.preferred_language = settings_data.preferred_language
        settings.max_questions_limit = settings_data.max_questions_limit
        settings.current_pdf_id = settings_data.current_pdf_id
        
        await session.commit()
        await session.refresh(settings)
        return settings


class PDFRepository:
    """Repository managing uploaded PDFs."""

    async def create_pdf(
        self,
        session: AsyncSession,
        user_id: int,
        file_name: str,
        file_path: str,
        file_size: int,
        page_count: int,
        char_count: int,
        extracted_text: str
    ) -> UploadedPDF:
        """Saves a new PDF record in the database."""
        logger.info(f"Saving PDF metadata to DB for user {user_id}: {file_name}")
        pdf = UploadedPDF(
            user_id=user_id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            page_count=page_count,
            char_count=char_count,
            extracted_text=extracted_text
        )
        session.add(pdf)
        await session.commit()
        await session.refresh(pdf)
        return pdf

    async def get_pdf(self, session: AsyncSession, pdf_id: int) -> Optional[UploadedPDF]:
        """Retrieves a PDF record by ID."""
        result = await session.execute(
            select(UploadedPDF).where(UploadedPDF.id == pdf_id)
        )
        return result.scalar_one_or_none()

    async def get_user_pdfs(self, session: AsyncSession, user_id: int) -> List[UploadedPDF]:
        """Lists all PDFs uploaded by a specific user, sorted by upload date."""
        result = await session.execute(
            select(UploadedPDF)
            .where(UploadedPDF.user_id == user_id)
            .order_by(UploadedPDF.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_pdf(self, session: AsyncSession, pdf_id: int) -> bool:
        """Deletes a PDF record from the database."""
        pdf = await self.get_pdf(session, pdf_id)
        if not pdf:
            return False
            
        await session.delete(pdf)
        await session.commit()
        return True


class ChatHistoryRepository:
    """Repository managing conversations with PDFs."""

    async def add_message(
        self, session: AsyncSession, user_id: int, pdf_id: Optional[int], role: str, content: str
    ) -> ChatHistory:
        """Adds a message to the conversation history."""
        msg = ChatHistory(
            user_id=user_id,
            pdf_id=pdf_id,
            role=role,
            content=content
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg

    async def get_history(
        self, session: AsyncSession, user_id: int, pdf_id: Optional[int], limit: int = 20
    ) -> List[ChatHistory]:
        """Fetches the latest chat messages for context injection."""
        result = await session.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id, ChatHistory.pdf_id == pdf_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        # Reverse list to keep chronological order
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def clear_history(self, session: AsyncSession, user_id: int, pdf_id: Optional[int]) -> None:
        """Clears chat history for a PDF."""
        await session.execute(
            delete(ChatHistory)
            .where(ChatHistory.user_id == user_id, ChatHistory.pdf_id == pdf_id)
        )
        await session.commit()


class StudyRepository:
    """Repository managing study utilities (summaries, flashcards, MCQs)."""

    async def save_summary(
        self, session: AsyncSession, pdf_id: int, summary_text: str, important_topics: str, explain_like_10: str
    ) -> GeneratedSummary:
        """Saves or updates a PDF's summary and themes."""
        result = await session.execute(
            select(GeneratedSummary).where(GeneratedSummary.pdf_id == pdf_id)
        )
        summary = result.scalar_one_or_none()

        if summary:
            summary.summary_text = summary_text
            summary.important_topics = important_topics
            summary.explain_like_10 = explain_like_10
        else:
            summary = GeneratedSummary(
                pdf_id=pdf_id,
                summary_text=summary_text,
                important_topics=important_topics,
                explain_like_10=explain_like_10
            )
            session.add(summary)

        await session.commit()
        await session.refresh(summary)
        return summary

    async def get_summary(self, session: AsyncSession, pdf_id: int) -> Optional[GeneratedSummary]:
        """Retrieves a cached PDF summary."""
        result = await session.execute(
            select(GeneratedSummary).where(GeneratedSummary.pdf_id == pdf_id)
        )
        return result.scalar_one_or_none()

    async def save_questions(
        self, session: AsyncSession, pdf_id: int, question_type: str, content: List[dict]
    ) -> GeneratedQuestion:
        """Saves generated questions (MCQs, QA, Flashcards, Interview) for caching."""
        question = GeneratedQuestion(
            pdf_id=pdf_id,
            question_type=question_type,
            content=content
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        return question

    async def get_questions(
        self, session: AsyncSession, pdf_id: int, question_type: str
    ) -> List[GeneratedQuestion]:
        """Retrieves generated questions of a specific type."""
        result = await session.execute(
            select(GeneratedQuestion)
            .where(GeneratedQuestion.pdf_id == pdf_id, GeneratedQuestion.question_type == question_type)
            .order_by(GeneratedQuestion.created_at.desc())
        )
        return list(result.scalars().all())
