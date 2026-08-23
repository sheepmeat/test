"""Focused tests for the M-PV3.8 lifecycle closure state."""

from scripts.validate_mmwave_m_pv38_lifecycle_state_consolidation import validate


def test_lifecycle_closure_is_consistent_and_non_executing() -> None:
    result = validate()
    assert result["ok"] is True
    assert result["closure_status"] == "RESOURCE_BLOCKED_CLOSED"
