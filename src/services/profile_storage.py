"""
Profile Storage Service
Stores and retrieves user profile information from PostgreSQL
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn

logger = logging.getLogger("agentic_memories.profile_storage")


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
        """Update user_profiles with field counts and completeness percentage"""
        # Count total fields and populated fields
        cursor.execute("""
            SELECT COUNT(*) as total_fields
            FROM profile_fields
            WHERE user_id = %s
        """, (user_id,))

        result = cursor.fetchone()
        # Handle both tuple and dict-like cursor results
        if result:
            populated_fields = result['total_fields'] if isinstance(result, dict) else result[0]
        else:
            populated_fields = 0

        # Define expected fields per category (baseline for completeness)
        # This is a simple heuristic - can be made more sophisticated
        expected_fields_per_category = {
            'basics': 6,       # name, age, location, occupation, education, family_status
            'preferences': 5,  # communication_style, likes, dislikes, favorites, work_style
            'goals': 3,        # short_term, long_term, aspirations
            'interests': 3,    # hobbies, topics, activities
            'background': 4    # history, experiences, skills, achievements
        }
        total_expected_fields = sum(expected_fields_per_category.values())  # 21 fields

        # Calculate completeness percentage
        completeness_pct = min(100.0, (populated_fields / total_expected_fields) * 100)

        # Update user_profiles
        cursor.execute("""
            UPDATE user_profiles
            SET
                completeness_pct = %s,
                total_fields = %s,
                populated_fields = %s,
                last_updated = %s
            WHERE user_id = %s
        """, (completeness_pct, total_expected_fields, populated_fields, datetime.now(timezone.utc), user_id))

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
                "background": {}
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
