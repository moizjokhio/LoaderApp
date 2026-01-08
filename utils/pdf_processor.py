"""
PDF Processing with OCR support
"""
import fitz  # PyMuPDF
from PIL import ImageFile
from config import OCR_DPI, OCR_MIN_TEXT_LENGTH, OCR_LANGUAGE

# Allow loading of truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# OCR imports (optional)
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def extract_text_with_ocr(page, page_num: int, pdf_bytes: bytes) -> tuple:
    """
    Extract text from PDF page with OCR fallback for scanned documents.
    
    Args:
        page: PyMuPDF page object
        page_num: Page number (0-indexed)
        pdf_bytes: PDF file bytes
    
    Returns:
        tuple: (extracted_text, used_ocr: bool)
    """
    # Try normal text extraction first
    text = page.get_text()
    
    # If text is too short (likely scanned image), use OCR
    if len(text.strip()) < OCR_MIN_TEXT_LENGTH and OCR_AVAILABLE:
        try:
            # Convert specific page to image
            images = convert_from_bytes(
                pdf_bytes, 
                first_page=page_num+1, 
                last_page=page_num+1, 
                dpi=OCR_DPI
            )
            if images:
                # Perform OCR
                ocr_text = pytesseract.image_to_string(images[0], lang=OCR_LANGUAGE)
                if len(ocr_text.strip()) > len(text.strip()):
                    return ocr_text, True
        except Exception:
            # OCR failed, use original text
            pass
    
    return text, False


def extract_all_pages(pdf_file) -> tuple:
    """
    Extract text from all PDF pages with OCR support.
    
    Args:
        pdf_file: Uploaded PDF file (Streamlit UploadedFile)
    
    Returns:
        tuple: (pages_data: list[dict], ocr_used_pages: list[int])
    """
    pdf_bytes = pdf_file.getvalue()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    pages_data = []
    ocr_used_pages = []
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        page_text, used_ocr = extract_text_with_ocr(page, page_num, pdf_bytes)
        
        pages_data.append({
            'page_num': page_num + 1,
            'text': page_text
        })
        
        if used_ocr:
            ocr_used_pages.append(page_num + 1)
    
    pdf_document.close()
    
    return pages_data, ocr_used_pages
