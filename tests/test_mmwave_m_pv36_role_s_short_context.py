"""Focused regression tests for the frozen M-PV3.6 Role S evaluation card."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_mmwave_m_pv36_role_s_short_context as validator  # noqa: E402


MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV3_6_ROLE_S_SHORT_CONTEXT_evaluation/evidence_manifest.json"


class RoleSShortContextEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_focused_validator_passes(self) -> None:
        result = validator.validate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")

    def test_role_scope_and_not_applicable_tasks_are_frozen(self) -> None:
        self.assertEqual(self.manifest["role_id"], "ROLE_S_SHORT_CONTEXT")
        self.assertEqual(self.manifest["input_and_target"]["input_shape"], "[B,150,1]")
        self.assertEqual(self.manifest["input_and_target"]["target_sample_range"], [100, 150])
        self.assertEqual(self.manifest["input_and_target"]["rr"]["status"], "NOT_APPLICABLE")
        self.assertEqual(self.manifest["input_and_target"]["temporal_hold"]["status"], "NOT_APPLICABLE")

    def test_all_seeds_and_subject_results_are_retained(self) -> None:
        breathing = self.manifest["cards"]["S_BREATHING"]
        self.assertEqual(set(breathing["per_seed"]), {"11", "23", "47"})
        for seed in ("11", "23", "47"):
            self.assertEqual(len(breathing["per_seed"][seed]["groups"]["D0_TRAIN_OBSERVE"]["subject_level_results"]), 66)
            self.assertEqual(len(breathing["per_seed"][seed]["groups"]["D1_DEV_VAL"]["subject_level_results"]), 3)
        self.assertEqual(breathing["summary_by_group"]["D1_DEV_VAL"]["absent_recall"]["status"], "NOT_APPLICABLE")
        self.assertFalse(self.manifest["execution_policy"]["seed_selection_performed"])

    def test_safety_and_responsiveness_are_non_physiological_synthetic_evidence(self) -> None:
        safety = self.manifest["cards"]["S_SAFETY"]
        self.assertEqual(set(safety["scenarios"]), {"LARGE_GAP", "SOURCE_FREEZE", "STALE_SOURCE", "FLAT_EXACT"})
        self.assertTrue(all(item["qualification"] == "SYNTHETIC_ONLY" for item in safety["scenarios"].values()))
        self.assertTrue(all(item["physiology_executed"] is False for item in safety["scenarios"].values()))
        self.assertEqual(safety["invalid_must_not_become"], ["PRESENT", "ABSENT", "NORMAL", "APNEA"])
        self.assertEqual(self.manifest["cards"]["S_RESPONSIVENESS"]["qualification"], "SYNTHETIC_ONLY")
        self.assertFalse(self.manifest["execution_policy"]["d2_accessed"])
        self.assertFalse(self.manifest["execution_policy"]["mr60_supervised_physiology_used"])


if __name__ == "__main__":
    unittest.main()
