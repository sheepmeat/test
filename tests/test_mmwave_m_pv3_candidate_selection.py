from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_candidate_selection"


class MMPV3CandidateSelectionArtifactsTest(unittest.TestCase):
    def test_contract_is_frozen_and_30s_only(self) -> None:
        contract = json.loads((ROOT / "config/mmwave/m_pv3_selection_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "FROZEN_BEFORE_EVALUATION")
        self.assertEqual(contract["lane"], "30S_CANDIDATE_ONLY")
        self.assertEqual(contract["evaluation_scope"]["authorized_candidates"], 9)
        self.assertTrue(contract["ranking_policy"]["combined_score"] == "NOT_USED")

    def test_required_evidence_and_all_candidates(self) -> None:
        required = (
            "selection_contract.json",
            "candidate_selection_inventory.json",
            "candidate_metrics_audit.json",
            "candidate_ranking.json",
            "selection_decision.json",
            "determinism_audit.json",
            "exception_registry.json",
            "validation_result.json",
            "checksums.sha256",
        )
        for name in required:
            self.assertTrue((OUT / name).is_file(), name)
        metrics = json.loads((OUT / "candidate_metrics_audit.json").read_text(encoding="utf-8"))
        keys = {row["candidate_key"] for row in metrics["candidates"]}
        expected = {f"{family}/seed_{seed}" for family in ("family_a", "family_b", "family_c") for seed in (11, 23, 47)}
        self.assertEqual(keys, expected)
        self.assertEqual(len(metrics["candidates"]), 9)

    def test_quality_rr_and_provenance_gates_are_reported(self) -> None:
        inventory = json.loads((OUT / "candidate_selection_inventory.json").read_text(encoding="utf-8"))
        self.assertTrue(inventory["all_inventory_checks_pass"])
        self.assertTrue(inventory["provenance_audit"]["provenance_intact"])
        metrics = json.loads((OUT / "candidate_metrics_audit.json").read_text(encoding="utf-8"))
        for row in metrics["candidates"]:
            validation = row["validation"]["D1_DEV_VAL_PLUS_Q2"]
            self.assertEqual(validation["quality"]["hard_Q2_invalid_false_acceptance"], 0.0)
            self.assertEqual(validation["consumer_quality_gate"]["invalid_input_physiology_exposed_count"], 0)
            rr = row["validation"]["D1_DEV_VAL"]["rr"]
            for name in ("within_2_bpm", "within_4_bpm", "within_6_bpm"):
                self.assertIn(name, rr)

    def test_selection_and_replay_are_fail_closed(self) -> None:
        decision = json.loads((OUT / "selection_decision.json").read_text(encoding="utf-8"))
        self.assertIn(decision["selection_result"], {"SELECTED_FLOAT_MODEL", "MULTIPLE_ACCEPTABLE_CANDIDATES", "NO_SELECTION_READY"})
        if decision["selection_result"] != "SELECTED_FLOAT_MODEL":
            self.assertIsNone(decision["selected_candidate"])
            self.assertFalse(decision["ready_for_m_pv4"])
        determinism = json.loads((OUT / "determinism_audit.json").read_text(encoding="utf-8"))
        self.assertTrue(determinism["fresh_process"])
        self.assertTrue(determinism["deterministic"])
        self.assertTrue(all(determinism["equalities"].values()))
        validation = json.loads((OUT / "validation_result.json").read_text(encoding="utf-8"))
        self.assertEqual(validation["training_invocations"], 0)
        self.assertFalse(validation["d2_access"])
        self.assertFalse(validation["mr60_supervised_use"])


if __name__ == "__main__":
    unittest.main()
