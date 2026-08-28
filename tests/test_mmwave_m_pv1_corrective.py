#!/usr/bin/env python3
"""Focused tests for the M-PV1 target/context corrective contract."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "datasets/mmwave/manifests/M-PV1_public_multidomain_contract"


class TestMmwaveMPv1Corrective(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((EVIDENCE / "m_pv2_example_manifest.json").read_text(encoding="utf-8"))
        cls.coverage = json.loads((EVIDENCE / "target_coverage_audit.json").read_text(encoding="utf-8"))
        cls.validation = json.loads((EVIDENCE / "validation_result.json").read_text(encoding="utf-8"))
        cls.rows = cls.manifest["examples"]
        cls.model_ready = [row for row in cls.rows if row.get("model_ready") is True]

    def test_present_absent_share_one_fixed_breathing_semantics(self) -> None:
        supervised = [
            row for row in self.model_ready
            if row.get("breathing_supervision_eligible") is True
        ]
        self.assertTrue(supervised)
        self.assertEqual({row["target_duration_s"] for row in supervised}, {5.0})
        self.assertEqual({row["target_anchor"] for row in supervised}, {"FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT"})
        self.assertEqual(
            {row["breathing_reference_state"] for row in supervised},
            {"BREATHING_REFERENCE_PRESENT", "BREATHING_REFERENCE_ABSENT"},
        )

    def test_target_is_final_interval_and_causal(self) -> None:
        for row in self.model_ready:
            self.assertTrue(row["causal_context"])
            self.assertAlmostEqual(row["target_start_s"], row["context_end_s"] - 5.0)
            self.assertAlmostEqual(row["target_end_s"], row["context_end_s"])
            self.assertGreaterEqual(row["target_start_s"], row["context_start_s"])
            self.assertLessEqual(row["target_end_s"], row["context_end_s"])
            self.assertEqual(row["target_anchor"], "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT")

    def test_every_model_ready_row_has_declared_valid_tensor(self) -> None:
        for row in self.model_ready:
            self.assertEqual(
                row["model_input_tensor_status"],
                "VALID_DECLARED_REGENERABLE_FROM_ACCEPTED_CONTRACTS",
            )
            self.assertEqual(row["model_input_tensor_contract"], "MMWAVE_V2_M_PV1_MODEL_INPUT_CONTRACT_V1")
            self.assertEqual(row["model_ready"], True)

    def test_short_events_are_audit_only_without_padding(self) -> None:
        audit_rows = [row for row in self.rows if row.get("model_ready") is not True]
        self.assertEqual(len(audit_rows), 21)
        for row in audit_rows:
            self.assertFalse(row.get("model_ready", False))
            self.assertIn("audit_only_reason", row)
            self.assertIn("NO_PADDING", row["audit_only_reason"])

    def test_unique_input_quality_accounting_and_no_overlay_duplicates(self) -> None:
        input_ids = [row["model_input_id"] for row in self.model_ready]
        self.assertEqual(len(input_ids), len(set(input_ids)))
        self.assertEqual(self.manifest["duplicate_target_overlay_count"], 0)
        self.assertEqual(self.coverage["duplicate_target_overlay_count"], 0)
        clean_ids = {row["model_input_id"] for row in self.model_ready if row["quality_status"] == "CLEAN"}
        self.assertEqual(self.coverage["quality_clean_unique_model_input_count"], len(clean_ids))
        self.assertEqual(len(clean_ids), len(input_ids))

    def test_task_records_do_not_contradict_one_input(self) -> None:
        for row in self.model_ready:
            self.assertNotEqual(row["example_role"], "EVENT_RELATIVE_HOLD_INTERVAL")
            records = {record["target_task"]: record for record in row["target_records"]}
            self.assertEqual(records["breathing_evidence"]["target_state"], row["breathing_reference_state"])
            self.assertFalse(records["temporal_hold"]["supervision_eligible"])
            self.assertEqual(records["temporal_hold"]["learning_boundary"], "DETERMINISTIC_POST_BREATHING_COMPOSITION_ONLY")

    def test_d1_uses_same_breathing_anchor(self) -> None:
        d1 = [row for row in self.model_ready if row["source_id"] == "D1"]
        self.assertEqual(len(d1), 244)
        self.assertEqual({row["target_duration_s"] for row in d1}, {5.0})
        self.assertEqual({row["target_anchor"] for row in d1}, {"FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT"})
        self.assertEqual({row["breathing_reference_state"] for row in d1}, {"BREATHING_REFERENCE_PRESENT", "BREATHING_REFERENCE_AMBIGUOUS"})

    def test_profile_task_compatibility_is_explicit(self) -> None:
        representation = json.loads((EVIDENCE / "representation_freeze.json").read_text(encoding="utf-8"))
        matrix = representation["task_compatibility_matrix"]
        self.assertFalse(matrix["PROFILE_A_FEATURE_F2_V1"]["breathing_evidence"])
        self.assertTrue(matrix["PROFILE_B_TRACE_F3_R1_V1"]["breathing_evidence"])
        self.assertTrue(matrix["PROFILE_C_HYBRID_TRACE_PLUS_F2_V1"]["breathing_evidence"])

    def test_recorded_determinism_and_gate(self) -> None:
        self.assertTrue(self.validation["deterministic_generation"])
        self.assertTrue(self.validation["ok"])
        self.assertEqual(self.validation["gate"], "PASS_WITH_LIMITATIONS")
        self.assertTrue(self.validation["m_pv1_ready_for_m_pv2"])


if __name__ == "__main__":
    unittest.main()
