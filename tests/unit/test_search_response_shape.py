from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from podcast_search.ingest.service import ingest_feed
from podcast_search.search.service import search


def _setup_isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))


def _fake_embeddings_factory():
    def _fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        # Fixed vectors per input string length just to keep shapes consistent.
        return [[float(len(t))] for t in texts]

    return _fake_embed_texts


def test_search_returns_snippet_only_shape(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import podcast_search.ingest.service as ingest_service_mod
    import podcast_search.search.service as search_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embeddings_factory())
    monkeypatch.setattr(search_service_mod, "embed_texts", _fake_embeddings_factory())
    monkeypatch.setattr(search_service_mod, "plan_query_text", lambda q: q)

    _setup_isolated_storage(monkeypatch, tmp_path)

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test</title>
    <item><title>Ep1</title><link>http://ep1</link></item>
  </channel>
</rss>"""

    ingest_feed(conn=None, feed_url="http://example.com/feed", feed_xml=rss_xml, http=None, episode_limit=10)
    hits = search(conn=None, query="Ep1", k=5)

    assert hits
    for hit in hits:
        d = hit.model_dump()
        # Required by OpenAPI: episode_title/excerpt/score.
        assert isinstance(d["episode_title"], str)
        assert isinstance(d["excerpt"], str)
        assert isinstance(d["score"], float)

        # Snippet-only: no generated summary/completion fields exist.
        assert "summary" not in d
        assert "completion" not in d

        allowed_keys = {
            "episode_title",
            "excerpt",
            "score",
            "episode_id",
            "published_at",
            "source_url",
        }
        assert set(d.keys()).issubset(allowed_keys)

