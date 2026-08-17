#!/usr/bin/env python3
"""Focused M-N7 device-domain checks. No public heldout. No fake MR60 labels."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.mmwave_m_n4_canonical import CONTRACT_ID, MR60_HELDOUT_REFERENCE, WINDOW_SECONDS
from scripts.mmwave_m_n6_select_lock import SELECTION_ID
from scripts.mmwave_m_n7_device_domain_check import (
    EXPECTED_SHA256,
    RESERVED_SPECS,
    candidate_window_starts,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/mmwave/m_n6_selected_candidate_lock.json"
KERAS = ROOT / "models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras"
SCRIPT = ROOT / "scripts/mmwave_m_n7_device_domain_check.py"
RESULT = ROOT / "datasets/mmwave/manifests/m_n7_device_domain_result.json"
PRED = ROOT / "datasets/mmwave/manifests/m_n7_mr60_predictions.jsonl"
CONTRACT = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"


class TestMmwaveMN7DeviceDomain(unittest.TestCase):
    def test_selected_artifact_identity(self) -> None:
        lock = json.loads(LOCK.read_text())
        self.assertEqual(lock["selection_id"], SELECTION_ID)
        self.assertEqual(lock["artifact_sha256"], EXPECTED_SHA256)
        self.assertTrue(KERAS.is_file())
        self.assertEqual(sha256_file(KERAS), EXPECTED_SHA256)
        self.assertEqual(lock["candidate_id"], "M-N5_DILATED_CONV1D_GAP_TINY")
        self.assertEqual(lock["seed"], 2026)
        self.assertEqual(lock["contract_id"], CONTRACT_ID)

    def test_script_does_not_reuse_heldout_or_fake_labels(self) -> None:
        text = SCRIPT.read_text()
        self.assertIn("accept_phase_events", text)
        self.assertIn("form_canonical_window", text)
        self.assertIn("production=True", text)
        self.assertNotIn("materialize_heldout", text)
        self.assertNotIn("NEW_MODEL_HELDOUT_TEST", text)
        self.assertNotIn("evaluate_val", text)
        self.assertNotIn("f1_score", text)
        self.assertNotIn("confusion_matrix", text)
        self.assertNotIn("class_weight", text)
        self.assertNotIn("M-N5_CONV1D_GAP_TINY", text)
        self.assertNotIn("M-N5_SMALL_MLP_BASELINE", text)
        for session_id in MR60_HELDOUT_REFERENCE:
            self.assertIn(session_id, text)
        self.assertEqual([s["session_id"] for s in RESERVED_SPECS], list(MR60_HELDOUT_REFERENCE))

    def test_evaluation_windowing_is_nonoverlapping_30s(self) -> None:
        starts = candidate_window_starts(10.0, 70.0, WINDOW_SECONDS)
        self.assertEqual(starts, [10.0, 40.0])
        starts_short = candidate_window_starts(0.0, 59.9, WINDOW_SECONDS)
        self.assertEqual(starts_short, [0.0])
        self.assertEqual(WINDOW_SECONDS, 30.0)

    def test_contract_file_untouched_identity(self) -> None:
        doc = json.loads(CONTRACT.read_text())
        self.assertEqual(doc["contract_id"], CONTRACT_ID)
        self.assertEqual(doc["resampling"]["input_shape"], [1, 240, 1])
        self.assertEqual(doc["team_mr60"]["mr60_heldout_reference"], list(MR60_HELDOUT_REFERENCE))

    def test_result_manifest_governance(self) -> None:
        if not RESULT.is_file():
            self.skipTest("M-N7 result not generated")
        result = json.loads(RESULT.read_text())
        lock = json.loads(LOCK.read_text())
        self.assertEqual(result["selection_id"], SELECTION_ID)
        self.assertEqual(result["artifact_sha256"], lock["artifact_sha256"])
        self.assertTrue(result["artifact_sha_match"])
        self.assertEqual(result["contract_id"], CONTRACT_ID)
        self.assertEqual(result["physical_subject_count"], 1)
        self.assertEqual(result["independent_respiratory_ground_truth"], "ABSENT")
        self.assertFalse(result["public_heldout_rerun"])
        self.assertFalse(result["mr60_accuracy_computed"])
        self.assertFalse(result["mr60_macro_f1_computed"])
        self.assertFalse(result["mr60_recall_computed"])
        self.assertFalse(result["occupied_treated_as_normal_gt"])
        self.assertFalse(result["empty_treated_as_apnea_gt"])
        self.assertFalse(result["development_recordings_used_for_primary_decision"])
        self.assertFalse(result["model_retrained"])
        self.assertFalse(result["m_n4_preprocessing_modified"])
        self.assertEqual(result["evaluation_windowing"], "M_N7_EVALUATION_WINDOWING_ONLY")
        self.assertFalse(result["production_stride_frozen"])
        self.assertEqual(result["reserved_recordings_requested"], list(MR60_HELDOUT_REFERENCE))
        self.assertIn(result["DEVICE_DOMAIN_GAP"], {"NOT_OBSERVED", "LIMITED", "MATERIAL", "INCONCLUSIVE"})
        self.assertIn(result["M_N8_REQUIRED"], {"YES", "NO", "NO_NOT_YET_JUSTIFIED"})
        self.assertIn(result["gate"], {"PASS", "PASS_WITH_LIMITATIONS", "FAIL"})
        self.assertEqual(result["focused_validation"]["selected_artifact_identity"], "PASS")
        self.assertEqual(result["focused_validation"]["model_reload"], "PASS")
        self.assertEqual(result["focused_validation"]["input_output_shape"], "PASS")
        windows = result["windows"]
        self.assertEqual(len(windows), result["window_counts"]["candidate"])
        for row in windows:
            self.assertEqual(row["selection_id"], SELECTION_ID)
            self.assertEqual(row["artifact_sha256"], EXPECTED_SHA256)
            self.assertEqual(row["contract_id"], CONTRACT_ID)
            self.assertNotIn("values", row)

    def test_prediction_jsonl_lightweight(self) -> None:
        if not PRED.is_file():
            self.skipTest("M-N7 predictions not generated")
        rows = [json.loads(line) for line in PRED.read_text().splitlines() if line.strip()]
        result = json.loads(RESULT.read_text())
        self.assertEqual(len(rows), result["window_counts"]["canonical_valid"] + result["window_counts"]["rejected"])
        for row in rows:
            self.assertEqual(row["selection_id"], SELECTION_ID)
            self.assertEqual(row["artifact_sha256"], EXPECTED_SHA256)
            self.assertFalse(row["accuracy_computed"])
            self.assertIsNone(row["supervised_label"])
            self.assertNotIn("values", row)
            self.assertNotIn("waveform", row)


if __name__ == "__main__":
    unittest.main()
