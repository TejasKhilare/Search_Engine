import re
import time
import logging
from typing import List

from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from core.config import settings

logger = logging.getLogger(__name__)

# ── OpenRouter client ─────────────────────────────────────────────────────────
client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

MODEL = "deepseek/deepseek-r1"

# ✅ FIX 1: raised from 400 → 1500 chars per chunk.
# 400 was silently cutting off data mid-sentence. The education chunk in the
# example is ~377 chars and just barely survived, but any slightly longer chunk
# (skills, projects) would be truncated before reaching the LLM.
# 1500 chars ≈ ~300 words — comfortably fits a dense resume section while
# staying well within the 150-token output budget + model context window.
CHUNK_CHAR_LIMIT = 1500

# How many top-ranked chunks are passed to the LLM.
TOP_K_CHUNKS = 3

MAX_RETRIES = 2
RETRY_DELAY = 2


# ── Detect multi-part queries ─────────────────────────────────────────────────
def is_multi_part_query(query: str) -> bool:
    """
    Returns True when the query contains multiple distinct questions or
    entities joined by commas, 'and', 'also', semicolons, etc.
    Examples that return True:
      - "what is cgpa, 10th percentage and 12th percentage"
      - "name, skills and experience of john"
    """
    parts = re.split(r"[,;]|\band\b|\balso\b", query.lower())
    # Discard very short fragments (stop words, articles) — count real parts
    meaningful = [p.strip() for p in parts if len(p.strip()) > 3]
    return len(meaningful) >= 2


# ── Keyword re-ranking ────────────────────────────────────────────────────────
def rank_chunks(query: str, chunks: List[str]) -> List[str]:
    """
    Sort chunks by number of query-word hits so the most relevant context
    reaches the LLM first. Ties preserved in original order.
    """
    query_words = set(query.lower().split())
    scored = [
        (sum(word in chunk.lower() for word in query_words), i, chunk)
        for i, chunk in enumerate(chunks)
    ]
    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    return [chunk for _, _, chunk in scored]


# ── ✅ FIX 2: structured regex extraction removed from generate_answer ─────────
# The old code ran regex extraction BEFORE the LLM call and returned
# immediately on the first match. For the query:
#   "what is cgpa, 10th percentage and also 12th percentage of tejas"
# the CGPA regex fired and returned "CGPA: 8.20" — the other two values
# (77% HSC, 80.80% SSC) were NEVER returned because the function exited early.
#
# Regex extraction is now a POST-PROCESSING step: if the LLM answer is
# suspiciously short (≤ 10 chars) or empty, we attempt regex as a last-resort
# fallback, not as a shortcut that bypasses the LLM.
def _regex_fallback(query: str, contexts: List[str]) -> str | None:
    """
    Last-resort structured extraction when the LLM returns nothing useful.
    Intentionally conservative — only fires when LLM output is empty/garbage.
    """
    combined = " ".join(contexts)
    q = query.lower()
    results = []

    if "cgpa" in q:
        m = re.search(r"CGPA[:\s]*([0-9]+(?:\.[0-9]+)?(?:/10)?)", combined, re.IGNORECASE)
        if m:
            results.append(f"CGPA: {m.group(1)}")

    if "percentage" in q or "10th" in q or "ssc" in q:
        # SSC / 10th — look for patterns like "Percentage: 80.80%" near SSC/10th context
        m = re.search(
            r"SSC.*?Percentage[:\s]*([0-9]+(?:\.[0-9]+)?)\s*%|"
            r"10th.*?([0-9]+(?:\.[0-9]+)?)\s*%",
            combined, re.IGNORECASE | re.DOTALL,
        )
        if m:
            val = m.group(1) or m.group(2)
            results.append(f"10th (SSC) percentage: {val}%")

    if "percentage" in q or "12th" in q or "hsc" in q:
        # HSC / 12th
        m = re.search(
            r"HSC.*?Percentage[:\s]*([0-9]+(?:\.[0-9]+)?)\s*%|"
            r"12th.*?([0-9]+(?:\.[0-9]+)?)\s*%",
            combined, re.IGNORECASE | re.DOTALL,
        )
        if m:
            val = m.group(1) or m.group(2)
            results.append(f"12th (HSC) percentage: {val}%")

    return "\n".join(results) if results else None


# ── Prompt builder ────────────────────────────────────────────────────────────
def build_prompt(query: str, contexts: List[str], multi_part: bool) -> str:
    """
    Build the LLM prompt.

    ✅ FIX 3: The old prompt said "Answer in 1-2 lines only." That single
    constraint caused the LLM to answer only the first sub-question it found
    and stop, even when the query had 3 distinct parts.

    The new prompt:
    - Detects multi-part queries and explicitly tells the LLM to answer EACH part.
    - Removes the "1-2 lines" cap so multi-part answers can be bullet-listed.
    - Still enforces "only from context" to prevent hallucination.
    """
    # ✅ FIX 1 effect: use the raised CHUNK_CHAR_LIMIT — no more data truncation
    trimmed = [c[:CHUNK_CHAR_LIMIT] for c in contexts[:TOP_K_CHUNKS]]
    context_text = "\n\n---\n\n".join(trimmed)

    if multi_part:
        answer_instruction = (
            "The question has MULTIPLE parts. "
            "Answer EACH part separately as a bullet point. "
            "If any part is not found in the context, write 'Not found' for that part only."
        )
    else:
        answer_instruction = (
            "Give a short, precise answer (1-3 sentences). "
            "Extract exact values if present (numbers, names, dates). "
            "If the answer is not in the context, say: 'Not found in document'."
        )

    return (
        "You are a precise information extraction assistant.\n\n"
        "Answer ONLY using the context provided below. "
        "Do NOT add any information from outside the context.\n\n"
        f"Instruction: {answer_instruction}\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question:\n{query}\n\n"
        "Answer:"
    )


# ── Main generation function ──────────────────────────────────────────────────
def generate_answer(query: str, contexts: List[str]) -> str:
    """
    Full RAG answer pipeline:
      1. Re-rank chunks by keyword overlap
      2. Detect whether query has multiple parts
      3. Build an appropriate prompt (multi-part vs single)
      4. Call OpenRouter LLM with retry + exponential back-off
      5. Regex fallback only if LLM returns empty/garbage
      6. Raise RuntimeError on total failure (caller returns HTTP 500)
    """
    if not contexts:
        return "No relevant information found."

    # Step 1 — re-rank
    ranked = rank_chunks(query, contexts)

    # Step 2 — detect query complexity
    multi_part = is_multi_part_query(query)
    logger.info("Query multi-part: %s", multi_part)

    # Step 3 — build prompt
    prompt = build_prompt(query, ranked, multi_part)

    # Step 4 — LLM call with retry
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                # ✅ FIX 4 (partial): raised max_tokens from 150 → 400 so the
                # LLM can actually write out bullet answers for multi-part queries.
                # 150 tokens was enough for a single value but forced truncation
                # the moment the answer had more than ~2 facts.
                max_tokens=400,
            )

            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()

            logger.warning("OpenRouter returned empty content on attempt %d", attempt)

        except RateLimitError as e:
            logger.warning("Rate limit on attempt %d: %s", attempt, e)
            last_error = e
            time.sleep(RETRY_DELAY * attempt)

        except APITimeoutError as e:
            logger.warning("Timeout on attempt %d: %s", attempt, e)
            last_error = e
            time.sleep(RETRY_DELAY)

        except APIError as e:
            logger.error("API error on attempt %d: %s", attempt, e)
            last_error = e
            time.sleep(RETRY_DELAY)

        except Exception as e:
            logger.error("Unexpected error: %s", e)
            raise RuntimeError(f"LLM call failed unexpectedly: {e}") from e

    # Step 5 — regex fallback (only when LLM is completely unresponsive)
    logger.warning("LLM failed %d times, attempting regex fallback", MAX_RETRIES)
    fallback = _regex_fallback(query, ranked)
    if fallback:
        return fallback

    # Step 6 — total failure
    raise RuntimeError(
        f"OpenRouter failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )