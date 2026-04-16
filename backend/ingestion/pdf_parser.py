import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from typing import cast, List, Dict


def extract_text_by_page(file_path: str) -> List[Dict]:
    """
    Extracts text from each page of a PDF.
    Falls back to OCR for image-only pages.
    Returns list of {"page_no": int, "text": str}
    """
    doc = fitz.open(file_path)
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = cast(str, page.get_text("text"))

        # OCR fallback for scanned pages
        if not text.strip():
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = pytesseract.image_to_string(img)

        if text.strip():
            pages.append({
                "page_no": page_num + 1,
                "text": text.strip()
            })

    doc.close()
    return pages