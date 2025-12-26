"""
Unit tests for timezone validation in IntentValidationService (Epic 6 Story 6.1).

Tests AC1.3: Invalid timezones return validation error with IANA format example.
"""
import pytest

from src.schemas import ScheduledIntentCreate, TriggerSchedule
from src.services.intent_validation import IntentValidationService


def make_intent(timezone: str = "America/Los_Angeles", **kwargs) -> ScheduledIntentCreate:
    """Helper to create a minimal valid intent with timezone."""
    defaults = {
        "user_id": "test-user",
        "intent_name": "Test Intent",
        "trigger_type": "cron",
        "trigger_schedule": TriggerSchedule(
            cron="0 9 * * *",
            timezone=timezone
        ),
        "action_context": "Test context",
    }
    defaults.update(kwargs)
    return ScheduledIntentCreate(**defaults)


@pytest.fixture
def service_no_db():
    """Create validation service without database connection."""
    return IntentValidationService(conn=None)


class TestTimezoneValidation:
    """Tests for timezone validation (AC1.3)."""

    def test_valid_timezone_america_los_angeles(self, service_no_db):
        """Valid timezone America/Los_Angeles passes validation."""
        intent = make_intent(timezone="America/Los_Angeles")
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_timezone_utc(self, service_no_db):
        """Valid timezone UTC passes validation."""
        intent = make_intent(timezone="UTC")
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_timezone_europe_london(self, service_no_db):
        """Valid timezone Europe/London passes validation."""
        intent = make_intent(timezone="Europe/London")
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_timezone_asia_tokyo(self, service_no_db):
        """Valid timezone Asia/Tokyo passes validation."""
        intent = make_intent(timezone="Asia/Tokyo")
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_valid_timezone_australia_sydney(self, service_no_db):
        """Valid timezone Australia/Sydney passes validation."""
        intent = make_intent(timezone="Australia/Sydney")
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_invalid_timezone_format(self, service_no_db):
        """Invalid timezone format fails with descriptive error."""
        intent = make_intent(timezone="Invalid/Zone")
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid timezone: Invalid/Zone" in err for err in result.errors)
        assert any("IANA format" in err for err in result.errors)
        assert any("America/Los_Angeles" in err for err in result.errors)

    def test_invalid_timezone_partial(self, service_no_db):
        """Partial timezone string fails validation."""
        intent = make_intent(timezone="America")
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid timezone" in err for err in result.errors)

    def test_invalid_timezone_numeric(self, service_no_db):
        """Numeric timezone string fails validation."""
        intent = make_intent(timezone="12345")
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid timezone" in err for err in result.errors)

    def test_invalid_timezone_abbreviation(self, service_no_db):
        """Timezone abbreviation (PST) fails - IANA requires full name."""
        intent = make_intent(timezone="PST")
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid timezone" in err for err in result.errors)

    def test_invalid_timezone_offset_format(self, service_no_db):
        """UTC offset format (UTC-8) fails - IANA requires zone name."""
        intent = make_intent(timezone="UTC-8")
        result = service_no_db.validate(intent)
        assert result.is_valid is False
        assert any("Invalid timezone" in err for err in result.errors)

    def test_default_timezone_is_used(self, service_no_db):
        """Default timezone (America/Los_Angeles) is applied when not specified."""
        # Create intent without explicitly setting timezone
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Test Intent",
            trigger_type="cron",
            trigger_schedule=TriggerSchedule(cron="0 9 * * *"),
            action_context="Test context",
        )
        assert intent.trigger_schedule.timezone == "America/Los_Angeles"
        result = service_no_db.validate(intent)
        assert result.is_valid is True

    def test_no_schedule_no_timezone_error(self, service_no_db):
        """Intent without trigger_schedule skips timezone validation gracefully."""
        intent = ScheduledIntentCreate(
            user_id="test-user",
            intent_name="Test Intent",
            trigger_type="price",
            action_context="Test context",
        )
        result = service_no_db.validate(intent)
        # Should not have timezone errors (but may have other validation errors)
        assert not any("timezone" in err.lower() for err in result.errors)
