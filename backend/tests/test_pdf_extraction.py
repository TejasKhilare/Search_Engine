import pymupdf
import pytest

from app.services.pdf import clean_text, extract_pages, ocr_available


def test_clean_text_rejoins_hyphenated_words() -> None:
    assert clean_text("the docu-\nment is long") == "the document is long"


def test_clean_text_unwraps_lines_but_keeps_paragraphs() -> None:
    raw = "First line of para one\ncontinues here.\n\nSecond   paragraph\twith  spaces."
    assert clean_text(raw) == "First line of para one continues here.\n\nSecond paragraph with spaces."


@pytest.mark.parametrize("line", ["12", "Page 3", "page 3 of 10", " 4 / 20 "])
def test_clean_text_drops_page_number_lines(line: str) -> None:
    assert clean_text(f"Body text.\n{line}") == "Body text."


def test_extract_pages_removes_repeated_headers_and_footers() -> None:
    doc = pymupdf.open()
    for n in range(1, 5):
        page = doc.new_page()
        page.insert_text((72, 40), "ACME Corp Confidential")
        page.insert_text((72, 100), f"Unique body content number {n} about topic {n * 7}.")
        page.insert_text((72, 800), f"Page {n} of 4")
    data = doc.tobytes()

    pages = extract_pages(data)
    assert [p.page_number for p in pages] == [1, 2, 3, 4]
    for p in pages:
        assert "ACME Corp Confidential" not in p.text
        assert "of 4" not in p.text
        assert f"Unique body content number {p.page_number}" in p.text


def test_extract_pages_skips_blank_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Only this page has text in it.")
    doc.new_page()  # blank
    monkeypatch.setattr("app.services.pdf.ocr_available", lambda: False)

    pages = extract_pages(doc.tobytes())
    assert [p.page_number for p in pages] == [1]


@pytest.mark.skipif(not ocr_available(), reason="Tesseract not installed")
def test_extract_pages_ocrs_scanned_pages() -> None:
    # Render text to an image and embed ONLY the image: no text layer, like a scan
    source = pymupdf.open()
    source.new_page().insert_text((72, 100), "Invoice total amount due 4520 dollars", fontsize=20)
    image = source[0].get_pixmap(dpi=200).tobytes("png")

    scanned = pymupdf.open()
    page = scanned.new_page()
    page.insert_image(page.rect, stream=image)
    assert page.get_text().strip() == ""

    [result] = extract_pages(scanned.tobytes())
    assert result.ocr is True
    assert "Invoice total amount due" in result.text
    assert "4520" in result.text
