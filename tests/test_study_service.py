import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import numpy as np
import faiss

from src.services.study_service import StudyService
from src.rag.engine import RAGEngine, DocumentChunk
from src.pdf.extractor import ExtractedPDF, PDFPageContent

@pytest.mark.asyncio
async def test_upload_pdf_empty_text():
    """Verifies that upload_pdf raises ValueError when the PDF contains 0 characters."""
    study_service = StudyService()
    
    # Mock pdf_extractor
    extracted_mock = ExtractedPDF(
        file_name="empty.pdf",
        page_count=1,
        total_characters=0,
        metadata={},
        pages=[PDFPageContent(page_number=1, text="")]
    )
    study_service.pdf_extractor.extract_text = MagicMock(return_value=extracted_mock)
    
    # Mock session
    session_mock = AsyncMock()
    
    with pytest.raises(ValueError, match="This PDF does not contain any extractable text"):
        await study_service.upload_pdf(
            session=session_mock,
            user_id=123,
            file_name="empty.pdf",
            file_bytes=b"dummy content"
        )

@pytest.mark.asyncio
async def test_create_index_dynamic_dimension():
    """Verifies that create_index dynamically sets the FAISS index dimension from embeddings."""
    ai_service_mock = AsyncMock()
    # Mock generate_batch_embeddings to return 3072-dimensional embeddings
    dummy_embedding = [0.1] * 3072
    ai_service_mock.generate_batch_embeddings = AsyncMock(return_value=[dummy_embedding])
    
    rag_engine = RAGEngine(ai_service=ai_service_mock)
    
    # Document chunks
    chunks = [
        DocumentChunk(pdf_id=1, page_number=1, text="Hello world", chunk_index=0)
    ]
    
    # Mock the write_index and file operations
    with patch("faiss.write_index") as mock_write_index, \
         patch("builtins.open", MagicMock()) as mock_open:
        
        await rag_engine.create_index(pdf_id=1, chunks=chunks)
        
        # Verify that IndexFlatIP was constructed with dimension 3072
        # The faiss.write_index first argument is the index object. Let's inspect its dimension.
        assert mock_write_index.called
        index_arg = mock_write_index.call_args[0][0]
        assert index_arg.d == 3072

@pytest.mark.asyncio
async def test_gemini_service_retry():
    """Verifies that GeminiService._execute_with_retry retries on 503 errors and eventually succeeds or propagates the error."""
    from src.ai.gemini import GeminiService
    from google.genai.errors import APIError
    
    service = GeminiService()
    
    # 1. Test successful after one retry
    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise APIError(503, {"error": {"message": "503 Service Unavailable"}})
        return "success"
        
    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        res = await service._execute_with_retry(mock_call)
        assert res == "success"
        assert call_count == 2
        assert mock_sleep.call_count == 1
        
    # 2. Test failure after maximum retries
    call_count = 0
    async def mock_failing_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise APIError(503, {"error": {"message": "503 Service Unavailable"}})
        
    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(APIError, match="503 Service Unavailable"):
            await service._execute_with_retry(mock_failing_call)
        assert call_count == 4  # Initial try + 3 retries
        assert mock_sleep.call_count == 3

@pytest.mark.asyncio
async def test_generate_questions_dynamic_limit():
    """Verifies that generate_questions uses the customized questions limit from settings in its prompt."""
    from src.models.schemas import MCQList
    study_service = StudyService()
    
    # Mock PDF repository return
    mock_pdf = MagicMock()
    mock_pdf.user_id = 999
    mock_pdf.file_name = "test.pdf"
    mock_pdf.extracted_text = "Some study guide text content."
    study_service.pdf_repo.get_pdf = AsyncMock(return_value=mock_pdf)
    
    # Mock study repository
    study_service.study_repo.get_questions = AsyncMock(return_value=[])
    study_service.study_repo.save_questions = AsyncMock()
    
    # Mock settings with limit 15
    mock_settings = MagicMock()
    mock_settings.max_questions_limit = 15
    mock_settings.preferred_language = "English"
    
    # Mock AI Service to return dummy MCQList so it doesn't crash on model validation
    mock_res = MCQList(questions=[])
    study_service.ai_service.generate_structured = AsyncMock(return_value=mock_res)
    
    with patch("src.services.user_service.UserService.get_user_settings", AsyncMock(return_value=mock_settings)):
        session_mock = AsyncMock()
        await study_service.generate_questions(session_mock, pdf_id=1, question_type="MCQ")
        
        # Verify generate_structured prompt contains 15
        assert study_service.ai_service.generate_structured.called
        call_args = study_service.ai_service.generate_structured.call_args
        prompt_arg = call_args[0][0]
        assert "15" in prompt_arg

@pytest.mark.asyncio
async def test_gemini_service_batch_embeddings_partitioning():
    """Verifies that generate_batch_embeddings partitions requests exceeding 100 items into batches of 100."""
    from src.ai.gemini import GeminiService
    service = GeminiService()
    
    # Mock return values for embed_content
    mock_emb = MagicMock()
    mock_emb.values = [0.1] * 768
    
    mock_response_1 = MagicMock()
    mock_response_1.embeddings = [mock_emb] * 100
    
    mock_response_2 = MagicMock()
    mock_response_2.embeddings = [mock_emb] * 100
    
    mock_response_3 = MagicMock()
    mock_response_3.embeddings = [mock_emb] * 50
    
    # We mock _execute_with_retry to return these sequentially
    service._execute_with_retry = AsyncMock(side_effect=[mock_response_1, mock_response_2, mock_response_3])
    
    texts = ["hello"] * 250
    res = await service.generate_batch_embeddings(texts)
    
    assert len(res) == 250
    assert service._execute_with_retry.call_count == 3
    
    # Check that calls had correct counts of texts
    call_args_list = service._execute_with_retry.call_args_list
    assert len(call_args_list[0][1]['contents']) == 100
    assert len(call_args_list[1][1]['contents']) == 100
    assert len(call_args_list[2][1]['contents']) == 50

@pytest.mark.asyncio
async def test_ask_question_tanglish():
    """Verifies that ask_question includes Tanglish instruction in RAG prompt."""
    study_service = StudyService()
    
    mock_pdf = MagicMock()
    mock_pdf.file_name = "test.pdf"
    study_service.pdf_repo.get_pdf = AsyncMock(return_value=mock_pdf)
    study_service.rag_engine.retrieve_relevant_chunks = AsyncMock(return_value=[])
    study_service.chat_repo.get_history = AsyncMock(return_value=[])
    study_service.chat_repo.add_message = AsyncMock()
    
    # Mock AI response
    study_service.ai_service.generate_text = AsyncMock(return_value="Intha book nalla iruku.")
    
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.preferred_language = "English"
    
    with patch("src.services.user_service.UserService.get_user_settings", AsyncMock(return_value=mock_settings)):
        session_mock = AsyncMock()
        res = await study_service.ask_question(session_mock, user_id=999, pdf_id=1, question="solunga?")
        
        assert res.answer == "Intha book nalla iruku."
        assert study_service.ai_service.generate_text.called
        call_args = study_service.ai_service.generate_text.call_args
        prompt = call_args[1]['prompt']
        sys_instr = call_args[1]['system_instruction']
        
        # Verify instructions mention Tanglish
        assert "Tanglish" in prompt
        assert "Tanglish" in sys_instr

def test_detect_pdf_language():
    study_service = StudyService()
    
    # English text
    assert study_service.detect_pdf_language("This is a simple english text document.") == "English"
    # Empty/None text
    assert study_service.detect_pdf_language("") == "English"
    # Tamil text
    assert study_service.detect_pdf_language("தமிழ் மொழி உலகின் மிக மூத்த மொழிகளில் ஒன்றாகும்.") == "Tamil"

@pytest.mark.asyncio
async def test_generate_questions_auto_detect_language():
    from src.models.schemas import MCQList
    study_service = StudyService()
    
    mock_pdf = MagicMock()
    mock_pdf.user_id = 999
    mock_pdf.file_name = "test_tamil.pdf"
    mock_pdf.extracted_text = "தமிழ் மொழி உலகின் மிக மூத்த மொழிகளில் ஒன்றாகும்."
    study_service.pdf_repo.get_pdf = AsyncMock(return_value=mock_pdf)
    study_service.study_repo.get_questions = AsyncMock(return_value=[])
    study_service.study_repo.save_questions = AsyncMock()
    
    # Mock settings with preferred_language = "Auto"
    mock_settings = MagicMock()
    mock_settings.max_questions_limit = 5
    mock_settings.preferred_language = "Auto"
    
    mock_res = MCQList(questions=[])
    study_service.ai_service.generate_structured = AsyncMock(return_value=mock_res)
    
    with patch("src.services.user_service.UserService.get_user_settings", AsyncMock(return_value=mock_settings)):
        session_mock = AsyncMock()
        await study_service.generate_questions(session_mock, pdf_id=1, question_type="MCQ")
        
        # Verify it auto-detected Tamil and passed it in the prompt instructions
        assert study_service.ai_service.generate_structured.called
        call_args = study_service.ai_service.generate_structured.call_args
        sys_instr = call_args[0][2]
        prompt = call_args[0][0]
        assert "Tamil" in sys_instr
        assert "Tamil" in prompt

@pytest.mark.asyncio
async def test_gemini_service_rate_limit_retry_parsing():
    """Verifies that _execute_with_retry parses explicit retry delay from APIError messages and sleeps accordingly."""
    from src.ai.gemini import GeminiService
    from google.genai.errors import APIError
    
    class MockAPIError(APIError):
        def __init__(self, message, code):
            self.message = message
            self.code = code
        def __str__(self):
            return self.message

    service = GeminiService()
    mock_error = MockAPIError("429 Resource exhausted. Please retry in 4.5s.", 429)
    
    call_count = 0
    async def mock_func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise mock_error
        return "Success"
        
    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        res = await service._execute_with_retry(mock_func)
        assert res == "Success"
        assert call_count == 2
        assert mock_sleep.called
        # Check that it slept for 4.5 + 1.5 = 6.0 seconds
        sleep_arg = mock_sleep.call_args[0][0]
        assert abs(sleep_arg - 6.0) < 0.01

@pytest.mark.asyncio
async def test_gemini_service_fallback_api_key_switching():
    """Verifies that generate_text switches to OpenRouter when rate limited and GEMINI_API_KEY_FALLBACK is set."""
    from src.ai.gemini import GeminiService
    from google.genai.errors import APIError
    
    class MockAPIError(APIError):
        def __init__(self, message, code):
            self.message = message
            self.code = code
        def __str__(self):
            return self.message

    service = GeminiService()
    mock_error = MockAPIError("429 Quota exceeded.", 429)
    
    # Mock Google SDK client to raise rate limit exception, trigger the real retry loop
    service.client.aio.models.generate_content = AsyncMock(side_effect=mock_error)
    
    # Mock _call_openrouter to return fallback success text
    service._call_openrouter = AsyncMock(return_value="OpenRouter Fallback Success")
    
    from src.config.settings import settings
    with patch.object(settings, "GEMINI_API_KEY_FALLBACK", "sk-or-fallback-value"):
        res = await service.generate_text("test prompt")
        assert res == "OpenRouter Fallback Success"
        assert service._active_key == "fallback"
        service._call_openrouter.assert_called_with("test prompt", None)

@pytest.mark.asyncio
async def test_study_service_fallback_summary_injection():
    """Verifies that generate_questions injects the cached Gemini summary into the prompt when fallback is active."""
    from src.services.study_service import StudyService
    from src.models.schemas import MCQList
    
    study_service = StudyService()
    
    # Enable fallback key
    study_service.ai_service._active_key = 'fallback'
    
    mock_pdf = MagicMock()
    mock_pdf.user_id = 999
    mock_pdf.file_name = "test.pdf"
    mock_pdf.extracted_text = "Full long raw text."
    study_service.pdf_repo.get_pdf = AsyncMock(return_value=mock_pdf)
    
    # Mock cached summary return
    mock_summary = MagicMock()
    mock_summary.summary_text = "This is the Gemini generated summary."
    mock_summary.important_topics = "Gemini topics."
    mock_summary.explain_like_10 = "Gemini simplified concepts."
    study_service.study_repo.get_summary = AsyncMock(return_value=mock_summary)
    
    study_service.study_repo.get_questions = AsyncMock(return_value=[])
    study_service.study_repo.save_questions = AsyncMock()
    
    mock_res = MCQList(questions=[])
    study_service.ai_service.generate_structured = AsyncMock(return_value=mock_res)
    
    mock_settings = MagicMock()
    mock_settings.max_questions_limit = 5
    mock_settings.preferred_language = "English"
    
    with patch("src.services.user_service.UserService.get_user_settings", AsyncMock(return_value=mock_settings)):
        session_mock = AsyncMock()
        await study_service.generate_questions(session_mock, pdf_id=1, question_type="MCQ")
        
        # Verify get_summary was called to fetch the cached summary
        study_service.study_repo.get_summary.assert_called_once_with(session_mock, 1)
        
        # Verify the prompt sent to structured generation contains the cached Gemini summary
        assert study_service.ai_service.generate_structured.called
        call_args = study_service.ai_service.generate_structured.call_args
        prompt = call_args[0][0]
        assert "SUMMARY OF THE DOCUMENT (Generated by Gemini)" in prompt
        assert "This is the Gemini generated summary." in prompt

def test_pdf_menu_keyboards():
    """Verifies that the PDF study menu and chat keyboards render correct buttons and callback queries."""
    from src.bot.keyboards.inline import get_pdf_menu_keyboard, get_chat_pdf_keyboard
    
    # 1. Test PDF Menu Keyboard
    menu_kb = get_pdf_menu_keyboard(456)
    buttons = []
    for row in menu_kb.inline_keyboard:
        for btn in row:
            buttons.append((btn.text, btn.callback_data))
            
    # Verify Chat with PDF is in the menu keyboard
    assert ("💬 Chat with PDF", "chat_pdf_456") in buttons
    # Verify Clear RAG Chat is no longer directly in the main menu
    assert not any("clear_chat_456" in item[1] for item in buttons)

    # 2. Test Chat PDF Keyboard
    chat_kb = get_chat_pdf_keyboard(456)
    chat_buttons = []
    for row in chat_kb.inline_keyboard:
        for btn in row:
            chat_buttons.append((btn.text, btn.callback_data))
            
    assert ("🧹 Clear Chat History", "clear_chat_456") in chat_buttons
    assert ("↩️ Back to Study Menu", "select_pdf_456") in chat_buttons



