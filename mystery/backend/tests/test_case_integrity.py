"""Fairness-validator-style checks for the hand-authored case (spec 09).

These run against the locked case data using the reusable validator and fail
if the mystery is unsolvable, leaky, or internally inconsistent.
"""

import pytest

from app.case_store import load_case_from_disk as load_case
from app.validator import validate_case


@pytest.fixture(scope="module")
def case():
    return load_case("case_001")


def test_golden_case_is_valid(case):
    result = validate_case(case)

    assert result["valid"], f"Golden case failed validation with errors: {result['errors']}"
    # Optionally, we can also assert no warnings for the golden case to ensure it's perfect.
    assert len(result["warnings"]) == 0, f"Golden case has warnings: {result['warnings']}"


ALL_CASE_IDS = ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006", "case_007"]


@pytest.mark.parametrize("case_id", ALL_CASE_IDS)
def test_every_shipped_case_passes_the_fairness_gate(case_id):
    """validate_case() with zero errors is the ship gate for EVERY case.

    Cases 002–006 once shipped invalid because nothing ran this; it is now a test,
    so an invalid case cannot ship again."""
    result = validate_case(load_case(case_id))
    assert result["valid"], f"{case_id} failed the fairness gate: {result['errors']}"
    assert result["errors"] == []
