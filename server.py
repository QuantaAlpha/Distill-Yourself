#!/usr/bin/env python3
"""Thin wrapper — delegates to chatview.server for backward compatibility.

Re-exports symbols used by analyze.py, tests, and other consumers so that
``import server`` continues to work unchanged.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
# Server core (ChatViewerHandler, main, PORT, etc.)
# ---------------------------------------------------------------------------
from chatview.server import *  # noqa: F401,F403
from chatview.server import main, ChatViewerHandler, PORT, STATIC_DIR

# ---------------------------------------------------------------------------
# Index state & functions (used by analyze.py, tests)
# ---------------------------------------------------------------------------
from chatview.index import (  # noqa: F401
    PROJECTS_DIR, CACHE_DIR, INDEX_CACHE,
    CODEX_SESSIONS_DIR, CODEX_ARCHIVED_DIR, CODEX_INDEX_FILE,
    _index, _index_lock, _index_gen,
    build_index, schedule_index_refresh_if_stale,
)

# ---------------------------------------------------------------------------
# Parsers (used by analyze.py, tests)
# ---------------------------------------------------------------------------
from chatview.parsers import (  # noqa: F401
    pretty_project_name,
    extract_metadata,
    _strip_tags,
    _extract_user_text,
    _is_system_text,
    _truncate_tool_output,
    _load_codex_titles,
    _codex_project_name,
    extract_codex_metadata,
    load_codex_session,
    _store_session_insights,
)
from chatview.parsers.codex import _CODEX_TOOL_NAMES  # noqa: F401

# ---------------------------------------------------------------------------
# Session loader (used by analyze.py, tests)
# ---------------------------------------------------------------------------
from chatview.session_loader import (  # noqa: F401
    load_session,
    load_session_from_file,
    _parse_content,
)

# ---------------------------------------------------------------------------
# Search helpers (used by tests)
# ---------------------------------------------------------------------------
from chatview.search import (  # noqa: F401
    search_sessions,
    _tokenize_query,
    _fuzzy_match,
)

# ---------------------------------------------------------------------------
# AI engine helpers (used by analyze.py)
# ---------------------------------------------------------------------------
from chatview.ai_engine import (  # noqa: F401
    _select_cognitive_avatar,
    _normalize_error,
)

if __name__ == "__main__":
    main()
