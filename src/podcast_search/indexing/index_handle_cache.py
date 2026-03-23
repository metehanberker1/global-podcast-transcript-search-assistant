from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from podcast_search.models import FeedRegistryEntry
from podcast_search.registry.feed_registry import FeedRegistry


@dataclass
class IndexHandleCacheEntry:
    feed_id: str
    collection_name: str
    loaded_at: str


_CACHE: dict[str, IndexHandleCacheEntry] = {}


def get_index_handle(
    normalized_url: str, *, entry: FeedRegistryEntry | None = None
) -> IndexHandleCacheEntry:
    """Cache-first resolution of the Chroma collection for a feed."""

    cached = _CACHE.get(normalized_url)
    if cached is not None:
        from podcast_search.metrics.service import record_cache_hit

        record_cache_hit()
        return cached

    from podcast_search.metrics.service import record_cache_miss

    record_cache_miss()

    # Cache miss: backfill from the persisted registry on disk.
    if entry is None:
        registry = FeedRegistry()
        lookup = registry.find_by_input_url(normalized_url)
        if lookup.entry is None:
            raise RuntimeError(f"Feed not found in registry for normalized_url={normalized_url!r}")
        entry = lookup.entry

    loaded = IndexHandleCacheEntry(
        feed_id=entry.feed_id,
        collection_name=entry.collection_name,
        loaded_at=datetime.utcnow().isoformat(),
    )
    _CACHE[normalized_url] = loaded
    return loaded


def update_cache_for_entry(entry: FeedRegistryEntry) -> None:
    _CACHE[entry.normalized_url] = IndexHandleCacheEntry(
        feed_id=entry.feed_id,
        collection_name=entry.collection_name,
        loaded_at=datetime.utcnow().isoformat(),
    )


def clear_cache() -> None:
    _CACHE.clear()


def cache_size() -> int:
    return len(_CACHE)

