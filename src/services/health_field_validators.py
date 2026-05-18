"""
Shape validators for Story 3.1 Tier 1 health profile fields.

Used by:
- src/routers/profile.py PUT /v1/profile/{category}/{field_name}
  to reject malformed manual edits with HTTP 400 + a descriptive message.

Each validator returns None on success and raises ValueError(message) on failure.
The caller is responsible for translating ValueError into the appropriate HTTP
response (HTTPException with status_code=400 and detail=message).

Validators are intentionally permissive about extra keys on object-shaped fields
(open schema) — they reject only on the *wrong* shape or *invalid* enum values.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict


# Canonical enums — single source of truth
BLOOD_TYPES = frozenset({"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"})
BIOLOGICAL_SEX_VALUES = frozenset({"male", "female", "intersex", "prefer_not_to_say"})

# Date strings must be either "YYYY-MM-DD" or "YYYY-MM"
_DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _require_number(value: Any, field: str) -> float:
    # Reject bool explicitly — bool is a subclass of int in Python
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number, not a boolean")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def _require_dict(value: Any, field: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _require_list_of_dicts(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{field}[{i}] must be an object")
    return value


def _validate_date_string(value: Any, field: str) -> None:
    s = _require_str(value, field)
    if not _DATE_RE.match(s):
        raise ValueError(
            f"{field} must be a date string in 'YYYY-MM-DD' or 'YYYY-MM' format"
        )


def validate_blood_type(value: Any) -> None:
    s = _require_str(value, "blood_type")
    if s not in BLOOD_TYPES:
        raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPES)}, got {s!r}")


def validate_height_cm(value: Any) -> None:
    n = _require_number(value, "height_cm")
    if n <= 0 or n > 300:
        raise ValueError("height_cm must be > 0 and <= 300")


def validate_weight_baseline_kg(value: Any) -> None:
    n = _require_number(value, "weight_baseline_kg")
    if n <= 0 or n > 500:
        raise ValueError("weight_baseline_kg must be > 0 and <= 500")


def validate_biological_sex(value: Any) -> None:
    s = _require_str(value, "biological_sex")
    if s not in BIOLOGICAL_SEX_VALUES:
        raise ValueError(
            f"biological_sex must be one of {sorted(BIOLOGICAL_SEX_VALUES)}, got {s!r}"
        )


def validate_primary_care_provider(value: Any) -> None:
    d = _require_dict(value, "primary_care_provider")
    # Open schema — only require that 'name' exists if any keys exist at all.
    # An empty {} would mean "we know you have one but no details" — reject as useless.
    if not d:
        raise ValueError(
            "primary_care_provider must contain at least one key (typically 'name')"
        )


def validate_specialists(value: Any) -> None:
    _require_list_of_dicts(value, "specialists")


def validate_insurance(value: Any) -> None:
    d = _require_dict(value, "insurance")
    if not d:
        raise ValueError(
            "insurance must contain at least one key (typically 'provider')"
        )


def validate_immunizations(value: Any) -> None:
    items = _require_list_of_dicts(value, "immunizations")
    for i, item in enumerate(items):
        if "vaccine" not in item or not isinstance(item.get("vaccine"), str):
            raise ValueError(
                f"immunizations[{i}] must include a string 'vaccine' field"
            )


def validate_last_physical_date(value: Any) -> None:
    _validate_date_string(value, "last_physical_date")


def validate_dental_care_last(value: Any) -> None:
    _validate_date_string(value, "dental_care_last")


def validate_eye_care_last(value: Any) -> None:
    _validate_date_string(value, "eye_care_last")


def validate_fitness_baseline(value: Any) -> None:
    _require_dict(value, "fitness_baseline")


def validate_sleep_baseline(value: Any) -> None:
    _require_dict(value, "sleep_baseline")


def validate_devices(value: Any) -> None:
    items = _require_list_of_dicts(value, "devices")
    for i, item in enumerate(items):
        if "type" not in item or not isinstance(item.get("type"), str):
            raise ValueError(f"devices[{i}] must include a string 'type' field")


def validate_family_medical_history_summary(value: Any) -> None:
    _require_str(value, "family_medical_history_summary")


# Registry: (category, field_name) -> validator function.
# Only Tier 1 health fields with structured shapes are listed here.
# Free-form text / array-of-strings fields (allergies, dietary_needs, medications,
# health_conditions when still a string, etc.) are intentionally NOT validated —
# they accept any reasonable value.
HEALTH_FIELD_VALIDATORS: Dict[str, Callable[[Any], None]] = {
    "blood_type": validate_blood_type,
    "height_cm": validate_height_cm,
    "weight_baseline_kg": validate_weight_baseline_kg,
    "biological_sex": validate_biological_sex,
    "primary_care_provider": validate_primary_care_provider,
    "specialists": validate_specialists,
    "insurance": validate_insurance,
    "immunizations": validate_immunizations,
    "last_physical_date": validate_last_physical_date,
    "dental_care_last": validate_dental_care_last,
    "eye_care_last": validate_eye_care_last,
    "fitness_baseline": validate_fitness_baseline,
    "sleep_baseline": validate_sleep_baseline,
    "devices": validate_devices,
    "family_medical_history_summary": validate_family_medical_history_summary,
}


def validate_field(category: str, field_name: str, value: Any) -> None:
    """
    Validate a profile field value against its known shape.

    Currently only Tier 1 health fields (Story 3.1) have shape validation.
    Unknown (category, field_name) pairs pass through unchanged.

    Raises:
        ValueError: with a descriptive message on shape mismatch.
    """
    if category != "health":
        return
    validator = HEALTH_FIELD_VALIDATORS.get(field_name)
    if validator is None:
        return
    validator(value)
