from abc import ABC, abstractmethod
from typing import List, Optional, Any, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class BaseLLMService(ABC):
    """Abstract interface defining required LLM operations for RAG and study content generation."""

    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generates a text response from the model.
        
        Args:
            prompt: User message or context block.
            system_instruction: System priming/instructions.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None
    ) -> T:
        """
        Generates structured outputs validated against a Pydantic schema.
        
        Args:
            prompt: User instruction or context block.
            response_schema: The target Pydantic class to enforce output validation.
            system_instruction: System priming instructions.
        """
        pass

    @abstractmethod
    async def generate_embeddings(self, text: str) -> List[float]:
        """Generates a 1D vector embedding for a single block of text."""
        pass

    @abstractmethod
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates 1D vector embeddings for a list of text blocks."""
        pass
