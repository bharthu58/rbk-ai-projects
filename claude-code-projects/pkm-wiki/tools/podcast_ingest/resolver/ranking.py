"""
ranking.py — Fuzzy matching and candidate scoring.

Scores candidate URLs/results against episode metadata using:
  - Token overlap (Jaccard) between title strings
  - Podcast name match bonus
  - Platform preference bonus (known podcast hosts)
  - Direct audio file bonus
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .spotify import EpisodeMetadata


# Podcast hosting platforms in rough preference order (more reliable = higher bonus)
_PLATFORM_SCORES: dict[str, float] = {
    "buzzsprout.com": 0.20,
    "libsyn.com": 0.20,
    "simplecast.com": 0.20,
    "podbean.com": 0.18,
    "transistor.fm": 0.18,
    "captivate.fm": 0.18,
    "spreaker.com": 0.15,
    "soundcloud.com": 0.12,
    "anchor.fm": 0.12,
    "creators.spotify.com": 0.10,
    "megaphone.fm": 0.18,
    "acast.com": 0.15,
    "podcastics.com": 0.10,
    "podomatic.com": 0.10,
}

_AUDIO_EXTENSIONS = re.compile(r"\.(mp3|m4a|ogg|wav|aac|opus|flac)(\?|$)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# String normalisation
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_set(text: str) -> set[str]:
    return set(normalize(text).split())


def jaccard(a: str, b: str) -> float:
    """Jaccard similarity on word tokens."""
    sa, sb = token_set(a), token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def token_overlap(a: str, b: str) -> float:
    """What fraction of a's tokens appear in b (recall-oriented)."""
    sa, sb = token_set(a), token_set(b)
    if not sa:
        return 0.0
    return len(sa & sb) / len(sa)


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    url: str
    title: str = ""        # page/result title
    snippet: str = ""      # search snippet
    raw_score: float = 0.0
    source_hint: str = ""  # "web" | "youtube" | "rss"


def score_candidate(c: Candidate, meta: "EpisodeMetadata") -> float:
    """
    Return a [0, 1] score for how likely this candidate is the target episode.
    Scores are additive, then clamped to [0, 1].
    """
    score = 0.0

    # Title similarity (most important signal)
    title_sim = max(
        jaccard(meta.title, c.title),
        token_overlap(meta.title, c.title),
        token_overlap(meta.title, c.snippet),
        jaccard(meta.title, c.snippet),
    )
    score += title_sim * 0.55

    # Podcast name match
    podcast_sim = max(
        jaccard(meta.podcast, c.title),
        jaccard(meta.podcast, c.snippet),
        token_overlap(meta.podcast, c.url),
    )
    score += podcast_sim * 0.20

    # Episode number match (strong signal when present)
    if meta.episode_number:
        ep_pattern = re.compile(
            rf"\b{re.escape(meta.episode_number)}\b", re.IGNORECASE
        )
        if ep_pattern.search(c.title) or ep_pattern.search(c.url):
            score += 0.15

    # Guest name match
    if meta.guest:
        guest_sim = max(
            token_overlap(meta.guest, c.title),
            token_overlap(meta.guest, c.snippet),
        )
        score += guest_sim * 0.10

    # Platform bonus
    for host, bonus in _PLATFORM_SCORES.items():
        if host in c.url:
            score += bonus
            break

    # Direct audio file bonus
    if _AUDIO_EXTENSIONS.search(c.url):
        score += 0.15

    return min(score, 1.0)


def rank_candidates(candidates: list[Candidate], meta: "EpisodeMetadata") -> list[Candidate]:
    """Return candidates sorted by score (descending), with score attached."""
    for c in candidates:
        c.raw_score = score_candidate(c, meta)
    return sorted(candidates, key=lambda c: c.raw_score, reverse=True)
