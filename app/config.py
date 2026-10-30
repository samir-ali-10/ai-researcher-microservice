from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_base_url: str = ""  # e.g. https://openrouter.ai/api/v1 for OpenRouter keys
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # local = FastEmbed (recommended with free OpenRouter keys); openai = remote embeddings API
    embedding_provider: str = "local"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chroma")
    chroma_collection: str = "knowledge_base"
    top_k: int = 4
    chunk_size: int = 500
    chunk_overlap: int = 50

    knowledge_base_path: str = str(PROJECT_ROOT / "knowledge_base.md")

    mcp_server_url: str = "http://127.0.0.1:8001/mcp"
    semantic_cache_ttl_seconds: int = 3600
    semantic_cache_enabled: bool = True

    # KB sufficiency: Chroma returns a distance score (lower = closer).
    # If the best chunk is farther than this, treat KB as insufficient → web search.
    kb_max_distance: float = 1.2
    # Also require at least this many query tokens to appear in retrieved text.
    kb_min_token_overlap: int = 1

    # Milestone 1 demo: short sleep so PENDING vs SUCCESS is observable.
    research_mock_sleep_seconds: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
