from __future__ import annotations

import pytest

from app.config import settings
from podcast_search.indexing.index_handle_cache import clear_cache, get_index_handle, update_cache_for_entry
from podcast_search.indexing.index_handle_cache import cache_size
from podcast_search.models import FeedRegistryEntry
from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url


def test_index_handle_cache_miss_hit_and_clear() -> None:
    clear_cache()
    assert cache_size() == 0

    entry = FeedRegistryEntry(
        feed_id="fid",
        original_url="http://x",
        normalized_url="http://x",
        related_urls=[],
        collection_name="feed_fid",
        last_indexed_at=None,
        episode_count=None,
        chunk_count=None,
        last_error=None,
    )

    h1 = get_index_handle(entry.normalized_url, entry=entry)
    assert cache_size() == 1
    h2 = get_index_handle(entry.normalized_url, entry=entry)
    assert h1 is h2

    update_cache_for_entry(entry)
    assert cache_size() == 1

    clear_cache()
    assert cache_size() == 0


def test_index_handle_cache_backfills_from_registry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))

    fr = FeedRegistry(registry_path=settings.registry_path)
    feed_url = "http://example.com/feed"
    normalized = normalize_url(feed_url)
    feed_id = feed_id_from_normalized_url(normalized)

    # Seed registry with one ingested feed entry.
    entry = fr.upsert_entry_after_ingest(
        feed_url=feed_url,
        parsed_related_urls=[],
        episode_count=1,
        chunk_count=1,
        last_error=None,
    )

    assert entry.feed_id == feed_id

    # Force cache-miss path by clearing memory and resolving from registry.
    clear_cache()
    handle = get_index_handle(normalized)
    assert handle.feed_id == entry.feed_id
    assert handle.collection_name == entry.collection_name


def test_index_handle_cache_write_through_avoids_registry_lookup(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))

    fr = FeedRegistry(registry_path=settings.registry_path)
    feed_url = "http://example.com/feed"
    normalized = normalize_url(feed_url)

    entry = fr.upsert_entry_after_ingest(
        feed_url=feed_url,
        parsed_related_urls=[],
        episode_count=1,
        chunk_count=1,
        last_error=None,
    )

    clear_cache()
    update_cache_for_entry(entry)

    def _boom(*args, **kwargs):
        raise AssertionError("Registry lookup should not be called on cache hit")

    monkeypatch.setattr(FeedRegistry, "find_by_input_url", _boom)
    handle = get_index_handle(normalized)
    assert handle.feed_id == entry.feed_id

