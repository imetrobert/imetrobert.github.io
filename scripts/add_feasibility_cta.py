#!/usr/bin/env python3
"""
add_feasibility_cta.py
Adds the end-of-issue feasibility-check call to action (utils.feasibility_cta_html)
to posts published BEFORE the renderer started adding it (December 2026 issue).
The article text is not touched: the block goes in just before the last
</article>.

Idempotent: any earlier copy is removed first (everything from the marker
comment to the end of its <div>), so a re-run after the wording changes updates
every post rather than stacking a second block. Redirect stubs are skipped.
The campaign in the link is "archive-<post date>", so a lead that arrives from
an old issue can be told apart from one that came from a new one.

Run from the repo root: python3 scripts/add_feasibility_cta.py
latest.html is patched too (it mirrors the newest post).
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import FEASIBILITY_CTA_MARKER, feasibility_cta_html

# The block is one <div class="section feasibility-cta"> with no nested <div>.
OLD_RE = re.compile(re.escape(FEASIBILITY_CTA_MARKER) + r'<div class="section feasibility-cta".*?</div>\s*', re.DOTALL)


def is_redirect_stub(html):
    head = html[:4000].lower()
    return 'http-equiv="refresh"' in head and "noindex" in head


def campaign_for(path, html):
    name = os.path.basename(path)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    if not m:  # latest.html: take the date from the canonical link
        m = re.search(r"/blog/posts/(\d{4}-\d{2}-\d{2})", html)
    return "archive-" + (m.group(1) if m else "post")


def patch(path, html):
    """Return (new_html, status): 'ok', 'stub' or 'no-article'."""
    if is_redirect_stub(html):
        return html, "stub"
    # A post the renderer built already names its own issue in the link; keep it.
    old = OLD_RE.search(html)
    kept = re.search(r"utm_campaign=(issue-[A-Za-z0-9-]+)", old.group(0)) if old else None
    campaign = kept.group(1) if kept else campaign_for(path, html)
    html = OLD_RE.sub("", html)
    end = html.rfind("</article>")
    if end == -1:
        return html, "no-article"
    return html[:end].rstrip() + "\n" + feasibility_cta_html(campaign) + "\n        " + html[end:], "ok"


def main():
    changed, same, skipped, problems = [], [], [], []
    for path in sorted(glob.glob("blog/posts/*.html")):
        with open(path, encoding="utf-8") as f:
            original = f.read()
        new, status = patch(path, original)
        if status == "stub":
            skipped.append(path)
        elif status != "ok":
            problems.append((path, status))
        elif new == original:
            same.append(path)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            changed.append(path)
    print(f"Added or updated: {len(changed)}")
    for p in changed:
        print("  ", p)
    print(f"Already current: {len(same)}   Redirect stubs skipped: {len(skipped)}")
    for p, why in problems:
        print(f"  PROBLEM {p}: {why}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
