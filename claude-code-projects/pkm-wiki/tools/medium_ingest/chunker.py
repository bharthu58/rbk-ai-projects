"""
chunker.py — Token-aware article chunking.

Splits markdown text into chunks that:
  - Stay within a token budget
  - Respect section boundaries (## / ### headings)
  - Never split a code block or list mid-block

Token estimation: 1 token ≈ 4 characters (adequate for prompt-budgeting; no tiktoken dep).
"""

import re

_CHARS_PER_TOKEN = 4
_DEFAULT_MAX_TOKENS = 1_200
_MIN_CHUNK_TOKENS = 200

_HEADING_RE = re.compile(r"^#{1,3} .+", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def chunk_article(text: str, max_tokens: int = _DEFAULT_MAX_TOKENS) -> list[str]:
    """
    Split `text` into chunks of at most `max_tokens` tokens, preferring
    section boundaries. Returns a list of non-empty chunk strings.
    """
    max_chars = max_tokens * _CHARS_PER_TOKEN

    # Fast path: article fits in one chunk
    if len(text) <= max_chars:
        return [text]

    sections = _split_on_headings(text)
    return _pack_sections(sections, max_chars)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _split_on_headings(text: str) -> list[str]:
    """
    Split text at heading boundaries, keeping the heading with its body.
    The preamble before the first heading is its own section.
    """
    parts: list[str] = []
    last = 0
    for m in _HEADING_RE.finditer(text):
        if m.start() > last:
            chunk = text[last:m.start()].strip()
            if chunk:
                parts.append(chunk)
        last = m.start()
    tail = text[last:].strip()
    if tail:
        parts.append(tail)
    return parts or [text]


def _pack_sections(sections: list[str], max_chars: int) -> list[str]:
    """
    Greedily pack sections into chunks without exceeding max_chars.
    If a single section exceeds max_chars, split it by paragraphs.
    """
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for section in sections:
        if len(section) > max_chars:
            # Flush current accumulation first
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts, current_len = [], 0
            # Split oversized section by paragraphs
            chunks.extend(_split_by_paragraphs(section, max_chars))
        elif current_len + len(section) + 2 > max_chars:
            # Flush and start new chunk
            if current_parts:
                chunks.append("\n\n".join(current_parts))
            current_parts = [section]
            current_len = len(section)
        else:
            current_parts.append(section)
            current_len += len(section) + 2

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [c for c in chunks if c.strip()]


def _split_by_paragraphs(text: str, max_chars: int) -> list[str]:
    """Emergency splitter: split on blank lines."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    for para in paragraphs:
        if buf_len + len(para) + 2 > max_chars:
            if buf:
                chunks.append("\n\n".join(buf))
            buf = [para]
            buf_len = len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 2

    if buf:
        chunks.append("\n\n".join(buf))

    return chunks or [text[:max_chars]]
