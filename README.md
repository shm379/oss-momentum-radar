# OSS Momentum Radar

**Discover promising open-source projects that keep shipping—even before they trend.**

A lightweight, zero-dependency Python tool from the NabuXAI open-source ecosystem.

## Free core, forever

MIT-licensed. No subscription, paid model, credit card, or third-party service required for the core tool. It uses Python's standard library and GitHub's public API. Anonymous requests have strict rate limits; an *optional* token raises that limit. The included GitHub Actions workflow receives GitHub's built-in short-lived token automatically—no personal token setup required.

## What it measures

- **Discovery coverage:** default searches include MCP servers, Rust automation, self-hosted agents, open-source CRM, agent coordination, and self-hosted PaaS.
- **Recent activity:** GitHub repositories with pushes in the past 14 days.
- **Multi-window maintenance momentum:** public commits in the last 24 hours, 7 days, and 30 days, sampled from one 30-day API page per repository.
- **Bounded counts:** 100+ is an explicit lower bound when the GitHub API page is full; it is never presented as an exact count.
- **Burst-resistant ranking:** the 7-day commit contribution has diminishing returns and is capped after 30 commits; raw activity is not proof of sustained maintenance.
- **Real star growth:** 24-hour and 7-day deltas require a baseline within 12 hours of the window boundary; 30-day deltas allow a one-day sampling tolerance. Longer gaps are reported as not yet measurable instead of being mislabeled as shorter-window growth. The 30-day value remains unavailable until enough history accumulates.
- **License metadata:** flags unknown SPDX data for manual review.
- **Ranked shortlist:** saves a Markdown report and a compact history file.

This is a research aid, not a guarantee that a repository is safe, commercially usable, or growing organically.

## Run locally

Requirements: Python 3.10+ and internet access.

```sh
python3 -m unittest discover -s tests -v
python3 radar.py
cat reports/latest.md
```

Customize topics and sample size:

```sh
python3 radar.py --topic "mcp server" --topic "rust automation" --limit 8 --top 5
```

No personal token is necessary for the default small sample. If you hit GitHub API limits, set your own optional `GITHUB_TOKEN` or reduce `--limit`. A scheduled workflow updates the report every six hours using a free standard runner for public repositories, subject to GitHub's platform policies and limits; scheduled jobs can be delayed. A separate CI workflow runs the unit tests on pull requests and pushes to main with read-only repository permissions. Only the scheduled/manual report workflow receives contents-write permission.

## Contributing

Fixes, tests, scoring improvements, and reports of false positives are welcome. Please open an issue before proposing a major new feature. Keep it dependency-free where practical.

## What it does *not* do

It does not scrape LinkedIn, bypass platform access requirements, automatically publish social posts, or silently install dependencies. GitHub search samples are **not** the official GitHub Trending ranking.

License: [MIT](LICENSE).
