"""Focused tests for the M-PV3.8 ABSENT feasibility decision audit."""

from scripts.validate_mmwave_m_pv38_absent_acquisition_feasibility_audit import validate


def test_feasibility_audit_is_valid_and_does_not_authorize_capture() -> None:
    result = validate()
    assert result["ok"] is True
    assert result["status"] == "ACQUISITION_REQUIRES_RESOURCE_ACCESS"
    assert result["capture_authorized"] is False
    assert result["capture_performed"] is False
