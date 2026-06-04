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


def get_issue_number():
    start = datetime(2025, 9, 1)
    now = datetime.now()
    return max(1, (now.year - start.year) * 12 + now.month - start.month + 1)


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
