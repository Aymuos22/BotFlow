"""
Retrieval post-processing: lexical MMR, near-duplicate removal, conversation
formatting, and citation labels for the LLM.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def _word_set(text: str) -> set[str]:
    return {w for w in re.split(r"\s+", text.lower()) if w}


def lexical_jaccard(a: str, b: str) -> float:
    wa = _word_set(a)
    wb = _word_set(b)
    if not wa and not wb:
        return 1.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def mmr_lexical_select(
    hits: List[Dict[str, Any]],
    *,
    query: str,
    max_chunks: int,
    lambda_mult: float = 0.55,
) -> List[Dict[str, Any]]:
    """
    Maximal Marginal Relevance using lexical Jaccard (no extra ML deps).

    ``hits`` are dicts with at least ``chunk_text``; order should be by retriever score.
    """
    if not hits or max_chunks <= 0:
        return []
    pool = [h for h in hits if (h.get("chunk_text") or "").strip()]
    if not pool:
        return []

    selected: List[Dict[str, Any]] = []
    candidates = list(pool)

    def rel_score(h: Dict[str, Any]) -> float:
        return lexical_jaccard(query, h.get("chunk_text", ""))

    first = max(candidates, key=rel_score)
    selected.append(first)
    candidates.remove(first)

    while len(selected) < max_chunks and candidates:
        best_h: Optional[Dict[str, Any]] = None
        best_val = float("-inf")
        for h in candidates:
            rel = rel_score(h)
            div = max(
                lexical_jaccard(h.get("chunk_text", ""), s.get("chunk_text", ""))
                for s in selected
            )
            mmr = lambda_mult * rel - (1.0 - lambda_mult) * div
            if mmr > best_val:
                best_val = mmr
                best_h = h
        if best_h is None:
            break
        selected.append(best_h)
        candidates.remove(best_h)

    return selected


def dedupe_chunk_texts(chunks: List[str]) -> List[str]:
    """Drop chunks whose normalized body matches an earlier chunk."""
    out: List[str] = []
    seen_set: set[str] = set()
    for c in chunks:
        body = c
        if body.startswith("[") and "]" in body:
            idx = body.index("]")
            body = body[idx + 1 :].lstrip()
        key = " ".join(body.lower().split())[:800]
        if key in seen_set:
            continue
        seen_set.add(key)
        out.append(c)
    return out


def format_hit_for_llm(hit: Dict[str, Any]) -> str:
    """Prefix chunk text with a stable source label for citations."""
    text = (hit.get("chunk_text") or "").strip()
    fn = (hit.get("file_name") or "document").strip() or "document"
    did = hit.get("document_id")
    idx = hit.get("chunk_index")
    if did is not None and idx is not None:
        label = f"{fn}#{idx}"
    else:
        label = fn
    return f"[{label}] {text}"


def format_conversation_transcript(
    messages: List[Any],
    *,
    max_turns: int = 5,
    max_chars: int = 1200,
) -> str:
    """
    Build a compact transcript from ORM Message rows (chronological).

    ``messages`` should be ordered oldest → newest. Only customer and bot
    lines are included (agent/system skipped for brevity).
    """
    if not messages or max_turns <= 0:
        return ""
    lines: List[str] = []
    window = messages[-max_turns:]
    for m in window:
        st = getattr(m, "sender_type", None)
        txt = (getattr(m, "message_text", None) or "").strip()
        if not txt:
            continue
        if st == "customer":
            lines.append(f"User: {txt}")
        elif st == "bot":
            lines.append(f"Assistant: {txt}")
    blob = "\n".join(lines)
    return blob[:max_chars] if len(blob) > max_chars else blob


def merge_query_with_history(
    current_query: str,
    history: str,
    max_chars: int = 600,
    max_user_turns: int = 3,
) -> str:
    """Build a BM25 search query from the current message + recent user messages only.

    Only "User:" lines are included — assistant responses are deliberately
    excluded because they are very long and dilute keyword relevance when
    injected into a BM25 query.  We keep at most ``max_user_turns`` prior
    user messages so follow-up references ("us wali chiz", "that product")
    can still be resolved without drowning out the current intent.
    """
    c = current_query.strip()
    h = (history or "").strip()
    if not h:
        return c

    user_lines = [
        line[len("User:"):].strip()
        for line in h.splitlines()
        if line.startswith("User:")
    ]
    recent = user_lines[-max_user_turns:] if user_lines else []
    if not recent:
        return c

    context = " ".join(recent)
    merged = f"{context} {c}"
    return merged[:max_chars] if len(merged) > max_chars else merged
