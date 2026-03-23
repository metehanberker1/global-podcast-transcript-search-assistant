from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Loaded from `.env`. Default to empty string so unit tests can run
    # without requiring a real API key unless embedding/planning is invoked.
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    chunk_size: int = Field(default=1500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")

    chroma_persist_dir: str = Field(default="./chromadb", alias="CHROMA_PERSIST_DIR")
    registry_path: str = Field(default="./data/feed_registry.json", alias="REGISTRY_PATH")

    query_planner_model: str = Field(default="gpt-4o-mini", alias="QUERY_PLANNER_MODEL")

    # Streamlit calls this name: `settings.ingest_episode_limit`
    ingest_episode_limit: int = Field(default=50, alias="INGEST_EPISODE_LIMIT")

    # `streamlit_app.py` passes `settings.database_url` into `get_db_config()`.
    # For this MVP, we don't use a real relational DB; the field exists for wiring compatibility.
    database_url: str = Field(default="local-mvp", alias="DATABASE_URL")

    # Sharding / routing (Phase 6 MVP)
    shard_nodes: str = Field(default="local", alias="SHARD_NODES")
    local_node_id: str = Field(default="local", alias="LOCAL_NODE_ID")
    consistent_hash_virtual_nodes: int = Field(default=100, alias="CONSISTENT_HASH_VIRTUAL_NODES")


settings = Settings()  # Loaded once at process start.

