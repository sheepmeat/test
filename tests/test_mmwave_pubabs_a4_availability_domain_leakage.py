"""Focused integrity tests for PUBABS-A4 audit artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "datasets/mmwave/manifests/PUBABS_A4_c1_availability_domain_leakage"
PROP = (
    ROOT
    / "datasets/mmwave/manifests/PUBABS_A3C_corrective_contract_proposal/proposed_adapter_contract.json"
)
FROZEN = "cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446"
A3R = (
    ROOT
    / "datasets/mmwave/manifests/PUBABS_A3R_c1_frozen_adapter_revalidation/session_results.json"
)


@pytest.mark.skipif(not MAN.exists(), reason="A4 manifests not generated yet")
def test_a4_population_integrity():
    rows = json.loads((MAN / "all77_availability_audit.json").read_text())["sessions"]
    assert len(rows) == 77
    assert len({r["zip_member"] for r in rows}) == 77
    assert sum(1 for r in rows if r["reporting_class"] == "ABSENT") == 11
    assert sum(1 for r in rows if r["reporting_class"] == "PRESENT") == 66
    assert sum(1 for r in rows if r["adapter_status"] == "VALID") == 34
    assert sum(1 for r in rows if r["adapter_status"] != "VALID") == 43
    assert (
        sum(
            1
            for r in rows
            if r.get("fail_closed_code") == "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP"
        )
        == 42
    )
    assert (
        sum(
            1
            for r in rows
            if r.get("fail_closed_code") == "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S"
        )
        == 1
    )


@pytest.mark.skipif(not MAN.exists(), reason="A4 manifests not generated yet")
def test_a4_matches_a3r_status():
    a4 = {
        r["zip_member"]: r
        for r in json.loads((MAN / "all77_availability_audit.json").read_text())["sessions"]
    }
    a3r = json.loads(A3R.read_text())
    assert len(a3r) == 77
    for r in a3r:
        assert a4[r["zip_member"]]["adapter_status"] == r["status"]
        assert a4[r["zip_member"]]["fail_closed_code"] == r.get("fail_closed_code")


def test_frozen_contract_hash_unchanged():
    assert hashlib.sha256(PROP.read_bytes()).hexdigest() == FROZEN


def test_historical_r1_file_present_and_profile_stable():
    text = (ROOT / "adapters/mmwave_r1_sensor_independent_trace.py").read_text()
    assert "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1" in text


def test_adapter_api_has_no_class_parameter():
    from adapters.mmwave_pubabs_c1_frozen_adapter import adapt_c1_raw
    import inspect

    params = list(inspect.signature(adapt_c1_raw).parameters)
    assert "reporting_class" not in params
    assert "class_label" not in params
    assert "label" not in params
