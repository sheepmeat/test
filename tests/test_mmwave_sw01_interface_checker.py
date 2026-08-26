"""Focused tests for MMWAVE-V2-D1-SWPREP-01 SW-01 interface checker."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/mmwave/check_m_pv38_mmwave_interface.py"
FIX = ROOT / "datasets/mmwave/manifests/MMWAVE_V2_D1_sw01_interface_checker_01/fixtures"
MAN = ROOT / "datasets/mmwave/manifests/MMWAVE_V2_D1_sw01_interface_checker_01"
LIB = ROOT / "adapters/mmwave_sw01_interface_checker.py"


def _run_fixture(name: str) -> dict:
    out = subprocess.check_output(
        [sys.executable, str(CLI), "--fixture", str(FIX / name)],
        cwd=str(ROOT),
        text=True,
    )
    return json.loads(out)


def test_valid_and_deterministic():
    a = _run_fixture("valid_stream.json")
    b = _run_fixture("valid_stream.json")
    assert a == b
    assert a["overall_status"] == "PASS_NON_CAMPAIGN_INTERFACE_CHECK"
    assert a["mode"] == "FIXTURE_OFFLINE_VALIDATION"
    assert a["campaign_data_created"] is False
    assert a["d1_admissible"] is False
    assert a["campaign_slot_consumed"] is False
    assert a["model_inference"] is False
    assert a["role_l_loaded"] is False


@pytest.mark.parametrize(
    "name,status",
    [
        ("missing_raw.json", "FAIL_RAW_OR_NEAR_RAW_UNAVAILABLE"),
        ("missing_timestamp.json", "FAIL_REQUIRED_FIELD_MISSING"),
        ("non_monotonic.json", "FAIL_NON_MONOTONIC_TIMESTAMP"),
        ("dropout_sequence_gap.json", "FAIL_CONTINUITY_UNOBSERVABLE"),
        ("health_fault.json", "FAIL_HEALTH_UNAVAILABLE"),
        ("backend_unavailable.json", "BACKEND_UNAVAILABLE"),
        ("scalar_only.json", "FAIL_SCALAR_TELEMETRY_ONLY"),
        ("missing_identities.json", "FAIL_REQUIRED_FIELD_MISSING"),
    ],
)
def test_fail_closed_fixtures(name: str, status: str):
    receipt = _run_fixture(name)
    assert receipt["overall_status"] == status
    assert receipt["d1_admissible"] is False
    assert receipt["campaign_data_created"] is False


def test_dropout_and_health_visible():
    drop = _run_fixture("dropout_sequence_gap.json")
    assert drop["dropouts"]
    health = _run_fixture("health_fault.json")
    assert any("health_fault" in f for f in health["faults"])
    reset = _run_fixture("session_reset.json")
    assert reset["resets"]


def test_no_role_l_model_imports_in_checker():
    text = LIB.read_text() + CLI.read_text()
    assert "candidate_seed_" not in text
    assert "MMWaveInterpreter" not in text
    assert "torch.load" not in text
    assert "family_b" not in text
    assert "family_c" not in text
    assert "sensors.mmwave.mmwave_adapter" not in text
    assert "from sensors.mmwave" not in text
    assert "import torch" not in text


def test_live_without_hardware_not_pass():
    out = subprocess.check_output(
        [sys.executable, str(CLI), "--live"],
        cwd=str(ROOT),
        text=True,
    )
    receipt = json.loads(out)
    assert receipt["mode"] == "LIVE_NON_CAMPAIGN_CHECK"
    assert receipt["overall_status"] in {
        "LIVE_TARGET_UNAVAILABLE",
        "BACKEND_UNAVAILABLE",
    }
    assert receipt["overall_status"] != "PASS_NON_CAMPAIGN_INTERFACE_CHECK"
    assert receipt["d1_admissible"] is False


@pytest.mark.skipif(not (MAN / "validation_result.json").exists(), reason="manifests not generated")
def test_manifest_terminal_verdict():
    val = json.loads((MAN / "validation_result.json").read_text())
    assert val["terminal_verdict"] == "SW01_IMPLEMENTED_OFFLINE_VALIDATED_LIVE_PENDING"
    assert val["live_target_available"] is False
    assert val["campaign_data_created"] is False
    assert val["d1_membership_created"] is False
