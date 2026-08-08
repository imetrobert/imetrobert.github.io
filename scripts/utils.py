"""
utils.py
Shared helper functions used across the blog generation pipeline.
"""

import re
import requests
from datetime import datetime


# ---------------------------------------------------------------------------
# Brand. Defined once and imported by every generator.
#
# Before this existed the publication answered to four different names across
# its own surfaces — "AI Insights for Canadian Business" in the feed and post
# nav, "AI Insights Blog" in the h1 and breadcrumbs, "AI News for Canadians |
# Monthly AI Insights Blog" in the index title, and "Robert Simon - AI
# Innovation" as og:site_name on every share. Nothing enforced agreement, so
# they drifted apart one edit at a time. Add a surface, import from here.
#
# BRAND is the canonical name. BRAND_SHORT exists because the full name is 34
# characters and does not fit a nav bar or a breadcrumb on a phone; it is a
# space-constrained alias, not a second brand.
# ---------------------------------------------------------------------------
BRAND         = "Practical AI for Canadian Business"
BRAND_SHORT   = "Practical AI Canada"
BRAND_TAGLINE = "The month's AI developments, and what to do about them"
AUTHOR        = "Robert Simon"


# ---------------------------------------------------------------------------
# Gemini request ledger — requests per day, which is the free-tier limit this
# pipeline can realistically hit.
#
# The free tier is NOT a monthly token pool. It is rate limits: requests per
# minute, tokens per minute, and requests per DAY. Repeated test runs bump into
# the daily request count long before anything else, so that is the only number
# worth showing.
#
# A RUN IS NOT A REQUEST. One generation can fire several: a 503 buys the same
# model a second attempt, a fallback tries the next model, and a 400/404 retries
# without grounding. Counting runs would undercount the quota, so the ledger is
# incremented at the HTTP call itself.
#
# Scope, stated plainly wherever this is displayed: this counts only requests
# made by THIS pipeline. An API key belongs to one Google Cloud project and every
# app using that key draws on the same quota, so anything else you run against it
# is invisible here. The authoritative view is Cloud Console -> APIs & Services
# -> Generative Language API -> Quotas.
# ---------------------------------------------------------------------------
USAGE_LEDGER_PATH = "blog/staging/usage.json"

# Free-tier requests per day, PER MODEL — these are separate budgets, not one
# shared pool, so 10 flash requests and 5 lite requests are 10/1500 and 5/1000
# rather than 15 against a single number. Which also means a run that falls back
# is not spending the leader's quota.
#
# Per Google's free tier as of August 2026. Quotas are assigned per Google Cloud
# PROJECT and Google no longer publishes a universal table, so treat these as
# defaults: the panel lets each one be overridden, and the console is
# authoritative.
MODEL_DAILY_LIMITS = {
    "gemini-2.5-flash": 1500,
    "gemini-2.5-flash-lite": 1000,
    "gemini-2.0-flash": 1500,
}

# Google resets these quotas at midnight Pacific, so the ledger buckets by
# Pacific date rather than UTC or Eastern — otherwise the count would roll over
# at the wrong moment and read as headroom that is not there.
_QUOTA_TZ = "America/Los_Angeles"


def quota_day(now=None):
    """Today's date in the timezone Google resets daily quotas in."""
    try:
        from zoneinfo import ZoneInfo
        return (now or datetime.now(ZoneInfo("UTC"))).astimezone(
            ZoneInfo(_QUOTA_TZ)).strftime("%Y-%m-%d")
    except Exception:
        return (now or datetime.now()).strftime("%Y-%m-%d")


def _read_ledger(path=None):
    import json
    try:
        with open(path or USAGE_LEDGER_PATH) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record_gemini_request(model="", tokens=0, path=None):
    """Count one HTTP request against today's quota bucket.

    Never raises: a ledger write failing must not lose a generated issue.
    Keeps 60 days and drops the rest, so the file cannot grow without bound.
    """
    import json, os
    path = path or USAGE_LEDGER_PATH
    try:
        day = quota_day()
        data = _read_ledger(path)
        entry = data.get(day) or {"requests": 0, "tokens": 0, "models": {}}
        entry["requests"] = int(entry.get("requests", 0)) + 1
        entry["tokens"] = int(entry.get("tokens", 0)) + int(tokens or 0)
        if model:
            entry.setdefault("models", {})
            entry["models"][model] = int(entry["models"].get(model, 0)) + 1
        data[day] = entry
        for old in sorted(data)[:-60]:
            data.pop(old, None)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        return entry
    except Exception as exc:
        print(f"  NOTE: could not update the request ledger ({exc}). "
              f"Generation is unaffected.")
        return None


def requests_today(path=None):
    """Requests this pipeline has made in the current quota day."""
    entry = _read_ledger(path).get(quota_day()) or {}
    return int(entry.get("requests", 0)), int(entry.get("tokens", 0))


def clean_filename(title, max_len=70):
    """Slug for the post URL. Capped at a word boundary: topical headlines are
    longer than the old "AI Insights for August 2026" titles, and an uncapped
    slug produces URLs like the 95-character GPT-5 post already in the archive."""
    clean = re.sub('<.*?>', '', title)
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', clean)
    clean = re.sub(r'\s+', '-', clean.strip()).lower()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit('-', 1)[0]
    return clean.strip('-')


def clean_ai_content(content):
    content = re.sub(r'\[\d+\]', '', content)
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
    content = re.sub(r'\*(.*?)\*', r'\1', content)
    content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'•\s*[-–—]\s*', '', content)
    content = re.sub(r'[-–—]\s*•\s*', '', content)
    content = re.sub(r'\nBusinesses\s*\n', '\n', content)
    content = re.sub(r'^Businesses\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'##\s*', '', content)
    content = re.sub(r'###\s*', '', content)
    content = re.sub(r' +', ' ', content)
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

    meta_patterns = [
        r'(?:^|\n)\s*(?:Correction|Note|Self-check|Self check|Clarification|Update|Revision)'
        r'[:\s][^\n]{10,400}(?:\n[^\n]{0,300}){0,5}',
        r'[^.\n]*\bI (?:will|have|am going to) (?:remove|replace|delete|correct|fix|update)'
        r'[^.\n]*\.?',
        r'[^.\n]*\b(?:listed|appears?|appeared|duplicated?|repeated?)\s+in\s+both\s+sections[^.\n]*\.?',
        r'[^.\n]*and replace it with a (?:different|new|another)[^.\n]*\.?',
        r'(?:^|\n)\s*(?:MANDATORY )?SELF-CHECK[^\n]*(?:\n[^\n]{0,200}){0,10}',
        r'(?:^|\n)MANDATORY SELF-CHECK.*?(?=\n[A-Z]{4,}|\Z)',
        r'(?:^|\n)List every news event.*?(?=\n[A-Z]{4,}|\Z)',
        r'(?:^|\n)Then list every news event.*?(?=\n[A-Z]{4,}|\Z)',
        r'(?:^|\n)Compare the two lists.*?(?=\n[A-Z]{4,}|\Z)',
    ]
    for pattern in meta_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)

    content = re.sub(r' +', ' ', content)
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
    return content.strip()


# Labels the generator emits so the renderer can turn them into badges. They are
# scaffolding, not prose: "IMPORTANCE: High. HORIZON: Now. ATTENTION: Yes." is
# read as three chips at a glance, not as eleven words of sentence.
_SCAFFOLD_RE = re.compile(
    r'\b(?:IMPORTANCE|HORIZON|ATTENTION|PRIORITY|EFFORT|IMPACT)\s*[:\-]\s*'
    r'(?:High|Medium|Low|Now|Small|Large|Yes|Monitor|Ignore|\d{1,2}\s*Months?)\s*\.?',
    re.IGNORECASE,
)
_LABEL_RE = re.compile(r'\b(?:STRATEGIC READ|OWNER)\s*[:\-]\s*', re.IGNORECASE)


def estimate_reading_time(text):
    """Minutes at 200 wpm, counting only what a reader actually reads as prose.

    Without the strip below, the rating labels alone add roughly a minute to
    every issue — the badge would overstate the read by more than the closing
    question takes to read in full.
    """
    text = _SCAFFOLD_RE.sub(' ', text or '')
    text = _LABEL_RE.sub(' ', text)
    words = len(text.split())
    return max(3, round(words / 200))


def get_issue_number(reference_date=None):
    """
    reference_date should be the ISSUE date (first of the issue month), not
    raw wall-clock "now" — otherwise regenerating a post a few days after
    the calendar rolls over would silently bump the issue number even
    though it's still the same issue. Pass get_issue_labels()["issue_date"].
    Defaults to now() only for standalone/back-compat use.
    """
    start = datetime(2025, 9, 1)
    ref = reference_date or datetime.now()
    return max(1, (ref.year - start.year) * 12 + ref.month - start.month + 1)


def get_issue_labels(reference_date=None):
    """
    Single source of truth for "which month" labeling across the blog.

    THE PROBLEM THIS SOLVES:
    The generator runs on the LAST DAY of a month and reports on news from
    that same month (the "coverage" month). But almost every reader opens
    the post after the calendar has already flipped to the next month —
    so a page that prominently says "June" reads as stale the moment
    someone opens it in July, even though it's the freshest issue there is.

    THE RULE:
    - Anything that identifies WHICH ISSUE this is (page title, issue badge,
      SEO title/description, "latest issue" labels) uses the ISSUE month —
      the month people are actually reading it in.
    - Anything that narrates the ACTUAL NEWS (intro, Robert's Take, the
      closing summary) uses the COVERAGE month, and says so explicitly
      ("Covering June's developments") so nothing is misleading.

    REGENERATION NOTE:
    `reference_date` should be the COVERAGE date — the month the report is
    actually ABOUT — not necessarily today. When a June 30 report gets
    regenerated on July 2nd because the content was bad, pass June 30 (or
    any date in June) back in here so the labels, issue number, and Gemini's
    search grounding all stay locked to June instead of drifting to July.
    Callers that don't pass anything get today's date, which is correct for
    a brand-new monthly run.

    To change how far ahead the issue label looks, or to revert to
    coverage-month labeling everywhere, this is the only function that
    needs to change — every caller reads from the dict it returns.
    """
    ref = reference_date or datetime.now()
    coverage_month_year = ref.strftime("%B %Y")
    coverage_month_name = ref.strftime("%B")

    if ref.month == 12:
        issue_ref = ref.replace(year=ref.year + 1, month=1, day=1)
    else:
        issue_ref = ref.replace(month=ref.month + 1, day=1)
    issue_month_year = issue_ref.strftime("%B %Y")

    return {
        "coverage_month_year": coverage_month_year,   # e.g. "June 2026" — the news this issue covers
        "coverage_month_name": coverage_month_name,   # e.g. "June"
        "issue_month_year":    issue_month_year,       # e.g. "July 2026"  — the label readers see
        "issue_date":          issue_ref,               # datetime for get_issue_number(), so regeneration doesn't bump it
        "issue_badge_text":    f"{issue_month_year} \u2014 Covering {coverage_month_name}",
    }


def build_search_url(publication, headline):
    if not publication and not headline:
        return None
    query_parts = []
    if publication:
        query_parts.append(f'"{publication.strip()}"')
    if headline:
        query_parts.append(f'"{headline.strip()}"')
    query = " ".join(query_parts)
    return "https://www.google.com/search?q=" + requests.utils.quote(query)


def is_episode_or_newsletter_item(body, company):
    if not body:
        return False
    stripped = body.strip()
    if re.match(r'^\d+\s*[:\-–—]', stripped):
        return True
    if re.match(r'^(?:Episode|Ep\.?|Issue|Vol\.?|#)\s*\d+', stripped, re.IGNORECASE):
        return True
    if not company and len(stripped) < 80 and re.match(r'^[A-Z0-9#]', stripped):
        words = stripped.split()
        if len(words) <= 10 and not stripped.endswith('.'):
            return True
    return False


# Platforms that host anyone's writing. The prompt already bans them, but a
# prompt rule is not enforcement: a real issue cited "ML Kenya Blogs" and
# "TechCraft Chronicles - Medium" for its two most specific, most checkable
# claims. Sourcing is the thing a sceptical reader checks first.
#
# Deliberately NOT a bare "blog": official company blogs are primary sources and
# explicitly allowed — "AWS News Blog", "Google Blog" and "OpenAI Blog" must all
# survive this. Only third-party platforms and the plural "Blogs" (which no
# first-party newsroom uses) are matched.
_LOW_QUALITY_SOURCE_MARKERS = (
    "medium", "substack", "blogspot", "wordpress", "blogs",
    "newsletter", "podcast", "episode",
)


# Outlets usually cited by their initials. Matched EXACTLY and kept out of
# _KNOWN_PUBLICATIONS on purpose: that set is matched as a substring, so a
# three-letter key there would fire inside unrelated names. "TNW" is The Next
# Web, and a real July story was dropped because only the long form was listed.
_KNOWN_ABBREVIATIONS = {
    "tnw", "wsj", "nyt", "ft", "ap", "afp", "npr", "wapo", "bnn", "cp",
    "mit tech review", "hbr", "cbc ca", "ctv news",
}


# Compiled on first use, not at import: _KNOWN_PUBLICATIONS is defined further
# down the file. Longest key first so the most specific name wins. Word
# boundaries are the whole point — see is_recognised_publication.
_PUBLICATION_RE = None


def _publication_re():
    global _PUBLICATION_RE
    if _PUBLICATION_RE is None:
        _PUBLICATION_RE = re.compile(
            r'\b(?:' + '|'.join(re.escape(k) for k in
                                sorted(_KNOWN_PUBLICATIONS, key=len, reverse=True)) + r')\b'
        )
    return _PUBLICATION_RE


def is_recognised_publication(source_name):
    """True when the citation names an outlet on the known list."""
    if not source_name:
        return False
    name = re.sub(r'[^a-z0-9 ]+', ' ', source_name.lower())
    name = re.sub(r'\s+', ' ', name).strip()
    if name in _KNOWN_ABBREVIATIONS:
        return True
    # Word-boundary, not raw substring. "intel" (the chipmaker) was matching
    # inside "futurum intelligence", so ANY source named "... Intelligence" was
    # silently accepted as Intel's newsroom — and analyst-style names ending in
    # "Intelligence" are exactly the shape this allowlist exists to catch.
    # Boundaries keep "CBC News" matching "cbc" while "intelligence" no longer
    # matches "intel". Same hazard the abbreviations set was created for; that
    # note said "three-letter", and "intel" is five.
    if _publication_re().search(name):
        return True
    # A source name shorter than the key it belongs to ("globe and mail" for
    # "the globe and mail"). Kept, but require enough of a name to be
    # meaningful, so a two-letter fragment cannot claim a long publication.
    return len(name) >= 6 and any(name in k for k in _KNOWN_PUBLICATIONS)


# Press-release distributors. Deliberately NOT in _KNOWN_PUBLICATIONS: a wire
# release is the company's own announcement, carried verbatim for a fee, so it
# is first-party evidence rather than independent reporting. Putting these on
# the publication list would let a month of pure corporate PR report itself as
# independently sourced, which is the failure the allowlist exists to prevent.
#
# Distinct from wire *journalism* — Reuters, Bloomberg and Canadian Press
# employ reporters and stay on the publication list.
_NEWSWIRE_NAMES = {
    "cnw", "cnw group", "canada newswire", "newswire", "globenewswire",
    "globe newswire", "business wire", "businesswire", "pr newswire",
    "prnewswire", "newsfile", "newsfile corp", "accesswire", "marketwired",
    "ein presswire", "prweb", "the newswire",
}


# Product documentation and support surfaces. These are NOT announcements: a
# help-centre article or a docs page is evergreen and undated, so it is no
# evidence an event happened in the month being reported. A run cited a
# ChatGPT Work launch to "OpenAI Help Center" and a platform change to
# "Microsoft Learn" — both first-party, both accepted, neither a report of
# anything happening.
#
# Deliberately specific rather than matching bare "learn" or "support", which
# would fire inside ordinary publication names.
_DOC_SURFACES = (
    "help center", "help centre", "helpcenter", "support center",
    "support centre", "knowledge base", "documentation", "docs",
    "developer guide", "dev guide", "api reference", "release notes",
    "changelog", "microsoft learn", "faq",
)


def is_documentation_source(source_name):
    """True when the citation is a docs, help-centre or reference page.

    Callers drop these from reported developments: the company blog post
    announcing the thing is the source, not the manual describing it.
    """
    if not source_name:
        return False
    name = re.sub(r'[^a-z0-9 ]+', ' ', source_name.lower())
    name = re.sub(r'\s+', ' ', name).strip()
    return any(re.search(r'\b' + re.escape(k) + r'\b', name) for k in _DOC_SURFACES)


# Corporate newsrooms. These stay in _KNOWN_PUBLICATIONS so they remain
# ACCEPTABLE sources — the prompt allows an official company blog, and one
# company's newsroom frequently carries a rival's or partner's announcement.
# But they must never be counted INDEPENDENT: Microsoft Source reporting a
# Microsoft partnership has a stake in the story. A run scored "2 independent"
# on Hugging Face and Microsoft Source, which suppressed the ALL FIRST-PARTY
# note on an issue where every development was in fact first-party.
_FIRST_PARTY_NEWSROOMS = {
    "aws", "amazon", "google", "openai", "anthropic", "microsoft", "nvidia",
    "meta", "ibm", "intel", "apple", "oracle", "salesforce", "shopify",
    "cohere", "mistral", "hugging face", "databricks", "snowflake",
}


def is_first_party_newsroom(source_name):
    """True when the citation is a company's own newsroom or blog.

    Acceptable as a source; never independent. Callers score it first-party
    whoever the story is about.
    """
    if not source_name:
        return False
    name = re.sub(r'[^a-z0-9 ]+', ' ', source_name.lower())
    name = re.sub(r'\s+', ' ', name).strip()
    return any(k in name or name in k for k in _FIRST_PARTY_NEWSROOMS)


def is_newswire(source_name):
    """True when the citation is a press-release wire.

    Acceptable as a source — CNW and GlobeNewswire are how Canadian companies
    actually issue announcements, and dropping them discards real primary
    material — but callers must count it as first-party, never independent.
    """
    if not source_name:
        return False
    name = re.sub(r'[^a-z0-9 ]+', ' ', source_name.lower())
    name = re.sub(r'\s+', ' ', name).strip()
    if name in _NEWSWIRE_NAMES:
        return True
    # Substring only for unambiguous tokens. "cnw" stays exact-match: three
    # letters would collide with ordinary words.
    return any(t in name for t in ("newswire", "presswire", "press wire",
                                   "business wire", "accesswire"))


# Words that mark a name as a publication or an organisation rather than a
# person. Used only to decide whether a two-or-three-word citation is somebody's
# byline — "Mark McNeilly" carried a real story in one issue, and a byline is
# not a source.
_PUBLICATION_WORDS = {
    "news", "times", "post", "journal", "review", "wire", "daily", "weekly",
    "monitor", "report", "reports", "insider", "watch", "press", "media",
    "magazine", "digest", "gazette", "herald", "tribune", "chronicle",
    "standard", "observer", "register", "bulletin", "today", "now", "hub",
    "street", "verge", "tech", "technica", "ai", "labs", "lab", "institute",
    "research", "group", "inc", "ltd", "llc", "corp", "co", "company",
    "canada", "canadian", "global", "international", "business", "financial",
    "economic", "science", "technology", "digital", "network", "channel",
    "radio", "broadcasting", "publishing", "analytics", "insights", "intel",
    "university", "school", "college", "foundation", "council", "association",
    "agency", "bureau", "office", "ministry", "department", "government",
}


def _looks_like_a_person(name):
    """Two or three capitalised words with nothing publication-like in them.

    Conservative on purpose: this only ever runs on names that already failed
    the known-publication check, and a legitimate outlet missing from that list
    would be dropped by a false positive here. Requiring every word to be a
    plain capitalised word with no publication noun keeps "Tech Monitor" and
    "Signal49 Research" out of it.
    """
    words = name.strip().split()
    if not 2 <= len(words) <= 3:
        return False
    if any(w.lower().strip(".,") in _PUBLICATION_WORDS for w in words):
        return False
    # Every word must be Title Case with at least one lowercase letter. An
    # all-caps word is an acronym, and organisations are what carry those:
    # "NTT DATA" and "IBM Research" are sources, "Mark McNeilly" is a byline.
    return all(
        re.fullmatch(r"[A-Z][A-Za-z'’.\-]*", w) and any(c.islower() for c in w)
        for w in words
    )


def is_low_quality_source(source_name):
    """True when a citation is not a publication at all.

    Three shapes, all of which reached a real issue:
      - self-publishing platforms (Medium, Substack, "... Blogs")
      - a bare domain, which names a site or a product rather than a newsroom
        ("BenchLM.ai" was the sole source for three of five stories in one run)
      - a person's name, which is a byline ("Mark McNeilly")

    Callers drop the item — the same treatment episode and newsletter items
    already get, and what the prompt says should happen to all of them.
    """
    if not source_name:
        return False
    raw = source_name.strip()

    # A domain that names a known outlet IS that outlet. This test used to run
    # before any publication check, so "Reuters.com" and "BetaKit.com" were
    # dropped as bare domains. Strip the suffix and ask first. ".ca" is in the
    # list now too — its absence let "Fintech.ca" through on a Canadian blog,
    # which is the single likeliest bare domain this publication will meet.
    _domain = r'\.(?:ai|com|io|co|net|org|dev|app|xyz|ca)\b'
    if re.search(_domain, raw, re.IGNORECASE):
        stem = re.sub(_domain + r'.*$', '', raw, flags=re.IGNORECASE)
        # Domains carry no spaces, so split camelCase before matching too:
        # "TheGlobeAndMail" only reads as the Globe and Mail once it does.
        spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', stem)
        return not (is_recognised_publication(stem)
                    or is_recognised_publication(spaced))

    name = re.sub(r'[^a-z0-9 ]+', ' ', raw.lower())
    if any(f' {marker} ' in f' {name} ' for marker in _LOW_QUALITY_SOURCE_MARKERS):
        return True

    return _looks_like_a_person(raw) and not is_recognised_publication(raw)


# Openers offered to the model in earlier versions of the prompt. Three issues
# in a row opened a Desk paragraph with one of them, which is how a signature
# voice turns into a house style nobody chose. Defined once so the prompt can
# ban them by name and the renderer can check whether the ban held.
# ---------------------------------------------------------------------------
# Household-name Canadian brands, for the Canadian Spotlight.
#
# The section used to fill up with AI vendors (Cohere, Ada, Coveo) and federal
# programs. Both are credible, neither is a name a reader meets in daily life,
# so the one section meant to feel local read like industry trade press. What
# resonates is a bank, telecom or retailer the reader already banks with, pays
# a bill to, or shops at, explaining how it actually uses AI.
#
# Defined once and used twice — interpolated into the Spotlight spec so the
# model knows the universe, and matched by is_household_canadian_brand() so the
# renderer can order those items first. Same single-source pattern as
# STOCK_VOICE_PHRASES; if the two drifted, the prompt would ask for one thing
# and the ordering would reward another.
#
# Ordering and reporting only. Nothing is ever dropped for failing this test,
# which is why a loose match here is cheap.
# ---------------------------------------------------------------------------
CANADIAN_HOUSEHOLD_BRANDS = (
    # Banks, insurers, money
    "RBC", "Royal Bank of Canada", "TD Bank", "Toronto-Dominion", "Scotiabank",
    "Bank of Nova Scotia", "BMO", "Bank of Montreal", "CIBC", "National Bank",
    "Desjardins", "Sun Life", "Manulife", "Intact", "Canada Life",
    "Wealthsimple", "Tangerine", "EQ Bank",
    # Telecom and media
    "Bell Canada", "BCE", "Rogers", "Telus", "Videotron", "Vidéotron",
    "Koodo", "Fido", "Freedom Mobile",
    # Retail, grocery, consumer
    "Loblaw", "Loblaws", "Shoppers Drug Mart", "Canadian Tire", "Sobeys",
    "Couche-Tard", "Circle K", "Lululemon", "Roots Canada", "Indigo",
    "Dollarama", "Giant Tiger", "London Drugs", "Home Hardware", "Metro Inc",
    # Travel, transport, energy, food, industry
    "Air Canada", "WestJet", "Porter Airlines", "VIA Rail", "Canada Post",
    "CN Rail", "Canadian National Railway", "Canadian Pacific", "Enbridge",
    "Suncor", "Hydro-Québec", "Hydro-Quebec", "Tim Hortons", "Saputo",
    "McCain", "Maple Leaf Foods", "Bombardier", "CAE", "Magna",
    # Canadian tech with genuine public recognition
    "Shopify", "Lightspeed", "OpenText",
)

# Word-boundary matched: "Bell Canada" must not fire inside "Campbell", and the
# short forms are spelled out for the same reason.
_BRAND_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(b) for b in
                         sorted(CANADIAN_HOUSEHOLD_BRANDS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)


def household_canadian_brands(text):
    """Which household-name Canadian brands this text names, in order."""
    if not text:
        return []
    seen, out = set(), []
    for m in _BRAND_RE.finditer(text):
        key = m.group(0).lower()
        if key not in seen:
            seen.add(key)
            out.append(m.group(0))
    return out


def is_household_canadian_brand(text):
    """True when the text names a brand an ordinary Canadian reader knows."""
    return bool(household_canadian_brands(text))


STOCK_VOICE_PHRASES = (
    "In my experience",
    "What I've seen inside large enterprises",
    "One lesson I've learned",
    "The governance challenge usually isn't technology",
    "The hardest part is organizational change",
)


def uses_stock_phrase(text):
    """Stock openers present in `text`.

    Contractions are expanded on both sides before matching: the model writes
    "What I have seen inside large enterprises" as readily as "What I've seen",
    and the phrase is equally stock either way. Matching the literal string
    would let a one-character rewording through.
    """
    if not text:
        return []

    def norm(s):
        s = re.sub(r'\s+', ' ', s.lower().replace('’', "'"))
        s = re.sub(r"\bi've\b", "i have", s)
        s = re.sub(r"\b(\w+)n't\b", r"\1 not", s)
        s = re.sub(r"\bisn not\b", "is not", s)      # "isn't" -> "isn not"
        s = re.sub(r"\bdoesn not\b", "does not", s)
        s = re.sub(r"\bwon not\b", "will not", s)
        return s

    body = norm(text)
    return [p for p in STOCK_VOICE_PHRASES if norm(p) in body]


# Publications a reader could look up. Not a whitelist for dropping — plenty of
# legitimate outlets are missing — but anything outside it, that is also not the
# subject's own newsroom and not a government body, is worth a human glance.
# A run cited "Signal49 Research" and "CanadianAI"; neither is a publication,
# and no blocklist pattern could ever have caught them.
_KNOWN_PUBLICATIONS = {
    # Canadian
    "globe and mail", "financial post", "national post", "toronto star", "cbc",
    "ctv", "global news", "bnn bloomberg", "the logic", "betakit",
    "canadian press", "la presse", "le devoir", "the hub", "cbc news",
    "canadian business journal", "it world canada", "montreal gazette",
    # International news
    "reuters", "bloomberg", "associated press", "wall street journal",
    "new york times", "financial times", "the economist", "wired", "the verge",
    "techcrunch", "ars technica", "mit technology review", "cnbc", "forbes",
    "business insider", "axios", "the information", "fortune", "cbs news",
    "nbc news", "abc news", "bbc", "the guardian", "thestreet", "venturebeat",
    "zdnet", "engadget", "semafor", "politico", "time", "the atlantic",
    # Research, analyst and statistical bodies
    "mckinsey", "deloitte", "kpmg", "pwc", "ernst young", "gartner",
    "forrester", "idc", "accenture", "boston consulting group", "bcg",
    "statistics canada", "conference board of canada", "bdc", "ised",
    "vector institute", "mila", "amii", "oecd", "world economic forum",
    "pew research", "stanford hai", "borderless ai", "crunchbase", "rsm",
    "alleywatch",
    # Canadian trade and regional press
    "the logic", "it business", "mobilesyrup", "investment executive",
    "advisor", "canadian lawyer", "communitech", "techvibes", "cartt",
    "financial times canada", "canadian underwriter", "benefits canada",
    # More international news and trade press
    "the register", "protocol", "rest of world", "nikkei", "cnn", "sky news",
    "le monde", "handelsblatt", "der spiegel", "the times", "sifted",
    "tech monitor", "computerworld", "infoworld", "network world", "cio",
    "silicon angle", "the next web", "gizmodo", "techradar", "digital trends",
    # Regulators, central banks and standards bodies
    "osfi", "bank of canada", "crtc", "privacy commissioner", "competition bureau",
    "cipo", "nist", "european commission", "iso", "ieee", "cra",
    "innovation science and economic development", "public safety canada",
    "treasury board", "canada revenue agency", "health canada",
    # First-party newsrooms. The prompt allows official company blogs as primary
    # sources, and they are frequently the source for a rival's announcement —
    # "AWS News Blog" carrying an Anthropic release, say — so they cannot be
    # cleared by the subject-matches-source check alone.
    "aws", "amazon", "google", "openai", "anthropic", "microsoft", "nvidia",
    "meta", "ibm", "intel", "apple", "oracle", "salesforce", "shopify",
    "cohere", "mistral", "hugging face", "databricks", "snowflake",
}




def is_acceptable_source(source_name, subject=""):
    """Whether a citation may carry a reported development.

    Four ways to qualify, and nothing else:
      - a publication on the known list
      - a government or regulatory body
      - the subject's own newsroom (an official company announcement)
      - a press-release wire (the same announcement, distributed)

    This is an ALLOWLIST, and callers drop what fails it. That is a deliberate
    reversal: for five issues the check flagged unrecognised sources and let
    them publish, and the model kept reaching for aggregators — "ML Kenya
    Blogs", "Signal49 Research", "BenchLM.ai", "Analytics Vidhya", "ThursdAI".
    The names are arbitrary, so no blocklist can anticipate them; only naming
    what IS acceptable closes the gap.

    The cost is real and intended: a month with little primary reporting now
    produces a thin issue that has to be regenerated, rather than a full one
    resting on sources nobody can check.
    """
    if not source_name:
        return False
    # Before everything else: a docs or help-centre page passes every test
    # below (it carries the company's name) while being no evidence that
    # anything happened. Reject it and make the model find the announcement.
    if is_documentation_source(source_name):
        return False
    if is_recognised_publication(source_name) or is_government_entity(source_name):
        return True
    # A wire release is the subject's own announcement under a distributor's
    # name, so the subject-matches-source check below can never clear it.
    # Acceptable, but callers must score it first-party, not independent.
    if is_newswire(source_name):
        return True
    # First-party: the citation names the organisation the item is about.
    subject = (subject or "").strip().lower()
    name = source_name.strip().lower()
    if not subject:
        return False
    return name in subject or subject.split()[0] in name


def is_government_entity(company):
    if not company:
        return False
    c = company.lower()
    return any([
        "government of" in c,
        "prime minister" in c,
        "minister of" in c,
        "ministry of" in c,
        "parliament" in c,
        "senate of" in c,
        "federal " in c,
        "provincial " in c,
        "municipal " in c,
        "city of " in c,
        "province of " in c,
        "legislature" in c,
        "treasury board" in c,
        "privy council" in c,
        "innovation, science" in c,
        "prairies economic" in c,
        "natural resources canada" in c,
        "health canada" in c,
        "transport canada" in c,
        "public safety canada" in c,
        "national research council" in c,
        "social sciences and humanities" in c,
        "nserc" in c,
        "sshrc" in c,
        "g7 " in c,
        "g20 " in c,
        "g8 " in c,
        c in {"canada.ca", "gc.ca"},
        # Regulators and agencies by their FULL legal names. Several were
        # recognised only by their abbreviation, so "OSFI" passed while
        # "Office of the Superintendent of Financial Institutions" was flagged
        # unrecognised — and would have been DROPPED from a development. That
        # is the name a regulator publishes under, and the Spotlight spec now
        # tells the model to cite these bodies directly, so the classifier has
        # to know them or the rule produces warnings on correct behaviour.
        "office of the" in c,
        "superintendent of" in c,
        "privacy commissioner" in c,
        "information commissioner" in c,
        "auditor general" in c,
        "ombudsman" in c,
        "competition bureau" in c,
        "bank of canada" in c,
        "revenue agency" in c,
        "statistics canada" in c,
        "statistique canada" in c,
        "radio-television" in c,
        "radio television" in c,
        "securities commission" in c,
        "regulatory authority" in c,
        # Quebec and other French-language bodies. "commission d'" covers the
        # Commission d'acces a l'information, named in the Spotlight spec.
        "commission d'" in c,
        "commission d " in c,
        "commission des " in c,
        "commission de l" in c,
        "regie " in c,
        "régie " in c,
    ])


def is_meta_commentary(text):
    triggers = [
        r'\blisted in both\b',
        r'\bwill remove\b',
        r'\bhave removed\b',
        r'\breplace it with\b',
        r'\bself.?check\b',
        r'^correction[:\s]',
        r'^note[:\s]',
        r'\bduplicate\b.{0,50}\bsection\b',
        r'\bappears? in both\b',
        r'\bremov(?:e|ed|ing) (?:it|this|the duplicate)\b',
    ]
    for t in triggers:
        if re.search(t, text, re.IGNORECASE):
            return True
    return False
