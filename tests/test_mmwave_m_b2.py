#!/usr/bin/env python3
"""Unit test suite for SafeNest mmWave M-B2 Class-Imbalance Strategy Comparison & Validator."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
import tensorflow as tf

from scripts.mmwave_m_b2_imbalance import (
    STRATEGIES,
    build_multiclass_focal_loss,
    build_oversampling_plan,
    compute_one_vs_rest_false_positives,
    compute_subject_level_diagnostics,
    compute_train_class_weights,
)
from scripts.mmwave_phase_b_access import LOCKED_TEST_AccessError, PhaseBAccessGuard
from scripts.validate_mmwave_m_b2 import MB2ValidationError, validate_m_b2_artifacts

ROOT_DIR = Path(__file__).resolve().parents[1]


class TestMMWaveMB2(unittest.TestCase):
    """Test suite for Phase M-B2 imbalance strategy, access guard, and validator."""

    def setUp(self) -> None:
        self.guard = PhaseBAccessGuard(root_dir=ROOT_DIR)
        self.manifest_dir = ROOT_DIR / "datasets/mmwave/manifests/M-B2_class_imbalance"

    def test_strategies_count_and_structure(self) -> None:
        self.assertEqual(len(STRATEGIES), 4)
        strategy_ids = [s["strategy_id"] for s in STRATEGIES]
        expected_ids = [
            "M-B2_CE_UNWEIGHTED",
            "M-B2_CE_CLASS_WEIGHT",
            "M-B2_CE_RANDOM_OVERSAMPLE",
            "M-B2_FOCAL_CLASS_ALPHA",
        ]
        self.assertEqual(strategy_ids, expected_ids)

    def test_train_class_weights_calculation(self) -> None:
        # Mock TRAIN labels: 100 Class 0, 50 Class 1, 150 Class 2 (total 300)
        labels = [0] * 100 + [1] * 50 + [2] * 150
        weights = compute_train_class_weights(labels)

        # w_c = 300 / (3 * n_c)
        self.assertAlmostEqual(weights[0], 300.0 / (3 * 100), places=5)
        self.assertAlmostEqual(weights[1], 300.0 / (3 * 50), places=5)
        self.assertAlmostEqual(weights[2], 300.0 / (3 * 150), places=5)

    def test_oversampling_plan_generation(self) -> None:
        train_windows = [
            {"canonical_sample_index": i, "window_id": f"w_{i}", "subject_id": f"sub_{i%2}", "recording_id": "r1", "safenest_label_id": i % 3}
            for i in range(10)
        ]
        # Class counts: 0 -> 4, 1 -> 3, 2 -> 3
        indices, plan_records = build_oversampling_plan(train_windows, seed=42)
        # Target count per class = 4, total oversampled count = 12
        self.assertEqual(len(indices), 12)
        self.assertEqual(len(plan_records), 10)

    def test_multiclass_focal_loss(self) -> None:
        alpha_weights = {0: 1.0, 1: 2.0, 2: 1.0}
        focal_loss_fn = build_multiclass_focal_loss(alpha_weights, gamma=2.0)

        y_true = tf.constant([1], dtype=tf.int32)
        y_pred = tf.constant([[0.1, 0.8, 0.1]], dtype=tf.float32)

        loss_val = focal_loss_fn(y_true, y_pred).numpy()
        # Loss should be non-negative and finite
        self.assertGreaterEqual(loss_val, 0.0)
        self.assertTrue(np.isfinite(loss_val))

    def test_one_vs_rest_false_positives(self) -> None:
        val_true = np.array([0, 0, 1, 1, 2, 2])
        val_pred = np.array([0, 1, 1, 1, 2, 0])

        metrics = compute_one_vs_rest_false_positives(val_true, val_pred)
        self.assertIn("NORMAL", metrics)
        self.assertIn("RAPID_OR_ABNORMAL", metrics)
        self.assertIn("APNEA", metrics)
        self.assertIn("fpr", metrics["NORMAL"])

    def test_subject_level_diagnostics(self) -> None:
        val_windows = [
            {"subject_id": "sub_A", "safenest_label_id": 0},
            {"subject_id": "sub_A", "safenest_label_id": 2},
            {"subject_id": "sub_B", "safenest_label_id": 1},
        ]
        val_preds = np.array([0, 2, 1])

        subj_diag = compute_subject_level_diagnostics(val_windows, val_preds)
        self.assertEqual(subj_diag["summary_across_subjects"]["subject_count"], 2)
        self.assertEqual(subj_diag["summary_across_subjects"]["mean_accuracy"], 1.0)

    def test_locked_test_model_selection_prohibited(self) -> None:
        with self.assertRaises(LOCKED_TEST_AccessError):
            self.guard.get_model_selection_dataset("LOCKED_TEST")

    def test_standalone_m_b2_validator_clean(self) -> None:
        if self.manifest_dir.is_dir():
            res = validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=self.manifest_dir)
            self.assertTrue(res["validation_success"])
            self.assertEqual(res["m_b2_gate_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(res["m_b3_entry_status"], "READY_WITH_CONDITIONS")
            self.assertTrue(res["independently_measured"]["class_distribution_recomputed"])

    def test_validator_detects_corrupted_strategy_selection(self) -> None:
        if not self.manifest_dir.is_dir():
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_manifest = Path(tmpdir)
            shutil.copytree(self.manifest_dir, tmp_manifest, dirs_exist_ok=True)

            sel_file = tmp_manifest / "selected_imbalance_strategy.json"
            data = json.loads(sel_file.read_text(encoding="utf-8"))
            data["selected_strategy_id"] = "INVALID_CORRUPTED_STRATEGY"
            sel_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            with self.assertRaises(MB2ValidationError):
                validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=tmp_manifest)

    def test_validator_fails_on_malformed_checksum_line(self) -> None:
        if not self.manifest_dir.is_dir():
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_manifest = Path(tmpdir)
            shutil.copytree(self.manifest_dir, tmp_manifest, dirs_exist_ok=True)

            chk_file = tmp_manifest / "checksums.sha256"
            content = chk_file.read_text(encoding="utf-8")
            chk_file.write_text("malformed_line_without_space\n" + content, encoding="utf-8")

            with self.assertRaises(MB2ValidationError):
                validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=tmp_manifest)

    def test_validator_fails_on_unpinned_environment(self) -> None:
        if not self.manifest_dir.is_dir():
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_manifest = Path(tmpdir)
            shutil.copytree(self.manifest_dir, tmp_manifest, dirs_exist_ok=True)

            env_file = tmp_manifest / "run_environment.json"
            data = json.loads(env_file.read_text(encoding="utf-8"))
            data["numpy_version"] = "2.0.2"
            env_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            with self.assertRaises(MB2ValidationError):
                validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=tmp_manifest)

    def test_validator_fails_on_stale_upstream_identity(self) -> None:
        if not self.manifest_dir.is_dir():
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_manifest = Path(tmpdir)
            shutil.copytree(self.manifest_dir, tmp_manifest, dirs_exist_ok=True)

            id_file = tmp_manifest / "input_identity.json"
            data = json.loads(id_file.read_text(encoding="utf-8"))
            data["inputs"][0]["measured_sha256"] = "0" * 64
            id_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            with self.assertRaises(MB2ValidationError):
                validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=tmp_manifest)

    def test_oversampling_majority_duplication_rejected(self) -> None:
        if not self.manifest_dir.is_dir():
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_manifest = Path(tmpdir)
            shutil.copytree(self.manifest_dir, tmp_manifest, dirs_exist_ok=True)

            ovs_file = tmp_manifest / "oversampling_plan.jsonl"
            lines = [json.loads(l) for l in ovs_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            for l in lines:
                if l.get("class_id") == 2:
                    l["additional_duplicate_count"] = 5
                    l["effective_multiplicity"] = 6
                    break

            ovs_file.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")

            with self.assertRaises(MB2ValidationError):
                validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=tmp_manifest)

    def test_validator_fails_on_baseline_drift(self) -> None:
        if not self.manifest_dir.is_dir():
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_manifest = Path(tmpdir)
            shutil.copytree(self.manifest_dir, tmp_manifest, dirs_exist_ok=True)

            tr_file = tmp_manifest / "training_runs.json"
            data = json.loads(tr_file.read_text(encoding="utf-8"))
            data["training_runs"]["M-B2_CE_UNWEIGHTED"]["final_weights_sha256"] = "0" * 64
            tr_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            with self.assertRaises(MB2ValidationError):
                validate_m_b2_artifacts(root_dir=ROOT_DIR, manifest_dir=tmp_manifest)


if __name__ == "__main__":
    unittest.main()
