"""Tests for the AI engine abstraction layer (chatview/ai_engine.py).

Covers Group C — 双引擎适配:
  1. Codex 健康探针解析抽成可测试的纯函数 _analyze_codex_probe。
  2. 显式 codex 不健康时不应傻等 30-60s 内部重试，而是给出可切换 claude 的 error。
  3. 统一 codex 工具事件解析粒度（file_change / web_search / mcp_tool_call / reasoning）。
"""

import json
import unittest

from chatview import ai_engine


class TestAnalyzeCodexProbe(unittest.TestCase):
    def test_detects_521_error_event(self):
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started"}),
                json.dumps(
                    {"type": "error", "message": "unexpected status 521 from server"}
                ),
            ]
        )
        ok, msg = ai_engine._analyze_codex_probe(stdout, 0)
        self.assertFalse(ok)
        self.assertIn("521", msg)

    def test_detects_turn_failed_event(self):
        stdout = json.dumps(
            {"type": "turn.failed", "error": {"message": "usage limit reached"}}
        )
        ok, msg = ai_engine._analyze_codex_probe(stdout, 0)
        self.assertFalse(ok)
        self.assertIn("usage limit", msg)

    def test_detects_nonzero_returncode(self):
        ok, msg = ai_engine._analyze_codex_probe("", 1)
        self.assertFalse(ok)

    def test_healthy_output_returns_ok(self):
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started"}),
                json.dumps(
                    {"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}
                ),
                json.dumps({"type": "turn.completed", "usage": {}}),
            ]
        )
        ok, msg = ai_engine._analyze_codex_probe(stdout, 0)
        self.assertTrue(ok)


class TestExplicitCodexUnhealthy(unittest.TestCase):
    def test_explicit_codex_unhealthy_yields_switch_error_without_running(self):
        """显式 codex 探针失败时，应直接给出可切换 claude 的 error，
        且不进入 _run_engine_stream_inner（避免 30-60s 卡顿）。"""
        inner_called = []

        class _FakeProbe:
            returncode = 0
            stdout = json.dumps(
                {"type": "error", "message": "unexpected status 521"}
            )
            stderr = ""

        orig_run = ai_engine.subprocess.run
        orig_inner = ai_engine._run_engine_stream_inner

        def _fake_run(*a, **k):
            return _FakeProbe()

        def _fake_inner(engine, *a, **k):
            inner_called.append(engine)
            yield {"type": "done", "content": ""}

        ai_engine.subprocess.run = _fake_run
        ai_engine._run_engine_stream_inner = _fake_inner
        try:
            events = list(
                ai_engine._run_ai_engine_stream_impl(
                    "hi", allow_write=False, timeout=60, engine_override="codex"
                )
            )
        finally:
            ai_engine.subprocess.run = orig_run
            ai_engine._run_engine_stream_inner = orig_inner

        # codex 未被实际运行
        self.assertNotIn("codex", inner_called)
        # 给出 error 且建议切换到 claude
        errs = [e for e in events if e.get("type") == "error"]
        self.assertTrue(errs, f"expected an error event, got {events}")
        self.assertEqual(errs[0].get("suggest_engine"), "claude")
        self.assertIn("521", errs[0].get("message", ""))

    def test_auto_codex_unhealthy_falls_back_to_claude(self):
        """auto 模式下 codex 不健康应回退 claude（保持既有行为）。"""
        inner_called = []

        class _FakeProbe:
            returncode = 0
            stdout = json.dumps({"type": "error", "message": "status 521"})
            stderr = ""

        orig_run = ai_engine.subprocess.run
        orig_inner = ai_engine._run_engine_stream_inner
        orig_detect = ai_engine._detect_ai_engine

        ai_engine.subprocess.run = lambda *a, **k: _FakeProbe()
        ai_engine._detect_ai_engine = lambda: "codex"

        def _fake_inner(engine, *a, **k):
            inner_called.append(engine)
            yield {"type": "done", "content": ""}

        ai_engine._run_engine_stream_inner = _fake_inner
        try:
            list(
                ai_engine._run_ai_engine_stream_impl(
                    "hi", allow_write=False, timeout=60, engine_override="auto"
                )
            )
        finally:
            ai_engine.subprocess.run = orig_run
            ai_engine._run_engine_stream_inner = orig_inner
            ai_engine._detect_ai_engine = orig_detect

        self.assertIn("claude", inner_called)


class TestCodexToolEventParsing(unittest.TestCase):
    def test_command_execution_started(self):
        line = json.dumps(
            {"type": "item.started", "item": {"type": "command_execution", "command": "ls"}}
        )
        evt = ai_engine._parse_stream_event("codex", line)
        self.assertEqual(evt["type"], "tool")
        self.assertEqual(evt["name"], "Bash")

    def test_file_change_completed(self):
        line = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "file_change",
                    "changes": [{"path": "foo.py", "kind": "edit"}],
                },
            }
        )
        evt = ai_engine._parse_stream_event("codex", line)
        self.assertEqual(evt["type"], "tool")
        self.assertIn(evt["name"], ("Edit", "Write"))
        self.assertIn("foo.py", evt["detail"])

    def test_web_search_event(self):
        line = json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "web_search", "query": "python asyncio"},
            }
        )
        evt = ai_engine._parse_stream_event("codex", line)
        self.assertEqual(evt["type"], "tool")
        self.assertEqual(evt["name"], "WebSearch")
        self.assertIn("asyncio", evt["detail"])

    def test_mcp_tool_call_event(self):
        line = json.dumps(
            {
                "type": "item.started",
                "item": {"type": "mcp_tool_call", "server": "fs", "tool": "read"},
            }
        )
        evt = ai_engine._parse_stream_event("codex", line)
        self.assertEqual(evt["type"], "tool")
        self.assertIn("read", evt["detail"])

    def test_reasoning_emitted_as_text(self):
        line = json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "reasoning", "text": "thinking about it"},
            }
        )
        evt = ai_engine._parse_stream_event("codex", line)
        self.assertEqual(evt["type"], "text")
        self.assertIn("thinking", evt["content"])


if __name__ == "__main__":
    unittest.main()
