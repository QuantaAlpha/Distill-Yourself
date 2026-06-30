"""Cognitive Model (Digital Twin) CRUD helpers."""

import sqlite3
from datetime import datetime
from typing import Optional

from .core import get_conn


# Table registry: name -> data columns (excluding id, updated_at which are auto-managed)
_CM_TABLES = {
    "evidence_events": ["run_id", "session_id", "event_index", "card_id", "task_type",
                        "ai_action", "user_reaction", "resolution", "lesson",
                        "signal_type", "signal_intensity", "domain", "created_at"],
    "judgment_cards": ["run_id", "applies_when", "judgment", "agent_action", "exceptions",
                       "tags", "confidence", "status", "evidence_count", "created_at"],
    "card_relations": ["from_id", "to_id", "relation"],
    "cognitive_traits": ["run_id", "name", "category", "description", "strength",
                         "supporting_card_ids", "status", "evidence_count"],
}

# Full column whitelist for ORDER BY / validation (includes id and audit columns)
_CM_ALL_COLUMNS = {
    table: {"id"} | set(cols) | (
        {"updated_at"} if table in ("judgment_cards", "cognitive_traits") else set()
    )
    for table, cols in _CM_TABLES.items()
}


def _validate_cm_table(table: str) -> None:
    if table not in _CM_TABLES:
        raise ValueError(f"Unknown CM table: {table}")


def _validate_order(table: str, order: str) -> None:
    """Validate ORDER BY clause: column names must be in the table's whitelist.

    Accepts forms like: "col", "col DESC", "col ASC", "col1, col2 DESC".
    """
    if not order:
        return
    valid_cols = _CM_ALL_COLUMNS[table]
    for part in order.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"Empty ORDER BY fragment: {order!r}")
        tokens = part.split()
        if len(tokens) == 0 or len(tokens) > 2:
            raise ValueError(f"Invalid ORDER BY fragment: {part!r}")
        col = tokens[0]
        direction = tokens[1].upper() if len(tokens) == 2 else "ASC"
        if col not in valid_cols:
            raise ValueError(
                f"Invalid ORDER BY column {col!r} for table {table!r}. "
                f"Valid columns: {sorted(valid_cols)}"
            )
        if direction not in ("ASC", "DESC"):
            raise ValueError(
                f"Invalid ORDER BY direction {direction!r} in {order!r}"
            )


def cm_upsert(table: str, item_id: str, data: dict, commit: bool = True):
    """Insert or update a cognitive model row. Partial updates are safe."""
    conn = get_conn()
    cols = _CM_TABLES.get(table)
    if not cols:
        raise ValueError(f"Unknown CM table: {table}")

    now = datetime.utcnow().isoformat()
    has_updated = table not in ("evidence_events", "card_relations")

    if "created_at" in cols and "created_at" not in data:
        data = {**data, "created_at": now}

    existing = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
    if existing:
        merged = dict(existing)
        merged.update({k: v for k, v in data.items() if v is not None})
        if has_updated:
            merged["updated_at"] = now
        update_cols = [c for c in cols + (["updated_at"] if has_updated else []) if c in merged]
        assignments = ",".join(f"{c}=?" for c in update_cols)
        vals = [merged[c] for c in update_cols] + [item_id]
        conn.execute(f"UPDATE {table} SET {assignments} WHERE id=?", vals)
    else:
        if table == "evidence_events" and data.get("session_id") is not None and data.get("event_index") is not None:
            run_id = data.get("run_id")
            if run_id:
                conflict = conn.execute(
                    "SELECT id FROM evidence_events WHERE run_id=? AND session_id=? AND event_index=?",
                    (run_id, data.get("session_id"), data.get("event_index")),
                ).fetchone()
            else:
                conflict = conn.execute(
                    "SELECT id FROM evidence_events WHERE (run_id IS NULL OR run_id='') AND session_id=? AND event_index=?",
                    (data.get("session_id"), data.get("event_index")),
                ).fetchone()
            if conflict and conflict["id"] != item_id:
                raise ValueError(
                    f"Duplicate evidence event for session_id={data.get('session_id')} "
                    f"event_index={data.get('event_index')} run_id={run_id or ''}: existing id={conflict['id']}"
                )
        all_cols = ["id"] + [c for c in cols if c in data]
        if has_updated:
            all_cols.append("updated_at")
        vals = [item_id] + [data.get(c) for c in cols if c in data]
        if has_updated:
            vals.append(now)
        placeholders = ",".join("?" * len(all_cols))
        col_str = ",".join(all_cols)
        conn.execute(
            f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})",
            vals,
        )
    if commit:
        conn.commit()


def cm_get(table: str, item_id: str) -> Optional[dict]:
    """Get a single row by id."""
    _validate_cm_table(table)
    conn = get_conn()
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def cm_get_all(table: str, where: str = "", params: tuple = (), order: str = "",
               limit: int = 500) -> list:
    """Get all rows from a CM table with optional filters.

    Args:
        table: CM table name (must be in _CM_TABLES whitelist).
        where: SQL WHERE clause **without** user-supplied values in the string.
            Only clause structure (column names, operators) should appear here;
            user values must be passed via ``params`` as parameterized placeholders.
        params: Parameter values for the ``where`` clause.
        order: ORDER BY clause (column names validated against table schema).
        limit: Maximum number of rows to return.
    """
    _validate_cm_table(table)
    _validate_order(table, order)
    conn = get_conn()
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    if order:
        sql += f" ORDER BY {order}"
    sql += f" LIMIT {limit}"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def cm_delete(table: str, item_id: str, commit: bool = True):
    """Delete a single row by id."""
    _validate_cm_table(table)
    conn = get_conn()
    conn.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
    if commit:
        conn.commit()


def cm_count(table: str, where: str = "", params: tuple = ()) -> int:
    """Count rows in a CM table.

    Args:
        table: CM table name (must be in _CM_TABLES whitelist).
        where: SQL WHERE clause **without** user-supplied values in the string.
            Only clause structure (column names, operators) should appear here;
            user values must be passed via ``params`` as parameterized placeholders.
        params: Parameter values for the ``where`` clause.
    """
    _validate_cm_table(table)
    conn = get_conn()
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return conn.execute(sql, params).fetchone()[0]


def cm_add_card_relation(from_id: str, to_id: str, relation: str):
    """Add a relation between two judgment cards."""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO card_relations (from_id, to_id, relation) "
        "VALUES (?,?,?)",
        (from_id, to_id, relation),
    )
    conn.commit()


def cm_get_evidence_for_card(card_id: str) -> list:
    """Get all evidence events linked to a judgment card."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM evidence_events WHERE card_id=? ORDER BY created_at DESC",
        (card_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def cm_get_card_relations(card_id: str) -> list:
    """Get all relations involving a card (as source or target)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM card_relations WHERE from_id=? OR to_id=?",
        (card_id, card_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_twin_stats() -> dict:
    """Return cognitive handbook statistics."""
    conn = get_conn()
    stats = {}
    _CONF_TABLES = {"judgment_cards", "cognitive_traits"}
    _UPDATED_TABLES = {"judgment_cards", "cognitive_traits"}
    for table in _CM_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        stats[table] = {"count": count}
        if table in _CONF_TABLES:
            try:
                conf_col = "confidence" if table == "judgment_cards" else "strength"
                rows = conn.execute(
                    f"SELECT AVG({conf_col}) as avg_conf, "
                    f"MIN({conf_col}) as min_conf, MAX({conf_col}) as max_conf "
                    f"FROM {table} WHERE {conf_col} IS NOT NULL"
                ).fetchone()
                if rows and rows["avg_conf"] is not None:
                    stats[table]["confidence"] = {
                        "avg": round(rows["avg_conf"], 2),
                        "min": round(rows["min_conf"], 2),
                        "max": round(rows["max_conf"], 2),
                    }
            except sqlite3.OperationalError:
                pass
        if table in _UPDATED_TABLES:
            try:
                row = conn.execute(
                    f"SELECT MAX(updated_at) as last FROM {table}"
                ).fetchone()
                if row and row["last"]:
                    stats[table]["last_updated"] = row["last"]
            except sqlite3.OperationalError:
                pass
    return stats
