"""LLM / embedding helpers (OpenAI-compatible, including OpenRouter)."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings


def resolve_base_url() -> str | None:
    settings = get_settings()
    if settings.openai_base_url:
        return settings.openai_base_url.rstrip("/")
    # OpenRouter keys look like sk-or-v1-...
    if settings.openai_api_key.startswith("sk-or-"):
        return "https://openrouter.ai/api/v1"
    return None


def get_chat_model(*, temperature: float = 0) -> ChatOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required. For OpenRouter, use an sk-or-v1 key and "
            "set OPENAI_BASE_URL=https://openrouter.ai/api/v1"
        )
    kwargs: dict = {
        "api_key": settings.openai_api_key,
        "model": settings.openai_model,
        "temperature": temperature,
    }
    base_url = resolve_base_url()
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def get_embeddings() -> Embeddings:
    """Return embeddings.

    - embedding_provider=local → FastEmbed (no cloud key needed for RAG)
    - embedding_provider=openai → OpenAI-compatible embeddings API
      (OpenAI or OpenRouter, depending on OPENAI_BASE_URL / key)
    """
    settings = get_settings()
    if settings.embedding_provider == "local":
        from langchain_community.embeddings import FastEmbedEmbeddings

        return FastEmbedEmbeddings(model_name=settings.local_embedding_model)

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for openai embeddings, or set "
            "EMBEDDING_PROVIDER=local"
        )

    kwargs: dict = {
        "api_key": settings.openai_api_key,
        "model": settings.openai_embedding_model,
    }
    base_url = resolve_base_url()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAIEmbeddings(**kwargs)
