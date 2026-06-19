"""Necessity gate routing — backend.office.necessity.classify."""

import pytest

from backend.office import necessity


@pytest.mark.parametrize(
    "category, route, who, requires_physician",
    [
        ("sick_note", "eliminate", "patient", False),
        ("disability_tax_credit", "physician_review", "physician", True),
        ("insurance_std", "physician_review", "physician", True),
        ("rx_renewal_stable", "automate", "pharmacist / protocol", False),
        ("school_note", "physician_review", "physician", True),
        ("monitoring_requisition", "automate", "standing order", False),
    ],
)
def test_classify_routes(category, route, who, requires_physician):
    result = necessity.classify(category)
    assert result["route"] == route
    assert result["who"] == who
    assert result["requires_physician"] is requires_physician


def test_unknown_category_defaults_to_physician_review():
    result = necessity.classify("not_a_real_category")
    assert result["route"] == "physician_review"
    assert result["requires_physician"] is True
