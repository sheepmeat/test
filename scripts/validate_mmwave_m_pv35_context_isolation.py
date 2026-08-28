#!/usr/bin/env python3
"""Focused fail-closed validator for M-PV3.5 controlled context isolation."""

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

CONTRACT = ROOT / "config/mmwave/m_pv35_context_isolation_contract.json"
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_5_controlled_context_isolation"
MODEL_ROOT = ROOT / "models/mmwave/m_pv35_context_isolation"
IDENTITY = "MMWAVE_V2_M_PV35_CONTROLLED_CONTEXT_ISOLATION_V1"
REQUIRED = (
    "experimental_controls.json",
    "common_scaler.json",
    "dataset_accounting.json",
    "checkpoint_registry.json",
    "subject_metrics.json",
    "cycle_count_analysis.json",
    "recovery_q2_audit.json",
    "footprint_comparison.json",
    "evaluation_result.json",
    "decision.json",
    "provenance_and_safety_audit.json",
    "run_metadata.json",
    "checksums.json",
    "checksums.sha256",
)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
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
        return [found for item in value.values() for found in walk_strings(item)]
    if isinstance(value, list):
        return [found for item in value for found in walk_strings(item)]
    return []


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    check(checks, "required_outputs_present", not missing, missing)
    if missing or not CONTRACT.is_file():
        return {
            "schema_version": "M-PV3.5.1",
            "phase": "M-PV3.5",
            "gate": "BLOCKED",
            "ok": False,
            "failed_checks": [item["name"] for item in checks if not item["ok"]],
            "checks": checks,
        }

    contract = read(CONTRACT)
    controls = read(OUT / "experimental_controls.json")
    scaler = read(OUT / "common_scaler.json")
    dataset = read(OUT / "dataset_accounting.json")
    registry = read(OUT / "checkpoint_registry.json")
    subjects = read(OUT / "subject_metrics.json")
    cycle = read(OUT / "cycle_count_analysis.json")
    recovery = read(OUT / "recovery_q2_audit.json")
    footprint = read(OUT / "footprint_comparison.json")
    evaluation = read(OUT / "evaluation_result.json")
    decision = read(OUT / "decision.json")
    safety = read(OUT / "provenance_and_safety_audit.json")
    checksums = read(OUT / "checksums.json")

    check(checks, "frozen_identity", contract.get("contract_id") == IDENTITY and controls.get("identity") == IDENTITY and evaluation.get("identity") == IDENTITY, {
        "contract": contract.get("contract_id"), "controls": controls.get("identity"), "evaluation": evaluation.get("identity"),
    })
    lanes = contract.get("lanes")
    expected_lanes = [
        {"lane_id": "CONTEXT_15S", "context_seconds": 15, "input_shape": "[B,150,1]", "sample_count": 150, "input_interval": "[t-15s,t]"},
        {"lane_id": "CONTEXT_30S", "context_seconds": 30, "input_shape": "[B,300,1]", "sample_count": 300, "input_interval": "[t-30s,t]"},
    ]
    check(checks, "only_context_length_varies", lanes == expected_lanes and controls.get("only_variable") == "context_duration_and_corresponding_input_tensor_length", lanes)
    shared = contract.get("shared_controls", {})
    architecture = shared.get("architecture", {})
    optimization = shared.get("optimization", {})
    check(checks, "architecture_and_parameters_frozen", architecture.get("identifier") == "PARITY_TRACE_CNN_V1" and architecture.get("parameter_count_expected") == 2297 and architecture.get("variable_input_length_is_the_only_architectural_degree_of_freedom") is True, architecture)
    check(checks, "optimizer_seed_loss_controls_frozen", optimization.get("name") == "Adam" and optimization.get("learning_rate") == 0.001 and optimization.get("weight_decay") == 0.0001 and optimization.get("batch_size") == 32 and optimization.get("max_epochs") == 150 and optimization.get("seeds") == [11, 23, 47] and shared.get("loss", {}).get("threshold_fixed_before_training") == 0.5, optimization)
    check(checks, "common_train_only_scaler", scaler.get("profile_id") == "MMWAVE_V2_M_PV35_COMMON_30S_TRAIN_ZSCORE_V1" and scaler.get("fit_scope") == ["D0:TRAIN", "D1:D1_DEV_TRAIN"] and scaler.get("fit_context_seconds") == 30 and scaler.get("shared_without_refit_across_lanes") is True and scaler.get("window_count") == 503, scaler)

    check(checks, "governed_dataset_scope", dataset.get("train_context_count") == 503 and dataset.get("d1_dev_val_context_count") == 59 and dataset.get("counts", {}).get("by_source") == {"D0": 318, "D1": 244} and dataset.get("counts", {}).get("by_split") == {"D1_DEV_TRAIN": 185, "D1_DEV_VAL": 59, "TRAIN": 318} and dataset.get("d1_train_subject_count") == 8 and dataset.get("d1_dev_val_subject_count") == 3 and dataset.get("d1_subject_intersection_count") == 0, dataset.get("counts"))
    forbidden_scope_detail = {
        key: dataset.get(key)
        for key in (
            "d0_val_used", "d0_subject_heldout_used", "d2_rows", "d2_semantic_access",
            "mr60_supervised_physiology_used", "new_labels_created", "target_regenerated",
        )
    }
    check(checks, "forbidden_dataset_scope_excluded", dataset.get("d0_val_used") is False and dataset.get("d0_subject_heldout_used") is False and dataset.get("d2_rows") == 0 and dataset.get("d2_semantic_access") is False and dataset.get("mr60_supervised_physiology_used") is False and dataset.get("new_labels_created") is False and dataset.get("target_regenerated") is False, forbidden_scope_detail)
    lineage = dataset.get("lineage", [])
    required_lineage = {"source_id", "subject_id", "recording_id", "model_input_id", "split", "breathing_state", "breathing_supervision_eligible", "quality_status", "base_context_interval_s", "target_interval_s", "r1_profile", "r2_profile", "synthetic"}
    check(checks, "complete_unique_lineage", len(lineage) == 562 and len({row.get("model_input_id") for row in lineage if isinstance(row, Mapping)}) == 562 and all(isinstance(row, Mapping) and required_lineage.issubset(row) for row in lineage), {"lineage_count": len(lineage), "unique": len({row.get("model_input_id") for row in lineage if isinstance(row, Mapping)})})

    registered = registry.get("checkpoints", [])
    expected_keys = {(lane, seed) for lane in ("CONTEXT_15S", "CONTEXT_30S") for seed in (11, 23, 47)}
    actual_keys = {(row.get("lane_id"), row.get("seed")) for row in registered if isinstance(row, Mapping)}
    checkpoint_problems = []
    for row in registered:
        if not isinstance(row, Mapping):
            checkpoint_problems.append("non-mapping")
            continue
        path = ROOT / str(row.get("path", ""))
        if not path.is_file() or not path.is_relative_to(MODEL_ROOT) or sha(path) != row.get("sha256"):
            checkpoint_problems.append(str(row.get("path")))
    check(checks, "all_six_checkpoint_artifacts_present", actual_keys == expected_keys and not checkpoint_problems and registry.get("selection_status") == "NO_SELECTION_EVALUATION_ONLY", {"keys": sorted(actual_keys), "problems": checkpoint_problems})

    lanes_result = evaluation.get("lanes", {})
    lane_problems = []
    for lane_id, seconds, samples in (("CONTEXT_15S", 15, 150), ("CONTEXT_30S", 30, 300)):
        lane = lanes_result.get(lane_id, {})
        seed_results = lane.get("seed_results", []) if isinstance(lane, Mapping) else []
        if lane.get("context_seconds") != seconds or lane.get("input_shape") != f"[B,{samples},1]" or [row.get("seed") for row in seed_results] != [11, 23, 47]:
            lane_problems.append(f"{lane_id}: identity/seeds")
        if any(row.get("training", {}).get("parameter_count") != 2297 for row in seed_results if isinstance(row, Mapping)):
            lane_problems.append(f"{lane_id}: parameter count")
        if any("dev_metrics" not in row or "d0_train_observe_metrics" not in row for row in seed_results if isinstance(row, Mapping)):
            lane_problems.append(f"{lane_id}: metrics")
        if lane.get("footprint", {}).get("parameter_count") != 2297:
            lane_problems.append(f"{lane_id}: footprint")
    comparison = evaluation.get("comparison", {})
    check(checks, "per_seed_metrics_and_exact_parameter_parity", not lane_problems and comparison.get("parameter_count_identical") is True and comparison.get("same_optimizer_loss_seeds_and_early_stopping_rule") is True and comparison.get("combined_score_created") is False, {"problems": lane_problems, "comparison": comparison})

    subject_rows = subjects.get("rows", [])
    expected_subject_keys = {(lane, seed, subject) for lane in ("CONTEXT_15S", "CONTEXT_30S") for seed in (11, 23, 47) for subject in {row.get("subject_id") for row in lineage if row.get("split") == "D1_DEV_VAL"}}
    actual_subject_keys = {(row.get("lane_id"), row.get("seed"), row.get("subject_id")) for row in subject_rows if isinstance(row, Mapping)}
    check(checks, "per_seed_subject_reporting", actual_subject_keys == expected_subject_keys and len(subject_rows) == 18, {"actual": len(actual_subject_keys), "expected": len(expected_subject_keys)})

    frequency = cycle.get("frequency_resolution", {})
    check(checks, "cycle_and_frequency_engineering_analysis", [(row.get("rr_bpm"), row.get("cycles_in_15s"), row.get("cycles_in_30s")) for row in cycle.get("rows", [])] == [(6, 1.5, 3.0), (8, 2.0, 4.0), (12, 3.0, 6.0), (20, 5.0, 10.0)] and frequency.get("15s_delta_f_hz") == 1 / 15 and frequency.get("30s_delta_f_hz") == 1 / 30 and cycle.get("interpretation") == "ENGINEERING_CONTEXT_ONLY_NOT_A_PROOF_OF_BREATHING_ACCURACY", cycle)
    recovery_lanes = recovery.get("lanes", {})
    recovery_ok = recovery.get("profile") == "SYNTHETIC_Q2_INPUT_UNAVAILABLE_ONLY" and recovery.get("comparison", {}).get("context_refill_difference_s_30_minus_15") == 15
    for lane_id, seconds in (("CONTEXT_15S", 15), ("CONTEXT_30S", 30)):
        rows = recovery_lanes.get(lane_id, [])
        recovery_ok = recovery_ok and len(rows) == 3 and all(
            row.get("context_refill_time_s") == seconds and row.get("first_valid_inference_time_s") == seconds and row.get("invalid_application_state") == "INPUT_UNAVAILABLE" and row.get("model_invocation_when_invalid") == "BLOCKED" and not any(row.get(key) for key in ("invalid_emitted_as_present", "invalid_emitted_as_absent", "invalid_emitted_as_normal", "invalid_emitted_as_apnea"))
            for row in rows
        )
    check(checks, "q2_fail_closed_and_synthetic_recovery_only", recovery_ok and recovery.get("not_a_real_sensor_latency_measurement") is True, recovery)
    check(checks, "footprint_separated_from_speed_claim", footprint.get("parameter_count_identical") is True and footprint.get("interpretation") == "operation_and_memory_estimates_only_not_a_hardware_benchmark" and all(not item.get("hardware_speed_measured") and not item.get("raspberry_pi_speed_claim") for item in footprint.get("lanes", {}).values()), footprint)

    check(checks, "no_selection_or_production_claim", decision.get("gate") == "PASS_WITH_LIMITATIONS" and decision.get("statement") == "controlled comparison completed" and decision.get("selection_result") == "NOT_APPLICABLE_NO_MODEL_SELECTION" and decision.get("selected_model") is None and decision.get("m_pv4_approved") is False and evaluation.get("selected_model") is None, decision)
    check(checks, "fail_closed_safety_preserved", safety.get("d2_semantic_access") is False and safety.get("mr60_supervised_physiology") is False and safety.get("q2_fail_closed") is True and safety.get("quality_gate_modified") is False and safety.get("invalid_input_application_state") == "INPUT_UNAVAILABLE" and safety.get("invalid_input_does_not_emit") == ["PRESENT", "ABSENT", "NORMAL", "APNEA"], safety)

    checksum_files = checksums.get("files", {})
    checksum_problems = []
    for relative, expected in checksum_files.items():
        path = ROOT / str(relative)
        if not path.is_file() or sha(path) != expected:
            checksum_problems.append(str(relative))
    actual_files = {
        path.relative_to(ROOT).as_posix()
        for root in (OUT, MODEL_ROOT)
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"checksums.json", "checksums.sha256"}
    }
    check(checks, "checksum_coverage", not checksum_problems and set(checksum_files) == actual_files, {"problems": checksum_problems, "expected_count": len(actual_files), "recorded_count": len(checksum_files)})
    absolute = [value for value in walk_strings([dataset, registry, evaluation, safety]) if value.startswith(("/", "file://", "~"))]
    check(checks, "repository_relative_machine_independent_artifacts", not absolute, absolute[:10])

    failures = [item["name"] for item in checks if not item["ok"]]
    return {
        "schema_version": "M-PV3.5.1",
        "phase": "M-PV3.5",
        "identity": IDENTITY,
        "gate": "PASS_WITH_LIMITATIONS" if not failures else "BLOCKED",
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation_result_validator.json")
    args = parser.parse_args()
    result = validate()
    if args.write:
        (OUT / "validation_result_validator.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
