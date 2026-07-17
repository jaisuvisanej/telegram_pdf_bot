import logging
from typing import List, Optional, Type, TypeVar
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel

from src.ai.base import BaseLLMService, T
from src.config.settings import settings

logger = logging.getLogger(__name__)

class GeminiService(BaseLLMService):
    """Concrete implementation of BaseLLMService using the official Google Gemini SDK."""

    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY environment variable is not set. Gemini API calls will fail.")
        
        # Initialize the official GenAI Client
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._active_key = 'main'
        self.model_name = settings.GEMINI_MODEL
        self.embedding_model_name = settings.EMBEDDING_MODEL

    async def _execute_with_retry(self, func, *args, **kwargs):
        """Executes a Gemini client async function with exponential backoff on 429/503/ResourceExhausted errors."""
        import asyncio
        import random
        import re
        max_retries = 3
        initial_delay = 1.0
        backoff_factor = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except APIError as e:
                code = getattr(e, 'code', None)
                err_msg = str(e).lower()
                is_retriable = (
                    code in [429, 503] or
                    any(kw in err_msg for kw in ["503", "429", "resource exhausted", "unavailable", "demand", "rate limit", "temporarily"])
                )
                # Determine if it's a daily/monthly quota exhaustion limit
                is_quota_exhausted = any(kw in err_msg for kw in ["quota exceeded", "exceeded your current quota", "requests per day", "billing", "credits", "free tier"])
                # Determine if it's a permission denied/blocked key error
                is_permission_denied = (
                    code == 403 or
                    any(kw in err_msg for kw in ["permission_denied", "permission denied", "denied access", "forbidden", "403"])
                )
                
                # Switch to fallback key if quota is exhausted or permission is denied
                if settings.GEMINI_API_KEY_FALLBACK and self._active_key == 'main' and (is_quota_exhausted or is_permission_denied):
                    logger.warning(
                        f"Main Gemini API key issue encountered (quota_exhausted={is_quota_exhausted}, "
                        f"permission_denied={is_permission_denied}). Switching to OpenRouter fallback API key..."
                    )
                    self._active_key = 'fallback'
                    raise RuntimeError("Switched to fallback OpenRouter key.")
                
                if is_retriable and attempt < max_retries:

                    # Attempt to extract explicit retry delay from Gemini rate limit error
                    delay = None
                    try:
                        match = re.search(r"retry in ([\d\.]+)s", str(e), re.IGNORECASE)
                        if match:
                            delay = float(match.group(1)) + 1.5  # 1.5s safety buffer
                    except Exception:
                        pass
                        
                    if not delay:
                        delay = initial_delay * (backoff_factor ** attempt) + random.uniform(0.0, 0.5)
                        
                    logger.warning(
                        f"Gemini API returned temporary rate limit/temporary error (code={code}). "
                        f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})... Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

    async def _call_openrouter(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Type[T]] = None
    ) -> str:
        """Call OpenRouter API as a fallback when the main Gemini key is exhausted."""
        import httpx
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GEMINI_API_KEY_FALLBACK}",
            "Content-Type": "application/json",
        }
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 4000  # Explicitly limit tokens to prevent OpenRouter 402 estimation errors
        }
        
        if response_schema:
            payload["response_format"] = {"type": "json_object"}
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"OpenRouter API error (status={response.status_code}): {response.text}")
            
            res_json = response.json()
            choices = res_json.get("choices", [])
            if not choices:
                raise RuntimeError(f"Invalid OpenRouter response: {res_json}")
            
            return choices[0].get("message", {}).get("content", "")

    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ) -> str:
        """Generates plain text response using Gemini client.aio or fallback OpenRouter."""
        if self._active_key == 'fallback':
            return await self._call_openrouter(prompt, system_instruction)

        logger.debug(f"Generating text with model {self.model_name}. Prompt length: {len(prompt)}")
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
        )
        
        try:
            response = await self._execute_with_retry(
                self.client.aio.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text or ""
        except Exception as e:
            if self._active_key == 'fallback':
                logger.info("Retrying text generation using OpenRouter fallback...")
                return await self._call_openrouter(prompt, system_instruction)
            logger.error(f"Gemini API Error in generate_text: {e}")
            raise RuntimeError(f"Gemini API returned an error: {str(e)}")

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None
    ) -> T:
        """Forces Gemini to generate structured output matching a Pydantic schema."""
        if self._active_key == 'fallback':
            text = await self._call_openrouter(prompt, system_instruction, response_schema)
            import re
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
                cleaned = cleaned.strip()
            return response_schema.model_validate_json(cleaned)

        logger.debug(f"Generating structured response. Prompt length: {len(prompt)}")
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=response_schema
        )
        
        try:
            response = await self._execute_with_retry(
                self.client.aio.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            # The client parses json dynamically if response_schema is defined.
            if hasattr(response, 'parsed') and response.parsed is not None:
                return response.parsed
                
            text_response = response.text or ""
            return response_schema.model_validate_json(text_response)
            
        except Exception as e:
            if self._active_key == 'fallback':
                logger.info("Retrying structured generation using OpenRouter fallback...")
                text = await self._call_openrouter(prompt, system_instruction, response_schema)
                import re
                cleaned = text.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
                    cleaned = re.sub(r"\n?```$", "", cleaned)
                    cleaned = cleaned.strip()
                return response_schema.model_validate_json(cleaned)
            logger.error(f"Gemini API Error in generate_structured: {e}")
            raise RuntimeError(f"Gemini API structured generation failure: {str(e)}")
 
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generates a 1D vector embedding for a block of text."""
        result = await self.generate_batch_embeddings([text])
        if result:
            return result[0]
        raise RuntimeError("No embedding returned from Gemini API.")
 
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates a batch of embeddings using text-embedding-004, partitioning requests in batches of 100."""
        if not texts:
            return []
            
        logger.debug(f"Generating embeddings for {len(texts)} chunks using {self.embedding_model_name}")
        
        batch_size = 100
        embeddings = []
        
        try:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                logger.debug(f"Embedding batch {i // batch_size + 1} ({len(batch_texts)} chunks)...")
                
                response = await self._execute_with_retry(
                    self.client.aio.models.embed_content,
                    model=self.embedding_model_name,
                    contents=batch_texts,
                )
                
                if response.embeddings:
                    for emb in response.embeddings:
                        embeddings.append(emb.values)
            return embeddings
            
        except APIError as e:
            logger.error(f"Gemini API Error in generate_batch_embeddings: {e}")
            raise RuntimeError(f"Gemini Embedding API failure: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during embeddings generation: {e}")
            raise
