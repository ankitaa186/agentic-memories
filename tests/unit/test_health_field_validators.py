"""
Unit tests for src/services/health_field_validators.py (Story 3.1).

These tests cover the Tier 1 health field shape validators used by
PUT /v1/profile/{category}/{field_name} to reject malformed manual edits.
"""

import pytest

from src.services.health_field_validators import (
    BIOLOGICAL_SEX_VALUES,
    BLOOD_TYPES,
    HEALTH_FIELD_VALIDATORS,
    validate_field,
)


# --- non-health passthrough ----------------------------------------------


def test_validate_field_passes_through_non_health_categories():
    # Validators only fire for category == "health"
    validate_field("basics", "name", "Alice")
    validate_field("preferences", "food_preferences", ["Indian", "Italian"])
    validate_field("personality", "personality_type", "INTJ")


def test_validate_field_passes_through_unknown_health_field():
    # Existing free-form health fields without a registered validator should pass.
    validate_field("health", "allergies", ["penicillin"])
    validate_field("health", "dietary_needs", "gluten-free")
    validate_field("health", "medications", ["ibuprofen"])


# --- blood_type ----------------------------------------------------------


@pytest.mark.parametrize("value", sorted(BLOOD_TYPES))
def test_blood_type_accepts_all_canonical_values(value):
    validate_field("health", "blood_type", value)


@pytest.mark.parametrize("value", ["A", "AB", "o+", "Z+", "", 42, None, []])
def test_blood_type_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="blood_type"):
        validate_field("health", "blood_type", value)


# --- height_cm -----------------------------------------------------------


@pytest.mark.parametrize("value", [50, 175, 175.5, 300])
def test_height_cm_accepts_valid_numbers(value):
    validate_field("health", "height_cm", value)


@pytest.mark.parametrize(
    "value",
    [
        0,  # zero
        -10,  # negative
        301,  # over max
        "175",  # string
        True,  # bool (subclass of int)
        None,
        [175],
    ],
)
def test_height_cm_rejects_invalid(value):
    with pytest.raises(ValueError, match="height_cm"):
        validate_field("health", "height_cm", value)


# --- weight_baseline_kg --------------------------------------------------


@pytest.mark.parametrize("value", [1, 76, 76.2, 500])
def test_weight_baseline_kg_accepts_valid_numbers(value):
    validate_field("health", "weight_baseline_kg", value)


@pytest.mark.parametrize("value", [0, -1, 501, "76", False, None])
def test_weight_baseline_kg_rejects_invalid(value):
    with pytest.raises(ValueError, match="weight_baseline_kg"):
        validate_field("health", "weight_baseline_kg", value)


# --- biological_sex ------------------------------------------------------


@pytest.mark.parametrize("value", sorted(BIOLOGICAL_SEX_VALUES))
def test_biological_sex_accepts_canonical(value):
    validate_field("health", "biological_sex", value)


@pytest.mark.parametrize("value", ["Male", "FEMALE", "m", "f", "", 1, None])
def test_biological_sex_rejects_invalid(value):
    with pytest.raises(ValueError, match="biological_sex"):
        validate_field("health", "biological_sex", value)


# --- primary_care_provider -----------------------------------------------


def test_primary_care_provider_accepts_object_with_at_least_one_key():
    validate_field(
        "health",
        "primary_care_provider",
        {"name": "Dr. Patel", "clinic": "Bay Area Medical"},
    )
    # Open schema — extra keys allowed
    validate_field(
        "health",
        "primary_care_provider",
        {"name": "Dr. Patel", "phone": "555-1234", "fax": "555-5678"},
    )


@pytest.mark.parametrize("value", [{}, "Dr. Patel", [], None, 42])
def test_primary_care_provider_rejects_invalid(value):
    with pytest.raises(ValueError, match="primary_care_provider"):
        validate_field("health", "primary_care_provider", value)


# --- specialists ---------------------------------------------------------


def test_specialists_accepts_list_of_objects():
    validate_field(
        "health",
        "specialists",
        [
            {"specialty": "cardiologist", "name": "Dr. Smith"},
            {"specialty": "dermatologist", "name": "Dr. Lee"},
        ],
    )
    # Empty list is allowed (means "user has none documented")
    validate_field("health", "specialists", [])


def test_specialists_rejects_non_list():
    with pytest.raises(ValueError, match="specialists"):
        validate_field("health", "specialists", {"specialty": "cardiologist"})


def test_specialists_rejects_list_of_non_dicts():
    with pytest.raises(ValueError, match=r"specialists\[0\]"):
        validate_field("health", "specialists", ["cardiologist"])


# --- insurance -----------------------------------------------------------


def test_insurance_accepts_object():
    validate_field("health", "insurance", {"provider": "Aetna", "plan": "PPO"})


@pytest.mark.parametrize("value", [{}, "Aetna", []])
def test_insurance_rejects_invalid(value):
    with pytest.raises(ValueError, match="insurance"):
        validate_field("health", "insurance", value)


# --- immunizations -------------------------------------------------------


def test_immunizations_accepts_valid_list():
    validate_field(
        "health",
        "immunizations",
        [
            {"vaccine": "MMR", "date": "1985"},
            {"vaccine": "COVID-19", "date": "2025-09"},
        ],
    )


def test_immunizations_requires_vaccine_field():
    with pytest.raises(ValueError, match=r"immunizations\[0\]"):
        validate_field("health", "immunizations", [{"date": "2025-09"}])
    with pytest.raises(ValueError, match=r"immunizations\[0\]"):
        validate_field("health", "immunizations", [{"vaccine": 123}])


# --- date fields ---------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["last_physical_date", "dental_care_last", "eye_care_last"]
)
@pytest.mark.parametrize("value", ["2026-05-17", "2025-10", "1999-12-31"])
def test_date_fields_accept_valid_formats(field, value):
    validate_field("health", field, value)


@pytest.mark.parametrize(
    "field", ["last_physical_date", "dental_care_last", "eye_care_last"]
)
@pytest.mark.parametrize(
    "value",
    [
        "2026/05/17",  # wrong separator
        "May 17 2026",  # wrong format entirely
        "2026-5-17",  # missing leading zero
        "26-05-17",  # 2-digit year
        "",
        20260517,
        None,
    ],
)
def test_date_fields_reject_invalid_formats(field, value):
    with pytest.raises(ValueError, match=field):
        validate_field("health", field, value)


@pytest.mark.parametrize(
    "field", ["last_physical_date", "dental_care_last", "eye_care_last"]
)
@pytest.mark.parametrize(
    "value",
    [
        "2026-13",  # month > 12
        "2026-00",  # month < 1
        "2026-99",  # month > 12 (regex-shape valid)
        "2026-02-30",  # Feb 30 doesn't exist
        "2026-02-99",  # day > max
        "2026-13-01",  # month > 12 with day
        "2026-04-31",  # April 31 doesn't exist
        "2025-02-29",  # 2025 isn't a leap year
    ],
)
def test_date_fields_reject_invalid_calendar_dates(field, value):
    """Codex review: regex was matching impossible calendar dates."""
    with pytest.raises(ValueError, match=field):
        validate_field("health", field, value)


@pytest.mark.parametrize(
    "field", ["last_physical_date", "dental_care_last", "eye_care_last"]
)
@pytest.mark.parametrize(
    "value",
    [
        "2024-02-29",  # 2024 IS a leap year — valid
        "2026-12-31",  # last day of year
        "2026-01-01",  # first day of year
    ],
)
def test_date_fields_accept_edge_calendar_dates(field, value):
    validate_field("health", field, value)


# --- fitness_baseline / sleep_baseline ----------------------------------


def test_fitness_baseline_accepts_dict():
    validate_field(
        "health",
        "fitness_baseline",
        {"resting_hr": 58, "vo2max": 42, "activity_level": "moderate"},
    )


def test_fitness_baseline_rejects_non_dict():
    with pytest.raises(ValueError, match="fitness_baseline"):
        validate_field("health", "fitness_baseline", 58)


def test_sleep_baseline_accepts_dict():
    validate_field(
        "health",
        "sleep_baseline",
        {"typical_duration_hr": 7.5, "typical_bedtime": "23:30"},
    )


def test_sleep_baseline_rejects_list():
    with pytest.raises(ValueError, match="sleep_baseline"):
        validate_field("health", "sleep_baseline", [7.5, "23:30"])


# --- devices -------------------------------------------------------------


def test_devices_accepts_list_of_typed_objects():
    validate_field(
        "health",
        "devices",
        [
            {"type": "CPAP", "model": "ResMed AirSense 10"},
            {"type": "glucose_monitor", "model": "Dexcom G7"},
        ],
    )
    validate_field("health", "devices", [])


def test_devices_requires_type_field():
    with pytest.raises(ValueError, match=r"devices\[0\]"):
        validate_field("health", "devices", [{"model": "ResMed AirSense 10"}])


# --- family_medical_history_summary --------------------------------------


def test_family_medical_history_summary_accepts_string():
    validate_field(
        "health",
        "family_medical_history_summary",
        "Father: heart attack at 55. Mother: T2D at 60.",
    )


def test_family_medical_history_summary_rejects_non_string():
    with pytest.raises(ValueError, match="family_medical_history_summary"):
        validate_field("health", "family_medical_history_summary", [])


# --- registry sanity -----------------------------------------------------


def test_registry_covers_all_structured_tier1_fields():
    """The validator registry must cover every Tier 1 health field with a
    structured shape (enum, number, object, list). Free-form text/array
    fields (allergies, dietary_needs, etc.) are intentionally absent."""
    expected = {
        "blood_type",
        "height_cm",
        "weight_baseline_kg",
        "biological_sex",
        "primary_care_provider",
        "specialists",
        "insurance",
        "immunizations",
        "last_physical_date",
        "dental_care_last",
        "eye_care_last",
        "fitness_baseline",
        "sleep_baseline",
        "devices",
        "family_medical_history_summary",
    }
    assert set(HEALTH_FIELD_VALIDATORS.keys()) == expected
