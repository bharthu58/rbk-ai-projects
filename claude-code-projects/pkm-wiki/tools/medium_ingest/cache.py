"""
cache.py — Simple JSON cache to avoid reprocessing articles.

Stored at <wiki_root>/raw/.medium_cache.json (alongside raw/ files).
Key: canonical article URL (query-string stripped).
Value: {"path": "medium--slug--date.md", "processed_at": "ISO datetime"}

Dedup checks both the canonical URL (fast path, exact match) and the
Medium post-ID embedded in the URL slug (catches the same story reachable
under a different publication alias, e.g. /@author/slug-abc123 vs
/some-publication/slug-abc123 — same trailing hex ID, different path).
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_POST_ID_RE = re.compile(r"-([0-9a-f]{6,})/?$")


class Cache:
    def __init__(self, cache_path: Path):
        self._path = cache_path
        self._data: dict[str, dict] = {}
        self._post_ids: dict[str, str] = {}  # post_id -> canonical URL already cached
        self._load()

    def is_processed(self, url: str) -> bool:
        canonical = self._canonical(url)
        if canonical in self._data:
            return True
        post_id = self._post_id(url)
        return post_id is not None and post_id in self._post_ids

    def mark_processed(self, url: str, output_path: str = "") -> None:
        canonical = self._canonical(url)
        self._data[canonical] = {
            "path": output_path,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        post_id = self._post_id(url)
        if post_id is not None:
            self._post_ids[post_id] = canonical
        self._save()

    def clear(self) -> None:
        self._data.clear()
        self._post_ids.clear()
        self._save()
        log.info("Cache cleared: %s", self._path)

    def __len__(self) -> int:
        return len(self._data)

    # ------------------------------------------------------------------

    @staticmethod
    def _canonical(url: str) -> str:
        return url.split("?")[0].rstrip("/")

    @staticmethod
    def _post_id(url: str) -> str | None:
        """Extract Medium's trailing post-ID hex suffix from a URL slug, if present."""
        match = _POST_ID_RE.search(url.split("?")[0])
        return match.group(1) if match else None

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Cache load failed (%s) — starting fresh", e)
                self._data = {}
        # Build the post-ID index from whatever URLs are already cached,
        # regardless of how they were originally keyed.
        for cached_url in self._data:
            post_id = self._post_id(cached_url)
            if post_id is not None:
                self._post_ids.setdefault(post_id, cached_url)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            log.warning("Cache save failed: %s", e)
