from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from podcast_search.ingest.service import ingest_feed


def _setup_isolated_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))


def test_ingest_dedup_skips_reembedding_for_aliases(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    call_counter: dict[str, int] = {"embed_texts_calls": 0}

    # Fake embeddings so we don't hit OpenAI.
    def fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        call_counter["embed_texts_calls"] += 1
        return [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in texts]

    # Ensure ingest discovers an alias URL from feed XML.
    alias_url = "http://example.com/feed-alias/"
    import podcast_search.ingest.service as ingest_service_mod

    monkeypatch.setattr(ingest_service_mod, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(ingest_service_mod, "discover_related_feed_urls", lambda _xml: [alias_url])

    _setup_isolated_storage(monkeypatch, tmp_path)

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test</title>
    <item><title>Ep1</title></item>
  </channel>
</rss>"""

    feed_url = "http://example.com/feed"

    ingest_feed(
        conn=None,
        feed_url=feed_url,
        feed_xml=rss_xml,
        http=None,
        episode_limit=10,
    )

    # Second ingest with alias should be deduped and skip embeddings entirely.
    ingest_feed(
        conn=None,
        feed_url=alias_url,
        feed_xml=rss_xml,
        http=None,
        episode_limit=10,
    )

    assert call_counter["embed_texts_calls"] == 1

