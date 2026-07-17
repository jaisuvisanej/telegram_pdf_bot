import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
import faiss
import numpy as np
from pydantic import BaseModel

from src.ai.base import BaseLLMService
from src.config.settings import settings

logger = logging.getLogger(__name__)

class DocumentChunk(BaseModel):
    pdf_id: int
    page_number: int
    text: str
    chunk_index: int

class RAGEngine:
    """Manages text chunking, FAISS index construction, persistence, and vector search."""

    def __init__(self, ai_service: BaseLLMService) -> None:
        self.ai_service = ai_service
        self.dimension = 768  # text-embedding-004 output dimension
        self.index_cache: Dict[int, Any] = {}
        self.chunks_cache: Dict[int, List[DocumentChunk]] = {}

    def chunk_pdf(
        self, 
        pdf_id: int, 
        pages: List[Any], 
        chunk_size: int = 1000, 
        chunk_overlap: int = 200
    ) -> List[DocumentChunk]:
        """
        Splits PDF page texts into overlapping chunks.
        Keeps page numbers accurate per chunk.
        """
        chunks: List[DocumentChunk] = []
        chunk_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            # If page text fits, add it as a single chunk
            if len(text) <= chunk_size:
                chunks.append(
                    DocumentChunk(
                        pdf_id=pdf_id,
                        page_number=page.page_number,
                        text=text,
                        chunk_index=chunk_idx
                    )
                )
                chunk_idx += 1
                continue

            # Split with overlap
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_text = text[start:end].strip()
                
                # Check for tiny orphan chunks at the end
                if len(chunk_text) > 50:
                    chunks.append(
                        DocumentChunk(
                            pdf_id=pdf_id,
                            page_number=page.page_number,
                            text=chunk_text,
                            chunk_index=chunk_idx
                        )
                    )
                    chunk_idx += 1
                
                start += (chunk_size - chunk_overlap)

        logger.info(f"Chunked PDF {pdf_id} into {len(chunks)} fragments.")
        return chunks

    async def create_index(self, pdf_id: int, chunks: List[DocumentChunk]) -> None:
        """
        Generates embeddings for chunks, constructs a FAISS index,
        saves both the index and chunk text to disk, and updates memory cache.
        """
        if not chunks:
            logger.warning(f"No chunks to index for PDF {pdf_id}")
            return

        texts = [chunk.text for chunk in chunks]
        
        # Get embeddings from LLM service
        logger.info(f"Requesting embeddings for {len(chunks)} chunks of PDF {pdf_id}...")
        embeddings = await self.ai_service.generate_batch_embeddings(texts)
        
        # Convert to numpy array
        embeddings_np = np.array(embeddings, dtype=np.float32)
        
        # Normalize vectors for Cosine Similarity (Inner Product)
        faiss.normalize_L2(embeddings_np)
        
        # Create FAISS Flat Inner Product index dynamically based on embeddings dimension
        dimension = embeddings_np.shape[1] if len(embeddings_np.shape) > 1 else self.dimension
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings_np)
        
        # Define storage files
        upload_dir = settings.upload_path
        index_path = upload_dir / f"pdf_{pdf_id}.faiss"
        chunks_path = upload_dir / f"pdf_{pdf_id}_chunks.json"
        
        # Save FAISS index and chunk metadata to disk using background threads
        import asyncio
        await asyncio.to_thread(faiss.write_index, index, str(index_path))
        
        chunks_data = [chunk.model_dump() for chunk in chunks]
        def write_chunks():
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        await asyncio.to_thread(write_chunks)
        
        # Cache in memory
        self.index_cache[pdf_id] = index
        self.chunks_cache[pdf_id] = chunks
            
        logger.info(f"Successfully saved FAISS index and chunk metadata for PDF {pdf_id} to disk.")

    async def retrieve_relevant_chunks(
        self, 
        pdf_id: int, 
        query: str, 
        top_k: int = 5
    ) -> List[DocumentChunk]:
        """
        Loads FAISS index from cache (or disk asynchronously), embeds the query,
        runs similarity search, and returns top-k matching DocumentChunks.
        """
        # Check memory cache first
        if pdf_id in self.index_cache and pdf_id in self.chunks_cache:
            index = self.index_cache[pdf_id]
            chunks = self.chunks_cache[pdf_id]
        else:
            upload_dir = settings.upload_path
            index_path = upload_dir / f"pdf_{pdf_id}.faiss"
            chunks_path = upload_dir / f"pdf_{pdf_id}_chunks.json"

            if not index_path.exists() or not chunks_path.exists():
                logger.warning(f"Index or chunk metadata missing for PDF {pdf_id} on disk.")
                return []

            # Load index and chunks metadata in a non-blocking way using thread pool
            import asyncio
            index = await asyncio.to_thread(faiss.read_index, str(index_path))
            
            def load_chunks():
                with open(chunks_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            chunks_data = await asyncio.to_thread(load_chunks)
            chunks = [DocumentChunk(**item) for item in chunks_data]
            
            # Cache it
            self.index_cache[pdf_id] = index
            self.chunks_cache[pdf_id] = chunks

        # Generate query embedding
        query_vector = await self.ai_service.generate_embeddings(query)
        query_vector_np = np.array([query_vector], dtype=np.float32)
        
        # Normalize query vector
        faiss.normalize_L2(query_vector_np)
        
        # Perform search
        # Clamp top_k to match maximum total chunks available
        search_k = min(top_k, len(chunks))
        if search_k <= 0:
            return []
            
        distances, indices = index.search(query_vector_np, search_k)
        
        retrieved_chunks = []
        for idx in indices[0]:
            if idx != -1 and idx < len(chunks):
                retrieved_chunks.append(chunks[idx])
                
        logger.info(f"Retrieved {len(retrieved_chunks)} relevant chunks for query: '{query[:30]}...'")
        return retrieved_chunks

    def delete_index(self, pdf_id: int) -> None:
        """Removes the index files from disk and clears memory cache for a deleted PDF."""
        self.index_cache.pop(pdf_id, None)
        self.chunks_cache.pop(pdf_id, None)
        
        upload_dir = settings.upload_path
        index_path = upload_dir / f"pdf_{pdf_id}.faiss"
        chunks_path = upload_dir / f"pdf_{pdf_id}_chunks.json"
        
        if index_path.exists():
            index_path.unlink()
        if chunks_path.exists():
            chunks_path.unlink()
        logger.info(f"Deleted vector index files and cleared cache for PDF {pdf_id}.")
