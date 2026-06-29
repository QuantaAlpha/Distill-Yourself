"""Evolve cache — AI-generated tab data storage."""

import json
from datetime import datetime
from typing import Optional

from .core import get_conn


def evolve_upsert(tab: str, source: str, date_range: str, project: str,
                  engine: str, data_json: str):
    """Insert or replace evolve tab data for a given scope."""
    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO evolve_cache (tab, source, date_range, project, engine,
                                  data, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tab, source, date_range, project, engine)
        DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
    """, (tab, source or "all", date_range or "7d", project or "",
          engine or "auto", data_json, now, now))
    conn.commit()


def evolve_get(tab: str, source: str, date_range: str, project: str,
               engine: str) -> Optional[dict]:
    """Return {data, updated_at} for an exact scope, or None."""
    conn = get_conn()
    row = conn.execute("""
        SELECT data, updated_at FROM evolve_cache
        WHERE tab=? AND source=? AND date_range=? AND project=? AND engine=?
    """, (tab, source or "all", date_range or "7d", project or "",
          engine or "auto")).fetchone()
    if row:
        return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}
    return None


def evolve_latest(tab: str) -> Optional[dict]:
    """Return most recent data for a tab regardless of scope (for Twin)."""
    conn = get_conn()
    row = conn.execute("""
        SELECT data, updated_at FROM evolve_cache
        WHERE tab=? ORDER BY updated_at DESC LIMIT 1
    """, (tab,)).fetchone()
    if row:
        return {"data": json.loads(row["data"]), "updated_at": row["updated_at"]}
    return None
