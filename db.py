"""Thin wrapper — delegates to chatview.db for backward compatibility.

All actual implementation lives in chatview/db/ submodules.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Re-export everything from chatview.db
from chatview.db import *  # noqa: F401,F403

# Explicit re-exports for symbols used by tests and external callers
from chatview.db.core import (  # noqa: F401
    get_conn, init_db, DB_PATH, CACHE_DIR, _local,
)
from chatview.db.sessions import (  # noqa: F401
    upsert_session, rebuild_fts, prune_stale_sessions,
    get_filtered_sessions, get_user_queries, search_fts,
    get_session_meta, get_session_by_partial_id, get_session_messages,
)
from chatview.db.insights import (  # noqa: F401
    get_aggregate, set_aggregate, refresh_aggregates,
    clear_session_insights,
    bulk_insert_tool_usage, bulk_insert_file_refs,
    bulk_insert_errors, bulk_insert_snippets,
    query_tool_heatmap, query_file_hotspots,
    query_error_patterns, query_snippets,
)
from chatview.db.twin import (  # noqa: F401
    _CM_TABLES,
    cm_upsert, cm_get, cm_get_all, cm_delete, cm_count,
    cm_add_card_relation, cm_get_evidence_for_card,
    cm_get_card_relations, get_twin_stats,
)
from chatview.db.evolve import evolve_upsert, evolve_get, evolve_latest  # noqa: F401
