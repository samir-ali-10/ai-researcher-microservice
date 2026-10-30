"""Ingest context files into the vector database using LangChain loaders and chunking."""

from __future__ import annotations

import argparse
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.rag.store import get_vectorstore


def ingest_knowledge_base(
    path: str | Path | None = None,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> int:
    settings = get_settings()
    source = Path(path or settings.knowledge_base_path)
    if not source.exists():
        raise FileNotFoundError(f"Knowledge base not found: {source}")

    loader = TextLoader(str(source), encoding="utf-8")
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        separators=["\n### ", "\n## ", "\n# ", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["source"] = source.name

    vectorstore = get_vectorstore(create_if_missing=True)
    # Replace collection contents so re-ingestion is idempotent for local demos.
    try:
        vectorstore.delete_collection()
    except Exception:
        pass
    vectorstore = get_vectorstore(create_if_missing=True)
    vectorstore.add_documents(chunks)
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk and embed context files into Chroma.")
    parser.add_argument(
        "--path",
        default=None,
        help="Path to a markdown/text knowledge file (defaults to knowledge_base.md).",
    )
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--chunk-overlap", type=int, default=None)
    args = parser.parse_args()

    count = ingest_knowledge_base(
        args.path,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Ingested {count} chunks into Chroma.")


if __name__ == "__main__":
    main()
