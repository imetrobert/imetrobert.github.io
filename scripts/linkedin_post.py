#!/usr/bin/env python3
"""
linkedin_post.py
Drafts the LinkedIn promotion for the issue that was just published, so it is waiting on the
"nothing pending" page the moment the issue goes live, and redrafts it from Robert's comments.

    python3 scripts/linkedin_post.py <post filename>                 # first draft (approve-blog.yml)
    python3 scripts/linkedin_post.py <post filename> "<comments>"    # redraft (linkedin-post.yml)

Writes blog/staging/linkedin.json and rewrites blog/staging/preview.html so the page shows it.
Never fails the publish: approve-blog.yml runs this step with continue-on-error.

The draft is built ONLY from the issue's own text (no search, no outside facts), so it cannot
introduce a claim the issue did not make. LinkedIn does not render markdown, so the output is plain
text with real line breaks. The link goes in a separate "first comment" block because LinkedIn
tends to show posts with an outbound link to fewer people.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

POSTS = "blog/posts"
OUT = "blog/staging/linkedin.json"
BASE = "https://www.imetrobert.com/blog/posts/"
MAX_ISSUE_CHARS = 7000


def permalink(filename):
    return f"{BASE}{filename}?utm_source=linkedin&utm_medium=social"


def issue_text(path):
    from bs4 import BeautifulSoup
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    art = soup.find("div", class_="article-content") or soup
    for cls in ("share-row", "survey-cta", "faq-section", "feasibility-cta"):
        for el in art.find_all(class_=cls):
            el.decompose()
    for el in art.find_all(["script", "style"]):
        el.decompose()
    text = re.sub(r"\n\s*\n+", "\n\n", art.get_text("\n", strip=True))
    return title, text[:MAX_ISSUE_CHARS]


def build_prompt(title, text, link, previous="", feedback=""):
    revise = ""
    if previous and feedback:
        revise = f"""
YOUR PREVIOUS DRAFT:
{previous}

ROBERT'S COMMENTS ON IT (apply them; they override the style defaults below where they conflict):
{feedback}
"""
    return f"""You write LinkedIn posts for Robert Simon, an independent AI consultant in Montreal (AI with Robert for Business). His newsletter, Practical AI for Canadian Business, explains what the low-cost AI plans (ChatGPT, Claude, Gemini, Microsoft 365 Copilot) can now do for small businesses. His LinkedIn voice is direct, practical, warm and a little opinionated. It shares expert knowledge. It never sells and never mentions his services, prices or consulting.

WHO READS IT (write for this person, and nobody else):
An owner or manager of a small business or professional practice in Montreal or elsewhere in Canada: about 5 to 20 people, in a trade, retail, professional services (accounting, law, real estate, consulting), or health and wellness. They are busy and not technical. They pay for, or are thinking about paying for, a ChatGPT, Claude, Gemini or Copilot plan, and suspect they are getting a fraction of its value. What they care about: hours saved on quotes and proposals, customer emails and follow-ups, paperwork and documents, recurring reports and scheduling; keeping costs predictable; not making a privacy mistake with client information (Quebec's Law 25 worries them). What they do not care about: model names and benchmarks, research, enterprise programs, politics, investment news.
Speak their language: "your team", "your customers", "your quotes", "an hour a week", "the plan you already pay for". Avoid jargon (LLM, RAG, agentic, tokens, sovereign AI, governance, stack, leverage). If the issue's topic is about big companies, governments or infrastructure, find the one honest takeaway that matters to an owner of a small business and lead with that. Never stretch a claim to make it relevant, and never invent one.

THE ISSUE (your ONLY source of facts; never add a company, number, date or claim that is not in it):
Title: {title}
{text}
{revise}
POST RULES
- 900 to 1,400 characters. Plain text only: no markdown, no asterisks, no bullet symbols other than a hyphen.
- Line 1 is a hook of at most 150 characters that makes a small-business owner stop scrolling: a concrete tension, surprising fact from the issue, or a sharp question. No "Excited to share" or "I'm thrilled".
- Then short paragraphs of one or two sentences with a blank line between them. Give 2 or 3 genuinely useful takeaways from the issue, stated plainly. Tease; do not retell the whole issue.
- Speak to small-business owners. First person ("I") is fine for opinion; never invent a personal story, client, meeting or result.
- End with one specific question that invites owners to answer from their own week (for example, which repetitive task eats most of their time).
- Then a blank line and 3 to 5 relevant hashtags on one line, chosen for this audience (for example #SmallBusiness, #AI, #Montreal, #ChatGPT, #Productivity). No emoji.
- Do NOT put a link in the post. Do not say "link in comments".

FIRST COMMENT RULES
- Two short sentences at most, inviting people to read the full issue, ending with this exact link on its own line: {link}

OUTPUT FORMAT, exactly, with these two labels and nothing before or after:
POST:
<the post>
FIRST COMMENT:
<the comment>"""


def fix_hashtags(post):
    """The model call strips a leading '#' from a line (markdown-header cleanup), which eats the first
    hashtag of the hashtag line. Put it back."""
    lines = post.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if not lines[i].strip():
            continue
        toks = lines[i].split()
        if len(toks) >= 2 and all(t.startswith("#") for t in toks[1:]) and not toks[0].startswith("#"):
            lines[i] = " ".join(["#" + toks[0]] + toks[1:])
        break
    return "\n".join(lines)


def parse(raw, link):
    raw = (raw or "").replace("\r", "").strip()
    m = re.search(r"POST:\s*(.*?)\s*FIRST COMMENT:\s*(.*)\Z", raw, re.S | re.I)
    if not m:
        raise ValueError("model reply did not follow the POST / FIRST COMMENT format")
    post, comment = m.group(1).strip(), m.group(2).strip()
    post = re.sub(r"\*\*|__", "", post)
    post = fix_hashtags(post)
    if len(post) < 800:
        raise ValueError(f"post is too short ({len(post)} characters; the target is 900 to 1,400)")
    if len(post) > 2200:
        raise ValueError(f"post is too long ({len(post)} characters)")
    if "http" in post.lower():
        raise ValueError("post contains a link; the link belongs in the first comment")
    if link not in comment:
        comment = (comment + "\n" + link).strip()
    return post, comment


def generate(filename, feedback="", call=None):
    path = os.path.join(POSTS, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    title, text = issue_text(path)
    link = permalink(filename)
    previous = ""
    history = []
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            if old.get("post_file") == filename:
                previous, history = old.get("post", ""), old.get("history", [])
        except Exception:
            pass
    if feedback and not previous:
        feedback = ""        # nothing to revise
    prompt = build_prompt(title, text, link, previous, feedback)
    if call is None:
        from gemini import _call_gemini
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        call = lambda p: _call_gemini(key, p, 1800, temperature=0.8, use_search=False, min_chars=300)["content"]
    raw, post, comment = None, None, None
    last_err = None
    for _ in range(2):                           # one retry on a bad format
        raw = call(prompt)
        try:
            post, comment = parse(raw, link)
            break
        except ValueError as e:
            last_err = e
            prompt += f"\n\nYour last reply was rejected: {e}. Follow the rules and format exactly."
    if post is None:
        raise last_err
    if feedback:
        history = history + [feedback]
    data = {
        "post_file": filename,
        "title": title,
        "post": post,
        "first_comment": comment,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "history": history[-10:],
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
    feedback = argv[1].strip() if len(argv) > 1 else ""
    kind = "linkedin"
    try:
        import runlog
    except Exception:
        runlog = None
    try:
        generate(filename, feedback)
        from write_nothing_pending_placeholder import write_page
        write_page()
        if runlog:
            runlog.ok(kind, f"LinkedIn draft ready for {filename}" + (" (from comments)" if feedback else ""))
        print("LinkedIn draft written.")
        return 0
    except Exception as e:
        print(f"LinkedIn draft failed: {e}")
        if runlog:
            try:
                runlog.fail(kind, runlog.classify(e), detail=str(e))
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
