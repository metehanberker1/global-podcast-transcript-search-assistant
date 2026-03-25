from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from podcast_search.models import FeedRegistryEntry
from podcast_search.registry.feed_registry import FeedRegistry
from app.config import settings


@dataclass
class IndexHandleCacheEntry:
    feed_id: str
    collection_name: str
    loaded_at: str
    persist_dir: str


_CACHE: dict[str, IndexHandleCacheEntry] = {}


def _persist_dir_for_owner(owner: str) -> str:
    # Single-node mode uses the shared base directory.
    nodes = [n.strip() for n in settings.shard_nodes.split(",") if n.strip()]
    if len(nodes) <= 1:
        return settings.chroma_persist_dir

    import os

    return os.path.join(settings.chroma_persist_dir, owner)


def _persist_dir_for_feed_id(feed_id: str) -> str:
    from podcast_search.sharding.router import Router

    owner = Router().get_owner(feed_id)
    return _persist_dir_for_owner(owner)


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

    # On cache miss, resolve the feed from persisted registry state.
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
        persist_dir=_persist_dir_for_feed_id(entry.feed_id),
    )
    _CACHE[normalized_url] = loaded
    return loaded


def update_cache_for_entry(entry: FeedRegistryEntry) -> None:
    _CACHE[entry.normalized_url] = IndexHandleCacheEntry(
        feed_id=entry.feed_id,
        collection_name=entry.collection_name,
        loaded_at=datetime.utcnow().isoformat(),
        persist_dir=_persist_dir_for_feed_id(entry.feed_id),
    )


def clear_cache() -> None:
    _CACHE.clear()


def cache_size() -> int:
    return len(_CACHE)

