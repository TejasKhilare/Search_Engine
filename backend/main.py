from fastapi import FastAPI
from contextlib import asynccontextmanager
from db.postgres import Base, engine
import db.models  # ensures all models are registered before create_all
from api.routes_upload import router as upload_router
from api.routes_search import router as search_router
from api.routes_rag import router as rag_router
from api.routes_auth import router as auth_router
from api.routes_documents import router as documents_router
from vector_store.qdrant_client import ensure_collection
from core.config import settings
import logging
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate all required env vars at startup — fail fast with clear message
    settings.validate()

    print("Creating Postgres tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables ready")

    print("Ensuring Qdrant collection...")
    ensure_collection()
    print("Qdrant ready")

    yield

    print("Shutting down...")


app = FastAPI(
    title="Document Semantic Search Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all localhost/127.0.0.1 origins across any port (Vite can be 5173,
# 5174, 3000, etc.). In production, replace with your real domain.
# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

# Add the S3 frontend URL from env if set (e.g. http://my-bucket.s3-website.ap-south-1.amazonaws.com)
if settings.FRONTEND_URL:
    allowed_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(upload_router)
app.include_router(search_router)
app.include_router(rag_router)
app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/")
def root():
    return {"message": "Document Search Engine running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}