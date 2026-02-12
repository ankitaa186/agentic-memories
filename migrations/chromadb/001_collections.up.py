#!/usr/bin/env python3
"""
Bootstrap Chroma collections used by Agentic Memories.
Run this against the configured CHROMA_HOST/CHROMA_PORT.

Creates: memories_3072 (default collection for 3072-dim embeddings)

For v2-only servers, this uses direct REST API calls to avoid client validation issues.
"""

import os
import requests


def main() -> None:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    tenant = os.getenv("CHROMA_TENANT", "agentic-memories")
    database = os.getenv("CHROMA_DATABASE", "memories")

    base_url = f"http://{host}:{port}/api/v2"
    headers = {"Content-Type": "application/json"}

    # Check if v2 API is available
    try:
        resp = requests.get(f"{base_url}/heartbeat", timeout=5)
        if resp.status_code != 200:
            print("❌ Chroma v2 API not available; this migration requires v2")
            return
    except Exception as e:
        print(f"❌ Could not connect to Chroma: {e}")
        return

    # Create tenant (idempotent)
    try:
        resp = requests.post(
            f"{base_url}/tenants", json={"name": tenant}, headers=headers, timeout=5
        )
        if resp.status_code in (200, 201, 409):  # 409 = already exists
            print(f"✅ Ensured tenant exists: {tenant}")
        else:
            print(f"⚠️  Tenant creation returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"⚠️  Could not create tenant {tenant}: {e}")

    # Create database (idempotent)
    try:
        resp = requests.post(
            f"{base_url}/tenants/{tenant}/databases",
            json={"name": database},
            headers=headers,
            timeout=5,
        )
        if resp.status_code in (200, 201, 409):
            print(f"✅ Ensured database exists: {tenant}/{database}")
        else:
            print(f"⚠️  Database creation returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"⚠️  Could not create database {database}: {e}")

    # Create collection using v2 API
    collection_name = "memories_3072"
    collection_endpoint = (
        f"{base_url}/tenants/{tenant}/databases/{database}/collections"
    )

    # Check if collection exists
    try:
        resp = requests.get(collection_endpoint, headers=headers, timeout=5)
        if resp.status_code == 200:
            existing_collections = resp.json()
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
        resp = requests.post(
            collection_endpoint, json=payload, headers=headers, timeout=5
        )
        if resp.status_code in (200, 201):
            print(f"✅ Created collection: {collection_name}")
        else:
            print(f"❌ Collection creation failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ Could not create collection: {e}")


if __name__ == "__main__":
    main()
