# ANN benchmark — dbpedia-100k (OpenAI text-embedding-3-small, precomputed)

**99,000 chunks** · 1536-dim · HNSW (cosine) · 500 queries (500 held-out vectors (not in the index)) · Recall@10 measured against exact search

- HNSW index size: **822 MB** over 105,160 chunks in the table (table incl. indexes: 1,871 MB)
- Index build time: **269.5s** (m=16, ef_construction=64)
- Exact search (sequential scan): p50 1227.1 ms, p95 1712.8 ms

## Recall vs latency (single client)

| ef_search | Recall@10 | p50 (ms) | p95 (ms) | p99 (ms) | QPS | speed-up vs exact (p95) |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.835 | 7.5 | 10.9 | 12.6 | 130 | 157.1× |
| 20 | 0.909 | 9.7 | 14.0 | 18.7 | 101 | 122.5× |
| 40 | 0.956 | 14.6 | 22.9 | 26.3 | 68 | 74.8× |
| 64 | 0.971 | 18.0 | 25.6 | 31.4 | 55 | 66.9× |
| 100 | 0.983 | 24.6 | 34.5 | 44.2 | 40 | 49.7× |
| 200 | 0.992 | 40.6 | 58.8 | 77.1 | 24 | 29.1× |
| 400 | 1.000 | 1215.5 | 1782.8 | 2512.8 | 1 | 1.0× |

Operating point (lowest ef_search with Recall@10 ≥ 0.95): **ef_search=40 → Recall@10 0.956, p95 22.9 ms**

## Under concurrent load (ef_search=40)

| concurrent clients | p50 (ms) | p95 (ms) | throughput (QPS) |
|---:|---:|---:|---:|
| 1 | 13.8 | 19.1 | 71 |
| 4 | 35.5 | 56.1 | 104 |
| 8 | 69.0 | 152.4 | 105 |
| 16 | 133.4 | 276.9 | 106 |

Latency is database retrieval time for the production vector query (owner filter, cosine, iterative index scan), measured client-side over a local connection. It excludes the OpenAI query-embedding call.

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
| postgres.maintenance_work_mem | `1900MB` |
| pgvector | `0.8.6` |
| hnsw_index | `CREATE INDEX ix_chunks_embedding_hnsw ON public.chunks USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')` |
