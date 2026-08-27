#!/usr/bin/env python3
"""Focused M-PROT-2 B23 deployable-contract tests (including Sol corrective)."""

from __future__ import annotations

import copy
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
    R1_ADAPTER_MODULE,
    R1_PROFILE,
    R2_EXTRACTOR_FUNCTION,
    R2_EXTRACTOR_MODULE,
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
    assemble_from_r1_common_trace,
    decode_rr,
    extract_profile_b_descriptors,
    load_b23_model,
    resolve_verified_runtime,
    run_prototype_inference,
    sha256_file,
    stage0_runtime_admissibility,
    stage1_canonical_preprocess,
    training_side_family_b_vector,
    valid_fixture_from_scaler,
    valid_r1_parity_fixture,
    verify_artifact,
    verify_model_identity,
    verify_scaler,
    verify_scaler_payload,
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
        verify_model_identity(self.model)

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
        self.assertEqual(vector[0:300].shape, (300,))
        self.assertEqual(vector[300:600].shape, (300,))
        self.assertEqual(vector[600:612].shape, (12,))
        self.assertEqual(vector[612:621].shape, (9,))

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
        receipt = run_prototype_inference(bad, root=ROOT)
        self.assertEqual(receipt.fail_closed_code, "DOUBLE_ZSCORE_FORBIDDEN")
        self.assertIsNone(receipt.breathing_decision)

    def test_positive_path_is_deterministic(self) -> None:
        first = run_prototype_inference(self.valid, root=ROOT)
        second = run_prototype_inference(self.valid, root=ROOT)
        self.assertEqual(first.to_json(), second.to_json())
        self.assertIn(first.breathing_decision, {"PRESENT", "ABSENT"})
        self.assertEqual(first.artifact_sha256, SOURCE_ARTIFACT_SHA256)
        self.assertEqual(first.representation, PRIMARY_REPRESENTATION)
        self.assertFalse(first.apnea_emitted)
        self.assertNotEqual(first.breathing_decision, "APNEA")
        self.assertIn("PROTOTYPE_INTEGRATION_ONLY", first.mandatory_semantics)
        self.assertTrue(first.identities_verified)
        self.assertEqual(first.lineage_class, "FIXTURE_NON_CAMPAIGN")

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
        receipt = run_prototype_inference(self.valid, root=ROOT, artifact_path=other)
        self.assertEqual(receipt.fail_closed_code, "ARTIFACT_SHA_MISMATCH")
        self.assertIsNone(receipt.rr_bpm)
        self.assertFalse(receipt.identities_verified)
        self.assertIsNone(receipt.artifact_sha256)

    def test_missing_artifact_rejected(self) -> None:
        missing = ROOT / "models/mmwave/m_pv2/family_b/does_not_exist.pt"
        receipt = run_prototype_inference(self.valid, root=ROOT, artifact_path=missing)
        self.assertEqual(receipt.fail_closed_code, "ARTIFACT_MISSING")
        self.assertFalse(receipt.identities_verified)

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
                receipt = run_prototype_inference(fixture, root=ROOT)
                self.assertEqual(receipt.fail_closed_code, code)
                self.assertIsNone(receipt.breathing_decision)
                self.assertIsNone(receipt.rr_bpm)

    def test_non_finite_input_rejected(self) -> None:
        nan_trace = list(self.valid["trace"])
        nan_trace[10] = float("nan")
        inf_scale = list(self.valid["scale"])
        inf_scale[0] = float("inf")
        for fixture in ({**self.valid, "trace": nan_trace}, {**self.valid, "scale": inf_scale}):
            receipt = run_prototype_inference(fixture, root=ROOT)
            self.assertEqual(receipt.fail_closed_code, "NON_FINITE_INPUT")
            self.assertIsNone(receipt.rr_bpm)

    def test_presence_unavailable_emits_no_physiology(self) -> None:
        receipt = run_prototype_inference(
            {**self.valid, "presence_available": False},
            root=ROOT,
        )
        self.assertEqual(receipt.fail_closed_code, "PRESENCE_UNAVAILABLE")
        self.assertIsNone(receipt.breathing_decision)
        self.assertNotEqual(receipt.breathing_decision, "APNEA")
        self.assertFalse(receipt.apnea_emitted)

    def test_quality_availability_failure_suppresses_physiology(self) -> None:
        receipt = run_prototype_inference(
            {**self.valid, "availability_state": "INPUT_UNAVAILABLE"},
            root=ROOT,
        )
        self.assertEqual(receipt.fail_closed_code, "INPUT_UNAVAILABLE")
        self.assertIsNone(receipt.rr_bpm)
        self.assertFalse(receipt.apnea_emitted)

    def test_absent_is_never_apnea(self) -> None:
        receipt = run_prototype_inference(self.valid, root=ROOT)
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
        source = (ROOT / "adapters/mmwave_m_prot_2_b23_runtime.py").read_text(encoding="utf-8")
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


class MProt2CorrectiveIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scaler = verify_scaler(ROOT)
        cls.model = load_b23_model(ROOT)
        cls.valid = valid_fixture_from_scaler(cls.scaler)

    def test_alternate_model_object_rejected(self) -> None:
        alternate = TraceModel(INPUT_DIM, FAMILY)
        with self.assertRaises(PrototypeFailClosed) as ctx:
            verify_model_identity(alternate)
        self.assertEqual(ctx.exception.code, "MODEL_IDENTITY_MISMATCH")
        receipt = run_prototype_inference(self.valid, root=ROOT, model=alternate)
        self.assertEqual(receipt.fail_closed_code, "MODEL_IDENTITY_MISMATCH")
        self.assertFalse(receipt.identities_verified)
        self.assertIsNone(receipt.artifact_sha256)
        self.assertIsNone(receipt.breathing_decision)

    def test_mutated_model_weights_rejected(self) -> None:
        mutated = TraceModel(INPUT_DIM, FAMILY)
        mutated.load_state_dict(self.model.state_dict(), strict=True)
        with torch.no_grad():
            for parameter in mutated.parameters():
                parameter.add_(0.01)
                break
        with self.assertRaises(PrototypeFailClosed) as ctx:
            verify_model_identity(mutated)
        self.assertEqual(ctx.exception.code, "MODEL_IDENTITY_MISMATCH")
        receipt = run_prototype_inference(self.valid, root=ROOT, model=mutated)
        self.assertEqual(receipt.fail_closed_code, "MODEL_IDENTITY_MISMATCH")
        self.assertIsNone(receipt.artifact_sha256)

    def test_canonical_model_injection_accepted_only_after_verify(self) -> None:
        loaded, scaler = resolve_verified_runtime(root=ROOT, model=self.model, scaler=self.scaler)
        self.assertIs(loaded, self.model)
        receipt = run_prototype_inference(self.valid, root=ROOT, model=self.model, scaler=self.scaler)
        self.assertTrue(receipt.identities_verified)
        self.assertEqual(receipt.artifact_sha256, SOURCE_ARTIFACT_SHA256)

    def test_alternate_scaler_mapping_rejected(self) -> None:
        alternate = copy.deepcopy(self.scaler)
        alternate["scale"]["mean"] = list(alternate["scale"]["mean"])
        alternate["scale"]["mean"][0] = float(alternate["scale"]["mean"][0]) + 1.0
        content = {key: value for key, value in alternate.items() if key != "sha256"}
        from scripts.mmwave_m_pv2_candidate_training import _sha256_json

        alternate["sha256"] = _sha256_json(content)
        with self.assertRaises(PrototypeFailClosed) as ctx:
            verify_scaler_payload(alternate)
        self.assertEqual(ctx.exception.code, "SCALER_SHA_MISMATCH")
        receipt = run_prototype_inference(self.valid, root=ROOT, scaler=alternate)
        self.assertEqual(receipt.fail_closed_code, "SCALER_SHA_MISMATCH")
        self.assertFalse(receipt.identities_verified)
        self.assertIsNone(receipt.scaler_content_sha256)

    def test_mutated_scaler_feature_order_rejected(self) -> None:
        mutated = copy.deepcopy(self.scaler)
        names = list(mutated["scale"]["names"])
        names[0], names[1] = names[1], names[0]
        mutated["scale"]["names"] = names
        with self.assertRaises(PrototypeFailClosed) as ctx:
            verify_scaler_payload(mutated)
        self.assertIn(ctx.exception.code, {"SCALER_SHA_MISMATCH", "SCALER_FEATURE_ORDER_MISMATCH"})

    def test_fixture_provenance_is_non_campaign(self) -> None:
        receipt = run_prototype_inference(self.valid, root=ROOT)
        payload = receipt.to_json()
        self.assertEqual(payload["lineage_class"], "FIXTURE_NON_CAMPAIGN")
        self.assertNotEqual(payload["lineage_class"], "DEBUG_CAPTURE")
        self.assertTrue(payload["PROTOTYPE_INTEGRATION_ONLY"])
        self.assertFalse(payload["FINAL_GOVERNED_EVALUATION"])
        forbidden = run_prototype_inference(
            {**self.valid, "lineage_class": "FINAL_GOVERNED_EVALUATION"},
            root=ROOT,
        )
        self.assertEqual(forbidden.fail_closed_code, "LINEAGE_CLASS_FORBIDDEN")


class MProt2CorrectivePreprocessingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scaler = verify_scaler(ROOT)

    def test_r1_r2_lineage_identity_recorded(self) -> None:
        self.assertEqual(R1_ADAPTER_MODULE, "adapters/mmwave_r1_sensor_independent_trace.py")
        self.assertEqual(R1_PROFILE, "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1")
        self.assertEqual(R2_EXTRACTOR_MODULE, "adapters/mmwave_r2_representation_features.py")
        self.assertEqual(R2_EXTRACTOR_FUNCTION, "extract_feature_candidates")

    def test_canonical_descriptor_extraction_parity(self) -> None:
        common = valid_r1_parity_fixture(seed=23)
        descriptors = extract_profile_b_descriptors(common)
        self.assertEqual(descriptors["trace"].shape, (300,))
        self.assertEqual(descriptors["trace_mask"].shape, (300,))
        self.assertEqual(descriptors["scale"].shape, (12,))
        self.assertEqual(descriptors["quality"].shape, (9,))
        runtime = assemble_from_r1_common_trace(common, self.scaler)
        training = training_side_family_b_vector(common, self.scaler)
        self.assertEqual(runtime.dtype, np.float32)
        self.assertEqual(training.dtype, np.float32)
        self.assertEqual(runtime.shape, (621,))
        max_abs = float(np.max(np.abs(runtime - training)))
        self.assertEqual(max_abs, 0.0)
        self.assertEqual(float(np.max(np.abs(runtime[0:300] - training[0:300]))), 0.0)
        self.assertEqual(float(np.max(np.abs(runtime[300:600] - training[300:600]))), 0.0)
        self.assertEqual(float(np.max(np.abs(runtime[600:612] - training[600:612]))), 0.0)
        self.assertEqual(float(np.max(np.abs(runtime[612:621] - training[612:621]))), 0.0)

    def test_admissibility_separated_from_canonical_preprocess(self) -> None:
        valid = valid_fixture_from_scaler(self.scaler)
        with self.assertRaises(PrototypeFailClosed) as ctx:
            stage0_runtime_admissibility(
                trace=valid["trace"],
                trace_mask=valid["trace_mask"],
                scale=valid["scale"],
                quality=[float("nan")] * 9,
            )
        self.assertEqual(ctx.exception.code, "NON_FINITE_INPUT")
        accepted = stage0_runtime_admissibility(
            trace=valid["trace"],
            trace_mask=valid["trace_mask"],
            scale=valid["scale"],
            quality=valid["quality"],
        )
        vector = stage1_canonical_preprocess(accepted, self.scaler)
        self.assertEqual(vector.shape, (621,))
        # Stage 1 does not invent physiology for invalid inputs; Stage 0 already gated.
        source = (ROOT / "adapters/mmwave_m_prot_2_b23_runtime.py").read_text(encoding="utf-8")
        self.assertIn("STAGE 0", source)
        self.assertIn("STAGE 1", source)
        # Runtime Stage 1 must not call nan_to_num; training-side parity helper
        # may mention historical training nan_to_num in docs only.
        stage1 = source.split("def stage1_canonical_preprocess", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("nan_to_num", stage1)
        self.assertNotIn("np.nan_to_num", stage0_runtime_admissibility.__code__.co_names)


class MProt2NegativeRRObservedMinIsNotClamped(unittest.TestCase):
    def test_development_negative_raw_is_not_clamped_to_zero(self) -> None:
        raw = (0.0 - 17.12899193548387) / 8.948729232744911
        bpm, status = decode_rr(raw)
        self.assertEqual(status, "UNAVAILABLE_INVALID_DECODE")
        self.assertIsNone(bpm)
        self.assertNotEqual(bpm, 0)
        self.assertNotEqual(bpm, 1)


if __name__ == "__main__":
    unittest.main()
