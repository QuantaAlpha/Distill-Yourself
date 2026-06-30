"""Session loading — full parse of JSONL files for conversation view."""

import json
import os

from chatview import index as _idx
from chatview.utils.constants import MAX_THINKING_LEN


def load_session(session_id: str):
    """Load and parse a full conversation by session ID."""
    with _idx._index_lock:
        meta = _idx._index.get("sessions", {}).get(session_id)
    if not meta:
        return None

    # Route Codex sessions to dedicated loader
    if meta.get("source") == "codex":
        from chatview.parsers.codex import load_codex_session as _load_codex

        return _load_codex(session_id, _idx._index, _idx._index_lock)

    filepath = meta["filePath"]
    if not os.path.exists(filepath):
        return None

    title = meta.get("title", "Untitled")
    project = meta.get("projectName", "")
    date = meta.get("date", "")
    return load_session_from_file(filepath, session_id, title, project, date)


def load_session_from_file(
    filepath: str, session_id: str, title: str = "", project: str = "", date: str = ""
):
    """Load and parse a full conversation from a JSONL file path."""
    if not os.path.exists(filepath):
        return None

    messages = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            msg_data = obj.get("message", {})
            content = msg_data.get("content", [])
            is_tool_result = bool(obj.get("toolUseResult"))

            parsed = {
                "id": obj.get("uuid", ""),
                "type": "tool_result" if is_tool_result else msg_type,
                "timestamp": obj.get("timestamp", ""),
                "isSidechain": obj.get("isSidechain", False),
                "content": _parse_content(content),
            }
            messages.append(parsed)

    return {
        "id": session_id,
        "title": title,
        "project": project,
        "date": date,
        "filePath": filepath,
        "messages": messages,
    }


def _parse_content(content) -> list:
    """Parse message content blocks into display-ready format."""
    from chatview.parsers.claude import _strip_tags, _truncate_tool_output

    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    blocks = []
    if not isinstance(content, list):
        return blocks

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")

        if btype == "text":
            text = block.get("text", "")
            if not text.strip():
                continue
            # Skip purely system blocks
            s = text.strip()
            if s.startswith(("<system-reminder", "<command-")):
                continue
            # Strip IDE/system tags, keep user content
            cleaned = _strip_tags(text)
            if cleaned.strip():
                blocks.append({"type": "text", "text": cleaned})

        elif btype == "image":
            blocks.append({"type": "image", "alt": "[Image attachment]"})

        elif btype == "tool_use":
            inp = block.get("input", {})
            tool_name = block.get("name", "")
            # Truncate large input values (but keep Agent prompt intact)
            inp_display = {}
            for k, v in inp.items():
                if isinstance(v, str) and len(v) > 500:
                    if tool_name == "Agent" and k == "prompt":
                        inp_display[k] = v
                    else:
                        inp_display[k] = v[:500] + "…[truncated]"
                else:
                    inp_display[k] = v
            blocks.append(
                {
                    "type": "tool_use",
                    "name": block.get("name", ""),
                    "id": block.get("id", ""),
                    "input": inp_display,
                }
            )

        elif btype == "tool_result":
            raw = block.get("content", "")
            raw = _truncate_tool_output(raw)
            blocks.append(
                {
                    "type": "tool_result",
                    "toolUseId": block.get("tool_use_id", ""),
                    "content": raw,
                }
            )

        elif btype == "thinking":
            text = block.get("thinking", "")
            blocks.append(
                {
                    "type": "thinking",
                    "text": text[:MAX_THINKING_LEN] + "…"
                    if len(text) > MAX_THINKING_LEN
                    else text,
                }
            )

    return blocks
