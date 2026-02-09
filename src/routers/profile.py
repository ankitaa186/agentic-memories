"""
Profile CRUD API Endpoints
Provides REST API for reading, creating, updating, and deleting user profile data.
"""

from typing import Dict, Any, Optional, List, Union
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from src.services.profile_storage import ProfileStorageService, VALID_CATEGORIES
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn

logger = logging.getLogger("agentic_memories.profile_api")

router = APIRouter(prefix="/v1/profile", tags=["profile"])


# Pydantic models for request/response validation
class UpdateFieldRequest(BaseModel):
    """Request model for updating a single profile field"""

    user_id: str
    value: Any
    source: str = "manual"


class ProfileResponse(BaseModel):
    """Response model for complete profile"""

    user_id: str
    profile: Dict[str, Dict[str, Any]]
    completeness_pct: float
    populated_fields: int
    total_fields: int
    last_updated: Optional[str] = None
    created_at: Optional[str] = None


class CategoryResponse(BaseModel):
    """Response model for category-specific data"""

    user_id: str
    category: str
    fields: Dict[str, Any]


class CompletenessResponse(BaseModel):
    """Response model for completeness metrics (simple mode)"""

    user_id: str
    overall_completeness_pct: float
    populated_fields: int
    total_fields: int


class CategoryCompleteness(BaseModel):
    """Completeness details for a single category"""

    completeness_pct: float
    populated: int
    total: int
    missing: List[str]


class DetailedCompletenessResponse(BaseModel):
    """Response model for detailed completeness metrics (with categories and gaps)"""

    user_id: str
    overall_completeness_pct: float
    populated_fields: int
    total_fields: int
    categories: Dict[str, CategoryCompleteness]
    high_value_gaps: List[str]


class DeleteResponse(BaseModel):
    """Response model for profile deletion"""

    deleted: bool
    user_id: str


class FieldDeleteResponse(BaseModel):
    """Response model for single field deletion"""

    deleted: bool
    user_id: str
    category: str
    field_name: str


class FieldUpdateResponse(BaseModel):
    """Response model for field update"""

    user_id: str
    category: str
    field_name: str
    value: Any
    confidence: float
    last_updated: str


# Initialize service
_profile_service = ProfileStorageService()


@router.get("", response_model=ProfileResponse)
def get_profile(
    user_id: str = Query(..., description="User identifier"),
) -> ProfileResponse:
    """
    Get complete user profile with all categories.

    Returns profile JSON with all categories (basics, preferences, goals, interests, background)
    and confidence scores, along with completeness metrics.
    """
    logger.info("[profile.api.get] user_id=%s", user_id)

    profile = _profile_service.get_profile_by_user(user_id)

    if profile is None:
        logger.info("[profile.api.get] user_id=%s not_found", user_id)
        raise HTTPException(
            status_code=404, detail=f"Profile not found for user_id: {user_id}"
        )

    return ProfileResponse(**profile)


@router.get(
    "/completeness",
    response_model=Union[CompletenessResponse, DetailedCompletenessResponse],
)
def get_profile_completeness(
    user_id: str = Query(..., description="User identifier"),
    details: bool = Query(
        False, description="If true, return per-category breakdown and high-value gaps"
    ),
) -> Union[CompletenessResponse, DetailedCompletenessResponse]:
    """
    Get profile completeness metrics.

    Args:
        user_id: User identifier
        details: If true, return detailed breakdown with categories and high_value_gaps.
                 If false (default), return simple completeness metrics for backward compatibility.

    Returns:
        Simple response (details=false):
            - overall_completeness_pct, populated_fields, total_fields

        Detailed response (details=true):
            - overall_completeness_pct, populated_fields, total_fields
            - categories: per-category breakdown with missing fields
            - high_value_gaps: prioritized list of fields to fill
    """
    logger.info("[profile.api.completeness] user_id=%s details=%s", user_id, details)

    if details:
        # Use service layer for detailed completeness (includes caching)
        completeness_data = _profile_service.get_completeness_details(user_id)

        if completeness_data is None:
            raise HTTPException(
                status_code=404, detail=f"Profile not found for user_id: {user_id}"
            )

        # Remove cached_at field if present (internal use only)
        completeness_data.pop("cached_at", None)

        return DetailedCompletenessResponse(user_id=user_id, **completeness_data)

    # Simple mode - backward compatible response
    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Get profile metadata
        cursor.execute(
            """
            SELECT completeness_pct, populated_fields, total_fields
            FROM user_profiles
            WHERE user_id = %s
        """,
            (user_id,),
        )

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Profile not found for user_id: {user_id}"
            )

        # Handle both tuple and dict-like cursor results
        if isinstance(row, dict):
            completeness_pct = row["completeness_pct"]
            populated_fields = row["populated_fields"]
            total_fields = row["total_fields"]
        else:
            completeness_pct, populated_fields, total_fields = row

        return CompletenessResponse(
            user_id=user_id,
            overall_completeness_pct=float(completeness_pct),
            populated_fields=populated_fields,
            total_fields=total_fields,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[profile.api.completeness] user_id=%s error=%s", user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get completeness: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_timescale_conn(conn)


@router.get("/{category}", response_model=CategoryResponse)
def get_profile_category(
    category: str, user_id: str = Query(..., description="User identifier")
) -> CategoryResponse:
    """
    Get category-specific profile data.

    Valid categories: basics, preferences, goals, interests, background
    Returns only that category's fields with confidence scores.
    """
    logger.info("[profile.api.get_category] user_id=%s category=%s", user_id, category)

    # Validate category
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}",
        )

    # Get full profile and extract category
    profile = _profile_service.get_profile_by_user(user_id)

    if profile is None:
        raise HTTPException(
            status_code=404, detail=f"Profile not found for user_id: {user_id}"
        )

    category_data = profile.get("profile", {}).get(category, {})

    return CategoryResponse(user_id=user_id, category=category, fields=category_data)


@router.put("/{category}/{field_name}", response_model=FieldUpdateResponse)
def update_profile_field(
    category: str, field_name: str, body: UpdateFieldRequest
) -> FieldUpdateResponse:
    """
    Update a single profile field value.

    Manual edits always set confidence to 100% (authoritative source).
    Records the change in profile_sources table with source_type="manual".
    """
    logger.info(
        "[profile.api.update] user_id=%s category=%s field_name=%s",
        body.user_id,
        category,
        field_name,
    )

    # Validate category
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}",
        )

    # Reject null values - use DELETE endpoint instead
    if body.value is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot set field value to null. Use DELETE /v1/profile/{category}/{field_name}?user_id={body.user_id} to remove the field.",
        )

    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Ensure user profile exists
        cursor.execute(
            """
            INSERT INTO user_profiles (user_id, completeness_pct, total_fields, populated_fields)
            VALUES (%s, 0.00, 0, 0)
            ON CONFLICT (user_id) DO NOTHING
        """,
            (body.user_id,),
        )

        # Infer value type
        value_type = _infer_value_type(body.value)
        value_str = _serialize_field_value(body.value)

        # UPSERT profile_field
        cursor.execute(
            """
            INSERT INTO profile_fields (user_id, category, field_name, field_value, value_type, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, category, field_name)
            DO UPDATE SET
                field_value = EXCLUDED.field_value,
                value_type = EXCLUDED.value_type,
                last_updated = EXCLUDED.last_updated
        """,
            (
                body.user_id,
                category,
                field_name,
                value_str,
                value_type,
                datetime.now(timezone.utc),
            ),
        )

        # Set confidence to 100% (manual is authoritative)
        # For manual updates: all scores = 100, mention_count = 1
        cursor.execute(
            """
            INSERT INTO profile_confidence_scores (
                user_id, category, field_name,
                overall_confidence, frequency_score, recency_score,
                explicitness_score, source_diversity_score,
                mention_count, last_mentioned, last_updated
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, category, field_name)
            DO UPDATE SET
                overall_confidence = EXCLUDED.overall_confidence,
                frequency_score = EXCLUDED.frequency_score,
                recency_score = EXCLUDED.recency_score,
                explicitness_score = EXCLUDED.explicitness_score,
                source_diversity_score = EXCLUDED.source_diversity_score,
                mention_count = profile_confidence_scores.mention_count + 1,
                last_mentioned = EXCLUDED.last_mentioned,
                last_updated = EXCLUDED.last_updated
        """,
            (
                body.user_id,
                category,
                field_name,
                100,
                100,
                100,
                100,
                100,  # All confidence scores = 100 for manual
                1,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            ),
        )

        # Record source (manual edits are "explicit" source_type)
        cursor.execute(
            """
            INSERT INTO profile_sources (user_id, category, field_name, source_memory_id, source_type, extracted_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (
                body.user_id,
                category,
                field_name,
                "manual",
                "explicit",
                datetime.now(timezone.utc),
            ),
        )

        # Update user_profiles metadata (also updates last_updated)
        _update_profile_metadata(cursor, body.user_id)

        conn.commit()

        logger.info(
            "[profile.api.update] user_id=%s category=%s field_name=%s success",
            body.user_id,
            category,
            field_name,
        )

        return FieldUpdateResponse(
            user_id=body.user_id,
            category=category,
            field_name=field_name,
            value=body.value,
            confidence=100.0,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(
            "[profile.api.update] user_id=%s category=%s field_name=%s error=%s",
            body.user_id,
            category,
            field_name,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to update profile field: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_timescale_conn(conn)


@router.delete("/{category}/{field_name}", response_model=FieldDeleteResponse)
def delete_profile_field(
    category: str,
    field_name: str,
    user_id: str = Query(..., description="User identifier"),
) -> FieldDeleteResponse:
    """
    Delete a single profile field.

    Removes the field from profile_fields, profile_confidence_scores, and profile_sources.
    Updates profile metadata (completeness, populated_fields count).
    """
    logger.info(
        "[profile.api.delete_field] user_id=%s category=%s field_name=%s",
        user_id,
        category,
        field_name,
    )

    # Validate category
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}",
        )

    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Check if user profile exists
        cursor.execute(
            """
            SELECT user_id FROM user_profiles WHERE user_id = %s
        """,
            (user_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404, detail=f"Profile not found for user_id: {user_id}"
            )

        # Check if field exists
        cursor.execute(
            """
            SELECT field_name FROM profile_fields
            WHERE user_id = %s AND category = %s AND field_name = %s
        """,
            (user_id, category, field_name),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"Field '{field_name}' not found in category '{category}' for user_id: {user_id}",
            )

        # Delete from profile_sources first (FK constraint)
        cursor.execute(
            """
            DELETE FROM profile_sources
            WHERE user_id = %s AND category = %s AND field_name = %s
        """,
            (user_id, category, field_name),
        )

        # Delete from profile_confidence_scores (FK constraint)
        cursor.execute(
            """
            DELETE FROM profile_confidence_scores
            WHERE user_id = %s AND category = %s AND field_name = %s
        """,
            (user_id, category, field_name),
        )

        # Delete from profile_fields
        cursor.execute(
            """
            DELETE FROM profile_fields
            WHERE user_id = %s AND category = %s AND field_name = %s
        """,
            (user_id, category, field_name),
        )

        # Update user_profiles metadata (also updates last_updated)
        _update_profile_metadata(cursor, user_id)

        conn.commit()

        logger.info(
            "[profile.api.delete_field] user_id=%s category=%s field_name=%s success",
            user_id,
            category,
            field_name,
        )

        return FieldDeleteResponse(
            deleted=True, user_id=user_id, category=category, field_name=field_name
        )

    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(
            "[profile.api.delete_field] user_id=%s category=%s field_name=%s error=%s",
            user_id,
            category,
            field_name,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete profile field: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_timescale_conn(conn)


@router.delete("", response_model=DeleteResponse)
def delete_profile(
    user_id: str = Query(..., description="User identifier"),
    confirmation: str = Query(..., description="Must be 'DELETE' to confirm deletion"),
) -> DeleteResponse:
    """
    Delete all profile data for a user.

    Requires confirmation='DELETE' (case-sensitive) to prevent accidental deletion.
    Deletes all rows from profile_fields, profile_confidence_scores, profile_sources,
    and user_profiles (CASCADE handles foreign keys).
    """
    logger.info(
        "[profile.api.delete] user_id=%s confirmation=%s", user_id, confirmation
    )

    # Validate confirmation
    if confirmation != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Confirmation failed. Must provide confirmation='DELETE' (case-sensitive)",
        )

    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Check if profile exists
        cursor.execute(
            """
            SELECT user_id FROM user_profiles WHERE user_id = %s
        """,
            (user_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404, detail=f"Profile not found for user_id: {user_id}"
            )

        # Delete from user_profiles (CASCADE will handle related tables)
        cursor.execute(
            """
            DELETE FROM user_profiles WHERE user_id = %s
        """,
            (user_id,),
        )

        conn.commit()

        logger.info("[profile.api.delete] user_id=%s success", user_id)

        return DeleteResponse(deleted=True, user_id=user_id)

    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(
            "[profile.api.delete] user_id=%s error=%s", user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete profile: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_timescale_conn(conn)


# Helper functions (copied from ProfileStorageService for consistency)
def _infer_value_type(value: Any) -> str:
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


def _serialize_field_value(value: Any) -> str:
    """Serialize field value to string for TEXT storage"""
    import json

    if isinstance(value, (list, dict)):
        return json.dumps(value)
    elif isinstance(value, bool):
        return str(value).lower()  # "true" or "false"
    else:
        return str(value)


def _update_profile_metadata(cursor, user_id: str):
    """
    Update user_profiles with field counts and completeness percentage.
    Uses the service layer constants (25 total fields across 5 categories).
    Also invalidates the completeness cache.
    """
    from src.services.profile_storage import (
        EXPECTED_PROFILE_FIELDS,
        TOTAL_EXPECTED_FIELDS,
    )

    # Get populated fields grouped by category
    cursor.execute(
        """
        SELECT category, field_name
        FROM profile_fields
        WHERE user_id = %s
    """,
        (user_id,),
    )

    rows = cursor.fetchall()

    # Build set of populated fields per category
    populated_by_category = {cat: set() for cat in EXPECTED_PROFILE_FIELDS}
    for row in rows:
        if isinstance(row, dict):
            category = row["category"]
            field_name = row["field_name"]
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

    # Calculate completeness percentage
    completeness_pct = min(100.0, (total_populated / TOTAL_EXPECTED_FIELDS) * 100)

    # Update user_profiles
    cursor.execute(
        """
        UPDATE user_profiles
        SET
            completeness_pct = %s,
            total_fields = %s,
            populated_fields = %s,
            last_updated = %s
        WHERE user_id = %s
    """,
        (
            completeness_pct,
            TOTAL_EXPECTED_FIELDS,
            total_populated,
            datetime.now(timezone.utc),
            user_id,
        ),
    )

    # Invalidate completeness cache
    _invalidate_completeness_cache(user_id)


def _invalidate_completeness_cache(user_id: str):
    """Invalidate the Redis completeness cache for a user"""
    from src.services.profile_storage import COMPLETENESS_CACHE_KEY
    from src.dependencies.redis_client import get_redis_client

    try:
        redis_client = get_redis_client()
        if redis_client:
            cache_key = COMPLETENESS_CACHE_KEY.format(user_id=user_id)
            redis_client.delete(cache_key)
            logger.debug(
                "[profile.cache] invalidated completeness cache for user_id=%s", user_id
            )
    except Exception as e:
        # Cache invalidation failure shouldn't break the main flow
        logger.warning(
            "[profile.cache] failed to invalidate cache for user_id=%s: %s", user_id, e
        )
