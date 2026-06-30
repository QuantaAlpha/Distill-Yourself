"""Claude JSONL parsing functions.

Extracted from server.py — handles Claude Code session JSONL format.
"""

import json
import os
import re
from pathlib import Path

from chatview.utils.constants import MAX_TOOL_RESULT_LEN
from chatview.utils.text import normalize_error as _normalize_error


# ---------------------------------------------------------------------------
# Constants (mirrored from server.py config)
# ---------------------------------------------------------------------------
def pretty_project_name(dirname: str) -> str:
    """Convert encoded dir name like '-Users-foo-Desktop-proj-bar' to readable name."""
    home_encoded = str(Path.home()).replace("/", "-").lstrip("-")
    name = dirname.lstrip("-")
    if name.startswith(home_encoded):
        name = name[len(home_encoded) :].lstrip("-")
    # Replace common prefixes for brevity
    for prefix in ("Desktop-proj-", "Desktop-personal-", "Desktop-", "Documents-"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    if not name:
        return "Global"
    return name


# ---------------------------------------------------------------------------
# JSONL Metadata Extraction (fast — for index building)
# ---------------------------------------------------------------------------
def extract_metadata(filepath: str) :
    """Quick scan of a JSONL file to extract session metadata."""
    title = None
    custom_title = None
    session_id = None
    first_ts = None
    last_ts = None
    user_texts = []  # (message_index, text, timestamp)
    assistant_snippets = []  # (message_index, first 300 chars of text)
    msg_index = 0
    # Insight extraction accumulators
    _tool_daily = {}     # (day, tool_name) -> count
    _file_refs = {}      # file_path -> count
    _error_list = []     # [(normalized_error, day)]
    _snippet_list = []   # [(lang, code, context, applied)]
    _code_re = re.compile(r'```(\w*)\n([\s\S]*?)```')
    _err_re = re.compile(
        r'((?:Traceback.*?:\s*)?'
        r'(?:(?:Error|Exception|TypeError|ValueError|KeyError|AttributeError|'
        r'ImportError|ModuleNotFoundError|NameError|IndexError|RuntimeError|'
        r'SyntaxError|FileNotFoundError|PermissionError|OSError|IOError|'
        r'ConnectionError|TimeoutError)'
        r'[:\s].{0,120}))',
        re.IGNORECASE
    )
    _prev_user_msg = ""

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type")

                if msg_type == "ai-title":
                    title = obj.get("aiTitle", "")
                    session_id = obj.get("sessionId", "")
                    continue

                # User-given session name (set via Claude Code). Written multiple
                # times per session; the last occurrence is the most recent name.
                if msg_type == "custom-title":
                    ct = obj.get("customTitle", "")
                    if ct:
                        custom_title = ct
                    if not session_id:
                        session_id = obj.get("sessionId", "")
                    continue

                if msg_type == "user" and not obj.get("toolUseResult"):
                    ts = obj.get("timestamp", "")
                    if not first_ts and ts:
                        first_ts = ts
                    last_ts = ts or last_ts
                    if not session_id:
                        session_id = obj.get("sessionId", "")

                    # Extract text content (filter system blocks, keep user text)
                    raw_content = obj.get("message", {}).get("content", [])
                    text = _extract_user_text(raw_content)
                    if text.strip():
                        user_texts.append(
                            {"idx": msg_index, "text": text[:2000], "ts": ts}
                        )
                    _prev_user_msg = text[:200] if text.strip() else _prev_user_msg
                    msg_index += 1

                elif msg_type == "assistant":
                    ts = obj.get("timestamp", "")
                    last_ts = ts or last_ts
                    # Extract first text snippet for correction detection
                    a_content = obj.get("message", {}).get("content", [])
                    a_texts = []
                    _code_blocks = []
                    _tool_writes = []
                    if isinstance(a_content, list):
                        for blk in a_content:
                            if isinstance(blk, dict) and blk.get("type") == "text":
                                t = blk.get("text", "").strip()
                                if t:
                                    a_texts.append(t)
                                # Insight: extract code snippets
                                for m in _code_re.finditer(blk.get("text", "")):
                                    lang = m.group(1) or ""
                                    code = m.group(2).strip()
                                    if 3 < len(code.split("\n")) <= 50 and len(code) > 30:
                                        _code_blocks.append({"lang": lang, "code": code[:1000]})
                            elif isinstance(blk, dict) and blk.get("type") == "tool_use":
                                # Insight: tool usage + file refs
                                tool_name = blk.get("name", "unknown")
                                day = (first_ts or "")[:10]
                                if day:
                                    key = (day, tool_name)
                                    _tool_daily[key] = _tool_daily.get(key, 0) + 1
                                inp = blk.get("input", {})
                                fp = inp.get("file_path") or inp.get("path") or ""
                                if fp and not fp.startswith("/tmp"):
                                    _file_refs[fp] = _file_refs.get(fp, 0) + 1
                                if tool_name in ("Edit", "Write"):
                                    w = inp.get("new_string", "") or inp.get("content", "")
                                    if w:
                                        _tool_writes.append(w[:2000])
                    elif isinstance(a_content, str) and a_content.strip():
                        a_texts.append(a_content.strip())
                    if a_texts:
                        snippet = a_texts[0][:300]
                        assistant_snippets.append({"idx": msg_index, "text": snippet, "ts": ts})
                    # Insight: determine applied status for code snippets
                    for cb in _code_blocks:
                        applied = False
                        if _tool_writes:
                            code_lines = set(cb["code"].strip().split("\n")[:10])
                            for tw in _tool_writes:
                                tw_lines = set(tw.strip().split("\n")[:20])
                                if len(code_lines & tw_lines) >= min(2, len(code_lines)):
                                    applied = True
                                    break
                        _snippet_list.append((cb["lang"], cb["code"], _prev_user_msg, applied))
                    msg_index += 1

                elif msg_type == "user" and obj.get("toolUseResult"):
                    # Insight: extract errors from tool results
                    content = obj.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for blk in content:
                            if isinstance(blk, dict) and blk.get("type") == "tool_result":
                                result_text = blk.get("content", "")
                                if isinstance(result_text, list):
                                    result_text = json.dumps(result_text)
                                if isinstance(result_text, str):
                                    day = (first_ts or "")[:10]
                                    for m in _err_re.finditer(result_text[:5000]):
                                        norm = _normalize_error(m.group(1))
                                        if len(norm) >= 10:
                                            _error_list.append((norm, day))
                    msg_index += 1

    except Exception:
        return None

    if not session_id:
        session_id = Path(filepath).stem

    # Title priority: user-given custom-title > ai-title > first user text.
    if custom_title:
        title = custom_title
    elif not title and user_texts:
        title = user_texts[0]["text"][:80]

    return {
        "id": session_id,
        "title": title or "Untitled",
        "date": first_ts or "",
        "lastDate": last_ts or "",
        "filePath": filepath,
        "fileSize": os.path.getsize(filepath),
        "userMessageCount": len(user_texts),
        "userTexts": user_texts,
        "assistantSnippets": assistant_snippets,
        "preview": user_texts[0]["text"][:200] if user_texts else "",
        # Insight data (consumed by build_index, not stored in _index cache)
        "_insight_tools": _tool_daily,
        "_insight_files": _file_refs,
        "_insight_errors": _error_list,
        "_insight_snippets": _snippet_list,
    }


def _extract_raw_text(content) -> str:
    """Extract raw text (before tag stripping) for system detection."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def _extract_text(content) -> str:
    """Extract plain text from message content (string or content blocks)."""
    if isinstance(content, str):
        return _strip_tags(content)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return _strip_tags(" ".join(parts))
    return ""


_SYSTEM_TAG_RE = re.compile(
    r"<\/?(?:system-reminder|ide_\w+|command-\w+|tool_use|tool_result|thinking|"
    r"function_calls?|function_result|session_meta|session_info|"
    r"assistant_context|user_context|tool|bash|read|edit|write|grep|search)[^>]*>",
    re.IGNORECASE,
)


def _strip_tags(text: str) -> str:
    """Remove known Claude Code system tags from text."""
    cleaned = _SYSTEM_TAG_RE.sub("", text).strip()
    # Remove leading system noise lines
    lines = cleaned.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip known system-generated lines
        if stripped.startswith(("The user opened the file", "The user selected the line")):
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def _is_system_text(text: str) -> bool:
    """Check if a single text block is purely system-generated."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith(("<ide_", "<system-reminder", "<command-")):
        return True
    return False


def _extract_user_text(content) -> str:
    """Extract user-authored text from content, skipping system-injected blocks."""
    if isinstance(content, str):
        return "" if _is_system_text(content) else _strip_tags(content)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if not _is_system_text(text):
                    parts.append(text)
        return _strip_tags(" ".join(parts))
    return ""


# ---------------------------------------------------------------------------
# Shared: truncate tool output (string or list with base64 images)
# ---------------------------------------------------------------------------
def _truncate_tool_output(output):
    """Truncate tool output, handling both string and list (Codex CUA) formats.
    Strips base64 image data and truncates text content."""
    if isinstance(output, list):
        cleaned = []
        for item in output:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type in ("input_image", "image") or "image_url" in item:
                    # Replace base64 image with placeholder
                    cleaned.append({"type": "image", "alt": "[Screenshot]"})
                elif "text" in item:
                    text = item.get("text", "")
                    if len(text) > MAX_TOOL_RESULT_LEN:
                        text = text[:MAX_TOOL_RESULT_LEN] + "…[truncated]"
                    cleaned.append({**item, "text": text})
                else:
                    cleaned.append(item)
            else:
                cleaned.append(item)
        return json.dumps(cleaned, ensure_ascii=False)
    if isinstance(output, str) and len(output) > MAX_TOOL_RESULT_LEN:
        return output[:MAX_TOOL_RESULT_LEN] + "…[truncated]"
    return output
