#!/usr/bin/env python3
"""Validate B6R-P4 evidence and its non-gating software-only boundary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.evaluate_thermal_b6r_p4_public_sdt_robustness import (
    DEFAULT_CONTRACT,
    ROOT,
    audit_model_identity,
    audit_protected_files,
    read_json,
    refresh_checksums,
    repo_path,
    sha256_file,
    write_json,
)


ABSOLUTE_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:[\\/]|file://|/Users/|/home/|/root/|/tmp/|\\\\)")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def checksum_errors(path: Path) -> list[str]:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args(argv)
    contract = read_json(args.contract)
    manifest_dir = repo_path(contract["manifest_dir"])
    checks: list[dict[str, Any]] = []

    snapshot = read_json(manifest_dir / "contract_snapshot.json")
    add_check(checks, "contract_snapshot", snapshot == contract, {"matches": snapshot == contract})

    source = read_json(manifest_dir / "source_identity_audit.json")
    source_ok = (
        source.get("status") == "PASS"
        and source.get("archive_count_expected") == source.get("archive_count_found") == 6
        and len(source.get("archives", [])) == 6
        and all(record.get("matches_registry") is True for record in source.get("archives", []))
        and all(record.get("matches_registry") is True for record in source.get("development_payload_files", []))
        and source.get("source_root_persisted") is False
        and source.get("source_mutation_performed") is False
    )
    add_check(checks, "public_source_and_development_lineage", source_ok, {
        "status": source.get("status"), "archives": len(source.get("archives", [])),
        "development_files": len(source.get("development_payload_files", [])),
    })

    stored_model = read_json(manifest_dir / "model_identity_audit.json")
    live_model = audit_model_identity(contract)
    model_ok = stored_model == live_model and live_model.get("status") == "PASS"
    add_check(checks, "p1_p2_exact_model_identity", model_ok, live_model)

    clean = read_json(manifest_dir / "clean_baseline_metrics.json")
    clean_ok = (
        clean.get("role") == "DEVELOPMENT"
        and clean.get("sample_count") == 8000
        and clean.get("metric_interpretation") == "DEVELOPMENT_DIAGNOSTIC_NOT_INDEPENDENT_TEST_PERFORMANCE"
        and clean.get("numerical_integrity", {}).get("status") == "PASS"
    )
    add_check(checks, "clean_development_baseline", clean_ok, {
        "sample_count": clean.get("sample_count"), "accuracy": clean.get("accuracy"), "macro_f1": clean.get("macro_f1")
    })

    registry = read_json(manifest_dir / "perturbation_registry.json")
    metrics = read_json(manifest_dir / "perturbation_metrics.json")
    perturbation_ok = (
        registry.get("sample_count") == 8000
        and len(registry.get("sample_ids", [])) == 8000
        and len(set(registry.get("sample_ids", []))) == 8000
        and len(registry.get("conditions", [])) == len(contract["perturbations"]) == 16
        and metrics.get("condition_count") == 16
        and metrics.get("all_normal_outputs_numerically_valid") is True
        and metrics.get("metrics_regeneration_byte_equal") is True
        and all(item.get("sample_count") == 8000 for item in metrics.get("conditions", []))
    )
    add_check(checks, "deterministic_full_development_perturbation_suite", perturbation_ok, {
        "sample_count": registry.get("sample_count"), "condition_count": metrics.get("condition_count"),
        "numerical": metrics.get("all_normal_outputs_numerically_valid"),
    })

    parity = read_json(manifest_dir / "parity_under_stress.json")
    parity_ok = (
        parity.get("status") == "PASS"
        and parity.get("fixture_count") == 48
        and parity.get("condition_count") == 17
        and parity.get("comparison_count") == 816
        and parity.get("probability_max_abs_difference", 1.0) <= contract["parity"]["probabilities_max_abs"]
        and parity.get("probability_mean_abs_difference", 1.0) <= contract["parity"]["probabilities_mean_abs"]
        and parity.get("mismatch_count") == 0
    )
    add_check(checks, "numpy_tflite_clean_and_stress_parity", parity_ok, {
        "max_abs": parity.get("probability_max_abs_difference"),
        "mean_abs": parity.get("probability_mean_abs_difference"),
        "mismatch_count": parity.get("mismatch_count"),
    })

    invalid = read_json(manifest_dir / "invalid_input_audit.json")
    case_ids = {record.get("case_id") for record in invalid.get("cases", [])}
    invalid_ok = (
        invalid.get("status") == "PASS"
        and invalid.get("case_count") == len(contract["invalid_input_cases"]) == 12
        and case_ids == set(contract["invalid_input_cases"])
        and invalid.get("production_validator_modified") is False
        and all(
            record.get("model_status") == "NOT_INVOKED"
            for record in invalid.get("cases", [])
            if record.get("case_id") in {"NAN", "+INF", "-INF", "WRONG_SHAPE", "EMPTY_ARRAY", "WRONG_RANK", "OUT_OF_RANGE_NEGATIVE", "OUT_OF_RANGE_ABOVE_ONE"}
        )
    )
    add_check(checks, "invalid_input_failure_modes", invalid_ok, {
        "case_count": invalid.get("case_count"), "accepted": invalid.get("accepted_count"), "rejected": invalid.get("rejected_count")
    })

    determinism = read_json(manifest_dir / "determinism_audit.json")
    determinism_ok = determinism.get("status") == "PASS" and all(determinism.get("comparisons", {}).values())
    add_check(checks, "software_determinism", determinism_ok, determinism.get("comparisons"))

    locked = read_json(manifest_dir / "locked_test_audit.json")
    locked_ok = (
        locked.get("status") == "PASS" and locked.get("path_configured") is False
        and locked.get("array_open_count") == 0 and locked.get("sample_read_count") == 0
        and locked.get("metrics_computed") is False and locked.get("selection_or_tuning_use") is False
    )
    add_check(checks, "locked_public_test_access_zero", locked_ok, locked)

    sensor = read_json(manifest_dir / "real_sensor_access_audit.json")
    sensor_ok = (
        sensor.get("status") == "PASS" and sensor.get("real_sensor_data_access_count") == 0
        and sensor.get("raspberry_pi_connection_attempt_count") == 0
        and sensor.get("raspberry_pi_scope") == "OUT_OF_SCOPE"
    )
    add_check(checks, "real_sensor_and_raspberry_pi_access_zero", sensor_ok, sensor)

    stored_protected = read_json(manifest_dir / "legacy_runtime_immutability_audit.json")
    live_protected = audit_protected_files(contract)
    protected_ok = stored_protected == live_protected and live_protected.get("status") == "PASS"
    add_check(checks, "model_legacy_default_runtime_immutability", protected_ok, live_protected)

    boundary = contract["claim_boundary"]
    boundary_ok = (
        contract["gate_policy"]["non_gating"] is True
        and contract["gate_policy"]["maximum_success_status"] == "PASS_WITH_LIMITATIONS"
        and all(boundary[key] is False for key in (
            "mi48_validated", "thermal90_validated", "physical_validation", "real_fall_validation",
            "raspberry_pi_validated", "safety_authority", "production_ready", "default_activation",
        ))
        and all(boundary[key] is True for key in (
            "public_sdt_only", "software_only", "offline_only", "synthetic_stress_test_only",
            "development_only", "fp32_tflite", "non_gating", "shadow_only",
        ))
    )
    add_check(checks, "non_gating_claim_boundary", boundary_ok, boundary)

    checksum_issue_list = checksum_errors(manifest_dir / "checksums.sha256")
    add_check(checks, "evidence_checksums", not checksum_issue_list, checksum_issue_list)
    path_violations = [
        path.name for path in sorted(manifest_dir.glob("*.json"))
        if ABSOLUTE_PATH_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    add_check(checks, "no_machine_absolute_paths", not path_violations, path_violations)

    all_passed = all(check["passed"] for check in checks)
    result = {
        "schema_version": "safenest.thermal.b6r_p4.validation_result.v1",
        "stage_id": "B6R-P4",
        "status": "PASS_WITH_LIMITATIONS" if all_passed else "FAIL",
        "status_qualifier": "PUBLIC_DATA_SOFTWARE_ONLY_NON_GATING",
        "checks": checks,
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_failed": sum(not check["passed"] for check in checks),
        "development_sample_count": 8000,
        "locked_public_test_access_count": 0,
        "real_sensor_access_count": 0,
        "raspberry_pi_connection_attempt_count": 0,
        "p3_status": "BLOCKED_HARDWARE_UNCHANGED",
        "next_stage_executed": False,
        "limitations": [
            "PUBLIC_SDT DEVELOPMENT diagnostics are not independent test performance.",
            "Synthetic perturbations are software stress tests, not sensor or physical robustness evidence.",
            "HUMAN_FALL_PROXY is a posture proxy, not real-fall or safety validation.",
            "B6R-P3 remains BLOCKED_HARDWARE and P4 does not provide Raspberry Pi evidence.",
        ],
    }
    write_json(manifest_dir / "validation_result.json", result)
    refresh_checksums(manifest_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
