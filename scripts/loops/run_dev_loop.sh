#!/usr/bin/env bash
# Dev contributor loop runner — free model opens PRs per CONTRIBUTING.md.
#
# One invocation = one contribution attempt (one PR). Schedule it on an interval
# (cron on your VPS, or WSL); the Opus PR-review loop reviews & merges what it opens.
#   crontab:  */30 * * * *  /mnt/g/tennis\ betting/scripts/loops/run_dev_loop.sh
#
# Requires: opencode on PATH, gh authenticated, OPENROUTER_API_KEY exported
# (or in the repo .env). Model is the free tier: nex-agi/nex-n2-pro:free via OpenRouter.
set -euo pipefail

REPO="${UNABETTING_REPO_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
MODEL="${DEV_LOOP_MODEL:-openrouter/nex-agi/nex-n2-pro:free}"
LOGDIR="$REPO/reports/loops"
PROMPT_FILE="$REPO/scripts/loops/dev_contribute.md"

cd "$REPO"
[ -f .env ] && set -a && . ./.env && set +a || true
: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY (env or .env) before running}"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/dev_contribute_$(date +%Y%m%d_%H%M%S).log"

# Always start from a clean, up-to-date main so each run picks fresh work.
git fetch origin --quiet
git switch --quiet main 2>/dev/null || git switch --quiet --create main origin/main
git reset --hard --quiet origin/main

PROMPT="Read and execute the instructions in scripts/loops/dev_contribute.md. \
Work fully autonomously, ask no questions, open exactly ONE pull request, and \
NEVER push to main or merge. Follow CONTRIBUTING.md literally."

# opencode headless run on the free OpenRouter model (adjust the flag if your opencode
# build differs: some use `-m`, some `--model`; both are shown for reference).
opencode run --model "$MODEL" "$PROMPT" 2>&1 | tee "$LOG"

# prune logs older than 30 days
find "$LOGDIR" -name 'dev_contribute_*.log' -mtime +30 -delete 2>/dev/null || true
