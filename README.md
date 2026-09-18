# 🔍 AI-Powered Document Search Engine

Upload PDFs, then search them by meaning and keywords, or ask questions and get answers with
page-level citations. It is built on retrieval-augmented generation (RAG).

## Features

- **Accounts:** JWT authentication with HttpOnly cookies, refresh-token rotation with theft
  detection, and CSRF protection.
- **Documents:** PDF upload (up to 10 MB) with content validation and duplicate detection.
  Processing runs in the background, with OCR for scanned pages.
- **Hybrid search:** semantic (pgvector) + keyword (full-text) + fuzzy (trigram) search, merged
  with Reciprocal Rank Fusion, with highlighted snippets and page numbers.
- **Ask your documents:** grounded answers from `gpt-4o-mini` with `[n]` citations, streamed as
  they're written. It says so when the answer isn't in your documents.
- **PDF viewer:** jumps to the matching page with highlights. Large files stream in pieces via
  Range requests.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite), Tailwind CSS, Zustand, React Router, Axios, react-pdf |
| API | FastAPI, async SQLAlchemy 2, Pydantic v2, Alembic |
| Database | PostgreSQL 16 + pgvector (HNSW) + pg_trgm |
| File storage | MinIO (S3-compatible) |
| AI | OpenAI `text-embedding-3-small` (embeddings), `gpt-4o-mini` (answers) |
| Text extraction | PyMuPDF, Tesseract OCR |
| Infrastructure | Docker Compose, GitHub Actions (CI + EC2 deploy) |

## Getting started

- **Backend:** see [backend/README.md](backend/README.md) for local setup, Docker, API reference,
  configuration and operations.
- **Frontend:** see [frontend/README.md](frontend/README.md).

Quick start for the full backend stack with Docker (after creating `backend/.env` from
`backend/.env.example`):
```bash
docker compose -f docker/docker-compose.yml --env-file backend/.env up -d --build
```

## Repository layout

```
backend/     FastAPI service (app/, alembic/, tests/)
frontend/    React single-page app
docker/      docker-compose stack and nginx config
.github/     CI (lint, migrations, tests) and deploy workflows
```
