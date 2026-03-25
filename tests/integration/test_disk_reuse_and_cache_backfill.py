from __future__ import annotations

import pytest

from podcast_search.indexing.index_handle_cache import clear_cache
from podcast_search.ingest.service import ingest_feed
from podcast_search.search.service import search
from fixtures.factories import fake_embed_texts_factory, setup_isolated_storage
from fixtures.rss_samples import RSS_A_EPISODE


def test_disk_reuse_after_clearing_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    call_counter: dict[str, int] = {"embed_texts": 0}

    import podcast_search.ingest.service as ingest_service_mod
    import podcast_search.search.service as search_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(call_counter))
    monkeypatch.setattr(search_service_mod, "embed_texts", fake_embed_texts_factory(call_counter))
    monkeypatch.setattr(search_service_mod, "plan_query_text", lambda q: q)

    setup_isolated_storage(monkeypatch, tmp_path)

    res = ingest_feed(
        conn=None,
        feed_url="http://example.com/feedA",
        feed_xml=RSS_A_EPISODE,
        http=None,
        episode_limit=10,
    )
    assert res.episode_count == 1
    assert res.chunk_count == 1
    assert call_counter["embed_texts"] == 1  # one embedding call during ingest

    clear_cache()  # simulate cold in-memory cache

    hits = search(conn=None, query="EpisodeA1", k=5)
    assert hits
    assert hits[0].episode_title == "EpisodeA1"

    # Query embedding runs, but corpus vectors are reused from storage.
    assert call_counter["embed_texts"] == 2

