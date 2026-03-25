from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app as api_app
from podcast_search.ingest import service as ingest_service_mod
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url
from fixtures.factories import fake_embed_texts_factory, setup_isolated_storage
from fixtures.rss_samples import RSS_EP1


def test_api_feeds_201_then_409_dedup_same_url(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    setup_isolated_storage(monkeypatch, tmp_path)

    call_counter: dict[str, int] = {"embed_texts": 0}
    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(call_counter))

    def fake_get_text(self, url: str) -> str:
        return RSS_EP1

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    feed_url = "http://example.com/feed"
    normalized = normalize_url(feed_url)
    feed_id = feed_id_from_normalized_url(normalized)

    resp1 = client.post("/api/feeds", json={"feed_url": feed_url, "episode_limit": 10})
    assert resp1.status_code == 201
    body1 = resp1.json()
    assert body1["feed_id"] == feed_id
    assert body1["normalized_url"] == normalized

    resp2 = client.post("/api/feeds", json={"feed_url": feed_url, "episode_limit": 10})
    assert resp2.status_code == 409
    body2 = resp2.json()
    assert body2["feed_id"] == feed_id

    # Embeddings should be created only on first ingest.
    assert call_counter["embed_texts"] == 1


def test_api_feeds_409_dedup_on_alias_without_refetch(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    setup_isolated_storage(monkeypatch, tmp_path)

    call_counter: dict[str, int] = {"embed_texts": 0, "get_text": 0}
    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts_factory(call_counter))

    alias_url = "http://example.com/feed-alias/"
    monkeypatch.setattr(ingest_service_mod, "discover_related_feed_urls", lambda _xml: [alias_url])

    def fake_get_text(self, url: str) -> str:
        call_counter["get_text"] += 1
        return RSS_EP1

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    feed_url = "http://example.com/feed"

    resp1 = client.post("/api/feeds", json={"feed_url": feed_url, "episode_limit": 10})
    assert resp1.status_code == 201

    resp2 = client.post("/api/feeds", json={"feed_url": alias_url, "episode_limit": 10})
    assert resp2.status_code == 409

    # Alias ingest should short-circuit before another fetch.
    assert call_counter["get_text"] == 1
    assert call_counter["embed_texts"] == 1


def test_api_feeds_unreachable_returns_400(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    setup_isolated_storage(monkeypatch, tmp_path)

    def fake_get_text(self, url: str) -> str:
        raise RuntimeError("unreachable")

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    resp = client.post("/api/feeds", json={"feed_url": "http://example.com/feed", "episode_limit": 10})
    assert resp.status_code == 400
    body = resp.json()
    assert "Failed to fetch RSS feed" in body.get("detail", "")


def test_api_feeds_non_rss_returns_400(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    setup_isolated_storage(monkeypatch, tmp_path)

    monkeypatch.setattr(ingest_service_mod, "extract_episode_items", lambda _xml, episode_limit: [])

    def fake_get_text(self, url: str) -> str:
        return "not xml"

    monkeypatch.setattr("app.http.Http.get_text", fake_get_text)

    client = TestClient(api_app)
    resp = client.post("/api/feeds", json={"feed_url": "http://example.com/feed", "episode_limit": 10})
    assert resp.status_code == 400

