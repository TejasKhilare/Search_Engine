from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from core.deps import get_current_user
from db.postgres import get_db
from db.models import Document, User
from services.embedding import embed_query
from vector_store.qdrant_client import search_vectors
from services.rag_service import generate_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["rag"])

MAX_QUERY_CHARS = 1000


class RagRequest(BaseModel):
    query: str
    doc_id: str | None = None
    # Raised from 5 → 10 so more chunks reach the ranker.
    # With top_k=5 and only 2-3 chunks used by the LLM, best chunks
    # spread across different pages could be missed entirely.
    top_k: int = 10


@router.post("/ai-search")
def ai_search(
    request: RagRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = request.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if len(query) > MAX_QUERY_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long ({len(query)} chars). Maximum allowed: {MAX_QUERY_CHARS}.",
        )

    # ── Resolve allowed documents ──────────────────────────────────────────
    user_docs = db.query(Document).filter(Document.user_id == user.id).all()
    allowed_doc_ids = {str(doc.doc_id) for doc in user_docs}

    # Build doc_id → filename map so sources include filename without
    # a separate /api/documents lookup on the frontend
    doc_name_map: dict[str, str] = {
        str(doc.doc_id): str(doc.filename) for doc in user_docs
    }

    if request.doc_id:
        if request.doc_id not in allowed_doc_ids:
            raise HTTPException(status_code=403, detail="Access denied")
        allowed_doc_ids = {request.doc_id}

    # ── Embed query ────────────────────────────────────────────────────────
    try:
        query_vector = embed_query(query)
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise HTTPException(status_code=500, detail="Embedding failed") from e

    # ── Vector search ──────────────────────────────────────────────────────
    try:
        hits = search_vectors(
            query_vector=query_vector,
            doc_id=None,
            top_k=request.top_k,
        )
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        raise HTTPException(status_code=500, detail="Vector search failed") from e

    # ── Filter to user's docs ──────────────────────────────────────────────
    filtered_hits = [
        hit for hit in hits
        if hit.payload and str(hit.payload.get("doc_id")) in allowed_doc_ids
    ]

    if not filtered_hits:
        return {
            "query": query,
            "answer": "No relevant information found.",
            "sources": [],
        }

    # ── Build contexts + sources ───────────────────────────────────────────
    contexts: list[str] = []
    sources: list[dict] = []

    for hit in filtered_hits:
        payload = hit.payload or {}
        content = str(payload.get("content", "")).strip()
        hit_doc_id = str(payload.get("doc_id", ""))

        if content:
            contexts.append(content)
            sources.append({
                "doc_id": hit_doc_id,
                "filename": doc_name_map.get(hit_doc_id, "unknown"),
                "page_no": int(payload.get("page_no", 0)),
                "score": round(float(hit.score), 4),
                "content": content,
            })

    # ── Generate answer ────────────────────────────────────────────────────
    try:
        answer = generate_answer(query, contexts)
    except RuntimeError as e:
        logger.error("LLM generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in generate_answer: %s", e)
        raise HTTPException(status_code=500, detail="Answer generation failed")

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
    }