"""HTTP handler utility functions.

Standalone versions of the helper methods originally on ChatViewerHandler.
Each takes ``handler`` (a BaseHTTPRequestHandler instance) as the first arg.
"""

import json
from pathlib import Path


def _json_response(handler, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", len(body))
    # No CORS — local-only server, same-origin requests only
    handler.end_headers()
    handler.wfile.write(body)


def _serve_file(handler, filepath: Path):
    ext = filepath.suffix.lower()
    mime = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }.get(ext, "application/octet-stream")

    data = filepath.read_bytes()
    handler.send_response(200)
    ct = (
        f"{mime}; charset=utf-8"
        if mime.startswith("text/")
        or mime.endswith("javascript")
        or mime.endswith("json")
        else mime
    )
    handler.send_header("Content-Type", ct)
    handler.send_header("Content-Length", len(data))
    # Local dev server: always revalidate so edits to html/js/css are picked
    # up immediately instead of being served from the browser's stale cache.
    handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    handler.end_headers()
    handler.wfile.write(data)


def _error(handler, code: int, msg: str):
    body = json.dumps({"error": msg}).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)


def _sse_event(handler, data: dict):
    """Write a single SSE event and flush."""
    payload = json.dumps(data, ensure_ascii=False)
    handler.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
    handler.wfile.flush()


def _start_sse(handler):
    """Send SSE response headers."""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()


MAX_POST_BODY = 10 * 1024 * 1024  # 10 MB


def _read_post_body(handler):
    try:
        content_len = int(handler.headers.get("Content-Length", 0))
    except (ValueError, TypeError):
        _error(handler, 400, "Invalid Content-Length")
        return None
    if content_len < 0 or content_len > MAX_POST_BODY:
        _error(
            handler,
            413,
            f"Request body too large (max {MAX_POST_BODY // 1024 // 1024}MB)",
        )
        return None
    return handler.rfile.read(content_len)


def log_message(handler, format, *args):
    """Suppress default request logging for cleaner output."""
    pass
