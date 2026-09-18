import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MatchType = Literal["semantic", "keyword", "fuzzy"]


class Snippet(BaseModel):
    text: str
    highlights: list[tuple[int, int]] = Field(
        description="[start, end) character ranges in `text` that matched the query"
    )


class SearchResult(BaseModel):
    document_id: uuid.UUID
    filename: str
    page_number: int
    chunk_index: int
    content: str
    char_start: int = Field(description="Offset of `content` within the page text")
    char_end: int
    snippet: Snippet
    score: float = Field(description="Semantic similarity, 0–1")
    match_types: list[MatchType]


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    took_ms: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[uuid.UUID] | None = Field(
        default=None, max_length=50, description="Restrict to these documents (default: all)"
    )

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question cannot be blank")
        return v.strip()


class Citation(BaseModel):
    index: int = Field(description="The [n] marker used in the answer")
    document_id: uuid.UUID
    filename: str
    page_number: int
    content: str
    char_start: int
    char_end: int
    score: float


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation] = Field(description="Sources actually cited in the answer")
    sources: list[Citation] = Field(description="All sources given to the model")
    took_ms: int
