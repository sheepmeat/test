"""Focused integrity tests for the frozen M-PV3.6 ROLE_L_FULL_TASK cards."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_mmwave_m_pv36_role_l_full_task_evaluation import validate


OUT = ROOT / "datasets/mmwave/manifests/M-PV3_6_role_L_full_task_evaluation"
EXPECTED = {f"family_{family}/seed_{seed}" for family in ("b", "c") for seed in (11, 23, 47)}


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_validator_passes_without_mutating_frozen_contract():
    result = validate()
    assert result["ok"] is True
    assert result["gate"] == "PASS_WITH_LIMITATIONS"
    assert result["role_id"] == "ROLE_L_FULL_TASK"
    assert result["no_model_selected"] is True
    assert result["failed_checks"] == []


def test_manifest_is_role_l_only_and_selection_stays_closed():
    manifest = load("role_l_full_task_evaluation_manifest.json")
    assert set(manifest["included_candidates"]) == EXPECTED
    assert manifest["role_id"] == "ROLE_L_FULL_TASK"
    assert manifest["m_pv3_baseline"]["selection_result"] == "NO_SELECTION_READY"
    assert manifest["combined_score"] is None
    assert manifest["winner_selected"] is False
    assert manifest["best_seed_selected"] is False
    assert manifest["m_pv4_recommended"] is False
    assert manifest["training_invocations"] == 0
    assert manifest["q2_evaluation"]["scope"] == "SYNTHETIC_ONLY"
    assert manifest["q2_evaluation"]["d2_used"] is False
    assert manifest["q2_evaluation"]["mr60_supervised_physiology"] is False


def test_breathing_card_preserves_absent_and_calibration_limitations():
    card = load("breathing_card.json")
    assert {row["candidate_key"] for row in card["candidates"]} == EXPECTED
    assert card["eligible_present"] == 57
    assert card["eligible_absent"] == 0
    assert card["calibration_fitting"] is False
    for row in card["candidates"]:
        metrics = row["metrics"]
        assert metrics["recall"] is not None
        assert metrics["precision"] is not None
        assert metrics["F1"] is not None
        assert metrics["Brier"] is not None
        assert metrics["absent_recall"]["status"] == "NOT_APPLICABLE"
        assert metrics["ece"]["status"] == "NOT_APPLICABLE"


def test_rr_card_reports_frozen_guards_without_selection_use():
    card = load("rr_card.json")
    assert card["frozen_guards"] == {
        "brier_max": 0.05,
        "present_recall_min": 0.95,
        "rr_mae_bpm_max": 5.0,
        "rr_within_2_bpm_min": 0.4,
        "rr_within_4_bpm_min": 0.6,
        "rr_within_6_bpm_min": 0.75,
    }
    assert {row["candidate_key"] for row in card["candidates"]} == EXPECTED
    for row in card["candidates"]:
        metrics = row["metrics"]
        assert all(metrics[name] is not None for name in ("MAE_bpm", "median_absolute_error_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm"))
        assert row["frozen_guard_comparison"]["thresholds_modified"] is False
        assert row["frozen_guard_comparison"]["selection_use"] is False


def test_safety_card_is_fail_closed_and_synthetic_only():
    card = load("quality_safety_card.json")
    assert card["q2_scope"] == "SYNTHETIC_ONLY"
    assert card["safety_class"] == "A_NON_COMPENSABLE"
    assert card["runtime_precedence"] == ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"]
    assert card["all_safety_pass"] is True
    for row in card["candidates"]:
        safety = row["safety"]
        assert safety["q2_invalid_false_acceptance"] == 0.0
        assert safety["invalid_to_physiology_transition"] == 0
        assert safety["physiology_emitted_after_invalid"] == 0
        assert safety["fail_closed_preservation"] is True
        assert safety["input_unavailable_emissions"] == {"PRESENT": 0, "ABSENT": 0, "NORMAL": 0, "APNEA": 0}
        assert safety["pass"] is True


def test_stability_keeps_all_frozen_seeds_and_subjects():
    card = load("stability_card.json")
    for family in ("family_b", "family_c"):
        family_card = card[family]
        assert set(family_card["seed_results"]) == {"11", "23", "47"}
        assert family_card["all_frozen_seeds_reported"] is True
        assert family_card["post_hoc_seed_selection"] is False
        assert set(family_card["per_subject_results"]["11"]) == {"D1_PERSON_03", "D1_PERSON_09", "D1_PERSON_11"}
        for summary in family_card["summary"].values():
            assert summary["all_frozen_seeds_present"] is True
            assert summary["selection_use"] is False
            assert all(field in summary for field in ("mean", "population_std", "min", "max", "worst_seed", "best_seed"))


def test_footprint_and_limitations_are_explicit():
    footprint = load("footprint_card.json")
    assert {row["candidate_key"] for row in footprint["candidates"]} == EXPECTED
    assert footprint["pi_latency_measured"] is False
    assert footprint["raspberry_pi_claim"] is False
    for row in footprint["candidates"]:
        assert row["hardware_latency"] == "NOT_MEASURED"
        assert row["selection_use"] is False
        assert all(row[field] > 0 for field in ("parameter_count", "model_bytes_checkpoint", "macs_estimate", "flops_estimate"))

    limitations = load("limitations.json")
    codes = {item["code"] for item in limitations["limitations"]}
    assert {"D1_ABSENT_LIMITATION", "D2_LOCKED", "MR60_SUPERVISED_FORBIDDEN", "NO_CALIBRATION", "NO_INT8_TFLITE", "NO_PI_BENCHMARK", "Q2_SYNTHETIC_ONLY"} <= codes
    assert limitations["sufficiently_evidenced_for_future_selection_consideration"] is False


class MMPV36RoleLFullTaskArtifactsTest(unittest.TestCase):
    """Expose the focused checks to the stdlib runner as well as pytest."""

    def test_validator(self):
        test_validator_passes_without_mutating_frozen_contract()

    def test_manifest(self):
        test_manifest_is_role_l_only_and_selection_stays_closed()

    def test_breathing(self):
        test_breathing_card_preserves_absent_and_calibration_limitations()

    def test_rr(self):
        test_rr_card_reports_frozen_guards_without_selection_use()

    def test_safety(self):
        test_safety_card_is_fail_closed_and_synthetic_only()

    def test_stability(self):
        test_stability_keeps_all_frozen_seeds_and_subjects()

    def test_footprint(self):
        test_footprint_and_limitations_are_explicit()
