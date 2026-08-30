from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from inference import thermal_tv2_a0 as a0


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "config/thermal/tv2_a0_standalone_prototype_manifest.json").read_text(encoding="utf-8")
)
PREPROCESS = json.loads(
    (ROOT / "config/thermal/tv2_a0_relative_appearance_preprocessing.json").read_text(encoding="utf-8")
)


class ThermalTv2A0StandaloneTest(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(42)
        self.frame = rng.normal(24.0, 3.0, size=(62, 80)).astype(np.float32)

    def test_preprocess_shape_dtype_range(self) -> None:
        out = a0.preprocess_canonical_frame(self.frame)
        self.assertEqual(out.shape, (1, 62, 80, 1))
        self.assertEqual(out.dtype, np.float32)
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)

    def test_preprocess_deterministic(self) -> None:
        first = a0.preprocess_canonical_frame(self.frame)
        second = a0.preprocess_canonical_frame(self.frame.copy())
        np.testing.assert_array_equal(first, second)

    def test_nan_rejected(self) -> None:
        bad = self.frame.copy()
        bad[0, 0] = np.nan
        with self.assertRaises(a0.ThermalTv2A0Error):
            a0.preprocess_canonical_frame(bad)

    def test_inf_rejected(self) -> None:
        bad = self.frame.copy()
        bad[1, 1] = np.inf
        with self.assertRaises(a0.ThermalTv2A0Error):
            a0.preprocess_canonical_frame(bad)

    def test_wrong_shape_rejected(self) -> None:
        with self.assertRaises(a0.ThermalTv2A0Error):
            a0.preprocess_canonical_frame(np.zeros((48, 64), dtype=np.float32))

    def test_unsupported_source_profile_rejected(self) -> None:
        with self.assertRaises(a0.ThermalTv2A0Error):
            a0.preprocess_canonical_frame(self.frame, source_profile="MI48_RAW_UINT16")

    def test_class_mapping_order(self) -> None:
        self.assertEqual(list(a0.CLASS_NAMES), ["NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY"])
        self.assertEqual(MANIFEST["class_mapping"], list(a0.CLASS_NAMES))

    def test_manifest_tflite_hash(self) -> None:
        path = ROOT / MANIFEST["tflite"]["repository_relative_path"]
        self.assertEqual(path.stat().st_size, MANIFEST["tflite"]["size_bytes"])
        self.assertEqual(a0.sha256_file(path), MANIFEST["tflite"]["sha256"])

    def test_tflite_load_allocate_one_inference(self) -> None:
        interpreter, inp, out, digest = a0.load_tflite_interpreter(ROOT, MANIFEST)
        self.assertEqual(digest, MANIFEST["tflite"]["sha256"])
        result = a0.infer_preprocessed(
            interpreter, inp, out, a0.preprocess_canonical_frame(self.frame),
        )
        self.assertEqual(len(result["probabilities"]), 3)
        self.assertTrue(np.isfinite(result["probabilities"]).all())
        self.assertIn(result["predicted_label"], a0.CLASS_NAMES)

    def test_tiny_keras_tflite_parity_sample(self) -> None:
        try:
            import tensorflow as tf
        except ImportError:
            self.skipTest("TensorFlow not available")
        keras_path = ROOT / MANIFEST["keras"]["repository_relative_path"]
        model = tf.keras.models.load_model(keras_path, compile=False)
        tensor = a0.preprocess_canonical_frame(self.frame)
        keras_out = model.predict(tensor, verbose=0).astype(np.float32)
        interpreter, inp, out, _ = a0.load_tflite_interpreter(ROOT, MANIFEST)
        tflite_out = np.asarray(
            a0.infer_preprocessed(interpreter, inp, out, tensor)["probabilities"],
            dtype=np.float32,
        )
        self.assertEqual(int(np.argmax(keras_out[0])), int(np.argmax(tflite_out)))
        self.assertLess(float(np.max(np.abs(keras_out[0] - tflite_out))), 1e-5)
        self.assertEqual(PREPROCESS["representation"], "RELATIVE_THERMAL_APPEARANCE_V1")
        self.assertEqual(PREPROCESS["normalization"], "FRAME_ROBUST_P2_P98_V1")
        self.assertEqual(PREPROCESS["output"]["shape"], [1, 62, 80, 1])


if __name__ == "__main__":
    unittest.main()
