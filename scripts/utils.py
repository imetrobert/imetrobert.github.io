"""
utils.py
Shared helper functions used across the blog generation pipeline.
"""

import re
import requests
from datetime import datetime


def clean_filename(title):
    clean = re.sub('<.*?>', '', title)
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', clean)
    clean = re.sub(r'\s+', '-', clean.strip())
    return clean.lower()


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


def estimate_reading_time(text):
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
