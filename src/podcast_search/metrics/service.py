from __future__ import annotations

from podcast_search.models import MetricsSnapshot

# In-memory counters for process-local metrics snapshots.
_INGEST_DURATION_MS_LAST: int = 0
_SEARCH_DURATION_MS_LAST: int = 0
_INGEST_REQUESTS_TOTAL: int = 0
_SEARCH_REQUESTS_TOTAL: int = 0
_LAST_INGEST_EPISODE_COUNT: int = 0
_LAST_INGEST_CHUNK_COUNT: int = 0
_LAST_SEARCH_HIT_COUNT: int = 0
_CHROMA_QUERY_DURATION_MS_LAST: int = 0
_CACHE_HITS_TOTAL: int = 0
_CACHE_MISSES_TOTAL: int = 0
_SHARD_OWNER_LAST: str | None = None


def record_ingest(*, duration_ms: int | None = None, episode_count: int | None = None, chunk_count: int | None = None) -> None:
    global _INGEST_DURATION_MS_LAST, _INGEST_REQUESTS_TOTAL, _LAST_INGEST_EPISODE_COUNT, _LAST_INGEST_CHUNK_COUNT
    if duration_ms is not None:
        _INGEST_DURATION_MS_LAST = int(duration_ms)
    _INGEST_REQUESTS_TOTAL += 1
    if episode_count is not None:
        _LAST_INGEST_EPISODE_COUNT = int(episode_count)
    if chunk_count is not None:
        _LAST_INGEST_CHUNK_COUNT = int(chunk_count)


def record_search(*, duration_ms: int, hit_count: int) -> None:
    global _SEARCH_DURATION_MS_LAST, _SEARCH_REQUESTS_TOTAL
    _SEARCH_DURATION_MS_LAST = int(duration_ms)
    _SEARCH_REQUESTS_TOTAL += 1
    global _LAST_SEARCH_HIT_COUNT
    _LAST_SEARCH_HIT_COUNT = int(hit_count)


def record_chroma_query_duration_ms_last(duration_ms: int) -> None:
    global _CHROMA_QUERY_DURATION_MS_LAST
    _CHROMA_QUERY_DURATION_MS_LAST = int(duration_ms)


def record_cache_hit() -> None:
    global _CACHE_HITS_TOTAL
    _CACHE_HITS_TOTAL += 1


def record_cache_miss() -> None:
    global _CACHE_MISSES_TOTAL
    _CACHE_MISSES_TOTAL += 1


def record_shard_owner_last(owner: str) -> None:
    global _SHARD_OWNER_LAST
    _SHARD_OWNER_LAST = owner


def build_metrics_snapshot() -> MetricsSnapshot:
    # Snapshot reads the latest values without resetting counters.
    snap = MetricsSnapshot(
        ingest_episode_count=_LAST_INGEST_EPISODE_COUNT,
        chunk_index_count=_LAST_INGEST_CHUNK_COUNT,
        search_hit_count=_LAST_SEARCH_HIT_COUNT,
        ingest_duration_ms_last=_INGEST_DURATION_MS_LAST,
        search_duration_ms_last=_SEARCH_DURATION_MS_LAST,
        chroma_query_duration_ms_last=_CHROMA_QUERY_DURATION_MS_LAST,
        cache_hits_total=_CACHE_HITS_TOTAL,
        cache_misses_total=_CACHE_MISSES_TOTAL,
        shard_owner_last=_SHARD_OWNER_LAST,
    )
    return snap

