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

    # Read from `.env`; empty by default so local/offline runs can start
    # without external credentials until model-backed paths are used.
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    chunk_size: int = Field(default=1500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")

    chroma_persist_dir: str = Field(default="./chromadb", alias="CHROMA_PERSIST_DIR")
    registry_path: str = Field(default="./data/feed_registry.json", alias="REGISTRY_PATH")

    query_planner_model: str = Field(default="gpt-4o-mini", alias="QUERY_PLANNER_MODEL")

    # UI and API use this shared default for episode ingestion limits.
    ingest_episode_limit: int = Field(default=50, alias="INGEST_EPISODE_LIMIT")

    # Reserved for connection wiring, even though this app currently uses
    # local file-backed persistence for indexing/registry state.
    database_url: str = Field(default="local-mvp", alias="DATABASE_URL")

    # Sharding and routing configuration.
    shard_nodes: str = Field(default="local", alias="SHARD_NODES")
    local_node_id: str = Field(default="local", alias="LOCAL_NODE_ID")
    consistent_hash_virtual_nodes: int = Field(default=100, alias="CONSISTENT_HASH_VIRTUAL_NODES")

    # Base URL used by the UI when calling backend API endpoints.
    api_base_url: str = Field(default="http://127.0.0.1:8000", alias="API_BASE_URL")


settings = Settings()  # Initialized once per process.

