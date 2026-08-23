"""Focused tests for the M-PV3.8 ABSENT resource-readiness checklist."""

from scripts.validate_mmwave_m_pv38_absent_resource_readiness_checklist import validate


def test_readiness_checklist_is_valid_without_authorizing_capture() -> None:
    result = validate()
    assert result["ok"] is True
    assert result["capture_authorized"] is False
    assert result["capture_started"] is False
