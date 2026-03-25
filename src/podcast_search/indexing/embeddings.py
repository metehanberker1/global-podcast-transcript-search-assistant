from __future__ import annotations

import time
from typing import Sequence

from app.config import settings


def embed_texts(texts: Sequence[str], *, max_retries: int = 3) -> list[list[float]]:
    """Embed text chunks using OpenAI embeddings."""

    if not texts:
        return []

    if not settings.openai_api_key:
        # Optional deterministic fallback for local/offline runs.
        # Enable with `PODCAST_SEARCH_DUMMY_EMBEDDINGS=1`.
        import os

        if os.getenv("PODCAST_SEARCH_DUMMY_EMBEDDINGS") == "1":
            out: list[list[float]] = []
            for t in texts:
                h = sum(ord(c) for c in (t or "")) % 1000
                out.append([float(h), float(h + 1), float(h + 2), float(h + 3), float(h + 4)])
            return out

        raise RuntimeError(
            "Missing OPENAI_API_KEY (set it in .env or provide it as environment variable)."
        )

    # Import lazily so environments that never call this path can still run.
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.embedding_model

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.embeddings.create(model=model, input=list(texts))
            # Embeddings are returned in the same order as input texts.
            return [d.embedding for d in resp.data]
        except Exception as exc:  # pragma: no cover (real API path)
            last_exc = exc
            sleep_s = 1.0 * (attempt + 1)
            time.sleep(sleep_s)

    raise RuntimeError(f"Embedding failed after {max_retries} attempts: {last_exc}")

