#!/usr/bin/env python3
"""
patch-existing-posts.py
Run once from repo root to retrofit all existing blog posts with full SEO/GEO meta tags.
Usage: python patch-existing-posts.py
"""

import os
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup

GA_TAG = '''    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>'''

def clean_title(raw_title):
    """Strip markdown artifacts and cruft from page titles"""
    t = re.sub(r'^[#\*\s]+', '', raw_title)
    t = re.sub(r'\s*\|.*$', '', t)
    t = t.strip()
    if not t or len(t) < 5:
        return None
    return t

def extract_date_from_filename(filename):
    match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except:
            pass
    return None

def extract_date_from_html(soup, filename):
    # Try blog-meta span
    blog_meta = soup.find('div', class_='blog-meta')
    if blog_meta:
        spans = blog_meta.find_all('span')
        for span in spans:
            text = span.get_text(strip=True)
            for fmt in ['%B %d, %Y', '%B %Y']:
                try:
                    return datetime.strptime(text, fmt)
                except:
                    pass
    # Fallback to filename
    return extract_date_from_filename(filename)

def extract_excerpt(soup):
    # Try header .intro div first
    intro = soup.find('div', class_='intro')
    if intro:
        text = re.sub(r'\s+', ' ', intro.get_text()).strip()
        if len(text) > 30:
            return text[:200].rstrip() + ('...' if len(text) > 200 else '')
    # Fall back to first paragraph in article content
    article = soup.find('div', class_='article-content')
    if article:
        first_sec = article.find('div', class_='section')
        if first_sec:
            p = first_sec.find('p')
            if p:
                text = re.sub(r'\s+', ' ', p.get_text()).strip()
                if len(text) > 30:
                    return text[:200].rstrip() + ('...' if len(text) > 200 else '')
    return None

def build_seo_head(title, meta_desc, canonical_url, iso_date, og_image, month_year, slug_keywords):
    """Build the full SEO <head> block to inject"""

    article_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": meta_desc,
        "datePublished": iso_date,
        "dateModified": iso_date,
        "author": {
            "@type": "Person",
            "name": "Robert Simon",
            "url": "https://www.imetrobert.com",
            "jobTitle": "AI Evangelist & Digital Sales Leader",
            "worksFor": {"@type": "Organization", "name": "Bell Canada"},
            "address": {"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}
        },
        "publisher": {"@type": "Person", "name": "Robert Simon", "url": "https://www.imetrobert.com"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "url": canonical_url,
        "image": og_image,
        "inLanguage": "en-CA",
        "about": [
            {"@type": "Thing", "name": "Artificial Intelligence"},
            {"@type": "Thing", "name": "Canadian Business"},
            {"@type": "Place", "name": "Canada"}
        ],
        "keywords": f"AI Canada {month_year}, Canadian AI, artificial intelligence Canada, Canadian business AI, AI news Montreal, digital transformation Canada"
    }, indent=2)

    breadcrumb_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.imetrobert.com"},
            {"@type": "ListItem", "position": 2, "name": "AI Insights Blog", "item": "https://www.imetrobert.com/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": canonical_url}
        ]
    }, indent=2)

    return f'''
    <!-- ═══ SEO: Primary meta ═══ -->
    <title>{title} | AI News for Canadian Business | Robert Simon</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="AI Canada {month_year}, Canadian AI insights, {slug_keywords}, artificial intelligence Canada, AI strategy Canada, Montreal AI expert, Canadian business AI, AI adoption Canada, Bell Canada AI, digital transformation Canada">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
    <meta name="language" content="en-CA">
    <meta name="revisit-after" content="30 days">

    <!-- ═══ GEO: Canadian location signals ═══ -->
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">

    <!-- ═══ Canonical ═══ -->
    <link rel="canonical" href="{canonical_url}">

    <!-- ═══ Open Graph ═══ -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="{title} | AI Insights for Canadian Business">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">
    <meta property="article:published_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:modified_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:author" content="Robert Simon">
    <meta property="article:section" content="AI Strategy">
    <meta property="article:tag" content="AI Canada">
    <meta property="article:tag" content="Canadian Business">
    <meta property="article:tag" content="Artificial Intelligence">
    <meta property="article:tag" content="Digital Transformation">
    <meta property="article:tag" content="Montreal">

    <!-- ═══ Twitter / X card ═══ -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title} | AI News for Canadian Business">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <meta name="twitter:site" content="@thedigitalrobert">

    <!-- ═══ Structured data: Article + Breadcrumb ═══ -->
    <script type="application/ld+json">
{article_schema}
    </script>
    <script type="application/ld+json">
{breadcrumb_schema}
    </script>'''

def inject_author_byline(soup):
    """Add author byline after breadcrumb if not already present"""
    # Don't add if already there
    if soup.find('div', class_='author-byline'):
        return
    
    article = soup.find('article')
    if not article:
        return

    # Add CSS for byline + breadcrumb if not present
    style_tag = soup.find('style')
    if style_tag and 'author-byline' not in style_tag.string:
        style_tag.string += '''
        .author-byline { display: flex; align-items: center; gap: 1rem; padding: 1.25rem 3rem; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }
        .author-byline img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }
        .author-byline .author-name { font-weight: 600; color: var(--dark-navy, #1e293b); font-size: 0.95rem; }
        .author-byline .author-role { font-size: 0.85rem; color: var(--medium-gray, #64748b); }
        .breadcrumb-visible { font-size: 0.82rem; color: var(--medium-gray, #64748b); padding: 0.75rem 3rem; background: #fafbfc; border-bottom: 1px solid #f1f5f9; }
        .breadcrumb-visible a { color: var(--primary-blue, #2563eb); text-decoration: none; }
        .breadcrumb-visible a:hover { text-decoration: underline; }
        @media (max-width: 768px) { .author-byline { padding: 1rem 1.5rem; } .breadcrumb-visible { padding: 0.75rem 1.5rem; } }'''

    # Build byline HTML and insert as first child of article
    byline_tag = soup.new_tag('div', attrs={'class': 'author-byline'})
    byline_tag.string = ''  # placeholder, will replace with raw html trick below
    # Use BeautifulSoup to parse and insert
    byline_html = BeautifulSoup('''
        <div class="author-byline">
            <img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon - AI Evangelist, Montreal" loading="lazy">
            <div>
                <div class="author-name">Robert Simon</div>
                <div class="author-role">AI Evangelist &amp; Digital Sales Leader, Bell Canada &mdash; Montreal, QC</div>
            </div>
        </div>''', 'html.parser')
    article.insert(0, byline_html)

def add_itemprop_to_article(soup, title, meta_desc, iso_date, canonical_url):
    """Add itemprop microdata to article element"""
    article = soup.find('article')
    if not article:
        return
    article['itemscope'] = ''
    article['itemtype'] = 'https://schema.org/BlogPosting'
    
    # Inject hidden meta tags inside article for microdata
    meta_html = BeautifulSoup(f'''
        <meta itemprop="headline" content="{title}">
        <meta itemprop="datePublished" content="{iso_date}">
        <meta itemprop="dateModified" content="{iso_date}">
        <meta itemprop="author" content="Robert Simon">
        <meta itemprop="publisher" content="Robert Simon">
        <meta itemprop="description" content="{meta_desc}">''', 'html.parser')
    
    # Insert after author-byline if present, else at start of article
    byline = article.find('div', class_='author-byline')
    if byline:
        byline.insert_after(meta_html)
    else:
        article.insert(0, meta_html)

def patch_file(filepath):
    filename = os.path.basename(filepath)
    print(f"\nPatching: {filename}")

    with open(filepath, 'r', encoding='utf-8') as f:
        raw_html = f.read()

    soup = BeautifulSoup(raw_html, 'html.parser')

    # ── Extract existing data ──
    h1 = soup.find('h1')
    raw_title = h1.get_text(strip=True) if h1 else ''
    title = clean_title(raw_title)

    if not title:
        # Try <title> tag
        title_tag = soup.find('title')
        if title_tag:
            title = clean_title(title_tag.get_text())
    
    if not title or len(title) < 5:
        print(f"  ⚠️  Could not extract clean title — using filename fallback")
        # Build from filename date
        date_obj = extract_date_from_filename(filename)
        title = f"AI Insights for {date_obj.strftime('%B %Y')}" if date_obj else "AI Insights"

    print(f"  Title: {title}")

    date_obj = extract_date_from_html(soup, filename)
    if not date_obj:
        date_obj = datetime.now()
    iso_date = date_obj.strftime('%Y-%m-%d')
    month_year = date_obj.strftime('%B %Y')
    print(f"  Date: {iso_date}")

    excerpt = extract_excerpt(soup)
    if not excerpt:
        excerpt = f"Monthly AI insights for Canadian business leaders — {month_year} analysis by Robert Simon."
    meta_desc = re.sub(r'\s+', ' ', excerpt).strip()
    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152].rstrip() + '...'
    # Escape quotes for HTML attribute
    meta_desc = meta_desc.replace('"', '&quot;')
    print(f"  Excerpt: {meta_desc[:60]}...")

    # Build canonical URL
    clean_fn = re.sub(r'\.html$', '', filename)
    canonical_url = f"https://www.imetrobert.com/blog/posts/{filename}"
    og_image = "https://www.imetrobert.com/blog/og-blog.jpg"

    # Slug keywords from title
    slug_keywords = title.lower().replace('ai insights for ', '').replace(' ', ', ')

    # ── Strip old <head> content (keep <link> for fonts and <style>) ──
    head = soup.find('head')
    if not head:
        print(f"  ⚠️  No <head> found, skipping")
        return False

    # Remove all existing meta, title, link (except fonts + favicon), script tags from head
    tags_to_remove = []
    for tag in head.children:
        if hasattr(tag, 'name'):
            if tag.name == 'title':
                tags_to_remove.append(tag)
            elif tag.name == 'meta':
                tags_to_remove.append(tag)
            elif tag.name == 'link':
                href = tag.get('href', '')
                # Keep font and favicon links, remove canonical/others we'll re-add
                if 'fonts.googleapis' not in href and 'favicon' not in href:
                    tags_to_remove.append(tag)
            elif tag.name == 'script':
                src = tag.get('src', '')
                # Remove GA tags (we'll re-add in correct order) but keep inline scripts that aren't GA
                if 'googletagmanager' in src or ('gtag' in (tag.string or '') and 'dataLayer' in (tag.string or '')):
                    tags_to_remove.append(tag)
    
    for tag in tags_to_remove:
        tag.decompose()

    # ── Build new SEO meta block ──
    new_meta_block = build_seo_head(title, meta_desc, canonical_url, iso_date, og_image, month_year, slug_keywords)
    
    # Insert at very start of head
    meta_soup = BeautifulSoup(new_meta_block, 'html.parser')
    
    # Find first remaining child of head to insert before
    first_child = None
    for child in head.children:
        if hasattr(child, 'name'):
            first_child = child
            break
    
    if first_child:
        first_child.insert_before(meta_soup)
    else:
        head.append(meta_soup)

    # Also append GA tag at end of head
    ga_soup = BeautifulSoup(GA_TAG, 'html.parser')
    head.append(ga_soup)

    # ── Add html lang attribute ──
    html_tag = soup.find('html')
    if html_tag:
        html_tag['lang'] = 'en-CA'

    # ── Add itemprop microdata to article ──
    add_itemprop_to_article(soup, title, meta_desc, iso_date, canonical_url)

    # ── Inject author byline ──
    inject_author_byline(soup)

    # ── Write patched file ──
    output = str(soup)
    
    # Clean up any double charset metas that BS4 sometimes adds
    output = re.sub(r'<meta charset="utf-8"/>\s*<meta charset="UTF-8"/>', '<meta charset="UTF-8"/>', output, flags=re.IGNORECASE)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"  ✅ Patched successfully")
    return True

def main():
    posts_dir = 'blog/posts'
    
    if not os.path.exists(posts_dir):
        print(f"❌ Directory not found: {posts_dir}")
        print("   Run this script from your repo root directory.")
        return

    # Files to patch — exclude template artifacts and latest.html (regenerated by workflow)
    html_files = [
        f for f in os.listdir(posts_dir)
        if f.endswith('.html')
        and f != 'latest.html'       # regenerated on next run
        and not f.startswith('{')    # exclude template artifact
        and '{' not in f
        and f != 'index.html'
    ]

    if not html_files:
        print("No eligible HTML files found in blog/posts/")
        return

    print(f"Found {len(html_files)} posts to patch:")
    for f in sorted(html_files):
        print(f"  - {f}")

    patched = 0
    failed = 0
    for filename in sorted(html_files):
        filepath = os.path.join(posts_dir, filename)
        try:
            success = patch_file(filepath)
            if success:
                patched += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Error patching {filename}: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"✅ Patched: {patched} files")
    if failed:
        print(f"❌ Failed:  {failed} files")
    print(f"\nNext steps:")
    print(f"  1. git add blog/posts/")
    print(f"  2. git commit -m 'Retrofit SEO meta tags on existing posts'")
    print(f"  3. git push")
    print(f"  4. Create blog/og-blog.jpg (1200x630px) in Canva")
    print(f"  5. Run monthly-blog workflow manually to refresh blog/index.html and latest.html")

if __name__ == '__main__':
    main()
