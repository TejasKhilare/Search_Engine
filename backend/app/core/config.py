from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    APP_NAME: str = "Document Search Engine"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = ""

    # ── Postgres ─────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("")
    POSTGRES_DB: str = "docsearch"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── OpenAI ───────────────────────────────────────────────
    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_CHAT_MODEL: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = Field(default=1536, gt=0, le=2000)  # HNSW index limit
    OPENAI_TIMEOUT_SECONDS: float = 60
    OPENAI_MAX_RETRIES: int = 3

    # ── JWT / Auth ───────────────────────────────────────────
    JWT_SECRET_KEY: SecretStr = SecretStr("")
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "docsearch-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # A just-rotated refresh token presented again within this window (e.g. two tabs
    # refreshing at once) is rejected without being treated as token theft.
    REFRESH_REUSE_GRACE_SECONDS: int = 30

    # ── Cookies ──────────────────────────────────────────────
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None

    # ── MinIO ────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: SecretStr = SecretStr("")
    MINIO_BUCKET: str = "documents"
    MINIO_SECURE: bool = False

    # ── Uploads / ingestion ──────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_PDF_PAGES: int = 500
    TESSERACT_CMD: str | None = None
    OCR_ENABLED: bool = True
    OCR_LANGUAGE: str = "eng"
    OCR_DPI: int = 300
    CHUNK_SIZE_TOKENS: int = 400
    CHUNK_OVERLAP_TOKENS: int = 60
    EMBEDDING_BATCH_SIZE: int = 100
    INGESTION_CONCURRENCY: int = 2  # documents processed in parallel per process
    # A document stuck in "processing" longer than this (e.g. server crashed mid-job)
    # is re-queued on startup
    INGESTION_STALE_AFTER_MINUTES: int = 15

    # ── Search / RAG ─────────────────────────────────────────
    SEARCH_TOP_K: int = 10
    # Semantic-only hits below this cosine similarity are dropped (keyword/fuzzy hits are kept)
    SEARCH_MIN_SCORE: float = 0.30
    # A keyword hit counts on its own only if it contains this share of the query's terms
    SEARCH_KEYWORD_MIN_COVERAGE: float = 0.5
    SEARCH_CANDIDATES: int = 40  # per retriever, before fusion
    SEARCH_RRF_K: int = 60  # Reciprocal Rank Fusion constant
    HNSW_EF_SEARCH: int = 100  # higher = better recall, slower
    RAG_CONTEXT_CHUNKS: int = 6
    RAG_MAX_CONTEXT_TOKENS: int = 6000
    RAG_MAX_OUTPUT_TOKENS: int = 800
    RAG_TEMPERATURE: float = 0.1

    # ── Rate limiting ────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_UPLOAD: str = "20/minute"

    # ── Maintenance ──────────────────────────────────────────
    MAINTENANCE_ENABLED: bool = True
    MAINTENANCE_INTERVAL_MINUTES: int = 60
    SEARCH_LOG_RETENTION_DAYS: int = 90
    # Storage objects without a DB row are deleted only once older than this, so an
    # upload that is between "file stored" and "row committed" is never touched
    ORPHAN_OBJECT_MIN_AGE_MINUTES: int = 60

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        # URL.create escapes special characters in the password
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if self.CHUNK_OVERLAP_TOKENS >= self.CHUNK_SIZE_TOKENS:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        if not self.COOKIE_DOMAIN:
            self.COOKIE_DOMAIN = None
        if len(self.JWT_SECRET_KEY.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")

        if self.is_production:
            missing = [
                name
                for name, value in {
                    "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD.get_secret_value(),
                    "OPENAI_API_KEY": self.OPENAI_API_KEY.get_secret_value(),
                    "OPENAI_CHAT_MODEL": self.OPENAI_CHAT_MODEL,
                    "JWT_SECRET_KEY": self.JWT_SECRET_KEY.get_secret_value(),
                    "MINIO_SECRET_KEY": self.MINIO_SECRET_KEY.get_secret_value(),
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"Missing required settings in production: {', '.join(missing)}")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
