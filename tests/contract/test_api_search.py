from __future__ import annotations

import chromadb
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from api.main import app as api_app
from podcast_search.ingest import service as ingest_service_mod
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url
from podcast_search.search import service as search_service_mod
from fixtures.factories import fake_embed_texts_factory, setup_isolated_storage
from fixtures.rss_samples import RSS_A_EPISODE, RSS_B_EPISODE, RSS_EP1


def _fake_plan_query_text(q: str) -> str:
    return q


def test_api_search_400_before_ingest(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Search should reject requests until at least one feed is ingested.
    setup_isolated_storage(monkeypatch, tmp_path)

    client = TestClient(api_app)
    resp = client.post("/api/search", json={"query": "hi", "top_k": 5})
    assert resp.status_code == 400


def test_api_search_scoped_to_last_ingested_feed(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Contract: search scope follows the most recently ingested feed.
    setup_isolated_storage(monkeypatch, tmp_path)

    embed_call_counter: dict[str, int] = {"embed_texts": 0}
    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(embed_call_counter))
    monkeypatch.setattr(search_service_mod, "embed_texts", fake_embed_texts_factory(embed_call_counter))
    monkeypatch.setattr(search_service_mod, "plan_query_text", _fake_plan_query_text)

    def fake_get_text(self, url: str) -> str:
        if "feedA" in url:
            return RSS_A_EPISODE
        return RSS_B_EPISODE

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    client.post("/api/feeds", json={"feed_url": "http://example.com/feedA", "episode_limit": 10})
    client.post("/api/feeds", json={"feed_url": "http://example.com/feedB", "episode_limit": 10})

    resp = client.post("/api/search", json={"query": "EpisodeB1", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    results = body["results"]
    assert results
    assert all(r["episode_title"] == "EpisodeB1" for r in results)


def test_api_search_does_not_persist_query_embeddings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Query-time embeddings must not append new documents to collections.
    setup_isolated_storage(monkeypatch, tmp_path)

    embed_call_counter: dict[str, int] = {"embed_texts": 0}
    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(embed_call_counter))
    monkeypatch.setattr(search_service_mod, "embed_texts", fake_embed_texts_factory(embed_call_counter))
    monkeypatch.setattr(search_service_mod, "plan_query_text", _fake_plan_query_text)

    feed_url = "http://example.com/feed"
    normalized = normalize_url(feed_url)
    feed_id = feed_id_from_normalized_url(normalized)
    collection_name = f"feed_{feed_id}"

    def fake_get_text(self, url: str) -> str:
        return RSS_A_EPISODE

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    client.post("/api/feeds", json={"feed_url": feed_url, "episode_limit": 10})

    chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = chroma.get_collection(collection_name)
    before = collection.count()

    _ = client.post("/api/search", json={"query": "EpisodeA1", "top_k": 5})
    after = collection.count()
    assert after == before


def test_api_search_returns_empty_results_when_query_collection_returns_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # API should return an empty list (not an error) when no hits are found.
    setup_isolated_storage(monkeypatch, tmp_path)

    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(None))
    monkeypatch.setattr(search_service_mod, "embed_texts", fake_embed_texts_factory(None))
    monkeypatch.setattr(search_service_mod, "plan_query_text", lambda q: q)
    monkeypatch.setattr(search_service_mod, "query_collection", lambda **kwargs: [])

    def fake_get_text(self, url: str) -> str:
        return RSS_EP1

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    resp_ingest = client.post(
        "/api/feeds",
        json={"feed_url": "http://example.com/feed", "episode_limit": 10},
    )
    assert resp_ingest.status_code == 201

    resp_search = client.post("/api/search", json={"query": "Anything", "top_k": 5})
    assert resp_search.status_code == 200
    body = resp_search.json()
    assert body["results"] == []


def test_api_top_k_validation(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Request validation should enforce the configured top_k bounds.
    setup_isolated_storage(monkeypatch, tmp_path)
    client = TestClient(api_app)

    resp = client.post("/api/search", json={"query": "hi", "top_k": 100})
    assert resp.status_code == 422

