"""
blog_index.py
Reads blog post metadata and writes the blog/index.html listing page.
"""

import os
import re
import json
from datetime import datetime
from html import escape as escape_html
from urllib.parse import quote
from xml.sax.saxutils import escape as escape_xml
from bs4 import BeautifulSoup

SITE = "https://www.imetrobert.com"


def _permalink(post):
    """The dated URL for an issue — never latest.html.

    posts[0] is read from latest.html, which is a rotating alias: the same URL
    serves a different article every month. Sharing it produces a link that
    silently changes what it points at, and a social preview cached against the
    wrong article. update_blog_index() resolves the real dated file into
    canonical_filename for exactly this reason; older entries already carry
    their own dated filename.
    """
    return f"{SITE}/blog/posts/{post.get('canonical_filename') or post['filename']}"


def _share_hrefs(url, title):
    """(linkedin, mailto) as HTML-attribute-safe strings.

    Resolved at build time so both work with JavaScript disabled — only the
    clipboard and OS share sheet need scripting.
    """
    linkedin = (
        "https://www.linkedin.com/sharing/share-offsite/?url=" + quote(url, safe='')
    )
    # Most archive titles already lead with "AI Insights for <month>"; appending
    # the publication name to those produces "AI Insights for August 2026 — AI
    # Insights" in the recipient's inbox.
    subject = title if "ai insights" in title.lower() else f"{title} — AI Insights"
    mailto = (
        "mailto:?subject=" + quote(subject, safe='')
        + "&body=" + quote(
            f"Thought this was worth your time — Robert Simon's monthly AI "
            f"briefing for Canadian business leaders.\n\n{title}\n{url}\n",
            safe=''
        )
    )
    return escape_html(linkedin, quote=True), escape_html(mailto, quote=True)

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

    # Link the newest issue by its DATED permalink, not /blog/posts/latest.html.
    # latest.html is a rotating alias: same URL, different article every month.
    # Social platforms cache Open Graph data per URL essentially forever, so a
    # share of latest.html keeps showing whichever month was scraped first —
    # and worse, an old post silently starts pointing at a newer article.
    # Every other issue in this list already uses its permalink; the newest one
    # was the only exception, which is exactly the one people share.
    latest_permalink = latest.get('canonical_filename') or latest['filename']
    latest_url = _permalink(latest)
    latest_li_href, latest_mail_href = _share_hrefs(latest_url, latest['title'])
    latest_url_attr = escape_html(latest_url, quote=True)
    latest_title_attr = escape_html(latest['title'], quote=True)

    older_html = ""
    if older:
        for post in older:
            # The share controls sit OUTSIDE the row's <a>. Interactive
            # elements cannot be nested inside a link — browsers recover from
            # it unpredictably, and a keyboard user ends up unable to reach the
            # buttons at all.
            post_url = _permalink(post)
            li_href, mail_href = _share_hrefs(post_url, post['title'])
            safe_title = escape_html(post['title'], quote=True)
            older_html += f'''
                <div class="older-post-item">
                    <a href="/blog/posts/{post['filename']}" class="older-post-link">
                        <div class="older-post-title">{post['title']}</div>
                        <div class="older-post-date">{post['date']}</div>
                    </a>
                    <div class="older-post-share">
                        <a class="mini-btn" href="{li_href}" target="_blank" rel="noopener noreferrer"
                           title="Share on LinkedIn" aria-label="Share &quot;{safe_title}&quot; on LinkedIn">
                            <svg class="icon" aria-hidden="true"><use href="#i-linkedin"/></svg>
                        </a>
                        <a class="mini-btn" href="{mail_href}"
                           title="Share by email" aria-label="Share &quot;{safe_title}&quot; by email">
                            <svg class="icon" aria-hidden="true"><use href="#i-mail"/></svg>
                        </a>
                        <button type="button" class="mini-btn share-copy" data-share-url="{escape_html(post_url, quote=True)}"
                           title="Copy link" aria-label="Copy link to &quot;{safe_title}&quot;">
                            <svg class="icon" aria-hidden="true"><use href="#i-copy"/></svg>
                        </button>
                    </div>
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
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
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
        "image": "https://www.imetrobert.com/profile.jpg",
        "jobTitle": "AI Thought Leader & Digital Transformation Expert",
        "knowsAbout": ["Artificial Intelligence", "Digital Transformation", "AI Adoption in Canada", "AI Strategy"],
        "sameAs": ["https://linkedin.com/in/thedigitalrobert"],
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }},
      "publisher": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "logo": {{"@type": "ImageObject", "url": "https://www.imetrobert.com/blog/logo-512.png", "width": 512, "height": 512}}
      }},
      "isAccessibleForFree": true
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
        .nav-content {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: 0.6rem; }}
        .nav-brand {{ display: flex; align-items: center; gap: 0.5rem; text-decoration: none; margin-right: auto; }}
        .nav-brand img {{ width: 28px; height: 28px; border-radius: 9px; }}
        .nav-brand span {{ font-weight: 800; font-size: 0.9rem; color: #0f172a; letter-spacing: -0.01em; }}
        .brand-logo {{ width: 76px; height: 76px; display: block; margin: 0 auto 1.25rem; padding: 7px; box-sizing: content-box; background: rgba(255,255,255,0.96); border-radius: 23px; box-shadow: 0 10px 26px rgba(15,23,42,0.25); }}
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
        /* Inline SVG icons, sprite defined at the top of <body>. Stroked in
           currentColor and sized in em so each icon matches its adjacent text. */
        .icon {{ width: 1.05em; height: 1.05em; flex-shrink: 0; fill: none; stroke: currentColor; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; vertical-align: -0.14em; }}
        /* Share on the latest-issue card. It sits on the blue gradient, so the
           buttons are translucent white rather than the bordered light style
           used in the archive rows below. */
        .latest-share {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-top: 1.5rem; padding-top: 1.25rem; border-top: 1px solid rgba(255,255,255,0.2); }}
        .latest-share-label {{ font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; opacity: 0.7; margin-right: 0.2rem; }}
        .latest-share .share-btn {{ display: inline-flex; align-items: center; justify-content: center; min-height: 36px; gap: 0.4rem; font: inherit; font-size: 0.78rem; font-weight: 600; color: white; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); border-radius: 20px; padding: 0.4rem 0.9rem; text-decoration: none; cursor: pointer; transition: background 0.2s, transform 0.15s; }}
        .latest-share .share-btn:hover {{ background: rgba(255,255,255,0.28); transform: translateY(-1px); }}
        .latest-share .share-btn.copied {{ background: #16a34a; border-color: #16a34a; }}
        .share-btn[hidden] {{ display: none; }}
        /* Archive rows: the link keeps its full-width hit area, the buttons sit
           beside it rather than inside it. */
        .older-post-item {{ display: flex; align-items: center; gap: 0.5rem; padding-right: 0.75rem; }}
        .older-post-link {{ flex: 1; min-width: 0; }}
        .older-post-share {{ display: flex; gap: 0.3rem; flex-shrink: 0; }}
        .mini-btn {{ display: inline-flex; align-items: center; justify-content: center; width: 2.25rem; height: 2.25rem; border-radius: 50%; border: 1px solid #e2e8f0; background: white; color: #64748b; cursor: pointer; text-decoration: none; transition: color 0.2s, border-color 0.2s, background 0.2s; font-size: 0.85rem; }}
        .mini-btn:hover {{ color: #2563eb; border-color: #2563eb; }}
        .mini-btn.copied {{ background: #16a34a; border-color: #16a34a; color: white; }}
        @media (max-width: 640px) {{
            h1 {{ font-size: 2rem; }}
            .brand-logo {{ width: 58px; height: 58px; padding: 6px; border-radius: 18px; }}
            .container {{ padding: 1rem; }}
            .latest-post-section {{ padding: 1.5rem; }}
            .latest-post-title {{ font-size: 1.35rem; }}
            /* Stack the archive row so a 44px touch target for the title link
               is never competing with the share buttons for the same tap. */
            .older-post-item {{ flex-direction: column; align-items: stretch; padding-right: 0; }}
            .older-post-share {{ padding: 0 1.25rem 0.9rem; }}
            .mini-btn {{ width: 2.75rem; height: 2.75rem; }}
            .latest-share .share-btn {{ min-height: 44px; padding: 0.55rem 1rem; }}
            .nav-content {{ padding: 0 1rem; row-gap: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <!-- Icon sprite. Reference a symbol by id from an svg.icon element.
         Markers here are geometric on purpose: the brand's maple leaf is
         illegible below ~32px, so it stays in the logo and does not get
         shrunk down into a button glyph. -->
    <svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
        <symbol id="i-linkedin" viewBox="0 0 24 24">
            <path fill="currentColor" stroke="none" d="M4.98 3.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM3 9.5h4v11H3zm7 0h3.8v1.5a4.2 4.2 0 0 1 3.7-1.9c3 0 4.5 1.9 4.5 5.3v6.1h-4v-5.4c0-1.6-.6-2.6-2-2.6s-2.2 1-2.2 2.6v5.4h-3.8z"/>
        </symbol>
        <symbol id="i-mail" viewBox="0 0 24 24">
            <rect x="3" y="5" width="18" height="14" rx="2.5"/>
            <path d="m3.5 7 8.5 6 8.5-6"/>
        </symbol>
        <symbol id="i-copy" viewBox="0 0 24 24">
            <rect x="9" y="9" width="11" height="11" rx="2.5"/>
            <path d="M6.5 15H5.5A2.5 2.5 0 0 1 3 12.5v-7A2.5 2.5 0 0 1 5.5 3h7A2.5 2.5 0 0 1 15 5.5v1"/>
        </symbol>
        <symbol id="i-share" viewBox="0 0 24 24">
            <circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/>
            <path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>
        </symbol>
    </svg>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="/blog/" class="nav-brand">
                <img src="/blog/logo.svg" alt="" width="28" height="28">
                <span>AI Insights</span>
            </a>
            <a href="https://www.imetrobert.com" class="nav-link">&#8592; Back to Homepage</a>
            <a href="/blog/canadian-ai-adoption.html" class="nav-link">Adoption Data</a>
            <a href="/blog/feed.xml" class="nav-link">RSS Feed</a>
        </div>
    </nav>
    <div class="container">
        <header>
            <img src="/blog/logo.svg" class="brand-logo" alt="AI Insights" width="76" height="76">
            <h1>AI Insights Blog</h1>
            <p>Monthly intelligence for Canadian business leaders</p>
            <p class="blog-tagline">by Robert Simon &mdash; Montreal, QC</p>
        </header>
        <section class="latest-post-section">
            <div class="latest-badge">Latest Issue</div>
            <h2 class="latest-post-title">{latest['title']}</h2>
            <div style="margin-bottom: 0.875rem; opacity: 0.85; font-size: 0.85rem;">{latest['date']}</div>
            <p style="line-height: 1.65; margin-bottom: 1.5rem; opacity: 0.9; font-size: 0.9rem;">{latest['excerpt']}</p>
            <a href="/blog/posts/{latest_permalink}" class="read-latest-btn">Read This Month\'s Issue &#8594;</a>
            <div class="latest-share">
                <span class="latest-share-label">Share</span>
                <a class="share-btn" href="{latest_li_href}" target="_blank" rel="noopener noreferrer">
                    <svg class="icon" aria-hidden="true"><use href="#i-linkedin"/></svg><span>LinkedIn</span>
                </a>
                <a class="share-btn" href="{latest_mail_href}">
                    <svg class="icon" aria-hidden="true"><use href="#i-mail"/></svg><span>Email</span>
                </a>
                <button type="button" class="share-btn share-copy" data-share-url="{latest_url_attr}">
                    <svg class="icon" aria-hidden="true"><use href="#i-copy"/></svg><span class="share-btn-text">Copy link</span>
                </button>
                <button type="button" class="share-btn share-native" hidden
                        data-share-url="{latest_url_attr}" data-share-title="{latest_title_attr}">
                    <svg class="icon" aria-hidden="true"><use href="#i-share"/></svg><span>Share</span>
                </button>
            </div>
        </section>
        <section class="older-posts-section">
            <h3 class="older-posts-title">Previous Issues</h3>
            <div class="older-posts-grid">{older_html}</div>
        </section>
    </div>
    <script>
      // Share behaviour for the hero card and every archive row. One delegated
      // listener, so adding issues to the page costs nothing.
      (function () {{
        function fallbackCopy(text) {{
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.setAttribute('readonly', '');
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          try {{ document.execCommand('copy'); }} catch (e) {{}}
          document.body.removeChild(ta);
        }}

        function flash(btn) {{
          var label = btn.querySelector('.share-btn-text');
          var original = label ? label.textContent : null;
          if (label) label.textContent = 'Copied';
          btn.classList.add('copied');
          setTimeout(function () {{
            if (label) label.textContent = original;
            btn.classList.remove('copied');
          }}, 1800);
        }}

        // Revealed rather than rendered: a desktop visitor should never see a
        // button that would do nothing. LinkedIn, email and copy cover them.
        if (navigator.share) {{
          document.querySelectorAll('.share-native').forEach(function (b) {{
            b.hidden = false;
          }});
        }}

        document.addEventListener('click', function (e) {{
          if (!e.target.closest) return;

          var copyBtn = e.target.closest('.share-copy');
          if (copyBtn) {{
            var url = copyBtn.dataset.shareUrl;
            if (!url) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {{
              navigator.clipboard.writeText(url).then(
                function () {{ flash(copyBtn); }},
                function () {{ fallbackCopy(url); flash(copyBtn); }}
              );
            }} else {{
              fallbackCopy(url);
              flash(copyBtn);
            }}
            if (typeof gtag === 'function') {{
              gtag('event', 'share', {{ method: 'copy_link' }});
            }}
            return;
          }}

          var nativeBtn = e.target.closest('.share-native');
          if (nativeBtn && navigator.share) {{
            navigator.share({{
              title: nativeBtn.dataset.shareTitle || document.title,
              url: nativeBtn.dataset.shareUrl
            }}).then(function () {{
              if (typeof gtag === 'function') {{
                gtag('event', 'share', {{ method: 'web_share' }});
              }}
            }}).catch(function () {{
              // Sheet dismissed. Not an error.
            }});
          }}
        }});
      }})();
    </script>
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


def create_llms_txt(posts):
    """llms.txt — a plain-language map of the site for answer engines.

    Answer engines do better when they can see, in one fetch, what a site is
    about and who is behind it, rather than inferring it from markup. Kept in
    sync with the post list here so it can never drift out of date."""
    lines = [
        "# Robert Simon — AI Insights for Canadian Business",
        "",
        "> Monthly AI intelligence written for Canadian business leaders by Robert",
        "> Simon, a Montreal-based AI thought leader and digital transformation",
        "> expert with 25+ years in digital. Each issue covers the month's major AI",
        "> developments, what is happening in Canada specifically, Canadian AI",
        "> adoption data, and concrete actions for executives.",
        "",
        "Content here may be quoted and cited. Please attribute to Robert Simon",
        "and link to the source URL of the issue you are quoting.",
        "",
        "## About the author",
        "",
        "- Name: Robert Simon",
        "- Role: AI Thought Leader & Digital Transformation Expert",
        "- Location: Montreal, Quebec, Canada",
        "- Site: https://www.imetrobert.com",
        "- LinkedIn: https://linkedin.com/in/thedigitalrobert",
        "",
        "## Key pages",
        "",
        "- [Homepage](https://www.imetrobert.com): background, career and areas of expertise",
        "- [AI Insights Blog](https://www.imetrobert.com/blog/): index of every issue",
        "- [RSS feed](https://www.imetrobert.com/blog/feed.xml): machine-readable issue list with dates",
        "- [Canadian AI adoption statistics](https://www.imetrobert.com/blog/canadian-ai-adoption.html): every adoption figure reported across the issues, by month, with sources",
        "",
        "## Issues",
        "",
    ]
    for post in posts:
        filename = post.get("canonical_filename", post["filename"])
        url = f"https://www.imetrobert.com/blog/posts/{filename}"
        excerpt = re.sub(r"\s+", " ", post["excerpt"]).strip()
        if len(excerpt) > 160:
            excerpt = excerpt[:157].rsplit(" ", 1)[0] + "..."
        lines.append(f"- [{post['title']}]({url}) — {post['date']}. {excerpt}")
    lines += [
        "",
        "## Not for indexing",
        "",
        "- /blog/staging/ — private drafting and approval tooling, not public content.",
        "",
    ]
    return "\n".join(lines)


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

    # Evergreen pillar: rebuilt from the archive on every publish, so it gains a
    # month of data automatically instead of needing a hand edit.
    try:
        from pillar_adoption import write_pillar
        write_pillar()
    except Exception as e:
        print(f"Pillar page skipped ({e})")

    # Survey results. Writes nothing until a wave exists in data/survey.json,
    # so there is never a results page describing data not yet collected.
    try:
        from survey import write_survey_page
        write_survey_page()
    except Exception as e:
        print(f"Survey page skipped ({e})")

    llms_txt = create_llms_txt(deduped)
    if llms_txt:
        with open("llms.txt", "w", encoding="utf-8") as f:
            f.write(llms_txt)
        print(f"llms.txt updated ({len(deduped)} issues).")

    return deduped
