from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from scripts.export_thermal_b6r_p2_public_sdt_fp32_tflite import (
    build_models,
    numpy_adaptive_mean_pool,
    numpy_intermediates,
    select_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "config/thermal/b6r_p2_public_sdt_fp32_tflite_contract.json").read_text(
        encoding="utf-8"
    )
)


class B6RP2PublicSdtTest(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(23)
        self.weights = {
            "weights_1": rng.normal(0.0, 0.02, size=(80, 32)).astype(np.float32),
            "bias_1": rng.normal(0.0, 0.02, size=(32,)).astype(np.float32),
            "weights_2": rng.normal(0.0, 0.02, size=(32, 3)).astype(np.float32),
            "bias_2": rng.normal(0.0, 0.02, size=(3,)).astype(np.float32),
        }

    def test_contract_freezes_tolerance_before_execution(self) -> None:
        tolerances = CONTRACT["predefined_tolerances"]
        self.assertEqual(tolerances["definition_timing"], "defined_before_B6R-P2_export_and_parity_execution")
        self.assertEqual(tolerances["probabilities_max_abs"], 1e-5)
        self.assertEqual(tolerances["probabilities_mean_abs"], 1e-6)
        self.assertEqual(tolerances["mismatch_count_max"], 0)
        self.assertFalse(CONTRACT["locked_test_policy"]["path_configured"])

    def test_pool_boundaries_match_contract(self) -> None:
        self.assertEqual(
            np.linspace(0, 62, 9, dtype=np.int64).tolist(),
            CONTRACT["adaptive_mean_pool"]["height_edges"],
        )
        self.assertEqual(
            np.linspace(0, 80, 11, dtype=np.int64).tolist(),
            CONTRACT["adaptive_mean_pool"]["width_edges"],
        )

    def test_numpy_tensorflow_intermediates_match(self) -> None:
        images = np.arange(3 * 62 * 80, dtype=np.float32).reshape(3, 62, 80, 1)
        images /= float(images.max())
        numpy_values = numpy_intermediates(images, self.weights)
        _, intermediate = build_models(self.weights)
        tensorflow_values = intermediate(images, training=False)
        for name, value in zip(("pooled", "hidden", "logits", "probabilities"), tensorflow_values):
            self.assertTrue(np.allclose(numpy_values[name], value.numpy(), rtol=0, atol=1e-5), name)

    def test_pool_output_shape_and_row_major_order(self) -> None:
        image = np.arange(62 * 80, dtype=np.float32).reshape(1, 62, 80, 1)
        pooled = numpy_adaptive_mean_pool(image)
        self.assertEqual(pooled.shape, (1, 80))
        self.assertLess(float(pooled[0, 0]), float(pooled[0, 1]))
        self.assertLess(float(pooled[0, 9]), float(pooled[0, 10]))

    def test_fixture_selection_is_deterministic_and_balanced(self) -> None:
        labels = np.repeat(np.arange(3, dtype=np.int8), 20)
        probabilities = np.tile(np.array([[0.2, 0.3, 0.5]], dtype=np.float32), (60, 1))
        first, reasons_first = select_fixture(labels, probabilities, 16)
        second, reasons_second = select_fixture(labels, probabilities, 16)
        self.assertEqual(first, second)
        self.assertEqual(reasons_first, reasons_second)
        self.assertEqual(len(first), 48)
        self.assertEqual(np.bincount(labels[first], minlength=3).tolist(), [16, 16, 16])


if __name__ == "__main__":
    unittest.main()
