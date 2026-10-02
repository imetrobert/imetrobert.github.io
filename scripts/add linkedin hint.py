#!/usr/bin/env python3
"""
add_linkedin_hint.py
Adds the LinkedIn in-app-browser hint to published posts that carry source
citations, and REPAIRS any copy that was inserted in the wrong place.

History: the first version matched the first "<body" in the file, which is the
literal text "<body>" inside a CSS comment in <head>. The banner landed inside
the <style> block and the page's CSS rendered as visible text. This version:
  1. strips the banner wherever it currently is (exact-string match),
  2. re-inserts it right after the REAL <body> tag, the first one that comes
     after </head>.
Idempotent: a correctly patched post is unchanged by a re-run.

Run from the repo root: python3 scripts/add_linkedin_hint.py
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkedin_hint import LINKEDIN_HINT

BODY_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)


def patch(html):
    """Return (new_html, status). status: 'ok', 'no-head' or 'no-body'."""
    html = html.replace(LINKEDIN_HINT, "")      # undo any earlier insertion
    head_end = html.find("</head>")
    if head_end == -1:
        return html, "no-head"
    m = BODY_RE.search(html, head_end)          # only a <body> AFTER </head>
    if not m:
        return html, "no-body"
    return html[:m.end()] + LINKEDIN_HINT + html[m.end():], "ok"


def main():
    changed, same, nocite, problems = [], [], [], []
    for path in sorted(glob.glob("blog/posts/*.html")):
        with open(path, encoding="utf-8") as f:
            original = f.read()
        if "Search Google for this article" not in original:
            nocite.append(path)  # no citations, nothing to protect
            continue
        new, status = patch(original)
        if status != "ok":
            problems.append((path, status))
            continue
        if new == original:
            same.append(path)
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        changed.append(path)

    print(f"Fixed or added: {len(changed)}")
    for p in changed:
        print(f"  + {p}")
    print(f"Already correct: {len(same)}")
    print(f"No citations (left alone): {len(nocite)}")
    for p, why in problems:
        print(f"WARNING: {p} left unchanged ({why})")


if __name__ == "__main__":
    main()
