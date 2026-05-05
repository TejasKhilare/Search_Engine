import os
import uuid
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ["pdf"]
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


def get_s3_key(doc_id: str, ext: str) -> str:
    """Returns the S3 object key for a document."""
    return f"documents/{doc_id}.{ext}"


def upload_to_s3(file_bytes: bytes, doc_id: str, ext: str, bucket: str, region: str) -> str:
    """
    Upload file bytes to S3. Returns the S3 key on success.
    """
    s3_key = get_s3_key(doc_id, ext)
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=file_bytes,
            ContentType="application/pdf",
        )
        logger.info(f"Uploaded {s3_key} to s3://{bucket}")
        return s3_key
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise


def delete_from_s3(s3_key: str, bucket: str, region: str) -> None:
    """Delete a file from S3."""
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.delete_object(Bucket=bucket, Key=s3_key)
        logger.info(f"Deleted {s3_key} from s3://{bucket}")
    except ClientError as e:
        logger.error(f"S3 delete failed: {e}")


def generate_presigned_url(s3_key: str, bucket: str, region: str, expires: int = 3600) -> str:
    """Generate a presigned GET URL for a document."""
    s3 = boto3.client("s3", region_name=region)
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expires,
        )
        return url
    except ClientError as e:
        logger.error(f"Presigned URL generation failed: {e}")
        raise


# Legacy local path helper — kept only for local dev fallback
def get_file_path(doc_id: str, ext: str) -> str:
    storage_dir = "storage"
    os.makedirs(storage_dir, exist_ok=True)
    return os.path.join(storage_dir, f"{doc_id}.{ext}")