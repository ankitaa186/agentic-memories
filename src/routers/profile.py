"""
Profile CRUD API Endpoints
Provides REST API for reading, creating, updating, and deleting user profile data.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from src.services.profile_storage import ProfileStorageService
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
    """Response model for completeness metrics"""
    user_id: str
    overall_completeness_pct: float
    populated_fields: int
    total_fields: int


class DeleteResponse(BaseModel):
    """Response model for profile deletion"""
    deleted: bool
    user_id: str


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
def get_profile(user_id: str = Query(..., description="User identifier")) -> ProfileResponse:
    """
    Get complete user profile with all categories.

    Returns profile JSON with all categories (basics, preferences, goals, interests, background)
    and confidence scores, along with completeness metrics.
    """
    logger.info("[profile.api.get] user_id=%s", user_id)

    profile = _profile_service.get_profile_by_user(user_id)

    if profile is None:
        logger.info("[profile.api.get] user_id=%s not_found", user_id)
        raise HTTPException(status_code=404, detail=f"Profile not found for user_id: {user_id}")

    return ProfileResponse(**profile)


@router.get("/completeness", response_model=CompletenessResponse)
def get_profile_completeness(
    user_id: str = Query(..., description="User identifier")
) -> CompletenessResponse:
    """
    Get profile completeness metrics.

    Returns overall completeness percentage, populated fields count,
    and total expected fields count (21 fields total).
    """
    logger.info("[profile.api.completeness] user_id=%s", user_id)

    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Get profile metadata
        cursor.execute("""
            SELECT completeness_pct, populated_fields, total_fields
            FROM user_profiles
            WHERE user_id = %s
        """, (user_id,))

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Profile not found for user_id: {user_id}")

        # Handle both tuple and dict-like cursor results
        if isinstance(row, dict):
            completeness_pct = row['completeness_pct']
            populated_fields = row['populated_fields']
            total_fields = row['total_fields']
        else:
            completeness_pct, populated_fields, total_fields = row

        return CompletenessResponse(
            user_id=user_id,
            overall_completeness_pct=float(completeness_pct),
            populated_fields=populated_fields,
            total_fields=total_fields
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[profile.api.completeness] user_id=%s error=%s",
            user_id,
            e,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to get completeness: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_timescale_conn(conn)


@router.get("/{category}", response_model=CategoryResponse)
def get_profile_category(
    category: str,
    user_id: str = Query(..., description="User identifier")
) -> CategoryResponse:
    """
    Get category-specific profile data.

    Valid categories: basics, preferences, goals, interests, background
    Returns only that category's fields with confidence scores.
    """
    logger.info("[profile.api.get_category] user_id=%s category=%s", user_id, category)

    # Validate category
    valid_categories = ["basics", "preferences", "goals", "interests", "background"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(valid_categories)}"
        )

    # Get full profile and extract category
    profile = _profile_service.get_profile_by_user(user_id)

    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found for user_id: {user_id}")

    category_data = profile.get("profile", {}).get(category, {})

    return CategoryResponse(
        user_id=user_id,
        category=category,
        fields=category_data
    )


@router.put("/{category}/{field_name}", response_model=FieldUpdateResponse)
def update_profile_field(
    category: str,
    field_name: str,
    body: UpdateFieldRequest
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
        field_name
    )

    # Validate category
    valid_categories = ["basics", "preferences", "goals", "interests", "background"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(valid_categories)}"
        )

    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Ensure user profile exists
        cursor.execute("""
            INSERT INTO user_profiles (user_id, completeness_pct, total_fields, populated_fields)
            VALUES (%s, 0.00, 0, 0)
            ON CONFLICT (user_id) DO NOTHING
        """, (body.user_id,))

        # Infer value type
        value_type = _infer_value_type(body.value)
        value_str = _serialize_field_value(body.value)

        # UPSERT profile_field
        cursor.execute("""
            INSERT INTO profile_fields (user_id, category, field_name, field_value, value_type, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, category, field_name)
            DO UPDATE SET
                field_value = EXCLUDED.field_value,
                value_type = EXCLUDED.value_type,
                last_updated = EXCLUDED.last_updated
        """, (body.user_id, category, field_name, value_str, value_type, datetime.now(timezone.utc)))

        # Set confidence to 100% (manual is authoritative)
        # For manual updates: all scores = 100, mention_count = 1
        cursor.execute("""
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
        """, (
            body.user_id, category, field_name,
            100, 100, 100, 100, 100,  # All confidence scores = 100 for manual
            1, datetime.now(timezone.utc), datetime.now(timezone.utc)
        ))

        # Record source (manual edits are "explicit" source_type)
        cursor.execute("""
            INSERT INTO profile_sources (user_id, category, field_name, source_memory_id, source_type, extracted_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (body.user_id, category, field_name, "manual", "explicit", datetime.now(timezone.utc)))

        # Update user_profiles metadata
        _update_profile_metadata(cursor, body.user_id)

        # Update last_updated timestamp
        cursor.execute("""
            UPDATE user_profiles
            SET last_updated = %s
            WHERE user_id = %s
        """, (datetime.now(timezone.utc), body.user_id))

        conn.commit()

        logger.info(
            "[profile.api.update] user_id=%s category=%s field_name=%s success",
            body.user_id,
            category,
            field_name
        )

        return FieldUpdateResponse(
            user_id=body.user_id,
            category=category,
            field_name=field_name,
            value=body.value,
            confidence=100.0,
            last_updated=datetime.now(timezone.utc).isoformat()
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
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to update profile field: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_timescale_conn(conn)


@router.delete("", response_model=DeleteResponse)
def delete_profile(
    user_id: str = Query(..., description="User identifier"),
    confirmation: str = Query(..., description="Must be 'DELETE' to confirm deletion")
) -> DeleteResponse:
    """
    Delete all profile data for a user.

    Requires confirmation='DELETE' (case-sensitive) to prevent accidental deletion.
    Deletes all rows from profile_fields, profile_confidence_scores, profile_sources,
    and user_profiles (CASCADE handles foreign keys).
    """
    logger.info("[profile.api.delete] user_id=%s confirmation=%s", user_id, confirmation)

    # Validate confirmation
    if confirmation != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Confirmation failed. Must provide confirmation='DELETE' (case-sensitive)"
        )

    conn = None
    cursor = None

    try:
        conn = get_timescale_conn()
        cursor = conn.cursor()

        # Check if profile exists
        cursor.execute("""
            SELECT user_id FROM user_profiles WHERE user_id = %s
        """, (user_id,))

        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"Profile not found for user_id: {user_id}")

        # Delete from user_profiles (CASCADE will handle related tables)
        cursor.execute("""
            DELETE FROM user_profiles WHERE user_id = %s
        """, (user_id,))

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
            "[profile.api.delete] user_id=%s error=%s",
            user_id,
            e,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete profile: {str(e)}")
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
    """Update user_profiles with field counts and completeness percentage"""
    # Count total fields
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

    # Define expected fields per category (21 total)
    expected_fields_per_category = {
        'basics': 6,
        'preferences': 5,
        'goals': 3,
        'interests': 3,
        'background': 4
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
