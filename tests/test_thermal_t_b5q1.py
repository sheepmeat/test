"""Focused compact tests for the T-B5Q1 TRAIN-domain gate."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from datasets.thermal.t_b1_preprocessing import canonical_json, sha256_file
from scripts.validate_thermal_t_b5q1 import (
    CHECKSUM_FILES,
    EVIDENCE_REL,
    REPORT_REL,
    REQUIRED_JSON,
    validate_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


class ThermalTB5Q1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="thermal_tb5q1_fixture_")
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
            rows = [f"{sha256_file(self.evidence / item)}  {item}" for item in sorted(CHECKSUM_FILES)]
            (self.evidence / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _result(self) -> dict:
        return validate_evidence(repo_root=self.repo, evidence_dir=self.evidence, check_checksums=True)

    def test_valid_train_domain_gap_bundle_passes(self) -> None:
        result = self._result()
        self.assertEqual(result["evidence_validation"], "PASS")
        self.assertEqual(result["root_cause"], "TRAIN_DOMAIN_RANGE_GAP")
        self.assertFalse(result["candidate_created"])

    def test_train_identity_hash_is_required(self) -> None:
        doc = self._load("source_identity.json")
        doc["canonical_train"]["sha256"] = "0" * 64
        self._save("source_identity.json", doc)
        self.assertTrue(any(item["code"] == "TRAIN_IDENTITY_INVALID" for item in self._result()["errors"]))

    def test_frozen_checkpoint_identity_is_required(self) -> None:
        doc = self._load("source_identity.json")
        doc["frozen_float_source"]["same_selected_weights_proven"] = False
        self._save("source_identity.json", doc)
        self.assertTrue(any(item["code"] == "FLOAT_SOURCE_INVALID" for item in self._result()["errors"]))

    def test_historical_selector_reproduction_is_required(self) -> None:
        doc = self._load("historical_calibration.json")
        doc["historical_selector"]["selection_reproduced"] = False
        self._save("historical_calibration.json", doc)
        self.assertTrue(any(item["code"] == "HISTORICAL_SELECTOR_INVALID" for item in self._result()["errors"]))

    def test_p1_must_remain_frozen(self) -> None:
        doc = self._load("source_identity.json")
        doc["p1_contract"]["refit"] = True
        self._save("source_identity.json", doc)
        self.assertTrue(any(item["code"] == "P1_IDENTITY_INVALID" for item in self._result()["errors"]))

    def test_real_field_data_cannot_be_used_for_calibration(self) -> None:
        doc = self._load("distribution_comparison.json")
        doc["real_evaluation_boundary"]["used_for_calibration"] = True
        self._save("distribution_comparison.json", doc)
        self.assertTrue(any(item["code"] == "REAL_BOUNDARY_INVALID" for item in self._result()["errors"]))

    def test_candidate_claim_is_rejected_after_domain_gap(self) -> None:
        doc = self._load("decision.json")
        doc["candidate_generation"]["created"] = True
        self._save("decision.json", doc)
        self.assertTrue(any(item["code"] == "CANDIDATE_SCOPE_INVALID" for item in self._result()["errors"]))

    def test_conversion_must_not_run_after_train_domain_gap(self) -> None:
        doc = self._load("execution_environment.json")
        doc["analysis"]["tflite_conversion_performed"] = True
        self._save("execution_environment.json", doc)
        self.assertTrue(any(item["code"] == "EXECUTION_SCOPE_INVALID" for item in self._result()["errors"]))

    def test_historical_artifact_must_remain_unchanged(self) -> None:
        doc = self._load("decision.json")
        doc["historical_preservation"]["historical_full_int8_modified"] = True
        self._save("decision.json", doc)
        self.assertTrue(any(item["code"] == "HISTORICAL_ARTIFACT_MODIFIED" for item in self._result()["errors"]))

    def test_absolute_paths_are_rejected(self) -> None:
        doc = self._load("source_identity.json")
        doc["debug_path"] = "/" + "Users/example/train.npy"
        self._save("source_identity.json", doc)
        self.assertTrue(any(item["code"] == "ABSOLUTE_PATH_LEAK" for item in self._result()["errors"]))

    def test_checksum_coverage_is_required(self) -> None:
        checksum = self.evidence / "checksums.sha256"
        lines = [line for line in checksum.read_text(encoding="utf-8").splitlines() if not line.endswith("  distribution_comparison.json")]
        checksum.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertTrue(any(item["code"] == "CHECKSUM_COVERAGE_MISSING" for item in self._result()["errors"]))

    def test_inherited_canonical_equivalence_is_locked(self) -> None:
        doc = self._load("distribution_comparison.json")
        doc["canonical_historical_equivalence"]["pairs"]["TFLITE_FP32__FULL_INT8"]["argmax_agreement"] = 1.0
        self._save("distribution_comparison.json", doc)
        self.assertTrue(any(item["code"] == "CANONICAL_EQUIVALENCE_INVALID" for item in self._result()["errors"]))


if __name__ == "__main__":
    unittest.main()
