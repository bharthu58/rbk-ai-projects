"""
extractors.py — Extract direct audio URLs from web pages.

Given a page URL, attempts to find a playable audio file via:
  1. URL is already a direct audio link
  2. Known podcast platform patterns (regex on URL)
  3. HTML parsing for <audio> tags and JSON-LD structured data
  4. Common embedded player iframe src patterns
"""

import logging
import re
import urllib.request
import urllib.parse

log = logging.getLogger(__name__)

_AUDIO_EXTENSIONS = re.compile(r"\.(mp3|m4a|ogg|wav|aac|opus)(\?[^\"'\s]*)?$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Known platform URL patterns → direct audio
# ---------------------------------------------------------------------------

_PLATFORM_PATTERNS: list[tuple[str, str]] = [
    # Buzzsprout — audio URL is in embed iframe src
    (r"buzzsprout\.com/\d+/episodes/(\d+)", "buzzsprout"),
    # Libsyn — direct MP3 in various URL shapes
    (r"\.libsyn\.com/.+\.mp3", "libsyn_direct"),
    # Simplecast — CDN audio URL
    (r"cdn\.simplecast\.com/audio/", "simplecast"),
    # Podbean
    (r"\.podbean\.com/mf/", "podbean"),
    # Transistor
    (r"media\.transistor\.fm/", "transistor"),
    # Megaphone
    (r"traffic\.megaphone\.fm/", "megaphone"),
    # Acast
    (r"feeds\.acast\.com/.+\.mp3", "acast"),
    # Soundcloud
    (r"soundcloud\.com/", "soundcloud"),
    # Generic MP3 on a CDN
    (r"https?://[^\s\"']+\.mp3(\?[^\s\"']*)?", "generic_mp3"),
]


def is_direct_audio(url: str) -> bool:
    return bool(_AUDIO_EXTENSIONS.search(url.split("?")[0]))


def _fetch_page(url: str, max_bytes: int = 131072) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; podcast-resolver/1.0)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read(max_bytes).decode("utf-8", errors="replace")
    except Exception as e:
        log.debug("Page fetch failed for %s: %s", url, e)
        return None


def _extract_audio_from_html(html: str, base_url: str) -> str | None:
    """Try various HTML patterns to find an audio source."""

    # 1. <audio src="..."> or <audio><source src="...">
    for pat in [
        r'<audio[^>]+src=["\']([^"\']+)["\']',
        r'<source[^>]+src=["\']([^"\']+\.(?:mp3|m4a|ogg|aac)(?:\?[^"\']*)?)["\']',
    ]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return urllib.parse.urljoin(base_url, m.group(1))

    # 2. JSON-LD contentUrl
    m = re.search(r'"contentUrl"\s*:\s*"([^"]+\.(?:mp3|m4a|ogg|aac)[^"]*)"', html)
    if m:
        return m.group(1)

    # 3. Common player data attributes / JS variables
    for pat in [
        r'(?:audioUrl|audio_url|file|mp3|stream_url)["\']?\s*:\s*["\']([^"\']+\.mp3[^"\']*)["\']',
        r'data-audio-url=["\']([^"\']+)["\']',
        r'data-mp3=["\']([^"\']+)["\']',
    ]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            url_candidate = m.group(1)
            if url_candidate.startswith("http"):
                return url_candidate

    # 4. Buzzsprout embed — audio URL is in the page script
    m = re.search(r'https://www\.buzzsprout\.com/\d+/\d+\.mp3[^"\']*', html)
    if m:
        return m.group(0)

    # 5. Simplecast player
    m = re.search(r'https://cdn\.simplecast\.com/audio/[^"\'&\s]+', html)
    if m:
        return m.group(0)

    # 6. Megaphone
    m = re.search(r'https://traffic\.megaphone\.fm/[^"\'&\s]+\.mp3[^"\'&\s]*', html)
    if m:
        return m.group(0)

    # 7. Generic: any .mp3 link in the page
    m = re.search(r'https?://[^\s"\'<>]+\.mp3(?:\?[^\s"\'<>]*)?', html)
    if m:
        return m.group(0)

    return None


# ---------------------------------------------------------------------------
# Buzzsprout — special handling (audio requires episode page)
# ---------------------------------------------------------------------------

def _resolve_buzzsprout(url: str) -> str | None:
    html = _fetch_page(url)
    if not html:
        return None
    m = re.search(r'https://www\.buzzsprout\.com/\d+/\d+\.mp3[^"\']*', html)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_audio_url(page_url: str) -> str | None:
    """
    Given any URL, attempt to return a direct audio file URL.
    Returns None if no audio source found.
    """
    # Already a direct audio link
    if is_direct_audio(page_url):
        log.debug("Direct audio URL: %s", page_url)
        return page_url

    # Known platform shortcut
    if "buzzsprout.com" in page_url:
        result = _resolve_buzzsprout(page_url)
        if result:
            log.debug("Buzzsprout audio: %s", result)
            return result

    # Generic: fetch page and parse
    log.debug("Fetching page for audio extraction: %s", page_url)
    html = _fetch_page(page_url)
    if not html:
        return None

    result = _extract_audio_from_html(html, page_url)
    if result:
        log.debug("Extracted audio from page: %s", result)
    return result
