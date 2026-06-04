#!/usr/bin/env python3
"""
fix_old_posts.py
Fixes two structural defects in blog posts generated before March 2026:

1. TRIPLE-DUPLICATED itemprop meta tags
   Old posts (Sep 2025 – Feb 2026) have <meta itemprop="headline"> etc. printed 3 times
   inside the <article>. This pollutes structured data. Keep only one copy.

2. <div class="section-title"> → <h2 class="section-title">
   Old posts used <div> instead of <h2> for section headings inside article content.
   This breaks SEO (no H2 hierarchy) and accessibility (no landmark headings).
   New posts (Mar 2026+) already use <h2> correctly — only patch older files.

Run: python3 scripts/fix_old_posts.py
     (or via the fix-old-posts GitHub Actions workflow)
"""

import os
import re

POSTS_DIR = "blog/posts"

# Posts that use the OLD template (div.section-title, triple itemprop tags)
# These are all posts before March 2026. The fix is safe to run on any post —
# it's idempotent (running twice changes nothing).
SKIP = {
    "latest.html",
    "index.html",
    "2025-10-01-key-ai-developments-this-month.html",
    "2026-03-26-march-1-2026-openai-announces-gpt5-boasting-enhanced-reasoning-and-multimodal-capabilities.html",
    "2026-03-27-ai-insights-for-march-2026.html",
}


def dedupe_itemprop_metas(html: str) -> tuple[str, int]:
    """
    Remove duplicate itemprop meta blocks inside <article>.
    The pattern: groups of 5 identical <meta itemprop=...> lines appear 2-3 times.
    Strategy: find the article element, keep only the FIRST occurrence of each
    itemprop attribute value, remove subsequent duplicates.
    """
    # Find all itemprop meta tags
    pattern = re.compile(
        r'<meta\s+content="([^"]+)"\s+itemprop="([^"]+)"\s*/?>'
    )
    
    seen_iprops = {}  # itemprop_name -> first occurrence index
    matches = list(pattern.finditer(html))
    
    if not matches:
        return html, 0
    
    # Count how many times each itemprop appears
    counts = {}
    for m in matches:
        key = m.group(2)  # itemprop name
        counts[key] = counts.get(key, 0) + 1
    
    # Only proceed if there are actually duplicates
    max_count = max(counts.values()) if counts else 1
    if max_count <= 1:
        return html, 0
    
    removed = 0
    # For each duplicated itemprop, remove all but the first occurrence
    for iprop_name, count in counts.items():
        if count <= 1:
            continue
        # Find all occurrences of this specific itemprop tag
        specific = re.compile(
            r'<meta\s+content="[^"]*"\s+itemprop="' + re.escape(iprop_name) + r'"\s*/?>\s*\n?'
        )
        occurrences = list(specific.finditer(html))
        # Remove all after the first
        # Work backwards to preserve indices
        for m in reversed(occurrences[1:]):
            html = html[:m.start()] + html[m.end():]
            removed += 1
    
    return html, removed


def upgrade_section_title_divs(html: str) -> tuple[str, int]:
    """
    Replace <div class="section-title"> with <h2 class="section-title">
    inside the article content area only.
    Also handles the closing tag.
    Only applies inside .article-content to avoid touching nav/header elements.
    """
    # Find the article-content div
    content_start = html.find('<div class="article-content"')
    if content_start == -1:
        content_start = html.find('class="article-content"')
    
    if content_start == -1:
        return html, 0
    
    # Find end of article content (look for </article> as boundary)
    content_end = html.find('</article>', content_start)
    if content_end == -1:
        content_end = len(html)
    
    before = html[:content_start]
    content = html[content_start:content_end]
    after = html[content_end:]
    
    # Count replacements
    count = len(re.findall(r'<div class="section-title">', content))
    
    if count == 0:
        return html, 0
    
    # Replace opening tags
    content = content.replace(
        '<div class="section-title">',
        '<h2 class="section-title">'
    )
    
    # Replace closing tags — this is trickier because we need to match the right </div>
    # The section-title div contains only text/inline elements, so the first </div>
    # after each <h2 class="section-title"> is its closing tag.
    # Use a targeted replacement: find h2 tags and replace their closing div.
    def replace_closing(m):
        inner = m.group(1)
        return f'<h2 class="section-title">{inner}</h2>'
    
    content = re.sub(
        r'<h2 class="section-title">(.*?)</div>',
        replace_closing,
        content,
        flags=re.DOTALL
    )
    
    return before + content + after, count


def fix_post(filepath: str) -> dict:
    filename = os.path.basename(filepath)
    
    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()
    
    html = original
    changes = {}
    
    # Fix 1: deduplicate itemprop meta tags
    html, itemprop_removed = dedupe_itemprop_metas(html)
    if itemprop_removed:
        changes["itemprop_dupes_removed"] = itemprop_removed
    
    # Fix 2: upgrade div.section-title to h2 (only for old posts)
    # Detect old-style posts: they use <div class="section-title"> NOT <h2 class="section-title">
    has_old_headings = '<div class="section-title">' in html
    if has_old_headings:
        html, heading_count = upgrade_section_title_divs(html)
        if heading_count:
            changes["section_title_divs_upgraded"] = heading_count
    
    if html == original:
        return {"file": filename, "status": "unchanged", "changes": {}}
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    return {"file": filename, "status": "fixed", "changes": changes}


def main():
    if not os.path.exists(POSTS_DIR):
        print(f"ERROR: {POSTS_DIR} not found. Run from repo root.")
        return
    
    post_files = sorted([
        f for f in os.listdir(POSTS_DIR)
        if f.endswith(".html") and f not in SKIP
        and not f.startswith("{") and "{" not in f
    ])
    
    print(f"Scanning {len(post_files)} blog posts for defects...\n")
    
    results = []
    for fname in post_files:
        result = fix_post(os.path.join(POSTS_DIR, fname))
        results.append(result)
        if result["status"] == "fixed":
            print(f"  ✅ Fixed  {fname}")
            for k, v in result["changes"].items():
                print(f"       {k}: {v}")
        else:
            print(f"  —  Clean  {fname}")
    
    fixed = [r for r in results if r["status"] == "fixed"]
    print(f"\nSummary: {len(fixed)} / {len(results)} posts patched.")
    
    if fixed:
        total_iprops = sum(r["changes"].get("itemprop_dupes_removed", 0) for r in fixed)
        total_headings = sum(r["changes"].get("section_title_divs_upgraded", 0) for r in fixed)
        if total_iprops:
            print(f"  Itemprop duplicate meta tags removed: {total_iprops}")
        if total_headings:
            print(f"  Section title divs upgraded to h2: {total_headings}")


if __name__ == "__main__":
    main()
