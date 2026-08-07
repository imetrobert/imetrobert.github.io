"""
survey.py
Publishes the Canadian AI Pulse reader survey results as blog/canadian-ai-pulse.html.

The point of this page is to make Robert a PRIMARY source. Everything else on
the site reports numbers other organisations produced, which is a crowded place
to be cited from. A figure that exists nowhere else — "x% of Canadian leaders
say their AI pilots reached production" — is the kind of thing that gets quoted,
and the quote has to name where it came from.

Collection is off-site: GitHub Pages is static and cannot receive form posts, so
responses are gathered with an external form and the tallies are recorded in
data/survey.json.

Two rules enforced here, both about not overclaiming:
  * the page is written only when a wave actually exists, so there is never a
    results page describing data that has not been collected;
  * n and the field dates are printed next to every chart, and the citation
    block includes n, because a sample presented without its size is the thing
    that gets a number discredited once someone checks.
"""

import html as H
import json
import os
from datetime import datetime

from utils import BRAND

BASE = "https://www.imetrobert.com"
OUT = "blog/canadian-ai-pulse.html"
CANONICAL = f"{BASE}/blog/canadian-ai-pulse.html"
CONFIG = "data/survey.json"

BLUE, CYAN = "#2563eb", "#06b6d4"


def load():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def _pct(counts):
    total = sum(counts.values()) or 1
    return {k: round(v * 100 / total, 1) for k, v in counts.items()}


def _bars(question, counts):
    """Inline SVG bar chart. No charting library: it would be a third-party
    request on a page whose whole purpose is to be quotable and fast."""
    pcts = _pct(counts)
    opts = [o for o in question["options"] if o in counts]
    row_h, gap, label_w, chart_w = 30, 10, 250, 300
    height = len(opts) * (row_h + gap)
    rows = ""
    for i, opt in enumerate(opts):
        y = i * (row_h + gap)
        pct = pcts[opt]
        w = max(2, pct / 100 * chart_w)
        rows += (
            f'<text x="0" y="{y + 20}" class="bar-label">{H.escape(opt)}</text>'
            f'<rect x="{label_w}" y="{y + 6}" width="{w:.1f}" height="18" rx="4" fill="url(#barGrad)"/>'
            f'<text x="{label_w + w + 8:.1f}" y="{y + 20}" class="bar-value">{pct}%</text>'
        )
    return (
        f'<svg class="chart" viewBox="0 0 {label_w + chart_w + 60} {height}" '
        f'role="img" aria-label="{H.escape(question["text"])}">'
        f'<defs><linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{BLUE}"/><stop offset="100%" stop-color="{CYAN}"/>'
        f'</linearGradient></defs>{rows}</svg>'
    )


def _headline(cfg, wave):
    """The single number the page exists to be quoted for."""
    q = next((q for q in cfg["questions"] if q.get("headline")), cfg["questions"][0])
    counts = wave["results"].get(q["id"], {})
    if not counts:
        return None, q
    pcts = _pct(counts)
    prod = sum(v for k, v in pcts.items() if "production" in k.lower())
    return round(prod, 1), q


def build_page(cfg, waves):
    latest = waves[-1]
    n = latest["n"]
    field = latest.get("field_dates", latest.get("date", ""))
    prod_pct, headline_q = _headline(cfg, latest)
    generated = datetime.now().strftime("%B %d, %Y")
    cite = (f"Robert Simon, “{cfg['survey_name']}”, {latest.get('label', '')} "
            f"(n={n}). {CANONICAL}")

    charts = ""
    for q in cfg["questions"]:
        counts = latest["results"].get(q["id"])
        if not counts:
            continue
        charts += (
            f'<section class="q-block">'
            f'<h3 class="q-text">{H.escape(q["text"])}</h3>'
            f'{_bars(q, counts)}'
            f'<p class="q-note">n={n}. Percentages may not total 100 due to rounding.</p>'
            f'</section>'
        )

    trend = ""
    if len(waves) > 1:
        rows = ""
        for w in waves:
            p, _ = _headline(cfg, w)
            rows += (f'<tr><td>{H.escape(w.get("label", ""))}</td>'
                     f'<td>{w["n"]}</td><td>{p if p is not None else "—"}%</td></tr>')
        trend = (
            '<h2 class="sec">Wave over wave</h2>'
            '<div class="table-wrap"><table class="trend">'
            '<thead><tr><th>Wave</th><th>Responses</th><th>In production</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )

    lead = (f"{prod_pct}% of responding Canadian organizations have AI running in production."
            if prod_pct is not None else
            f"Results from the {cfg['survey_name']} reader survey.")

    faq = [
        (f"How many Canadian organizations have AI in production?",
         f"In the {latest.get('label','')} wave of the {cfg['survey_name']} survey, "
         f"{prod_pct}% of {n} responding Canadian organizations reported AI running in "
         f"production in at least one area." if prod_pct is not None else
         f"See the {latest.get('label','')} results above."),
        ("Who is surveyed, and how?",
         f"{cfg['audience']}. Responses are self-reported through an open online form "
         f"linked from each monthly issue. This is a readership sample, not a randomised "
         f"national sample, so it describes this audience rather than all Canadian "
         f"businesses — n is reported with every figure."),
        ("Can I cite these figures?",
         f"Yes, with attribution. Suggested citation: {cite}"),
    ]
    faq_html = "".join(
        f'<div class="faq-item"><h3 class="faq-q">{H.escape(q)}</h3>'
        f'<p class="faq-a">{H.escape(a)}</p></div>' for q, a in faq)
    faq_schema = ",\n".join(
        '{"@type":"Question","name":%s,"acceptedAnswer":{"@type":"Answer","text":%s}}'
        % (json.dumps(q), json.dumps(a)) for q, a in faq)

    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<title>{H.escape(cfg['survey_name'])}: original survey data on Canadian AI adoption | Robert Simon</title>
<meta name="description" content="{H.escape(lead)} Original reader survey data from {BRAND}, with methodology and sample size.">
<meta name="author" content="Robert Simon">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<link rel="canonical" href="{CANONICAL}">
<meta property="og:type" content="article">
<meta property="og:url" content="{CANONICAL}">
<meta property="og:title" content="{H.escape(cfg['survey_name'])}: original Canadian AI adoption data">
<meta property="og:description" content="{H.escape(lead)}">
<meta property="og:image" content="{BASE}/blog/og/canadian-ai-pulse.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{H.escape(cfg['survey_name'])} survey results">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{BASE}/blog/og/canadian-ai-pulse.jpg">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "{H.escape(cfg['survey_name'])} \\u2014 {H.escape(latest.get('label',''))}",
  "description": "Original reader survey of Canadian business and technology leaders on AI adoption stage, blockers, spend and policy. n={n}.",
  "url": "{CANONICAL}",
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "isAccessibleForFree": true,
  "inLanguage": "en-CA",
  "temporalCoverage": "{H.escape(str(field))}",
  "spatialCoverage": {{"@type": "Place", "name": "Canada"}},
  "creator": {{
    "@type": "Person",
    "name": "Robert Simon",
    "url": "{BASE}",
    "sameAs": ["https://linkedin.com/in/thedigitalrobert"]
  }},
  "variableMeasured": [{", ".join(json.dumps(q["text"]) for q in cfg["questions"])}]
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
    {{"@type": "ListItem", "position": 2, "name": "{BRAND}", "item": "{BASE}/blog/"}},
    {{"@type": "ListItem", "position": 3, "name": "{H.escape(cfg['survey_name'])}", "item": "{CANONICAL}"}}
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
body {{ font-family:'Inter',-apple-system,sans-serif; background:linear-gradient(160deg,#f0f4ff 0%,#e8eef8 100%); color:var(--navy); line-height:1.6; -webkit-font-smoothing:antialiased; }}
.nav-bar {{ background:var(--white); padding:0.875rem 0; border-bottom:1px solid var(--border); }}
.nav-content {{ max-width:900px; margin:0 auto; padding:0 1.5rem; }}
.nav-link {{ color:var(--white); text-decoration:none; font-weight:600; padding:0.4rem 1rem; font-size:0.8rem; border-radius:20px; background:linear-gradient(135deg,var(--blue),var(--cyan)); }}
.header {{ background:linear-gradient(135deg,var(--blue) 0%,#1a7fb5 50%,var(--cyan) 100%); color:var(--white); padding:3.5rem 0 3rem; text-align:center; }}
.header-content {{ max-width:780px; margin:0 auto; padding:0 1.5rem; }}
.brand-logo {{ width:76px; height:76px; display:block; margin:0 auto 1.5rem; padding:7px; box-sizing:content-box; background:rgba(255,255,255,0.96); border-radius:23px; box-shadow:0 10px 26px rgba(15,23,42,0.25); }}
.header h1 {{ font-size:clamp(1.6rem,4.5vw,2.3rem); font-weight:800; line-height:1.2; margin-bottom:0.6rem; }}
.badge {{ display:inline-block; background:rgba(255,255,255,0.18); border:1px solid rgba(255,255,255,0.3); padding:0.25rem 0.85rem; border-radius:20px; font-size:0.68rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:1rem; }}
.container {{ max-width:900px; margin:0 auto; padding:2.5rem 1.5rem 5rem; }}
.card {{ background:var(--white); border-radius:20px; box-shadow:0 8px 32px rgb(0 0 0/0.10); border:1px solid rgba(226,232,240,0.6); padding:2rem; }}
.headline-stat {{ font-size:clamp(1.6rem,5vw,2.4rem); font-weight:800; line-height:1.25; letter-spacing:-0.02em; color:var(--navy); border-left:4px solid var(--cyan); padding-left:1.25rem; margin-bottom:1.5rem; }}
.method {{ font-size:0.82rem; color:var(--gray); background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1rem 1.25rem; margin-bottom:2rem; }}
h2.sec {{ font-size:1.2rem; font-weight:700; margin:2.5rem 0 1.25rem; padding-left:0.875rem; position:relative; }}
h2.sec::before {{ content:''; position:absolute; left:0; top:0.15rem; bottom:0.15rem; width:3px; background:linear-gradient(to bottom,var(--blue),var(--cyan)); border-radius:2px; }}
.q-block {{ margin-bottom:2rem; }}
.q-text {{ font-size:0.95rem; font-weight:700; margin-bottom:0.9rem; }}
.chart {{ width:100%; height:auto; overflow:visible; }}
.bar-label {{ font-size:13px; fill:#1e293b; }}
.bar-value {{ font-size:13px; font-weight:700; fill:var(--blue); }}
.q-note {{ font-size:0.72rem; color:var(--gray-light); margin-top:0.5rem; }}
.table-wrap {{ overflow-x:auto; }}
table.trend {{ border-collapse:collapse; width:100%; font-size:0.85rem; }}
table.trend th, table.trend td {{ text-align:left; padding:0.6rem 0.75rem; border-bottom:1px solid var(--border); }}
table.trend th {{ font-size:0.72rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--gray-light); }}
.cite {{ margin-top:2rem; background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--blue); border-radius:12px; padding:1rem 1.25rem; }}
.cite h3 {{ font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; color:var(--gray-light); margin-bottom:0.5rem; }}
.cite code {{ display:block; font-size:0.8rem; line-height:1.6; color:#1e293b; word-break:break-word; }}
.faq-item {{ padding:1rem 1.25rem; background:var(--surface); border:1px solid var(--border); border-radius:12px; border-left:3px solid var(--blue); margin-bottom:0.875rem; }}
.faq-q {{ font-size:0.925rem; font-weight:700; margin-bottom:0.4rem; }}
.faq-a {{ font-size:0.875rem; color:var(--gray); line-height:1.7; }}
.updated {{ margin-top:2rem; font-size:0.75rem; color:var(--gray-light); }}
@media (max-width:640px) {{ .container {{ padding:1.5rem 1rem 3rem; }} .card {{ padding:1.25rem; }} .bar-label {{ font-size:11px; }} }}
</style>
</head>
<body>
<nav class="nav-bar"><div class="nav-content"><a href="/blog/" class="nav-link">&#8592; Back to Blog</a></div></nav>
<header class="header"><div class="header-content">
  <img src="/blog/logo.svg" class="brand-logo" alt="{BRAND}" width="76" height="76">
  <div class="badge">Original research</div>
  <h1>{H.escape(cfg['survey_name'])}</h1>
  <p>Reader survey of Canadian business and technology leaders</p>
</div></header>
<div class="container"><div class="card">
  <p class="headline-stat">{H.escape(lead)}</p>
  <p class="method"><strong>Methodology.</strong> {H.escape(cfg['audience'])}.
  Self-reported responses collected through an open online form linked from each monthly issue,
  fielded {H.escape(str(field))}. n={n}. This is a readership sample, not a randomised national
  sample: it describes what this audience reports, not all Canadian businesses. Sample size is
  published with every figure so readers can weigh it themselves.</p>
  <h2 class="sec">Results</h2>
  {charts}
  {trend}
  <div class="cite"><h3>Cite this</h3><code>{H.escape(cite)}</code></div>
  <h2 class="sec">Questions about this data</h2>
  {faq_html}
  <p class="updated">Last updated {generated}.</p>
</div></div>
</body>
</html>"""


def write_survey_page():
    cfg = load()
    if not cfg:
        return None
    waves = [w for w in cfg.get("waves", []) if w.get("results") and w.get("n")]
    if not waves:
        print("Survey: no published waves yet; results page not written.")
        return None

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_page(cfg, waves))
    print(f"Survey results page updated ({len(waves)} wave(s), latest n={waves[-1]['n']}).")

    try:
        from og_image import build_og_image
        build_og_image("blog/og/canadian-ai-pulse.jpg", "Original research",
                       headline="Canadian AI Pulse", subhead="reader survey results")
    except Exception as e:
        print(f"  survey OG card unavailable ({e})")
    return OUT


if __name__ == "__main__":
    write_survey_page()
