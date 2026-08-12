"""Focused M-B10A candidate-selection setup tests.

The suite uses VALIDATION-only evidence.  It intentionally never calls the
LOCKED_TEST final-evaluation accessor.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from mmwave_m_b10a_selection import REQUIRED_OUTPUTS, SEEDS  # noqa: E402
from validate_mmwave_m_b10a import (  # noqa: E402
    NEGATIVE_CASES,
    MB10AValidationError,
    _negative_case_detected,
    validate_m_b10a_artifacts,
)


OUT = ROOT / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup"


class TestMMWaveMB10A(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validation = validate_m_b10a_artifacts(ROOT, run_upstream=False)

    def test_required_outputs_and_setup_status(self) -> None:
        for name in REQUIRED_OUTPUTS:
            self.assertTrue((OUT / name).is_file(), name)
        summary = json.loads((OUT / "m_b10a_summary.json").read_text())
        self.assertTrue(summary["validation_success"])
        self.assertEqual(summary["selection_status"], "SELECTED_PRELOCKED_REAL_DATA_CANDIDATE")
        self.assertEqual(summary["locked_test_accesses"], 0)
        self.assertFalse(summary["m_b10b_started"])

    def test_pool_is_exact_frozen_real_data_pool(self) -> None:
        pool = json.loads((OUT / "candidate_pool.json").read_text())
        self.assertEqual(pool["candidate_count"], 3)
        self.assertEqual(sorted(row["seed"] for row in pool["candidates"]), list(SEEDS))
        self.assertTrue(all(row["model"]["input_dtype"] == "int8" for row in pool["candidates"]))
        self.assertTrue(all(row["model"]["output_dtype"] == "int8" for row in pool["candidates"]))
        self.assertEqual(pool["excluded_baseline_ids"], ["mmwave_resp_int8", "mmwave_resp_int8_v0.2.0_candidate"])

    def test_rule_is_frozen_before_winner_and_rank_is_lexicographic(self) -> None:
        rule = json.loads((OUT / "selection_rule.json").read_text())
        ranking = json.loads((OUT / "candidate_ranking.json").read_text())
        selected = json.loads((OUT / "selected_candidate_pretest.json").read_text())
        self.assertTrue(rule["frozen_before_candidate_winner"])
        self.assertTrue(rule["no_composite_score"])
        self.assertEqual(rule["epsilon"], 1e-5)
        self.assertEqual(ranking["selected_candidate_id"], selected["candidate_id"])
        self.assertEqual(ranking["deciding_criterion"]["criterion_rank"], 1)
        self.assertEqual(selected["status"], "M-B10_PRELOCKED_REAL_DATA_CANDIDATE")

    def test_seed_44_moderate_collapse_gate_is_visible(self) -> None:
        evidence = json.loads((OUT / "candidate_selection_evidence.json").read_text())
        row = next(item for item in evidence["candidate_evidence"] if item["seed"] == 44)
        self.assertFalse(row["eligible"])
        self.assertFalse(row["eligibility"]["E11"]["passed"])
        failed_profiles = [profile for profile, metrics in row["moderate_profile_metrics"].items() if metrics["recomputed_class_collapse"]["collapsed"]]
        self.assertEqual(failed_profiles, ["M-B7_AMP_X0_75", "M-B7_COMBINED_MODERATE"])

    def test_locked_test_protocol_and_audit_are_preregistered_zero(self) -> None:
        contract = json.loads((OUT / "locked_test_evaluation_contract.json").read_text())
        readiness = json.loads((OUT / "locked_test_access_readiness.json").read_text())
        audit = json.loads((OUT / "locked_test_access_audit.json").read_text())
        self.assertEqual(contract["contract_status"], "PREREGISTERED_NOT_EXECUTED")
        self.assertEqual(readiness["authorization_for_locked_test"], "NO")
        self.assertTrue(readiness["independent_review_required"])
        self.assertEqual(audit["final_accessor_calls"], 0)
        self.assertFalse(audit["locked_test_inputs_loaded"])
        self.assertFalse(audit["locked_test_prediction_output_generated"])
        self.assertEqual(contract["applicable_predefined_numerical_acceptance_threshold"], "FINAL_LOCKED_TEST_NUMERICAL_ACCEPTANCE_THRESHOLD_NOT_PREDEFINED")
        self.assertIn("fpr", contract["metrics_schema"]["per_class_fields"])
        self.assertIn("worst_subject_macro_f1", contract["metrics_schema"]["subject_level"])
        self.assertTrue(readiness["final_access_mechanism_ready"])
        self.assertFalse(readiness["final_access_mechanism"]["final_accessor_called"])

    def test_historical_baselines_are_registered_but_excluded(self) -> None:
        registry = json.loads((OUT / "historical_baseline_registry.json").read_text())
        self.assertEqual(len(registry["baselines"]), 2)
        self.assertTrue(all(row["pool_eligible"] is False for row in registry["baselines"]))
        self.assertTrue(all(row["exclusion_reason"] for row in registry["baselines"]))

    def test_no_sample_level_locked_test_fields_or_local_paths(self) -> None:
        for path in OUT.glob("*.json"):
            text = path.read_text()
            self.assertNotIn("/Users/", text, str(path))
            self.assertNotIn("/private/", text, str(path))
            self.assertNotIn("file://", text, str(path))
            for forbidden in ("locked_test_predictions", "locked_test_macro_f1", "locked_test_confusion", "test_subject_metrics", "test_prediction_distribution"):
                self.assertNotIn(f'"{forbidden}"', text.lower(), str(path))

    def test_complete_validation_evidence_is_present(self) -> None:
        evidence = json.loads((OUT / "candidate_selection_evidence.json").read_text())
        self.assertEqual(evidence["architecture_seed_sensitivity"]["worst_seed"], 44)
        for row in evidence["candidate_evidence"]:
            self.assertEqual(row["subject_level"]["subject_count"], 17)
            self.assertIn("m_b4_seed_stability", row)
            self.assertIn("m_b6_stage_equivalence", row)
            self.assertIn("output_probability_mae", row["m_b6_stage_equivalence"]["pairwise"]["a_to_c"])
            self.assertIn("invoke_p99_ns", row["m_b8_latency_footprint"])
            self.assertIn("model_identity", row["m_b9_runtime_identity"])
            self.assertEqual(set(row["eligibility_evidence"]), {f"E{i}" for i in range(1, 12)})

    def test_negative_corruption_cases_fail_closed(self) -> None:
        """Seven isolated corruption cases are subtests of one test method."""
        for case_id in NEGATIVE_CASES:
            with self.subTest(case_id=case_id):
                self.assertTrue(_negative_case_detected(case_id, ROOT))


if __name__ == "__main__":
    unittest.main(verbosity=2)
