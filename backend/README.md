# Backend: Document Search API

FastAPI service to upload PDFs, then search them (hybrid semantic + keyword + fuzzy) and ask
questions answered by an LLM with page-level citations.

**Stack:** FastAPI · async SQLAlchemy 2 + asyncpg · PostgreSQL 16 + pgvector 0.8 · Alembic ·
MinIO (S3-compatible) · OpenAI (`text-embedding-3-small`, `gpt-4o-mini`) · PyMuPDF + Tesseract OCR

---

## Architecture

```
            ┌──────────── FastAPI (app/) ────────────┐
 browser ──►│ api/v1/endpoints  →  services  →  repositories ──► PostgreSQL + pgvector
            │   auth · documents · search · ask        │          users, refresh_tokens,
            │                                          │          documents, chunks, search_logs
            │ services/storage ─────────────────────────────────► MinIO  (original PDFs)
            │ services/embedding · llm ─────────────────────────► OpenAI
            └──────────────────────────────────────────┘
```

**Ingestion** (background, after upload): `pending → processing → ready | failed`
1. Extract text per page with PyMuPDF; pages without a text layer are OCR'd (Tesseract).
2. Clean up: rejoin hyphenated words, drop repeated headers/footers and page numbers.
3. Chunk into ~400-token pieces on sentence boundaries with 60-token overlap (never across pages).
4. Embed in batches (title-prefixed), then store chunks and vectors in one transaction.

**Search:** three retrievers in one SQL query, all filtered by owner inside SQL, merged with
Reciprocal Rank Fusion:
- semantic: pgvector HNSW, cosine, iterative index scan
- keyword: Postgres full-text, OR-ed terms, ranked by coverage
- fuzzy: `pg_trgm`, for short queries

Weak semantic-only hits (similarity < `SEARCH_MIN_SCORE`) are dropped.

**Ask:** the top chunks are packed within a token budget into a grounded prompt. Answers carry
`[n]` citations. Document text is treated as data, never as instructions. If nothing relevant
is found, the LLM is never called.

## Project layout

```
app/
  main.py              app factory, lifespan (DB/pgvector/MinIO checks, job resume, maintenance)
  core/                config, security (JWT, Argon2, CSRF), cookies, logging, errors, middleware
  api/deps.py          dependency wiring (current user, services)
  api/v1/endpoints/    health, auth, documents, search/ask
  models/              SQLAlchemy models
  schemas/             Pydantic request/response models
  repositories/        database queries (always scoped to the owner)
  services/            business logic: auth, documents, storage, pdf, chunking, embedding,
                       ingestion (+ queue), search, rag, llm, maintenance
alembic/               migrations
tests/                 pytest suite (real Postgres, fakes for OpenAI/MinIO)
```

---

## Local development

### Prerequisites
- Python 3.12
- PostgreSQL 16 with the **pgvector** extension installed
- MinIO (Docker is the easiest way to run it)
- Tesseract OCR (optional; without it, scanned pages are skipped)
- An OpenAI API key

### 1. Database
Create the database, then enable the extensions **in that database** as a superuser:
```sql
CREATE DATABASE docsearch;
\c docsearch
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```
(The first migration also runs these, provided the migrating user is allowed to.)

### 2. MinIO
```bash
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin123 \
  -v minio_data:/data quay.io/minio/minio server /data --console-address ":9001"
```
Console: http://localhost:9001. The app creates its bucket on startup.

### 3. Python environment
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env            # then fill in the values
```
At minimum, set `POSTGRES_PASSWORD`, `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL` and `JWT_SECRET_KEY`.
Generate the JWT secret with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

### 4. Migrate and run
```bash
alembic upgrade head
uvicorn app.main:app --reload
```
- API docs: http://localhost:8000/docs (disabled in production). In Swagger, **Authorize** with
  your email as the username.
- Health: `GET /api/v1/health` (liveness) and `GET /api/v1/ready` (DB, pgvector and storage).

### Tests and linting
```bash
pytest                  # uses your dev database, but every test rolls back
ruff check . && ruff format --check .
alembic check           # models and migrations are in sync
```
OpenAI and MinIO are replaced by fakes in tests. `tests/test_storage_minio.py` talks to a real
MinIO when one is reachable (temporary bucket, removed afterwards) and skips otherwise.

### Database changes
```bash
# edit app/models/*, then:
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/, then:
alembic upgrade head
```

---

## Docker

From the repository root:
```bash
docker compose -f docker/docker-compose.yml --env-file backend/.env up -d --build
```
This starts the following services:
- `db`: pgvector/pgvector:pg16
- `minio`
- `migrate`: runs `alembic upgrade head` once
- `api`: port 8000, non-root, with Tesseract and the tokenizer baked in

Postgres and MinIO are published only on localhost ports 5433 and 9010/9011, so they don't clash
with local installs. Stop the stack with `docker compose -f docker/docker-compose.yml down`
(add `-v` to delete its data).

---

## Authentication (for frontend developers)

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/register` | Create an account |
| `POST /api/v1/auth/login` | Sets HttpOnly `access_token` and `refresh_token` cookies. Returns `{user, csrf_token, access_token_expires_at}` |
| `POST /api/v1/auth/refresh` | Rotates the refresh token and issues a new access token (same response as login) |
| `POST /api/v1/auth/logout` | Ends this session |
| `POST /api/v1/auth/logout-all` | Ends all sessions |
| `GET /api/v1/auth/me` | Current user |
| `POST /api/v1/auth/token` | OAuth2 password flow returning a Bearer token (Swagger and scripts) |

Rules for a browser client:
- **Send cookies** with every request (`withCredentials: true` or `credentials: "include"`).
- **CSRF:** send `X-CSRF-Token: <csrf_token>` on every POST, PUT, PATCH and DELETE. The token
  comes from the login and refresh responses, and from the readable `csrf_token` cookie.
- **Session refresh:** on a `401`, call `/auth/refresh` once and retry the request. If refresh
  also fails, send the user to the login page. After a page reload, call `/auth/refresh` to get
  a fresh `csrf_token`.
- Access tokens last 15 minutes. Refresh tokens last 7 days, are used only once, and reusing an
  old one revokes the whole session (theft detection).

## API overview

| Endpoint | Description |
|---|---|
| `POST /documents` | Upload a PDF (multipart `file`). Max 10 MB and 500 pages. Returns 201 with `pending` |
| `GET /documents?limit&offset&status` | Paginated list |
| `GET /documents/{id}` | Details and processing status (poll this) |
| `GET /documents/{id}/file` | The PDF, with Range support for PDF.js |
| `POST /documents/{id}/reprocess` | Retry a failed or finished document |
| `DELETE /documents/{id}` | Delete the document, its chunks and its file |
| `GET /search?q&document_id&limit` | Hybrid search, one result per page, with snippet and highlight ranges |
| `POST /ask` | `{question, document_ids?}` returns `{answer, citations, sources}` |
| `POST /ask/stream` | The same answer as Server-Sent Events: `sources`, then `delta`s, then `done` or `error` |

All errors share one format:
`{"error": {"code", "message", "request_id", "details?"}}`

---

## Configuration

Every setting lives in `.env`; see `.env.example` for the full, commented list. The most
important ones:

| Setting | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | In `production`, required secrets are enforced, `COOKIE_SECURE=true` is required, and docs are hidden |
| `CORS_ORIGINS` | – | Comma-separated frontend origins; credentials are allowed |
| `COOKIE_SAMESITE` | `lax` | Use `none` (with HTTPS) if the frontend is on a different site |
| `EMBEDDING_DIM` | `1536` | Must match the model **and** the DB column; changing it needs a migration and re-embedding |
| `SEARCH_MIN_SCORE` | `0.30` | Tune against your real documents |
| `RAG_CONTEXT_CHUNKS` / `RAG_MAX_CONTEXT_TOKENS` | `6` / `6000` | Context budget per answer |
| `INGESTION_CONCURRENCY` | `2` | Documents processed in parallel |
| `RATE_LIMIT_*` | – | Per-IP limits (auth 5/min, upload 20/min, search/ask 60/min) |

## Operations

- **Logs:** plain text in development, one JSON object per line in production. Every line and
  every response carries an `X-Request-ID`.
- **Maintenance** runs hourly under a Postgres advisory lock, so only one instance does it. It
  purges expired refresh tokens and search logs older than 90 days, and deletes stored files
  whose document no longer exists.
- **Crash recovery:** on startup, `pending` documents and ones stuck in `processing` are queued
  again.
- **Scaling:** run **one** Uvicorn worker per container for now. Ingestion jobs and rate-limit
  counters live in memory. To scale out:
  - move the rate limiter to Redis (`storage_uri` in `app/core/rate_limit.py`)
  - move ingestion to a worker queue (implement `IngestionQueue.enqueue`)
- **Behind a proxy:** set `FORWARDED_ALLOW_IPS` to the proxy's IP so rate limits see real
  client IPs. See `docker/nginx.conf`; SSE needs `proxy_buffering off`.
