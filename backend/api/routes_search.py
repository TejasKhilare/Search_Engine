import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.postgres import get_db
from db.models import SearchLog, Document
from services.embedding import embed_query
from vector_store.qdrant_client import search_vectors

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.get("/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    doc_id: Optional[str] = Query(None, description="Filter by document ID"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results"),
    db: Session = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        query_vector = embed_query(q)
    except Exception as e:
        logger.error(f"Embedding failed for query '{q}': {e}")
        raise HTTPException(status_code=500, detail="Failed to embed query")

    try:
        hits = search_vectors(query_vector=query_vector, doc_id=doc_id, top_k=top_k)
    except Exception as e:
        logger.error(f"Qdrant search failed: {e}")
        raise HTTPException(status_code=500, detail="Vector search failed")

    hit_doc_ids = list({hit.payload.get("doc_id") for hit in hits if hit.payload})
    docs = db.query(Document).filter(Document.doc_id.in_(hit_doc_ids)).all() if hit_doc_ids else []
    doc_map = {doc.doc_id: doc.filename for doc in docs}

    results = []
    for hit in hits:
        payload = hit.payload or {}
        hit_doc_ids = list({
            str(hit.payload.get("doc_id"))
            for hit in hits
            if hit.payload and hit.payload.get("doc_id")
            })
        docs = (
            db.query(Document)
            .filter(Document.doc_id.in_(hit_doc_ids))
            .all()
            if hit_doc_ids else []
            )
        doc_map = {
            str(doc.doc_id): str(doc.filename)
            for doc in docs
            }
        results = []

        for hit in hits:
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
    try:
        db.add(SearchLog(query=q, doc_id=doc_id, results_count=len(results)))
        db.commit()
    except Exception:
        db.rollback()

    return SearchResponse(query=q, results=results, total=len(results))