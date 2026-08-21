#!/usr/bin/env python3
"""Focused D0 split/label audit tests. No training, D2 payload, or MR60 labels."""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit"
GENERATOR = ROOT / "scripts/mmwave_d0_v2_split_label_audit.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_d0_v2_split_label_audit.py"
SPLIT = ROOT / "datasets/mmwave/splits/mmwave_v2_d0_subject_split_v1.json"
MN4_SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"

from scripts.mmwave_d0_v2_split_label_audit import (  # noqa: E402
    ELIGIBILITY_TAXONOMY,
    SPLIT_IDENTITY,
    SPLIT_NAMES,
    assign_subject_splits,
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


class TestMmwaveD0V2SplitLabelAudit(unittest.TestCase):
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
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["checks"]["D2_ACCESSED"], "NO")
        self.assertEqual(result["checks"]["MR60_SUPERVISED_USE"], "NO")
        self.assertEqual(result["checks"]["PARALLEL_TRACK_BRANCH_CONTAMINATION"], "NO")

    def test_canonical_identity_and_accounting(self) -> None:
        population = load("source_population_audit.json")
        split = load("v2_subject_split.json")
        self.assertEqual(population["canonical_d0_identity"]["doi"], "10.5281/zenodo.18599983")
        self.assertEqual(population["canonical_d0_identity"]["canonical_safenest_version"], "Zenodo v1.1")
        self.assertEqual(population["source_population"]["total_subjects"], 110)
        self.assertEqual(population["source_population"]["frozen_excluded_subjects"], 16)
        self.assertEqual(population["source_population"]["v2_eligible_subjects"], 94)
        self.assertEqual(split["eligible_subject_count"], 94)
        self.assertEqual(split["excluded_subject_count"], 16)

    def test_excluded_heldout_absent_from_v2(self) -> None:
        split = load("v2_subject_split.json")
        mn4 = json.loads(MN4_SPLIT.read_text(encoding="utf-8"))
        heldout = set(mn4["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        self.assertEqual(split["excluded_subject_ids"], mn4["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        assigned = set()
        for name in SPLIT_NAMES:
            assigned.update(split["subject_ids"][name])
        self.assertFalse(assigned & heldout)
        self.assertEqual(len(assigned), 94)

    def test_subject_disjoint_and_deterministic(self) -> None:
        split = load("v2_subject_split.json")
        train = set(split["subject_ids"]["TRAIN"])
        val = set(split["subject_ids"]["VAL"])
        heldout = set(split["subject_ids"]["D0_SUBJECT_HELDOUT"])
        self.assertFalse(train & val)
        self.assertFalse(train & heldout)
        self.assertFalse(val & heldout)
        eligible = sorted(train | val | heldout)
        regenerated = assign_subject_splits(list(reversed(eligible)))
        for name in SPLIT_NAMES:
            self.assertEqual(
                sorted(sid for sid, role in regenerated.items() if role == name),
                split["subject_ids"][name],
            )
        self.assertEqual(split["split_identity"], SPLIT_IDENTITY)
        self.assertNotIn("FINAL_TEST", split["subject_ids"])
        self.assertNotIn("LOCKED_PUBLIC_CROSS_DEVICE_TEST", split["subject_ids"])
        self.assertFalse(split["historical_m_n6_train_val_copied"])

    def test_heldout_target_coverage(self) -> None:
        balance = load("split_balance_summary.json")
        coverage = balance["heldout_coverage"]
        self.assertTrue(coverage["usable"])
        self.assertGreaterEqual(coverage["assigned_apnea_proxy_windows"], 1)
        self.assertGreaterEqual(coverage["rr_supervised_windows"], 1)
        self.assertGreaterEqual(coverage["rest_windows"], 1)
        self.assertGreaterEqual(coverage["post_exercise_windows"], 1)
        self.assertGreaterEqual(coverage["lying_windows"], 1)
        self.assertGreaterEqual(coverage["sitting_windows"], 1)
        heldout = balance["by_split"]["D0_SUBJECT_HELDOUT"]
        self.assertGreaterEqual(heldout["subjects_with_assigned_apnea_proxy"], 1)
        self.assertEqual(heldout["conditions"]["Rest"], heldout["recordings"] // 2)
        self.assertEqual(heldout["conditions"]["Post-exercise"], heldout["recordings"] // 2)

    def test_eligibility_taxonomy_and_no_clinical_apnea(self) -> None:
        eligibility = load("eligibility_summary.json")
        label = load("label_reference_audit.json")
        self.assertEqual(eligibility["taxonomy"], list(ELIGIBILITY_TAXONOMY))
        self.assertFalse(label["apnea_policy"]["clinical_apnea_claimed"])
        self.assertTrue(label["apnea_policy"]["unlabeled_quiet_region_is_not_apnea"])
        self.assertTrue(label["apnea_policy"]["low_radar_amplitude_is_not_apnea"])
        self.assertIn("voluntary breath-hold", label["apnea_policy"]["safenest_apnea"])
        blob = json.dumps(label)
        self.assertNotIn("clinical apnea diagnosis claimed", blob.lower())

    def test_no_absolute_paths_and_checksums(self) -> None:
        checksums = load("checksums.json")
        split_text = (MANIFEST / "v2_subject_split.json").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", split_text)
        self.assertNotIn("file://", split_text)
        digest = hashlib.sha256(split_text.encode("utf-8")).hexdigest()
        self.assertEqual(checksums["files"]["v2_subject_split.json"], digest)
        published = SPLIT.read_text(encoding="utf-8")
        self.assertEqual(published, split_text)
        self.assertEqual(
            checksums["split_file"]["sha256"],
            hashlib.sha256(published.encode("utf-8")).hexdigest(),
        )

    def test_deterministic_regeneration(self) -> None:
        first = load("checksums.json")
        subprocess.check_call(["python3", str(GENERATOR)], cwd=ROOT)
        second = load("checksums.json")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
