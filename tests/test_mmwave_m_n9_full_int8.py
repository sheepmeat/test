#!/usr/bin/env python3
"""Focused M-N9 FULL_INT8 checks. No heldout inference. No retraining."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.mmwave_m_n4_canonical import CONTRACT_ID
from scripts.mmwave_m_n6_select_lock import SELECTION_ID
from scripts.mmwave_m_n9_full_int8 import ARTIFACT_ID, EXPECTED_FLOAT_SHA, sha256_file

ROOT = Path(__file__).resolve().parents[1]
FLOAT = ROOT / "models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras"
INT8 = ROOT / "models/mmwave/m_n9/MMWAVE_M_N9_FULL_INT8_V1.tflite"
LOCK = ROOT / "config/mmwave/m_n9_full_int8_artifact_lock.json"
RESULT = ROOT / "datasets/mmwave/manifests/m_n9_full_int8_result.json"
SCRIPT = ROOT / "scripts/mmwave_m_n9_full_int8.py"
MN4 = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"


class TestMmwaveMN9FullInt8(unittest.TestCase):
    def test_float_identity_unchanged(self) -> None:
        self.assertTrue(FLOAT.is_file())
        self.assertEqual(sha256_file(FLOAT), EXPECTED_FLOAT_SHA)

    def test_script_governance(self) -> None:
        text = SCRIPT.read_text()
        self.assertIn("PUBLIC_TRAIN_ONLY", text)
        self.assertIn("TFLITE_BUILTINS_INT8", text)
        self.assertIn("PRESENCE_GATE_REQUIRED", text)
        self.assertIn("NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9 = 0", text)
        self.assertNotIn("materialize_heldout", text)
        self.assertNotIn("fine_tune", text)
        self.assertNotIn("M-N5_CONV1D_GAP_TINY", text)
        self.assertNotIn("M-N5_SMALL_MLP_BASELINE", text)

    def test_lock_and_artifact(self) -> None:
        if not LOCK.is_file() or not INT8.is_file():
            self.skipTest("M-N9 artifact not generated")
        lock = json.loads(LOCK.read_text())
        self.assertEqual(lock["artifact_id"], ARTIFACT_ID)
        self.assertEqual(lock["source_selection_id"], SELECTION_ID)
        self.assertEqual(lock["source_float_sha256"], EXPECTED_FLOAT_SHA)
        self.assertEqual(lock["contract_id"], CONTRACT_ID)
        self.assertEqual(sha256_file(INT8), lock["artifact_sha256"])
        self.assertEqual(INT8.stat().st_size, lock["artifact_size_bytes"])
        self.assertEqual(lock["input_contract"]["dtype"], "int8")
        self.assertEqual(lock["input_contract"]["shape"], [1, 240, 1])
        self.assertEqual(lock["output_contract"]["dtype"], "int8")
        self.assertEqual(lock["output_contract"]["shape"], [1, 3])
        self.assertTrue(lock["quantization"]["FULL_INT8_ONLY"])
        self.assertFalse(lock["quantization"]["float_fallback_ops"])
        self.assertTrue(lock["presence_gate"]["PRESENCE_GATE_REQUIRED"])
        self.assertFalse(lock["presence_gate"]["fourth_neural_class_added"])
        self.assertFalse(lock["DEVICE_VALIDATED"])
        self.assertEqual(lock["calibration"]["INT8_CALIBRATION_SOURCE"], "PUBLIC_TRAIN_ONLY")
        self.assertFalse(lock["calibration"]["public_heldout_used"])
        self.assertFalse(lock["calibration"]["mr60_used_for_calibration"])
        self.assertEqual(lock["NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9"], 0)
        self.assertNotIn("conversion_git_sha", lock)
        self.assertEqual(lock["conversion_base_sha"], "bee5fd6f1611036d1a5cade29712586bdca4b6bf")
        self.assertEqual(
            lock["artifact_introducing_commit"],
            "a475d06623dd91298a8563924fafaa5fc6d3532b",
        )

    def test_result_parity_and_boundaries(self) -> None:
        if not RESULT.is_file():
            self.skipTest("M-N9 result not generated")
        result = json.loads(RESULT.read_text())
        self.assertNotIn("/Users/", json.dumps(result))
        self.assertEqual(result["NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9"], 0)
        self.assertFalse(result["public_heldout_rerun"])
        self.assertFalse(result["model_retrained"])
        self.assertFalse(result["m_n8_adaptation"])
        self.assertFalse(result["DEVICE_VALIDATED"])
        self.assertEqual(result["val_parity"]["parity_gate"], "PASS")
        self.assertGreaterEqual(result["val_parity"]["top1_agreement"], 0.95)
        self.assertLessEqual(result["val_parity"]["macro_f1_degradation"], 0.03)
        self.assertEqual(result["val_float"]["per_class_recall"]["RAPID_OR_ABNORMAL"], 0.4)
        self.assertEqual(result["val_int8"]["per_class_recall"]["RAPID_OR_ABNORMAL"], 0.4)
        self.assertTrue(result["presence_gate"]["PRESENCE_GATE_REQUIRED"])
        self.assertEqual(result["zero_no_person"]["float_predicted_class"], "APNEA")
        self.assertEqual(result["zero_no_person"]["int8_predicted_class"], "APNEA")
        self.assertEqual(result["raspberry_pi"]["PI_DEVICE_SMOKE"], "NOT_PERFORMED_ENVIRONMENT_UNAVAILABLE")
        self.assertEqual(result["NEXT_RECOMMENDED_PHASE"], "M-N10")
        mn4 = json.loads(MN4.read_text())
        self.assertEqual(mn4["contract_id"], CONTRACT_ID)
        self.assertEqual(mn4["resampling"]["input_shape"], [1, 240, 1])


if __name__ == "__main__":
    unittest.main()
