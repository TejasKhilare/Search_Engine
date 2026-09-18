import logging
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache

import pymupdf

from app.core.config import settings
from app.core.exceptions import UnsupportedMediaError

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"

# A page with less extractable text than this is treated as scanned and OCR'd
_MIN_NATIVE_TEXT_CHARS = 25
# Lines repeated on at least this share of pages (top/bottom) are headers/footers
_BOILERPLATE_PAGE_RATIO = 0.5
_BOILERPLATE_MIN_PAGES = 3
_EDGE_LINES = 2


@dataclass(frozen=True, slots=True)
class PdfInfo:
    page_count: int


@dataclass(frozen=True, slots=True)
class PageText:
    page_number: int  # 1-based
    text: str
    ocr: bool = False


# ── Validation ───────────────────────────────────────────────────────────────
def inspect_pdf(data: bytes) -> PdfInfo:
    """
    Validates that the bytes are a usable PDF. CPU-bound: call via asyncio.to_thread.
    Checks the real content, never the client-supplied filename or Content-Type.
    """
    if not data.startswith(PDF_MAGIC):
        raise UnsupportedMediaError("File is not a PDF")

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise UnsupportedMediaError("PDF is corrupted or unreadable") from e

    with doc:
        if doc.needs_pass:
            raise UnsupportedMediaError("Password-protected PDFs are not supported")
        if doc.page_count == 0:
            raise UnsupportedMediaError("PDF has no pages")
        if doc.page_count > settings.MAX_PDF_PAGES:
            raise UnsupportedMediaError(
                f"PDF has {doc.page_count} pages; the maximum is {settings.MAX_PDF_PAGES}"
            )
        return PdfInfo(page_count=doc.page_count)


# ── Extraction ───────────────────────────────────────────────────────────────
@cache
def ocr_available() -> bool:
    if not settings.OCR_ENABLED:
        return False
    try:
        import pytesseract

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        logger.warning("OCR disabled: Tesseract not available (%s)", e)
        return False


def _ocr_page(page: pymupdf.Page) -> str:
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=settings.OCR_DPI, colorspace=pymupdf.csGRAY)
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGE)


def _native_page_text(page: pymupdf.Page) -> str:
    # Blocks in reading order; each block is roughly one paragraph
    blocks = page.get_text("blocks", sort=True)
    paragraphs = [b[4] for b in blocks if b[6] == 0 and b[4].strip()]  # b[6]==0: text block
    return "\n\n".join(paragraphs)


def extract_pages(data: bytes) -> list[PageText]:
    """
    Extracts cleaned text per page, OCR-ing pages that have no usable text layer.
    CPU-bound: call via asyncio.to_thread. Pages with no text are omitted.
    """
    raw_pages: list[PageText] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for index, page in enumerate(doc):
            text = _native_page_text(page)
            used_ocr = False
            if len(text.strip()) < _MIN_NATIVE_TEXT_CHARS and ocr_available():
                ocr_text = _ocr_page(page)
                if len(ocr_text.strip()) > len(text.strip()):
                    text, used_ocr = ocr_text, True
            raw_pages.append(PageText(page_number=index + 1, text=text, ocr=used_ocr))

    boilerplate = _find_boilerplate_lines([p.text for p in raw_pages])
    pages = []
    for p in raw_pages:
        cleaned = clean_text(p.text, boilerplate)
        if cleaned:
            pages.append(PageText(page_number=p.page_number, text=cleaned, ocr=p.ocr))
    return pages


# ── Cleaning ─────────────────────────────────────────────────────────────────
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SPACES = re.compile(r"[ \t ]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")
_PAGE_NUMBER_LINE = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.IGNORECASE)
_DIGITS = re.compile(r"\d+")


def _line_signature(line: str) -> str:
    """Normalises a line so 'Page 3 of 10' and 'Page 4 of 10' compare equal."""
    return _DIGITS.sub("#", line.strip().lower())


def _find_boilerplate_lines(page_texts: list[str]) -> set[str]:
    if len(page_texts) < _BOILERPLATE_MIN_PAGES:
        return set()
    counts: Counter[str] = Counter()
    for text in page_texts:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        # Never let the top/bottom windows cover the whole page: at least one
        # middle line is always treated as body
        n = min(_EDGE_LINES, (len(lines) - 1) // 2)
        if n == 0:
            continue
        edge = set(lines[:n] + lines[-n:])
        counts.update({_line_signature(ln) for ln in edge})
    threshold = max(_BOILERPLATE_MIN_PAGES, int(len(page_texts) * _BOILERPLATE_PAGE_RATIO))
    return {sig for sig, n in counts.items() if n >= threshold and sig}


def clean_text(text: str, boilerplate: set[str] | None = None) -> str:
    """
    - rejoins words hyphenated across line breaks
    - drops repeated headers/footers and bare page-number lines
    - unwraps hard line breaks inside paragraphs, keeping paragraph breaks
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    kept = []
    for line in text.split("\n"):
        stripped = line.strip()
        if boilerplate and stripped and _line_signature(stripped) in boilerplate:
            continue
        if _PAGE_NUMBER_LINE.match(stripped):
            continue
        kept.append(_SPACES.sub(" ", stripped))
    text = "\n".join(kept)

    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraphs = [" ".join(p.split("\n")).strip() for p in paragraphs]
    return _MANY_NEWLINES.sub("\n\n", "\n\n".join(paragraphs)).strip()
