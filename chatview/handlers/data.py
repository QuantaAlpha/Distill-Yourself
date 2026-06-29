"""Data API endpoint handlers.

Standalone versions of the data-fetching methods originally on
ChatViewerHandler.  Each takes ``handler`` (the request handler instance)
as the first arg.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from chatview import index as _idx
from chatview.parsers import _extract_user_text
from chatview.parsers.codex import _CODEX_TOOL_NAMES


# ---- projects / sessions / timeline / stats --------------------------------

def _get_projects(handler) -> list:
    with _idx._index_lock:
        projects = _idx._index.get("projects", {})
    result = sorted(projects.values(), key=lambda p: p["name"])
    return result


def _get_sessions(handler, project: str) -> list:
    with _idx._index_lock:
        sessions = _idx._index.get("sessions", {})
    result = []
    for sid, meta in sessions.items():
        if project and meta.get("projectName") != project:
            continue
        result.append({
            "id": sid,
            "title": meta.get("title", "Untitled"),
            "project": meta.get("projectName", ""),
            "date": meta.get("date", ""),
            "userMessageCount": meta.get("userMessageCount", 0),
            "fileSize": meta.get("fileSize", 0),
            "source": meta.get("source", "claude"),
        })
    result.sort(key=lambda s: s.get("date", ""), reverse=True)
    return result


def _get_timeline(handler) -> dict:
    """Group sessions by date for the activity timeline view."""
    with _idx._index_lock:
        sessions = _idx._index.get("sessions", {})

    days = {}  # "YYYY-MM-DD" -> {sessions: [...], stats}
    for sid, meta in sessions.items():
        date_str = meta.get("date", "")
        if not date_str:
            continue
        try:
            day = date_str[:10]  # "YYYY-MM-DD"
            # Validate format
            datetime.strptime(day, "%Y-%m-%d")
        except (ValueError, IndexError):
            continue

        if day not in days:
            days[day] = {"date": day, "sessions": [], "totalMessages": 0}

        days[day]["sessions"].append({
            "id": sid,
            "title": meta.get("title", "Untitled"),
            "project": meta.get("projectName", ""),
            "source": meta.get("source", "claude"),
            "userMessageCount": meta.get("userMessageCount", 0),
            "date": date_str,
            "lastDate": meta.get("lastDate", ""),
        })
        days[day]["totalMessages"] += meta.get("userMessageCount", 0)

    # Sort sessions within each day by date desc
    for day_data in days.values():
        day_data["sessions"].sort(key=lambda s: s.get("date", ""), reverse=True)
        day_data["sessionCount"] = len(day_data["sessions"])

    # Return sorted by date desc
    result = sorted(days.values(), key=lambda d: d["date"], reverse=True)
    return {"days": result}


def _get_stats(handler) -> dict:
    with _idx._index_lock:
        return {
            "totalSessions": len(_idx._index.get("sessions", {})),
            "totalProjects": len(_idx._index.get("projects", {})),
        }


# ---- analytics / snippets / file-evolution / project-health ----------------

def _get_analytics(handler) -> dict:
    """Compute analytics from pre-aggregated DB tables."""
    from chatview import db as _db
    home = str(Path.home())

    # File hotspots (top 50)
    raw_hotspots = _db.query_file_hotspots(50)
    hotspots = []
    for row in raw_hotspots:
        fp = row["file_path"]
        short = fp.replace(home, "~") if fp.startswith(home) else fp
        projects = [p for p in (row.get("projects") or "").split(",") if p]
        hotspots.append({
            "path": short,
            "fullPath": fp,
            "count": row["total_count"],
            "sessionCount": row["session_count"],
            "projects": projects,
        })

    # Tool heatmap (last 30 days)
    raw_tools = _db.query_tool_heatmap()
    tool_daily = {}
    for row in raw_tools:
        day = row["day"]
        tool_daily.setdefault(day, {})[row["tool_name"]] = row["total"]

    sorted_days = sorted(tool_daily.keys(), reverse=True)[:30]
    tool_totals = {}
    for day_tools in tool_daily.values():
        for t, c in day_tools.items():
            tool_totals[t] = tool_totals.get(t, 0) + c
    sorted_tools = sorted(tool_totals.keys(), key=lambda t: -tool_totals.get(t, 0))[:15]

    heatmap = {
        "days": sorted_days,
        "tools": sorted_tools,
        "data": {day: {t: tool_daily.get(day, {}).get(t, 0) for t in sorted_tools} for day in sorted_days},
        "totals": {t: tool_totals.get(t, 0) for t in sorted_tools},
    }

    # Error patterns (top 30)
    raw_errors = _db.query_error_patterns(30)
    errors = []
    for row in raw_errors:
        projects = [p for p in (row.get("projects") or "").split(",") if p]
        errors.append({
            "pattern": row["error_key"][:200],
            "count": row["total_count"],
            "sessionCount": row["session_count"],
            "projects": projects,
            "firstSeen": row.get("first_seen", ""),
            "lastSeen": row.get("last_seen", ""),
        })

    return {"hotspots": hotspots, "heatmap": heatmap, "errors": errors}


def _get_session_summary(handler, session_id: str) -> dict:
    """F11: Request vs Reality — first user request vs files actually changed."""
    with _idx._index_lock:
        sessions = _idx._index.get("sessions", {})
    meta = sessions.get(session_id)
    if not meta:
        return {"request": "", "files": [], "tools": {}}

    filepath = meta.get("filePath", "")
    source = meta.get("source", "claude")
    if not filepath or not os.path.exists(filepath):
        return {"request": "", "files": [], "tools": {}}

    first_user_msg = ""
    files_touched = {}  # path -> {reads, edits, writes}
    tool_counts = {}

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if source == "claude":
                    msg_type = obj.get("type")
                    if msg_type == "user" and not obj.get("toolUseResult") and not first_user_msg:
                        content = obj.get("message", {}).get("content", [])
                        first_user_msg = _extract_user_text(content)[:500]
                    elif msg_type == "assistant":
                        content = obj.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_use":
                                    name = block.get("name", "")
                                    tool_counts[name] = tool_counts.get(name, 0) + 1
                                    inp = block.get("input", {})
                                    fp = inp.get("file_path") or inp.get("path") or ""
                                    if fp and not fp.startswith("/tmp"):
                                        home = str(Path.home())
                                        short = fp.replace(home, "~") if fp.startswith(home) else fp
                                        if short not in files_touched:
                                            files_touched[short] = {"reads": 0, "edits": 0, "writes": 0}
                                        if name in ("Read", "Glob", "Grep"):
                                            files_touched[short]["reads"] += 1
                                        elif name == "Edit":
                                            files_touched[short]["edits"] += 1
                                        elif name == "Write":
                                            files_touched[short]["writes"] += 1
                elif source == "codex":
                    rec_type = obj.get("type")
                    payload = obj.get("payload", {})
                    if rec_type == "event_msg" and payload.get("type") == "user_message" and not first_user_msg:
                        first_user_msg = payload.get("message", "")[:500]
                    elif rec_type == "response_item" and payload.get("type") in ("function_call", "custom_tool_call"):
                        raw_name = payload.get("name", "")
                        name = _CODEX_TOOL_NAMES.get(raw_name, raw_name)
                        tool_counts[name] = tool_counts.get(name, 0) + 1
    except Exception:
        pass

    # Sort files: most edits first
    file_list = sorted(
        [{"path": fp, **counts} for fp, counts in files_touched.items()],
        key=lambda x: -(x["edits"] + x["writes"]),
    )[:30]

    return {"request": first_user_msg, "files": file_list, "tools": tool_counts}


def _get_snippets(handler) -> dict:
    """Solution Snippet Library from pre-aggregated DB."""
    from chatview import db as _db
    raw = _db.query_snippets(150)
    snippets = []
    for row in raw:
        snippets.append({
            "sessionId": row["session_id"],
            "sessionTitle": row.get("session_title") or "Untitled",
            "project": row.get("project") or "",
            "language": row.get("language") or "",
            "code": row.get("code") or "",
            "context": row.get("context") or "",
            "date": row.get("date") or "",
            "applied": bool(row.get("applied")),
        })
    return {"snippets": snippets}


def _get_file_evolution(handler, file_path: str) -> dict:
    """F13: Cross-session edit timeline for a specific file."""
    if not file_path:
        return {"file": "", "events": []}

    with _idx._index_lock:
        sessions = dict(_idx._index.get("sessions", {}))

    basename = os.path.basename(file_path)
    events = []

    for sid, meta in sessions.items():
        filepath = meta.get("filePath", "")
        source = meta.get("source", "claude")
        if not filepath or not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                prev_user_msg = ""
                for line in f:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg_type = obj.get("type")
                    if source == "claude":
                        if msg_type == "user" and not obj.get("toolUseResult"):
                            content = obj.get("message", {}).get("content", [])
                            prev_user_msg = _extract_user_text(content)[:200]
                        elif msg_type == "assistant":
                            content = obj.get("message", {}).get("content", [])
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "tool_use":
                                        name = block.get("name", "")
                                        inp = block.get("input", {})
                                        fp = inp.get("file_path") or inp.get("path") or ""
                                        if fp and os.path.basename(fp) == basename and name in ("Edit", "Write"):
                                            events.append({
                                                "sessionId": sid,
                                                "sessionTitle": meta.get("title", ""),
                                                "project": meta.get("projectName", ""),
                                                "date": meta.get("date", ""),
                                                "tool": name,
                                                "context": prev_user_msg,
                                            })
        except Exception:
            continue

    events.sort(key=lambda e: e.get("date", ""))
    return {"file": file_path, "basename": basename, "events": events[:50]}


def _get_project_health(handler) -> dict:
    """F14: Project Health Dashboard — cross-project aggregate metrics."""
    with _idx._index_lock:
        sessions = dict(_idx._index.get("sessions", {}))

    projects = {}
    now = datetime.now()

    for sid, meta in sessions.items():
        pname = meta.get("projectName", "unknown")
        source = meta.get("source", "claude")
        date_str = meta.get("date", "")
        msgs = meta.get("userMessageCount", 0)

        if pname not in projects:
            projects[pname] = {
                "name": pname,
                "source": source,
                "sessionCount": 0,
                "totalMessages": 0,
                "firstSeen": date_str,
                "lastSeen": date_str,
                "recentSessions": 0,  # last 7 days
                "sessions_by_week": {},
            }
        p = projects[pname]
        p["sessionCount"] += 1
        p["totalMessages"] += msgs
        if date_str and (not p["firstSeen"] or date_str < p["firstSeen"]):
            p["firstSeen"] = date_str
        if date_str and (not p["lastSeen"] or date_str > p["lastSeen"]):
            p["lastSeen"] = date_str

        # Recent activity
        if date_str:
            try:
                d = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if (now - d).days <= 7:
                    p["recentSessions"] += 1
                # Week bucket
                week_key = d.strftime("%Y-W%W")
                p["sessions_by_week"][week_key] = p["sessions_by_week"].get(week_key, 0) + 1
            except Exception:
                pass

    # Compute staleness and trend
    result = []
    for pname, p in projects.items():
        staleness = 999
        if p["lastSeen"]:
            try:
                last = datetime.fromisoformat(p["lastSeen"].replace("Z", "+00:00")).replace(tzinfo=None)
                staleness = (now - last).days
            except Exception:
                pass

        # Activity trend: compare last 2 weeks
        weeks = sorted(p["sessions_by_week"].keys())
        trend = "stable"
        if len(weeks) >= 2:
            last_week = p["sessions_by_week"].get(weeks[-1], 0)
            prev_week = p["sessions_by_week"].get(weeks[-2], 0)
            if last_week > prev_week * 1.5:
                trend = "up"
            elif last_week < prev_week * 0.5:
                trend = "down"

        result.append({
            "name": pname,
            "source": p["source"],
            "sessionCount": p["sessionCount"],
            "totalMessages": p["totalMessages"],
            "firstSeen": p["firstSeen"][:10] if p["firstSeen"] else "",
            "lastSeen": p["lastSeen"][:10] if p["lastSeen"] else "",
            "staleDays": staleness,
            "recentSessions": p["recentSessions"],
            "trend": trend,
        })

    result.sort(key=lambda p: (-p["recentSessions"], p["staleDays"]))
    return {"projects": result}
