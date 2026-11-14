#!/usr/bin/env bash
# Commit blog/staging/run-log.json (the persistent failure/success log) even when the step before it failed.
# Used as an `if: always()` step so a failed run still leaves its explanation in the repo.
set -uo pipefail
[ -f blog/staging/run-log.json ] || exit 0
git config --local user.email "action@github.com"
git config --local user.name "Blog run log"
git add blog/staging/run-log.json
if git diff --staged --quiet; then exit 0; fi
git commit -m "Run log: $(date +%Y-%m-%d) (${GITHUB_WORKFLOW:-manual} run ${GITHUB_RUN_ID:-local})" || exit 0
bash scripts/git_push_retry.sh || echo "run log push failed (not fatal)"
