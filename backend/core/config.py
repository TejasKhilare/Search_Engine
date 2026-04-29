import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    )

    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", 3072))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "document_chunks")

    def validate(self):
        """
        Called once at startup (from main.py lifespan).
        Raises clearly if a critical key is missing so the developer
        sees the problem immediately instead of a cryptic 500 later.
        """
        missing = []
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not self.OPENROUTER_API_KEY:
            missing.append("OPENROUTER_API_KEY")
        if not self.SECRET_KEY:
            missing.append("SECRET_KEY")
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


settings = Settings()