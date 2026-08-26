"""Focused tests for MMWAVE-V2-D1-RESREC-01."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "datasets/mmwave/manifests/MMWAVE_V2_D1_physical_resource_recovery_01"
PLAN = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_acquisition_planning/acquisition_plan.json"
PRE = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_capture_preflight/preflight_readiness.json"

pytestmark = pytest.mark.skipif(not MAN.exists(), reason="RESREC manifests not generated")


def _load(name: str):
    return json.loads((MAN / name).read_text())


def test_plan_unchanged_and_preflight_blocked():
    assert hashlib.sha256(PLAN.read_bytes()).hexdigest() == (
        "797cb281b1d7be9ba3946e34fa0b824df44b44dc436474d63b4d4d472f87c18a"
    )
    pre = json.loads(PRE.read_text())
    assert pre["result"]["status"] == "CAPTURE_BLOCKED"
    val = _load("validation_result.json")
    assert val["preflight_executed"] is False
    assert val["preflight_prerequisites_complete"] is False
    assert val["d1_absent"] == 0
    assert val["d1_present"] == 57
    assert val["governed_absent_capture"] == "NOT_EXECUTED"
    assert val["model_inference"] == "NOT_EXECUTED"
    assert val["m_pv4"] == "UNAUTHORIZED"


def test_matrix_and_fixture_semantics():
    rows = {r["id"]: r for r in _load("resource_matrix.json")["rows"]}
    assert set(rows) == {"B-01", "B-02", "B-03", "B-04", "B-05", "B-06", "B-07"}
    assert rows["B-01"]["blocking"] is True
    assert rows["B-07"]["status"] == "BLOCKED_OWNER_OR_ACCESS"
    tool = _load("tooling_readiness.json")
    assert tool["fixture_demo"]["real_slot_consumed"] is False
    assert tool["fixture_demo"]["d1_membership_entries_created"] == 0
    fix = json.loads((MAN / "fixtures/fixture_campaign_predeclaration.json").read_text())
    assert "FIXTURE_ONLY" in fix["semantics"]
    assert "NOT_D1_MEMBERSHIP" in fix["semantics"]
    assert len(fix["slots"]) == 9


def test_verdicts():
    val = _load("validation_result.json")
    assert val["resource_recovery_verdict"] == "RESREC_PARTIAL_RECOVERY"
    assert val["next_recommendation"] == "RECOMMEND_RESOURCE_ACQUISITION_OR_OWNER_ACTION"
    assert val["live_preflight_ready"] is False
