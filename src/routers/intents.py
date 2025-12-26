"""
Scheduled Intents API Router (Story 5.4)

Provides REST API for CRUD operations on scheduled intents.
Integrates with IntentService for business logic and IntentValidationService for validation.
"""
from typing import List, Optional
from uuid import UUID
import logging

from fastapi import APIRouter, Query, HTTPException, Response
from fastapi.responses import JSONResponse
from psycopg import Error as DatabaseError

from src.schemas import (
    ScheduledIntentCreate,
    ScheduledIntentUpdate,
    ScheduledIntentResponse,
    IntentFireRequest,
    IntentFireResponse,
    IntentExecutionResponse,
    IntentClaimResponse,
)
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.services.intent_service import IntentService

logger = logging.getLogger("agentic_memories.intents_api")

router = APIRouter(prefix="/v1/intents", tags=["intents"])


# =============================================================================
# POST /v1/intents - Create Intent (AC1)
# =============================================================================

@router.post("", response_model=ScheduledIntentResponse, status_code=201)
def create_intent(request: ScheduledIntentCreate):
    """
    Create a new scheduled intent.

    Validates the intent, calculates initial next_check, and stores in database.
    Returns 400 if validation fails with list of errors.
    Returns 201 with created intent on success.
    """
    logger.info(
        "[intents.api.create] user_id=%s intent_name=%s trigger_type=%s",
        request.user_id, request.intent_name, request.trigger_type
    )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.create] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.create_intent(request)

        if not result.success:
            logger.warning(
                "[intents.api.create] user_id=%s validation_failed errors=%s",
                request.user_id, result.errors
            )
            return JSONResponse(
                status_code=400,
                content={"errors": result.errors}
            )

        logger.info(
            "[intents.api.create] user_id=%s intent_id=%s created",
            request.user_id, result.intent.id
        )

        return JSONResponse(
            status_code=201,
            content=result.intent.model_dump(mode='json')
        )

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.create] user_id=%s database_error=%s", request.user_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.create] user_id=%s unexpected_error=%s", request.user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# GET /v1/intents - List Intents (AC2)
# =============================================================================

@router.get("", response_model=List[ScheduledIntentResponse])
def list_intents(
    user_id: str = Query(..., description="User identifier (required)"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results to skip")
):
    """
    List scheduled intents for a user.

    Returns intents ordered by created_at DESC with optional filters.
    """
    logger.info(
        "[intents.api.list] user_id=%s trigger_type=%s enabled=%s limit=%d offset=%d",
        user_id, trigger_type, enabled, limit, offset
    )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.list] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.list_intents(
            user_id=user_id,
            trigger_type=trigger_type,
            enabled=enabled,
            limit=limit,
            offset=offset
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Unknown error")

        logger.info("[intents.api.list] user_id=%s count=%d", user_id, len(result.intents or []))

        return [intent.model_dump(mode='json') for intent in (result.intents or [])]

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.list] user_id=%s database_error=%s", user_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.list] user_id=%s unexpected_error=%s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# GET /v1/intents/pending - Get Pending Intents (Story 5.5)
# =============================================================================

@router.get("/pending", response_model=List[ScheduledIntentResponse])
def get_pending_intents(
    user_id: Optional[str] = Query(None, description="Optional user filter")
):
    """
    Get pending intents that are due for execution.

    Returns intents where enabled = true AND next_check <= NOW().
    Used by Annie's proactive worker to poll for triggers to evaluate.
    Results are ordered by next_check ASC (oldest/most overdue first).
    """
    logger.info("[intents.api.pending] user_id=%s", user_id)

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.pending] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.get_pending_intents(user_id=user_id)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Unknown error")

        logger.info("[intents.api.pending] user_id=%s count=%d", user_id, len(result.intents or []))

        return [intent.model_dump(mode='json') for intent in (result.intents or [])]

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.pending] user_id=%s database_error=%s", user_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.pending] user_id=%s unexpected_error=%s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# POST /v1/intents/{id}/fire - Fire Intent (Story 5.6)
# =============================================================================

@router.post("/{intent_id}/fire", response_model=IntentFireResponse)
def fire_intent(intent_id: UUID, request: IntentFireRequest):
    """
    Report execution result and update intent state (Story 5.6).

    Updates last_checked, last_executed (on success), calculates next_check,
    handles auto-disable, and logs to intent_executions table.

    Returns 404 if intent not found.
    Returns IntentFireResponse with updated state on success.
    """
    logger.info(
        "[intents.api.fire] intent_id=%s status=%s",
        intent_id, request.status
    )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.fire] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.fire_intent(intent_id, request)

        if not result.success:
            if result.errors and "not found" in result.errors[0].lower():
                logger.info("[intents.api.fire] intent_id=%s not_found", intent_id)
                raise HTTPException(status_code=404, detail="Intent not found")
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Unknown error")

        logger.info(
            "[intents.api.fire] intent_id=%s status=%s next_check=%s enabled=%s",
            intent_id, result.response.status, result.response.next_check, result.response.enabled
        )

        return result.response.model_dump(mode='json')

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.fire] intent_id=%s database_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.fire] intent_id=%s unexpected_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# POST /v1/intents/{id}/claim - Claim Intent for Processing (Story 6.3)
# =============================================================================

@router.post("/{intent_id}/claim", response_model=IntentClaimResponse)
def claim_intent(intent_id: UUID):
    """
    Claim an intent for exclusive processing (Story 6.3).

    Sets claimed_at to NOW() to prevent other workers from processing.
    Uses FOR UPDATE SKIP LOCKED to prevent race conditions.

    Returns 404 if intent not found.
    Returns 409 if intent already claimed by another worker (within 5 min timeout).
    Returns IntentClaimResponse with intent data and claimed_at on success.

    Multi-worker Flow:
        1. GET /v1/intents/pending - Get available intents (read-only)
        2. POST /v1/intents/{id}/claim - Claim intent for processing (409 if already claimed)
        3. [Process: evaluate condition, call LLM, send message]
        4. POST /v1/intents/{id}/fire - Report result, clear claim, update next_check
    """
    logger.info("[intents.api.claim] intent_id=%s", intent_id)

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.claim] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.claim_intent(intent_id)

        if not result.success:
            if result.conflict:
                logger.info("[intents.api.claim] intent_id=%s conflict", intent_id)
                raise HTTPException(status_code=409, detail=result.errors[0] if result.errors else "Intent already claimed")
            if result.errors and "not found" in result.errors[0].lower():
                logger.info("[intents.api.claim] intent_id=%s not_found", intent_id)
                raise HTTPException(status_code=404, detail="Intent not found")
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Unknown error")

        logger.info(
            "[intents.api.claim] intent_id=%s claimed_at=%s",
            intent_id, result.response.claimed_at
        )

        return result.response.model_dump(mode='json')

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.claim] intent_id=%s database_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.claim] intent_id=%s unexpected_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# GET /v1/intents/{id}/history - Get Execution History (Story 5.7)
# =============================================================================

@router.get("/{intent_id}/history", response_model=List[IntentExecutionResponse])
def get_intent_history(
    intent_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="Maximum results (default 50, max 100)"),
    offset: int = Query(0, ge=0, description="Results to skip")
):
    """
    Get execution history for an intent (Story 5.7).

    Returns execution records ordered by executed_at DESC.
    Used by Annie Dashboard/Admin to view audit trail of when and how triggers were fired.
    """
    logger.info(
        "[intents.api.history] intent_id=%s limit=%d offset=%d",
        intent_id, limit, offset
    )

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.history] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.get_intent_history(intent_id, limit=limit, offset=offset)

        if not result.success:
            if result.errors and "not found" in result.errors[0].lower():
                logger.info("[intents.api.history] intent_id=%s not_found", intent_id)
                raise HTTPException(status_code=404, detail="Intent not found")
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Unknown error")

        logger.info("[intents.api.history] intent_id=%s count=%d", intent_id, len(result.executions or []))

        return [execution.model_dump(mode='json') for execution in (result.executions or [])]

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.history] intent_id=%s database_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.history] intent_id=%s unexpected_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# GET /v1/intents/{id} - Get Single Intent (AC3)
# =============================================================================

@router.get("/{intent_id}", response_model=ScheduledIntentResponse)
def get_intent(intent_id: UUID):
    """
    Get a single scheduled intent by ID.

    Returns 404 if intent not found.
    """
    logger.info("[intents.api.get] intent_id=%s", intent_id)

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.get] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.get_intent(intent_id)

        if not result.success:
            logger.info("[intents.api.get] intent_id=%s not_found", intent_id)
            raise HTTPException(status_code=404, detail="Intent not found")

        logger.info("[intents.api.get] intent_id=%s found", intent_id)

        return result.intent.model_dump(mode='json')

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.get] intent_id=%s database_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.get] intent_id=%s unexpected_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# PUT /v1/intents/{id} - Update Intent (AC4)
# =============================================================================

@router.put("/{intent_id}", response_model=ScheduledIntentResponse)
def update_intent(intent_id: UUID, request: ScheduledIntentUpdate):
    """
    Update an existing scheduled intent.

    If trigger_schedule or trigger_type changes, recalculates next_check.
    Returns 404 if intent not found.
    """
    logger.info("[intents.api.update] intent_id=%s", intent_id)

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.update] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.update_intent(intent_id, request)

        if not result.success:
            if result.errors and "not found" in result.errors[0].lower():
                logger.info("[intents.api.update] intent_id=%s not_found", intent_id)
                raise HTTPException(status_code=404, detail="Intent not found")
            # Return 400 for validation errors (e.g., incompatible trigger_type/schedule)
            logger.warning("[intents.api.update] intent_id=%s validation_failed errors=%s", intent_id, result.errors)
            return JSONResponse(
                status_code=400,
                content={"errors": result.errors}
            )

        logger.info("[intents.api.update] intent_id=%s updated", intent_id)

        return result.intent.model_dump(mode='json')

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.update] intent_id=%s database_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.update] intent_id=%s unexpected_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)


# =============================================================================
# DELETE /v1/intents/{id} - Delete Intent (AC5)
# =============================================================================

@router.delete("/{intent_id}", status_code=204)
def delete_intent(intent_id: UUID):
    """
    Delete a scheduled intent by ID.

    CASCADE deletes related intent_executions records.
    Returns 404 if intent not found.
    Returns 204 on success.
    """
    logger.info("[intents.api.delete] intent_id=%s", intent_id)

    conn = None
    try:
        conn = get_timescale_conn()
        if conn is None:
            logger.error("[intents.api.delete] database_unavailable")
            raise HTTPException(status_code=500, detail="Database connection unavailable")

        service = IntentService(conn)
        result = service.delete_intent(intent_id)

        if not result.success:
            logger.info("[intents.api.delete] intent_id=%s not_found", intent_id)
            raise HTTPException(status_code=404, detail="Intent not found")

        logger.info("[intents.api.delete] intent_id=%s deleted", intent_id)

        return Response(status_code=204)

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error("[intents.api.delete] intent_id=%s database_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error("[intents.api.delete] intent_id=%s unexpected_error=%s", intent_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    finally:
        if conn is not None:
            release_timescale_conn(conn)
