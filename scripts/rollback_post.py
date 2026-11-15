#!/usr/bin/env python3
"""
rollback_post.py
Rolls back the LATEST published issue, so the site looks as if that month was never
published, and leaves a "Rerun this month?" page in the review area.

What it does (all in the working tree; rollback-blog.yml commits it):
  1. Turns blog/posts/<file> into a noindex redirect stub to /blog/ (a shared link lands
     on the blog home). The stub is excluded from the index, sitemap, feed and llms.txt
     because those scripts skip noindex meta-refresh pages by what they are.
  2. Points blog/posts/latest.html at the newest remaining issue.
  3. Undoes the survey wave(s) the approval added (found through git history).
  4. Rebuilds blog index, feed, llms.txt, the adoption page, the survey page and sitemap.
  5. Replaces blog/staging/preview.html with the "rolled back, rerun?" page. The rerun
     covers the SAME month: the issue's own coverage month (December issue = November).

Refuses (exit 1, nothing changed) when: the file is not the newest published issue, a
draft is waiting in staging, or no other issue would remain to be "latest".

    python3 scripts/rollback_post.py <post filename>
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

POSTS = "blog/posts"
STAGING = "blog/staging"
SURVEY = "data/survey.json"
SURVEY_PAGE = "blog/canadian-ai-pulse.html"
HOME = "https://www.imetrobert.com/blog/"
KEEP_IN_STAGING = {"linkedin.json", "promo.json", "reply.json", "preview.html", "health.html", "preview-sample.html", "gate.js",
                   "run-log.json", "usage.json"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


class RollbackError(Exception):
    pass


def is_stub(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = f.read(4000).lower()
    except OSError:
        return False
    return 'http-equiv="refresh"' in head and "noindex" in head


def published_issues():
    """Newest first. Same rule blog_index.py uses: dated .html files, not stubs."""
    names = [f for f in os.listdir(POSTS)
             if f.endswith(".html") and f not in ("latest.html", "index.html")
             and "{" not in f and not is_stub(os.path.join(POSTS, f))]
    return sorted(names, reverse=True)


def coverage_of(post_path):
    """(issue label, coverage month name, coverage year) read from the post itself."""
    from blog_index import extract_post_info
    info = extract_post_info(post_path)
    if not info or not info.get("issue_ym"):
        raise RollbackError("could not read this post's issue month; refusing to guess")
    y, mo = info["issue_ym"]
    cy, cmo = (y, mo - 1) if mo > 1 else (y - 1, 12)
    return f"{MONTHS[mo - 1]} {y}", MONTHS[cmo - 1], str(cy)


def stub_html(label):
    return f"""<!DOCTYPE html>
<html lang="en-CA"><head><meta charset="utf-8">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={HOME}">
<link rel="canonical" href="{HOME}">
<title>Moved | Robert Simon</title>
<script>location.replace("{HOME}");</script>
</head><body>
<p>This issue ({label}) is no longer published. <a href="{HOME}">Go to the blog</a>.</p>
</body></html>
"""


def changed_waves(now_cfg, parent_cfg, commit_cfg):
    """Waves the publish commit added or changed -> new waves list with that undone."""
    before = {w.get("label"): w for w in (parent_cfg or {}).get("waves", [])}
    after = {w.get("label"): w for w in (commit_cfg or {}).get("waves", [])}
    touched = {lab for lab, w in after.items() if before.get(lab) != w}
    waves = [w for w in now_cfg.get("waves", []) if w.get("label") not in touched]
    for lab in touched:
        if lab in before:
            waves.append(before[lab])           # it replaced an older wave: put that back
    waves.sort(key=lambda w: w.get("date", ""))
    return waves, sorted(touched)


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def undo_survey(filename):
    if not os.path.exists(SURVEY):
        return []
    added = _git("log", "--diff-filter=A", "--format=%H", "--", f"{POSTS}/{filename}")
    commits = [c for c in (added or "").split() if c]
    if not commits:
        print("  Survey: no publish commit found in history; left alone.")
        return []
    c = commits[-1]                              # the commit that first added the post
    commit_raw, parent_raw = _git("show", f"{c}:{SURVEY}"), _git("show", f"{c}^:{SURVEY}")
    if commit_raw is None:
        return []
    with open(SURVEY, encoding="utf-8") as f:
        now_cfg = json.load(f)
    waves, touched = changed_waves(now_cfg,
                                   json.loads(parent_raw) if parent_raw else {},
                                   json.loads(commit_raw))
    if not touched:
        return []
    now_cfg["waves"] = waves
    with open(SURVEY, "w", encoding="utf-8") as f:
        json.dump(now_cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    if not waves and os.path.exists(SURVEY_PAGE):
        os.remove(SURVEY_PAGE)                   # no waves left: the results page must go
    print(f"  Survey: undid wave(s) {touched}; {len(waves)} left.")
    return touched


def rollback(filename):
    path = os.path.join(POSTS, filename)
    if not os.path.isfile(path) or is_stub(path):
        raise RollbackError(f"{filename} is not a published issue")
    issues = published_issues()
    if not issues or issues[0] != filename:
        raise RollbackError("only the newest published issue can be rolled back "
                            f"(newest is {issues[0] if issues else 'none'})")
    if len(issues) < 2:
        raise RollbackError("no earlier issue would remain to become 'latest'; refusing")
    pending = [f for f in os.listdir(STAGING)
               if f.endswith(".html") and f not in KEEP_IN_STAGING] if os.path.isdir(STAGING) else []
    if pending:
        raise RollbackError(f"a draft is waiting in staging ({pending[0]}); approve or discard it first")

    label, cov_month, cov_year = coverage_of(path)
    new_latest = issues[1]

    with open(path, "w", encoding="utf-8") as f:
        f.write(stub_html(label))
    shutil.copyfile(os.path.join(POSTS, new_latest), os.path.join(POSTS, "latest.html"))
    print(f"  Stubbed {filename}; latest.html now {new_latest}.")

    undo_survey(filename)

    from blog_index import update_blog_index
    posts = update_blog_index()
    print(f"  Blog index rebuilt with {len(posts)} posts.")
    subprocess.run([sys.executable, "scripts/regenerate_sitemap.py"], check=True)

    for gone in ("linkedin.json", "promo.json", "reply.json"):
        if os.path.exists("blog/staging/" + gone):
            os.remove("blog/staging/" + gone)   # their issue is gone
    from write_nothing_pending_placeholder import write_page
    write_page(rolled_back=(label, cov_month, cov_year))
    print(f"  Rerun page written: {cov_month} {cov_year} (issue {label}).")
    return label, cov_month, cov_year


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        rollback(os.path.basename(sys.argv[1]))
    except RollbackError as e:
        print(f"ERROR: {e}")
        try:
            import runlog
            runlog.fail("rollback", "ROLLBACK_REFUSED", detail=str(e))
        except Exception:
            pass
        sys.exit(1)
