"""
extractor.py — HTML → clean markdown extraction.

Strategy (in order, first success wins):
  1. trafilatura  — battle-tested boilerplate removal; outputs markdown natively
  2. BeautifulSoup + markdownify — direct parse of <article> tag
  3. Full-body markdownify fallback — last resort

trafilatura handles Medium articles reliably because it targets the main content
block and discards headers, footers, navigation, and recommendations.
"""

import logging
import re

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Elements to strip before fallback extraction (UI noise)
_STRIP_TAGS = [
    "header", "footer", "nav", "aside",
    "script", "style", "noscript",
    "[role='navigation']", "[role='banner']", "[role='complementary']",
    "[data-testid='post-sidebar']",
    "[data-testid='headerSocialRow']",
    "[data-testid='recommendedPosts']",
    "[data-testid='audio-player']",
]


def extract_content(html: str, url: str = "") -> str:
    """
    Return clean markdown text from a Medium article HTML string.
    Raises ValueError if no content could be extracted.
    """
    text = _try_trafilatura(html, url)
    if text and len(text) > 200:
        log.debug("  Extractor: trafilatura success (%d chars)", len(text))
        return _post_clean(text)

    text = _try_beautifulsoup(html)
    if text and len(text) > 200:
        log.debug("  Extractor: BeautifulSoup success (%d chars)", len(text))
        return _post_clean(text)

    raise ValueError("Could not extract article content — page may be paywalled or JS-gated")


# ---------------------------------------------------------------------------
# Strategy 1 — trafilatura
# ---------------------------------------------------------------------------

def _try_trafilatura(html: str, url: str) -> str | None:
    try:
        import trafilatura
    except ImportError:
        log.warning("trafilatura not installed; skipping. Run: pip install trafilatura")
        return None

    text = trafilatura.extract(
        html,
        url=url or None,
        output_format="markdown",
        include_formatting=True,
        include_links=False,
        include_images=False,
        include_tables=True,
        no_fallback=False,
        favor_recall=True,       # prefer more content over precision
    )
    return text


# ---------------------------------------------------------------------------
# Strategy 2 — BeautifulSoup + markdownify
# ---------------------------------------------------------------------------

def _try_beautifulsoup(html: str) -> str | None:
    try:
        from markdownify import markdownify as md
    except ImportError:
        log.warning("markdownify not installed; skipping. Run: pip install markdownify")
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Strip noise
    for tag in soup.select(", ".join(_STRIP_TAGS)):
        tag.decompose()

    # Try article tag first, then body
    article = soup.find("article") or soup.find("main") or soup.body
    if article is None:
        return None

    # Remove inline clutter
    for tag in article.find_all(["button", "svg", "figure > figcaption"]):
        if tag.name == "figcaption":
            continue  # keep captions
        tag.decompose()

    text = md(
        str(article),
        heading_style="ATX",
        bullets="-",
        code_language="",
        strip=["img", "button", "svg", "input"],
    )
    return text


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def _post_clean(text: str) -> str:
    """Remove artefacts common in Medium extractions."""
    lines = []
    prev_blank = False
    for line in text.splitlines():
        stripped = line.rstrip()

        # Drop lines that are pure noise
        if _is_noise_line(stripped):
            continue

        # Collapse multiple blank lines into one
        if stripped == "":
            if not prev_blank:
                lines.append("")
            prev_blank = True
        else:
            lines.append(stripped)
            prev_blank = False

    return "\n".join(lines).strip()


_NOISE_PATTERNS = [
    re.compile(r"^\s*(Follow|Sign in|Subscribe|Sign up|Members only|Open in app)\s*$", re.I),
    re.compile(r"^\s*\d+\s*(min read|minute read)\s*$", re.I),
    re.compile(r"^\s*[-–—]{3,}\s*$"),  # horizontal rules from nav
    re.compile(r"^\s*\*{3,}\s*$"),
    re.compile(r"^\s*Listen\s*$", re.I),
    re.compile(r"^!\[.*?\]\(.*?\)$"),   # bare images with no context
]


def _is_noise_line(line: str) -> bool:
    if not line.strip():
        return False  # blanks handled separately
    return any(p.match(line) for p in _NOISE_PATTERNS)
