from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from podcast_search.models import FeedRegistryEntry
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url


@dataclass(frozen=True)
class RegistryLookup:
    entry: FeedRegistryEntry | None
    feed_id: str | None


class FeedRegistry:
    """Persisted feed deduplication + pointer to most recent successful ingest."""

    def __init__(self, *, registry_path: str | None = None) -> None:
        self._registry_path = Path(registry_path or settings.registry_path)

    def _load_raw(self) -> dict[str, Any]:
        if not self._registry_path.exists():
            return {"most_recent_feed_id": None, "feeds": {}}

        with self._registry_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_raw_atomic(self, data: dict[str, Any]) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(prefix="feed_registry_", dir=str(self._registry_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self._registry_path))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def load(self) -> dict[str, FeedRegistryEntry]:
        raw = self._load_raw()
        feeds_raw: dict[str, Any] = raw.get("feeds", {}) or {}

        out: dict[str, FeedRegistryEntry] = {}
        for feed_id, entry in feeds_raw.items():
            try:
                out[feed_id] = FeedRegistryEntry.model_validate(entry)
            except Exception:
                # Skip malformed entries so one bad record does not block reads.
                continue
        return out

    def get_most_recent_feed_id(self) -> str | None:
        raw = self._load_raw()
        return raw.get("most_recent_feed_id")

    def set_most_recent_feed_id(self, feed_id: str) -> None:
        raw = self._load_raw()
        raw["most_recent_feed_id"] = feed_id
        self._save_raw_atomic(raw)

    def find_by_input_url(self, feed_url: str) -> RegistryLookup:
        normalized = normalize_url(feed_url)
        feeds = self.load()

        # Prefer direct match on canonical URL.
        for entry in feeds.values():
            if entry.normalized_url == normalized:
                return RegistryLookup(entry=entry, feed_id=entry.feed_id)

        # Fall back to known URL aliases.
        for entry in feeds.values():
            if feed_url in (entry.related_urls or []) or normalized in (entry.related_urls or []):
                return RegistryLookup(entry=entry, feed_id=entry.feed_id)

        return RegistryLookup(entry=None, feed_id=None)

    def get_entry_for_feed_id(self, feed_id: str) -> FeedRegistryEntry | None:
        feeds = self.load()
        return feeds.get(feed_id)

    def upsert_entry_after_ingest(
        self,
        *,
        feed_url: str,
        parsed_related_urls: list[str],
        episode_count: int,
        chunk_count: int,
        last_error: str | None = None,
        now: datetime | None = None,
    ) -> FeedRegistryEntry:
        now = now or datetime.utcnow()

        normalized = normalize_url(feed_url)
        feed_id = feed_id_from_normalized_url(normalized)
        collection_name = f"feed_{feed_id}"

        raw = self._load_raw()
        feeds_raw: dict[str, Any] = raw.get("feeds", {}) or {}

        existing = feeds_raw.get(feed_id)
        if existing:
            entry = FeedRegistryEntry.model_validate(existing)
        else:
            entry = FeedRegistryEntry(
                feed_id=feed_id,
                original_url=feed_url,
                normalized_url=normalized,
                related_urls=[],
                collection_name=collection_name,
                last_indexed_at=None,
                episode_count=None,
                chunk_count=None,
                last_error=None,
            )

        # Keep all observed URL variants so future ingest requests dedupe correctly.
        related = set(entry.related_urls or [])
        related.add(feed_url)
        related.add(normalized)
        for u in parsed_related_urls:
            if u:
                related.add(u)
        entry.related_urls = sorted(related)

        entry.original_url = feed_url
        entry.collection_name = collection_name
        entry.episode_count = episode_count
        entry.chunk_count = chunk_count
        entry.last_indexed_at = now
        entry.last_error = last_error

        feeds_raw[feed_id] = entry.model_dump(mode="json")
        raw["feeds"] = feeds_raw
        raw["most_recent_feed_id"] = feed_id
        self._save_raw_atomic(raw)

        return entry

