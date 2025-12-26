"""Unit tests for IntentValidationService (Story 5.3).

Tests validation rules for scheduled intent creation:
- AC1: Max 25 triggers per user
- AC2: Cron minimum interval 60 seconds
- AC3: Cron max 96 fires per day
- AC4: Interval minimum 5 minutes
- AC5: One-time triggers must be in future
- AC6: Required fields by trigger type
- AC7: All errors returned in single response
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.schemas import ScheduledIntentCreate, TriggerSchedule, TriggerCondition
from src.services.intent_validation import (
    IntentValidationService,
    ValidationResult,
    MAX_TRIGGERS_PER_USER,
    CRON_MIN_INTERVAL_SECONDS,
    CRON_MAX_FIRES_PER_DAY,
    INTERVAL_MIN_MINUTES,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


@pytest.fixture
def service_no_db():
    """Create validation service without database connection."""
    return IntentValidationService(conn=None)


@pytest.fixture
def service_with_db(mock_conn):
    """Create validation service with mocked database connection."""
    conn, cursor = mock_conn
    return IntentValidationService(conn=conn), cursor


def make_intent(
    trigger_type: str = "cron",
    trigger_schedule: TriggerSchedule = None,
    trigger_condition: TriggerCondition = None,
    user_id: str = "test-user"
) -> ScheduledIntentCreate:
    """Helper to create a ScheduledIntentCreate with defaults."""
    return ScheduledIntentCreate(
        user_id=user_id,
        intent_name="Test Intent",
        trigger_type=trigger_type,
        trigger_schedule=trigger_schedule,
        trigger_condition=trigger_condition,
        action_context="Test action context"
    )


# =============================================================================
# AC1: Trigger Count Validation (max 25 per user)
# =============================================================================

class TestTriggerCountValidation:
    """Tests for AC1: Max 25 active triggers per user."""

    def test_trigger_count_24_ok(self, mock_conn):
        """24 existing triggers allows creation."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"count": 24}

        service = IntentValidationService(conn=conn)
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 9 * * *")
        )

        result = service.validate(intent)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_trigger_count_25_fails(self, mock_conn):
        """25 existing triggers rejects with limit error."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"count": 25}

        service = IntentValidationService(conn=conn)
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 9 * * *")
        )

        result = service.validate(intent)

        assert result.is_valid is False
        assert any("Limit reached" in err for err in result.errors)
        assert any("25 active triggers max" in err for err in result.errors)

    def test_trigger_count_exceeded(self, mock_conn):
        """30 existing triggers also fails."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"count": 30}

        service = IntentValidationService(conn=conn)
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=10)
        )

        result = service.validate(intent)

        assert result.is_valid is False
        assert any("Limit reached" in err for err in result.errors)

    def test_trigger_count_db_error_continues(self, mock_conn):
        """Database error doesn't fail validation."""
        conn, cursor = mock_conn
        cursor.fetchone.side_effect = Exception("DB error")

        service = IntentValidationService(conn=conn)
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=10)
        )

        # Should not raise and should be valid if other checks pass
        result = service.validate(intent)
        # Only valid because no other errors (DB error is swallowed)
        assert result.is_valid is True


# =============================================================================
# AC2: Cron Minimum Interval (60 seconds)
# =============================================================================

class TestCronFrequencyValidation:
    """Tests for AC2: Cron minimum interval 60 seconds."""

    def test_cron_every_minute_fails(self, service_no_db):
        """'* * * * *' (every minute) rejects - passes frequency (60s = limit) but fails daily count (1440/day > 96)."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="* * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        # Every minute = 60s which is at the limit, so passes frequency check
        # But 1440/day exceeds 96/day limit
        assert any("x/day" in err or "/day" in err for err in result.errors)

    def test_cron_every_30_seconds_fails(self, service_no_db):
        """Cron with seconds field firing every 30s should fail."""
        # Note: Standard cron doesn't have seconds, but croniter supports it
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="*/30 * * * * *")  # Every 30 seconds
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("Cron too frequent" in err for err in result.errors)

    def test_cron_every_2_minutes_fails_daily_count(self, service_no_db):
        """'*/2 * * * *' (every 2 minutes) passes frequency but fails daily count (720/day > 96)."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="*/2 * * * *")
        )

        result = service_no_db.validate(intent)

        # Passes frequency check (120s > 60s) but 720/day exceeds 96 limit
        assert result.is_valid is False
        assert any("/day" in err or "x/day" in err for err in result.errors)

    def test_cron_hourly_ok(self, service_no_db):
        """'0 * * * *' (hourly) passes frequency check."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_cron_daily_ok(self, service_no_db):
        """'0 9 * * *' (daily at 9am) passes frequency check."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 9 * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True


# =============================================================================
# AC3: Cron Max Fires Per Day (96)
# =============================================================================

class TestCronDailyCountValidation:
    """Tests for AC3: Cron max 96 fires per day."""

    def test_cron_every_minute_exceeds_daily_limit(self, service_no_db):
        """Every minute = 1440/day exceeds 96 limit."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="* * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        # Should have both frequency and daily count errors
        assert any("x/day" in err or "/day" in err for err in result.errors)
        assert any("96" in err for err in result.errors)

    def test_cron_every_15_minutes_at_limit(self, service_no_db):
        """Every 15 min = 96/day at limit."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="*/15 * * * *")
        )

        result = service_no_db.validate(intent)

        # 96 fires/day is at the limit, should pass
        assert result.is_valid is True

    def test_cron_every_10_minutes_exceeds_limit(self, service_no_db):
        """Every 10 min = 144/day exceeds 96 limit."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="*/10 * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("144" in err or "x/day" in err for err in result.errors)

    def test_cron_hourly_well_under_limit(self, service_no_db):
        """Hourly = 24/day well under 96 limit."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True


# =============================================================================
# AC4: Interval Minimum (5 minutes)
# =============================================================================

class TestIntervalValidation:
    """Tests for AC4: Interval minimum 5 minutes."""

    def test_interval_4_minutes_fails(self, service_no_db):
        """interval_minutes=4 rejects with minimum error."""
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=4)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("Interval too short" in err for err in result.errors)
        assert any("5m" in err for err in result.errors)

    def test_interval_5_minutes_ok(self, service_no_db):
        """interval_minutes=5 passes minimum check."""
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=5)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_interval_30_minutes_ok(self, service_no_db):
        """interval_minutes=30 passes minimum check."""
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=30)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_interval_1_minute_fails(self, service_no_db):
        """interval_minutes=1 rejects with minimum error."""
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=1)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("Interval too short" in err for err in result.errors)


# =============================================================================
# AC5: One-Time Trigger Future Validation
# =============================================================================

class TestOnceTriggerValidation:
    """Tests for AC5: One-time triggers must be in future."""

    def test_once_past_fails(self, service_no_db):
        """trigger_at in past rejects with error."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        intent = make_intent(
            trigger_type="once",
            trigger_schedule=TriggerSchedule(trigger_at=past_time)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("must be in the future" in err for err in result.errors)

    def test_once_future_ok(self, service_no_db):
        """trigger_at in future passes."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        intent = make_intent(
            trigger_type="once",
            trigger_schedule=TriggerSchedule(trigger_at=future_time)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_once_now_fails(self, service_no_db):
        """trigger_at at current time fails (must be strictly in future)."""
        # Use a time slightly in the past to ensure it fails
        now = datetime.now(timezone.utc) - timedelta(seconds=1)
        intent = make_intent(
            trigger_type="once",
            trigger_schedule=TriggerSchedule(trigger_at=now)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False

    def test_once_naive_datetime_handled(self, service_no_db):
        """Timezone-naive datetime is handled correctly."""
        # Naive datetime in the past
        past_naive = datetime.now() - timedelta(hours=1)
        intent = make_intent(
            trigger_type="once",
            trigger_schedule=TriggerSchedule(trigger_at=past_naive)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("must be in the future" in err for err in result.errors)


# =============================================================================
# AC6: Required Fields by Trigger Type
# =============================================================================

class TestRequiredFieldsValidation:
    """Tests for AC6: Required fields by trigger type."""

    def test_cron_missing_schedule_fails(self, service_no_db):
        """Cron type without cron field rejects."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=None
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("trigger_schedule.cron required" in err for err in result.errors)

    def test_cron_empty_schedule_fails(self, service_no_db):
        """Cron type with empty schedule rejects."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule()  # No cron field set
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("trigger_schedule.cron required" in err for err in result.errors)

    def test_interval_missing_interval_minutes_fails(self, service_no_db):
        """Interval type without interval_minutes rejects."""
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule()  # No interval_minutes
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("trigger_schedule.interval_minutes required" in err for err in result.errors)

    def test_once_missing_trigger_at_fails(self, service_no_db):
        """Once type without trigger_at rejects."""
        intent = make_intent(
            trigger_type="once",
            trigger_schedule=TriggerSchedule()  # No trigger_at
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("trigger_schedule.trigger_at required" in err for err in result.errors)

    def test_price_partial_structured_fields_ok(self, service_no_db):
        """Price type with partial structured fields passes (Story 6.2: expression alternative)."""
        # Story 6.2: Price triggers can use EITHER structured fields OR expression
        # With partial structured fields and no expression, validation passes
        # (actual evaluation is done by Annie, not validation service)
        intent = make_intent(
            trigger_type="price",
            trigger_condition=TriggerCondition(operator=">", value=100.0)  # Missing ticker
        )

        result = service_no_db.validate(intent)

        # Story 6.2: Structured fields no longer strictly required (expression is alternative)
        assert result.is_valid is True

    def test_price_with_expression_no_structured_fields_ok(self, service_no_db):
        """Price type with expression instead of structured fields passes (Story 6.2)."""
        intent = make_intent(
            trigger_type="price",
            trigger_condition=TriggerCondition(expression="AAPL > 200", condition_type="price")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_price_empty_condition_ok(self, service_no_db):
        """Price type with empty condition passes (Story 6.2: no required condition fields)."""
        # Story 6.2: Price triggers accept either structured fields or expression
        intent = make_intent(
            trigger_type="price",
            trigger_condition=TriggerCondition()  # Empty - no structured fields, no expression
        )

        result = service_no_db.validate(intent)

        # No required condition fields - actual validation happens at evaluation time
        assert result.is_valid is True

    def test_price_all_fields_ok(self, service_no_db):
        """Price type with all required fields passes."""
        intent = make_intent(
            trigger_type="price",
            trigger_condition=TriggerCondition(ticker="AAPL", operator=">", value=200.0)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_silence_empty_condition_ok(self, service_no_db):
        """Silence type with empty condition passes (Story 6.2: expression alternative)."""
        # Story 6.2: Silence triggers can use EITHER threshold_hours OR expression
        intent = make_intent(
            trigger_type="silence",
            trigger_condition=TriggerCondition()  # No threshold_hours, no expression
        )

        result = service_no_db.validate(intent)

        # Story 6.2: No required condition fields (expression is alternative)
        assert result.is_valid is True

    def test_silence_with_expression_no_threshold_ok(self, service_no_db):
        """Silence type with expression instead of threshold_hours passes (Story 6.2)."""
        intent = make_intent(
            trigger_type="silence",
            trigger_condition=TriggerCondition(expression="inactive_hours > 48", condition_type="silence")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_silence_with_threshold_ok(self, service_no_db):
        """Silence type with threshold_hours passes."""
        intent = make_intent(
            trigger_type="silence",
            trigger_condition=TriggerCondition(threshold_hours=24)
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is True

    def test_portfolio_no_required_condition_fields_ok(self, service_no_db):
        """Portfolio type with empty condition passes (expression field added in Epic 6)."""
        intent = make_intent(
            trigger_type="portfolio",
            trigger_condition=TriggerCondition()
        )

        result = service_no_db.validate(intent)

        # Portfolio has no required fields currently (expression added in Epic 6)
        assert result.is_valid is True


# =============================================================================
# AC7: Multiple Errors Returned (No Short-Circuit)
# =============================================================================

class TestMultipleErrorsValidation:
    """Tests for AC7: All errors returned in single response."""

    def test_multiple_errors_returned(self, service_no_db):
        """Intent with multiple violations returns all errors."""
        # Cron type with too frequent schedule (violates both frequency and daily count)
        # Every 30 seconds = 2880/day > 96 limit, and 30s < 60s minimum interval
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="*/30 * * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        # Should have at least 2 errors: frequency too high and daily count exceeded
        assert len(result.errors) >= 2
        assert any("frequent" in err.lower() or "second" in err.lower() for err in result.errors)
        assert any("day" in err.lower() or "96" in err for err in result.errors)

    def test_no_short_circuit_cron_and_required(self, service_no_db):
        """All validations run even if required fields fail."""
        # Cron type with no schedule at all
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=None
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        # Should have error for missing cron field
        assert any("trigger_schedule.cron required" in err for err in result.errors)

    def test_cron_frequency_and_daily_errors_together(self, service_no_db):
        """Cron with both frequency and daily count violations returns both errors."""
        # Every 30 seconds (6-field cron) - fires too frequently AND exceeds daily limit
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="*/30 * * * * *")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        # Should have both frequency error (30s < 60s) and daily count error (2880/day > 96)
        assert len(result.errors) >= 2
        assert any("too frequent" in err.lower() for err in result.errors)
        assert any("day" in err.lower() for err in result.errors)

    def test_interval_and_trigger_count_errors_together(self, mock_conn):
        """Interval too short and trigger count exceeded returns both errors."""
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"count": 25}  # At limit

        service = IntentValidationService(conn=conn)
        intent = make_intent(
            trigger_type="interval",
            trigger_schedule=TriggerSchedule(interval_minutes=3)  # Too short
        )

        result = service.validate(intent)

        assert result.is_valid is False
        assert len(result.errors) >= 2
        assert any("Limit reached" in err for err in result.errors)
        assert any("Interval too short" in err for err in result.errors)


# =============================================================================
# Edge Cases and Additional Tests
# =============================================================================

class TestEdgeCases:
    """Additional edge case tests."""

    def test_invalid_cron_expression(self, service_no_db):
        """Invalid cron expression returns error."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="invalid cron")
        )

        result = service_no_db.validate(intent)

        assert result.is_valid is False
        assert any("Invalid cron expression" in err for err in result.errors)

    def test_validation_result_dataclass(self):
        """ValidationResult dataclass works correctly."""
        result = ValidationResult(is_valid=True, errors=[])
        assert result.is_valid is True
        assert result.errors == []

        result2 = ValidationResult(is_valid=False, errors=["Error 1", "Error 2"])
        assert result2.is_valid is False
        assert len(result2.errors) == 2

    def test_service_without_db_skips_count_check(self, service_no_db):
        """Service without DB connection skips trigger count validation."""
        intent = make_intent(
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 9 * * *")
        )

        result = service_no_db.validate(intent)

        # Should be valid since we can't check DB and other validations pass
        assert result.is_valid is True
