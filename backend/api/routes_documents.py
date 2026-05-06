import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.postgres import get_db
from db.models import Document, Chunk, User
from core.deps import get_current_user
from core.config import settings
from vector_store.qdrant_client import delete_document_vectors
from utils.file_utils import delete_from_s3, generate_presigned_url

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents")
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = db.query(Document).filter(
        Document.user_id == user.id
    ).order_by(Document.created_at.desc()).all()

    return [
        {
            "doc_id": str(doc.doc_id),
            "filename": str(doc.filename),
            "status": str(doc.status),
            "total_chunks": getattr(doc, "total_chunks", 0),
            "created_at": doc.created_at,
        }
        for doc in docs
    ]


@router.get("/documents/{doc_id}/view")
def view_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == user.id,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    url = generate_presigned_url(
        s3_key=str(doc.path),
        bucket=settings.S3_BUCKET_NAME,
        region=settings.AWS_REGION,
        expires=3600,
    )
    return {"url": url}


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == user.id,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        db.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
        delete_document_vectors(doc_id)

        s3_key = str(doc.path)
        db.delete(doc)
        db.commit()

        # Delete from S3
        delete_from_s3(
            s3_key=s3_key,
            bucket=settings.S3_BUCKET_NAME,
            region=settings.AWS_REGION,
        )

        return {
            "message": "Document deleted successfully",
            "doc_id": doc_id,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")