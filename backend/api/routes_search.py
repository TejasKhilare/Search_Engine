import logging
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.postgres import get_db
from db.models import SearchLog, Document, User
from core.deps import get_current_user

from services.embedding import embed_query
from vector_store.qdrant_client import search_vectors

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


# ---------------------------
# RESPONSE MODELS
# ---------------------------
class SearchResult(BaseModel):
    doc_id: str
    filename: str
    file_url: str
    page_no: int
    chunk_id: int
    content: str
    score: float
    start_pos: int
    end_pos: int


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


# ---------------------------
# SEARCH API
# ---------------------------
@router.get("/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., min_length=1),
    doc_id: Optional[str] = Query(None),
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Step 1: Get user's documents
    user_docs = db.query(Document).filter(
        Document.user_id == user.id
    ).all()

    allowed_doc_ids = {str(doc.doc_id) for doc in user_docs}

    # Optional: filter by specific doc_id
    if doc_id:
        if doc_id not in allowed_doc_ids:
            raise HTTPException(status_code=403, detail="Access denied")
        allowed_doc_ids = {doc_id}

    # Step 2: Embed query
    try:
        query_vector = embed_query(q)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail="Embedding failed")

    # Step 3: Search vectors
    try:
        hits = search_vectors(
            query_vector=query_vector,
            doc_id=None,
            top_k=top_k
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

    # Step 4: Filter hits by user access
    filtered_hits = [
        hit for hit in hits
        if hit.payload and str(hit.payload.get("doc_id")) in allowed_doc_ids
    ]

    # Step 5: Build doc_map (NO extra DB query)
    doc_map: Dict[str, str] = {
        str(doc.doc_id): str(doc.filename)
        for doc in user_docs
    }

    #Step 6: Build results
    results: List[SearchResult] = []

    for hit in filtered_hits:
        payload = hit.payload or {}

        hit_doc_id = str(payload.get("doc_id", ""))

        results.append(SearchResult(
            doc_id=hit_doc_id,
            filename=doc_map.get(hit_doc_id, "unknown"),
            file_url=f"/api/documents/{hit_doc_id}/view",
            page_no=int(payload.get("page_no", 0)),
            chunk_id=int(payload.get("chunk_id", 0)),
            content=str(payload.get("content", "")),
            score=round(float(hit.score), 4),
            start_pos=int(payload.get("start_pos", 0)),
            end_pos=int(payload.get("end_pos", 0)),
        ))

    #Step 7: Log search
    try:
        db.add(SearchLog(
            query=q,
            doc_id=doc_id,
            user_id=user.id,
            results_count=len(results)
        ))
        db.commit()
    except Exception:
        db.rollback()

    return SearchResponse(
        query=q,
        results=results,
        total=len(results)
    )