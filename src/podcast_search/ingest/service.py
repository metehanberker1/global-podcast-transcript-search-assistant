from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from app.config import settings
from podcast_search.indexing.chroma_store import upsert_chunks
from podcast_search.indexing.chunking import chunk_text
from podcast_search.indexing.embeddings import embed_texts
from podcast_search.indexing.index_handle_cache import update_cache_for_entry
from podcast_search.ingest.rss_extract import discover_related_feed_urls, extract_episode_items
from podcast_search.models import IngestResult
from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url
from podcast_search.sharding.router import Router


def ingest_feed(
    conn: Any,
    *,
    feed_url: str,
    feed_xml: str,
    http: Any,
    episode_limit: int,
) -> IngestResult:
    """Ingest a feed once (ingest-once) and persist embeddings to Chroma on disk."""

    _ = (conn, http)

    started = time.perf_counter()
    registry = FeedRegistry()

    normalized = normalize_url(feed_url)
    feed_id = feed_id_from_normalized_url(normalized)
    router = Router()
    owner = router.get_owner(feed_id)
    from podcast_search.metrics.service import record_shard_owner_last

    record_shard_owner_last(owner)

    existing_lookup = registry.find_by_input_url(feed_url)
    if existing_lookup.entry is not None and existing_lookup.entry.last_indexed_at is not None:
        # Ingest-once: do not re-embed after a successful ingest.
        entry = existing_lookup.entry
        duration_ms = int((time.perf_counter() - started) * 1000)
        from podcast_search.metrics.service import record_ingest

        record_ingest(duration_ms=duration_ms)
        return IngestResult(
            episode_count=int(entry.episode_count or 0),
            chunk_count=int(entry.chunk_count or 0),
        )

    related_urls = discover_related_feed_urls(feed_xml)
    episodes = extract_episode_items(feed_xml, episode_limit=episode_limit)

    # Build deterministic chunk IDs and metadata.
    chunk_ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    texts_for_embedding: list[str] = []

    for ep in episodes:
        for i, chunk in enumerate(
            chunk_text(ep.text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
        ):
            chunk_id = f"{feed_id}:{ep.episode_id}:{i}"
            chunk_ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "feed_id": feed_id,
                    "episode_id": ep.episode_id,
                    "episode_title": ep.episode_title,
                    "published_at": ep.published_at,
                    "source_url": ep.source_url,
                }
            )
            texts_for_embedding.append(chunk)

    embeddings = embed_texts(texts_for_embedding) if texts_for_embedding else []

    collection_name = f"feed_{feed_id}"
    upsert_chunks(
        collection_name=collection_name,
        chunk_ids=chunk_ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    chunk_count = len(chunk_ids)
    episode_count = len(episodes)

    entry = registry.upsert_entry_after_ingest(
        feed_url=feed_url,
        parsed_related_urls=related_urls,
        episode_count=episode_count,
        chunk_count=chunk_count,
        last_error=None,
        now=datetime.utcnow(),
    )
    # Update cache immediately after successful ingest.
    update_cache_for_entry(entry)

    duration_ms = int((time.perf_counter() - started) * 1000)
    from podcast_search.metrics.service import record_ingest

    record_ingest(duration_ms=duration_ms, episode_count=episode_count, chunk_count=chunk_count)

    return IngestResult(episode_count=episode_count, chunk_count=chunk_count)

