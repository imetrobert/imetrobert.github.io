"""
gemini.py
Gemini API integration and prompt construction for the monthly blog generator.
"""

import time
import requests
from datetime import datetime, timedelta
from utils import clean_ai_content


def generate_blog_with_gemini(api_key, topic=None):
    current_date = datetime.now()
    month_year   = current_date.strftime("%B %Y")
    prev_month   = (current_date.replace(day=1) - timedelta(days=1)).strftime("%B %Y")

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
    rules = _shared_rules_block(month_year, prev_month)
    return f"""You are writing the monthly AI insights newsletter for Robert Simon — an independent AI thought leader based in Montreal, QC, Canada. Robert has 25+ years in digital transformation and is known for direct, opinionated takes on AI adoption.

AUDIENCE
Canadian business leaders — C-suite, VPs, and directors at mid-to-large Canadian enterprises in financial services, retail, manufacturing, telecom, and healthcare. They are time-pressed and want signal, not noise.

CONTENT FOCUS DIRECTIVE:
{topic}

This directive changes WHAT events and examples you select and emphasise. It does NOT change the structure, section counts, formatting rules, or citation requirements. All structural rules below are mandatory and unchanged.

{rules}"""


def _shared_rules_block(month_year, prev_month):
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

SOURCE QUALITY RULE: Only cite primary sources — official company blogs, government press releases, major news outlets (Globe and Mail, Financial Post, CBC, Reuters, Bloomberg, TechCrunch, The Verge, Wired). Do NOT cite newsletters, podcast episodes, Substack posts, or aggregator summaries. If a result looks like "26: GPT-5.5, Claude Mythos & What It Means" or "Episode 14: ..." it is a newsletter/podcast — skip it and find the original primary source instead.

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
CRITICAL SECTION ROUTING RULE: KEY AI DEVELOPMENTS is strictly for AI company announcements — products, models, partnerships, research. It must NEVER contain items from any government entity. This includes: the Government of Canada, any provincial or municipal government, the Prime Minister, any federal minister, any G7/G20/OECD ministerial body, Statistics Canada, Bank of Canada policy announcements, or any Crown corporation acting in a regulatory/policy capacity. Any government funding, policy, regulation, or strategy announcement MUST go in CANADIAN SPOTLIGHT — never here.
CRITICAL SOURCE RULE: Every single item MUST end with a Source line. No exceptions.
CRITICAL SOURCE QUALITY RULE: Every source MUST be a primary source — official company announcements, government press releases, or major news publications. Newsletters, podcast episodes, Substack posts, and aggregator blogs are NEVER acceptable sources. If your search returns a newsletter item (e.g. "26: GPT-5.5..." or "Episode 14:..."), discard it and find the original primary source announcement instead.
CRITICAL DEDUPLICATION RULE: Treat KEY AI DEVELOPMENTS and CANADIAN SPOTLIGHT as one combined list. Every individual news event, funding program, company announcement, or policy decision may appear ONCE across both sections combined — never twice. Same program = same event = one section only. If the AI Compute Access Fund, RAII, or any government initiative appears in KEY AI DEVELOPMENTS, it must NOT appear in CANADIAN SPOTLIGHT under any name, wording, or angle. No exceptions.

Use this EXACT format for every item — copy it precisely:
[Month Day]: [Company] — [One sentence: what they did]. [One sentence: why it matters for Canadian business]. Source: [Publication name] | [Exact article headline as published]

Example of correct format:
May 15: Google — Released Gemini 3.1 with enhanced reasoning for enterprise. Canadian financial services firms can now deploy it within existing Google Workspace contracts. Source: The Verge | Google Releases Gemini 3.1 With Stronger Reasoning

Rules:
- MINIMUM 8 items. Aim for 8-10.
- Every item has a date from {month_year}
- Every item ends with Source: [Publication] | [Headline] — no URLs, no brackets around the headline
- Every source is a PRIMARY source (company blog, government site, major news outlet) — NEVER a newsletter or podcast
- Vary the companies — mix US tech, Canadian companies, global players
- The Canadian relevance sentence must be specific, not generic
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
- MINIMUM 3 items. Aim for 3-4.
- No generic "Canada is positioning itself" filler
- Every item ends with Source: [Publication] | [Headline]
- Every source is a PRIMARY source — NEVER a newsletter or podcast

MANDATORY SELF-CHECK — DO THIS BEFORE WRITING ANY FURTHER:
List every news event you have written in KEY AI DEVELOPMENTS (by topic, one line each).
Then list every news event in CANADIAN SPOTLIGHT (by topic, one line each).
Compare the two lists. If ANY topic appears in both lists — even described with different words — you MUST go back and replace the duplicate in CANADIAN SPOTLIGHT with a genuinely different Canadian news item before continuing.
Only continue to WHAT THIS MEANS once every item across both sections is a unique, non-overlapping news event.

WHAT THIS MEANS FOR CANADIAN BUSINESS (3 paragraphs):
CRITICAL CROSS-REFERENCE RULE: Every paragraph MUST name at least one specific event, company, or statistic from KEY AI DEVELOPMENTS, CANADIAN SPOTLIGHT, or ADOPTION SNAPSHOT above.

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

Each action must:
- Start with a strong verb: Audit, Pilot, Negotiate, Commission, Assign, Test, Require, Demand, Sunset, Block time to
- Name the specific development, company, tool, regulation, or funding program it responds to
- State WHO in the organization owns it (CTO, CFO, CHRO, Legal team, Board Audit Committee, etc.)
- Include a specific deadline (this week / by end of Q2 / before June 30 / within 30 days)
- Be 2-3 sentences

Format: 1. [Action text]

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

ROBERTS TAKE:
CRITICAL: This is NOT a summary of the newsletter. Robert speaks in first person with a direct, opinionated voice. He references 1-2 specific items from KEY AI DEVELOPMENTS or CANADIAN SPOTLIGHT and offers a take that a reader would NOT get from reading those items alone.

Write 2-3 sentences. Start with "The [thing] that surprised me most this month was..." or "What I keep hearing from Canadian leaders right now is..." or similar first-person opener. Never start with "This month" or "The AI landscape".

Do NOT write the placeholder. Write actual content that Robert would say based on the specific news reported above.

---
Context: {month_year} edition"""
