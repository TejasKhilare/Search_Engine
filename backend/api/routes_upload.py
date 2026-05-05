import os
import logging
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from core.deps import get_current_user
from core.config import settings
from db.postgres import get_db
from db.models import Document, User
from utils.file_utils import validate_file, generate_doc_id, upload_to_s3, get_s3_key
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
    tmp_path = None
    doc_id = None
    try:
        contents = await file.read()
        size = len(contents)

        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        ext = validate_file(filename, size)
        doc_id = generate_doc_id()

        # Upload to S3
        s3_key = upload_to_s3(
            file_bytes=contents,
            doc_id=doc_id,
            ext=ext,
            bucket=settings.S3_BUCKET_NAME,
            region=settings.AWS_REGION,
        )

        # Write to a temp file so the background ingestion task can read it
        # (pdf_parser uses fitz.open which needs a real file path)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        tmp.write(contents)
        tmp.close()
        tmp_path = tmp.name

        document = Document(
            doc_id=doc_id,
            filename=filename,
            file_type=ext,
            path=s3_key,          # store S3 key in the path column
            status="pending",
            user_id=user.id,
        )
        db.add(document)
        db.commit()

        background_tasks.add_task(process_document_and_cleanup, doc_id, tmp_path)

        return {
            "doc_id": doc_id,
            "filename": filename,
            "status": "processing",
            "message": "File uploaded. Poll /api/document/{doc_id}/status for completion.",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        db.rollback()
        logger.error(f"Upload failed: {e}")
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail="Upload failed")


def process_document_and_cleanup(doc_id: str, tmp_path: str):
    """Wrapper that runs ingestion then removes the temp file."""
    try:
        process_document(doc_id, tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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