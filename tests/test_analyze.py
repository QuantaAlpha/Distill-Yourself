import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analyze


class TestValidateEvolveMechanism(unittest.TestCase):
    """Tests for the validation mechanism itself."""

    def test_unknown_tab_returns_error(self):
        ok, errors = analyze._validate_evolve_data("nonexistent", {})
        self.assertFalse(ok)
        self.assertEqual(len(errors), 1)
        self.assertIn("Unknown tab", errors[0])
        self.assertIn("nonexistent", errors[0])

    def test_non_dict_data_returns_error(self):
        ok, errors = analyze._validate_evolve_data("rules", ["not", "a", "dict"])
        self.assertFalse(ok)
        self.assertEqual(len(errors), 1)
        self.assertIn("JSON object", errors[0])

    def test_empty_dict_autofills_and_passes(self):
        # _validate_evolve_data auto-fills missing top-level fields with empty defaults
        data = {}
        ok, errors = analyze._validate_evolve_data("rules", data)
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        # Side effect: auto-filled key should now exist
        self.assertIn("rules", data)


class TestValidateEvolveProfile(unittest.TestCase):
    """Tests for the 'profile' tab — the most complex schema."""

    def _make_valid_profile(self):
        return {
            "categories": [{"name": "Test", "items": [{"text": "item1"}]}],
            "radar": {"dimensions": [{"name": "skill", "score": 0.5}]},
        }

    def test_valid_minimal_profile_passes(self):
        ok, errors = analyze._validate_evolve_data("profile", self._make_valid_profile())
        self.assertTrue(ok, f"Expected valid, got errors: {errors}")
        self.assertEqual(errors, [])

    def test_category_missing_required_name_fails(self):
        data = {
            "categories": [{}],          # missing "name"
            "radar": {"dimensions": []},
        }
        ok, errors = analyze._validate_evolve_data("profile", data)
        self.assertFalse(ok)
        combined = " ".join(errors)
        self.assertIn("required", combined)

    def test_radar_score_out_of_range_fails(self):
        data = {
            "categories": [],
            "radar": {"dimensions": [{"name": "x", "score": 1.5}]},
        }
        ok, errors = analyze._validate_evolve_data("profile", data)
        self.assertFalse(ok)
        combined = " ".join(errors)
        self.assertIn("0.0-1.0", combined)


class TestValidateEvolveRules(unittest.TestCase):
    """Tests for the 'rules' tab — simplest schema."""

    def test_valid_rules_passes(self):
        data = {"rules": [{"id": "r1", "rule": "Do X"}]}
        ok, errors = analyze._validate_evolve_data("rules", data)
        self.assertTrue(ok, f"Expected valid, got errors: {errors}")
        self.assertEqual(errors, [])

    def test_rule_missing_required_id_fails(self):
        data = {"rules": [{"rule": "Do X"}]}   # missing "id"
        ok, errors = analyze._validate_evolve_data("rules", data)
        self.assertFalse(ok)
        combined = " ".join(errors)
        self.assertIn("required field missing", combined)


if __name__ == "__main__":
    unittest.main()
