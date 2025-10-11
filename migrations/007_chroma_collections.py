#!/usr/bin/env python3
"""
Bootstrap Chroma collections used by Agentic Memories.
Run this against the configured CHROMA_HOST/CHROMA_PORT.
"""
import os
from chromadb import HttpClient


def _standard_collection_name() -> str:
    tenant = os.getenv("CHROMA_TENANT", "agentic-memories")
    db = os.getenv("CHROMA_DATABASE", "memories")
    return f"{tenant}:{db}:memories"


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    client = HttpClient(host=host, port=port)
    name = _standard_collection_name()
    existing = [c.name for c in client.list_collections()]
    if name not in existing:
        client.create_collection(
            name=name,
            metadata={
                "distance": "cosine",
                "dimension": 3072,
                "description": "Agentic Memories embeddings"
            },
        )
        print(f"created collection: {name}")
    else:
        print(f"collection exists: {name}")


if __name__ == "__main__":
    main()


