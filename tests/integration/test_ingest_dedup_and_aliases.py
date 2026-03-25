from __future__ import annotations

from typing import Any

import pytest

from podcast_search.ingest.service import ingest_feed
from fixtures.factories import setup_isolated_storage
from fixtures.rss_samples import RSS_EP1


def test_ingest_dedup_skips_reembedding_for_aliases(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    call_counter: dict[str, int] = {"embed_texts_calls": 0}

    # Stub embeddings to keep the test offline and deterministic.
    def fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        call_counter["embed_texts_calls"] += 1
        return [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in texts]

    # Return one alias URL discovered from the feed payload.
    alias_url = "http://example.com/feed-alias/"
    import podcast_search.ingest.service as ingest_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(ingest_service_mod, "discover_related_feed_urls", lambda _xml: [alias_url])

    setup_isolated_storage(monkeypatch, tmp_path)

    feed_url = "http://example.com/feed"

    ingest_feed(
        conn=None,
        feed_url=feed_url,
        feed_xml=RSS_EP1,
        http=None,
        episode_limit=10,
    )

    # Alias ingest should dedupe and avoid another embedding call.
    ingest_feed(
        conn=None,
        feed_url=alias_url,
        feed_xml=RSS_EP1,
        http=None,
        episode_limit=10,
    )

    assert call_counter["embed_texts_calls"] == 1

