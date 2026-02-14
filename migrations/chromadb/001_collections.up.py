#!/usr/bin/env python3
"""
Bootstrap Chroma collections used by Agentic Memories.
Run this against the configured CHROMA_HOST/CHROMA_PORT.

Creates: memories_3072 (default collection for 3072-dim embeddings)

For v2-only servers, this uses direct REST API calls to avoid client validation issues.
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

    base_url = f"http://{host}:{port}/api/v2"

    # Check if v2 API is available
    try:
        status, _ = _request(f"{base_url}/heartbeat")
        if status != 200:
            print("❌ Chroma v2 API not available; this migration requires v2")
            return
    except Exception as e:
        print(f"❌ Could not connect to Chroma: {e}")
        return

    # Create tenant (idempotent)
    try:
        status, body = _request(
            f"{base_url}/tenants", method="POST", data={"name": tenant}
        )
        if status in (200, 201, 409):  # 409 = already exists
            print(f"✅ Ensured tenant exists: {tenant}")
        else:
            print(f"⚠️  Tenant creation returned {status}: {body}")
    except Exception as e:
        print(f"⚠️  Could not create tenant {tenant}: {e}")

    # Create database (idempotent)
    try:
        status, body = _request(
            f"{base_url}/tenants/{tenant}/databases",
            method="POST",
            data={"name": database},
        )
        if status in (200, 201, 409):
            print(f"✅ Ensured database exists: {tenant}/{database}")
        else:
            print(f"⚠️  Database creation returned {status}: {body}")
    except Exception as e:
        print(f"⚠️  Could not create database {database}: {e}")

    # Create collection using v2 API
    collection_name = "memories_3072"
    collection_endpoint = (
        f"{base_url}/tenants/{tenant}/databases/{database}/collections"
    )

    # Check if collection exists
    try:
        status, body = _request(collection_endpoint)
        if status == 200:
            existing_collections = json.loads(body)
            exists = any(c.get("name") == collection_name for c in existing_collections)
            if exists:
                print(f"ℹ️  Collection already exists: {collection_name}")
                return
    except Exception as e:
        print(f"⚠️  Could not list collections: {e}")

    # Create collection
    try:
        payload = {
            "name": collection_name,
            "metadata": {
                "distance": "cosine",
                "dimension": 3072,
                "description": "Agentic Memories embeddings (text-embedding-3-large)",
                "created_by": "migration",
            },
        }
        status, body = _request(collection_endpoint, method="POST", data=payload)
        if status in (200, 201):
            print(f"✅ Created collection: {collection_name}")
        else:
            print(f"❌ Collection creation failed ({status}): {body}")
    except Exception as e:
        print(f"❌ Could not create collection: {e}")


if __name__ == "__main__":
    main()
