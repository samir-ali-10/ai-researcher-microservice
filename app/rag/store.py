from pathlib import Path

from langchain_community.vectorstores import Chroma

from app.config import get_settings
from app.llm import get_embeddings


def get_vectorstore(*, create_if_missing: bool = True) -> Chroma:
    settings = get_settings()
    persist_dir = Path(settings.chroma_persist_dir)
    if create_if_missing:
        persist_dir.mkdir(parents=True, exist_ok=True)

    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_dir),
    )
