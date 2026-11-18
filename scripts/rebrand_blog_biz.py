#!/usr/bin/env python3
"""One-time, idempotent re-brand of already-published blog pages to the Business brand (2026-11-17).

Usage: python3 scripts/rebrand_blog_biz.py        (run from the repo root; safe to run twice)
New pages already carry the brand from utils.py (BRAND, BRAND_SHORT, publisher_jsonld). This patches pages generated BEFORE the change,
and ONLY the branding around the issue: favicon links, og:site_name, the nav name, the logo alt text and the publisher in the JSON-LD.
Issue titles, headlines and body copy are left alone on purpose (historical text, not branding). The logo itself changed by replacing
blog/logo.svg (every page already points at it). /blog/staging/ and redirect stubs are skipped. Also see docs/blog-pipeline.md, "Brand".
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from utils import BRAND, BRAND_SHORT, PUBLISHER_ID, PUBLISHER_NAME, PUBLISHER_URL, PARENT_ID  # noqa: E402

OLD_NAMES = ("AI Insights for Canadian Business", "Practical AI for Canadian Business", "Practical AI Canada", "AI Insights Blog", "AI Insights",
             "AI News for Canadians")
ICON_OLD = "<link rel=\"icon\" type=\"image/svg+xml\" href=\"/favicon.svg\">"
ICON_NEW = '<link rel="icon" type="image/png" sizes="32x32" href="/blog/favicon-32x32.png">'
APPLE_OLD = '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
APPLE_NEW = '<link rel="apple-touch-icon" href="/blog/apple-touch-icon.png">'
PUBLISHER = {"@type": "Organization", "@id": PUBLISHER_ID, "name": PUBLISHER_NAME, "url": PUBLISHER_URL, "parentOrganization": {"@id": PARENT_ID},
             "logo": {"@type": "ImageObject", "url": "https://www.imetrobert.com/blog/logo-512.png", "width": 512, "height": 512}}


def fix_jsonld(m):
    try:
        data = json.loads(m.group(2))
    except Exception:
        return m.group(0)
    changed = False

    def walk(o):
        nonlocal changed
        if isinstance(o, dict):
            p = o.get("publisher")
            if isinstance(p, dict) and p.get("@type") == "Person":
                o["publisher"] = dict(PUBLISHER); changed = True
            if o.get("item") in ("https://www.imetrobert.com/blog/", "https://www.imetrobert.com/blog") and o.get("name") in OLD_NAMES:
                o["name"] = BRAND; changed = True   # breadcrumb entry for the blog
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    if not changed:
        return m.group(0)
    return m.group(1) + "\n" + json.dumps(data, indent=2, ensure_ascii=False) + "\n" + m.group(3)


def rebrand(s):
    s = s.replace(ICON_OLD, ICON_NEW).replace(APPLE_OLD, APPLE_NEW)
    s = re.sub(r'(<meta\s+content=")[^"]*("\s+property="og:site_name"\s*/?>)', lambda m: m.group(1) + BRAND + m.group(2), s)
    s = re.sub(r'(<meta\s+property="og:site_name"\s+content=")[^"]*(")', lambda m: m.group(1) + BRAND + m.group(2), s)
    for old in OLD_NAMES:   # the brand name in the nav bar only (a lone <span> in the top bar)
        s = s.replace("<span>" + old + "</span>", "<span>" + BRAND_SHORT + "</span>")
    for old in OLD_NAMES:   # breadcrumb link to the blog
        s = s.replace('<a href="https://www.imetrobert.com/blog/">' + old + "</a>", '<a href="https://www.imetrobert.com/blog/">' + BRAND + "</a>")
    s = re.sub(r'(<img src="/blog/logo\.svg" class="brand-logo" alt=")[^"]*(")', lambda m: m.group(1) + BRAND + m.group(2), s)
    s = re.sub(r'(<script type="application/ld\+json">)(.*?)(</script>)', fix_jsonld, s, flags=re.S)
    return s


def main():
    paths = [p for p in glob.glob("blog/**/*.html", recursive=True) if not p.startswith("blog/staging/")]
    changed = 0
    for p in sorted(paths):
        s = open(p, encoding="utf-8").read()
        if 'http-equiv="refresh"' in s.lower()[:4000] and "noindex" in s.lower()[:4000]:
            continue
        t = rebrand(s)
        if t != s:
            open(p, "w", encoding="utf-8").write(t)
            changed += 1
    print(f"Re-branded {changed} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
