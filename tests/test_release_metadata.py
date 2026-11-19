import unittest
from datetime import datetime, timezone

import radar


class ReleaseMetadataTests(unittest.TestCase):
    def test_latest_release_includes_prereleases_and_skips_drafts(self):
        releases = [
            {
                "tag_name": "v2.0.0-rc.1",
                "published_at": "2026-11-18T12:00:00Z",
                "draft": False,
                "prerelease": True,
            },
            {
                "tag_name": "v1.9.0",
                "published_at": "2026-11-17T12:00:00Z",
                "draft": False,
                "prerelease": False,
            },
            {
                "tag_name": "v3.0.0-draft",
                "published_at": None,
                "created_at": "2026-11-19T12:00:00Z",
                "draft": True,
                "prerelease": True,
            },
        ]
        result = radar.latest_release(
            {"full_name": "example/repo"},
            api=lambda endpoint: releases,
        )
        self.assertEqual(result, {
            "release_status": "available",
            "latest_release_tag": "v2.0.0-rc.1",
            "latest_release_published_at": "2026-11-18T12:00:00Z",
        })

    def test_latest_release_reports_none_for_empty_release_list(self):
        result = radar.latest_release(
            {"full_name": "example/repo"},
            api=lambda endpoint: [],
        )
        self.assertEqual(result["release_status"], "none")

    def test_latest_release_reports_unknown_when_api_fails(self):
        def fail(_endpoint):
            raise RuntimeError("GitHub request failed: HTTP Error 403: rate limit")

        result = radar.latest_release({"full_name": "example/repo"}, api=fail)
        self.assertEqual(result["release_status"], "unknown")

    def test_latest_release_paginates_to_find_newer_published_release(self):
        first_page = [
            {
                "tag_name": f"v0.{index}",
                "published_at": "2026-10-01T12:00:00Z",
                "draft": False,
            }
            for index in range(radar.RELEASES_PER_PAGE)
        ]
        second_page = [{
            "tag_name": "late-published-release",
            "published_at": "2026-11-18T12:00:00Z",
            "draft": False,
        }]
        calls = []

        def api(endpoint):
            calls.append(endpoint)
            if endpoint.endswith("page=1"):
                return first_page
            if endpoint.endswith("page=2"):
                return second_page
            self.fail(f"Unexpected release page request: {endpoint}")

        result = radar.latest_release({"full_name": "example/repo"}, api=api)
        self.assertEqual(result["latest_release_tag"], "late-published-release")
        self.assertEqual(result["release_status"], "available")
        self.assertEqual(len(calls), 2)

    def test_latest_release_fails_closed_when_later_page_cannot_be_read(self):
        first_page = [
            {"tag_name": f"v0.{index}", "published_at": "2026-10-01T12:00:00Z", "draft": False}
            for index in range(radar.RELEASES_PER_PAGE)
        ]

        def api(endpoint):
            if "page=1" in endpoint:
                return first_page
            raise RuntimeError("GitHub request failed: HTTP Error 403: rate limit")

        result = radar.latest_release({"full_name": "example/repo"}, api=api)
        self.assertEqual(result["release_status"], "unknown")
        self.assertIsNone(result["latest_release_tag"])

    def test_latest_release_reports_unknown_when_page_limit_is_reached(self):
        calls = []

        def api(endpoint):
            calls.append(endpoint)
            return [
                {"tag_name": f"v{len(calls)}.{index}", "published_at": "2026-10-01T12:00:00Z", "draft": False}
                for index in range(radar.RELEASES_PER_PAGE)
            ]

        result = radar.latest_release({"full_name": "example/repo"}, api=api)
        self.assertEqual(result["release_status"], "unknown")
        self.assertEqual(len(calls), radar.MAX_RELEASE_PAGES)

    def test_markdown_escapes_pipe_in_release_tag(self):
        repo = {
            "full_name": "example/repo",
            "topics_found": ["mcp"],
            "pushed_at": "2026-11-18T10:00:00Z",
            "open_issues_count": 1,
            "release_status": "available",
            "latest_release_tag": "v1.0|beta",
            "latest_release_published_at": "2026-11-18T10:00:00Z",
            "commits_24h": 1,
            "commits_7d": 2,
            "commits_30d": 3,
            "stars_gained_24h": None,
            "stars_gained_7d": None,
            "stars_gained_30d": None,
            "stargazers_count": 5,
            "license": {"spdx_id": "MIT"},
        }
        report = radar.markdown(
            [repo],
            datetime(2026, 11, 19, tzinfo=timezone.utc),
            5,
        )
        self.assertIn("v1.0\\|beta", report)
        self.assertNotIn("v1.0|beta", report)


if __name__ == "__main__":
    unittest.main()
