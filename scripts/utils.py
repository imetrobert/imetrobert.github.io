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


def is_recognised_publication(source_name):
    """True when the citation names an outlet on the known list."""
    if not source_name:
        return False
    name = re.sub(r'[^a-z0-9 ]+', ' ', source_name.lower())
    name = re.sub(r'\s+', ' ', name).strip()
    return any(k in name or name in k for k in _KNOWN_PUBLICATIONS)


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

    if re.search(r'\.(ai|com|io|co|net|org|dev|app|xyz)\b', raw, re.IGNORECASE):
        return True

    name = re.sub(r'[^a-z0-9 ]+', ' ', raw.lower())
    if any(f' {marker} ' in f' {name} ' for marker in _LOW_QUALITY_SOURCE_MARKERS):
        return True

    return _looks_like_a_person(raw) and not is_recognised_publication(raw)


# Openers offered to the model in earlier versions of the prompt. Three issues
# in a row opened a Desk paragraph with one of them, which is how a signature
# voice turns into a house style nobody chose. Defined once so the prompt can
# ban them by name and the renderer can check whether the ban held.
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
    "pew research", "stanford hai", "borderless ai",
    # First-party newsrooms. The prompt allows official company blogs as primary
    # sources, and they are frequently the source for a rival's announcement —
    # "AWS News Blog" carrying an Anthropic release, say — so they cannot be
    # cleared by the subject-matches-source check alone.
    "aws", "amazon", "google", "openai", "anthropic", "microsoft", "nvidia",
    "meta", "ibm", "intel", "apple", "oracle", "salesforce", "shopify",
    "cohere", "mistral", "hugging face", "databricks", "snowflake",
}




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
