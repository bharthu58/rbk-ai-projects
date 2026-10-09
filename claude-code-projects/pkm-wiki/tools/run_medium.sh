#!/usr/bin/env bash
# run_medium.sh — Medium article ingestion pipeline
#
# SETUP (first time only):
#   1. pip install -r tools/medium_ingest/requirements.txt
#   2. playwright install chrome    (installs real Chrome for Playwright)
#   3. bash tools/run_medium.sh --login
#      → Browser opens. Log in to Medium, complete any verification, press ENTER.
#      → Session is saved to ~/.medium_ingest_profile for all future runs.
#
# USAGE:
#   bash tools/run_medium.sh --check-auth
#   bash tools/run_medium.sh --bookmarks --limit 5
#   bash tools/run_medium.sh --topic "system design" --limit 10
#   bash tools/run_medium.sh --list-url "https://medium.com/me/list/YOUR-LIST-ID" --limit 10
#   bash tools/run_medium.sh --bookmarks --dry-run
#   bash tools/run_medium.sh --bookmarks --raw    # no LLM, dump to raw/ for /wiki-ingest
#
# If login expires mid-session, the browser will pause and prompt you to re-login.
# After this script completes, run /wiki-ingest in Claude Code to integrate
# the new files into the wiki (backlinks, index entry, move to ingested/).

# --- credentials -----------------------------------------------------------
# export ANTHROPIC_API_KEY="paste_here"   # required for LLM structuring (--raw skips this)

# --- optional overrides ----------------------------------------------------
# export MEDIUM_LLM_MODEL="claude-sonnet-4-6"   # default: claude-haiku-4-5-20251001
# export WIKI_ROOT="/path/to/wiki"               # auto-detected via wiki-config.md

cd "$(dirname "$0")" && python -m medium_ingest "$@"
