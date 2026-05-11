import argparse
import os
import requests
import json
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════

def clean_filename(title):
    clean = re.sub('<.*?>', '', title)
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', clean)
    clean = re.sub(r'\s+', '-', clean.strip())
    return clean.lower()


def clean_ai_content(content):
    """Strip markdown artifacts and stray symbols from Gemini output."""
    content = re.sub(r'\[\d+\]', '', content)           # citation numbers
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # bold
    content = re.sub(r'\*(.*?)\*', r'\1', content)       # italic
    content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)  # headings
    content = re.sub(r'•\s*[-–—]\s*', '', content)
    content = re.sub(r'[-–—]\s*•\s*', '', content)
    content = re.sub(r' +', ' ', content)
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
    return content.strip()


# ══════════════════════════════════════════════════════════════════
# GEMINI API  —  improved prompt with grounding
# ══════════════════════════════════════════════════════════════════

def generate_blog_with_gemini(api_key, topic=None):
    """
    Generate blog content using Gemini with Google Search grounding
    so that events, dates and statistics are real, not hallucinated.
    """
    import time

    current_date = datetime.now()
    month_year   = current_date.strftime("%B %Y")
    prev_month   = (current_date.replace(day=1) - __import__('datetime').timedelta(days=1)).strftime("%B %Y")

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    # Flash-Lite handles the free tier; Flash is the fallback
    models_to_try = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]

    # ── Build the prompt ──────────────────────────────────────────
    if topic:
        prompt = _build_custom_prompt(topic, month_year)
    else:
        prompt = _build_monthly_prompt(month_year, prev_month)

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],          # grounding — real events only
        "generationConfig": {
            "maxOutputTokens": 3000,
            "temperature": 0.6,
            "candidateCount": 1
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",      "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_ONLY_HIGH"}
        ]
    }

    for attempt, model in enumerate(models_to_try):
        if attempt > 0:
            print(f"  Waiting 30 s before trying {model}...")
            time.sleep(30)

        print(f"Trying model: {model} (attempt {attempt+1}/{len(models_to_try)})")
        url = f"{BASE}/{model}:generateContent?key={api_key}"

        try:
            response = requests.post(url, json=payload, timeout=180)
            print(f"  HTTP status: {response.status_code}")

            if response.status_code == 429:
                print("  Rate limited. Trying next model after wait.")
                continue
            if response.status_code == 403:
                raise Exception(
                    "API key rejected (403). Check your GEMINI_API_KEY secret. "
                    "Get a fresh key at https://aistudio.google.com/app/apikey"
                )
            if response.status_code in (404, 400):
                # 400 can mean grounding not supported on this model — retry without it
                print(f"  {response.status_code} on {model}. Retrying without grounding.")
                payload_no_ground = {k: v for k, v in payload.items() if k != "tools"}
                r2 = requests.post(url, json=payload_no_ground, timeout=180)
                if r2.status_code == 200:
                    response = r2
                else:
                    print(f"  Still {r2.status_code}, trying next model.")
                    continue
            if response.status_code != 200:
                print(f"  Unexpected {response.status_code}: {response.text[:300]}")
                continue

            data       = response.json()
            candidates = data.get('candidates', [])
            if not candidates:
                print(f"  No candidates. Feedback: {data.get('promptFeedback', {})}")
                continue

            candidate     = candidates[0]
            finish_reason = candidate.get('finishReason', '')
            print(f"  Finish reason: {finish_reason}")
            if finish_reason in ('SAFETY', 'RECITATION'):
                continue

            parts    = candidate.get('content', {}).get('parts', [])
            raw_text = ' '.join(p.get('text', '') for p in parts if p.get('text')).strip()

            if len(raw_text) < 200:
                print(f"  Response too short ({len(raw_text)} chars).")
                continue

            cleaned = clean_ai_content(raw_text)
            print(f"  SUCCESS: {len(cleaned)} chars from {model}")
            return {"content": cleaned, "model": model}

        except requests.exceptions.Timeout:
            print(f"  Timeout on {model}.")
            continue
        except Exception as e:
            if '403' in str(e):
                raise
            print(f"  Error on {model}: {e}")
            continue

    raise Exception(
        "All Gemini models failed. "
        "429 = quota exhausted (wait 1 h). "
        "403 = bad API key. "
        "404 = model unavailable."
    )


def _build_monthly_prompt(month_year, prev_month):
    return f"""You are writing a monthly AI insights newsletter for Robert Simon, an independent AI thought leader based in Montreal, QC, Canada.

Your audience is Canadian business leaders — C-suite, VPs, and directors at mid-to-large Canadian companies in financial services, retail, manufacturing, telecom, healthcare, and professional services. They are time-pressed, smart, and want to know WHAT happened, WHY it matters to THEIR business, and WHAT to do about it.

Write the {month_year} edition. Use your Google Search grounding to retrieve REAL AI news events from {prev_month} and {month_year}. Do not invent events, dates, or statistics.

Write in plain text only. No markdown, no asterisks, no hashtags, no bullet symbols in the prose. Structure your response with EXACTLY these plain-text section headers on their own lines (nothing else on those lines):

INTRODUCTION
KEY AI DEVELOPMENTS
CANADIAN SPOTLIGHT
WHAT THIS MEANS FOR CANADIAN BUSINESS
STRATEGIC ACTIONS FOR THIS MONTH
ADOPTION SNAPSHOT
ROBERTS TAKE

--- SECTION REQUIREMENTS ---

INTRODUCTION (2-3 sentences):
Open with a sharp, opinionated hook that captures why this particular month matters — not generic AI commentary. Reference a specific event or trend from {month_year}.

KEY AI DEVELOPMENTS (exactly 8 items):
List 8 real AI news items from {prev_month}–{month_year}. Each item MUST include:
- The exact date (e.g. "April 3") and company name
- What was released/announced in one crisp sentence
- Why it is significant (one sentence)
Format each as: [Date]: [Company] — [What happened]. [Why it matters one sentence].
Only include events you can verify. If fewer than 8 are clearly verifiable, list what you have confidently.

CANADIAN SPOTLIGHT (3-4 items):
Focus ONLY on AI developments specifically relevant to Canada: Canadian companies (Cohere, Ada, Coveo, D-Wave, Shopify, RBC, TD, Scotiabank, Manulife, BCE/Bell, Rogers, Telus, etc.), federal/provincial government AI policy, Canadian university research (Mila, Vector Institute, Amii), or major international AI company expansions into Canada. Include specific company names, dollar amounts, or policy names where known.

WHAT THIS MEANS FOR CANADIAN BUSINESS (2-3 focused paragraphs):
Be specific. Name which Canadian industries are most affected. Reference the actual developments listed above. Avoid generic statements like "companies must adapt." Instead: "RBC's deployment of X means that mid-size wealth management firms now face..." Connect the global AI shifts to Canadian competitive dynamics, regulatory environment (PIPEDA, Bill C-27, Quebec Law 25), and Canada's trade position with the US.

STRATEGIC ACTIONS FOR THIS MONTH (exactly 5 items):
These must be SPECIFIC and ACTIONABLE — not platitudes. Each recommendation should:
- Start with a strong verb (Audit, Pilot, Negotiate, Assign, Block, Commission, etc.)
- Reference a specific tool, model, or event mentioned in this month's developments
- Specify WHO in the organization should act (CTO, CHRO, CFO, Board, etc.)
- Include a timeline (this week, this quarter, by end of month, etc.)
Format as numbered items: 1. [Action verb] [specific action]...

ADOPTION SNAPSHOT (4-5 data points):
Use ONLY real, citable Canadian AI statistics from reputable sources: Statistics Canada, BDC (Business Development Bank), CIRA, ISED (Innovation, Science and Economic Development Canada), Conference Board of Canada, Deloitte Canada, KPMG Canada, or Mila/Vector Institute annual reports. Include the source name and approximate date for each stat. If you cannot find real Canadian stats, use real North American stats and label them as such. Do NOT invent percentages.

ROBERTS TAKE (2-3 sentences):
Write a placeholder in brackets: [ROBERTS TAKE: Robert — add your 2-3 sentence personal perspective here before publishing. What surprised you this month? What are you telling your clients? What pattern are you seeing that others are missing?]

--- STYLE NOTES ---
Write like a knowledgeable colleague, not a press release. Be direct. Have a point of view. Canadian businesses are currently navigating US trade tensions, a post-election federal government, and skills shortages — acknowledge this context where relevant. The newsletter should feel like it was written by someone who actually follows AI news daily and cares about Canadian business outcomes."""


def _build_custom_prompt(topic, month_year):
    return f"""You are writing an AI insights article for Robert Simon, an independent AI thought leader based in Montreal, QC, Canada.

Topic: {topic}

Your audience is Canadian business leaders who want practical, Canada-specific AI intelligence.

Write in plain text only. No markdown, no asterisks. Structure with EXACTLY these headers on their own lines:

INTRODUCTION
KEY AI DEVELOPMENTS
CANADIAN SPOTLIGHT
WHAT THIS MEANS FOR CANADIAN BUSINESS
STRATEGIC ACTIONS FOR THIS MONTH
ADOPTION SNAPSHOT
ROBERTS TAKE

Use the same section requirements as the monthly newsletter:
- Real, verifiable events only (use grounding)
- Canadian-specific business implications
- Specific, actionable recommendations with owner and timeline
- Real Canadian statistics with sources
- Roberts Take as a bracketed placeholder

Month context: {month_year}"""


# ══════════════════════════════════════════════════════════════════
# CONTENT PARSING
# ══════════════════════════════════════════════════════════════════

SECTION_HEADERS = [
    "INTRODUCTION",
    "KEY AI DEVELOPMENTS",
    "CANADIAN SPOTLIGHT",
    "WHAT THIS MEANS FOR CANADIAN BUSINESS",
    "STRATEGIC ACTIONS FOR THIS MONTH",
    "ADOPTION SNAPSHOT",
    "ROBERTS TAKE",
]

def parse_sections(content):
    """Split the flat text into named sections."""
    sections = {h: "" for h in SECTION_HEADERS}

    # Find each header position
    positions = {}
    content_upper = content.upper()
    for header in SECTION_HEADERS:
        # Allow for slight variations (e.g. "ROBERT'S TAKE")
        variants = [header, header.replace(" ", "S "), header + "S", header + ":"]
        for variant in variants:
            idx = content_upper.find(variant)
            if idx != -1:
                positions[header] = idx
                break

    if not positions:
        # Fallback: dump everything into introduction
        sections["INTRODUCTION"] = content
        return sections

    sorted_headers = sorted(positions.keys(), key=lambda h: positions[h])

    for i, header in enumerate(sorted_headers):
        start = positions[header] + len(header)
        # Skip colon or newline after header
        while start < len(content) and content[start] in ':\n ':
            start += 1
        end = positions[sorted_headers[i + 1]] if i + 1 < len(sorted_headers) else len(content)
        sections[header] = content[start:end].strip()

    return sections


def parse_list_items(text, min_length=40):
    """Extract numbered or paragraph list items from a text block."""
    items = []
    # Try numbered list first
    numbered = re.findall(r'^\d+\.\s+(.+?)(?=\n\d+\.|\Z)', text, re.MULTILINE | re.DOTALL)
    if numbered:
        for item in numbered:
            cleaned = ' '.join(item.strip().split())
            if len(cleaned) >= min_length:
                items.append(cleaned)
        return items

    # Fall back to sentence / paragraph splitting
    for line in text.split('\n'):
        line = line.strip()
        line = re.sub(r'^[-•*]\s*', '', line)
        if len(line) >= min_length:
            items.append(line)
    return items


def parse_developments(text):
    """Parse the KEY AI DEVELOPMENTS block into structured dicts."""
    items = []
    # Each item starts with a date pattern: "Month DD:" or "April 3:"
    pattern = re.compile(
        r'(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'[\s\.]?\d{1,2}[,.]?)',
        re.IGNORECASE
    )

    splits = pattern.split(text)
    # splits = [pre_text, date1, body1, date2, body2 ...]
    i = 1
    while i + 1 < len(splits):
        date_str = splits[i].strip().rstrip(',.')
        body     = splits[i + 1].strip()
        body     = ' '.join(body.split())
        if len(body) > 30:
            items.append({"date": date_str, "body": body})
        i += 2

    # If date parsing found nothing, fall back to paragraph items
    if not items:
        for raw in parse_list_items(text):
            # Try to detect a leading date
            m = re.match(r'^([A-Z][a-z]+ \d{1,2})[:\-–—]\s*(.*)', raw)
            if m:
                items.append({"date": m.group(1), "body": m.group(2)})
            else:
                items.append({"date": "", "body": raw})

    return items[:10]


def extract_title_and_excerpt(content, month_year):
    title   = f"AI Insights for {month_year}"
    excerpt = ""

    sections = parse_sections(content)
    intro    = sections.get("INTRODUCTION", "")
    if intro:
        sentences = re.split(r'(?<=[.!?])\s+', intro)
        excerpt   = ' '.join(sentences[:2]).strip()

    if not excerpt or len(excerpt) < 50:
        excerpt = f"Your monthly AI intelligence briefing for Canadian business leaders — {month_year}."

    if len(excerpt) > 220:
        excerpt = excerpt[:217].rstrip() + "..."

    return title, excerpt


# ══════════════════════════════════════════════════════════════════
# HTML GENERATION — richer template
# ══════════════════════════════════════════════════════════════════

def create_html_blog_post(content, title, excerpt):
    """Produce a polished, content-rich HTML blog post."""
    current_date  = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    iso_date      = current_date.strftime("%Y-%m-%d")
    month_year    = current_date.strftime("%B %Y")

    clean_title = re.sub(r'^[#\*\s]+', '', title).strip() or f"AI Insights for {month_year}"
    seo_title   = f"{clean_title} | AI News for Canadian Business | Robert Simon"
    slug        = clean_filename(clean_title)
    canonical   = f"https://www.imetrobert.com/blog/posts/{iso_date}-{slug}.html"
    og_image    = "https://www.imetrobert.com/blog/og-blog.jpg"

    meta_desc = re.sub(r'\s+', ' ', excerpt).strip()
    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152].rstrip() + "..."

    # ── Parse sections ────────────────────────────────────────────
    sections = parse_sections(content)

    intro_text       = sections.get("INTRODUCTION", "")
    canadian_spot    = sections.get("CANADIAN SPOTLIGHT", "")
    business_impact  = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    roberts_take_raw = sections.get("ROBERTS TAKE", "")
    adoption_raw     = sections.get("ADOPTION SNAPSHOT", "")

    developments = parse_developments(sections.get("KEY AI DEVELOPMENTS", ""))
    actions      = parse_list_items(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""), min_length=40)
    adoption     = parse_list_items(adoption_raw, min_length=20)

    # ── Roberts Take — keep as placeholder if not yet personalised ─
    roberts_take_html = _build_roberts_take(roberts_take_raw, month_year)

    # ── Build article content ─────────────────────────────────────
    article_parts = []

    if intro_text:
        article_parts.append(f'<div class="section intro-section"><p class="intro-lead">{intro_text}</p></div>')

    if developments:
        dev_items = "\n".join(
            f'<li><span class="dev-date">{d["date"]}</span> {d["body"]}</li>'
            if d["date"] else f'<li>{d["body"]}</li>'
            for d in developments
        )
        article_parts.append(f'''
<div class="section">
  <h2 class="section-title">Key AI Developments This Month</h2>
  <ul class="dev-list">{dev_items}</ul>
</div>''')

    if canadian_spot:
        spot_items = parse_list_items(canadian_spot, min_length=30)
        if spot_items:
            spot_html = "\n".join(f'<li>{item}</li>' for item in spot_items)
            article_parts.append(f'''
<div class="section canada-section">
  <div class="canada-badge">🍁 Canadian Spotlight</div>
  <h2 class="section-title">What\'s Happening in Canada</h2>
  <ul class="bullet-list">{spot_html}</ul>
</div>''')
        elif len(canadian_spot) > 60:
            article_parts.append(f'''
<div class="section canada-section">
  <div class="canada-badge">🍁 Canadian Spotlight</div>
  <h2 class="section-title">What\'s Happening in Canada</h2>
  <p>{canadian_spot}</p>
</div>''')

    if business_impact:
        # Split into paragraphs
        paras = [p.strip() for p in business_impact.split('\n\n') if len(p.strip()) > 40]
        if not paras:
            paras = [business_impact.strip()]
        paras_html = "\n".join(f'<p>{p}</p>' for p in paras)
        article_parts.append(f'''
<div class="section impact-section">
  <h2 class="section-title">What This Means for Canadian Business</h2>
  {paras_html}
</div>''')

    if actions:
        action_items = "\n".join(
            f'<li><span class="action-num">{i+1}</span><div class="action-body">{a}</div></li>'
            for i, a in enumerate(actions[:5])
        )
        article_parts.append(f'''
<div class="section actions-section">
  <h2 class="section-title">Strategic Actions for This Month</h2>
  <ul class="actions-list">{action_items}</ul>
</div>''')

    if adoption:
        stat_items = "\n".join(f'<li>{item}</li>' for item in adoption)
        article_parts.append(f'''
<div class="section adoption-section">
  <h2 class="section-title">Canadian AI Adoption Snapshot</h2>
  <ul class="stat-list">{stat_items}</ul>
  <p class="stat-note">Sources: Statistics Canada, BDC, ISED, Vector Institute, Conference Board of Canada.</p>
</div>''')

    # Roberts Take always last before conclusion
    article_parts.append(roberts_take_html)

    article_html = "\n".join(article_parts)

    # ── FAQ schema from actions ───────────────────────────────────
    faq_qs = [
        f"What AI developments matter most for Canadian businesses in {month_year}?",
        "What should Canadian executives do about AI right now?",
        "How is AI adoption tracking in Canada?",
        "What Canadian AI companies or initiatives should I know about?",
        "How do global AI trends affect Canadian competitiveness?",
    ]
    faq_items = []
    for i, action in enumerate(actions[:5]):
        faq_items.append({
            "question": faq_qs[i],
            "answer": action[:500]
        })
    faq_schema_items = ',\n'.join([
        f'{{"@type":"Question","name":{json.dumps(f["question"])},"acceptedAnswer":{{"@type":"Answer","text":{json.dumps(f["answer"])}}}}}'
        for f in faq_items
    ]) if faq_items else ''

    # ── Assemble HTML ─────────────────────────────────────────────
    html = f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- ═══ SEO: Primary meta ═══ -->
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="AI Canada {month_year}, Canadian AI news, artificial intelligence Canada, AI business strategy Canada, AI adoption Canada, Montreal AI, Canadian digital transformation, AI news for Canadians, AI insights {month_year}">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
    <meta name="language" content="en-CA">

    <!-- ═══ GEO: Canadian location signals ═══ -->
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">

    <!-- ═══ Canonical ═══ -->
    <link rel="canonical" href="{canonical}">

    <!-- ═══ Open Graph ═══ -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{clean_title} | AI Insights for Canadian Business">
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
    <meta name="twitter:title" content="{clean_title} | AI News for Canadian Business">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <meta name="twitter:site" content="@thedigitalrobert">

    <!-- ═══ Structured data ═══ -->
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
    {f"""<script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [{faq_schema_items}]
    }}
    </script>""" if faq_schema_items else ""}
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

    <!-- ═══ Google Analytics ═══ -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --blue: #2563eb;
            --cyan: #06b6d4;
            --navy: #1e293b;
            --gray: #64748b;
            --light: #f8fafc;
            --white: #ffffff;
            --canada-red: #d62828;
            --green: #16a34a;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); color: var(--navy); line-height: 1.6; }}

        /* ── Nav ── */
        .nav-bar {{ background: var(--white); padding: 1rem 0; box-shadow: 0 1px 3px rgb(0 0 0 / 0.08); position: sticky; top: 0; z-index: 100; }}
        .nav-content {{ max-width: 1100px; margin: 0 auto; padding: 0 1.5rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }}
        .nav-link {{ color: white; text-decoration: none; font-weight: 600; padding: 0.45rem 1.1rem; font-size: 0.875rem; border-radius: 20px; background: linear-gradient(135deg, var(--blue), var(--cyan)); transition: all 0.25s; flex-shrink: 0; }}
        .nav-link:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgb(37 99 235 / 0.3); }}
        .blog-meta {{ font-size: 0.8rem; color: var(--gray); display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}

        /* ── Header ── */
        .header {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: white; padding: 3.5rem 0 3rem; text-align: center; position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; inset: 0; background: radial-gradient(circle at 20% 80%, rgba(255,255,255,0.08) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.06) 0%, transparent 50%); pointer-events: none; }}
        .header-content {{ max-width: 860px; margin: 0 auto; padding: 0 1.5rem; position: relative; z-index: 1; }}
        .header h1 {{ font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 700; margin-bottom: 0.5rem; line-height: 1.2; }}
        .header .subtitle {{ font-size: 1rem; font-weight: 500; opacity: 0.9; margin-bottom: 0.75rem; }}
        .header .intro {{ font-size: 0.95rem; opacity: 0.85; max-width: 720px; margin: 0 auto; line-height: 1.65; }}
        .issue-badge {{ display: inline-block; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); padding: 0.3rem 0.85rem; border-radius: 20px; font-size: 0.78rem; font-weight: 600; margin-bottom: 1rem; letter-spacing: 0.05em; text-transform: uppercase; }}

        /* ── Container ── */
        .container {{ max-width: 860px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
        .article-container {{ background: white; border-radius: 16px; box-shadow: 0 8px 30px rgb(0 0 0 / 0.08); overflow: hidden; }}

        /* ── Byline + breadcrumb ── */
        .author-byline {{ display: flex; align-items: center; gap: 0.875rem; padding: 1rem 1.75rem; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }}
        .author-byline img {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }}
        .author-name {{ font-weight: 600; color: var(--navy); font-size: 0.875rem; }}
        .author-role {{ font-size: 0.775rem; color: var(--gray); }}
        .breadcrumb {{ font-size: 0.75rem; color: var(--gray); padding: 0.6rem 1.75rem; background: #fafbfc; border-bottom: 1px solid #f1f5f9; }}
        .breadcrumb a {{ color: var(--blue); text-decoration: none; }}

        /* ── Article content ── */
        .article-content {{ padding: 2rem 1.75rem; }}

        /* ── Sections ── */
        .section {{ margin-bottom: 2.75rem; }}
        .section-title {{ font-size: 1.35rem; color: var(--navy); margin-bottom: 1.25rem; font-weight: 700; padding-left: 1rem; position: relative; }}
        .section-title::before {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: linear-gradient(to bottom, var(--blue), var(--cyan)); border-radius: 2px; }}

        /* ── Intro ── */
        .intro-lead {{ font-size: 1.05rem; line-height: 1.8; color: var(--navy); font-weight: 400; border-left: 3px solid var(--cyan); padding-left: 1rem; }}

        /* ── Dev list ── */
        .dev-list {{ list-style: none; padding: 0; }}
        .dev-list li {{ padding: 1rem 1.25rem; margin-bottom: 0.75rem; border: 1px solid #e8edf5; border-radius: 10px; line-height: 1.65; font-size: 0.9rem; color: var(--gray); transition: border-color 0.2s, box-shadow 0.2s; }}
        .dev-list li:hover {{ border-color: var(--blue); box-shadow: 0 2px 12px rgb(37 99 235 / 0.08); }}
        .dev-date {{ display: inline-block; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: white; font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.55rem; border-radius: 10px; margin-right: 0.5rem; white-space: nowrap; vertical-align: middle; }}

        /* ── Canada section ── */
        .canada-section {{ background: linear-gradient(135deg, #fff5f5 0%, #fff 100%); border: 1px solid #fecaca; border-radius: 12px; padding: 1.5rem; }}
        .canada-badge {{ display: inline-block; background: var(--canada-red); color: white; font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.7rem; border-radius: 12px; margin-bottom: 0.75rem; letter-spacing: 0.04em; }}
        .canada-section .section-title::before {{ background: var(--canada-red); }}

        /* ── Impact section ── */
        .impact-section p {{ line-height: 1.8; color: var(--gray); margin-bottom: 1rem; font-size: 0.925rem; }}
        .impact-section p:last-child {{ margin-bottom: 0; }}

        /* ── Actions list ── */
        .actions-list {{ list-style: none; padding: 0; counter-reset: actions; }}
        .actions-list li {{ display: flex; gap: 1rem; align-items: flex-start; padding: 1rem 1.25rem; margin-bottom: 0.75rem; border-left: 3px solid var(--blue); background: #f8faff; border-radius: 0 10px 10px 0; font-size: 0.9rem; line-height: 1.65; color: var(--navy); }}
        .action-num {{ display: flex; align-items: center; justify-content: center; width: 1.6rem; height: 1.6rem; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: white; font-size: 0.75rem; font-weight: 700; border-radius: 50%; flex-shrink: 0; margin-top: 0.1rem; }}
        .action-body {{ flex: 1; }}

        /* ── Adoption stats ── */
        .stat-list {{ list-style: none; padding: 0; display: grid; gap: 0.6rem; }}
        .stat-list li {{ padding: 0.75rem 1rem; background: #f0fdf4; border-left: 3px solid var(--green); border-radius: 0 8px 8px 0; font-size: 0.875rem; color: var(--navy); line-height: 1.6; }}
        .stat-note {{ font-size: 0.75rem; color: var(--gray); margin-top: 0.75rem; font-style: italic; }}

        /* ── Bullet list (generic) ── */
        .bullet-list {{ list-style: none; padding: 0; }}
        .bullet-list li {{ position: relative; padding-left: 1.5rem; margin-bottom: 0.875rem; line-height: 1.7; color: var(--gray); font-size: 0.9rem; }}
        .bullet-list li::before {{ content: '●'; position: absolute; left: 0; color: var(--blue); font-size: 0.6rem; top: 0.35rem; }}

        /* ── Roberts Take ── */
        .roberts-take {{ background: linear-gradient(135deg, var(--navy) 0%, #2d3f5c 100%); color: white; border-radius: 12px; padding: 1.75rem; margin-top: 0.5rem; }}
        .roberts-take-header {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; }}
        .roberts-take-header img {{ width: 40px; height: 40px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.3); object-fit: cover; }}
        .roberts-take-label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; }}
        .roberts-take-name {{ font-weight: 700; font-size: 0.95rem; }}
        .roberts-take-body {{ font-size: 0.95rem; line-height: 1.75; opacity: 0.95; font-style: italic; }}
        .roberts-take-placeholder {{ font-size: 0.85rem; line-height: 1.7; opacity: 0.7; border: 1px dashed rgba(255,255,255,0.3); padding: 1rem; border-radius: 8px; }}

        /* ── Conclusion ── */
        .conclusion {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: white; padding: 2rem; border-radius: 12px; margin-top: 2rem; }}
        .conclusion p {{ color: rgba(255,255,255,0.95); font-size: 0.975rem; font-weight: 500; line-height: 1.7; }}
        .conclusion strong {{ color: white; }}

        /* ── Earlier insights ── */
        .earlier-insights {{ margin-top: 2.5rem; padding-top: 2rem; border-top: 1px solid #f1f5f9; }}
        .earlier-posts-grid {{ display: grid; gap: 0.75rem; margin-top: 1rem; }}
        .earlier-post-link {{ display: block; padding: 0.875rem 1.1rem; border: 1px solid #e2e8f0; border-radius: 10px; text-decoration: none; color: inherit; transition: all 0.2s; background: #fafbfc; }}
        .earlier-post-link:hover {{ border-color: var(--blue); background: white; transform: translateX(4px); }}
        .earlier-post-title {{ font-size: 0.9rem; font-weight: 600; color: var(--blue); margin-bottom: 0.2rem; }}
        .earlier-post-date {{ font-size: 0.775rem; color: var(--gray); }}

        /* ── General prose ── */
        p {{ margin-bottom: 1rem; line-height: 1.75; color: var(--gray); font-size: 0.925rem; }}
        strong {{ color: var(--navy); font-weight: 600; }}

        /* ── Mobile ── */
        @media (max-width: 640px) {{
            .header h1 {{ font-size: 1.5rem; }}
            .container {{ padding: 1.5rem 1rem 3rem; }}
            .article-content {{ padding: 1.25rem 1rem; }}
            .nav-content {{ flex-direction: column; align-items: flex-start; gap: 0.4rem; }}
            .author-byline {{ padding: 0.875rem 1rem; }}
            .breadcrumb {{ padding: 0.5rem 1rem; }}
            .canada-section {{ padding: 1.1rem; }}
            .actions-list li {{ flex-direction: column; gap: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">&#8592; Back to Blog</a>
            <div class="blog-meta">
                <span>AI Insights for Canadian Business</span>
                <span>&#8226;</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>

    <header class="header">
        <div class="header-content">
            <div class="issue-badge">Monthly Edition &mdash; {month_year}</div>
            <h1>{clean_title}</h1>
            <div class="subtitle">The AI briefing built for Canadian business leaders</div>
            <div class="intro">{excerpt}</div>
        </div>
    </header>

    <div class="container">
        <article class="article-container" itemscope itemtype="https://schema.org/BlogPosting">
            <meta itemprop="headline" content="{clean_title}">
            <meta itemprop="datePublished" content="{iso_date}">
            <meta itemprop="dateModified" content="{iso_date}">
            <meta itemprop="author" content="Robert Simon">
            <meta itemprop="description" content="{meta_desc}">

            <nav class="breadcrumb" aria-label="Breadcrumb">
                <a href="https://www.imetrobert.com">Home</a> &#8250;
                <a href="https://www.imetrobert.com/blog/">AI Insights Blog</a> &#8250;
                <span>{clean_title}</span>
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
                    <p><strong>The Bottom Line for Canadian Leaders:</strong> {_build_conclusion(sections, month_year)}</p>
                </div>
            </div>
        </article>
    </div>
</body>
</html>'''

    return html


def _build_roberts_take(raw_text, month_year):
    """Build the Robert's Take section HTML."""
    # Check if it's still a placeholder
    is_placeholder = not raw_text or '[ROBERTS TAKE' in raw_text.upper() or len(raw_text.strip()) < 30

    header = '''<div class="roberts-take-header">
        <img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon">
        <div>
            <div class="roberts-take-label">Editor\'s Note</div>
            <div class="roberts-take-name">Robert\'s Take</div>
        </div>
    </div>'''

    if is_placeholder:
        body = f'''<div class="roberts-take-placeholder">
        ✏️ <strong>Add your personal perspective before publishing.</strong><br><br>
        What surprised you most this month? What pattern are you seeing across your conversations with Canadian leaders? What would you tell a friend who's a CEO at a mid-size Canadian company right now?<br><br>
        2-3 sentences of your genuine view — this is the E-E-A-T signal that makes this newsletter yours.
        </div>'''
    else:
        cleaned = raw_text.strip()
        # Remove any leading bracket artifacts
        cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned, flags=re.DOTALL).strip()
        body = f'<p class="roberts-take-body">"{cleaned}"</p>'

    return f'<div class="section"><div class="roberts-take">{header}{body}</div></div>'


def _build_conclusion(sections, month_year):
    """Build a conclusion paragraph from parsed sections."""
    impact = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    actions = parse_list_items(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""), min_length=40)

    if impact:
        # Use the last sentence of the impact section
        sentences = re.split(r'(?<=[.!?])\s+', impact.strip())
        if sentences:
            base = sentences[-1].strip()
            if base and len(base) > 40:
                return f"{base} The organizations that act on this month's developments now will define their sector's AI baseline for the next 12 months."

    if actions:
        return (f"With {len(actions)} clear priorities identified this month, Canadian leaders have no shortage of direction. "
                f"The question is not whether to act on AI — it's whether you act before your competitors do.")

    return (f"The {month_year} AI landscape demands decisive action from Canadian business leaders. "
            f"Strategy documents are not enough — the gap between AI-adopting and AI-waiting organizations is widening every month.")


# ══════════════════════════════════════════════════════════════════
# BLOG INDEX + SUPPORTING UTILITIES  (unchanged from original)
# ══════════════════════════════════════════════════════════════════

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
    blog_meta = soup.find("div", class_="blog-meta")
    if blog_meta:
        meta_text = blog_meta.get_text()
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
    intro_div = soup.find("div", class_="intro") or soup.find("p", class_="intro-lead")
    if intro_div:
        excerpt = re.sub(r'\s+', ' ', intro_div.get_text()).strip()[:200]
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

    latest   = validated[0]
    older    = validated[1:]

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
    for i, post in enumerate(validated[:10], 1):
        url = f"https://www.imetrobert.com/blog/posts/{post['filename']}"
        itemlist_elements.append(
            f'{{"@type":"ListItem","position":{i},"url":"{url}","name":{json.dumps(post["title"])}}}'
        )

    return f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI News for Canadians | Monthly AI Insights Blog | Robert Simon</title>
    <meta name="description" content="Monthly AI insights for Canadian business leaders. Stay ahead with expert analysis of AI breakthroughs, Canadian AI adoption data, and practical implementation strategies from Montreal-based AI thought leader Robert Simon.">
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
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://www.imetrobert.com/blog/">
    <meta property="og:title" content="AI News for Canadians | Monthly AI Insights Blog | Robert Simon">
    <meta property="og:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI thought leader Robert Simon.">
    <meta property="og:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="AI News for Canadians | Monthly AI Insights | Robert Simon">
    <meta name="twitter:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI thought leader Robert Simon.">
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
        body {{ font-family: Inter, sans-serif; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); margin: 0; padding: 0; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
        header {{ background: linear-gradient(135deg, #2563eb 0%, #06b6d4 50%, #8b5cf6 100%); color: white; padding: 4rem 0; text-align: center; margin-bottom: 2.5rem; border-radius: 20px; }}
        h1 {{ font-size: 3rem; font-weight: 700; margin-bottom: 0.5rem; }}
        .nav-bar {{ background: white; padding: 1rem 0; box-shadow: 0 1px 3px rgb(0 0 0 / 0.08); position: sticky; top: 0; z-index: 100; }}
        .nav-content {{ max-width: 1100px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: flex-start; }}
        .nav-link {{ color: white; text-decoration: none; font-weight: 600; padding: 0.5rem 1.25rem; font-size: 0.875rem; border-radius: 20px; background: linear-gradient(135deg, #2563eb, #06b6d4); }}
        .latest-post-section {{ background: linear-gradient(135deg, #2563eb 0%, #06b6d4 50%, #8b5cf6 100%); color: white; padding: 3rem; border-radius: 20px; margin-bottom: 2.5rem; }}
        .latest-badge {{ background: rgba(255,255,255,0.25); color: white; padding: 0.4rem 1rem; border-radius: 20px; display: inline-block; margin-bottom: 1rem; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }}
        .latest-post-title {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 1rem; }}
        .read-latest-btn {{ background: rgba(255,255,255,0.2); color: white; border: 2px solid rgba(255,255,255,0.35); padding: 0.7rem 1.75rem; border-radius: 25px; text-decoration: none; display: inline-block; transition: all 0.25s; font-weight: 600; }}
        .read-latest-btn:hover {{ background: rgba(255,255,255,0.3); transform: translateY(-2px); }}
        .older-posts-section {{ background: white; border-radius: 20px; padding: 2.5rem; box-shadow: 0 10px 30px rgb(0 0 0 / 0.07); }}
        .older-posts-title {{ font-size: 1.6rem; margin-bottom: 2rem; text-align: center; color: #1e293b; font-weight: 700; }}
        .older-post-item {{ border: 1px solid #f1f5f9; border-radius: 12px; margin-bottom: 0.875rem; transition: all 0.25s; }}
        .older-post-item:hover {{ border-color: #2563eb; box-shadow: 0 4px 12px rgb(37 99 235 / 0.1); }}
        .older-post-link {{ display: block; padding: 1.25rem 1.5rem; text-decoration: none; color: inherit; }}
        .older-post-title {{ font-size: 1.1rem; font-weight: 600; color: #2563eb; margin-bottom: 0.35rem; }}
        .older-post-date {{ font-size: 0.85rem; color: #64748b; }}
        .no-posts-message {{ text-align: center; padding: 2rem; color: #64748b; }}
        .blog-tagline {{ font-size: 1.05rem; opacity: 0.9; margin-top: 0.5rem; }}
        @media (max-width: 640px) {{
            h1 {{ font-size: 2rem; }}
            .container {{ padding: 1rem; }}
            .latest-post-section {{ padding: 1.75rem; }}
            .latest-post-title {{ font-size: 1.35rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com" class="nav-link">&#8592; Back to Homepage</a>
        </div>
    </nav>
    <div class="container">
        <header>
            <h1>AI Insights Blog</h1>
            <p>The monthly AI briefing built for Canadian business leaders</p>
            <p class="blog-tagline">Curated by Robert Simon &mdash; Montreal, QC</p>
        </header>
        <section class="latest-post-section">
            <div class="latest-badge">Latest Issue</div>
            <h2 class="latest-post-title">{latest['title']}</h2>
            <div style="margin-bottom: 1rem; opacity: 0.9; font-size: 0.9rem;">{latest['date']}</div>
            <p style="line-height: 1.65; margin-bottom: 1.5rem; opacity: 0.95; font-size: 0.95rem;">{latest['excerpt']}</p>
            <a href="/blog/posts/latest.html" class="read-latest-btn">Read This Month\'s Issue &#8594;</a>
        </section>
        <section class="older-posts-section">
            <h3 class="older-posts-title">Previous Issues</h3>
            <div class="older-posts-grid">{older_html}</div>
        </section>
    </div>
</body>
</html>'''


def update_blog_index():
    posts_dir  = "blog/posts"
    index_file = "blog/index.html"
    if not os.path.exists(posts_dir):
        return []

    latest_path = os.path.join(posts_dir, "latest.html")
    posts = []
    if os.path.exists(latest_path) and os.path.getsize(latest_path) > 100:
        try:
            info = extract_post_info(latest_path)
            if info:
                info['filename'] = 'latest.html'
                posts.append(info)
        except Exception as e:
            print(f"Warning: could not read latest.html: {e}")

    html_files = [
        f for f in os.listdir(posts_dir)
        if f.endswith(".html") and f not in ("latest.html", "index.html")
        and not f.startswith("{") and '{' not in f
    ]
    for fname in sorted(html_files, reverse=True):
        try:
            info = extract_post_info(os.path.join(posts_dir, fname))
            if info:
                posts.append(info)
        except Exception:
            continue

    if not posts:
        print("Warning: no posts found for index.")
        return []

    # Dedupe by month
    seen, deduped = set(), []
    for post in posts:
        try:
            d = datetime.strptime(post['date'], "%B %d, %Y")
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
    return deduped


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic",  help="Custom topic (optional)")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"])
    args = parser.parse_args()

    print("=== Blog Generator (improved) ===")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        sys.exit(1)

    try:
        result     = generate_blog_with_gemini(api_key, args.topic)
        month_year = datetime.now().strftime("%B %Y")
        title, excerpt = extract_title_and_excerpt(result["content"], month_year)

        print(f"Title:   {title}")
        print(f"Excerpt: {excerpt[:80]}...")

        html_content = create_html_blog_post(result["content"], title, excerpt)

        iso_date   = datetime.now().strftime("%Y-%m-%d")
        filename   = f"{iso_date}-{clean_filename(title)}.html"
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)

        out_path = os.path.join(output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            f.flush()
            os.fsync(f.fileno())
        print(f"Saved: {out_path}")

        # Also write latest.html
        latest_path = os.path.join("blog", "posts", "latest.html")
        os.makedirs(os.path.dirname(latest_path), exist_ok=True)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            f.flush()
            os.fsync(f.fileno())
        print("Updated latest.html")

        import time; time.sleep(0.2)
        update_blog_index()
        print("SUCCESS.")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
