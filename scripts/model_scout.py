#!/usr/bin/env python3
"""
model_scout.py: find, test and rank Gemini models so the blog always leads with
the best FREE model that actually works, without anyone picking one by hand.

Why a scout instead of "use the newest model": being listed by the API does not
mean a model is callable on the free tier (429 on every request), supports
search grounding (the monthly issue must be built from live search), or writes a
complete issue. gemini-3.8-flash led once, failed, and cost a monthly run. So a
model leads only after it has PASSED, in order:

  1. PROBE: one tiny search-grounded request. Catches 404, 429 (no free quota),
     400 (grounding unsupported), and "answered without searching".
  2. TRIAL: one full-size issue generation with the real prompt, then a quality
     gate (all sections present, long enough Desk essay, enough items parsed).

Qualified models are recorded in blog/model-config.json; gemini.py leads with the
best one (utils.resolve_model_order) and keeps the built-in baseline as the
tail of the fallback chain. Each run also re-probes the current leader and
demotes it if it stopped working. Rejected models are retried after a cooldown
(free quota is sometimes added later).

Cost: at most 1 probe for the leader + 2 candidate probes + 1 trial per run, and
only when a newer candidate exists. Never raises; never touches an issue.

Usage:  GEMINI_API_KEY=... python3 scripts/model_scout.py [--dry-run]
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))

from utils import (DEFAULT_MODEL_ORDER, discover_models, is_text_generation_model,
                   load_model_config, model_rank_key, record_gemini_request,
                   resolve_model_order, save_model_config, version_tuple)

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

REJECT_COOLDOWN_DAYS = 14      # probe failures: quota/availability changes
QUALITY_COOLDOWN_DAYS = 30     # wrote a poor issue: models change slowly
MAX_CANDIDATES_PER_RUN = 2
MIN_LEADER_RPD = 200           # known free-tier daily limit below this: never lead
LOG_KEEP = 12

PROBE_PROMPT = ("Use Google Search. In one sentence of at most 25 words, name one "
                "Canadian artificial intelligence news item from the past two weeks.")


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


# --------------------------------------------------------------------------
# Candidate selection
# --------------------------------------------------------------------------

def is_candidate(name):
    """A full flash-class text model: the only kind that can lead an issue.

    Lite models flatten the judgment half of the issue and Pro models have
    free-tier limits of a few requests a day, so neither may lead. They can
    still sit in the fallback chain (the baseline already has flash-lite).
    """
    low = (name or "").lower()
    return (is_text_generation_model(low) and "flash" in low
            and "lite" not in low and "pro" not in low)


def pick_candidates(discovered, cfg, now=None):
    """Newest-first models worth testing: newer than the current leader, not
    already qualified, and not rejected recently."""
    now = now or now_utc()
    qualified = set((cfg.get("qualified") or {}).keys())
    rejected = cfg.get("rejected") or {}
    leader = resolve_model_order({**cfg, "mode": "auto"})[0]
    out = []
    for name in discovered:
        if not is_candidate(name) or name in DEFAULT_MODEL_ORDER or name in qualified:
            continue
        if name in (cfg.get("dismissed") or []):
            continue          # "Hide this one" on the preview page is honoured
        # A known tiny daily limit (gemini-3.8-flash: 20) cannot carry regenerates
        # and redrafts on top of the monthly run, so it never leads.
        if int((cfg.get("limits") or {}).get(name, 10**6)) < MIN_LEADER_RPD:
            continue
        if version_tuple(name) <= version_tuple(leader):
            continue
        retry_after = parse_iso((rejected.get(name) or {}).get("retry_after", ""))
        if retry_after and now < retry_after:
            continue
        out.append(name)
    return sorted(out, key=model_rank_key)[:MAX_CANDIDATES_PER_RUN]


# --------------------------------------------------------------------------
# Step 1: probe
# --------------------------------------------------------------------------

def _grounded(candidate):
    gm = candidate.get("groundingMetadata") or {}
    return bool(gm.get("webSearchQueries") or gm.get("groundingChunks")
                or gm.get("searchEntryPoint") or gm.get("groundingSupports"))


def probe(api_key, model, post=None, sleep=time.sleep):
    """One small grounded request. Returns {"ok": bool, "reason": str}."""
    post = post or requests.post
    url = f"{_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": PROBE_PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.2},
        "tools": [{"google_search": {}}],
    }
    status = None
    for attempt in range(2):
        try:
            r = post(url, json=payload, timeout=90)
        except Exception as exc:
            return {"ok": False, "reason": f"request failed ({type(exc).__name__})"}
        status = r.status_code
        try:
            record_gemini_request(model, 0)
        except Exception:
            pass
        # 429 / 5xx can be a passing spike: one retry, then judge.
        if status in (429, 500, 502, 503, 504) and attempt == 0:
            sleep(30)
            continue
        break
    if status == 200:
        try:
            data = r.json()
            cand = (data.get("candidates") or [{}])[0]
            parts = (cand.get("content") or {}).get("parts") or []
            text = " ".join(p.get("text", "") for p in parts
                            if p.get("text") and not p.get("thought")).strip()
        except Exception:
            return {"ok": False, "reason": "unreadable response"}
        if len(text) < 20:
            return {"ok": False, "reason": "empty answer"}
        if not _grounded(cand):
            return {"ok": False, "reason": "answered without using Google Search"}
        return {"ok": True, "reason": "ok"}
    reasons = {
        429: "429: no free-tier quota (or rate limited) on this project",
        404: "404: not callable with generateContent on this key",
        400: "400: request rejected (search grounding unsupported?)",
        403: "403: API key rejected",
    }
    return {"ok": False, "reason": reasons.get(status, f"HTTP {status}")}


# --------------------------------------------------------------------------
# Step 2: trial + quality gate
# --------------------------------------------------------------------------

def _words(text):
    return len((text or "").split())


def score_issue(content):
    """Quality gate for a full issue. Returns (passed, summary, failures).

    Deliberately about COMPLETENESS and shape, which is what a weaker or
    mismatched model gets wrong first (truncation, missing sections, a thin
    Desk essay, items the parser cannot read). It cannot judge insight, which
    is why the issue is still reviewed before it publishes.
    """
    from parser import (parse_sections, parse_developments, parse_spotlight_items,
                        parse_actions, parse_predictions, parse_question)
    failures = []
    sections = parse_sections(content)

    def count(fn, header, *args):
        try:
            return len(fn(sections.get(header, ""), *args))
        except Exception:
            return 0

    checks = {
        "developments": count(parse_developments, "KEY AI DEVELOPMENTS"),
        "spotlight": count(parse_spotlight_items, "CANADIAN SPOTLIGHT"),
        "actions": count(parse_actions, "STRATEGIC ACTIONS FOR THIS MONTH"),
        "predictions": count(parse_predictions, "LOOKING AHEAD: THREE PREDICTIONS"),
        "desk_words": _words(sections.get("FROM ROBERTS DESK", "")),
    }
    try:
        checks["question"] = 1 if parse_question(
            sections.get("ONE QUESTION FOR YOUR LEADERSHIP TEAM", "")) else 0
    except Exception:
        checks["question"] = 0
    minimums = {"developments": 5, "spotlight": 2, "actions": 3,
                "predictions": 3, "desk_words": 250, "question": 1}
    for key, need in minimums.items():
        if checks[key] < need:
            failures.append(f"{key} {checks[key]} < {need}")
    if not sections.get("EXECUTIVE SUMMARY", "").strip():
        failures.append("no executive summary")
        checks["executive_summary"] = 0
    else:
        checks["executive_summary"] = 1
    return (not failures), checks, failures


def trial(api_key, model):
    """Generate a full issue with ONLY this model and grade it."""
    try:
        from gemini import _call_gemini, _build_monthly_prompt, prepare_plan_block
        today = datetime.now()
        month_year = today.strftime("%B %Y")
        prev_month = (today.replace(day=1) - timedelta(days=1)).strftime("%B %Y")
        # The same research pass the monthly run does, once per scout run:
        # without the verified list most plan-change items lose their source
        # and every candidate would fail the developments count.
        prepare_plan_block(api_key, month_year, today, reuse=True)
        prompt = _build_monthly_prompt(month_year, prev_month, False, today)
        result = _call_gemini(api_key, prompt, max_output_tokens=8192, temperature=0.55,
                              use_search=True, min_chars=200, require_grounding=True,
                              models=[model])
    except Exception as exc:
        return {"ok": False, "reason": f"could not generate a grounded issue ({str(exc)[:90]})",
                "checks": {}}
    passed, checks, failures = score_issue(result.get("content", ""))
    if not passed:
        return {"ok": False, "reason": "quality: " + "; ".join(failures), "checks": checks}
    return {"ok": True, "reason": "ok", "checks": checks}


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def _log(cfg, msg):
    print(f"  {msg}")
    scout = cfg.setdefault("scout", {})
    scout.setdefault("log", []).append(f"{iso(now_utc())[:10]} {msg}")
    scout["log"] = scout["log"][-LOG_KEEP:]


def _reject(cfg, model, reason, days, now):
    cfg.setdefault("rejected", {})[model] = {
        "at": iso(now), "reason": reason, "retry_after": iso(now + timedelta(days=days))}
    cfg.get("qualified", {}).pop(model, None)


def run_scout(api_key, cfg, discovered=None, probe_fn=probe, trial_fn=trial, now=None):
    """Update cfg in place. Returns True if anything changed."""
    now = now or now_utc()
    before = (dict(cfg.get("qualified") or {}), dict(cfg.get("rejected") or {}))
    cfg.setdefault("qualified", {})
    cfg.setdefault("rejected", {})
    discovered = discover_models(api_key) if discovered is None else discovered

    # 1. The current best non-baseline leader must still work.
    for model in list(cfg["qualified"].keys()):
        res = probe_fn(api_key, model)
        if res["ok"]:
            cfg["qualified"][model]["verified"] = iso(now)
            _log(cfg, f"{model}: still working")
        else:
            _reject(cfg, model, res["reason"], REJECT_COOLDOWN_DAYS, now)
            _log(cfg, f"{model}: DEMOTED ({res['reason']})")

    # 2. Newer candidates: probe, then a full trial. Newest first; once one
    #    qualifies, anything older than it is no longer a candidate.
    for model in pick_candidates(discovered, cfg, now):
        res = probe_fn(api_key, model)
        if not res["ok"]:
            _reject(cfg, model, res["reason"], REJECT_COOLDOWN_DAYS, now)
            _log(cfg, f"{model}: rejected at probe ({res['reason']})")
            continue
        _log(cfg, f"{model}: probe passed, running a full trial issue")
        t = trial_fn(api_key, model)
        if not t["ok"]:
            _reject(cfg, model, t["reason"], QUALITY_COOLDOWN_DAYS, now)
            _log(cfg, f"{model}: rejected after trial ({t['reason']})")
            continue
        cfg["qualified"][model] = {"at": iso(now), "verified": iso(now), "checks": t["checks"]}
        cfg["rejected"].pop(model, None)
        _log(cfg, f"{model}: QUALIFIED {t['checks']}")
        break

    # 3. Bookkeeping: the new order, and no stale "offer" for the old UI.
    cfg["order"] = resolve_model_order({**cfg, "mode": "auto"})
    cfg["available"] = []
    cfg["known"] = sorted(set(cfg.get("known") or []) | {m for m in discovered if is_candidate(m)})
    cfg.setdefault("scout", {})["last_run"] = iso(now)
    return before != (cfg["qualified"], cfg["rejected"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Test but do not write the config")
    args = ap.parse_args()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set; nothing to scout.")
        return 0
    print("=== Model scout ===")
    try:
        cfg = load_model_config()
        changed = run_scout(api_key, cfg)
        leader = resolve_model_order(cfg)[0]
        print(f"  Leader now: {leader} (mode: {cfg.get('mode')}); changed: {changed}")
        if not args.dry_run:
            save_model_config(cfg)
    except Exception as exc:  # the scout must never break anything else
        print(f"  Scout failed safely: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
