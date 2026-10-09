"""
writer.py — Render and write the final markdown note.

Output goes to <wiki_root>/raw/ with filename:
  medium--{slugified-title}--{YYYY-MM-DD}.md

The file has full wiki frontmatter so /wiki-ingest can process it immediately:
create the wiki page, add backlinks, move to ingested/articles/, update index.md.

Raw mode (--raw): write clean extracted text without LLM structuring.
"""

import logging
import re
from datetime import date
from pathlib import Path

from .fetcher import ArticleMetadata
from .llm import StructuredNote

log = logging.getLogger(__name__)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:72]


def render_note(note: StructuredNote, meta: ArticleMetadata) -> str:
    today = date.today().isoformat()
    tags_yaml = ", ".join(f'"{t}"' for t in (note.tags or ["medium", "article"]))
    pub_line = f'source_publication: "{meta.publication}"\n' if meta.publication else ""
    yt_date = meta.published_date[:10] if meta.published_date else today

    frontmatter = (
        f"---\n"
        f'title: "{meta.title}"\n'
        f"source_type: article\n"
        f'source_author: "{meta.author}"\n'
        f"{pub_line}"
        f'source_url: "{meta.url}"\n'
        f"date: {today}\n"
        f"published: {yt_date}\n"
        f"tags: [{tags_yaml}]\n"
        f"---"
    )

    sections: list[str] = [frontmatter, f"# {meta.title}"]

    # TL;DR
    if note.tl_dr:
        sections.append(f"## TL;DR\n\n{note.tl_dr}")

    # Key Ideas
    if note.key_ideas:
        body = "\n".join(f"- {item}" for item in note.key_ideas)
        sections.append(f"## Key Ideas\n\n{body}")

    # Deep Insights
    if note.deep_insights:
        body = "\n".join(f"- {item}" for item in note.deep_insights)
        sections.append(f"## Deep Insights\n\n{body}")

    # Mental Models
    if note.mental_models:
        body = "\n".join(f"- {item}" for item in note.mental_models)
        sections.append(f"## Mental Models\n\n{body}")

    # Actionable Takeaways
    if note.actionable_takeaways:
        body = "\n".join(f"- {item}" for item in note.actionable_takeaways)
        sections.append(f"## Actionable Takeaways\n\n{body}")

    # Notable Quotes
    if note.notable_quotes:
        body = "\n\n".join(f"> {q}" for q in note.notable_quotes)
        sections.append(f"## Notable Quotes\n\n{body}")

    # Technical Concepts
    if note.technical_concepts:
        rows = "\n".join(
            f"| {c['term']} | {c['definition']} |"
            for c in note.technical_concepts
        )
        table = f"| Concept | Definition |\n|---|---|\n{rows}"
        sections.append(f"## Concepts & References\n\n{table}")

    # Source
    author_str = f" by {meta.author}" if meta.author else ""
    pub_str = f" ({meta.publication})" if meta.publication else ""
    sections.append(
        f"## Source\n\n"
        f"[{meta.title}{author_str}{pub_str}]({meta.url})"
    )

    return "\n\n".join(sections) + "\n"


def render_raw_note(content: str, meta: ArticleMetadata) -> str:
    """Raw mode: no LLM structuring — write extracted markdown to raw/ for wiki-ingest."""
    today = date.today().isoformat()
    pub_line = f'source_publication: "{meta.publication}"\n' if meta.publication else ""

    frontmatter = (
        f"---\n"
        f'title: "{meta.title}"\n'
        f"source_type: article\n"
        f'source_author: "{meta.author}"\n'
        f"{pub_line}"
        f'source_url: "{meta.url}"\n'
        f"date: {today}\n"
        f"tags: [medium, article]\n"
        f"---"
    )

    header = (
        f"# {meta.title}\n\n"
        f"> **Author:** {meta.author or 'Unknown'}\n"
        f"> **Source:** [{meta.url}]({meta.url})\n"
        f"> **Date:** {today}\n"
    )

    return f"{frontmatter}\n\n{header}\n## Content\n\n{content}\n"


def write_note(
    content_or_note: "str | StructuredNote",
    meta: ArticleMetadata,
    wiki_root: Path,
    raw_mode: bool = False,
) -> Path:
    """
    Render and write a note to <wiki_root>/raw/.
    Returns the path of the written file.
    """
    today = date.today().isoformat()
    slug = slugify(meta.title or "untitled")
    filename = f"medium--{slug}--{today}.md"

    raw_dir = wiki_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / filename

    if raw_mode or isinstance(content_or_note, str):
        text = render_raw_note(
            content_or_note if isinstance(content_or_note, str) else "",
            meta,
        )
    else:
        text = render_note(content_or_note, meta)

    out_path.write_text(text, encoding="utf-8")
    log.info("  Written: %s", out_path.name)
    return out_path
