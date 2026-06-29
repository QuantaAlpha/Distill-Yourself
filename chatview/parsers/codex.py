"""Codex CLI JSONL parsing functions.

Extracted from server.py — handles Codex CLI session JSONL format.
"""

import json
import os
import re
from pathlib import Path

from chatview.parsers.claude import _truncate_tool_output


# ---------------------------------------------------------------------------
# Constants (mirrored from server.py config)
# ---------------------------------------------------------------------------
CODEX_DIR = Path.home() / ".codex"
CODEX_SESSIONS_DIR = CODEX_DIR / "sessions"
CODEX_ARCHIVED_DIR = CODEX_DIR / "archived_sessions"
CODEX_INDEX_FILE = CODEX_DIR / "session_index.jsonl"

# Module-level state
_codex_titles = {}  # session_id -> thread_name

_CODEX_TOOL_NAMES = {
    "shell": "Bash", "exec_command": "Bash", "write_stdin": "Bash",
    "apply_patch": "Edit", "read_file": "Read", "write_file": "Write",
    "list_directory": "Glob",
}


def _normalize_error(msg: str) -> str:
    """Normalize error message for grouping: strip paths, numbers, hashes."""
    s = msg.strip()
    # Remove file paths
    s = re.sub(r'(/[^\s:]+)', '<path>', s)
    # Remove line numbers
    s = re.sub(r'line \d+', 'line N', s, flags=re.IGNORECASE)
    # Remove hex addresses
    s = re.sub(r'0x[0-9a-f]+', '0xN', s, flags=re.IGNORECASE)
    return s[:150]


# ---------------------------------------------------------------------------
# Codex CLI — helpers
# ---------------------------------------------------------------------------
def _load_codex_titles():
    """Load Codex session titles from session_index.jsonl."""
    global _codex_titles
    _codex_titles = {}
    if not CODEX_INDEX_FILE.exists():
        return
    try:
        with open(CODEX_INDEX_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    sid = obj.get("id", "")
                    name = obj.get("thread_name", "")
                    if sid and name:
                        _codex_titles[sid] = name
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass


def _codex_project_name(cwd: str) -> str:
    """Derive a readable project name from Codex session cwd."""
    if not cwd:
        return "Codex"
    home = str(Path.home())
    name = cwd
    if name.startswith(home):
        name = name[len(home):].lstrip("/")
    for prefix in ("Desktop/proj/", "Desktop/personal/", "Desktop/", "Documents/"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name or "Codex"


# ---------------------------------------------------------------------------
# Codex CLI — metadata extraction
# ---------------------------------------------------------------------------
def extract_codex_metadata(filepath: str):
    """Quick scan of a Codex JSONL file to extract session metadata."""
    session_id = None
    first_ts = None
    last_ts = None
    cwd = None
    user_texts = []
    assistant_snippets = []
    msg_index = 0
    # Insight extraction accumulators
    _tool_daily = {}
    _file_refs = {}
    _error_list = []
    _err_re = re.compile(
        r'((?:Traceback.*?:\s*)?'
        r'(?:(?:Error|Exception|TypeError|ValueError|KeyError|AttributeError|'
        r'ImportError|ModuleNotFoundError|NameError|IndexError|RuntimeError|'
        r'SyntaxError|FileNotFoundError|PermissionError|OSError|IOError|'
        r'ConnectionError|TimeoutError)'
        r'[:\s].{0,120}))',
        re.IGNORECASE
    )

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = obj.get("timestamp", "")
                if not first_ts and ts:
                    first_ts = ts
                last_ts = ts or last_ts
                rec_type = obj.get("type")
                payload = obj.get("payload", {})

                if rec_type == "session_meta":
                    session_id = payload.get("id", "")
                    cwd = payload.get("cwd", "")

                elif rec_type == "event_msg" and payload.get("type") == "user_message":
                    text = payload.get("message", "")
                    if text.strip():
                        user_texts.append({"idx": msg_index, "text": text[:2000], "ts": ts})
                    msg_index += 1

                elif rec_type == "response_item":
                    p_type = payload.get("type")
                    if p_type == "message" and payload.get("role") == "assistant":
                        blocks = payload.get("content", [])
                        for blk in blocks:
                            if isinstance(blk, dict) and blk.get("type") == "output_text":
                                t = blk.get("text", "").strip()
                                if t:
                                    assistant_snippets.append({"idx": msg_index, "text": t[:300], "ts": ts})
                                    break
                        msg_index += 1
                    elif p_type in ("function_call", "custom_tool_call"):
                        # Insight: tool usage + file refs
                        raw_name = payload.get("name", "unknown")
                        tool_name = _CODEX_TOOL_NAMES.get(raw_name, raw_name)
                        day = (first_ts or "")[:10]
                        if day:
                            key = (day, tool_name)
                            _tool_daily[key] = _tool_daily.get(key, 0) + 1
                        args_str = payload.get("arguments", "{}")
                        try:
                            args = json.loads(args_str) if isinstance(args_str, str) else {}
                        except json.JSONDecodeError:
                            args = {}
                        fp = args.get("file_path") or args.get("path") or ""
                        if fp and not fp.startswith("/tmp"):
                            _file_refs[fp] = _file_refs.get(fp, 0) + 1
                        msg_index += 1
                    elif p_type in ("function_call_output", "custom_tool_call_output"):
                        # Insight: errors from tool output
                        output = payload.get("output", "")
                        if isinstance(output, str):
                            day = (first_ts or "")[:10]
                            for m in _err_re.finditer(output[:5000]):
                                norm = _normalize_error(m.group(1))
                                if len(norm) >= 10:
                                    _error_list.append((norm, day))
                        msg_index += 1
    except Exception:
        return None

    if not session_id:
        stem = Path(filepath).stem
        parts = stem.split("-")
        session_id = "-".join(parts[-5:]) if len(parts) >= 6 else stem

    title = _codex_titles.get(session_id, "")
    if not title and user_texts:
        title = user_texts[0]["text"][:80]

    return {
        "id": "codex-" + session_id,
        "title": title or "Untitled",
        "date": first_ts or "",
        "lastDate": last_ts or "",
        "filePath": filepath,
        "fileSize": os.path.getsize(filepath),
        "userMessageCount": len(user_texts),
        "userTexts": user_texts,
        "assistantSnippets": assistant_snippets,
        "preview": user_texts[0]["text"][:200] if user_texts else "",
        "source": "codex",
        "cwd": cwd or "",
        "_insight_tools": _tool_daily,
        "_insight_files": _file_refs,
        "_insight_errors": _error_list,
        "_insight_snippets": [],
    }


# ---------------------------------------------------------------------------
# Codex CLI — full session loading
# ---------------------------------------------------------------------------
def load_codex_session(session_id: str, index: dict, index_lock):
    """Load and parse a full Codex conversation by session ID.

    Args:
        session_id: The Codex session ID (prefixed with "codex-").
        index: The shared _index dict from server.py.
        index_lock: The threading.Lock protecting _index.
    """
    with index_lock:
        meta = index.get("sessions", {}).get(session_id)
    if not meta or meta.get("source") != "codex":
        return None

    filepath = meta["filePath"]
    if not os.path.exists(filepath):
        return None

    messages = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp", "")
            rec_type = obj.get("type")
            payload = obj.get("payload", {})

            # User message
            if rec_type == "event_msg" and payload.get("type") == "user_message":
                text = payload.get("message", "")
                if text.strip():
                    messages.append({
                        "id": payload.get("client_id", ""),
                        "type": "user",
                        "timestamp": ts,
                        "isSidechain": False,
                        "content": [{"type": "text", "text": text}],
                    })

            elif rec_type == "response_item":
                p_type = payload.get("type")

                # Assistant text
                if p_type == "message" and payload.get("role") == "assistant":
                    blocks = payload.get("content", [])
                    texts = [b.get("text", "") for b in blocks if b.get("type") == "output_text"]
                    text = "\n".join(texts)
                    if text.strip():
                        messages.append({
                            "id": "", "type": "assistant", "timestamp": ts,
                            "isSidechain": False,
                            "content": [{"type": "text", "text": text}],
                        })

                # Tool call
                elif p_type in ("function_call", "custom_tool_call"):
                    name = payload.get("name", "")
                    if p_type == "function_call":
                        args_str = payload.get("arguments", "{}")
                        try:
                            inp = json.loads(args_str)
                        except (json.JSONDecodeError, TypeError):
                            inp = {"raw": args_str}
                    else:
                        raw = payload.get("input", "")
                        inp = {"raw": raw[:500] + "…" if len(raw) > 500 else raw}
                    # Truncate large values
                    inp_display = {}
                    for k, v in inp.items():
                        if isinstance(v, str) and len(v) > 500:
                            inp_display[k] = v[:500] + "…[truncated]"
                        else:
                            inp_display[k] = v
                    messages.append({
                        "id": "", "type": "assistant", "timestamp": ts,
                        "isSidechain": False,
                        "content": [{
                            "type": "tool_use",
                            "name": _CODEX_TOOL_NAMES.get(name, name),
                            "id": payload.get("call_id", ""),
                            "input": inp_display,
                        }],
                    })

                # Tool result
                elif p_type in ("function_call_output", "custom_tool_call_output"):
                    output = payload.get("output", "")
                    output = _truncate_tool_output(output)
                    messages.append({
                        "id": "", "type": "tool_result", "timestamp": ts,
                        "isSidechain": False,
                        "content": [{
                            "type": "tool_result",
                            "toolUseId": payload.get("call_id", ""),
                            "content": output,
                        }],
                    })

    return {
        "id": session_id,
        "title": meta.get("title", "Untitled"),
        "project": meta.get("projectName", ""),
        "date": meta.get("date", ""),
        "filePath": filepath,
        "messages": messages,
        "source": "codex",
    }


# ---------------------------------------------------------------------------
# Insight DB storage (called during index build for changed sessions)
# ---------------------------------------------------------------------------
def _store_session_insights(meta):
    """Extract insight data from meta and store in DB."""
    from chatview import db as _db
    sid = meta["id"]
    project = meta.get("projectName", "")
    date_str = meta.get("date", "")

    _db.clear_session_insights(sid)

    tool_daily = meta.get("_insight_tools", {})
    if tool_daily:
        _db.bulk_insert_tool_usage([
            (sid, day, tool, count) for (day, tool), count in tool_daily.items()
        ])

    file_refs = meta.get("_insight_files", {})
    if file_refs:
        _db.bulk_insert_file_refs([
            (sid, fp, count, project) for fp, count in file_refs.items()
        ])

    error_list = meta.get("_insight_errors", [])
    if error_list:
        err_agg = {}
        for norm, day in error_list:
            if norm not in err_agg:
                err_agg[norm] = {"day": day, "count": 0}
            err_agg[norm]["count"] += 1
        _db.bulk_insert_errors([
            (sid, key, data["day"], project, data["count"])
            for key, data in err_agg.items()
        ])

    snippet_list = meta.get("_insight_snippets", [])
    if snippet_list:
        _db.bulk_insert_snippets([
            (sid, lang, code, context, date_str, int(applied))
            for lang, code, context, applied in snippet_list
        ])
