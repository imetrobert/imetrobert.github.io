#!/usr/bin/env python3
"""One-time, idempotent recolour of the blog from blue/cyan to the Business brand (navy + dark gold).

Usage: python3 scripts/rebrand_blog.py        (run from the repo root; safe to run twice)
The generators (renderer.py, blog_index.py, pillar_*.py, survey.py) already use the new colours; this patches the
issues and pages that were generated BEFORE the change so the whole blog looks the same. Redirect stubs are untouched.
Gold text colour is #8a6d0b (the Business brand's gold-for-text, readable with white text); navy is #11304c.
"""
import glob
import os
import sys

MAP = {"#2563eb": "#11304c", "#1d4ed8": "#0b2237", "#06b6d4": "#8a6d0b", "#1a7fb5": "#1f3b4d"}


def recolour(text):
    for old, new in MAP.items():
        text = text.replace(old, new).replace(old.upper(), new)
    return text


def main():
    paths = [p for p in glob.glob("blog/**/*.html", recursive=True) if not p.startswith("blog/staging/")]
    changed = 0
    for p in sorted(paths):
        s = open(p, encoding="utf-8").read()
        if 'http-equiv="refresh"' in s.lower()[:4000] and "noindex" in s.lower()[:4000]:
            continue
        t = recolour(s)
        if t != s:
            open(p, "w", encoding="utf-8").write(t)
            changed += 1
    print(f"Recoloured {changed} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
