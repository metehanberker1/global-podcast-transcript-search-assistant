from __future__ import annotations

import pytest

from app.config import settings
from podcast_search.indexing.index_handle_cache import clear_cache, get_index_handle
from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url


def test_index_handle_cache_backfills_from_registry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))

    fr = FeedRegistry(registry_path=settings.registry_path)
    feed_url = "http://example.com/feed"
    normalized = normalize_url(feed_url)
    feed_id = feed_id_from_normalized_url(normalized)

    # Create a registry entry as if ingest already happened.
    entry = fr.upsert_entry_after_ingest(
        feed_url=feed_url,
        parsed_related_urls=[],
        episode_count=1,
        chunk_count=1,
        last_error=None,
    )

    assert entry.feed_id == feed_id

    # Cache miss path: clear in-memory cache, then request without passing entry.
    clear_cache()
    handle = get_index_handle(normalized)
    assert handle.feed_id == entry.feed_id
    assert handle.collection_name == entry.collection_name

