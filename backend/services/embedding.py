from typing import List, cast
from google import genai
from google.genai.types import ContentListUnion

from core.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

EMBEDDING_MODEL = "gemini-embedding-001"


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Batch embed document chunks using Gemini.
    """
    if not texts:
        return []

    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=cast(ContentListUnion, texts),
    )

    embeddings = result.embeddings

    if not embeddings:
        raise ValueError("No embeddings returned")

    output: List[List[float]] = []

    for embedding in embeddings:
        values = embedding.values

        if values is None:
            raise ValueError("Missing embedding values in batch response")

        output.append(list(values))

    return output


def embed_query(query: str) -> List[float]:
    """
    Embed search query using Gemini.
    """
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
    )

    embeddings = result.embeddings

    if not embeddings:
        raise ValueError("No query embedding returned")

    values = embeddings[0].values

    if values is None:
        raise ValueError("Missing query embedding values")

    return list(values)