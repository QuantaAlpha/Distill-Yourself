import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_app_js():
    # The live frontend is modular (static/js/*.js). Concatenate the routing-
    # relevant modules so assertions cover the code actually served.
    parts = []
    for rel in ("js/app.js", "js/state.js"):
        with open(os.path.join(ROOT, "static", rel), encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)


def read_index_html():
    with open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8") as f:
        return f.read()


class TestFrontendRoutingStatic(unittest.TestCase):
    def test_main_views_are_restored_from_hash(self):
        script = read_app_js()

        self.assertIn("MAIN_VIEW_HASHES", script)
        for view in ("sessions", "insights", "ai", "twin"):
            self.assertIn(f'"{view}"', script)
        self.assertIn("restoreViewFromHash", script)

    def test_session_hash_restore_is_separate_from_main_view_hashes(self):
        script = read_app_js()

        self.assertIn("restoreSessionFromHash", script)
        self.assertIn("MAIN_VIEW_HASHES.has(hash)", script)
        self.assertIn("loadSession(hash, undefined, false)", script)

    def test_d3_loads_before_app_can_restore_ai_view(self):
        html = read_index_html()

        self.assertIn("https://d3js.org/d3.v7.min.js", html)
        self.assertNotIn('<script defer src="https://d3js.org/d3.v7.min.js"></script>', html)

    def test_keyboard_help_matches_actual_main_view_shortcuts(self):
        html = read_index_html()

        self.assertIn("<tr><td><kbd>2</kbd></td><td>AI Evolve</td></tr>", html)
        self.assertIn("<tr><td><kbd>4</kbd></td><td>Distill Yourself</td></tr>", html)
        self.assertNotIn("<tr><td><kbd>2</kbd></td><td>Sessions</td></tr>", html)
        self.assertNotIn("<tr><td><kbd>4</kbd></td><td>AI page</td></tr>", html)

    def test_poll_reruns_active_search_after_index_generation_changes(self):
        script = read_app_js()

        self.assertIn('currentView === "search"', script)
        self.assertIn("doSearch(dom.searchInput.value.trim())", script)

    def test_welcome_cards_include_three_primary_entrypoints_and_six_insights(self):
        html = read_index_html()
        script = read_app_js()

        self.assertEqual(html.count('<button class="welcome-card'), 9)
        for action in ("sessions", "ai", "twin", "heatmap", "hotspots", "errors", "profile", "health", "snippets"):
            self.assertIn(f'data-action="{action}"', html)

        self.assertIn('<span class="welcome-card-title">Sessions</span>', html)
        self.assertIn('<span class="welcome-card-title">AI Evolve</span>', html)
        self.assertIn('<span class="welcome-card-title">Distill Yourself</span>', html)
        self.assertIn('action === "sessions"', script)
        self.assertIn('action === "twin"', script)

    def test_welcome_cards_use_premium_primary_and_tool_groups(self):
        html = read_index_html()

        self.assertIn('class="welcome-primary-grid"', html)
        self.assertIn('class="welcome-tools-head"', html)
        self.assertIn('class="welcome-tool-grid"', html)
        self.assertEqual(html.count("welcome-primary-card"), 3)
        self.assertEqual(html.count("welcome-tool-card"), 6)

    def test_mobile_topbar_can_shrink_without_horizontal_overflow(self):
        css_path = os.path.join(ROOT, "static", "css", "layout.css")
        with open(css_path, encoding="utf-8") as f:
            css = f.read()

        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn(".topbar-right { display: none; }", css)
        self.assertIn(".search-wrapper { min-width: 0;", css)


if __name__ == "__main__":
    unittest.main()
