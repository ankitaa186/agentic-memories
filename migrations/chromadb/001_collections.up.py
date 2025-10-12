#!/usr/bin/env python3
"""
Bootstrap Chroma collections used by Agentic Memories.
Run this against the configured CHROMA_HOST/CHROMA_PORT.

Creates: memories_3072 (default collection for 3072-dim embeddings)
"""
import os
from chromadb import HttpClient


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    client = HttpClient(host=host, port=port)
    
    # Create default collection for 3072-dimension embeddings (text-embedding-3-large)
    # This matches the naming convention in src/services/retrieval.py
    name = "memories_3072"
    
    existing = [c.name for c in client.list_collections()]
    if name not in existing:
        client.create_collection(
            name=name,
            metadata={
                "distance": "cosine",
                "dimension": 3072,
                "description": "Agentic Memories embeddings (text-embedding-3-large)"
            },
        )
        print(f"✅ Created collection: {name}")
    else:
        print(f"ℹ️  Collection already exists: {name}")


if __name__ == "__main__":
    main()


