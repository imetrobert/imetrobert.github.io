"""
parser.py
Parses Gemini's plain-text output into structured data for HTML rendering.
"""

import re
from datetime import datetime
from utils import (
    BRAND,
    build_search_url,
    is_episode_or_newsletter_item,
    is_government_entity,
    is_meta_commentary,
)


SECTION_HEADERS = [
    "HEADLINE",
    "INTRODUCTION",
    "EXECUTIVE SUMMARY",
    "KEY AI DEVELOPMENTS",
    "CANADIAN SPOTLIGHT",
    "FROM ROBERTS DESK",
    "WHAT THIS MEANS FOR CANADIAN BUSINESS",
    "STRATEGIC ACTIONS FOR THIS MONTH",
    "ADOPTION SNAPSHOT",
    "AI MYTH OF THE MONTH",
    "LOOKING AHEAD: THREE PREDICTIONS",
    "ONE QUESTION FOR YOUR LEADERSHIP TEAM",
]

# Spellings the model actually produces, mapped to the canonical header.
# "FROM ROBERTS DESK" is asked for without an apostrophe because the header has
# to survive a literal string match, but the model types the possessive anyway
# often enough to be worth accepting. "ROBERTS TAKE" is the pre-rename header:
# keeping it here means an archived draft, or a regeneration that answers in the
# old format, still lands in the right section instead of vanishing.
SECTION_ALIASES = {
    "FROM ROBERTS DESK": [
        "FROM ROBERT'S DESK", "FROM ROBERT’S DESK", "ROBERT'S DESK",
        "ROBERTS TAKE", "ROBERT'S TAKE", "ROBERT’S TAKE",
    ],
    "LOOKING AHEAD: THREE PREDICTIONS": [
        "LOOKING AHEAD - THREE PREDICTIONS",
        "LOOKING AHEAD — THREE PREDICTIONS",
        "LOOKING AHEAD",
    ],
    "ONE QUESTION FOR YOUR LEADERSHIP TEAM": [
        "ONE QUESTION FOR THE LEADERSHIP TEAM",
        "ONE QUESTION EVERY EXECUTIVE SHOULD ASK THIS MONTH",
        "ONE QUESTION",
    ],
    "AI MYTH OF THE MONTH": ["MYTH OF THE MONTH"],
}


def _header_candidates(header):
    """Canonical spelling first, then known aliases, then the loose plural
    variants the original implementation tolerated."""
    out = [header]
    out.extend(SECTION_ALIASES.get(header, []))
    out.extend([header + "S", header.replace(" ", "S ")])
    seen, ordered = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _find_header(content_upper, candidate):
    """Locate a header, requiring it to start its own line.

    Anchoring matters: several headers are ordinary English ("LOOKING AHEAD",
    "EXECUTIVE SUMMARY"). An unanchored substring search finds the first
    occurrence, so one such phrase used mid-paragraph would silently cut the
    document at the wrong place and swallow every section after it.
    Returns (index, matched_length) or (None, 0).
    """
    pattern = re.compile(
        r'^[ \t]*' + re.escape(candidate) + r'[ \t]*:?[ \t]*(?=\n|$)',
        re.MULTILINE,
    )
    m = pattern.search(content_upper)
    if m:
        return m.start(), len(m.group(0))
    return None, 0


def parse_sections(content):
    sections = {h: "" for h in SECTION_HEADERS}
    positions = {}
    lengths = {}
    content_upper = content.upper()

    for header in SECTION_HEADERS:
        for candidate in _header_candidates(header):
            idx, matched_len = _find_header(content_upper, candidate)
            if idx is not None:
                positions[header] = idx
                lengths[header] = matched_len
                break

    # Fall back to the old unanchored search only for headers still missing —
    # a model that runs a header into the same line as its content should not
    # cost us the whole section.
    for header in SECTION_HEADERS:
        if header in positions:
            continue
        for candidate in _header_candidates(header):
            idx = content_upper.find(candidate)
            if idx != -1:
                positions[header] = idx
                lengths[header] = len(candidate)
                break

    if not positions:
        sections["INTRODUCTION"] = content
        return sections

    sorted_headers = sorted(positions.keys(), key=lambda h: positions[h])
    for i, header in enumerate(sorted_headers):
        start = positions[header] + lengths[header]
        while start < len(content) and content[start] in ':\n ':
            start += 1
        end = positions[sorted_headers[i + 1]] if i + 1 < len(sorted_headers) else len(content)
        raw = content[start:end].strip()
        raw = re.sub(r'^Businesses\s*\n?', '', raw).strip()
        sections[header] = raw

    return sections


def parse_list_items(text, min_length=40):
    items = []

    numbered = re.findall(r'^\d+\.\s+(.+?)(?=\n\d+\.|\Z)', text, re.MULTILINE | re.DOTALL)
    if numbered:
        for item in numbered:
            cleaned = ' '.join(item.strip().split())
            if len(cleaned) >= min_length:
                items.append(cleaned)
        if items:
            return items

    line_items = []
    for line in text.split('\n'):
        line = line.strip()
        line = re.sub(r'^[-•*]\s*', '', line)
        if len(line) >= min_length:
            line_items.append(line)

    if len(line_items) > 1:
        return line_items

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentence_items = [s.strip() for s in sentences if len(s.strip()) >= min_length]
    if len(sentence_items) > 1:
        return sentence_items

    return line_items if line_items else ([text.strip()] if len(text.strip()) >= min_length else [])


def _extract_source_from_text(text):
    source_name = ""
    source_url = ""

    m = re.search(
        r'(?:^|[.\n])\s*Source[:\s]+([^|\r\n]{3,80}?)\s*\|\s*([^\r\n]{5,200})',
        text, re.IGNORECASE | re.MULTILINE
    )
    if not m:
        m = re.search(
            r'(?:^|[.\n])\s*Source[:\s]+([^\u2014\u2013\r\n]{3,60})[\u2014\u2013]+([^\r\n]{5,200})',
            text, re.IGNORECASE | re.MULTILINE
        )
    if not m:
        m = re.search(
            r'(?:^|[.\n])\s*Source[:\s]+([A-Za-z][^\d\r\n,]{2,50}),\s*(\d{4}[^\r\n]{0,30})',
            text, re.IGNORECASE | re.MULTILINE
        )

    if m:
        source_name = m.group(1).strip().rstrip('.,')
        source_headline = m.group(2).strip().rstrip('.,')
        source_headline = re.sub(r'https?://\S+', '', source_headline).strip().rstrip('.,')
        source_url = build_search_url(source_name, source_headline) if len(source_headline) > 6 else None
        source_kw = text.upper().rfind('SOURCE', 0, m.end())
        cleaned = text[:source_kw].strip().rstrip('.') if source_kw > 0 else text[:m.start()].strip()
        return source_name, source_url, cleaned

    # None of the expected shapes matched, which means the model wrote a Source
    # line without the "Publication | Headline" format. Left alone the raw
    # "Source: ..." string ships as body copy — and worse, flows into the FAQ
    # answer and the FAQPage schema, which answer engines quote verbatim.
    # Salvage it as a search link and take it out of the prose either way.
    trailer = re.search(
        r'(?:^|[.\n])\s*Sources?\s*[:–—-]\s*(\S.*)$',
        text, re.IGNORECASE | re.DOTALL
    )
    if trailer:
        cited = ' '.join(trailer.group(1).split()).strip().rstrip('.,;')
        cited = re.sub(r'https?://\S+', '', cited).strip(' |.,;')
        cut_at = text.upper().rfind('SOURCE', 0, trailer.end())
        body = text[:cut_at].strip().rstrip('.,;').strip() if cut_at > 0 else text.strip()
        if body:
            url = build_search_url("", cited) if len(cited) > 6 else None
            # No publication name to show, so the chip falls back to "Source".
            return "", url, body

    return "", "", text.strip()


# The labels the generator appends to a major development, in the order they
# appear. Everything from the first one onward is metadata, not body copy.
_DEV_META_LABEL = r'(?:STRATEGIC\s+READ|IMPORTANCE|HORIZON|ATTENTION)'
_ACTION_META_LABEL = r'(?:OWNER|PRIORITY|EFFORT|IMPACT)'


def _titlecase_rating(value):
    """'3 months' -> '3 Months', 'high' -> 'High'. The model is asked for exact
    casing and mostly complies, but a rating badge that reads 'high' next to one
    that reads 'High' looks like a bug to a reader."""
    if not value:
        return ""
    value = re.sub(r'\s+', ' ', value.strip())
    return ' '.join(w if w.isdigit() else w.capitalize() for w in value.split())


def _extract_dev_ratings(text):
    """Split a development body from the executive ratings appended to it.

    Only the major stories carry these, so absence is normal and returns the
    body untouched with empty ratings — that is what makes a development render
    as a compact log entry rather than a rated card.
    """
    ratings = {"strategic_read": "", "importance": "", "horizon": "", "attention": ""}
    if not text:
        return text, ratings

    read = re.search(
        r'\bSTRATEGIC\s+READ\s*[:\-–—]\s*(.+?)'
        r'(?=\s*\b(?:IMPORTANCE|HORIZON|ATTENTION)\s*[:\-–—]|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    if read:
        body = ' '.join(read.group(1).split()).strip(' ;,')
        if body and not body.endswith(('.', '!', '?')):
            body += '.'
        ratings["strategic_read"] = body

    imp = re.search(r'\bIMPORTANCE\s*[:\-–—]\s*(High|Medium|Low)\b', text, re.IGNORECASE)
    hor = re.search(
        r'\bHORIZON\s*[:\-–—]\s*(Now|3\s*Months?|6\s*Months?|12\s*Months?)\b',
        text, re.IGNORECASE
    )
    att = re.search(r'\bATTENTION\s*[:\-–—]\s*(Yes|Monitor|Ignore)\b', text, re.IGNORECASE)

    ratings["importance"] = _titlecase_rating(imp.group(1)) if imp else ""
    ratings["horizon"]    = _titlecase_rating(hor.group(1)) if hor else ""
    ratings["attention"]  = _titlecase_rating(att.group(1)) if att else ""

    cut = re.search(r'\s*\b' + _DEV_META_LABEL + r'\s*[:\-–—]', text, re.IGNORECASE)
    body = text[:cut.start()].strip() if cut else text.strip()
    # Strip separators but never the terminal full stop: rstrip it and the
    # "does it already end in punctuation" test below can only ever see the
    # stripped string, so the sentence ships without its period.
    body = body.rstrip(' ;,')
    if body and not body.endswith(('.', '!', '?')):
        body += '.'
    return body, ratings


_MONTH_NUMBERS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _resolve_item_date(date_str, coverage_date):
    """Turn "August 12" into a real date, using the coverage month for the year.

    Items carry no year — the generator is told to report one month, so the
    year is implied. Candidate years are tried on both sides of the coverage
    date and the closest one wins, which is what keeps a December item in a
    January issue from landing eleven months out.

    Returns None when the string is not a date or the date does not exist
    (February 30), because an unparseable date is not evidence of anything.
    """
    if not date_str or not coverage_date:
        return None
    m = re.match(r'\s*([A-Za-z]{3,9})\.?\s+(\d{1,2})', date_str)
    if not m:
        return None
    month = _MONTH_NUMBERS.get(m.group(1)[:3].lower())
    if not month:
        return None
    day = int(m.group(2))

    best = None
    for year in (coverage_date.year - 1, coverage_date.year, coverage_date.year + 1):
        try:
            candidate = datetime(year, month, day)
        except ValueError:
            continue
        if best is None or abs((candidate - coverage_date).days) < abs((best - coverage_date).days):
            best = candidate
    return best


def _drop_future_dated(items, coverage_date, today=None):
    """Remove developments dated after today.

    The scheduled run fires on the last day of the month, so every item it asks
    for has already happened. A manual force_run, or a regeneration with no
    coverage_month, asks for the CURRENT month while it is still in progress —
    and the prompt demands five or six dated items from it. When the real ones
    run out, a plausible-looking forward-dated item is exactly the gap-filling
    to expect, and nothing downstream would catch it.

    Skipped entirely when coverage_date is unknown: without a year there is no
    way to resolve "August 12", and guessing would be worse than not checking.
    """
    if not coverage_date:
        return items
    today = (today or datetime.now()).date()

    kept = []
    for item in items:
        resolved = _resolve_item_date(item.get('date', ''), coverage_date)
        if resolved and resolved.date() > today:
            print(f"  future-date: dropping '{item.get('date')}' "
                  f"({item.get('company') or item.get('body', '')[:40]}) — after {today}")
            continue
        kept.append(item)

    dropped = len(items) - len(kept)
    if dropped:
        # Said plainly, because the visible symptom is a thin issue and the
        # cause is three lines further up the log. A reviewer who does not
        # connect the two will assume the generator broke.
        print(f"  future-date: removed {dropped} of {len(items)} developments dated "
              f"after {today}. Expected on a mid-month run — the month is not over, "
              f"so those events have not happened yet. Re-run on the last day of the "
              f"month for a full issue.")
    return kept


def _finalize_developments(items, strategy, coverage_date=None, today=None):
    items = [i for i in items if not is_meta_commentary(i.get('body', '') + ' ' + i.get('company', ''))]
    items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('company', ''))]
    items = [i for i in items if not is_government_entity(i.get('company', ''))]
    items = _drop_future_dated(items, coverage_date, today)
    for item in items:
        body, ratings = _extract_dev_ratings(item.get('body', ''))
        item['body'] = body
        item.update(ratings)
    rated = sum(1 for i in items if i.get('strategic_read'))
    print(f"  parse_developments: strategy {strategy} found {len(items)} items ({rated} with a strategic read)")
    return items[:8]


def parse_actions(text):
    """Strategic actions, split from the decision metadata appended to each.

    Falls back to a bare body with empty metadata, so an action the model wrote
    without the OWNER/PRIORITY labels still renders — just without its badges.
    """
    actions = []
    for raw in parse_list_items(text, min_length=40):
        meta = {"owner": "", "owner_rationale": "", "priority": "", "effort": "", "impact": ""}

        owner = re.search(
            r'\bOWNER\s*[:\-]\s*([^—–\r\n.]{2,45}?)\s*[—–-]\s*(.+?)'
            r'(?=\s*\b(?:PRIORITY|EFFORT|IMPACT)\s*[:\-]|\Z)',
            raw, re.IGNORECASE | re.DOTALL
        )
        if owner:
            meta["owner"] = ' '.join(owner.group(1).split()).strip(' .,;')
            rationale = ' '.join(owner.group(2).split()).strip(' ;,')
            if rationale and not rationale.endswith(('.', '!', '?')):
                rationale += '.'
            meta["owner_rationale"] = rationale
        else:
            # OWNER present but with no rationale after a dash.
            bare = re.search(
                r'\bOWNER\s*[:\-]\s*([^\r\n.]{2,45}?)\s*(?=\.|\b(?:PRIORITY|EFFORT|IMPACT)\s*[:\-]|\Z)',
                raw, re.IGNORECASE
            )
            if bare:
                meta["owner"] = ' '.join(bare.group(1).split()).strip(' .,;')

        for key, allowed in (
            ("priority", r'High|Medium|Low'),
            ("effort",   r'Small|Medium|Large'),
            ("impact",   r'High|Medium|Low'),
        ):
            m = re.search(rf'\b{key.upper()}\s*[:\-]\s*({allowed})\b', raw, re.IGNORECASE)
            meta[key] = _titlecase_rating(m.group(1)) if m else ""

        cut = re.search(r'\s*\b' + _ACTION_META_LABEL + r'\s*[:\-]', raw, re.IGNORECASE)
        body = raw[:cut.start()].strip() if cut else raw.strip()
        if not body:
            continue

        actions.append({"body": body, **meta})

    owned = sum(1 for a in actions if a["owner"])
    print(f"  parse_actions: {len(actions)} actions ({owned} with an assigned owner)")
    return actions


def parse_myth(text):
    """{'myth': ..., 'reality': ...}, or None when either half is missing —
    half a myth box is worse than none."""
    if not text or len(text.strip()) < 40:
        return None

    myth = re.search(
        r'\bMyth\s*[:\-–—]\s*(.+?)(?=\s*\bReality\s*[:\-–—]|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    reality = re.search(
        r'\bReality\s*[:\-–—]\s*(.+)\Z',
        text, re.IGNORECASE | re.DOTALL
    )
    if not myth or not reality:
        return None

    myth_text    = ' '.join(myth.group(1).split()).strip()
    reality_text = ' '.join(reality.group(1).split()).strip()
    if len(myth_text) < 15 or len(reality_text) < 40:
        return None
    return {"myth": myth_text, "reality": reality_text}


_PREDICTION_HORIZONS = ("One month", "Six months", "One year")


def parse_predictions(text):
    """The three horizons, in the fixed order the section is designed around —
    not whatever order the model emitted them in."""
    if not text:
        return []

    found = []
    for label in _PREDICTION_HORIZONS:
        m = re.search(
            rf'^[\s\-•\d.)]*{label}\s*[:\-–—]\s*(.+?)'
            rf'(?=^[\s\-•\d.)]*(?:{"|".join(_PREDICTION_HORIZONS)})\s*[:\-–—]|\Z)',
            text, re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        if not m:
            continue
        body = ' '.join(m.group(1).split()).strip()
        if len(body) < 25:
            continue
        found.append({"horizon": label, "body": body})
    return found


def parse_question(text):
    """The closing question. Anything the model added around it is dropped:
    the section is one question, and a preamble dilutes it."""
    if not text:
        return ""
    flat = ' '.join(text.split()).strip()
    flat = re.sub(r'^(?:Question|The question)\s*[:\-–—]\s*', '', flat, flags=re.IGNORECASE)

    questions = re.findall(r'[^.?!]*\?', flat)
    if questions:
        # The last question is the real one when the model wrote a lead-in;
        # keep a preceding setup sentence only if it is short enough to help.
        candidate = questions[-1].strip()
        if len(candidate) < 25 and len(questions) > 1:
            candidate = questions[-2].strip() + ' ' + candidate
        return candidate
    return flat if 25 <= len(flat) <= 400 else ""


def deduplicate_spotlight_against_developments(spotlight_items, development_items):
    if not spotlight_items or not development_items:
        return spotlight_items

    def key_words(text):
        stops = {
            'the','a','an','of','in','to','for','and','or','is','are','was',
            'were','this','that','these','those','it','its','with','by','at',
            'on','as','from','be','been','has','have','had','not','but','we',
            'our','your','their','will','also','can','more','new','all','may',
            'into','than','through','about','up','out','after','over','under',
            'such','both','each','how','which','who','what','when','where',
            'fund','funding','initiative','program','project','projects',
            'announced','announces','announcement','launch','launches','released',
        }
        words = re.findall(r'[a-z]{4,}', text.lower())
        return {w for w in words if w not in stops}

    dev_keywords = set()
    dev_orgs = set()
    for d in development_items:
        dev_keywords |= key_words(d.get('body', '') + ' ' + d.get('company', ''))
        org = d.get('company', '').strip().lower()
        if org:
            dev_orgs.add(org)

    cleaned = []
    for item in spotlight_items:
        org = item.get('org', '').strip()
        body = item.get('body', '').strip()
        combined = org + ' ' + body

        if org.lower() in dev_orgs:
            item_words = key_words(body)
            overlap = item_words & dev_keywords
            overlap_ratio = len(overlap) / max(len(item_words), 1)
            if overlap_ratio > 0.55:
                print(f"  dedup: removing spotlight '{org}' (org match + {overlap_ratio:.0%} keyword overlap)")
                continue

        item_words = key_words(combined)
        if len(item_words) >= 5:
            overlap = item_words & dev_keywords
            overlap_ratio = len(overlap) / max(len(item_words), 1)
            if overlap_ratio > 0.65:
                print(f"  dedup: removing spotlight '{org}' ({overlap_ratio:.0%} keyword overlap with developments)")
                continue

        cleaned.append(item)

    removed = len(spotlight_items) - len(cleaned)
    if removed:
        print(f"  dedup: removed {removed} duplicate spotlight item(s)")
    return cleaned


def parse_developments(text, coverage_date=None, today=None):
    items = []

    # The date must START A LINE. Every item is emitted as "[Month Day]: ..."
    # on its own line, so anchoring costs nothing — and without it the split
    # fires on any date inside body prose. One real story reading "...closing
    # them to new customers effective July 30. These services are being folded
    # into Bedrock..." was cut in half: the first half lost its strategic read
    # and ratings, and the second half published as a headless card dated
    # July 30 with no company, carrying the analysis that belonged to the
    # story above it. Same failure mode as an unanchored section header.
    date_pattern = re.compile(
        r'^[ \t]*(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\.?\s+\d{1,2}(?:st|nd|rd|th)?[,.]?)',
        re.IGNORECASE | re.MULTILINE
    )

    splits = date_pattern.split(text)
    if len(splits) >= 3:
        i = 1
        while i + 1 < len(splits):
            date_str = splits[i].strip().rstrip(',.')
            body = splits[i + 1].strip().lstrip(': ')
            body = ' '.join(body.split())

            if len(body) > 30:
                source_name, source_url, body_clean = _extract_source_from_text(body)
                company = ""
                desc = body_clean

                for sep in [" — ", " – ", " - "]:
                    if sep in body_clean:
                        parts = body_clean.split(sep, 1)
                        company = parts[0].strip().rstrip(":")
                        desc = parts[1].strip()
                        break

                items.append({
                    "date": date_str,
                    "company": company,
                    "body": desc,
                    "source_name": source_name,
                    "source_url": source_url
                })
            i += 2

        if len(items) >= 3:
            return _finalize_developments(items, 1, coverage_date, today)

    # Strategy 2: numbered list
    items = []
    numbered_blocks = re.findall(
        r'^\d+[\.)]\s+(.+?)(?=^\d+[\.)]\s|\Z)',
        text, re.MULTILINE | re.DOTALL
    )
    if numbered_blocks:
        for block in numbered_blocks:
            block = block.strip()
            if len(block) < 30:
                continue
            source_name, source_url, block_clean = _extract_source_from_text(block)
            date_str = ""
            company = ""
            desc = block_clean

            dm = re.match(
                r'^((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
                r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
                r'\.?\s+\d{1,2}(?:st|nd|rd|th)?[,.]?)[:\s]+(.+)',
                block_clean, re.IGNORECASE | re.DOTALL
            )
            if dm:
                date_str = dm.group(1).strip().rstrip(',.')
                desc = dm.group(2).strip().lstrip(': ')

            for sep in [" — ", " – ", " - "]:
                if sep in desc:
                    parts = desc.split(sep, 1)
                    company = parts[0].strip().rstrip(":")
                    desc = parts[1].strip()
                    break

            items.append({
                "date": date_str,
                "company": company,
                "body": desc,
                "source_name": source_name,
                "source_url": source_url
            })

        if len(items) >= 3:
            return _finalize_developments(items, 2, coverage_date, today)

    # Strategy 3: line-by-line fallback
    items = []
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 40]
    current_block = []

    for line in lines:
        is_new = bool(re.match(
            r'^(\d+[\.)]\s+|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))',
            line, re.IGNORECASE
        ))
        if is_new and current_block:
            block_text = ' '.join(current_block)
            source_name, source_url, block_clean = _extract_source_from_text(block_text)
            date_str = ""
            company = ""
            desc = block_clean

            dm = re.match(
                r'^((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
                r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
                r'\.?\s+\d{1,2}[,.]?)[:\s]+(.+)',
                block_clean, re.IGNORECASE | re.DOTALL
            )
            if dm:
                date_str = dm.group(1).strip().rstrip(',.')
                desc = dm.group(2).strip().lstrip(': ')

            for sep in [" — ", " – ", " - "]:
                if sep in desc:
                    parts = desc.split(sep, 1)
                    company = parts[0].strip().rstrip(":")
                    desc = parts[1].strip()
                    break

            items.append({"date": date_str, "company": company, "body": desc,
                          "source_name": source_name, "source_url": source_url})
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        block_text = ' '.join(current_block)
        if len(block_text) > 40:
            source_name, source_url, block_clean = _extract_source_from_text(block_text)
            items.append({"date": "", "company": "", "body": block_clean,
                          "source_name": source_name, "source_url": source_url})

    return _finalize_developments(items, 3, coverage_date, today)


def parse_spotlight_items(text):
    items = []

    blocks = re.split(r'\n(?=[A-Z][^\n:]{2,60}:)', text)
    for block in blocks:
        block = block.strip()
        if len(block) < 30:
            continue
        source_name, source_url, block_clean = _extract_source_from_text(block)
        org = ""
        body = block_clean
        colon_pos = block_clean.find(':')
        if colon_pos > 0 and colon_pos < 80:
            org = block_clean[:colon_pos].strip()
            body = block_clean[colon_pos+1:].strip()
        if len(body) > 20:
            items.append({"org": org, "body": body, "source_name": source_name, "source_url": source_url})

    items = [i for i in items if not is_meta_commentary(i.get('body', '') + ' ' + i.get('org', ''))]
    items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('org', ''))]

    if len(items) >= 2:
        return items[:6]

    # Strategy 2: numbered list fallback
    items = []
    numbered = re.findall(r'^\d+[\.)]\s+(.+?)(?=^\d+[\.)]\s|\Z)', text, re.MULTILINE | re.DOTALL)
    for block in numbered:
        block = block.strip()
        if len(block) < 20:
            continue
        source_name, source_url, block_clean = _extract_source_from_text(block)
        org = ""
        body = block_clean
        colon_pos = block_clean.find(':')
        if colon_pos > 0 and colon_pos < 80:
            org = block_clean[:colon_pos].strip()
            body = block_clean[colon_pos+1:].strip()
        items.append({"org": org, "body": body, "source_name": source_name, "source_url": source_url})

    if items:
        items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('org', ''))]
        return items[:6]

    # Strategy 3: line fallback
    items = []
    for line in text.split('\n'):
        line = re.sub(r'^[-•*\d.)\s]+', '', line).strip()
        if len(line) < 30:
            continue
        source_name, source_url, line_clean = _extract_source_from_text(line)
        org = ""
        body = line_clean
        colon_pos = line_clean.find(':')
        if colon_pos > 0 and colon_pos < 80:
            org = line_clean[:colon_pos].strip()
            body = line_clean[colon_pos+1:].strip()
        items.append({"org": org, "body": body, "source_name": source_name, "source_url": source_url})

    items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('org', ''))]
    return items[:6]


def parse_adoption_stats(text):
    text = re.sub(r'\.\s+(?=(?:Global:|Nearly|Over|About|Almost|\d))', '.\n', text)
    text = re.sub(r'(Source:[^.\n]{5,100}\.)\s+(?=\d|Global:)', r'\1\n', text, flags=re.IGNORECASE)

    items = []
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 15]

    for line in lines:
        line = re.sub(r'^[-•*\d.)]+\s+', '', line).strip()
        line = re.sub(r'^%\s+', '', line).strip()
        if len(line) < 10:
            continue

        source_name, source_url, line_clean = _extract_source_from_text(line)

        if re.match(r'^[,;]|^[a-z]', line_clean.strip()):
            continue

        num_match = re.match(
            r'^([\d.]+\s*(?:%|percent|\+)?(?:\s*(?:billion|million|B|M))?)',
            line_clean, re.IGNORECASE
        )

        if not num_match or not re.search(r'\d', num_match.group(1)):
            num_match2 = re.search(
                r'((?:nearly|over|about|approximately|around|almost|more than|less than|up to|\$)?\s*[\d.]+\s*(?:%|percent|\+|\$)?(?:\s*(?:billion|million|B|M))?)',
                line_clean, re.IGNORECASE
            )
            if num_match2 and re.search(r'\d', num_match2.group(1)):
                items.append({
                    "stat_text": line_clean,
                    "stat_number": num_match2.group(1).strip(),
                    "source_name": source_name,
                    "source_url": source_url
                })
                continue

        if num_match and re.search(r'\d', num_match.group(1)):
            stat_number = num_match.group(1).strip()
            stat_text = re.sub(r'^of\s+', '', line_clean[num_match.end():].strip()).strip()
            if len(stat_text) < 10:
                stat_text = line_clean
        else:
            stat_number = ""
            stat_text = line_clean

        if len(stat_text) > 5:
            items.append({
                "stat_text": stat_text,
                "stat_number": stat_number,
                "source_name": source_name,
                "source_url": source_url
            })

    return items[:8]


_GENERIC_HEADLINES = (
    "ai insights", "key ai developments", "the month in ai", "monthly ai",
    "ai news", "this month in ai", "ai roundup", "ai update", "headline",
)


def _clean_headline(raw):
    """Accept a model-written headline only if it actually says something.

    A generic headline is worse than the month fallback: it occupies the most
    valuable retrieval real estate on the page while asserting no topic, and it
    would silently look fine. So anything generic is rejected outright rather
    than published."""
    if not raw:
        return None

    line = raw.strip().split("\n")[0].strip()
    line = re.sub(r'^(?:headline|title)\s*[:\-\u2014]\s*', '', line, flags=re.I)
    line = line.strip().strip('"\u201c\u201d\'')
    line = re.sub(r'^[#*\s]+', '', line)
    line = re.sub(r'\s+', ' ', line).strip().rstrip('.')

    if not (25 <= len(line) <= 110):
        return None
    low = line.lower()
    if any(low.startswith(g) for g in _GENERIC_HEADLINES):
        return None
    # must contain a real word beyond the boilerplate, not just "AI" + a month
    if len(re.findall(r'[A-Za-z]{4,}', line)) < 4:
        return None
    return line

def extract_title_and_excerpt(content, issue_month_year, coverage_month_name=None):
    # The title is the single strongest retrieval signal on the page: it is what
    # a search engine and an AI assistant match a question against. "AI Insights
    # for August 2026" states no topic, so it can never match one — the model is
    # asked for a specific claim instead, and that becomes the title.
    #
    # The month is NOT in the title. It is already carried by the issue badge,
    # the dateline and the URL, and spending title characters on it costs topic.
    fallback_title = f"{BRAND} \u2014 {issue_month_year}"
    title   = fallback_title
    excerpt = ""

    sections = parse_sections(content)

    headline = _clean_headline(sections.get("HEADLINE", ""))
    if headline:
        title = headline
    else:
        print("  headline missing or generic; falling back to the month title")
    intro    = sections.get("INTRODUCTION", "")
    if intro:
        sentences = re.split(r'(?<=[.!?])\s+', intro)
        excerpt   = ' '.join(sentences[:2]).strip()

    if not excerpt or len(excerpt) < 50:
        coverage_clause = f", covering {coverage_month_name}'s developments" if coverage_month_name else ""
        excerpt = f"Your monthly AI intelligence briefing for Canadian business leaders — {issue_month_year} issue{coverage_clause}."

    if len(excerpt) > 220:
        excerpt = excerpt[:217].rstrip() + "..."

    return title, excerpt
