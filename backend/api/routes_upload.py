import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from core.deps import get_current_user
from db.postgres import get_db
from db.models import Document, User
from utils.file_utils import validate_file, generate_doc_id, get_file_path
from services.ingestion_service import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_path = None
    try:
        contents = await file.read()
        size = len(contents)

        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        ext = validate_file(filename, size)

        doc_id = generate_doc_id()
        file_path = get_file_path(doc_id, ext)

        with open(file_path, "wb") as f:
            f.write(contents)

        document = Document(
            doc_id=doc_id,
            filename=filename,
            file_type=ext,
            path=file_path,
            status="pending",
            user_id=user.id,
        )
        db.add(document)
        db.commit()

        background_tasks.add_task(process_document, doc_id, file_path)

        return {
            "doc_id": doc_id,
            "filename": filename,
            "status": "processing",
            "message": "File uploaded. Poll /api/document/{doc_id}/status for completion.",
        }

    except ValueError as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        db.rollback()
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


#added get_current_user dependency + ownership check
@router.get("/document/{doc_id}/status")
def get_document_status(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(
        Document.doc_id == doc_id,
        Document.user_id == user.id, 
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "doc_id": document.doc_id,
        "filename": document.filename,
        "status": document.status,
        "total_chunks": document.total_chunks,
        "created_at": document.created_at,
    }