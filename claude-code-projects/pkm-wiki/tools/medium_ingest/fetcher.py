import asyncio
import logging
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

log = logging.getLogger(__name__)

_BOOKMARKS_URL = "https://medium.com/me/list/bookmarks"
_TAG_URL       = "https://medium.com/tag/{tag}"
_NAV_TIMEOUT   = 35_000  # ms

_PROFILE_DIR = Path.home() / ".medium_ingest_profile"

# Matches medium.com/@user/slug-hash or medium.com/pub/slug-hash
_ARTICLE_RE = re.compile(
    r"https?://(?:[\w-]+\.)?medium\.com/"
    r"(?:@[\w-]+/[\w-]+-[0-9a-f]{8,}|[\w-]+/[\w-]+-[0-9a-f]{8,})"
)


@dataclass
class ArticleMetadata:
    url: str
    title: str = ""
    author: str = ""
    publication: str = ""
    reading_time: str = ""
    published_date: str = ""
    tags: list[str] = field(default_factory=list)


class MediumFetcher:
    """
    Wraps a persistent Chrome context.
    Profile at ~/.medium_ingest_profile preserves session across runs.
    Always non-headless — avoids bot-detection fingerprinting.
    """

    def __init__(self, profile_dir: Path = _PROFILE_DIR):
        self._profile_dir = profile_dir
        self._pw = None
        self._ctx: BrowserContext | None = None

    async def __aenter__(self) -> "MediumFetcher":
        self._pw = await async_playwright().start()
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self._profile_dir),
            channel="chrome",
            headless=False,
            slow_mo=50,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ],
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            locale="en-US",
        )
        return self

    async def __aexit__(self, *_):
        if self._ctx:
            await self._ctx.close()
        if self._pw:
            await self._pw.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_logged_in(self, page: Page) -> bool:
        await page.goto(_BOOKMARKS_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
        if "signin" in page.url or "/m/signin" in page.url:
            return False
        try:
            return await page.locator("text=Sign in").count() == 0
        except Exception:
            return True

    async def _is_blocked(self, page: Page) -> bool:
        url = page.url
        # Cloudflare challenge pages land on /cdn-cgi/ paths or have a generic title
        if "cdn-cgi/challenge" in url:
            log.warning("  Cloudflare challenge URL detected: %s", url)
            return True
        content = (await page.content()).lower()
        # "verify you are human" on a page that has no article title = real block
        if "verify you are human" in content and "hcaptcha" in content:
            log.warning("  hCaptcha challenge detected | url=%s", url)
            return True
        return False

    async def _check_blocked(self, page: Page) -> None:
        if await self._is_blocked(page):
            if not sys.stdin.isatty():
                raise RuntimeError("Bot check triggered but stdin is not interactive. Run manually in a terminal to resolve.")
            print("\nBot check triggered. Resolve manually in the browser window.")
            input("Press ENTER after completing verification...\n")

    async def _ensure_logged_in(self, page: Page, target_url: str) -> None:
        """Navigate to target_url; pause for manual login or bot verification if needed."""
        await page.goto(target_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
        await page.wait_for_timeout(1500)
        await self._check_blocked(page)
        # URL-only check: Medium redirects to /m/signin if not authenticated
        needs_login = "signin" in page.url or "login" in page.url
        if needs_login:
            if not sys.stdin.isatty():
                raise RuntimeError("Auth required but stdin is not interactive. Run: python -m medium_ingest --login")
            print("\nAuth required. Please log in in the opened browser window.")
            input("Press ENTER after completing login...\n")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
            await page.wait_for_timeout(1500)
            await self._check_blocked(page)
            if "signin" in page.url or "login" in page.url:
                raise RuntimeError("Still not logged in after manual login attempt.")

    async def check_auth(self) -> dict:
        page = await self._ctx.new_page()
        try:
            await page.goto(_BOOKMARKS_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
            await asyncio.sleep(2)
            url   = page.url
            title = await page.title()
            links = await page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href]')).slice(0,20).map(a=>a.href)"
            )
            authenticated = "/signin" not in url and "/m/signin" not in url and "/me/" in url
            return {"url": url, "title": title, "authenticated": authenticated, "sample_links": links}
        finally:
            await page.close()

    async def get_bookmarks(self, limit: int = 10) -> list[ArticleMetadata]:
        page = await self._ctx.new_page()
        try:
            log.info("Loading bookmarks page...")
            await self._ensure_logged_in(page, _BOOKMARKS_URL)
            await self._wait_for_articles(page)
            return await self._collect_article_links(page, limit)
        finally:
            await page.close()

    async def get_list_articles(self, list_url: str, limit: int = 10) -> list[ArticleMetadata]:
        page = await self._ctx.new_page()
        try:
            log.info("Loading list page: %s", list_url)
            await self._ensure_logged_in(page, list_url)
            await self._wait_for_articles(page)
            return await self._collect_article_links(page, limit)
        finally:
            await page.close()

    async def get_topic_articles(self, topic: str, limit: int = 10) -> list[ArticleMetadata]:
        tag = topic.strip().lower().replace(" ", "-")
        url = _TAG_URL.format(tag=tag)
        page = await self._ctx.new_page()
        try:
            log.info("Loading topic page: %s", url)
            await self._ensure_logged_in(page, url)
            await self._wait_for_articles(page)
            return await self._collect_article_links(page, limit)
        finally:
            await page.close()

    async def fetch_article(self, meta: ArticleMetadata) -> tuple[str, ArticleMetadata]:
        page = await self._ctx.new_page()
        try:
            log.info("  Fetching: %s", meta.url)
            await self._ensure_logged_in(page, meta.url)
            await page.mouse.wheel(0, random.randint(1000, 2000))
            await page.wait_for_timeout(random.randint(800, 2000))
            try:
                await page.wait_for_selector("article, [data-testid='post-body']", timeout=10_000)
            except Exception:
                pass
            enriched = await page.evaluate(_METADATA_JS)
            meta.title          = enriched.get("title")        or meta.title
            meta.author         = enriched.get("author")       or meta.author
            meta.publication    = enriched.get("publication")  or meta.publication
            meta.reading_time   = enriched.get("readingTime")  or meta.reading_time
            meta.published_date = enriched.get("publishedDate") or meta.published_date
            meta.tags           = enriched.get("tags")         or meta.tags
            return await page.content(), meta
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    async def _wait_for_articles(page: Page) -> None:
        try:
            await page.wait_for_selector("article, h2 a, h3 a", timeout=12_000)
        except Exception:
            pass
        await asyncio.sleep(1.5)

    async def _collect_article_links(self, page: Page, limit: int) -> list[ArticleMetadata]:
        seen: set[str] = set()
        results: list[ArticleMetadata] = []
        for _ in range(max(3, limit // 4 + 2)):
            for item in await page.evaluate(_LINK_EXTRACT_JS):
                url = item.get("url", "").split("?")[0].rstrip("/")
                if not url or url in seen or not _ARTICLE_RE.match(url):
                    continue
                seen.add(url)
                results.append(ArticleMetadata(url=url, title=item.get("title", "").strip()))
                if len(results) >= limit:
                    return results
            if len(results) >= limit:
                break
            await page.mouse.wheel(0, random.randint(1200, 2500))
            await page.wait_for_timeout(random.randint(2000, 4500))
        log.info("  Found %d article links", len(results))
        return results


# ---------------------------------------------------------------------------
# JavaScript helpers
# ---------------------------------------------------------------------------

_LINK_EXTRACT_JS = """
() => {
    const out = [];
    document.querySelectorAll('a[href]').forEach(a => {
        const href = a.href;
        if (!href) return;
        const h = a.querySelector('h1,h2,h3,h4') ||
                  a.closest('article,[data-post-id]')?.querySelector('h1,h2,h3');
        const title = h ? h.textContent.trim()
                        : (a.textContent.trim().length > 20 ? a.textContent.trim() : '');
        out.push({url: href, title});
    });
    return out;
}
"""

_METADATA_JS = """
() => {
    const title = (document.querySelector('h1')?.textContent || document.title || '').trim();
    let author = '';
    for (const sel of ['[data-testid="authorName"]','.pw-author-name','a[rel="author"]']) {
        const el = document.querySelector(sel);
        if (el?.textContent.trim()) { author = el.textContent.trim(); break; }
    }
    let publication = '';
    for (const sel of ['[data-testid="publicationName"]','.pw-publication-name']) {
        const el = document.querySelector(sel);
        if (el?.textContent.trim()) { publication = el.textContent.trim(); break; }
    }
    const readingTime   = document.querySelector('[data-testid="storyReadTime"],.readingTime')?.textContent.trim() || '';
    const timeEl        = document.querySelector('time[datetime]');
    const publishedDate = timeEl?.getAttribute('datetime') || timeEl?.textContent.trim() || '';
    const tags = [...new Set(
        [...document.querySelectorAll('a[href*="/tag/"]')].map(a => a.textContent.trim()).filter(Boolean)
    )].slice(0, 8);
    return {title, author, publication, readingTime, publishedDate, tags};
}
"""
