"""
gemini.py
Gemini API integration and prompt construction for the monthly blog generator.
"""

import time
import requests
from datetime import datetime, timedelta
from utils import clean_ai_content, STOCK_VOICE_PHRASES


def generate_blog_with_gemini(api_key, topic=None, coverage_date=None):
    # coverage_date lets a regeneration stay locked to the ORIGINAL month
    # being reported on (e.g. regenerating a June 30 post on July 2nd should
    # still search for June news, not July's). Defaults to today for a
    # brand-new monthly run. See utils.get_issue_labels() for the full story.
    current_date = coverage_date or datetime.now()
    month_year   = current_date.strftime("%B %Y")
    prev_month   = (current_date.replace(day=1) - timedelta(days=1)).strftime("%B %Y")
    is_backfill  = coverage_date is not None and (
        coverage_date.year, coverage_date.month
    ) != (datetime.now().year, datetime.now().month)

    if topic:
        prompt = _build_custom_prompt(topic, month_year, prev_month, is_backfill, datetime.now())
    else:
        prompt = _build_monthly_prompt(month_year, prev_month, is_backfill, datetime.now())

    # The issue carries four analysis sections the old 4000-token cap never had
    # to fit (the Desk essay alone is ~450 words). At 4000 the response
    # truncated mid-section, and a truncated tail is silent: the parser just
    # renders fewer sections. Headroom is cheap; a missing "Looking Ahead" is not.
    return _call_gemini(api_key, prompt, max_output_tokens=8192,
                        temperature=0.55, use_search=True, min_chars=200)


# Flash first, lite as the fallback. The issue is now half original judgment —
# strategic reads, ratings, predictions, the Desk essay — and flash-lite
# reliably produces the reported half but flattens the analysis into restated
# news. Quality of judgment is the product now, so the stronger model leads and
# lite only catches a rate-limited run.
MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _call_gemini(api_key, prompt, max_output_tokens, temperature=0.55,
                 use_search=True, min_chars=200):
    """Post a prompt, walking the model fallback list. Returns {content, model}.

    Shared by the monthly generation and the single-section redraft so both get
    the same rate-limit handling, the same ungrounded retry on 400/404, and the
    same content cleanup.
    """
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_output_tokens,
            "temperature": temperature,
            "candidateCount": 1
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
        ]
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]

    models_to_try = MODELS_TO_TRY

    for attempt, model in enumerate(models_to_try):
        if attempt > 0:
            print(f"  Waiting 30 s before trying {model}...")
            time.sleep(30)

        print(f"Trying model: {model} (attempt {attempt+1}/{len(models_to_try)})")
        url = f"{_BASE}/{model}:generateContent?key={api_key}"

        try:
            response = requests.post(url, json=payload, timeout=180)
            print(f"  HTTP status: {response.status_code}")

            if response.status_code == 429:
                print("  Rate limited. Trying next model after wait.")
                continue
            if response.status_code == 403:
                raise Exception("API key rejected (403). Check your GEMINI_API_KEY secret.")
            if response.status_code in (404, 400):
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
                continue

            candidate     = candidates[0]
            finish_reason = candidate.get('finishReason', '')
            print(f"  Finish reason: {finish_reason}")
            if finish_reason in ('SAFETY', 'RECITATION'):
                continue

            parts    = candidate.get('content', {}).get('parts', [])
            raw_text = ' '.join(p.get('text', '') for p in parts if p.get('text')).strip()

            if len(raw_text) < min_chars:
                print(f"  Only {len(raw_text)} chars, below the {min_chars} minimum.")
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

    raise Exception("All Gemini models failed.")


# Sections the preview page can send back to the model on their own. All five
# are Robert's judgment rather than reported fact, which is exactly why they are
# the ones worth iterating on — and why redrafting one cannot invent news, since
# the call runs without search grounding and works only from the issue as
# already written.
REDRAFTABLE_SECTIONS = {
    "FROM ROBERTS DESK": {
        "label": "From Robert's Desk",
        "spec":  lambda: _SPEC_ROBERTS_DESK,
    },
    "EXECUTIVE SUMMARY": {
        "label": "Executive Summary",
        "spec":  lambda: _SPEC_EXECUTIVE_SUMMARY,
    },
    "AI MYTH OF THE MONTH": {
        "label": "AI Myth of the Month",
        "spec":  lambda: _SPEC_MYTH,
    },
    "LOOKING AHEAD: THREE PREDICTIONS": {
        "label": "Looking Ahead",
        "spec":  lambda: _SPEC_PREDICTIONS,
    },
    "ONE QUESTION FOR YOUR LEADERSHIP TEAM": {
        "label": "One Question",
        "spec":  lambda: _SPEC_QUESTION,
    },
}


def generate_section_redraft(api_key, section, issue_text, guidance="", month_year=None):
    """Rewrite ONE section, returning just that section's plain text.

    Deliberately ungrounded: no google_search tool. The section is written from
    the issue as it already stands, so a redraft can sharpen the argument but
    cannot introduce a new event, statistic or company that never went through
    the sourcing rules the reported sections are held to.

    Returns the section body WITHOUT its header line — the same shape
    parse_sections() would have handed the renderer.
    """
    if section not in REDRAFTABLE_SECTIONS:
        raise ValueError(f"'{section}' is not a redraftable section.")

    spec = REDRAFTABLE_SECTIONS[section]["spec"]()
    month_line = f"This is the {month_year} issue.\n" if month_year else ""
    guidance_block = ""
    if guidance and guidance.strip():
        guidance_block = (
            "\nROBERT'S DIRECTION FOR THIS REDRAFT — this is the reason you are\n"
            "being asked to rewrite the section, and it takes precedence over your\n"
            "own choice of angle. It does NOT relax any rule in the specification\n"
            "above: length, format, and the constraint against invented specifics\n"
            "all still apply.\n\n"
            f"{guidance.strip()}\n"
        )

    prompt = f"""You are rewriting ONE section of Robert Simon's monthly newsletter, Practical AI for Canadian Business. Robert is an independent AI thought leader in Montreal. His voice is direct, opinionated and grounded in business outcomes. He does not hedge.

{month_line}
{_EDITORIAL_PREAMBLE}

THE ISSUE AS IT CURRENTLY STANDS — this is your source material. Do not introduce
any event, company, statistic or date that does not already appear here. You are
sharpening judgment, not reporting news.

<issue>
{issue_text.strip()}
</issue>

YOUR TASK
Rewrite the section specified below. It must be materially different from the
version currently in the issue — a new angle or a sharper argument, not a
paraphrase. Everything else in the issue stays as it is.
{guidance_block}
SPECIFICATION FOR THE SECTION YOU ARE WRITING:

{spec}

OUTPUT RULES
Return ONLY the body of the section. Do NOT repeat the section header. Do not
add a preamble, a sign-off, markdown, or any commentary about what you changed.
Plain text only — no *, no **, no #.
"""

    result = _call_gemini(
        api_key, prompt,
        max_output_tokens=2048,
        temperature=0.8,          # higher than the monthly run: the point of a
                                  # redraft is to land somewhere different
        use_search=False,
        min_chars=40,
    )
    return _strip_section_header(result["content"], section), result["model"]


def _strip_section_header(text, section):
    """Drop a repeated header line. The spec says not to emit one, but models
    echo the header they were just shown often enough that leaving it in would
    put 'FROM ROBERTS DESK' in the body of the published page."""
    lines = text.strip().split("\n")
    if not lines:
        return ""
    first = lines[0].strip().rstrip(':').upper()
    candidates = {section.upper(), REDRAFTABLE_SECTIONS[section]["label"].upper()}
    candidates |= {c.replace("'", "").replace("’", "") for c in candidates}
    if first.replace("'", "").replace("’", "") in candidates:
        lines = lines[1:]
    return "\n".join(lines).strip()


def _build_monthly_prompt(month_year, prev_month, is_backfill=False, today=None):
    rules = _shared_rules_block(month_year, prev_month, is_backfill, today)
    return f"""You are writing Practical AI for Canadian Business, the monthly executive AI briefing by Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert spent 25+ years in digital transformation. His voice is direct, opinionated, and grounded in real business outcomes. He does not hedge. He calls things what they are.

AUDIENCE
Canadian business leaders — C-suite, VPs, and directors at mid-to-large Canadian enterprises across financial services, retail, manufacturing, telecom, and healthcare. These are busy, experienced executives. They have seen every tech hype cycle. Give them signal, cut the noise, and respect their time.

{rules}"""


def _build_custom_prompt(topic, month_year, prev_month, is_backfill=False, today=None):
    rules = _shared_rules_block(month_year, prev_month, is_backfill, today)
    return f"""You are writing Practical AI for Canadian Business, the monthly executive AI briefing by Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert spent 25+ years in digital transformation. His voice is direct, opinionated, and grounded in real business outcomes. He does not hedge. He calls things what they are.

AUDIENCE
Canadian business leaders — C-suite, VPs, and directors at mid-to-large Canadian enterprises across financial services, retail, manufacturing, telecom, and healthcare. These are busy, experienced executives. They have seen every tech hype cycle. Give them signal, cut the noise, and respect their time.

CONTENT FOCUS DIRECTIVE:
{topic}

This directive changes WHAT events and examples you select and emphasise. It does NOT change the structure, section counts, formatting rules, or citation requirements. All structural rules below are mandatory and unchanged.

{rules}"""



# ---------------------------------------------------------------------------
# Section specs, defined once and shared by two callers: the monthly prompt
# below, and generate_section_redraft() which sends a single spec back to the
# model to rewrite one section in place. Inlining these in the monthly prompt
# and paraphrasing them in the redraft prompt would let the two drift, and the
# drift would be invisible — a redrafted section that quietly follows different
# rules than the issue around it.
# ---------------------------------------------------------------------------
_BANNED_OPENERS = "\n".join(f'  - "{_p}"' for _p in STOCK_VOICE_PHRASES)

# f-string so the banned list stays tied to utils.STOCK_VOICE_PHRASES, which
# renderer.py also checks the finished Desk against. Two copies would drift.
_EDITORIAL_PREAMBLE = f"""EDITORIAL MISSION — read this before any other instruction:

This is not an AI news site. There are hundreds of those and none of them are the
reason anyone subscribes to this one. A reader subscribes for Robert's reading of
what AI developments actually mean for a Canadian organization.

Roughly HALF this issue is reported fact. The other half is original strategic
judgment: what matters, what does not, what to ignore, what to prioritise. The
reader must finish every issue understanding not only what happened, but what to
do next.

Test every sentence in an analysis section against this: could it appear verbatim
in a Reuters summary of the same event? If yes, it is reporting, and it does not
count toward the analysis half. Restating the news in a more emphatic tone is the
single most common way this publication fails.

VOICE AND EXPERIENCE:
Robert writes from experience leading enterprise AI transformation inside a large
Canadian organization. The first-person sections should sound like someone who has
run large change programmes and watched them stall — specific about mechanism,
unsentimental about process, willing to name the part nobody wants to discuss.

BANNED OPENERS — do not use any of these, in any section:
{_BANNED_OPENERS}

Earlier versions of this prompt offered those as suggested openings, and three
issues in a row opened a paragraph with one of them. They now read as house
filler rather than as anyone's voice. Write your own opening, in your own
construction, built from THIS month's material. Vary how you open each
paragraph — a reader who sees the same four constructions every month stops
believing there is a person behind them.

HARD CONSTRAINT ON THIS — it is not negotiable: never invent a specific anecdote,
meeting, client, colleague, project, internal metric, or dated event. Never name
or imply any current or former employer. Every experience-based observation must
be a pattern that is broadly true of large enterprises generally, not a story.

ILLUSTRATION ONLY — these show the SHAPE of an allowed observation. They are
about ERP and warehouse automation precisely so they cannot be reused in an AI
newsletter. Never copy a sentence, clause or example out of these instructions
into your output; a real issue lifted one of these examples verbatim and
published it under Robert's byline as his own hard-won experience.

Allowed shape: "Every ERP replacement I have seen stalls at the same place —
not the software, but the three business units that cannot agree whose
definition of a customer wins."
Forbidden outright: "Last quarter my team discovered...", "A bank I worked
with...", "When we rolled this out at...".

Write your own observation about THIS month's material, in your own words.

BE OPINIONATED — strategically, never politically:
Readers already have the news. What they cannot get elsewhere is judgment. Use
"I believe", "My assessment is", "I expect", "The bigger implication is", "The
risk executives are overlooking is", "The organizations that win will".
Every opinion must be followed by its reasoning in the same breath. An assertion
with no argument behind it is worse than no assertion. Be willing to say the
uncomfortable thing if it is what the evidence supports."""

_SPEC_EXECUTIVE_SUMMARY = """EXECUTIVE SUMMARY (exactly 3 numbered items, one sentence each, max 25 words each):
The three things a busy executive must take away if they read nothing else. Each
one states a CONCLUSION, not a topic. "Ottawa's compute fund makes on-shore
inference cheaper than US hosting for the first time" is a conclusion. "Government
AI funding" is a topic and is useless here.
At least one of the three must be a judgment call rather than a reported fact.
Format: 1. [sentence]"""

_SPEC_ROBERTS_DESK = """FROM ROBERTS DESK (300-450 words — this is the most important section in the issue):
This is the signature section. It is the reason someone subscribes rather than
reading a news aggregator, and it is the section a reader should look for first.
Treat every other section as supporting material for this one.

It is NOT a summary of the news above. If a reader could get the substance of this
section by re-reading the developments, it has failed.

Write 3 or 4 paragraphs of continuous prose, separated by a blank line. No bullet
points, no sub-headings, no source lines, no numbered lists. First person
throughout.

Answer three or four of these — not all of them, and not in a mechanical order:
- What genuinely surprised me this month, and why I did not expect it?
- What do executives consistently misunderstand about this?
- What trend worries me, and what specifically is the failure mode?
- What is overhyped right now, and what is the tell?
- What should Canadian businesses begin doing now?
- What can safely wait, and why is waiting the right call?
- What will actually matter six months from now that almost nobody is discussing?

You may use at most TWO specific items from the sections above, and only as a
springboard into an argument that goes somewhere they do not. The value here is
the pattern behind the news, not the news.

At least one paragraph must draw on the experience of running AI transformation
inside a large enterprise — governance, change management, executive sponsorship,
procurement friction, the gap between a working pilot and a deployed system.
Obey the HARD CONSTRAINT above: patterns that are broadly true, never invented
specifics, never a named or implied employer.

Say at least one thing a cautious writer would leave out. Support it with reasoning
in the same paragraph.

Do not open with "This month". Do not open with a summary sentence. Open on the
observation itself."""

_SPEC_MYTH = """AI MYTH OF THE MONTH:
One belief that is genuinely widespread among senior executives and is wrong or
badly incomplete. Not a strawman, and not a myth about the technology's
capabilities — a myth about how AI actually succeeds or fails inside an
organization. Governance, sponsorship, change management, procurement, process
redesign, talent, and measurement are the fertile ground here.

Use this EXACT format, both labels on their own lines:
Myth: [one sentence stating the belief plainly, as a believer would state it].
Reality: [3-4 sentences. Explain what is actually true and why the myth is so persistent. Give the reader something they can act on, not just a correction.]"""

_SPEC_PREDICTIONS = """LOOKING AHEAD: THREE PREDICTIONS
Three predictions at three horizons. These are explicitly predictions, not
reporting, and must read that way — "I expect", "I think it is likely that", "My
assessment is". Never state a prediction as a fact.

Be conservative. A prediction that is obviously safe is useless, but a dramatic
one that fails destroys the credibility of everything else in the issue. Aim for
claims that are specific enough to be wrong, and that you would still defend if
challenged. Each is 1-2 sentences.

Use this EXACT format, each on its own line:
One month: [prediction]
Six months: [prediction]
One year: [prediction]"""

_SPEC_QUESTION = """ONE QUESTION FOR YOUR LEADERSHIP TEAM:
A single question a CEO or CIO could put on next month's leadership agenda. Write
the question and nothing else — no preamble, no answer, no explanation.

It must be answerable in a real meeting and uncomfortable enough to be worth
asking. It should expose a gap rather than invite a status update.
Good: "If our AI budget doubled tomorrow, which initiative would produce a
measurable business result within six months — and can we name the metric today?"
Weak: "How can we better take advantage of AI?"

Write one or two sentences maximum, ending in a question mark."""

def _shared_rules_block(month_year, prev_month, is_backfill=False, today=None):
    today_str = (today or datetime.now()).strftime('%B %d, %Y')
    return f"""{_EDITORIAL_PREAMBLE}

WRITING RULES — follow these exactly:
0. NEVER reuse wording from these instructions. Every example below shows the
   required FORM. The content is disposable and must not appear in your output.
   If a sentence you are about to write also appears in this prompt, rewrite it.
1. Write as an active peer and practitioner — someone in the room, not observing from the outside. Use "What we're seeing on the ground" over "studies suggest." Be casually authoritative. Enthusiasm for technology is fine; uncritical hype is not.
2. Maximum 22 words per sentence. Short sentences hit harder. Mix punchy 4-word sentences with longer conversational ones. Vary the rhythm deliberately.
3. Start every section with a direct hook or a counter-intuitive observation. No warmup phrases, no formal introductions.
4. Never use these words or phrases:
   - "dual-edged sword" → describe the tension directly
   - "unprecedented opportunities" → name the specific opportunity
   - "navigate" → deal with / address / respond to
   - "harness" → use / deploy / apply
   - "leverage" → use
   - "landscape" → market / industry / sector
   - "stakeholders" → customers / employees / investors / regulators
   - "game-changer" → describe why it changes things
   - "paradigm shift" → describe the actual shift
   - "move the needle" → describe the specific outcome
   - "in today's fast-paced world" → delete entirely
   - "Welcome to the [month] edition" → do not use
   - "This month, the pace of AI innovation continues to accelerate" → do not use
   - "delve" → cut entirely
   - "testament" → cut entirely
   - "synergy" → cut entirely
   - "tapestry" → cut entirely
   - "Furthermore" → cut entirely
   - "Moreover" → cut entirely
   - "It is important to remember" → cut entirely
   - "In conclusion" → cut entirely
   - "Looking ahead" → cut entirely; it is a section header below and using it
     in prose breaks the parser that splits this document into sections
   - "Executive summary" → same reason; never use the phrase inside prose
5. Ground everything in Canadian business reality: US-Canada trade tensions under the Carney government, Bill C-27 (AIDA) working through Parliament, Quebec Law 25 privacy requirements, PIPEDA, the Canadian dollar, AI talent competition between Toronto/Montreal/Vancouver.
6. Name real Canadian companies and institutions where relevant: Shopify, Cohere, D-Wave, Ada, Coveo, RBC, TD, Scotiabank, CIBC, Manulife, Sun Life, Bell, Rogers, Telus, BCE, Loblaw, Couche-Tard, CAE, BRP, Bombardier, Mila, Vector Institute, Amii, Ivey Business School, Rotman School of Management.

Use Google Search grounding to find REAL AI news events from {month_year} ONLY. Do NOT use events from {prev_month} or any prior month. Do not invent events, dates, companies, or statistics.

CRITICAL FUTURE-DATE RULE: Today is {today_str}. Never report an event dated
after today. If {month_year} is still in progress, cover ONLY what has already
happened — report fewer developments rather than reaching forward to fill the
count. A forward-dated item is not a forecast, it is a fabrication: it states as
reported fact something that has not occurred, with a source line implying
somebody published it. Predictions belong in LOOKING AHEAD, labelled as
predictions, and nowhere else. Any item dated after today is discarded before
publication, so writing one costs you the slot and gains nothing.
{"" if not is_backfill else f'''
BACKFILL NOTICE: This is a re-run of the {month_year} report, being regenerated after {month_year} has already ended. Today's real date is later than {month_year} — ignore that. Your search results will surface newer news by default; you must actively filter it out. Every single item, statistic, and example must be dated within {month_year}. If you cannot find 8 qualifying developments strictly from {month_year}, use fewer rather than reaching into a later month.
'''}

SOURCE QUALITY RULE: Only cite primary sources — official company blogs, government press releases, major news outlets (Globe and Mail, Financial Post, CBC, Reuters, Bloomberg, TechCrunch, The Verge, Wired). Do NOT cite newsletters, podcast episodes, Substack posts, Medium posts, personal or community blogs, or aggregator summaries. If a result looks like "26: GPT-5.5, Claude Mythos & What It Means" or "Episode 14: ..." it is a newsletter/podcast — skip it and find the original primary source instead.

The distinction is WHO PUBLISHED IT, not what it says. "AWS News Blog", "Google
Blog" and "OpenAI Blog" are first-party newsrooms and are fine. "Something
Blogs", "<Anything> - Medium", a Substack, or a personal site are not,
regardless of how accurate the post looks — a real issue cited "ML Kenya Blogs"
and "TechCraft Chronicles - Medium" for its two most specific product claims,
and neither could be verified.

Any item you can only source to one of those is DISCARDED before publication.
Report fewer developments rather than citing a blog: a thin issue costs you one
story, a bad citation costs the publication its credibility.

OUTPUT FORMAT
Write plain text only. No markdown (no *, no **, no #). Use EXACTLY these section headers, spelled exactly like this, each on its own line, in this order:

HEADLINE
INTRODUCTION
EXECUTIVE SUMMARY
KEY AI DEVELOPMENTS
CANADIAN SPOTLIGHT
FROM ROBERTS DESK
WHAT THIS MEANS FOR CANADIAN BUSINESS
STRATEGIC ACTIONS FOR THIS MONTH
ADOPTION SNAPSHOT
AI MYTH OF THE MONTH
LOOKING AHEAD: THREE PREDICTIONS
ONE QUESTION FOR YOUR LEADERSHIP TEAM

Write FROM ROBERTS DESK without an apostrophe, exactly as shown.

LENGTH BUDGET — the issue is a focused executive briefing, not a digest. These
readers have limited time and the publication's promise is a short read. Depth in
the analysis sections is paid for by discipline in the reported ones. Stay inside
this budget; it totals roughly 1,300 words:

  INTRODUCTION                            55 words
  EXECUTIVE SUMMARY                       55 words   (3 items, max 25 each)
  KEY AI DEVELOPMENTS                    340 words   (3 major at ~80, then 2-3 log entries at ~35)
  CANADIAN SPOTLIGHT                     115 words   (3 items)
  FROM ROBERTS DESK                  300-450 words
  WHAT THIS MEANS FOR CANADIAN BUSINESS  135 words   (3 paragraphs)
  STRATEGIC ACTIONS FOR THIS MONTH       250 words   (5 actions, ~50 each including the owner line)
  ADOPTION SNAPSHOT                       70 words
  AI MYTH OF THE MONTH                    80 words
  LOOKING AHEAD: THREE PREDICTIONS        85 words
  ONE QUESTION FOR YOUR LEADERSHIP TEAM   30 words

Never exceed the item counts specified below; they are maximums as well as
minimums. If a section is running long, cut reported detail before cutting
judgment — the analysis is what the reader came for.

---

HEADLINE (one line, 50-85 characters):
Name the single biggest story of {month_year} for a Canadian business audience, as a specific claim. This becomes the page title, so it is what a search engine or an AI assistant matches a question against.
State the actual entity and the actual number or policy. "Ottawa commits $2.3B to AI for All: what mid-market firms must do" works. "AI Insights for {month_year}", "Key AI developments", "The month in AI" and any other generic phrasing are useless here and must never be used — a title with no topic in it cannot be retrieved for a topic.
No colon-free clickbait, no questions, no "you won't believe". Plain declarative. Do not include the month name — it is added automatically.
Write the headline on ONE line directly under the HEADLINE header, with no quotes around it.

INTRODUCTION (3 sentences maximum):
CRITICAL: The first sentence MUST contain the specific claim you made in the
HEADLINE — the same entity and the same number, policy or figure, stated as a
fact. The headline is a promise; the sentence under it has to pay that promise
immediately. An issue titled "Ottawa's new AI strategy commits $700M for SME
compute access" whose opening paragraph says only "a five-year plan for domestic
AI leadership" reads as though the title belongs to a different article, and the
reader has to hunt for the number that drew them in.

Second sentence: what it means for Canadian business. Third sentence: what this analysis helps the reader do. Do NOT start with "Welcome", "This month", or any warmup phrase. Make the reader want to keep going.

{_SPEC_EXECUTIVE_SUMMARY}

KEY AI DEVELOPMENTS (exactly 5 or 6 items — not more, not fewer):
This section used to run to ten items. It no longer does, because coverage volume
is not the value of this publication. Select ruthlessly: an item earns its place
only if a Canadian executive would make a different decision knowing it.
CRITICAL DATE RULE: Include ONLY events from {month_year}. Never fabricate. Never use events from prior months, and never use a date after {today_str} (see the future-date rule above).
CRITICAL SECTION ROUTING RULE: KEY AI DEVELOPMENTS is strictly for AI company announcements — products, models, partnerships, research. It must NEVER contain items from any government entity. This includes: the Government of Canada, any provincial or municipal government, the Prime Minister, any federal minister, any G7/G20/OECD ministerial body, Statistics Canada, Bank of Canada policy announcements, or any Crown corporation acting in a regulatory/policy capacity. Any government funding, policy, regulation, or strategy announcement MUST go in CANADIAN SPOTLIGHT — never here.
CRITICAL SOURCE RULE: Every single item MUST end with a Source line. No exceptions.
CRITICAL SOURCE QUALITY RULE: Every source MUST be a primary source — official company announcements, government press releases, or major news publications. Newsletters, podcast episodes, Substack posts, and aggregator blogs are NEVER acceptable sources. If your search returns a newsletter item (e.g. "26: GPT-5.5..." or "Episode 14:..."), discard it and find the original primary source announcement instead.
CRITICAL DEDUPLICATION RULE: Treat KEY AI DEVELOPMENTS and CANADIAN SPOTLIGHT as one combined list. Every individual news event, funding program, company announcement, or policy decision may appear ONCE across both sections combined — never twice. Same program = same event = one section only. If the AI Compute Access Fund, RAII, or any government initiative appears in KEY AI DEVELOPMENTS, it must NOT appear in CANADIAN SPOTLIGHT under any name, wording, or angle. No exceptions.

THIS SECTION HAS TWO TIERS. The FIRST THREE items are the major stories and carry
Robert's interpretation plus executive ratings. Items 4 onward are the compact log
and carry neither. Order the section so the three highest-consequence stories come
first — that ordering IS the designation.

Use this EXACT format for items 1, 2 and 3 — copy the label words precisely,
including the capitalisation and the full stops:
[Month Day]: [Company] — [One sentence: what they did]. [One sentence: why it matters for Canadian business]. STRATEGIC READ: [2-3 sentences of Robert's own interpretation]. IMPORTANCE: [High or Medium or Low]. HORIZON: [Now or 3 Months or 6 Months or 12 Months]. ATTENTION: [Yes or Monitor or Ignore]. Source: [Publication name] | [Exact article headline as published]

Example of a correct major item:
May 15: Google — Released Gemini 3.1 with enhanced reasoning for enterprise. Canadian financial services firms can deploy it inside existing Workspace contracts. STRATEGIC READ: Most firms will treat this as a procurement question and route it to IT. It is a data-residency question, and the people who should be in the room are Legal and the Chief Risk Officer. The opportunity competitors are missing is that an existing contract means you can pilot this in weeks without a new vendor review. IMPORTANCE: High. HORIZON: Now. ATTENTION: Yes. Source: The Verge | Google Releases Gemini 3.1 With Stronger Reasoning

What STRATEGIC READ must do — it answers some of these, never all:
- Why does this actually matter, beyond the announcement?
- How should an executive react, concretely?
- What mistake will most companies make in response to this?
- What opportunity are competitors likely to miss?
It must NOT restate the two sentences above it in different words. If your
strategic read could be deleted without losing any information, rewrite it.

Use this EXACT format for items 4 onward — no strategic read, no ratings:
[Month Day]: [Company] — [One sentence: what they did]. [One sentence: why it matters for Canadian business]. Source: [Publication name] | [Exact article headline as published]

Rules:
- EXACTLY 5 or 6 items total. The first 3 carry STRATEGIC READ and all three ratings; the rest carry none.
- Every item has ONE date from {month_year}. A single day, never a range: write "July 22", never "July 22-30" or "July 22 to 30". If the story unfolded over a week, date it to the day the thing you are reporting actually happened.
- Every item ends with Source: [Publication] | [Headline] — no URLs, no brackets around the headline
- The word "Source" must always be preceded by a full stop, so ratings lines end with a full stop as shown
- Every source is a PRIMARY source (company blog, government site, major news outlet) — NEVER a newsletter or podcast
- Vary the companies — mix US tech, Canadian companies, global players
- The Canadian relevance sentence must be specific, not generic
- Do not rate everything High. If all three major stories are High importance, you have not made a judgment. ATTENTION: Ignore is a legitimate and useful verdict on a story that is loud but consequence-free.
- UNIQUENESS RULE: Every item must cover a distinct news event or announcement.

CANADIAN SPOTLIGHT (MINIMUM 3 items — hard requirement):
SECTION ROUTING RULE FOR SPOTLIGHT: This section receives TWO types of content:
1. GOVERNMENT items (MANDATORY here, never in Key Developments): Any announcement, funding, policy, regulation, or strategy from the Government of Canada, any provincial/territorial/municipal government, the Prime Minister or any minister, G7/G20/OECD ministerial bodies, Statistics Canada, or any Crown corporation acting in policy capacity.
2. CANADIAN PRIVATE SECTOR items (optional, if not already in Key Developments): Canadian AI companies making news (Cohere, Ada, Coveo, D-Wave, Mila spinouts, etc.)

CRITICAL SOURCE RULE: Every single Canadian Spotlight item MUST end with a Source line using a PRIMARY source only.
CRITICAL UNIQUENESS RULE: Canadian Spotlight items MUST NOT repeat any announcement already in KEY AI DEVELOPMENTS.

Use this EXACT format for every item:
[Company/Organization]: [What happened — one sentence]. [Why it matters — one sentence]. Source: [Publication name] | [Exact article headline as published]

Rules:
- EXACTLY 3 items.
- No generic "Canada is positioning itself" filler
- Every item ends with Source: [Publication] | [Headline]
- Every source is a PRIMARY source — NEVER a newsletter or podcast

MANDATORY SELF-CHECK — DO THIS BEFORE WRITING ANY FURTHER:
List every news event you have written in KEY AI DEVELOPMENTS (by topic, one line each).
Then list every news event in CANADIAN SPOTLIGHT (by topic, one line each).
Compare the two lists. If ANY topic appears in both lists — even described with different words — you MUST go back and replace the duplicate in CANADIAN SPOTLIGHT with a genuinely different Canadian news item before continuing.
Only continue once every item across both sections is a unique, non-overlapping news event.

{_SPEC_ROBERTS_DESK}

WHAT THIS MEANS FOR CANADIAN BUSINESS (3 paragraphs, maximum 3 sentences each):
CRITICAL CROSS-REFERENCE RULE: Every paragraph MUST name at least one specific event, company, or statistic from KEY AI DEVELOPMENTS, CANADIAN SPOTLIGHT, or ADOPTION SNAPSHOT above.
Write like a practitioner who has seen this play out. Skip the academic framing. Say what is actually happening and what Canadian leaders need to do about it.

Paragraph 1 — Financial services / technology impact:
- Open by naming a specific development from KEY AI DEVELOPMENTS.
- Explain the direct operational consequence for a named Canadian bank, insurer, or tech company.
- 3-4 sentences maximum.

Paragraph 2 — Sector impact (manufacturing, healthcare, or retail):
- Open by naming a specific item from CANADIAN SPOTLIGHT or KEY AI DEVELOPMENTS that affects this sector.
- Name a real Canadian company or describe a real sector dynamic.
- 3-4 sentences maximum.

Paragraph 3 — Regulatory and competitive pressure:
- Open by naming a specific regulation or policy item already referenced above.
- State a specific compliance deadline or decision point Canadian leaders face.
- 3-4 sentences maximum.

STRATEGIC ACTIONS FOR THIS MONTH (exactly 5 items):
CRITICAL TRACEABILITY RULE: Each of the 5 actions MUST trace directly to a named item from KEY AI DEVELOPMENTS or CANADIAN SPOTLIGHT.
These are not generic best practices. Each action responds to something specific that happened this month. Make that connection explicit.

Each action carries a decision header so an executive can triage the five at a
glance. Use this EXACT format — copy the label words precisely, including the
capitalisation and the full stops:

1. [Action, 2 sentences. Starts with a strong verb, names the specific development it responds to, and includes a specific deadline.] OWNER: [Role] — [one sentence: why this role and not the obvious alternative]. PRIORITY: [High or Medium or Low]. EFFORT: [Small or Medium or Large]. IMPACT: [Low or Medium or High].

Example of a correct action:
1. Audit your Microsoft and Google enterprise agreements for the inference data-residency clauses both vendors revised this month. You need the answer before any business unit expands a pilot past proof of concept, so set a 30-day deadline. OWNER: General Counsel — the instinct is to hand this to the CIO, but the exposure is contractual rather than technical, and Legal is the only function that can actually reopen the terms. PRIORITY: High. EFFORT: Small. IMPACT: High.

Each action must:
- Start with a strong verb: Audit, Pilot, Negotiate, Commission, Assign, Test, Require, Demand, Sunset, Block time to
- Name the specific development, company, tool, regulation, or funding program it responds to
- Include a specific deadline (this week / by end of Q2 / before June 30 / within 30 days)
- Be 2 sentences before the OWNER label

OWNER rules:
- Pick from: CEO, President, CIO, CTO, CDO, CFO, CHRO, Chief Risk Officer, General Counsel, Head of Data Governance, VP Marketing, VP Operations, Board Audit Committee
- The rationale after the dash must explain why THIS role rather than the one a reader would assume. "CIO — because it is a technology decision" is worthless. The useful version names the alternative and rules it out.
- Do not assign every action to the CIO or CTO. If AI work in an organization only ever lands on technology leadership, that is itself the problem this publication exists to correct.

PRIORITY, EFFORT and IMPACT rules:
- These are independent axes. A High priority action can be Small effort; that combination is exactly what an executive is scanning for.
- At most two of the five actions may be PRIORITY: High. Five high priorities is no priority.
- Be honest about EFFORT: Large. Understating effort is how these lists lose credibility.

ADOPTION SNAPSHOT (exactly 5 data points):
CRITICAL: Each stat on its own line. Never combine into a paragraph.
CRITICAL FORMAT: The number MUST come first.

Correct format examples:
30% of Canadian businesses have adopted AI in at least one function. Source: BDC, 2025.
46% of employed Canadians say AI has impacted their career trajectory. Source: Borderless AI, 2026.
Global: 70% of organizations have an AI strategy in place. Source: McKinsey, 2025.

Format for each line:
[Number]% [rest of stat]. Source: [Organization], [year].

Use only real, verifiable Canadian stats from: Statistics Canada, BDC, ISED, CIRA, Conference Board of Canada, Deloitte Canada, KPMG Canada, PwC Canada, Mila Annual Report, Vector Institute Annual Report, McKinsey Canada.

{_SPEC_MYTH}

{_SPEC_PREDICTIONS}

{_SPEC_QUESTION}

---
Context: {month_year} edition"""
