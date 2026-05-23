#!/usr/bin/env python3
"""
seo-fixes-2.py  —  run from repo root
======================================
Round 2 SEO fixes for imetrobert.com blog:

1. Fixes blog/index.html meta description (removes "AI Evangelist")
2. Fixes blog/index.html OG description (removes "AI Evangelist")
3. Adds "Earlier Insights" internal links to every post
4. Fixes broken Canadian AI Adoption Metrics formatting (all stats
   crammed into one bullet → proper separate bullet items)

Usage:  python seo-fixes-2.py
        or via GitHub Actions workflow_dispatch
"""

import os
import re
import sys
from datetime import datetime

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    os.system("pip install beautifulsoup4 lxml --break-system-packages --quiet")
    from bs4 import BeautifulSoup, NavigableString

POSTS_DIR = "blog/posts"
BASE_URL  = "https://www.imetrobert.com"

# Posts to treat as canonical (newest first after sorting)
EXCLUDE = {
    "latest.html", "index.html",
    "2026-03-26-march-1-2026-openai-announces-gpt5-boasting-enhanced-reasoning-and-multimodal-capabilities.html",
    "2026-03-27-ai-insights-for-march-2026.html",
    "2025-10-01-key-ai-developments-this-month.html",
}

# ─── Post discovery ────────────────────────────────────────────────────────────

def get_canonical_posts():
    """Return sorted list of (filename, title, formatted_date) tuples, newest first."""
    posts = []
    for fname in os.listdir(POSTS_DIR):
        if (fname.endswith(".html")
                and fname not in EXCLUDE
                and not fname.startswith("{")
                and "{" not in fname):
            fpath = os.path.join(POSTS_DIR, fname)
            title, date_str = extract_title_and_date(fpath, fname)
            posts.append((fname, title, date_str))

    # Sort by filename date prefix (newest first)
    posts.sort(key=lambda x: x[0], reverse=True)
    return posts


def extract_title_and_date(filepath, filename):
    """Extract h1 title and formatted date from a post file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # Title from h1
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        title = re.sub(r'^[#*\s]+', '', title).strip()
        if not title or len(title) < 5:
            title = f"AI Insights"

        # Date from blog-meta span
        date_str = ""
        blog_meta = soup.find("div", class_="blog-meta")
        if blog_meta:
            spans = blog_meta.find_all("span")
            for span in spans:
                text = span.get_text(strip=True)
                for fmt in ["%B %d, %Y", "%B %Y"]:
                    try:
                        datetime.strptime(text, fmt)
                        date_str = text
                        break
                    except ValueError:
                        pass
                if date_str:
                    break

        # Fallback: parse from filename
        if not date_str:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", filename)
            if m:
                try:
                    d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    date_str = d.strftime("%B %d, %Y")
                except ValueError:
                    pass

        return title, date_str

    except Exception:
        return "AI Insights", ""


# ─── Fix 1 & 2: Blog index description ────────────────────────────────────────

def fix_blog_index_description():
    index_file = "blog/index.html"
    if not os.path.exists(index_file):
        print("  [SKIP] blog/index.html not found")
        return

    with open(index_file, "r", encoding="utf-8") as f:
        html = f.read()

    OLD = "AI Evangelist Robert Simon"
    NEW = "AI Thought Leader Robert Simon"

    if OLD not in html:
        print("  [SKIP] blog/index.html — description already clean")
        return

    updated = html.replace(OLD, NEW)
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(updated)

    count = html.count(OLD)
    print(f"  [FIXED] blog/index.html — replaced {count} instance(s) of '{OLD}'")


# ─── Fix 3: Internal links ─────────────────────────────────────────────────────

EARLIER_SECTION_TEMPLATE = """
<div class="earlier-insights">
  <h3 style="font-size:1rem;font-weight:700;color:var(--dark-navy,#1e293b);margin-bottom:0.25rem;">
    More AI Insights
  </h3>
  <div class="earlier-posts-grid">
{links}
  </div>
</div>"""

EARLIER_LINK_TEMPLATE = (
    '    <a href="/blog/posts/{filename}" class="earlier-post-link">\n'
    '      <div class="earlier-post-title">{title}</div>\n'
    '      <div class="earlier-post-date">{date}</div>\n'
    '    </a>'
)


def build_earlier_section(current_filename, all_posts, max_links=4):
    """Build the Earlier Insights HTML for a given post."""
    others = [(f, t, d) for f, t, d in all_posts if f != current_filename][:max_links]
    if not others:
        return ""

    links = "\n".join(
        EARLIER_LINK_TEMPLATE.format(filename=f, title=t, date=d)
        for f, t, d in others
    )
    return EARLIER_SECTION_TEMPLATE.format(links=links)


def add_internal_links(filename, all_posts):
    """Add or refresh Earlier Insights section in a post."""
    filepath = os.path.join(POSTS_DIR, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Remove any existing earlier-insights section
    existing = soup.find("div", class_="earlier-insights")
    if existing:
        existing.decompose()

    # Build new section
    section_html = build_earlier_section(filename, all_posts)
    if not section_html:
        return False

    new_section = BeautifulSoup(section_html, "html.parser")

    # Insert before closing </article> tag
    article = soup.find("article")
    if article:
        article.append(new_section)
    else:
        # Fallback: append inside .article-content
        content = soup.find("div", class_="article-content")
        if content:
            content.append(new_section)
        else:
            return False

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(str(soup))

    return True


# ─── Fix 4: Adoption Metrics formatting ───────────────────────────────────────

def fix_adoption_metrics(filename):
    """
    Split adoption metrics that Gemini returned as one long prose bullet
    into separate <li> elements.
    Targets the Canadian Business AI Adoption Metrics section.
    """
    filepath = os.path.join(POSTS_DIR, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    changed = False

    # Find all bullet lists
    for ul in soup.find_all("ul", class_="bullet-list"):
        items = ul.find_all("li")

        for li in items:
            text = li.get_text(strip=True)

            # Only target suspiciously long single-stat bullets
            # that contain sentence-ending numbers (percent, %, figures)
            if len(text) < 150:
                continue

            # Check if it looks like multiple stats crammed together
            stat_pattern = re.compile(
                r'\d+[\s]?(?:percent|%)|'
                r'\$[\d,]+|'
                r'\d+\.\d+\s?(?:percent|%)',
                re.IGNORECASE
            )
            if len(stat_pattern.findall(text)) < 2:
                continue

            # Split on sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            if len(sentences) < 2:
                continue

            # Replace the single li with multiple li elements
            parent = li.parent
            insert_pos = list(parent.children).index(li)

            li.decompose()

            for i, sentence in enumerate(sentences):
                new_li = soup.new_tag("li")
                new_li.string = sentence
                parent.insert(insert_pos + i, new_li)

            changed = True

    if changed:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(str(soup))
        return True

    return False


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 62)
    print("  SEO Fixes Round 2 — imetrobert.com blog")
    print("=" * 62)

    if not os.path.exists(POSTS_DIR):
        print(f"\nERROR: '{POSTS_DIR}' not found. Run from repo root.")
        sys.exit(1)

    # ── Fix 1 & 2: blog/index.html descriptions ──────────────────
    print("\n1. Fixing blog/index.html descriptions …")
    fix_blog_index_description()

    # ── Discover all canonical posts ─────────────────────────────
    all_posts = get_canonical_posts()
    print(f"\n   Found {len(all_posts)} canonical posts:")
    for fname, title, date in all_posts:
        print(f"     {fname[:50]:<50}  {date}")

    # ── Fix 3: Internal links ─────────────────────────────────────
    print(f"\n2. Adding internal links to {len(all_posts)} posts …")
    linked = 0
    for fname, _, _ in all_posts:
        try:
            ok = add_internal_links(fname, all_posts)
            status = "LINKED" if ok else "SKIP"
            print(f"  [{status}] {fname}")
            if ok:
                linked += 1
        except Exception as e:
            print(f"  [ERROR] {fname}: {e}")

    print(f"\n   {linked} posts updated with internal links")

    # ── Fix 4: Adoption metrics ───────────────────────────────────
    print(f"\n3. Fixing broken adoption metrics formatting …")
    fixed_metrics = 0
    for fname, _, _ in all_posts:
        try:
            ok = fix_adoption_metrics(fname)
            if ok:
                print(f"  [FIXED] {fname}")
                fixed_metrics += 1
        except Exception as e:
            print(f"  [ERROR] {fname}: {e}")

    if fixed_metrics == 0:
        print("  [SKIP] No broken metrics found (already formatted correctly)")
    else:
        print(f"\n   {fixed_metrics} posts had metrics reformatted")

    print("\n" + "=" * 62)
    print("  DONE — commit and push:")
    print("  git add -A")
    print('  git commit -m "SEO fixes: internal links, metrics, index description"')
    print("  git push")
    print("=" * 62)


if __name__ == "__main__":
    main()
