from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class DbConfig:
    database_url: str
    chroma_persist_dir: str
    registry_path: str


class DbConnection:
    """MVP connection handle.

    For this phase we don't need a real database; we keep a unified context
    object so ingest/search signatures match future implementations.
    """

    def __init__(self, cfg: DbConfig) -> None:
        self.cfg = cfg

    def close(self) -> None:
        # No external resources in Phase 1.
        return None


def get_db_config(database_url: str) -> DbConfig:
    # Import inside function to avoid import cycles during app startup.
    from app.config import settings

    return DbConfig(
        database_url=database_url,
        chroma_persist_dir=settings.chroma_persist_dir,
        registry_path=settings.registry_path,
    )


def connect(cfg: DbConfig) -> DbConnection:
    return DbConnection(cfg)

