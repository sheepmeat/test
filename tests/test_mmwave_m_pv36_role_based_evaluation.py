"""Focused regression tests for the M-PV3.6 contract-design phase."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_mmwave_m_pv36_role_based_evaluation as validator


def test_contract_prohibits_selection_and_combined_winner_score() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    assert contract["decision_boundary"]["production_model_selection"] is False
    assert contract["decision_boundary"]["m_pv4_approval"] is False
    assert contract["global_rules"]["combined_winner_score"] == "PROHIBITED"
    assert contract["global_rules"]["safety_is_non_compensable"] is True


def test_short_role_does_not_receive_rr_penalty() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    role = contract["roles"]["ROLE_S_SHORT_CONTEXT"]
    assert role["rr_metric_status"] == "NOT_APPLICABLE"
    assert role["temporal_hold_metric_status"] == "NOT_APPLICABLE"


def test_long_role_subroles_have_non_overlapping_membership_and_explicit_not_applicable_metrics() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    full_task = contract["roles"]["ROLE_L_FULL_TASK"]
    rr_quality = contract["roles"]["ROLE_L_RR_QUALITY"]
    isolation = contract["roles"]["ROLE_L_ISOLATION"]

    assert full_task["membership"] == "M_PV3_FAMILY_B_AND_FAMILY_C_ONLY"
    assert full_task["input_shape"] == "[B,300,1]"
    assert full_task["tasks"] == ["breathing_evidence", "rr", "quality"]

    assert rr_quality["membership"] == "M_PV3_FAMILY_A_ONLY"
    assert rr_quality["input_shape"] == "[B,59]"
    assert rr_quality["breathing_metric_status"] == "NOT_APPLICABLE_NO_BREATHING_HEAD"

    assert isolation["membership"] == "M_PV35_30S_PARITY_CNN_ONLY"
    assert isolation["input_shape"] == "[B,300,1]"
    assert isolation["rr_metric_status"] == "NOT_APPLICABLE_NO_RR_HEAD"
    assert isolation["quality_metric_status"] == "NOT_APPLICABLE_NO_QUALITY_HEAD"


def test_i1_q2_safety_precedence_is_class_a_and_non_compensable() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    safety = contract["metric_taxonomy"]["class_a_safety"]
    invariants = safety["i1_q2_runtime_invariants"]

    assert safety["runtime_precedence"] == ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"]
    assert invariants["presence_false_blocks_physiology_card"] is True
    assert invariants["presence_unknown_blocks_physiology_card"] is True
    assert invariants["input_unavailable_blocks_physiology_card"] is True
    assert invariants["input_unavailable_must_not_emit"] == ["PRESENT", "ABSENT", "NORMAL", "APNEA"]
    assert invariants["q2_synthetic_evidence_scope"] == "SAFETY_EVIDENCE_ONLY"
    assert contract["metric_taxonomy"]["class_b_role_specific_physiology"]["q2_safety_metrics_are_compensable_utility"] is False


def test_d1_present_is_available_with_limitation_not_stable_role_eligibility() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    d1 = contract["evaluation_data_requirements"]["breathing_both_class_evaluation_required"]["current_d1_dev_val"]
    assert d1 == {
        "eligible_present": 57,
        "ambiguous": 2,
        "eligible_absent": 0,
        "present_evaluation_state": "AVAILABLE_WITH_LIMITATION",
        "stable_role_eligibility": "INCOMPLETE",
    }


def test_focused_contract_validator_passes() -> None:
    result = validator.validate()
    assert result["ok"] is True, result
    assert result["gate"] == "PASS_WITH_LIMITATIONS"
