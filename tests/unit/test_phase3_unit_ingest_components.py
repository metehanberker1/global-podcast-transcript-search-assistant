from __future__ import annotations

import hashlib

import pytest

from podcast_search.indexing.chunking import chunk_text
from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url


def test_normalize_url_and_feed_id_stable_across_aliases() -> None:
    # Equivalent URLs differing by case, trailing slash, and fragment.
    a = "https://feeds.Captivate.fm/the-news-agents#frag"
    b = "https://feeds.captivate.fm/the-news-agents/"

    na = normalize_url(a)
    nb = normalize_url(b)

    assert na == nb
    assert feed_id_from_normalized_url(na) == feed_id_from_normalized_url(nb)

    # Must match the existing pre-seeded registry feed_id.
    expected = "22543618f282e8f41f598859"  # sha256(canonical_url)[:24] for the captivate url
    assert feed_id_from_normalized_url(nb) == expected


def test_chunk_text_overlap_correctness() -> None:
    # chunk_size=10 overlap=3 => step=7
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunk_text(text, chunk_size=10, overlap=3)

    assert chunks
    assert len(chunks[0]) <= 10

    # Overlap: suffix of prev length overlap equals prefix of next length overlap.
    if len(chunks) >= 2:
        ov = 3
        assert chunks[0][-ov:] == chunks[1][:ov]


def test_feed_registry_alias_storage_and_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Isolate persistence.
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

    # Both original and related aliases must appear in related_urls.
    assert feed_url in loaded.related_urls
    assert alias_url in loaded.related_urls

    # Finder should match on alias URL input.
    lookup = fr.find_by_input_url(alias_url)
    assert lookup.entry is not None
    assert lookup.feed_id == entry.feed_id

    # Pointer must be set to the latest ingested feed_id.
    assert fr.get_most_recent_feed_id() == entry.feed_id

