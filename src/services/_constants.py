"""Shared constants for service-layer modules.

This module exists to provide a single source of truth for constants that
need to be imported by multiple service-layer modules without creating
circular imports between them.

Cross-references:
- ``SYSTEM_MANAGED_FIELDS`` is consumed by:
  * ``src/routers/memories.py`` PATCH handler (AC8 router-level guard)
  * ``src/services/storage.py`` ``update_chroma_record`` (AC20 storage-level guard)
  * ``src/services/retrieval.py`` ``metadata_filter`` validator (X.2 AC4)
  Any addition here MUST be reflected in ``_build_metadata`` in
  ``src/services/storage.py`` (the function that authoritatively writes these
  fields on ingest).
"""

from __future__ import annotations

# Fields that the system manages internally and that callers MUST NOT be able
# to set, override, or delete via user-facing APIs (PATCH metadata, retrieve
# metadata_filter, etc.). Defense-in-depth: enforced at both the router layer
# (AC8) and the storage layer (AC20).
SYSTEM_MANAGED_FIELDS: frozenset[str] = frozenset(
    {
        "user_id",
        "layer",
        "type",
        "ttl_epoch",
        "timestamp",
        "content_hash",
        "stored_in_episodic",
        "stored_in_emotional",
        "stored_in_procedural",
        "typed_table_id",
    }
)
