#!/usr/bin/env python3
"""Focused M-PROT-2 B23 deployable-contract tests. No training, D1 final, D2, or C1 ranking."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from adapters.mmwave_m_prot_2_b23_runtime import (
    BREATHING_THRESHOLD,
    CANONICAL_PARAMETER_SHA256,
    CANDIDATE_ID,
    FAMILY,
    INPUT_DIM,
    PANEL_ID,
    PRIMARY_REPRESENTATION,
    QUALITY_FEATURE_NAMES,
    QUALITY_THRESHOLD,
    SAMPLE_RATE_HZ,
    SCALE_FEATURE_NAMES,
    SCALER_CONTENT_SHA256,
    SEED,
    SOURCE_ARTIFACT_REL,
    SOURCE_ARTIFACT_SHA256,
    TRACE_SAMPLES,
    WINDOW_DURATION_S,
    PrototypeFailClosed,
    assemble_family_b_vector,
    decode_rr,
    load_b23_model,
    run_prototype_inference,
    sha256_file,
    valid_fixture_from_scaler,
    verify_artifact,
    verify_scaler,
)
from scripts.mmwave_m_pv2_candidate_training import TraceModel, _canonical_parameter_sha


ROOT = Path(__file__).resolve().parents[1]


class MProt2DeployableContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scaler = verify_scaler(ROOT)
        cls.model = load_b23_model(ROOT)
        cls.valid = valid_fixture_from_scaler(cls.scaler)

    def test_b23_identity_and_sha(self) -> None:
        self.assertEqual(PANEL_ID, "B23")
        self.assertEqual(CANDIDATE_ID, "M-PV2_FAMILY_B_TRACE_TCN_BREATHING_RR_QUALITY")
        self.assertEqual(FAMILY, "family_b")
        self.assertEqual(SEED, 23)
        self.assertEqual(SOURCE_ARTIFACT_REL, "models/mmwave/m_pv2/family_b/candidate_seed_23.pt")
        self.assertEqual(
            SOURCE_ARTIFACT_SHA256,
            "8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c",
        )
        verify_artifact(ROOT)
        self.assertEqual(sha256_file(ROOT / SOURCE_ARTIFACT_REL), SOURCE_ARTIFACT_SHA256)
        self.assertEqual(_canonical_parameter_sha(self.model), CANONICAL_PARAMETER_SHA256)
        self.assertIsInstance(self.model, TraceModel)

    def test_window_rate_and_feature_contract(self) -> None:
        self.assertEqual(WINDOW_DURATION_S, 30.0)
        self.assertEqual(SAMPLE_RATE_HZ, 10.0)
        self.assertEqual(TRACE_SAMPLES, 300)
        self.assertEqual(INPUT_DIM, 621)
        self.assertEqual(len(SCALE_FEATURE_NAMES), 12)
        self.assertEqual(len(QUALITY_FEATURE_NAMES), 9)
        self.assertEqual(SCALE_FEATURE_NAMES[9], "respiratory_band_energy")
        self.assertEqual(SCALE_FEATURE_NAMES[10], "respiratory_band_power")
        vector = assemble_family_b_vector(
            trace=self.valid["trace"],
            trace_mask=self.valid["trace_mask"],
            scale=self.valid["scale"],
            quality=self.valid["quality"],
            scaler=self.scaler,
        )
        self.assertEqual(vector.shape, (621,))
        self.assertEqual(vector.dtype, np.float32)

    def test_scaler_sha_frozen(self) -> None:
        self.assertEqual(
            SCALER_CONTENT_SHA256,
            "5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c",
        )
        self.assertEqual(self.scaler["sha256"], SCALER_CONTENT_SHA256)

    def test_double_zscore_prohibited(self) -> None:
        with self.assertRaises(PrototypeFailClosed) as ctx:
            assemble_family_b_vector(
                trace=self.valid["trace"],
                trace_mask=self.valid["trace_mask"],
                scale=self.valid["scale"],
                quality=self.valid["quality"],
                scaler=self.scaler,
                already_zscored=True,
            )
        self.assertEqual(ctx.exception.code, "DOUBLE_ZSCORE_FORBIDDEN")
        bad = dict(self.valid)
        bad["already_zscored"] = True
        receipt = run_prototype_inference(bad, root=ROOT, model=self.model, scaler=self.scaler)
        self.assertEqual(receipt.fail_closed_code, "DOUBLE_ZSCORE_FORBIDDEN")
        self.assertIsNone(receipt.breathing_decision)

    def test_positive_path_is_deterministic(self) -> None:
        first = run_prototype_inference(self.valid, root=ROOT, model=self.model, scaler=self.scaler)
        second = run_prototype_inference(self.valid, root=ROOT, model=self.model, scaler=self.scaler)
        self.assertEqual(first.to_json(), second.to_json())
        self.assertIn(first.breathing_decision, {"PRESENT", "ABSENT"})
        self.assertEqual(first.artifact_sha256, SOURCE_ARTIFACT_SHA256)
        self.assertEqual(first.representation, PRIMARY_REPRESENTATION)
        self.assertFalse(first.apnea_emitted)
        self.assertNotEqual(first.breathing_decision, "APNEA")
        self.assertIn("PROTOTYPE_INTEGRATION_ONLY", first.mandatory_semantics)

    def test_thresholds_not_retuned(self) -> None:
        self.assertEqual(BREATHING_THRESHOLD, 0.5)
        self.assertEqual(QUALITY_THRESHOLD, 0.5)
        nomination = json.loads(
            (ROOT / "datasets/mmwave/manifests/M_PROT_1_prototype_candidate_nomination/prototype_nomination.json").read_text()
        )
        self.assertEqual(nomination["nominated"]["prototype_threshold"]["breathing_decision"], 0.5)
        self.assertEqual(nomination["nominated"]["prototype_threshold"]["quality_historical_diagnostic"], 0.5)
        self.assertFalse(nomination["nominated"]["prototype_threshold"]["retuned_in_m_prot_1"])

    def test_wrong_artifact_rejected(self) -> None:
        other = ROOT / "models/mmwave/m_pv2/family_b/candidate_seed_11.pt"
        with self.assertRaises(PrototypeFailClosed) as ctx:
            verify_artifact(ROOT, other)
        self.assertEqual(ctx.exception.code, "ARTIFACT_SHA_MISMATCH")
        receipt = run_prototype_inference(
            self.valid, root=ROOT, model=self.model, scaler=self.scaler, artifact_path=other
        )
        self.assertEqual(receipt.fail_closed_code, "ARTIFACT_SHA_MISMATCH")
        self.assertIsNone(receipt.rr_bpm)

    def test_missing_artifact_rejected(self) -> None:
        missing = ROOT / "models/mmwave/m_pv2/family_b/does_not_exist.pt"
        receipt = run_prototype_inference(
            self.valid, root=ROOT, scaler=self.scaler, artifact_path=missing
        )
        self.assertEqual(receipt.fail_closed_code, "ARTIFACT_MISSING")

    def test_wrong_scaler_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scaler.json"
            payload = dict(self.scaler)
            payload["sha256"] = "0" * 64
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(PrototypeFailClosed) as ctx:
                verify_scaler(ROOT, path)
            self.assertEqual(ctx.exception.code, "SCALER_SHA_MISMATCH")

    def test_malformed_and_incomplete_inputs_rejected(self) -> None:
        cases = [
            ({**self.valid, "trace": self.valid["trace"][:10]}, "WRONG_DIMENSION"),
            ({**self.valid, "sample_count": 12}, "INCOMPLETE_INPUT"),
            ({**self.valid, "trace": self.valid["trace"][:-1]}, "WRONG_DIMENSION"),
            ({**self.valid, "trace_mask": None}, "INCOMPLETE_INPUT"),
            ({**self.valid, "scale": self.valid["scale"][:3]}, "WRONG_SCALE_DIM"),
            ({**self.valid, "quality": self.valid["quality"][:2]}, "WRONG_QUALITY_DIM"),
            ({**self.valid, "window_valid": False}, "INCOMPLETE_INPUT"),
        ]
        for fixture, code in cases:
            with self.subTest(code=code, keys=list(fixture.keys())):
                receipt = run_prototype_inference(fixture, root=ROOT, model=self.model, scaler=self.scaler)
                self.assertEqual(receipt.fail_closed_code, code)
                self.assertIsNone(receipt.breathing_decision)
                self.assertIsNone(receipt.rr_bpm)

    def test_non_finite_input_rejected(self) -> None:
        nan_trace = list(self.valid["trace"])
        nan_trace[10] = float("nan")
        inf_scale = list(self.valid["scale"])
        inf_scale[0] = float("inf")
        for fixture in ({**self.valid, "trace": nan_trace}, {**self.valid, "scale": inf_scale}):
            receipt = run_prototype_inference(fixture, root=ROOT, model=self.model, scaler=self.scaler)
            self.assertEqual(receipt.fail_closed_code, "NON_FINITE_INPUT")
            self.assertIsNone(receipt.rr_bpm)

    def test_presence_unavailable_emits_no_physiology(self) -> None:
        receipt = run_prototype_inference(
            {**self.valid, "presence_available": False},
            root=ROOT,
            model=self.model,
            scaler=self.scaler,
        )
        self.assertEqual(receipt.fail_closed_code, "PRESENCE_UNAVAILABLE")
        self.assertIsNone(receipt.breathing_decision)
        self.assertNotEqual(receipt.breathing_decision, "APNEA")
        self.assertFalse(receipt.apnea_emitted)

    def test_quality_availability_failure_suppresses_physiology(self) -> None:
        receipt = run_prototype_inference(
            {**self.valid, "availability_state": "INPUT_UNAVAILABLE"},
            root=ROOT,
            model=self.model,
            scaler=self.scaler,
        )
        self.assertEqual(receipt.fail_closed_code, "INPUT_UNAVAILABLE")
        self.assertIsNone(receipt.rr_bpm)
        self.assertFalse(receipt.apnea_emitted)

    def test_absent_is_never_apnea(self) -> None:
        receipt = run_prototype_inference(self.valid, root=ROOT, model=self.model, scaler=self.scaler)
        if receipt.breathing_decision == "ABSENT":
            self.assertEqual(receipt.rr_status, "SUPPRESSED_ABSENT")
            self.assertIsNone(receipt.rr_bpm)
        self.assertNotEqual(receipt.breathing_decision, "APNEA")
        self.assertFalse(receipt.apnea_emitted)
        payload = receipt.to_json()
        self.assertNotIn("APNEA", json.dumps(payload))

    def test_negative_and_nonfinite_rr_fail_closed(self) -> None:
        raw_for_negative_bpm = (-0.3417701721191406 - 17.12899193548387) / 8.948729232744911
        bpm, status = decode_rr(raw_for_negative_bpm)
        self.assertIsNone(bpm)
        self.assertEqual(status, "UNAVAILABLE_INVALID_DECODE")
        bpm, status = decode_rr(float("nan"))
        self.assertIsNone(bpm)
        self.assertEqual(status, "UNAVAILABLE_INVALID_DECODE")
        bpm, status = decode_rr(-2.0)
        self.assertIsNone(bpm)
        self.assertEqual(status, "UNAVAILABLE_INVALID_DECODE")

    def test_no_fallback_model(self) -> None:
        source = inspect_no_fallback()
        self.assertNotIn("mmwave_heuristic_fallback", source)
        self.assertNotIn("MN9Interpreter", source)
        self.assertNotIn("candidate_seed_11.pt", source)

    def test_final_lane_unchanged(self) -> None:
        closure = json.loads(
            (ROOT / "datasets/mmwave/manifests/M-PV3_8_lifecycle_closure/lifecycle_closure_state.json").read_text()
        )
        self.assertEqual(closure["closure_status"], "RESOURCE_BLOCKED_CLOSED")
        self.assertEqual(closure["evaluation_status"], "NOT_EXECUTED")
        self.assertEqual(closure["membership_status"], "BLOCKED_INVALID_FINAL_MEMBERSHIP")
        self.assertEqual(closure["mpv4_authorization"], "UNAUTHORIZED")
        d2 = json.loads(
            (ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/d2_lock_audit.json").read_text()
        )
        self.assertEqual(d2["status"], "LOCKED")
        self.assertFalse(d2["semantic_access"])
        critical = json.loads(
            (ROOT / "datasets/mmwave/manifests/MMWAVE_V2_post_pubabs_critical_path/critical_path_state.json").read_text()
        )
        observed = critical["d1"]["observed_governed"]
        self.assertEqual(observed["PRESENT"], 57)
        self.assertEqual(observed["ABSENT"], 0)
        nomination = json.loads(
            (ROOT / "datasets/mmwave/manifests/M_PROT_1_prototype_candidate_nomination/prototype_nomination.json").read_text()
        )
        self.assertFalse(nomination["m_pv38_panel_changed"])
        self.assertEqual(
            nomination["candidates_not_dropped"],
            ["B11", "B47", "C11", "C23", "C47"],
        )
        frozen = json.loads(
            (ROOT / "datasets/mmwave/manifests/M_PROT_2_deployable_artifact_runtime_contract/validation_result.json").read_text()
        )
        self.assertEqual(frozen["terminal_verdict"], "M_PROT_2_DEPLOYABLE_CONTRACT_FROZEN")
        self.assertEqual(frozen["PRIMARY_PROTOTYPE_DEPLOYABLE_REPRESENTATION"], "PYTORCH_FLOAT32_STATE_DICT")
        self.assertEqual(frozen["source_artifact_sha256"], SOURCE_ARTIFACT_SHA256)
        self.assertFalse(frozen["thresholds_retuned"])
        self.assertEqual(frozen["unchanged_final_lane"]["D1_PRESENT"], 57)
        self.assertEqual(frozen["unchanged_final_lane"]["D1_ABSENT"], 0)


def inspect_no_fallback() -> str:
    source = (ROOT / "adapters/mmwave_m_prot_2_b23_runtime.py").read_text(encoding="utf-8")
    return source


class MProt2NegativeRRObservedMinIsNotClamped(unittest.TestCase):
    def test_development_negative_raw_is_not_clamped_to_zero(self) -> None:
        # Historical B23 D1_DEV_VAL min was a decoded bpm of -0.34, which is
        # already a decoded value. A raw that decodes to <= 0 must be unavailable,
        # never clamped to 0/1/min-plausible.
        raw = (0.0 - 17.12899193548387) / 8.948729232744911
        bpm, status = decode_rr(raw)
        self.assertEqual(status, "UNAVAILABLE_INVALID_DECODE")
        self.assertIsNone(bpm)
        self.assertNotEqual(bpm, 0)
        self.assertNotEqual(bpm, 1)


if __name__ == "__main__":
    unittest.main()
