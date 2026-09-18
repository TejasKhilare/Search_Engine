import pytest

from app.services.chunking import chunk_text, count_tokens


def _sentences(n: int) -> str:
    return " ".join(f"Sentence number {i} talks about subject {i} in some detail." for i in range(n))


def test_short_text_is_one_chunk() -> None:
    text = "A short paragraph. With two sentences."
    [chunk] = chunk_text(text, max_tokens=100, overlap_tokens=10)
    assert chunk.content == text
    assert (chunk.char_start, chunk.char_end) == (0, len(text))
    assert chunk.token_count == count_tokens(text)


def test_empty_text_has_no_chunks() -> None:
    assert chunk_text("   \n\n  ", max_tokens=100, overlap_tokens=10) == []


def test_chunks_respect_token_limit_and_sentence_boundaries() -> None:
    text = _sentences(60)
    chunks = chunk_text(text, max_tokens=80, overlap_tokens=15)

    assert len(chunks) > 1
    for c in chunks:
        assert c.token_count <= 80
        assert c.content.startswith("Sentence number")  # starts on a sentence
        assert c.content.endswith(".")  # ends on a sentence


def test_offsets_point_into_source_text() -> None:
    text = "Intro paragraph here.\n\n" + _sentences(40)
    for c in chunk_text(text, max_tokens=60, overlap_tokens=10):
        assert text[c.char_start : c.char_end] == c.content


def test_consecutive_chunks_overlap_and_cover_everything() -> None:
    text = _sentences(50)
    chunks = chunk_text(text, max_tokens=70, overlap_tokens=20)

    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt.char_start < prev.char_end  # overlap
        assert nxt.char_start > prev.char_start  # progress
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)


def test_over_long_sentence_is_split_by_words() -> None:
    text = " ".join(f"word{i}" for i in range(500))  # no sentence punctuation at all
    chunks = chunk_text(text, max_tokens=50, overlap_tokens=5)
    assert len(chunks) > 5
    assert all(c.token_count <= 55 for c in chunks)  # small tolerance at word joins
    assert "word499" in chunks[-1].content


def test_paragraph_break_is_a_boundary() -> None:
    text = "no punctuation in this paragraph\n\nsecond paragraph also lowercase"
    chunks = chunk_text(text, max_tokens=8, overlap_tokens=0)
    assert [c.content for c in chunks] == [
        "no punctuation in this paragraph",
        "second paragraph also lowercase",
    ]


def test_overlap_must_be_smaller_than_chunk() -> None:
    with pytest.raises(ValueError):
        chunk_text("text", max_tokens=10, overlap_tokens=10)
