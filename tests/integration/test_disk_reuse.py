from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from podcast_search.indexing.index_handle_cache import clear_cache
from podcast_search.ingest.service import ingest_feed
from podcast_search.search.service import search


def _setup_isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))


def _fake_embeddings_factory(call_counter: dict[str, int]):
    def _fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        call_counter["embed_texts"] += 1
        # One vector per input string.
        return [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in texts]

    return _fake_embed_texts


def test_disk_reuse_after_clearing_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    call_counter: dict[str, int] = {"embed_texts": 0}

    import podcast_search.ingest.service as ingest_service_mod
    import podcast_search.search.service as search_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embeddings_factory(call_counter))
    monkeypatch.setattr(search_service_mod, "embed_texts", _fake_embeddings_factory(call_counter))
    monkeypatch.setattr(search_service_mod, "plan_query_text", lambda q: q)

    _setup_isolated_storage(monkeypatch, tmp_path)

    rss_a = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>A</title>
    <item><title>EpisodeA1</title></item>
  </channel>
</rss>"""

    res = ingest_feed(
        conn=None,
        feed_url="http://example.com/feedA",
        feed_xml=rss_a,
        http=None,
        episode_limit=10,
    )
    assert res.episode_count == 1
    assert res.chunk_count == 1
    assert call_counter["embed_texts"] == 1  # corpus embeddings embedded once

    clear_cache()  # simulate restart: in-memory index-handle cache cleared

    hits = search(conn=None, query="EpisodeA1", k=5)
    assert hits
    assert hits[0].episode_title == "EpisodeA1"

    # Query embedding should happen, but corpus embedding should NOT re-run.
    assert call_counter["embed_texts"] == 2

