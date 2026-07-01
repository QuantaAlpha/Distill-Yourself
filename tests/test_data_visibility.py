"""Regression tests: data created under one scope must remain visible
when defaults or query parameters change.

These tests guard against the class of bug where adding a new filter
dimension (engine, run_id, etc.) makes legacy data invisible.

Adapted from main branch for integrate's DB API:
- evolve_get(tab, src, date, proj, engine)  — 5 args, engine-exact
- evolve_upsert(tab, src, date, proj, engine, data)  — 6 args, engine before data
- evolve_get_shared()  — cross-engine fallback (replaces main's 4-arg evolve_get)
- No _migrate_evolve_cache_drop_engine_pk (integrate schema already uses 5-col PK)
- No twin_run_create/twin_run_update (uses checkpoint system)
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chatview.db as db


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        from chatview.db import core as _dbcore
        self._orig_db_path = _dbcore.DB_PATH
        self._orig_cache_dir = _dbcore.CACHE_DIR
        self._tmpdir = tempfile.mkdtemp()
        _dbcore.CACHE_DIR = Path(self._tmpdir)
        _dbcore.DB_PATH = Path(self._tmpdir) / "sessions.db"
        _dbcore._local = threading.local()
        db.init_db()

    def tearDown(self):
        from chatview.db import core as _dbcore
        _dbcore.DB_PATH = self._orig_db_path
        _dbcore.CACHE_DIR = self._orig_cache_dir
        _dbcore._local = threading.local()
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class TestEvolveVisibility(BaseTestCase):
    """Evolve cache data must be visible regardless of engine used.

    Integrate allows one row per (tab, source, date_range, project, engine).
    Cross-engine reads go through evolve_get_shared() which falls back to
    the newest row for the scope regardless of engine.
    """

    def test_data_written_with_claude_visible_via_shared(self):
        """Data written with engine=claude must be readable via evolve_get_shared."""
        db.evolve_upsert("rules", "all", "7d", "", "claude",
                         json.dumps({"rules": [{"id": "r1"}]}))
        row = db.evolve_get_shared("rules", "all", "7d", "", engine="auto")
        self.assertIsNotNone(row)
        self.assertEqual(row["data"]["rules"][0]["id"], "r1")

    def test_data_written_with_auto_visible_via_exact(self):
        """Data written with engine=auto is readable via exact evolve_get."""
        db.evolve_upsert("profile", "all", "7d", "", "auto",
                         json.dumps({"summary": "test"}))
        row = db.evolve_get("profile", "all", "7d", "", "auto")
        self.assertIsNotNone(row)
        self.assertEqual(row["data"]["summary"], "test")

    def test_different_engines_same_scope_coexist(self):
        """Integrate allows per-engine rows; evolve_get_shared returns newest."""
        db.evolve_upsert("memory", "all", "7d", "", "claude",
                         json.dumps({"items": ["a"]}))
        db.evolve_upsert("memory", "all", "7d", "", "codex",
                         json.dumps({"items": ["b"]}))
        # Exact engine reads still work
        row_claude = db.evolve_get("memory", "all", "7d", "", "claude")
        row_codex = db.evolve_get("memory", "all", "7d", "", "codex")
        self.assertIsNotNone(row_claude)
        self.assertIsNotNone(row_codex)
        # evolve_get_shared prefers exact match, else newest
        row_shared = db.evolve_get_shared("memory", "all", "7d", "", engine="codex")
        self.assertIsNotNone(row_shared)
        self.assertEqual(row_shared["data"]["items"], ["b"])

    def test_different_scopes_are_independent(self):
        """Different (source, date, project) scopes are separate entries."""
        db.evolve_upsert("rules", "all", "7d", "", "auto",
                         json.dumps({"rules": [{"id": "week"}]}))
        db.evolve_upsert("rules", "all", "30d", "", "auto",
                         json.dumps({"rules": [{"id": "month"}]}))
        row_7d = db.evolve_get("rules", "all", "7d", "", "auto")
        row_30d = db.evolve_get("rules", "all", "30d", "", "auto")
        self.assertEqual(row_7d["data"]["rules"][0]["id"], "week")
        self.assertEqual(row_30d["data"]["rules"][0]["id"], "month")

    def test_evolve_latest_returns_newest_across_scopes(self):
        """evolve_latest ignores scope and returns newest for a tab."""
        db.evolve_upsert("signals", "all", "7d", "", "claude",
                         json.dumps({"old": True}))
        db.evolve_upsert("signals", "codex", "30d", "proj", "codex",
                         json.dumps({"new": True}))
        row = db.evolve_latest("signals")
        self.assertIsNotNone(row)
        self.assertTrue(row["data"].get("new"))

    def test_evolve_get_shared_exact_engine_preferred(self):
        """evolve_get_shared returns exact engine match when available."""
        db.evolve_upsert("profile", "all", "7d", "", "claude",
                         json.dumps({"source": "claude"}))
        db.evolve_upsert("profile", "all", "7d", "", "codex",
                         json.dumps({"source": "codex"}))
        row = db.evolve_get_shared("profile", "all", "7d", "", engine="claude")
        self.assertIsNotNone(row)
        self.assertEqual(row["data"]["source"], "claude")

    def test_evolve_get_shared_fallback_when_no_exact_match(self):
        """evolve_get_shared falls back to newest row when engine doesn't match."""
        db.evolve_upsert("profile", "all", "7d", "", "claude",
                         json.dumps({"source": "claude"}))
        # Request engine=auto but only claude row exists
        row = db.evolve_get_shared("profile", "all", "7d", "", engine="auto")
        self.assertIsNotNone(row)
        self.assertEqual(row["data"]["source"], "claude")


class TwinVisibilityWithCheckpoints(BaseTestCase):
    """Twin data with no run_id must remain visible.

    Integrate uses checkpoint-based runs (save_checkpoint) rather than
    twin_run_create/twin_run_update. These tests use the checkpoint API.
    """

    def test_legacy_data_without_run_id_visible_in_overview(self):
        """Pre-checkpoint data (run_id=NULL) should be countable."""
        conn = db.get_conn()
        conn.execute("""
            INSERT INTO judgment_cards (id, applies_when, judgment, agent_action,
                                       tags, confidence, status, evidence_count,
                                       created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("jc_test", "test condition", "test judgment", "test action",
              '["test"]', 0.8, "confirmed", 1,
              "2026-06-01T00:00:00", "2026-06-01T00:00:00"))
        conn.commit()
        # Query without run_id filter should find it
        count = db.cm_count("judgment_cards")
        self.assertGreaterEqual(count, 1)
        # Query with non-matching run_id should NOT find it
        count_scoped = db.cm_count("judgment_cards", where="run_id=?", params=("nonexistent",))
        self.assertEqual(count_scoped, 0)

    def test_cancelled_run_with_no_products_does_not_hide_legacy(self):
        """A checkpoint-run with 0 products should not scope the UI to emptiness."""
        conn = db.get_conn()
        # Insert legacy card
        conn.execute("""
            INSERT INTO judgment_cards (id, applies_when, judgment, agent_action,
                                       tags, confidence, status, evidence_count,
                                       created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("jc_legacy", "cond", "judg", "act", '[]', 0.5, "confirmed", 0,
              "2026-06-01T00:00:00", "2026-06-01T00:00:00"))
        conn.commit()
        # Simulate a run that produced 0 products
        run_id = "test_run_cancelled"
        db.save_checkpoint(run_id, 1, "failed")
        # The run has 0 products
        for tbl in ("evidence_events", "judgment_cards", "cognitive_traits"):
            count = conn.execute(
                f"SELECT COUNT(*) FROM {tbl} WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            self.assertEqual(count, 0, f"{tbl} should have 0 products for this run")
        # Global count should still find the legacy card
        total = db.cm_count("judgment_cards")
        self.assertGreaterEqual(total, 1)


if __name__ == "__main__":
    unittest.main()
