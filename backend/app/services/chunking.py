import re
from dataclasses import dataclass
from functools import cache

import tiktoken

# Sentence boundary: end punctuation followed by whitespace and a likely sentence
# start, or a paragraph break.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])|\n\s*\n")
_WORD = re.compile(r"\S+")


@cache
def _encoding() -> tiktoken.Encoding:
    # The tokenizer used by OpenAI's text-embedding-3 models
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=()))


@dataclass(frozen=True, slots=True)
class TextChunk:
    content: str
    char_start: int  # offsets into the source text, for highlighting
    char_end: int
    token_count: int


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return [_trim(text, s, e) for s, e in spans if text[s:e].strip()]


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_long_span(text: str, start: int, end: int, max_tokens: int) -> list[tuple[int, int]]:
    """Splits a single over-long sentence at word boundaries."""
    words = [(m.start(), m.end(), count_tokens(" " + m.group())) for m in _WORD.finditer(text, start, end)]
    pieces: list[tuple[int, int]] = []
    first = 0
    tokens = 0
    for idx, (_, _, word_tokens) in enumerate(words):
        if idx > first and tokens + word_tokens > max_tokens:
            pieces.append((words[first][0], words[idx - 1][1]))
            first, tokens = idx, 0
        tokens += word_tokens
    if words:
        pieces.append((words[first][0], words[-1][1]))
    return pieces


def chunk_text(text: str, max_tokens: int, overlap_tokens: int) -> list[TextChunk]:
    """
    Packs whole sentences into chunks of at most ~max_tokens, repeating up to
    overlap_tokens of trailing sentences at the start of the next chunk so context
    that straddles a boundary is retrievable from either side.
    """
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be smaller than max_tokens")

    spans: list[tuple[int, int]] = []
    for start, end in _sentence_spans(text):
        if count_tokens(text[start:end]) > max_tokens:
            spans.extend(_split_long_span(text, start, end, max_tokens))
        else:
            spans.append((start, end))
    if not spans:
        return []

    sizes = [count_tokens(text[s:e]) for s, e in spans]
    chunks: list[TextChunk] = []
    i = 0
    while i < len(spans):
        j, total = i, 0
        while j < len(spans) and (j == i or total + sizes[j] <= max_tokens):
            total += sizes[j]
            j += 1

        char_start, char_end = spans[i][0], spans[j - 1][1]
        content = text[char_start:char_end]
        chunks.append(TextChunk(content, char_start, char_end, count_tokens(content)))
        if j >= len(spans):
            break

        # Step back over trailing sentences for overlap, always making progress
        k, overlap = j, 0
        while k - 1 > i and overlap + sizes[k - 1] <= overlap_tokens:
            overlap += sizes[k - 1]
            k -= 1
        i = k
    return chunks
