"""Search functions for session content and titles."""

import re

from chatview import index as _idx
from chatview.index import schedule_index_refresh_if_stale


def _tokenize_query(query: str) -> list:
    """Split query into tokens by whitespace and punctuation for fuzzy matching."""
    tokens = re.split(
        r"""[\s，。、！？；：""''（）【】《》,.!?;:()\[\]<>\-—…·]+""", query
    )
    return [t for t in tokens if len(t) >= 2]


def _fuzzy_match(text_lower: str, query_lower: str, tokens: list):
    """Returns (matched, score). Exact substring → 1.0, token-based → ratio."""
    if query_lower in text_lower:
        return True, 1.0
    if not tokens:
        return False, 0
    matched = sum(1 for t in tokens if t in text_lower)
    ratio = matched / len(tokens)
    # Adaptive threshold: fewer tokens → more lenient
    threshold = 0.4 if len(tokens) <= 3 else 0.6
    if ratio >= threshold:
        return True, ratio
    return False, 0


def search_sessions(query: str, refresh_on_empty: bool = True) -> list:
    """Search user messages via SQLite FTS5 + title fuzzy fallback."""
    if not query or len(query) < 2:
        return []

    from chatview import db as _db

    results = []
    seen = set()  # (session_id, idx) dedup

    # 1) FTS5 search on message content (fast, indexed)
    fts_rows = _db.search_fts(query, limit=100)
    for row in fts_rows:
        key = (row["session_id"], row["idx"])
        if key in seen:
            continue
        seen.add(key)
        text = row.get("text", "")
        results.append(
            {
                "sessionId": row["session_id"],
                "title": row.get("title", "Untitled"),
                "project": row.get("project_name", ""),
                "date": row.get("ts", ""),
                "messageIndex": row["idx"],
                "snippet": _make_snippet(text, query.lower()),
                "timestamp": row.get("ts", ""),
                "matchType": "content",
                "score": 0.9,
            }
        )

    # 2) Title fuzzy match (still in-memory, but lightweight — one string per session)
    query_lower = query.lower()
    tokens = _tokenize_query(query_lower)
    with _idx._index_lock:
        sessions = dict(_idx._index.get("sessions", {}))
    for sid, meta in sessions.items():
        title = meta.get("title", "Untitled")
        matched, score = _fuzzy_match(title.lower(), query_lower, tokens)
        if matched and (sid, 0) not in seen:
            seen.add((sid, 0))
            results.append(
                {
                    "sessionId": sid,
                    "title": title,
                    "project": meta.get("projectName", ""),
                    "date": meta.get("date", ""),
                    "messageIndex": 0,
                    "snippet": title,
                    "timestamp": meta.get("date", ""),
                    "matchType": "title",
                    "score": score,
                }
            )

    results.sort(key=lambda r: (-r.get("score", 0), r.get("date", "")), reverse=False)
    if not results and refresh_on_empty:
        schedule_index_refresh_if_stale(reason="search-empty")
    return results[:100]


def _make_snippet(text: str, query: str, tokens: list = None, ctx: int = 80) -> str:
    """Create a context snippet around the first match."""
    idx = text.lower().find(query)
    if idx == -1 and tokens:
        # Find first matching token for snippet context
        for t in tokens:
            idx = text.lower().find(t)
            if idx != -1:
                break
    if idx == -1:
        return text[:160]
    start = max(0, idx - ctx)
    end = min(len(text), idx + len(query) + ctx)
    snippet = (
        ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
    )
    return snippet
