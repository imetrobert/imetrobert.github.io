#!/usr/bin/env python3
"""
generate-preview-page.py
Generates blog/staging/preview.html — the approval UI Robert visits to review,
regenerate with a prompt, or approve and publish his monthly blog post.
"""

import argparse
import os
import sys
import json
from datetime import datetime

# Ensure scripts/ is on the path so `from utils import ...` resolves whether
# this runs via `python3 scripts/generate-preview-page.py` (repo root) or
# `cd scripts && python3 generate-preview-page.py` (as regenerate-blog.yml does).
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))

from utils import get_issue_labels
from gemini import REDRAFTABLE_SECTIONS

import re as _re
from html import escape as html_escape, unescape as html_unescape

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


def _limit_prompt_block(ident, dark=False):
    """A prompt to paste into ChatGPT or Gemini to look the limits up.

    Replaces the step-by-step console instructions that used to sit here.
    Those told the reviewer where to click; this hands them something that
    answers the question directly, names the exact models in play, and asks
    for uncertainty to be stated rather than guessed — which matters, because
    a confidently wrong RPD figure drives a quota bar that is also wrong.
    """
    muted = "opacity:0.85;" if dark else "color:#64748b;"
    bg    = "#451a03" if dark else "#0f172a"
    bd    = "#a16207" if dark else "#334155"
    fg    = "#fde68a" if dark else "#e2e8f0"
    return f"""
          <details style="margin-top:0.4rem;">
            <summary style="cursor:pointer;font-size:0.66rem;{muted}">
              Get a prompt to look these limits up
            </summary>
            <p style="font-size:0.63rem;{muted}line-height:1.5;margin:0.4rem 0 0.3rem;">
              Paste this into ChatGPT or the Gemini app, then type the numbers above.
            </p>
            <textarea id="{ident}-text" readonly rows="7" style="width:100%;font-size:0.63rem;
                      font-family:ui-monospace,monospace;line-height:1.45;padding:0.4rem;
                      border-radius:5px;border:1px solid {bd};background:{bg};color:{fg};
                      resize:vertical;"></textarea>
            <button class="btn btn-secondary" id="{ident}-copy" style="width:100%;margin-top:0.35rem;"
                    onclick="copyLimitPrompt('{ident}')">Copy prompt</button>
          </details>"""


def _model_daily_limits():
    """Free-tier requests per day, per model. Defaults only — the panel lets
    each be overridden, since quotas are assigned per Google Cloud project."""
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from utils import MODEL_DAILY_LIMITS
        return dict(MODEL_DAILY_LIMITS)
    except Exception:
        return {}


def _quota_snapshot():
    """Requests this pipeline has made in the current quota day.

    Baked in as a fallback only — the page re-fetches the ledger on load, so a
    page cached from an earlier run still shows a current number.
    """
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from utils import requests_today
        reqs, _toks = requests_today()
        return reqs
    except Exception:
        return 0


def _generated_stamp():
    """When this draft was generated, in Robert's timezone.

    The runner is UTC, so an unlabelled date on this page is ambiguous — and
    with several drafts generated on the same day it is the time, not the date,
    that tells you which one you are looking at. %Z gives EDT or EST, so the
    label is right on both sides of the DST switch.

    Falls back to UTC if tzdata is unavailable; a stamp in the wrong zone,
    clearly labelled, beats no stamp.
    """
    now = datetime.now()
    if ZoneInfo is not None:
        try:
            now = datetime.now(ZoneInfo("America/Toronto"))
        except Exception:
            return datetime.utcnow().strftime("%B %-d, %Y at %H:%M UTC").replace(" 0", " ")
    hour = now.strftime("%I").lstrip("0") or "12"
    return f"{now.strftime('%B')} {now.day}, {now.year} at {hour}:{now.strftime('%M %p')} {now.strftime('%Z') or 'ET'}"


def _extract_desk_draft(staging_filename: str) -> str:
    """Pull the drafted 'From Robert's Desk' prose back out of the staged post.

    The reviewer edits this section in a plain textarea, so what comes out here
    has to be plain text: tags stripped, entities decoded, paragraphs separated
    by a blank line — the same shape inject_take.py expects to be handed back.

    Returns "" for anything unexpected (file missing, placeholder box instead of
    a draft, path resolved differently by a caller that runs from scripts/).
    An empty editor is a worse experience but a safe one; failing here must
    never take the whole approval page down with it.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "blog", "staging", staging_filename)
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return ""

    paragraphs = []
    for raw in _re.findall(r'<p class="roberts-body">(.*?)</p>', src, _re.S):
        text = html_unescape(_re.sub(r'<[^>]+>', '', raw))
        text = _re.sub(r'\s+', ' ', text).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def build_preview_html(staging_filename: str, month_year: str, run_id: str, regenerated: bool = False) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "imetrobert/imetrobert.github.io")

    # `month_year` arrives from the workflow as the COVERAGE month (the real
    # calendar month at generation time, e.g. "June 2026" for a post
    # generated June 30 covering June's news). Derive the reader-facing
    # ISSUE month from it here so this review screen always matches what
    # will actually appear on the published post — see utils.get_issue_labels().
    try:
        coverage_date = datetime.strptime(month_year, "%B %Y")
        issue_labels  = get_issue_labels(coverage_date)
        issue_month_year     = issue_labels["issue_month_year"]
        coverage_month_year  = issue_labels["coverage_month_year"]
        coverage_month_name  = issue_labels["coverage_month_name"]
    except (ValueError, TypeError):
        # Unexpected format — fall back to showing the raw value as-is
        # rather than failing the whole preview page generation.
        issue_month_year    = month_year
        coverage_month_year = month_year
        coverage_month_name = month_year

    # The URL this issue will live at once published. approve-blog.yml promotes
    # the staging file to blog/posts/ under the same name, so it is knowable now
    # — which is what lets the reviewer copy a share link without hunting for it
    # after the fact, and without reaching for latest.html.
    permalink = f"https://www.imetrobert.com/blog/posts/{staging_filename}"
    permalink_json = json.dumps(permalink)

    # Build the wave form from the live survey config, so adding or renaming a
    # question in data/survey.json changes the form without touching this file.
    try:
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(_root, "data", "survey.json"), encoding="utf-8") as _f:
            _cfg = json.load(_f)
        survey_questions_json = json.dumps(
            [{"id": q["id"], "text": q["text"], "options": q["options"]}
             for q in _cfg.get("questions", [])]
        )
        _has_form = bool((_cfg.get("form_url") or "").strip())
    except Exception:
        survey_questions_json = "[]"
        _has_form = False

    # The wave form is hidden until a form_url exists. Until one does there are
    # no responses to type in, so the section is a control that cannot be used —
    # and this screen is reviewed on a phone, where an unusable control is not
    # neutral, it is something to scroll past every month. It reappears by
    # itself the moment data/survey.json points at a real form.
    # Same reasoning as the section itself: do not advertise a step that cannot
    # happen. With no form there is no wave to record.
    survey_bullet = ("<li>Record your survey wave, if you entered one</li>"
                     if _has_form else "")
    survey_section = ""
    if _has_form:
        survey_section = (
            '<details class="sidebar-section survey-block sec-survey">'
            '<summary><h3 style="display:inline;">Survey results (optional)</h3></summary>'
            '<p class="take-hint">Type the counts from your form. Submitted with Approve, '
            'validated before it is recorded, and left alone entirely if you skip it.</p>'
            '<label class="survey-label">Wave label'
            f'<input type="text" id="wave-label" class="survey-input" placeholder="Wave 1 &mdash; {issue_month_year}">'
            '</label>'
            '<label class="survey-label">Total responses (n)'
            '<input type="number" id="wave-n" class="survey-input" min="1" placeholder="e.g. 68">'
            '</label>'
            '<div id="survey-questions"></div>'
            '<p class="take-hint" id="survey-status"></p>'
            '</details>'
        )

    regen_badge = ""
    if regenerated:
        regen_badge = '<div class="regen-badge">🔄 Regenerated with custom prompt</div>'

    # Built from gemini.REDRAFTABLE_SECTIONS rather than hardcoded, so this
    # picker cannot offer a section the redraft script does not know how to
    # rebuild. (The choice list in redraft-section.yml still has to be kept in
    # step by hand — GitHub Actions cannot generate workflow_dispatch options.)
    redraft_options = "".join(
        f'<option value="{html_escape(key, quote=True)}">'
        f'{html_escape(cfg["label"], quote=False)}</option>'
        for key, cfg in REDRAFTABLE_SECTIONS.items()
    )

    # Pre-load the editor with the model's draft of From Robert's Desk. The
    # section runs 300-450 words now; handed an empty box that often meant
    # shipping the model's version under Robert's byline, because rewriting
    # from nothing is a much bigger ask than editing. A localStorage draft
    # still wins over this — see initTake().
    generated_stamp = _generated_stamp()
    generated_stamp_json = json.dumps(generated_stamp)
    quota_baked = _quota_snapshot()
    quota_limits_json = json.dumps(_model_daily_limits())
    quota_help_light = _limit_prompt_block("quota-prompt", dark=False)
    quota_help_dark = _limit_prompt_block("model-prompt", dark=True)

    desk_draft = _extract_desk_draft(staging_filename)
    desk_draft_attr = html_escape(desk_draft)
    desk_draft_words = len(desk_draft.split())
    desk_draft_note = (
        f"Pre-filled with the model&#39;s {desk_draft_words}-word draft &mdash; "
        f"edit it into your own words."
        if desk_draft else
        "The model left this section empty. Whatever you type here is what publishes."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow">
  <!-- GitHub Pages serves this with a ten-minute max-age and no way to override
       the header, so a browser will happily show a stale approval screen. These
       help where they are honoured; the staleness check in JS is what actually
       catches it. -->
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <title>Review: {issue_month_year} Issue (covers {coverage_month_name}) — Robert Simon</title>
  <style>
    :root {{
      --blue:    #2563eb;
      --cyan:    #06b6d4;
      --navy:    #0f172a;
      --gray:    #475569;
      --light:   #f8fafc;
      --border:  #e2e8f0;
      --green:   #16a34a;
      --red:     #dc2626;
      --amber:   #d97706;
      --white:   #ffffff;
      --shadow:  0 4px 24px rgb(0 0 0 / 0.10);
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%);
      min-height: 100vh;
      color: var(--navy);
    }}
    .topbar {{
      background: var(--white);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 1px 4px rgb(0 0 0 / 0.06);
    }}
    .topbar-left {{ display: flex; align-items: center; gap: 1rem; }}
    .logo {{ font-weight: 800; font-size: 1.1rem; color: var(--blue); }}
    .issue-label {{
      background: linear-gradient(135deg, var(--blue), var(--cyan));
      color: white;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.2rem 0.7rem;
      border-radius: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .topbar-right {{ display: flex; gap: 0.75rem; align-items: center; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.6rem 1.25rem;
      border-radius: 10px;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      text-decoration: none;
    }}
    .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .btn-primary {{
      background: linear-gradient(135deg, var(--green), #15803d);
      color: white;
      box-shadow: 0 2px 8px rgb(22 163 74 / 0.3);
    }}
    .btn-primary:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgb(22 163 74 / 0.4); }}
    .btn-secondary {{
      background: linear-gradient(135deg, var(--blue), var(--cyan));
      color: white;
      box-shadow: 0 2px 8px rgb(37 99 235 / 0.2);
    }}
    .btn-secondary:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgb(37 99 235 / 0.3); }}
    .btn-outline {{
      background: white;
      color: var(--gray);
      border: 1px solid var(--border);
    }}
    .btn-outline:hover {{ border-color: var(--blue); color: var(--blue); }}
    .btn-discard-outline {{
      background: white;
      color: #b91c1c;
      border: 1px solid #fecaca;
    }}
    .btn-discard-outline:hover:not(:disabled) {{ border-color: var(--red); background: #fef2f2; }}
    .btn-force-refresh {{
      background: linear-gradient(135deg, #7c3aed, #6d28d9);
      color: white;
      box-shadow: 0 2px 8px rgb(124 58 237 / 0.3);
    }}
    .btn-force-refresh:hover {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgb(124 58 237 / 0.4); }}
    .btn-force-refresh.spinning svg {{
      animation: spin 0.7s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .layout {{
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 0;
      min-height: calc(100vh - 65px);
    }}
    .sidebar {{
      background: var(--white);
      border-right: 1px solid var(--border);
      padding: 1.75rem 1.5rem;
      overflow-y: auto;
      position: sticky;
      top: 65px;
      height: calc(100vh - 65px);
    }}
    .sidebar-section {{ margin-bottom: 2rem; }}
    .take-hint {{ font-size: 0.72rem; color: #64748b; line-height: 1.55; margin-bottom: 0.6rem; }}
    .take-meta {{ display: flex; justify-content: space-between; font-size: 0.68rem; color: #94a3b8; margin-top: 0.35rem; }}
    .take-saved {{ color: #16a34a; font-weight: 600; }}
    .perma-row {{ display: flex; align-items: center; gap: 0.5rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.5rem 0.6rem; }}
    .perma-row code {{ flex: 1; font-size: 0.66rem; word-break: break-all; color: #1e293b; }}
    .survey-block summary {{ cursor: pointer; list-style: none; }}
    .survey-block summary::-webkit-details-marker {{ display: none; }}
    .survey-block summary::before {{ content: "\25B8 "; color: #94a3b8; }}
    .survey-block[open] summary::before {{ content: "\25BE "; }}
    .survey-label {{ display: block; font-size: 0.7rem; font-weight: 600; color: #475569; margin: 0.5rem 0 0.15rem; }}
    .survey-input {{ width: 100%; padding: 0.4rem 0.55rem; border: 1px solid #e2e8f0; border-radius: 6px; font: inherit; font-size: 0.78rem; }}
    .survey-q {{ margin-top: 0.9rem; padding-top: 0.6rem; border-top: 1px dashed #e2e8f0; }}
    .survey-q-text {{ font-size: 0.72rem; font-weight: 700; color: #1e293b; margin-bottom: 0.3rem; }}
    .survey-opt {{ display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.25rem; }}
    .survey-opt span {{ flex: 1; font-size: 0.68rem; color: #475569; }}
    .survey-opt input {{ width: 4.5rem; padding: 0.25rem 0.4rem; border: 1px solid #e2e8f0; border-radius: 5px; font: inherit; font-size: 0.72rem; }}
    .sidebar-section h3 {{
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #94a3b8;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }}
    .status-card {{
      background: var(--light);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .status-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.8rem;
      margin-bottom: 0.5rem;
    }}
    .status-row:last-child {{ margin-bottom: 0; }}
    .status-label {{ color: var(--gray); }}
    .status-value {{ font-weight: 600; color: var(--navy); font-size: 0.78rem; }}
    .badge-pending {{
      background: #fef3c7;
      color: var(--amber);
      padding: 0.15rem 0.5rem;
      border-radius: 8px;
      font-size: 0.68rem;
      font-weight: 700;
    }}
    .pat-section input {{
      width: 100%;
      padding: 0.6rem 0.875rem;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 0.8rem;
      font-family: monospace;
      margin-bottom: 0.5rem;
      transition: border-color 0.2s;
      background: var(--light);
    }}
    .pat-section input:focus {{ outline: none; border-color: var(--blue); background: white; }}
    .pat-hint {{
      font-size: 0.72rem;
      color: #94a3b8;
      line-height: 1.5;
      margin-top: 0.25rem;
    }}
    .pat-hint a {{ color: var(--blue); }}
    .pat-saved {{ display: none; font-size: 0.75rem; color: var(--green); margin-top: 0.25rem; font-weight: 600; }}
    .pat-missing-banner {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 10px;
      padding: 0.875rem 1rem;
      margin-bottom: 0.75rem;
      font-size: 0.78rem;
      color: #991b1b;
      line-height: 1.55;
    }}
    .pat-missing-banner strong {{ display: block; margin-bottom: 0.3rem; color: #7f1d1d; }}
    .pat-missing-banner a.btn {{
      margin-top: 0.6rem;
      width: 100%;
      justify-content: center;
      background: linear-gradient(135deg, var(--red), #b91c1c);
      color: white;
      box-shadow: 0 2px 8px rgb(220 38 38 / 0.25);
    }}
    .pat-missing-banner.attention {{ animation: patPulse 0.9s ease-in-out 2; }}
    @keyframes patPulse {{
      0%, 100% {{ box-shadow: none; }}
      50% {{ box-shadow: 0 0 0 4px rgb(220 38 38 / 0.25); }}
    }}
    .prompt-area {{
      width: 100%;
      min-height: 120px;
      padding: 0.75rem;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 0.825rem;
      font-family: inherit;
      line-height: 1.6;
      resize: vertical;
      margin-bottom: 0.75rem;
      transition: border-color 0.2s;
      background: var(--light);
    }}
    .prompt-area:focus {{ outline: none; border-color: var(--blue); background: white; }}
    .prompt-hint {{
      font-size: 0.72rem;
      color: #94a3b8;
      margin-bottom: 0.75rem;
      line-height: 1.5;
    }}
    .prompt-examples {{ margin-bottom: 0.875rem; }}
    .prompt-examples p {{
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--gray);
      margin-bottom: 0.4rem;
    }}
    .prompt-chip {{
      display: inline-block;
      background: #eff6ff;
      color: var(--blue);
      border: 1px solid #bfdbfe;
      padding: 0.2rem 0.6rem;
      border-radius: 8px;
      font-size: 0.7rem;
      cursor: pointer;
      margin: 0.2rem 0.2rem 0.2rem 0;
      transition: all 0.15s;
    }}
    .prompt-chip:hover {{ background: #dbeafe; border-color: var(--blue); }}
    .approve-confirm {{
      font-size: 0.78rem;
      color: var(--gray);
      line-height: 1.6;
      margin-bottom: 0.875rem;
    }}
    .approve-confirm ul {{ padding-left: 1.2rem; margin-top: 0.5rem; }}
    .approve-confirm li {{ margin-bottom: 0.3rem; }}
    .preview-area {{
      padding: 2rem;
      overflow-y: auto;
    }}
    .preview-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1.25rem;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}
    .preview-toolbar h2 {{
      font-size: 1rem;
      font-weight: 700;
      color: var(--navy);
    }}
    .preview-meta {{ font-size: 0.78rem; color: #94a3b8; }}
    .preview-frame {{
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: var(--shadow);
      background: white;
      position: relative;
    }}
    .preview-frame iframe {{
      width: 100%;
      height: calc(100vh - 220px);
      border: none;
      display: block;
    }}
    .iframe-loading {{
      display: none;
      position: absolute;
      inset: 0;
      background: rgba(248,250,252,0.85);
      border-radius: 16px;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 0.75rem;
      z-index: 10;
    }}
    .iframe-loading.show {{ display: flex; }}
    .iframe-loading-spinner {{
      width: 36px; height: 36px;
      border: 3px solid #e2e8f0;
      border-top-color: #7c3aed;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }}
    .iframe-loading-text {{
      font-size: 0.8rem;
      color: var(--gray);
      font-weight: 600;
    }}
    #toast {{
      position: fixed;
      bottom: 2rem;
      left: 50%;
      transform: translateX(-50%) translateY(100px);
      background: var(--navy);
      color: white;
      padding: 0.875rem 1.5rem;
      border-radius: 12px;
      font-size: 0.875rem;
      font-weight: 500;
      z-index: 1000;
      transition: transform 0.3s ease;
      max-width: 480px;
      text-align: center;
      box-shadow: 0 8px 32px rgb(0 0 0 / 0.2);
    }}
    #toast.show {{ transform: translateX(-50%) translateY(0); }}
    #toast.success {{ background: var(--green); }}
    #toast.error   {{ background: var(--red); }}
    #toast.info    {{ background: var(--blue); }}
    #toast.purple  {{ background: #7c3aed; }}
    #overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15,23,42,0.6);
      backdrop-filter: blur(4px);
      z-index: 200;
      align-items: center;
      justify-content: center;
    }}
    #overlay.show {{ display: flex; }}
    .overlay-card {{
      background: white;
      border-radius: 20px;
      padding: 2.5rem;
      max-width: 440px;
      width: 90%;
      text-align: center;
      box-shadow: 0 20px 60px rgb(0 0 0 / 0.2);
    }}
    .overlay-icon {{ font-size: 3rem; margin-bottom: 1rem; }}
    .overlay-title {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; }}
    .overlay-body  {{ font-size: 0.9rem; color: var(--gray); line-height: 1.65; margin-bottom: 1.5rem; }}
    .spinner {{
      width: 40px; height: 40px;
      border: 3px solid #e2e8f0;
      border-top-color: var(--blue);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 1rem;
    }}
    .regen-badge {{
      background: #fef3c7;
      color: var(--amber);
      border: 1px solid #fde68a;
      padding: 0.4rem 1rem;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 600;
      display: inline-block;
      margin-bottom: 0.75rem;
    }}
    .lock-banner {{
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 10px;
      padding: 0.875rem 1rem;
      margin-top: 0.75rem;
      font-size: 0.78rem;
      color: #92400e;
      line-height: 1.55;
    }}
    .lock-banner strong {{ display: block; margin-bottom: 0.2rem; color: #78350f; }}
    .lock-banner button {{
      display: block;
      margin-top: 0.6rem;
      background: none;
      border: none;
      color: #92400e;
      font-weight: 700;
      font-size: 0.75rem;
      text-decoration: underline;
      cursor: pointer;
      padding: 0;
    }}
    /* ── Mobile ───────────────────────────────────────────────────────
       This screen is reviewed on a phone, not a desktop, so the phone layout
       is the real one. Two things drive it:

       1. The post comes FIRST. On a stacked layout the sidebar used to push
          the actual draft 2,300px down the page — you scrolled past every
          control, including Approve, before reaching the thing you came to
          read. The preview is now first and the controls follow in the order
          you need them: write your take, publish, grab the share link.
       2. Inputs are 16px. Below that, iOS Safari zooms the viewport on focus
          and does not zoom back out, which leaves the page stranded
          mid-review. This is the single most common way a form breaks on
          iPhone and it is invisible on a desktop browser. */
    @media (max-width: 900px) {{
      .layout {{ display: flex; flex-direction: column; }}
      .preview-frame {{ order: 1; }}
      .sidebar {{
        order: 2; position: static; height: auto;
        border-right: none; border-top: 1px solid var(--border);
        display: flex; flex-direction: column; padding: 1.25rem 1rem 3rem;
      }}
      .preview-frame iframe {{ height: 78vh; }}

      /* Controls in the order the review actually happens */
      .sidebar > * {{ order: 50; }}
      .sec-take    {{ order: 10; }}
      .sec-approve {{ order: 20; }}
      .sec-share   {{ order: 30; }}
      .sec-regen   {{ order: 40; }}
      .sec-status  {{ order: 60; }}
      .sec-survey  {{ order: 70; }}
      .pat-section {{ order: 80; }}
      .sec-discard {{ order: 90; }}

      .topbar {{ flex-wrap: wrap; gap: 0.5rem; padding: 0.6rem 0.9rem; height: auto; }}
      .topbar-left {{ flex-wrap: wrap; gap: 0.5rem; }}
      .topbar-right {{ width: 100%; justify-content: stretch; }}
      .topbar-right .btn {{ flex: 1; text-align: center; }}
      .sidebar {{ top: auto; }}

      /* 16px stops iOS zooming on focus; 44px is the minimum comfortable tap.
         The token field is type="password" and carries no class, so it slipped
         past both the .pat-input and the input[type="text"] selectors and kept
         zooming the page on focus. Kept as an explicit list rather than a bare
         `input` so a future checkbox does not inherit a 16px font. */
      .prompt-area, .survey-input, .pat-input, select, input[type="text"],
      input[type="number"], input[type="password"], textarea {{ font-size: 16px; }}
      .survey-opt input {{ width: 5.5rem; font-size: 16px; padding: 0.45rem; }}
      .survey-opt span {{ font-size: 0.8rem; }}
      .btn {{ min-height: 44px; }}
      /* .btn's min-height does not reach the selects and inputs. */
      select, .survey-input, input[type="password"] {{ min-height: 44px; }}
      #take-input {{ min-height: 150px; }}
      .perma-row {{ flex-wrap: wrap; }}
      .perma-row code {{ flex-basis: 100%; font-size: 0.72rem; }}
      .perma-row .btn {{ width: 100%; }}
    }}
  </style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <span class="logo">imetrobert.com</span>
    <span class="issue-label">📝 Review: {issue_month_year} &mdash; covers {coverage_month_name}</span>
  </div>
  <div class="topbar-right">
    <a href="https://www.imetrobert.com/blog/" class="btn btn-outline" target="_blank">
      🌐 Live Blog
    </a>
    <button class="btn btn-outline" onclick="openStagingPost()">
      ↗ Open Full Post
    </button>
  </div>
</div>

<div class="layout">

  <div class="sidebar">

    <div class="sidebar-section sec-status">
      <h3>Status</h3>
      <div class="status-card">
        <div class="status-row">
          <span class="status-label">Issue</span>
          <span class="status-value">{issue_month_year}</span>
        </div>
        <div class="status-row">
          <span class="status-label">Covers</span>
          <span class="status-value">{coverage_month_name}</span>
        </div>
        <div class="status-row">
          <span class="status-label">File</span>
          <span class="status-value" style="font-family:monospace;font-size:0.7rem;">{staging_filename}</span>
        </div>
        <div class="status-row">
          <span class="status-label">Status</span>
          <span class="badge-pending">⏳ Awaiting approval</span>
        </div>
        <div class="status-row" id="gen-info" style="display:none;">
          <span class="status-label">Generated</span>
          <span class="status-value" id="gen-run">—</span>
        </div>
        <div class="status-row">
          <span class="status-label">Page loaded</span>
          <span class="status-value" id="page-loaded-time">—</span>
        </div>
      </div>

      <!-- Gemini daily requests. The free tier is rate-limited per minute and
           per DAY, not a monthly token pool, so requests-per-day is the number
           repeated testing actually threatens. -->
      <div class="status-card" id="quota-card" style="margin-top:0.75rem;">
        <div class="status-row">
          <span class="status-label">Gemini requests today</span>
          <span class="status-value" id="quota-count" style="font-weight:700;">—</span>
        </div>
        <!-- One row per model. Free-tier RPD is a SEPARATE budget per model, so
             a single combined bar would misreport both. -->
        <div id="quota-models" style="margin-top:0.5rem;"></div>
        <div id="quota-note" style="font-size:0.68rem;color:#94a3b8;line-height:1.45;margin-top:0.4rem;"></div>
      </div>

      <!-- Model choice. Lives in blog/model-config.json so adopting a newly
           launched Gemini model is a decision made here, not a code edit. A new
           model is never adopted automatically: availability is not quality,
           and flash-lite proved that by producing a materially worse issue. -->
      <div class="status-card" id="model-card" style="margin-top:0.75rem;">
        <div class="status-row">
          <span class="status-label">Model</span>
          <span class="status-value" id="model-leader" style="font-family:monospace;font-size:0.7rem;">—</span>
        </div>
        <div id="model-fallbacks" style="font-size:0.66rem;color:#64748b;margin-top:0.25rem;"></div>
        <div id="model-new" style="display:none;margin-top:0.6rem;padding:0.6rem;
             border-radius:6px;background:#78350f;color:#fff;font-size:0.72rem;line-height:1.5;">
          <div style="font-weight:700;margin-bottom:0.35rem;">New Gemini model available</div>
          <select id="model-new-name" style="width:100%;font-family:monospace;font-size:0.72rem;
                  margin-bottom:0.45rem;padding:0.25rem;border-radius:4px;border:1px solid #a16207;
                  background:#451a03;color:#fff;"></select>
          <!-- The decision that matters is not "is it newer" but "does it cost
               me headroom". Pro-tier free limits are in the tens per day against
               Flash's thousands, so adopting one silently would remove ~95% of
               the daily budget. The current limit is shown beside the new one so
               the comparison is unavoidable. -->
          <div id="model-tier-warn" style="display:none;font-size:0.66rem;background:#7f1d1d;
               border-radius:4px;padding:0.4rem 0.5rem;margin-bottom:0.45rem;"></div>
          <div style="display:flex;gap:0.5rem;align-items:flex-end;margin-bottom:0.4rem;flex-wrap:wrap;">
            <div>
              <div style="font-size:0.63rem;opacity:0.8;">Today (<span id="model-cur-name">—</span>)</div>
              <div id="model-cur-limit" style="font-size:0.82rem;font-weight:700;">—</div>
            </div>
            <div style="font-size:0.9rem;opacity:0.6;padding-bottom:0.1rem;">&rarr;</div>
            <div>
              <div style="font-size:0.63rem;opacity:0.8;">New model, per day</div>
              <input id="model-new-limit" type="number" min="1" placeholder="RPD"
                     style="width:5rem;padding:0.2rem 0.4rem;font-size:0.72rem;border-radius:4px;
                            border:1px solid #a16207;background:#451a03;color:#fff;">
            </div>
            <div>
              <div style="font-size:0.63rem;opacity:0.8;">Per minute</div>
              <input id="model-new-rpm" type="number" min="1" placeholder="RPM"
                     style="width:4.4rem;padding:0.2rem 0.4rem;font-size:0.72rem;border-radius:4px;
                            border:1px solid #a16207;background:#451a03;color:#fff;">
            </div>
          </div>
          <div id="model-rpm-note" style="font-size:0.64rem;opacity:0.85;margin-bottom:0.4rem;"></div>
          <div id="model-delta" style="font-size:0.68rem;font-weight:700;margin-bottom:0.45rem;"></div>
          <div style="font-size:0.64rem;opacity:0.85;margin-bottom:0.5rem;">
            Google publishes no API for rate limits, so this number cannot be
            discovered. Nothing switches until you press the button, and it
            applies from the next run.
          </div>
          {quota_help_dark}
          <div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
            <button class="btn btn-secondary" id="model-adopt" style="flex:1;min-width:8rem;"
                    onclick="adoptNewModel()">Lead with it</button>
            <button class="btn btn-secondary" id="model-dismiss" style="flex:1;min-width:6rem;"
                    onclick="dismissNewModel()">Not now</button>
          </div>
        </div>
        <div id="model-status" style="font-size:0.66rem;color:#94a3b8;margin-top:0.4rem;"></div>
        <div style="font-size:0.65rem;color:#64748b;line-height:1.45;margin-top:0.45rem;">
          Counts only runs from this blog. Any other app using the same API key
          draws on the same quota and is not counted here — the console has the
          authoritative number.
        </div>
        {quota_help_light}
      </div>
      {regen_badge}
      <div id="lock-banner" style="display:none;">
        <div class="lock-banner">
          <strong>⏳ Regenerating…</strong>
          <span id="lock-banner-text">This page will reload automatically when the new version is ready. Approve and Regenerate are locked until then — the file this page knows about will be replaced.</span>
          <!-- forceRefresh, not location.reload: a regenerate replaces this
               page, and a plain reload can still be answered from the cached
               copy — which is how you end up staring at the previous run's
               timestamp after a successful regenerate. -->
          <button onclick="forceRefresh()">🔄 Reload page now</button>
        </div>
      </div>
    </div>

    <div class="sidebar-section pat-section" id="pat-section">
      <h3>GitHub Access Token</h3>
      <div id="pat-missing-banner" style="display:none;">
        <div class="pat-missing-banner">
          <strong>🔑 No token found on this browser</strong>
          <span>Needed to trigger GitHub Actions from this page. This happens after clearing your cache, or on a new browser or device — nothing's wrong, you just need to add one again.</span>
          <a href="https://github.com/settings/tokens/new?scopes=workflow&description=Blog+Preview+Approval" target="_blank" class="btn">
            🔗 Create a token on GitHub
          </a>
        </div>
      </div>
      <input
        type="password"
        id="pat-input"
        placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
        autocomplete="off"
      >
      <div id="pat-saved" class="pat-saved">✓ Token saved in this browser</div>
      <p class="pat-hint">
        Needs <strong>workflow</strong> scope. Saved only in this browser's localStorage — you'll need to re-add it after clearing your cache or on a new browser/device.
        <a href="https://github.com/settings/tokens/new?scopes=workflow&description=Blog+Preview+Approval" target="_blank">Create a token</a>
        if you don't have one handy.
      </p>
      <button class="btn btn-outline" style="width:100%;margin-top:0.5rem;" onclick="savePAT()">
        Save Token
      </button>
    </div>

    <div class="sidebar-section sec-redraft-section">
      <h3>Ask Gemini to redraft a section</h3>
      <p class="take-hint">Rewrites one section in place. The rest of the issue,
      and the filename, stay exactly as they are &mdash; use this instead of a full
      regeneration when only one section is flat. Only the judgment sections are
      listed: the reported ones went through date, source and deduplication rules
      that a one-section rewrite cannot reproduce.</p>
      <label class="survey-label">Section
        <select id="redraft-section" class="survey-input">{redraft_options}</select>
      </label>
      <div class="prompt-examples">
        <p>Quick steers:</p>
        <span class="prompt-chip" onclick="setRedraftGuidance('Make it more contrarian. Say the thing most people in the room would not say, and back it up.')">More contrarian</span>
        <span class="prompt-chip" onclick="setRedraftGuidance('Lead with the governance and change-management angle rather than the technology.')">Governance angle</span>
        <span class="prompt-chip" onclick="setRedraftGuidance('Ground this more in what actually happens inside a large enterprise — procurement friction, legal review capacity, the gap between a pilot and a deployment.')">More enterprise reality</span>
        <span class="prompt-chip" onclick="setRedraftGuidance('Too abstract. Tie it to a specific decision an executive has to make this quarter.')">Make it concrete</span>
        <span class="prompt-chip" onclick="setRedraftGuidance('Pick a completely different angle from the current draft. Same section, new argument.')">Different angle</span>
      </div>
      <textarea id="redraft-guidance" class="prompt-area" rows="4"
        placeholder="What should change? e.g. 'Focus the Desk on why cheap compute will not fix the governance queue.' Leave blank to just ask for a different angle."></textarea>
      <p class="prompt-hint">
        Runs without web search, so a redraft can sharpen the argument but cannot
        introduce an event or statistic that was never sourced. If the result does
        not fit the section&#39;s format, nothing is changed.
      </p>
      <!-- The one place the reviewer's OWN words leave the machine. The Desk
           textarea does not: inject_take.py runs in approve-blog.yml, after
           every Gemini call, so that text goes straight into the published
           HTML. This box is sent with the issue on every redraft. -->
      <p class="prompt-hint" style="border-left:2px solid #b45309;padding-left:0.6rem;">
        <strong>This box is sent to Google.</strong> On the Gemini free tier,
        submitted data may be reviewed by humans and used to train Google&#39;s
        models. Steer the writing here — don&#39;t paste anything confidential or
        employer-specific. Your Desk text is different: it is injected at
        approval, after every model call, and never leaves this machine.
      </p>
      <button class="btn btn-secondary" id="redraft-btn" style="width:100%;" onclick="triggerRedraft()">
        &#9998; Redraft This Section
      </button>
    </div>

    <div class="sidebar-section sec-take">
      <h3>From Robert&#39;s Desk &mdash; in your words</h3>
      <p class="take-hint">The signature section, and the one part of the issue that
      claims to be you. {desk_draft_note} Target 300&ndash;450 words. Separate
      paragraphs with a blank line. Clearing this box entirely keeps the draft
      below as-is.</p>
      <textarea id="take-input" class="prompt-area" rows="16"
        placeholder="What surprised you this month? What do executives keep getting wrong? What is overhyped, what can wait, and what will matter six months from now?">{desk_draft_attr}</textarea>
      <div class="take-meta">
        <span id="take-count">0 words</span>
        <span id="take-saved" class="take-saved"></span>
      </div>
    </div>

    <div class="sidebar-section sec-share">
      <h3>Share link (after publishing)</h3>
      <p class="take-hint">The permanent URL for this issue. Use this on LinkedIn &mdash;
      never latest.html, which changes every month.</p>
      <div class="perma-row">
        <code id="perma-url">{permalink}</code>
        <button class="btn btn-secondary" style="padding:0.4rem 0.8rem;font-size:0.72rem;"
          onclick="copyPermalink()">Copy</button>
      </div>
    </div>

    {survey_section}

    <div class="sidebar-section sec-regen">
      <h3>Regenerate with Prompt</h3>
      <div class="prompt-examples">
        <p>Quick prompts:</p>
        <span class="prompt-chip" onclick="setPrompt('Make the Canadian business impact section more specific to financial services and banking')">More FinServ focus</span>
        <span class="prompt-chip" onclick="setPrompt('Rewrite with a more direct, less corporate tone. Cut all filler phrases.')">Sharper tone</span>
        <span class="prompt-chip" onclick="setPrompt('Add more specific Canadian company examples — Shopify, RBC, Bell, Cohere — throughout the analysis')">More Cdn examples</span>
        <span class="prompt-chip" onclick="setPrompt('Focus this month on agentic AI and autonomous workflows for enterprise. Make it the central theme.')">Agentic AI focus</span>
        <span class="prompt-chip" onclick="setPrompt('Completely rewrite — different angle, fresher insights, less repetitive structure')">Fresh rewrite</span>
      </div>
      <textarea
        id="prompt-input"
        class="prompt-area"
        placeholder="e.g. Make the strategic recommendations more specific to manufacturing. Add more detail on Quebec AI regulation. Cut the intro and get to the insights faster."
      ></textarea>
      <div id="last-prompt-box" style="display:none;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:0.75rem;margin-bottom:0.75rem;">
        <div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#16a34a;margin-bottom:0.3rem;">Last prompt used</div>
        <div id="last-prompt-text" style="font-size:0.78rem;color:#1e293b;line-height:1.5;"></div>
        <button onclick="reuseLastPrompt()" style="margin-top:0.5rem;font-size:0.7rem;color:#16a34a;background:none;border:none;cursor:pointer;padding:0;font-weight:600;text-decoration:underline;">↩ Reuse this prompt</button>
      </div>
      <p class="prompt-hint">
        Your prompt is passed to Gemini as a refinement topic. The full monthly newsletter format is preserved. Allow ~5 min for generation + GitHub Pages rebuild.
      </p>
      <button class="btn btn-secondary" id="regenerate-btn" style="width:100%;" onclick="triggerRegenerate()">
        🔄 Regenerate Post
      </button>
    </div>

    <div class="sidebar-section sec-approve">
      <h3>Approve &amp; Publish</h3>
      <p class="approve-confirm">
        Publishing will:
        <ul>
          <li>Apply your Robert&#39;s Take, if you wrote one</li>
          <li>Move post to <code>blog/posts/</code> and update <code>latest.html</code></li>
          <li>Regenerate <code>sitemap.xml</code>, the blog index, RSS and <code>llms.txt</code></li>
          <li>Rebuild the adoption pillar page with this month&#39;s figures</li>
          <li>Mint this issue&#39;s social card</li>
          {survey_bullet}
        </ul>
      </p>
      <button class="btn btn-primary" id="approve-btn" style="width:100%;padding:0.875rem;" onclick="triggerApprove()">
        ✅ Approve &amp; Publish
      </button>
    </div>

    <div class="sidebar-section sec-discard">
      <h3>Discard</h3>
      <p class="approve-confirm">
        Deletes this draft from staging. Nothing is published or affected —
        only undoes the generation. Use this if the draft isn't worth
        fixing with a prompt; you can't recover it after.
      </p>
      <button class="btn btn-discard-outline" id="discard-btn" style="width:100%;" onclick="triggerDiscard()">
        🗑️ Discard Draft
      </button>
    </div>

  </div>

  <div class="preview-area">
    <div class="preview-toolbar">
      <div>
        <h2>Post Preview — {issue_month_year} <span style="font-weight:400;opacity:0.6;">(covers {coverage_month_name})</span></h2>
        <div class="preview-meta">Generated {generated_stamp}</div>
        <div class="preview-meta">Staging file: {staging_filename}</div>
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <span id="cache-hint" style="font-size:0.72rem;color:#94a3b8;display:none;">Seeing an old version?</span>
        <button class="btn btn-force-refresh" id="force-refresh-btn" onclick="forceRefresh()" title="Bypass cache and reload the latest version">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
            <path d="M21 3v5h-5"/>
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
            <path d="M3 21v-5h5"/>
          </svg>
          Force Refresh
        </button>
      </div>
    </div>
    <div class="preview-frame" id="preview-frame-wrapper">
      <div class="iframe-loading show" id="iframe-loading">
        <div class="iframe-loading-spinner"></div>
        <div class="iframe-loading-text">Loading latest version…</div>
      </div>
      <!-- The load handler is attached in JS, not as an onload attribute: an
           iframe with an empty src fires load for about:blank while the page
           is still parsing, which is before the script at the end of body
           exists, so the attribute version threw ReferenceError on every
           load. Harmless — the real draft load cleared the overlay — but it
           buried genuine errors in the console. -->
      <iframe id="preview-iframe" src="" title="Blog post preview"></iframe>
    </div>
  </div>

</div>

<div id="toast"></div>
<div id="overlay">
  <div class="overlay-card" id="overlay-card"></div>
</div>

<script>
  const REPO          = "{repo}";
  const STAGING_FILE  = "{staging_filename}";
  const ISSUE_MONTH_YEAR    = "{issue_month_year}";
  const COVERAGE_MONTH_YEAR = "{coverage_month_year}";
  const SURVEY_QUESTIONS = {survey_questions_json};
  const PERMALINK        = {permalink_json};
  const APPROVE_WF    = "approve-blog.yml";
  const REGENERATE_WF = "regenerate-blog.yml";
  const REDRAFT_WF    = "redraft-section.yml";
  const DISCARD_WF    = "discard-blog.yml";
  const GITHUB_API    = "https://api.github.com";

  // ── Set iframe src with cache-busting timestamp on load ────────
  function setIframeSrc(extraBust) {{
    const iframe = document.getElementById("preview-iframe");
    const ts = extraBust || Date.now();
    iframe.src = `/blog/staging/${{STAGING_FILE}}?v=${{ts}}`;
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    loadPAT();
    loadLastPrompt();
    const runId = "{run_id}";
    if (runId && runId !== "0") {{
      const row = document.getElementById("gen-info");
      const val = document.getElementById("gen-run");
      if (row && val) {{
        row.style.display = "flex";
        val.innerHTML = `<a href="https://github.com/${{REPO}}/actions/runs/${{runId}}" target="_blank" style="color:var(--blue);">Run #${{runId}}</a>`;
      }}
    }}
    // Set iframe src with cache-busting timestamp — fixes blank iframe on slow JS
    document.getElementById("preview-iframe")
            .addEventListener("load", onIframeLoad);
    setIframeSrc();
    // Show cache hint after 3 seconds in case content looks stale
    setTimeout(() => {{
      document.getElementById("cache-hint").style.display = "inline";
    }}, 3000);
    checkForStalePage();
    loadQuota();
    loadModelConfig();
    // Every full page load reflects the true current staging_filename (baked
    // in server-side at generation time) — this timestamp is how you can
    // tell whether THIS page still matches what's actually on GitHub.
    document.getElementById("page-loaded-time").textContent = new Date().toLocaleTimeString();
  }});

  // Is this page the one that is actually deployed?
  //
  // The approval screen lives at a fixed URL and is regenerated on every run,
  // so a cached copy shows an old issue with an old generation time and gives
  // no sign of it. That happened: a stamp read 10:38 PM for a run that had
  // already been superseded, and the natural conclusion was that the stamp was
  // broken rather than the page being stale.
  //
  // Fetch the live copy, compare the server-rendered stamp, and say so plainly
  // if they differ. Fails silently — offline or blocked, a missing warning is
  // better than a false one.
  const GENERATED_STAMP = {generated_stamp_json};

  // ── Gemini daily requests ───────────────────────────────────────
  // The free tier is rate-limited per minute and per DAY, not a monthly token
  // pool, so this tracks requests per day — the limit repeated testing hits.
  // The count is re-fetched rather than trusted from the baked-in value,
  // because a redraft makes requests without regenerating this page.
  const QUOTA_BAKED = {quota_baked};
  const QUOTA_LIMIT_KEY = "blog_preview_quota_limit";

  // Google resets these quotas at midnight Pacific, so the bucket to read is
  // today's PACIFIC date — not the browser's local date, which rolls over at
  // the wrong moment and would read as headroom that is not there.
  function quotaDay() {{
    return new Date().toLocaleDateString("en-CA", {{ timeZone: "America/Los_Angeles" }});
  }}

  // Limits are per model and separate. Defaults come from the free tier; each
  // is overridable because quotas are assigned per Google Cloud project.
  const QUOTA_DEFAULT_LIMITS = {quota_limits_json};
  const QUOTA_LIMIT_PREFIX = "blog_preview_quota_limit_";

  function quotaLimitFor(model) {{
    const saved = parseInt(localStorage.getItem(QUOTA_LIMIT_PREFIX + model) || "", 10);
    if (saved > 0) return saved;
    return QUOTA_DEFAULT_LIMITS[model] || 0;
  }}

  function quotaColour(pct) {{
    return pct >= 85 ? "#ef4444" : (pct >= 60 ? "#f59e0b" : "#22c55e");
  }}

  function renderQuota(entry) {{
    const total = entry && entry.requests ? entry.requests : 0;
    const models = (entry && entry.models) ? entry.models : {{}};
    const el = document.getElementById("quota-count");
    const host = document.getElementById("quota-models");
    const note = document.getElementById("quota-note");
    if (!el || !host) return;
    el.textContent = total;

    const names = Object.keys(models).sort((a, b) => models[b] - models[a]);
    // Feeds the lookup prompt, so it asks about the models actually in use.
    QUOTA_MODELS_SEEN = names;
    host.innerHTML = "";
    let worst = 0;
    names.forEach(function (m) {{
      const used = models[m];
      const limit = quotaLimitFor(m);
      const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
      if (pct > worst) worst = pct;
      const row = document.createElement("div");
      row.style.cssText = "margin-bottom:0.5rem;";
      const short = m.replace("gemini-", "");
      row.innerHTML =
        '<div style="display:flex;justify-content:space-between;gap:0.5rem;'
        + 'font-size:0.7rem;color:#cbd5e1;margin-bottom:0.2rem;">'
        + '<span style="font-family:monospace;">' + short + '</span>'
        + '<span style="font-weight:700;color:' + quotaColour(pct) + ';">'
        + used + (limit ? " / " : "") + '</span></div>'
        + '<div style="height:5px;background:#1e293b;border-radius:3px;overflow:hidden;">'
        + '<div style="height:100%;width:' + pct + '%;background:' + quotaColour(pct) + ';"></div>'
        + '</div>';
      // The limit is an input so a project with a different quota can correct it.
      const input = document.createElement("input");
      input.type = "number"; input.min = "1"; input.value = limit || "";
      input.title = "Daily request limit for " + m;
      input.style.cssText = "width:4.6rem;padding:0.15rem 0.3rem;font-size:0.68rem;"
        + "border-radius:4px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;";
      input.addEventListener("input", function () {{
        const v = parseInt(input.value, 10);
        if (v > 0) localStorage.setItem(QUOTA_LIMIT_PREFIX + m, String(v));
        else localStorage.removeItem(QUOTA_LIMIT_PREFIX + m);
        loadQuota();
      }});
      row.querySelector("span:last-child").appendChild(input);
      host.appendChild(row);
    }});

    renderLimitPrompts();
    if (!names.length) {{
      note.textContent = "No requests recorded yet today. Resets at midnight Pacific.";
    }} else if (worst >= 85) {{
      note.textContent = worst + "% of a model's daily requests used. Stop testing — "
        + "a single run can fire several requests when a model retries or falls back.";
    }} else if (worst >= 60) {{
      note.textContent = worst + "% of a model's daily requests used. Resets at midnight Pacific.";
    }} else {{
      note.textContent = "Well inside the daily limits. Resets at midnight Pacific.";
    }}
  }}

  // ── Model choice ───────────────────────────────────────────────
  // Config lives in the repo so the workflow reads it too. Written back from
  // here with the same PAT that dispatches workflows, which is what makes
  // adopting a new model a UI action rather than a code change.
  const MODEL_CONFIG_PATH = "blog/model-config.json";
  let MODEL_CFG = null;

  async function loadModelConfig() {{
    const leader = document.getElementById("model-leader");
    const fallbacks = document.getElementById("model-fallbacks");
    if (!leader) return;
    let cfg = {{ order: [], limits: {{}}, available: [] }};
    try {{
      const res = await fetch("/" + MODEL_CONFIG_PATH + "?v=" + Date.now(),
                              {{ cache: "no-store" }});
      if (res.ok) cfg = await res.json();
    }} catch (e) {{ /* no config yet — the run falls back to built-in defaults */ }}
    MODEL_CFG = cfg;
    const order = (cfg.order && cfg.order.length) ? cfg.order : ["(built-in default)"];
    leader.textContent = order[0].replace("gemini-", "");
    fallbacks.textContent = order.length > 1
      ? "falls back to " + order.slice(1).map(m => m.replace("gemini-", "")).join(", ")
      : "no fallback configured";

    const fresh = (cfg.available || []).filter(m => !(cfg.dismissed || []).includes(m));
    const box = document.getElementById("model-new");
    if (fresh.length) {{
      // A dropdown, not a label: the discovery call can return several newer
      // models at once, and "Lead with it" silently taking the first would
      // adopt something the reviewer never chose.
      const sel = document.getElementById("model-new-name");
      sel.innerHTML = "";
      fresh.forEach(function (m) {{
        const o = document.createElement("option");
        o.value = m; o.textContent = m;
        sel.appendChild(o);
      }});
      sel.onchange = renderModelDelta;
      const lim = document.getElementById("model-new-limit");
      [lim, document.getElementById("model-new-rpm")].forEach(function (inp) {{
        if (inp && !inp.dataset.wired) {{
          inp.addEventListener("input", renderModelDelta);
          inp.dataset.wired = "1";
        }}
      }});
      box.style.display = "block";
      renderModelDelta();
      renderLimitPrompts();
    }} else {{
      box.style.display = "none";
    }}
  }}

  // Read-modify-write through the Contents API. The SHA is fetched immediately
  // before the write so a config the workflow changed in between is not
  // silently clobbered.
  async function writeModelConfig(cfg, message) {{
    const pat = loadPAT();
    if (!pat) {{
      showToast("Please add your GitHub token below first.", "error");
      flashPatAttention();
      return false;
    }}
    const url = `${{GITHUB_API}}/repos/${{REPO}}/contents/${{MODEL_CONFIG_PATH}}`;
    const headers = {{ "Authorization": `Bearer ${{pat}}`,
                      "Accept": "application/vnd.github+json" }};
    let sha = null;
    try {{
      const cur = await fetch(url + "?ref=main", {{ headers, cache: "no-store" }});
      if (cur.ok) sha = (await cur.json()).sha;
      else if (cur.status !== 404) {{
        showToast(`Could not read the config (${{cur.status}}).`, "error");
        return false;
      }}
    }} catch (e) {{ showToast("Network error reading the config.", "error"); return false; }}

    const body = {{
      message: message,
      content: btoa(unescape(encodeURIComponent(JSON.stringify(cfg, null, 2)))),
      branch: "main"
    }};
    if (sha) body.sha = sha;
    try {{
      const res = await fetch(url, {{ method: "PUT", headers, body: JSON.stringify(body) }});
      if (!res.ok) {{
        const t = await res.text();
        showToast(`Write failed (${{res.status}}). ${{t.slice(0, 120)}}`, "error");
        return false;
      }}
      return true;
    }} catch (e) {{ showToast("Network error writing the config.", "error"); return false; }}
  }}

  // ── Limit-lookup prompt ────────────────────────────────────────
  // Built from the models actually in play, so it never asks about something
  // irrelevant. It asks for uncertainty to be stated rather than estimated: a
  // confidently wrong RPD drives a quota bar that is confidently wrong too.
  function buildLimitPrompt(models, current, currentLimit) {{
    const list = models.filter(Boolean).map(m => "- " + m).join("\\n");
    const baseline = current
      ? `My current model is ${{current}}${{currentLimit ? ` (I have it recorded as `
        + `${{currentLimit}} requests/day)` : ""}}.`
      : "";
    return [
      "I use the Google Gemini API on the FREE tier (Google AI Studio key, not Vertex AI).",
      "",
      "For each model below, give me the current free-tier rate limits:",
      list,
      "",
      baseline,
      "",
      "Answer with:",
      "1. A table: model | requests per day | requests per minute | tokens per minute",
      "2. Whether each model is available on the free tier at all, or paid-only",
      "3. Which of them give me the SAME or MORE requests per day than my current model,"
        + " and which would cut it — state the percentage change",
      "4. The date your figures are from, and a link to Google's official rate-limits page",
      "",
      "If you are not certain of a number, say so explicitly rather than estimating."
        + " I am using these figures to set a quota warning, so a wrong number is worse"
        + " than no number.",
      "",
      "Note: Google assigns these per Google Cloud project and no longer publishes one"
        + " universal table, so tell me if the figure varies by project."
    ].filter(l => l !== null).join("\\n");
  }}

  function renderLimitPrompts() {{
    const cfg = MODEL_CFG || {{}};
    const current = (cfg.order || [])[0] || "";
    const currentLimit = (cfg.limits || {{}})[current] || QUOTA_DEFAULT_LIMITS[current] || 0;

    // New-model panel: the models being offered.
    const sel = document.getElementById("model-new-name");
    const offered = sel ? Array.from(sel.options).map(o => o.value) : [];
    const mp = document.getElementById("model-prompt-text");
    if (mp) mp.value = buildLimitPrompt(offered, current, currentLimit);

    // Quota panel: the models actually being used.
    const inUse = Array.from(new Set((cfg.order || []).concat(QUOTA_MODELS_SEEN)));
    const qp = document.getElementById("quota-prompt-text");
    if (qp) qp.value = buildLimitPrompt(inUse, current, currentLimit);
  }}

  function copyLimitPrompt(ident) {{
    const el = document.getElementById(ident + "-text");
    if (!el) return;
    navigator.clipboard.writeText(el.value).then(
      function () {{ showToast("Prompt copied — paste it into ChatGPT or Gemini.", "success"); }},
      function () {{ el.select(); showToast("Select and copy the text above.", "error"); }}
    );
  }}

  let QUOTA_MODELS_SEEN = [];

  // Pro-tier free limits are roughly an order of magnitude below Flash, so the
  // risk is flagged from the NAME before any number is looked up — the reviewer
  // should know a pro model costs headroom before going to find the figure.
  function modelTierRisk(model, currentModel) {{
    const isPro = /(^|-)pro(-|$)/.test(model);
    const curIsPro = /(^|-)pro(-|$)/.test(currentModel || "");
    if (isPro && !curIsPro) {{
      return "Pro-tier model. On the free tier Pro daily limits are typically tens "
        + "of requests against thousands for Flash — expect a large drop in headroom. "
        + "Confirm the number before adopting.";
    }}
    if (/lite/.test(model) && !/lite/.test(currentModel || "")) {{
      return "Lite model. Lite usually carries a lower daily limit than full Flash, "
        + "and produced a materially weaker issue the one time this pipeline fell "
        + "back to it.";
    }}
    return "";
  }}

  function renderModelDelta() {{
    const cfg = MODEL_CFG || {{}};
    const current = (cfg.order || [])[0] || "";
    const currentLimit = (cfg.limits || {{}})[current] || QUOTA_DEFAULT_LIMITS[current] || 0;
    const sel = document.getElementById("model-new-name");
    const model = sel ? sel.value : "";
    const curName = document.getElementById("model-cur-name");
    const curLimitEl = document.getElementById("model-cur-limit");
    const delta = document.getElementById("model-delta");
    const warn = document.getElementById("model-tier-warn");
    if (!curName || !delta || !warn) return;
    curName.textContent = current.replace("gemini-", "") || "—";
    curLimitEl.textContent = currentLimit ? currentLimit.toLocaleString() + "/day" : "not set";

    renderLimitPrompts();
    const risk = modelTierRisk(model, current);
    warn.style.display = risk ? "block" : "none";
    warn.textContent = risk;

    // Requests per minute. This pipeline peaks at about three requests inside a
    // minute — the ungrounded 400/404 retry fires immediately, the transient
    // retry waits 45s, the model fallback waits 30s — and the blog-pipeline
    // concurrency group serialises runs, so bursts cannot stack. Anything from
    // about 5 RPM up is therefore untouchable; below that is worth knowing.
    const rpmEl = document.getElementById("model-new-rpm");
    const rpm = rpmEl ? parseInt(rpmEl.value, 10) : 0;
    const rpmNote = document.getElementById("model-rpm-note");
    if (rpmNote) {{
      if (!rpm || rpm <= 0) {{
        rpmNote.textContent = "";
      }} else if (rpm < 5) {{
        rpmNote.style.color = "#fca5a5";
        rpmNote.textContent = rpm + " requests/minute is tight. A run can fire about "
          + "three inside a minute when a model retries or falls back, so this could "
          + "throttle a single generation.";
      }} else {{
        rpmNote.style.color = "#86efac";
        rpmNote.textContent = rpm + " requests/minute is ample — a run peaks at about "
          + "three, and runs are serialised so they cannot stack.";
      }}
    }}

    const el = document.getElementById("model-new-limit");
    const n = el ? parseInt(el.value, 10) : 0;
    if (!n || n <= 0 || !currentLimit) {{ delta.textContent = ""; return; }}
    const pct = Math.round(((n - currentLimit) / currentLimit) * 100);
    if (pct >= 0) {{
      delta.style.color = "#86efac";
      delta.textContent = (pct === 0 ? "Same headroom" : "+" + pct + "% headroom")
        + " — " + n.toLocaleString() + " requests/day.";
    }} else if (pct > -50) {{
      delta.style.color = "#fcd34d";
      delta.textContent = pct + "% headroom — " + n.toLocaleString() + "/day instead of "
        + currentLimit.toLocaleString() + ".";
    }} else {{
      delta.style.color = "#fca5a5";
      delta.textContent = pct + "% headroom. " + n.toLocaleString() + "/day instead of "
        + currentLimit.toLocaleString() + " — a severe cut. Adopt only if the model is "
        + "worth losing that much testing room.";
    }}
  }}

  async function adoptNewModel() {{
    const cfg = MODEL_CFG || {{}};
    const fresh = (cfg.available || []).filter(m => !(cfg.dismissed || []).includes(m));
    if (!fresh.length) return;
    const model = document.getElementById("model-new-name").value || fresh[0];
    const limit = parseInt(document.getElementById("model-new-limit").value, 10);
    const rpmVal = parseInt(document.getElementById("model-new-rpm").value, 10) || 0;
    if (!limit || limit <= 0) {{
      showToast("Set the daily request limit first — it cannot be discovered.", "error");
      return;
    }}
    // A severe cut is an informed decision, not a blocked one — but it has to be
    // an explicit click, because losing most of the daily budget is not
    // recoverable until midnight Pacific.
    const cur0 = (cfg.order || [])[0] || "";
    const curLim = (cfg.limits || {{}})[cur0] || QUOTA_DEFAULT_LIMITS[cur0] || 0;
    if (curLim && limit < curLim * 0.5) {{
      const drop = Math.abs(Math.round(((limit - curLim) / curLim) * 100));
      if (!confirm(model + " would cut your daily requests by " + drop + "% ("
                   + limit + "/day instead of " + curLim + "). Adopt anyway?")) return;
    }}
    const btn = document.getElementById("model-adopt");
    btn.disabled = true;
    // New model leads; the previous order becomes the fallback chain, so a bad
    // new model degrades to what was already working instead of failing.
    const order = [model].concat((cfg.order || []).filter(m => m !== model));
    const next = Object.assign({{}}, cfg, {{
      order: order,
      limits: Object.assign({{}}, cfg.limits || {{}}, {{ [model]: limit }}),
      limits_rpm: Object.assign({{}}, cfg.limits_rpm || {{}},
                                rpmVal > 0 ? {{ [model]: rpmVal }} : {{}}),
      known: Array.from(new Set((cfg.known || []).concat(order))),
      available: (cfg.available || []).filter(m => m !== model)
    }});
    const ok = await writeModelConfig(next, `Lead with ${{model}} (set from the approval page)`);
    btn.disabled = false;
    if (ok) {{
      MODEL_CFG = next;
      showToast(`${{model}} will lead from the next run.`, "success");
      document.getElementById("model-status").textContent =
        "Saved. Takes effect on the next generation.";
      loadModelConfig();
    }}
  }}

  async function dismissNewModel() {{
    const cfg = MODEL_CFG || {{}};
    const fresh = (cfg.available || []).filter(m => !(cfg.dismissed || []).includes(m));
    if (!fresh.length) return;
    const btn = document.getElementById("model-dismiss");
    btn.disabled = true;
    const next = Object.assign({{}}, cfg, {{
      dismissed: Array.from(new Set((cfg.dismissed || []).concat(fresh))),
      known: Array.from(new Set((cfg.known || []).concat(fresh))),
      available: []
    }});
    const ok = await writeModelConfig(next, "Dismiss new Gemini model(s) (from the approval page)");
    btn.disabled = false;
    if (ok) {{
      MODEL_CFG = next;
      showToast("Dismissed. It will not be offered again.", "purple");
      loadModelConfig();
    }}
  }}

  async function loadQuota() {{
    let entry = {{ requests: QUOTA_BAKED, models: {{}} }};
    try {{
      const res = await fetch("/blog/staging/usage.json?v=" + Date.now(),
                              {{ cache: "no-store" }});
      if (res.ok) {{
        const data = await res.json();
        entry = data[quotaDay()] || {{ requests: 0, models: {{}} }};
      }}
    }} catch (e) {{ /* offline, or no ledger yet — fall back to the baked value */ }}
    renderQuota(entry);
  }}


  async function checkForStalePage() {{
    try {{
      const res = await fetch("/blog/staging/preview.html?stale=" + Date.now(),
                              {{ cache: "no-store" }});
      if (!res.ok) return;
      const live = await res.text();
      const m = live.match(/Generated ([^<]+)</);
      if (!m || m[1].trim() === GENERATED_STAMP) return;
      // One bar only. Called once on load today, but two stacked warnings
      // saying the same thing would read as two separate problems.
      if (document.getElementById("stale-bar")) return;

      const bar = document.createElement("div");
      bar.id = "stale-bar";
      bar.style.cssText = "position:sticky;top:0;z-index:9999;background:#b45309;" +
        "color:#fff;padding:0.7rem 1rem;font-size:0.85rem;font-weight:600;" +
        "display:flex;gap:0.75rem;align-items:center;flex-wrap:wrap;";
      bar.innerHTML =
        "<span>You are looking at a cached copy of this page. It was generated " +
        GENERATED_STAMP + "; the current one was generated " + m[1].trim() + ".</span>";
      const btn = document.createElement("button");
      btn.textContent = "Load the current version";
      btn.style.cssText = "background:#fff;color:#b45309;border:none;border-radius:6px;" +
        "padding:0.4rem 0.9rem;font-weight:700;cursor:pointer;min-height:36px;";
      btn.onclick = forceRefresh;
      bar.appendChild(btn);
      document.body.prepend(bar);
    }} catch (e) {{
      /* offline or blocked — stay quiet rather than warn wrongly */
    }}
  }}

  function onIframeLoad() {{
    document.getElementById("iframe-loading").classList.remove("show");
    const btn = document.getElementById("force-refresh-btn");
    btn.classList.remove("spinning");
    btn.disabled = false;
  }}

  // ── Force Refresh — bypasses all browser and CDN cache ─────────
  //
  // This must reload THIS page, not just the iframe. It used to only re-point
  // the iframe src, which reloads the draft but leaves the approval screen
  // itself exactly as it was cached — including the "Generated …" stamp, which
  // is rendered server-side into this page. So the one control whose whole job
  // is "show me the current version" could not change the one field you would
  // check to see whether it had worked, and neither could the stale-page bar,
  // which calls this function.
  //
  // A regenerate replaces both the draft and this page, so reloading the whole
  // thing is the correct scope in every case; a redraft leaves this page
  // unchanged, where a full reload is merely harmless.
  //
  // The cache-busting query param is what makes it a real refresh:
  // location.reload() may still be answered from the browser's copy, and
  // GitHub Pages serves this path with a ten-minute max-age we cannot override.
  // A URL never requested before cannot be in any cache, browser or CDN.
  // Built from pathname, not href, so repeat presses don't stack params.
  function forceRefresh() {{
    const btn = document.getElementById("force-refresh-btn");
    if (btn) {{
      btn.classList.add("spinning");
      btn.disabled = true;
    }}
    showToast("Fetching latest version, bypassing cache…", "purple");
    flushTake();
    location.replace(location.pathname + "?v=" + Date.now());
  }}

  // Write any pending Desk text before navigating away. initTake() debounces
  // its save by 400ms, so the last few keystrokes before a refresh would
  // otherwise be dropped — and this section is the one thing on the page that
  // is genuinely Robert's, not recoverable by regenerating.
  function flushTake() {{
    try {{
      const el = document.getElementById("take-input");
      if (el) localStorage.setItem(TAKE_KEY, el.value);
    }} catch (e) {{ /* private mode or storage full — refresh anyway */ }}
  }}

  // ── PAT management ─────────────────────────────────────────────
  // Shows the loud "no token" banner (with a direct link to GitHub's token
  // creation page) whenever there's nothing saved, and the quiet green
  // checkmark otherwise. Called on load and every time the saved value
  // changes, so clearing your cache / a new browser / a rejected token all
  // land you back at the same clear "here's what to do" state.
  function updatePatUI(saved) {{
    document.getElementById("pat-saved").style.display = saved ? "block" : "none";
    document.getElementById("pat-missing-banner").style.display = saved ? "none" : "block";
    if (saved) document.getElementById("pat-input").value = saved;
  }}

  function flashPatAttention() {{
    document.getElementById("pat-section").scrollIntoView({{ behavior: "smooth", block: "start" }});
    const banner = document.getElementById("pat-missing-banner");
    banner.classList.remove("attention");
    void banner.offsetWidth; // restart the animation if it's already mid-flash
    banner.classList.add("attention");
  }}

  function loadPAT() {{
    const saved = localStorage.getItem("blog_preview_pat");
    updatePatUI(saved);
    return saved || "";
  }}

  // ── Last prompt persistence ─────────────────────────────────────
  const LAST_PROMPT_KEY = "blog_preview_last_prompt";

  function saveLastPrompt(prompt) {{
    localStorage.setItem(LAST_PROMPT_KEY, prompt);
  }}

  function loadLastPrompt() {{
    const saved = localStorage.getItem(LAST_PROMPT_KEY);
    const box = document.getElementById("last-prompt-box");
    const text = document.getElementById("last-prompt-text");
    if (saved && saved.trim()) {{
      text.textContent = saved;
      box.style.display = "block";
    }} else {{
      box.style.display = "none";
    }}
  }}

  function reuseLastPrompt() {{
    const saved = localStorage.getItem(LAST_PROMPT_KEY);
    if (saved) {{
      document.getElementById("prompt-input").value = saved;
      document.getElementById("prompt-input").focus();
      document.getElementById("prompt-input").scrollIntoView({{ behavior: "smooth", block: "center" }});
    }}
  }}

  function savePAT() {{
    const val = document.getElementById("pat-input").value.trim();
    if (!val.startsWith("ghp_") && !val.startsWith("github_pat_")) {{
      showToast("Token should start with ghp_ or github_pat_", "error");
      return;
    }}
    localStorage.setItem("blog_preview_pat", val);
    updatePatUI(val);
    showToast("Token saved in this browser ✓", "success");
  }}

  // ── GitHub Actions trigger ──────────────────────────────────────
  async function triggerWorkflow(workflow, inputs) {{
    const pat = loadPAT();
    if (!pat) {{
      showToast("Please add your GitHub token below first.", "error");
      document.getElementById("pat-input").focus();
      flashPatAttention();
      return null;
    }}
    const url = `${{GITHUB_API}}/repos/${{REPO}}/actions/workflows/${{workflow}}/dispatches`;
    try {{
      const res = await fetch(url, {{
        method: "POST",
        headers: {{
          "Authorization": `Bearer ${{pat}}`,
          "Accept": "application/vnd.github+json",
          "Content-Type": "application/json",
          "X-GitHub-Api-Version": "2022-11-28"
        }},
        body: JSON.stringify({{ ref: "main", inputs }})
      }});
      if (res.status === 401) {{
        // Confirmed dead — don't leave the misleading green "✓ Token saved"
        // checkmark up for a token GitHub just rejected.
        localStorage.removeItem("blog_preview_pat");
        updatePatUI(null);
        flashPatAttention();
      }}
      return res;
    }} catch (err) {{
      // Network drop, DNS failure, offline, blocked request — fetch throws
      // rather than resolving, so without this the loading overlay would
      // spin forever with no explanation.
      hideOverlay();
      showToast("Network error contacting GitHub — check your connection and try again.", "error");
      return null;
    }}
  }}

  function apiErrorMessage(res, body) {{
    if (res.status === 401) return "GitHub rejected the token (401) — it's invalid or expired, so it's been cleared from this browser. See the banner in the sidebar to get a new one.";
    if (res.status === 403) return `GitHub returned 403 — the token likely lacks 'workflow' scope. ${{body.message || ""}}`;
    if (res.status === 404) return "GitHub returned 404 — check the token has 'workflow' scope and that all four workflow files are committed to the main branch.";
    return `GitHub API returned ${{res.status}}: ${{body.message || "Unknown error"}}.`;
  }}

  // ── Lock/unlock Approve + Regenerate + Discard while a workflow run is
  // in flight, or while this page's known staging_filename may be stale
  // (a regenerate can rename the file — see startPolling; approve/discard
  // both remove it entirely). Only a full page reload can safely
  // re-establish current state, so unlocking happens via reload, not a
  // timer.
  let draftGone = false; // true once Approve or Discard actually succeeds — this page is done either way
  function lockButtons(message) {{
    document.getElementById("regenerate-btn").disabled = true;
    document.getElementById("approve-btn").disabled = true;
    document.getElementById("discard-btn").disabled = true;
    const banner = document.getElementById("lock-banner");
    if (message) document.getElementById("lock-banner-text").innerHTML = message;
    banner.style.display = "block";
  }}
  function unlockButtons() {{
    if (draftGone) return;
    document.getElementById("regenerate-btn").disabled = false;
    document.getElementById("approve-btn").disabled = false;
    document.getElementById("discard-btn").disabled = false;
    document.getElementById("lock-banner").style.display = "none";
  }}


  // ── Robert's Take ───────────────────────────────────────────────
  // Kept in localStorage: a half-written take should survive a reload or an
  // accidental navigation, since it is the one thing here nobody else can
  // reproduce for him.
  const TAKE_KEY = "blog_preview_take_" + STAGING_FILE;

  function takeText() {{
    const el = document.getElementById("take-input");
    return el ? el.value.trim() : "";
  }}

  function initTake() {{
    const el = document.getElementById("take-input");
    if (!el) return;
    const saved = localStorage.getItem(TAKE_KEY);
    if (saved) el.value = saved;
    const count = document.getElementById("take-count");
    const savedFlag = document.getElementById("take-saved");
    let timer = null;
    function update() {{
      const words = takeText() ? takeText().split(/\s+/).length : 0;
      if (count) {{
        // The target range is the whole point of the section — showing the
        // count alone gives no sense of whether 180 words is short.
        let note = " · target 300–450";
        if (words >= 300 && words <= 450) note = " · in range";
        else if (words > 450) note = " · over 450, consider trimming";
        count.textContent = words + (words === 1 ? " word" : " words") + note;
      }}
      clearTimeout(timer);
      timer = setTimeout(function () {{
        localStorage.setItem(TAKE_KEY, el.value);
        if (savedFlag) {{
          savedFlag.textContent = "saved";
          setTimeout(function () {{ savedFlag.textContent = ""; }}, 1500);
        }}
      }}, 400);
    }}
    el.addEventListener("input", update);
    update();
  }}

  // ── Permalink ───────────────────────────────────────────────────
  function copyPermalink() {{
    navigator.clipboard.writeText(PERMALINK).then(
      function () {{ showToast("Share link copied.", "success"); }},
      function () {{ showToast("Could not copy — select the text manually.", "error"); }}
    );
  }}

  // ── Survey wave form ────────────────────────────────────────────
  function initSurvey() {{
    const host = document.getElementById("survey-questions");
    if (!host || !SURVEY_QUESTIONS.length) return;
    host.innerHTML = SURVEY_QUESTIONS.map(function (q) {{
      const opts = q.options.map(function (o) {{
        return '<label class="survey-opt"><span>' + o + '</span>' +
               '<input type="number" min="0" data-q="' + q.id + '" data-opt="' +
               o.replace(/"/g, "&quot;") + '"></label>';
      }}).join("");
      return '<div class="survey-q"><div class="survey-q-text">' + q.text + '</div>' + opts + '</div>';
    }}).join("");
  }}

  function surveyPayload() {{
    const label = (document.getElementById("wave-label") || {{}}).value;
    const n = parseInt((document.getElementById("wave-n") || {{}}).value, 10);
    if (!label || !label.trim() || !n) return "";      // nothing entered: skip silently

    const results = {{}};
    document.querySelectorAll('#survey-questions input[type="number"]').forEach(function (inp) {{
      const v = parseInt(inp.value, 10);
      if (!isNaN(v) && v >= 0) {{
        const q = inp.dataset.q;
        results[q] = results[q] || {{}};
        results[q][inp.dataset.opt] = v;
      }}
    }});
    if (!Object.keys(results).length) return "";

    const today = new Date().toISOString().slice(0, 10);
    return JSON.stringify({{
      label: label.trim(), date: today, field_dates: ISSUE_MONTH_YEAR,
      n: n, results: results
    }});
  }}

  document.addEventListener("DOMContentLoaded", function () {{
    initTake();
    initSurvey();
  }});

  // ── Approve ─────────────────────────────────────────────────────
  async function triggerApprove() {{
    showOverlay("confirming");
  }}

  async function confirmApprove() {{
    hideOverlay();
    lockButtons("Publishing… Approve, Regenerate, and Discard are locked while this runs.");
    showOverlay("loading", "Publishing...", "Triggering the publish workflow on GitHub Actions.");
    const res = await triggerWorkflow(APPROVE_WF, {{
      staging_filename: STAGING_FILE,
      month_year: ISSUE_MONTH_YEAR,
      roberts_take: takeText(),
      survey_wave: surveyPayload()
    }});
    if (!res) {{ unlockButtons(); return; }}
    if (res.status === 204) {{
      draftGone = true;
      document.getElementById("lock-banner-text").innerHTML = "✅ Published. This staging file no longer exists, so this page stays locked — visit the live blog to see the post, or generate a new draft next month.";
      showOverlay("success",
        "🎉 Post queued for publishing!",
        "The approve-blog workflow is now running. Your post will be live in ~2 minutes.",
        `https://github.com/${{REPO}}/actions/workflows/${{APPROVE_WF}}`
      );
    }} else {{
      const body = await res.json().catch(() => ({{}}));
      unlockButtons();
      showOverlay("error", "Publish failed", apiErrorMessage(res, body));
    }}
  }}

  // ── Discard ─────────────────────────────────────────────────────
  async function triggerDiscard() {{
    showOverlay("confirming-discard");
  }}

  async function confirmDiscard() {{
    hideOverlay();
    lockButtons("Discarding… Approve, Regenerate, and Discard are locked while this runs.");
    showOverlay("loading", "Discarding draft...", "Triggering the discard workflow on GitHub Actions.");
    const res = await triggerWorkflow(DISCARD_WF, {{
      staging_filename: STAGING_FILE
    }});
    if (!res) {{ unlockButtons(); return; }}
    if (res.status === 204) {{
      draftGone = true;
      document.getElementById("lock-banner-text").innerHTML = "🗑️ Discarded. This staging file no longer exists, so this page stays locked — nothing was published. Wait for next month's draft, or trigger monthly-blog.yml manually with Force run.";
      showOverlay("success",
        "🗑️ Draft discarded",
        "The discard-blog workflow is now running. Nothing was published — this only removed the staging draft.",
        `https://github.com/${{REPO}}/actions/workflows/${{DISCARD_WF}}`
      );
    }} else {{
      const body = await res.json().catch(() => ({{}}));
      unlockButtons();
      showOverlay("error", "Discard failed", apiErrorMessage(res, body));
    }}
  }}

  // ── Regenerate ──────────────────────────────────────────────────
  async function triggerRegenerate() {{
    const prompt = document.getElementById("prompt-input").value.trim();
    if (!prompt) {{
      showToast("Please enter a prompt describing what to change.", "error");
      document.getElementById("prompt-input").focus();
      return;
    }}
    saveLastPrompt(prompt);
    // Locked immediately, before the network round-trip: regeneration almost
    // always produces a NEW staging filename (it's stamped with today's
    // date), which orphans the filename this page currently knows about.
    // Approving or re-triggering against that stale value fails or, worse,
    // targets the wrong file — so both actions stay locked until a full
    // page reload picks up the real current state.
    lockButtons();
    showOverlay("loading", "🔄 Triggering regeneration...",
      "GitHub Actions will regenerate the post with your prompt. This takes ~5 minutes. This page will reload itself automatically once the new version is live."
    );
    const res = await triggerWorkflow(REGENERATE_WF, {{
      prompt: prompt,
      staging_filename: STAGING_FILE,
      coverage_month: COVERAGE_MONTH_YEAR
    }});
    if (!res) {{ hideOverlay(); unlockButtons(); return; }}
    if (res.status === 204) {{
      startPolling();
      showOverlay("regen-queued", "⏳ Regeneration queued!",
        "This page checks every 15s for up to 10 min and reloads itself the moment the new version is live — you can close this dialog and it'll keep watching.",
        `https://github.com/${{REPO}}/actions/workflows/${{REGENERATE_WF}}`
      );
    }} else {{
      const body = await res.json().catch(() => ({{}}));
      hideOverlay();
      unlockButtons();
      showToast(apiErrorMessage(res, body), "error");
    }}
  }}

  // ── Redraft one section ─────────────────────────────────────────
  // Unlike a full regeneration this rewrites a single section in place. The
  // staging filename does not change, so the buttons are NOT locked the way
  // triggerRegenerate() locks them — there is no orphaned filename to guard
  // against, and locking Approve for a one-section edit would be a nuisance.
  async function triggerRedraft() {{
    const section  = document.getElementById("redraft-section").value;
    const guidance = document.getElementById("redraft-guidance").value.trim();
    if (!section) {{
      showToast("Pick which section to redraft.", "error");
      return;
    }}
    const label = document.getElementById("redraft-section")
                    .selectedOptions[0].textContent;
    showOverlay("loading", "Redrafting " + label + "...",
      "Gemini is rewriting just this section from the issue as it already stands. Takes about a minute."
    );
    const res = await triggerWorkflow(REDRAFT_WF, {{
      staging_filename: STAGING_FILE,
      section: section,
      guidance: guidance,
      month_year: COVERAGE_MONTH_YEAR
    }});
    if (!res) {{ hideOverlay(); return; }}
    if (res.status === 204) {{
      startPolling();
      showOverlay("regen-queued", "Redraft queued",
        "This page checks every 15s and reloads once the new version is live. Every other section stays exactly as it is.",
        `https://github.com/${{REPO}}/actions/workflows/${{REDRAFT_WF}}`
      );
    }} else {{
      const body = await res.json().catch(() => ({{}}));
      hideOverlay();
      showToast(apiErrorMessage(res, body), "error");
    }}
  }}

  function setRedraftGuidance(text) {{
    const el = document.getElementById("redraft-guidance");
    el.value = text;
    el.focus();
  }}

  // ── Prompt chips ────────────────────────────────────────────────
  function setPrompt(text) {{
    document.getElementById("prompt-input").value = text;
    document.getElementById("prompt-input").focus();
  }}

  function openStagingPost() {{
    const bust = Date.now() + "_" + Math.random().toString(36).slice(2);
    window.open(`/blog/staging/${{STAGING_FILE}}?v=${{bust}}`, "_blank");
  }}

  // ── Toast ────────────────────────────────────────────────────────
  let toastTimer;
  function showToast(msg, type = "info") {{
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `show ${{type}}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {{ el.className = ""; }}, 4000);
  }}

  // ── Overlay ──────────────────────────────────────────────────────
  function showOverlay(type, title = "", body = "", actionUrl = "") {{
    const card = document.getElementById("overlay-card");
    const overlay = document.getElementById("overlay");
    let html = "";
    if (type === "confirming") {{
      html = `
        <div class="overlay-icon">📤</div>
        <div class="overlay-title">Ready to publish?</div>
        <div class="overlay-body">This will publish <code>${{STAGING_FILE}}</code> — promote it to production, update <code>latest.html</code>, regenerate the sitemap, and ping Google. Double-check that filename matches what you've been reviewing in the frame on the right — if you regenerated recently and haven't reloaded this page, it may not.</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;">
          <button class="btn btn-outline" onclick="hideOverlay()">Cancel</button>
          <button class="btn btn-primary" onclick="confirmApprove()">Yes, Publish Now</button>
        </div>`;
    }} else if (type === "confirming-discard") {{
      html = `
        <div class="overlay-icon">🗑️</div>
        <div class="overlay-title">Discard this draft?</div>
        <div class="overlay-body">This permanently deletes <code>${{STAGING_FILE}}</code> from staging. Nothing is published or affected — it only undoes the generation. This can't be undone; you'd need to regenerate or wait for the next automatic run.</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;">
          <button class="btn btn-outline" onclick="hideOverlay()">Cancel</button>
          <button class="btn btn-discard-outline" style="border-color:var(--red);" onclick="confirmDiscard()">Yes, Discard It</button>
        </div>`;
    }} else if (type === "loading") {{
      html = `<div class="spinner"></div><div class="overlay-title">${{title}}</div><div class="overlay-body">${{body}}</div>`;
    }} else if (type === "success") {{
      html = `
        <div class="overlay-icon">✅</div>
        <div class="overlay-title">${{title}}</div>
        <div class="overlay-body">${{body}}</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;flex-wrap:wrap;">
          ${{actionUrl ? `<a href="${{actionUrl}}" target="_blank" class="btn btn-secondary">View Workflow Run</a>` : ""}}
          <a href="https://www.imetrobert.com/blog/" target="_blank" class="btn btn-primary">View Live Blog</a>
          <button class="btn btn-outline" onclick="hideOverlay()">Close</button>
        </div>`;
    }} else if (type === "regen-queued") {{
      html = `
        <div class="overlay-icon">⏳</div>
        <div class="overlay-title">${{title}}</div>
        <div class="overlay-body">${{body}}</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;flex-wrap:wrap;">
          ${{actionUrl ? `<a href="${{actionUrl}}" target="_blank" class="btn btn-secondary">Watch Workflow</a>` : ""}}
          <button class="btn btn-outline" onclick="hideOverlay()">Dismiss (still watching)</button>
        </div>`;
    }} else if (type === "error") {{
      html = `
        <div class="overlay-icon">❌</div>
        <div class="overlay-title">${{title}}</div>
        <div class="overlay-body">${{body}}</div>
        <button class="btn btn-outline" onclick="hideOverlay()">Close</button>`;
    }}
    card.innerHTML = html;
    overlay.classList.add("show");
  }}

  function hideOverlay() {{
    document.getElementById("overlay").classList.remove("show");
  }}

  // ── Auto-refresh polling after regeneration ─────────────────────
  // Polls the freshly-pushed preview.html itself (not the iframe) and, once
  // it sees the regen badge, does a FULL page reload — not just an iframe
  // refresh. Regeneration renames the staging file (new date-stamped
  // filename) essentially every time, so only a real reload of this parent
  // page picks up the new STAGING_FILE constant baked in server-side.
  // Refreshing just the iframe would leave Approve pointed at a filename
  // that's already been deleted.
  let pollInterval;
  function startPolling() {{
    if (pollInterval) return; // already watching — don't stack intervals
    let checks = 0;
    pollInterval = setInterval(async () => {{
      checks++;
      if (checks > 40) {{
        clearInterval(pollInterval);
        pollInterval = null;
        lockButtons(
          `Regeneration is taking longer than 10 minutes or may have failed. ` +
          `<a href="https://github.com/${{REPO}}/actions/workflows/${{REGENERATE_WF}}" target="_blank">Check the Actions tab</a>, ` +
          `then reload once you've confirmed it finished.`
        );
        showToast("Stopped auto-checking — see the sidebar for what to do next.", "error");
        return;
      }}
      try {{
        const r = await fetch(`/blog/staging/preview.html?nocache=${{Date.now()}}`, {{ cache: "no-store" }});
        const text = await r.text();
        if (text.includes("🔄 Regenerated with custom prompt")) {{
          clearInterval(pollInterval);
          pollInterval = null;
          showToast("✅ New version ready! Reloading page…", "success");
          // forceRefresh, not location.reload. This branch is reached because
          // a cache-busted fetch proved a NEW page exists — reloading the
          // same URL can still be served the old one from cache, which lands
          // you back on the previous run's timestamp having been told the new
          // version was ready.
          setTimeout(forceRefresh, 1200);
        }}
      }} catch (e) {{}}
    }}, 15000);
  }}
</script>

</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename",    required=True, help="Staging HTML filename")
    parser.add_argument("--month",       required=True, help="Month year label, e.g. May 2026")
    parser.add_argument("--run-id",      default="0",   help="GitHub Actions run ID")
    parser.add_argument("--regenerated", action="store_true", help="Flag post as regenerated")
    args = parser.parse_args()

    html = build_preview_html(
        staging_filename=args.filename,
        month_year=args.month,
        run_id=args.run_id,
        regenerated=args.regenerated
    )

    os.makedirs("blog/staging", exist_ok=True)
    output_path = "blog/staging/preview.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Preview page written to: {output_path}")


if __name__ == "__main__":
    main()
