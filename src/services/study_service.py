import logging
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.pdf.extractor import PDFExtractor
from src.rag.engine import RAGEngine
from src.ai.gemini import GeminiService
from src.database.repository import PDFRepository, ChatHistoryRepository, StudyRepository
from src.models.schemas import (
    SummaryResponse, MCQList, FlashcardList, QAList, InterviewList,
    AskQuestionResponse, UploadedPDFResponse
)
from src.config.settings import settings

logger = logging.getLogger(__name__)

class StudyService:
    """Service coordinates PDF processing, RAG searches, and study resource generations."""

    def __init__(self) -> None:
        self.ai_service = GeminiService()
        self.pdf_extractor = PDFExtractor()
        self.rag_engine = RAGEngine(self.ai_service)
        
        self.pdf_repo = PDFRepository()
        self.chat_repo = ChatHistoryRepository()
        self.study_repo = StudyRepository()

    def detect_pdf_language(self, extracted_text: str) -> str:
        """Detects if the PDF is primarily in Tamil or English by scanning for Tamil characters."""
        if not extracted_text:
            return "English"
        # Count how many characters are in the Tamil Unicode block range (0x0B80 - 0x0BFF)
        tamil_char_count = sum(1 for c in extracted_text if 0x0B80 <= ord(c) <= 0x0BFF)
        # If more than 0.5% of characters are Tamil, classify as Tamil
        if tamil_char_count > 0 and (tamil_char_count / len(extracted_text)) > 0.005:
            return "Tamil"
        return "English"

    async def upload_pdf(self, session: AsyncSession, user_id: int, file_name: str, file_bytes: bytes) -> UploadedPDFResponse:
        """
        Processes PDF upload: saves file, extracts text, writes DB metadata,
        and constructs RAG search index.
        """
        # Save file to upload directory
        clean_file_name = "".join(c for c in file_name if c.isalnum() or c in "._- ")
        timestamp = int(time.time())
        unique_name = f"{user_id}_{timestamp}_{clean_file_name}"
        
        upload_dir = settings.upload_path
        file_path = upload_dir / unique_name
        
        logger.info(f"Saving PDF to disk: {file_path}")
        def write_file():
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        await asyncio.to_thread(write_file)

        try:
            # 1. Extract text and validate in background thread
            extracted = await asyncio.to_thread(self.pdf_extractor.extract_text, file_path)
            if extracted.total_characters == 0:
                raise ValueError("This PDF does not contain any extractable text. It might be scanned or image-only. Please upload a PDF with a text layer.")
            
            # 2. Save metadata to DB
            pdf_db = await self.pdf_repo.create_pdf(
                session=session,
                user_id=user_id,
                file_name=file_name,
                file_path=str(file_path),
                file_size=len(file_bytes),
                page_count=extracted.page_count,
                char_count=extracted.total_characters,
                extracted_text=extracted.full_text
            )
            
            # 3. Create FAISS index
            chunks = await asyncio.to_thread(self.rag_engine.chunk_pdf, pdf_id=pdf_db.id, pages=extracted.pages)
            await self.rag_engine.create_index(pdf_id=pdf_db.id, chunks=chunks)
            
            return UploadedPDFResponse.model_validate(pdf_db)

        except Exception as e:
            logger.exception("Error processing PDF upload")
            if file_path.exists():
                file_path.unlink()  # Cleanup file
            raise

    async def get_pdf(self, session: AsyncSession, pdf_id: int) -> Optional[Any]:
        """Retrieves PDF metadata."""
        return await self.pdf_repo.get_pdf(session, pdf_id)

    async def list_user_pdfs(self, session: AsyncSession, user_id: int) -> List[Any]:
        """Retrieves list of all PDFs uploaded by a user."""
        return await self.pdf_repo.get_user_pdfs(session, user_id)

    async def delete_pdf(self, session: AsyncSession, pdf_id: int) -> bool:
        """Deletes a PDF record, local files, and FAISS vector indexes."""
        pdf = await self.pdf_repo.get_pdf(session, pdf_id)
        if not pdf:
            return False
            
        # 1. Delete vector index
        self.rag_engine.delete_index(pdf_id)
        
        # 2. Delete physical PDF file
        file_path = Path(pdf.file_path)
        if file_path.exists():
            file_path.unlink()
            
        # 3. Delete database records (Cascades automatically deletes chats, questions, summaries)
        return await self.pdf_repo.delete_pdf(session, pdf_id)

    async def generate_summary(self, session: AsyncSession, pdf_id: int) -> SummaryResponse:
        """Generates or retrieves cached summary, key topics, and simplified explanations."""
        # Check cache
        cached = await self.study_repo.get_summary(session, pdf_id)
        if cached:
            return SummaryResponse(
                summary=cached.summary_text,
                important_topics=cached.important_topics,
                explain_like_10=cached.explain_like_10
            )

        pdf = await self.pdf_repo.get_pdf(session, pdf_id)
        if not pdf:
            raise ValueError("PDF not found.")

        # Resolve preferred language
        from src.services.user_service import UserService
        user_service = UserService()
        settings = await user_service.get_user_settings(session, pdf.user_id)
        preferred_lang = settings.preferred_language if settings else "Auto"
        if preferred_lang == "Auto":
            preferred_lang = self.detect_pdf_language(pdf.extracted_text)

        # Construct generation prompt
        prompt = (
            f"Analyze the following text from the document '{pdf.file_name}'.\n"
            f"Provide an overall detailed summary, list the most important topics, and explain the core concepts simplified as if explaining to a 10-year-old.\n"
            f"Generate all output fields in the preferred language: {preferred_lang}.\n\n"
            f"TEXT CONTENT:\n{pdf.extracted_text[:40000]}"  # Cap length to avoid token spill on huge text
        )
        
        sys_instruction = f"You are an expert tutor helping a student learn complex topics from text documents. Output your entire response in {preferred_lang}."
        
        # Request structured response matching SummaryResponse
        summary_result = await self.ai_service.generate_structured(
            prompt=prompt,
            response_schema=SummaryResponse,
            system_instruction=sys_instruction
        )

        # Cache results in DB
        await self.study_repo.save_summary(
            session=session,
            pdf_id=pdf_id,
            summary_text=summary_result.summary,
            important_topics=summary_result.important_topics,
            explain_like_10=summary_result.explain_like_10
        )

        return summary_result

    async def generate_questions(self, session: AsyncSession, pdf_id: int, question_type: str) -> List[Dict[str, Any]]:
        """
        Generates study questions (MCQs, QA, Flashcard, Interview)
        from a document, returning lists of structured items.
        """
        question_type = question_type.upper()
        if question_type not in ["MCQ", "FLASHCARD", "QA", "INTERVIEW"]:
            raise ValueError(f"Invalid question type '{question_type}' requested.")

        pdf = await self.pdf_repo.get_pdf(session, pdf_id)
        if not pdf:
            raise ValueError("PDF not found.")

        # Resolve user settings limit
        from src.services.user_service import UserService
        user_service = UserService()
        settings = await user_service.get_user_settings(session, pdf.user_id)
        limit = settings.max_questions_limit if settings else 5

        preferred_lang = settings.preferred_language if settings else "Auto"
        if preferred_lang == "Auto":
            preferred_lang = self.detect_pdf_language(pdf.extracted_text)

        # Check DB Cache for matching question count
        cached = await self.study_repo.get_questions(session, pdf_id, question_type)
        if cached:
            for cache_entry in cached:
                if len(cache_entry.content) == limit:
                    return cache_entry.content

        # Map type to prompting and schema
        sys_instruction = (
            "You are an AI examination board. Your goal is to write educational questions based strictly and only on the provided text. "
            "Maintain 100% factual accuracy relative to the text. Do not make up any facts, assume external details, or hallucinate. "
            f"Generate all output fields (questions, options, explanations, card fronts/backs, answers) in the preferred language: {preferred_lang}. "
            "Ensure that every generated item is unique and covers a completely different fact, section, or concept of the document. "
            "Strictly avoid any duplicate questions, highly similar questions, or overlapping concepts in the output."
        )
        
        # Determine source text (use cached Gemini summary if fallback is active)
        source_text = pdf.extracted_text[:40000]
        if self.ai_service._active_key == 'fallback':
            summary_cache = await self.study_repo.get_summary(session, pdf_id)
            if summary_cache:
                source_text = (
                    f"SUMMARY OF THE DOCUMENT (Generated by Gemini):\n{summary_cache.summary_text}\n\n"
                    f"IMPORTANT TOPICS:\n{summary_cache.important_topics}\n\n"
                    f"CORE CONCEPTS:\n{summary_cache.explain_like_10}"
                )
                logger.info("Using cached Gemini summary as source context for fallback API question generation.")

        prompt = f"Write study materials using the following text from the document '{pdf.file_name}':\n\nTEXT:\n{source_text}\n\n"

        if question_type == "MCQ":
            prompt += f"Create {limit} unique multiple choice questions (MCQs) covering key ideas with exactly 4 options, a 0-indexed correct option key, and brief logical explanations. Ensure every question is distinct with absolutely no repeats or duplicate questions. Output everything in {preferred_lang}."
            res = await self.ai_service.generate_structured(prompt, MCQList, sys_instruction)
            content = [item.model_dump() for item in res.questions]

        elif question_type == "FLASHCARD":
            prompt += f"Create {limit} unique double-sided flashcards with a concise 'front' (term or question) and an explanatory 'back' (definition/answer). Ensure every flashcard is distinct with absolutely no repeats or duplicate terms. Output everything in {preferred_lang}."
            res = await self.ai_service.generate_structured(prompt, FlashcardList, sys_instruction)
            content = [item.model_dump() for item in res.flashcards]

        elif question_type == "QA":
            prompt += f"Create {limit} unique conceptual short questions and detailed study answers. Ensure every question tests a distinct concept from the text with absolutely no repeats or duplicate questions. Output everything in {preferred_lang}."
            res = await self.ai_service.generate_structured(prompt, QAList, sys_instruction)
            content = [item.model_dump() for item in res.items]

        else:  # INTERVIEW
            prompt += f"Create {limit} unique tough interview questions designed to test deep comprehension, alongside model answers. Ensure every question covers a distinct scenario or concept with absolutely no repeats or overlapping questions. Output everything in {preferred_lang}."
            res = await self.ai_service.generate_structured(prompt, InterviewList, sys_instruction)
            content = [item.model_dump() for item in res.questions]

        # Cache in DB
        await self.study_repo.save_questions(session, pdf_id, question_type, content)
        return content

    async def ask_question(self, session: AsyncSession, user_id: int, pdf_id: int, question: str) -> AskQuestionResponse:
        """
        Uses RAG to answer user questions using only relevant pages as context.
        Injects conversational history.
        """
        pdf = await self.pdf_repo.get_pdf(session, pdf_id)
        if not pdf:
            raise ValueError("PDF not found.")

        # 1. Retrieve top relevant chunks
        chunks = await self.rag_engine.retrieve_relevant_chunks(pdf_id, question, top_k=5)
        
        # Format retrieval context and collect source citations
        context_blocks = []
        sources = []
        seen_pages = set()
        
        for chunk in chunks:
            context_blocks.append(f"[Page {chunk.page_number}]: {chunk.text}")
            if chunk.page_number not in seen_pages:
                sources.append({"page_number": chunk.page_number})
                seen_pages.add(chunk.page_number)
                
        context_str = "\n\n".join(context_blocks)
        
        # 2. Get recent chat history
        history = await self.chat_repo.get_history(session, user_id, pdf_id, limit=6)
        history_str = ""
        if history:
            history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in history])

        # Determine fallback context inclusion (inject Gemini summary)
        summary_info = ""
        if self.ai_service._active_key == 'fallback':
            summary_cache = await self.study_repo.get_summary(session, pdf_id)
            if summary_cache:
                summary_info = (
                    f"DOCUMENT SUMMARY (Generated by Gemini when active):\n{summary_cache.summary_text}\n\n"
                    f"IMPORTANT TOPICS:\n{summary_cache.important_topics}\n\n"
                )
                logger.info("Injecting cached Gemini summary into RAG context for fallback API.")

        # 3. Create RAG prompt
        rag_prompt = (
            f"You are a helpful study assistant. You answer questions about a PDF document called '{pdf.file_name}' using ONLY the context blocks provided below.\n"
            f"If the answer cannot be found in the context blocks, politely state that you do not know or that it isn't mentioned in the document. Do not make things up.\n"
            f"Output your final response in the same language as the User Question. If the user query is in Tanglish (Tamil written with the English alphabet, e.g., 'ithu enna?', 'solunga'), reply in Tanglish. If the query is in standard Tamil, reply in Tamil. If in English, reply in English.\n\n"
            f"CONTEXT BLOCKS:\n{summary_info}{context_str}\n\n"
            f"CHAT HISTORY:\n{history_str}\n\n"
            f"User Question: {question}"
        )
        
        sys_instruction = (
            "You are an AI study tutor conducting a Q&A session on a text document. Base your answers strictly on the retrieved context blocks. "
            "Analyze the User Question and output your final response in the exact same language and script (supporting English, Tamil Unicode script, and Tanglish - Tamil written using the English alphabet)."
        )

        # 4. Generate answer
        answer = await self.ai_service.generate_text(
            prompt=rag_prompt,
            system_instruction=sys_instruction
        )

        # 5. Log chat interactions to DB
        await self.chat_repo.add_message(session, user_id, pdf_id, "user", question)
        await self.chat_repo.add_message(session, user_id, pdf_id, "model", answer)

        return AskQuestionResponse(answer=answer, sources=sources)

    async def clear_chat_history(self, session: AsyncSession, user_id: int, pdf_id: int) -> None:
        """Clears chat histories for a given document."""
        await self.chat_repo.clear_history(session, user_id, pdf_id)
