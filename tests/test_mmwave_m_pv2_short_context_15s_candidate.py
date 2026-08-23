from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV2_short_context_15s_candidate"


class MMPV2ShortContext15SCandidateTest(unittest.TestCase):
    def test_required_evidence_bundle_exists(self) -> None:
        required = {
            "input_contract.json",
            "target_alignment.json",
            "dataset_audit.json",
            "training_config.json",
            "model_card.json",
            "evaluation_result.json",
            "limitations.json",
            "checksums.json",
        }
        self.assertEqual(
            required,
            {path.name for path in OUT.iterdir() if path.is_file()},
        )

    def test_short_contract_and_alignment(self) -> None:
        contract = json.loads((OUT / "input_contract.json").read_text())
        alignment = json.loads((OUT / "target_alignment.json").read_text())
        self.assertEqual(contract["context"]["duration_s"], 15)
        self.assertEqual(contract["context"]["sampling_rate_hz"], 10)
        self.assertEqual(contract["context"]["samples"], 150)
        self.assertEqual(contract["context"]["shape"], "[B,150,1]")
        self.assertEqual(
            contract["task_contract"]["target_states"],
            ["PRESENT", "ABSENT", "AMBIGUOUS", "TARGET_UNAVAILABLE"],
        )
        self.assertTrue(alignment["alignment_validation"]["future_samples"] is False)
        self.assertEqual(
            alignment["short_target_contract"]["relative_target_sample_range"],
            [100, 150],
        )

    def test_governed_membership_and_no_selection(self) -> None:
        audit = json.loads((OUT / "dataset_audit.json").read_text())
        result = json.loads((OUT / "evaluation_result.json").read_text())
        self.assertEqual(audit["source_membership"]["D0"]["context_count"], 318)
        self.assertEqual(audit["source_membership"]["D0"]["subject_count"], 66)
        self.assertEqual(audit["source_membership"]["D1"]["context_count"], 244)
        self.assertEqual(audit["source_membership"]["total_model_ready_unique"], 562)
        self.assertEqual(audit["leakage_audit"]["d2_rows"], 0)
        self.assertFalse(result["selection"]["performed"])
        self.assertFalse(result["selection"]["final_selection"])
        self.assertEqual(result["status"], "EVIDENCE_PRODUCED_NO_SELECTION")

    def test_focused_validator_passes(self) -> None:
        from scripts.validate_mmwave_m_pv2_short_context_15s_candidate import validate

        result = validate()
        self.assertTrue(result["ok"], result["failed_checks"])
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")


if __name__ == "__main__":
    unittest.main()
