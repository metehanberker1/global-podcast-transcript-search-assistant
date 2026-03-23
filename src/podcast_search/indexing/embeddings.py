from __future__ import annotations

import time
from typing import Sequence

from app.config import settings


def embed_texts(texts: Sequence[str], *, max_retries: int = 3) -> list[list[float]]:
    """Embed text chunks using OpenAI embeddings."""

    if not texts:
        return []

    if not settings.openai_api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY (set it in .env or provide it as environment variable)."
        )

    # Import inside so tests that monkeypatch this function don't need openai installed.
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.embedding_model

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.embeddings.create(model=model, input=list(texts))
            # OpenAI returns data in order of inputs.
            return [d.embedding for d in resp.data]
        except Exception as exc:  # pragma: no cover (real API path)
            last_exc = exc
            sleep_s = 1.0 * (attempt + 1)
            time.sleep(sleep_s)

    raise RuntimeError(f"Embedding failed after {max_retries} attempts: {last_exc}")

