"""Focused compact tests for the T-B5 real-MI48 corrective audit."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from datasets.thermal.t_b1_preprocessing import canonical_json, sha256_file
from scripts.validate_thermal_t_b5_mi48_quantization_review import (
    EVIDENCE_REL,
    REPORT_REL,
    CHECKSUM_FILES,
    REQUIRED_JSON,
    is_true_unquantized_fp32_policy,
    validate_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


class ThermalTB5MI48QuantizationReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="thermal_tb5_mi48_review_")
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.evidence = self.repo / EVIDENCE_REL
        shutil.copytree(ROOT / EVIDENCE_REL, self.evidence)
        report = self.repo / REPORT_REL
        report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / REPORT_REL, report)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _load(self, name: str) -> dict:
        return json.loads((self.evidence / name).read_text(encoding="utf-8"))

    def _save(self, name: str, value: dict, *, refresh_checksums: bool = True) -> None:
        (self.evidence / name).write_text(canonical_json(value), encoding="utf-8")
        if refresh_checksums:
            rows = [
                f"{sha256_file(self.evidence / item)}  {item}"
                for item in sorted(CHECKSUM_FILES)
            ]
            (self.evidence / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _result(self) -> dict:
        return validate_evidence(repo_root=self.repo, evidence_dir=self.evidence, check_checksums=True)

    def test_valid_audit_only_bundle_passes(self) -> None:
        result = self._result()
        self.assertEqual(result["evidence_validation"], "PASS")
        self.assertEqual(result["overall_outcome"], "PASS_WITH_LIMITATIONS")
        self.assertFalse(result["new_candidate_created"])

    def test_historical_selection_metadata_is_deterministic(self) -> None:
        first = self._load("historical_lineage.json")["representative_source"]
        second = self._load("historical_lineage.json")["representative_source"]
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(first["sample_count"], 512)
        self.assertEqual(first["class_composition"]["real_samples_used"], 0)

    def test_float32_io_alone_is_not_true_fp32(self) -> None:
        dynamic_range_float_io = {
            "input_dtype": "float32",
            "output_dtype": "float32",
            "optimizations": ["DEFAULT"],
            "representative_dataset_attached": False,
            "float16_enabled": False,
            "dynamic_range_quantization": True,
            "quantization_mode": "DYNAMIC_RANGE",
            "builtin_only": True,
        }
        self.assertFalse(is_true_unquantized_fp32_policy(dynamic_range_float_io))
        true_fp32 = dict(dynamic_range_float_io, optimizations=[], dynamic_range_quantization=False, quantization_mode="NONE")
        self.assertTrue(is_true_unquantized_fp32_policy(true_fp32))

    def test_field_data_cannot_become_calibration(self) -> None:
        doc = self._load("real_mi48_evidence.json")
        doc["source"]["used_for_calibration"] = True
        self._save("real_mi48_evidence.json", doc)
        result = self._result()
        self.assertTrue(any(item["code"] == "REAL_SCOPE_INVALID" for item in result["errors"]))

    def test_historical_artifact_identity_is_locked(self) -> None:
        doc = self._load("historical_lineage.json")
        doc["artifact"]["sha256"] = "0" * 64
        self._save("historical_lineage.json", doc)
        result = self._result()
        self.assertTrue(any(item["code"] == "HISTORICAL_ARTIFACT_DRIFT" for item in result["errors"]))

    def test_pixel_distribution_must_not_be_fabricated(self) -> None:
        doc = self._load("historical_lineage.json")
        doc["pixel_level_distribution"]["train_p1"] = {"min": -1.0}
        self._save("historical_lineage.json", doc)
        result = self._result()
        self.assertTrue(any(item["code"] == "UNSUPPORTED_TRAIN_DISTRIBUTION" for item in result["errors"]))

    def test_absolute_path_is_rejected(self) -> None:
        doc = self._load("access_status.json")
        doc["note"] = "/" + "Users/example/field.npz"
        self._save("access_status.json", doc)
        result = self._result()
        self.assertTrue(any(item["code"] == "ABSOLUTE_PATH_LEAK" for item in result["errors"]))

    def test_missing_checksum_is_rejected(self) -> None:
        checksum = self.evidence / "checksums.sha256"
        rows = [line for line in checksum.read_text(encoding="utf-8").splitlines() if not line.endswith("  real_mi48_evidence.json")]
        checksum.write_text("\n".join(rows) + "\n", encoding="utf-8")
        result = self._result()
        self.assertTrue(any(item["code"] == "CHECKSUM_COVERAGE_MISSING" for item in result["errors"]))

    def test_candidate_claim_is_blocked_without_train_payload(self) -> None:
        doc = self._load("audit_summary.json")
        doc["new_int8_candidate_created"] = True
        self._save("audit_summary.json", doc)
        result = self._result()
        self.assertTrue(any(item["code"] == "UNJUSTIFIED_CANDIDATE" for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
