"""Focused tests for the M-PV3.8 ABSENT capture-preflight record."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_mmwave_m_pv38_absent_capture_preflight import validate


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_capture_preflight"


def test_preflight_is_validly_blocked_without_capture() -> None:
    result = validate()
    assert result["ok"] is True
    assert result["status"] == "CAPTURE_BLOCKED"
    assert result["capture_authorized"] is False
    assert result["capture_performed"] is False


def test_preflight_preserves_no_campaign_artifact_state() -> None:
    preflight = json.loads((OUT / "preflight_readiness.json").read_text(encoding="utf-8"))
    assert preflight["campaign_structure"]["predeclared_slots_created"] == 0
    assert preflight["campaign_structure"]["slot_lock_created"] is False
    assert all(value is False for value in preflight["artifact_state"].values())
    assert preflight["prohibitions_preserved"]["membership_constructed"] is False
