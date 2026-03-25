from __future__ import annotations

from typing import Any

from app.config import settings


def setup_isolated_storage(monkeypatch: Any, tmp_path: Any) -> None:
    # Point storage paths at per-test temporary directories.
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chromadb"))
    monkeypatch.setattr(settings, "registry_path", str(tmp_path / "feed_registry.json"))


def fake_embed_texts_factory(call_counter: dict[str, int] | None = None):
    # Return a deterministic embedder for offline and unit/integration tests.
    def _fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        if call_counter is not None:
            call_counter["embed_texts"] += 1
        return [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in texts]

    return _fake_embed_texts

