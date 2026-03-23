from __future__ import annotations

import math
from typing import Any

import chromadb

from app.config import settings
from podcast_search.models import SearchHit


def _get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def _get_collection(client: chromadb.PersistentClient, collection_name: str) -> chromadb.Collection:
    return client.get_or_create_collection(name=collection_name)


def _score_from_distance(distance: float | None) -> float:
    if distance is None:
        return 0.0

    # Chroma commonly uses cosine distance. Convert to a score where higher is better.
    # For cosine distance: similarity = 1 - distance.
    score = 1.0 - float(distance)
    if math.isnan(score) or math.isinf(score):
        return 0.0
    return max(0.0, score)


def upsert_chunks(
    *,
    collection_name: str,
    chunk_ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    if not chunk_ids:
        return

    client = _get_client()
    collection = _get_collection(client, collection_name)

    collection.upsert(
        ids=chunk_ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )


def query_collection(
    *,
    collection_name: str,
    query_embedding: list[float],
    k: int,
) -> list[SearchHit]:
    client = _get_client()
    collection = _get_collection(client, collection_name)

    res = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(int(k), 1),
        include=["documents", "metadatas", "distances"],
    )

    hits: list[SearchHit] = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        episode_title = (meta or {}).get("episode_title") or "Unknown episode"
        hits.append(
            SearchHit(
                episode_title=str(episode_title),
                excerpt=str(doc or ""),
                score=_score_from_distance(dist),
                episode_id=(meta or {}).get("episode_id"),
                published_at=(meta or {}).get("published_at"),
                source_url=(meta or {}).get("source_url"),
            )
        )

    return hits

