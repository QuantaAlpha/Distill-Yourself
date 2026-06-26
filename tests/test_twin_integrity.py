import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import analyze
import db


class TwinIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cache_dir = db.CACHE_DIR
        self.old_db_path = db.DB_PATH
        self.old_conn = getattr(db._local, "conn", None)
        if self.old_conn is not None:
            self.old_conn.close()
            db._local.conn = None
        db.CACHE_DIR = Path(self.tmp.name)
        db.DB_PATH = db.CACHE_DIR / "sessions.db"
        db.init_db()

    def tearDown(self):
        conn = getattr(db._local, "conn", None)
        if conn is not None:
            conn.close()
            db._local.conn = None
        db.CACHE_DIR = self.old_cache_dir
        db.DB_PATH = self.old_db_path
        if self.old_conn is not None:
            db._local.conn = None
        self.tmp.cleanup()

    def test_duplicate_evidence_event_index_is_rejected_without_replacing_existing_row(self):
        db.cm_upsert("evidence_events", "ev_original", {
            "session_id": "s1",
            "event_index": 1,
            "lesson": "original lesson",
        })

        with self.assertRaises(ValueError):
            db.cm_upsert("evidence_events", "ev_duplicate", {
                "session_id": "s1",
                "event_index": 1,
                "lesson": "duplicate lesson",
            })

        self.assertEqual(db.cm_get("evidence_events", "ev_original")["lesson"], "original lesson")
        self.assertIsNone(db.cm_get("evidence_events", "ev_duplicate"))

    def test_twin_batch_rejects_invalid_link_and_rolls_back_prior_add(self):
        payload = {
            "operations": [
                {
                    "resource": "events",
                    "action": "add",
                    "data": {
                        "session_id": "s1",
                        "event_index": 1,
                        "lesson": "should roll back",
                    },
                },
                {
                    "action": "link",
                    "from": "ev_missing",
                    "to": "jc_missing",
                },
            ]
        }

        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                analyze.cmd_twin_batch(None)
        finally:
            sys.stdin = old_stdin

        result = json.loads(out.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["results"][-1]["index"], 1)
        self.assertTrue(result["results"][-1]["rolled_back"])
        self.assertEqual(db.cm_count("evidence_events"), 0)
        self.assertEqual(db.cm_count("judgment_cards"), 0)

    def test_twin_candidates_validates_without_writing(self):
        payload = {
            "candidates": [
                {
                    "resource": "events",
                    "data": {
                        "session_id": "s1",
                        "event_index": 1,
                        "lesson": "prefer scoped changes",
                        "signal_type": "correction",
                        "domain": "coding/scope",
                    },
                }
            ]
        }

        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                analyze.cmd_twin_candidates(None)
        finally:
            sys.stdin = old_stdin

        result = json.loads(out.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual(db.cm_count("evidence_events"), 0)

    def test_twin_candidates_rejects_missing_required_fields(self):
        payload = {"candidates": [{"resource": "events", "data": {"session_id": "s1"}}]}

        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        out = io.StringIO()
        try:
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(out):
                    analyze.cmd_twin_candidates(None)
        finally:
            sys.stdin = old_stdin

        result = json.loads(out.getvalue())
        self.assertFalse(result["ok"])
        self.assertIn("lesson", result["results"][0]["missing"])


if __name__ == "__main__":
    unittest.main()
