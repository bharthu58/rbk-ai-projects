#!/usr/bin/env bash
# run_podcast.sh — Spotify podcast ingestion pipeline
#
# Credentials come from the environment (never hardcode them here):
#   export SPOTIFY_CLIENT_ID=...
#   export SPOTIFY_CLIENT_SECRET=...
#   export OPENAI_API_KEY=...   # optional — only needed if Whisper audio fallback triggers
#
# Then run:
#   bash tools/run_podcast.sh "https://open.spotify.com/episode/XYZ"

missing=()
[ -n "${SPOTIFY_CLIENT_ID:-}" ] || missing+=(SPOTIFY_CLIENT_ID)
[ -n "${SPOTIFY_CLIENT_SECRET:-}" ] || missing+=(SPOTIFY_CLIENT_SECRET)
if [ ${#missing[@]} -gt 0 ]; then
  echo "run_podcast.sh: missing required environment variable(s): ${missing[*]}" >&2
  echo "Export them in your shell before running (see tools/run_podcast.sh header)." >&2
  exit 1
fi
export SPOTIFY_CLIENT_ID SPOTIFY_CLIENT_SECRET

cd "$(dirname "$0")" && python -m podcast_ingest "$@"
