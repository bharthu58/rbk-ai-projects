"""
spotify.py — Episode metadata extraction from Spotify.

Strategy (in order):
  1. oEmbed endpoint — no auth, returns title + provider info
  2. spotipy API     — full metadata (requires SPOTIFY_CLIENT_ID/SECRET)
  3. HTML page parse — fragile fallback, last resort
"""

import json
import logging
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EpisodeMetadata:
    title: str
    podcast: str
    description: str = ""
    episode_number: str | None = None
    guest: str | None = None
    duration_ms: int = 0
    episode_id: str | None = None
    spotify_url: str = ""
    release_date: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_episode_id(url: str) -> str | None:
    """Extract Spotify episode ID from any supported URL format."""
    # open.spotify.com/episode/ID or spotify:episode:ID
    m = re.search(r"episode[/:]([A-Za-z0-9]{15,})", url)
    if m:
        return m.group(1)
    # creators.spotify.com/pod/profile/{show}/episodes/{slug}
    m = re.search(r"/episodes/([^/?#]+)", url)
    if m:
        return None  # slug, not ID — handled by search fallback
    return None


def _parse_guest(title: str, description: str) -> str | None:
    """
    Heuristic guest extraction. Only matches explicit guest indicators
    to avoid false positives on question-style episode titles.
    """
    # Only match when there's an explicit guest indicator keyword
    patterns = [
        r"(?:with|ft\.?|feat\.?|featuring|guest[:\s]+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"\|\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*$",   # "Topic | Guest Name"
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}):\s+\w",      # "Guest Name: Topic..."
    ]
    for src in (title, description[:300]):
        for pat in patterns:
            m = re.search(pat, src)
            if m:
                candidate = m.group(1).strip()
                words = candidate.split()
                # Must be 2+ words, each capitalised — typical of a person's name
                if (
                    len(words) >= 2
                    and all(w[0].isupper() for w in words)
                    and not any(w.lower() in ("what", "how", "why", "when", "where", "who", "the", "are") for w in words)
                ):
                    return candidate
    return None


def _parse_episode_number(title: str) -> str | None:
    m = re.search(
        r"(?:^|[\s#|–—-])(?:ep(?:isode)?\.?\s*|#\s*)(\d+)\b",
        title,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Strategy 1: oEmbed (no auth)
# ---------------------------------------------------------------------------

def _fetch_oembed(url: str) -> dict | None:
    endpoint = f"https://open.spotify.com/oembed?url={urllib.parse.quote(url)}"
    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.debug("oEmbed failed: %s", e)
        return None


def _parse_oembed(data: dict, url: str) -> EpisodeMetadata | None:
    raw_title = data.get("title", "")
    if not raw_title:
        return None

    # Common formats: "Episode Title | Podcast Name" or "Episode Title — Podcast Name"
    for sep in (" | ", " — ", " - ", " – "):
        if sep in raw_title:
            parts = raw_title.split(sep, 1)
            title, podcast = parts[0].strip(), parts[1].strip()
            break
    else:
        title, podcast = raw_title, data.get("provider_name", "Unknown")

    episode_id = _extract_episode_id(url)
    return EpisodeMetadata(
        title=title,
        podcast=podcast,
        episode_number=_parse_episode_number(title),
        guest=_parse_guest(title, ""),
        episode_id=episode_id,
        spotify_url=url,
    )


# ---------------------------------------------------------------------------
# Strategy 2: spotipy API (full metadata)
# ---------------------------------------------------------------------------

def _fetch_spotipy(url: str) -> EpisodeMetadata | None:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        log.debug("No Spotify credentials — skipping API strategy.")
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        log.debug("spotipy not installed.")
        return None

    sp = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
    )

    episode_id = _extract_episode_id(url)

    if not episode_id:
        # creators.spotify.com URL — search by slug title
        m = re.search(r"/episodes/([^/?#]+)", url)
        if not m:
            return None
        raw_slug = m.group(1)
        title_slug = re.sub(r"-[a-z0-9]{6,8}$", "", raw_slug)
        query = title_slug.replace("-", " ")
        results = sp.search(q=query, type="episode", limit=3)
        items = results.get("episodes", {}).get("items", [])
        if not items:
            return None
        episode_id = items[0]["id"]

    try:
        ep = sp.episode(episode_id)
    except Exception as e:
        log.debug("spotipy episode fetch failed: %s", e)
        return None

    title = ep["name"]
    podcast = ep["show"]["name"]
    description = ep.get("description", "")

    return EpisodeMetadata(
        title=title,
        podcast=podcast,
        description=description,
        episode_number=_parse_episode_number(title),
        guest=_parse_guest(title, description),
        duration_ms=ep.get("duration_ms", 0),
        episode_id=episode_id,
        spotify_url=url,
        release_date=ep.get("release_date", ""),
    )


# ---------------------------------------------------------------------------
# Strategy 3: HTML page parse (last resort)
# ---------------------------------------------------------------------------

def _fetch_html_meta(url: str) -> EpisodeMetadata | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; podcast-resolver/1.0)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read(65536).decode("utf-8", errors="replace")
    except Exception as e:
        log.debug("HTML fetch failed: %s", e)
        return None

    def og(prop: str) -> str:
        m = re.search(rf'<meta[^>]+property="og:{prop}"[^>]+content="([^"]+)"', html)
        return m.group(1) if m else ""

    title = og("title") or ""
    description = og("description") or ""
    if not title:
        m = re.search(r"<title>([^<]+)</title>", html)
        title = m.group(1).strip() if m else ""

    # Strip " | Spotify" suffix
    title = re.sub(r"\s*\|\s*Spotify\s*$", "", title).strip()

    podcast = ""
    m = re.search(r'"show":\s*\{"name":\s*"([^"]+)"', html)
    if m:
        podcast = m.group(1)

    if not title:
        return None

    return EpisodeMetadata(
        title=title,
        podcast=podcast or "Unknown",
        description=description,
        episode_number=_parse_episode_number(title),
        guest=_parse_guest(title, description),
        spotify_url=url,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_metadata(url: str) -> EpisodeMetadata:
    """
    Fetch episode metadata from Spotify using best available strategy.
    Raises ValueError if all strategies fail.
    """
    log.info("Fetching metadata: %s", url)

    # Strategy 2 first if credentials available (richest data)
    if os.environ.get("SPOTIFY_CLIENT_ID"):
        log.info("  Trying spotipy API...")
        meta = _fetch_spotipy(url)
        if meta:
            log.info("  Metadata via spotipy: %r / %r", meta.podcast, meta.title)
            return meta

    # Strategy 1: oEmbed (no auth)
    log.info("  Trying oEmbed...")
    data = _fetch_oembed(url)
    if data:
        meta = _parse_oembed(data, url)
        if meta:
            log.info("  Metadata via oEmbed: %r / %r", meta.podcast, meta.title)
            return meta

    # Strategy 3: HTML
    log.info("  Trying HTML page parse...")
    meta = _fetch_html_meta(url)
    if meta:
        log.info("  Metadata via HTML: %r / %r", meta.podcast, meta.title)
        return meta

    raise ValueError(f"Could not extract metadata from: {url}")
