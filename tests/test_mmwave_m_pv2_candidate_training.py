from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MMPV2CandidateTrainingArtifactsTest(unittest.TestCase):
    def test_contract_is_frozen_and_bounded(self) -> None:
        contract = json.loads((ROOT / "config/mmwave/m_pv2_candidate_training_contract.json").read_text())
        self.assertEqual(contract["status"], "FROZEN_BEFORE_TRAINING")
        self.assertEqual(contract["max_primary_runs"], 9)
        self.assertEqual(contract["seeds"], [11, 23, 47])
        self.assertEqual(contract["dataset_scope"]["d2"]["semantic_access"], "FORBIDDEN")
        self.assertFalse(contract["authorized_candidate_families"]["family_a"]["breathing_head"])

    def test_registry_has_no_selected_model(self) -> None:
        registry = json.loads((ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/candidate_registry.json").read_text())
        self.assertFalse(registry["final_selection"])
        self.assertFalse(registry["selected_float_model"])
        self.assertEqual(len(registry["candidates"]), 9)
        self.assertTrue(all(item["selection_status"] == "NOT_SELECTED" for item in registry["candidates"]))

    def test_membership_and_d2_lock(self) -> None:
        tensor = json.loads((ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/tensor_materialization_audit.json").read_text())
        self.assertEqual(tensor["counts"]["model_ready_unique"], 562)
        self.assertEqual(tensor["counts"]["by_source"], {"D0": 318, "D1": 244})
        self.assertFalse(tensor["tensor_cache_committed"])
        d2 = json.loads((ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/d2_lock_audit.json").read_text())
        self.assertEqual(d2["model_inference_count"], 0)
        self.assertFalse(d2["semantic_access"])

    def test_clean_process_replay(self) -> None:
        audit = json.loads((ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/determinism_audit.json").read_text())
        self.assertTrue(audit["fresh_process"])
        self.assertTrue(audit["canonical_parameter_sha256_equal"])
        self.assertTrue(audit["deterministic"])


if __name__ == "__main__":
    unittest.main()
