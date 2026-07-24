"""
blog_index.py
Reads blog post metadata and writes the blog/index.html listing page.
"""

import os
import re
import json
from datetime import datetime
from xml.sax.saxutils import escape as escape_xml
from bs4 import BeautifulSoup

# Noindex redirect stubs / superseded drafts — must stay excluded from the
# index the same way regenerate_sitemap.py excludes them from the sitemap.
# Kept as a separate literal list (not shared code) because these two
# scripts run independently in different workflow steps.
EXCLUDE_STUBS = {
    "2025-10-01-key-ai-developments-this-month.html",
    "2026-03-26-march-1-2026-openai-announces-gpt5-boasting-enhanced-reasoning-and-multimodal-capabilities.html",
    "2026-03-27-ai-insights-for-march-2026.html",
    "2026-05-30-ai-insights-for-may-2026.html",
}


def extract_post_info(html_file):
    if not os.path.exists(html_file) or os.path.getsize(html_file) == 0:
        return None
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "AI Insights"
    title = re.sub(r'^[#\*\s]+', '', title).strip()

    date_text = None
    nav_meta = soup.find("div", class_="nav-meta") or soup.find("div", class_="blog-meta")
    if nav_meta:
        meta_text = nav_meta.get_text()
        if "•" in meta_text:
            date_text = meta_text.split("•")[-1].strip()
    if not date_text:
        basename = os.path.basename(html_file)
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", basename)
        if match:
            date_obj = datetime.strptime(match.group(1), "%Y-%m-%d")
            date_text = date_obj.strftime("%B %d, %Y")
        else:
            date_text = datetime.now().strftime("%B %d, %Y")

    excerpt = None
    intro = soup.find("p", class_="intro-lead") or soup.find("div", class_="intro-text")
    if intro:
        excerpt = re.sub(r'\s+', ' ', intro.get_text()).strip()[:200]
    if not excerpt:
        article = soup.find("div", class_="article-content")
        if article:
            p = article.find("p")
            if p:
                excerpt = re.sub(r'\s+', ' ', p.get_text()).strip()[:200]
    if not excerpt:
        excerpt = "Read the latest AI insights for Canadian business leaders."

    return {"title": title, "date": date_text, "excerpt": excerpt, "filename": os.path.basename(html_file)}


def create_blog_index_html(posts):
    if not posts:
        return None
    posts_dir = "blog/posts"
    validated = [p for p in posts if os.path.exists(os.path.join(posts_dir, p['filename']))]
    if not validated:
        return None

    latest = validated[0]
    older  = validated[1:]

    older_html = ""
    if older:
        for post in older:
            older_html += f'''
                <div class="older-post-item">
                    <a href="/blog/posts/{post['filename']}" class="older-post-link">
                        <div class="older-post-title">{post['title']}</div>
                        <div class="older-post-date">{post['date']}</div>
                    </a>
                </div>'''
    else:
        older_html = '<div class="no-posts-message"><p>Previous issues will appear here.</p></div>'

    itemlist_elements = []
    for i, post in enumerate(validated[:12], 1):
        schema_filename = post.get('canonical_filename', post['filename'])
        url = f"https://www.imetrobert.com/blog/posts/{schema_filename}"
        itemlist_elements.append(
            f'{{"@type":"ListItem","position":{i},"url":"{url}","name":{json.dumps(post["title"])}}}'
        )

    return f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI News for Canadians | Monthly AI Insights Blog | Robert Simon</title>
    <meta name="description" content="Monthly AI insights for Canadian business leaders. Expert analysis of AI breakthroughs, Canadian AI adoption data, and practical implementation strategies from Montreal-based AI Thought Leader Robert Simon.">
    <meta name="keywords" content="AI blog Canada, Canadian AI insights, AI news for Canadians, artificial intelligence Canada, AI strategy Canada, Montreal AI expert, Canadian business AI, AI adoption Canada, digital transformation Canada">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="language" content="en-CA">
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">
    <link rel="canonical" href="https://www.imetrobert.com/blog/">
    <link rel="alternate" type="application/rss+xml" title="AI Insights for Canadian Business — RSS Feed" href="https://www.imetrobert.com/blog/feed.xml">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://www.imetrobert.com/blog/">
    <meta property="og:title" content="AI News for Canadians | Monthly AI Insights Blog | Robert Simon">
    <meta property="og:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI Thought Leader Robert Simon.">
    <meta property="og:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="AI News for Canadians | Monthly AI Insights | Robert Simon">
    <meta name="twitter:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI Thought Leader Robert Simon.">
    <meta name="twitter:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Blog",
      "name": "AI Insights for Canadian Business",
      "description": "Monthly AI intelligence for Canadian business leaders by Robert Simon.",
      "url": "https://www.imetrobert.com/blog/",
      "inLanguage": "en-CA",
      "author": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "jobTitle": "AI Thought Leader & Digital Transformation Expert",
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }}
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "ItemList",
      "name": "AI Insights Blog Posts",
      "url": "https://www.imetrobert.com/blog/",
      "numberOfItems": {len(validated)},
      "itemListElement": [{", ".join(itemlist_elements)}]
    }}
    </script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>
    <style>
        body {{ font-family: Inter, sans-serif; background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%); margin: 0; padding: 0; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }}
        header {{ background: linear-gradient(135deg, #2563eb 0%, #1a7fb5 50%, #06b6d4 100%); color: white; padding: 4rem 0; text-align: center; margin-bottom: 2.5rem; border-radius: 20px; }}
        h1 {{ font-size: 2.8rem; font-weight: 800; margin-bottom: 0.5rem; letter-spacing: -0.02em; }}
        .nav-bar {{ background: white; padding: 1rem 0; box-shadow: 0 1px 3px rgb(0 0 0 / 0.08); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #e2e8f0; }}
        .nav-content {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; justify-content: flex-start; gap: 0.6rem; }}
        .nav-link {{ color: white; text-decoration: none; font-weight: 600; padding: 0.4rem 1rem; font-size: 0.8rem; border-radius: 20px; background: linear-gradient(135deg, #2563eb, #06b6d4); }}
        .latest-post-section {{ background: linear-gradient(135deg, #2563eb 0%, #1a7fb5 50%, #06b6d4 100%); color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem; box-shadow: 0 8px 32px rgb(37 99 235 / 0.2); }}
        .latest-badge {{ background: rgba(255,255,255,0.2); color: white; padding: 0.3rem 0.9rem; border-radius: 20px; display: inline-block; margin-bottom: 1rem; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
        .latest-post-title {{ font-size: 1.7rem; font-weight: 800; margin-bottom: 0.875rem; letter-spacing: -0.01em; }}
        .read-latest-btn {{ background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.35); padding: 0.65rem 1.5rem; border-radius: 25px; text-decoration: none; display: inline-block; transition: all 0.25s; font-weight: 600; font-size: 0.875rem; }}
        .read-latest-btn:hover {{ background: rgba(255,255,255,0.3); transform: translateY(-2px); }}
        .older-posts-section {{ background: white; border-radius: 20px; padding: 2rem; box-shadow: 0 4px 16px rgb(0 0 0 / 0.06); border: 1px solid #e2e8f0; }}
        .older-posts-title {{ font-size: 0.8rem; font-weight: 700; margin-bottom: 1.25rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
        .older-post-item {{ border: 1px solid #f1f5f9; border-radius: 12px; margin-bottom: 0.65rem; transition: all 0.2s; }}
        .older-post-item:hover {{ border-color: #2563eb; box-shadow: 0 4px 12px rgb(37 99 235 / 0.08); }}
        .older-post-link {{ display: block; padding: 1rem 1.25rem; text-decoration: none; color: inherit; }}
        .older-post-title {{ font-size: 0.95rem; font-weight: 600; color: #2563eb; margin-bottom: 0.25rem; }}
        .older-post-date {{ font-size: 0.78rem; color: #94a3b8; }}
        .no-posts-message {{ text-align: center; padding: 2rem; color: #94a3b8; }}
        .blog-tagline {{ font-size: 0.95rem; opacity: 0.85; margin-top: 0.5rem; }}
        @media (max-width: 640px) {{
            h1 {{ font-size: 2rem; }}
            .container {{ padding: 1rem; }}
            .latest-post-section {{ padding: 1.5rem; }}
            .latest-post-title {{ font-size: 1.35rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com" class="nav-link">&#8592; Back to Homepage</a>
            <a href="/blog/feed.xml" class="nav-link">RSS Feed</a>
        </div>
    </nav>
    <div class="container">
        <header>
            <h1>AI Insights Blog</h1>
            <p>Monthly intelligence for Canadian business leaders</p>
            <p class="blog-tagline">by Robert Simon &mdash; Montreal, QC</p>
        </header>
        <section class="latest-post-section">
            <div class="latest-badge">Latest Issue</div>
            <h2 class="latest-post-title">{latest['title']}</h2>
            <div style="margin-bottom: 0.875rem; opacity: 0.85; font-size: 0.85rem;">{latest['date']}</div>
            <p style="line-height: 1.65; margin-bottom: 1.5rem; opacity: 0.9; font-size: 0.9rem;">{latest['excerpt']}</p>
            <a href="/blog/posts/latest.html" class="read-latest-btn">Read This Month\'s Issue &#8594;</a>
        </section>
        <section class="older-posts-section">
            <h3 class="older-posts-title">Previous Issues</h3>
            <div class="older-posts-grid">{older_html}</div>
        </section>
    </div>
</body>
</html>'''


def create_feed_xml(posts):
    """RSS 2.0 feed — the explicit, machine-readable proof of the monthly
    cadence: each item carries its own pubDate, unlike sitemap.xml which
    only exposes lastmod."""
    if not posts:
        return None

    build_date = datetime.now().strftime("%a, %d %b %Y 00:00:00 GMT")

    items = []
    for post in posts:
        filename = post.get('canonical_filename', post['filename'])
        url = f"https://www.imetrobert.com/blog/posts/{filename}"
        try:
            pub_date = datetime.strptime(post['date'], "%B %d, %Y").strftime("%a, %d %b %Y 00:00:00 GMT")
        except Exception:
            pub_date = build_date
        items.append(f'''    <item>
      <title>{escape_xml(post['title'])}</title>
      <link>{url}</link>
      <guid isPermaLink="true">{url}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape_xml(post['excerpt'])}</description>
    </item>''')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>AI Insights for Canadian Business &#8212; Robert Simon</title>
  <link>https://www.imetrobert.com/blog/</link>
  <atom:link href="https://www.imetrobert.com/blog/feed.xml" rel="self" type="application/rss+xml"/>
  <description>Monthly AI insights for Canadian business leaders. Expert analysis of AI breakthroughs, Canadian AI adoption data, and practical implementation strategies from Montreal-based AI Thought Leader Robert Simon.</description>
  <language>en-ca</language>
  <lastBuildDate>{build_date}</lastBuildDate>
  <image>
    <url>https://www.imetrobert.com/blog/og-blog.jpg</url>
    <title>AI Insights for Canadian Business &#8212; Robert Simon</title>
    <link>https://www.imetrobert.com/blog/</link>
  </image>
{chr(10).join(items)}
</channel>
</rss>'''


def update_blog_index():
    posts_dir  = "blog/posts"
    index_file = "blog/index.html"
    feed_file  = "blog/feed.xml"
    if not os.path.exists(posts_dir):
        return []

    latest_path = os.path.join(posts_dir, "latest.html")
    posts = []
    if os.path.exists(latest_path) and os.path.getsize(latest_path) > 100:
        try:
            info = extract_post_info(latest_path)
            if info:
                canonical_filename = None
                html_files_check = sorted(
                    [f for f in os.listdir(posts_dir)
                     if f.endswith(".html") and f not in ("latest.html", "index.html")
                     and not f.startswith("{") and "{" not in f
                     and f not in EXCLUDE_STUBS],
                    reverse=True
                )
                if html_files_check:
                    canonical_filename = html_files_check[0]
                info['filename'] = 'latest.html'
                info['canonical_filename'] = canonical_filename or 'latest.html'
                posts.append(info)
        except Exception as e:
            print(f"Warning: could not read latest.html: {e}")

    html_files = [
        f for f in os.listdir(posts_dir)
        if f.endswith(".html") and f not in ("latest.html", "index.html")
        and not f.startswith("{") and '{' not in f
        and f not in EXCLUDE_STUBS
    ]
    for fname in sorted(html_files, reverse=True):
        try:
            info = extract_post_info(os.path.join(posts_dir, fname))
            if info:
                posts.append(info)
        except Exception:
            continue

    if not posts:
        return []

    seen, deduped = set(), []
    for post in posts:
        try:
            d   = datetime.strptime(post['date'], "%B %d, %Y")
            key = d.strftime("%Y-%m")
        except Exception:
            key = post['date']
        if key not in seen:
            deduped.append(post)
            seen.add(key)

    idx_html = create_blog_index_html(deduped)
    if idx_html:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(idx_html)
        print(f"Blog index updated ({len(deduped)} issues).")

    feed_xml = create_feed_xml(deduped)
    if feed_xml:
        with open(feed_file, "w", encoding="utf-8") as f:
            f.write(feed_xml)
        print(f"RSS feed updated ({len(deduped)} items).")

    return deduped
