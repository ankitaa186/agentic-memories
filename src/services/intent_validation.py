"""
Intent Validation Service for Scheduled Intents API (Story 5.3)

Validates scheduled intent creation requests before database mutations.
Collects all validation errors without short-circuiting for better UX.

Validation Rules:
- AC1: Max 25 active triggers per user
- AC2: Cron minimum interval 60 seconds
- AC3: Cron max 96 fires per day
- AC4: Interval minimum 5 minutes
- AC5: One-time triggers must be in the future
- AC6: Required fields by trigger type
- AC7: Return all errors in single response
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import logging
import re

from croniter import croniter

from src.schemas import ScheduledIntentCreate, TriggerSchedule, TriggerCondition

if TYPE_CHECKING:
    from psycopg import Connection

logger = logging.getLogger("agentic_memories.intent_validation")

# Validation constants
MAX_TRIGGERS_PER_USER = 25
CRON_MIN_INTERVAL_SECONDS = 60
CRON_MAX_FIRES_PER_DAY = 96
INTERVAL_MIN_MINUTES = 5

# Required fields mapping by trigger type
# Note: price and silence can use EITHER structured fields OR expression (Story 6.2)
REQUIRED_FIELDS = {
    "cron": {"schedule": ["cron"]},
    "interval": {"schedule": ["interval_minutes"]},
    "once": {"schedule": ["trigger_at"]},
    "price": {"condition": []},  # Accepts ticker/operator/value OR expression
    "silence": {"condition": []},  # Accepts threshold_hours OR expression
    "portfolio": {"condition": []},  # Accepts expression only
}

# Expression validation patterns (Story 6.2)
# Price expression: TICKER OP VALUE (e.g., "NVDA < 130", "AAPL >= 200.50")
PRICE_EXPR_PATTERN = re.compile(r"^[A-Z]{1,5}\s*[<>=!]{1,2}\s*[0-9.]+$")

# Portfolio expression keywords
PORTFOLIO_KEYWORDS = {
    "any_holding_change",
    "any_holding_up",
    "any_holding_down",
    "total_value",
    "total_change",
}

# Portfolio expression patterns (Story 6.5 AC5.2)
# Percentage patterns: any_holding_change > 5%, total_change >= -10%
PORTFOLIO_PERCENTAGE_PATTERN = re.compile(
    r"^(any_holding_change|any_holding_down|any_holding_up|total_change)\s*(>|>=|<|<=)\s*(-?\d+(\.\d+)?)%$",
    re.IGNORECASE,
)
# Absolute value pattern: total_value >= 100000
PORTFOLIO_ABSOLUTE_PATTERN = re.compile(
    r"^total_value\s*(>|>=|<|<=)\s*(-?\d+(\.\d+)?)$", re.IGNORECASE
)

# Silence expression: inactive_hours > N
SILENCE_EXPR_PATTERN = re.compile(r"^inactive_hours\s*>\s*\d+$")


@dataclass
class ValidationResult:
    """Result of intent validation containing validity status and error messages.

    Attributes:
        is_valid: True if all validation checks passed
        errors: List of human-readable error messages for failed checks
    """

    is_valid: bool
    errors: List[str]


class IntentValidationService:
    """Validates scheduled intent creation requests.

    This service runs all validation checks before any database mutations.
    It collects all errors without short-circuiting to provide complete
    feedback to the caller.

    Usage:
        from src.dependencies.timescale import get_timescale_conn

        conn = get_timescale_conn()
        service = IntentValidationService(conn)
        result = service.validate(intent_create_request)

        if not result.is_valid:
            return {"errors": result.errors}, 400
    """

    def __init__(self, conn: Optional["Connection"] = None):
        """Initialize validation service with optional database connection.

        Args:
            conn: PostgreSQL connection for trigger count validation.
                  If None, trigger count validation will be skipped.
        """
        self._conn = conn

    def validate(self, intent: ScheduledIntentCreate) -> ValidationResult:
        """Validate a scheduled intent creation request.

        Runs all validation checks and collects errors without short-circuiting.
        This allows callers to receive all validation issues in a single response.

        Args:
            intent: The scheduled intent creation request to validate

        Returns:
            ValidationResult with is_valid=True if all checks pass,
            otherwise is_valid=False with list of error messages
        """
        errors: List[str] = []

        # AC1: Validate trigger count per user
        if self._conn is not None:
            count_errors = self._validate_trigger_count(intent.user_id)
            errors.extend(count_errors)

        # AC6: Validate required fields by trigger type (run first for better error ordering)
        required_errors = self._validate_required_fields(intent)
        errors.extend(required_errors)

        # AC2, AC3: Validate cron expression frequency and daily count
        if (
            intent.trigger_type == "cron"
            and intent.trigger_schedule
            and intent.trigger_schedule.cron
        ):
            cron_errors = self._validate_cron_frequency(intent.trigger_schedule.cron)
            errors.extend(cron_errors)

        # AC4: Validate interval minimum
        if intent.trigger_type == "interval":
            interval_errors = self._validate_interval(intent.trigger_schedule)
            errors.extend(interval_errors)

        # AC5: Validate one-time trigger is in future
        if intent.trigger_type == "once":
            once_errors = self._validate_once_trigger(intent.trigger_schedule)
            errors.extend(once_errors)

        # Epic 6 AC1.3: Validate timezone if present in trigger_schedule
        if intent.trigger_schedule and intent.trigger_schedule.timezone:
            timezone_errors = self._validate_timezone(intent.trigger_schedule.timezone)
            errors.extend(timezone_errors)

        # Epic 6 Story 6.2: Validate condition expression if present
        if intent.trigger_condition:
            expression_errors = self._validate_condition_expression(
                intent.trigger_type, intent.trigger_condition
            )
            errors.extend(expression_errors)

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(
                "[intent.validation] user_id=%s trigger_type=%s errors=%d",
                intent.user_id,
                intent.trigger_type,
                len(errors),
            )
        else:
            logger.info(
                "[intent.validation] user_id=%s trigger_type=%s valid=true",
                intent.user_id,
                intent.trigger_type,
            )

        return ValidationResult(is_valid=is_valid, errors=errors)

    def _validate_trigger_count(self, user_id: str) -> List[str]:
        """Validate user has not exceeded maximum trigger count (AC1).

        Queries the scheduled_intents table to count existing enabled triggers.
        Uses idx_intents_user_enabled index for efficient lookup.

        Args:
            user_id: The user ID to check

        Returns:
            List with error message if limit exceeded, empty list otherwise
        """
        errors: List[str] = []

        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM scheduled_intents
                    WHERE user_id = %s AND enabled = true
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                count = row["count"] if row else 0

                if count >= MAX_TRIGGERS_PER_USER:
                    errors.append(
                        f"Limit reached: {MAX_TRIGGERS_PER_USER} active triggers max"
                    )
                    logger.info(
                        "[intent.validation.count] user_id=%s count=%d limit=%d exceeded=true",
                        user_id,
                        count,
                        MAX_TRIGGERS_PER_USER,
                    )
        except Exception as e:
            logger.error("[intent.validation.count] user_id=%s error=%s", user_id, e)
            # Don't fail validation on DB error - let creation attempt handle it

        return errors

    def _validate_cron_frequency(self, cron_expression: str) -> List[str]:
        """Validate cron expression frequency constraints (AC2, AC3).

        AC2: Checks that cron fires at least 60 seconds apart
        AC3: Checks that cron fires at most 96 times per day

        Args:
            cron_expression: The cron expression to validate

        Returns:
            List of error messages for any violated constraints
        """
        errors: List[str] = []

        try:
            base_time = datetime.now(timezone.utc)
            cron = croniter(cron_expression, base_time)

            # AC2: Calculate interval between first two occurrences
            first = cron.get_next(datetime)
            second = cron.get_next(datetime)
            delta_seconds = (second - first).total_seconds()

            if delta_seconds < CRON_MIN_INTERVAL_SECONDS:
                errors.append(
                    f"Cron too frequent: every {int(delta_seconds)}s. Minimum: {CRON_MIN_INTERVAL_SECONDS}s"
                )

            # AC3: Count occurrences in 24 hours
            # Reset iterator and count fires in a day
            cron = croniter(cron_expression, base_time)
            end_time = base_time + timedelta(hours=24)
            fire_count = 0

            while True:
                next_fire = cron.get_next(datetime)
                if next_fire > end_time:
                    break
                fire_count += 1
                # Safety limit to prevent infinite loop
                if fire_count > 2000:
                    break

            if fire_count > CRON_MAX_FIRES_PER_DAY:
                errors.append(
                    f"Cron would fire {fire_count}x/day. Max: {CRON_MAX_FIRES_PER_DAY}"
                )

        except Exception as e:
            errors.append(f"Invalid cron expression: {e}")
            logger.warning(
                "[intent.validation.cron] expression=%s error=%s", cron_expression, e
            )

        return errors

    def _validate_interval(
        self, trigger_schedule: Optional[TriggerSchedule]
    ) -> List[str]:
        """Validate interval trigger meets minimum duration (AC4).

        Note: Pydantic already validates check_interval_minutes >= 5,
        but interval_minutes needs explicit validation here.

        Args:
            trigger_schedule: The trigger schedule containing interval_minutes

        Returns:
            List with error message if interval too short, empty list otherwise
        """
        errors: List[str] = []

        if trigger_schedule is None or trigger_schedule.interval_minutes is None:
            # Required fields validation will catch missing interval_minutes
            return errors

        interval = trigger_schedule.interval_minutes
        if interval < INTERVAL_MIN_MINUTES:
            errors.append(
                f"Interval too short: {interval}m. Minimum: {INTERVAL_MIN_MINUTES}m"
            )

        return errors

    def _validate_once_trigger(
        self, trigger_schedule: Optional[TriggerSchedule]
    ) -> List[str]:
        """Validate one-time trigger is scheduled in the future (AC5).

        Handles timezone-aware comparisons correctly.

        Args:
            trigger_schedule: The trigger schedule containing trigger_at

        Returns:
            List with error message if trigger_at is in past, empty list otherwise
        """
        errors: List[str] = []

        if trigger_schedule is None or trigger_schedule.trigger_at is None:
            # Required fields validation will catch missing trigger_at
            return errors

        trigger_at = trigger_schedule.trigger_at
        now = datetime.now(timezone.utc)

        # Handle timezone-naive datetimes by assuming UTC
        if trigger_at.tzinfo is None:
            trigger_at = trigger_at.replace(tzinfo=timezone.utc)

        if trigger_at <= now:
            errors.append("One-time trigger must be in the future")

        return errors

    def _validate_required_fields(self, intent: ScheduledIntentCreate) -> List[str]:
        """Validate required fields are present based on trigger type (AC6).

        Different trigger types require different fields:
        - cron: trigger_schedule.cron
        - interval: trigger_schedule.interval_minutes
        - once: trigger_schedule.trigger_at
        - price: trigger_condition.ticker, operator, value
        - silence: trigger_condition.threshold_hours
        - portfolio: trigger_condition.expression (Epic 6)

        Args:
            intent: The scheduled intent to validate

        Returns:
            List of error messages for missing required fields
        """
        errors: List[str] = []
        trigger_type = intent.trigger_type

        if trigger_type not in REQUIRED_FIELDS:
            logger.warning(
                "[intent.validation.required] unknown trigger_type=%s", trigger_type
            )
            return errors

        requirements = REQUIRED_FIELDS[trigger_type]

        # Check schedule fields
        if "schedule" in requirements:
            for field in requirements["schedule"]:
                if intent.trigger_schedule is None:
                    errors.append(
                        f"trigger_schedule.{field} required for type '{trigger_type}'"
                    )
                elif getattr(intent.trigger_schedule, field, None) is None:
                    errors.append(
                        f"trigger_schedule.{field} required for type '{trigger_type}'"
                    )

        # Check condition fields
        if "condition" in requirements:
            for field in requirements["condition"]:
                if intent.trigger_condition is None:
                    errors.append(
                        f"trigger_condition.{field} required for type '{trigger_type}'"
                    )
                elif getattr(intent.trigger_condition, field, None) is None:
                    errors.append(
                        f"trigger_condition.{field} required for type '{trigger_type}'"
                    )

        return errors

    def _validate_timezone(self, tz: str) -> List[str]:
        """Validate IANA timezone string (Epic 6 AC1.3).

        Uses Python's zoneinfo module to validate timezone strings.
        Valid timezones include 'America/Los_Angeles', 'Europe/London', 'UTC', etc.

        Args:
            tz: The timezone string to validate

        Returns:
            List with error message if invalid, empty list otherwise
        """
        errors: List[str] = []

        if not tz:
            errors.append(
                "timezone cannot be empty. Use IANA format (e.g., 'America/Los_Angeles')"
            )
            return errors

        try:
            ZoneInfo(tz)
            logger.debug("[intent.validation.timezone] tz=%s valid=true", tz)
        except ZoneInfoNotFoundError:
            errors.append(
                f"Invalid timezone: {tz}. Use IANA format (e.g., 'America/Los_Angeles')"
            )
            logger.info("[intent.validation.timezone] tz=%s valid=false", tz)

        return errors

    def _validate_condition_expression(
        self, trigger_type: str, condition: TriggerCondition
    ) -> List[str]:
        """Validate condition expression format (Epic 6 Story 6.2 AC2.3, AC2.4).

        Validates expression format based on condition_type or trigger_type.
        Only checks format - actual evaluation happens in Annie.

        Args:
            trigger_type: The trigger type (price, portfolio, silence)
            condition: The trigger condition with optional expression

        Returns:
            List of error messages for invalid expressions, empty list otherwise
        """
        errors: List[str] = []

        # Skip if no expression provided (backward compatibility with structured fields)
        if not condition.expression:
            return errors

        # Determine condition type from explicit field or trigger_type
        cond_type = condition.condition_type or trigger_type

        # Warn if both expression and structured fields are provided
        has_structured_price = (
            condition.ticker is not None
            or condition.operator is not None
            or condition.value is not None
        )
        has_structured_silence = condition.threshold_hours is not None

        if condition.expression and (has_structured_price or has_structured_silence):
            logger.warning(
                "[intent.validation.expression] Both expression and structured fields provided. "
                "Expression takes precedence. trigger_type=%s expression=%s",
                trigger_type,
                condition.expression,
            )

        # Validate based on condition type
        if cond_type == "price":
            if not PRICE_EXPR_PATTERN.match(condition.expression):
                errors.append(
                    f"Invalid price expression: '{condition.expression}'. "
                    "Use format: 'TICKER OP VALUE' (e.g., 'NVDA < 130', 'AAPL >= 200')"
                )
                logger.info(
                    "[intent.validation.expression] price expression invalid: %s",
                    condition.expression,
                )

        elif cond_type == "portfolio":
            # Story 6.5 AC5.2: Validate portfolio expression with strict regex
            expr_stripped = condition.expression.strip()
            is_valid_percentage = PORTFOLIO_PERCENTAGE_PATTERN.match(expr_stripped)
            is_valid_absolute = PORTFOLIO_ABSOLUTE_PATTERN.match(expr_stripped)

            if not (is_valid_percentage or is_valid_absolute):
                errors.append(
                    f"Invalid portfolio expression: '{condition.expression}'. "
                    f"Supported formats: 'any_holding_change > 5%', 'any_holding_down > 10%', "
                    f"'any_holding_up >= 15%', 'total_change > 3%', 'total_value >= 100000'. "
                    f"Supported keywords: {', '.join(sorted(PORTFOLIO_KEYWORDS))}"
                )
                logger.info(
                    "[intent.validation.expression] portfolio expression invalid: %s",
                    condition.expression,
                )

        elif cond_type == "silence":
            if not SILENCE_EXPR_PATTERN.match(condition.expression):
                errors.append(
                    f"Invalid silence expression: '{condition.expression}'. "
                    "Use format: 'inactive_hours > N' (e.g., 'inactive_hours > 48')"
                )
                logger.info(
                    "[intent.validation.expression] silence expression invalid: %s",
                    condition.expression,
                )

        else:
            # Unknown condition type with expression - just log, don't error
            logger.debug(
                "[intent.validation.expression] Unknown condition type %s with expression: %s",
                cond_type,
                condition.expression,
            )

        if not errors:
            logger.debug(
                "[intent.validation.expression] valid=true type=%s expression=%s",
                cond_type,
                condition.expression,
            )

        return errors
