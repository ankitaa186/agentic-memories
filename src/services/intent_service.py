"""
Intent Service for Scheduled Intents API (Story 5.4)

Provides business logic for CRUD operations on scheduled intents.
Handles next_check calculation, validation integration, and database operations.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import json

from croniter import croniter

from src.schemas import (
    ScheduledIntentCreate,
    ScheduledIntentUpdate,
    ScheduledIntentResponse,
    TriggerSchedule,
    TriggerCondition,
    IntentFireRequest,
    IntentFireResponse,
    IntentExecutionResponse,
)
from src.services.intent_validation import IntentValidationService, ValidationResult

logger = logging.getLogger("agentic_memories.intent_service")


@dataclass
class IntentServiceResult:
    """Result of an intent service operation.

    Attributes:
        success: True if operation succeeded
        intent: The intent data if successful
        errors: List of error messages if failed
    """
    success: bool
    intent: Optional[ScheduledIntentResponse] = None
    intents: Optional[List[ScheduledIntentResponse]] = None
    errors: Optional[List[str]] = None


@dataclass
class IntentFireResult:
    """Result of firing an intent (Story 5.6).

    Attributes:
        success: True if operation succeeded
        response: The fire response with updated state
        errors: List of error messages if failed
    """
    success: bool
    response: Optional[IntentFireResponse] = None
    errors: Optional[List[str]] = None


@dataclass
class IntentHistoryResult:
    """Result of getting intent execution history (Story 5.7).

    Attributes:
        success: True if operation succeeded
        executions: List of execution records
        errors: List of error messages if failed
    """
    success: bool
    executions: Optional[List[IntentExecutionResponse]] = None
    errors: Optional[List[str]] = None


class IntentService:
    """Service for managing scheduled intents.

    Handles CRUD operations with validation and next_check calculation.
    Uses dependency injection for database connection.

    Usage:
        from src.dependencies.timescale import get_timescale_conn

        conn = get_timescale_conn()
        service = IntentService(conn)
        result = service.create_intent(intent_create_request)

        if not result.success:
            return {"errors": result.errors}, 400
    """

    def __init__(self, conn):
        """Initialize intent service with database connection.

        Args:
            conn: PostgreSQL connection for database operations
        """
        self._conn = conn
        self._validator = IntentValidationService(conn)

    def create_intent(self, intent: ScheduledIntentCreate) -> IntentServiceResult:
        """Create a new scheduled intent with validation.

        Validates the intent, calculates initial next_check, and inserts into database.

        Args:
            intent: The intent creation request

        Returns:
            IntentServiceResult with created intent or validation errors
        """
        # Validate the intent
        validation_result = self._validator.validate(intent)
        if not validation_result.is_valid:
            logger.warning(
                "[intent.service.create] user_id=%s validation_failed errors=%d",
                intent.user_id, len(validation_result.errors)
            )
            return IntentServiceResult(success=False, errors=validation_result.errors)

        # Calculate initial next_check
        next_check = self._calculate_initial_next_check(
            intent.trigger_type,
            intent.trigger_schedule
        )

        try:
            with self._conn.cursor() as cur:
                # Serialize schedule and condition to JSON
                # Use mode='json' to properly serialize datetime objects
                trigger_schedule_json = None
                if intent.trigger_schedule:
                    trigger_schedule_json = json.dumps(intent.trigger_schedule.model_dump(mode='json', exclude_none=True))

                trigger_condition_json = None
                if intent.trigger_condition:
                    trigger_condition_json = json.dumps(intent.trigger_condition.model_dump(mode='json', exclude_none=True))

                metadata_json = json.dumps(intent.metadata, default=str) if intent.metadata else '{}'

                cur.execute(
                    """
                    INSERT INTO scheduled_intents (
                        user_id, intent_name, description,
                        trigger_type, trigger_schedule, trigger_condition,
                        action_type, action_context, action_priority,
                        next_check, expires_at, max_executions,
                        created_by, metadata
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    ) RETURNING *
                    """,
                    (
                        intent.user_id,
                        intent.intent_name,
                        intent.description,
                        intent.trigger_type,
                        trigger_schedule_json,
                        trigger_condition_json,
                        intent.action_type,
                        intent.action_context,
                        intent.action_priority,
                        next_check,
                        intent.expires_at,
                        intent.max_executions,
                        intent.user_id,  # created_by = user_id
                        metadata_json,
                    )
                )

                row = cur.fetchone()
                self._conn.commit()

                response = self._row_to_response(row)

                logger.info(
                    "[intent.service.create] user_id=%s intent_id=%s trigger_type=%s next_check=%s",
                    intent.user_id, response.id, intent.trigger_type, next_check
                )

                return IntentServiceResult(success=True, intent=response)

        except Exception as e:
            logger.error("[intent.service.create] user_id=%s error=%s", intent.user_id, e)
            self._conn.rollback()
            return IntentServiceResult(success=False, errors=[f"Database error: {str(e)}"])

    def list_intents(
        self,
        user_id: str,
        trigger_type: Optional[str] = None,
        enabled: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> IntentServiceResult:
        """List intents for a user with optional filters.

        Args:
            user_id: The user ID to filter by (required)
            trigger_type: Optional filter by trigger type
            enabled: Optional filter by enabled status
            limit: Maximum number of results (default 50)
            offset: Number of results to skip (default 0)

        Returns:
            IntentServiceResult with list of intents
        """
        try:
            with self._conn.cursor() as cur:
                # Build query with optional filters
                query = """
                    SELECT * FROM scheduled_intents
                    WHERE user_id = %s
                """
                params: List[Any] = [user_id]

                if trigger_type is not None:
                    query += " AND trigger_type = %s"
                    params.append(trigger_type)

                if enabled is not None:
                    query += " AND enabled = %s"
                    params.append(enabled)

                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, tuple(params))
                rows = cur.fetchall()

                intents = [self._row_to_response(row) for row in rows]

                logger.info(
                    "[intent.service.list] user_id=%s count=%d trigger_type=%s enabled=%s",
                    user_id, len(intents), trigger_type, enabled
                )

                return IntentServiceResult(success=True, intents=intents)

        except Exception as e:
            logger.error("[intent.service.list] user_id=%s error=%s", user_id, e)
            return IntentServiceResult(success=False, errors=[f"Database error: {str(e)}"])

    def get_intent(self, intent_id: UUID) -> IntentServiceResult:
        """Get a single intent by ID.

        Args:
            intent_id: The intent UUID

        Returns:
            IntentServiceResult with intent or not found error
        """
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM scheduled_intents WHERE id = %s",
                    (str(intent_id),)
                )
                row = cur.fetchone()

                if row is None:
                    logger.info("[intent.service.get] intent_id=%s not_found", intent_id)
                    return IntentServiceResult(success=False, errors=["Intent not found"])

                response = self._row_to_response(row)

                logger.info("[intent.service.get] intent_id=%s found", intent_id)

                return IntentServiceResult(success=True, intent=response)

        except Exception as e:
            logger.error("[intent.service.get] intent_id=%s error=%s", intent_id, e)
            return IntentServiceResult(success=False, errors=[f"Database error: {str(e)}"])

    def update_intent(self, intent_id: UUID, update: ScheduledIntentUpdate) -> IntentServiceResult:
        """Update an existing intent.

        If trigger_schedule or trigger_type changes, recalculates next_check.

        Args:
            intent_id: The intent UUID
            update: The update request with optional fields

        Returns:
            IntentServiceResult with updated intent or error
        """
        try:
            with self._conn.cursor() as cur:
                # First get the existing intent
                cur.execute(
                    "SELECT * FROM scheduled_intents WHERE id = %s",
                    (str(intent_id),)
                )
                existing = cur.fetchone()

                if existing is None:
                    logger.info("[intent.service.update] intent_id=%s not_found", intent_id)
                    return IntentServiceResult(success=False, errors=["Intent not found"])

                # Build merged state for validation
                new_trigger_type = update.trigger_type or existing["trigger_type"]
                new_trigger_schedule = None
                new_trigger_condition = None

                # Merge trigger_schedule
                if update.trigger_schedule is not None:
                    new_trigger_schedule = update.trigger_schedule
                elif existing["trigger_schedule"]:
                    new_trigger_schedule = TriggerSchedule(**existing["trigger_schedule"])

                # Merge trigger_condition
                if update.trigger_condition is not None:
                    new_trigger_condition = update.trigger_condition
                elif existing["trigger_condition"]:
                    new_trigger_condition = TriggerCondition(**existing["trigger_condition"])

                # Build merged ScheduledIntentCreate for full validation
                merged_intent = ScheduledIntentCreate(
                    user_id=existing["user_id"],
                    intent_name=update.intent_name or existing["intent_name"],
                    description=update.description if update.description is not None else existing.get("description"),
                    trigger_type=new_trigger_type,
                    trigger_schedule=new_trigger_schedule,
                    trigger_condition=new_trigger_condition,
                    action_type=update.action_type or existing["action_type"],
                    action_context=update.action_context or existing["action_context"],
                    action_priority=update.action_priority or existing["action_priority"],
                    expires_at=update.expires_at if update.expires_at is not None else existing.get("expires_at"),
                    max_executions=update.max_executions if update.max_executions is not None else existing.get("max_executions"),
                    metadata=update.metadata if update.metadata is not None else existing.get("metadata"),
                )

                # Run full validation on merged state
                # Use validator without db connection to skip trigger count check for updates
                # (user already has the trigger, we're just modifying it)
                update_validator = IntentValidationService(conn=None)
                validation_result = update_validator.validate(merged_intent)
                if not validation_result.is_valid:
                    logger.warning(
                        "[intent.service.update] intent_id=%s validation_failed errors=%d",
                        intent_id, len(validation_result.errors)
                    )
                    return IntentServiceResult(success=False, errors=validation_result.errors)

                # Determine if schedule changed (need to recalculate next_check)
                schedule_changed = False
                if update.trigger_type and update.trigger_type != existing["trigger_type"]:
                    schedule_changed = True
                if update.trigger_schedule is not None:
                    schedule_changed = True

                # Calculate new next_check if schedule changed
                new_next_check = None
                if schedule_changed and new_trigger_schedule:
                    new_next_check = self._calculate_initial_next_check(
                        new_trigger_type,
                        new_trigger_schedule
                    )

                # Build dynamic UPDATE query
                set_clauses = ["updated_at = NOW()"]
                params: List[Any] = []

                if update.intent_name is not None:
                    set_clauses.append("intent_name = %s")
                    params.append(update.intent_name)

                if update.description is not None:
                    set_clauses.append("description = %s")
                    params.append(update.description)

                if update.trigger_type is not None:
                    set_clauses.append("trigger_type = %s")
                    params.append(update.trigger_type)

                if update.trigger_schedule is not None:
                    set_clauses.append("trigger_schedule = %s")
                    params.append(json.dumps(update.trigger_schedule.model_dump(mode='json', exclude_none=True)))

                if update.trigger_condition is not None:
                    set_clauses.append("trigger_condition = %s")
                    params.append(json.dumps(update.trigger_condition.model_dump(mode='json', exclude_none=True)))

                if update.action_type is not None:
                    set_clauses.append("action_type = %s")
                    params.append(update.action_type)

                if update.action_context is not None:
                    set_clauses.append("action_context = %s")
                    params.append(update.action_context)

                if update.action_priority is not None:
                    set_clauses.append("action_priority = %s")
                    params.append(update.action_priority)

                if update.enabled is not None:
                    set_clauses.append("enabled = %s")
                    params.append(update.enabled)

                if update.expires_at is not None:
                    set_clauses.append("expires_at = %s")
                    params.append(update.expires_at)

                if update.max_executions is not None:
                    set_clauses.append("max_executions = %s")
                    params.append(update.max_executions)

                if update.metadata is not None:
                    set_clauses.append("metadata = %s")
                    params.append(json.dumps(update.metadata, default=str))

                if new_next_check is not None:
                    set_clauses.append("next_check = %s")
                    params.append(new_next_check)

                # Add intent_id to params
                params.append(str(intent_id))

                query = f"""
                    UPDATE scheduled_intents
                    SET {', '.join(set_clauses)}
                    WHERE id = %s
                    RETURNING *
                """

                cur.execute(query, tuple(params))
                row = cur.fetchone()
                self._conn.commit()

                response = self._row_to_response(row)

                logger.info(
                    "[intent.service.update] intent_id=%s schedule_changed=%s next_check=%s",
                    intent_id, schedule_changed, response.next_check
                )

                return IntentServiceResult(success=True, intent=response)

        except Exception as e:
            logger.error("[intent.service.update] intent_id=%s error=%s", intent_id, e)
            self._conn.rollback()
            return IntentServiceResult(success=False, errors=[f"Database error: {str(e)}"])

    def delete_intent(self, intent_id: UUID) -> IntentServiceResult:
        """Delete an intent by ID.

        CASCADE will automatically delete related intent_executions.

        Args:
            intent_id: The intent UUID

        Returns:
            IntentServiceResult with success or not found error
        """
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM scheduled_intents WHERE id = %s RETURNING id",
                    (str(intent_id),)
                )
                row = cur.fetchone()

                if row is None:
                    logger.info("[intent.service.delete] intent_id=%s not_found", intent_id)
                    return IntentServiceResult(success=False, errors=["Intent not found"])

                self._conn.commit()

                logger.info("[intent.service.delete] intent_id=%s deleted", intent_id)

                return IntentServiceResult(success=True)

        except Exception as e:
            logger.error("[intent.service.delete] intent_id=%s error=%s", intent_id, e)
            self._conn.rollback()
            return IntentServiceResult(success=False, errors=[f"Database error: {str(e)}"])

    def get_pending_intents(
        self,
        user_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> IntentServiceResult:
        """Get pending intents that are due for execution (Story 5.5).

        Returns intents where enabled = true AND next_check <= NOW().
        Used by Annie's proactive worker to poll for triggers to evaluate.

        Multi-worker Safety:
            Uses FOR UPDATE SKIP LOCKED to prevent multiple workers from
            picking up the same intent simultaneously. Each worker should:
            1. Call get_pending_intents(limit=N) to get a batch
            2. Process each intent with fire_intent()
            3. Repeat

            Note: The row lock is only held during this query. For full
            protection against duplicate execution, workers should also
            check last_checked timestamp or use external locking (Redis).

        Args:
            user_id: Optional filter to get pending intents for a specific user.
                     If None, returns all users' pending intents.
            limit: Optional limit on number of intents to return.
                   Recommended for multi-worker setups to reduce contention.

        Returns:
            IntentServiceResult with list of pending intents ordered by next_check ASC
        """
        try:
            with self._conn.cursor() as cur:
                # Build query - uses idx_intents_pending partial index
                # FOR UPDATE SKIP LOCKED prevents multiple workers from
                # picking up the same pending intent simultaneously
                query = """
                    SELECT * FROM scheduled_intents
                    WHERE enabled = true
                      AND next_check IS NOT NULL
                      AND next_check <= NOW()
                """
                params: List[Any] = []

                # Add optional user_id filter
                if user_id is not None:
                    query += " AND user_id = %s"
                    params.append(user_id)

                # Order by next_check ASC (oldest/most overdue first)
                query += " ORDER BY next_check ASC"

                # Add limit if specified (recommended for multi-worker setups)
                if limit is not None:
                    query += " LIMIT %s"
                    params.append(limit)

                # FOR UPDATE SKIP LOCKED: lock rows and skip already-locked ones
                query += " FOR UPDATE SKIP LOCKED"

                cur.execute(query, tuple(params) if params else None)
                rows = cur.fetchall()

                intents = [self._row_to_response(row) for row in rows]

                logger.info(
                    "[intent.service.pending] user_id=%s count=%d",
                    user_id, len(intents)
                )

                return IntentServiceResult(success=True, intents=intents)

        except Exception as e:
            logger.error("[intent.service.pending] user_id=%s error=%s", user_id, e)
            return IntentServiceResult(success=False, errors=[f"Database error: {str(e)}"])

    def fire_intent(
        self,
        intent_id: UUID,
        request: IntentFireRequest
    ) -> IntentFireResult:
        """Report execution result and update intent state (Story 5.6).

        Updates last_checked, last_executed (on success), calculates next_check,
        handles auto-disable, and logs to intent_executions table.

        Args:
            intent_id: The intent UUID
            request: The fire request with execution results

        Returns:
            IntentFireResult with updated state or errors
        """
        try:
            with self._conn.cursor() as cur:
                # Get existing intent
                cur.execute(
                    "SELECT * FROM scheduled_intents WHERE id = %s",
                    (str(intent_id),)
                )
                row = cur.fetchone()

                if row is None:
                    logger.info("[intent.service.fire] intent_id=%s not_found", intent_id)
                    return IntentFireResult(success=False, errors=["Intent not found"])

                intent = self._row_to_response(row)
                now = datetime.now(timezone.utc)

                # Always update last_checked (AC2)
                new_last_checked = now

                # Update execution state on success (AC3)
                new_last_executed = intent.last_executed
                new_execution_count = intent.execution_count
                new_last_execution_status = request.status
                new_last_message_id = intent.last_message_id
                new_last_execution_error = request.error_message

                if request.status == "success":
                    new_last_executed = now
                    new_execution_count = intent.execution_count + 1
                    new_last_message_id = request.message_id

                # Calculate next_check based on trigger type and result (AC4)
                trigger_schedule = None
                if intent.trigger_schedule:
                    if isinstance(intent.trigger_schedule, dict):
                        trigger_schedule = TriggerSchedule(**intent.trigger_schedule)
                    else:
                        trigger_schedule = intent.trigger_schedule

                new_next_check = self._calculate_next_check_after_fire(
                    intent.trigger_type,
                    trigger_schedule,
                    request.status,
                    now
                )

                # Check auto-disable conditions (AC5)
                new_enabled = intent.enabled
                was_disabled_reason = None

                # Disable one-time triggers after success
                if intent.trigger_type == "once" and request.status == "success":
                    new_enabled = False
                    new_next_check = None
                    was_disabled_reason = "one-time trigger executed"

                # Disable if max_executions reached
                if intent.max_executions is not None and new_execution_count >= intent.max_executions:
                    new_enabled = False
                    was_disabled_reason = f"max_executions ({intent.max_executions}) reached"

                # Disable if expires_at passed
                if intent.expires_at is not None and now >= intent.expires_at:
                    new_enabled = False
                    was_disabled_reason = "expires_at passed"

                # Update intent record in database (AC2, AC3, AC4, AC5)
                cur.execute(
                    """
                    UPDATE scheduled_intents
                    SET last_checked = %s,
                        last_executed = %s,
                        execution_count = %s,
                        last_execution_status = %s,
                        last_execution_error = %s,
                        last_message_id = %s,
                        next_check = %s,
                        enabled = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        new_last_checked,
                        new_last_executed,
                        new_execution_count,
                        new_last_execution_status,
                        new_last_execution_error,
                        new_last_message_id,
                        new_next_check,
                        new_enabled,
                        str(intent_id),
                    )
                )

                # Log execution to intent_executions table (AC6)
                trigger_data_json = json.dumps(request.trigger_data) if request.trigger_data else None
                gate_result_json = json.dumps(request.gate_result) if request.gate_result else None

                cur.execute(
                    """
                    INSERT INTO intent_executions (
                        intent_id, user_id, executed_at, trigger_type, trigger_data,
                        status, gate_result, message_id, message_preview,
                        evaluation_ms, generation_ms, delivery_ms, error_message
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        str(intent_id),
                        intent.user_id,
                        now,
                        intent.trigger_type,
                        trigger_data_json,
                        request.status,
                        gate_result_json,
                        request.message_id,
                        request.message_preview,
                        request.evaluation_ms,
                        request.generation_ms,
                        request.delivery_ms,
                        request.error_message,
                    )
                )

                self._conn.commit()

                # Build response
                response = IntentFireResponse(
                    intent_id=intent_id,
                    status=request.status,
                    next_check=new_next_check,
                    enabled=new_enabled,
                    execution_count=new_execution_count,
                    was_disabled_reason=was_disabled_reason,
                )

                logger.info(
                    "[intent.service.fire] intent_id=%s status=%s next_check=%s enabled=%s exec_count=%d disabled_reason=%s",
                    intent_id, request.status, new_next_check, new_enabled, new_execution_count, was_disabled_reason
                )

                return IntentFireResult(success=True, response=response)

        except Exception as e:
            logger.error("[intent.service.fire] intent_id=%s error=%s", intent_id, e)
            self._conn.rollback()
            return IntentFireResult(success=False, errors=[f"Database error: {str(e)}"])

    def get_intent_history(
        self,
        intent_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> IntentHistoryResult:
        """Get execution history for an intent (Story 5.7).

        Returns execution records ordered by executed_at DESC.
        Used by Annie Dashboard/Admin to view audit trail.

        Args:
            intent_id: The intent UUID
            limit: Maximum number of results (default 50, max 100)
            offset: Number of results to skip (default 0)

        Returns:
            IntentHistoryResult with list of executions or errors
        """
        # Enforce max limit
        limit = min(limit, 100)

        try:
            with self._conn.cursor() as cur:
                # First verify intent exists (AC5)
                cur.execute(
                    "SELECT id FROM scheduled_intents WHERE id = %s",
                    (str(intent_id),)
                )
                if cur.fetchone() is None:
                    logger.info("[intent.service.history] intent_id=%s not_found", intent_id)
                    return IntentHistoryResult(success=False, errors=["Intent not found"])

                # Query execution history (AC1, AC2, AC3, AC4)
                cur.execute(
                    """
                    SELECT id, intent_id, user_id, executed_at, trigger_type,
                           trigger_data, status, gate_result, message_id,
                           message_preview, evaluation_ms, generation_ms,
                           delivery_ms, error_message
                    FROM intent_executions
                    WHERE intent_id = %s
                    ORDER BY executed_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (str(intent_id), limit, offset)
                )
                rows = cur.fetchall()

                executions = [self._execution_row_to_response(row) for row in rows]

                logger.info(
                    "[intent.service.history] intent_id=%s count=%d limit=%d offset=%d",
                    intent_id, len(executions), limit, offset
                )

                return IntentHistoryResult(success=True, executions=executions)

        except Exception as e:
            logger.error("[intent.service.history] intent_id=%s error=%s", intent_id, e)
            return IntentHistoryResult(success=False, errors=[f"Database error: {str(e)}"])

    def _calculate_next_check_after_fire(
        self,
        trigger_type: str,
        trigger_schedule: Optional[TriggerSchedule],
        status: str,
        now: datetime
    ) -> Optional[datetime]:
        """Calculate next_check after firing based on trigger type and result (Story 5.6).

        Args:
            trigger_type: The type of trigger
            trigger_schedule: The schedule configuration
            status: The execution status (success, failed, gate_blocked, condition_not_met)
            now: Current timestamp

        Returns:
            The calculated next_check datetime, or None for one-time triggers
        """
        # Handle failure states with backoff (AC4)
        if status == "failed":
            return now + timedelta(minutes=15)
        elif status in ("gate_blocked", "condition_not_met"):
            return now + timedelta(minutes=5)

        # Handle success cases by trigger type
        if status == "success":
            if trigger_type == "cron" and trigger_schedule and trigger_schedule.cron:
                try:
                    cron = croniter(trigger_schedule.cron, now)
                    return cron.get_next(datetime)
                except Exception as e:
                    logger.warning("[intent.service.next_check_fire] cron_error=%s", e)
                    return now + timedelta(minutes=5)

            elif trigger_type == "interval" and trigger_schedule and trigger_schedule.interval_minutes:
                return now + timedelta(minutes=trigger_schedule.interval_minutes)

            elif trigger_type == "once":
                # One-time triggers: no next check after success
                return None

            elif trigger_type in ("price", "silence", "event", "calendar", "news"):
                # Condition-based triggers: use check_interval_minutes or default 5
                check_interval = 5  # default
                if trigger_schedule and trigger_schedule.check_interval_minutes:
                    check_interval = trigger_schedule.check_interval_minutes
                return now + timedelta(minutes=check_interval)

        # Default fallback
        return now + timedelta(minutes=5)

    def _validate_trigger_type_schedule_compatibility(
        self,
        trigger_type: str,
        trigger_schedule: TriggerSchedule
    ) -> List[str]:
        """Validate that trigger_type and trigger_schedule are compatible.

        This prevents inconsistent states when updating trigger_type without
        providing a compatible trigger_schedule.

        Args:
            trigger_type: The trigger type (cron, interval, once, etc.)
            trigger_schedule: The trigger schedule configuration

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if trigger_type == "cron":
            if not trigger_schedule.cron:
                errors.append(
                    "Cannot use trigger_type 'cron' without providing 'cron' expression in schedule"
                )

        elif trigger_type == "interval":
            if not trigger_schedule.interval_minutes:
                errors.append(
                    "Cannot use trigger_type 'interval' without providing 'interval_minutes' in schedule"
                )

        elif trigger_type == "once":
            if not trigger_schedule.trigger_at:
                errors.append(
                    "Cannot use trigger_type 'once' without providing 'trigger_at' in schedule"
                )

        # price, silence, event, calendar, news types only need check_interval_minutes
        # which has a default value, so no validation needed

        return errors

    def _calculate_initial_next_check(
        self,
        trigger_type: str,
        trigger_schedule: Optional[TriggerSchedule]
    ) -> Optional[datetime]:
        """Calculate initial next_check based on trigger type.

        Args:
            trigger_type: The type of trigger
            trigger_schedule: The schedule configuration

        Returns:
            The calculated next_check datetime, or None if not applicable
        """
        now = datetime.now(timezone.utc)

        if trigger_type == "cron" and trigger_schedule and trigger_schedule.cron:
            try:
                cron = croniter(trigger_schedule.cron, now)
                return cron.get_next(datetime)
            except Exception as e:
                logger.warning("[intent.service.next_check] cron_error=%s", e)
                return now

        elif trigger_type == "interval" and trigger_schedule and trigger_schedule.interval_minutes:
            return now + timedelta(minutes=trigger_schedule.interval_minutes)

        elif trigger_type == "once" and trigger_schedule and trigger_schedule.trigger_at:
            return trigger_schedule.trigger_at

        elif trigger_type in ("price", "silence", "event", "calendar", "news"):
            # Condition-based triggers: check immediately
            return now

        # Default: no next_check
        return None

    def _row_to_response(self, row: Dict[str, Any]) -> ScheduledIntentResponse:
        """Convert a database row to a ScheduledIntentResponse.

        Note: Connection pool is configured with dict_row factory, so rows
        are always dictionaries. No tuple fallback needed.

        Args:
            row: The database row (dict from dict_row cursor)

        Returns:
            ScheduledIntentResponse instance
        """
        return ScheduledIntentResponse(
            id=row["id"],
            user_id=row["user_id"],
            intent_name=row["intent_name"],
            description=row.get("description"),
            trigger_type=row["trigger_type"],
            trigger_schedule=row.get("trigger_schedule"),
            trigger_condition=row.get("trigger_condition"),
            action_type=row["action_type"],
            action_context=row["action_context"],
            action_priority=row["action_priority"],
            next_check=row.get("next_check"),
            last_checked=row.get("last_checked"),
            last_executed=row.get("last_executed"),
            execution_count=row.get("execution_count", 0),
            last_execution_status=row.get("last_execution_status"),
            last_execution_error=row.get("last_execution_error"),
            last_message_id=row.get("last_message_id"),
            enabled=row.get("enabled", True),
            expires_at=row.get("expires_at"),
            max_executions=row.get("max_executions"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row.get("created_by"),
            metadata=row.get("metadata"),
        )

    def _execution_row_to_response(self, row: Dict[str, Any]) -> IntentExecutionResponse:
        """Convert an intent_executions database row to IntentExecutionResponse.

        Note: Connection pool is configured with dict_row factory, so rows
        are always dictionaries. No tuple fallback needed.

        Args:
            row: The database row (dict from dict_row cursor)

        Returns:
            IntentExecutionResponse instance
        """
        return IntentExecutionResponse(
            id=row["id"],
            intent_id=row["intent_id"],
            user_id=row["user_id"],
            executed_at=row["executed_at"],
            trigger_type=row["trigger_type"],
            trigger_data=row.get("trigger_data"),
            status=row["status"],
            gate_result=row.get("gate_result"),
            message_id=row.get("message_id"),
            message_preview=row.get("message_preview"),
            evaluation_ms=row.get("evaluation_ms"),
            generation_ms=row.get("generation_ms"),
            delivery_ms=row.get("delivery_ms"),
            error_message=row.get("error_message"),
        )
