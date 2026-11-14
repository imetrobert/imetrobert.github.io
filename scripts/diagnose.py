#!/usr/bin/env python3
"""
diagnose.py — one compact, paste-able report of the blog pipeline's health.

Built so a chat with NO access to this repo (or a short context budget) can investigate from ~60 lines:
    python3 scripts/diagnose.py            # run in the repo (Claude Code) or in an Actions step
The 'Blog health report' workflow runs it and prints the report in the run summary, so from a phone you can
open Actions > Blog health report > latest run, copy the summary, and paste it into any chat.

Sections: recent failures with plain explanation and next step, recent runs of each blog workflow (when `gh` and a
token are available), model configuration, today's Gemini usage, what is staged, and the first thing to try.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runlog  # noqa: E402

WORKFLOWS = ["monthly-blog.yml", "redraft-section.yml", "regenerate-blog.yml", "approve-blog.yml",
             "discard-blog.yml", "model-scout.yml", "plan-research-test.yml"]


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        return ""


def section(title):
    print(f"\n== {title} ==")


def main():
    print(f"BLOG HEALTH REPORT  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    log = runlog._load()

    section("Last 8 pipeline events (blog/staging/run-log.json)")
    if not log:
        print("  (empty: nothing has run since the run log was introduced)")
    for e in log[-8:]:
        print(f'  {e["at"][:16]} {e["kind"]:10} {e["status"]:6} {e["code"]:20} {e.get("section", "") or e.get("month", "")}')

    fails = [e for e in log if e.get("status") == "failed"]
    section("Most recent failure, explained")
    if fails:
        e = fails[-1]
        print(f'  When: {e["at"]}   Run: https://github.com/imetrobert/imetrobert.github.io/actions/runs/{e.get("run", "")}')
        print(f'  Code: {e["code"]}\n  What: {e["message"]}\n  Next: {e["next"]}\n  Detail: {e["detail"][:300]}')
    else:
        print("  No failures recorded.")

    section("Recent runs of each blog workflow (needs gh + token)")
    any_runs = False
    for wf in WORKFLOWS:
        out = sh(["gh", "run", "list", "--workflow", wf, "--limit", "3", "--json", "conclusion,createdAt,databaseId,event",
                  "--jq", '.[] | "\\(.createdAt[:16]) \\(.conclusion // "running") \\(.event) #\\(.databaseId)"'])
        if out:
            any_runs = True
            print(f"  {wf}:")
            for line in out.splitlines():
                print("    " + line)
    if not any_runs:
        print("  (gh not available here; open the Actions tab)")

    section("Model configuration")
    try:
        import utils
        cfg = json.load(open("blog/model-config.json", encoding="utf-8"))
        order = utils.resolve_model_order()
        print(f'  will lead with: {order[0]}   order tried: {order}')
        print(f'  configured order: {cfg.get("order")}   dismissed: {cfg.get("dismissed")}   limits: {cfg.get("limits")}')
    except Exception as ex:
        print(f"  (could not read the model configuration: {ex})")

    section("Gemini usage today (blog/staging/usage.json)")
    try:
        u = json.load(open("blog/staging/usage.json", encoding="utf-8"))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        print("  " + (json.dumps(u[today]) if today in u else "no Gemini requests recorded today (UTC)"))
    except Exception:
        print("  (no usage file)")

    section("Staged right now")
    names = sorted(n for n in os.listdir("blog/staging") if n.endswith(".html") and not n.startswith("preview")) \
        if os.path.isdir("blog/staging") else []
    print("  " + (", ".join(names) if names else "no draft staged (nothing pending, or discarded/approved)"))

    section("First thing to try")
    if fails:
        print("  " + runlog.explain(fails[-1]["code"])[1])
    else:
        print("  Everything recorded looks fine. If the preview looks stale, wait 2-3 minutes for GitHub Pages and reload.")
    print("\nMore: docs/DIAGNOSE.md")


if __name__ == "__main__":
    main()
