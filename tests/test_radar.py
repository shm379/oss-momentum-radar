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

    def test_star_growth_uses_chronological_samples_even_if_history_is_unsorted(self):
        old = (self.now - timedelta(days=8)).isoformat()
        new = self.now.isoformat()
        self.assertEqual(radar.star_change([{"at": new, "stars": 15},
                                            {"at": old, "stars": 12}], self.now), 3)

    def test_star_growth_ignores_future_and_malformed_observations(self):
        old = (self.now - timedelta(days=8)).isoformat()
        new = self.now.isoformat()
        future = (self.now + timedelta(days=1)).isoformat()
        history = [{"at": old, "stars": 12}, {"at": new, "stars": 15},
                   {"at": future, "stars": 999}, {"at": "bad", "stars": 5},
                   {"at": new, "stars": "invalid"}]
        self.assertEqual(radar.star_change(history, self.now), 3)

    def test_record_prunes_expired_history_for_undiscovered_repos(self):
        old = (self.now - timedelta(days=32)).isoformat()
        recent = (self.now - timedelta(days=30)).isoformat()
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

    def test_record_rejects_naive_timestamps_without_dropping_valid_samples(self):
        recent = (self.now - timedelta(days=2)).isoformat()
        history = {"mixed/repo": [
            {"at": "2026-11-03T00:00:00", "stars": 1},
            {"at": recent, "stars": 2},
        ]}
        result = radar.record(history, [], self.now)
        self.assertEqual(result["mixed/repo"], [{"at": recent, "stars": 2}])

    def test_record_ignores_malformed_history_containers_and_entries(self):
        history = {"null/repo": None, "text/repo": "invalid",
                   "mixed/repo": [None, 42, {"at": 123},
                                  {"at": self.now.isoformat(), "stars": 3}]}
        result = radar.record(history, [], self.now)
        self.assertNotIn("null/repo", result)
        self.assertNotIn("text/repo", result)
        self.assertEqual(len(result["mixed/repo"]), 1)
        self.assertEqual(result["mixed/repo"][0]["stars"], 3)

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
        # 100+ is a lower bound, not 100 exact commits or quality.
        self.assertAlmostEqual(radar.rank(repo), radar.rank({**repo, "commits_7d": 30}))

    def test_commit_burst_cannot_swamp_other_signals(self):
        burst = {"commits_7d": "100+", "stargazers_count": 0}
        balanced = {"commits_7d": 30, "stargazers_count": 20, "stars_gained_7d": 2}
        self.assertGreater(radar.rank(balanced), radar.rank(burst))

    def test_negative_star_growth_is_not_a_bonus_or_penalty(self):
        base = {"commits_7d": 8, "stargazers_count": 10}
        self.assertEqual(radar.rank(base), radar.rank({**base, "stars_gained_7d": -3}))

    def test_star_growth_30d_waits_for_a_full_baseline(self):
        old = (self.now - timedelta(days=31)).isoformat()
        new = self.now.isoformat()
        self.assertEqual(radar.star_change([{"at": old, "stars": 20}, {"at": new, "stars": 26}],
                                           self.now, days=30), 6)
        short_history = [{"at": (self.now - timedelta(days=8)).isoformat(), "stars": 20},
                         {"at": new, "stars": 26}]
        self.assertIsNone(radar.star_change(short_history, self.now, days=30))

    def test_commit_windows_count_24h_7d_and_30d_from_one_page(self):
        def commit(hours_ago):
            when = self.now - timedelta(hours=hours_ago)
            return {"commit": {"author": {"date": when.isoformat()}}}
        rows = [commit(1), commit(48), commit(24 * 20), commit(24 * 40)]
        calls = []
        def api(endpoint):
            calls.append(endpoint)
            return rows
        result = radar.count_commit_windows({"full_name": "example/repo"}, self.now, api=api)
        self.assertEqual(result, {"commits_24h": 1, "commits_7d": 2, "commits_30d": 3})
        self.assertEqual(len(calls), 1)
        self.assertIn("per_page=100", calls[0])

    def test_commit_windows_prefer_committer_date_for_activity(self):
        author_date = (self.now - timedelta(days=40)).isoformat()
        committer_date = (self.now - timedelta(hours=1)).isoformat()
        row = {"commit": {"author": {"date": author_date},
                          "committer": {"date": committer_date}}}
        result = radar.count_commit_windows({"full_name": "example/repo"}, self.now, api=lambda _: [row])
        self.assertEqual(result, {"commits_24h": 1, "commits_7d": 1, "commits_30d": 1})

    def test_commit_window_full_page_marks_30d_as_lower_bound(self):
        def api(_endpoint):
            rows = []
            for index in range(100):
                when = self.now - timedelta(days=10, minutes=index)
                rows.append({"commit": {"author": {"date": when.isoformat()}}})
            return rows
        result = radar.count_commit_windows({"full_name": "example/repo"}, self.now, api=api)
        self.assertEqual(result["commits_24h"], 0)
        self.assertEqual(result["commits_7d"], 0)
        self.assertEqual(result["commits_30d"], "100+")

    def test_report_is_honest_about_missing_growth(self):
        repo = {"full_name": "x/y", "topics_found": ["mcp"], "commits_24h": 1,
                "commits_7d": 2, "commits_30d": 3, "stars_gained_24h": None,
                "stars_gained_7d": None, "stars_gained_30d": None,
                "stargazers_count": 5, "license": None}
        result = radar.markdown([repo], self.now, 5)
        self.assertIn("not yet measurable", result)
        self.assertIn("unverified", result)
        self.assertIn("Commits (24h)", result)
        self.assertIn("Commits (30d)", result)
        self.assertIn("Stars gained (30d)", result)

if __name__ == "__main__":
    unittest.main()
