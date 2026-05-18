#!/usr/bin/env python3
"""
Recompute profile completeness for every user (Story 3.1).

Story 3.1 expanded EXPECTED_PROFILE_FIELDS["health"] from 2 baseline fields
to 22. TOTAL_EXPECTED_FIELDS grew accordingly; every existing user's
user_profiles.completeness_pct row is now stale relative to the new
denominator. This script does a one-shot refresh.

Usage:
  python scripts/recompute_completeness.py              # apply to all users
  python scripts/recompute_completeness.py --dry-run    # report what would change

Connects via src.dependencies.timescale (reads DSN from env).

Idempotent — running it twice produces no further change beyond updating
the user_profiles.last_updated timestamp.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Set, Tuple

# Make the src/ package importable when invoking from repo root
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dependencies.timescale import (  # noqa: E402
    get_timescale_conn,
    release_timescale_conn,
)
from src.services.profile_storage import (  # noqa: E402
    EXPECTED_PROFILE_FIELDS,
    TOTAL_EXPECTED_FIELDS,
    COMPLETENESS_CACHE_KEY,
)
from src.dependencies.redis_client import get_redis_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("recompute_completeness")


def _load_all_populated_fields(cursor) -> Dict[str, Dict[str, Set[str]]]:
    """
    Bulk-load every (user_id, category, field_name) tuple from profile_fields
    in ONE query, grouped by user_id then category.

    Avoids the N+1 query pattern that would result from issuing one query per
    user during recompute. For thousands of users this is the difference
    between thousands of round-trips and a single fetch.
    """
    cursor.execute(
        """
        SELECT user_id, category, field_name
        FROM profile_fields
        ORDER BY user_id
        """
    )
    by_user: Dict[str, Dict[str, Set[str]]] = {}
    for row in cursor.fetchall():
        if isinstance(row, dict):
            user_id = row["user_id"]
            category = row["category"]
            field_name = row["field_name"]
        else:
            user_id, category, field_name = row
        if category not in EXPECTED_PROFILE_FIELDS:
            continue
        by_user.setdefault(user_id, {cat: set() for cat in EXPECTED_PROFILE_FIELDS})[
            category
        ].add(field_name)
    return by_user


def _compute_from_populated(populated: Dict[str, Set[str]]) -> Tuple[int, float]:
    """Pure-Python completeness math against an already-loaded populated map."""
    total_populated = 0
    for category, expected_fields in EXPECTED_PROFILE_FIELDS.items():
        total_populated += len(populated[category].intersection(set(expected_fields)))
    pct = (
        min(100.0, (total_populated / TOTAL_EXPECTED_FIELDS) * 100)
        if TOTAL_EXPECTED_FIELDS
        else 0.0
    )
    return total_populated, pct


def _invalidate_cache(user_id: str) -> None:
    try:
        redis_client = get_redis_client()
        if redis_client:
            redis_client.delete(COMPLETENESS_CACHE_KEY.format(user_id=user_id))
    except Exception as e:  # noqa: BLE001 — best-effort cache invalidation
        logger.warning("cache invalidation failed user_id=%s err=%s", user_id, e)


def recompute_all(dry_run: bool = False) -> None:
    conn = get_timescale_conn()
    cursor = conn.cursor()
    updated = 0
    unchanged = 0
    try:
        # One bulk fetch instead of N per-user queries — avoids the N+1 pattern.
        all_populated = _load_all_populated_fields(cursor)

        cursor.execute(
            "SELECT user_id, completeness_pct, populated_fields, total_fields "
            "FROM user_profiles ORDER BY user_id"
        )
        rows = cursor.fetchall()
        logger.info(
            "starting recompute users=%s users_with_fields=%s "
            "new_total_expected_fields=%s dry_run=%s",
            len(rows),
            len(all_populated),
            TOTAL_EXPECTED_FIELDS,
            dry_run,
        )

        for row in rows:
            if isinstance(row, dict):
                user_id = row["user_id"]
                old_pct = float(row["completeness_pct"] or 0.0)
                old_populated = int(row["populated_fields"] or 0)
                old_total = int(row["total_fields"] or 0)
            else:
                user_id, old_pct_raw, old_populated_raw, old_total_raw = row
                old_pct = float(old_pct_raw or 0.0)
                old_populated = int(old_populated_raw or 0)
                old_total = int(old_total_raw or 0)

            # Users with no profile_fields rows still need their counts zeroed
            # against the new denominator — fall back to empty-populated map.
            populated = all_populated.get(
                user_id, {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
            )
            new_populated, new_pct = _compute_from_populated(populated)

            changed = (
                round(new_pct, 2) != round(old_pct, 2)
                or new_populated != old_populated
                or TOTAL_EXPECTED_FIELDS != old_total
            )

            if not changed:
                unchanged += 1
                logger.debug(
                    "no-change user_id=%s pct=%.2f populated=%s",
                    user_id,
                    new_pct,
                    new_populated,
                )
                continue

            logger.info(
                "user_id=%s pct %.2f -> %.2f, populated %s -> %s, total %s -> %s",
                user_id,
                old_pct,
                new_pct,
                old_populated,
                new_populated,
                old_total,
                TOTAL_EXPECTED_FIELDS,
            )

            if not dry_run:
                cursor.execute(
                    """
                    UPDATE user_profiles
                    SET completeness_pct = %s,
                        populated_fields = %s,
                        total_fields = %s,
                        last_updated = %s
                    WHERE user_id = %s
                    """,
                    (
                        new_pct,
                        new_populated,
                        TOTAL_EXPECTED_FIELDS,
                        datetime.now(timezone.utc),
                        user_id,
                    ),
                )
                _invalidate_cache(user_id)
            updated += 1

        if not dry_run:
            conn.commit()

        logger.info(
            "done updated=%s unchanged=%s dry_run=%s", updated, unchanged, dry_run
        )

    except Exception:
        if not dry_run:
            conn.rollback()
        raise
    finally:
        cursor.close()
        release_timescale_conn(conn)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = parser.parse_args()
    recompute_all(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
