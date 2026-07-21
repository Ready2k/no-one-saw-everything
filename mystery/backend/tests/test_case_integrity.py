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
