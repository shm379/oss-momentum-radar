from datetime import datetime, timedelta, timezone
import unittest
import radar

class Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 4, tzinfo=timezone.utc)

    def test_duplicate_results_merge_topic_names(self):
        def api(_):
            return {"items": [{"full_name": "x/y", "archived": False, "fork": False}]}
        result = radar.discover(["rust", "agent"], self.now, api=api)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["topics_found"], ["rust", "agent"])

    def test_small_active_repo_outscores_big_stale_repo(self):
        self.assertGreater(radar.rank({"commits_7d": 8, "stargazers_count": 10}),
                           radar.rank({"commits_7d": 0, "stargazers_count": 3000}))

    def test_star_growth_requires_history(self):
        old = (self.now - timedelta(days=8)).isoformat()
        new = self.now.isoformat()
        self.assertEqual(radar.star_change([{"at": old, "stars": 12}, {"at": new, "stars": 15}], self.now), 3)
        self.assertIsNone(radar.star_change([{"at": new, "stars": 15}], self.now))

    def test_record_prunes_expired_history_for_undiscovered_repos(self):
        old = (self.now - timedelta(days=10)).isoformat()
        recent = (self.now - timedelta(days=2)).isoformat()
        history = {
            "stale/repo": [{"at": old, "stars": 1}],
            "recent/repo": [{"at": recent, "stars": 2}],
        }
        result = radar.record(history, [], self.now)
        self.assertNotIn("stale/repo", result)
        self.assertEqual(result["recent/repo"], [{"at": recent, "stars": 2}])

    def test_record_keeps_recent_history_and_appends_current_sample(self):
        recent = (self.now - timedelta(days=8)).isoformat()
        history = {"example/repo": [{"at": recent, "stars": 3}]}
        result = radar.record(history, [{"full_name": "example/repo", "stargazers_count": 5}], self.now)
        self.assertEqual([row["stars"] for row in result["example/repo"]], [3, 5])

    def test_record_discards_invalid_and_future_dated_history(self):
        future = (self.now + timedelta(days=1)).isoformat()
        history = {"bad/repo": [{"stars": 3}, {"at": future, "stars": 4}]}
        self.assertEqual(radar.record(history, [], self.now), {})

    def test_commit_counts_are_bounded_when_first_page_is_full(self):
        for count, expected in ((0, 0), (99, 99), (100, "100+")):
            def api(_endpoint):
                return [{} for _ in range(count)]
            repo = {"full_name": "example/repo"}
            self.assertEqual(radar.count_commits_7d(repo, self.now, api=api), expected)

    def test_bounded_commit_count_renders_and_ranks(self):
        repo = {"full_name": "example/repo", "topics_found": ["mcp"],
                "commits_7d": "100+", "stars_gained_7d": None,
                "stargazers_count": 5, "license": None}
        self.assertIn("100+", radar.markdown([repo], self.now, 1))
        self.assertGreater(radar.rank(repo), 500)

    def test_report_is_honest_about_missing_growth(self):
        repo = {"full_name": "x/y", "topics_found": ["mcp"], "commits_7d": 2,
                "stars_gained_7d": None, "stargazers_count": 5, "license": None}
        result = radar.markdown([repo], self.now, 5)
        self.assertIn("not yet measurable", result)
        self.assertIn("unverified", result)

if __name__ == "__main__":
    unittest.main()
