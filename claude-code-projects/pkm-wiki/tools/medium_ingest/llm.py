"""
llm.py — Anthropic API-based article structuring.

Single-pass for articles ≤ ~80k chars; multi-pass map-reduce for longer articles.
Uses claude-haiku-4-5 for speed and cost-efficiency on daily ingestion runs.
Set MEDIUM_LLM_MODEL env var to override (e.g. claude-sonnet-4-6 for richer output).
"""

import json
import logging
import os
from dataclasses import dataclass, field

from .chunker import chunk_article, estimate_tokens
from .fetcher import ArticleMetadata

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_SINGLE_PASS_TOKENS = 20_000  # chars; articles beyond this get map-reduce
_MAX_CHUNK_TOKENS = 1_200

_SYSTEM_PROMPT = """\
You are a knowledge distillation engine. Your only job is to convert article text into \
a high-signal structured note optimised for future retrieval and deep understanding.

Rules:
- Extract insight, NOT summaries. A summary says what happened; an insight explains why it matters.
- Compress aggressively. Every sentence must earn its place.
- No filler phrases ("In this article...", "The author argues...", "Overall...").
- Prefer concrete over abstract. Trade "improved performance" for "3× throughput via batched writes".
- Mental models: only include if genuinely generalisable beyond this article.
- Quotes: only verbatim lines that would lose impact if paraphrased. Max 3.
- Technical concepts: only terms a reader would need to look up; one-line definitions.
- Tags: 3–6 lowercase tags, always start with the broadest domain.
"""

_USER_TEMPLATE = """\
Article: {title}
Author: {author}
URL: {url}

CONTENT:
{content}

Output JSON matching this schema exactly — no markdown fences, no commentary:
{{
  "tl_dr": "2–3 sentence compressed essence. What is the core insight and why does it matter?",
  "key_ideas": ["Compressed idea — not a sentence fragment, not a full paragraph. 1–2 sentences each.", "..."],
  "deep_insights": ["Non-obvious insight that took reasoning to extract — not visible from skimming.", "..."],
  "mental_models": ["Name: one-sentence explanation of the model and when to apply it.", "..."],
  "actionable_takeaways": ["Concrete thing a practitioner can do or apply. Start with a verb.", "..."],
  "notable_quotes": ["Verbatim quote worth preserving exactly as written.", "..."],
  "technical_concepts": [{{"term": "...", "definition": "one line"}}],
  "tags": ["tag1", "tag2", "tag3"]
}}

If a section has no high-signal content, return an empty array for it. Do not fabricate.
"""

_REDUCE_TEMPLATE = """\
Below are structured notes from {n} chunks of the same article: "{title}"

CHUNK NOTES:
{chunk_notes}

Merge them into a single unified note. Deduplicate aggressively. \
Preserve the highest-signal items only. Same JSON schema, same rules as before.
"""


@dataclass
class StructuredNote:
    tl_dr: str = ""
    key_ideas: list[str] = field(default_factory=list)
    deep_insights: list[str] = field(default_factory=list)
    mental_models: list[str] = field(default_factory=list)
    actionable_takeaways: list[str] = field(default_factory=list)
    notable_quotes: list[str] = field(default_factory=list)
    technical_concepts: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "StructuredNote":
        return cls(
            tl_dr=d.get("tl_dr", ""),
            key_ideas=_coerce_list(d.get("key_ideas")),
            deep_insights=_coerce_list(d.get("deep_insights")),
            mental_models=_coerce_list(d.get("mental_models")),
            actionable_takeaways=_coerce_list(d.get("actionable_takeaways")),
            notable_quotes=_coerce_list(d.get("notable_quotes")),
            technical_concepts=_coerce_concepts(d.get("technical_concepts")),
            tags=_coerce_list(d.get("tags")),
        )


async def structure_article(content: str, meta: ArticleMetadata) -> StructuredNote:
    """
    Call the Claude API to produce a StructuredNote for `content`.
    Raises ImportError if anthropic is not installed.
    Raises RuntimeError if ANTHROPIC_API_KEY is not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. "
            "Set it in run_medium.sh or use --raw to skip LLM structuring."
        )

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise ImportError("anthropic not installed. Run: pip install anthropic")

    client = AsyncAnthropic(api_key=api_key)
    model = os.environ.get("MEDIUM_LLM_MODEL", _DEFAULT_MODEL)

    total_tokens = estimate_tokens(content)
    log.info("  LLM: %d tokens, model=%s", total_tokens, model)

    if total_tokens <= _MAX_SINGLE_PASS_TOKENS:
        return await _single_pass(client, model, content, meta)
    else:
        return await _map_reduce(client, model, content, meta)


# ---------------------------------------------------------------------------
# Single-pass
# ---------------------------------------------------------------------------

async def _single_pass(client, model: str, content: str, meta: ArticleMetadata) -> StructuredNote:
    prompt = _USER_TEMPLATE.format(
        title=meta.title or "Untitled",
        author=meta.author or "Unknown",
        url=meta.url,
        content=content[:80_000],  # hard cap; haiku context is 200k
    )
    resp = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    return StructuredNote.from_dict(_parse_json(raw))


# ---------------------------------------------------------------------------
# Map-reduce for long articles
# ---------------------------------------------------------------------------

async def _map_reduce(client, model: str, content: str, meta: ArticleMetadata) -> StructuredNote:
    chunks = chunk_article(content, max_tokens=_MAX_CHUNK_TOKENS)
    log.info("  LLM: map-reduce over %d chunks", len(chunks))

    chunk_notes: list[str] = []
    for i, chunk in enumerate(chunks):
        log.info("  LLM: chunk %d/%d", i + 1, len(chunks))
        prompt = _USER_TEMPLATE.format(
            title=meta.title or "Untitled",
            author=meta.author or "Unknown",
            url=meta.url,
            content=chunk,
        )
        resp = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        chunk_notes.append(resp.content[0].text.strip())

    reduce_prompt = _REDUCE_TEMPLATE.format(
        n=len(chunks),
        title=meta.title or "Untitled",
        chunk_notes="\n\n---\n\n".join(chunk_notes),
    )
    resp = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": reduce_prompt}],
    )
    raw = resp.content[0].text.strip()
    return StructuredNote.from_dict(_parse_json(raw))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    # Strip ```json ... ``` wrapper if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.warning("JSON parse failed: %s — raw response: %.200s", e, text)
        return {}


def _coerce_list(val) -> list[str]:
    if isinstance(val, list):
        return [str(v) for v in val if v]
    if isinstance(val, str) and val:
        return [val]
    return []


def _coerce_concepts(val) -> list[dict]:
    if not isinstance(val, list):
        return []
    out = []
    for item in val:
        if isinstance(item, dict) and "term" in item:
            out.append({"term": str(item["term"]), "definition": str(item.get("definition", ""))})
        elif isinstance(item, str):
            out.append({"term": item, "definition": ""})
    return out
