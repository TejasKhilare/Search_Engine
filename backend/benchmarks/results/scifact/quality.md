# Retrieval quality — BEIR/scifact

300 human-judged queries (test split) · 6,160 chunks · document-level ranking (best chunk per document)

| method | Recall@10 | nDCG@10 | MRR@10 | p50 (ms) | p95 (ms) |
|---|---:|---:|---:|---:|---:|
| vector | 0.862 | 0.716 | 0.678 | 53.1 | 125.4 |
| keyword | 0.494 | 0.331 | 0.285 | 245.1 | 2015.8 |
| hybrid | 0.805 | 0.610 | 0.557 | 216.0 | 2388.6 |

Hybrid vs vector-only: nDCG@10 -14.9%, Recall@10 -6.6%

- **vector**: HNSW cosine search (ef_search=100), `text-embedding-3-small` embeddings
- **keyword**: Postgres full-text search (English stemming, OR-ed terms, `ts_rank_cd`)
- **hybrid**: production query — vector + keyword + trigram, Reciprocal Rank Fusion (k=60), 40 candidates per retriever

Latency is database time for the query (query embeddings are precomputed).

## Environment

| | |
|---|---|
| date | `2026-09-18` |
| os | `Windows 10` |
| cpu | `Intel64 Family 6 Model 142 Stepping 9, GenuineIntel` |
| cpu_threads | `4` |
| python | `3.12.5` |
| embedding_model | `text-embedding-3-small (1536-dim)` |
| postgres.server_version | `16.4` |
| postgres.shared_buffers | `128MB` |
| postgres.work_mem | `4MB` |
| postgres.maintenance_work_mem | `64MB` |
| pgvector | `0.8.6` |
| hnsw_index | `CREATE INDEX ix_chunks_embedding_hnsw ON public.chunks USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')` |
