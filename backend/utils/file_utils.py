import os
import uuid

ALLOWED_TYPES = ["pdf"]  # focusing on PDF for now; add png/jpg when OCR is needed
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_file(filename: str, size: int) -> str:
    if not filename or "." not in filename:
        raise ValueError("Invalid filename")

    ext = filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: .{ext}. Allowed: {ALLOWED_TYPES}")

    if size > MAX_FILE_SIZE:
        raise ValueError(f"File size {size} exceeds 10MB limit")

    return ext


def generate_doc_id() -> str:
    return str(uuid.uuid4())


def get_file_path(doc_id: str, ext: str) -> str:
    storage_dir = "storage"
    os.makedirs(storage_dir, exist_ok=True)
    return os.path.join(storage_dir, f"{doc_id}.{ext}")