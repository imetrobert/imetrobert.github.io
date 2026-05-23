#!/usr/bin/env python3
"""
seo-cleanup.py  —  run from repo root
======================================
Full SEO/GEO cleanup for imetrobert.com blog posts. Run once via
GitHub Actions (workflow below) or locally: python seo-cleanup.py

What it does
------------
1. Deduplicates JSON-LD blocks on every post (older posts had 3x repeats)
2. Standardizes author jobTitle → "AI Thought Leader & Digital Transformation Expert"
3. Removes worksFor: Bell Canada from all schemas
4. Removes FAQPage schemas where answers don't match questions
5. Standardizes .author-role byline text
6. Adds meta refresh redirect + noindex to March 26 and March 27 duplicates
7. Adds meta redirect + noindex to the near-empty Oct 1 stub
8. Regenerates sitemap.xml with all canonical posts
9. Fixes blog/index.html numberOfItems count in ItemList schema
10. Updates patch-existing-posts.py with correct jobTitle
"""

import os
import re
import json
import sys
from datetime import datetime

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing beautifulsoup4...")
    os.system("pip install beautifulsoup4 lxml --break-system-packages --quiet")
    from bs4 import BeautifulSoup

# ─── Configuration ─────────────────────────────────────────────────────────────

POSTS_DIR    = "blog/posts"
BASE_URL     = "https://www.imetrobert.com"
AUTHOR_TITLE = "AI Thought Leader & Digital Transformation Expert"
AUTHOR_ROLE_HTML = (
    "AI Thought Leader &amp; Digital Transformation Expert &mdash; Montreal, QC"
)

# Files to redirect → their target URL
REDIRECT_MAP = {
    "2026-03-26-march-1-2026-openai-announces-gpt5-boasting-enhanced-reasoning-and-multimodal-capabilities.html":
        f"{BASE_URL}/blog/posts/2026-03-31-ai-insights-for-march-2026.html",
    "2026-03-27-ai-insights-for-march-2026.html":
        f"{BASE_URL}/blog/posts/2026-03-31-ai-insights-for-march-2026.html",
    "2025-10-01-key-ai-developments-this-month.html":
        f"{BASE_URL}/blog/posts/2025-10-31-key-ai-developments-this-month.html",
}

# Files excluded from normal processing
SKIP_FILES = {"latest.html", "index.html"}

# Files excluded from the sitemap (redirected or non-canonical)
SITEMAP_EXCLUDE = set(REDIRECT_MAP.keys()) | {"latest.html", "index.html"}


# ─── Helpers ───────────────────────────────────────────────────────────────────

def get_all_posts():
    """Return every processable HTML filename in blog/posts."""
    return [
        f for f in os.listdir(POSTS_DIR)
        if f.endswith(".html")
        and f not in SKIP_FILES
        and not f.startswith("{")
        and "{" not in f
    ]


def standardize_author(obj):
    """Recursively fix author jobTitle and remove worksFor: Bell Canada."""
    if isinstance(obj, dict):
        if obj.get("@type") == "Person" and obj.get("name") == "Robert Simon":
            obj["jobTitle"] = AUTHOR_TITLE
            obj.pop("worksFor", None)
        for v in list(obj.values()):
            standardize_author(v)
    elif isinstance(obj, list):
        for item in obj:
            standardize_author(item)
    return obj


def is_faq_mismatched(schema):
    """Return True if a FAQPage has answers that don't actually answer their questions."""
    if schema.get("@type") != "FAQPage":
        return False
    entities = schema.get("mainEntity", [])
    if not entities:
        return True
    for entity in entities:
        q = entity.get("name", "").lower()
        a = (entity.get("acceptedAnswer", {}).get("text", "")).lower()
        # If the answer looks like a generic recommendation rather than
        # a direct response to the question, flag it
        recommendation_phrases = [
            "invest in", "prioritize", "develop a", "foster collab",
            "monitor global", "adopt ai responsibly", "experiment with",
        ]
        if any(phrase in a for phrase in recommendation_phrases):
            return True
    return False


def dedup_jsonld(soup):
    """
    Extract all JSON-LD blocks, deduplicate by @type (keep most complete),
    remove bad FAQPage schemas, standardize author fields.
    Returns list of cleaned schema dicts.
    """
    best = {}  # @type -> dict with most keys

    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        raw = (tag.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        schema_type = data.get("@type", "_unknown")

        # Drop FAQPage with mismatched answers
        if schema_type == "FAQPage" and is_faq_mismatched(data):
            continue

        # Keep the instance with the most keys (most complete)
        existing = best.get(schema_type)
        if existing is None or len(data) >= len(existing):
            best[schema_type] = standardize_author(data)

    # Emit in a logical order
    order = ["BlogPosting", "BreadcrumbList", "FAQPage",
             "Person", "WebPage", "WebSite", "Blog", "ItemList"]
    result = [best[t] for t in order if t in best]
    for t, d in best.items():
        if t not in order:
            result.append(d)

    return result


def rebuild_jsonld(soup, schemas):
    """Remove every JSON-LD tag and re-insert the cleaned set."""
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        tag.decompose()

    head = soup.find("head")
    if not head or not schemas:
        return

    # Insert before <style> if present, otherwise append to head
    style_tag = head.find("style")

    for schema in schemas:
        new_tag = soup.new_tag("script")
        new_tag["type"] = "application/ld+json"
        new_tag.string = "\n" + json.dumps(schema, indent=2, ensure_ascii=False) + "\n    "
        if style_tag:
            style_tag.insert_before(new_tag)
        else:
            head.append(new_tag)


def fix_byline(soup):
    """Standardize the .author-role div."""
    role_div = soup.find("div", class_="author-role")
    if role_div:
        role_div.clear()
        role_div.append(
            BeautifulSoup(AUTHOR_ROLE_HTML, "html.parser")
        )


def fix_html_lang(soup):
    tag = soup.find("html")
    if tag:
        tag["lang"] = "en-CA"


def add_redirect(soup, target_url):
    """Prepend meta refresh + noindex and update canonical."""
    head = soup.find("head")
    if not head:
        return

    # Remove any existing refresh or robots metas
    for m in head.find_all("meta"):
        if m.get("http-equiv", "").lower() == "refresh":
            m.decompose()
        elif m.get("name", "").lower() == "robots":
            m.decompose()

    # Update canonical
    canonical = head.find("link", {"rel": "canonical"})
    if canonical:
        canonical["href"] = target_url

    # Build new tags
    refresh = soup.new_tag("meta")
    refresh["http-equiv"] = "refresh"
    refresh["content"] = f"0; url={target_url}"

    noindex = soup.new_tag("meta")
    noindex["name"] = "robots"
    noindex["content"] = "noindex, follow"

    # Insert at very top of head
    first = next(
        (c for c in head.children if hasattr(c, "name") and c.name),
        None
    )
    if first:
        first.insert_before(noindex)
        first.insert_before(refresh)
    else:
        head.append(refresh)
        head.append(noindex)


# ─── File processing ───────────────────────────────────────────────────────────

def process_file(filename):
    filepath = os.path.join(POSTS_DIR, filename)
    is_redirect = filename in REDIRECT_MAP

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    fix_html_lang(soup)
    schemas = dedup_jsonld(soup)
    rebuild_jsonld(soup, schemas)
    fix_byline(soup)

    if is_redirect:
        add_redirect(soup, REDIRECT_MAP[filename])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(str(soup))

    tag = "REDIRECT" if is_redirect else "CLEANED"
    ld_count = len(schemas)
    print(f"  [{tag}] {filename}  ({ld_count} schema blocks)")


# ─── Sitemap ───────────────────────────────────────────────────────────────────

def iso_from_filename(filename):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return (m.group(1) + "T00:00:00+00:00") if m else datetime.now().strftime("%Y-%m-%dT00:00:00+00:00")


def get_canonical_posts():
    """All posts that should appear in the sitemap, newest first."""
    return sorted(
        [
            f for f in os.listdir(POSTS_DIR)
            if f.endswith(".html")
            and f not in SITEMAP_EXCLUDE
            and not f.startswith("{")
            and "{" not in f
        ],
        reverse=True,
    )


def generate_sitemap():
    posts = get_canonical_posts()
    today = datetime.now().strftime("%Y-%m-%dT00:00:00+00:00")

    entries = [
        (f"{BASE_URL}/",       today, "1.00"),
        (f"{BASE_URL}/blog/",  today, "0.80"),
    ]

    for i, fname in enumerate(posts):
        priority = "0.90" if i == 0 else ("0.75" if i == 1 else "0.65")
        entries.append((
            f"{BASE_URL}/blog/posts/{fname}",
            iso_from_filename(fname),
            priority,
        ))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9',
        '              http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">',
        "",
    ]
    for loc, lastmod, priority in entries:
        lines += [
            "<url>",
            f"  <loc>{loc}</loc>",
            f"  <lastmod>{lastmod}</lastmod>",
            f"  <priority>{priority}</priority>",
            "</url>",
        ]
    lines.append("</urlset>")

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  [GENERATED] sitemap.xml  ({len(entries)} URLs)")


# ─── Blog index fix ────────────────────────────────────────────────────────────

def fix_blog_index():
    index_file = "blog/index.html"
    if not os.path.exists(index_file):
        print("  [SKIP] blog/index.html not found")
        return

    posts = get_canonical_posts()
    count = len(posts)  # latest.html shares URL with newest post, so no +1

    with open(index_file, "r", encoding="utf-8") as f:
        html = f.read()

    updated = re.sub(
        r'"numberOfItems"\s*:\s*\d+',
        f'"numberOfItems": {count}',
        html,
    )

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"  [UPDATED] blog/index.html  numberOfItems → {count}")


# ─── Fix patch-existing-posts.py ───────────────────────────────────────────────

def fix_patch_script():
    target = "patch-existing-posts.py"
    if not os.path.exists(target):
        print(f"  [SKIP] {target} not found")
        return

    with open(target, "r", encoding="utf-8") as f:
        src = f.read()

    OLD_TITLE   = "AI Evangelist & Digital Sales Leader"
    OLD_WORKFOR = (
        '"worksFor": {\n'
        '      "@type": "Organization",\n'
        '      "name": "Bell Canada"\n'
        '    },'
    )

    updated = src.replace(
        f'"jobTitle": "{OLD_TITLE}"',
        f'"jobTitle": "{AUTHOR_TITLE}"',
    )
    # Remove worksFor block (with trailing comma)
    updated = re.sub(
        r',?\s*"worksFor"\s*:\s*\{[^}]+\}',
        "",
        updated,
    )

    if updated == src:
        print(f"  [SKIP] {target}  — already up to date")
        return

    with open(target, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"  [UPDATED] {target}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 62)
    print("  SEO Cleanup — imetrobert.com blog")
    print("=" * 62)

    if not os.path.exists(POSTS_DIR):
        print(f"\nERROR: '{POSTS_DIR}' not found.")
        print("Run this script from the root of your repository.")
        sys.exit(1)

    posts = get_all_posts()
    print(f"\n1. Processing {len(posts)} blog posts …")
    ok = err = 0
    for fname in sorted(posts):
        try:
            process_file(fname)
            ok += 1
        except Exception as exc:
            print(f"  [ERROR] {fname}: {exc}")
            import traceback; traceback.print_exc()
            err += 1

    print(f"\n   {ok} processed  |  {err} errors")

    print("\n2. Regenerating sitemap.xml …")
    generate_sitemap()

    print("\n3. Fixing blog/index.html schema count …")
    fix_blog_index()

    print("\n4. Updating patch-existing-posts.py …")
    fix_patch_script()

    print("\n" + "=" * 62)
    print("  DONE — commit and push, then:")
    print("  • Google Search Console → Sitemaps → submit sitemap.xml")
    print("  • URL Inspection tool → request re-index on April post")
    print("=" * 62)


if __name__ == "__main__":
    main()
