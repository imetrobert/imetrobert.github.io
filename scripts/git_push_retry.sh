#!/usr/bin/env bash
# Push the current branch; if another workflow pushed first (keepalive.yml and the
# usage ledger are not in the blog-pipeline concurrency group), rebase onto
# origin/main and try again instead of failing a run that already finished its
# expensive Gemini work.
set -uo pipefail
for i in 1 2 3 4; do
  if git push; then exit 0; fi
  echo "Push rejected (attempt $i of 4). Rebasing onto origin/main and retrying."
  if ! git pull --rebase origin main; then
    git rebase --abort 2>/dev/null || true
    echo "Rebase conflict; cannot retry automatically."
    exit 1
  fi
  sleep $((i * 3))
done
echo "Push still failing after 4 attempts."
exit 1
