from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from scripts.evaluate_thermal_b6r_p4_public_sdt_robustness import (
    TFLiteRunner,
    classification_metrics,
    condition_metrics,
    perturb_one,
    prepare_replay_input,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/thermal/b6r_p4_public_sdt_software_robustness_failure_mode_contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class B6RP4PublicSdtRobustnessTest(unittest.TestCase):
    def test_contract_is_full_development_non_gating_and_locked_test_free(self) -> None:
        self.assertEqual(CONTRACT["stage_id"], "B6R-P4")
        self.assertEqual(CONTRACT["development_input"]["sample_count"], 8000)
        self.assertEqual(len(CONTRACT["perturbations"]), 16)
        self.assertTrue(CONTRACT["gate_policy"]["non_gating"])
        self.assertFalse(CONTRACT["locked_test_policy"]["path_configured"])
        self.assertEqual(CONTRACT["locked_test_policy"]["array_open_count_required"], 0)
        self.assertEqual(CONTRACT["raspberry_pi_scope"], "OUT_OF_SCOPE")

    def test_noise_is_seeded_bounded_and_repeatable(self) -> None:
        frame = np.full((62, 80, 1), 0.5, dtype=np.float32)
        spec = next(item for item in CONTRACT["perturbations"] if item["id"] == "additive_noise_sigma_0p03")
        first = perturb_one(frame, "sdt:validation:00001", spec, CONTRACT["perturbation_seed"])
        second = perturb_one(frame, "sdt:validation:00001", spec, CONTRACT["perturbation_seed"])
        other = perturb_one(frame, "sdt:validation:00002", spec, CONTRACT["perturbation_seed"])
        self.assertTrue(np.array_equal(first, second))
        self.assertFalse(np.array_equal(first, other))
        self.assertGreaterEqual(float(first.min()), 0.0)
        self.assertLessEqual(float(first.max()), 1.0)
        self.assertLessEqual(float(np.max(np.abs(first - frame))), 0.090001)

    def test_sparse_line_occlusion_and_shift_preserve_tensor_contract(self) -> None:
        frame = np.linspace(0.0, 1.0, 62 * 80, dtype=np.float32).reshape(62, 80, 1)
        selected = [
            next(item for item in CONTRACT["perturbations"] if item["id"] == condition_id)
            for condition_id in ("sparse_hot_cold_ratio_0p010", "line_dropout_4", "occlusion_22x23", "spatial_shift_p2_m2")
        ]
        hashes = []
        for spec in selected:
            result = perturb_one(frame, "sdt:validation:00123", spec, CONTRACT["perturbation_seed"])
            self.assertEqual(result.shape, (62, 80, 1))
            self.assertEqual(result.dtype, np.float32)
            self.assertTrue(np.isfinite(result).all())
            self.assertGreaterEqual(float(result.min()), 0.0)
            self.assertLessEqual(float(result.max()), 1.0)
            hashes.append(hashlib.sha256(result.astype("<f4").tobytes()).hexdigest())
        self.assertEqual(len(set(hashes)), len(hashes))

    def test_metrics_report_per_class_flip_probability_and_numerical_fields(self) -> None:
        labels = np.array([0, 1, 2, 1], dtype=np.int64)
        clean = np.array([[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.2, 0.7], [0.1, 0.6, 0.3]], dtype=np.float32)
        changed = clean.copy()
        changed[3] = np.array([0.1, 0.3, 0.6], dtype=np.float32)
        baseline = classification_metrics(labels, clean)
        result = condition_metrics(labels, clean, changed, 1e-5)
        self.assertEqual(baseline["accuracy"], 1.0)
        self.assertEqual(result["prediction_flip_count"], 1)
        self.assertEqual(result["prediction_flip_rate"], 0.25)
        self.assertIn("HUMAN_FALL_PROXY", result["per_class"])
        self.assertEqual(result["numerical_integrity"]["status"], "PASS")

    def test_isolated_helper_rejects_nonfinite_shape_and_range_but_casts_dtype(self) -> None:
        with self.assertRaises(ValueError):
            prepare_replay_input(np.full((62, 80, 1), np.nan, dtype=np.float32))
        with self.assertRaises(ValueError):
            prepare_replay_input(np.zeros((61, 80, 1), dtype=np.float32))
        with self.assertRaises(ValueError):
            prepare_replay_input(np.full((62, 80, 1), 2.0, dtype=np.float32))
        float64 = prepare_replay_input(np.ones((62, 80, 1), dtype=np.float64))
        integer = prepare_replay_input(np.ones((62, 80), dtype=np.uint8))
        self.assertEqual(float64.dtype, np.float32)
        self.assertEqual(integer.shape, (62, 80, 1))

    def test_exact_p2_artifact_loads_with_fp32_contract(self) -> None:
        artifact = ROOT / CONTRACT["p2_artifact"]["path"]
        self.assertEqual(sha256_file(artifact), CONTRACT["p2_artifact"]["sha256"])
        runner = TFLiteRunner(artifact)
        metadata = runner.metadata()
        self.assertEqual(metadata["input"]["shape"], [1, 62, 80, 1])
        self.assertEqual(metadata["input"]["dtype"], "float32")
        self.assertEqual(metadata["output"]["shape"], [1, 3])
        self.assertEqual(metadata["output"]["dtype"], "float32")


if __name__ == "__main__":
    unittest.main()
