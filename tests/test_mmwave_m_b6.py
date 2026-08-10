# SafeNest mmWave Track — Phase M-B6 Focused Unit Tests

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from validate_mmwave_m_b6 import MB6ValidationError, validate_m_b6_artifacts


class TestMB6StageEquivalence(unittest.TestCase):
    """Focused negative & integrity unit tests for Phase M-B6 stage-equivalence artifacts."""

    def setUp(self):
        self.root_dir = ROOT_DIR
        self.manifest_dir = ROOT_DIR / "datasets/mmwave/manifests/M-B6_stage_equivalence"
        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_manifest_dir = self.temp_dir / "M-B6_stage_equivalence"
        shutil.copytree(self.manifest_dir, self.temp_manifest_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_validator_passes_on_unmodified_artifacts(self):
        """Clean baseline validator execution must pass."""
        res = validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.manifest_dir)
        self.assertTrue(res["validation_success"])
        self.assertEqual(res["m_b6_gate_status"], "PASS_WITH_WARNINGS")

    def test_validator_fails_on_stale_input_identity_sha(self):
        """Stale or corrupted upstream SHA in input_identity.json must raise validation error."""
        p = self.temp_manifest_dir / "input_identity.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["inputs"][0]["measured_sha256"] = "0" * 64
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Upstream identity SHA mismatch", str(ctx.exception))

    def test_validator_fails_on_keras_prediction_corruption(self):
        """Corrupted Keras predictions in keras_predictions.npz must raise validation error."""
        p = self.temp_manifest_dir / "keras_predictions.npz"
        npz = dict(np.load(p))
        first_k = list(npz.keys())[0]
        npz[first_k][0] = (npz[first_k][0] + 1) % 3
        np.savez_compressed(p, **npz)

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Keras prediction vector mismatch", str(ctx.exception))

    def test_validator_fails_on_float_tflite_sha_corruption(self):
        """Corrupted Float TFLite file SHA in manifest must raise validation error."""
        p = self.temp_manifest_dir / "stage_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = [key for key in data["artifacts"] if "stage_b" in key][0]
        data["artifacts"][k]["sha256"] = "0" * 64
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Float TFLite SHA mismatch", str(ctx.exception))

    def test_validator_fails_on_float_tflite_dtype_mismatch(self):
        """Non-float32 dtype for Float TFLite must raise validation error."""
        p = self.temp_manifest_dir / "stage_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = [key for key in data["artifacts"] if "stage_b" in key][0]
        data["artifacts"][k]["input_dtype"] = "int8"
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Float TFLite dtype mismatch", str(ctx.exception))

    def test_validator_fails_on_int8_sha_corruption(self):
        """Corrupted Strict INT8 file SHA in manifest must raise validation error."""
        p = self.temp_manifest_dir / "stage_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = [key for key in data["artifacts"] if "stage_c" in key][0]
        data["artifacts"][k]["sha256"] = "0" * 64
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Strict INT8 SHA mismatch", str(ctx.exception))

    def test_validator_fails_on_int8_input_dtype_mismatch(self):
        """Non-int8 input dtype for Strict INT8 must raise validation error."""
        p = self.temp_manifest_dir / "stage_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = [key for key in data["artifacts"] if "stage_c" in key][0]
        data["artifacts"][k]["input_dtype"] = "float32"
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Strict INT8 dtype mismatch", str(ctx.exception))

    def test_validator_fails_on_select_tf_ops_detected(self):
        """Presence of Select TF Ops in Strict INT8 manifest must raise validation error."""
        p = self.temp_manifest_dir / "stage_artifact_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        k = [key for key in data["artifacts"] if "stage_c" in key][0]
        data["artifacts"][k]["select_tf_ops_count"] = 1
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Select TF Ops detected", str(ctx.exception))

    def test_validator_fails_on_top1_agreement_corruption(self):
        """Corrupted top1_agreement metric in pairwise equivalence JSON must raise error."""
        p = self.temp_manifest_dir / "pairwise_equivalence_metrics.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        first_k = list(data["pairwise_equivalence"].keys())[0]
        data["pairwise_equivalence"][first_k]["a_to_c"]["top1_agreement"] = 0.0
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Pairwise field 'a_to_c.top1_agreement' mismatch", str(ctx.exception))

    def test_validator_fails_on_subject_level_tp_corruption(self):
        """Subject-level per-class metric corruption must trigger validation failure."""
        p = self.temp_manifest_dir / "subject_level_stage_metrics.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        first_k = list(data["subject_level_stage_metrics"].keys())[0]
        first_subj = list(data["subject_level_stage_metrics"][first_k]["stage_a"]["per_subject"].keys())[0]
        data["subject_level_stage_metrics"][first_k]["stage_a"]["per_subject"][first_subj]["class_metrics"]["NORMAL"]["tp"] += 999
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("class_metrics field 'NORMAL.tp' mismatch", str(ctx.exception))

    def test_validator_fails_on_locked_test_access_violation(self):
        """Non-zero performance access to LOCKED_TEST must raise error."""
        p = self.temp_manifest_dir / "locked_test_access_audit.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["performance_access_attempts"] = 1
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("LOCKED_TEST_ACCESS_VIOLATION", str(ctx.exception))

    def test_validator_fails_on_path_traversal_checksum(self):
        """Path traversal attempt in checksums.sha256 must raise validation error."""
        p = self.temp_manifest_dir / "checksums.sha256"
        content = p.read_text(encoding="utf-8")
        corrupted = content.replace("m_b6_summary.json", "../m_b6_summary.json")
        p.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Path traversal", str(ctx.exception))

    def test_validator_fails_on_malformed_checksum_digest(self):
        """Malformed SHA digest in checksums.sha256 must raise validation error."""
        p = self.temp_manifest_dir / "checksums.sha256"
        content = p.read_text(encoding="utf-8")
        corrupted = content.replace(content[:64], "INVALID_SHA_DIGEST")
        p.write_text(corrupted, encoding="utf-8")

        with self.assertRaises(MB6ValidationError) as ctx:
            validate_m_b6_artifacts(root_dir=self.root_dir, manifest_dir=self.temp_manifest_dir)
        self.assertIn("Invalid SHA-256 digest format", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
