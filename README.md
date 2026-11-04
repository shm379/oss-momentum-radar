# OSS Momentum Radar

**Discover promising open-source projects that keep shipping—even before they trend.**

A lightweight, zero-dependency Python tool from the NabuXAI open-source ecosystem.

## Free core, forever

MIT-licensed. No subscription, paid model, credit card, or third-party service required for the core tool. It uses Python's standard library and GitHub's public API. Anonymous requests have strict rate limits; an *optional* token raises that limit. The included GitHub Actions workflow receives GitHub's built-in short-lived token automatically—no personal token setup required.

## What it measures

- **Recent activity:** GitHub repositories with pushes in the past 14 days.
- **Maintenance momentum:** public commits in the last seven days, even for small projects.
- **Real star growth:** only calculated once seven days of past samples exist (never invented).
- **License metadata:** flags unknown SPDX data for manual review.
- **Ranked shortlist:** saves a Markdown report and a compact history file.

This is a research aid, not a guarantee that a repository is safe, commercially usable, or growing organically.

## Run locally

Requirements: Python 3.10+ and internet access.

\`\`\`sh
python3 -m unittest discover -s tests -v
python3 radar.py
cat reports/latest.md
\`\`\`

Customize topics and sample size:

\`\`\`sh
python3 radar.py --topic "mcp server" --topic "rust automation" --limit 8 --top 5
\`\`\`

No personal token is necessary for the default small sample. If you hit GitHub API limits, set your own optional \`GITHUB_TOKEN\` or reduce \`--limit\`. The workflow updates every six hours using a free standard runner for public repositories, subject to GitHub's platform policies and limits. Scheduled jobs can be delayed.

## Contributing

Fixes, tests, scoring improvements, and reports of false positives are welcome. Please open an issue before proposing a major new feature. Keep it dependency-free where practical.

## What it does *not* do

It does not scrape LinkedIn, bypass platform access requirements, automatically publish social posts, or silently install dependencies. GitHub search samples are **not** the official GitHub Trending ranking.

License: [MIT](LICENSE).
