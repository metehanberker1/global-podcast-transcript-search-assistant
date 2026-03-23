from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import connect, get_db_config
from app.http import Http
from app.migrations.runner import apply_all
from api.main import app as api_app
from podcast_search.ingest.service import ingest_feed
from podcast_search.search.service import search


def _setup_isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))


def _fake_embeddings_factory(call_counter: dict[str, int]):
    def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
        call_counter["embed_texts"] += 1
        # Fixed-size vectors; Chroma only requires consistency.
        return [[0.123, 0.456, 0.789, 0.111, 0.222] for _ in texts]

    return _fake_embed_texts


def test_settings_loaded_defaults() -> None:
    assert settings.database_url == "local-mvp"
    assert settings.ingest_episode_limit > 0


def test_db_connect_close() -> None:
    cfg = get_db_config(settings.database_url)
    conn = connect(cfg)
    conn.close()


def test_http_get_text_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss/>")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    http = Http(client=client)
    try:
        assert http.get_text("http://example.com") == "<rss/>"
    finally:
        http.close()


def test_http_get_text_request_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    http = Http(client=httpx.Client(transport=transport))
    with pytest.raises(RuntimeError, match="Failed to fetch URL"):
        http.get_text("http://example.com")
    http.close()


def test_http_get_text_http_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    transport = httpx.MockTransport(handler)
    http = Http(client=httpx.Client(transport=transport))
    with pytest.raises(RuntimeError, match="Non-200 response"):
        http.get_text("http://example.com")
    http.close()


def test_apply_all_noop() -> None:
    apply_all(conn=object(), migrations_dir=__import__("pathlib").Path("."))


def test_ingest_creates_chunks_and_updates_registry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Prevent real OpenAI calls.
    call_counter: dict[str, int] = {"embed_texts": 0}
    import podcast_search.ingest.service as ingest_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embeddings_factory(call_counter))

    _setup_isolated_storage(monkeypatch, tmp_path)

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test</title>
    <item><title>Ep1</title></item>
    <item><title>Ep2</title></item>
  </channel>
</rss>"""

    res = ingest_feed(conn=None, feed_url="http://example.com/feed", feed_xml=rss_xml, http=None, episode_limit=1)
    assert res.episode_count == 1
    assert res.chunk_count == 1
    assert call_counter["embed_texts"] == 1  # one call for one chunk


def test_ingest_dedup_skips_reembedding(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    call_counter: dict[str, int] = {"embed_texts": 0}
    import podcast_search.ingest.service as ingest_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embeddings_factory(call_counter))
    _setup_isolated_storage(monkeypatch, tmp_path)

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test</title>
    <item><title>Ep1</title></item>
  </channel>
</rss>"""

    feed_url = "http://example.com/feed"
    res1 = ingest_feed(conn=None, feed_url=feed_url, feed_xml=rss_xml, http=None, episode_limit=10)
    res2 = ingest_feed(conn=None, feed_url=feed_url, feed_xml=rss_xml, http=None, episode_limit=10)

    assert res1 == res2
    assert call_counter["embed_texts"] == 1  # second ingest skips embeddings entirely


def test_search_scoped_to_last_ingested_feed(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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
    rss_b = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>B</title>
    <item><title>EpisodeB1</title></item>
  </channel>
</rss>"""

    ingest_feed(conn=None, feed_url="http://example.com/feedA", feed_xml=rss_a, http=None, episode_limit=10)
    ingest_feed(conn=None, feed_url="http://example.com/feedB", feed_xml=rss_b, http=None, episode_limit=10)

    hits = search(conn=None, query="EpisodeB1", k=5)
    assert hits
    assert all(h.episode_title == "EpisodeB1" for h in hits)


def test_search_without_ingest_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _setup_isolated_storage(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="No ingested feed found"):
        search(conn=None, query="hi", k=5)


def test_metrics_endpoint_smoke() -> None:
    client = TestClient(api_app)
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.json()
    # Must include at least the core required metrics fields.
    required = {
        "ingest_episode_count",
        "chunk_index_count",
        "search_hit_count",
        "ingest_duration_ms_last",
        "search_duration_ms_last",
    }
    assert required.issubset(set(body.keys()))

