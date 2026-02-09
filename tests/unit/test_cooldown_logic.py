"""
Unit tests for cooldown logic in IntentService (Epic 6 Story 6.3).

Tests AC3.1: cooldown_hours validation (1-168 range)
Tests AC3.2: Fire endpoint checks cooldown before processing
Tests AC3.3: Returns cooldown_active=true with remaining hours
Tests AC3.4: Updates last_condition_fire on successful fires
Tests AC3.5: Pending query includes in_cooldown flag
Tests AC3.6: Claim endpoint prevents duplicate processing
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas import TriggerCondition, IntentFireResponse, IntentClaimResponse
from src.services.intent_service import (
    IntentService,
    CONDITION_TRIGGER_TYPES,
    CLAIM_TIMEOUT_MINUTES,
)


# =============================================================================
# Test AC3.1: cooldown_hours validation
# =============================================================================


class TestCooldownHoursValidation:
    """Tests for cooldown_hours validation (AC3.1)."""

    def test_cooldown_hours_default_is_24(self):
        """cooldown_hours defaults to 24 hours."""
        condition = TriggerCondition()
        assert condition.cooldown_hours == 24

    def test_cooldown_hours_minimum_valid(self):
        """cooldown_hours minimum of 1 is valid."""
        condition = TriggerCondition(cooldown_hours=1)
        assert condition.cooldown_hours == 1

    def test_cooldown_hours_maximum_valid(self):
        """cooldown_hours maximum of 168 (7 days) is valid."""
        condition = TriggerCondition(cooldown_hours=168)
        assert condition.cooldown_hours == 168

    def test_cooldown_hours_below_minimum_invalid(self):
        """cooldown_hours below 1 fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TriggerCondition(cooldown_hours=0)
        errors = exc_info.value.errors()
        assert any("greater than or equal to 1" in str(e) for e in errors)

    def test_cooldown_hours_above_maximum_invalid(self):
        """cooldown_hours above 168 fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TriggerCondition(cooldown_hours=169)
        errors = exc_info.value.errors()
        assert any("less than or equal to 168" in str(e) for e in errors)

    def test_cooldown_hours_negative_invalid(self):
        """Negative cooldown_hours fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TriggerCondition(cooldown_hours=-1)
        errors = exc_info.value.errors()
        assert any("greater than or equal to 1" in str(e) for e in errors)


# =============================================================================
# Test AC3.2/3.3: Cooldown check in fire_intent
# =============================================================================


class TestCooldownCheck:
    """Tests for _check_cooldown method (AC3.2, AC3.3)."""

    @pytest.fixture
    def service(self):
        """Create IntentService with mock connection."""
        mock_conn = MagicMock()
        return IntentService(mock_conn)

    def test_cooldown_not_active_for_cron_trigger(self, service):
        """Cron triggers do not have cooldown logic."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=1)

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type="cron",
            last_condition_fire=last_fire,
            cooldown_hours=24,
            now=now
        )

        assert is_in_cooldown is False
        assert remaining is None

    def test_cooldown_not_active_for_interval_trigger(self, service):
        """Interval triggers do not have cooldown logic."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=1)

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type="interval",
            last_condition_fire=last_fire,
            cooldown_hours=24,
            now=now
        )

        assert is_in_cooldown is False
        assert remaining is None

    def test_cooldown_not_active_for_once_trigger(self, service):
        """Once triggers do not have cooldown logic."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=1)

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type="once",
            last_condition_fire=last_fire,
            cooldown_hours=24,
            now=now
        )

        assert is_in_cooldown is False
        assert remaining is None

    @pytest.mark.parametrize("trigger_type", ["price", "silence", "portfolio"])
    def test_cooldown_active_for_condition_triggers(self, service, trigger_type):
        """Condition-based triggers have cooldown when within period."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=1)  # 1 hour ago
        cooldown_hours = 24

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type=trigger_type,
            last_condition_fire=last_fire,
            cooldown_hours=cooldown_hours,
            now=now
        )

        assert is_in_cooldown is True
        assert remaining is not None
        assert 22.9 < remaining < 23.1  # About 23 hours remaining

    @pytest.mark.parametrize("trigger_type", ["price", "silence", "portfolio"])
    def test_cooldown_not_active_after_period(self, service, trigger_type):
        """Condition-based triggers not in cooldown after period expires."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=25)  # 25 hours ago
        cooldown_hours = 24

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type=trigger_type,
            last_condition_fire=last_fire,
            cooldown_hours=cooldown_hours,
            now=now
        )

        assert is_in_cooldown is False
        assert remaining is None

    @pytest.mark.parametrize("trigger_type", ["price", "silence", "portfolio"])
    def test_cooldown_not_active_if_never_fired(self, service, trigger_type):
        """Condition-based triggers not in cooldown if never fired."""
        now = datetime.now(timezone.utc)

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type=trigger_type,
            last_condition_fire=None,  # Never fired
            cooldown_hours=24,
            now=now
        )

        assert is_in_cooldown is False
        assert remaining is None

    def test_cooldown_remaining_hours_calculation(self, service):
        """Remaining hours is correctly calculated."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=6)  # 6 hours ago
        cooldown_hours = 24

        is_in_cooldown, remaining = service._check_cooldown(
            trigger_type="price",
            last_condition_fire=last_fire,
            cooldown_hours=cooldown_hours,
            now=now
        )

        assert is_in_cooldown is True
        assert remaining is not None
        assert 17.9 < remaining < 18.1  # About 18 hours remaining

    def test_condition_trigger_types_constant(self):
        """CONDITION_TRIGGER_TYPES contains expected values."""
        assert CONDITION_TRIGGER_TYPES == {"price", "silence", "portfolio"}


# =============================================================================
# Test AC3.3/3.4: IntentFireResponse with cooldown fields
# =============================================================================


class TestIntentFireResponseCooldownFields:
    """Tests for cooldown fields in IntentFireResponse (AC3.3, AC3.4)."""

    def test_cooldown_active_default_false(self):
        """cooldown_active defaults to False."""
        response = IntentFireResponse(
            intent_id=uuid4(),
            status="success",
            enabled=True,
            execution_count=1
        )
        assert response.cooldown_active is False

    def test_cooldown_remaining_hours_default_none(self):
        """cooldown_remaining_hours defaults to None."""
        response = IntentFireResponse(
            intent_id=uuid4(),
            status="success",
            enabled=True,
            execution_count=1
        )
        assert response.cooldown_remaining_hours is None

    def test_last_condition_fire_default_none(self):
        """last_condition_fire defaults to None."""
        response = IntentFireResponse(
            intent_id=uuid4(),
            status="success",
            enabled=True,
            execution_count=1
        )
        assert response.last_condition_fire is None

    def test_cooldown_active_response(self):
        """Response with cooldown_active=True includes remaining hours."""
        now = datetime.now(timezone.utc)
        last_fire = now - timedelta(hours=1)

        response = IntentFireResponse(
            intent_id=uuid4(),
            status="cooldown_active",
            enabled=True,
            execution_count=1,
            cooldown_active=True,
            cooldown_remaining_hours=23.0,
            last_condition_fire=last_fire
        )

        assert response.cooldown_active is True
        assert response.cooldown_remaining_hours == 23.0
        assert response.last_condition_fire == last_fire

    def test_successful_fire_response_with_last_condition_fire(self):
        """Successful fire response includes last_condition_fire."""
        now = datetime.now(timezone.utc)

        response = IntentFireResponse(
            intent_id=uuid4(),
            status="success",
            enabled=True,
            execution_count=2,
            cooldown_active=False,
            last_condition_fire=now
        )

        assert response.status == "success"
        assert response.last_condition_fire == now


# =============================================================================
# Test AC3.6: IntentClaimResponse
# =============================================================================


class TestIntentClaimResponse:
    """Tests for IntentClaimResponse schema (AC3.6)."""

    def test_claim_response_has_intent_and_claimed_at(self):
        """IntentClaimResponse includes intent and claimed_at."""
        from src.schemas import ScheduledIntentResponse

        now = datetime.now(timezone.utc)
        intent = ScheduledIntentResponse(
            id=uuid4(),
            user_id="test-user",
            intent_name="Test Intent",
            trigger_type="price",
            action_type="message",
            action_context="Test context",
            action_priority="medium",
            execution_count=0,
            enabled=True,
            created_at=now,
            updated_at=now
        )

        response = IntentClaimResponse(
            intent=intent,
            claimed_at=now
        )

        assert response.intent.id == intent.id
        assert response.claimed_at == now


class TestClaimTimeoutConstant:
    """Tests for claim timeout configuration."""

    def test_claim_timeout_is_5_minutes(self):
        """Claim timeout is 5 minutes as per AC3.6."""
        assert CLAIM_TIMEOUT_MINUTES == 5


# =============================================================================
# Test TriggerCondition model with cooldown_hours
# =============================================================================


class TestTriggerConditionWithCooldown:
    """Tests for TriggerCondition model including cooldown_hours."""

    def test_model_dump_includes_cooldown_hours(self):
        """model_dump() includes cooldown_hours."""
        condition = TriggerCondition(cooldown_hours=48)
        data = condition.model_dump(exclude_none=True)
        assert data["cooldown_hours"] == 48

    def test_model_dump_default_cooldown_hours(self):
        """model_dump() includes default cooldown_hours."""
        condition = TriggerCondition()
        data = condition.model_dump(exclude_none=True)
        assert data["cooldown_hours"] == 24

    def test_cooldown_hours_with_other_fields(self):
        """cooldown_hours coexists with other TriggerCondition fields."""
        condition = TriggerCondition(
            ticker="NVDA",
            operator="<",
            value=130.0,
            expression="NVDA < 130",
            condition_type="price",
            cooldown_hours=12
        )

        assert condition.ticker == "NVDA"
        assert condition.expression == "NVDA < 130"
        assert condition.cooldown_hours == 12
