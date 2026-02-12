"""E2E-style integration tests for Scheduled Intents API with real database.

These tests hit the running Docker container with real HTTP requests and
real TimescaleDB connections. They test the full intent lifecycle.

Run with: pytest tests/integration/test_intents_e2e.py -v

Requires: Docker container running (./scripts/run_docker.sh)
"""

import time
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4


@pytest.mark.e2e
class TestIntentsE2ECRUD:
    """E2E tests for intent CRUD operations with real database."""

    def test_create_intent_interval(self, real_api_client, e2e_config, unique_user_id):
        """Test creating an interval-based intent with real database."""
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Interval Test",
            "description": "Test interval trigger",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "Remind me to check status",
            "action_priority": "normal",
        }

        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )

        assert response.status_code == 201, f"Failed: {response.text}"
        data = response.json()

        # Verify response structure
        assert data["user_id"] == unique_user_id
        assert data["intent_name"] == "E2E Interval Test"
        assert data["trigger_type"] == "interval"
        assert data["enabled"] is True
        assert data["execution_count"] == 0
        assert "id" in data
        assert "next_check" in data

        # Verify next_check is approximately NOW + 30 minutes
        next_check = datetime.fromisoformat(data["next_check"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (next_check - now).total_seconds() / 60
        assert 28 <= delta <= 32, (
            f"next_check should be ~30 min from now, got {delta} min"
        )

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{data['id']}")

    def test_create_intent_cron(self, real_api_client, e2e_config, unique_user_id):
        """Test creating a cron-based intent with real database."""
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Cron Test",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "0 9 * * 1"},  # Every Monday at 9 AM
            "action_context": "Weekly reminder",
        }

        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )

        assert response.status_code == 201, f"Failed: {response.text}"
        data = response.json()

        assert data["trigger_type"] == "cron"
        assert data["trigger_schedule"]["cron"] == "0 9 * * 1"

        # Verify next_check is on a Monday at 9 AM
        next_check = datetime.fromisoformat(data["next_check"].replace("Z", "+00:00"))
        assert next_check.weekday() == 0, "next_check should be on Monday"
        assert next_check.hour == 9, "next_check should be at 9 AM"

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{data['id']}")

    def test_list_intents_by_user(self, real_api_client, e2e_config, unique_user_id):
        """Test listing intents filtered by user with real database."""
        # Create 3 intents
        intent_ids = []
        for i in range(3):
            payload = {
                "user_id": unique_user_id,
                "intent_name": f"E2E List Test {i}",
                "trigger_type": "interval",
                "trigger_schedule": {"interval_minutes": 30 + i * 10},
                "action_context": f"Test action {i}",
            }
            response = real_api_client.post(
                f"{e2e_config.api_base_url}/v1/intents", json=payload
            )
            assert response.status_code == 201
            intent_ids.append(response.json()["id"])

        # List intents for user
        response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents", params={"user_id": unique_user_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Verify all intents belong to the user
        for intent in data:
            assert intent["user_id"] == unique_user_id

        # Cleanup
        for intent_id in intent_ids:
            real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_get_intent_by_id(self, real_api_client, e2e_config, unique_user_id):
        """Test getting a single intent by ID with real database."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Get Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 60},
            "action_context": "Test get by ID",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Get the intent by ID
        response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == intent_id
        assert data["intent_name"] == "E2E Get Test"

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_get_intent_not_found(self, real_api_client, e2e_config):
        """Test 404 for non-existent intent with real database."""
        fake_id = str(uuid4())
        response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{fake_id}"
        )

        assert response.status_code == 404

    def test_update_intent(self, real_api_client, e2e_config, unique_user_id):
        """Test updating an intent with real database."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Update Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "Original context",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Update the intent
        update_payload = {
            "intent_name": "E2E Update Test - Modified",
            "action_context": "Updated context",
            "trigger_schedule": {"interval_minutes": 45},
        }
        response = real_api_client.put(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}", json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["intent_name"] == "E2E Update Test - Modified"
        assert data["action_context"] == "Updated context"

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_update_trigger_type_without_compatible_schedule_fails(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test that changing trigger_type without compatible schedule returns 400.

        This prevents silent data corruption where an intent becomes unschedulable.
        """
        # Create a cron-based intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Update Validation Test",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "0 9 * * *"},
            "action_context": "Test update validation",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Try to change trigger_type to 'interval' without providing interval_minutes
        # This should fail validation because existing schedule has cron, not interval_minutes
        update_payload = {
            "trigger_type": "interval"
            # No trigger_schedule provided - should fail!
        }
        response = real_api_client.put(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}", json=update_payload
        )

        assert response.status_code == 400, (
            f"Expected 400, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "errors" in data
        assert any("interval_minutes" in err.lower() for err in data["errors"])

        # Verify intent is unchanged
        get_response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}"
        )
        assert get_response.status_code == 200
        intent_data = get_response.json()
        assert intent_data["trigger_type"] == "cron"  # Still cron

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_update_trigger_type_with_compatible_schedule_succeeds(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test that changing trigger_type with compatible schedule succeeds."""
        # Create a cron-based intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Update Type Test",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "0 9 * * *"},
            "action_context": "Test update with schedule",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Change trigger_type to 'interval' AND provide compatible schedule
        update_payload = {
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
        }
        response = real_api_client.put(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}", json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["trigger_type"] == "interval"
        assert data["trigger_schedule"]["interval_minutes"] == 30

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_delete_intent(self, real_api_client, e2e_config, unique_user_id):
        """Test deleting an intent with real database."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Delete Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "To be deleted",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Delete the intent
        response = real_api_client.delete(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}"
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}"
        )
        assert get_response.status_code == 404


@pytest.mark.e2e
class TestIntentsE2EFire:
    """E2E tests for intent fire operations with real database."""

    def test_fire_intent_success(self, real_api_client, e2e_config, unique_user_id):
        """Test firing an intent with success status."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Fire Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "Fire test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]
        original_next_check = create_response.json()["next_check"]

        # Fire the intent
        fire_payload = {
            "status": "success",
            "message_id": "e2e-msg-001",
            "trigger_data": {"test": "data"},
            "evaluation_ms": 50,
            "generation_ms": 100,
            "delivery_ms": 25,
        }
        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/fire", json=fire_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["intent_id"] == intent_id
        assert data["status"] == "success"
        assert data["execution_count"] == 1
        assert data["enabled"] is True
        assert data["next_check"] is not None
        assert data["next_check"] != original_next_check

        # Verify the intent was updated in database
        get_response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}"
        )
        assert get_response.status_code == 200
        intent_data = get_response.json()
        assert intent_data["execution_count"] == 1
        assert intent_data["last_execution_status"] == "success"
        assert intent_data["last_message_id"] == "e2e-msg-001"

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_fire_intent_failed_backoff(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test firing an intent with failed status applies 15-min backoff."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Fire Failed Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 60},
            "action_context": "Fire failed test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Fire with failed status
        fire_payload = {"status": "failed", "error_message": "E2E test failure"}
        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/fire", json=fire_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["execution_count"] == 0  # Failed doesn't increment

        # Verify next_check is approximately NOW + 15 minutes (backoff)
        next_check = datetime.fromisoformat(data["next_check"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (next_check - now).total_seconds() / 60
        assert 13 <= delta <= 17, f"Failed should have 15-min backoff, got {delta} min"

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_fire_once_disables_intent(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test firing a one-time intent disables it."""
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Fire Once Test",
            "trigger_type": "once",
            "trigger_schedule": {"trigger_at": future_time},
            "action_context": "One-time fire test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]
        assert create_response.json()["enabled"] is True

        # Fire the intent
        fire_payload = {"status": "success", "message_id": "e2e-once-msg"}
        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/fire", json=fire_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["was_disabled_reason"] == "one-time trigger executed"
        assert data["next_check"] is None

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_fire_condition_not_met_5min_retry(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test condition_not_met applies 5-minute retry."""
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Condition Not Met Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 60},
            "action_context": "Condition not met test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Fire with condition_not_met
        fire_payload = {"status": "condition_not_met"}
        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/fire", json=fire_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["execution_count"] == 0  # Doesn't increment

        # Verify next_check is approximately NOW + 5 minutes
        next_check = datetime.fromisoformat(data["next_check"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (next_check - now).total_seconds() / 60
        assert 4 <= delta <= 6, (
            f"condition_not_met should have 5-min retry, got {delta} min"
        )

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")


@pytest.mark.e2e
class TestIntentsE2EHistory:
    """E2E tests for intent execution history with real database."""

    def test_intent_history(self, real_api_client, e2e_config, unique_user_id):
        """Test getting execution history for an intent."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E History Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "History test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Fire the intent multiple times
        for i in range(3):
            fire_payload = {
                "status": "success" if i % 2 == 0 else "condition_not_met",
                "message_id": f"e2e-hist-msg-{i}" if i % 2 == 0 else None,
                "trigger_data": {"iteration": i},
            }
            fire_response = real_api_client.post(
                f"{e2e_config.api_base_url}/v1/intents/{intent_id}/fire",
                json=fire_payload,
            )
            assert fire_response.status_code == 200
            time.sleep(0.1)  # Small delay to ensure ordering

        # Get history
        response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/history"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Verify ordering (most recent first)
        assert data[0]["trigger_data"]["iteration"] == 2
        assert data[1]["trigger_data"]["iteration"] == 1
        assert data[2]["trigger_data"]["iteration"] == 0

        # Verify history includes all fields
        for execution in data:
            assert "id" in execution
            assert "intent_id" in execution
            assert "executed_at" in execution
            assert "status" in execution

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")

    def test_intent_history_pagination(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test execution history pagination."""
        # Create an intent
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E History Pagination Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 30},
            "action_context": "History pagination test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Fire 5 times
        for i in range(5):
            fire_payload = {"status": "success", "message_id": f"e2e-page-{i}"}
            real_api_client.post(
                f"{e2e_config.api_base_url}/v1/intents/{intent_id}/fire",
                json=fire_payload,
            )
            time.sleep(0.05)

        # Get first page
        response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/history",
            params={"limit": 2, "offset": 0},
        )
        assert response.status_code == 200
        page1 = response.json()
        assert len(page1) == 2

        # Get second page
        response = real_api_client.get(
            f"{e2e_config.api_base_url}/v1/intents/{intent_id}/history",
            params={"limit": 2, "offset": 2},
        )
        assert response.status_code == 200
        page2 = response.json()
        assert len(page2) == 2

        # Verify different records
        assert page1[0]["id"] != page2[0]["id"]

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")


@pytest.mark.e2e
class TestIntentsE2EValidation:
    """E2E tests for intent validation with real database."""

    def test_validation_rejects_invalid_cron(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test validation rejects invalid cron expression."""
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Invalid Cron Test",
            "trigger_type": "cron",
            "trigger_schedule": {"cron": "not a valid cron"},
            "action_context": "Should fail validation",
        }

        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )

        assert response.status_code == 400
        data = response.json()
        assert "errors" in data
        assert any("cron" in err.lower() for err in data["errors"])

    def test_validation_rejects_missing_schedule(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test validation rejects missing required schedule field."""
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Missing Schedule Test",
            "trigger_type": "interval",
            # Missing trigger_schedule.interval_minutes
            "action_context": "Should fail validation",
        }

        response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )

        assert response.status_code == 400
        data = response.json()
        assert "errors" in data

    def test_pending_intents_endpoint(
        self, real_api_client, e2e_config, unique_user_id
    ):
        """Test getting pending intents."""
        # Create an intent (minimum interval is 5 minutes)
        payload = {
            "user_id": unique_user_id,
            "intent_name": "E2E Pending Test",
            "trigger_type": "interval",
            "trigger_schedule": {"interval_minutes": 5},
            "action_context": "Pending test",
        }
        create_response = real_api_client.post(
            f"{e2e_config.api_base_url}/v1/intents", json=payload
        )
        assert create_response.status_code == 201
        intent_id = create_response.json()["id"]

        # Get pending intents
        response = real_api_client.get(f"{e2e_config.api_base_url}/v1/intents/pending")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Cleanup
        real_api_client.delete(f"{e2e_config.api_base_url}/v1/intents/{intent_id}")
