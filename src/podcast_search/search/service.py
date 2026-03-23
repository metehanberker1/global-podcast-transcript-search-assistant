from __future__ import annotations

import time
from typing import Any

from app.config import settings
from podcast_search.indexing.chroma_store import query_collection
from podcast_search.indexing.embeddings import embed_texts
from podcast_search.indexing.index_handle_cache import get_index_handle
from podcast_search.models import SearchHit
from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.search.query_planner import plan_query_text
from podcast_search.sharding.router import Router


def search(conn: Any, *, query: str, k: int) -> list[SearchHit]:
    """Search snippets in the most recently ingested feed only."""

    _ = conn
    started = time.perf_counter()

    registry = FeedRegistry()
    last_feed_id = registry.get_most_recent_feed_id()
    if not last_feed_id:
        raise RuntimeError("No ingested feed found. Please ingest a feed first.")

    entry = registry.get_entry_for_feed_id(last_feed_id)
    if entry is None:
        raise RuntimeError("Most recently ingested feed is missing from the registry.")

    index_handle = get_index_handle(entry.normalized_url, entry=entry)
    router = Router()
    owner = router.get_owner(entry.feed_id)
    from podcast_search.metrics.service import record_shard_owner_last

    record_shard_owner_last(owner)

    query_text = plan_query_text(query)
    query_embedding = embed_texts([query_text])
    if not query_embedding:
        return []
    embedding = query_embedding[0]

    started_chroma = time.perf_counter()
    hits = query_collection(
        collection_name=index_handle.collection_name,
        query_embedding=embedding,
        k=k,
    )
    from podcast_search.metrics.service import record_chroma_query_duration_ms_last

    record_chroma_query_duration_ms_last(int((time.perf_counter() - started_chroma) * 1000))

    duration_ms = int((time.perf_counter() - started) * 1000)
    from podcast_search.metrics.service import record_search

    record_search(duration_ms=duration_ms, hit_count=len(hits))
    # Optional: clamp to model constraints if needed.
    return hits

