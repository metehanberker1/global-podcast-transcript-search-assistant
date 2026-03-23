from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from podcast_search.indexing import chroma_store
from podcast_search.indexing.embeddings import embed_texts
from podcast_search.indexing.index_handle_cache import (
    cache_size,
    clear_cache,
    get_index_handle,
    update_cache_for_entry,
)
from podcast_search.models import FeedRegistryEntry
from podcast_search.ingest.rss_extract import discover_related_feed_urls, extract_episode_items
from podcast_search.search.query_planner import plan_query_text


def test_chroma_score_branches() -> None:
    assert chroma_store._score_from_distance(None) == 0.0
    assert chroma_store._score_from_distance(0.0) == 1.0

    # NaN -> score is NaN -> clamped to 0.0
    assert chroma_store._score_from_distance(float("nan")) == 0.0
    # Infinite -> clamped to 0.0
    assert chroma_store._score_from_distance(float("-inf")) == 0.0


def test_chroma_upsert_empty_chunk_ids() -> None:
    # Should short-circuit before touching chromadb
    chroma_store.upsert_chunks(
        collection_name="feed_x",
        chunk_ids=[],
        documents=[],
        metadatas=[],
        embeddings=[],
    )


def test_index_handle_cache_miss_hit_and_clear() -> None:
    clear_cache()
    assert cache_size() == 0

    entry = FeedRegistryEntry(
        feed_id="fid",
        original_url="http://x",
        normalized_url="http://x",
        related_urls=[],
        collection_name="feed_fid",
        last_indexed_at=None,
        episode_count=None,
        chunk_count=None,
        last_error=None,
    )

    h1 = get_index_handle(entry.normalized_url, entry=entry)
    assert cache_size() == 1
    h2 = get_index_handle(entry.normalized_url, entry=entry)
    assert h1 is h2  # cached object returned

    update_cache_for_entry(entry)
    assert cache_size() == 1

    clear_cache()
    assert cache_size() == 0


def test_embed_texts_empty_short_circuit() -> None:
    assert embed_texts([]) == []


def test_embed_texts_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub OpenAI client with deterministic embeddings.
    class FakeClient:
        class embeddings:  # noqa: N801
            @staticmethod
            def create(model: str, input: list[str]) -> Any:
                # Each embedding must be a list[float]
                return SimpleNamespace(data=[SimpleNamespace(embedding=[float(i)]) for i, _ in enumerate(input)])

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", lambda api_key=None: FakeClient())

    out = embed_texts(["a", "b"])
    assert out == [[0.0], [1.0]]


def test_embed_texts_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    def fake_sleep(s: float) -> None:
        sleeps.append(s)

    class FakeClient:
        class embeddings:  # noqa: N801
            calls = 0

            @staticmethod
            def create(model: str, input: list[str]) -> Any:
                FakeClient.embeddings.calls += 1
                if FakeClient.embeddings.calls == 1:
                    raise RuntimeError("transient")
                return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1]) for _ in input])

    import openai as openai_mod
    monkeypatch.setattr(openai_mod, "OpenAI", lambda api_key=None: FakeClient())

    import podcast_search.indexing.embeddings as embeddings_mod
    monkeypatch.setattr(embeddings_mod.time, "sleep", fake_sleep)

    out = embed_texts(["x", "y"], max_retries=3)
    assert out == [[0.1], [0.1]]
    assert sleeps  # ensures retry path executed


def test_plan_query_text_fallback_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert plan_query_text("hello") == "hello"


def test_plan_query_text_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeChat:
        class completions:  # noqa: N801
            @staticmethod
            def create(model: str, messages: list[dict[str, str]], temperature: float, response_format: Any) -> Any:
                payload = {
                    "query_text": "structured query text",
                    "filters": [],
                }
                # Put JSON inside extra text to cover `{...}` extraction.
                content = f"prefix\\n{payload}\\nsuffix"
                # Python dict -> string uses single quotes; json.loads would fail.
                # So make content valid JSON.
                import json

                content = f"prefix\\n{json.dumps(payload)}\\nsuffix"
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = FakeChat()

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", FakeOpenAI)

    out = plan_query_text("find trump mentions")
    assert out == "structured query text"


def test_plan_query_text_falls_back_when_query_text_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeChat:
        class completions:  # noqa: N801
            @staticmethod
            def create(model: str, messages: list[dict[str, str]], temperature: float, response_format: Any) -> Any:
                import json

                payload = {"filters": []}  # no query_text
                content = f"prefix\\n{json.dumps(payload)}\\nsuffix"
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = FakeChat()

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", FakeOpenAI)

    # If query_text is missing/invalid, planner must fall back to raw user query.
    out = plan_query_text("raw query should win")
    assert out == "raw query should win"


def test_plan_query_text_returns_user_query_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            raise RuntimeError("boom")

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", FakeOpenAI)

    out = plan_query_text("query")
    assert out == "query"


def test_rss_extract_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    # Monkeypatch feedparser.parse so we fully control entry shapes.
    import podcast_search.ingest.rss_extract as rss_mod

    class FakeEntry(dict):
        # Provide `get` via dict, but also allow attribute fallbacks if needed.
        pass

    def fake_parse(_xml: str) -> Any:
        entries = [
            # Has title + summary + description + link + guid + published.
            FakeEntry(
                {
                    "title": "T1",
                    "published": "2020-01-01",
                    "link": "http://ep1",
                    "guid": "g1",
                    "summary": "sum1",
                    "description": "desc1",
                    "content": [{"value": "encoded1"}],
                }
            ),
            # No summary/description/content -> fallback to title only.
            FakeEntry({"title": "T2", "link": "http://ep2", "guid": "g2"}),
        ]

        # RSS parser object has `entries` attribute.
        return SimpleNamespace(entries=entries)

    import feedparser as feedparser_mod
    monkeypatch.setattr(feedparser_mod, "parse", fake_parse)

    items = extract_episode_items("<rss/>", episode_limit=10)
    assert len(items) == 2
    assert items[0].episode_id == "g1"
    assert "sum1" in items[0].text
    assert "desc1" in items[0].text
    assert "encoded1" in items[0].text
    assert items[0].published_at == "2020-01-01"
    assert items[1].episode_id == "g2"
    assert items[1].text.strip() == "T2"


def test_discover_related_feed_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    import feedparser as feedparser_mod

    def fake_parse(_xml: str) -> Any:
        return SimpleNamespace(
            feed=SimpleNamespace(
                links=[
                    {"href": "http://alt1"},
                    SimpleNamespace(href="http://alt2"),
                    {"nope": "x"},
                ]
            )
        )

    monkeypatch.setattr(feedparser_mod, "parse", fake_parse)
    urls = discover_related_feed_urls("<rss/>")
    assert urls == ["http://alt1", "http://alt2"]

