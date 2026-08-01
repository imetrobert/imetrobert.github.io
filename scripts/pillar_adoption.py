"""
pillar_adoption.py
Builds blog/canadian-ai-adoption.html — the evergreen adoption-statistics page.

Why an aggregate page: the archive is fourteen dated roundups, and a roundup is
cited for about as long as it is new. A statistics page keyed to a question
people actually ask ("how many Canadian businesses use AI?") stays citable, and
gets better every month instead of decaying.

Everything here is extracted from figures ALREADY PUBLISHED in the issues, with
the source named in that issue and a link back to it. Nothing is invented, and
no figure appears without its issue attribution — the page is an index of
Robert's own reporting, not a new claim on top of it.

Two markup eras are handled: the current template exposes .stat-text /
.stat-source, and the older one puts the figures in a <ul class="bullet-list">
under an "Adoption" heading.
"""

import glob
import html as H
import os
import re
from datetime import datetime

BASE = "https://www.imetrobert.com"
OUT = "blog/canadian-ai-adoption.html"
CANONICAL = f"{BASE}/blog/canadian-ai-adoption.html"

MONTHS = ("January February March April May June July August September "
          "October November December").split()


def _text(fragment):
    t = H.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", t).strip(" —-•*")


def _issue_meta(path, source):
    """Title, url and sort date for the issue a figure came from."""
    base = os.path.basename(path)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", source, re.S)
    title = _text(h1.group(1)) if h1 else base
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", base)
    date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else datetime.min
    label = re.search(r"(%s)\s+(\d{4})" % "|".join(MONTHS), title)
    return {
        "title": title,
        "url": f"{BASE}/blog/posts/{base}",
        "date": date,
        "month": f"{label.group(1)} {label.group(2)}" if label
                 else (date.strftime("%B %Y") if date != datetime.min else ""),
    }


def collect_stats():
    rows, seen = [], set()

    for path in sorted(glob.glob("blog/posts/*.html"), reverse=True):
        if os.path.basename(path) == "latest.html":
            continue                      # a copy of the newest issue; would double-count
        src = open(path, encoding="utf-8").read()
        meta = _issue_meta(path, src)
        found = []

        # current template
        for m in re.finditer(r'<div class="stat-item">(.*?)</div>\s*</div>', src, re.S):
            block = m.group(1)
            stat = _text(re.search(r'class="stat-text">(.*?)</p>', block, re.S).group(1)) \
                if re.search(r'class="stat-text">', block) else ""
            srcname = re.search(r'class="stat-source(?:-plain)?"[^>]*>(.*?)</div>', block, re.S)
            if stat:
                found.append((stat, _text(srcname.group(1)) if srcname else ""))

        # older template: bullet list under the adoption heading
        if not found:
            sec = re.search(r"Adoption[^<]*</h2>(.*?)</ul>", src, re.S)
            if sec:
                for li in re.findall(r"<li>(.*?)</li>", sec.group(1), re.S):
                    stat = _text(li)
                    if stat and re.search(r"\d", stat):
                        found.append((stat, ""))

        for stat, srcname in found:
            if len(stat) < 25:
                continue
            key = re.sub(r"[^a-z0-9]", "", stat.lower())[:90]
            if key in seen:               # the same figure repeats across issues
                continue
            seen.add(key)
            rows.append({"stat": stat, "source": srcname, **meta})

    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def _faq(rows):
    latest = rows[0] if rows else None
    pct = next((re.search(r"(\d{1,3}(?:\.\d)?%)", r["stat"]) for r in rows
                if re.search(r"(\d{1,3}(?:\.\d)?%)", r["stat"])), None)
    items = []
    if latest:
        items.append((
            "What is the most recent Canadian AI adoption figure tracked here?",
            f"{latest['stat']} This figure was reported in the {latest['month']} issue"
            + (f", sourced to {latest['source']}." if latest['source'] else ".")))
    items.append((
        "Where do these Canadian AI adoption numbers come from?",
        "Each figure is reproduced from a monthly issue of AI Insights for Canadian "
        "Business, with the source named in that issue. Every row links back to the "
        "issue it appeared in so the original reporting and its source can be checked."))
    items.append((
        "How often is this page updated?",
        "It is regenerated whenever a new issue is published, which is monthly. "
        "Figures are added as they are reported; earlier figures are kept so the "
        "trend over time stays visible rather than being overwritten."))
    return items


def build_page(rows):
    generated = datetime.now().strftime("%B %d, %Y")
    faq_items = _faq(rows)

    by_issue = []
    for r in rows:
        if not by_issue or by_issue[-1][0]["url"] != r["url"]:
            by_issue.append((r, [r]))
        else:
            by_issue[-1][1].append(r)

    groups = ""
    for meta, items in by_issue:
        lis = "".join(
            f'<li class="stat-row"><span class="stat-body">{H.escape(i["stat"])}</span>'
            + (f'<span class="stat-src">{H.escape(i["source"])}</span>' if i["source"] else "")
            + "</li>"
            for i in items)
        groups += (
            f'<section class="issue-group">'
            f'<h3 class="issue-month">{H.escape(meta["month"] or meta["title"])}</h3>'
            f'<ul class="stat-rows">{lis}</ul>'
            f'<a class="issue-link" href="{meta["url"]}">'
            f'<svg class="icon" aria-hidden="true" width="1em" height="1em" fill="none" '
            f'stroke="currentColor" stroke-width="1.75"><use href="#i-doc"/></svg> '
            f'Read the full issue: {H.escape(meta["title"])}</a>'
            f'</section>')

    faq_html = "".join(
        f'<div class="faq-item"><h3 class="faq-q">{H.escape(q)}</h3>'
        f'<p class="faq-a">{H.escape(a)}</p></div>' for q, a in faq_items)

    faq_schema = ",\n".join(
        '{"@type":"Question","name":%s,"acceptedAnswer":{"@type":"Answer","text":%s}}'
        % (_json(q), _json(a)) for q, a in faq_items)

    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<title>Canadian AI adoption statistics, tracked monthly | Robert Simon</title>
<meta name="description" content="Every Canadian AI adoption figure tracked in AI Insights for Canadian Business, by month, with the source for each and a link to the issue it was reported in.">
<meta name="author" content="Robert Simon">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<meta name="language" content="en-CA">
<meta name="geo.region" content="CA-QC">
<link rel="canonical" href="{CANONICAL}">
<meta property="og:type" content="article">
<meta property="og:url" content="{CANONICAL}">
<meta property="og:title" content="Canadian AI adoption statistics, tracked monthly">
<meta property="og:description" content="Every Canadian AI adoption figure tracked in AI Insights for Canadian Business, by month, with sources.">
<meta property="og:image" content="{BASE}/blog/og/canadian-ai-adoption.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Canadian AI adoption statistics tracked monthly by Robert Simon">
<meta property="og:site_name" content="Robert Simon - AI Innovation">
<meta property="og:locale" content="en_CA">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Canadian AI adoption statistics, tracked monthly">
<meta name="twitter:description" content="Every Canadian AI adoption figure tracked in AI Insights for Canadian Business, by month, with sources.">
<meta name="twitter:image" content="{BASE}/blog/og/canadian-ai-adoption.jpg">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Canadian AI adoption statistics, tracked monthly",
  "description": "Every Canadian AI adoption figure tracked in AI Insights for Canadian Business, by month, with the source for each.",
  "dateModified": "{datetime.now().strftime('%Y-%m-%d')}",
  "author": {{
    "@type": "Person",
    "name": "Robert Simon",
    "url": "{BASE}",
    "image": "{BASE}/profile.jpg",
    "jobTitle": "AI Thought Leader & Digital Transformation Expert",
    "knowsAbout": ["Artificial Intelligence", "Digital Transformation", "AI Adoption in Canada", "AI Strategy"],
    "sameAs": ["https://linkedin.com/in/thedigitalrobert"],
    "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
  }},
  "publisher": {{
    "@type": "Person",
    "name": "Robert Simon",
    "url": "{BASE}",
    "logo": {{"@type": "ImageObject", "url": "{BASE}/blog/logo-512.png", "width": 512, "height": 512}}
  }},
  "mainEntityOfPage": {{"@type": "WebPage", "@id": "{CANONICAL}"}},
  "url": "{CANONICAL}",
  "inLanguage": "en-CA",
  "isAccessibleForFree": true,
  "about": [
    {{"@type": "Thing", "name": "AI adoption"}},
    {{"@type": "Place", "name": "Canada"}}
  ],
  "speakable": {{"@type": "SpeakableSpecification", "cssSelector": [".pillar-lead", ".faq-q", ".faq-a"]}}
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{faq_schema}]
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "{BASE}"}},
    {{"@type": "ListItem", "position": 2, "name": "AI Insights Blog", "item": "{BASE}/blog/"}},
    {{"@type": "ListItem", "position": 3, "name": "Canadian AI adoption statistics", "item": "{CANONICAL}"}}
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
:root {{ --blue:#2563eb; --cyan:#06b6d4; --navy:#0f172a; --gray:#475569; --gray-light:#94a3b8; --surface:#f8fafc; --border:#e2e8f0; --white:#fff; }}
*,*::before,*::after {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif; background:linear-gradient(160deg,#f0f4ff 0%,#e8eef8 100%); color:var(--navy); line-height:1.6; -webkit-font-smoothing:antialiased; }}
.icon {{ width:1.05em; height:1.05em; flex-shrink:0; fill:none; stroke:currentColor; stroke-width:1.75; stroke-linecap:round; stroke-linejoin:round; vertical-align:-0.14em; }}
.nav-bar {{ background:var(--white); padding:0.875rem 0; box-shadow:0 1px 3px rgb(0 0 0/0.08); border-bottom:1px solid var(--border); }}
.nav-content {{ max-width:900px; margin:0 auto; padding:0 1.5rem; display:flex; align-items:center; gap:0.6rem; }}
.nav-link {{ color:var(--white); text-decoration:none; font-weight:600; padding:0.4rem 1rem; font-size:0.8rem; border-radius:20px; background:linear-gradient(135deg,var(--blue),var(--cyan)); }}
.header {{ background:linear-gradient(135deg,var(--blue) 0%,#1a7fb5 50%,var(--cyan) 100%); color:var(--white); padding:3.5rem 0 3rem; text-align:center; }}
.header-content {{ max-width:780px; margin:0 auto; padding:0 1.5rem; }}
.brand-logo {{ width:76px; height:76px; display:block; margin:0 auto 1.5rem; padding:7px; box-sizing:content-box; background:rgba(255,255,255,0.96); border-radius:23px; box-shadow:0 10px 26px rgba(15,23,42,0.25); }}
.header h1 {{ font-size:clamp(1.6rem,4.5vw,2.4rem); font-weight:800; line-height:1.2; letter-spacing:-0.02em; margin-bottom:0.75rem; }}
.header .sub {{ font-size:0.95rem; opacity:0.88; }}
.container {{ max-width:900px; margin:0 auto; padding:2.5rem 1.5rem 5rem; }}
.card {{ background:var(--white); border-radius:20px; box-shadow:0 8px 32px rgb(0 0 0/0.10); border:1px solid rgba(226,232,240,0.6); padding:2rem; }}
.breadcrumb {{ font-size:0.72rem; color:var(--gray-light); margin-bottom:1.25rem; }}
.breadcrumb a {{ color:var(--blue); text-decoration:none; }}
.pillar-lead {{ font-size:1.02rem; line-height:1.75; color:#1e293b; border-left:3px solid var(--cyan); padding-left:1.25rem; margin-bottom:1.25rem; }}
.method {{ font-size:0.82rem; color:var(--gray); background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1rem 1.25rem; margin-bottom:2rem; }}
.issue-group {{ margin-bottom:1.75rem; padding-bottom:1.5rem; border-bottom:1px solid var(--border); }}
.issue-group:last-of-type {{ border-bottom:none; }}
.issue-month {{ font-size:1.05rem; font-weight:800; color:var(--navy); margin-bottom:0.75rem; letter-spacing:-0.01em; }}
.stat-rows {{ list-style:none; display:grid; gap:0.6rem; margin-bottom:0.75rem; }}
.stat-row {{ padding:0.85rem 1rem; background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--blue); border-radius:10px; }}
.stat-body {{ display:block; font-size:0.9rem; color:#1e293b; line-height:1.65; }}
.stat-src {{ display:block; margin-top:0.3rem; font-size:0.72rem; color:var(--gray-light); font-weight:600; }}
.issue-link {{ display:inline-flex; align-items:center; gap:0.4rem; font-size:0.78rem; font-weight:600; color:var(--blue); text-decoration:none; }}
.issue-link:hover {{ text-decoration:underline; }}
h2.sec {{ font-size:1.2rem; font-weight:700; margin:2.5rem 0 1.25rem; padding-left:0.875rem; position:relative; }}
h2.sec::before {{ content:''; position:absolute; left:0; top:0.15rem; bottom:0.15rem; width:3px; background:linear-gradient(to bottom,var(--blue),var(--cyan)); border-radius:2px; }}
.faq-item {{ padding:1rem 1.25rem; background:var(--surface); border:1px solid var(--border); border-radius:12px; border-left:3px solid var(--blue); margin-bottom:0.875rem; }}
.faq-q {{ font-size:0.925rem; font-weight:700; color:var(--navy); margin-bottom:0.4rem; }}
.faq-a {{ font-size:0.875rem; color:var(--gray); line-height:1.7; }}
.updated {{ margin-top:2rem; font-size:0.75rem; color:var(--gray-light); }}
@media (max-width:640px) {{ .container {{ padding:1.5rem 1rem 3rem; }} .card {{ padding:1.25rem; }} .brand-logo {{ width:58px; height:58px; padding:6px; border-radius:18px; }} }}
</style>
</head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
  <symbol id="i-doc" viewBox="0 0 24 24">
    <path d="M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8z"/>
    <path d="M14 3v5h5"/><path d="M8.5 13h7M8.5 16.5h4.5"/>
  </symbol>
</svg>
<nav class="nav-bar"><div class="nav-content">
  <a href="/blog/" class="nav-link">&#8592; Back to Blog</a>
</div></nav>
<header class="header"><div class="header-content">
  <img src="/blog/logo.svg" class="brand-logo" alt="AI Insights" width="76" height="76">
  <h1>Canadian AI adoption statistics, tracked monthly</h1>
  <p class="sub">Every figure reported in AI Insights for Canadian Business, with its source</p>
</div></header>
<div class="container"><div class="card">
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <a href="{BASE}">Home</a> &#8250; <a href="{BASE}/blog/">AI Insights Blog</a> &#8250;
    <span>Canadian AI adoption statistics</span>
  </nav>
  <p class="pillar-lead">Canadian AI adoption is reported in fragments — a Statistics Canada release here,
  a sector survey there — and the numbers are hard to line up over time. This page collects every adoption
  figure reported in the monthly issues, newest first, so the trend is visible in one place.</p>
  <p class="method"><strong>How to read this.</strong> Each figure is reproduced as it was reported in that
  month's issue, with the source named there. Follow the issue link to see the original context and source
  before citing a number. Figures from earlier months are kept rather than overwritten, so a change in
  methodology between sources stays visible instead of being smoothed away.</p>
  <h2 class="sec">The figures, by issue</h2>
  {groups if groups else '<p>No figures recorded yet.</p>'}
  <h2 class="sec">Questions about this data</h2>
  {faq_html}
  <p class="updated">Regenerated automatically with each new issue. Last updated {generated}.</p>
</div></div>
</body>
</html>"""


def _json(s):
    import json
    return json.dumps(s, ensure_ascii=False)


def write_pillar():
    rows = collect_stats()
    if not rows:
        print("Pillar: no adoption figures found; page not written.")
        return None
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_page(rows))
    print(f"Pillar page updated ({len(rows)} figures from "
          f"{len({r['url'] for r in rows})} issues).")

    try:
        from og_image import build_og_image
        build_og_image("blog/og/canadian-ai-adoption.jpg", "Adoption Tracker",
                       headline="Canadian AI", subhead="adoption, tracked monthly")
    except Exception as e:
        print(f"  pillar OG card unavailable ({e})")
    return OUT


if __name__ == "__main__":
    write_pillar()
