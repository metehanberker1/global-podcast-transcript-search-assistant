from __future__ import annotations

from typing import Any

import chromadb
import pytest

from app.config import settings
from podcast_search.ingest.service import ingest_feed
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url
from podcast_search.search.service import search


def _setup_isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))


def _fake_embeddings_factory():
    def _fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in texts]

    return _fake_embed_texts


def test_query_embeddings_do_not_create_new_documents(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import podcast_search.ingest.service as ingest_service_mod
    import podcast_search.search.service as search_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embeddings_factory())
    monkeypatch.setattr(search_service_mod, "embed_texts", _fake_embeddings_factory())
    monkeypatch.setattr(search_service_mod, "plan_query_text", lambda q: q)

    _setup_isolated_storage(monkeypatch, tmp_path)

    feed_url = "http://example.com/feed"
    normalized = normalize_url(feed_url)
    feed_id = feed_id_from_normalized_url(normalized)
    collection_name = f"feed_{feed_id}"

    rss_a = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>A</title>
    <item><title>EpisodeA1</title><link>http://epA1</link></item>
  </channel>
</rss>"""

    ingest_feed(conn=None, feed_url=feed_url, feed_xml=rss_a, http=None, episode_limit=10)

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_collection(collection_name)
    before_count = collection.count()

    _ = search(conn=None, query="EpisodeA1", k=5)

    after_count = collection.count()
    assert after_count == before_count

