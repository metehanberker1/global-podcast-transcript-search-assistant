from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from podcast_search.indexing import chroma_store
from podcast_search.indexing.chunking import chunk_text
from podcast_search.indexing.embeddings import embed_texts


def test_chroma_score_branches() -> None:
    assert chroma_store._score_from_distance(None) == 0.0
    assert chroma_store._score_from_distance(0.0) == 1.0
    assert chroma_store._score_from_distance(0.5, space="cosine") == 0.5
    assert chroma_store._score_from_distance(2.0, space="l2") == pytest.approx(1.0 / 3.0)

    # Invalid numeric values should map to a safe score.
    assert chroma_store._score_from_distance(float("nan")) == 0.0
    assert chroma_store._score_from_distance(float("-inf")) == 0.0


def test_chroma_upsert_empty_chunk_ids() -> None:
    # Empty upsert input should return without client calls.
    chroma_store.upsert_chunks(
        collection_name="feed_x",
        chunk_ids=[],
        documents=[],
        metadatas=[],
        embeddings=[],
    )


def test_query_collection_uses_collection_metric_space(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCollection:
        def __init__(self, space: str) -> None:
            self.metadata = {"hnsw:space": space}

        def query(self, query_embeddings, n_results, include):
            _ = (query_embeddings, n_results, include)
            return {
                "documents": [["chunk"]],
                "metadatas": [[{"episode_title": "Ep"}]],
                "distances": [[2.0]],
            }

    monkeypatch.setattr(chroma_store, "_get_client", lambda **kwargs: object())
    monkeypatch.setattr(chroma_store, "_get_collection", lambda client, name: FakeCollection("l2"))

    hits_l2 = chroma_store.query_collection(
        collection_name="feed_x",
        query_embedding=[0.1, 0.2],
        k=1,
    )
    assert hits_l2
    assert hits_l2[0].score == pytest.approx(1.0 / 3.0)

    monkeypatch.setattr(chroma_store, "_get_collection", lambda client, name: FakeCollection("cosine"))
    hits_cos = chroma_store.query_collection(
        collection_name="feed_x",
        query_embedding=[0.1, 0.2],
        k=1,
    )
    assert hits_cos
    assert hits_cos[0].score == pytest.approx(0.0)


def test_chunk_text_overlap_correctness() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunk_text(text, chunk_size=10, overlap=3)
    assert chunks
    assert len(chunks[0]) <= 10
    if len(chunks) >= 2:
        ov = 3
        assert chunks[0][-ov:] == chunks[1][:ov]


def test_embed_texts_empty_short_circuit() -> None:
    assert embed_texts([]) == []


def test_embed_texts_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub OpenAI client to return deterministic vectors.
    class FakeClient:
        class embeddings:
            @staticmethod
            def create(model: str, input: list[str]) -> Any:
                # API response shape mirrors real embedding payloads.
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
        class embeddings:
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
    assert sleeps  # retry path executed



