#!/usr/bin/env python3
"""Promo kit for a published issue: everything beyond the single LinkedIn post.

Usage: python3 scripts/promo_kit.py <post_filename>      (run from the repo root)

Writes blog/staging/promo.json with
  hooks   three alternative opening lines for the main LinkedIn post
  french  a Quebec-French version of the main post (blog/staging/linkedin.json) + comment
  drip    three follow-up posts (one per use case in the issue), each linking to the matching
          service page on biz.aiwithrobert.com, with the day offset to post it on
Links are added by THIS code, never by the model (so they cannot be invented); every link carries
utm_source=linkedin and utm_campaign=issue-YYYY-MM[-dN], which the Business site saves on the lead.
The nothing-pending page (scripts/write_nothing_pending_placeholder.py) shows it. Error code: PROMO_REJECTED.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkedin_post import issue_text, fix_hashtags  # noqa: E402

POSTS = "blog/posts"
OUT = "blog/staging/promo.json"
LINKEDIN = "blog/staging/linkedin.json"
BIZ = "https://biz.aiwithrobert.com"
DRIP_DAYS = (8, 15, 22)

# The Business site's service pages and articles (source: aiwithrobert-biz scripts/pages_data.py).
# id -> (folder, English slug, French slug, what the page is about)
TARGETS = {
    "consulting": ("services", "ai-consulting-small-business-montreal", "conseil-ia-petite-entreprise-montreal",
                   "finding where AI can save a small business time with the tools it already pays for"),
    "platforms": ("services", "chatgpt-gemini-copilot-consulting", "conseil-chatgpt-gemini-copilot",
                  "choosing and setting up ChatGPT, Gemini or Copilot for a small business"),
    "automation": ("services", "workflow-automation-small-business", "automatisation-flux-de-travail-ia",
                   "automating recurring work: reports, follow-ups, documents, scheduling"),
    "agents": ("services", "ai-agents-for-small-teams", "agents-ia-petites-equipes",
               "AI assistants that do a defined job for a small team, under the owner's control"),
    "training": ("services", "practical-ai-staff-training", "formation-pratique-ia-employes",
                 "practical AI training for staff"),
    "compare": ("articles", "chatgpt-vs-gemini-vs-copilot-small-business", "chatgpt-gemini-copilot-petite-entreprise",
                "comparing ChatGPT, Gemini and Copilot for a small business"),
    "subs": ("articles", "get-more-from-your-ai-subscriptions", "tirer-plus-de-vos-abonnements-ia",
             "getting more from the AI subscriptions a business already pays for"),
    "feasibility": ("articles", "free-ai-feasibility-check-small-business", "verification-faisabilite-ia-gratuite-petite-entreprise",
                    "the free feasibility check: whether the AI plan a business already has can do a given job"),
    "briefing": ("articles", "monthly-ai-briefing-small-canadian-businesses", "breve-mensuelle-ia-petites-entreprises-canadiennes",
                 "The Briefing: a monthly issue on what low-cost AI plans can do for small Canadian businesses"),
}

OWN_DATA = re.compile(r"\b(my|our) (analytics|clients?|customers|data|research|surveys?|findings|numbers)\b|\bI(?:'ve| have) seen\b|\bwe (?:found|measured|saw)\b|\b(mes|nos) (clients?|donn[ée]es|analyses|sondages)\b|\bj'ai (?:vu|constat[ée])\b", re.I)


def campaign(filename, n=None):
    m = re.match(r"(\d{4})-(\d{2})", filename)
    base = f"issue-{m.group(1)}-{m.group(2)}" if m else "issue"
    if n == "fr":
        return f"{base}-fr"
    return f"{base}-d{n}" if n else base


def biz_link(page_id, lang, camp):
    folder, en, fr, _ = TARGETS[page_id]
    path = f"/{folder}/{en}/" if lang == "en" else f"/fr/{folder}/{fr}/"
    return f"{BIZ}{path}?utm_source=linkedin&utm_medium=social&utm_campaign={camp}"


def feas_link_fr(camp):
    return f"{BIZ}/fr/?utm_source=linkedin&utm_medium=social&utm_campaign={camp}#feas-check"


def _call_model(prompt):
    from gemini import _call_gemini
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return _call_gemini(key, prompt, 8000, temperature=0.8, use_search=False, min_chars=300, reject_truncated=True)["content"]


def _clean_post(text, lo, hi, what):
    text = fix_hashtags(re.sub(r"\*\*|__", "", text.strip()))
    if not lo <= len(text) <= hi:
        raise ValueError(f"{what} is {len(text)} characters (allowed {lo} to {hi})")
    if "http" in text.lower():
        raise ValueError(f"{what} contains a link; links are added by the program")
    if OWN_DATA.search(text):
        raise ValueError(f"{what} claims Robert's own data, clients or experience")
    return text


def _clean_comment(text, what):
    text = re.sub(r"\*\*|__", "", text.strip())
    if not 20 <= len(text) <= 400:
        raise ValueError(f"{what} comment is {len(text)} characters (allowed 20 to 400)")
    if "http" in text.lower():
        raise ValueError(f"{what} comment contains a link; links are added by the program")
    if re.search(r"\bRobert\b", text):
        raise ValueError(f"{what} comment names Robert; it must be written by him in the first person")
    return text


AUDIENCE = """WHO READS IT: an owner or manager of a small business or professional practice in Montreal or elsewhere in Canada (about 5 to 20 people). Busy, not technical, pays for or is thinking about a ChatGPT, Claude, Gemini or Copilot plan. Cares about hours saved on quotes, customer emails, paperwork, reports; predictable costs; privacy of client information (Quebec Law 25). Avoid jargon (LLM, RAG, agentic, tokens, stack, leverage). Robert's voice: direct, practical, warm, a little opinionated; shares expert knowledge, never sells, never mentions his services, prices or consulting.
FACTS: use ONLY what is in the issue below. Never invent a company, number, date or claim. Never claim data, clients, results or experience of Robert's own."""


def _extract(raw, labels):
    """Split `raw` on lines that are exactly one of the labels; returns {label: text}."""
    out, cur = {}, None
    for line in (raw or "").replace("\r", "").split("\n"):
        key = line.strip().rstrip(":").upper()
        if key in labels and line.strip().endswith(":"):
            cur = key
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def build_hooks_french_prompt(title, text, main_post):
    return f"""You help Robert Simon (AI with Robert for Business) promote his newsletter on LinkedIn.
{AUDIENCE}

ISSUE: {title}
{text}

HIS LINKEDIN POST FOR THIS ISSUE (English):
{main_post}

DO TWO THINGS.
1) Write 3 alternative opening lines for that post, each at most 150 characters, each a different angle (a concrete tension, a surprising fact from the issue, a sharp question). No emoji, no "Excited to share".
2) Write a Quebec-French version of the post: natural business French as spoken in Quebec (not a word-for-word translation; keep it 900 to 1,500 characters, same facts, same final question, hashtags in French or neutral such as #PME #IA #Montreal), plus a first comment of at most two sentences, in the first person, inviting owners to read the full issue (which is in English, say so), with NO link.

OUTPUT FORMAT, exactly these labels each on its own line ending with a colon, nothing before or after:
HOOKS:
<hook 1>
<hook 2>
<hook 3>
FRENCH POST:
<post>
FRENCH COMMENT:
<comment>"""


def parse_hooks_french(raw):
    parts = _extract(raw, {"HOOKS", "FRENCH POST", "FRENCH COMMENT"})
    if len(parts) < 3:
        raise ValueError("reply did not contain HOOKS, FRENCH POST and FRENCH COMMENT")
    hooks = [re.sub(r"^\s*(?:\d+[.)]|[-*])\s*", "", h).strip() for h in parts["HOOKS"].split("\n") if h.strip()]
    if len(hooks) != 3 or any(len(h) > 160 or len(h) < 15 for h in hooks):
        raise ValueError("expected exactly 3 hooks of 15 to 160 characters")
    if any("http" in h.lower() for h in hooks):
        raise ValueError("a hook contains a link")
    post = _clean_post(parts["FRENCH POST"], 700, 1900, "French post")
    comment = _clean_comment(parts["FRENCH COMMENT"], "French")
    return hooks, post, comment


def build_drip_prompt(title, text):
    menu = "\n".join(f"- {k}: {v[3]}" for k, v in TARGETS.items())
    return f"""You write LinkedIn posts for Robert Simon (AI with Robert for Business) to keep promoting one issue of his newsletter over the following weeks.
{AUDIENCE}

ISSUE: {title}
{text}

Write THREE separate follow-up posts. Each takes ONE practical use case, tip or change from the issue (a different one each time) and gives a small business owner something useful in 500 to 900 characters: a hook line of at most 150 characters, two or three short paragraphs, one question to the reader, then 3 to 5 hashtags on one line. Plain text, no emoji, no markdown, no link. Then choose the ONE page from this list that best matches the post's topic:
{menu}
and write a first comment of at most two sentences, in the first person, that points readers to that page for more (no link; the program adds it).

OUTPUT FORMAT, exactly, repeated for 1, 2 and 3, labels on their own line ending with a colon:
POST 1:
<post>
PAGE 1:
<one id from the list>
COMMENT 1:
<comment>
POST 2:
...
"""


def parse_drip(raw, filename):
    labels = {f"{k} {n}" for k in ("POST", "PAGE", "COMMENT") for n in (1, 2, 3)}
    parts = _extract(raw, labels)
    drip = []
    for n in (1, 2, 3):
        try:
            post, page, comment = parts[f"POST {n}"], parts[f"PAGE {n}"].strip().lower(), parts[f"COMMENT {n}"]
        except KeyError:
            raise ValueError(f"reply is missing part of post {n}")
        page = re.sub(r"[^a-z]", "", page)
        if page not in TARGETS:
            raise ValueError(f"post {n} named an unknown page '{page}'")
        post = _clean_post(post, 400, 1300, f"Post {n}")
        comment = _clean_comment(comment, f"Post {n}")
        link = biz_link(page, "en", campaign(filename, n))
        drip.append({"day": DRIP_DAYS[n - 1], "page": page, "post": post,
                     "comment": comment + "\n" + link, "link": link})
    return drip


def _attempt(prompt, parse, call):
    err = None
    for _ in range(3):
        raw = call(prompt)
        try:
            return parse(raw)
        except ValueError as e:
            err = e
            prompt += f"\n\nYour last reply was rejected: {e}. Follow the rules and format exactly."
    raise err


def generate(filename, call=None):
    call = call or _call_model
    path = os.path.join(POSTS, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if not os.path.exists(LINKEDIN):
        raise FileNotFoundError("blog/staging/linkedin.json is missing: draft the main LinkedIn post first")
    main = json.load(open(LINKEDIN, encoding="utf-8"))
    if main.get("post_file") != filename:
        raise ValueError("linkedin.json belongs to a different issue; redraft the main post first")
    title, text = issue_text(path)
    hooks, fr_post, fr_comment = _attempt(
        build_hooks_french_prompt(title, text, main["post"]), parse_hooks_french, call)
    drip = _attempt(build_drip_prompt(title, text), lambda raw: parse_drip(raw, filename), call)
    fr_camp = campaign(filename, "fr")
    fr_link = feas_link_fr(fr_camp)
    data = {
        "post_file": filename,
        "title": title,
        "published": (re.match(r"\d{4}-\d{2}-\d{2}", filename) or [""])[0],
        "hooks": hooks,
        "french": {"post": fr_post, "first_comment": fr_comment + "\n" + fr_link, "link": fr_link},
        "drip": drip,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return data


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    filename = os.path.basename(argv[0])
    try:
        import runlog
    except Exception:
        runlog = None
    try:
        generate(filename)
        from write_nothing_pending_placeholder import write_page
        write_page()
        if runlog:
            runlog.ok("promo", f"Promo kit ready for {filename}")
        print("Promo kit written.")
        return 0
    except Exception as e:
        print(f"Promo kit failed: {e}")
        if runlog:
            try:
                runlog.fail("promo", "PROMO_REJECTED" if isinstance(e, ValueError) else runlog.classify(e), detail=str(e))
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
