#!/usr/bin/env python3
"""
redraft_section.py
Sends ONE section of a staged issue back to Gemini and swaps the result into the
staging file in place.

The preview page can already replace From Robert's Desk with text Robert types
himself (inject_take.py). This is the other half: asking the model for a
different draft of a section, optionally with a note about what to change,
without regenerating the whole issue and losing the parts that were already
good.

Only the judgment sections are redraftable — the Desk, the executive summary,
the myth, the predictions, the closing question. The reported sections are not,
on purpose: those items went through date rules, source-quality rules and
deduplication in the monthly run, and a one-section rewrite has none of that
context. The redraft call is also ungrounded, so it can sharpen an argument but
cannot introduce an event that was never sourced.

    python3 scripts/redraft_section.py <html_path> "<SECTION KEY>" "<guidance>" [--month "August 2026"]

Exit codes: 0 on success, 1 on failure. The staging file is only written once a
redraft has been parsed and rendered successfully, so a failed run leaves the
issue exactly as it was.
"""

import argparse
import json
import os
import re
import sys
from html import escape as escape_html

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))

from utils import clean_ai_content
from gemini import REDRAFTABLE_SECTIONS, generate_section_redraft
from parser import parse_list_items, parse_myth, parse_predictions, parse_question
from renderer import (
    _build_summary_section, _build_myth_section,
    _build_predictions_section, _build_question_section, _build_roberts_desk,
    faq_plain, faq_join,
)


# Which block in the rendered page each section owns, and how to turn the
# model's plain text back into that block. Parsing returns None (or empty) when
# the redraft does not satisfy the section's format — that is a hard failure
# rather than something to paper over, because a half-parsed section would
# publish as a gap in the page.
SECTION_BLOCKS = {
    "FROM ROBERTS DESK": {
        "block_class": "desk-section",
        "parse":       lambda t: t if len(t.strip()) >= 120 else None,
        "render":      lambda v: _build_roberts_desk(v),
    },
    "EXECUTIVE SUMMARY": {
        "block_class": "summary-section",
        "parse":       lambda t: (parse_list_items(t, min_length=25)[:3] or None),
        "render":      lambda v: _build_summary_section(v),
    },
    "AI MYTH OF THE MONTH": {
        "block_class": "myth-section",
        "parse":       parse_myth,
        "render":      lambda v: _build_myth_section(v),
    },
    "LOOKING AHEAD: THREE PREDICTIONS": {
        "block_class": "pred-section",
        "parse":       lambda t: (parse_predictions(t) or None),
        "render":      lambda v: _build_predictions_section(v),
    },
    "ONE QUESTION FOR YOUR LEADERSHIP TEAM": {
        "block_class": "question-section",
        "parse":       lambda t: (parse_question(t) or None),
        "render":      lambda v: _build_question_section(v),
    },
}

# Two of the redraftable sections are also quoted in the FAQ, which is rendered
# on the page AND duplicated into FAQPage schema. Rewriting the section without
# refreshing both would leave the schema asserting an answer that is no longer
# anywhere on the page — the exact structured-data mismatch the FAQ was built to
# avoid. The question text must match renderer.py's faq_candidates verbatim.
FAQ_FED_BY = {
    "AI MYTH OF THE MONTH": {
        "question": "What is the biggest misconception executives have about AI adoption?",
        "answer":   lambda v: faq_plain(v["reality"]),
    },
    "LOOKING AHEAD: THREE PREDICTIONS": {
        "question": "What should Canadian executives expect from AI over the next year?",
        "answer":   lambda v: faq_join([f'{p["horizon"]}: {p["body"]}' for p in v]),
    },
}

_DIV_TOKEN = re.compile(r'<div\b|</div\s*>', re.IGNORECASE)


def update_faq(html, question, answer):
    """Rewrite one FAQ answer in both places it lives: the visible .faq-a and
    the FAQPage JSON-LD. Returns (html, changed_count)."""
    if not answer:
        return html, 0
    changed = 0

    visible = re.compile(
        r'(<h3 class="faq-q">' + re.escape(escape_html(question, quote=False))
        + r'</h3>\s*<p class="faq-a">)(.*?)(</p>)', re.S
    )
    html, n = visible.subn(
        lambda m: m.group(1) + escape_html(answer, quote=False) + m.group(3), html
    )
    changed += n

    schema = re.compile(
        r'(\{"@type":"Question","name":' + re.escape(json.dumps(question))
        + r',"acceptedAnswer":\{"@type":"Answer","text":)(".*?")(\}\})'
    )
    html, n = schema.subn(lambda m: m.group(1) + json.dumps(answer) + m.group(3), html)
    changed += n

    return html, changed


def find_block(html, block_class):
    """Span of the <div class="section X"> ... </div> that owns `block_class`.

    Counts div tokens rather than pattern-matching the whole block: these
    sections nest divs several deep and a non-greedy regex would stop at the
    first inner </div>. Nothing inside them opens a div that is not closed —
    the inline SVGs contain no divs — so the count is exact.

    Returns (start, end) or None.
    """
    opening = re.search(
        r'<div\s+class="[^"]*\b' + re.escape(block_class) + r'\b[^"]*"[^>]*>',
        html
    )
    if not opening:
        return None

    depth = 0
    for token in _DIV_TOKEN.finditer(html, opening.start()):
        if token.group(0).lower().startswith('<div'):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return opening.start(), token.end()
    return None


def redraft(path, section, guidance="", month_year=None):
    if section not in SECTION_BLOCKS:
        print(f"  '{section}' is not redraftable. Choose one of: "
              f"{', '.join(SECTION_BLOCKS)}")
        return False

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  GEMINI_API_KEY is not set.")
        return False

    with open(path, encoding="utf-8") as f:
        html = f.read()

    cfg  = SECTION_BLOCKS[section]
    span = find_block(html, cfg["block_class"])
    if not span:
        print(f"  No .{cfg['block_class']} block in {os.path.basename(path)} — "
              f"nothing to replace, leaving the file untouched.")
        return False

    issue_text = extract_issue_text(html)
    if len(issue_text) < 300:
        print("  Could not read the issue body to use as context.")
        return False

    label = REDRAFTABLE_SECTIONS[section]["label"]
    print(f"  Redrafting '{label}'"
          + (f" with guidance: {guidance.strip()[:90]}" if guidance.strip() else " (no guidance)"))

    text, model = generate_section_redraft(
        api_key, section, issue_text, guidance=guidance, month_year=month_year
    )
    text = clean_ai_content(text)

    parsed = cfg["parse"](text)
    if not parsed:
        print(f"  The redraft did not match the format '{label}' requires "
              f"({len(text)} chars returned). Leaving the issue unchanged.")
        return False

    new_block = cfg["render"](parsed)
    start, end = span
    html = html[:start] + new_block + html[end:]

    # Keep the FAQ and its schema in step with the section they quote.
    faq = FAQ_FED_BY.get(section)
    if faq:
        html, changed = update_faq(html, faq["question"], faq["answer"](parsed))
        if changed == 2:
            print("  FAQ answer and FAQPage schema refreshed to match.")
        elif changed:
            print(f"  WARNING: refreshed only {changed}/2 FAQ copies — the visible "
                  f"answer and the schema may now disagree.")
        else:
            print("  Note: this issue has no FAQ entry for that section; nothing to sync.")

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  '{label}' redrafted by {model} ({len(text.split())} words).")
    return True


def extract_issue_text(html):
    """The issue as plain text, for the model to work from.

    The share row, survey call to action and FAQ are stripped: they are
    interface and derived copy rather than the issue's argument, and the FAQ in
    particular is assembled FROM the other sections, so leaving it in would feed
    the model the same content twice.
    """
    article = re.search(
        r'<div class="article-content"[^>]*>(.*?)</article>', html, re.S
    )
    body = article.group(1) if article else html

    for cls in ("share-row", "survey-cta", "faq-section"):
        span = find_block(body, cls)
        while span:
            body = body[:span[0]] + body[span[1]:]
            span = find_block(body, cls)

    body = re.sub(r'<(script|style)\b.*?</\1>', ' ', body, flags=re.S | re.I)
    body = re.sub(r'<[^>]+>', '\n', body)
    body = re.sub(r'&#8220;|&#8221;', '"', body)
    body = re.sub(r'&#39;|&#x27;', "'", body)
    body = re.sub(r'&amp;', '&', body)
    body = re.sub(r'&mdash;|&#8212;', '—', body)
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n\s*\n+', '\n', body)
    return body.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Staging HTML file to rewrite in place")
    ap.add_argument("section", help="Section key, e.g. 'FROM ROBERTS DESK'")
    ap.add_argument("guidance", nargs="?", default="",
                    help="Optional note on what to change")
    ap.add_argument("--month", default=None, help="Issue month, e.g. 'September 2026'")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"  No such file: {args.path}")
        sys.exit(1)

    try:
        ok = redraft(args.path, args.section.strip(), args.guidance or "", args.month)
    except Exception as e:
        # A failed redraft must never destroy a draft that was fine before it.
        print(f"  Redraft failed ({e}). The issue is unchanged.")
        sys.exit(1)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
