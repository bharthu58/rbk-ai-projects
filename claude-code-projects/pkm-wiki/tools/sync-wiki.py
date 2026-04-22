#!/usr/bin/env python3
"""
sync-wiki.py
Copies rbk-pkm-wiki pages into Jekyll _wiki/ collection.
Converts [[wikilinks]] to standard markdown links.

Usage:
    python3 tools/sync-wiki.py
"""

import re
import sys
from pathlib import Path

SOURCE = Path("/mnt/g/My Drive/RBK-OBSIDIAN-NOTES/rbk-obsidian-vault/Agent Access/rbk-pkm-wiki")
DEST   = Path("/home/bharthu/repos/github/bharthu58.github.io/_wiki")
SKIP   = {"index.md", "log.md"}


def slugify(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 3:].lstrip("\n")
    fm: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            val = v.strip().strip('"').strip("'")
            fm[k.strip()] = val
    return fm, body


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf"}


def build_slug_map(source: Path) -> dict[str, str]:
    slug_map: dict[str, str] = {}
    for md in source.rglob("*.md"):
        if md.name in SKIP:
            continue
        slug_map[md.stem] = slugify(md.stem)
    return slug_map


def convert_wikilinks(text: str, slug_map: dict[str, str]) -> str:
    def replace(m: re.Match) -> str:
        # skip image embeds: ![[file.jpg]]
        if m.group(0).startswith("!"):
            return ""
        inner = m.group(1)
        if "|" in inner:
            page, alias = inner.split("|", 1)
        else:
            page = alias = inner
        page  = page.strip()
        alias = alias.strip()
        # skip bare image file links
        if any(page.lower().endswith(ext) for ext in IMAGE_EXTS):
            return ""
        slug = slug_map.get(page)
        if slug is None:
            return alias  # unresolved wikilink → plain text
        return f"[{alias}](/wiki/{slug}/)"

    return re.sub(r"!?\[\[([^\]]+)\]\]", replace, text)


def sync() -> None:
    if not SOURCE.exists():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    DEST.mkdir(exist_ok=True)
    for old in DEST.glob("*.md"):
        old.unlink()

    slug_map = build_slug_map(SOURCE)
    count = 0

    for md in sorted(SOURCE.rglob("*.md")):
        if md.name in SKIP:
            continue

        text       = md.read_text(encoding="utf-8")
        fm, body   = parse_frontmatter(text)
        title      = fm.get("title") or md.stem
        slug       = slugify(md.stem)

        body = convert_wikilinks(body, slug_map)

        out = (
            f"---\n"
            f"layout: page\n"
            f"title: \"{title}\"\n"
            f"---\n\n"
            f"{body}\n"
        )

        (DEST / f"{slug}.md").write_text(out, encoding="utf-8")
        print(f"  {md.relative_to(SOURCE)} → _wiki/{slug}.md")
        count += 1

    print(f"\n✓ {count} pages synced to _wiki/")
    print("Next: commit _wiki/ and push to trigger GitHub Actions deploy.")


if __name__ == "__main__":
    sync()
