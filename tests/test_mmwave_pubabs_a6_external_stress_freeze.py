"""Focused tests for PUBABS-A6 external-stress population freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "datasets/mmwave/manifests/PUBABS_A6_c1_external_stress_freeze"
A3R = (
    ROOT
    / "datasets/mmwave/manifests/PUBABS_A3R_c1_frozen_adapter_revalidation/session_results.json"
)
PROP = (
    ROOT
    / "datasets/mmwave/manifests/PUBABS_A3C_corrective_contract_proposal/proposed_adapter_contract.json"
)
FROZEN = "cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446"
EXPECTED_PRESENT_VALID = {"N1": 1, "N2": 1, "N3": 9, "N4": 8, "N5": 6, "N6": 0}


pytestmark = pytest.mark.skipif(not MAN.exists(), reason="A6 manifests not generated yet")


def _load(name: str):
    return json.loads((MAN / name).read_text())


def test_layer_counts_and_subset():
    l1 = _load("layer1_all77_population.json")["sessions"]
    l2 = _load("layer2_valid34_population.json")["sessions"]
    assert len(l1) == 77
    assert len(l2) == 34
    l1_ids = {r["external_stress_session_id"] for r in l1}
    assert all(r["external_stress_session_id"] in l1_ids for r in l2)
    assert all(r["layer1_member"] for r in l1)
    assert all(r["layer2_member"] for r in l2)
    assert all(r["adapter_status"] == "VALID" for r in l2)
    assert all(r.get("fail_closed_code") is None for r in l2)


def test_layer2_iff_a3r_valid():
    a3r = {r["zip_member"]: r for r in json.loads(A3R.read_text())}
    l1 = _load("layer1_all77_population.json")["sessions"]
    for r in l1:
        upstream = a3r[r["canonical_source_path"]]
        expect_l2 = upstream["status"] == "VALID"
        assert r["layer2_member"] is expect_l2
        assert r["adapter_status"] == upstream["status"]
        assert r.get("fail_closed_code") == upstream.get("fail_closed_code")


def test_fail_closed_preserved_in_layer1_only():
    l1 = _load("layer1_all77_population.json")["sessions"]
    fail = [r for r in l1 if r["adapter_status"] != "VALID"]
    assert len(fail) == 43
    assert all(r["layer1_member"] and not r["layer2_member"] for r in fail)
    assert all(r["fail_closed_code"] for r in fail)
    codes = {r["fail_closed_code"] for r in fail}
    assert "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP" in codes
    assert "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S" in codes


def test_class_and_subject_composition():
    l2 = _load("layer2_valid34_population.json")["sessions"]
    assert sum(1 for r in l2 if r["reporting_class"] == "ABSENT") == 9
    assert sum(1 for r in l2 if r["reporting_class"] == "PRESENT") == 25
    from collections import Counter

    got = Counter(
        r["subject_or_empty_identity"]
        for r in l2
        if r["reporting_class"] == "PRESENT"
    )
    for k, v in EXPECTED_PRESENT_VALID.items():
        assert got.get(k, 0) == v
    assert all(r["layer2_semantics"] == "CONDITIONAL_ON_ADAPTER_VALID" for r in l2)


def test_no_d1_identity_as_target():
    contract = _load("external_stress_contract.json")
    assert contract["contract_id"] == "PUBABS_C1_EXTERNAL_STRESS_V1"
    assert "D1_FINAL_SELECTION_BOTH_CLASS_V1" not in contract["contract_id"]
    assert contract["future_authority"]["eligible_for_D1"] is False
    assert contract["future_authority"]["eligible_for_M_PV3_8_final_selection"] is False


def test_frozen_adapter_hash_and_tensor_receipts():
    assert hashlib.sha256(PROP.read_bytes()).hexdigest() == FROZEN
    contract = _load("external_stress_contract.json")
    assert contract["frozen_adapter_hash"] == FROZEN
    l2 = _load("layer2_valid34_population.json")["sessions"]
    for r in l2:
        assert r["r1t_10hz_sha256"]
        assert r["r1_centered_sha256"]
        assert r["train_zscore_trace_sha256"]
        assert r["selected_bin"] is not None


def test_determinism_receipt_and_no_model_imports():
    repro = _load("reproducibility_receipt.json")
    assert repro["identical_manifest_sha256"] is True
    script = (
        ROOT / "scripts/mmwave/pubabs_a6_freeze_external_stress_population.py"
    ).read_text()
    assert "tf.lite" not in script
    assert "Interpreter(" not in script
    assert "tensorflow" not in script.lower()
    assert "family b" not in script.lower()
    assert "family c" not in script.lower()
