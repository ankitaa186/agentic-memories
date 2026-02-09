"""Unit tests for Scheduled Intents Pydantic models (Story 5.2).

Tests validation rules, required field enforcement, Literal type constraints,
Field constraints, and serialization/deserialization.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas import (
    IntentExecutionResponse,
    IntentFireRequest,
    IntentFireResponse,
    ScheduledIntentCreate,
    ScheduledIntentResponse,
    ScheduledIntentUpdate,
    TriggerCondition,
    TriggerSchedule,
)


class TestTriggerSchedule:
    """Tests for TriggerSchedule model (AC1)."""

    def test_valid_cron_schedule(self):
        """TriggerSchedule accepts valid cron expression."""
        schedule = TriggerSchedule(cron="0 9 * * *")
        assert schedule.cron == "0 9 * * *"
        assert schedule.check_interval_minutes == 5  # default

    def test_valid_interval_schedule(self):
        """TriggerSchedule accepts valid interval_minutes."""
        schedule = TriggerSchedule(interval_minutes=30)
        assert schedule.interval_minutes == 30

    def test_valid_trigger_at_schedule(self):
        """TriggerSchedule accepts valid trigger_at datetime."""
        dt = datetime(2025, 12, 25, 10, 0, 0, tzinfo=timezone.utc)
        schedule = TriggerSchedule(trigger_at=dt)
        assert schedule.trigger_at == dt

    def test_check_interval_default(self):
        """TriggerSchedule has default check_interval_minutes of 5."""
        schedule = TriggerSchedule()
        assert schedule.check_interval_minutes == 5

    def test_check_interval_minimum(self):
        """TriggerSchedule rejects check_interval_minutes less than 5."""
        with pytest.raises(ValidationError) as exc_info:
            TriggerSchedule(check_interval_minutes=3)
        assert "check_interval_minutes" in str(exc_info.value)

    def test_check_interval_valid_custom(self):
        """TriggerSchedule accepts check_interval_minutes >= 5."""
        schedule = TriggerSchedule(check_interval_minutes=10)
        assert schedule.check_interval_minutes == 10


class TestTriggerCondition:
    """Tests for TriggerCondition model (AC2)."""

    def test_valid_price_condition(self):
        """TriggerCondition accepts valid price trigger fields."""
        condition = TriggerCondition(ticker="AAPL", operator=">=", value=200.0)
        assert condition.ticker == "AAPL"
        assert condition.operator == ">="
        assert condition.value == 200.0

    def test_valid_silence_condition(self):
        """TriggerCondition accepts valid silence trigger fields."""
        condition = TriggerCondition(threshold_hours=24)
        assert condition.threshold_hours == 24

    def test_all_fields_optional(self):
        """TriggerCondition allows all fields to be None."""
        condition = TriggerCondition()
        assert condition.ticker is None
        assert condition.operator is None
        assert condition.value is None
        assert condition.threshold_hours is None


class TestScheduledIntentCreate:
    """Tests for ScheduledIntentCreate model (AC3)."""

    def test_valid_cron_intent(self):
        """ScheduledIntentCreate accepts valid cron-based intent."""
        intent = ScheduledIntentCreate(
            user_id="user-123",
            intent_name="Daily Market Check",
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 9 * * *"),
            action_context="Check morning market conditions",
        )
        assert intent.user_id == "user-123"
        assert intent.intent_name == "Daily Market Check"
        assert intent.trigger_type == "cron"
        assert intent.action_type == "notify"  # default
        assert intent.action_priority == "normal"  # default

    def test_valid_price_intent(self):
        """ScheduledIntentCreate accepts valid price-based intent."""
        intent = ScheduledIntentCreate(
            user_id="user-123",
            intent_name="AAPL Price Alert",
            trigger_type="price",
            trigger_condition=TriggerCondition(
                ticker="AAPL", operator=">=", value=200.0
            ),
            action_context="Alert when AAPL reaches $200",
        )
        assert intent.trigger_type == "price"

    def test_required_fields_missing_user_id(self):
        """ScheduledIntentCreate rejects missing user_id."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentCreate(
                intent_name="Test", trigger_type="cron", action_context="Test context"
            )
        assert "user_id" in str(exc_info.value)

    def test_required_fields_missing_intent_name(self):
        """ScheduledIntentCreate rejects missing intent_name."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentCreate(
                user_id="user-123", trigger_type="cron", action_context="Test context"
            )
        assert "intent_name" in str(exc_info.value)

    def test_required_fields_missing_action_context(self):
        """ScheduledIntentCreate rejects missing action_context."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentCreate(
                user_id="user-123", intent_name="Test", trigger_type="cron"
            )
        assert "action_context" in str(exc_info.value)

    def test_invalid_trigger_type(self):
        """ScheduledIntentCreate rejects invalid trigger_type."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentCreate(
                user_id="user-123",
                intent_name="Test",
                trigger_type="invalid_type",
                action_context="Test context",
            )
        assert "trigger_type" in str(exc_info.value)

    def test_valid_trigger_types(self):
        """ScheduledIntentCreate accepts all valid trigger_types."""
        valid_types = ["cron", "interval", "once", "price", "silence", "portfolio"]
        for trigger_type in valid_types:
            intent = ScheduledIntentCreate(
                user_id="user-123",
                intent_name="Test",
                trigger_type=trigger_type,
                action_context="Test context",
            )
            assert intent.trigger_type == trigger_type

    def test_invalid_action_type(self):
        """ScheduledIntentCreate rejects invalid action_type."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentCreate(
                user_id="user-123",
                intent_name="Test",
                trigger_type="cron",
                action_type="invalid_action",
                action_context="Test context",
            )
        assert "action_type" in str(exc_info.value)

    def test_valid_action_types(self):
        """ScheduledIntentCreate accepts all valid action_types."""
        valid_types = ["notify", "check_in", "briefing", "analysis", "reminder"]
        for action_type in valid_types:
            intent = ScheduledIntentCreate(
                user_id="user-123",
                intent_name="Test",
                trigger_type="cron",
                action_type=action_type,
                action_context="Test context",
            )
            assert intent.action_type == action_type

    def test_invalid_action_priority(self):
        """ScheduledIntentCreate rejects invalid action_priority."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentCreate(
                user_id="user-123",
                intent_name="Test",
                trigger_type="cron",
                action_priority="urgent",
                action_context="Test context",
            )
        assert "action_priority" in str(exc_info.value)

    def test_valid_action_priorities(self):
        """ScheduledIntentCreate accepts all valid action_priorities."""
        valid_priorities = ["low", "normal", "high", "critical"]
        for priority in valid_priorities:
            intent = ScheduledIntentCreate(
                user_id="user-123",
                intent_name="Test",
                trigger_type="cron",
                action_priority=priority,
                action_context="Test context",
            )
            assert intent.action_priority == priority

    def test_optional_fields_accept_none(self):
        """ScheduledIntentCreate accepts None for optional fields."""
        intent = ScheduledIntentCreate(
            user_id="user-123",
            intent_name="Test",
            trigger_type="cron",
            action_context="Test context",
        )
        assert intent.description is None
        assert intent.trigger_schedule is None
        assert intent.trigger_condition is None
        assert intent.expires_at is None
        assert intent.max_executions is None
        assert intent.metadata is None


class TestIntentFireRequest:
    """Tests for IntentFireRequest model (AC4)."""

    def test_valid_success_fire(self):
        """IntentFireRequest accepts valid success status."""
        request = IntentFireRequest(
            status="success",
            message_id="msg-123",
            message_preview="Market update: AAPL up 5%",
            evaluation_ms=50,
            generation_ms=200,
            delivery_ms=30,
        )
        assert request.status == "success"
        assert request.message_id == "msg-123"

    def test_valid_failed_fire(self):
        """IntentFireRequest accepts valid failed status with error."""
        request = IntentFireRequest(status="failed", error_message="LLM timeout")
        assert request.status == "failed"
        assert request.error_message == "LLM timeout"

    def test_valid_gate_blocked_fire(self):
        """IntentFireRequest accepts valid gate_blocked status."""
        request = IntentFireRequest(
            status="gate_blocked", gate_result={"score": 0.3, "reason": "User busy"}
        )
        assert request.status == "gate_blocked"
        assert request.gate_result["score"] == 0.3

    def test_valid_condition_not_met_fire(self):
        """IntentFireRequest accepts valid condition_not_met status."""
        request = IntentFireRequest(
            status="condition_not_met",
            trigger_data={"current_price": 195.0, "target": 200.0},
        )
        assert request.status == "condition_not_met"

    def test_invalid_status(self):
        """IntentFireRequest rejects invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            IntentFireRequest(status="pending")
        assert "status" in str(exc_info.value)

    def test_valid_statuses(self):
        """IntentFireRequest accepts all valid statuses."""
        valid_statuses = ["success", "failed", "gate_blocked", "condition_not_met"]
        for status in valid_statuses:
            request = IntentFireRequest(status=status)
            assert request.status == status

    def test_optional_fields_accept_none(self):
        """IntentFireRequest accepts None for optional fields."""
        request = IntentFireRequest(status="success")
        assert request.trigger_data is None
        assert request.gate_result is None
        assert request.message_id is None
        assert request.message_preview is None
        assert request.evaluation_ms is None
        assert request.generation_ms is None
        assert request.delivery_ms is None
        assert request.error_message is None


class TestScheduledIntentResponse:
    """Tests for ScheduledIntentResponse model (AC5)."""

    def test_serializes_all_24_columns(self):
        """ScheduledIntentResponse serializes all 24 database columns."""
        now = datetime.now(timezone.utc)
        intent_id = uuid4()

        response = ScheduledIntentResponse(
            id=intent_id,
            user_id="user-123",
            intent_name="Daily Check",
            description="Morning market check",
            trigger_type="cron",
            trigger_schedule={"cron": "0 9 * * *"},
            trigger_condition=None,
            action_type="notify",
            action_context="Check markets",
            action_priority="normal",
            next_check=now,
            last_checked=now,
            last_executed=now,
            execution_count=5,
            last_execution_status="success",
            last_execution_error=None,
            last_message_id="msg-123",
            enabled=True,
            expires_at=None,
            max_executions=100,
            created_at=now,
            updated_at=now,
            created_by="system",
            metadata={"source": "api"},
        )

        # Verify all 24 fields
        assert response.id == intent_id
        assert response.user_id == "user-123"
        assert response.intent_name == "Daily Check"
        assert response.description == "Morning market check"
        assert response.trigger_type == "cron"
        assert response.trigger_schedule == {"cron": "0 9 * * *"}
        assert response.trigger_condition is None
        assert response.action_type == "notify"
        assert response.action_context == "Check markets"
        assert response.action_priority == "normal"
        assert response.next_check == now
        assert response.last_checked == now
        assert response.last_executed == now
        assert response.execution_count == 5
        assert response.last_execution_status == "success"
        assert response.last_execution_error is None
        assert response.last_message_id == "msg-123"
        assert response.enabled is True
        assert response.expires_at is None
        assert response.max_executions == 100
        assert response.created_at == now
        assert response.updated_at == now
        assert response.created_by == "system"
        assert response.metadata == {"source": "api"}

    def test_from_attributes_config(self):
        """ScheduledIntentResponse has from_attributes=True for ORM mapping."""
        assert ScheduledIntentResponse.model_config.get("from_attributes") is True


class TestIntentFireResponse:
    """Tests for IntentFireResponse model (AC5)."""

    def test_valid_fire_response(self):
        """IntentFireResponse serializes fire result correctly."""
        intent_id = uuid4()
        now = datetime.now(timezone.utc)

        response = IntentFireResponse(
            intent_id=intent_id,
            status="success",
            next_check=now,
            enabled=True,
            execution_count=6,
        )

        assert response.intent_id == intent_id
        assert response.status == "success"
        assert response.next_check == now
        assert response.enabled is True
        assert response.execution_count == 6


class TestIntentExecutionResponse:
    """Tests for IntentExecutionResponse model (AC5)."""

    def test_serializes_all_14_columns(self):
        """IntentExecutionResponse serializes all 14 database columns."""
        now = datetime.now(timezone.utc)
        exec_id = uuid4()
        intent_id = uuid4()

        response = IntentExecutionResponse(
            id=exec_id,
            intent_id=intent_id,
            user_id="user-123",
            executed_at=now,
            trigger_type="cron",
            trigger_data={"scheduled": True},
            status="success",
            gate_result={"score": 0.9},
            message_id="msg-456",
            message_preview="Your daily briefing is ready",
            evaluation_ms=45,
            generation_ms=180,
            delivery_ms=25,
            error_message=None,
        )

        # Verify all 14 fields
        assert response.id == exec_id
        assert response.intent_id == intent_id
        assert response.user_id == "user-123"
        assert response.executed_at == now
        assert response.trigger_type == "cron"
        assert response.trigger_data == {"scheduled": True}
        assert response.status == "success"
        assert response.gate_result == {"score": 0.9}
        assert response.message_id == "msg-456"
        assert response.message_preview == "Your daily briefing is ready"
        assert response.evaluation_ms == 45
        assert response.generation_ms == 180
        assert response.delivery_ms == 25
        assert response.error_message is None

    def test_from_attributes_config(self):
        """IntentExecutionResponse has from_attributes=True for ORM mapping."""
        assert IntentExecutionResponse.model_config.get("from_attributes") is True


class TestScheduledIntentUpdate:
    """Tests for ScheduledIntentUpdate model (AC5)."""

    def test_all_fields_optional(self):
        """ScheduledIntentUpdate allows all fields to be None (partial update)."""
        update = ScheduledIntentUpdate()
        assert update.intent_name is None
        assert update.description is None
        assert update.trigger_type is None
        assert update.trigger_schedule is None
        assert update.trigger_condition is None
        assert update.action_type is None
        assert update.action_context is None
        assert update.action_priority is None
        assert update.enabled is None
        assert update.expires_at is None
        assert update.max_executions is None
        assert update.metadata is None

    def test_partial_update(self):
        """ScheduledIntentUpdate accepts partial field updates."""
        update = ScheduledIntentUpdate(intent_name="Updated Name", enabled=False)
        assert update.intent_name == "Updated Name"
        assert update.enabled is False
        assert update.action_context is None  # unchanged

    def test_validates_literal_fields(self):
        """ScheduledIntentUpdate validates Literal fields when provided."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentUpdate(trigger_type="invalid")
        assert "trigger_type" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentUpdate(action_type="invalid")
        assert "action_type" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ScheduledIntentUpdate(action_priority="invalid")
        assert "action_priority" in str(exc_info.value)
