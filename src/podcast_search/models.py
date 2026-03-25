from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeedRegistryEntry(BaseModel):
    feed_id: str
    original_url: str
    normalized_url: str
    related_urls: list[str] = Field(default_factory=list)
    collection_name: str
    last_indexed_at: datetime | None = None
    episode_count: int | None = None
    chunk_count: int | None = None
    last_error: str | None = None


class SearchHit(BaseModel):
    episode_title: str
    excerpt: str
    score: float = Field(ge=0.0)

    # Optional fields used by API contracts and result rendering.
    episode_id: str | None = None
    published_at: str | None = None
    source_url: str | None = None


class IngestResult(BaseModel):
    episode_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class MetricsSnapshot(BaseModel):
    ingest_episode_count: int = Field(default=0, ge=0)
    chunk_index_count: int = Field(default=0, ge=0)
    search_hit_count: int = Field(default=0, ge=0)

    ingest_duration_ms_last: int = Field(default=0, ge=0)
    search_duration_ms_last: int = Field(default=0, ge=0)

    chroma_query_duration_ms_last: int = Field(default=0, ge=0)
    cache_hits_total: int = Field(default=0, ge=0)
    cache_misses_total: int = Field(default=0, ge=0)
    shard_owner_last: str | None = None

