from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class DbConfig:
    database_url: str
    chroma_persist_dir: str
    registry_path: str


class DbConnection:
    """Lightweight connection wrapper used by ingest/search service signatures."""

    def __init__(self, cfg: DbConfig) -> None:
        self.cfg = cfg

    def close(self) -> None:
        # Placeholder for parity with real connection interfaces.
        return None


def get_db_config(database_url: str) -> DbConfig:
    # Import lazily to avoid startup-time import cycles.
    from app.config import settings

    return DbConfig(
        database_url=database_url,
        chroma_persist_dir=settings.chroma_persist_dir,
        registry_path=settings.registry_path,
    )


def connect(cfg: DbConfig) -> DbConnection:
    return DbConnection(cfg)

