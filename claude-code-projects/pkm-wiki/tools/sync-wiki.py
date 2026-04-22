#!/usr/bin/env python3
"""
sync-wiki.py
Copies rbk-pkm-wiki pages into Jekyll _wiki/ collection.
Converts [[wikilinks]] to standard markdown links.
Also writes _data/wiki_graph.json for the interactive graph page.

Usage:
    python3 tools/sync-wiki.py
"""

import json
import re
import sys
from pathlib import Path

SOURCE   = Path("/mnt/g/My Drive/RBK-OBSIDIAN-NOTES/rbk-obsidian-vault/Agent Access/rbk-pkm-wiki")
DEST     = Path("/home/bharthu/repos/github/bharthu58.github.io/_wiki")
DATA_DIR = Path("/home/bharthu/repos/github/bharthu58.github.io/_data")
SKIP     = {"index.md", "log.md"}

# Order matters: longer prefixes first to avoid "c-" matching "cpp-" etc.
DOMAIN_PREFIXES = [
    ("architecture-", "Architecture"),
    ("ai-",           "AI / LLM"),
    ("c-",            "C++ / Systems"),
    ("devops-",       "DevOps"),
    ("linux-",        "Linux"),
    ("obsidian-",     "Obsidian"),
    ("pkm-",          "PKM"),
    ("python-",       "Python"),
    ("llm-",          "Meta"),
    ("web-",          "Web"),
]


def infer_domain(slug: str) -> str:
    for prefix, domain in DOMAIN_PREFIXES:
        if slug.startswith(prefix):
            return domain
    return "Meta"


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
    """Returns {page_stem: slug}"""
    slug_map: dict[str, str] = {}
    for md in source.rglob("*.md"):
        if md.name in SKIP:
            continue
        slug_map[md.stem] = slugify(md.stem)
    return slug_map


def convert_wikilinks(text: str, slug_map: dict[str, str]) -> tuple[str, list[str]]:
    """Returns (converted_text, list_of_resolved_target_slugs)."""
    resolved: list[str] = []

    def replace(m: re.Match) -> str:
        if m.group(0).startswith("!"):
            return ""
        inner = m.group(1)
        if "|" in inner:
            page, alias = inner.split("|", 1)
        else:
            page = alias = inner
        page  = page.strip()
        alias = alias.strip()
        if any(page.lower().endswith(ext) for ext in IMAGE_EXTS):
            return ""
        slug = slug_map.get(page)
        if slug is None:
            return alias
        resolved.append(slug)
        return f"[{alias}](/wiki/{slug}/)"

    converted = re.sub(r"!?\[\[([^\]]+)\]\]", replace, text)
    return converted, resolved


def strip_leading_h1(body: str, title: str) -> str:
    """Remove the first h1 if it duplicates the frontmatter title (Chirpy renders title already)."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            h1_text = stripped[2:].strip()
            # strip markdown emphasis chars for loose comparison
            h1_clean = re.sub(r"[*_`]", "", h1_text).strip()
            title_clean = re.sub(r"[*_`\"']", "", title).strip()
            if h1_clean == title_clean:
                remaining = "\n".join(lines[i + 1:]).lstrip("\n")
                return remaining
            break  # only check the first h1
    return body


def sync() -> None:
    if not SOURCE.exists():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    DEST.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    for old in DEST.glob("*.md"):
        old.unlink()

    slug_map = build_slug_map(SOURCE)

    graph_nodes: list[dict] = []
    graph_links: list[dict] = []
    count = 0

    for md in sorted(SOURCE.rglob("*.md")):
        if md.name in SKIP:
            continue

        text     = md.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        title    = fm.get("title") or md.stem
        slug     = slugify(md.stem)
        domain   = infer_domain(slug)

        body, resolved_targets = convert_wikilinks(body, slug_map)
        body = strip_leading_h1(body, title)

        out = (
            f"---\n"
            f"layout: page\n"
            f"title: \"{title}\"\n"
            f"domain: \"{domain}\"\n"
            f"---\n\n"
            f"{body}\n"
        )

        (DEST / f"{slug}.md").write_text(out, encoding="utf-8")
        print(f"  {md.relative_to(SOURCE)} → _wiki/{slug}.md")

        graph_nodes.append({
            "id":     slug,
            "title":  title,
            "domain": domain,
            "url":    f"/wiki/{slug}/",
        })
        for target in set(resolved_targets):
            if target != slug:
                graph_links.append({"source": slug, "target": target})

        count += 1

    # Deduplicate edges (same source+target pair)
    seen_edges: set[tuple] = set()
    unique_links = []
    for lnk in graph_links:
        key = (lnk["source"], lnk["target"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_links.append(lnk)

    graph_data = {"nodes": graph_nodes, "links": unique_links}
    graph_path = DATA_DIR / "wiki_graph.json"
    graph_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ {count} pages synced to _wiki/")
    print(f"✓ Graph data written to _data/wiki_graph.json ({len(graph_nodes)} nodes, {len(unique_links)} edges)")
    print("Next: commit _wiki/, _data/wiki_graph.json, and push to trigger GitHub Actions deploy.")


if __name__ == "__main__":
    sync()
