from __future__ import annotations

from podcast_search.metrics.service import build_metrics_snapshot as _build


def build_snapshot():
    # Keep a dedicated module boundary so Phase 6 tasks have a place to evolve
    # toward richer metric sources.
    return _build()

