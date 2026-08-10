# SafeNest mmWave Track — Phase M-B5 Focused Unit Tests

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from validate_mmwave_m_b5 import MB5ValidationError, validate_m_b5_artifacts


class TestMB5RepresentativeCalibration(unittest.TestCase):
    """Focused negative & integrity unit tests for Phase M-B5 representative calibration artifacts."""

    def setUp(self):
        self.root_dir = ROOT_DIR
        self.manifest_dir = ROOT_DIR / "datasets/mmwave/manifests/M-B5_representative_calibration"
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_manifest_dir = self.temp_dir / "M-B5_representative_calibration"
        shutil.copytree(self.manifest_dir, self.temp_manifest_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_validator_passes_on_unmodified_artifacts(self):
        """Clean baseline validator execution must pass."""
        res = validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.manifest_dir)
        self.assertTrue(res["validation_success"])
        self.assertEqual(res["m_b5_gate_status"], "PASS_WITH_WARNINGS")
        self.assertEqual(res["independently_measured"]["selected_calibration_profile"], "M-B5_CAL_CLASS_BALANCED_120")

    def test_validator_fails_on_duplicate_representative_index(self):
        """Duplicate index inside representative_dataset_indices.json must trigger validation failure."""
        p = self.temp_manifest_dir / "representative_dataset_indices.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        # Corrupt Profile A by introducing a duplicate
        data["profile_indices"]["M-B5_CAL_TRAIN_ORDER_120"][1] = data["profile_indices"]["M-B5_CAL_TRAIN_ORDER_120"][0]
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Duplicate index", str(ctx.exception))

    def test_validator_fails_on_wrong_profile_size(self):
        """Profile containing wrong sample count (e.g. 119 instead of 120) must trigger validation failure."""
        p = self.temp_manifest_dir / "representative_dataset_indices.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["profile_indices"]["M-B5_CAL_TRAIN_ORDER_120"].pop()
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("index count mismatch", str(ctx.exception))

    def test_validator_fails_on_profile_nondeterministic_indices(self):
        """Corrupted representative indices must fail deterministic recomputation check."""
        p = self.temp_manifest_dir / "representative_dataset_indices.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        # Swap two indices in Profile B
        data["profile_indices"]["M-B5_CAL_RANDOM_PROPORTIONAL_120"][0], data["profile_indices"]["M-B5_CAL_RANDOM_PROPORTIONAL_120"][1] = (
            data["profile_indices"]["M-B5_CAL_RANDOM_PROPORTIONAL_120"][1],
            data["profile_indices"]["M-B5_CAL_RANDOM_PROPORTIONAL_120"][0],
        )
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("M-B5_PROFILE_NONDETERMINISTIC", str(ctx.exception))

    def test_validator_fails_on_locked_test_access_violation(self):
        """Non-zero performance access to LOCKED_TEST must raise error."""
        p = self.temp_manifest_dir / "locked_test_access_audit.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["performance_access_attempts"] = 1
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("LOCKED_TEST_ACCESS_VIOLATION", str(ctx.exception))

    def test_validator_fails_on_select_tf_ops_detected(self):
        """Presence of Select TF Ops in strict INT8 manifest must raise error."""
        p = self.temp_manifest_dir / "tflite_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = list(data["tflite_artifacts"].keys())[0]
        data["tflite_artifacts"][k]["select_tf_ops_count"] = 1
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("M-B5_SELECT_TF_OPS_DETECTED", str(ctx.exception))

    def test_validator_fails_on_tflite_file_size_mismatch(self):
        """TFLite file byte size mismatch must raise validation error."""
        p = self.temp_manifest_dir / "tflite_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = list(data["tflite_artifacts"].keys())[0]
        data["tflite_artifacts"][k]["bytes"] += 100
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("TFLite file size mismatch", str(ctx.exception))

    def test_validator_fails_on_tflite_sha256_mismatch(self):
        """TFLite file SHA mismatch must raise validation error."""
        p = self.temp_manifest_dir / "tflite_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = list(data["tflite_artifacts"].keys())[0]
        data["tflite_artifacts"][k]["sha256"] = "0" * 64
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("TFLite SHA-256 mismatch", str(ctx.exception))

    def test_validator_fails_on_calibration_selection_mismatch(self):
        """Selected calibration profile mismatch in manifest must trigger validation failure."""
        p = self.temp_manifest_dir / "selected_calibration_profile.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["selected_calibration_profile"] = "M-B5_CAL_TRAIN_ORDER_120"
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Calibration profile selection mismatch", str(ctx.exception))

    def test_validator_fails_on_path_traversal_checksum(self):
        """Path traversal attempt in checksums.sha256 must raise validation error."""
        p = self.temp_manifest_dir / "checksums.sha256"
        content = p.read_text(encoding="utf-8")
        corrupted = content.replace("m_b5_summary.json", "../m_b5_summary.json")
        p.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Path traversal", str(ctx.exception))

    def test_validator_fails_on_malformed_checksum_digest(self):
        """Malformed SHA digest in checksums.sha256 must raise validation error."""
        p = self.temp_manifest_dir / "checksums.sha256"
        content = p.read_text(encoding="utf-8")
        corrupted = content.replace(content[:64], "INVALID_SHA_DIGEST")
        p.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(MB5ValidationError) as ctx:
            validate_m_b5_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Invalid SHA-256 digest format", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
