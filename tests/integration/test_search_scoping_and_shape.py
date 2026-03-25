from __future__ import annotations

import pytest

from podcast_search.ingest.service import ingest_feed
from podcast_search.search.service import search
from fixtures.factories import fake_embed_texts_factory, setup_isolated_storage
from fixtures.rss_samples import RSS_A_EPISODE, RSS_B_EPISODE


def test_search_scoped_to_last_ingested_feed(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Integration check: results come from the latest ingested feed only.
    call_counter: dict[str, int] = {"embed_texts": 0}

    import podcast_search.ingest.service as ingest_service_mod
    import podcast_search.search.service as search_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(call_counter))
    monkeypatch.setattr(search_service_mod, "embed_texts", fake_embed_texts_factory(call_counter))
    monkeypatch.setattr(search_service_mod, "plan_query_text", lambda q: q)

    setup_isolated_storage(monkeypatch, tmp_path)

    ingest_feed(conn=None, feed_url="http://example.com/feedA", feed_xml=RSS_A_EPISODE, http=None, episode_limit=10)
    ingest_feed(conn=None, feed_url="http://example.com/feedB", feed_xml=RSS_B_EPISODE, http=None, episode_limit=10)

    hits = search(conn=None, query="EpisodeB1", k=5)
    assert hits
    for h in hits:
        assert h.episode_title == "EpisodeB1"
        assert isinstance(h.excerpt, str) and h.excerpt.strip()
        assert isinstance(h.score, float)

