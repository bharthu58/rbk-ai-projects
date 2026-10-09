"""
resolver.py — Orchestration: runs the 4-stage pipeline and returns ResolveResult.

Pipeline:
  Stage 1: Web search  → direct MP3 or podcast page → extract audio URL
  Stage 2: YouTube     → YouTube video URL (captions preferred downstream)
  Stage 3: RSS         → locate feed → match episode → extract audio URL
  Stage 4: Record      → null audio_url, caller must record manually

Confidence thresholds:
  >= 0.50 → accept result
  <  0.50 → try next stage (or return best available)
"""

import asyncio
import json
import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Literal

from .spotify import EpisodeMetadata, fetch_metadata
from .search import build_queries, search_web, search_youtube, search_rss
from .extractors import extract_audio_url, is_direct_audio
from .ranking import Candidate, rank_candidates, token_overlap, normalize

log = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.45  # minimum score to accept a web/YouTube result


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ResolveResult:
    audio_url: str | None
    source: Literal["direct", "web", "youtube", "rss", "record"]
    confidence: float
    metadata: EpisodeMetadata
    youtube_url: str | None = None   # set when source=="youtube"
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------

def _try_extract_audio(candidate: Candidate) -> str | None:
    """Try to get a direct audio URL from a candidate (direct link or page)."""
    if is_direct_audio(candidate.url):
        return candidate.url
    return extract_audio_url(candidate.url)


def _resolve_via_rss(feed_url: str, meta: EpisodeMetadata) -> str | None:
    """Parse RSS feed and find audio URL for the matching episode."""
    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; podcast-resolver/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            tree = ET.parse(resp)
    except Exception as e:
        log.debug("RSS fetch failed: %s", e)
        return None

    title_words = set(normalize(meta.title).split())
    best_url: str | None = None
    best_overlap = 0.0

    for item in tree.iter("item"):
        item_title = normalize(item.findtext("title") or "")
        item_words = set(item_title.split())
        overlap = len(title_words & item_words) / len(title_words) if title_words else 0.0
        if overlap > best_overlap:
            enc = item.find("enclosure")
            if enc is not None and enc.get("url"):
                best_overlap = overlap
                best_url = enc.get("url")

    if best_url and best_overlap >= 0.4:
        log.info("  RSS match (overlap=%.2f): %s", best_overlap, best_url)
        return best_url
    return None


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve(spotify_url: str) -> ResolveResult:
    """
    Resolve a Spotify episode URL to an audio source.

    Returns ResolveResult with:
      audio_url  — direct audio URL, or YouTube URL (source="youtube"), or None (source="record")
      source     — which stage succeeded
      confidence — match confidence [0, 1]
      metadata   — episode metadata
    """
    log.info("=" * 60)
    log.info("Resolving: %s", spotify_url)

    # ── Stage 0: Metadata ──────────────────────────────────────────────────
    log.info("[0] Fetching Spotify metadata...")
    meta = fetch_metadata(spotify_url)
    log.info("    Show:    %s", meta.podcast)
    log.info("    Title:   %s", meta.title)
    log.info("    Episode: %s", meta.episode_number or "—")
    log.info("    Guest:   %s", meta.guest or "—")

    notes: list[str] = []

    # ── Stage 1: Web search → direct audio ────────────────────────────────
    log.info("[1] Web search (primary)...")
    queries = build_queries(meta)
    log.info("    Queries: %d", len(queries))

    web_candidates = search_web(queries)
    ranked_web = rank_candidates(web_candidates, meta)

    for c in ranked_web[:8]:   # try top 8
        log.info("    Candidate (score=%.2f): %s", c.raw_score, c.url[:80])
        if c.raw_score < CONFIDENCE_THRESHOLD:
            break
        audio_url = _try_extract_audio(c)
        if audio_url:
            source = "direct" if is_direct_audio(audio_url) else "web"
            log.info("    ✓ Audio found via %s: %s", source, audio_url[:80])
            return ResolveResult(
                audio_url=audio_url,
                source=source,
                confidence=c.raw_score,
                metadata=meta,
                notes=notes,
            )
        else:
            log.debug("    No audio extracted from: %s", c.url[:80])

    notes.append("Stage 1 (web search): no direct audio found above threshold.")
    log.info("    Stage 1: no result.")

    # ── Stage 2: YouTube ──────────────────────────────────────────────────
    log.info("[2] YouTube search...")
    yt_candidates = search_youtube(meta)
    ranked_yt = rank_candidates(yt_candidates, meta)

    if ranked_yt:
        best_yt = ranked_yt[0]
        log.info("    Best YouTube (score=%.2f): %s", best_yt.raw_score, best_yt.url)
        # Accept even lower confidence for YouTube — it's a reliable fallback
        if best_yt.raw_score >= 0.25 or len(ranked_yt) > 0:
            log.info("    ✓ YouTube result accepted.")
            return ResolveResult(
                audio_url=best_yt.url,   # YouTube URL — downstream handles captions
                source="youtube",
                confidence=best_yt.raw_score,
                metadata=meta,
                youtube_url=best_yt.url,
                notes=notes,
            )

    notes.append("Stage 2 (YouTube): no match found.")
    log.info("    Stage 2: no result.")

    # ── Stage 3: RSS ──────────────────────────────────────────────────────
    log.info("[3] RSS feed search...")
    feed_url = search_rss(meta)
    if feed_url:
        log.info("    Feed: %s", feed_url)
        audio_url = _resolve_via_rss(feed_url, meta)
        if audio_url:
            log.info("    ✓ RSS audio: %s", audio_url[:80])
            return ResolveResult(
                audio_url=audio_url,
                source="rss",
                confidence=0.85,  # RSS match is highly reliable if found
                metadata=meta,
                notes=notes,
            )
    else:
        log.info("    No RSS feed located.")

    notes.append("Stage 3 (RSS): no audio found.")
    log.info("    Stage 3: no result.")

    # ── Stage 4: Record fallback ───────────────────────────────────────────
    log.info("[4] Fallback: manual recording required.")
    log.info("    Fallback to recording required (FFmpeg needed).")
    notes.append("All automated stages failed. Manual recording required.")

    return ResolveResult(
        audio_url=None,
        source="record",
        confidence=1.0,
        metadata=meta,
        notes=notes,
    )
