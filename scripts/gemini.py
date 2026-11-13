"""
gemini.py
Gemini API integration and prompt construction for the monthly blog generator.
"""

import time
import requests
from datetime import datetime, timedelta
from utils import (clean_ai_content, STOCK_VOICE_PHRASES, CANADIAN_HOUSEHOLD_BRANDS,
                   record_gemini_request, requests_today, load_model_config,
                   save_model_config, new_models_available,
                   resolve_model_order)


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
    # require_grounding: the reported half of the issue (named releases, dates,
    # figures) is only trustworthy if it came from live search results. Without
    # search the model writes from training data and presents last year's
    # releases as this month's news. That happened once and went out under the
    # issue's name, so an ungrounded answer is now a failed run, not a draft.
    result = _call_gemini(api_key, prompt, max_output_tokens=8192,
                          temperature=0.55, use_search=True, min_chars=200,
                          require_grounding=True)
    return result


# Flash first, lite as the fallback. The issue is now half original judgment —
# strategic reads, ratings, predictions, the Desk essay — and flash-lite
# reliably produces the reported half but flattens the analysis into restated
# news. Quality of judgment is the product now, so the stronger model leads and
# lite only catches a rate-limited run.
# Fallback only. The live order comes from blog/model-config.json via
# load_model_config(), so adopting a newly launched model is a preview-page
# decision rather than a code edit. See utils.MODEL_CONFIG_PATH.
MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

# Busy, not broken. These buy the same model a second attempt before the run
# settles for a weaker one — see the retry loop in _call_gemini.
_TRANSIENT_STATUSES = (429, 500, 502, 503, 504)

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _tokens_used(response):
    """Total tokens Gemini reports for a call, or 0 if it said nothing.

    usageMetadata comes back on every successful response and was previously
    discarded, so a run left no record of what it cost.
    """
    try:
        return int(response.json().get("usageMetadata", {}).get("totalTokenCount", 0))
    except Exception:
        return 0


def _call_gemini(api_key, prompt, max_output_tokens, temperature=0.55,
                 use_search=True, min_chars=200, reject_truncated=False,
                 require_grounding=False, models=None):
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

    # Which models, in what order. `models` is an explicit list (used by
    # model_scout.py to test ONE model). Otherwise the order comes from
    # utils.resolve_model_order(): only PROVEN models can appear (the built-in
    # baseline plus whatever the scout has qualified: callable on the free tier,
    # search-grounded, able to write a whole issue). On 2026-11-01 an unproven
    # model led, failed, and the issue was written without live search; a model
    # that is merely listed by the API can no longer lead. The baseline always
    # stays at the tail as the safety net.
    if models:
        models_to_try = list(models)
    else:
        models_to_try = resolve_model_order()
        if models_to_try[0] != MODELS_TO_TRY[0]:
            print(f"  MODEL ORDER: leading with {models_to_try[0]} (best proven "
                  f"model, or the one pinned on the preview page).")

    for attempt, model in enumerate(models_to_try):
        if attempt > 0:
            print(f"  Waiting 30 s before trying {model}...")
            time.sleep(30)

        print(f"Trying model: {model} (attempt {attempt+1}/{len(models_to_try)})")
        url = f"{_BASE}/{model}:generateContent?key={api_key}"

        try:
            # A 503 says the model is busy, not broken — Google's own message
            # calls the spike temporary. Dropping straight to the next model
            # trades the analysis for availability: the fallbacks reliably
            # produce the reported half of the issue and flatten the judgment
            # half, which is now the product. A run went out exactly that way,
            # so a transient failure buys this model a second attempt first.
            response = None
            for transient_attempt in range(2):
                if transient_attempt:
                    print(f"  {response.status_code} is transient — retrying "
                          f"{model} in 45 s before falling back.")
                    time.sleep(45)
                response = requests.post(url, json=payload, timeout=180)
                # Counted here, not per run: this loop, the model fallback and
                # the ungrounded retry below each fire their own request, and
                # the daily quota counts requests.
                record_gemini_request(model, _tokens_used(response))
                print(f"  HTTP status: {response.status_code}")
                if response.status_code not in _TRANSIENT_STATUSES:
                    break

            if response.status_code == 429:
                # A 429 on the CONFIGURED LEADER, on a day with barely any
                # requests, is almost never rate limiting. It usually means the
                # model has no free-tier quota on this Cloud project at all —
                # ListModels reports what the key can SEE, not what it may call,
                # so a model can be adopted from the approval page and then 429
                # on every single request. Left unsaid, the pipeline silently
                # spends two requests and ~75s of waiting on it every run.
                if attempt == 0:
                    _reqs, _ = requests_today()
                    _lim = load_model_config().get("limits", {}).get(model)
                    _ctx = (f"{_reqs} request(s) recorded today against a limit of "
                            f"{_lim}" if _lim else f"{_reqs} request(s) recorded today")
                    print(f"  LEADER UNUSABLE: {model} returned 429 on both attempts "
                          f"with {_ctx}. That is very unlikely to be rate limiting — a "
                          f"429 on a model you have barely called usually means it has "
                          f"NO free-tier quota on your Cloud project. Being listed by "
                          f"the API does not mean you can call it. The weekly model scout "
                          f"re-tests the leader and demotes it; pin another model on "
                          f"the approval page if you do not want to wait for it.")
                else:
                    print("  Rate limited. Trying next model after wait.")
                continue
            if response.status_code == 403:
                raise Exception("API key rejected (403). Check your GEMINI_API_KEY secret.")
            if response.status_code in (404, 400):
                if require_grounding:
                    # The retry below would produce an answer written without
                    # search and hand it back as if nothing happened.
                    print(f"  {response.status_code} on {model}. NOT retrying without "
                          f"grounding: this issue must be built from live search "
                          f"results. Trying the next model instead.")
                    continue
                print(f"  {response.status_code} on {model}. Retrying without grounding.")
                payload_no_ground = {k: v for k, v in payload.items() if k != "tools"}
                r2 = requests.post(url, json=payload_no_ground, timeout=180)
                record_gemini_request(model, _tokens_used(r2))
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

            _src_list = []
            if require_grounding:
                _gm = candidate.get('groundingMetadata') or {}
                _queries = len(_gm.get('webSearchQueries') or [])
                _chunks  = _gm.get('groundingChunks') or []
                _sources = len(_chunks)
                # Any of these shows search ran; Google only attaches the block
                # when it did, so a differently shaped one on a newer model
                # must not read as "ungrounded".
                _searched = (_queries or _sources or _gm.get('searchEntryPoint')
                             or _gm.get('groundingSupports'))
                if not _searched:
                    # A 200 with the search tool attached is not proof it was
                    # used: the model may simply answer from memory.
                    print(f"  UNGROUNDED: {model} answered without using Google Search "
                          f"(no search queries, no sources). Discarding it: written "
                          f"from training data, it would present old releases as "
                          f"this month's news.")
                    continue
                print(f"  Grounded: {_queries} search quer{'y' if _queries == 1 else 'ies'}, "
                      f"{_sources} source(s).")
                for _c in _chunks:
                    _w = _c.get('web') or {}
                    _name = _w.get('title') or _w.get('uri')
                    if _name and _name not in _src_list:
                        _src_list.append(_name)

            # Thinking models spend part of maxOutputTokens on reasoning before
            # they write the answer. Logged so a cut-off answer is explainable.
            _thoughts = (data.get('usageMetadata') or {}).get('thoughtsTokenCount')
            if _thoughts:
                print(f"  Thinking used {_thoughts} tokens of the "
                      f"{max_output_tokens}-token output budget.")
            if finish_reason == 'MAX_TOKENS' and reject_truncated:
                # A single-section redraft is all-or-nothing: a cut-off answer
                # is worse than none, because it can be reasoning notes or half
                # a paragraph. Discard it and let the next model try.
                print(f"  {model} ran out of output tokens before finishing. "
                      f"Discarding the cut-off text.")
                continue

            parts    = candidate.get('content', {}).get('parts', [])
            # Skip "thought" parts: they are the model's reasoning notes, never
            # part of the answer, and joining them in put a constraint checklist
            # on the page in place of a redrafted section.
            raw_text = ' '.join(p.get('text', '') for p in parts
                                if p.get('text') and not p.get('thought')).strip()

            if len(raw_text) < min_chars:
                print(f"  Only {len(raw_text)} chars, below the {min_chars} minimum.")
                continue

            cleaned = clean_ai_content(raw_text)
            print(f"  SUCCESS: {len(cleaned)} chars from {model}")
            _reqs, _toks = requests_today()
            print(f"  QUOTA: {_reqs} request(s) today from this pipeline "
                  f"({_toks:,} tokens). Daily requests are the free-tier limit "
                  f"repeated testing actually hits. Other apps using this API key "
                  f"draw on the same quota and are not counted here.")
            if model != models_to_try[0]:
                print(f"  FALLBACK MODEL: this issue came from {model}, not "
                      f"{models_to_try[0]}. The reported half survives on the "
                      f"fallbacks; the judgment half — strategic reads, the "
                      f"Desk, the predictions — flattens into restated news. "
                      f"Read those sections closely, and prefer regenerating "
                      f"once the leader is available again.")
            # Tier of the model ACTUALLY USED, independent of whether it was a
            # fallback. The warning above assumed the configured leader is always
            # the strong model — but a lite model can now be adopted as the
            # leader from the approval page, and that silenced the one signal
            # saying to read the judgment sections closely, precisely when it
            # matters most.
            if "lite" in model.lower():
                print(f"  LITE MODEL: {model} is a lite-tier model. The reported "
                      f"half of an issue holds up on lite; the judgment half — "
                      f"strategic reads, the Desk, the predictions — flattens into "
                      f"restated news. Read those sections closely. This fires "
                      f"whether lite is the configured leader or a fallback.")
            return {"content": cleaned, "model": model, "sources": _src_list}

        except requests.exceptions.Timeout:
            print(f"  Timeout on {model}.")
            continue
        except Exception as e:
            if '403' in str(e):
                raise
            print(f"  Error on {model}: {e}")
            continue

    if require_grounding:
        raise Exception(
            "All Gemini models failed to produce a search-grounded answer. Nothing was "
            "staged or changed, on purpose: text written without live search presents "
            "old releases as current news. Try again later; if it keeps happening, "
            "check the log lines above for 429, 400 and UNGROUNDED."
        )
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

    With a direction from Robert the call is SEARCH-GROUNDED: he may point at a
    topic the issue does not cover, and the section is then built on live search
    results (and fails rather than falling back to memory). With the box left
    blank it stays ungrounded: written from the issue as it already stands, it
    can sharpen the argument but cannot introduce a new event, statistic or
    company that never went through the sourcing rules.

    Returns the section body WITHOUT its header line — the same shape
    parse_sections() would have handed the renderer.
    """
    if section not in REDRAFTABLE_SECTIONS:
        raise ValueError(f"'{section}' is not a redraftable section.")

    spec = REDRAFTABLE_SECTIONS[section]["spec"]()
    month_line = f"This is the {month_year} issue.\n" if month_year else ""
    grounded = bool(guidance and guidance.strip())
    guidance_block = ""
    research_block = ""
    if grounded:
        guidance_block = (
            "\nROBERT'S DIRECTION FOR THIS REDRAFT — this is the reason you are\n"
            "being asked to rewrite the section, and it takes precedence over your\n"
            "own choice of angle. Length, format and voice rules in the\n"
            "specification still apply; the RESEARCH RULES below say what changes\n"
            "about facts.\n\n"
            f"{guidance.strip()}\n"
        )
        research_block = f"""
RESEARCH RULES — these apply because Robert gave a direction, and they override the specification wherever the two conflict on facts:
1. Before writing, use Google Search to find current, real information on what Robert's direction asks about. Build the section on what the search returns, not on memory.
2. You MAY now state specific public facts: named organizations, products, laws, figures, dates. But ONLY facts that appear in your search results or in the issue above. Say where each one comes from inside the sentence (for example "according to ..."). This replaces the specification's limit on specific items and its ban on dated events, for public facts only.
3. Today is {datetime.now().strftime("%B %d, %Y")}. Treat events from the last 60 days as current. Anything older is background: say when it happened. Never present a release, law, bill or figure from your training data as current. If a claim is not supported by your search results, leave it out.
4. If the search finds nothing reliable on the topic, argue from patterns and make no factual claim you could not confirm. Do not fill the gap from memory.
5. Nothing changes about Robert himself: never invent a personal anecdote, meeting, client, colleague, project, internal metric or employer. His experience appears only as patterns broadly true of how organizations adopt technology.
6. Every other rule in the specification stays: length, format, voice, no source lines or links inside the text, plain text only.
"""
    source_line = (
        "THE ISSUE AS IT CURRENTLY STANDS — context, so the section you write fits\n"
        "with the rest. Robert's direction below may point at a topic this issue does\n"
        "not cover. If it does, research that topic (see RESEARCH RULES) rather than\n"
        "working from this text alone."
        if grounded else
        "THE ISSUE AS IT CURRENTLY STANDS — this is your source material. Do not introduce\n"
        "any event, company, statistic or date that does not already appear here. You are\n"
        "sharpening judgment, not reporting news."
    )

    prompt = f"""You are rewriting ONE section of Robert Simon's monthly newsletter, Practical AI for Canadian Business. Robert is an independent AI thought leader in Montreal. His voice is direct, opinionated and grounded in business outcomes. He does not hedge.

{month_line}
{_EDITORIAL_PREAMBLE}

{source_line}

<issue>
{issue_text.strip()}
</issue>

YOUR TASK
Rewrite the section specified below. It must be materially different from the
version currently in the issue — a new angle or a sharper argument, not a
paraphrase. Everything else in the issue stays as it is.
{guidance_block}{research_block}
SPECIFICATION FOR THE SECTION YOU ARE WRITING:

{spec}

OUTPUT RULES
Return ONLY the body of the section. Do NOT repeat the section header. Do not
add a preamble, a sign-off, markdown, or any commentary about what you changed.
Plain text only — no *, no **, no #.
"""

    result = _call_gemini(
        api_key, prompt,
        max_output_tokens=8192,   # was 2048: a thinking model could spend the
                                  # whole budget reasoning and never answer
        temperature=0.6 if grounded else 0.8,   # an ungrounded redraft should
                                  # land somewhere different; a grounded one is
                                  # reporting facts, so it runs cooler
        use_search=grounded,
        min_chars=40,
        reject_truncated=True,
        require_grounding=grounded,
    )
    if grounded:
        _names = result.get("sources") or []
        print(f"  Web sources behind this redraft ({len(_names)}): "
              + (", ".join(_names[:10]) if _names else "none reported"))
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
    return f"""You are writing Practical AI for Canadian Business, the monthly AI briefing for small Canadian businesses by Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert spent 25+ years in digital transformation and now helps small businesses and professional practices get real work out of the AI subscriptions they already pay for. His voice is direct, opinionated, and grounded in real business outcomes. He does not hedge. He calls things what they are.

AUDIENCE
Owners and small teams (1 to 20 people) of Canadian small businesses and professional practices: accountants, advisors, clinics, trades, agencies, shops, consultants. Most already pay about $30 a month per person for ChatGPT, Claude, Gemini or Microsoft 365 Copilot, or are deciding whether to. They have no IT department and no time. They do not care about the AI industry; they care about what their subscription can now do for their own work. Write in plain language, define any term a non-technical owner would not know, and respect their time. Readers from larger organizations still read this: the Canadian section and Robert's own section keep the wider context for them.

{rules}"""


def _build_custom_prompt(topic, month_year, prev_month, is_backfill=False, today=None):
    rules = _shared_rules_block(month_year, prev_month, is_backfill, today)
    return f"""You are writing Practical AI for Canadian Business, the monthly AI briefing for small Canadian businesses by Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert spent 25+ years in digital transformation and now helps small businesses and professional practices get real work out of the AI subscriptions they already pay for. His voice is direct, opinionated, and grounded in real business outcomes. He does not hedge. He calls things what they are.

AUDIENCE
Owners and small teams (1 to 20 people) of Canadian small businesses and professional practices: accountants, advisors, clinics, trades, agencies, shops, consultants. Most already pay about $30 a month per person for ChatGPT, Claude, Gemini or Microsoft 365 Copilot, or are deciding whether to. They have no IT department and no time. They do not care about the AI industry; they care about what their subscription can now do for their own work. Write in plain language, define any term a non-technical owner would not know, and respect their time. Readers from larger organizations still read this: the Canadian section and Robert's own section keep the wider context for them.

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
reason anyone subscribes to this one. A reader comes here for one thing: what the
low-cost AI plans (ChatGPT, Claude, Gemini, Microsoft 365 Copilot) can do NOW that
they could not do last month, and what that is worth to a small Canadian business.

Roughly HALF this issue is reported fact: what launched, in which plan, on what
date. The other half is original judgment: which of it is worth an owner's time,
which is noise, who it suits and what the catch is. The reader must finish every
issue knowing not only what changed, but what they could try next.

Test every sentence in an analysis section against this: could it appear verbatim
in the vendor's own announcement? If yes, it is reporting, and it does not count
toward the analysis half. Restating the news in a more emphatic tone is the single
most common way this publication fails.

TEASE, DO NOT TEACH. Each issue names use cases and their benefit: the kind of
business, the job, the time or hassle it removes. It never gives the step-by-step
set-up, the prompt wording, the settings or the workaround for a limit. A reader
should finish thinking "that would help us" and want to find out whether their own
plan can do it. Do not write any call to action, offer, link or mention of
Robert's services, consulting, website or a feasibility check anywhere in the
issue: the page adds that itself, once, at the end.

VOICE AND EXPERIENCE:
Robert writes from 25+ years of digital transformation, much of it watching large
organizations buy technology and then fail to change how the work gets done. He
now applies that to small teams. The first-person sections should sound like
someone who has seen many technology roll-outs stall and knows why: specific about
mechanism, unsentimental, willing to name the part nobody wants to discuss, and
clear that a small business can move faster than a large one because it has no
committees.

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
or imply any current or former employer. Never describe a client, a client result
or "a business I worked with". Every experience-based observation must be a
pattern that is broadly true of how organizations adopt technology, not a story.

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
catch owners are overlooking is", "The small businesses that get value will".
Every opinion must be followed by its reasoning in the same breath. An assertion
with no argument behind it is worse than no assertion. Be willing to say the
uncomfortable thing if it is what the evidence supports."""

_SPEC_EXECUTIVE_SUMMARY = """EXECUTIVE SUMMARY (exactly 3 numbered items, one sentence each, max 25 words each):
The three things a busy owner must take away if they read nothing else. Each one
states a CONCLUSION about what a low-cost AI plan can now do or what a small
business should do about it, not a topic. "A $30 plan can now read a year of
invoices and flag the unpaid ones without anyone exporting a file" is a
conclusion. "New spreadsheet features" is a topic and is useless here.
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
- What do small business owners consistently misunderstand about this?
- What trend worries me, and what specifically is the failure mode?
- What is overhyped right now, and what is the tell?
- What should a small Canadian business begin doing now with the plan it already pays for?
- What can safely wait, and why is waiting the right call?
- What will actually matter six months from now that almost nobody is discussing?

You may use at most TWO specific items from the sections above, and only as a
springboard into an argument that goes somewhere they do not. The value here is
the pattern behind the news, not the news.

At least one paragraph must draw on how technology adoption really goes, applied to
a small team: the tool gets bought and not used, the owner is the bottleneck,
nobody writes down how the work is done, habit beats features, and the gap between
a clever demo and a job that runs every week. Where it helps, contrast it with how
large organizations get this wrong, because a small business can skip those
mistakes. Obey the HARD CONSTRAINT above: patterns that are broadly true, never
invented specifics, never a client story, never a named or implied employer.

Say at least one thing a cautious writer would leave out. Support it with reasoning
in the same paragraph.

Do not open with "This month". Do not open with a summary sentence. Open on the
observation itself."""


_SPEC_PREDICTIONS = """LOOKING AHEAD: THREE PREDICTIONS
Three predictions at three horizons. These are explicitly predictions, not
reporting, and must read that way — "I expect", "I think it is likely that", "My
assessment is". Never state a prediction as a fact.

Make them about what the low-cost AI plans will be able to do, what they will cost,
or what a small Canadian business will have to deal with. Be conservative. A
prediction that is obviously safe is useless, but a dramatic
one that fails destroys the credibility of everything else in the issue. Aim for
claims that are specific enough to be wrong, and that you would still defend if
challenged. Each is 1-2 sentences.

Use this EXACT format, each on its own line:
One month: [prediction]
Six months: [prediction]
One year: [prediction]"""

_SPEC_QUESTION = """ONE QUESTION FOR YOUR LEADERSHIP TEAM:
(The header keeps this wording because the page is built from it. The reader is
the owner of a small business, so write the question for them.)
A single question an owner could ask themselves, or put to their small team on
Monday morning. Write the question and nothing else — no preamble, no answer, no
explanation.

It must be answerable in a real conversation and uncomfortable enough to be worth
asking. It should expose a gap rather than invite a status update, and it should
come out of this month's material.
Good: "We pay for four AI seats. Which single weekly task has each of them
actually stopped doing by hand — and if the answer is none, what are we paying
for?"
Weak: "How can we better take advantage of AI?"

Write one or two sentences maximum, ending in a question mark."""

# The December 2026 issue (covering November 2026) is the first one written for
# small businesses rather than for executives at large organizations. Regular
# readers get a short, one-time explanation at the top of Robert's own section.
# Keyed on the coverage month so it can never appear in any other issue.
_TRANSITION_COVERAGE_MONTH = "November 2026"


def _transition_note(month_year):
    if str(month_year).strip() != _TRANSITION_COVERAGE_MONTH:
        return ""
    return """
ONE-TIME NOTE FOR THIS ISSUE ONLY: this is the first issue written for small
businesses. Open FROM ROBERTS DESK with two or three plain first-person sentences
telling regular readers that this briefing is narrowing its lens: from the AI
industry at large to what the low-cost AI plans can actually do for a small
Canadian business, because that is where the practical value now sits and where
most Canadian businesses are. Say that the Canadian context stays. Do not
apologise, do not announce a "new format", do not mention any service or offer.
Then carry on with the section as specified; this opening counts toward its
length. This note overrides "Open on the observation itself" for this issue.
"""


def _shared_rules_block(month_year, prev_month, is_backfill=False, today=None):
    today_str = (today or datetime.now()).strftime('%B %d, %Y')
    # Drawn from the one list in utils.py rather than retyped here, so the
    # names the prompt asks for and the names the renderer orders by cannot
    # drift apart. A sample, not the whole set — the point is to establish the
    # KIND of company, and the full list would read as a checklist to fill.
    brand_examples = ", ".join([
        "RBC", "TD Bank", "Scotiabank", "BMO", "CIBC", "Desjardins",
        "Bell Canada", "Rogers", "Telus", "Loblaw", "Canadian Tire",
        "Shoppers Drug Mart", "Sobeys", "Couche-Tard", "Air Canada", "WestJet",
        "Canada Post", "Tim Hortons", "Sun Life", "Manulife", "Enbridge",
        "Hydro-Québec", "CN Rail", "Lululemon", "Dollarama",
    ])
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
5. Ground everything in Canadian small-business reality: prices in Canadian dollars, features that launch in the US first and reach Canada later, Quebec Law 25 and PIPEDA when customer information is involved, serving customers in English and French, tight margins and no IT department. Mention a law, program or price only when a search result for this month supports it.
6. Name the real product and the real plan every time: "ChatGPT Plus", "Claude Pro", "Google AI Pro", "Microsoft 365 Copilot", not "an AI tool". Name real Canadian companies and institutions where relevant: Shopify, Intuit QuickBooks, Wave, Desjardins, RBC, TD, Scotiabank, BMO, CIBC, Bell, Rogers, Telus, Canada Post, BDC, CFIB, the Privacy Commissioner of Canada, Quebec's Commission d'acces a l'information.
7. Say which plan or tier includes a feature ONLY when the source says so. If the source does not say, or says it is rolling out gradually, write that plainly ("rolling out; check whether your plan has it"). Never guess a tier, a price or Canadian availability. A wrong claim about what a reader's plan includes is the most damaging error this publication can make.

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

THIS IS ENFORCED IN CODE, NOT LEFT TO JUDGMENT. Every development is checked
against a list of known publications before publication. A citation qualifies
only if it is one of:

  1. A recognised news outlet or research body — Reuters, Bloomberg, Associated
     Press, Globe and Mail, Financial Post, National Post, CBC, The Logic,
     BetaKit, The Verge, TechCrunch, Ars Technica, Wired, MIT Technology
     Review, CNBC, Business Insider, Axios, The Register, Statistics Canada,
     McKinsey, Deloitte, KPMG, Gartner, Forrester, and the like.
  2. A government or regulatory body — Government of Canada, ISED, OSFI,
     Bank of Canada, the Privacy Commissioner, a provincial ministry.
  3. The subject's OWN newsroom — an OpenAI announcement cited to the OpenAI
     blog, a Google release cited to the Google blog.

Anything else is deleted from the issue automatically. Recent runs lost stories
to "Analytics Vidhya", "ThursdAI", "BenchLM.ai", "Signal49 Research" and
"ML Kenya Blogs" — aggregators and newsletters whose names give nothing away.
If the only place you can find a story is one of those, THE STORY DOES NOT GO
IN. Find the primary announcement it was summarising, or report a different
development.

Report fewer developments rather than citing an aggregator: a thin issue costs
you one story, a bad citation costs the publication its credibility.

OUTPUT FORMAT
WRITE THE ISSUE EXACTLY ONCE. Emit each section header one time only and stop after ONE QUESTION FOR YOUR LEADERSHIP TEAM. Do not restate, repeat or re-draft the issue after finishing it. A run that wrote every section twice put the entire duplicate inside the closing question, which then published with a raw header in its text.
Write plain text only. No markdown (no *, no **, no #). Use EXACTLY these section headers, spelled exactly like this, each on its own line, in this order:

HEADLINE
INTRODUCTION
EXECUTIVE SUMMARY
KEY AI DEVELOPMENTS
CANADIAN SPOTLIGHT
FROM ROBERTS DESK
STRATEGIC ACTIONS FOR THIS MONTH
ADOPTION SNAPSHOT
LOOKING AHEAD: THREE PREDICTIONS
ONE QUESTION FOR YOUR LEADERSHIP TEAM

Write FROM ROBERTS DESK without an apostrophe, exactly as shown.

LENGTH BUDGET — the issue is a focused briefing for busy owners, not a digest. These
readers have limited time and the publication's promise is a short read. Depth in
the analysis sections is paid for by discipline in the reported ones. Stay inside
this budget; it totals roughly 1,300 words:

  INTRODUCTION                            55 words
  EXECUTIVE SUMMARY                       55 words   (3 items, max 25 each)
  KEY AI DEVELOPMENTS                    340 words   (3 major at ~80, then 2-3 log entries at ~35)
  CANADIAN SPOTLIGHT                     115 words   (3 items)
  FROM ROBERTS DESK                  300-450 words
  STRATEGIC ACTIONS FOR THIS MONTH       180 words   (3 use cases, 60 each MAXIMUM, owner line included)
  ADOPTION SNAPSHOT                       70 words
  LOOKING AHEAD: THREE PREDICTIONS        85 words
  ONE QUESTION FOR YOUR LEADERSHIP TEAM   30 words

These are CEILINGS, not targets to grow into. Recent issues came in at 2,100
words against this 1,300-word budget and read at nine minutes rather than six;
the promise on the tin is a short briefing. Before you finish, count your
STRATEGIC ACTIONS section in particular — it has been the longest section in
every recent issue while the budget makes it one of the shortest.

Per item, the hard caps are:
  - a major development: 2 sentences of report + 3 sentences of Robert's read
  - a log development: 2 sentences, nothing more
  - a spotlight item: 2 sentences
  - a use case: 2 sentences, then ONE sentence naming who in the business and why

Never exceed the item counts specified below; they are maximums as well as
minimums. If a section is running long, cut reported detail before cutting
judgment — the analysis is what the reader came for.

---

HEADLINE (one line, 50-85 characters):
Name the single most useful change of {month_year} for a small Canadian business, as a specific claim: what a low-cost AI plan can now do. This becomes the page title, so it is what a search engine or an AI assistant matches a question against.
State the actual product and the actual capability. "Claude Pro can now work inside Excel files: what it means for a small bookkeeping practice" works. "AI Insights for {month_year}", "Key AI developments", "The month in AI" and any other generic phrasing are useless here and must never be used — a title with no topic in it cannot be retrieved for a topic.
No colon-free clickbait, no questions, no "you won't believe". Plain declarative. Do not include the month name — it is added automatically.
Write the headline on ONE line directly under the HEADLINE header, with no quotes around it.
Build the headline ONLY from a KEY AI DEVELOPMENTS item whose source is the vendor's own post or release notes, or a major outlet. A headline about an item that is later deleted for its source leaves the issue promising a story it does not contain.

INTRODUCTION (3 sentences maximum):
CRITICAL: The first sentence MUST contain the specific claim you made in the
HEADLINE — the same entity and the same number, policy or figure, stated as a
fact. The headline is a promise; the sentence under it has to pay that promise
immediately. An issue titled "Ottawa's new AI strategy commits $700M for SME
compute access" whose opening paragraph says only "a five-year plan for domestic
AI leadership" reads as though the title belongs to a different article, and the
reader has to hunt for the number that drew them in.

Second sentence: what it means for a small Canadian business. Third sentence: what this analysis helps the reader do. Do NOT start with "Welcome", "This month", or any warmup phrase. Make the reader want to keep going.

{_SPEC_EXECUTIVE_SUMMARY}

KEY AI DEVELOPMENTS (exactly 5 or 6 items — not more, not fewer):
On the page this section is titled "New in your AI subscription". It reports what
changed in {month_year} in the low-cost AI plans a small business actually buys:
ChatGPT (Plus, Business/Team), Claude (Pro, Team), Google Gemini (Google AI Pro,
Gemini in Google Workspace) and Microsoft 365 Copilot. New features, new
connections to everyday tools (email, calendar, files, spreadsheets, accounting),
changes to limits or price, and availability in Canada.
Select ruthlessly: an item earns its place only if the owner of a 1-to-20 person
business could do something new with it, or should change what they pay for,
without hiring a developer. At least FOUR of the items must be a change to one of
those plans. At most TWO may be other AI company news (a new model, a security
incident, a deal), and only when it changes what those plans can do or what a
small business should watch out for. Funding rounds, benchmarks, research papers,
chips, data centres and enterprise-only products do not belong here.
Spread the items across vendors: do not give one vendor more than three slots.
CRITICAL DATE RULE: Include ONLY events from {month_year}. Never fabricate. Never use events from prior months, and never use a date after {today_str} (see the future-date rule above).
CRITICAL SECTION ROUTING RULE: KEY AI DEVELOPMENTS is strictly for AI company announcements — products, features, plans, models, partnerships. It must NEVER contain items from any government entity. This includes: the Government of Canada, any provincial or municipal government, the Prime Minister, any federal minister, any G7/G20/OECD ministerial body, Statistics Canada, Bank of Canada policy announcements, or any Crown corporation acting in a regulatory/policy capacity. Any government funding, policy, regulation, or strategy announcement MUST go in CANADIAN SPOTLIGHT — never here.
CRITICAL SOURCE RULE: Every single item MUST end with a Source line. No exceptions.
CRITICAL SOURCE QUALITY RULE: Every source MUST be a primary source — the vendor's own announcement post, or a major news publication reporting it. Newsletters, podcast episodes, Substack posts, and aggregator blogs are NEVER acceptable sources.

HOW TO SEARCH FOR THESE ITEMS. Read this before searching; it is the difference between an issue that publishes and one that gets thrown away.

A roundup is a LEAD, NOT A SOURCE. If a newsletter or aggregator ("ThursdAI", "Analytics Vidhya", a weekly AI digest) surfaces a story, that is useful — it told you the event exists. Do not discard it and do not cite it. Follow it through: find the announcement or the article it was summarising, and cite THAT. Every story in a roundup came from somewhere, and that somewhere is your source.

Search the VENDORS' OWN SITES and the major outlets, not the open web. A general query such as "ChatGPT new feature {month_year}" returns resellers, agencies and training companies summarising the vendor, and every item cited to one of those is deleted. Two trial issues lost most of this section that way. Restrict each search to a site that is an acceptable source, for example:
  - "site:openai.com {month_year} ChatGPT", "site:help.openai.com ChatGPT release notes"
  - "site:anthropic.com/news Claude {month_year}", "site:support.anthropic.com release notes"
  - "site:blog.google Gemini {month_year}", "site:workspaceupdates.googleblog.com Gemini {month_year}"
  - "site:microsoft.com Microsoft 365 Copilot {month_year}", "site:techcommunity.microsoft.com Copilot what's new {month_year}"
  - "site:theverge.com ChatGPT OR Claude OR Gemini OR Copilot {month_year}", and the same for techcrunch.com, arstechnica.com, cnbc.com, reuters.com, betakit.com
Then, for each change you found, run one more search for price, usage-limit or Canadian-availability details on the same sites.
Aim for 5-6 items spanning at least THREE of the four vendors. Before you write an item, check its source against the list below; if it is not on the list, search the vendor's site for the same change and cite that, or drop the item and use another. It is better to hand in five items you can source properly than six of which three will be deleted.

WHERE THE SOURCE MUST COME FROM — the first trial of this format lost EVERY item in this section, because each one was cited to a third-party blog that had summarised the vendor ("Allianze Technologies", "The Oxford AI School", "Jetstream BLOG"). Those are deleted automatically. For a change to one of the four plans there are only three acceptable kinds of source:
  1. The vendor's own announcement. Write the Source name as the vendor's own publication: "OpenAI", "Anthropic", "Google", "Google Workspace Updates", "Microsoft", "Microsoft 365 Blog". The headline after the bar is the title of the vendor's own post.
  2. The vendor's own dated release notes, when that is where the change was announced. Write it as "OpenAI Release Notes", "Anthropic Release Notes", "Google Workspace Release Notes", "Microsoft 365 Release Notes", and use the entry's own title as the headline.
  3. A major technology or business outlet that reported it: The Verge, TechCrunch, Ars Technica, Wired, CNBC, Reuters, Bloomberg, Axios, The Register, Business Insider, BetaKit, The Logic, Globe and Mail, Financial Post, CBC.
A consultancy, a training company, a reseller, an agency or an "AI school" writing about a vendor's feature is a LEAD: it tells you the feature exists. Open the vendor's own post or release-note entry about it and cite THAT. If you cannot find the vendor's own post or a major outlet, the item does not go in.

Evergreen documentation is still not an announcement. A help centre how-to article, a docs page, "Microsoft Learn" or an API reference describes how something works and is no evidence it changed this month. Dated release notes are the exception, as above.

Name the outlet, not the aggregator that repeated it. If you cannot say which publication reported a story, or which company announced it, you do not have the source yet — keep looking or drop the item.
CRITICAL DEDUPLICATION RULE: Treat KEY AI DEVELOPMENTS and CANADIAN SPOTLIGHT as one combined list. Every individual news event, funding program, company announcement, or policy decision may appear ONCE across both sections combined — never twice. Same program = same event = one section only. If the AI Compute Access Fund, RAII, or any government initiative appears in KEY AI DEVELOPMENTS, it must NOT appear in CANADIAN SPOTLIGHT under any name, wording, or angle. No exceptions.

THIS SECTION HAS TWO TIERS. The FIRST THREE items are the most useful changes and
carry Robert's read plus three ratings. Items 4 onward are the compact log and
carry neither. Order the section so the three changes most useful to a small
business come first — that ordering IS the designation.

Use this EXACT format for items 1, 2 and 3 — copy the label words precisely,
including the capitalisation and the full stops (the labels are fixed because the
page is built from them; their meaning for this audience is given below):
[Month Day]: [Company] — [One sentence: what changed, naming the product and, if the source states it, the plan]. [One sentence: what a small business can now do that it could not do before]. STRATEGIC READ: [2-3 sentences of Robert's own interpretation]. IMPORTANCE: [High or Medium or Low]. HORIZON: [Now or 3 Months or 6 Months or 12 Months]. ATTENTION: [Yes or Monitor or Ignore]. Source: [Publication name] | [Exact article headline as published]

What the three ratings mean here:
- IMPORTANCE = how useful this is to a typical small business (High, Medium, Low).
- HORIZON = when a Canadian small business can realistically use it. "Now" only if it is available today on a low-cost plan in Canada according to the source; otherwise 3, 6 or 12 Months.
- ATTENTION = the verdict. Yes = worth trying. Monitor = wait and see. Ignore = skip it.

Example of the FORM only (invented product, do not reuse any of it):
May 15: Acme AI — Added a calendar connection to Acme Assistant on its paid personal plan. A two-person office can now ask it to find a meeting time across both calendars and draft the invitation. STRATEGIC READ: The feature is not the point; the hour a week an owner spends on scheduling is. It suits practices that book their own appointments, and the catch is that it reads every calendar entry, so anything confidential in a title is now in front of the assistant. Most small firms will switch it on and never give it a real job. IMPORTANCE: Medium. HORIZON: Now. ATTENTION: Yes. Source: Acme AI Blog | Acme Assistant Can Now Read Your Calendar

What STRATEGIC READ must do — it answers some of these, never all:
- Who is this actually for? Name a kind of small business and the weekly job it touches.
- What does it replace or remove: which chore, which export, which hour?
- What is the catch: the plan tier, a usage limit, a privacy consequence, a Canadian delay?
- What will most small businesses get wrong about it?
It must NOT restate the two sentences above it in different words, and it must NOT
explain how to set the feature up. If your read could be deleted without losing any
information, rewrite it.

Use this EXACT format for items 4 onward — no strategic read, no ratings:
[Month Day]: [Company] — [One sentence: what changed]. [One sentence: what it means for a small business]. Source: [Publication name] | [Exact article headline as published]

Rules:
- EXACTLY 5 or 6 items total. The first 3 carry STRATEGIC READ and all three ratings; the rest carry none.
- [Company] is the vendor: OpenAI, Anthropic, Google or Microsoft (or the company concerned for the at-most-two other items). Put the product and plan name in the sentence, not in the [Company] slot.
- Every item has ONE date from {month_year}. A single day, never a range: write "July 22", never "July 22-30" or "July 22 to 30". If a feature rolled out over a week, date it to the day it was announced.
- Every item ends with Source: [Publication] | [Headline] — no URLs, no brackets around the headline
- The word "Source" must always be preceded by a full stop, so ratings lines end with a full stop as shown
- Every source is a PRIMARY source (the vendor's announcement, a major news outlet) — NEVER a newsletter or podcast
- The small-business sentence must be specific: a kind of business and a job, not "businesses can be more productive"
- Do not rate everything High. If all three are High, you have not made a judgment. ATTENTION: Ignore is a legitimate and useful verdict on a feature that is loud but useless to a small team.
- UNIQUENESS RULE: Every item must cover a distinct announcement.

CANADIAN SPOTLIGHT (MINIMUM 3 items — hard requirement):
WHO THIS SECTION IS FOR. On the page this section is titled "The Canadian angle". The reader runs a small Canadian business. This is the section that makes the issue Canadian: what is different, required or available HERE. It also keeps the wider Canadian picture for readers from larger organizations. Keep it to what a small business owner would act on or want to know.

SELECT IN THIS PRIORITY ORDER:
1. HOUSEHOLD-NAME CANADIAN COMPANIES putting AI in front of their customers, first choice whenever such stories exist, and best of all when the customers are small businesses: a bank's small-business banking assistant, a telecom's AI call handling, Shopify or an accounting tool adding AI their merchants can use, Canada Post, an insurer's AI claims service. For example: {brand_examples}. What earns the slot is a company the reader recognises describing a REAL DEPLOYMENT — what it does, where it runs, who it serves. "Bank X launched an AI assistant for small-business accounts" is the shape. "Bank X is investing in AI" is not.
2. GOVERNMENT AND REGULATOR items that touch a small business — these belong HERE and never in Key Developments (routing rule below), and take AT MOST ONE slot unless there are fewer than two qualifying brand stories this month. Privacy guidance on using AI with customer information (the Privacy Commissioner of Canada, Quebec's Commission d'acces a l'information, Law 25), funding or advice programs a small business can apply for (BDC, ISED, provincial programs), a rule that changes what a small business must do. Skip national strategy, compute funds and sovereign-AI items unless they change something for a small business this year.
3. CANADIAN AVAILABILITY AND PRICE of the low-cost AI plans (a feature reaching Canada, a Canadian-dollar price change, French-language support) and CANADIAN AI COMPANIES — use these to fill remaining slots.

HOW TO SEARCH FOR THE BRAND ITEMS. This is the part that decides whether the section works, and it is the same lesson as the developments section: a priority list alone does not change what your searches return.

A generic query — "Canadian AI news {month_year}", "Canada artificial intelligence {month_year}" — returns GOVERNMENT announcements, because Ottawa publishes constantly and consistently and ranks for those terms. That is why this section keeps filling with federal programs. Searching harder on the same query will not fix it.

Search COMPANY BY COMPANY instead. Run a separate query for the recognisable names in each sector, for example "RBC small business AI {month_year}", "Telus AI customer service", "Shopify AI merchants", "QuickBooks Canada AI", "Canada Post AI", "Desjardins AI". Work through banks, then telecoms, then the tools small businesses run on (payments, accounting, e-commerce), then retail, travel, insurance and energy. Also search the regulators directly: "Privacy Commissioner of Canada AI {month_year}", "Commission d'acces a l'information intelligence artificielle", "BDC AI small business". Most will return nothing in a given month; two or three will return something real, and those are your items.

IF YOU HAVE WRITTEN TWO GOVERNMENT ITEMS, STOP. Go back and run the company-by-company searches before adding a third. Three federal items is the specific failure this section is being corrected for.

"MANDATORY here" in the routing rule means a government item BELONGS in this section rather than in Key Developments. It does not mean this section must be filled with government items.

ORDER THE SECTION so household-name adopters appear first.

Do NOT invent or stretch to satisfy the priority. If only one household-name adoption story is properly sourced this month, run one and fill the rest by priority. A padded brand item cited to a vendor blog is worse than a well-sourced government item.

CRITICAL SOURCE RULE: Every single Canadian Spotlight item MUST end with a Source line using a PRIMARY source only.
CRITICAL GOVERNMENT-SOURCE RULE: When the item is a government, regulator or Crown-agency action — ISED, the AI Compute Access Fund, OSFI, the Privacy Commissioner, Quebec's Commission d'acces a l'information, a provincial ministry — cite THAT BODY'S OWN page or release. Those bodies publish everything they announce. A run cited an ISED funding program to a business-services blog and Quebec Law 25 guidance to a marketing site, when both were announced by the bodies themselves. A consultancy or vendor blog writing about a government program is not the source for it.
CRITICAL UNIQUENESS RULE: Canadian Spotlight items MUST NOT repeat any announcement already in KEY AI DEVELOPMENTS.

Use this EXACT format for every item:
[Company/Organization]: [What happened — one sentence]. [Why it matters to a small Canadian business — one sentence]. Source: [Publication name] | [Exact article headline as published]

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
{_transition_note(month_year)}

STRATEGIC ACTIONS FOR THIS MONTH (exactly 3 items):
On the page this section is titled "Worth trying this month". These are three USE
CASES, each for a different kind of small business, each made possible or easier by
something in KEY AI DEVELOPMENTS or CANADIAN SPOTLIGHT this month.
CRITICAL TRACEABILITY RULE: Each of the 3 use cases MUST trace directly to a named item above. Make that connection explicit by naming the product or feature.
CRITICAL TEASER RULE: Describe the job and the benefit, never the method. No steps, no prompt wording, no settings, no "first... then...". Whether a particular reader's own plan can do it is the open question the page answers after the issue, so do not promise that it will work on every plan.

Use this EXACT format — copy the label words precisely, including the
capitalisation and the full stops (fixed labels; their meaning here is below):

1. [Use case, 2 sentences. Starts with a strong verb, names a kind of small business and the specific weekly job, names the feature it relies on, and says what it saves or removes.] OWNER: [Who in a small business] — [one sentence: why this person and not the obvious alternative]. PRIORITY: [High or Medium or Low]. EFFORT: [Small or Medium or Large]. IMPACT: [Low or Medium or High].

What the labels mean here:
- OWNER = who in a small business should try it.
- PRIORITY = how soon it is worth trying. EFFORT = how much set-up it takes a non-technical person. IMPACT = how much time or hassle it removes.

Example of the FORM only (invented, do not reuse any of it):
1. Hand the weekly supplier-statement check in a small renovation firm to Acme Assistant's new spreadsheet connection, so nobody has to line up invoices against payments by eye. It turns a Friday-afternoon chore into a short review, worth trying before the next month-end. OWNER: Bookkeeper — the owner will want to do this personally, but the person who knows which suppliers always invoice late is the one who can tell a real error from a normal one. PRIORITY: Medium. EFFORT: Small. IMPACT: Medium.

Each use case must:
- Start with a strong verb: Try, Test, Hand, Draft, Turn, Replace, Stop, Give, Let, Block time to
- Name a different kind of small business each time (for example a bookkeeping practice, a dental clinic, a contractor, a boutique, a two-person agency, a financial advisor)
- Name the specific feature or development it relies on
- Include a time frame (this week / before month-end / before the busy season)
- Be 2 sentences before the OWNER label

OWNER rules:
- Pick from: Owner, Office manager, Bookkeeper, Practice manager, Whoever answers client email, Sales lead, Marketing lead, Operations lead, Front desk, Senior technician
- The rationale after the dash must explain why THIS person rather than the one a reader would assume, usually the owner.
- Do not assign all three to the Owner. In a small business everything lands on the owner, which is exactly why nothing gets adopted.

PRIORITY, EFFORT and IMPACT rules:
- These are independent axes. High impact with Small effort is exactly what an owner is scanning for.
- At most one of the three may be PRIORITY: High.
- Be honest about EFFORT. If it needs a paid add-on, a connection someone has to approve, or cleaning up files first, it is not Small.

ADOPTION SNAPSHOT (exactly 5 data points):
CRITICAL: Each stat on its own line. Never combine into a paragraph.
CRITICAL FORMAT: The number MUST come first.

Correct format examples:
30% of Canadian businesses have adopted AI in at least one function. Source: BDC, 2025.
46% of employed Canadians say AI has impacted their career trajectory. Source: Borderless AI, 2026.
Global: 70% of organizations have an AI strategy in place. Source: McKinsey, 2025.

Format for each line:
[Number]% [rest of stat]. Source: [Organization], [year].

Prefer statistics about small and medium-sized Canadian businesses (adoption, spending, barriers, time saved) over statistics about large enterprises. Use only real, verifiable Canadian stats from: Statistics Canada, BDC, ISED, CIRA, Conference Board of Canada, Deloitte Canada, KPMG Canada, PwC Canada, Mila Annual Report, Vector Institute Annual Report, McKinsey Canada.

{_SPEC_PREDICTIONS}

{_SPEC_QUESTION}

---
Context: {month_year} edition"""
