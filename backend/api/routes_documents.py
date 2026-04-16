import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.postgres import get_db
from db.models import Document, Chunk
from vector_store.qdrant_client import delete_document_vectors

router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()

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
def view_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = str(doc.path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing on server")

    return FileResponse(
        path=file_path,
        filename=str(doc.filename),
        media_type="application/pdf"
    )

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        db.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
        delete_document_vectors(doc_id)

        file_path = str(doc.path)
        db.delete(doc)
        db.commit()

        if os.path.exists(file_path):
            os.remove(file_path)

        return {
            "message": "Document deleted successfully",
            "doc_id": doc_id,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")