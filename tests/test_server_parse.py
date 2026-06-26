"""Regression tests for server.py pure functions: _extract_user_text,
_fuzzy_match, _parse_content, and extract_metadata."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server


class TestIsSystemText(unittest.TestCase):
    def test_system_reminder_prefix(self):
        self.assertTrue(server._is_system_text("<system-reminder>some text</system-reminder>"))

    def test_ide_prefix(self):
        self.assertTrue(server._is_system_text("<ide_file_contents>...</ide_file_contents>"))

    def test_command_prefix(self):
        self.assertTrue(server._is_system_text("<command-output>result</command-output>"))

    def test_normal_text_not_system(self):
        self.assertFalse(server._is_system_text("Hello, how can I help?"))

    def test_empty_is_system(self):
        self.assertTrue(server._is_system_text(""))
        self.assertTrue(server._is_system_text("   "))


class TestExtractUserText(unittest.TestCase):
    def test_system_string_returns_empty(self):
        result = server._extract_user_text("<system-reminder>You are helpful.</system-reminder>")
        self.assertEqual(result, "")

    def test_normal_string_returns_text(self):
        result = server._extract_user_text("What is the capital of France?")
        self.assertIn("capital", result)

    def test_mixed_list_keeps_only_user_blocks(self):
        content = [
            {"type": "text", "text": "<system-reminder>be helpful</system-reminder>"},
            {"type": "text", "text": "Please fix the bug in my code."},
        ]
        result = server._extract_user_text(content)
        self.assertIn("fix the bug", result)
        self.assertNotIn("system-reminder", result)

    def test_empty_list_returns_empty_string(self):
        result = server._extract_user_text([])
        self.assertEqual(result, "")


class TestFuzzyMatch(unittest.TestCase):
    def test_exact_substring_returns_true_and_score_one(self):
        tokens = server._tokenize_query("hello world")
        matched, score = server._fuzzy_match("say hello world today", "hello world", tokens)
        self.assertTrue(matched)
        self.assertEqual(score, 1.0)

    def test_all_tokens_match_returns_true(self):
        # "python unittest" — both tokens present in text
        tokens = server._tokenize_query("python unittest")
        text = "i use python and unittest every day"
        matched, score = server._fuzzy_match(text, "python unittest", tokens)
        self.assertTrue(matched)
        self.assertGreater(score, 0)

    def test_no_tokens_match_returns_false(self):
        tokens = server._tokenize_query("xyzzy foobar")
        matched, score = server._fuzzy_match("the quick brown fox jumps", "xyzzy foobar", tokens)
        self.assertFalse(matched)
        self.assertEqual(score, 0)

    def test_partial_match_clearly_below_threshold(self):
        # 4 tokens, only 1 matches → ratio=0.25, threshold=0.6 → False
        tokens = ["alpha", "beta", "gamma", "delta"]
        text = "only alpha is here"
        matched, score = server._fuzzy_match(text, "alpha beta gamma delta", tokens)
        self.assertFalse(matched)
        self.assertEqual(score, 0)


class TestParseContent(unittest.TestCase):
    def test_string_input_returns_single_text_block(self):
        result = server._parse_content("Hello there")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "text")
        self.assertIn("text", result[0])

    def test_list_with_text_and_tool_use(self):
        content = [
            {"type": "text", "text": "I will run a tool now."},
            {"type": "tool_use", "name": "Bash", "id": "tu-001", "input": {"command": "ls"}},
        ]
        result = server._parse_content(content)
        types = [b["type"] for b in result]
        self.assertIn("text", types)
        self.assertIn("tool_use", types)
        tool_block = next(b for b in result if b["type"] == "tool_use")
        self.assertIn("name", tool_block)
        self.assertIn("input", tool_block)

    def test_list_with_thinking_block(self):
        content = [
            {"type": "thinking", "thinking": "Let me reason step by step..."},
            {"type": "text", "text": "The answer is 42."},
        ]
        result = server._parse_content(content)
        types = [b["type"] for b in result]
        self.assertIn("thinking", types)

    def test_unknown_block_type_silently_skipped(self):
        content = [
            {"type": "unknown_future_type", "data": "something"},
            {"type": "text", "text": "This is real content."},
        ]
        result = server._parse_content(content)
        types = [b["type"] for b in result]
        self.assertNotIn("unknown_future_type", types)
        self.assertIn("text", types)


class TestExtractMetadata(unittest.TestCase):
    def _write_jsonl(self, lines):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        for obj in lines:
            f.write(json.dumps(obj) + "\n")
        f.close()
        return f.name

    def tearDown(self):
        # Clean up temp files created in individual tests
        if hasattr(self, "_tmp_path") and os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_ai_title_and_user_messages(self):
        self._tmp_path = self._write_jsonl([
            {"type": "ai-title", "aiTitle": "Test Session", "sessionId": "sess-abc"},
            {
                "type": "user",
                "timestamp": "2026-06-01T10:00:00Z",
                "sessionId": "sess-abc",
                "message": {"content": [{"type": "text", "text": "Hello world"}]},
            },
            {
                "type": "assistant",
                "timestamp": "2026-06-01T10:01:00Z",
                "message": {"content": [{"type": "text", "text": "Hi there"}]},
            },
        ])
        meta = server.extract_metadata(self._tmp_path)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["title"], "Test Session")
        self.assertEqual(meta["id"], "sess-abc")
        self.assertEqual(meta["userMessageCount"], 1)
        self.assertIn("Hello world", meta["userTexts"][0]["text"])

    def test_custom_title_overrides_ai_title(self):
        self._tmp_path = self._write_jsonl([
            {"type": "ai-title", "aiTitle": "AI Generated Title", "sessionId": "sess-xyz"},
            {
                "type": "user",
                "timestamp": "2026-06-02T09:00:00Z",
                "sessionId": "sess-xyz",
                "message": {"content": [{"type": "text", "text": "Fix the bug please"}]},
            },
            {"type": "custom-title", "customTitle": "My Custom Name", "sessionId": "sess-xyz"},
        ])
        meta = server.extract_metadata(self._tmp_path)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["title"], "My Custom Name")

    def test_malformed_json_lines_skipped_gracefully(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        f.write('{"type": "ai-title", "aiTitle": "Good Title", "sessionId": "sess-err"}\n')
        f.write("this is not json at all\n")
        f.write("{broken json\n")
        f.write('{"type": "user", "timestamp": "2026-06-03T08:00:00Z", "sessionId": "sess-err", '
                '"message": {"content": [{"type": "text", "text": "Hello"}]}}\n')
        f.close()
        self._tmp_path = f.name

        meta = server.extract_metadata(self._tmp_path)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["title"], "Good Title")
        self.assertEqual(meta["userMessageCount"], 1)


if __name__ == "__main__":
    unittest.main()
