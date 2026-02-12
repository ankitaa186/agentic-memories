"""
Unit tests for condition expression validation in IntentValidationService (Epic 6 Story 6.2).

Tests AC2.3: Price expressions validated as "TICKER OP VALUE" format.
Tests AC2.4: Portfolio expressions validated against supported keywords.
Tests AC2.5: Backward compatible with existing structured fields.
"""

import pytest

from src.schemas import ScheduledIntentCreate, TriggerCondition
from src.services.intent_validation import IntentValidationService


def make_condition_intent(
    trigger_type: str = "price", condition: TriggerCondition = None, **kwargs
) -> ScheduledIntentCreate:
    """Helper to create a minimal valid intent with condition."""
    defaults = {
        "user_id": "test-user",
        "intent_name": "Test Intent",
        "trigger_type": trigger_type,
        "trigger_condition": condition,
        "action_context": "Test context",
    }
    defaults.update(kwargs)
    return ScheduledIntentCreate(**defaults)


@pytest.fixture
def service_no_db():
    """Create validation service without database connection."""
    return IntentValidationService(conn=None)


class TestPriceExpressionValidation:
    """Tests for price expression validation (AC2.3)."""

    def test_valid_price_expression_less_than(self, service_no_db):
        """Valid price expression 'NVDA < 130' passes validation."""
        condition = TriggerCondition(expression="NVDA < 130", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_price_expression_greater_equal(self, service_no_db):
        """Valid price expression 'AAPL >= 200' passes validation."""
        condition = TriggerCondition(expression="AAPL >= 200", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_price_expression_equals(self, service_no_db):
        """Valid price expression 'TSLA == 250' passes validation."""
        condition = TriggerCondition(expression="TSLA == 250", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_price_expression_decimal(self, service_no_db):
        """Valid price expression with decimal 'AAPL >= 200.50' passes validation."""
        condition = TriggerCondition(
            expression="AAPL >= 200.50", condition_type="price"
        )
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_price_expression_no_spaces(self, service_no_db):
        """Valid price expression without spaces 'NVDA<130' passes validation."""
        condition = TriggerCondition(expression="NVDA<130", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_invalid_price_expression_lowercase(self, service_no_db):
        """Invalid price expression with lowercase ticker fails."""
        condition = TriggerCondition(expression="nvda < 130", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid price expression" in err for err in result.errors)
        assert any("TICKER OP VALUE" in err for err in result.errors)

    def test_invalid_price_expression_no_operator(self, service_no_db):
        """Invalid price expression without operator fails."""
        condition = TriggerCondition(expression="NVDA 130", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid price expression" in err for err in result.errors)

    def test_invalid_price_expression_no_value(self, service_no_db):
        """Invalid price expression without value fails."""
        condition = TriggerCondition(expression="NVDA <", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid price expression" in err for err in result.errors)

    def test_invalid_price_expression_text_value(self, service_no_db):
        """Invalid price expression with text value fails."""
        condition = TriggerCondition(expression="NVDA < high", condition_type="price")
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid price expression" in err for err in result.errors)

    def test_price_expression_inferred_from_trigger_type(self, service_no_db):
        """Price expression validation uses trigger_type when condition_type is None."""
        condition = TriggerCondition(expression="NVDA < 130")  # No condition_type
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True


class TestPortfolioExpressionValidation:
    """Tests for portfolio expression validation (AC2.4)."""

    def test_valid_portfolio_expression_any_holding_change(self, service_no_db):
        """Valid portfolio expression 'any_holding_change > 5%' passes validation."""
        condition = TriggerCondition(
            expression="any_holding_change > 5%", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_portfolio_expression_any_holding_up(self, service_no_db):
        """Valid portfolio expression 'any_holding_up > 10%' passes validation."""
        condition = TriggerCondition(
            expression="any_holding_up > 10%", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_portfolio_expression_any_holding_down(self, service_no_db):
        """Valid portfolio expression 'any_holding_down > 5%' passes validation."""
        condition = TriggerCondition(
            expression="any_holding_down > 5%", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_portfolio_expression_total_value(self, service_no_db):
        """Valid portfolio expression 'total_value >= 100000' passes validation."""
        condition = TriggerCondition(
            expression="total_value >= 100000", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_portfolio_expression_total_change(self, service_no_db):
        """Valid portfolio expression 'total_change > -5%' passes validation."""
        condition = TriggerCondition(
            expression="total_change > -5%", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_invalid_portfolio_expression_unknown_keyword(self, service_no_db):
        """Invalid portfolio expression with unknown keyword fails."""
        condition = TriggerCondition(
            expression="unknown_metric > 5%", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid portfolio expression" in err for err in result.errors)
        assert any("Supported keywords" in err for err in result.errors)

    def test_invalid_portfolio_expression_price_format(self, service_no_db):
        """Portfolio expression in price format fails."""
        condition = TriggerCondition(
            expression="NVDA < 130", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid portfolio expression" in err for err in result.errors)


class TestSilenceExpressionValidation:
    """Tests for silence expression validation."""

    def test_valid_silence_expression(self, service_no_db):
        """Valid silence expression 'inactive_hours > 48' passes validation."""
        condition = TriggerCondition(
            expression="inactive_hours > 48", condition_type="silence"
        )
        intent = make_condition_intent(trigger_type="silence", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_silence_expression_no_spaces(self, service_no_db):
        """Valid silence expression without spaces passes validation."""
        condition = TriggerCondition(
            expression="inactive_hours>24", condition_type="silence"
        )
        intent = make_condition_intent(trigger_type="silence", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_invalid_silence_expression_wrong_format(self, service_no_db):
        """Invalid silence expression format fails."""
        condition = TriggerCondition(
            expression="silence > 48", condition_type="silence"
        )
        intent = make_condition_intent(trigger_type="silence", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid silence expression" in err for err in result.errors)
        assert any("inactive_hours > N" in err for err in result.errors)

    def test_invalid_silence_expression_wrong_operator(self, service_no_db):
        """Invalid silence expression with wrong operator fails."""
        condition = TriggerCondition(
            expression="inactive_hours < 48",  # Should be >
            condition_type="silence",
        )
        intent = make_condition_intent(trigger_type="silence", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid silence expression" in err for err in result.errors)


class TestBackwardCompatibility:
    """Tests for backward compatibility with structured fields (AC2.5)."""

    def test_structured_fields_still_work(self, service_no_db):
        """Intent with only structured fields (ticker/operator/value) still works."""
        condition = TriggerCondition(ticker="NVDA", operator="<", value=130.0)
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        # Should pass - no expression to validate
        assert result.is_valid is True

    def test_structured_threshold_hours_still_works(self, service_no_db):
        """Intent with only threshold_hours structured field still works."""
        condition = TriggerCondition(threshold_hours=48)
        intent = make_condition_intent(trigger_type="silence", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_no_condition_fields_for_portfolio(self, service_no_db):
        """Portfolio trigger type with expression works."""
        condition = TriggerCondition(
            expression="any_holding_change > 5%", condition_type="portfolio"
        )
        intent = make_condition_intent(trigger_type="portfolio", condition=condition)
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_expression_takes_precedence(self, service_no_db):
        """When both expression and structured fields provided, expression is validated."""
        condition = TriggerCondition(
            ticker="AAPL",
            operator=">",
            value=200.0,
            expression="NVDA < 130",  # Expression takes precedence
            condition_type="price",
        )
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        # Expression is valid, so should pass
        assert result.is_valid is True

    def test_no_expression_no_validation(self, service_no_db):
        """When no expression provided, expression validation is skipped."""
        condition = TriggerCondition(
            ticker="NVDA",
            operator="<",
            value=130.0,
            # No expression field
        )
        intent = make_condition_intent(trigger_type="price", condition=condition)
        result = service_no_db.validate(intent)
        # No expression to validate, structured fields work
        assert result.is_valid is True


class TestTriggerConditionModel:
    """Tests for TriggerCondition Pydantic model (AC2.2)."""

    def test_condition_type_field_exists(self):
        """TriggerCondition has condition_type field."""
        condition = TriggerCondition(condition_type="price")
        assert condition.condition_type == "price"

    def test_expression_field_exists(self):
        """TriggerCondition has expression field."""
        condition = TriggerCondition(expression="NVDA < 130")
        assert condition.expression == "NVDA < 130"

    def test_new_fields_default_to_none(self):
        """New fields default to None for backward compatibility."""
        condition = TriggerCondition()
        assert condition.condition_type is None
        assert condition.expression is None

    def test_all_fields_coexist(self):
        """All fields (old and new) can coexist."""
        condition = TriggerCondition(
            ticker="NVDA",
            operator="<",
            value=130.0,
            threshold_hours=48,
            condition_type="price",
            expression="NVDA < 130",
        )
        assert condition.ticker == "NVDA"
        assert condition.operator == "<"
        assert condition.value == 130.0
        assert condition.threshold_hours == 48
        assert condition.condition_type == "price"
        assert condition.expression == "NVDA < 130"

    def test_model_dump_includes_new_fields(self):
        """model_dump() includes new fields when set."""
        condition = TriggerCondition(condition_type="price", expression="NVDA < 130")
        data = condition.model_dump(exclude_none=True)
        assert data["condition_type"] == "price"
        assert data["expression"] == "NVDA < 130"

    def test_model_dump_excludes_none_fields(self):
        """model_dump(exclude_none=True) excludes None fields."""
        condition = TriggerCondition(ticker="NVDA")
        data = condition.model_dump(exclude_none=True)
        assert "ticker" in data
        assert "condition_type" not in data
        assert "expression" not in data
