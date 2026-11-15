"""
pillar_plans.py
Builds blog/ai-plan-changes.html: an evergreen page listing every "New in Your AI Subscription" item
published in the issues (what the ChatGPT, Claude, Gemini and Microsoft 365 Copilot plans gained or changed),
newest issue first, each with its source and a link to the issue. It exists so a small-business owner
searching "what changed in ChatGPT / Claude / Copilot plans" can land on a page that stays current,
and so the page carries the free feasibility check link to the Business site.

Same rule as pillar_adoption.py: nothing is written that was not already published in an issue.
Only issues from the December 2026 format on have the section, so the page appears after that issue.
Writes nothing until at least one item exists. Called from blog_index.update_blog_index() (failures are logged, never block a publish).
"""
import glob
import html as H
import os
import re
from datetime import datetime

from utils import BRAND

BASE = "https://www.imetrobert.com"
OUT = "blog/ai-plan-changes.html"
CANONICAL = f"{BASE}/blog/ai-plan-changes.html"
SECTION = "New in Your AI Subscription"
BIZ = "https://biz.aiwithrobert.com/"


def _clean(t):
    return re.sub(r"\s+", " ", t or "").strip()


def collect_items(posts_glob="blog/posts/*.html"):
    from bs4 import BeautifulSoup
    from pillar_adoption import _issue_meta
    rows = []
    for path in sorted(glob.glob(posts_glob), reverse=True):
        if os.path.basename(path) == "latest.html":
            continue
        src = open(path, encoding="utf-8").read()
        if SECTION not in src or ('http-equiv="refresh"' in src.lower()[:4000] and "noindex" in src.lower()[:4000]):
            continue
        soup = BeautifulSoup(src, "html.parser")
        h2 = next((h for h in soup.find_all("h2") if SECTION in h.get_text()), None)
        sec = h2.find_parent("div", class_="section") if h2 else None
        if not sec:
            continue
        meta = _issue_meta(path, src)
        for card in sec.find_all("div", class_="dev-card"):
            body = card.find(class_="dev-body")
            if not body:
                continue
            company = card.find(class_="dev-company")
            date = card.find(class_="dev-date")
            a = card.find(class_="dev-source")
            rows.append({"issue": meta, "company": _clean(company.get_text()) if company else "",
                         "date": _clean(date.get_text()) if date else "",
                         "text": _clean(body.get_text()),
                         "source": _clean(a.get_text()) if a else "",
                         "source_url": (a.find("a") or {}).get("href", "") if a else ""})
    return rows


def build_page(rows):
    updated = datetime.now().strftime("%B %d, %Y")
    groups, last = "", None
    for r in rows:
        u = r["issue"]["url"]
        if u != last:
            if last is not None:
                groups += "</ul></section>"
            groups += (f'<section class="g"><h3>{H.escape(r["issue"]["month"] or r["issue"]["title"])}</h3><ul>')
            last = u
        src = ""
        if r["source"]:
            src = (f'<span class="s"><a href="{H.escape(r["source_url"])}" rel="noopener">{H.escape(r["source"])}</a></span>'
                   if r["source_url"] else f'<span class="s">{H.escape(r["source"])}</span>')
        head = " ".join(x for x in (r["company"], r["date"]) if x)
        groups += f'<li><strong>{H.escape(head)}</strong> {H.escape(r["text"])} {src}</li>'
    if last is not None:
        groups += "</ul></section>"
    n_issues = len({r["issue"]["url"] for r in rows})
    cta = (f"{BIZ}?utm_source=imetrobert-blog&amp;utm_medium=page&amp;utm_campaign=plans-page#feas-check")
    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<title>What changed in ChatGPT, Claude, Gemini and Copilot plans | Robert Simon</title>
<meta name="description" content="What the ChatGPT, Claude, Gemini and Microsoft 365 Copilot plans gained or changed, month by month, with sources. Written for small businesses.">
<meta name="author" content="Robert Simon">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<link rel="canonical" href="{CANONICAL}">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Article","headline":"What changed in ChatGPT, Claude, Gemini and Copilot plans","dateModified":"{datetime.now().strftime('%Y-%m-%d')}","author":{{"@type":"Person","name":"Robert Simon","url":"{BASE}"}},"url":"{CANONICAL}","inLanguage":"en-CA","isAccessibleForFree":true}}
</script>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;margin:0;background:#f1f5f9;color:#0f172a;line-height:1.65}}
.w{{max-width:760px;margin:0 auto;padding:1.5rem 1.2rem 4rem}} a{{color:#2563eb}}
h1{{font-size:1.6rem;line-height:1.25;margin:1rem 0 .5rem}} .lead{{border-left:3px solid #06b6d4;padding-left:1rem;margin:1rem 0 1.5rem}}
.g{{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:1rem 1.25rem;margin:0 0 1rem}} .g h3{{margin:0 0 .5rem;font-size:1.05rem}}
.g ul{{padding-left:1.1rem;margin:0}} .g li{{margin:.6rem 0;font-size:.92rem}} .s{{display:block;font-size:.75rem}}
.i{{font-size:.78rem;display:block;margin-top:.4rem}}
.cta{{background:#11304c;color:#fff;border-radius:14px;padding:1.25rem;margin:2rem 0}} .cta a{{display:inline-block;background:#c9a227;color:#11304c;font-weight:700;padding:.6rem 1.3rem;border-radius:24px;text-decoration:none;margin-top:.6rem}}
.u{{font-size:.75rem;color:#64748b}}
</style>
</head>
<body><div class="w">
<p><a href="/blog/">&#8592; Back to the blog</a></p>
<h1>What changed in ChatGPT, Claude, Gemini and Copilot plans</h1>
<p class="lead">The AI plans a small business pays for keep gaining features and changing terms. This page collects every plan change reported in {H.escape(BRAND)}, newest first, with its source, so you can see what your plan can do now. {n_issues} issue{'s' if n_issues != 1 else ''} so far.</p>
{groups}
<div class="cta"><strong>Does your plan do what you need?</strong><br>The free feasibility check takes about two minutes: name your plan and up to three things you would like it to do, and see a Yes, Partly or No for each one.<br><a href="{cta}">Get a free feasibility check</a></div>
<p class="u">Each item is reproduced from the issue where it was reported; follow the source before relying on a price or limit. Regenerated automatically with each new issue. Last updated {updated}.</p>
</div></body></html>"""


def write_plans_page():
    rows = collect_items()
    if not rows:
        print("Plans page: no plan-change items yet; page not written.")
        return None
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_page(rows))
    print(f"Plans page updated ({len(rows)} items from {len({r['issue']['url'] for r in rows})} issues).")
    return OUT


if __name__ == "__main__":
    write_plans_page()
