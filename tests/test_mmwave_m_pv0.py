#!/usr/bin/env python3
"""Focused M-PV0 tests. No D2 payload, training, or adapter work."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry"
GENERATOR = ROOT / "scripts/mmwave_m_pv0_public_multidomain_registry.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_m_pv0.py"
SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"


def load(name: str) -> dict:
    return json.loads((REGISTRY / name).read_text(encoding="utf-8"))


class TestMmwaveMPV0(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.check_call(["python3", str(GENERATOR)], cwd=ROOT)
        cls.validator = subprocess.run(
            ["python3", str(VALIDATOR)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_validator_pass(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertIn(result["gate"], {"PASS", "PASS_WITH_LIMITATIONS"})

    def test_roles_and_d2_lock(self) -> None:
        policy = load("role_lock_policy.json")
        self.assertEqual(policy["roles"]["D0"], "REQUIRED_PRIMARY_DEVELOPMENT_DOMAIN")
        self.assertEqual(policy["roles"]["D1"], "REQUIRED_AUXILIARY_DEVELOPMENT_DOMAIN")
        self.assertEqual(policy["roles"]["D2"], "LOCKED_PUBLIC_CROSS_DEVICE_TEST")
        self.assertEqual(policy["roles"]["D3"], "OPTIONAL_NON_BLOCKING_QUALITY_RR_DEVELOPMENT_DOMAIN")
        self.assertEqual(policy["D3_NON_BLOCKING"], "YES")
        lock = policy["d2_lock"]
        self.assertEqual(lock["PUBLIC_METADATA_ACCESS"], "YES")
        self.assertEqual(lock["PAYLOAD_ACQUISITION"], "NO")
        self.assertEqual(lock["PAYLOAD_SEMANTIC_INSPECTION"], "NO")
        self.assertEqual(lock["FEATURE_EXTRACTION"], "NO")
        self.assertEqual(lock["MODEL_INFERENCE"], "NO")
        self.assertEqual(lock["MODEL_INFERENCE_COUNT"], 0)
        self.assertEqual(lock["candidate_inference"], "FORBIDDEN")
        self.assertEqual(lock["candidate_inference_count"], 0)

    def test_mr60_and_heldout_exclusion(self) -> None:
        policy = load("role_lock_policy.json")
        for key in ("supervised_TRAIN", "supervised_VAL", "supervised_TEST"):
            self.assertEqual(policy["mr60_policy"][key], "FORBIDDEN")
        source = load("source_registry.json")
        split = json.loads(SPLIT.read_text(encoding="utf-8"))
        heldout = source["consumed_evidence"]["m_n6_new_model_heldout_test"]
        self.assertEqual(heldout["subject_ids"], split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        self.assertEqual(heldout["V2_SELECTION_REUSE"], "FORBIDDEN")
        self.assertFalse(source["consumed_evidence"]["CONSUMED_SUBJECT_SET_UNRESOLVED"])
        self.assertEqual(policy["heldout_exclusion"]["OLD_HELDOUT_SELECTION_REUSE_FORBIDDEN"], "YES")

    def test_no_absolute_paths_and_checksums(self) -> None:
        checksums = load("checksums.json")
        blob = json.dumps(load("source_registry.json"))
        self.assertNotIn("/Users/", blob)
        self.assertNotIn("file://", blob)
        source_text = (REGISTRY / "source_registry.json").read_text(encoding="utf-8")
        import hashlib

        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        self.assertEqual(checksums["files"]["source_registry.json"], digest)

    def test_d3_conflict_recorded(self) -> None:
        exceptions = load("exception_registry.json")
        codes = [row["code"] for row in exceptions["exceptions"]]
        self.assertIn("D3_PARTICIPANT_RECORDING_COUNT_CONFLICT", codes)
        self.assertEqual(exceptions["total_blockers"], 0)

    def test_generator_idempotent(self) -> None:
        first = (REGISTRY / "checksums.json").read_text(encoding="utf-8")
        subprocess.check_call(["python3", str(GENERATOR)], cwd=ROOT)
        second = (REGISTRY / "checksums.json").read_text(encoding="utf-8")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
