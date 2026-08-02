import sys
import logging
from pathlib import Path
from src.pdf.extractor import PDFExtractor

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 2:
        print("Usage: python scratch/test_ocr.py <path_to_pdf>")
        return
        
    pdf_path = Path(sys.argv[1])
    extractor = PDFExtractor()
    try:
        result = extractor.extract_text(pdf_path)
        print("--- EXTRACTED INFO ---")
        print(f"File Name: {result.file_name}")
        print(f"Page Count: {result.page_count}")
        print(f"Total Characters: {result.total_characters}")
        print(f"Metadata: {result.metadata}")
        print("\nFirst page preview:")
        if result.pages:
            print(result.pages[0].text[:500])
        else:
            print("No pages extracted.")
    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
