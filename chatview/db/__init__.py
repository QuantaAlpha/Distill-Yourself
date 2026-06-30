"""Database layer — re-exports all public symbols for backward compatibility.

Usage:
    from chatview.db import get_conn, init_db, upsert_session, ...
"""

from .core import get_conn, init_db, DB_PATH, CACHE_DIR
from .sessions import (
    upsert_session, rebuild_fts, prune_stale_sessions,
    get_filtered_sessions, get_user_queries, search_fts,
    get_session_meta, get_session_messages,
)
from .insights import (
    get_aggregate, set_aggregate, refresh_aggregates,
    clear_session_insights,
    bulk_insert_tool_usage, bulk_insert_file_refs,
    bulk_insert_errors, bulk_insert_snippets,
    query_tool_heatmap, query_file_hotspots,
    query_error_patterns, query_snippets,
)
from .twin import (
    _CM_TABLES,
    cm_upsert, cm_get, cm_get_all, cm_delete, cm_count,
    cm_add_card_relation, cm_get_evidence_for_card,
    cm_get_card_relations, get_twin_stats,
)
from .evolve import evolve_upsert, evolve_get, evolve_latest

__all__ = [
    "get_conn", "init_db", "DB_PATH", "CACHE_DIR",
    "upsert_session", "rebuild_fts", "prune_stale_sessions",
    "get_filtered_sessions", "get_user_queries", "search_fts",
    "get_session_meta", "get_session_messages",
    "get_aggregate", "set_aggregate", "refresh_aggregates",
    "clear_session_insights",
    "bulk_insert_tool_usage", "bulk_insert_file_refs",
    "bulk_insert_errors", "bulk_insert_snippets",
    "query_tool_heatmap", "query_file_hotspots",
    "query_error_patterns", "query_snippets",
    "_CM_TABLES",
    "cm_upsert", "cm_get", "cm_get_all", "cm_delete", "cm_count",
    "cm_add_card_relation", "cm_get_evidence_for_card",
    "cm_get_card_relations", "get_twin_stats",
    "evolve_upsert", "evolve_get", "evolve_latest",
]
