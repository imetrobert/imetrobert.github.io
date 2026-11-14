#!/usr/bin/env python3
"""
runlog.py
One place for the blog pipeline's failures to be recorded and explained.

Why it exists: when a redraft or a monthly run goes wrong, the only trace used to be a
long Actions log. This module gives every entry point (redraft, regenerate, monthly
generation, approve, discard) the same three things:

  1. ERROR CODES with a plain-language message and the next step to take (CATALOGUE).
  2. A PERSISTENT LOG, blog/staging/run-log.json (newest last, capped), committed with the
     staging files so it survives the run. It is what the preview page and a future
     troubleshooting chat read first.
  3. GitHub ANNOTATIONS and a step summary, so the failing run itself says what happened.

Usage from a script:
    import runlog
    runlog.record("redraft", "failed", code="TOO_SIMILAR", detail="...", section="FROM ROBERTS DESK")
    code = runlog.classify(exception_or_text)       # best guess code for an exception
    runlog.fail("redraft", code, detail)            # prints, annotates, logs, returns the message

Offline: python3 scripts/runlog.py explain TOO_SIMILAR | python3 scripts/runlog.py tail 10
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.getcwd(), "blog", "staging", "run-log.json")
MAX_ENTRIES = 150

# code: (what happened, what to do). Keep these plain: they are shown to a non-engineer
# on a phone and to a chat that has never seen this repo.
CATALOGUE = {
    "OK": ("Finished normally.", ""),
    "NO_API_KEY": (
        "The Gemini key is not available to this run.",
        "Repo Settings > Secrets and variables > Actions: check GEMINI_API_KEY exists, then run again."),
    "API_KEY_REJECTED": (
        "Google rejected the Gemini key (403).",
        "The key was revoked or restricted. Create a new key in Google AI Studio, replace the GEMINI_API_KEY secret, run again."),
    "QUOTA_EXHAUSTED": (
        "Gemini free-tier limits were hit (429). The model said 'too many requests' on every try.",
        "Wait until the quota resets (midnight Pacific) or a minute for the per-minute limit, then run again. "
        "The approval page's quota panel shows today's requests."),
    "MODEL_UNAVAILABLE": (
        "The chosen Gemini model is not available to this key (404/400).",
        "On the approval page press Back to Auto, or pin a different model. Weekly Model Scout also fixes this."),
    "UNGROUNDED_REJECTED": (
        "No Gemini model returned an answer backed by live web search, so nothing was changed (on purpose).",
        "Run again later. Text written without search presents old news as current."),
    "ALL_MODELS_FAILED": (
        "Every Gemini model in the fallback list failed.",
        "Open the run log and look for HTTP status lines (429, 500, 503, timeout). Usually temporary: run again in 10 minutes."),
    "FORMAT_MISMATCH": (
        "The model's answer did not fit the format this section needs.",
        "Nothing was changed. Run again; if it repeats, give a more specific direction or pin a stronger model."),
    "JUNK_OUTPUT": (
        "The model returned notes or chat text instead of the section (for example a checklist or 'Here is...').",
        "Nothing was changed. Run again; this is usually a weaker or busy model."),
    "TOO_SHORT": (
        "The model's answer was too short for this section.",
        "Nothing was changed. Run again."),
    "TOO_SIMILAR": (
        "The new draft was nearly the same as the current one, so it was not applied.",
        "Add a direction (what angle to take) and run again; blank directions ask only for a different angle."),
    "BLOCK_NOT_FOUND": (
        "The section could not be located in the staged page.",
        "The page layout may have changed. Regenerate the issue, or check renderer.py block classes."),
    "FILE_MISSING": (
        "The staging file was not found.",
        "It may already be approved or discarded. Check blog/staging/ and blog/posts/."),
    "VERIFY_FAILED": (
        "The edit was written but the check afterwards found a problem, so it was rolled back.",
        "Nothing changed. Open the run log: it lists which check failed."),
    "SECTION_NOT_REDRAFTABLE": (
        "That section cannot be redrafted by itself.",
        "Only the four judgment sections can. Reported sections come back only by regenerating the whole issue."),
    "UNEXPECTED": (
        "Something unexpected went wrong.",
        "Open the failing step in the run log; the last lines name the error. Nothing was changed if the step is the redraft."),
}


def explain(code):
    what, todo = CATALOGUE.get(code, CATALOGUE["UNEXPECTED"])
    return what, todo


def classify(err):
    """Best-guess error code from an exception or a message."""
    t = str(err or "").lower()
    if "gemini_api_key is not set" in t or "no api key" in t:
        return "NO_API_KEY"
    if "403" in t or "key rejected" in t:
        return "API_KEY_REJECTED"
    if "search-grounded" in t or "ungrounded" in t:
        return "UNGROUNDED_REJECTED"
    if "429" in t or "quota" in t or "rate limit" in t or "resource_exhausted" in t:
        return "QUOTA_EXHAUSTED"
    if "all gemini models failed" in t:
        return "ALL_MODELS_FAILED"
    if "404" in t or "not found for api" in t or "no longer available" in t:
        return "MODEL_UNAVAILABLE"
    return "UNEXPECTED"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load():
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record(kind, status, code="OK", detail="", **extra):
    """Append one event to blog/staging/run-log.json. Never raises: logging must not break a run."""
    try:
        what, todo = explain(code)
        entry = {
            "at": _now(),
            "run": os.getenv("GITHUB_RUN_ID", ""),
            "kind": kind,            # redraft | regenerate | monthly | approve | discard | scout | test
            "status": status,        # ok | failed | skipped
            "code": code,
            "message": what,
            "next": todo,
            "detail": str(detail)[:600],
        }
        entry.update({k: v for k, v in extra.items() if v not in (None, "")})
        log = _load()
        log.append(entry)
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log[-MAX_ENTRIES:], f, indent=1, ensure_ascii=False)
        return entry
    except Exception as e:  # pragma: no cover
        print(f"  (run log not written: {e})")
        return None


def _annotate(level, title, message):
    # GitHub turns these lines into a red/yellow banner on the run page.
    message = message.replace("\r", " ").replace("\n", " ")
    print(f"::{level} title={title}::{message}")


def _summary(lines):
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


def fail(kind, code, detail="", **extra):
    """Print a clear failure, annotate the run, log it. Returns the plain message."""
    what, todo = explain(code)
    print(f"\n  RESULT: FAILED [{code}] {what}")
    if todo:
        print(f"  NEXT STEP: {todo}")
    if detail:
        print(f"  DETAIL: {str(detail)[:400]}")
    _annotate("error", f"{kind} failed: {code}", f"{what} {todo}".strip())
    _summary([f"## {kind} failed: `{code}`", "", what, "", f"**Next step:** {todo}" if todo else "",
              f"", f"Detail: {str(detail)[:400]}" if detail else ""])
    record(kind, "failed", code, detail, **extra)
    return what


def ok(kind, detail="", **extra):
    print(f"\n  RESULT: OK. {detail}")
    _summary([f"## {kind}: OK", "", str(detail)])
    record(kind, "ok", "OK", detail, **extra)


def _cli(argv):
    if len(argv) >= 3 and argv[1] == "explain":
        what, todo = explain(argv[2])
        print(what, "\n", todo)
    elif len(argv) >= 2 and argv[1] == "last":
        # One HTML-safe line about the newest failure, for failure notices: python3 scripts/runlog.py last
        from html import escape
        fails = [e for e in _load() if e.get("status") == "failed"]
        if fails:
            e = fails[-1]
            print(escape(f'[{e["code"]}] {e["message"]} Next step: {e["next"]} (detail: {e["detail"][:160]})'))
        else:
            print("No reason was recorded; open the failed run and read the last lines of the failing step.")
    elif len(argv) >= 2 and argv[1] == "tail":
        n = int(argv[2]) if len(argv) > 2 else 10
        for e in _load()[-n:]:
            print(f'{e["at"]} {e["kind"]:10} {e["status"]:7} {e["code"]:20} {e.get("section","")} {e["detail"][:100]}')
    else:
        print(__doc__)


if __name__ == "__main__":
    _cli(sys.argv)
