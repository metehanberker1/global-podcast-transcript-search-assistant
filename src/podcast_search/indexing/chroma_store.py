from __future__ import annotations

import math
from typing import Any

import chromadb

from app.config import settings
from podcast_search.models import SearchHit


def _nodes_count() -> int:
    nodes = [n.strip() for n in settings.shard_nodes.split(",") if n.strip()]
    return max(len(nodes), 1)


def _resolve_persist_dir(*, owner: str | None = None, persist_dir: str | None = None) -> str:
    # Use one shared directory for single-node mode.
    # In multi-node mode, store each shard under `<base>/<owner>/`.
    if persist_dir:
        return persist_dir

    if _nodes_count() <= 1:
        return settings.chroma_persist_dir

    if not owner:
        raise ValueError("owner is required when using multi-node shard storage")

    import os

    return os.path.join(settings.chroma_persist_dir, owner)


def _get_client(*, owner: str | None = None, persist_dir: str | None = None) -> chromadb.PersistentClient:
    resolved = _resolve_persist_dir(owner=owner, persist_dir=persist_dir)
    return chromadb.PersistentClient(path=resolved)


def _get_collection(client: chromadb.PersistentClient, collection_name: str) -> chromadb.Collection:
    # New collections default to cosine distance.
    # Existing collections keep their stored metric metadata.
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def _score_from_distance(distance: float | None, *, space: str = "cosine") -> float:
    if distance is None:
        return 0.0

    dist = float(distance)
    metric = (space or "cosine").lower()

    if metric == "cosine":
        # Convert cosine distance to similarity-like score.
        score = 1.0 - dist
    else:
        # Keep non-cosine metrics in a bounded, readable score range.
        score = 1.0 / (1.0 + max(dist, 0.0))

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
    persist_dir: str | None = None,
    owner: str | None = None,
) -> None:
    if not chunk_ids:
        return

    client = _get_client(owner=owner, persist_dir=persist_dir)
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
    persist_dir: str | None = None,
    owner: str | None = None,
) -> list[SearchHit]:
    client = _get_client(owner=owner, persist_dir=persist_dir)
    collection = _get_collection(client, collection_name)

    res = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(int(k), 1),
        include=["documents", "metadatas", "distances"],
    )

    hits: list[SearchHit] = []
    space = str((getattr(collection, "metadata", None) or {}).get("hnsw:space", "cosine"))
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        episode_title = (meta or {}).get("episode_title") or "Unknown episode"
        hits.append(
            SearchHit(
                episode_title=str(episode_title),
                excerpt=str(doc or ""),
                score=_score_from_distance(dist, space=space),
                episode_id=(meta or {}).get("episode_id"),
                published_at=(meta or {}).get("published_at"),
                source_url=(meta or {}).get("source_url"),
            )
        )

    return hits

