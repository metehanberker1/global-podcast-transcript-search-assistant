from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

# Make `src/` importable when running from repo root (e.g. uvicorn).
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from podcast_search.metrics.metrics_snapshot import build_snapshot  # noqa: E402
from podcast_search.models import MetricsSnapshot  # noqa: E402

app = FastAPI(title="Podcast Search Assistant API")


@app.get("/api/metrics", response_model=MetricsSnapshot)
def metrics() -> MetricsSnapshot:
    return build_snapshot()

