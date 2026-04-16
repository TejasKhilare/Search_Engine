from typing import List, Dict


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 50) -> List[Dict]:
    """
    Splits text into overlapping word-level chunks.
    Returns list of {"chunk_id", "content", "start_pos", "end_pos"}
    """
    words = text.split()
    chunks = []
    start = 0
    chunk_id = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]

        if not chunk_words:
            break

        chunks.append({
            "chunk_id": chunk_id,
            "content": " ".join(chunk_words),  # ← fixed: space between words
            "start_pos": start,
            "end_pos": end,
        })

        # ← fixed: these were outside the loop before
        start += (chunk_size - overlap)
        chunk_id += 1

    return chunks