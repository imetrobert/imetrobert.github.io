"""Resolve a rebase conflict in blog/staging/usage.json (the daily Gemini request ledger).

Two workflows can finish at the same time and both append to the ledger; git cannot merge the
numbers. During a rebase, stage :2 is the upstream version and :3 is ours. The ledger only counts
things, so keeping the larger value for every number is a safe merge (it can under-count a few
requests, never lose a day or a model).
Usage: python3 scripts/merge_usage.py blog/staging/usage.json   (run while the conflict is open)
"""
import json
import subprocess
import sys


def show(stage, path):
    return json.loads(subprocess.check_output(["git", "show", f":{stage}:{path}"], text=True))


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: merge(a[k], b[k]) if k in a and k in b else (a[k] if k in a else b[k])
                for k in sorted(set(a) | set(b))}
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return max(a, b)
    return b


def main(path):
    merged = merge(show(2, path), show(3, path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
