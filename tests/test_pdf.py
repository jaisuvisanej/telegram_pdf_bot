import pytest
from pathlib import Path
from src.pdf.extractor import PDFExtractor
from src.config.settings import settings

def test_pdf_validation_invalid_extension(tmp_path):
    """Verifies that PDFExtractor rejects files without .pdf extensions."""
    invalid_file = tmp_path / "study_notes.txt"
    invalid_file.write_text("Some text content")
    
    extractor = PDFExtractor()
    with pytest.raises(ValueError, match="Unsupported file type"):
        extractor.validate_file(invalid_file)

def test_pdf_validation_missing_file():
    """Verifies that PDFExtractor raises FileNotFoundError for missing files."""
    missing_file = Path("non_existent_file.pdf")
    extractor = PDFExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.validate_file(missing_file)

def test_pdf_validation_too_large(tmp_path, monkeypatch):
    """Verifies that PDFExtractor rejects files exceeding maximum size limits."""
    # Temporarily set limit to 1KB for easy testing
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    
    large_file = tmp_path / "large_file.pdf"
    # Write 2MB of dummy data
    with open(large_file, "wb") as f:
        f.write(b"\0" * (2 * 1024 * 1024))
        
    extractor = PDFExtractor()
    with pytest.raises(ValueError, match="exceeds the maximum allowed size"):
        extractor.validate_file(large_file)
