# Benchmarks

Reproducible measurements of the search stack. They use the **production code path**: the same
`chunks` table, HNSW index, chunker, embedding input and hybrid-search SQL. Results are written
to `results/<dataset>/` as Markdown and JSON, together with the machine and Postgres settings
they were measured on.

| Script | What it measures | OpenAI calls |
|---|---|---|
| `load_vectors` | Loads 99K **precomputed** `text-embedding-3-small` vectors (public DBpedia set) and times the HNSW build | **none** |
| `ann` | HNSW Recall@10 vs exact search across `ef_search`, p50/p95/p99 latency, throughput under concurrent load | none with `dbpedia-100k` (held-out query vectors) |
| `load_beir` | Loads a BEIR corpus through the real chunker and embedder | yes, **once** (resumable, prints the cost first) |
| `quality` | Recall@10 / nDCG@10 / MRR@10 against human relevance labels for vector, keyword and hybrid search | query embeddings, **once** (cached on disk) |

## Setup (once)

```bash
pip install -r requirements-bench.txt
# a separate database, so benchmark data never mixes with real documents
psql -U postgres -c "CREATE DATABASE docsearch_bench"
POSTGRES_DB=docsearch_bench alembic upgrade head
```

The scripts refuse to run unless `POSTGRES_DB` contains "bench".

## Run

```bash
export POSTGRES_DB=docsearch_bench          # PowerShell: $env:POSTGRES_DB="docsearch_bench"

# ANN at ~100K scale (free)
python -m benchmarks.load_vectors
python -m benchmarks.ann --dataset dbpedia-100k

# Retrieval quality (one small, cached embedding run)
python -m benchmarks.load_beir --dataset scifact
python -m benchmarks.quality --dataset scifact
```

Useful options:
- `ann --ef-search 10 40 100 200`: the values to sweep.
- `ann --concurrency 1 8 16`: the load-test levels.
- `ann --rebuild-index --m 32 --ef-construction 128`: explore index build parameters.
- `quality --max-queries 100`: run on fewer queries for a quicker check.

## Methodology notes

- **ANN recall** compares HNSW results with an exact sequential scan over the same data (the
  standard ann-benchmarks method). Query vectors are **held out**: they are never indexed.
- **Retrieval quality** uses BEIR human judgements (qrels) on the test split. Chunk results are
  collapsed to documents, keeping the best rank per document.
- **Latency** is database time for the query, measured client-side over a local connection after
  a warm-up. It **excludes** the OpenAI query-embedding call, which is typically 100–400 ms over
  the network.
- The absolute numbers depend on the hardware recorded in each report. Compare runs made on the
  same machine.
