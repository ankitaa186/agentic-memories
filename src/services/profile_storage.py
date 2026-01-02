"""
Profile Storage Service
Stores and retrieves user profile information from PostgreSQL
"""
from typing import List, Dict, Any, Optional, Set
import logging
import json
from datetime import datetime, timezone

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.dependencies.redis_client import get_redis_client

logger = logging.getLogger("agentic_memories.profile_storage")


# Expected profile fields per category
# These define the baseline for completeness calculation
# Core fields a "complete" profile should have
EXPECTED_PROFILE_FIELDS: Dict[str, List[str]] = {
    'basics': ['name', 'birthday', 'location', 'occupation', 'family_status'],
    'preferences': ['communication_style', 'food_preferences', 'love_language', 'gift_preferences'],
    'goals': ['short_term', 'long_term', 'bucket_list'],
    'interests': ['hobbies', 'learning_areas', 'favorite_topics'],
    'background': ['skills', 'education_history', 'work_history', 'current_employer'],
    'health': ['allergies', 'dietary_needs'],
    'personality': ['personality_type', 'stress_response', 'social_battery'],
    'values': ['life_values', 'philanthropy', 'spiritual_alignment']
}

# Total expected fields count
TOTAL_EXPECTED_FIELDS = sum(len(fields) for fields in EXPECTED_PROFILE_FIELDS.values())  # 25

# Valid category names - single source of truth
VALID_CATEGORIES = list(EXPECTED_PROFILE_FIELDS.keys())

# Redis cache key pattern and TTL for completeness data
COMPLETENESS_CACHE_KEY = "profile_completeness:{user_id}"
COMPLETENESS_CACHE_TTL = 3600  # 1 hour


class ProfileStorageService:
    """Handles storage and retrieval of user profile data"""

    def store_profile_extractions(
        self,
        user_id: str,
        extractions: List[Dict[str, Any]]
    ) -> int:
        """
        Store profile extractions in PostgreSQL.

        This method:
        1. Upserts profile_fields with new values
        2. Records sources in profile_sources
        3. Updates user_profiles metadata

        Args:
            user_id: User identifier
            extractions: List of profile extraction dictionaries

        Returns:
            Number of fields updated
        """
        if not extractions:
            logger.info("[profile.store] user_id=%s no_extractions", user_id)
            return 0

        conn = None
        cursor = None
        fields_updated = 0

        try:
            conn = get_timescale_conn()
            cursor = conn.cursor()

            # Ensure user profile exists
            cursor.execute("""
                INSERT INTO user_profiles (user_id, completeness_pct, total_fields, populated_fields)
                VALUES (%s, 0.00, 0, 0)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id,))

            # Process each extraction
            for extraction in extractions:
                category = extraction.get("category")
                field_name = extraction.get("field_name")
                field_value = extraction.get("field_value")
                confidence = extraction.get("confidence", 70)
                source_type = extraction.get("source_type", "implicit")
                source_memory_id = extraction.get("source_memory_id", "unknown")

                # Determine value_type
                value_type = self._infer_value_type(field_value)

                # Convert field_value to string for storage
                field_value_str = self._serialize_field_value(field_value)

                # Upsert profile_field
                cursor.execute("""
                    INSERT INTO profile_fields (user_id, category, field_name, field_value, value_type, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, category, field_name)
                    DO UPDATE SET
                        field_value = EXCLUDED.field_value,
                        value_type = EXCLUDED.value_type,
                        last_updated = EXCLUDED.last_updated
                """, (user_id, category, field_name, field_value_str, value_type, datetime.now(timezone.utc)))

                # Record source (insert new source record each time)
                cursor.execute("""
                    INSERT INTO profile_sources (user_id, category, field_name, source_memory_id, source_type, extracted_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, category, field_name, source_memory_id, source_type, datetime.now(timezone.utc)))

                fields_updated += 1

            # Update user_profiles metadata (counts and completeness)
            self._update_profile_metadata(cursor, user_id)

            conn.commit()

            logger.info(
                "[profile.store] user_id=%s fields_updated=%s",
                user_id,
                fields_updated
            )

            return fields_updated

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(
                "[profile.store] user_id=%s error=%s",
                user_id,
                e,
                exc_info=True
            )
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                release_timescale_conn(conn)

    def _infer_value_type(self, value: Any) -> str:
        """Infer the value_type from Python type"""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, list):
            return "list"
        elif isinstance(value, dict):
            return "dict"
        else:
            return "string"

    def _serialize_field_value(self, value: Any) -> str:
        """Serialize field value to string for TEXT storage"""
        import json

        if isinstance(value, (list, dict)):
            return json.dumps(value)
        elif isinstance(value, bool):
            return str(value).lower()  # "true" or "false"
        else:
            return str(value)

    def _update_profile_metadata(self, cursor, user_id: str):
        """
        Update user_profiles with field counts and completeness percentage.
        Also invalidates the completeness cache.

        Uses EXPECTED_PROFILE_FIELDS constant (25 total fields across 5 categories).
        """
        # Get populated fields grouped by category
        cursor.execute("""
            SELECT category, field_name
            FROM profile_fields
            WHERE user_id = %s
        """, (user_id,))

        rows = cursor.fetchall()

        # Build set of populated fields per category
        populated_by_category: Dict[str, Set[str]] = {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
        for row in rows:
            if isinstance(row, dict):
                category = row['category']
                field_name = row['field_name']
            else:
                category, field_name = row

            if category in populated_by_category:
                populated_by_category[category].add(field_name)

        # Count total populated fields (intersection with expected fields)
        total_populated = 0
        for category, expected_fields in EXPECTED_PROFILE_FIELDS.items():
            populated = populated_by_category.get(category, set())
            # Count only fields that are in our expected list
            total_populated += len(populated.intersection(set(expected_fields)))

        # Calculate overall completeness percentage
        completeness_pct = min(100.0, (total_populated / TOTAL_EXPECTED_FIELDS) * 100)

        # Update user_profiles
        cursor.execute("""
            UPDATE user_profiles
            SET
                completeness_pct = %s,
                total_fields = %s,
                populated_fields = %s,
                last_updated = %s
            WHERE user_id = %s
        """, (completeness_pct, TOTAL_EXPECTED_FIELDS, total_populated, datetime.now(timezone.utc), user_id))

        # Invalidate completeness cache
        self._invalidate_completeness_cache(user_id)

    def _invalidate_completeness_cache(self, user_id: str):
        """Invalidate the Redis completeness cache for a user"""
        try:
            redis_client = get_redis_client()
            if redis_client:
                cache_key = COMPLETENESS_CACHE_KEY.format(user_id=user_id)
                redis_client.delete(cache_key)
                logger.debug("[profile.cache] invalidated completeness cache for user_id=%s", user_id)
        except Exception as e:
            # Cache invalidation failure shouldn't break the main flow
            logger.warning("[profile.cache] failed to invalidate cache for user_id=%s: %s", user_id, e)

    def get_completeness_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed completeness information including per-category breakdown and high-value gaps.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with overall_completeness_pct, populated_fields, total_fields,
            categories breakdown, and high_value_gaps list.
            Returns None if profile doesn't exist.
        """
        # Check cache first
        cached = self._get_cached_completeness(user_id)
        if cached:
            logger.debug("[profile.completeness] cache_hit user_id=%s", user_id)
            return cached

        logger.debug("[profile.completeness] cache_miss user_id=%s", user_id)

        conn = None
        cursor = None

        try:
            conn = get_timescale_conn()
            cursor = conn.cursor()

            # Check if profile exists
            cursor.execute("""
                SELECT completeness_pct, populated_fields, total_fields
                FROM user_profiles
                WHERE user_id = %s
            """, (user_id,))

            profile_row = cursor.fetchone()
            if not profile_row:
                return None

            # Get populated fields by category
            cursor.execute("""
                SELECT category, field_name
                FROM profile_fields
                WHERE user_id = %s
            """, (user_id,))

            rows = cursor.fetchall()

            # Build set of populated fields per category
            populated_by_category: Dict[str, Set[str]] = {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
            for row in rows:
                if isinstance(row, dict):
                    category = row['category']
                    field_name = row['field_name']
                else:
                    category, field_name = row

                if category in populated_by_category:
                    populated_by_category[category].add(field_name)

            # Get confidence scores for gap prioritization
            cursor.execute("""
                SELECT category, field_name, overall_confidence
                FROM profile_confidence_scores
                WHERE user_id = %s
            """, (user_id,))

            confidence_rows = cursor.fetchall()
            confidence_by_field: Dict[str, float] = {}
            for row in confidence_rows:
                if isinstance(row, dict):
                    cat = row['category']
                    field = row['field_name']
                    conf = row['overall_confidence']
                else:
                    cat, field, conf = row
                confidence_by_field[f"{cat}.{field}"] = float(conf) if conf else 0.0

            # Calculate per-category completeness
            categories = {}
            total_populated = 0
            for category, expected_fields in EXPECTED_PROFILE_FIELDS.items():
                populated = populated_by_category.get(category, set())
                expected_set = set(expected_fields)

                # Count only expected fields that are populated
                populated_expected = populated.intersection(expected_set)
                missing = list(expected_set - populated)

                category_total = len(expected_fields)
                category_populated = len(populated_expected)
                category_pct = (category_populated / category_total) * 100 if category_total > 0 else 0.0

                categories[category] = {
                    "completeness_pct": round(category_pct, 1),
                    "populated": category_populated,
                    "total": category_total,
                    "missing": sorted(missing)
                }

                total_populated += category_populated

            # Calculate overall completeness
            overall_pct = (total_populated / TOTAL_EXPECTED_FIELDS) * 100 if TOTAL_EXPECTED_FIELDS > 0 else 0.0

            # Identify high-value gaps
            high_value_gaps = self._identify_high_value_gaps(
                populated_by_category,
                confidence_by_field,
                categories
            )

            result = {
                "overall_completeness_pct": round(overall_pct, 1),
                "populated_fields": total_populated,
                "total_fields": TOTAL_EXPECTED_FIELDS,
                "categories": categories,
                "high_value_gaps": high_value_gaps
            }

            # Cache the result
            self._cache_completeness(user_id, result)

            return result

        except Exception as e:
            logger.error(
                "[profile.completeness] user_id=%s error=%s",
                user_id,
                e,
                exc_info=True
            )
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                release_timescale_conn(conn)

    def _identify_high_value_gaps(
        self,
        populated_by_category: Dict[str, Set[str]],
        confidence_by_field: Dict[str, float],
        categories: Dict[str, Any]
    ) -> List[str]:
        """
        Identify high-value gaps to prioritize for filling.

        Priority order:
        1. Missing basics fields (foundational identity)
        2. Fields with zero confidence (never extracted)
        3. Fields relevant to populated goals

        Args:
            populated_by_category: Set of populated fields per category
            confidence_by_field: Confidence scores keyed by "category.field_name"
            categories: Category completeness data with missing fields

        Returns:
            Ordered list of field names (format: "field_name" for basics, "category_field" otherwise)
        """
        high_value_gaps = []

        # Priority 1: Missing basics fields (highest priority - foundational identity)
        basics_missing = categories.get('basics', {}).get('missing', [])
        for field in basics_missing:
            high_value_gaps.append(field)

        # Priority 2: Fields with zero confidence (never extracted) across other categories
        for category in ['preferences', 'goals', 'interests', 'background']:
            missing = categories.get(category, {}).get('missing', [])
            for field in missing:
                key = f"{category}.{field}"
                conf = confidence_by_field.get(key, 0.0)
                if conf == 0.0 and field not in high_value_gaps:
                    # Use descriptive name for non-basics fields
                    gap_name = f"{field}" if category == 'basics' else f"{field}"
                    if gap_name not in high_value_gaps:
                        high_value_gaps.append(gap_name)

        # Priority 3: Goal-relevant fields (if goals category is partially populated)
        goals_populated = populated_by_category.get('goals', set())
        if goals_populated:
            # If user has goals, skills and background are relevant
            for field in ['skills', 'experiences', 'learning']:
                for category in ['background', 'interests']:
                    if field in categories.get(category, {}).get('missing', []):
                        if field not in high_value_gaps:
                            high_value_gaps.append(field)

        # Limit to top 10 most important gaps
        return high_value_gaps[:10]

    def _get_cached_completeness(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get completeness data from Redis cache"""
        try:
            redis_client = get_redis_client()
            if redis_client:
                cache_key = COMPLETENESS_CACHE_KEY.format(user_id=user_id)
                cached = redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
        except Exception as e:
            logger.warning("[profile.cache] failed to get cache for user_id=%s: %s", user_id, e)
        return None

    def _cache_completeness(self, user_id: str, data: Dict[str, Any]):
        """Cache completeness data in Redis"""
        try:
            redis_client = get_redis_client()
            if redis_client:
                cache_key = COMPLETENESS_CACHE_KEY.format(user_id=user_id)
                # Add cache timestamp
                data_with_ts = {
                    **data,
                    "cached_at": datetime.now(timezone.utc).isoformat()
                }
                redis_client.setex(cache_key, COMPLETENESS_CACHE_TTL, json.dumps(data_with_ts))
                logger.debug("[profile.cache] cached completeness for user_id=%s", user_id)
        except Exception as e:
            logger.warning("[profile.cache] failed to cache for user_id=%s: %s", user_id, e)

    def get_profile_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete profile for a user.

        Args:
            user_id: User identifier

        Returns:
            Profile dictionary with metadata and fields grouped by category
        """
        conn = None
        cursor = None

        try:
            conn = get_timescale_conn()
            cursor = conn.cursor()

            # Get profile metadata
            cursor.execute("""
                SELECT completeness_pct, total_fields, populated_fields, last_updated, created_at
                FROM user_profiles
                WHERE user_id = %s
            """, (user_id,))

            profile_row = cursor.fetchone()
            if not profile_row:
                logger.info("[profile.get] user_id=%s not_found", user_id)
                return None

            # Handle both tuple and dict-like cursor results
            if isinstance(profile_row, dict):
                completeness_pct = profile_row['completeness_pct']
                total_fields = profile_row['total_fields']
                populated_fields = profile_row['populated_fields']
                last_updated = profile_row['last_updated']
                created_at = profile_row['created_at']
            else:
                completeness_pct, total_fields, populated_fields, last_updated, created_at = profile_row

            # Get all profile fields
            cursor.execute("""
                SELECT category, field_name, field_value, value_type, last_updated
                FROM profile_fields
                WHERE user_id = %s
                ORDER BY category, field_name
            """, (user_id,))

            fields_rows = cursor.fetchall()

            # Group fields by category
            profile_data = {
                "basics": {},
                "preferences": {},
                "goals": {},
                "interests": {},
                "background": {},
                "health": {},
                "personality": {},
                "values": {}
            }

            for row in fields_rows:
                # Handle both tuple and dict-like cursor results
                if isinstance(row, dict):
                    category = row['category']
                    field_name = row['field_name']
                    field_value = row['field_value']
                    value_type = row['value_type']
                    field_last_updated = row['last_updated']
                else:
                    category, field_name, field_value, value_type, field_last_updated = row

                # Deserialize value based on type
                parsed_value = self._deserialize_field_value(field_value, value_type)

                # Handle both datetime objects and string timestamps
                if field_last_updated:
                    if hasattr(field_last_updated, 'isoformat'):
                        last_updated_str = field_last_updated.isoformat()
                    else:
                        last_updated_str = str(field_last_updated)
                else:
                    last_updated_str = None

                profile_data[category][field_name] = {
                    "value": parsed_value,
                    "last_updated": last_updated_str
                }

            # Build final profile object
            # Handle both datetime objects and string timestamps for metadata
            last_updated_str = last_updated.isoformat() if hasattr(last_updated, 'isoformat') else str(last_updated) if last_updated else None
            created_at_str = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at) if created_at else None

            profile = {
                "user_id": user_id,
                "completeness_pct": float(completeness_pct),
                "total_fields": total_fields,
                "populated_fields": populated_fields,
                "last_updated": last_updated_str,
                "created_at": created_at_str,
                "profile": profile_data
            }

            logger.info(
                "[profile.get] user_id=%s completeness=%.1f%% fields=%s",
                user_id,
                completeness_pct,
                populated_fields
            )

            return profile

        except Exception as e:
            logger.error(
                "[profile.get] user_id=%s error=%s",
                user_id,
                e,
                exc_info=True
            )
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                release_timescale_conn(conn)

    def _deserialize_field_value(self, value_str: str, value_type: str) -> Any:
        """Deserialize field value from TEXT storage"""
        import json

        if value_type == "bool":
            return value_str.lower() == "true"
        elif value_type == "int":
            return int(value_str)
        elif value_type == "float":
            return float(value_str)
        elif value_type == "list":
            return json.loads(value_str)
        elif value_type == "dict":
            return json.loads(value_str)
        else:
            return value_str
