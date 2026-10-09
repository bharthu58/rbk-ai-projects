"""
medium_ingest — Medium article → wiki note pipeline

Usage (via run_medium.sh):
    bash tools/run_medium.sh --bookmarks --limit 5
    bash tools/run_medium.sh --topic "system design" --limit 10
    bash tools/run_medium.sh --list-url "https://medium.com/me/list/..." --limit 10

Options:
    --bookmarks             Fetch from authenticated bookmark list
    --topic TOPIC           Fetch from a Medium tag page (e.g. "system design")
    --list-url URL          Fetch from a specific Medium reading list URL
    --limit N               Max articles to process (default: 100). Also bounds discovery
                            scroll depth for --list-url/--topic/--bookmarks — set explicitly
                            low (e.g. --limit 5) for a small, deliberate run.
    --login                 Open browser to log in; session saved for future runs
    --raw                   Skip LLM structuring; write extracted text for /wiki-ingest
    --dry-run               Print extraction preview without writing files
    --no-cache              Ignore cache; reprocess already-seen articles
    --clear-cache           Clear the URL cache and exit
    --resolve-only          Print discovered article URLs and exit
    --check-auth            Check Medium auth status and exit

Pipeline:
    1. Fetcher   → persistent Chrome session → article HTML
    2. Extractor → trafilatura / BeautifulSoup → clean markdown
    3. LLM       → Anthropic API → structured note  (skipped with --raw)
    4. Writer    → frontmatter + sections → raw/{filename}.md
    5. Cache     → mark URL as processed
    → Then run /wiki-ingest in Claude Code to integrate into the wiki
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))

from medium_ingest.cache import Cache
from medium_ingest.extractor import extract_content
from medium_ingest.fetcher import MediumFetcher
from medium_ingest.llm import structure_article
from medium_ingest.writer import write_note

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wiki root discovery
# ---------------------------------------------------------------------------

def find_wiki_root() -> Path:
    env = os.environ.get("WIKI_ROOT")
    if env:
        return Path(env)
    for root in [Path.cwd(), _HERE.parent.parent, Path.home()]:
        for cfg in root.rglob("wiki-config.md"):
            return cfg.parent
    raise FileNotFoundError(
        "Could not locate wiki-config.md. Set WIKI_ROOT env var or run from inside the wiki."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    wiki_root = find_wiki_root()
    log.info("Wiki root: %s", wiki_root)

    cache_path = wiki_root / "raw" / ".medium_cache.json"
    cache = Cache(cache_path)

    if args.clear_cache:
        cache.clear()
        return

    async with MediumFetcher() as fetcher:

        # ── Login: explicit auth setup — navigate to bookmarks, prompt if needed ──
        if args.login:
            page = await fetcher._ctx.new_page()
            try:
                logged_in = await fetcher.is_logged_in(page)
                if logged_in:
                    print("Already logged in. Session is valid.")
                else:
                    print("\nBrowser opened. Log in to Medium, complete any verification.")
                    input("Press ENTER after completing login...\n")
                    logged_in = await fetcher.is_logged_in(page)
                    if logged_in:
                        print("Session saved. Run --check-auth to verify.")
                    else:
                        print("WARNING: Still not authenticated. Try running --login again.")
            finally:
                await page.close()
            return

        # ── Auth check ───────────────────────────────────────────────────
        if args.check_auth:
            info = await fetcher.check_auth()
            print(f"URL   : {info['url']}")
            print(f"Title : {info['title']}")
            print(f"Auth  : {'YES' if info['authenticated'] else 'NO — redirected to login'}")
            print(f"Links : {len(info['sample_links'])} found on page")
            for lnk in info["sample_links"][:10]:
                print(f"  {lnk}")
            return

        # ── Discover articles ────────────────────────────────────────────
        if args.url:
            from medium_ingest.fetcher import ArticleMetadata
            articles = [ArticleMetadata(url=args.url)]
        elif args.bookmarks:
            articles = await fetcher.get_bookmarks(limit=args.limit)
        elif args.topic:
            articles = await fetcher.get_topic_articles(args.topic, limit=args.limit)
        elif args.list_url:
            articles = await fetcher.get_list_articles(args.list_url, limit=args.limit)
        else:
            log.error("Specify --url URL, --bookmarks, --topic TOPIC, or --list-url URL.")
            sys.exit(1)

        if not articles:
            log.warning("No articles found.")
            return

        log.info("Discovered %d articles.", len(articles))

        if args.resolve_only:
            for a in articles:
                print(f"{a.url}  {a.title[:80]}")
            return

        # ── Process each article ─────────────────────────────────────────
        written: list[Path] = []
        skipped = 0
        failed = 0

        for i, meta in enumerate(articles, 1):
            log.info("[%d/%d] %s", i, len(articles), meta.url)

            if not args.no_cache and cache.is_processed(meta.url):
                log.info("  Skipping (cached)")
                skipped += 1
                continue

            try:
                html, meta = await fetcher.fetch_article(meta)
                if not meta.title:
                    log.warning("  No title found — skipping")
                    failed += 1
                    continue

                try:
                    content = extract_content(html, meta.url)
                except ValueError as e:
                    log.error("  Extraction failed: %s", e)
                    failed += 1
                    continue

                log.info("  Extracted %d chars: %s", len(content), meta.title[:60])

                if args.dry_run:
                    _dry_run_preview(content, meta)
                    continue

                if args.raw:
                    path = write_note(content, meta, wiki_root, raw_mode=True)
                else:
                    try:
                        note = await structure_article(content, meta)
                        path = write_note(note, meta, wiki_root, raw_mode=False)
                    except RuntimeError as e:
                        log.warning("  LLM unavailable (%s) — falling back to --raw", e)
                        path = write_note(content, meta, wiki_root, raw_mode=True)

                written.append(path)
                cache.mark_processed(meta.url, str(path.name))

            except Exception as e:
                log.error("  Unhandled error for %s: %s", meta.url, e)
                failed += 1

    log.info("")
    log.info("Done. Written: %d | Skipped: %d | Failed: %d", len(written), skipped, failed)
    if written:
        log.info("Files in raw/:")
        for p in written:
            log.info("  %s", p.name)
        log.info("Next: run /wiki-ingest in Claude Code to integrate into the wiki.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dry_run_preview(content: str, meta) -> None:
    print(f"\n=== DRY RUN: {meta.title} ===")
    print(f"Author: {meta.author}  |  Publication: {meta.publication}")
    print(f"URL: {meta.url}")
    print(f"Content: {len(content)} chars")
    print("--- first 400 chars ---")
    print(content[:400])
    print("---\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Medium articles via Chrome CDP and write structured wiki notes."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url", metavar="URL",
                        help="Fetch and ingest a single article by URL")
    source.add_argument("--bookmarks", action="store_true",
                        help="Fetch from authenticated bookmark list")
    source.add_argument("--topic", metavar="TOPIC",
                        help='Fetch from a Medium tag page (e.g. "system design")')
    source.add_argument("--list-url", metavar="URL",
                        help="Fetch from a specific Medium reading list URL")

    parser.add_argument("--limit", type=int, default=100, metavar="N",
                        help="Max articles to process (default: 100). Also bounds discovery "
                             "scroll depth — a low --limit can silently truncate --list-url "
                             "discovery before the full list loads, not just the fetch count.")
    parser.add_argument("--login", action="store_true",
                        help="Open visible browser to log in; saves session for future headless runs")
    parser.add_argument("--raw", action="store_true",
                        help="Skip LLM structuring; write raw extracted text")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print extraction preview; do not write files")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore cache; reprocess all articles")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Clear URL cache and exit")
    parser.add_argument("--resolve-only", action="store_true",
                        help="Print discovered URLs and exit")
    parser.add_argument("--check-auth", action="store_true",
                        help="Check Medium auth status and exit")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
