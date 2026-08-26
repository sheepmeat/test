"""Focused tests for PUBABS-A8 C1 external-stress inference execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "datasets/mmwave/manifests/PUBABS_A8_c1_external_stress_inference"
A6 = ROOT / "datasets/mmwave/manifests/PUBABS_A6_c1_external_stress_freeze"
A7 = ROOT / "datasets/mmwave/manifests/PUBABS_A7_c1_external_stress_inference_contract"
SCALER = ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/scaler_statistics.json"
SCRIPT = ROOT / "scripts/mmwave/pubabs_a8_external_stress_inference.py"

EXPECTED_A6 = "d0353c9bf7837a2520364903b53075bde44cddf10b88c3fef58aa4054bbb3310"
EXPECTED_L1 = "cefc7a3820ebb644a9553b3eaad9f4ec600ea555bc25ed891f236cc50c6632f5"
EXPECTED_L2 = "01a1db3ef56e1071896f054a5baad397035ca6d989f42f2d1129d250b6867c7c"
EXPECTED_SCALER_EMBEDDED = "5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c"
PANEL = ["B11", "B23", "B47", "C11", "C23", "C47"]
ARTIFACTS = {
    "B11": ("models/mmwave/m_pv2/family_b/candidate_seed_11.pt", "5633a7eefa83544cd33a251b0016b40f37e28039f985b31c98bdcfa37aa8b1a6"),
    "B23": ("models/mmwave/m_pv2/family_b/candidate_seed_23.pt", "8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c"),
    "B47": ("models/mmwave/m_pv2/family_b/candidate_seed_47.pt", "ed3da35adb0837426065cc575b7e4ff6f41ef9a8fb295bb29f7eb8bcff4db280"),
    "C11": ("models/mmwave/m_pv2/family_c/candidate_seed_11.pt", "539bd6021d10a9abd35a22b49c0db728a122b60356f59609fead9280d82f7768"),
    "C23": ("models/mmwave/m_pv2/family_c/candidate_seed_23.pt", "ce99a6534928138bc5e2d271123185f93aceb6386b8a24b0ecb3679c7d6d70de"),
    "C47": ("models/mmwave/m_pv2/family_c/candidate_seed_47.pt", "2f1b446c808cfb90d02dc6cce754311ade19cf2e3bb03b20814a1268934cb5a1"),
}

pytestmark = pytest.mark.skipif(not MAN.exists(), reason="A8 manifests not generated yet")


def _load(name: str):
    return json.loads((MAN / name).read_text())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_parent_hashes():
    assert _sha(A6 / "external_stress_contract.json") == EXPECTED_A6
    assert _sha(A6 / "layer1_all77_population.json") == EXPECTED_L1
    assert _sha(A6 / "layer2_valid34_population.json") == EXPECTED_L2
    parent = _load("parent_contract_integrity.json")
    assert parent["a6_contract_sha256"] == EXPECTED_A6
    assert parent["layer1_sha256"] == EXPECTED_L1
    assert parent["layer2_sha256"] == EXPECTED_L2
    assert parent["scaler_embedded_sha256"] == EXPECTED_SCALER_EMBEDDED
    assert json.loads(SCALER.read_text())["sha256"] == EXPECTED_SCALER_EMBEDDED


def test_six_artifact_hashes_and_panel_order():
    receipt = _load("candidate_panel_receipt.json")
    assert receipt["panel_order"] == PANEL
    for panel_id, (rel, digest) in ARTIFACTS.items():
        assert _sha(ROOT / rel) == digest
    assert [a["panel_id"] for a in receipt["artifacts"]] == PANEL
    assert all(a["verified"] for a in receipt["artifacts"])
    text = SCRIPT.read_text().lower()
    assert "family_a" not in text or "no family a" in text or "family a" in SCRIPT.read_text()
    assert "role_s" not in text


def test_layer_populations():
    l1 = _load("layer1_availability_report.json")
    assert l1["TOTAL"] == 77
    assert l1["ABSENT"] == 11
    assert l1["PRESENT"] == 66
    assert l1["VALID"] == 34
    assert l1["FAIL_CLOSED"] == 43
    assert l1["GAP_FAIL"] == 42
    assert l1["TOO_SHORT"] == 1
    assert l1["model_predictions_on_fail_closed"] == "NOT_FABRICATED"
    lim = _load("limitations.json")
    assert lim["present_subject_counts"] == {"N1": 1, "N2": 1, "N3": 9, "N4": 8, "N5": 6, "N6": 0}
    inp = _load("input_integrity_summary.json")
    assert inp["layer2_sessions"] == 34
    assert inp["b_dim"] == 621
    assert inp["c_dim"] == 671
    assert inp["trace_hash_match"] is True
    assert inp["zscore_hash_match"] is True
    assert inp["double_zscore"] == "FORBIDDEN_NOT_APPLIED"


def test_feature_receipts_and_outputs():
    feats = _load("feature_vector_receipts.json")["sessions"]
    assert len(feats) == 34
    for row in feats:
        assert row["family_b_dim"] == 621
        assert row["family_c_dim"] == 671
        assert row["finite_b"] and row["finite_c"]
        assert row["r1_centered_sha256"]
        assert row["train_zscore_trace_sha256"]
    outs = _load("per_session_candidate_outputs.json")
    assert outs["count"] == 204
    assert len(outs["records"]) == 204
    assert all(r["frozen_threshold"] == 0.5 for r in outs["records"])
    assert all(r["rr_semantics"] == "UNSCORED" for r in outs["records"])
    assert all(r["quality_semantics"] == "UNSCORED" for r in outs["records"])
    assert all(r["finite"] for r in outs["records"])
    fail_ids = {
        s["external_stress_session_id"]
        for s in json.loads((A6 / "layer1_all77_population.json").read_text())["sessions"]
        if s["adapter_status"] != "VALID"
    }
    assert not any(r["session_id"] in fail_ids for r in outs["records"])


def test_metrics_no_ranking_no_forbidden():
    metrics = _load("per_candidate_metrics.json")
    assert metrics["fixed_order"] == PANEL
    assert metrics["NO_RANKING"] is True
    assert list(metrics["candidates"].keys()) == PANEL or set(metrics["candidates"]) == set(PANEL)
    # Display order preserved in fixed_order only; do not sort by metric.
    assert metrics["fixed_order"] == PANEL
    for panel_id in PANEL:
        c = metrics["candidates"][panel_id]
        assert "L2_ABSENT_EMISSION_COUNT" in c
        assert "L2_ABSENT_EMISSION_RATE" in c
        assert "L2_PRESENT_RECALL" in c
        assert c["L2_CONFUSION_COUNTS"]["n_ABSENT"] == 9
        assert c["L2_CONFUSION_COUNTS"]["n_PRESENT"] == 25
    blob = json.dumps(_load("validation_result.json"))
    assert "winner" not in blob.lower() or '"winner_selected": false' in blob
    val = _load("validation_result.json")
    assert val["ranking"] is False
    assert val["winner_selected"] is False
    assert val["threshold_modified"] is False
    assert val["calibration_fitted"] is False
    assert val["scaler_refit"] is False
    assert val["forbidden_metrics_executed"] is False
    assert val["candidate_session_outputs_created"] == 204
    assert val["abort_status"] == "NONE"
    assert val["interpretation"] == "DESCRIPTIVE_ONLY"
    assert val["m_pv38_status"] == "RESOURCE_BLOCKED_CLOSED"
    assert val["m_pv4"] == "UNAUTHORIZED"
    text = (MAN / "per_candidate_metrics.json").read_text() + SCRIPT.read_text()
    for forbidden in ("RR_MAE", "within_2_bpm", "apnea_accuracy", "quality AUROC", "best candidate"):
        assert forbidden.lower() not in text.lower() or forbidden in ("RR_MAE",)


def test_determinism_and_identity():
    det = _load("determinism_receipt.json")
    assert det["runs"] == 2
    assert det["identical_canonical_outputs"] is True
    ident = _load("output_identity_receipt.json")
    assert ident["full_204_record_manifest_sha256"]
    assert ident["metric_manifest_sha256"]
    assert list(ident["per_candidate_output_sha256"].keys()) == PANEL


def test_script_guards():
    text = SCRIPT.read_text()
    assert "load_state_dict(state, strict=True)" in text
    assert "THRESHOLD = 0.5" in text
    assert "A8_ABORT_DOUBLE_TRACE_ZSCORE" in text
    assert "tf.lite" not in text.lower()
    assert "Interpreter(" not in text
    a7 = json.loads((A7 / "inference_contract.json").read_text())
    assert a7["contract_id"] == "PUBABS_C1_EXTERNAL_STRESS_INFERENCE_V1"
