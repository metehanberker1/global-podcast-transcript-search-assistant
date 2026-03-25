from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl

# Ensure `src/` imports work when starting from repository root.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from app.http import Http

from podcast_search.ingest.service import ingest_feed as ingest_feed_service
from podcast_search.metrics.metrics_snapshot import build_snapshot
from podcast_search.models import MetricsSnapshot, SearchHit
from podcast_search.registry.feed_registry import FeedRegistry
from podcast_search.registry.normalize_url import (
    feed_id_from_normalized_url,
    normalize_url,
)
from podcast_search.search.service import search as search_service

app = FastAPI(title="Podcast Search Assistant API")


class IngestFeedRequest(BaseModel):
    feed_url: HttpUrl
    episode_limit: int = Field(default=200, ge=1, le=1000)


class IngestFeedResponse(BaseModel):
    feed_id: str
    normalized_url: str
    episode_count: int
    chunk_count: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResponse(BaseModel):
    feed_id: str | None = None
    results: list[SearchHit]


@app.get("/api/metrics", response_model=MetricsSnapshot)
def metrics() -> MetricsSnapshot:
    return build_snapshot()


@app.post("/api/feeds", response_model=IngestFeedResponse, status_code=201)
def ingest_feed(req: IngestFeedRequest) -> IngestFeedResponse:
    registry = FeedRegistry()
    feed_url_str = str(req.feed_url)

    # Short-circuit duplicate ingests before fetching RSS content.
    lookup = registry.find_by_input_url(feed_url_str)
    if lookup.entry is not None and lookup.entry.last_indexed_at is not None:
        entry = lookup.entry
        return JSONResponse(
            status_code=409,
            content={
                "feed_id": entry.feed_id,
                "normalized_url": entry.normalized_url,
                "episode_count": int(entry.episode_count or 0),
                "chunk_count": int(entry.chunk_count or 0),
            },
        )

    http = Http()
    try:
        try:
            feed_xml = http.get_text(feed_url_str)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to fetch RSS feed: {exc}") from exc
    finally:
        http.close()

    try:
        res = ingest_feed_service(
            None,
            feed_url=feed_url_str,
            feed_xml=feed_xml,
            http=http,
            episode_limit=req.episode_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    normalized = normalize_url(feed_url_str)
    feed_id = feed_id_from_normalized_url(normalized)
    return IngestFeedResponse(
        feed_id=feed_id,
        normalized_url=normalized,
        episode_count=res.episode_count,
        chunk_count=res.chunk_count,
    )


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    registry = FeedRegistry()
    last_feed_id = registry.get_most_recent_feed_id()
    if not last_feed_id:
        raise HTTPException(status_code=400, detail="No ingested feed found. Please ingest a feed first.")

    try:
        hits = search_service(None, query=req.query, k=req.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SearchResponse(feed_id=last_feed_id, results=hits)

