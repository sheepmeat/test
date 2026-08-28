#!/usr/bin/env python3
"""Standalone validator for B6R-P3 replay evidence and hardware boundaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_ROOT_FOR_IMPORT))

from scripts.benchmark_thermal_b6r_p3_rpi import (
    NOT_AVAILABLE,
    NOT_MEASURED,
    P0_CONTRACT,
    P0_MANIFEST,
    P2_MANIFEST,
    ROOT,
    DEFAULT_CONTRACT,
    expected_p2_artifact,
    legacy_audit,
    load_contract,
    load_fixture,
    p0_fixture_file_audit,
    read_json,
    refresh_checksums,
    repo_path,
    sha256_file,
    write_json,
)


ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/]|file://|/Users/|/home/|/root/|/tmp/|\\\\)"
)
STAT_KEYS = ("count", "mean", "median", "p50", "p95", "p99", "min", "max")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def validate_checksum_registry(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return ["missing:checksums.sha256"]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
            target = repo_path(relative)
        except (ValueError, OSError) as error:
            errors.append(f"invalid:{type(error).__name__}")
            continue
        if not target.is_file():
            errors.append(f"missing:{relative}")
        elif sha256_file(target) != expected:
            errors.append(f"sha256:{relative}")
    return errors


def all_not_measured(statistics: Any) -> bool:
    return isinstance(statistics, dict) and all(statistics.get(key) == NOT_MEASURED for key in STAT_KEYS)


def validate_replay_manifest(contract: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    p2 = read_json(P2_MANIFEST / "parity_manifest.json")
    expected = [
        {
            "fixture_position": int(record["fixture_position"]),
            "development_index": int(record["development_index"]),
            "sample_id": record["sample_id"],
            "target_class_index": int(record["target_class_index"]),
            "target_class": record["target_class"],
            "selection_reason": record["selection_reason"],
        }
        for record in sorted(p2["samples"], key=lambda item: int(item["fixture_position"]))
    ]
    actual = replay.get("samples", [])
    return {
        "stage_id": replay.get("stage_id") == "B6R-P3",
        "role": replay.get("role") == "DEVELOPMENT",
        "dataset_id": replay.get("dataset_id") == contract["required_inheritance"]["dataset_id"],
        "preprocessing_id": replay.get("preprocessing_id") == contract["required_inheritance"]["preprocessing_id"],
        "label_mapping_id": replay.get("label_mapping_id") == contract["required_inheritance"]["label_mapping_id"],
        "parent_p2_sha256": replay.get("parent_p2_parity_manifest_sha256") == sha256_file(
            repo_path(contract["replay_fixture"]["parent_p2_parity_manifest_path"])
        ),
        "sample_count": replay.get("sample_count") == contract["replay_fixture"]["sample_count"],
        "sample_records_inherited_exactly": actual == expected,
        "locked_public_test_access_zero": replay.get("locked_public_test_access_count") == 0,
        "only_development_path": all(
            "validation/" in str(replay.get(key, "")).replace("\\", "/")
            for key in ("images_path", "labels_path", "sample_index_path")
        ),
    }


def validate_blocked_target_evidence(
    contract: dict[str, Any],
    target_access: dict[str, Any],
    environment: dict[str, Any],
    interpreter: dict[str, Any],
    latency: dict[str, Any],
    resources: dict[str, Any],
    stability: dict[str, Any],
    determinism: dict[str, Any],
    run_summary: dict[str, Any],
) -> dict[str, Any]:
    required_env_fields = contract["target_requirements"]["target_environment_fields"]
    environment_unavailable = all(environment.get(field) == NOT_AVAILABLE for field in required_env_fields)
    stats = latency.get("statistics", {})
    latency_unavailable = (
        latency.get("target_status") == "BLOCKED_HARDWARE"
        and latency.get("target_measurement_status") == NOT_MEASURED
        and all_not_measured(stats.get(stage))
        for stage in ("preprocessing_ingress_ms", "inference_ms", "total_ms")
    )
    latency_unavailable = all(latency_unavailable)
    resources_unavailable = (
        resources.get("target_status") == "BLOCKED_HARDWARE"
        and resources.get("target_measurement_status") == NOT_MEASURED
        and resources.get("rss_memory") == NOT_MEASURED
        and resources.get("cpu_utilization") == NOT_MEASURED
        and resources.get("cpu_temperature") == NOT_MEASURED
    )
    stability_unavailable = (
        stability.get("target_status") == "BLOCKED_HARDWARE"
        and stability.get("target_measurement_status") == NOT_MEASURED
        and stability.get("duration_seconds") == NOT_MEASURED
        and stability.get("total_inference_count") == NOT_MEASURED
        and stability.get("failed_inference_count") == NOT_MEASURED
        and stability.get("unexpected_process_termination") == NOT_MEASURED
    )
    determinism_unavailable = (
        determinism.get("target_status") == "BLOCKED_HARDWARE"
        and determinism.get("target_measurement_status") == NOT_MEASURED
        and determinism.get("same_interpreter_instance") == NOT_MEASURED
        and determinism.get("repeated_model_loads") == NOT_MEASURED
        and determinism.get("process_reexecution") == NOT_MEASURED
    )
    return {
        "target_access_blocked": (
            target_access.get("status") == "BLOCKED_HARDWARE"
            and target_access.get("target_measurement_available") is False
            and target_access.get("target_address_persisted") is False
        ),
        "target_environment_unavailable_without_desktop_substitution": (
            environment.get("target_status") == "BLOCKED_HARDWARE"
            and environment.get("target_measurement_status") == NOT_MEASURED
            and environment.get("desktop_substitution_used") is False
            and environment_unavailable
        ),
        "interpreter_unavailable_without_target_claim": (
            interpreter.get("target_status") == "BLOCKED_HARDWARE"
            and interpreter.get("selected_backend") == NOT_MEASURED
            and all(value == NOT_AVAILABLE for value in interpreter.get("packages", {}).values())
        ),
        "latency_not_measured_on_target": latency_unavailable,
        "resources_not_measured_on_target": resources_unavailable,
        "stability_not_measured_on_target": stability_unavailable,
        "determinism_not_measured_on_target": determinism_unavailable,
        "run_summary_hardware_blocked": (
            run_summary.get("status") == "BLOCKED_HARDWARE"
            and run_summary.get("target_benchmark_executed") is False
            and run_summary.get("next_stage_executed") is False
        ),
    }


def _numeric_statistics(statistics: Any, minimum_count: int) -> bool:
    if not isinstance(statistics, dict):
        return False
    try:
        return (
            int(statistics["count"]) >= minimum_count
            and all(np.isfinite(float(statistics[key])) for key in STAT_KEYS[1:])
        )
    except (KeyError, TypeError, ValueError):
        return False


def validate_target_measurement_evidence(
    contract: dict[str, Any],
    target_access: dict[str, Any],
    environment: dict[str, Any],
    interpreter: dict[str, Any],
    latency: dict[str, Any],
    resources: dict[str, Any],
    stability: dict[str, Any],
    determinism: dict[str, Any],
    run_summary: dict[str, Any],
    live_tensor: dict[str, Any],
) -> dict[str, Any]:
    required_env_fields = contract["target_requirements"]["target_environment_fields"]
    latency_stats = latency.get("statistics", {})
    fixed_resource = resources.get("fixed_replay", {})
    same = determinism.get("same_interpreter_instance", {})
    loads = determinism.get("repeated_model_loads", {})
    process = determinism.get("process_reexecution", {})
    return {
        "target_access_reached": (
            target_access.get("status") == "PASS"
            and target_access.get("probe_status") == "TARGET_REACHED"
            and target_access.get("target_measurement_available") is True
            and target_access.get("target_address_persisted") is False
        ),
        "target_identity_recorded": (
            environment.get("target_status") == "TARGET_MEASURED"
            and environment.get("target_identity_confirmed") is True
            and all(environment.get(field) not in (None, NOT_AVAILABLE, NOT_MEASURED) for field in required_env_fields)
            and environment.get("desktop_substitution_used") is False
        ),
        "interpreter_recorded": (
            interpreter.get("target_status") == "TARGET_MEASURED"
            and interpreter.get("selected_backend") not in (None, NOT_AVAILABLE, NOT_MEASURED)
            and interpreter.get("thread_count") == contract["interpreter"]["thread_count"]
        ),
        "live_tensor_contract_pass": live_tensor.get("status") == "PASS",
        "latency_distribution_complete": (
            latency.get("status") == "PASS"
            and latency.get("measured_sample_count_actual") == contract["replay_fixture"]["measured_sample_count"]
            and all(
                _numeric_statistics(latency_stats.get(stage), contract["replay_fixture"]["measured_sample_count"])
                for stage in ("preprocessing_ingress_ms", "inference_ms", "total_ms")
            )
        ),
        "resource_evidence_recorded": (
            resources.get("target_status") == "TARGET_MEASURED"
            and isinstance(fixed_resource, dict)
            and fixed_resource.get("rss_memory") != NOT_MEASURED
            and fixed_resource.get("cpu_utilization") != NOT_MEASURED
        ),
        "prolonged_replay_complete": (
            stability.get("status") == "PASS"
            and float(stability.get("duration_seconds", 0.0)) >= contract["prolonged_replay"]["minimum_duration_seconds"]
            and stability.get("failed_inference_count") == 0
            and stability.get("exception_count") == 0
            and stability.get("nan_inf_output_count") == 0
            and stability.get("shape_dtype_violation_count") == 0
            and stability.get("unexpected_process_termination") is False
        ),
        "determinism_complete": (
            determinism.get("status") == "PASS"
            and same.get("status") == "PASS"
            and loads.get("status") == "PASS"
            and process.get("status") == "PASS"
        ),
        "run_summary_target_recorded": (
            run_summary.get("target_benchmark_executed") is True
            and run_summary.get("next_stage_executed") is False
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args(argv)
    contract = load_contract(args.contract)
    manifest_dir = repo_path(contract["manifest_dir"])
    checks: list[dict[str, Any]] = []

    contract_snapshot = read_json(manifest_dir / "contract_snapshot.json")
    add_check(
        checks,
        "contract_snapshot_matches_live_contract",
        contract_snapshot == contract,
        {"snapshot_matches": contract_snapshot == contract},
    )

    expected_artifact = expected_p2_artifact(contract)
    add_check(checks, "p2_exact_artifact_identity", expected_artifact["status"] == "PASS", expected_artifact)
    add_check(
        checks,
        "p2_contract_identity",
        contract["p2_artifact"]["class_order"] == ["NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY"]
        and contract["p2_artifact"]["quantization"] == "NONE"
        and contract["required_inheritance"]["dataset_authority"] == "PUBLIC_SDT_ONLY_NOT_MI48",
        contract["p2_artifact"],
    )

    replay = read_json(manifest_dir / "replay_manifest.json")
    replay_checks = validate_replay_manifest(contract, replay)
    add_check(checks, "development_fixture_inherited_without_reselection", all(replay_checks.values()), replay_checks)
    try:
        fixture = load_fixture(contract)
        fixture_runtime_ok = all(
            int(record["target_class_index"]) == int(fixture.labels[index])
            for index, record in enumerate(fixture.records)
        )
        fixture_detail: Any = {
            "sample_count": len(fixture.records),
            "canonical_fixture_sha256": fixture.canonical_fixture_sha256,
            "labels_match_replay_manifest": fixture_runtime_ok,
        }
        fixture_ok = fixture_runtime_ok
    except Exception as error:
        fixture_ok = False
        fixture_detail = f"{type(error).__name__}: {str(error)[:240]}"
    add_check(checks, "development_fixture_files_and_labels", fixture_ok, fixture_detail)

    stored_fixture_audit = read_json(manifest_dir / "replay_fixture_audit.json")
    live_fixture_audit = p0_fixture_file_audit(contract)
    add_check(
        checks,
        "p0_development_file_identity",
        stored_fixture_audit == live_fixture_audit and live_fixture_audit["status"] == "PASS",
        live_fixture_audit,
    )

    source_audit = read_json(manifest_dir / "source_identity_audit.json")
    p0_contract = read_json(P0_CONTRACT)
    expected_archives = p0_contract["source_archive_registry"]
    source_checks = {
        "status_pass": source_audit.get("status") == "PASS",
        "expected_six": source_audit.get("archive_count_expected") == 6,
        "found_six": source_audit.get("archive_count_found") == 6,
        "all_match": len(source_audit.get("archives", [])) == 6
        and all(
            item.get("matches_registry") is True
            and item.get("actual_size_bytes") == expected_archives[item["archive_name"]]["size_bytes"]
            and item.get("actual_sha256") == expected_archives[item["archive_name"]]["sha256"]
            for item in source_audit.get("archives", [])
        ),
        "source_root_not_persisted": source_audit.get("source_root_persisted") is False,
        "source_not_modified": source_audit.get("source_mutation_performed") is False,
        "p0_immutability_pass": source_audit.get("p0_recorded_source_immutability_status") == "PASS",
    }
    add_check(checks, "p0_source_archive_identity_six_of_six", all(source_checks.values()), source_checks)

    target_access = read_json(manifest_dir / "target_access_audit.json")
    environment = read_json(manifest_dir / "target_environment.json")
    interpreter = read_json(manifest_dir / "interpreter_inventory.json")
    latency = read_json(manifest_dir / "latency_metrics.json")
    resources = read_json(manifest_dir / "resource_metrics.json")
    stability = read_json(manifest_dir / "stability_metrics.json")
    determinism = read_json(manifest_dir / "determinism_metrics.json")
    run_summary = read_json(manifest_dir / "run_summary.json")
    target_checks = validate_blocked_target_evidence(
        contract, target_access, environment, interpreter, latency, resources, stability, determinism, run_summary
    ) if target_access.get("status") == "BLOCKED_HARDWARE" else validate_target_measurement_evidence(
        contract,
        target_access,
        environment,
        interpreter,
        latency,
        resources,
        stability,
        determinism,
        run_summary,
        read_json(manifest_dir / "live_tensor_metadata.json"),
    )
    add_check(checks, "hardware_blocker_is_explicit", all(target_checks.values()), target_checks)

    locked = read_json(manifest_dir / "locked_test_access_audit.json")
    locked_expected = {
        "role": "LOCKED_PUBLIC_TEST",
        "array_open_count": 0,
        "sample_read_count": 0,
        "metrics_computed": False,
        "used_for_selection_or_tuning": False,
        "path_configured": False,
        "status": "PASS",
    }
    add_check(checks, "locked_public_test_access_zero", all(locked.get(key) == value for key, value in locked_expected.items()), locked)

    shadow = read_json(manifest_dir / "shadow_only_audit.json")
    current_legacy = legacy_audit()
    shadow_unchanged = shadow.get("legacy_unchanged_during_preparation", shadow.get("legacy_unchanged_during_benchmark"))
    add_check(
        checks,
        "legacy_default_runtime_unchanged_and_rollback_preserved",
        shadow.get("deployment_mode") == "SHADOW_ONLY"
        and shadow.get("explicit_opt_in_required") is True
        and shadow.get("candidate_activation") in ("NOT_PERFORMED", "SHADOW_RUN_ONLY")
        and shadow.get("default_activation") is False
        and shadow.get("safety_authority") is False
        and shadow.get("default_manifest_update") is False
        and shadow.get("production_runtime_selector_update") is False
        and shadow.get("legacy_model_overwrite") is False
        and shadow_unchanged is True
        and shadow.get("legacy_before") == shadow.get("legacy_after") == current_legacy,
        current_legacy,
    )

    boundary = contract["deployment_boundary"]
    boundary_false_keys = (
        "default_activation",
        "safety_authority",
        "legacy_model_overwrite",
        "model_manifest_default_update",
        "production_runtime_selector_update",
        "mi48_claim",
        "physical_validation_claim",
        "real_fall_detection_claim",
        "production_ready_claim",
        "competition_lock_claim",
    )
    add_check(
        checks,
        "shadow_only_deployment_boundary",
        boundary.get("deployment_mode") == "SHADOW_ONLY"
        and boundary.get("explicit_opt_in_required") is True
        and all(boundary.get(key) is False for key in boundary_false_keys),
        boundary,
    )

    checksum_errors = validate_checksum_registry(manifest_dir / "checksums.sha256")
    add_check(checks, "evidence_checksums", not checksum_errors, checksum_errors)
    path_violations: list[str] = []
    for path in sorted(manifest_dir.glob("*.json")):
        if ABSOLUTE_PATH_PATTERN.search(path.read_text(encoding="utf-8")):
            path_violations.append(path.name)
    add_check(checks, "no_absolute_path_persistence", not path_violations, path_violations)

    structural_pass = all(check["passed"] for check in checks)
    target_status = target_access.get("status")
    if not structural_pass:
        status = "FAIL"
    elif target_status == "BLOCKED_HARDWARE":
        status = "BLOCKED_HARDWARE"
    elif target_status == "TARGET_REACHED":
        status = "PASS"
    else:
        status = "PASS_WITH_LIMITATIONS"
    result = {
        "schema_version": "safenest.thermal.b6r_p3.validation_result.v1",
        "stage_id": "B6R-P3",
        "status": status,
        "checks": checks,
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks_failed": sum(1 for check in checks if not check["passed"]),
        "p2_artifact_sha256": expected_artifact.get("actual_sha256"),
        "p2_artifact_identity_status": expected_artifact.get("status"),
        "target_measurement_status": (
            "NOT_MEASURED_ON_TARGET" if status == "BLOCKED_HARDWARE" else "RECORDED_IN_TARGET_EVIDENCE"
        ),
        "locked_public_test_access_count": 0,
        "default_activation": False,
        "safety_authority": False,
        "next_stage_executed": False,
        "limitations": [
            "The replay fixture is public SDT DEVELOPMENT data and is not MI48 or physical sensor evidence.",
            "P0 preprocessing is inherited; P3 preprocessing latency measures canonical float32 ingress only, not PNG resize.",
            "No target metric is substituted with desktop measurements.",
            "HUMAN_FALL_PROXY is a posture proxy, not a real-fall or safety decision.",
        ],
    }
    write_json(manifest_dir / "validation_result.json", result)
    refresh_checksums(manifest_dir, repo_path(contract["p2_artifact"]["path"]))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
