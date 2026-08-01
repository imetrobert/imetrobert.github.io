"""
add_survey_wave.py
Records a survey wave into data/survey.json from the preview page, so results
never require hand-editing a JSON file.

Called by approve-blog.yml with a JSON blob assembled by the preview form.
Validated rather than trusted: option keys must match the configured questions,
counts must be non-negative integers, and n must agree with what was submitted.
A wave that fails validation is rejected and the publish continues — a bad wave
silently entering a page whose whole value is being trustworthy would be worse
than no wave at all.

Re-submitting a wave with an existing label replaces it, so a correction is
just a second submission.

    python3 scripts/add_survey_wave.py '<json>'
"""

import json
import os
import sys

CONFIG = "data/survey.json"


def validate(cfg, wave):
    if not isinstance(wave, dict):
        return "payload is not an object"
    label = (wave.get("label") or "").strip()
    if not label:
        return "missing label"
    results = wave.get("results")
    if not isinstance(results, dict) or not results:
        return "missing results"

    known = {q["id"]: set(q["options"]) for q in cfg.get("questions", [])}
    total_by_q = []
    for qid, counts in results.items():
        if qid not in known:
            return f"unknown question id '{qid}'"
        if not isinstance(counts, dict):
            return f"counts for '{qid}' are not an object"
        for opt, val in counts.items():
            if opt not in known[qid]:
                return f"unknown option '{opt}' for question '{qid}'"
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                return f"count for '{qid}/{opt}' is not a non-negative integer"
        s = sum(counts.values())
        if s:
            total_by_q.append(s)

    if not total_by_q:
        return "every count is zero"

    n = wave.get("n")
    if not isinstance(n, int) or n <= 0:
        return "n must be a positive integer"
    # Respondents can skip questions, so per-question totals may be below n,
    # but none may exceed it — that would mean more answers than respondents.
    if max(total_by_q) > n:
        return f"a question has {max(total_by_q)} answers but n is {n}"
    return None


def add_wave(payload):
    if not os.path.exists(CONFIG):
        print("  No data/survey.json — nothing to record into.")
        return False
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)

    try:
        wave = json.loads(payload) if isinstance(payload, str) else payload
    except Exception as e:
        print(f"  Survey wave rejected: could not parse JSON ({e})")
        return False

    problem = validate(cfg, wave)
    if problem:
        print(f"  Survey wave rejected: {problem}")
        return False

    waves = [w for w in cfg.get("waves", []) if w.get("label") != wave["label"]]
    replaced = len(waves) != len(cfg.get("waves", []))
    waves.append(wave)
    waves.sort(key=lambda w: w.get("date", ""))
    cfg["waves"] = waves

    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")

    verb = "replaced" if replaced else "recorded"
    print(f"  Survey wave {verb}: {wave['label']} (n={wave['n']}). "
          f"{len(waves)} wave(s) on file.")
    return True


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else ""
    if not raw.strip():
        print("  No survey wave submitted.")
        sys.exit(0)
    try:
        add_wave(raw)
    except Exception as e:
        print(f"  Survey wave skipped ({e})")
    sys.exit(0)                          # never fail the publish over this
