"""
search.py — Web and YouTube search for podcast audio sources.

Web search: DuckDuckGo (no API key) via ddgs library.
YouTube:    yt-dlp search subprocess.

Both return lists of Candidate objects for ranking.py to score.
"""

import logging
import os
import re
import subprocess
from typing import TYPE_CHECKING

from .ranking import Candidate

if TYPE_CHECKING:
    from .spotify import EpisodeMetadata

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query generation
# ---------------------------------------------------------------------------

def build_queries(meta: "EpisodeMetadata") -> list[str]:
    title, podcast = meta.title, meta.podcast
    queries = [
        f'"{title}" {podcast} full episode',
        f'"{title}" podcast mp3',
        f"{podcast} {title} audio",
    ]
    if meta.episode_number:
        queries.append(f"{podcast} episode {meta.episode_number} mp3")
        queries.append(f"{podcast} #{meta.episode_number} full episode")
    if meta.guest:
        queries.append(f"{meta.guest} interview {podcast} podcast")
        queries.append(f"{meta.guest} {podcast} mp3")
    queries += [
        f'site:buzzsprout.com "{podcast}" "{title}"',
        f'site:simplecast.com "{podcast}" "{title}"',
        f'site:podbean.com "{podcast}" "{title}"',
    ]
    return queries


# ---------------------------------------------------------------------------
# DuckDuckGo web search
# ---------------------------------------------------------------------------

def _get_ddgs():
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        pass
    try:
        from duckduckgo_search import DDGS
        return DDGS
    except ImportError:
        return None


def search_web(
    queries: list[str],
    max_results_per_query: int = 5,
    target_candidates: int = 15,
) -> list[Candidate]:
    """
    Run queries sequentially — DDG rate-limits concurrent requests.
    Stops early once target_candidates unique results are collected.
    """
    DDGS = _get_ddgs()
    if DDGS is None:
        log.warning("ddgs not installed. Run: pip install ddgs")
        return []

    seen: set[str] = set()
    candidates: list[Candidate] = []

    for query in queries:
        if len(candidates) >= target_candidates:
            break
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results_per_query))
        except Exception as e:
            log.debug("DDG search failed for %r: %s", query, e)
            continue

        for r in results:
            url = r.get("href", "")
            if not url or "spotify.com" in url or url in seen:
                continue
            seen.add(url)
            candidates.append(Candidate(
                url=url,
                title=r.get("title", ""),
                snippet=r.get("body", ""),
                source_hint="web",
            ))

    log.info("  Web search: %d candidates from %d queries", len(candidates), len(queries))
    return candidates


# ---------------------------------------------------------------------------
# YouTube search via yt-dlp
# ---------------------------------------------------------------------------

def search_youtube(meta: "EpisodeMetadata") -> list[Candidate]:
    """Search YouTube for the episode; returns Candidates with YouTube URLs."""
    base_queries = [f"{meta.podcast} {meta.title}"]
    if meta.guest:
        base_queries.append(f"{meta.guest} interview {meta.podcast}")
    if meta.episode_number:
        base_queries.append(f"{meta.podcast} episode {meta.episode_number}")

    candidates: list[Candidate] = []
    seen: set[str] = set()

    for query in base_queries[:2]:
        cmd = [
            "yt-dlp", "--no-playlist",
            "--print", "%(webpage_url)s",
            "--print", "%(title)s",
            "--js-runtimes", "node",
            f"ytsearch3:{query}",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            log.debug("yt-dlp search failed: %s", e)
            continue

        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        for yt_url, yt_title in zip(lines[::2], lines[1::2]):
            if not yt_url or "youtube.com" not in yt_url or yt_url in seen:
                continue
            seen.add(yt_url)
            candidates.append(Candidate(
                url=yt_url,
                title=yt_title,
                snippet=query,
                source_hint="youtube",
            ))

    log.info("  YouTube search: %d candidates", len(candidates))
    return candidates


# ---------------------------------------------------------------------------
# RSS feed search
# ---------------------------------------------------------------------------

def search_rss(meta: "EpisodeMetadata") -> str | None:
    """Locate podcast RSS feed URL via Spotify API, podcastindex, or web search."""
    return (
        _rss_from_spotify(meta)
        or _rss_from_podcastindex(meta.podcast)
        or _rss_from_web_search(meta.podcast)
    )


def _rss_from_spotify(meta: "EpisodeMetadata") -> str | None:
    if not (os.environ.get("SPOTIFY_CLIENT_ID") and meta.episode_id):
        return None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=os.environ["SPOTIFY_CLIENT_ID"],
            client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        ))
        ep = sp.episode(meta.episode_id)
        show = sp.show(ep["show"]["id"])
        for val in show.get("external_urls", {}).values():
            if "feed" in val or "rss" in val:
                return val
    except Exception as e:
        log.debug("RSS from Spotify failed: %s", e)
    return None


def _rss_from_podcastindex(podcast_name: str) -> str | None:
    """Query podcastindex.org (requires PODCASTINDEX_API_KEY env var)."""
    import hashlib
    import json
    import time
    import urllib.parse
    import urllib.request

    pi_key = os.environ.get("PODCASTINDEX_API_KEY", "")
    pi_secret = os.environ.get("PODCASTINDEX_API_SECRET", "")
    if not pi_key:
        return None
    try:
        ts = str(int(time.time()))
        auth_hash = hashlib.sha1((pi_key + pi_secret + ts).encode()).hexdigest()
        url = f"https://api.podcastindex.org/api/1.0/search/byterm?q={urllib.parse.quote(podcast_name)}&max=1"
        req = urllib.request.Request(url, headers={
            "X-Auth-Key": pi_key, "X-Auth-Date": ts,
            "Authorization": auth_hash, "User-Agent": "podcast-resolver/1.0",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            feeds = json.loads(resp.read()).get("feeds", [])
        return feeds[0].get("url") if feeds else None
    except Exception as e:
        log.debug("podcastindex search failed: %s", e)
    return None


def _rss_from_web_search(podcast_name: str) -> str | None:
    """Last resort: DuckDuckGo search for RSS feed URL."""
    DDGS = _get_ddgs()
    if DDGS is None:
        return None
    query = f"{podcast_name} podcast RSS feed"
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                url = r.get("href", "")
                if re.search(r"/feed|/rss|\.xml|\.rss", url, re.IGNORECASE):
                    return url
    except Exception as e:
        log.debug("RSS web search failed: %s", e)
    return None
