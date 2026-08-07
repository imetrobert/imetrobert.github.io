"""
renderer.py
Builds the HTML blog post from parsed content sections.
"""

import re
import json
from datetime import datetime
from html import escape as escape_html
from urllib.parse import quote
from utils import clean_filename, estimate_reading_time, get_issue_number, get_issue_labels
from parser import (
    parse_sections, parse_list_items, parse_developments, parse_spotlight_items,
    parse_adoption_stats, deduplicate_spotlight_against_developments,
    parse_actions, parse_myth, parse_predictions, parse_question,
)


def create_html_blog_post(content, title, excerpt, coverage_date=None, is_draft=False):
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
    word_count     = len(re.sub(r'\s+', ' ', content).split())

    clean_title = re.sub(r'^[#\*\s]+', '', title).strip() or f"AI Insights for {issue_month_year}"
    slug        = clean_filename(clean_title)
    canonical   = f"https://www.imetrobert.com/blog/posts/{iso_date}-{slug}.html"
    # Per-issue social card. Falls back to the static one rather than risking a
    # 404 og:image if Pillow or the fonts are unavailable in the runner.
    og_image    = "https://www.imetrobert.com/blog/og-blog.jpg"
    og_alt      = f"AI Insights for Canadian Business \u2014 {issue_month_year} issue by Robert Simon"
    try:
        import os as _os
        from og_image import build_og_image
        _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _rel  = f"blog/og/{iso_date}-{slug}.jpg"
        build_og_image(_os.path.join(_root, _rel), issue_month_year)
        og_image = f"https://www.imetrobert.com/{_rel}"
    except Exception as _e:
        print(f"  OG image generation unavailable ({_e}); using the static card")
    # Drafts sitting in blog/staging/ must never be indexable — the URL
    # differs from the eventual blog/posts/ URL, so a crawler that found a
    # draft before approval would leave a stale, permanent entry in search
    # results with no path to ever clean it up. Canonical still points to
    # the eventual published URL either way (see `canonical` above).
    robots_meta = (
        "noindex, nofollow"
        if is_draft else
        "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
    )

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
    # Topic first: the front of the title carries the most retrieval weight, and
    # it is what survives truncation in a SERP. Month second for freshness and
    # issue identity, brand last.
    seo_title         = f"{clean_title_html} | AI Insights {issue_month_year} | Robert Simon"

    sections = parse_sections(content)

    intro_text      = sections.get("INTRODUCTION", "")
    canadian_spot   = sections.get("CANADIAN SPOTLIGHT", "")
    business_impact = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    roberts_raw     = sections.get("FROM ROBERTS DESK", "")
    adoption_raw    = sections.get("ADOPTION SNAPSHOT", "")

    developments    = parse_developments(sections.get("KEY AI DEVELOPMENTS", ""))
    spotlight_items = parse_spotlight_items(canadian_spot)
    spotlight_items = deduplicate_spotlight_against_developments(spotlight_items, developments)
    actions         = parse_actions(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""))
    adoption        = parse_adoption_stats(adoption_raw)
    summary_points  = parse_list_items(sections.get("EXECUTIVE SUMMARY", ""), min_length=25)[:3]
    myth            = parse_myth(sections.get("AI MYTH OF THE MONTH", ""))
    predictions     = parse_predictions(sections.get("LOOKING AHEAD: THREE PREDICTIONS", ""))
    closing_question = parse_question(sections.get("ONE QUESTION FOR YOUR LEADERSHIP TEAM", ""))

    # Action bodies are what the FAQ and the conclusion quote; they should never
    # carry the OWNER/PRIORITY labels into prose meant to be read as a sentence.
    action_bodies   = [a["body"] for a in actions]

    print(f"  Parsed: {len(developments)} developments, {len(spotlight_items)} spotlight, "
          f"{len(actions)} actions, {len(adoption)} stats, {len(summary_points)} summary points, "
          f"{len(predictions)} predictions, myth={'yes' if myth else 'no'}, "
          f"question={'yes' if closing_question else 'no'}")
    desk_words = len(roberts_raw.split())
    if desk_words < 200:
        print(f"  NOTE: From Robert's Desk is only {desk_words} words — the signature "
              f"section is meant to run 300-450. Consider rewriting it in the preview page.")

    article_parts = []

    if intro_text:
        article_parts.append(
            f'<div class="section intro-section">'
            f'<p class="intro-lead">{intro_text}</p>'
            f'</div>'
        )

    if summary_points:
        points_html = "".join(f'<li>{p}</li>' for p in summary_points)
        article_parts.append(
            f'<div class="section summary-section">'
            f'<div class="summary-label">Executive Summary</div>'
            f'<ul class="summary-list">{points_html}</ul>'
            f'</div>'
        )

    if developments:
        # Two tiers. A development the model rated is a major story and gets the
        # full treatment; the rest are the log. The split is driven by whether
        # the ratings are actually present, so a month where the model rates
        # nothing degrades to the old flat list instead of rendering empty
        # badge rows.
        major   = [d for d in developments if d.get("strategic_read") or d.get("importance")]
        minor   = [d for d in developments if d not in major]
        dev_cards = ""

        for d in major:
            date_html    = f'<span class="dev-date">{d["date"]}</span>' if d["date"] else ""
            company_html = f'<div class="dev-company">{d["company"]}</div>' if d["company"] else ""
            dev_cards += (
                f'<div class="dev-card dev-card-major">'
                f'  <div class="dev-header">{date_html}{company_html}'
                f'<span class="dev-tier">Major story</span></div>'
                f'  <p class="dev-body">{d["body"]}</p>'
                f'  {_build_strategic_read(d)}'
                f'  {_build_rating_row(d)}'
                f'  {_build_dev_source(d)}'
                f'</div>\n'
            )

        if minor:
            # "Also worth knowing" only means something when there is something
            # above it. If the model rated nothing this month, every item is in
            # this list, and the subordinate framing plus the de-emphasised card
            # style would present the entire section as a footnote.
            demote = bool(major)
            minor_rows = ""
            for d in minor:
                date_html = f'<span class="dev-date">{d["date"]}</span>' if d["date"] else ""
                company_html = f'<span class="dev-company">{d["company"]}</span>' if d["company"] else ""
                minor_rows += (
                    f'<div class="dev-card{" dev-card-minor" if demote else ""}">'
                    f'  <div class="dev-header">{date_html}{company_html}</div>'
                    f'  <p class="dev-body">{d["body"]}</p>'
                    f'  {_build_dev_source(d)}'
                    f'</div>\n'
                )
            dev_cards += (
                f'<div class="dev-log">'
                f'<div class="dev-log-label">Also worth knowing</div>'
                f'{minor_rows}'
                f'</div>'
            ) if demote else minor_rows

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
                    f'<svg class="icon" aria-hidden="true"><use href="#i-search"/></svg> {src_label}'
                    f'</a></div>'
                )
            spot_cards += (
                f'<li>'
                f'<span class="spot-bullet"><svg class="icon icon-solid" aria-hidden="true"><use href="#i-diamond"/></svg></span>'
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

    # The signature section sits here on purpose — immediately after the facts
    # and before the analysis that leans on them, at the point in the page where
    # attention is still high. It used to close the issue, which is exactly
    # where a reader who skims stops reading.
    article_parts.append(_build_roberts_desk(roberts_raw))

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
            owner_html = ""
            if a.get("owner"):
                rationale = (
                    f'<div class="action-owner-why">{a["owner_rationale"]}</div>'
                    if a.get("owner_rationale") else ""
                )
                owner_html = (
                    f'<div class="action-owner">'
                    f'<span class="action-owner-label">Owner</span>'
                    f'<span class="action-owner-role">{a["owner"]}</span>'
                    f'{rationale}'
                    f'</div>'
                )
            action_cards += (
                f'<div class="action-card">'
                f'  <div class="action-num">{i+1}</div>'
                f'  <div class="action-main">'
                f'    <div class="action-body">{a["body"]}</div>'
                f'    {owner_html}'
                f'    {_build_action_meta(a)}'
                f'  </div>'
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
                    f'<svg class="icon" aria-hidden="true"><use href="#i-search"/></svg> {item["source_name"]}'
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

    if myth:
        article_parts.append(
            f'<div class="section myth-section">'
            f'<div class="myth-label">AI Myth of the Month</div>'
            f'<div class="myth-block myth-claim">'
            f'<span class="myth-tag">Myth</span><p>{myth["myth"]}</p></div>'
            f'<div class="myth-block myth-reality">'
            f'<span class="myth-tag">Reality</span><p>{myth["reality"]}</p></div>'
            f'</div>'
        )

    if predictions:
        pred_html = "".join(
            f'<div class="pred-card">'
            f'<div class="pred-horizon">{p["horizon"]}</div>'
            f'<p class="pred-body">{p["body"]}</p>'
            f'</div>'
            for p in predictions
        )
        article_parts.append(
            f'<div class="section pred-section">'
            f'<h2 class="section-title">Looking Ahead</h2>'
            f'<p class="pred-note">These are predictions, not reported facts — '
            f'Robert’s assessment of where this goes next, offered so you can '
            f'judge it against your own.</p>'
            f'<div class="pred-grid">{pred_html}</div>'
            f'</div>'
        )

    # Each question is answered from the section that actually addresses it.
    # Pairing questions against whatever happened to be in `actions` produced
    # confident non-sequiturs — fine while the FAQ was schema-only, actively
    # misleading now that it is on the page and quotable by answer engines.
    def _plain(text, limit=480):
        text = re.sub(r"<[^>]+>", " ", str(text))
        # Answers get quoted verbatim by answer engines, so scrub anything that
        # betrays the source format: bare URLs, the pipe-delimited field syntax
        # the generator emits, markdown headings, and leading list bullets.
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"#{1,6}\s*[A-Z][A-Z '\u2019]*$", "", text)
        text = re.sub(r"^[\s\-\*\u2022]+", "", text)
        text = text.replace(" | ", " \u2014 ")
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"(?:\s*\u2014){2,}", " \u2014", text)          # URL removal can leave a dangling dash
        text = re.sub(r"\s*\u2014\s*$", "", text)
        text = text.strip(" \u2014-#*\u2022 ")
        if len(text) > limit:
            text = text[: limit - 3].rsplit(" ", 1)[0] + "..."
        return text

    def _join(parts, limit=480):
        out = ""
        for part in parts:
            part = _plain(part, limit)
            if not part:
                continue
            candidate = f"{out} {part}".strip() if out else part
            if len(candidate) > limit:
                break
            out = candidate
        return out

    faq_candidates = [
        (
            f"What AI developments matter most for Canadian businesses in {coverage_month_year}?",
            _join([f'{d["company"]}: {d["body"]}' if d.get("company") else d["body"]
                   for d in developments[:3]]),
        ),
        (
            "What should Canadian executives do about AI right now?",
            _join(action_bodies[:3]),
        ),
        (
            "How is AI adoption tracking across Canada?",
            _join([f'{i.get("stat_number", "")} {i.get("stat_text", "")}'.strip()
                   for i in adoption[:3]]),
        ),
        (
            "What Canadian AI companies or initiatives should I know about?",
            _join([f'{i["org"]}: {i["body"]}' if i.get("org") else i["body"]
                   for i in spotlight_items[:3]]),
        ),
        (
            "How do global AI trends affect Canadian competitiveness?",
            _plain(business_impact),
        ),
    ]
    # Only publish a Q&A when the post genuinely contains the answer.
    faq_items = [{"question": q, "answer": a} for q, a in faq_candidates if len(a) > 60]

    # The FAQ must be VISIBLE, not schema-only. Google requires FAQPage content
    # to appear on the page, and an answer engine can only quote what it can
    # read — schema alone gets ignored and risks a structured-data penalty.
    if faq_items:
        faq_html = "".join(
            f'<div class="faq-item">'
            f'<h3 class="faq-q">{f["question"]}</h3>'
            f'<p class="faq-a">{f["answer"]}</p>'
            f'</div>'
            for f in faq_items
        )
        article_parts.append(
            f'<div class="section faq-section">'
            f'<h2 class="section-title">Questions Canadian Leaders Are Asking</h2>'
            f'<div class="faq-list">{faq_html}</div>'
            f'</div>'
        )

    if closing_question:
        article_parts.append(
            f'<div class="section question-section">'
            f'<div class="question-label">One question for your leadership team</div>'
            f'<p class="question-body">{closing_question}</p>'
            f'</div>'
        )

    article_parts.append(_build_survey_cta())
    article_parts.append(_build_prompts_section(canonical, clean_title, issue_month_year))

    article_html = "\n".join(article_parts)

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
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc_html}">
    <meta name="keywords" content="AI Canada {issue_month_year}, Canadian AI news, artificial intelligence Canada, AI business strategy Canada, AI adoption Canada, Montreal AI, Canadian digital transformation, AI news for Canadians, AI insights {issue_month_year}, {coverage_month_year} AI recap">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="{robots_meta}">
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
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="{og_alt}">
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
    <meta name="twitter:image:alt" content="{og_alt}">
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
      "mainEntityOfPage": {{"@type": "WebPage", "@id": {json.dumps(canonical)}}},
      "url": {json.dumps(canonical)},
      "image": {json.dumps(og_image)},
      "inLanguage": "en-CA",
      "about": [
        {{"@type": "Thing", "name": "Artificial Intelligence"}},
        {{"@type": "Thing", "name": "Canadian Business"}},
        {{"@type": "Place", "name": "Canada"}}
      ],
      "keywords": "AI Canada, artificial intelligence Canada, Canadian business AI, AI news Montreal, AI strategy Canada, digital transformation Canada",
      "articleSection": "AI Strategy",
      "wordCount": {word_count},
      "timeRequired": "PT{reading_time}M",
      "isAccessibleForFree": true,
      "speakable": {{
        "@type": "SpeakableSpecification",
        "cssSelector": [".intro-lead", ".faq-q", ".faq-a"]
      }}
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
        .nav-meta .brand-icon {{ width: 22px; height: 22px; border-radius: 7px; flex-shrink: 0; }}
        .brand-logo {{ width: 76px; height: 76px; display: block; margin: 0 auto 1.5rem; padding: 7px; box-sizing: content-box; background: rgba(255,255,255,0.96); border-radius: 23px; box-shadow: 0 10px 26px rgba(15,23,42,0.25); }}
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
        /* Inline SVG icons, sprite defined at the top of <body>. Stroked in
           currentColor and sized in em so each icon matches its adjacent text. */
        .icon {{ width: 1.05em; height: 1.05em; flex-shrink: 0; fill: none; stroke: currentColor; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; vertical-align: -0.14em; }}
        .icon-solid {{ fill: currentColor; stroke: none; }}
        .canada-title::before {{ background: var(--canada-red) !important; }}
        .spot-list {{ list-style: none; padding: 0; display: grid; gap: 0.875rem; }}
        .spot-list li {{ display: flex; gap: 0.6rem; align-items: flex-start; font-size: 0.875rem; color: var(--gray); line-height: 1.65; padding: 0.875rem 1rem; background: var(--white); border-radius: 10px; border: 1px solid #fde8e8; }}
        .spot-bullet {{ flex-shrink: 0; margin-top: 0.35rem; font-size: 0.55rem; color: var(--canada-red); display: flex; }}
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
        .roberts-body + .roberts-body {{ margin-top: 0.9rem; }}
        /* Executive summary — the three things, above the fold. */
        .summary-section {{ background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--navy); border-radius: 12px; padding: 1.4rem 1.6rem; }}
        .summary-label {{ font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: var(--navy); opacity: 0.75; margin-bottom: 0.85rem; }}
        .summary-list {{ list-style: none; padding: 0; display: grid; gap: 0.7rem; counter-reset: summary; }}
        .summary-list li {{ position: relative; padding-left: 1.9rem; font-size: 0.9rem; line-height: 1.6; color: var(--gray-dark); font-weight: 500; counter-increment: summary; }}
        .summary-list li::before {{ content: counter(summary); position: absolute; left: 0; top: 0.05rem; width: 1.3rem; height: 1.3rem; display: flex; align-items: center; justify-content: center; background: var(--navy); color: var(--white); border-radius: 50%; font-size: 0.65rem; font-weight: 800; }}
        /* Major stories carry judgment and ratings; the log below does not. */
        .dev-card-major {{ padding: 1.25rem 1.4rem; }}
        .dev-tier {{ margin-left: auto; font-size: 0.58rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.09em; color: var(--blue); opacity: 0.7; }}
        .dev-read {{ margin-top: 0.85rem; padding: 0.9rem 1.1rem; background: var(--white); border: 1px solid #dbeafe; border-left: 3px solid var(--cyan); border-radius: 0 10px 10px 0; }}
        .dev-read-label {{ display: block; font-size: 0.58rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--cyan); margin-bottom: 0.35rem; }}
        .dev-read p {{ font-size: 0.86rem; line-height: 1.7; color: var(--gray-dark); margin: 0; }}
        .dev-log {{ margin-top: 1.25rem; padding-top: 1.1rem; border-top: 1px dashed var(--border); display: grid; gap: 0.6rem; }}
        .dev-log-label {{ font-size: 0.6rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-light); }}
        .dev-card-minor {{ padding: 0.8rem 1rem; background: var(--white); border-left-color: var(--border); }}
        .dev-card-minor .dev-body {{ font-size: 0.83rem; }}
        .dev-card-minor .dev-company {{ font-size: 0.8rem; }}
        /* Rating badges. Label above value so a badge reads without a legend. */
        .badge-row {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.9rem; }}
        .badge {{ display: inline-flex; flex-direction: column; gap: 0.1rem; padding: 0.35rem 0.7rem; border-radius: 8px; border: 1px solid var(--border); background: var(--white); min-width: 5.5rem; }}
        .badge-label {{ font-size: 0.55rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--gray-light); }}
        .badge-value {{ font-size: 0.8rem; font-weight: 800; color: var(--navy); line-height: 1.2; }}
        .badge.tone-high {{ background: #fff7ed; border-color: #fed7aa; }}
        .badge.tone-high .badge-value {{ color: #c2410c; }}
        .badge.tone-mid {{ background: #eff6ff; border-color: #bfdbfe; }}
        .badge.tone-mid .badge-value {{ color: #1d4ed8; }}
        .badge.tone-low {{ background: var(--surface); border-color: var(--border); }}
        .badge.tone-low .badge-value {{ color: var(--gray); }}
        .badge.tone-neutral .badge-value {{ color: var(--gray-dark); }}
        .badge-row-action {{ margin-top: 0.75rem; }}
        /* Actions: body, then who owns it and why, then the triage badges. */
        .action-main {{ flex: 1; }}
        .action-owner {{ margin-top: 0.75rem; padding: 0.6rem 0.85rem; background: var(--white); border: 1px solid #dbeafe; border-radius: 8px; }}
        .action-owner-label {{ font-size: 0.55rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.09em; color: var(--gray-light); margin-right: 0.45rem; }}
        .action-owner-role {{ font-size: 0.8rem; font-weight: 800; color: var(--navy); }}
        .action-owner-why {{ font-size: 0.78rem; line-height: 1.6; color: var(--gray); margin-top: 0.3rem; }}
        /* Myth of the month. */
        .myth-section {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 16px; padding: 1.6rem 1.75rem; }}
        .myth-label {{ font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: #b45309; margin-bottom: 1rem; }}
        .myth-block {{ display: flex; gap: 0.8rem; align-items: flex-start; padding: 0.9rem 1.1rem; border-radius: 10px; background: var(--white); }}
        .myth-block + .myth-block {{ margin-top: 0.65rem; }}
        .myth-block p {{ margin: 0; font-size: 0.875rem; line-height: 1.7; }}
        .myth-tag {{ flex-shrink: 0; font-size: 0.58rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; padding: 0.22rem 0.55rem; border-radius: 6px; margin-top: 0.15rem; }}
        .myth-claim {{ border: 1px solid #fde68a; }}
        .myth-claim .myth-tag {{ background: #fef3c7; color: #b45309; }}
        .myth-claim p {{ color: var(--gray); }}
        .myth-reality {{ border: 1px solid #bbf7d0; }}
        .myth-reality .myth-tag {{ background: #dcfce7; color: #15803d; }}
        .myth-reality p {{ color: var(--gray-dark); }}
        /* Looking ahead — three predictions, explicitly labelled as such. */
        .pred-note {{ font-size: 0.78rem; color: var(--gray-light); line-height: 1.6; margin-bottom: 1.1rem; font-style: italic; }}
        .pred-grid {{ display: grid; gap: 0.75rem; }}
        .pred-card {{ padding: 1rem 1.25rem; background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--navy); border-radius: 0 10px 10px 0; }}
        .pred-horizon {{ font-size: 0.6rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--navy); opacity: 0.7; margin-bottom: 0.35rem; }}
        .pred-body {{ font-size: 0.875rem; line-height: 1.7; color: var(--gray-dark); margin: 0; }}
        /* The closing question. Deliberately the largest type in the article. */
        .question-section {{ border: 2px solid var(--navy); border-radius: 16px; padding: 1.75rem 2rem; background: var(--white); }}
        .question-label {{ font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: var(--navy); opacity: 0.7; margin-bottom: 0.7rem; }}
        .question-body {{ font-size: 1.15rem; line-height: 1.6; font-weight: 600; color: var(--navy); margin: 0; letter-spacing: -0.01em; }}
        .faq-section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 1.75rem; }}
        .faq-list {{ display: grid; gap: 1rem; }}
        .faq-item {{ padding: 1rem 1.25rem; background: var(--white); border: 1px solid var(--border); border-radius: 12px; border-left: 3px solid var(--blue); }}
        .faq-q {{ font-size: 0.925rem; font-weight: 700; color: var(--navy); margin-bottom: 0.4rem; line-height: 1.45; }}
        .faq-a {{ font-size: 0.875rem; color: var(--gray); line-height: 1.7; margin: 0; }}
        .survey-cta {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: var(--white); border-radius: 16px; padding: 1.75rem; }}
        .survey-cta .section-title {{ color: var(--white); }}
        .survey-cta .section-title::before {{ background: rgba(255,255,255,0.85); }}
        .survey-body {{ font-size: 0.9rem; line-height: 1.75; color: rgba(255,255,255,0.94); margin-bottom: 1.25rem; }}
        .survey-body strong {{ color: var(--white); }}
        .survey-actions {{ display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }}
        .survey-btn {{ display: inline-block; background: var(--white); color: var(--blue); font-weight: 700; font-size: 0.85rem; padding: 0.6rem 1.4rem; border-radius: 25px; text-decoration: none; transition: transform 0.15s; }}
        .survey-btn:hover {{ transform: translateY(-1px); }}
        .survey-results {{ color: rgba(255,255,255,0.92); font-size: 0.8rem; font-weight: 600; text-decoration: underline; }}
        .prompts-section {{ background: linear-gradient(135deg, #f8fafc 0%, #eef4ff 100%); border: 1px solid var(--border); border-radius: 16px; padding: 1.75rem; }}
        .prompts-intro {{ font-size: 0.875rem; color: var(--gray); line-height: 1.7; margin-bottom: 1.25rem; }}
        .prompt-list {{ display: grid; gap: 0.875rem; }}
        .prompt-card {{ background: var(--white); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
        .prompt-head {{ display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.8rem 1rem; border-bottom: 1px solid var(--border); background: var(--surface); }}
        .prompt-label {{ font-weight: 700; font-size: 0.85rem; color: var(--navy); display: block; }}
        .prompt-blurb {{ font-size: 0.75rem; color: var(--gray-light); display: block; margin-top: 0.1rem; }}
        .copy-btn {{ display: inline-flex; align-items: center; gap: 0.4rem; flex-shrink: 0; font: inherit; font-size: 0.78rem; font-weight: 600; color: var(--white); background: linear-gradient(135deg, var(--blue), var(--cyan)); border: none; border-radius: 20px; padding: 0.45rem 0.9rem; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }}
        .copy-btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgb(37 99 235 / 0.3); }}
        .copy-btn.copied {{ background: var(--green); }}
        .prompt-text {{ margin: 0; padding: 1rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; line-height: 1.65; color: var(--gray-dark); white-space: pre-wrap; word-break: break-word; background: var(--white); }}
        .prompt-foot {{ display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem; margin-top: 1.1rem; padding-top: 1.1rem; border-top: 1px dashed var(--border); font-size: 0.8rem; color: var(--gray); }}
        .prompt-foot-note {{ font-size: 0.75rem; color: var(--gray-light); flex-basis: 100%; }}
        .conclusion {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: var(--white); padding: 2rem; border-radius: 14px; margin-top: 2.5rem; }}
        .conclusion-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.75; margin-bottom: 0.5rem; }}
        .conclusion p {{ color: rgba(255,255,255,0.95); font-size: 0.95rem; font-weight: 500; line-height: 1.75; }}
        .conclusion strong {{ color: var(--white); font-weight: 700; }}
        /* Share row. Sits under The Bottom Line — the point at which a reader
           who found the issue useful decides to pass it on. */
        .share-row {{ margin-top: 1.75rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }}
        .share-label {{ font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: var(--gray-light); margin-bottom: 0.8rem; }}
        .share-actions {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
        .share-btn {{ display: inline-flex; align-items: center; gap: 0.45rem; font: inherit; font-size: 0.8rem; font-weight: 600; color: var(--navy); background: var(--white); border: 1px solid var(--border); border-radius: 22px; padding: 0.5rem 1rem; text-decoration: none; cursor: pointer; transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s; }}
        .share-btn:hover {{ border-color: var(--blue); color: var(--blue); box-shadow: var(--shadow-md); transform: translateY(-1px); }}
        .share-btn .icon {{ width: 1.1em; height: 1.1em; }}
        /* The share row reuses .copy-btn for its clipboard behaviour but not
           its pill styling, which is a filled gradient built for the prompt
           cards and would read as the primary action here. */
        .share-btn.copy-btn {{ background: var(--white); color: var(--navy); border: 1px solid var(--border); }}
        .share-btn.copy-btn:hover {{ color: var(--blue); box-shadow: var(--shadow-md); }}
        .share-btn.copy-btn.copied {{ background: var(--green); border-color: var(--green); color: var(--white); }}
        .share-btn[hidden] {{ display: none; }}
        p {{ margin-bottom: 1rem; line-height: 1.75; color: var(--gray); font-size: 0.9rem; }}
        strong {{ color: var(--navy); font-weight: 600; }}
        @media (max-width: 640px) {{
            .header {{ padding: 2.5rem 0 2.25rem; }}
            .header h1 {{ font-size: 1.6rem; }}
            .brand-logo {{ width: 58px; height: 58px; padding: 6px; border-radius: 18px; margin-bottom: 1.1rem; }}
            .container {{ padding: 1.5rem 1rem 3rem; }}
            .article-content {{ padding: 1.5rem 1.25rem; }}
            .nav-content {{ flex-direction: column; align-items: flex-start; gap: 0.35rem; }}
            .author-byline {{ padding: 0.875rem 1.25rem; }}
            .breadcrumb {{ padding: 0.5rem 1.25rem; }}
            .canada-section {{ padding: 1.25rem; }}
            .action-card {{ flex-direction: column; gap: 0.6rem; }}
            .action-num {{ width: 1.5rem; height: 1.5rem; min-width: 1.5rem; }}
            .prompts-section {{ padding: 1.25rem; }}
            .prompt-head {{ flex-direction: column; align-items: flex-start; }}
            .prompt-text {{ font-size: 0.72rem; }}
            .summary-section {{ padding: 1.1rem 1.2rem; }}
            .myth-section {{ padding: 1.25rem; }}
            .myth-block {{ flex-direction: column; gap: 0.5rem; }}
            .question-section {{ padding: 1.25rem 1.35rem; }}
            .question-body {{ font-size: 1rem; }}
            .dev-tier {{ margin-left: 0; flex-basis: 100%; }}
            /* Badges go full width rather than wrapping into ragged rows. */
            .badge {{ flex: 1 1 auto; min-width: 6.5rem; }}
        }}
    </style>
</head>
<body>
    <!-- Icon sprite. Reference a symbol by id from an svg.icon element.
         Markers here are geometric on purpose: the brand's maple leaf is
         illegible below ~32px, so it stays in the logo and does not get
         shrunk down into list bullets. -->
    <svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
        <symbol id="i-search" viewBox="0 0 24 24">
            <circle cx="10.5" cy="10.5" r="6.5"/>
            <path d="m15.5 15.5 4.5 4.5"/>
        </symbol>
        <symbol id="i-clock" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="8.5"/>
            <path d="M12 7v5.2l3.2 2"/>
        </symbol>
        <symbol id="i-copy" viewBox="0 0 24 24">
            <rect x="9" y="9" width="11" height="11" rx="2.5"/>
            <path d="M6.5 15H5.5A2.5 2.5 0 0 1 3 12.5v-7A2.5 2.5 0 0 1 5.5 3h7A2.5 2.5 0 0 1 15 5.5v1"/>
        </symbol>
        <symbol id="i-linkedin" viewBox="0 0 24 24">
            <path fill="currentColor" stroke="none" d="M4.98 3.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM3 9.5h4v11H3zm7 0h3.8v1.5a4.2 4.2 0 0 1 3.7-1.9c3 0 4.5 1.9 4.5 5.3v6.1h-4v-5.4c0-1.6-.6-2.6-2-2.6s-2.2 1-2.2 2.6v5.4h-3.8z"/>
        </symbol>
        <symbol id="i-mail" viewBox="0 0 24 24">
            <rect x="3" y="5" width="18" height="14" rx="2.5"/>
            <path d="m3.5 7 8.5 6 8.5-6"/>
        </symbol>
        <symbol id="i-share" viewBox="0 0 24 24">
            <circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/>
            <path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>
        </symbol>
        <symbol id="i-doc" viewBox="0 0 24 24">
            <path d="M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8z"/>
            <path d="M14 3v5h5"/>
            <path d="M8.5 13h7M8.5 16.5h4.5"/>
        </symbol>
        <symbol id="i-pencil" viewBox="0 0 24 24">
            <path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17z"/>
            <path d="m14.5 6 3 3"/>
        </symbol>
        <symbol id="i-diamond" viewBox="0 0 24 24">
            <path d="M12 4.5 19.5 12 12 19.5 4.5 12Z"/>
        </symbol>
    </svg>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">&#8592; Back to Blog</a>
            <div class="nav-meta">
                <img src="/blog/logo.svg" class="brand-icon" alt="" width="22" height="22">
                <span>AI Insights for Canadian Business</span>
                <span>&#8226;</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>
    <header class="header">
        <div class="header-content">
            <img src="/blog/logo.svg" class="brand-logo" alt="AI Insights" width="76" height="76">
            <div class="issue-badge">Issue #{issue_num} &nbsp;&#8226;&nbsp; {issue_month_year} <span class="issue-badge-coverage">&mdash; Covering {coverage_month_name}</span></div>
            <h1>{clean_title_html}</h1>
            <div class="subtitle">The AI briefing built for Canadian business leaders</div>
            <div class="intro-text">{excerpt_html}</div>
            <div class="reading-badge"><svg class="icon" aria-hidden="true"><use href="#i-clock"/></svg> {reading_time} min read</div>
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
                {_build_share_row(canonical, clean_title, issue_month_year)}
            </div>
        </article>
    </div>
    <script>
      // Copy-to-clipboard for the prompt cards. Delegated, so it costs one
      // listener regardless of how many prompts a post carries.
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
          var label = btn.querySelector('.copy-btn-text');
          if (!label) return;
          var original = label.textContent;
          label.textContent = 'Copied';
          btn.classList.add('copied');
          setTimeout(function () {{
            label.textContent = original;
            btn.classList.remove('copied');
          }}, 1800);
        }}

        document.addEventListener('click', function (e) {{
          var btn = e.target.closest ? e.target.closest('.copy-btn') : null;
          if (!btn) return;

          var text;
          if (btn.classList.contains('share-copy')) {{
            // The canonical permalink, baked in at build time. Never
            // location.href — this same article is also served at
            // latest.html, which points at a different issue next month.
            text = btn.dataset.shareUrl || '';
          }} else if (btn.classList.contains('copy-article')) {{
            // Clone and strip these sections out first: pasting the issue WITH
            // the prompt cards in it hands the assistant three competing sets
            // of instructions alongside the article it is meant to read, and
            // the share row contributes nothing but button labels.
            var src = document.querySelector('.article-content');
            var art = null;
            if (src) {{
              art = src.cloneNode(true);
              ['.prompts-section', '.share-row'].forEach(function (sel) {{
                var strip = art.querySelector(sel);
                if (strip) strip.remove();
              }});
            }}
            // Canonical, not location.href: read via latest.html this would
            // otherwise hand the reader a URL that points at a different
            // article next month.
            var link = document.querySelector('link[rel="canonical"]');
            var url = link ? link.href : location.href;
            text = document.title + '\\n' + url + '\\n\\n' + (art ? art.innerText : '');
          }} else {{
            var pre = document.getElementById(btn.dataset.prompt);
            text = pre ? pre.innerText : '';
          }}
          if (!text) return;

          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function () {{ flash(btn); }},
                                                     function () {{ fallbackCopy(text); flash(btn); }});
          }} else {{
            fallbackCopy(text);
            flash(btn);
          }}

          // So there is evidence of whether any of this gets used.
          if (typeof gtag === 'function') {{
            gtag('event', 'prompt_copy', {{ prompt_type: btn.dataset.label || 'unknown' }});
          }}
        }});

        // The OS share sheet, where the browser has one. Revealed rather than
        // rendered, so a desktop visitor never sees a button that would do
        // nothing — LinkedIn, email and copy already cover that case.
        if (navigator.share) {{
          document.querySelectorAll('.share-native').forEach(function (b) {{
            b.hidden = false;
          }});
        }}

        document.addEventListener('click', function (e) {{
          var btn = e.target.closest ? e.target.closest('.share-native') : null;
          if (!btn || !navigator.share) return;
          navigator.share({{
            title: btn.dataset.shareTitle || document.title,
            url: btn.dataset.shareUrl
          }}).then(function () {{
            if (typeof gtag === 'function') {{
              gtag('event', 'share', {{ method: 'web_share' }});
            }}
          }}).catch(function () {{
            // The user dismissed the sheet. Not an error, and not worth a message.
          }});
        }});
      }})();
    </script>
</body>
</html>'''

    return html


def _build_survey_cta():
    """Invitation to the reader survey, rendered only once a form URL is set.

    This is the collection end of the one thing on the site that makes Robert a
    primary source rather than a reporter of other people's numbers. It stays
    invisible until data/survey.json has a form_url, so the section can be built
    and reviewed without ever shipping a dead link.
    """
    import json as _json, os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    try:
        with open(_os.path.join(root, "data", "survey.json"), encoding="utf-8") as f:
            cfg = _json.load(f)
    except Exception:
        return ""

    form_url = (cfg.get("form_url") or "").strip()
    if not form_url:
        return ""

    name = escape_html(cfg.get("survey_name", "reader survey"))
    results_exists = _os.path.exists(_os.path.join(root, "blog", "canadian-ai-pulse.html"))
    results_link = ('<a class="survey-results" href="/blog/canadian-ai-pulse.html">'
                    'See the current results</a>') if results_exists else ""

    return (
        f'<div class="section survey-cta">'
        f'<h2 class="section-title">Add your data point</h2>'
        f'<p class="survey-body">Most of the adoption numbers in this issue come from '
        f'somebody else\'s survey. <strong>{name}</strong> is ours: five questions, under a '
        f'minute, no email required. Results are published openly with the sample size, so '
        f'you get to compare your position against the rest of this readership rather than '
        f'against a national average that may not look anything like you.</p>'
        f'<div class="survey-actions">'
        f'<a class="survey-btn" href="{form_url}" target="_blank" rel="noopener noreferrer">'
        f'Take the {name} survey</a>{results_link}'
        f'</div></div>'
    )


def _build_prompts_section(canonical, title_text, issue_month_year):
    """The "work this issue" block: prompts readers paste into their own
    chatbot.

    Design notes, because each one is load-bearing:

    * The URL is this issue's PERMALINK, never latest.html. latest.html rotates
      monthly, so a prompt carrying it would silently start pointing at a
      different article than the one the reader is holding.
    * Every prompt carries a refusal instruction. Most readers are on free
      tiers that cannot browse, and a model asked to analyse a page it cannot
      open will happily invent "insights from Robert Simon" that he never
      wrote. Telling it to stop converts the likeliest failure from silent
      fabrication into an honest "I can't reach that".
    * Every prompt asks for the source URL back. When the output gets pasted
      into a deck or a Slack thread, the link travels with it — that is the
      only part of this section that does anything for discoverability.
    * The issue title is embedded, so this block is unique per post rather than
      site-wide boilerplate repeated fourteen times.
    """
    guard = ("If you cannot open that link, tell me so and stop \u2014 "
             "do not answer from memory or guess what it says.")
    source_line = f"Read this article \u2014 \u201c{title_text}\u201d: {canonical}"

    prompts = [
        ("Personalize", "What in this issue actually applies to me",
         "I work in [your industry] at a company of about [number] employees in "
         "[province], and my role is [your role].\n\n"
         f"{source_line}\n\n{guard}\n\n"
         "Using only that article, tell me: which developments genuinely affect a "
         "business like mine and which I can safely ignore; what the realistic "
         "impact looks like over the next six months; and the single thing I "
         "should look into first.\n\n"
         "Cite the article URL in your answer."),
        ("Pressure-test", "Argue against it for my situation",
         "I work in [your industry], we have about [number] employees, and my "
         "biggest constraint right now is [budget / talent / legacy systems / "
         "regulatory approval].\n\n"
         f"{source_line}\n\n{guard}\n\n"
         "Argue against applying this article's recommendations in my situation. "
         "Where is the advice too generic, too early, or too expensive for a "
         "company like mine? What would have to be true for it to be worth acting "
         "on this quarter? Be specific and skeptical rather than balanced.\n\n"
         "Cite the article URL in your answer."),
        ("Operationalize", "Turn it into something I can send upward",
         "I am a [your role] at a [your industry] company with about [number] "
         "employees in Canada.\n\n"
         f"{source_line}\n\n{guard}\n\n"
         "Turn it into a one-page briefing for my leadership team: what changed "
         "this month, why it matters for us specifically, the three decisions we "
         "need to make, and what it costs us to wait a quarter.\n\n"
         "Cite the article URL so my team can read the source."),
    ]

    cards = ""
    for i, (label, blurb, body) in enumerate(prompts, 1):
        cards += (
            f'<div class="prompt-card">'
            f'<div class="prompt-head">'
            f'<div><span class="prompt-label">{label}</span>'
            f'<span class="prompt-blurb">{blurb}</span></div>'
            f'<button type="button" class="copy-btn" data-prompt="p{i}" '
            f'data-label="{label}" aria-label="Copy the {label} prompt">'
            f'<svg class="icon" aria-hidden="true"><use href="#i-copy"/></svg>'
            f'<span class="copy-btn-text">Copy</span></button>'
            f'</div>'
            f'<pre class="prompt-text" id="p{i}">{escape_html(body)}</pre>'
            f'</div>'
        )

    return (
        f'<div class="section prompts-section">'
        f'<h2 class="section-title">Work this issue with your own AI assistant</h2>'
        f'<p class="prompts-intro">These are written for ChatGPT, Claude or Gemini. '
        f'Copy one, fill in the bracketed parts, and you get analysis of this issue '
        f'for your situation rather than a generic summary.</p>'
        f'<div class="prompt-list">{cards}</div>'
        f'<div class="prompt-foot">'
        f'<span>Assistant cannot open links?</span>'
        f'<button type="button" class="copy-btn copy-article" data-label="Full issue" '
        f'aria-label="Copy the full text of this issue">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-doc"/></svg>'
        f'<span class="copy-btn-text">Copy the full issue text</span></button>'
        f'<span class="prompt-foot-note">Paste it above your prompt and any '
        f'assistant can work from it, no browsing needed.</span>'
        f'</div>'
        f'</div>'
    )


def _build_share_row(canonical, title, issue_month_year):
    """Share controls for a published issue.

    Every link is built from `canonical`, never from the page's own address.
    A post is served at BOTH its dated permalink and at latest.html, and
    latest.html is a rotating alias — same URL, a different article every
    month. Sharing the address the reader happens to be at means a link that
    silently points at next month's issue, and social platforms cache Open
    Graph data per URL essentially forever, so the preview stays wrong too.

    LinkedIn and email are plain hrefs resolved at build time, so they work
    with JavaScript disabled. Only copy-to-clipboard and the OS share sheet
    need scripting, and the share sheet button stays hidden until the browser
    says it supports it.
    """
    url_q = quote(canonical, safe='')
    # A topical headline gets the publication name appended for context; a
    # fallback title like "AI Insights for August 2026" already carries it and
    # would otherwise read "... — AI Insights, September 2026".
    subject = (
        title if "ai insights" in title.lower()
        else f"{title} — AI Insights, {issue_month_year}"
    )
    subject_q = quote(subject, safe='')
    body_q    = quote(
        f"Thought this was worth your time — Robert Simon's monthly AI briefing "
        f"for Canadian business leaders.\n\n{title}\n{canonical}\n",
        safe=''
    )

    linkedin = f"https://www.linkedin.com/sharing/share-offsite/?url={url_q}"
    mailto   = f"mailto:?subject={subject_q}&body={body_q}"
    url_attr = escape_html(canonical, quote=True)

    return (
        f'<div class="share-row">'
        f'  <div class="share-label">Forward this issue</div>'
        f'  <div class="share-actions">'
        f'    <a class="share-btn" href="{escape_html(linkedin, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-linkedin"/></svg>'
        f'<span>LinkedIn</span></a>'
        f'    <a class="share-btn" href="{escape_html(mailto, quote=True)}">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-mail"/></svg>'
        f'<span>Email</span></a>'
        f'    <button type="button" class="share-btn copy-btn share-copy" '
        f'data-share-url="{url_attr}" data-label="share_copy">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-copy"/></svg>'
        f'<span class="copy-btn-text">Copy link</span></button>'
        f'    <button type="button" class="share-btn share-native" hidden '
        f'data-share-url="{url_attr}" data-share-title="{escape_html(title, quote=True)}">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-share"/></svg>'
        f'<span>Share</span></button>'
        f'  </div>'
        f'</div>'
    )


def _build_dev_source(d):
    if not d.get("source_url"):
        return ""
    src_label = d.get("source_name") or "Source"
    return (
        f'<div class="dev-source">'
        f'<a href="{d["source_url"]}" target="_blank" rel="noopener noreferrer" '
        f'title="Search Google for this article">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-search"/></svg> {src_label}'
        f'</a></div>'
    )


def _build_strategic_read(d):
    """Robert's interpretation of a major story. Visually distinct from the
    reported sentences above it — a reader must be able to tell at a glance
    which half of this card is fact and which half is judgment."""
    text = (d.get("strategic_read") or "").strip()
    if len(text) < 40:
        return ""
    return (
        f'<div class="dev-read">'
        f'<span class="dev-read-label">Strategic read</span>'
        f'<p>{escape_html(text, quote=False)}</p>'
        f'</div>'
    )


# Rating value -> modifier class. Anything unrecognised renders neutral rather
# than unstyled, so an off-script value from the model still looks deliberate.
_RATING_TONE = {
    "high": "tone-high", "medium": "tone-mid", "low": "tone-low",
    "yes": "tone-high", "monitor": "tone-mid", "ignore": "tone-low",
    "now": "tone-high", "3 months": "tone-mid",
    "6 months": "tone-low", "12 months": "tone-low",
    "small": "tone-low", "large": "tone-high",
}


def _badge(label, value, extra=""):
    if not value:
        return ""
    tone = _RATING_TONE.get(value.strip().lower(), "tone-neutral")
    return (
        f'<span class="badge {tone} {extra}">'
        f'<span class="badge-label">{label}</span>'
        f'<span class="badge-value">{escape_html(value, quote=False)}</span>'
        f'</span>'
    )


def _build_rating_row(d):
    badges = (
        _badge("Strategic importance", d.get("importance", ""))
        + _badge("Time horizon", d.get("horizon", ""))
        + _badge("Executive attention", d.get("attention", ""))
    )
    if not badges:
        return ""
    return f'<div class="badge-row">{badges}</div>'


def _build_action_meta(a):
    badges = (
        _badge("Priority", a.get("priority", ""))
        + _badge("Effort", a.get("effort", ""))
        + _badge("Impact", a.get("impact", ""))
    )
    if not badges:
        return ""
    return f'<div class="badge-row badge-row-action">{badges}</div>'


def _build_roberts_desk(raw_text):
    """The signature section.

    Rendered as ordinary paragraphs, not a pull quote. The old two-sentence
    take was wrapped in curly quotes, which reads as an aside; at 300-450 words
    that framing would undercut the one section the publication is sold on.

    The class names (.roberts-take / .roberts-header / .roberts-body) are load
    bearing — inject_take.py finds and replaces the body through them when the
    reviewer types their own version in the preview page. Renaming them here
    silently breaks that path, and the failure mode is the model's draft
    shipping under Robert's byline.
    """
    cleaned = (raw_text or "").strip()
    cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned, flags=re.DOTALL).strip()
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)

    is_placeholder = (
        not cleaned
        or 'PLACEHOLDER' in cleaned.upper()
        or len(cleaned) < 120
    )

    header = (
        '<div class="roberts-header">'
        '<img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon">'
        '<div>'
        '<div class="roberts-label">Executive Perspective</div>'
        '<div class="roberts-name">From Robert&#39;s Desk</div>'
        '</div>'
        '</div>'
    )

    if is_placeholder:
        body = (
            '<div class="roberts-placeholder">'
            '<strong><svg class="icon" aria-hidden="true"><use href="#i-pencil"/></svg> '
            'Write this section before publishing.</strong><br><br>'
            'What surprised you this month? What do executives keep getting wrong about it? '
            'What is overhyped, what can wait, and what will matter six months from now? '
            '300-450 words in your own voice. This is the section people subscribe for — '
            'it is also the E-E-A-T signal that separates this from an aggregator.'
            '</div>'
        )
    else:
        paras = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if len(p.strip()) > 25]
        if len(paras) < 2:
            # Single-newline paragraphing, or one long block. Splitting a wall of
            # text on sentence boundaries is worse than leaving it whole, so only
            # the line-break case is recovered.
            paras = [p.strip() for p in cleaned.split('\n') if len(p.strip()) > 25] or [cleaned]
        body = "".join(
            f'<p class="roberts-body">{escape_html(" ".join(p.split()), quote=False)}</p>'
            for p in paras
        )

    return f'<div class="section"><div class="roberts-take">{header}{body}</div></div>'


def _build_conclusion(sections, coverage_month_year):
    impact  = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    actions = parse_actions(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""))

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
