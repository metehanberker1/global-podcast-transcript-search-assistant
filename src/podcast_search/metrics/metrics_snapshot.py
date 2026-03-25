from __future__ import annotations

from podcast_search.metrics.service import build_metrics_snapshot as _build


def build_snapshot():
    # Keep a small boundary so callers depend on one stable snapshot function.
    return _build()

