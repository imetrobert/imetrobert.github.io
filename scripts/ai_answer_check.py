#!/usr/bin/env python3
"""Monthly AI-answer check: does Google's AI (Gemini with search) name or cite Robert's sites for the questions
his clients would ask? Writes ops/ai-answer-log.json (last 12 runs). The weekly health check in
imetrobert/aiwithrobert-root reads it from www.imetrobert.com/ops/ai-answer-log.json and fails if no run is
recent. It sees Gemini only, never ChatGPT, Perplexity or Claude.  Run from the repo root:
    GEMINI_API_KEY=... python3 scripts/ai_answer_check.py
Edit QUESTIONS below to change what is asked (keep them to what a real client would type)."""
import json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "ops/ai-answer-log.json"
QUESTIONS = [
    "AI tutor for seniors in Côte Saint-Luc, Montreal",
    "AI training for small businesses in Montreal",
    "who is Robert Simon, AI thought leader in Montreal",
    "free AI feasibility check for a small business in Canada",
    "formation en IA pour les aînés à Montréal",
    "monthly briefing on what low-cost AI plans can do for small Canadian businesses",
]
DOMAINS = ("aiwithrobert.com", "imetrobert.com")
NAMES = ("ai with robert", "aiwithrobert", "robert simon", "imetrobert")


def analyse(question, answer):
    """answer = the dict _call_gemini returns. Pure function (tested offline)."""
    text = (answer.get("content") or "").lower()
    chunks = (answer.get("grounding") or {}).get("chunks") or []
    cited = any(d in ((c.get("title") or "") + " " + (c.get("uri") or "")).lower() for c in chunks for d in DOMAINS)
    named = any(n in text for n in NAMES)
    return {"q": question, "named": named, "cited": cited,
            "sources": [c.get("title") or c.get("uri") or "" for c in chunks][:5]}


def run(call):
    results = []
    for q in QUESTIONS:
        try:
            results.append(analyse(q, call(q)))
        except Exception as e:                      # one question failing must not lose the others
            results.append({"q": q, "error": f"{type(e).__name__}: {str(e)[:120]}"})
    return results


def main():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("GEMINI_API_KEY is not set")
        return 1
    from gemini import _call_gemini
    call = lambda q: _call_gemini(key, q, 1500, temperature=0.2, use_search=True, min_chars=40, require_grounding=True)
    results = run(call)
    ok = [r for r in results if "error" not in r]
    if not ok:
        print("every question failed:", results[0].get("error"))
        return 1
    log = {"runs": []}
    if os.path.exists(OUT):
        try:
            log = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            pass
    log["runs"] = (log.get("runs", []) + [{"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "results": results}])[-12:]
    os.makedirs("ops", exist_ok=True)
    json.dump(log, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(OUT, "a").write("\n")
    print(f"asked {len(results)}, answered {len(ok)}: named in {sum(r['named'] for r in ok)}, cited in {sum(r['cited'] for r in ok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
