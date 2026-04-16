from fastapi import FastAPI
from contextlib import asynccontextmanager
from db.postgres import Base, engine
import db.models  # ensures all models are registered before create_all
from api.routes_upload import router as upload_router
from api.routes_search import router as search_router
from vector_store.qdrant_client import ensure_collection
import logging
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
                   "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(search_router, prefix="/api", tags=["search"])
from api.routes_documents import router as documents_router
app.include_router(documents_router)



@app.get("/")
def root():
    return {"message": "Document Search Engine running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}