import uuid
import logging

from db.postgres import SessionLocal
from db.models import Document, Chunk
from ingestion.pdf_parser import extract_text_by_page
from services.chunking import chunk_text
from services.embedding import embed_texts
from vector_store.qdrant_client import upsert_vectors, delete_vectors_by_ids
from typing import cast
logger = logging.getLogger(__name__)


def process_document(doc_id: str, file_path: str) -> dict:
    db = SessionLocal()
    document = None
    inserted_vector_ids = []

    try:
        document = db.query(Document).filter(Document.doc_id == doc_id).first()
        if not document:
            raise ValueError(f"Document {doc_id} not found in DB")

        setattr(document, "status", "processing")
        db.commit()

        pages = extract_text_by_page(file_path)
        logger.info(f"[{doc_id}] Extracted {len(pages)} pages")

        if not pages:
            setattr(document, "status", "failed")
            db.commit()
            return {"status": "failed", "reason": "no text extracted from document"}

        all_chunks = []
        for page in pages:
            for chunk in chunk_text(page["text"]):
                all_chunks.append((page["page_no"], chunk))

        if not all_chunks:
            setattr(document, "status", "failed")
            db.commit()
            return {"status": "failed", "reason": "no chunks produced"}

        logger.info(f"[{doc_id}] Created {len(all_chunks)} chunks")

        texts = [chunk["content"] for _, chunk in all_chunks]
        embeddings = embed_texts(texts)

        if len(embeddings) != len(all_chunks):
            raise ValueError(
                f"Embedding count mismatch: expected={len(all_chunks)}, got={len(embeddings)}"
            )

        logger.info(f"[{doc_id}] Embedded {len(embeddings)} chunks")

        points = []
        chunk_objects = []

        for (page_no, chunk), vector in zip(all_chunks, embeddings):
            vector_id = str(uuid.uuid4())
            inserted_vector_ids.append(vector_id)

            points.append({
                "id": vector_id,
                "vector": vector,
                "payload": {
                    "doc_id": doc_id,
                    "page_no": page_no,
                    "chunk_id": chunk["chunk_id"],
                    "content": chunk["content"],
                    "start_pos": chunk["start_pos"],
                    "end_pos": chunk["end_pos"],
                },
            })

            chunk_objects.append(Chunk(
                doc_id=doc_id,
                page_no=page_no,
                chunk_id=chunk["chunk_id"],
                content=chunk["content"],
                start_pos=chunk["start_pos"],
                end_pos=chunk["end_pos"],
                vector_id=vector_id,
            ))

        upsert_vectors(points)
        logger.info(f"[{doc_id}] Upserted {len(points)} vectors to Qdrant")

        try:
            db.bulk_save_objects(chunk_objects)
            setattr(document, "status", "completed")
            setattr(document, "total_chunks", len(chunk_objects))
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.error(f"[{doc_id}] DB save failed, rolling back vectors: {db_err}")
            delete_vectors_by_ids(inserted_vector_ids)
            raise db_err

        logger.info(f"[{doc_id}] Completed. {len(chunk_objects)} chunks saved.")
        return {"status": "completed", "chunks": len(chunk_objects)}

    except Exception as e:
        logger.error(f"[{doc_id}] Processing failed: {e}")
        try:
            if document:
                setattr(document, "status", "failed")
                db.commit()
        except Exception:
            db.rollback()
        raise

    finally:
        db.close()