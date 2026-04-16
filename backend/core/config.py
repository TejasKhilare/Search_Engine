import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    # Qdrant collection name
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", 3072))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "document_chunks")


settings = Settings()