#!/usr/bin/env python3
"""Focused D2 locked-acquisition tests. No payload unzip, listing, or parsing."""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_D2_locked_acquisition"
GENERATOR = ROOT / "scripts/mmwave_d2_locked_acquisition.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_d2_locked_acquisition.py"
MPV0_POLICY = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/role_lock_policy.json"
PAYLOAD_LOGICAL = "datasets/raw_archives/external_datasets/VITALSENSE_120_DATASET.zip"

FORBIDDEN_TOKEN_PARTS = (
    ("scipy.io.", "loadmat"),
    ("numpy.", "load("),
    ("h5py.", "File"),
    ("zipfile.", "ZipFile"),
    (".name", "list()"),
    ("tarfile.", "open"),
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


class TestMmwaveD2LockedAcquisition(unittest.TestCase):
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

    def test_validator_records_auth_block_without_lock_violation(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["gate"], "BLOCKED")
        self.assertEqual(result["checks"]["D2_PAYLOAD_ACQUISITION"], "BLOCKED_AUTH_REQUIRED")
        self.assertEqual(result["checks"]["PAYLOAD_GIT_TRACKED"], "NO")
        self.assertEqual(result["checks"]["PAYLOAD_SEMANTIC_INSPECTION"], "NO")
        self.assertEqual(result["checks"]["ARCHIVE_MEMBER_LISTING"], "NO")
        self.assertEqual(result["checks"]["FEATURE_EXTRACTION"], "NO")
        self.assertEqual(result["checks"]["MODEL_INFERENCE"], "NO")
        self.assertEqual(result["checks"]["MODEL_INFERENCE_COUNT"], 0)
        self.assertTrue(result["d2_remains_locked"])

    def test_canonical_identity_and_parent_lock(self) -> None:
        identity = load("source_identity.json")
        policy = json.loads(MPV0_POLICY.read_text(encoding="utf-8"))
        self.assertEqual(identity["role"], "LOCKED_PUBLIC_CROSS_DEVICE_TEST")
        self.assertEqual(identity["dataset_doi"], "10.21227/wq68-sv85")
        self.assertEqual(identity["publication_doi"], "10.1038/s41597-026-07016-6")
        self.assertEqual(identity["publisher"], "IEEE DataPort")
        self.assertEqual(policy["roles"]["D2"], "LOCKED_PUBLIC_CROSS_DEVICE_TEST")
        self.assertEqual(identity["parent_m_pv0_lock"]["commit"], "18e4a4e86d6bf95795d6749a91ce303ad3f1c417")
        self.assertTrue(identity["do_not_substitute"])

    def test_payload_not_acquired_and_not_tracked(self) -> None:
        acquisition = load("acquisition_record.json")
        digest = load("payload_digest_lock.json")
        self.assertFalse(acquisition["payload_acquired"])
        self.assertTrue(acquisition["authentication_required"])
        self.assertFalse(acquisition["ieee_account_session_present_in_environment"])
        self.assertIsNone(digest["LOCAL_COMPUTED_SHA256"])
        self.assertIsNone(digest["payload_byte_size"])
        self.assertFalse(digest["published_checksum_available"])
        tracked = subprocess.check_output(["git", "ls-files", "--", PAYLOAD_LOGICAL], cwd=ROOT, text=True).strip()
        self.assertEqual(tracked, "")
        ignore = subprocess.run(["git", "check-ignore", "-q", "--", PAYLOAD_LOGICAL], cwd=ROOT, check=False)
        self.assertEqual(ignore.returncode, 0)
        self.assertFalse((ROOT / PAYLOAD_LOGICAL).exists())

    def test_lock_invariants_and_no_derived_data(self) -> None:
        access = load("access_state.json")
        self.assertEqual(access["PAYLOAD_SEMANTIC_INSPECTION"], "NO")
        self.assertEqual(access["ARCHIVE_MEMBER_LISTING"], "NO")
        self.assertEqual(access["FEATURE_EXTRACTION"], "NO")
        self.assertEqual(access["MODEL_INFERENCE"], "NO")
        self.assertEqual(access["MODEL_INFERENCE_COUNT"], 0)
        self.assertEqual(access["selection_policy"]["representation_selection"], "FORBIDDEN")
        self.assertEqual(access["selection_policy"]["model_family_selection"], "FORBIDDEN")
        self.assertEqual(access["selection_policy"]["threshold_selection"], "FORBIDDEN")
        self.assertFalse(access["final_evaluation_authorized"])
        self.assertEqual(access["D2_DEVELOPMENT_DEPENDENCY_FOUND"], "NO")
        self.assertEqual(access["d2_derived_data"]["windows"], 0)
        self.assertEqual(access["d2_derived_data"]["model_outputs"], 0)
        self.assertFalse(access["payload_git_tracked"])
        self.assertEqual(access["PARALLEL_TRACK_BRANCH_CONTAMINATION"], "NO")

    def test_no_forbidden_loaders_or_absolute_paths(self) -> None:
        tokens = tuple("".join(parts) for parts in FORBIDDEN_TOKEN_PARTS)
        for rel in (
            "scripts/mmwave_d2_locked_acquisition.py",
            "scripts/validate_mmwave_d2_locked_acquisition.py",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            for token in tokens:
                self.assertNotIn(token, text, rel)
        blob = json.dumps(load("acquisition_record.json"))
        self.assertNotIn("/Users/", blob)
        self.assertNotIn("file://", blob)
        self.assertNotIn("/private/tmp/", blob)

    def test_no_absolute_paths_and_checksums(self) -> None:
        checksums = load("checksums.json")
        text = (MANIFEST / "source_identity.json").read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(checksums["files"]["source_identity.json"], digest)

    def test_deterministic_regeneration(self) -> None:
        first = load("checksums.json")
        subprocess.check_call(["python3", str(GENERATOR)], cwd=ROOT)
        second = load("checksums.json")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
