#!/usr/bin/env python3
"""
Rollback Chroma collections - DELETE the memories collection.
WARNING: This will delete all vector embeddings!

For v2-only servers, this uses direct REST API calls.
Uses only Python stdlib (no pip dependencies).
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional, Tuple


def _request(
    url: str, *, method: str = "GET", data: Optional[dict] = None, timeout: int = 5
) -> Tuple[int, str]:
    """Minimal HTTP helper using stdlib."""
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    tenant = os.getenv("CHROMA_TENANT", "agentic-memories")
    database = os.getenv("CHROMA_DATABASE", "memories")

    collection_name = "memories_3072"
    base_url = f"http://{host}:{port}/api/v2"

    # Get collection ID
    try:
        collections_url = (
            f"{base_url}/tenants/{tenant}/databases/{database}/collections"
        )
        status, body = _request(collections_url)
        if status != 200:
            print(f"⚠️  Could not list collections: {status}")
            return

        collections = json.loads(body)
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
        status, body = _request(delete_url, method="DELETE")
        if status in (200, 204):
            print(f"✅ Deleted collection: {collection_name}")
        else:
            print(f"⚠️  Delete failed ({status}): {body}")
    except Exception as e:
        print(f"⚠️  Could not delete collection: {e}")


if __name__ == "__main__":
    main()
