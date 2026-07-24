"""
renderer.py
Builds the HTML blog post from parsed content sections.
"""

import re
import json
from datetime import datetime
from html import escape as escape_html
from utils import clean_filename, estimate_reading_time, get_issue_number, get_issue_labels
from parser import parse_sections, parse_list_items, parse_developments, parse_spotlight_items, parse_adoption_stats, deduplicate_spotlight_against_developments


def create_html_blog_post(content, title, excerpt, coverage_date=None):
    current_date   = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    iso_date       = current_date.strftime("%Y-%m-%d")

    # issue_month_year = the label readers see (never looks stale).
    # coverage_month_year/name = the month the actual news is from.
    # coverage_date lets a regeneration stay locked to the ORIGINAL month
    # being reported on, even if it's run days later — see
    # utils.get_issue_labels() for the full story.
    labels               = get_issue_labels(coverage_date or current_date)
    issue_month_year     = labels["issue_month_year"]
    coverage_month_year  = labels["coverage_month_year"]
    coverage_month_name  = labels["coverage_month_name"]
    issue_badge_text     = labels["issue_badge_text"]

    # Pass the ISSUE date (not real "now") so regenerating a couple days
    # after the calendar rolls over doesn't bump the issue number.
    issue_num      = get_issue_number(labels["issue_date"])
    reading_time   = estimate_reading_time(content)

    clean_title = re.sub(r'^[#\*\s]+', '', title).strip() or f"AI Insights for {issue_month_year}"
    slug        = clean_filename(clean_title)
    canonical   = f"https://www.imetrobert.com/blog/posts/{iso_date}-{slug}.html"
    og_image    = "https://www.imetrobert.com/blog/og-blog.jpg"

    meta_desc = re.sub(r'\s+', ' ', excerpt).strip()
    if len(meta_desc) > 155:
        truncated = meta_desc[:152]
        if ' ' in truncated:
            truncated = truncated[:truncated.rfind(' ')]
        meta_desc = truncated.rstrip('.,;:- ') + '...'

    # Raw (unescaped) versions go into JSON-LD via json.dumps, which does its
    # own string escaping. HTML-escaped versions go everywhere else — meta
    # tag attributes and text nodes — so a quote or ampersand in the
    # AI-generated excerpt/title (e.g. a quoted strategy name) can't truncate
    # or corrupt the surrounding markup.
    meta_desc_html    = escape_html(meta_desc, quote=True)
    clean_title_html  = escape_html(clean_title, quote=True)
    excerpt_html      = escape_html(re.sub(r'\s+', ' ', excerpt).strip(), quote=True)
    seo_title         = f"{clean_title_html} | AI News for Canadian Business | Robert Simon"

    sections = parse_sections(content)

    intro_text      = sections.get("INTRODUCTION", "")
    canadian_spot   = sections.get("CANADIAN SPOTLIGHT", "")
    business_impact = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    roberts_raw     = sections.get("ROBERTS TAKE", "")
    adoption_raw    = sections.get("ADOPTION SNAPSHOT", "")

    developments    = parse_developments(sections.get("KEY AI DEVELOPMENTS", ""))
    spotlight_items = parse_spotlight_items(canadian_spot)
    spotlight_items = deduplicate_spotlight_against_developments(spotlight_items, developments)
    actions         = parse_list_items(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""), min_length=40)
    adoption        = parse_adoption_stats(adoption_raw)

    print(f"  Parsed: {len(developments)} developments, {len(spotlight_items)} spotlight, {len(actions)} actions, {len(adoption)} stats")

    article_parts = []

    if intro_text:
        article_parts.append(
            f'<div class="section intro-section">'
            f'<p class="intro-lead">{intro_text}</p>'
            f'</div>'
        )

    if developments:
        dev_cards = ""
        for d in developments:
            date_html    = f'<span class="dev-date">{d["date"]}</span>' if d["date"] else ""
            company_html = f'<div class="dev-company">{d["company"]}</div>' if d["company"] else ""
            source_html  = ""
            if d.get("source_url"):
                src_label = d.get("source_name") or "Source"
                source_html = (
                    f'<div class="dev-source">'
                    f'<a href="{d["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this article">'
                    f'🔍 {src_label}'
                    f'</a></div>'
                )
            dev_cards += (
                f'<div class="dev-card">'
                f'  <div class="dev-header">{date_html}{company_html}</div>'
                f'  <p class="dev-body">{d["body"]}</p>'
                f'  {source_html}'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section">'
            f'<h2 class="section-title">Key AI Developments This Month</h2>'
            f'<div class="dev-grid">{dev_cards}</div>'
            f'</div>'
        )

    if spotlight_items:
        spot_cards = ""
        for item in spotlight_items:
            org_html = f'<div class="spot-org">{item["org"]}</div>' if item["org"] else ""
            source_html = ""
            if item.get("source_url"):
                src_label = item.get("source_name") or "Source"
                source_html = (
                    f'<div class="spot-source">'
                    f'<a href="{item["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this article">'
                    f'🔍 {src_label}'
                    f'</a></div>'
                )
            spot_cards += (
                f'<li>'
                f'<span class="spot-bullet">🍁</span>'
                f'<div class="spot-content">'
                f'{org_html}'
                f'<div class="spot-body">{item["body"]}</div>'
                f'{source_html}'
                f'</div>'
                f'</li>\n'
            )
        article_parts.append(
            f'<div class="section canada-section">'
            f'<div class="canada-header"><span class="canada-label">Canadian Spotlight</span></div>'
            f'<h2 class="section-title canada-title">What\'s Happening in Canada</h2>'
            f'<ul class="spot-list">{spot_cards}</ul>'
            f'</div>'
        )
    elif canadian_spot and len(canadian_spot) > 60:
        article_parts.append(
            f'<div class="section canada-section">'
            f'<div class="canada-header"><span class="canada-label">Canadian Spotlight</span></div>'
            f'<h2 class="section-title canada-title">What\'s Happening in Canada</h2>'
            f'<p>{canadian_spot}</p>'
            f'</div>'
        )

    if business_impact:
        paras = [p.strip() for p in business_impact.split('\n\n') if len(p.strip()) > 40]
        if not paras:
            paras = [p.strip() for p in business_impact.split('\n') if len(p.strip()) > 40]
        if not paras:
            paras = [business_impact.strip()]
        paras_html = "\n".join(f'<p>{p}</p>' for p in paras)
        article_parts.append(
            f'<div class="section impact-section">'
            f'<h2 class="section-title">What This Means for Canadian Business</h2>'
            f'{paras_html}'
            f'</div>'
        )

    if actions:
        action_cards = ""
        for i, a in enumerate(actions[:5]):
            action_cards += (
                f'<div class="action-card">'
                f'  <div class="action-num">{i+1}</div>'
                f'  <div class="action-body">{a}</div>'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section actions-section">'
            f'<h2 class="section-title">Strategic Actions for This Month</h2>'
            f'<div class="actions-grid">{action_cards}</div>'
            f'</div>'
        )

    if adoption:
        stat_items_html = ""
        for item in adoption:
            if item["stat_number"] and item["stat_text"] and item["stat_number"] in item["stat_text"]:
                highlighted = item["stat_text"].replace(
                    item["stat_number"],
                    f'<span class="stat-highlight">{item["stat_number"]}</span>',
                    1
                )
                stat_content = f'<p class="stat-text">{highlighted}</p>'
            elif item["stat_number"]:
                stat_content = f'<p class="stat-text"><span class="stat-highlight">{item["stat_number"]}</span> {item["stat_text"]}</p>'
            else:
                stat_content = f'<p class="stat-text">{item["stat_text"]}</p>'

            src_html = ""
            if item.get("source_url"):
                src_html = (
                    f'<div class="stat-source">'
                    f'<a href="{item["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this statistic">'
                    f'🔍 {item["source_name"]}'
                    f'</a></div>'
                )
            elif item.get("source_name"):
                src_html = f'<div class="stat-source-plain">{item["source_name"]}</div>'

            stat_items_html += (
                f'<div class="stat-item">'
                f'  {stat_content}'
                f'  {src_html}'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section adoption-section">'
            f'<h2 class="section-title">Canadian AI Adoption Snapshot</h2>'
            f'<div class="stat-grid">{stat_items_html}</div>'
            f'<p class="stat-note">Sources: Statistics Canada, BDC, ISED, Vector Institute, '
            f'Conference Board of Canada, Mila.</p>'
            f'</div>'
        )

    article_parts.append(_build_roberts_take(roberts_raw, coverage_month_year))

    article_html = "\n".join(article_parts)

    faq_qs = [
        f"What AI developments matter most for Canadian businesses in {coverage_month_year}?",
        "What should Canadian executives do about AI right now?",
        "How is AI adoption tracking across Canada?",
        "What Canadian AI companies or initiatives should I know about?",
        "How do global AI trends affect Canadian competitiveness?",
    ]
    faq_items = []
    for i, action in enumerate(actions[:5]):
        faq_items.append({"question": faq_qs[i], "answer": action[:500]})

    faq_schema = ""
    if faq_items:
        faq_schema_items = ',\n'.join([
            f'{{"@type":"Question","name":{json.dumps(f["question"])},'
            f'"acceptedAnswer":{{"@type":"Answer","text":{json.dumps(f["answer"])}}}}}'
            for f in faq_items
        ])
        faq_schema = f"""    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [{faq_schema_items}]
    }}
    </script>"""

    html = f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc_html}">
    <meta name="keywords" content="AI Canada {issue_month_year}, Canadian AI news, artificial intelligence Canada, AI business strategy Canada, AI adoption Canada, Montreal AI, Canadian digital transformation, AI news for Canadians, AI insights {issue_month_year}, {coverage_month_year} AI recap">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
    <meta name="language" content="en-CA">
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">
    <link rel="canonical" href="{canonical}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{clean_title_html} | AI Insights for Canadian Business">
    <meta property="og:description" content="{meta_desc_html}">
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
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{clean_title_html} | AI News for Canadian Business">
    <meta name="twitter:description" content="{meta_desc_html}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <meta name="twitter:site" content="@thedigitalrobert">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": {json.dumps(clean_title)},
      "description": {json.dumps(meta_desc)},
      "datePublished": "{iso_date}",
      "dateModified": "{iso_date}",
      "author": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "jobTitle": "AI Thought Leader & Digital Transformation Expert",
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }},
      "publisher": {{"@type": "Person", "name": "Robert Simon", "url": "https://www.imetrobert.com"}},
      "mainEntityOfPage": {{"@type": "WebPage", "@id": {json.dumps(canonical)}}},
      "url": {json.dumps(canonical)},
      "image": {json.dumps(og_image)},
      "inLanguage": "en-CA",
      "about": [
        {{"@type": "Thing", "name": "Artificial Intelligence"}},
        {{"@type": "Thing", "name": "Canadian Business"}},
        {{"@type": "Place", "name": "Canada"}}
      ],
      "keywords": "AI Canada, artificial intelligence Canada, Canadian business AI, AI news Montreal, AI strategy Canada, digital transformation Canada"
    }}
    </script>
{faq_schema}
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.imetrobert.com"}},
        {{"@type": "ListItem", "position": 2, "name": "AI Insights Blog", "item": "https://www.imetrobert.com/blog/"}},
        {{"@type": "ListItem", "position": 3, "name": {json.dumps(clean_title)}, "item": {json.dumps(canonical)}}}
      ]
    }}
    </script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --blue:        #2563eb;
            --blue-dark:   #1d4ed8;
            --cyan:        #06b6d4;
            --navy:        #0f172a;
            --gray-dark:   #1e293b;
            --gray:        #475569;
            --gray-light:  #94a3b8;
            --surface:     #f8fafc;
            --border:      #e2e8f0;
            --white:       #ffffff;
            --canada-red:  #dc2626;
            --green:       #16a34a;
            --amber:       #d97706;
            --shadow-sm:   0 1px 3px rgb(0 0 0 / 0.08);
            --shadow-md:   0 4px 16px rgb(0 0 0 / 0.08);
            --shadow-lg:   0 8px 32px rgb(0 0 0 / 0.10);
        }}
        *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%); color: var(--navy); line-height: 1.6; -webkit-font-smoothing: antialiased; }}
        .nav-bar {{ background: var(--white); padding: 0.875rem 0; box-shadow: var(--shadow-sm); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid var(--border); }}
        .nav-content {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }}
        .nav-link {{ color: var(--white); text-decoration: none; font-weight: 600; padding: 0.4rem 1rem; font-size: 0.8rem; border-radius: 20px; background: linear-gradient(135deg, var(--blue), var(--cyan)); transition: all 0.2s; letter-spacing: 0.01em; flex-shrink: 0; }}
        .nav-link:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgb(37 99 235 / 0.3); }}
        .nav-meta {{ font-size: 0.78rem; color: var(--gray-light); display: flex; align-items: center; gap: 0.5rem; }}
        .header {{ background: linear-gradient(135deg, var(--blue) 0%, #1a7fb5 50%, var(--cyan) 100%); color: var(--white); padding: 4rem 0 3.5rem; text-align: center; position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; inset: 0; background: radial-gradient(circle at 15% 85%, rgba(255,255,255,0.07) 0%, transparent 45%), radial-gradient(circle at 85% 15%, rgba(255,255,255,0.05) 0%, transparent 45%); pointer-events: none; }}
        .header-content {{ max-width: 780px; margin: 0 auto; padding: 0 1.5rem; position: relative; z-index: 1; }}
        .issue-badge {{ display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); padding: 0.3rem 0.9rem; border-radius: 20px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 1.25rem; }}
        .issue-badge-coverage {{ font-weight: 500; opacity: 0.75; letter-spacing: 0.04em; }}
        .header h1 {{ font-size: clamp(1.75rem, 4.5vw, 2.6rem); font-weight: 800; line-height: 1.15; margin-bottom: 0.6rem; letter-spacing: -0.02em; }}
        .header .subtitle {{ font-size: 0.95rem; font-weight: 500; opacity: 0.85; margin-bottom: 1rem; }}
        .header .intro-text {{ font-size: 0.925rem; opacity: 0.8; max-width: 640px; margin: 0 auto 1.25rem; line-height: 1.65; }}
        .reading-badge {{ display: inline-flex; align-items: center; gap: 0.3rem; background: rgba(255,255,255,0.12); padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.72rem; font-weight: 500; opacity: 0.85; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
        .article-card {{ background: var(--white); border-radius: 20px; box-shadow: var(--shadow-lg); overflow: hidden; border: 1px solid rgba(226,232,240,0.6); }}
        .breadcrumb {{ font-size: 0.72rem; color: var(--gray-light); padding: 0.65rem 2rem; background: var(--surface); border-bottom: 1px solid var(--border); }}
        .breadcrumb a {{ color: var(--blue); text-decoration: none; }}
        .author-byline {{ display: flex; align-items: center; gap: 0.875rem; padding: 1rem 2rem; border-bottom: 1px solid var(--border); background: var(--surface); }}
        .author-byline img {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 2px solid var(--border); }}
        .author-name  {{ font-weight: 700; color: var(--navy); font-size: 0.875rem; }}
        .author-role  {{ font-size: 0.75rem; color: var(--gray-light); margin-top: 0.1rem; }}
        .article-content {{ padding: 2.25rem 2rem; }}
        .section {{ margin-bottom: 3rem; }}
        .section-title {{ font-size: 1.2rem; font-weight: 700; color: var(--navy); margin-bottom: 1.25rem; padding-left: 0.875rem; position: relative; letter-spacing: -0.01em; }}
        .section-title::before {{ content: ''; position: absolute; left: 0; top: 0.1rem; bottom: 0.1rem; width: 3px; background: linear-gradient(to bottom, var(--blue), var(--cyan)); border-radius: 2px; }}
        .intro-section {{ border-left: 3px solid var(--cyan); padding-left: 1.25rem; }}
        .intro-lead {{ font-size: 1.05rem; line-height: 1.75; color: var(--gray-dark); font-weight: 400; }}
        .dev-grid {{ display: grid; gap: 0.75rem; }}
        .dev-card {{ padding: 1rem 1.25rem; border: 1px solid var(--border); border-radius: 12px; transition: border-color 0.2s, box-shadow 0.2s; border-left: 3px solid var(--blue); background: #fafbff; }}
        .dev-card:hover {{ border-color: var(--blue); box-shadow: var(--shadow-md); background: var(--white); }}
        .dev-header {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.4rem; flex-wrap: wrap; }}
        .dev-date {{ display: inline-block; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: var(--white); font-size: 0.65rem; font-weight: 700; padding: 0.15rem 0.55rem; border-radius: 10px; white-space: nowrap; letter-spacing: 0.03em; }}
        .dev-company {{ font-weight: 700; color: var(--navy); font-size: 0.85rem; }}
        .dev-body {{ font-size: 0.875rem; color: var(--gray); line-height: 1.65; }}
        .dev-source {{ margin-top: 0.5rem; }}
        .dev-source a {{ font-size: 0.72rem; color: var(--blue); text-decoration: none; font-weight: 600; opacity: 0.8; transition: opacity 0.2s; }}
        .dev-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .canada-section {{ background: linear-gradient(135deg, #fff5f5 0%, #fffbfb 100%); border: 1px solid #fecaca; border-radius: 16px; padding: 1.75rem; }}
        .canada-header {{ margin-bottom: 0.75rem; }}
        .canada-label {{ display: inline-flex; align-items: center; gap: 0.35rem; background: var(--canada-red); color: var(--white); font-size: 0.65rem; font-weight: 700; padding: 0.2rem 0.7rem; border-radius: 12px; letter-spacing: 0.06em; text-transform: uppercase; }}
        .canada-label::before {{ content: "🍁"; font-size: 0.75rem; }}
        .canada-title::before {{ background: var(--canada-red) !important; }}
        .spot-list {{ list-style: none; padding: 0; display: grid; gap: 0.875rem; }}
        .spot-list li {{ display: flex; gap: 0.6rem; align-items: flex-start; font-size: 0.875rem; color: var(--gray); line-height: 1.65; padding: 0.875rem 1rem; background: var(--white); border-radius: 10px; border: 1px solid #fde8e8; }}
        .spot-bullet {{ flex-shrink: 0; margin-top: 0.1rem; font-size: 0.85rem; }}
        .spot-content {{ flex: 1; }}
        .spot-org {{ font-weight: 700; color: var(--navy); font-size: 0.85rem; margin-bottom: 0.2rem; }}
        .spot-body {{ font-size: 0.875rem; color: var(--gray); line-height: 1.6; }}
        .spot-source {{ margin-top: 0.4rem; }}
        .spot-source a {{ font-size: 0.72rem; color: var(--canada-red); text-decoration: none; font-weight: 600; opacity: 0.8; transition: opacity 0.2s; }}
        .spot-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .impact-section p {{ font-size: 0.9rem; line-height: 1.8; color: var(--gray); margin-bottom: 1rem; }}
        .impact-section p:last-child {{ margin-bottom: 0; }}
        .actions-grid {{ display: grid; gap: 0.875rem; }}
        .action-card {{ display: flex; gap: 1rem; align-items: flex-start; padding: 1.1rem 1.25rem; background: #f8faff; border: 1px solid #dbeafe; border-radius: 12px; border-left: 3px solid var(--blue); transition: box-shadow 0.2s; }}
        .action-card:hover {{ box-shadow: var(--shadow-md); background: var(--white); }}
        .action-num {{ display: flex; align-items: center; justify-content: center; width: 1.75rem; height: 1.75rem; min-width: 1.75rem; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: var(--white); font-size: 0.72rem; font-weight: 800; border-radius: 50%; margin-top: 0.1rem; }}
        .action-body {{ font-size: 0.875rem; color: var(--gray-dark); line-height: 1.7; flex: 1; }}
        .stat-grid {{ display: grid; gap: 0.75rem; }}
        .stat-item {{ padding: 1rem 1.25rem; background: #f0fdf4; border-left: 3px solid var(--green); border-radius: 0 10px 10px 0; }}
        .stat-text {{ font-size: 0.875rem; color: var(--gray-dark); line-height: 1.65; }}
        .stat-highlight {{ font-weight: 800; color: var(--green); font-size: 1rem; }}
        .stat-source {{ margin-top: 0.35rem; }}
        .stat-source a {{ font-size: 0.7rem; color: var(--green); text-decoration: none; font-weight: 600; opacity: 0.75; transition: opacity 0.2s; }}
        .stat-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .stat-source-plain {{ font-size: 0.7rem; color: var(--gray-light); margin-top: 0.35rem; }}
        .stat-note {{ font-size: 0.72rem; color: var(--gray-light); margin-top: 0.875rem; font-style: italic; }}
        .roberts-take {{ background: linear-gradient(135deg, #1e3a6e 0%, #1a5276 100%); border-radius: 16px; padding: 1.75rem; color: var(--white); }}
        .roberts-header {{ display: flex; align-items: center; gap: 0.875rem; margin-bottom: 1.1rem; padding-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.12); }}
        .roberts-header img {{ width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,0.25); flex-shrink: 0; }}
        .roberts-label {{ font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; margin-bottom: 0.1rem; }}
        .roberts-name {{ font-weight: 700; font-size: 0.9rem; }}
        .roberts-body {{ font-size: 0.925rem; line-height: 1.85; color: #ffffff; font-style: normal; font-weight: 400; }}
        .roberts-placeholder {{ font-size: 0.825rem; line-height: 1.7; opacity: 0.65; border: 1px dashed rgba(255,255,255,0.25); padding: 1rem 1.25rem; border-radius: 10px; }}
        .roberts-placeholder strong {{ color: var(--white); opacity: 1; font-style: normal; }}
        .conclusion {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: var(--white); padding: 2rem; border-radius: 14px; margin-top: 2.5rem; }}
        .conclusion-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.75; margin-bottom: 0.5rem; }}
        .conclusion p {{ color: rgba(255,255,255,0.95); font-size: 0.95rem; font-weight: 500; line-height: 1.75; }}
        .conclusion strong {{ color: var(--white); font-weight: 700; }}
        p {{ margin-bottom: 1rem; line-height: 1.75; color: var(--gray); font-size: 0.9rem; }}
        strong {{ color: var(--navy); font-weight: 600; }}
        @media (max-width: 640px) {{
            .header {{ padding: 2.5rem 0 2.25rem; }}
            .header h1 {{ font-size: 1.6rem; }}
            .container {{ padding: 1.5rem 1rem 3rem; }}
            .article-content {{ padding: 1.5rem 1.25rem; }}
            .nav-content {{ flex-direction: column; align-items: flex-start; gap: 0.35rem; }}
            .author-byline {{ padding: 0.875rem 1.25rem; }}
            .breadcrumb {{ padding: 0.5rem 1.25rem; }}
            .canada-section {{ padding: 1.25rem; }}
            .action-card {{ flex-direction: column; gap: 0.6rem; }}
            .action-num {{ width: 1.5rem; height: 1.5rem; min-width: 1.5rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">&#8592; Back to Blog</a>
            <div class="nav-meta">
                <span>AI Insights for Canadian Business</span>
                <span>&#8226;</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>
    <header class="header">
        <div class="header-content">
            <div class="issue-badge">Issue #{issue_num} &nbsp;&#8226;&nbsp; {issue_month_year} <span class="issue-badge-coverage">&mdash; Covering {coverage_month_name}</span></div>
            <h1>{clean_title_html}</h1>
            <div class="subtitle">The AI briefing built for Canadian business leaders</div>
            <div class="intro-text">{excerpt_html}</div>
            <div class="reading-badge">&#9201; {reading_time} min read</div>
        </div>
    </header>
    <div class="container">
        <article class="article-card" itemscope itemtype="https://schema.org/BlogPosting">
            <meta itemprop="headline"      content="{clean_title_html}">
            <meta itemprop="datePublished" content="{iso_date}">
            <meta itemprop="dateModified"  content="{iso_date}">
            <meta itemprop="author"        content="Robert Simon">
            <meta itemprop="description"   content="{meta_desc_html}">
            <nav class="breadcrumb" aria-label="Breadcrumb">
                <a href="https://www.imetrobert.com">Home</a> &#8250;
                <a href="https://www.imetrobert.com/blog/">AI Insights Blog</a> &#8250;
                <span>{clean_title_html}</span>
            </nav>
            <div class="author-byline">
                <img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon" loading="lazy">
                <div>
                    <div class="author-name">Robert Simon</div>
                    <div class="author-role">AI Thought Leader &amp; Digital Transformation Expert &mdash; Montreal, QC</div>
                </div>
            </div>
            <div class="article-content" itemprop="articleBody">
                {article_html}
                <div class="conclusion">
                    <div class="conclusion-label">The Bottom Line</div>
                    <p>{_build_conclusion(sections, coverage_month_year)}</p>
                </div>
            </div>
        </article>
    </div>
</body>
</html>'''

    return html


def _build_roberts_take(raw_text, coverage_month_year):
    is_placeholder = (
        not raw_text
        or 'PLACEHOLDER' in raw_text.upper()
        or '[PLACEHOLDER' in raw_text
        or len(raw_text.strip()) < 40
    )

    header = (
        '<div class="roberts-header">'
        '<img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon">'
        '<div>'
        '<div class="roberts-label">Editor\'s Note</div>'
        '<div class="roberts-name">Robert\'s Take</div>'
        '</div>'
        '</div>'
    )

    if is_placeholder:
        body = (
            '<div class="roberts-placeholder">'
            '<strong>&#9998; Add your personal take before publishing.</strong><br><br>'
            'What surprised you most this month? What are you hearing from Canadian leaders right now? '
            'What is the pattern others are missing? 2-3 sentences in your own voice — '
            'this is the E-E-A-T signal that makes this newsletter yours.'
            '</div>'
        )
    else:
        cleaned = raw_text.strip()
        cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned, flags=re.DOTALL).strip()
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)
        cleaned = cleaned.replace('"', '&quot;').replace("'", '&#39;')
        body = f'<p class="roberts-body">&#8220;{cleaned}&#8221;</p>'

    return f'<div class="section"><div class="roberts-take">{header}{body}</div></div>'


def _build_conclusion(sections, coverage_month_year):
    impact  = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    actions = parse_list_items(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""), min_length=40)

    if impact:
        sentences = re.split(r'(?<=[.!?])\s+', impact.strip())
        if sentences:
            base = sentences[-1].strip()
            if base and len(base) > 40:
                return (
                    f"{base} The organizations that act on this month's intelligence "
                    f"will set the AI standard in their sector for the next 12 months."
                )

    if actions:
        return (
            f"With {len(actions)} clear priorities this month, Canadian leaders have no shortage of direction. "
            f"The gap between organizations that act and those that wait is growing every month."
        )

    return (
        f"The {coverage_month_year} AI landscape demands decisive action from Canadian business leaders. "
        f"Strategy documents are not enough — execution is the only differentiator now."
    )
