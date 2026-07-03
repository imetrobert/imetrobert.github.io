"""
parser.py
Parses Gemini's plain-text output into structured data for HTML rendering.
"""

import re
from utils import (
    build_search_url,
    is_episode_or_newsletter_item,
    is_government_entity,
    is_meta_commentary,
)


SECTION_HEADERS = [
    "INTRODUCTION",
    "KEY AI DEVELOPMENTS",
    "CANADIAN SPOTLIGHT",
    "WHAT THIS MEANS FOR CANADIAN BUSINESS",
    "STRATEGIC ACTIONS FOR THIS MONTH",
    "ADOPTION SNAPSHOT",
    "ROBERTS TAKE",
]


def parse_sections(content):
    sections = {h: "" for h in SECTION_HEADERS}
    positions = {}
    content_upper = content.upper()

    for header in SECTION_HEADERS:
        variants = [header, header + ":", header + "S", header.replace(" ", "S ")]
        for variant in variants:
            idx = content_upper.find(variant)
            if idx != -1:
                positions[header] = idx
                break

    if not positions:
        sections["INTRODUCTION"] = content
        return sections

    sorted_headers = sorted(positions.keys(), key=lambda h: positions[h])
    for i, header in enumerate(sorted_headers):
        start = positions[header] + len(header)
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

    return "", "", text.strip()


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


def parse_developments(text):
    items = []

    date_pattern = re.compile(
        r'(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\.?\s+\d{1,2}(?:st|nd|rd|th)?[,.]?)',
        re.IGNORECASE
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
            items = [i for i in items if not is_meta_commentary(i.get('body', '') + ' ' + i.get('company', ''))]
            items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('company', ''))]
            items = [i for i in items if not is_government_entity(i.get('company', ''))]
            print(f"  parse_developments: strategy 1 found {len(items)} items")
            return items[:10]

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
            items = [i for i in items if not is_meta_commentary(i.get('body', '') + ' ' + i.get('company', ''))]
            items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('company', ''))]
            items = [i for i in items if not is_government_entity(i.get('company', ''))]
            print(f"  parse_developments: strategy 2 found {len(items)} items")
            return items[:10]

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

    items = [i for i in items if not is_meta_commentary(i.get('body', '') + ' ' + i.get('company', ''))]
    items = [i for i in items if not is_episode_or_newsletter_item(i.get('body', ''), i.get('company', ''))]
    items = [i for i in items if not is_government_entity(i.get('company', ''))]
    print(f"  parse_developments: strategy 3 found {len(items)} items")
    return items[:10]


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


def extract_title_and_excerpt(content, issue_month_year, coverage_month_name=None):
    # Title uses the ISSUE month (the month readers actually open this in),
    # so the headline never looks stale. See utils.get_issue_labels().
    title   = f"AI Insights for {issue_month_year}"
    excerpt = ""

    sections = parse_sections(content)
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
