#!/usr/bin/env python3
"""
Rollback Chroma collections - DELETE the memories collection.
WARNING: This will delete all vector embeddings!

For v2-only servers, this uses direct REST API calls.
"""
import os
import requests


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    tenant = os.getenv("CHROMA_TENANT", "agentic-memories")
    database = os.getenv("CHROMA_DATABASE", "memories")
    
    collection_name = "memories_3072"
    base_url = f"http://{host}:{port}/api/v2"
    headers = {"Content-Type": "application/json"}
    
    # Get collection ID
    try:
        collections_url = f"{base_url}/tenants/{tenant}/databases/{database}/collections"
        resp = requests.get(collections_url, headers=headers, timeout=5)
        if resp.status_code != 200:
            print(f"⚠️  Could not list collections: {resp.status_code}")
            return
        
        collections = resp.json()
        collection_id = None
        for c in collections:
            if c.get("name") == collection_name:
                collection_id = c.get("id")
                break
        
        if not collection_id:
            print(f"ℹ️  Collection {collection_name} does not exist (already deleted)")
            return
        
        # Delete collection
        delete_url = f"{base_url}/tenants/{tenant}/databases/{database}/collections/{collection_id}"
        resp = requests.delete(delete_url, headers=headers, timeout=5)
        if resp.status_code in (200, 204):
            print(f"✅ Deleted collection: {collection_name}")
        else:
            print(f"⚠️  Delete failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"⚠️  Could not delete collection: {e}")


if __name__ == "__main__":
    main()
