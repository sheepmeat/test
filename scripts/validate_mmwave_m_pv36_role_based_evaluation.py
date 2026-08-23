#!/usr/bin/env python3
"""Fail-closed validator for the M-PV3.6 role-based evaluation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json"
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_6_role_based_evaluation"
MATRIX = OUT / "evaluation_matrix.json"
EVIDENCE = OUT / "evidence_requirements.json"
IDENTITY = "MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [entry for item in value.values() for entry in walk_strings(item)]
    if isinstance(value, list):
        return [entry for item in value for entry in walk_strings(item)]
    return []


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    required = [path for path in (CONTRACT, MATRIX, EVIDENCE) if not path.is_file()]
    check(checks, "required_contract_artifacts_present", not required, [path.relative_to(ROOT).as_posix() for path in required])
    if required:
        return {"schema_version": "M-PV3.6.1", "phase": "M-PV3.6", "gate": "BLOCKED", "ok": False, "failed_checks": [item["name"] for item in checks if not item["ok"]], "checks": checks}

    contract, matrix, evidence = read(CONTRACT), read(MATRIX), read(EVIDENCE)
    check(checks, "identity_and_design_only_mode", contract.get("contract_id") == IDENTITY and contract.get("phase") == "M-PV3.6" and contract.get("phase_mode") == "CONTRACT_DESIGN_ONLY" and matrix.get("contract_id") == IDENTITY and evidence.get("contract_id") == IDENTITY and matrix.get("result_population_policy") == "NO_NEW_PERFORMANCE_RESULTS_IN_THIS_PHASE", {"contract": contract.get("contract_id"), "matrix": matrix.get("contract_id"), "evidence": evidence.get("contract_id")})

    predecessors = contract.get("predecessors", {})
    pv3 = predecessors.get("m_pv3", {})
    check(checks, "predecessor_state_preserved", pv3.get("authoritative_selection_result") == "NO_SELECTION_READY" and pv3.get("historical_interpretation_must_not_change") is True and predecessors.get("m_pv35", {}).get("controlled_conclusion") == "NO_STABLE_CONTEXT_DURATION_ADVANTAGE_ISOLATED", predecessors)
    expected_guards = {"present_recall_min": 0.95, "brier_max": 0.05, "rr_mae_bpm_max": 5.0, "rr_within_2_bpm_min": 0.4, "rr_within_4_bpm_min": 0.6, "rr_within_6_bpm_min": 0.75}
    check(checks, "m_pv3_utility_guards_preserved_unchanged", pv3.get("preserved_30s_utility_guards") == expected_guards, pv3.get("preserved_30s_utility_guards"))

    boundary = contract.get("decision_boundary", {})
    forbidden = ("production_model_selection", "winning_context_length", "m_pv4_approval", "new_checkpoint", "threshold_tuning", "calibration_fitting", "int8_or_tflite", "raspberry_pi_benchmark", "reserved_evaluation_set_opened", "d2_semantic_access", "mr60_supervised_physiology", "cascade_or_adaptive_context_implementation")
    check(checks, "no_training_selection_or_reserved_access_authorized", all(boundary.get(name) is False for name in forbidden), {name: boundary.get(name) for name in forbidden})

    global_rules = contract.get("global_rules", {})
    check(checks, "no_combined_score_and_safety_non_compensable", global_rules.get("combined_winner_score") == "PROHIBITED" and global_rules.get("weighted_aggregate_score") == "PROHIBITED" and global_rules.get("accuracy_latency_scalar") == "PROHIBITED" and global_rules.get("safety_is_non_compensable") is True and global_rules.get("undefined_metric_representation") == "NOT_APPLICABLE", global_rules)

    roles = contract.get("roles", {})
    short, long = roles.get("ROLE_S_SHORT_CONTEXT", {}), roles.get("ROLE_L_LONG_CONTEXT", {})
    check(checks, "explicit_role_definitions", short.get("context_seconds") == 15 and short.get("input_shape") == "[B,150,1]" and long.get("context_seconds") == 30 and long.get("input_shape") == "[B,300,1]", {"short": short.get("context_seconds"), "long": long.get("context_seconds")})
    check(checks, "short_rr_and_temporal_hold_not_applicable", short.get("rr_metric_status") == "NOT_APPLICABLE" and short.get("temporal_hold_metric_status") == "NOT_APPLICABLE" and "rr" not in short.get("allowed_metric_cards", []), short)
    check(checks, "long_rr_is_role_specific_and_guarded", long.get("m_pv3_utility_guards") == "PRESERVED_UNCHANGED" and set(long.get("rr_metrics", [])) == {"rr_mae_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm"}, long.get("rr_metrics"))

    stability = contract.get("metric_taxonomy", {}).get("class_c_stability", {})
    required_stability = {"every_frozen_seed", "mean", "population_standard_deviation", "minimum", "maximum", "worst_seed", "best_seed", "per_subject_results"}
    check(checks, "seed_instability_explicitly_governed", stability.get("mean_only_summary") == "PROHIBITED" and required_stability.issubset(set(stability.get("required_reporting", []))) and stability.get("seed_selection_policy") == "THRESHOLD_REQUIRES_PRE_REGISTRATION" and stability.get("future_stability_threshold") == "THRESHOLD_REQUIRES_PRE_REGISTRATION", stability)

    data = contract.get("evaluation_data_requirements", {}).get("breathing_both_class_evaluation_required", {})
    check(checks, "d1_absent_deficiency_and_future_authorization_recorded", data.get("state") == "REQUIRES_FUTURE_GATE" and data.get("current_d1_dev_val") == {"eligible_present": 57, "ambiguous": 2, "eligible_absent": 0, "sufficiency": "INCOMPLETE"} and data.get("reserved_d0_evaluation_membership") == "NOT_AUTHORIZED_TO_OPEN_IN_M_PV36", data)

    role_cards = {card.get("role_id"): card for card in matrix.get("role_cards", []) if isinstance(card, Mapping)}
    short_cards = {card.get("card_id"): card for card in role_cards.get("ROLE_S_SHORT_CONTEXT", {}).get("cards", []) if isinstance(card, Mapping)}
    long_cards = {card.get("card_id"): card for card in role_cards.get("ROLE_L_LONG_CONTEXT", {}).get("cards", []) if isinstance(card, Mapping)}
    check(checks, "evaluation_matrix_has_separate_role_cards", {"S_BREATHING", "S_SAFETY", "S_STABILITY", "S_RESPONSIVENESS", "S_FOOTPRINT", "S_RR", "S_TEMPORAL_HOLD"}.issubset(short_cards) and {"L_BREATHING", "L_RR", "L_QUALITY", "L_SAFETY", "L_STABILITY", "L_RESPONSIVENESS", "L_FOOTPRINT"}.issubset(long_cards) and short_cards.get("S_RR", {}).get("state") == "NOT_APPLICABLE", {"short": sorted(short_cards), "long": sorted(long_cards)})

    states = {entry.get("requirement_id"): entry.get("state") for entry in evidence.get("evidence_requirements", []) if isinstance(entry, Mapping)}
    expected_states = {"D1_ABSENT_EVALUATION": "INCOMPLETE", "D2_FINAL_CROSS_DEVICE": "NOT_AUTHORIZED", "MR60_SUPERVISED_PHYSIOLOGY": "NOT_AUTHORIZED", "ROLE_S_RR": "NOT_APPLICABLE", "RASPBERRY_PI_LATENCY": "REQUIRES_FUTURE_GATE", "SEED_STABILITY_THRESHOLD": "THRESHOLD_REQUIRES_PRE_REGISTRATION"}
    check(checks, "evidence_requirement_states_explicit", all(states.get(key) == value for key, value in expected_states.items()) and evidence.get("new_performance_results_populated") is False and evidence.get("production_model_selected") is False and evidence.get("m_pv4_authorized") is False, {key: states.get(key) for key in expected_states})

    future = contract.get("future_gate_requirements", {}).get("cascade_or_adaptive_context_hypothesis_only", {})
    check(checks, "cascade_and_adaptive_implementation_deferred", future.get("implementation_authorized") is False and {"stable_15s_screening_behavior", "joint_confusion_error_matrix", "error_correlation", "threshold_persistence_policy", "fail_closed_composition", "buffer_state_semantics", "latency_composition"}.issubset(set(future.get("required_evidence_first", []))), future)

    absolute = [value for value in walk_strings([contract, matrix, evidence]) if value.startswith(("/", "file://", "~"))]
    check(checks, "machine_readable_artifacts_use_no_machine_paths", not absolute, absolute[:10])
    failures = [item["name"] for item in checks if not item["ok"]]
    return {"schema_version": "M-PV3.6.1", "phase": "M-PV3.6", "contract_id": IDENTITY, "gate": "PASS_WITH_LIMITATIONS" if not failures else "BLOCKED", "ok": not failures, "failed_checks": failures, "checks": checks}


def write_outputs(result: Mapping[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result_path = OUT / "validation_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths = [CONTRACT, MATRIX, EVIDENCE, result_path]
    files = {path.relative_to(ROOT).as_posix(): sha256(path) for path in paths}
    (OUT / "checksums.json").write_text(json.dumps({"schema_version": "M-PV3.6.1", "files": files}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "checksums.sha256").write_text("\n".join(f"{digest}  {path}" for path, digest in files.items()) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write compact validation and checksum evidence")
    args = parser.parse_args()
    result = validate()
    if args.write:
        write_outputs(result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
