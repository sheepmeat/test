#!/usr/bin/env python3
"""Unit test suite for SafeNest mmWave M-B0 Evaluation Protocol & LOCKED_TEST Guard."""

from __future__ import annotations

from pathlib import Path
import unittest

from scripts.mmwave_phase_b_access import LOCKED_TEST_AccessError, PhaseBAccessGuard
from scripts.validate_mmwave_m_b0 import validate_m_b0_artifacts

ROOT_DIR = Path(__file__).resolve().parents[1]


class TestMMWaveMB0(unittest.TestCase):
    """Test suite for Phase M-B0 access control, isolation, and validator."""

    def setUp(self) -> None:
        self.guard = PhaseBAccessGuard(root_dir=ROOT_DIR)

    def test_train_data_retrieval(self) -> None:
        train_data = self.guard.get_train_data(include_ambiguous=False)
        self.assertEqual(train_data["split"], "TRAIN")
        self.assertEqual(train_data["total_count"], 327)
        self.assertEqual(train_data["signals"].shape, (327, 300))

        train_data_all = self.guard.get_train_data(include_ambiguous=True)
        self.assertEqual(train_data_all["total_count"], 358)

    def test_validation_data_retrieval(self) -> None:
        val_data = self.guard.get_validation_data(include_ambiguous=False)
        self.assertEqual(val_data["split"], "VALIDATION")
        self.assertEqual(val_data["total_count"], 79)
        self.assertEqual(val_data["signals"].shape, (79, 300))

    def test_locked_test_model_selection_prohibited(self) -> None:
        with self.assertRaises(LOCKED_TEST_AccessError):
            self.guard.get_model_selection_dataset("LOCKED_TEST")

    def test_locked_test_structural_audit_allowed(self) -> None:
        struct_data = self.guard.get_structural_audit_dataset("LOCKED_TEST")
        self.assertEqual(struct_data["split"], "LOCKED_TEST")
        self.assertEqual(struct_data["total_count"], 88)
        self.assertEqual(struct_data["signals"].shape, (88, 300))

    def test_locked_test_final_eval_token(self) -> None:
        with self.assertRaises(LOCKED_TEST_AccessError):
            self.guard.get_locked_test_final_evaluation_dataset(authorization_token=None)

        with self.assertRaises(LOCKED_TEST_AccessError):
            self.guard.get_locked_test_final_evaluation_dataset(authorization_token="WRONG_TOKEN")

        valid_data = self.guard.get_locked_test_final_evaluation_dataset(
            authorization_token="AUTHORIZED_FINAL_LOCKED_TEST_EVALUATION_TOKEN_V1"
        )
        self.assertEqual(valid_data["total_count"], 75)

    def test_standalone_m_b0_validator(self) -> None:
        manifest_dir = ROOT_DIR / "datasets/mmwave/manifests/M-B0_evaluation_protocol"
        if manifest_dir.is_dir():
            res = validate_m_b0_artifacts(root_dir=ROOT_DIR, manifest_dir=manifest_dir)
            self.assertTrue(res["validation_success"])
            self.assertEqual(res["m_b0_gate_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(res["m_b1_entry_status"], "READY_WITH_CONDITIONS")


if __name__ == "__main__":
    unittest.main()
