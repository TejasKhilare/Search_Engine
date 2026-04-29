import uuid
import logging
from typing import List, Dict, Optional, cast

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    ScoredPoint,
    Filter,
    FieldCondition,
    MatchValue,
    PointIdsList,
    ExtendedPointId,
)

from core.config import settings

logger = logging.getLogger(__name__)

# Shared Qdrant client
client = QdrantClient(
    host=settings.QDRANT_HOST,
    port=settings.QDRANT_PORT,
)

COLLECTION = settings.QDRANT_COLLECTION
DIM = settings.EMBEDDING_DIM


def ensure_collection():
    """
    Create Qdrant collection if it does not already exist.
    """
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(
                size=DIM,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {COLLECTION}")
    else:
        logger.info(f"Qdrant collection already exists: {COLLECTION}")


def upsert_vectors(points: List[Dict]):
    """
    Batch upsert chunk vectors into Qdrant.
    Point IDs are stored as UUID strings and converted to uuid.UUID objects
    for the Qdrant client so that rollback lookups work correctly.
    """
    if not points:
        return

    qdrant_points = [
        PointStruct(
            id=uuid.UUID(p["id"]),
            vector=p["vector"],
            payload=p["payload"],
        )
        for p in points
    ]

    batch_size = 100

    for i in range(0, len(qdrant_points), batch_size):
        batch = qdrant_points[i : i + batch_size]
        client.upsert(
            collection_name=COLLECTION,
            points=batch,
        )


def delete_vectors_by_ids(vector_ids: List[str]):
    """
    Delete specific vectors by their UUID string point IDs.
    Used for rollback if Postgres save fails after Qdrant upsert.
    """
    if not vector_ids:
        return

    try:
        typed_ids: List[ExtendedPointId] = [uuid.UUID(vid) for vid in vector_ids]

        client.delete(
            collection_name=COLLECTION,
            points_selector=PointIdsList(points=typed_ids),
        )

        logger.info(f"Rolled back {len(vector_ids)} vectors from Qdrant")

    except Exception as e:
        logger.error(f"Qdrant rollback failed: {e}")


def delete_document_vectors(doc_id: str):
    """
    Delete all vectors belonging to a document.
    Useful when deleting a document.
    """
    try:
        client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id),
                    )
                ]
            ),
        )

        logger.info(f"Deleted vectors for document: {doc_id}")

    except Exception as e:
        logger.error(f"Failed to delete vectors for doc {doc_id}: {e}")


def search_vectors(
    query_vector: List[float],
    doc_id: Optional[str] = None,
    top_k: int = 10,
) -> List[ScoredPoint]:
    """
    Semantic vector search in Qdrant.
    Optionally filter by document ID.
    """
    query_filter = None

    if doc_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="doc_id",
                    match=MatchValue(value=doc_id),
                )
            ]
        )

    response = client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    return cast(List[ScoredPoint], response.points)