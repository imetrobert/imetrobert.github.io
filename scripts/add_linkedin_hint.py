#!/usr/bin/env python3
"""
add_linkedin_hint.py
One-off patch: adds the LinkedIn in-app-browser hint to already-published posts
that carry source citations. Idempotent: posts that already contain id="li-hint"
are skipped, so it is safe to run twice.

Run from the repo root: python3 scripts/add_linkedin_hint.py
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkedin_hint import LINKEDIN_HINT

BODY_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)


def main():
    patched, skipped, nocite = [], [], []
    for path in sorted(glob.glob("blog/posts/*.html")):
        with open(path, encoding="utf-8") as f:
            html = f.read()
        if 'id="li-hint"' in html:
            skipped.append(path)
            continue
        if "Search Google for this article" not in html:
            nocite.append(path)  # no citations, nothing to protect
            continue
        m = BODY_RE.search(html)
        if not m:
            print(f"WARNING: no <body> tag in {path}, left unchanged")
            continue
        html = html[:m.end()] + LINKEDIN_HINT + html[m.end():]
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        patched.append(path)

    print(f"Patched: {len(patched)}")
    for p in patched:
        print(f"  + {p}")
    print(f"Already had hint: {len(skipped)}")
    print(f"No citations (left alone): {len(nocite)}")


if __name__ == "__main__":
    main()
