#!/usr/bin/env python3
"""
Rollback Chroma collections - DELETE the memories collection.
WARNING: This will delete all vector embeddings!
"""
import os
from chromadb import HttpClient


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    client = HttpClient(host=host, port=port)
    
    # Delete default collection
    name = "memories_3072"
    
    try:
        client.delete_collection(name=name)
        print(f"✅ Deleted collection: {name}")
    except Exception as e:
        print(f"⚠️  Collection may not exist or failed to delete: {name} - {e}")


if __name__ == "__main__":
    main()

