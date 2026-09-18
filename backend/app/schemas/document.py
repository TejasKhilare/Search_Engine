import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    size_bytes: int
    page_count: int | None
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    created_at: datetime
    processed_at: datetime | None
