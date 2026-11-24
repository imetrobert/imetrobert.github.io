#!/usr/bin/env python3
"""Monthly content gap suggestion: ONE guide worth adding to biz.aiwithrobert.com, based on the newest blog issue,
the pages that already exist (promo_kit.TARGETS) and the questions where the AI answer check did not name Robert
(ops/ai-answer-log.json). It only SUGGESTS: writes ops/content-gap.json (last 6). Nothing is published.
To act on it: use the "add a guide" prompt in imetrobert/aiwithrobert-root docs/SEO-AIO-GEO.md.
Run from the repo root:  GEMINI_API_KEY=... python3 scripts/content_gap_report.py"""
import glob, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = "ops/content-gap.json"


def existing_pages():
    from promo_kit import TARGETS
    return {k: {"kind": v[0], "slug": v[1], "about": v[3]} for k, v in TARGETS.items()}


def weak_questions():
    try:
        runs = json.load(open("ops/ai-answer-log.json", encoding="utf-8"))["runs"]
        return [r["q"] for r in runs[-1]["results"] if r.get("named") is False]
    except Exception:
        return []


def build_prompt(title, text, pages, weak):
    plist = "\n".join(f"- {k}: {v['about']}" for k, v in pages.items())
    return f"""You advise an independent AI consultant (Robert Simon, Montreal) who sells to small Canadian businesses (5 to 20 people).
Suggest ONE new guide for his Business website that a real owner would search for, and that his existing pages do not already answer.

Newest briefing issue: {title}
{text[:3500]}

Existing pages (id: what it covers):
{plist}

Questions where AI assistants did NOT name his site (may be empty):
{chr(10).join('- ' + q for q in weak) or '- (none)'}

Rules: only things a low-cost AI plan can do; platform-neutral; no statistics, clients, results, prices or savings figures; no invented facts.
Reply with ONLY a JSON object, no markdown:
{{"title": "...", "question": "the exact question an owner would type", "why": "one sentence: the gap it fills",
 "outline": ["3 to 5 short section headings"], "link_to": "one existing page id from the list", "faq": ["2 short questions"]}}"""


def parse(raw, pages):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    d = json.loads(m.group(0))
    for k in ("title", "question", "why", "outline", "link_to", "faq"):
        if not d.get(k):
            raise ValueError(f"missing {k}")
    if d["link_to"] not in pages:
        raise ValueError(f"link_to must be one of {sorted(pages)}")
    if not isinstance(d["outline"], list) or not 3 <= len(d["outline"]) <= 5:
        raise ValueError("outline must have 3 to 5 headings")
    if re.search(r"\d+\s*%|\$\s*\d", json.dumps(d)):
        raise ValueError("no figures or prices allowed")
    return d


def generate(call):
    posts = sorted(p for p in glob.glob("blog/posts/*.html") if not p.endswith("latest.html"))
    if not posts:
        raise RuntimeError("no published issue found")
    from linkedin_post import issue_text
    title, text = issue_text(posts[-1])
    pages, weak = existing_pages(), weak_questions()
    prompt, err = build_prompt(title, text, pages, weak), None
    for _ in range(3):
        raw = call(prompt)
        try:
            d = parse(raw, pages)
            d.update(issue=os.path.basename(posts[-1]), date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), weak_questions=weak)
            return d
        except ValueError as e:
            err = e
            prompt += f"\n\nYour last reply was rejected: {e}. Reply with only the JSON object, following the rules."
    raise err


def main():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("GEMINI_API_KEY is not set")
        return 1
    from gemini import _call_gemini
    d = generate(lambda p: _call_gemini(key, p, 8000, temperature=0.6, use_search=False, min_chars=100, reject_truncated=True)["content"])
    log = {"suggestions": []}
    if os.path.exists(OUT):
        try:
            log = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            pass
    log["suggestions"] = (log.get("suggestions", []) + [d])[-6:]
    os.makedirs("ops", exist_ok=True)
    json.dump(log, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(OUT, "a").write("\n")
    print("Suggested guide:", d["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
