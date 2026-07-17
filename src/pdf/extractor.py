import logging
from pathlib import Path
from typing import Dict, List, Optional
import fitz  # PyMuPDF
from pydantic import BaseModel, Field
from src.config.settings import settings

logger = logging.getLogger(__name__)

class PDFPageContent(BaseModel):
    page_number: int = Field(..., description="1-indexed page number of the PDF")
    text: str = Field(..., description="Extracted text content from this page")

class ExtractedPDF(BaseModel):
    file_name: str
    page_count: int
    total_characters: int
    metadata: Dict[str, str]
    pages: List[PDFPageContent]

    @property
    def full_text(self) -> str:
        """Helper to get the entire PDF text joined by page boundary markers."""
        return "\n\n--- PAGE BREAK ---\n\n".join(page.text for page in self.pages)

class PDFExtractor:
    """Service to validate and extract text from PDF files using PyMuPDF."""

    @staticmethod
    def validate_file(file_path: Path) -> None:
        """
        Validates that the file exists, has a .pdf extension,
        and is within the size limit.
        
        Raises:
            ValueError: If file is invalid or too large.
            FileNotFoundError: If file does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Unsupported file type '{file_path.suffix}'. Only PDF files are allowed.")
        
        file_size = file_path.stat().st_size
        max_size = settings.max_file_size_bytes
        if file_size > max_size:
            raise ValueError(
                f"File size ({file_size / (1024*1024):.2f} MB) exceeds "
                f"the maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB."
            )

    def extract_text(self, file_path: Path) -> ExtractedPDF:
        """
        Validates and extracts all text content from the PDF page by page.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            ExtractedPDF object containing structured pages and metadata.
            
        Raises:
            ValueError: If PDF cannot be read or is corrupted.
        """
        self.validate_file(file_path)
        
        logger.info(f"Extracting text from: {file_path}")
        
        try:
            # Open PDF document
            doc = fitz.open(file_path)
        except Exception as e:
            logger.error(f"Failed to open PDF file {file_path}: {e}")
            raise ValueError(f"Failed to open or parse PDF. It might be corrupted. Error: {str(e)}")
            
        try:
            page_count = len(doc)
            extracted_pages: List[PDFPageContent] = []
            total_chars = 0
            
            # Read document metadata
            doc_metadata = {
                "title": doc.metadata.get("title") or "",
                "author": doc.metadata.get("author") or "",
                "subject": doc.metadata.get("subject") or "",
                "keywords": doc.metadata.get("keywords") or "",
                "creator": doc.metadata.get("creator") or "",
                "producer": doc.metadata.get("producer") or ""
            }
            
            for page_idx in range(page_count):
                page = doc.load_page(page_idx)
                
                # Get text block by block to preserve order
                raw_text = page.get_text("text")
                cleaned_text = self._clean_text(raw_text)
                
                # Track statistics
                total_chars += len(cleaned_text)
                
                extracted_pages.append(
                    PDFPageContent(
                        page_number=page_idx + 1,
                        text=cleaned_text
                    )
                )
                
            logger.info(f"Successfully extracted {page_count} pages, {total_chars} characters from {file_path.name}")
            
            return ExtractedPDF(
                file_name=file_path.name,
                page_count=page_count,
                total_characters=total_chars,
                metadata=doc_metadata,
                pages=extracted_pages
            )
            
        finally:
            doc.close()

    def _clean_text(self, text: str) -> str:
        """Basic text cleaning to clean up double spaces and odd Unicode spacing."""
        if not text:
            return ""
        
        # Replace Windows line endings and isolate carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Clean duplicate spaces and formatting tabs/ligatures
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            # Replace multiple spaces with a single space
            words = line.split()
            cleaned_line = " ".join(words)
            if cleaned_line:
                lines.append(cleaned_line)
                
        return "\n".join(lines)
