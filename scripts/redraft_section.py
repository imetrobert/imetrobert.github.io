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
the predictions, the closing question. The reported sections are not,
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
from parser import parse_list_items, parse_predictions, parse_question
from renderer import (
    _build_summary_section,
    _build_predictions_section, _build_question_section, _build_roberts_desk,
    faq_plain, faq_join,
)


# The Desk used to accept any text of 120+ characters, which let a model's
# reasoning notes (a "constraint checklist") through as the section. The Desk is
# specified at 300-450 words of first-person prose, so anything short, cut off
# mid-sentence, or shaped like a checklist is a failed redraft, not a draft.
_DESK_JUNK = (
    "no invented specifics", "opinionated language used",
    "constraint checklist", "confidence score",
)


def parse_desk(text):
    t = (text or "").strip()
    if any(marker in t.lower() for marker in _DESK_JUNK):
        return None
    if len(t.split()) < 200:
        return None
    if t[-1] not in '.!?"\u201d\u2019)':
        return None
    return t


# Which block in the rendered page each section owns, and how to turn the
# model's plain text back into that block. Parsing returns None (or empty) when
# the redraft does not satisfy the section's format — that is a hard failure
# rather than something to paper over, because a half-parsed section would
# publish as a gap in the page.
SECTION_BLOCKS = {
    "FROM ROBERTS DESK": {
        "block_class": "desk-section",
        "parse":       parse_desk,
        "render":      lambda v: _build_roberts_desk(v),
    },
    "EXECUTIVE SUMMARY": {
        "block_class": "summary-section",
        "parse":       lambda t: ((lambda items: items[:3] if len(items) >= 3 else None)(parse_list_items(t, min_length=25))),
        "render":      lambda v: _build_summary_section(v),
    },
    "LOOKING AHEAD: THREE PREDICTIONS": {
        "block_class": "pred-section",
        "parse":       lambda t: ((lambda items: items if len(items) == 3 else None)(parse_predictions(t))),
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
    "LOOKING AHEAD: THREE PREDICTIONS": {
        "question": "What should small Canadian businesses expect from AI over the next year?",
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


# ---------------------------------------------------------------------------
# Quality gates. A redraft is applied only if it passes all of these; otherwise the issue is left
# exactly as it was and the failure is explained (runlog.py) and retried once with the reason.
# ---------------------------------------------------------------------------
MAX_ATTEMPTS = 2
SIMILARITY_LIMIT = 0.80      # word-sequence similarity to the CURRENT text above which a draft counts as unchanged
MIN_WORDS = {
    "FROM ROBERTS DESK": 200,
    "EXECUTIVE SUMMARY": 30,                       # spec: exactly 3 items of up to 25 words
    "LOOKING AHEAD: THREE PREDICTIONS": 36,        # spec: three horizons, 1-2 sentences each
    "ONE QUESTION FOR YOUR LEADERSHIP TEAM": 10,   # spec: one question
}
# Structural junk is rejected anywhere in the text; conversational openers only at the start (first-person
# prose in the Desk can legitimately say "I can't" or "sure," mid-sentence).
_JUNK_ANYWHERE = (
    "constraint checklist", "confidence score", "no invented specifics", "opinionated language used",
    "as an ai language model", "```", "<div", "</", "**", "[source", "(source:", "http://", "https://",
)
_JUNK_OPENERS = ("sure", "certainly", "here is", "here's", "here are", "okay", "of course", "i cannot", "i can't",
                 "i'm sorry", "i am sorry", "as an ai")


def block_text(html_fragment):
    """Plain text of a rendered block, for comparing old and new."""
    t = re.sub(r'<(script|style)\b.*?</\1>', ' ', html_fragment, flags=re.S | re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'&[a-z#0-9]+;', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def similarity(a, b):
    """0..1 similarity of two texts by word sequence (1 = identical)."""
    import difflib
    wa, wb = a.lower().split(), b.lower().split()
    if not wa or not wb:
        return 0.0
    return difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio()


def check_text(section, text, old_text):
    """Return (code, reason) if the model's raw text must be rejected, else (None, '')."""
    t = (text or "").strip()
    low = t.lower()
    for marker in _JUNK_ANYWHERE:
        if marker in low:
            return "JUNK_OUTPUT", f"it contains '{marker.strip()}', which belongs to notes or chat, not the section"
    for opener in _JUNK_OPENERS:
        if low.startswith(opener):
            return "JUNK_OUTPUT", f"it opens like a chat reply ('{opener}...') instead of the section itself"
    if len(t.split()) < MIN_WORDS.get(section, 12):
        return "TOO_SHORT", f"only {len(t.split())} words; this section needs at least {MIN_WORDS.get(section, 12)}"
    if old_text and similarity(t, old_text) >= SIMILARITY_LIMIT:
        return "TOO_SIMILAR", "it repeats the current text almost word for word; write a clearly different angle"
    return None, ""


def verify_written(path, before_html, after_html, cfg, new_block_text):
    """Re-read the file after writing. Returns a list of problems (empty = fine)."""
    problems = []
    with open(path, encoding="utf-8") as f:
        on_disk = f.read()
    if on_disk != after_html:
        problems.append("file on disk differs from what was just written")
    if len(_DIV_TOKEN.findall(on_disk)) % 2 != 0 or \
       on_disk.lower().count("<div") != on_disk.lower().count("</div"):
        problems.append("div tags are no longer balanced")
    span = find_block(on_disk, cfg["block_class"])
    if not span:
        problems.append(f".{cfg['block_class']} block missing after the edit")
    elif block_text(on_disk[span[0]:span[1]]) != new_block_text:
        problems.append("the block on disk is not the new draft")
    for cls in ("share-row", "faq-section"):
        if find_block(before_html, cls) and not find_block(on_disk, cls):
            problems.append(f"the {cls} block disappeared")
    if before_html.count("application/ld+json") != on_disk.count("application/ld+json"):
        problems.append("the structured-data (JSON-LD) blocks changed count")
    return problems


def redraft(path, section, guidance="", month_year=None):
    import runlog
    kind = "redraft"
    base = os.path.basename(path)

    if section not in SECTION_BLOCKS:
        runlog.fail(kind, "SECTION_NOT_REDRAFTABLE", f"'{section}'. Choose one of: {', '.join(SECTION_BLOCKS)}",
                    section=section, file=base)
        return False

    if not os.getenv("GEMINI_API_KEY"):
        runlog.fail(kind, "NO_API_KEY", "GEMINI_API_KEY is empty in this run", section=section, file=base)
        return False
    api_key = os.getenv("GEMINI_API_KEY")

    with open(path, encoding="utf-8") as f:
        html = f.read()

    cfg = SECTION_BLOCKS[section]
    span = find_block(html, cfg["block_class"])
    if not span:
        runlog.fail(kind, "BLOCK_NOT_FOUND", f"no .{cfg['block_class']} block in {base}", section=section, file=base)
        return False

    issue_text = extract_issue_text(html)
    if len(issue_text) < 300:
        runlog.fail(kind, "UNEXPECTED", "could not read the issue body to use as context (under 300 characters)",
                    section=section, file=base)
        return False

    old_text = block_text(html[span[0]:span[1]])
    label = REDRAFTABLE_SECTIONS[section]["label"]
    print(f"  Redrafting '{label}'"
          + (f" with guidance: {guidance.strip()[:90]}" if guidance.strip() else " (no guidance)"))

    parsed, text, model, last = None, "", "", ("FORMAT_MISMATCH", "")
    note = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"  Attempt {attempt}/{MAX_ATTEMPTS}")
        try:
            text, model = generate_section_redraft(
                api_key, section, issue_text, guidance=guidance, month_year=month_year, retry_note=note
            )
        except Exception as e:
            code = runlog.classify(e)
            last = (code, str(e))
            print(f"  The model call failed ({code}): {str(e)[:200]}")
            # A key problem or a missing grounded answer will not improve on a second try.
            if code in ("API_KEY_REJECTED", "NO_API_KEY", "UNGROUNDED_REJECTED") or attempt == MAX_ATTEMPTS:
                break
            note = ""
            continue
        text = clean_ai_content(text)
        code, reason = check_text(section, text, old_text)
        if code:
            last = (code, reason)
            print(f"  Rejected by the quality check: {reason}.")
            note = reason
            continue
        parsed = cfg["parse"](text)
        if not parsed:
            last = ("FORMAT_MISMATCH", f"{len(text)} characters returned that do not fit the format '{label}' requires")
            print(f"  Rejected: {last[1]}.")
            note = last[1] + ". Follow the format in the specification exactly."
            continue
        break

    if not parsed:
        runlog.fail(kind, last[0], last[1], section=section, file=base, model=model)
        print("  The issue is unchanged.")
        return False

    new_block = cfg["render"](parsed)
    start, end = span
    new_html = html[:start] + new_block + html[end:]

    # Keep the FAQ and its schema in step with the section they quote.
    faq = FAQ_FED_BY.get(section)
    if faq:
        new_html, changed = update_faq(new_html, faq["question"], faq["answer"](parsed))
        if changed == 2:
            print("  FAQ answer and FAQPage schema refreshed to match.")
        elif changed:
            print(f"  WARNING: refreshed only {changed}/2 FAQ copies — the visible "
                  f"answer and the schema may now disagree.")
        else:
            print("  Note: this issue has no FAQ entry for that section; nothing to sync.")

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)

    new_block_text = block_text(new_block)
    problems = verify_written(path, html, new_html, cfg, new_block_text)
    if problems:
        with open(path, "w", encoding="utf-8") as f:      # roll back: a half-good edit must not stay
            f.write(html)
        runlog.fail(kind, "VERIFY_FAILED", "; ".join(problems), section=section, file=base, model=model)
        print("  The edit was rolled back; the issue is unchanged.")
        return False

    sim = similarity(new_block_text, old_text)
    runlog.ok(kind, f"'{label}' redrafted by {model} ({len(text.split())} words, "
                    f"{round((1 - sim) * 100)}% different from before).",
              section=section, file=base, model=model, words=len(text.split()))
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
