#!/usr/bin/env python3
"""Fail-closed validator for the M-PV3.6 Role S evaluation card."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_VERSION = "M-PV3.6-ROLE-S.1"
ROLE_ID = "ROLE_S_SHORT_CONTEXT"
CANDIDATE_ID = "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1"
CONTRACT_ID = "MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1"
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_6_ROLE_S_SHORT_CONTEXT_evaluation"
MANIFEST = OUT / "evidence_manifest.json"
VALIDATION = OUT / "validation_result.json"
CHECKSUMS = OUT / "checksums.json"
CONTRACT = ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [item for child in value.values() for item in walk_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in walk_strings(child)]
    return []


def finite_unit(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value)) and minimum <= float(value) <= maximum


def _validate_metrics(
    checks: list[dict[str, Any]],
    group_name: str,
    seed: str,
    metrics: Mapping[str, Any],
) -> None:
    for name in ("present_recall", "precision", "f1", "brier"):
        value = metrics.get(name)
        lower = 0.0
        upper = 1.0
        add_check(checks, f"metric_range_{group_name}_{seed}_{name}", finite_unit(value, lower, upper), value)
    absent = metrics.get("absent_recall")
    if group_name == "D1_DEV_VAL":
        add_check(checks, f"d1_absent_not_applicable_{seed}", absent is None, absent)
    else:
        add_check(checks, f"d0_absent_recall_defined_{seed}", finite_unit(absent), absent)
    add_check(checks, f"threshold_not_tuned_{group_name}_{seed}", metrics.get("threshold") == 0.5 and metrics.get("threshold_tuned") is False, {"threshold": metrics.get("threshold"), "tuned": metrics.get("threshold_tuned")})
    add_check(checks, f"ambiguous_not_rewritten_{group_name}_{seed}", metrics.get("ambiguous_handling") == "EXCLUDED_FROM_METRICS_NO_LABEL_REWRITE", metrics.get("ambiguous_handling"))


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    required = [CONTRACT, MANIFEST]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    add_check(checks, "required_role_s_artifacts_present", not missing, missing)
    if missing:
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": "M-PV3.6",
            "role_id": ROLE_ID,
            "gate": "BLOCKED",
            "ok": False,
            "failed_checks": [item["name"] for item in checks if not item["ok"]],
            "checks": checks,
        }

    contract = read(CONTRACT)
    manifest = read(MANIFEST)
    add_check(checks, "identity_and_role", manifest.get("schema_version") == SCHEMA_VERSION and manifest.get("role_id") == ROLE_ID and manifest.get("candidate_identity") == CANDIDATE_ID and manifest.get("evaluation_identity") == "M-PV3_6_ROLE_S_SHORT_CONTEXT_EVALUATION_RESULT" and contract.get("contract_id") == CONTRACT_ID, {"manifest_role": manifest.get("role_id"), "candidate": manifest.get("candidate_identity"), "contract": contract.get("contract_id")})
    add_check(checks, "frozen_role_input_and_target", manifest.get("input_and_target") == {
        "context_interval": "[t-15s,t]",
        "input_shape": "[B,150,1]",
        "ordering": "OLDEST_TO_NEWEST",
        "rr": {"evaluated": False, "status": "NOT_APPLICABLE"},
        "sample_count": 150,
        "sampling_rate_hz": 10,
        "target_interval": "[t-5s,t]",
        "target_sample_range": [100, 150],
        "task_scope": "BREATHING_EVIDENCE_ONLY",
        "temporal_hold": {"evaluated": False, "status": "NOT_APPLICABLE"},
        "source_input_contract": "datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/input_contract.json",
        "source_target_alignment": "datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/target_alignment.json",
    }, manifest.get("input_and_target"))

    execution = manifest.get("execution_policy", {})
    forbidden_false = (
        "training_performed",
        "retraining_performed",
        "new_checkpoint_created",
        "threshold_tuning_performed",
        "calibration_fitted",
        "seed_selection_performed",
        "combined_score_created",
        "role_l_comparison_performed",
        "cascade_or_adaptive_context_implemented",
        "d2_accessed",
        "mr60_supervised_physiology_used",
        "int8_generated",
        "raspberry_pi_benchmark_performed",
    )
    add_check(checks, "evaluation_only_no_prohibited_actions", manifest.get("evaluation_only") is True and all(execution.get(name) is False for name in forbidden_false), {name: execution.get(name) for name in forbidden_false})
    frozen = manifest.get("frozen_contract_snapshot", {})
    add_check(checks, "m_pv3_no_selection_and_m_pv4_locked", frozen.get("m_pv3_selection_state") == "NO_SELECTION_READY" and frozen.get("m_pv4_authorized") is False and frozen.get("d2_authorized") is False and frozen.get("mr60_supervised_physiology_authorized") is False and frozen.get("no_combined_score") == "PROHIBITED" and frozen.get("safety_non_compensable") is True, frozen)

    data = manifest.get("governed_data_audit", {})
    add_check(checks, "governed_membership_and_no_reserved_access", data.get("D0", {}).get("context_count") == 318 and data.get("D0", {}).get("subject_count") == 66 and data.get("D0", {}).get("role") == "OBSERVE_ONLY_NOT_HELD_OUT" and data.get("D1", {}).get("val_context_count") == 59 and data.get("D1", {}).get("val_subject_count") == 3 and data.get("D1", {}).get("subject_intersection_count") == 0 and data.get("D0_VAL_accessed") is False and data.get("D0_SUBJECT_HELDOUT_accessed") is False and data.get("D2_accessed") is False and data.get("MR60_supervised_physiology_accessed") is False, {"D0": data.get("D0"), "D1": data.get("D1"), "D0_VAL_accessed": data.get("D0_VAL_accessed"), "D0_SUBJECT_HELDOUT_accessed": data.get("D0_SUBJECT_HELDOUT_accessed"), "D2_accessed": data.get("D2_accessed"), "MR60": data.get("MR60_supervised_physiology_accessed")})
    add_check(checks, "no_target_or_label_leakage", all(data.get(name) is False for name in ("target_regenerated", "future_samples_used", "target_from_radar_amplitude", "target_from_apnea_protocol_string", "target_from_breath_hold_name", "target_from_model_output")), {name: data.get(name) for name in ("target_regenerated", "future_samples_used", "target_from_radar_amplitude", "target_from_apnea_protocol_string", "target_from_breath_hold_name", "target_from_model_output")})

    cards = manifest.get("cards", {})
    required_cards = {"S_BREATHING", "S_SAFETY", "S_STABILITY", "S_RESPONSIVENESS", "S_FOOTPRINT"}
    add_check(checks, "required_role_s_cards_present", required_cards.issubset(cards) and cards.get("S_BREATHING", {}).get("state") == "PASS_WITH_LIMITATIONS" and cards.get("S_SAFETY", {}).get("class") == "A" and cards.get("S_STABILITY", {}).get("class") == "C" and cards.get("S_RESPONSIVENESS", {}).get("class") == "D" and cards.get("S_FOOTPRINT", {}).get("class") == "E", sorted(cards))

    breathing = cards.get("S_BREATHING", {})
    add_check(checks, "ece_not_generated", breathing.get("metrics", {}).get("ece") == {"calibration_already_exists": False, "calibration_generated": False, "reason": "M-PV3.6 permits ECE only when calibration already exists; no calibration was generated.", "state": "NOT_APPLICABLE"}, breathing.get("metrics", {}).get("ece"))
    per_seed = breathing.get("per_seed", {})
    add_check(checks, "all_frozen_seeds_present", set(per_seed) == {"11", "23", "47"}, sorted(per_seed))
    expected_subject_counts = {"D0_TRAIN_OBSERVE": data.get("D0", {}).get("subject_count"), "D1_DEV_VAL": data.get("D1", {}).get("val_subject_count")}
    for seed in ("11", "23", "47"):
        for group_name in ("D0_TRAIN_OBSERVE", "D1_DEV_VAL"):
            group = per_seed.get(seed, {}).get("groups", {}).get(group_name, {})
            metrics = group.get("metrics", {})
            _validate_metrics(checks, group_name, seed, metrics)
            subjects = group.get("subject_level_results", [])
            subject_ids = [item.get("subject_id") for item in subjects]
            add_check(checks, f"subject_results_present_{group_name}_{seed}", len(subjects) == expected_subject_counts[group_name] and len(subject_ids) == len(set(subject_ids)) and all(subject_ids), {"count": len(subjects), "expected": expected_subject_counts[group_name]})

    stability = cards.get("S_STABILITY", {})
    add_check(checks, "stability_card_keeps_all_seed_results", stability.get("all_frozen_seeds_reported") is True and stability.get("mean_only_summary_prohibited") is True and stability.get("post_hoc_seed_selection") is False and stability.get("seed_instability_observed") is True, stability)
    for group_name in ("D0_TRAIN_OBSERVE", "D1_DEV_VAL"):
        summary = breathing.get("summary_by_group", {}).get(group_name, {})
        for metric in ("present_recall", "absent_recall", "precision", "f1", "brier"):
            entry = summary.get(metric, {})
            if group_name == "D1_DEV_VAL" and metric == "absent_recall":
                add_check(checks, f"summary_not_applicable_{group_name}_{metric}", entry.get("status") == "NOT_APPLICABLE" and entry.get("n") == 0, entry)
            else:
                add_check(checks, f"summary_has_population_stats_{group_name}_{metric}", entry.get("status") == "DEFINED" and all(key in entry for key in ("mean", "population_std", "min", "max", "worst_seed", "best_seed")), entry)

    safety = cards.get("S_SAFETY", {})
    scenarios = safety.get("scenarios", {})
    expected_scenarios = {"LARGE_GAP": "LARGE_GAP", "SOURCE_FREEZE": "SOURCE_FREEZE", "STALE_SOURCE": "SOURCE_STALE", "FLAT_EXACT": "SIGNAL_FLAT_EXACT"}
    add_check(checks, "class_a_safety_scenarios_fail_closed", set(scenarios) == set(expected_scenarios) and all(scenarios[name].get("status") == "PASS" and scenarios[name].get("qualification") == "SYNTHETIC_ONLY" and scenarios[name].get("availability_state") == "INPUT_UNAVAILABLE" and scenarios[name].get("physiology_executed") is False and scenarios[name].get("physiology_class_assigned") is None and scenarios[name].get("primary_reason") == reason for name, reason in expected_scenarios.items()), scenarios)
    presence = safety.get("presence_precedence", {})
    add_check(checks, "presence_precedes_quality_and_physiology", all(presence.get(name, {}).get("status") == "PASS" and presence.get(name, {}).get("physiology_executed") is False for name in ("presence_false", "presence_unknown", "presence_true_plus_invalid")), presence)
    add_check(checks, "invalid_outputs_forbidden", safety.get("invalid_must_not_become") == ["PRESENT", "ABSENT", "NORMAL", "APNEA"] and safety.get("invalid_to_physiology_transition", {}).get("status") == "PASS", safety.get("invalid_must_not_become"))
    add_check(checks, "safety_is_synthetic_only", safety.get("qualification") == "SYNTHETIC_ONLY" and safety.get("source_policy", {}).get("d2_accessed") is False and safety.get("source_policy", {}).get("mr60_supervised_physiology_used") is False and safety.get("source_policy", {}).get("threshold_tuning_on_corruption") is False, safety.get("source_policy"))

    responsiveness = cards.get("S_RESPONSIVENESS", {})
    add_check(checks, "responsiveness_is_synthetic_only", responsiveness.get("qualification") == "SYNTHETIC_ONLY" and responsiveness.get("real_device_latency_measured") is False and responsiveness.get("raspberry_pi_benchmark") is False, responsiveness)
    for mode in ("gap", "freeze", "stale_source"):
        item = responsiveness.get("modes", {}).get(mode, {})
        add_check(checks, f"responsiveness_fields_{mode}", item.get("context_refill_time_s") == 15.0 and item.get("first_valid_decision_time_s") == 15.0 and item.get("usable_slot_ratio") is not None and 0.0 <= item.get("usable_slot_ratio") <= 1.0 and item.get("qualification") == "SYNTHETIC_ONLY", item)

    footprint = cards.get("S_FOOTPRINT", {})
    add_check(checks, "footprint_fields_present_without_hardware_claim", footprint.get("parameter_count") == 2297 and footprint.get("model_bytes", {}).get("selected_model_bytes") is None and footprint.get("input_tensor_bytes", {}).get("bytes") == 600 and footprint.get("macs") == 45304 and footprint.get("flops") == 90608 and footprint.get("raspberry_pi_benchmark") is False and footprint.get("int8_generated") is False, footprint)

    limitations = manifest.get("limitations", [])
    required_limitations = ("D1_DEV_VAL contains zero eligible ABSENT", "Seed instability", "limited subject", "RR is NOT_APPLICABLE", "Temporal hold is NOT_APPLICABLE", "D2 remains locked", "MR60 supervised physiology", "No INT8", "No Raspberry Pi")
    add_check(checks, "required_limitations_recorded", all(any(required.lower() in limitation.lower() for limitation in limitations) for required in required_limitations), {"required": required_limitations, "limitations": limitations})
    conclusion = manifest.get("conclusion", {})
    add_check(checks, "future_role_comparison_conclusion_is_non_selection", conclusion.get("question") == "Is ROLE_S_SHORT_CONTEXT sufficiently evidenced for future role comparison?" and conclusion.get("answer") == "PASS_WITH_LIMITATIONS" and "not a final model or context selection" in conclusion.get("statement", ""), conclusion)

    absolute = [value for value in walk_strings(manifest) if value.startswith(("/", "file://", "~"))]
    add_check(checks, "manifest_has_no_machine_absolute_paths", not absolute, absolute[:10])

    if CHECKSUMS.is_file():
        checksum_doc = read(CHECKSUMS)
        files = checksum_doc.get("files", {})
        checksum_failures = []
        for relative, expected in files.items():
            path = ROOT / relative
            if not path.is_file() or sha256(path) != expected:
                checksum_failures.append(relative)
        add_check(checks, "evidence_checksums_match", not checksum_failures and _relative_manifest_key() in files, checksum_failures)
    else:
        add_check(checks, "evidence_checksums_match", True, "deferred_until_validator_write")

    failures = [item["name"] for item in checks if not item["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "M-PV3.6",
        "role_id": ROLE_ID,
        "candidate_identity": CANDIDATE_ID,
        "gate": "PASS_WITH_LIMITATIONS" if not failures else "BLOCKED",
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
    }


def _relative_manifest_key() -> str:
    return MANIFEST.relative_to(ROOT).as_posix()


def write_outputs(result: Mapping[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    VALIDATION.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = read(MANIFEST)
    files = dict(manifest.get("source_artifact_sha256", {}))
    files[_relative_manifest_key()] = sha256(MANIFEST)
    CHECKSUMS.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "files": dict(sorted(files.items()))}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation_result.json and checksums.json")
    args = parser.parse_args()
    result = validate()
    if args.write:
        write_outputs(result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
