import argparse
import os
import requests
import json
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════

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

    # ── Strip Gemini self-check / correction commentary ──────────────
    # Gemini sometimes includes its own reasoning in the output, e.g.:
    # "Correction: The FedDev Ontario investment was listed in both sections..."
    # "Note: I have removed the duplicate item..."
    # "Self-check: ..."
    # These must never appear in the published post.
    meta_patterns = [
        # "Correction: ..." paragraph
        r'(?:^|\n)\s*(?:Correction|Note|Self-check|Self check|Clarification|Update|Revision)'
        r'[:\s][^\n]{10,400}(?:\n[^\n]{0,300}){0,5}',
        # "I will remove..." / "I have removed..." sentences
        r'[^.\n]*\bI (?:will|have|am going to) (?:remove|replace|delete|correct|fix|update)'
        r'[^.\n]*\.?',
        # "This (?:item|entry|announcement) was listed in both..."
        r'[^.\n]*\b(?:listed|appears?|appeared|duplicated?|repeated?)\s+in\s+both\s+sections[^.\n]*\.?',
        # "...and replace it with a different Canadian..."
        r'[^.\n]*and replace it with a (?:different|new|another)[^.\n]*\.?',
        # MANDATORY SELF-CHECK output that leaked through
        r'(?:^|\n)\s*(?:MANDATORY )?SELF-CHECK[^\n]*(?:\n[^\n]{0,200}){0,10}',
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
    """Build a Google search URL. Always works — no dead links."""
    if not publication and not headline:
        return None
    query_parts = []
    if publication:
        query_parts.append(f'"{publication.strip()}"')
    if headline:
        query_parts.append(f'"{headline.strip()}"')
    query = " ".join(query_parts)
    return "https://www.google.com/search?q=" + requests.utils.quote(query)


# ══════════════════════════════════════════════════════════════════
# SHARED PROMPT RULES (used by both monthly and custom prompts)
# ══════════════════════════════════════════════════════════════════

def _shared_rules_block(month_year, prev_month):
    """Returns the invariant rules/format block shared by all prompt variants."""
    return f"""WRITING RULES — follow these exactly:
1. Write like a trusted senior advisor talking to a peer. Confident. Direct. No hedging.
2. Maximum 22 words per sentence. Short sentences hit harder.
3. Never use these phrases:
   - "dual-edged sword" → describe the tension directly
   - "unprecedented opportunities" → name the specific opportunity
   - "navigate" → deal with / address / respond to
   - "leverage" → use
   - "harness" → use / deploy / apply
   - "landscape" → market / industry / sector
   - "stakeholders" → customers / employees / investors / regulators
   - "game-changer" → describe why it changes things
   - "paradigm shift" → describe the actual shift
   - "move the needle" → describe the specific outcome
   - "in today's fast-paced world" → delete entirely
   - "Welcome to the [month] edition" → do not use
   - "This month, the pace of AI innovation continues to accelerate" → do not use
4. Ground everything in Canadian business reality: US-Canada trade tensions under the Carney government, Bill C-27 (AIDA) working through Parliament, Quebec Law 25 privacy requirements, PIPEDA, the Canadian dollar, AI talent competition between Toronto/Montreal/Vancouver.
5. Name real Canadian companies and institutions where relevant: Shopify, Cohere, D-Wave, Ada, Coveo, RBC, TD, Scotiabank, CIBC, Manulife, Sun Life, Bell, Rogers, Telus, BCE, Loblaw, Couche-Tard, CAE, BRP, Bombardier, Mila, Vector Institute, Amii, Ivey Business School, Rotman School of Management.

Use Google Search grounding to find REAL AI news events from {month_year} ONLY. Do NOT use events from {prev_month} or any prior month. Do not invent events, dates, companies, or statistics.

OUTPUT FORMAT
Write plain text only. No markdown (no *, no **, no #). Use EXACTLY these section headers on their own lines:

INTRODUCTION
KEY AI DEVELOPMENTS
CANADIAN SPOTLIGHT
WHAT THIS MEANS FOR CANADIAN BUSINESS
STRATEGIC ACTIONS FOR THIS MONTH
ADOPTION SNAPSHOT
ROBERTS TAKE

---

INTRODUCTION (3 sentences maximum):
Open with one specific fact or event from {month_year}. Second sentence: what it means for Canadian business. Third sentence: what this analysis helps the reader do. Do NOT start with "Welcome", "This month", or any warmup phrase.

KEY AI DEVELOPMENTS (MINIMUM 8 items — this is a hard requirement):
CRITICAL DATE RULE: Include ONLY events from {month_year}. Never fabricate. Never use events from prior months.
CRITICAL SOURCE RULE: Every single item MUST end with a Source line. No exceptions.
CRITICAL DEDUPLICATION RULE: Treat KEY AI DEVELOPMENTS and CANADIAN SPOTLIGHT as one combined list. Every individual news event, announcement, funding program, product launch, or policy decision may appear ONCE across both sections combined — never twice. Before finalising your full response, scan every item in KEY AI DEVELOPMENTS and every item in CANADIAN SPOTLIGHT. If the same announcement appears in both (even reworded or described differently), DELETE it from CANADIAN SPOTLIGHT and replace it with a genuinely different Canadian news item. The AI Compute Access Fund, or any government funding program, or any company product launch, must not appear in both sections. This is a hard constraint with zero exceptions.

Use this EXACT format for every item — copy it precisely:
[Month Day]: [Company] — [One sentence: what they did]. [One sentence: why it matters for Canadian business]. Source: [Publication name] | [Exact article headline as published]

Example of correct format:
May 15: Google — Released Gemini 3.1 with enhanced reasoning for enterprise. Canadian financial services firms can now deploy it within existing Google Workspace contracts. Source: The Verge | Google Releases Gemini 3.1 With Stronger Reasoning

Rules:
- MINIMUM 8 items. Aim for 8-10.
- Every item has a date from {month_year}
- Every item ends with Source: [Publication] | [Headline] — no URLs, no brackets around the headline
- Vary the companies — mix US tech, Canadian companies, global players
- The Canadian relevance sentence must be specific, not generic
- UNIQUENESS RULE: Every item must cover a distinct news event or announcement. The same company may appear more than once only if each appearance covers a completely different announcement, product, or decision. Do NOT list the same funding program, product launch, or policy announcement twice even with different wording.

CANADIAN SPOTLIGHT (MINIMUM 3 items — hard requirement):
Only genuinely Canadian content:
- Canadian AI companies making news (Cohere, Ada, Coveo, D-Wave, Mila spinouts, etc.)
- Federal or provincial government AI funding, policy, or regulation updates
- Major foreign AI investment specifically into Canada
- Canadian enterprise AI deployments (named company + what they did)
- Canadian university or research breakthroughs (Mila, Vector Institute, Amii)

CRITICAL SOURCE RULE: Every single Canadian Spotlight item MUST end with a Source line.

CRITICAL UNIQUENESS RULE: Canadian Spotlight items MUST NOT repeat any announcement, funding program, policy, or event that already appeared in KEY AI DEVELOPMENTS above. Before writing each Spotlight item, check: has this specific announcement already been covered above? If yes, choose a different Canadian news item. The same organization can appear in both sections only if each entry covers a completely separate announcement. Duplicate topics — even reworded — are a failure.

Use this EXACT format for every item:
[Company/Organization]: [What happened — one sentence]. [Why it matters — one sentence]. Source: [Publication name] | [Exact article headline as published]

Example:
Cohere: Launched Command R+ with enhanced bilingual French-English support. Quebec enterprises can now deploy a Canadian-built model for both official languages without US data residency concerns. Source: Globe and Mail | Cohere Launches Bilingual AI Model Built for Canadian Enterprises

Rules:
- MINIMUM 3 items. Aim for 3-4.
- No generic "Canada is positioning itself" filler
- Every item ends with Source: [Publication] | [Headline]
- Every item covers a news event NOT already listed in KEY AI DEVELOPMENTS

MANDATORY SELF-CHECK — DO THIS BEFORE WRITING ANY FURTHER:
List every news event you have written in KEY AI DEVELOPMENTS (by topic, one line each).
Then list every news event in CANADIAN SPOTLIGHT (by topic, one line each).
Compare the two lists. If ANY topic, announcement, funding program, or event appears in both lists — even described with different words — you MUST go back and replace the duplicate in CANADIAN SPOTLIGHT with a genuinely different Canadian news item before continuing.
Example of a violation: "Government of Canada AI Compute Access Fund $66M" appearing in KEY AI DEVELOPMENTS AND also appearing in CANADIAN SPOTLIGHT under any wording. That is a hard failure. Remove it from one section.
Only continue to WHAT THIS MEANS once every item across both sections is a unique, non-overlapping news event.

WHAT THIS MEANS FOR CANADIAN BUSINESS (3 paragraphs):
CRITICAL CROSS-REFERENCE RULE: Every paragraph MUST name at least one specific event, company, or statistic from KEY AI DEVELOPMENTS, CANADIAN SPOTLIGHT, or ADOPTION SNAPSHOT above. Do not introduce new information here — this section interprets what was already reported. Generic analysis with no link to the items above is a failure.

Paragraph 1 — Financial services / technology impact:
- Open by naming a specific development from KEY AI DEVELOPMENTS (use the company name and what they did).
- Explain the direct operational consequence for a named Canadian bank, insurer, or tech company (RBC, TD, Manulife, Cohere, etc.).
- Connect to an adoption stat if one is relevant.
- 3-4 sentences maximum.

Paragraph 2 — Sector impact (manufacturing, healthcare, or retail):
- Open by naming a specific item from CANADIAN SPOTLIGHT or KEY AI DEVELOPMENTS that affects this sector.
- Name a real Canadian company or describe a real sector dynamic (not a hypothetical).
- Make the opportunity or risk concrete and specific.
- 3-4 sentences maximum.

Paragraph 3 — Regulatory and competitive pressure:
- Open by naming a specific regulation or policy item already referenced above (Bill C-27, Quebec Law 25, PIPEDA, OSFI guidelines, or a government funding program from CANADIAN SPOTLIGHT).
- State a specific compliance deadline or decision point Canadian leaders face.
- Connect to what the ADOPTION SNAPSHOT numbers mean for urgency.
- 3-4 sentences maximum.

STRATEGIC ACTIONS FOR THIS MONTH (exactly 5 items):
CRITICAL TRACEABILITY RULE: Each of the 5 actions MUST trace directly to a named item from KEY AI DEVELOPMENTS or CANADIAN SPOTLIGHT. Write the action as a direct operational response to that specific news item. A reader should be able to look up the item in the sections above and see the connection immediately. Generic AI advice with no link to the reported news is a failure.

Each action must:
- Start with a strong verb: Audit, Pilot, Negotiate, Commission, Assign, Test, Require, Demand, Sunset, Block time to
- Name the specific development, company, tool, regulation, or funding program it responds to (e.g. "In response to [company]'s [action] reported above...")
- State WHO in the organization owns it (CTO, CFO, CHRO, Legal team, Board Audit Committee, etc.)
- Include a specific deadline (this week / by end of Q2 / before June 30 / within 30 days)
- Be 2-3 sentences

Format: 1. [Action text]

ADOPTION SNAPSHOT (exactly 5 data points):
CRITICAL: Each stat on its own line. Never combine into a paragraph.
CRITICAL FORMAT: The number MUST come first. Never start a line with "%" or "of". Always write "30% of Canadian businesses..." not "% of Canadian businesses...". Never omit the number.

Correct format examples:
30% of Canadian businesses have adopted AI in at least one function. Source: BDC, 2025.
46% of employed Canadians say AI has impacted their career trajectory. Source: Borderless AI, 2026.
Global: 70% of organizations have an AI strategy in place. Source: McKinsey, 2025.

Format for each line:
[Number]% [rest of stat]. Source: [Organization], [year].

Use only real, verifiable Canadian stats from: Statistics Canada, BDC, ISED, CIRA, Conference Board of Canada, Deloitte Canada, KPMG Canada, PwC Canada, Mila Annual Report, Vector Institute Annual Report, McKinsey Canada.
If no Canadian stat exists for a category, use a global stat and clearly label it "Global:".
Never invent percentages. Never attribute to vague sources.
Where possible, choose stats that contextualise or add weight to the developments reported in KEY AI DEVELOPMENTS and CANADIAN SPOTLIGHT above.

ROBERTS TAKE:
CRITICAL: This is NOT a summary of the newsletter. Robert speaks in first person with a direct, opinionated voice. He references 1-2 specific items from KEY AI DEVELOPMENTS or CANADIAN SPOTLIGHT and offers a take that a reader would NOT get from reading those items alone — a pattern, a contradiction, a warning, or a client conversation that reveals something the headlines missed.

Write 2-3 sentences. Start with "The [thing] that surprised me most this month was..." or "What I keep telling clients right now is..." or similar first-person opener. Never start with "This month" or "The AI landscape".

Do NOT write the placeholder. Write actual content that Robert would say based on the specific news reported above.

---
Context: {month_year} edition"""


# ══════════════════════════════════════════════════════════════════
# GEMINI API
# ══════════════════════════════════════════════════════════════════

def generate_blog_with_gemini(api_key, topic=None):
    import time

    current_date = datetime.now()
    month_year   = current_date.strftime("%B %Y")
    prev_month   = (current_date.replace(day=1) - __import__('datetime').timedelta(days=1)).strftime("%B %Y")

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    models_to_try = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]

    if topic:
        prompt = _build_custom_prompt(topic, month_year, prev_month)
    else:
        prompt = _build_monthly_prompt(month_year, prev_month)

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "maxOutputTokens": 4000,
            "temperature": 0.55,
            "candidateCount": 1
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
        ]
    }

    for attempt, model in enumerate(models_to_try):
        if attempt > 0:
            print(f"  Waiting 30 s before trying {model}...")
            time.sleep(30)

        print(f"Trying model: {model} (attempt {attempt+1}/{len(models_to_try)})")
        url = f"{BASE}/{model}:generateContent?key={api_key}"

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

            if len(raw_text) < 200:
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


def _build_monthly_prompt(month_year, prev_month):
    rules = _shared_rules_block(month_year, prev_month)
    return f"""You are writing the monthly AI insights newsletter for Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert has 25+ years in digital transformation and is known for direct, opinionated takes on AI adoption.

AUDIENCE
Canadian business leaders — C-suite, VPs, and directors at mid-to-large Canadian enterprises in financial services, retail, manufacturing, telecom, and healthcare. They are time-pressed and want signal, not noise.

{rules}"""


def _build_custom_prompt(topic, month_year, prev_month):
    """
    Custom/regeneration prompt. Identical structure to monthly prompt.
    The topic is a CONTENT FOCUS DIRECTIVE only — it changes what events
    and examples are chosen, never the format or structural requirements.
    All section counts, source citation rules, and format specs are identical.
    """
    rules = _shared_rules_block(month_year, prev_month)
    return f"""You are writing the monthly AI insights newsletter for Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert has 25+ years in digital transformation and is known for direct, opinionated takes on AI adoption.

AUDIENCE
Canadian business leaders — C-suite, VPs, and directors at mid-to-large Canadian enterprises in financial services, retail, manufacturing, telecom, and healthcare. They are time-pressed and want signal, not noise.

CONTENT FOCUS DIRECTIVE:
{topic}

This directive changes WHAT events and examples you select and emphasise. It does NOT change the structure, section counts, formatting rules, or citation requirements. All structural rules below are mandatory and unchanged. The focus applies to which developments you prioritise in KEY AI DEVELOPMENTS, which items you choose for CANADIAN SPOTLIGHT, how you frame WHAT THIS MEANS FOR CANADIAN BUSINESS, and which STRATEGIC ACTIONS you recommend. The newsletter must still contain ALL sections with ALL minimum item counts and ALL source citations.

{rules}"""


# ══════════════════════════════════════════════════════════════════
# CONTENT PARSING
# ══════════════════════════════════════════════════════════════════

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
    """
    Extract Source: Publication | Headline from a block of text.
    Returns (source_name, source_url, cleaned_text_without_source_line).
    Only matches Source: lines after a sentence boundary to avoid
    truncating body text that contains colons or pipes.
    """
    source_name = ""
    source_url = ""

    # Pattern 1: Source: Publication | Headline  (pipe — most reliable)
    m = re.search(
        r'(?:^|[.\n])\s*Source[:\s]+([^|\r\n]{3,80}?)\s*\|\s*([^\r\n]{5,200})',
        text, re.IGNORECASE | re.MULTILINE
    )
    if not m:
        # Pattern 2: Source: Publication — Headline  (em/en dash)
        m = re.search(
            r'(?:^|[.\n])\s*Source[:\s]+([^\u2014\u2013\r\n]{3,60})[\u2014\u2013]+([^\r\n]{5,200})',
            text, re.IGNORECASE | re.MULTILINE
        )
    if not m:
        # Pattern 3: Source: OrganizationName, YYYY  (adoption stats format)
        m = re.search(
            r'(?:^|[.\n])\s*Source[:\s]+([A-Za-z][^\d\r\n,]{2,50}),\s*(\d{4}[^\r\n]{0,30})',
            text, re.IGNORECASE | re.MULTILINE
        )

    if m:
        source_name = m.group(1).strip().rstrip('.,')
        source_headline = m.group(2).strip().rstrip('.,')
        source_headline = re.sub(r'https?://\S+', '', source_headline).strip().rstrip('.,')
        source_url = build_search_url(source_name, source_headline) if len(source_headline) > 6 else None
        # Trim from where "Source" keyword starts (not match start, which may
        # include the preceding period character from the lookahead)
        source_kw = text.upper().rfind('SOURCE', 0, m.end())
        cleaned = text[:source_kw].strip().rstrip('.') if source_kw > 0 else text[:m.start()].strip()
        return source_name, source_url, cleaned

    return "", "", text.strip()

def parse_developments(text):
    """
    Parse KEY AI DEVELOPMENTS into structured dicts.
    Robust multi-strategy parser: tries date-anchored splitting first,
    then falls back to line-by-line and numbered-list approaches.
    Always attempts to extract Source citations from each item.
    """
    items = []

    # ── Strategy 1: Split on date patterns ──────────────────────
    date_pattern = re.compile(
        r'(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\.?\s+\d{1,2}(?:st|nd|rd|th)?[,.]?)',
        re.IGNORECASE
    )

    splits = date_pattern.split(text)
    if len(splits) >= 3:  # at least one date found
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
            items = [i for i in items if not _is_meta_commentary(i.get('body', '') + ' ' + i.get('company', ''))]
            print(f"  parse_developments: strategy 1 found {len(items)} items")
            return items[:10]

    # ── Strategy 2: Numbered list items ─────────────────────────
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
            # Try to extract date and company from the cleaned block
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
            print(f"  parse_developments: strategy 2 found {len(items)} items")
            return items[:10]

    # ── Strategy 3: Line-by-line fallback ───────────────────────
    items = []
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 40]
    current_block = []

    for line in lines:
        # A new item starts when we see a date or a number at the start
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

    # Don't forget the last block
    if current_block:
        block_text = ' '.join(current_block)
        if len(block_text) > 40:
            source_name, source_url, block_clean = _extract_source_from_text(block_text)
            items.append({"date": "", "company": "", "body": block_clean,
                          "source_name": source_name, "source_url": source_url})

    items = [i for i in items if not _is_meta_commentary(i.get('body', '') + ' ' + i.get('company', ''))]
    print(f"  parse_developments: strategy 3 found {len(items)} items")
    return items[:10]


def _is_meta_commentary(text):
    """
    Returns True if a parsed item looks like Gemini self-check commentary
    that leaked into the output — should be filtered out before rendering.
    """
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


def parse_spotlight_items(text):
    """
    Parse CANADIAN SPOTLIGHT items. Each should have company: body. Source: pub | headline.
    Returns list of dicts with keys: org, body, source_name, source_url.
    """
    items = []

    # Strategy 1: Split on lines that start with an org name followed by colon
    # Look for patterns like "Cohere: ..." or "Government of Canada: ..."
    blocks = re.split(r'\n(?=[A-Z][^\n:]{2,60}:)', text)

    for block in blocks:
        block = block.strip()
        if len(block) < 30:
            continue
        source_name, source_url, block_clean = _extract_source_from_text(block)

        # Extract org name (text before first colon)
        org = ""
        body = block_clean
        colon_pos = block_clean.find(':')
        if colon_pos > 0 and colon_pos < 80:
            org = block_clean[:colon_pos].strip()
            body = block_clean[colon_pos+1:].strip()

        if len(body) > 20:
            items.append({
                "org": org,
                "body": body,
                "source_name": source_name,
                "source_url": source_url
            })

    # ── Filter out any Gemini self-correction items that slipped through ──
    items = [i for i in items if not _is_meta_commentary(i.get('body', '') + ' ' + i.get('org', ''))]

    if len(items) >= 2:
        return items[:6]

    # Strategy 2: Numbered list fallback
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
        return items[:6]

    # Strategy 3: Line fallback — treat each substantial line as an item
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

    return items[:6]


def parse_adoption_stats(text):
    """
    Parse ADOPTION SNAPSHOT stats. Handles:
    - One stat per line (ideal Gemini output)
    - Multiple stats packed into a paragraph (common Gemini failure)
    - Stats with inline Source: attribution
    - % appearing before the number (broken Gemini output)
    - Leading fragments like ", showing..." (skipped)
    """
    # ── Pre-process: split paragraph-packed stats into individual lines ──
    # Handles: "37% of businesses... Source: X, 2025. 45% of businesses..."
    text = re.sub(r'\.\s+(?=(?:Global:|Nearly|Over|About|Almost|\d))', '.\n', text)
    text = re.sub(r'(Source:[^.\n]{5,100}\.)\s+(?=\d|Global:)', r'\1\n', text, flags=re.IGNORECASE)

    items = []
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 15]

    for line in lines:
        # Strip leading list markers
        line = re.sub(r'^[-•*\d.)]+\s+', '', line).strip()
        # Strip leading standalone % with no preceding digit (broken Gemini)
        line = re.sub(r'^%\s+', '', line).strip()
        if len(line) < 10:
            continue

        source_name, source_url, line_clean = _extract_source_from_text(line)

        # Skip fragment lines (start with comma/semicolon or lowercase — mid-sentence leftovers)
        if re.match(r'^[,;]|^[a-z]', line_clean.strip()):
            continue

        # Strategy 1: number at start
        num_match = re.match(
            r'^([\d.]+\s*(?:%|percent|\+)?(?:\s*(?:billion|million|B|M))?)',
            line_clean, re.IGNORECASE
        )

        # Strategy 2: qualifier word + number (e.g. "Nearly 30%", "Over $500M")
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
            stat_text = line_clean[num_match.end():].strip().lstrip('of ').strip()
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

def extract_title_and_excerpt(content, month_year):
    title   = f"AI Insights for {month_year}"
    excerpt = ""

    sections = parse_sections(content)
    intro    = sections.get("INTRODUCTION", "")
    if intro:
        sentences = re.split(r'(?<=[.!?])\s+', intro)
        excerpt   = ' '.join(sentences[:2]).strip()

    if not excerpt or len(excerpt) < 50:
        excerpt = f"Your monthly AI intelligence briefing for Canadian business leaders — {month_year}."

    if len(excerpt) > 220:
        excerpt = excerpt[:217].rstrip() + "..."

    return title, excerpt


# ══════════════════════════════════════════════════════════════════
# HTML GENERATION
# ══════════════════════════════════════════════════════════════════

def create_html_blog_post(content, title, excerpt):
    current_date   = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    iso_date       = current_date.strftime("%Y-%m-%d")
    month_year     = current_date.strftime("%B %Y")
    issue_num      = get_issue_number()
    reading_time   = estimate_reading_time(content)

    clean_title = re.sub(r'^[#\*\s]+', '', title).strip() or f"AI Insights for {month_year}"
    seo_title   = f"{clean_title} | AI News for Canadian Business | Robert Simon"
    slug        = clean_filename(clean_title)
    canonical   = f"https://www.imetrobert.com/blog/posts/{iso_date}-{slug}.html"
    og_image    = "https://www.imetrobert.com/blog/og-blog.jpg"

    meta_desc = re.sub(r'\s+', ' ', excerpt).strip()
    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152].rstrip() + "..."

    sections = parse_sections(content)

    intro_text      = sections.get("INTRODUCTION", "")
    canadian_spot   = sections.get("CANADIAN SPOTLIGHT", "")
    business_impact = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    roberts_raw     = sections.get("ROBERTS TAKE", "")
    adoption_raw    = sections.get("ADOPTION SNAPSHOT", "")

    developments    = parse_developments(sections.get("KEY AI DEVELOPMENTS", ""))
    spotlight_items = parse_spotlight_items(canadian_spot)
    actions         = parse_list_items(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""), min_length=40)
    adoption        = parse_adoption_stats(adoption_raw)

    print(f"  Parsed: {len(developments)} developments, {len(spotlight_items)} spotlight, {len(actions)} actions, {len(adoption)} stats")

    article_parts = []

    # ── Introduction ────────────────────────────────────────────
    if intro_text:
        article_parts.append(
            f'<div class="section intro-section">'
            f'<p class="intro-lead">{intro_text}</p>'
            f'</div>'
        )

    # ── Key AI Developments ──────────────────────────────────────
    if developments:
        dev_cards = ""
        for d in developments:
            date_html    = f'<span class="dev-date">{d["date"]}</span>' if d["date"] else ""
            company_html = f'<div class="dev-company">{d["company"]}</div>' if d["company"] else ""
            source_html  = ""
            if d.get("source_url"):
                src_label = d.get("source_name") or "Source"
                source_html = (
                    f'<div class="dev-source">'
                    f'<a href="{d["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this article">'
                    f'🔍 {src_label}'
                    f'</a></div>'
                )
            dev_cards += (
                f'<div class="dev-card">'
                f'  <div class="dev-header">{date_html}{company_html}</div>'
                f'  <p class="dev-body">{d["body"]}</p>'
                f'  {source_html}'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section">'
            f'<h2 class="section-title">Key AI Developments This Month</h2>'
            f'<div class="dev-grid">{dev_cards}</div>'
            f'</div>'
        )

    # ── Canadian Spotlight ───────────────────────────────────────
    if spotlight_items:
        spot_cards = ""
        for item in spotlight_items:
            org_html = f'<div class="spot-org">{item["org"]}</div>' if item["org"] else ""
            source_html = ""
            if item.get("source_url"):
                src_label = item.get("source_name") or "Source"
                source_html = (
                    f'<div class="spot-source">'
                    f'<a href="{item["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this article">'
                    f'🔍 {src_label}'
                    f'</a></div>'
                )
            spot_cards += (
                f'<li>'
                f'<span class="spot-bullet">🍁</span>'
                f'<div class="spot-content">'
                f'{org_html}'
                f'<div class="spot-body">{item["body"]}</div>'
                f'{source_html}'
                f'</div>'
                f'</li>\n'
            )
        article_parts.append(
            f'<div class="section canada-section">'
            f'<div class="canada-header"><span class="canada-label">Canadian Spotlight</span></div>'
            f'<h2 class="section-title canada-title">What\'s Happening in Canada</h2>'
            f'<ul class="spot-list">{spot_cards}</ul>'
            f'</div>'
        )
    elif canadian_spot and len(canadian_spot) > 60:
        # Plain text fallback
        article_parts.append(
            f'<div class="section canada-section">'
            f'<div class="canada-header"><span class="canada-label">Canadian Spotlight</span></div>'
            f'<h2 class="section-title canada-title">What\'s Happening in Canada</h2>'
            f'<p>{canadian_spot}</p>'
            f'</div>'
        )

    # ── Business Impact ──────────────────────────────────────────
    if business_impact:
        paras = [p.strip() for p in business_impact.split('\n\n') if len(p.strip()) > 40]
        if not paras:
            paras = [p.strip() for p in business_impact.split('\n') if len(p.strip()) > 40]
        if not paras:
            paras = [business_impact.strip()]
        paras_html = "\n".join(f'<p>{p}</p>' for p in paras)
        article_parts.append(
            f'<div class="section impact-section">'
            f'<h2 class="section-title">What This Means for Canadian Business</h2>'
            f'{paras_html}'
            f'</div>'
        )

    # ── Strategic Actions ────────────────────────────────────────
    if actions:
        action_cards = ""
        for i, a in enumerate(actions[:5]):
            action_cards += (
                f'<div class="action-card">'
                f'  <div class="action-num">{i+1}</div>'
                f'  <div class="action-body">{a}</div>'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section actions-section">'
            f'<h2 class="section-title">Strategic Actions for This Month</h2>'
            f'<div class="actions-grid">{action_cards}</div>'
            f'</div>'
        )

    # ── Adoption Snapshot ────────────────────────────────────────
    if adoption:
        stat_items_html = ""
        for item in adoption:
            # If stat_number exists AND stat_text is the full sentence,
            # highlight the number inline within the sentence.
            # If stat_text is the remainder after stripping the number, prepend it.
            if item["stat_number"] and item["stat_text"] and item["stat_number"] in item["stat_text"]:
                # Number appears inside the full sentence — highlight it inline
                highlighted = item["stat_text"].replace(
                    item["stat_number"],
                    f'<span class="stat-highlight">{item["stat_number"]}</span>',
                    1
                )
                stat_content = f'<p class="stat-text">{highlighted}</p>'
            elif item["stat_number"]:
                # Number was at the start, stat_text is the remainder
                stat_content = f'<p class="stat-text"><span class="stat-highlight">{item["stat_number"]}</span> {item["stat_text"]}</p>'
            else:
                stat_content = f'<p class="stat-text">{item["stat_text"]}</p>'

            src_html = ""
            if item.get("source_url"):
                src_html = (
                    f'<div class="stat-source">'
                    f'<a href="{item["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this statistic">'
                    f'🔍 {item["source_name"]}'
                    f'</a></div>'
                )
            elif item.get("source_name"):
                src_html = f'<div class="stat-source-plain">{item["source_name"]}</div>'

            stat_items_html += (
                f'<div class="stat-item">'
                f'  {stat_content}'
                f'  {src_html}'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section adoption-section">'
            f'<h2 class="section-title">Canadian AI Adoption Snapshot</h2>'
            f'<div class="stat-grid">{stat_items_html}</div>'
            f'<p class="stat-note">Sources: Statistics Canada, BDC, ISED, Vector Institute, '
            f'Conference Board of Canada, Mila.</p>'
            f'</div>'
        )

    # ── Robert's Take ────────────────────────────────────────────
    article_parts.append(_build_roberts_take(roberts_raw, month_year))

    article_html = "\n".join(article_parts)

    # ── FAQ schema ───────────────────────────────────────────────
    faq_qs = [
        f"What AI developments matter most for Canadian businesses in {month_year}?",
        "What should Canadian executives do about AI right now?",
        "How is AI adoption tracking across Canada?",
        "What Canadian AI companies or initiatives should I know about?",
        "How do global AI trends affect Canadian competitiveness?",
    ]
    faq_items = []
    for i, action in enumerate(actions[:5]):
        faq_items.append({"question": faq_qs[i], "answer": action[:500]})

    faq_schema = ""
    if faq_items:
        faq_schema_items = ',\n'.join([
            f'{{"@type":"Question","name":{json.dumps(f["question"])},'
            f'"acceptedAnswer":{{"@type":"Answer","text":{json.dumps(f["answer"])}}}}}'
            for f in faq_items
        ])
        faq_schema = f"""    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [{faq_schema_items}]
    }}
    </script>"""

    html = f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="AI Canada {month_year}, Canadian AI news, artificial intelligence Canada, AI business strategy Canada, AI adoption Canada, Montreal AI, Canadian digital transformation, AI news for Canadians, AI insights {month_year}">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
    <meta name="language" content="en-CA">
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">
    <link rel="canonical" href="{canonical}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{clean_title} | AI Insights for Canadian Business">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">
    <meta property="article:published_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:modified_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:author" content="Robert Simon">
    <meta property="article:section" content="AI Strategy">
    <meta property="article:tag" content="AI Canada">
    <meta property="article:tag" content="Canadian Business">
    <meta property="article:tag" content="Artificial Intelligence">
    <meta property="article:tag" content="Digital Transformation">
    <meta property="article:tag" content="Montreal">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{clean_title} | AI News for Canadian Business">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <meta name="twitter:site" content="@thedigitalrobert">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": {json.dumps(clean_title)},
      "description": {json.dumps(meta_desc)},
      "datePublished": "{iso_date}",
      "dateModified": "{iso_date}",
      "author": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "jobTitle": "AI Thought Leader & Digital Transformation Expert",
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }},
      "publisher": {{"@type": "Person", "name": "Robert Simon", "url": "https://www.imetrobert.com"}},
      "mainEntityOfPage": {{"@type": "WebPage", "@id": {json.dumps(canonical)}}},
      "url": {json.dumps(canonical)},
      "image": {json.dumps(og_image)},
      "inLanguage": "en-CA",
      "about": [
        {{"@type": "Thing", "name": "Artificial Intelligence"}},
        {{"@type": "Thing", "name": "Canadian Business"}},
        {{"@type": "Place", "name": "Canada"}}
      ],
      "keywords": "AI Canada, artificial intelligence Canada, Canadian business AI, AI news Montreal, AI strategy Canada, digital transformation Canada"
    }}
    </script>
{faq_schema}
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.imetrobert.com"}},
        {{"@type": "ListItem", "position": 2, "name": "AI Insights Blog", "item": "https://www.imetrobert.com/blog/"}},
        {{"@type": "ListItem", "position": 3, "name": {json.dumps(clean_title)}, "item": {json.dumps(canonical)}}}
      ]
    }}
    </script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --blue:        #2563eb;
            --blue-dark:   #1d4ed8;
            --cyan:        #06b6d4;
            --navy:        #0f172a;
            --gray-dark:   #1e293b;
            --gray:        #475569;
            --gray-light:  #94a3b8;
            --surface:     #f8fafc;
            --border:      #e2e8f0;
            --white:       #ffffff;
            --canada-red:  #dc2626;
            --green:       #16a34a;
            --amber:       #d97706;
            --shadow-sm:   0 1px 3px rgb(0 0 0 / 0.08);
            --shadow-md:   0 4px 16px rgb(0 0 0 / 0.08);
            --shadow-lg:   0 8px 32px rgb(0 0 0 / 0.10);
        }}
        *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%); color: var(--navy); line-height: 1.6; -webkit-font-smoothing: antialiased; }}
        .nav-bar {{ background: var(--white); padding: 0.875rem 0; box-shadow: var(--shadow-sm); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid var(--border); }}
        .nav-content {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }}
        .nav-link {{ color: var(--white); text-decoration: none; font-weight: 600; padding: 0.4rem 1rem; font-size: 0.8rem; border-radius: 20px; background: linear-gradient(135deg, var(--blue), var(--cyan)); transition: all 0.2s; letter-spacing: 0.01em; flex-shrink: 0; }}
        .nav-link:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgb(37 99 235 / 0.3); }}
        .nav-meta {{ font-size: 0.78rem; color: var(--gray-light); display: flex; align-items: center; gap: 0.5rem; }}
        .header {{ background: linear-gradient(135deg, var(--blue) 0%, #1a7fb5 50%, var(--cyan) 100%); color: var(--white); padding: 4rem 0 3.5rem; text-align: center; position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; inset: 0; background: radial-gradient(circle at 15% 85%, rgba(255,255,255,0.07) 0%, transparent 45%), radial-gradient(circle at 85% 15%, rgba(255,255,255,0.05) 0%, transparent 45%); pointer-events: none; }}
        .header-content {{ max-width: 780px; margin: 0 auto; padding: 0 1.5rem; position: relative; z-index: 1; }}
        .issue-badge {{ display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); padding: 0.3rem 0.9rem; border-radius: 20px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 1.25rem; }}
        .header h1 {{ font-size: clamp(1.75rem, 4.5vw, 2.6rem); font-weight: 800; line-height: 1.15; margin-bottom: 0.6rem; letter-spacing: -0.02em; }}
        .header .subtitle {{ font-size: 0.95rem; font-weight: 500; opacity: 0.85; margin-bottom: 1rem; }}
        .header .intro-text {{ font-size: 0.925rem; opacity: 0.8; max-width: 640px; margin: 0 auto 1.25rem; line-height: 1.65; }}
        .reading-badge {{ display: inline-flex; align-items: center; gap: 0.3rem; background: rgba(255,255,255,0.12); padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.72rem; font-weight: 500; opacity: 0.85; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
        .article-card {{ background: var(--white); border-radius: 20px; box-shadow: var(--shadow-lg); overflow: hidden; border: 1px solid rgba(226,232,240,0.6); }}
        .breadcrumb {{ font-size: 0.72rem; color: var(--gray-light); padding: 0.65rem 2rem; background: var(--surface); border-bottom: 1px solid var(--border); }}
        .breadcrumb a {{ color: var(--blue); text-decoration: none; }}
        .author-byline {{ display: flex; align-items: center; gap: 0.875rem; padding: 1rem 2rem; border-bottom: 1px solid var(--border); background: var(--surface); }}
        .author-byline img {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 2px solid var(--border); }}
        .author-name  {{ font-weight: 700; color: var(--navy); font-size: 0.875rem; }}
        .author-role  {{ font-size: 0.75rem; color: var(--gray-light); margin-top: 0.1rem; }}
        .article-content {{ padding: 2.25rem 2rem; }}
        .section {{ margin-bottom: 3rem; }}
        .section-title {{ font-size: 1.2rem; font-weight: 700; color: var(--navy); margin-bottom: 1.25rem; padding-left: 0.875rem; position: relative; letter-spacing: -0.01em; }}
        .section-title::before {{ content: ''; position: absolute; left: 0; top: 0.1rem; bottom: 0.1rem; width: 3px; background: linear-gradient(to bottom, var(--blue), var(--cyan)); border-radius: 2px; }}
        .intro-section {{ border-left: 3px solid var(--cyan); padding-left: 1.25rem; }}
        .intro-lead {{ font-size: 1.05rem; line-height: 1.75; color: var(--gray-dark); font-weight: 400; }}
        .dev-grid {{ display: grid; gap: 0.75rem; }}
        .dev-card {{ padding: 1rem 1.25rem; border: 1px solid var(--border); border-radius: 12px; transition: border-color 0.2s, box-shadow 0.2s; border-left: 3px solid var(--blue); background: #fafbff; }}
        .dev-card:hover {{ border-color: var(--blue); box-shadow: var(--shadow-md); background: var(--white); }}
        .dev-header {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.4rem; flex-wrap: wrap; }}
        .dev-date {{ display: inline-block; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: var(--white); font-size: 0.65rem; font-weight: 700; padding: 0.15rem 0.55rem; border-radius: 10px; white-space: nowrap; letter-spacing: 0.03em; }}
        .dev-company {{ font-weight: 700; color: var(--navy); font-size: 0.85rem; }}
        .dev-body {{ font-size: 0.875rem; color: var(--gray); line-height: 1.65; }}
        .dev-source {{ margin-top: 0.5rem; }}
        .dev-source a {{ font-size: 0.72rem; color: var(--blue); text-decoration: none; font-weight: 600; opacity: 0.8; transition: opacity 0.2s; }}
        .dev-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .canada-section {{ background: linear-gradient(135deg, #fff5f5 0%, #fffbfb 100%); border: 1px solid #fecaca; border-radius: 16px; padding: 1.75rem; }}
        .canada-header {{ margin-bottom: 0.75rem; }}
        .canada-label {{ display: inline-flex; align-items: center; gap: 0.35rem; background: var(--canada-red); color: var(--white); font-size: 0.65rem; font-weight: 700; padding: 0.2rem 0.7rem; border-radius: 12px; letter-spacing: 0.06em; text-transform: uppercase; }}
        .canada-label::before {{ content: "🍁"; font-size: 0.75rem; }}
        .canada-title::before {{ background: var(--canada-red) !important; }}
        .spot-list {{ list-style: none; padding: 0; display: grid; gap: 0.875rem; }}
        .spot-list li {{ display: flex; gap: 0.6rem; align-items: flex-start; font-size: 0.875rem; color: var(--gray); line-height: 1.65; padding: 0.875rem 1rem; background: var(--white); border-radius: 10px; border: 1px solid #fde8e8; }}
        .spot-bullet {{ flex-shrink: 0; margin-top: 0.1rem; font-size: 0.85rem; }}
        .spot-content {{ flex: 1; }}
        .spot-org {{ font-weight: 700; color: var(--navy); font-size: 0.85rem; margin-bottom: 0.2rem; }}
        .spot-body {{ font-size: 0.875rem; color: var(--gray); line-height: 1.6; }}
        .spot-source {{ margin-top: 0.4rem; }}
        .spot-source a {{ font-size: 0.72rem; color: var(--canada-red); text-decoration: none; font-weight: 600; opacity: 0.8; transition: opacity 0.2s; }}
        .spot-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .impact-section p {{ font-size: 0.9rem; line-height: 1.8; color: var(--gray); margin-bottom: 1rem; }}
        .impact-section p:last-child {{ margin-bottom: 0; }}
        .actions-grid {{ display: grid; gap: 0.875rem; }}
        .action-card {{ display: flex; gap: 1rem; align-items: flex-start; padding: 1.1rem 1.25rem; background: #f8faff; border: 1px solid #dbeafe; border-radius: 12px; border-left: 3px solid var(--blue); transition: box-shadow 0.2s; }}
        .action-card:hover {{ box-shadow: var(--shadow-md); background: var(--white); }}
        .action-num {{ display: flex; align-items: center; justify-content: center; width: 1.75rem; height: 1.75rem; min-width: 1.75rem; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: var(--white); font-size: 0.72rem; font-weight: 800; border-radius: 50%; margin-top: 0.1rem; }}
        .action-body {{ font-size: 0.875rem; color: var(--gray-dark); line-height: 1.7; flex: 1; }}
        .stat-grid {{ display: grid; gap: 0.75rem; }}
        .stat-item {{ padding: 1rem 1.25rem; background: #f0fdf4; border-left: 3px solid var(--green); border-radius: 0 10px 10px 0; }}
        .stat-text {{ font-size: 0.875rem; color: var(--gray-dark); line-height: 1.65; }}
        .stat-highlight {{ font-weight: 800; color: var(--green); font-size: 1rem; }}
        .stat-source {{ margin-top: 0.35rem; }}
        .stat-source a {{ font-size: 0.7rem; color: var(--green); text-decoration: none; font-weight: 600; opacity: 0.75; transition: opacity 0.2s; }}
        .stat-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .stat-source-plain {{ font-size: 0.7rem; color: var(--gray-light); margin-top: 0.35rem; }}
        .stat-note {{ font-size: 0.72rem; color: var(--gray-light); margin-top: 0.875rem; font-style: italic; }}
        .roberts-take {{ background: linear-gradient(135deg, #1e3a6e 0%, #1a5276 100%); border-radius: 16px; padding: 1.75rem; color: var(--white); }}
        .roberts-header {{ display: flex; align-items: center; gap: 0.875rem; margin-bottom: 1.1rem; padding-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.12); }}
        .roberts-header img {{ width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,0.25); flex-shrink: 0; }}
        .roberts-label {{ font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; margin-bottom: 0.1rem; }}
        .roberts-name {{ font-weight: 700; font-size: 0.9rem; }}
        .roberts-body {{ font-size: 0.925rem; line-height: 1.85; color: #ffffff; font-style: normal; font-weight: 400; }}
        .roberts-placeholder {{ font-size: 0.825rem; line-height: 1.7; opacity: 0.65; border: 1px dashed rgba(255,255,255,0.25); padding: 1rem 1.25rem; border-radius: 10px; }}
        .roberts-placeholder strong {{ color: var(--white); opacity: 1; font-style: normal; }}
        .conclusion {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: var(--white); padding: 2rem; border-radius: 14px; margin-top: 2.5rem; }}
        .conclusion-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.75; margin-bottom: 0.5rem; }}
        .conclusion p {{ color: rgba(255,255,255,0.95); font-size: 0.95rem; font-weight: 500; line-height: 1.75; }}
        .conclusion strong {{ color: var(--white); font-weight: 700; }}
        p {{ margin-bottom: 1rem; line-height: 1.75; color: var(--gray); font-size: 0.9rem; }}
        strong {{ color: var(--navy); font-weight: 600; }}
        @media (max-width: 640px) {{
            .header {{ padding: 2.5rem 0 2.25rem; }}
            .header h1 {{ font-size: 1.6rem; }}
            .container {{ padding: 1.5rem 1rem 3rem; }}
            .article-content {{ padding: 1.5rem 1.25rem; }}
            .nav-content {{ flex-direction: column; align-items: flex-start; gap: 0.35rem; }}
            .author-byline {{ padding: 0.875rem 1.25rem; }}
            .breadcrumb {{ padding: 0.5rem 1.25rem; }}
            .canada-section {{ padding: 1.25rem; }}
            .action-card {{ flex-direction: column; gap: 0.6rem; }}
            .action-num {{ width: 1.5rem; height: 1.5rem; min-width: 1.5rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">&#8592; Back to Blog</a>
            <div class="nav-meta">
                <span>AI Insights for Canadian Business</span>
                <span>&#8226;</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>
    <header class="header">
        <div class="header-content">
            <div class="issue-badge">Issue #{issue_num} &nbsp;&#8226;&nbsp; {month_year}</div>
            <h1>{clean_title}</h1>
            <div class="subtitle">The AI briefing built for Canadian business leaders</div>
            <div class="intro-text">{excerpt}</div>
            <div class="reading-badge">&#9201; {reading_time} min read</div>
        </div>
    </header>
    <div class="container">
        <article class="article-card" itemscope itemtype="https://schema.org/BlogPosting">
            <meta itemprop="headline"      content="{clean_title}">
            <meta itemprop="datePublished" content="{iso_date}">
            <meta itemprop="dateModified"  content="{iso_date}">
            <meta itemprop="author"        content="Robert Simon">
            <meta itemprop="description"   content="{meta_desc}">
            <nav class="breadcrumb" aria-label="Breadcrumb">
                <a href="https://www.imetrobert.com">Home</a> &#8250;
                <a href="https://www.imetrobert.com/blog/">AI Insights Blog</a> &#8250;
                <span>{clean_title}</span>
            </nav>
            <div class="author-byline">
                <img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon" loading="lazy">
                <div>
                    <div class="author-name">Robert Simon</div>
                    <div class="author-role">AI Thought Leader &amp; Digital Transformation Expert &mdash; Montreal, QC</div>
                </div>
            </div>
            <div class="article-content" itemprop="articleBody">
                {article_html}
                <div class="conclusion">
                    <div class="conclusion-label">The Bottom Line</div>
                    <p>{_build_conclusion(sections, month_year)}</p>
                </div>
            </div>
        </article>
    </div>
</body>
</html>'''

    return html


def _build_roberts_take(raw_text, month_year):
    """
    Renders Robert's Take section.
    Gemini now generates real content here (not a placeholder).
    We still show the editable placeholder UI if the content looks like
    a placeholder or is too short, so Robert can override it before approving.
    """
    is_placeholder = (
        not raw_text
        or 'PLACEHOLDER' in raw_text.upper()
        or '[PLACEHOLDER' in raw_text
        or len(raw_text.strip()) < 40
    )

    header = (
        '<div class="roberts-header">'
        '<img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon">'
        '<div>'
        '<div class="roberts-label">Editor\'s Note</div>'
        '<div class="roberts-name">Robert\'s Take</div>'
        '</div>'
        '</div>'
    )

    if is_placeholder:
        # Fallback: Gemini didn't produce content — show editable prompt
        body = (
            '<div class="roberts-placeholder">'
            '<strong>&#9998; Add your personal take before publishing.</strong><br><br>'
            'What surprised you most this month? What are you telling clients right now? '
            'What is the pattern others are missing? 2-3 sentences in your own voice — '
            'this is the E-E-A-T signal that makes this newsletter yours.'
            '</div>'
        )
    else:
        # Real content from Gemini — clean and render it
        cleaned = raw_text.strip()
        # Strip any residual placeholder brackets if Gemini partially complied
        cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned, flags=re.DOTALL).strip()
        # Strip markdown artifacts
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)
        # Escape quotes for HTML safety
        cleaned = cleaned.replace('"', '&quot;').replace("'", '&#39;')
        # Wrap in quotation marks
        body = (
            f'<p class="roberts-body">&#8220;{cleaned}&#8221;</p>'
            f'<p style="font-size:0.72rem;opacity:0.5;margin-top:0.75rem;color:rgba(255,255,255,0.6);">'
            f'&#9998; You can refine this in the regenerate prompt before approving.</p>'
        )

    return f'<div class="section"><div class="roberts-take">{header}{body}</div></div>'


def _build_conclusion(sections, month_year):
    impact  = sections.get("WHAT THIS MEANS FOR CANADIAN BUSINESS", "")
    actions = parse_list_items(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""), min_length=40)

    if impact:
        sentences = re.split(r'(?<=[.!?])\s+', impact.strip())
        if sentences:
            base = sentences[-1].strip()
            if base and len(base) > 40:
                return (
                    f"{base} The organizations that act on this month's intelligence "
                    f"will set the AI standard in their sector for the next 12 months."
                )

    if actions:
        return (
            f"With {len(actions)} clear priorities this month, Canadian leaders have no shortage of direction. "
            f"The gap between organizations that act and those that wait is growing every month."
        )

    return (
        f"The {month_year} AI landscape demands decisive action from Canadian business leaders. "
        f"Strategy documents are not enough — execution is the only differentiator now."
    )


# ══════════════════════════════════════════════════════════════════
# BLOG INDEX
# ══════════════════════════════════════════════════════════════════

def extract_post_info(html_file):
    if not os.path.exists(html_file) or os.path.getsize(html_file) == 0:
        return None
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "AI Insights"
    title = re.sub(r'^[#\*\s]+', '', title).strip()

    date_text = None
    nav_meta = soup.find("div", class_="nav-meta") or soup.find("div", class_="blog-meta")
    if nav_meta:
        meta_text = nav_meta.get_text()
        if "•" in meta_text:
            date_text = meta_text.split("•")[-1].strip()
    if not date_text:
        basename = os.path.basename(html_file)
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", basename)
        if match:
            date_obj = datetime.strptime(match.group(1), "%Y-%m-%d")
            date_text = date_obj.strftime("%B %d, %Y")
        else:
            date_text = datetime.now().strftime("%B %d, %Y")

    excerpt = None
    intro = soup.find("p", class_="intro-lead") or soup.find("div", class_="intro-text")
    if intro:
        excerpt = re.sub(r'\s+', ' ', intro.get_text()).strip()[:200]
    if not excerpt:
        article = soup.find("div", class_="article-content")
        if article:
            p = article.find("p")
            if p:
                excerpt = re.sub(r'\s+', ' ', p.get_text()).strip()[:200]
    if not excerpt:
        excerpt = "Read the latest AI insights for Canadian business leaders."

    return {"title": title, "date": date_text, "excerpt": excerpt, "filename": os.path.basename(html_file)}


def create_blog_index_html(posts):
    if not posts:
        return None
    posts_dir = "blog/posts"
    validated = [p for p in posts if os.path.exists(os.path.join(posts_dir, p['filename']))]
    if not validated:
        return None

    latest = validated[0]
    older  = validated[1:]

    older_html = ""
    if older:
        for post in older:
            older_html += f'''
                <div class="older-post-item">
                    <a href="/blog/posts/{post['filename']}" class="older-post-link">
                        <div class="older-post-title">{post['title']}</div>
                        <div class="older-post-date">{post['date']}</div>
                    </a>
                </div>'''
    else:
        older_html = '<div class="no-posts-message"><p>Previous issues will appear here.</p></div>'

    itemlist_elements = []
    for i, post in enumerate(validated[:12], 1):
        url = f"https://www.imetrobert.com/blog/posts/{post['filename']}"
        itemlist_elements.append(
            f'{{"@type":"ListItem","position":{i},"url":"{url}","name":{json.dumps(post["title"])}}}'
        )

    return f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI News for Canadians | Monthly AI Insights Blog | Robert Simon</title>
    <meta name="description" content="Monthly AI insights for Canadian business leaders. Expert analysis of AI breakthroughs, Canadian AI adoption data, and practical implementation strategies from Montreal-based AI Thought Leader Robert Simon.">
    <meta name="keywords" content="AI blog Canada, Canadian AI insights, AI news for Canadians, artificial intelligence Canada, AI strategy Canada, Montreal AI expert, Canadian business AI, AI adoption Canada, digital transformation Canada">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="language" content="en-CA">
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">
    <link rel="canonical" href="https://www.imetrobert.com/blog/">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://www.imetrobert.com/blog/">
    <meta property="og:title" content="AI News for Canadians | Monthly AI Insights Blog | Robert Simon">
    <meta property="og:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI Thought Leader Robert Simon.">
    <meta property="og:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="AI News for Canadians | Monthly AI Insights | Robert Simon">
    <meta name="twitter:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI Thought Leader Robert Simon.">
    <meta name="twitter:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Blog",
      "name": "AI Insights for Canadian Business",
      "description": "Monthly AI intelligence for Canadian business leaders by Robert Simon.",
      "url": "https://www.imetrobert.com/blog/",
      "inLanguage": "en-CA",
      "author": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "jobTitle": "AI Thought Leader & Digital Transformation Expert",
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }}
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "ItemList",
      "name": "AI Insights Blog Posts",
      "url": "https://www.imetrobert.com/blog/",
      "numberOfItems": {len(validated)},
      "itemListElement": [{", ".join(itemlist_elements)}]
    }}
    </script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>
    <style>
        body {{ font-family: Inter, sans-serif; background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%); margin: 0; padding: 0; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }}
        header {{ background: linear-gradient(135deg, #2563eb 0%, #1a7fb5 50%, #06b6d4 100%); color: white; padding: 4rem 0; text-align: center; margin-bottom: 2.5rem; border-radius: 20px; }}
        h1 {{ font-size: 2.8rem; font-weight: 800; margin-bottom: 0.5rem; letter-spacing: -0.02em; }}
        .nav-bar {{ background: white; padding: 1rem 0; box-shadow: 0 1px 3px rgb(0 0 0 / 0.08); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #e2e8f0; }}
        .nav-content {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; justify-content: flex-start; }}
        .nav-link {{ color: white; text-decoration: none; font-weight: 600; padding: 0.4rem 1rem; font-size: 0.8rem; border-radius: 20px; background: linear-gradient(135deg, #2563eb, #06b6d4); }}
        .latest-post-section {{ background: linear-gradient(135deg, #2563eb 0%, #1a7fb5 50%, #06b6d4 100%); color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem; box-shadow: 0 8px 32px rgb(37 99 235 / 0.2); }}
        .latest-badge {{ background: rgba(255,255,255,0.2); color: white; padding: 0.3rem 0.9rem; border-radius: 20px; display: inline-block; margin-bottom: 1rem; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
        .latest-post-title {{ font-size: 1.7rem; font-weight: 800; margin-bottom: 0.875rem; letter-spacing: -0.01em; }}
        .read-latest-btn {{ background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.35); padding: 0.65rem 1.5rem; border-radius: 25px; text-decoration: none; display: inline-block; transition: all 0.25s; font-weight: 600; font-size: 0.875rem; }}
        .read-latest-btn:hover {{ background: rgba(255,255,255,0.3); transform: translateY(-2px); }}
        .older-posts-section {{ background: white; border-radius: 20px; padding: 2rem; box-shadow: 0 4px 16px rgb(0 0 0 / 0.06); border: 1px solid #e2e8f0; }}
        .older-posts-title {{ font-size: 0.8rem; font-weight: 700; margin-bottom: 1.25rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
        .older-post-item {{ border: 1px solid #f1f5f9; border-radius: 12px; margin-bottom: 0.65rem; transition: all 0.2s; }}
        .older-post-item:hover {{ border-color: #2563eb; box-shadow: 0 4px 12px rgb(37 99 235 / 0.08); }}
        .older-post-link {{ display: block; padding: 1rem 1.25rem; text-decoration: none; color: inherit; }}
        .older-post-title {{ font-size: 0.95rem; font-weight: 600; color: #2563eb; margin-bottom: 0.25rem; }}
        .older-post-date {{ font-size: 0.78rem; color: #94a3b8; }}
        .no-posts-message {{ text-align: center; padding: 2rem; color: #94a3b8; }}
        .blog-tagline {{ font-size: 0.95rem; opacity: 0.85; margin-top: 0.5rem; }}
        @media (max-width: 640px) {{
            h1 {{ font-size: 2rem; }}
            .container {{ padding: 1rem; }}
            .latest-post-section {{ padding: 1.5rem; }}
            .latest-post-title {{ font-size: 1.35rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com" class="nav-link">&#8592; Back to Homepage</a>
        </div>
    </nav>
    <div class="container">
        <header>
            <h1>AI Insights Blog</h1>
            <p>Monthly intelligence for Canadian business leaders</p>
            <p class="blog-tagline">by Robert Simon &mdash; Montreal, QC</p>
        </header>
        <section class="latest-post-section">
            <div class="latest-badge">Latest Issue</div>
            <h2 class="latest-post-title">{latest['title']}</h2>
            <div style="margin-bottom: 0.875rem; opacity: 0.85; font-size: 0.85rem;">{latest['date']}</div>
            <p style="line-height: 1.65; margin-bottom: 1.5rem; opacity: 0.9; font-size: 0.9rem;">{latest['excerpt']}</p>
            <a href="/blog/posts/latest.html" class="read-latest-btn">Read This Month\'s Issue &#8594;</a>
        </section>
        <section class="older-posts-section">
            <h3 class="older-posts-title">Previous Issues</h3>
            <div class="older-posts-grid">{older_html}</div>
        </section>
    </div>
</body>
</html>'''


def update_blog_index():
    posts_dir  = "blog/posts"
    index_file = "blog/index.html"
    if not os.path.exists(posts_dir):
        return []

    latest_path = os.path.join(posts_dir, "latest.html")
    posts = []
    if os.path.exists(latest_path) and os.path.getsize(latest_path) > 100:
        try:
            info = extract_post_info(latest_path)
            if info:
                info['filename'] = 'latest.html'
                posts.append(info)
        except Exception as e:
            print(f"Warning: could not read latest.html: {e}")

    html_files = [
        f for f in os.listdir(posts_dir)
        if f.endswith(".html") and f not in ("latest.html", "index.html")
        and not f.startswith("{") and '{' not in f
    ]
    for fname in sorted(html_files, reverse=True):
        try:
            info = extract_post_info(os.path.join(posts_dir, fname))
            if info:
                posts.append(info)
        except Exception:
            continue

    if not posts:
        return []

    seen, deduped = set(), []
    for post in posts:
        try:
            d   = datetime.strptime(post['date'], "%B %d, %Y")
            key = d.strftime("%Y-%m")
        except Exception:
            key = post['date']
        if key not in seen:
            deduped.append(post)
            seen.add(key)

    idx_html = create_blog_index_html(deduped)
    if idx_html:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(idx_html)
        print(f"Blog index updated ({len(deduped)} issues).")
    return deduped


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic",  help="Custom topic / focus directive (optional)")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"])
    args = parser.parse_args()

    print("=== Blog Generator ===")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        sys.exit(1)

    try:
        result     = generate_blog_with_gemini(api_key, args.topic)
        month_year = datetime.now().strftime("%B %Y")
        title, excerpt = extract_title_and_excerpt(result["content"], month_year)

        print(f"Title:   {title}")
        print(f"Excerpt: {excerpt[:80]}...")

        html_content = create_html_blog_post(result["content"], title, excerpt)

        iso_date   = datetime.now().strftime("%Y-%m-%d")
        filename   = f"{iso_date}-{clean_filename(title)}.html"
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)

        out_path = os.path.join(output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            f.flush()
            os.fsync(f.fileno())
        print(f"Saved: {out_path}")

        if args.output == "posts":
            latest_path = os.path.join("blog", "posts", "latest.html")
            os.makedirs(os.path.dirname(latest_path), exist_ok=True)
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                f.flush()
                os.fsync(f.fileno())
            print("Updated latest.html")
        else:
            print("Staging mode — latest.html NOT updated (production unchanged)")

        import time; time.sleep(0.2)

        if args.output == "posts":
            update_blog_index()
            print("Blog index updated.")
        else:
            print("Staging mode — blog/index.html NOT updated (production unchanged)")

        print("SUCCESS.")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
