from __future__ import annotations

import hashlib

import pytest

from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url


def test_normalize_url_and_feed_id_stable_across_aliases() -> None:
    # URL variants should normalize to the same canonical value.
    a = "https://feeds.Captivate.fm/the-news-agents#frag"
    b = "https://feeds.captivate.fm/the-news-agents/"

    na = normalize_url(a)
    nb = normalize_url(b)

    assert na == nb
    assert feed_id_from_normalized_url(na) == feed_id_from_normalized_url(nb)

    # Feed IDs are stable hashes of canonical URLs.
    expected = "22543618f282e8f41f598859"
    assert feed_id_from_normalized_url(nb) == expected


def test_feed_registry_alias_storage_and_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Use isolated registry storage for the test.
    registry_path = str(tmp_path / "feed_registry.json")
    fr = FeedRegistry(registry_path=registry_path)

    feed_url = "http://example.com/feed"
    alias_url = "http://example.com/feed-alias/"
    now = None

    entry = fr.upsert_entry_after_ingest(
        feed_url=feed_url,
        parsed_related_urls=[alias_url],
        episode_count=2,
        chunk_count=3,
        last_error=None,
        now=now,
    )

    loaded = fr.get_entry_for_feed_id(entry.feed_id)
    assert loaded is not None

    # Registry should keep both original and alias URLs.
    assert feed_url in loaded.related_urls
    assert alias_url in loaded.related_urls

    # Alias lookup should resolve to the same feed.
    lookup = fr.find_by_input_url(alias_url)
    assert lookup.entry is not None
    assert lookup.feed_id == entry.feed_id

    # Most-recent pointer should track the latest successful ingest.
    assert fr.get_most_recent_feed_id() == entry.feed_id

