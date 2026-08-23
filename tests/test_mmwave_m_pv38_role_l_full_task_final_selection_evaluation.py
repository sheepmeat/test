"""Focused tests for the fail-closed M-PV3.8 final-selection gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_mmwave_m_pv38_role_l_full_task_final_selection_evaluation import validate


OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_role_L_full_task_final_selection_evaluation"
EXPECTED = {f"Family_{family}_seed_{seed}" for family in ("B", "C") for seed in (11, 23, 47)}


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_validator_accepts_terminal_membership_block():
    result = validate()
    assert result["ok"] is True
    assert result["artifact_valid"] is True
    assert result["gate"] == "BLOCKED_INVALID_FINAL_MEMBERSHIP"
    assert result["failed_checks"] == []
    assert result["evaluated_candidate_count"] == 0


def test_manifest_freezes_roster_and_prohibitions():
    manifest = load("evaluation_manifest.json")
    assert set(manifest["authorized_candidates"]) == EXPECTED
    assert manifest["candidate_count"] == 6
    assert manifest["decision"] == "BLOCKED_INVALID_FINAL_MEMBERSHIP"
    assert manifest["candidate_output_accessed"] is False
    assert manifest["candidate_evaluation_performed"] is False
    assert manifest["training_performed"] is False
    assert manifest["threshold_modified"] is False
    assert manifest["combined_score_created"] is False
    assert manifest["ranking_created"] is False
    assert manifest["post_hoc_seed_selection"] is False
    assert manifest["d2_access"] is False
    assert manifest["mr60_supervised_physiology"] is False
    assert manifest["m_pv4_approved"] is False


def test_membership_audit_records_missing_absent_class_without_relabeling():
    audit = load("membership_audit.json")
    assert audit["membership_id"] == "D1_FINAL_SELECTION_BOTH_CLASS_V1"
    assert audit["membership_manifest_present"] is False
    assert audit["membership_lock_valid"] is False
    observed = audit["observed_source_rows"]
    assert observed["eligible_present"] == 57
    assert observed["eligible_absent"] == 0
    assert observed["ambiguous"] == 2
    for subject, row in audit["per_subject"].items():
        assert row["observed_eligible_absent"] == 0, subject
        assert row["absent_deficit"] == 19, subject
    assert {row["breathing_reference_state"] for row in audit["ambiguous_records"]} == {"BREATHING_REFERENCE_AMBIGUOUS"}
    assert audit["candidate_training_subject_disjointness"]["pass"] is True


def test_decision_table_and_cards_do_not_fabricate_metrics():
    table = load("candidate_decision_table.json")
    assert {row["candidate_key"] for row in table["rows"]} == EXPECTED
    assert all(row["decision"] == "BLOCKED_INVALID_FINAL_MEMBERSHIP" for row in table["rows"])
    assert all(row["evaluation_status"] == "NOT_EVALUATED" for row in table["rows"])
    assert all(row["candidate_output_accessed"] is False and row["safety"] is None and row["breathing"] is None and row["rr"] is None and row["stability"] is None for row in table["rows"])
    for name in ("card_a_safety.json", "card_b_breathing.json", "card_c_rr.json", "card_d_stability.json"):
        card = load(name)
        assert card["evaluation_status"] == "BLOCKED_INVALID_FINAL_MEMBERSHIP"
        assert card["candidate_output_accessed"] is False
        assert len(card["candidates"]) == 6
        assert all(row["status"] == "NOT_EVALUATED" and row["metrics"] is None for row in card["candidates"])


def test_validation_locks_and_checksums_are_explicit():
    result = load("validation_result.json")
    assert result["decision"] == "BLOCKED_INVALID_FINAL_MEMBERSHIP"
    assert result["terminal_membership_block"] is True
    assert result["no_training"] is True
    assert result["no_threshold_change"] is True
    assert result["no_combined_score"] is True
    assert result["no_ranking"] is True
    assert result["no_d2"] is True
    assert result["no_mr60_supervised_physiology"] is True
    checksums = load("checksums.json")
    report = "docs/mmwave/20260823_M-PV3_8_ROLE_L_FULL_TASK_FINAL_SELECTION_EVALUATION.md"
    assert report in checksums["inputs"]


class MMPV38FinalSelectionGateTest(unittest.TestCase):
    """Expose the checks to the stdlib unittest runner."""

    def test_validator(self):
        test_validator_accepts_terminal_membership_block()

    def test_manifest(self):
        test_manifest_freezes_roster_and_prohibitions()

    def test_membership(self):
        test_membership_audit_records_missing_absent_class_without_relabeling()

    def test_cards(self):
        test_decision_table_and_cards_do_not_fabricate_metrics()

    def test_validation(self):
        test_validation_locks_and_checksums_are_explicit()
