#!/usr/bin/env python3
"""Regenerates sitemap.xml. Called by monthly-blog.yml when publishing directly to posts."""
import os, re
from datetime import datetime

POSTS_DIR = "blog/posts"
BASE_URL  = "https://www.imetrobert.com"

# Exclude noindex redirect stubs and superseded drafts from the sitemap.
EXCLUDE = {
    "latest.html",
    "index.html",
    # Noindex redirect stubs — canonical redirects to the dated version
    "2025-10-01-key-ai-developments-this-month.html",
    "2026-03-26-march-1-2026-openai-announces-gpt5-boasting-enhanced-reasoning-and-multimodal-capabilities.html",
    "2026-03-27-ai-insights-for-march-2026.html",
    # Superseded draft — May 31 is the canonical May 2026 post
    "2026-05-30-ai-insights-for-may-2026.html",
}

def iso_date(filename):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return (m.group(1) + "T00:00:00+00:00") if m else datetime.now().strftime("%Y-%m-%dT00:00:00+00:00")

posts = sorted(
    [f for f in os.listdir(POSTS_DIR)
     if f.endswith(".html") and f not in EXCLUDE
     and not f.startswith("{") and "{" not in f],
    reverse=True
)

today = datetime.now().strftime("%Y-%m-%dT00:00:00+00:00")

entries = [
    (f"{BASE_URL}/",      today, "1.00"),
    (f"{BASE_URL}/blog/", today, "0.80"),
]
for i, fname in enumerate(posts):
    priority = "0.90" if i == 0 else ("0.75" if i == 1 else "0.65")
    entries.append((f"{BASE_URL}/blog/posts/{fname}", iso_date(fname), priority))

lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
    '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
    '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9',
    '              http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">',
    "",
]
for loc, lastmod, priority in entries:
    lines += ["<url>", f"  <loc>{loc}</loc>",
              f"  <lastmod>{lastmod}</lastmod>",
              f"  <priority>{priority}</priority>", "</url>"]
lines.append("</urlset>")

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"sitemap.xml regenerated with {len(entries)} URLs ({len(posts)} blog posts)")
print(f"Excluded noindex/redirect stubs: {sorted(EXCLUDE - {'latest.html', 'index.html'})}")
