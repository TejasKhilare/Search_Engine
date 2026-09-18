"""Download and parse BEIR datasets (https://github.com/beir-cellar/beir)."""

import csv
import json
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).parent / "data"
BEIR_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{name}.zip"

# Approximate sizes, for choosing a dataset (docs / test queries)
KNOWN_DATASETS = {
    "scifact": "5K scientific abstracts, 300 test queries (quick runs)",
    "nfcorpus": "3.6K medical documents, 323 test queries",
    "fiqa": "57K financial Q&A posts, 648 test queries",
    "trec-covid": "171K COVID-19 papers, 50 deeply-judged queries (100K+ chunk scale)",
    "quora": "523K short questions, 10K test queries",
}


@dataclass(frozen=True, slots=True)
class BeirDoc:
    id: str
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class BeirDataset:
    name: str
    corpus: list[BeirDoc]
    queries: dict[str, str]  # query id -> text (all splits)
    qrels: dict[str, dict[str, int]]  # query id -> {doc id: relevance grade}, test split


def download(name: str) -> Path:
    """Downloads and unzips a BEIR dataset once; returns its directory."""
    target = DATA_DIR / name
    if (target / "corpus.jsonl").exists():
        return target

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archive = DATA_DIR / f"{name}.zip"
    print(f"Downloading BEIR/{name} …", flush=True)
    with httpx.stream("GET", BEIR_URL.format(name=name), follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with archive.open("wb") as f:
            for block in r.iter_bytes(1 << 20):
                f.write(block)
    with zipfile.ZipFile(archive) as z:
        z.extractall(DATA_DIR)
    archive.unlink()
    return target


def load(name: str, split: str = "test") -> BeirDataset:
    root = download(name)

    corpus = []
    with (root / "corpus.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            text = (row.get("text") or "").strip()
            if text:
                corpus.append(BeirDoc(id=str(row["_id"]), title=(row.get("title") or "").strip(), text=text))

    queries = {}
    with (root / "queries.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            queries[str(row["_id"])] = row["text"]

    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    qrels_file = root / "qrels" / f"{split}.tsv"
    if qrels_file.exists():
        with qrels_file.open(encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)  # header
            for query_id, doc_id, score in reader:
                qrels[query_id][doc_id] = int(score)

    return BeirDataset(name=name, corpus=corpus, queries=queries, qrels=dict(qrels))
