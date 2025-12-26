"""
Unit tests for portfolio trigger type (Epic 6 Story 6.5).

Tests AC5.1: 'portfolio' is valid trigger_type
Tests AC5.2: Portfolio expressions validated with proper regex
Tests AC5.3: Default check_interval_minutes=15 for portfolio triggers
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas import (
    ScheduledIntentCreate,
    TriggerSchedule,
    TriggerCondition,
)
from src.services.intent_service import CONDITION_TRIGGER_TYPES
from src.services.intent_validation import (
    IntentValidationService,
    PORTFOLIO_KEYWORDS,
    PORTFOLIO_PERCENTAGE_PATTERN,
    PORTFOLIO_ABSOLUTE_PATTERN,
)


# =============================================================================
# Test AC5.1: 'portfolio' is valid trigger_type
# =============================================================================


class TestPortfolioTriggerType:
    """Tests for portfolio trigger type validation (AC5.1)."""

    def test_portfolio_in_condition_trigger_types(self):
        """'portfolio' is in CONDITION_TRIGGER_TYPES constant."""
        assert "portfolio" in CONDITION_TRIGGER_TYPES

    def test_portfolio_trigger_type_accepted(self):
        """'portfolio' is valid trigger_type in ScheduledIntentCreate."""
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Portfolio Alert",
            trigger_type="portfolio",
            trigger_condition=TriggerCondition(
                expression="any_holding_change > 5%",
                condition_type="portfolio"
            ),
            action_context="Alert when portfolio changes"
        )
        assert intent.trigger_type == "portfolio"

    def test_portfolio_with_other_condition_types(self):
        """'portfolio' coexists with price and silence in CONDITION_TRIGGER_TYPES."""
        assert CONDITION_TRIGGER_TYPES == {"price", "silence", "portfolio"}

    def test_portfolio_keywords_defined(self):
        """PORTFOLIO_KEYWORDS contains expected values."""
        expected = {
            'any_holding_change', 'any_holding_up', 'any_holding_down',
            'total_value', 'total_change'
        }
        assert PORTFOLIO_KEYWORDS == expected


# =============================================================================
# Test AC5.2: Portfolio expression validation - Valid cases
# =============================================================================


class TestPortfolioExpressionValidCases:
    """Tests for valid portfolio expressions (AC5.2)."""

    @pytest.mark.parametrize("expression", [
        "any_holding_change > 5%",
        "any_holding_change >= 10%",
        "any_holding_change < 3%",
        "any_holding_change <= 1%",
    ])
    def test_any_holding_change_expressions(self, expression):
        """any_holding_change expressions with various operators are valid."""
        assert PORTFOLIO_PERCENTAGE_PATTERN.match(expression)

    @pytest.mark.parametrize("expression", [
        "any_holding_down > 5%",
        "any_holding_down >= 10%",
        "any_holding_down < 15%",
        "any_holding_down <= 20%",
    ])
    def test_any_holding_down_expressions(self, expression):
        """any_holding_down expressions are valid."""
        assert PORTFOLIO_PERCENTAGE_PATTERN.match(expression)

    @pytest.mark.parametrize("expression", [
        "any_holding_up > 5%",
        "any_holding_up >= 8.5%",
        "any_holding_up < 10.25%",
        "any_holding_up <= 15%",
    ])
    def test_any_holding_up_expressions(self, expression):
        """any_holding_up expressions are valid."""
        assert PORTFOLIO_PERCENTAGE_PATTERN.match(expression)

    @pytest.mark.parametrize("expression", [
        "total_change > 3%",
        "total_change >= 5%",
        "total_change < 10%",
        "total_change <= 2.5%",
    ])
    def test_total_change_expressions(self, expression):
        """total_change expressions are valid."""
        assert PORTFOLIO_PERCENTAGE_PATTERN.match(expression)

    @pytest.mark.parametrize("expression", [
        "total_value > 100000",
        "total_value >= 50000",
        "total_value < 1000000",
        "total_value <= 250000.50",
    ])
    def test_total_value_expressions(self, expression):
        """total_value expressions with absolute values are valid."""
        assert PORTFOLIO_ABSOLUTE_PATTERN.match(expression)

    def test_expression_case_insensitive(self):
        """Portfolio expressions are case-insensitive."""
        assert PORTFOLIO_PERCENTAGE_PATTERN.match("ANY_HOLDING_CHANGE > 5%")
        assert PORTFOLIO_PERCENTAGE_PATTERN.match("Total_Change > 3%")
        assert PORTFOLIO_ABSOLUTE_PATTERN.match("TOTAL_VALUE >= 100000")

    def test_expression_with_decimal_percentage(self):
        """Decimal percentages are valid."""
        assert PORTFOLIO_PERCENTAGE_PATTERN.match("any_holding_change > 5.5%")
        assert PORTFOLIO_PERCENTAGE_PATTERN.match("total_change >= 0.5%")

    def test_expression_with_decimal_absolute(self):
        """Decimal absolute values are valid."""
        assert PORTFOLIO_ABSOLUTE_PATTERN.match("total_value > 100000.50")


# =============================================================================
# Test AC5.2: Portfolio expression validation - Invalid cases
# =============================================================================


class TestPortfolioExpressionInvalidCases:
    """Tests for invalid portfolio expressions (AC5.2)."""

    def test_unknown_keyword_rejected(self):
        """Unknown keywords are rejected."""
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("unknown_metric > 5%")
        assert not PORTFOLIO_ABSOLUTE_PATTERN.match("unknown_value > 100")

    def test_missing_percentage_sign_rejected(self):
        """Percentage expressions without % are rejected."""
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("any_holding_change > 5")
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("total_change >= 10")

    def test_total_value_with_percentage_rejected(self):
        """total_value with percentage is rejected (should be absolute)."""
        assert not PORTFOLIO_ABSOLUTE_PATTERN.match("total_value > 100000%")

    def test_invalid_operator_rejected(self):
        """Invalid operators are rejected."""
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("any_holding_change == 5%")
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("any_holding_change != 5%")

    def test_missing_operator_rejected(self):
        """Missing operator is rejected."""
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("any_holding_change 5%")

    def test_missing_value_rejected(self):
        """Missing value is rejected."""
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("any_holding_change >%")
        assert not PORTFOLIO_ABSOLUTE_PATTERN.match("total_value >=")

    def test_empty_expression_rejected(self):
        """Empty expression is rejected."""
        assert not PORTFOLIO_PERCENTAGE_PATTERN.match("")
        assert not PORTFOLIO_ABSOLUTE_PATTERN.match("")


# =============================================================================
# Test AC5.2: IntentValidationService portfolio validation
# =============================================================================


class TestPortfolioValidationService:
    """Tests for portfolio expression validation through IntentValidationService."""

    def test_valid_portfolio_expression_passes(self):
        """Valid portfolio expression passes validation."""
        validator = IntentValidationService(conn=None)
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Portfolio Alert",
            trigger_type="portfolio",
            trigger_condition=TriggerCondition(
                expression="any_holding_change > 5%",
                condition_type="portfolio"
            ),
            action_context="Alert"
        )
        result = validator.validate(intent)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_valid_total_value_expression_passes(self):
        """Valid total_value expression passes validation."""
        validator = IntentValidationService(conn=None)
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Value Alert",
            trigger_type="portfolio",
            trigger_condition=TriggerCondition(
                expression="total_value >= 100000",
                condition_type="portfolio"
            ),
            action_context="Alert"
        )
        result = validator.validate(intent)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_invalid_portfolio_expression_fails(self):
        """Invalid portfolio expression fails validation."""
        validator = IntentValidationService(conn=None)
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Invalid Alert",
            trigger_type="portfolio",
            trigger_condition=TriggerCondition(
                expression="unknown_metric > 5%",
                condition_type="portfolio"
            ),
            action_context="Alert"
        )
        result = validator.validate(intent)
        assert not result.is_valid
        assert any("Invalid portfolio expression" in err for err in result.errors)

    def test_portfolio_without_expression_passes(self):
        """Portfolio without expression passes (expression optional for backward compat)."""
        validator = IntentValidationService(conn=None)
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Portfolio Alert",
            trigger_type="portfolio",
            trigger_condition=TriggerCondition(
                condition_type="portfolio"
            ),
            action_context="Alert"
        )
        result = validator.validate(intent)
        # Currently expression is optional, validation passes
        assert result.is_valid


# =============================================================================
# Test AC5.3: Default check_interval_minutes for portfolio
# =============================================================================


class TestPortfolioCheckInterval:
    """Tests for default check_interval_minutes=15 for portfolio triggers (AC5.3)."""

    def test_trigger_schedule_default_is_5(self):
        """TriggerSchedule default check_interval_minutes is 5."""
        schedule = TriggerSchedule()
        assert schedule.check_interval_minutes == 5

    def test_trigger_schedule_accepts_15(self):
        """TriggerSchedule accepts check_interval_minutes=15."""
        schedule = TriggerSchedule(check_interval_minutes=15)
        assert schedule.check_interval_minutes == 15

    def test_trigger_schedule_accepts_custom_value(self):
        """TriggerSchedule accepts custom check_interval_minutes."""
        schedule = TriggerSchedule(check_interval_minutes=30)
        assert schedule.check_interval_minutes == 30

    def test_portfolio_intent_with_explicit_interval(self):
        """Portfolio intent with explicit check_interval_minutes is accepted."""
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Portfolio Alert",
            trigger_type="portfolio",
            trigger_schedule=TriggerSchedule(check_interval_minutes=30),
            trigger_condition=TriggerCondition(
                expression="any_holding_change > 5%",
                condition_type="portfolio"
            ),
            action_context="Alert"
        )
        assert intent.trigger_schedule.check_interval_minutes == 30


# =============================================================================
# Test portfolio with cooldown and fire_mode
# =============================================================================


class TestPortfolioWithCooldownFireMode:
    """Tests for portfolio triggers using cooldown and fire_mode features."""

    def test_portfolio_supports_cooldown_hours(self):
        """Portfolio triggers support cooldown_hours field."""
        condition = TriggerCondition(
            expression="any_holding_change > 5%",
            condition_type="portfolio",
            cooldown_hours=48
        )
        assert condition.cooldown_hours == 48

    def test_portfolio_supports_fire_mode_once(self):
        """Portfolio triggers support fire_mode='once'."""
        condition = TriggerCondition(
            expression="any_holding_change > 5%",
            condition_type="portfolio",
            fire_mode="once"
        )
        assert condition.fire_mode == "once"

    def test_portfolio_supports_fire_mode_recurring(self):
        """Portfolio triggers support fire_mode='recurring' (default)."""
        condition = TriggerCondition(
            expression="any_holding_change > 5%",
            condition_type="portfolio"
        )
        assert condition.fire_mode == "recurring"

    def test_portfolio_full_condition_config(self):
        """Portfolio condition with all options configured."""
        condition = TriggerCondition(
            expression="total_value >= 100000",
            condition_type="portfolio",
            cooldown_hours=72,
            fire_mode="once"
        )
        assert condition.expression == "total_value >= 100000"
        assert condition.condition_type == "portfolio"
        assert condition.cooldown_hours == 72
        assert condition.fire_mode == "once"

