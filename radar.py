"""Find actively developed open-source repos, including small ones. Stdlib only."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOPICS = ("mcp server", "rust automation", "self hosted agent", "open source CRM")
WINDOWS = (("24h", 1), ("7d", 7), ("30d", 30))

def request_json(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "oss-momentum-radar/0.1"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        with urlopen(Request("https://api.github.com" + path, headers=headers), timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"GitHub request failed: {error}") from error

def discover(topics, now, api=request_json, per_topic=6):
    since = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    repos = {}
    for topic in topics:
        query = f"{topic} in:name,description pushed:>={since} archived:false fork:false"
        endpoint = "/search/repositories?" + urlencode({"q": query, "sort": "updated", "per_page": per_topic})
        for repo in api(endpoint).get("items", []):
            key = repo["full_name"]
            if repo.get("fork") or repo.get("archived"):
                continue
            if key not in repos:
                repos[key] = {**repo, "topics_found": []}
            repos[key]["topics_found"].append(topic)
    return list(repos.values())

def count_commit_windows(repo, now, api=request_json):
    """Count recent commits from one 30-day API page; full windows are lower bounds."""
    since = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    endpoint = "/repos/" + repo["full_name"] + "/commits?" + urlencode({"since": since, "per_page": 100})
    try:
        result = api(endpoint)
    except RuntimeError:
        return {f"commits_{label}": None for label, _ in WINDOWS}
    if not isinstance(result, list):
        return {f"commits_{label}": None for label, _ in WINDOWS}

    counts = {label: 0 for label, _ in WINDOWS}
    cutoffs = {label: now - timedelta(days=days) for label, days in WINDOWS}
    for item in result:
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        committer = commit.get("committer") or {}
        raw_date = committer.get("date") or author.get("date")
        if not isinstance(raw_date, str):
            continue
        try:
            when = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None or when > now:
            continue
        for label, _ in WINDOWS:
            if when >= cutoffs[label]:
                counts[label] += 1

    # GitHub returns the newest commits first. A full 30-day page is truncated.
    for label, _ in WINDOWS:
        if counts[label] >= 100 or (label == "30d" and len(result) == 100):
            counts[label] = "100+"
    return {f"commits_{label}": counts[label] for label, _ in WINDOWS}


def count_commits_7d(repo, now, api=request_json):
    """Backward-compatible bounded 7-day count used by older callers."""
    since = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    endpoint = "/repos/" + repo["full_name"] + "/commits?" + urlencode({"since": since, "per_page": 100})
    try:
        result = api(endpoint)
        return ("100+" if len(result) == 100 else len(result)) if isinstance(result, list) else None
    except RuntimeError:
        return None

def load_history(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}

def record(history, repos, now):
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    oldest = now - timedelta(days=31)
    # Prune every key, not only repos seen in this run: search results rotate.
    for key in list(history):
        saved = []
        entries = history[key] if isinstance(history[key], list) else []
        for item in entries:
            try:
                date = datetime.fromisoformat(item["at"].replace("Z", "+00:00"))
                # Naive timestamps have no reliable UTC meaning; discard them.
                if date.tzinfo is not None and oldest <= date <= now:
                    saved.append(item)
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
        if saved:
            history[key] = saved[-160:]
        else:
            del history[key]
    for repo in repos:
        key = repo["full_name"]
        history[key] = (history.get(key, []) + [{"at": stamp, "stars": repo.get("stargazers_count", 0)}])[-160:]
    return history

def star_change(history, now, days=7):
    """Compare the latest valid observation to the nearest observation at least days old."""
    threshold = now - timedelta(days=days)
    valid = []
    for entry in history:
        try:
            when = datetime.fromisoformat(entry["at"].replace("Z", "+00:00"))
            stars = entry["stars"]
            if when.tzinfo is None or not isinstance(stars, int) or isinstance(stars, bool) or when > now:
                continue
            valid.append((when, stars))
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
    baseline = [(when, stars) for when, stars in valid if when <= threshold]
    current = [(when, stars) for when, stars in valid if when > threshold]
    if not baseline or not current:
        return None
    return max(current)[1] - max(baseline)[1]

def rank(repo):
    # Commit bursts are evidence of activity, not proportional evidence of
    # maintenance quality. Cap the contribution to avoid 100+ commits swamping
    # a smaller project with steadier activity or observed star growth.
    commits = max(0, int(str(repo.get("commits_7d") or 0).rstrip("+")))
    growth = max(0, repo.get("stars_gained_7d") or 0)
    return 12 * math.log1p(min(commits, 30)) + 3 * growth + math.log1p(repo.get("stargazers_count", 0))

def markdown(repos, now, limit):
    output = [
        "# OSS Momentum Radar",
        "",
        "Updated UTC: " + now.strftime("%Y-%m-%d %H:%M"),
        "",
        "Recent commits indicate activity, **not** a guarantee of quality. Star growth is reported only after sufficient saved observations.",
        "",
        "| Repository | Search topics | Commits (24h) | Commits (7d) | Commits (30d) | Stars | Stars gained (24h) | Stars gained (7d) | Stars gained (30d) | License metadata |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for repo in sorted(repos, key=rank, reverse=True)[:limit]:
        key = repo["full_name"]
        license_name = (repo.get("license") or {}).get("spdx_id") or "unverified"
        commits = ["unknown" if repo.get(f"commits_{label}") is None else str(repo[f"commits_{label}"]) for label, _ in WINDOWS]
        growth = ["not yet measurable" if repo.get(f"stars_gained_{label}") is None else str(repo[f"stars_gained_{label}"]) for label, _ in WINDOWS]
        output.append(
            f"| [{key}](https://github.com/{key}) | {', '.join(repo['topics_found'])} | "
            f"{commits[0]} | {commits[1]} | {commits[2]} | {repo.get('stargazers_count', 0)} | "
            f"{growth[0]} | {growth[1]} | {growth[2]} | {license_name} |"
        )
    output += ["", "## Limitations", "- Not GitHub's official Trending list. Results come from sampled GitHub Search queries.",
               "- Commit counts are bounded to the first 100 results per repository; 100+ is a lower bound, not an exact count.",
               "- Star deltas need saved observations at least as old as each window; 30-day star growth is unavailable until 30 days of history accumulate.",
               "- GitHub API rate limits and scheduled workflow delays may apply.",
               "- Review project LICENSE, CI, maintainer responsiveness, and security before adopting.",
               "- No paid model or third-party key required. An optional GitHub token raises rate limits.", ""]
    return "\n".join(output)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--topic", action="append", dest="topics")
    p.add_argument("--limit", type=int, default=15, help="Maximum repos to inspect for commits (max 30)")
    p.add_argument("--top", type=int, default=10, help="Maximum results in report")
    p.add_argument("--history", type=Path, default=Path("data/history.json"))
    p.add_argument("--output", type=Path, default=Path("reports/latest.md"))
    args = p.parse_args()
    now = datetime.now(timezone.utc)
    try:
        repos = sorted(discover(args.topics or TOPICS, now), key=lambda x: x.get("pushed_at", ""), reverse=True)
        repos = repos[:max(1, min(args.limit, 30))]
        history = load_history(args.history)
        for repo in repos:
            repo.update(count_commit_windows(repo, now))
        history = record(history, repos, now)
        for repo in repos:
            for label, days in WINDOWS:
                repo[f"stars_gained_{label}"] = star_change(history[repo["full_name"]], now, days=days)
        report = markdown(repos, now, args.top)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        args.history.parent.mkdir(parents=True, exist_ok=True)
        args.history.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Saved report with {len(repos)} inspected repositories.")
        return 0
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
