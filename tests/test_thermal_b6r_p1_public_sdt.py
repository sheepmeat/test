from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.train_thermal_b6r_p1_public_sdt import (
    adaptive_mean_pool,
    macro_f1,
    softmax,
    train_once,
    write_deterministic_npz,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "config/thermal/b6r_p1_public_sdt_training_contract.json").read_text(encoding="utf-8")
)


class B6RP1PublicSdtTest(unittest.TestCase):
    def test_adaptive_pool_shape_and_repeat(self) -> None:
        images = np.arange(2 * 62 * 80, dtype=np.float32).reshape(2, 62, 80, 1)
        first = adaptive_mean_pool(images)
        second = adaptive_mean_pool(images)
        self.assertEqual(first.shape, (2, 80))
        self.assertTrue(np.array_equal(first, second))

    def test_softmax_rows_sum_to_one(self) -> None:
        probabilities = softmax(np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]]))
        self.assertTrue(np.allclose(probabilities.sum(axis=1), 1.0))

    def test_macro_f1_perfect_predictions(self) -> None:
        labels = np.array([0, 1, 2, 0, 1, 2], dtype=np.int8)
        self.assertEqual(macro_f1(labels, labels), 1.0)

    def test_training_repeat_is_identical(self) -> None:
        rng = np.random.default_rng(7)
        train_features = rng.random((24, 80), dtype=np.float32)
        train_labels = np.arange(24, dtype=np.int8) % 3
        development_features = rng.random((9, 80), dtype=np.float32)
        development_labels = np.arange(9, dtype=np.int8) % 3
        first = train_once(train_features, train_labels, development_features, development_labels, CONTRACT)
        second = train_once(train_features, train_labels, development_features, development_labels, CONTRACT)
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[2], second[2])
        for name in first[0]:
            self.assertTrue(np.array_equal(first[0][name], second[0][name]))

    def test_deterministic_npz_has_stable_bytes(self) -> None:
        arrays = {"bias": np.arange(3, dtype="<f4"), "weights": np.arange(6, dtype="<f4").reshape(2, 3)}
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "first.npz"
            second_path = Path(temp_dir) / "second.npz"
            write_deterministic_npz(first_path, arrays)
            write_deterministic_npz(second_path, arrays)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
