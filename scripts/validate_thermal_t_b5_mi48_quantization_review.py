#!/usr/bin/env python3
"""Validate the compact, audit-only T-B5 real-MI48 quantization evidence.

This validator deliberately does not open field captures, canonical arrays,
checkpoints, or TFLite binaries.  It validates the frozen historical lineage,
the read-only O2.6 summary, the evidence boundary, and the explicit blocker
that prevents a same-weight corrective conversion until TRAIN payloads are
materialized by the owner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.thermal.t_b1_preprocessing import canonical_json, sha256_file


PHASE_ID = "T-B5"
EVIDENCE_REL = "datasets/thermal/manifests/T-B5_MI48_quantization_corrective_review"
REPORT_REL = "docs/20260818_Thermal_T-B5_MI48_INT8_Quantization_Corrective_Audit_01.md"
REQUIRED_JSON = (
    "access_status.json",
    "audit_summary.json",
    "historical_lineage.json",
    "real_mi48_evidence.json",
)
CHECKSUM_FILES = REQUIRED_JSON + ("validation_result.json",)
ALLOWED_ROOT_CAUSES = {
    "HISTORICAL_CALIBRATION_COVERAGE_DEFECT",
    "TRAIN_DOMAIN_RANGE_GAP",
    "CONVERTER_CONFIGURATION_DEFECT",
    "MULTIFACTOR",
    "INCONCLUSIVE",
}
ALLOWED_RESULTS = {
    "QUANTIZATION_CORRECTION_SUCCESSFUL",
    "QUANTIZATION_CORRECTION_PARTIAL",
    "TRAIN_DOMAIN_DOES_NOT_COVER_REAL_DEVICE",
    "QUANTIZATION_NOT_PRIMARY_CAUSE",
    "INCONCLUSIVE",
}


def is_true_unquantized_fp32_policy(policy: Mapping[str, Any]) -> bool:
    """Return whether converter metadata proves a non-quantized FP32 path.

    Float32 input/output tensors alone are deliberately insufficient: a
    dynamic-range conversion can retain float I/O while quantizing weights.
    """

    return (
        policy.get("input_dtype") == "float32"
        and policy.get("output_dtype") == "float32"
        and policy.get("optimizations") == []
        and policy.get("representative_dataset_attached") is False
        and policy.get("float16_enabled") is False
        and policy.get("dynamic_range_quantization") is False
        and policy.get("quantization_mode") == "NONE"
        and policy.get("builtin_only") is True
    )


def _error(errors: list[dict[str, str]], code: str, location: str, message: str) -> None:
    errors.append({"code": code, "location": location, "message": message})


def _walk_strings(value: Any, location: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, Mapping):
        for key in sorted(value):
            child = f"{location}.{key}" if location else str(key)
            yield from _walk_strings(value[key], child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{location}[{index}]")


def _portable(value: str) -> bool:
    lower = value.lower()
    return not (
        value.startswith(("/", "~/", "file://"))
        or "\\" in value
        or "/users/" in lower
        or "/private/" in lower
        or lower.startswith(("/volumes/", "/content/"))
    )


def _read_documents(evidence: Path, errors: list[dict[str, str]]) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for name in CHECKSUM_FILES:
        path = evidence / name
        if not path.is_file():
            _error(errors, "MISSING_EVIDENCE", name, "Required compact T-B5 MI48 evidence is missing.")
            continue
        try:
            documents[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _error(errors, "INVALID_JSON", name, str(exc))
    return documents


def _validate_checksums(evidence: Path, errors: list[dict[str, str]]) -> None:
    checksum_path = evidence / "checksums.sha256"
    if not checksum_path.is_file():
        _error(errors, "CHECKSUM_REGISTRY_MISSING", "checksums.sha256", "Compact evidence requires a checksum registry.")
        return
    entries: dict[str, str] = {}
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            _error(errors, "CHECKSUM_LINE_INVALID", f"checksums.sha256:{line_number}", "Expected '<sha256>  <filename>'.")
            continue
        entries[parts[1]] = parts[0]
    for name in REQUIRED_JSON:
        if name not in entries:
            _error(errors, "CHECKSUM_COVERAGE_MISSING", name, "Required evidence has no checksum coverage.")
        elif (evidence / name).is_file() and sha256_file(evidence / name) != entries[name]:
            _error(errors, "CHECKSUM_MISMATCH", name, "Evidence checksum does not match the current file.")


def _validate_portability(documents: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    for name, document in documents.items():
        for location, value in _walk_strings(document):
            if not _portable(value):
                _error(errors, "ABSOLUTE_PATH_LEAK", f"{name}:{location}", "Tracked evidence must use portable logical paths.")
            if "archive/" in value.lower() and "historical" not in value.lower() and "diagnostic" not in value.lower():
                _error(errors, "ARCHIVE_TREATED_AS_ACTIVE", f"{name}:{location}", "Archive paths cannot be active evidence sources.")


def _validate_lineage(lineage: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    artifact = lineage.get("artifact", {})
    expected_artifact = {
        "sha256": "fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be",
        "size_bytes": 318280,
        "input_dtype": "int8",
        "output_dtype": "int8",
        "input_scale": 0.31791284680366516,
        "input_zero_point": -125,
        "historical_locked": True,
        "modified": False,
    }
    for key, expected in expected_artifact.items():
        if artifact.get(key) != expected:
            _error(errors, "HISTORICAL_ARTIFACT_DRIFT", f"historical_lineage.json:artifact.{key}", f"Expected {expected!r}.")
    rep = lineage.get("representative_source", {})
    expected_rep = {
        "role": "TRAIN",
        "split": "TRAIN",
        "sample_count": 512,
        "policy_id": "T-B4_TRAIN_ONLY_STRATIFIED_CALIBRATION_512",
        "validation_samples_used": 0,
        "real_samples_used": 0,
        "locked_test_used": False,
    }
    for key, expected in expected_rep.items():
        actual = rep.get(key) if key in {"role", "split", "sample_count", "policy_id"} else rep.get("class_composition", {}).get(key)
        if actual != expected:
            _error(errors, "HISTORICAL_CALIBRATION_SCOPE_INVALID", f"historical_lineage.json:representative_source.{key}", f"Expected {expected!r}.")
    converter = lineage.get("converter", {})
    for key, expected in {
        "optimizations": ["DEFAULT"],
        "representative_dataset_attached": True,
        "supported_ops": ["TFLITE_BUILTINS_INT8"],
        "inference_input_type": "int8",
        "inference_output_type": "int8",
        "float16_enabled": False,
        "dynamic_range_only": False,
        "strict_full_int8": True,
    }.items():
        if converter.get(key) != expected:
            _error(errors, "CONVERTER_LINEAGE_INVALID", f"historical_lineage.json:converter.{key}", f"Expected {expected!r}.")
    p1 = lineage.get("p1_contract", {})
    if p1.get("profile") != "P1_TRAIN_FITTED_GLOBAL_ZSCORE" or p1.get("mean") != 22.769290618485442 or p1.get("std") != 2.8684523405441222:
        _error(errors, "P1_CONTRACT_DRIFT", "historical_lineage.json:p1_contract", "Frozen P1 mean/std/profile changed.")
    pixel = lineage.get("pixel_level_distribution", {})
    for key in ("historical_calibration_p1", "train_p1", "historical_calibration_celsius", "train_celsius"):
        if pixel.get(key) != "NOT_MEASURABLE_WITHOUT_TRAIN_TENSOR_PAYLOAD":
            _error(errors, "UNSUPPORTED_TRAIN_DISTRIBUTION", f"historical_lineage.json:pixel_level_distribution.{key}", "Pixel-level TRAIN statistics must not be fabricated from compact means.")


def _validate_real(real: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    source = real.get("source", {})
    for key, expected in {"role": "REAL_EVAL_DEVELOPMENT", "used_for_calibration": False, "used_for_selection": False, "locked_test": False, "ground_truth_available": False}.items():
        if source.get(key) != expected:
            _error(errors, "REAL_SCOPE_INVALID", f"real_mi48_evidence.json:source.{key}", f"Expected {expected!r}.")
    inventory = real.get("capture_inventory", {})
    for key, expected in {"npz_files_listed": 1979, "readable_npz_files": 1964, "corrupt_npz_files": 15, "readable_frames": 23788, "selected_frame_count": 154, "raw_dtype": "uint16"}.items():
        if inventory.get(key) != expected:
            _error(errors, "REAL_INVENTORY_INVALID", f"real_mi48_evidence.json:capture_inventory.{key}", f"Expected {expected!r}.")
    dist = real.get("p1_distribution_over_selected_pixels", {})
    for key, expected in {"min": -30.441255510601113, "p1": -8.791950370596547, "p5": -5.061715829565169, "median": -0.8782752228010011, "p95": 3.1308553586813264, "p99": 5.327161677232518, "max": 13.55459487053539, "fraction_below_historical_int8_lower_range": 0.4816636992040218}.items():
        if dist.get(key) != expected:
            _error(errors, "REAL_DISTRIBUTION_INVALID", f"real_mi48_evidence.json:p1_distribution_over_selected_pixels.{key}", f"Expected {expected!r}.")
    hist = real.get("historical_float_int8_equivalence", {})
    for key, expected in {"top1_agree": 139, "top1_disagree": 15, "top1_agreement": 0.9025974025974026, "low_side_saturation_median": 0.4344758064516129, "low_side_saturation_p95": 0.8314516129032258, "high_side_saturation_max": 0.0}.items():
        if hist.get(key) != expected:
            _error(errors, "REAL_EQUIVALENCE_INVALID", f"real_mi48_evidence.json:historical_float_int8_equivalence.{key}", f"Expected {expected!r}.")
    if hist.get("saturation_relationship") != "STRONG_ASSOCIATION_OBSERVED":
        _error(errors, "REAL_ASSOCIATION_MISSING", "real_mi48_evidence.json:historical_float_int8_equivalence.saturation_relationship", "The frozen O2.6 association must be retained.")


def validate_evidence(*, repo_root: Path = ROOT, evidence_dir: Path | None = None, check_checksums: bool = True) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    evidence = Path(evidence_dir or repo / EVIDENCE_REL).resolve()
    errors: list[dict[str, str]] = []
    documents = _read_documents(evidence, errors)
    if all(name in documents for name in REQUIRED_JSON):
        audit = documents["audit_summary.json"]
        if audit.get("phase") != PHASE_ID or audit.get("review_id") != "THERMAL_T_B5_REAL_MI48_INT8_QUANTIZATION_CORRECTIVE_001":
            _error(errors, "AUDIT_IDENTITY_INVALID", "audit_summary.json", "T-B5 MI48 review identity is invalid.")
        if audit.get("status") != "PASS_WITH_LIMITATIONS" or audit.get("overall_gate") != "THERMAL_T_B5_REAL_MI48_QUANTIZATION_CORRECTIVE=PASS_WITH_LIMITATIONS":
            _error(errors, "AUDIT_GATE_INVALID", "audit_summary.json", "Audit-only gate must remain PASS_WITH_LIMITATIONS.")
        if audit.get("root_cause_classification") not in ALLOWED_ROOT_CAUSES or audit.get("corrective_result_classification") not in ALLOWED_RESULTS:
            _error(errors, "CLASSIFICATION_INVALID", "audit_summary.json", "Root-cause/result classification is outside the T-B5 contract.")
        if audit.get("new_int8_candidate_created") is not False or audit.get("new_int8_candidate_eligible_for_integration_review") is not False:
            _error(errors, "UNJUSTIFIED_CANDIDATE", "audit_summary.json", "No corrective candidate may be claimed without TRAIN tensors and a frozen checkpoint.")
        if any(audit.get(key) is not False for key in ("historical_artifact_modified", "production_model_changed", "production_activation", "t_c_validated", "device_domain_accuracy_validated", "temporal_fall_validated", "ground_truth_available", "real_mi48_used_for_calibration", "locked_test_used", "integration_repository_modified", "pi_snapshot_modified", "real_field_data_committed")):
            _error(errors, "SCOPE_OVERCLAIM", "audit_summary.json", "Audit-only review contains a forbidden positive claim.")
        _validate_lineage(documents["historical_lineage.json"], errors)
        _validate_real(documents["real_mi48_evidence.json"], errors)
        access = documents["access_status.json"]
        if access.get("external_storage", {}).get("status") != "NOT_MOUNTED" or access.get("candidate_generation", {}).get("performed") is not False:
            _error(errors, "ACCESS_BOUNDARY_INVALID", "access_status.json", "External storage/candidate-generation boundary changed.")
        if access.get("candidate_generation", {}).get("reason", "").find("without the frozen Float checkpoint") < 0:
            _error(errors, "BLOCKER_NOT_EXPLAINED", "access_status.json:candidate_generation.reason", "Missing checkpoint blocker must be explicit.")
    _validate_portability(documents, errors)
    if check_checksums:
        _validate_checksums(evidence, errors)
    report = repo / REPORT_REL
    if not report.is_file():
        _error(errors, "REPORT_MISSING", REPORT_REL, "Human-readable T-B5 MI48 audit report is required.")
    errors.sort(key=lambda item: (item["code"], item["location"], item["message"]))
    result = {
        "phase": PHASE_ID,
        "review_id": "THERMAL_T_B5_REAL_MI48_INT8_QUANTIZATION_CORRECTIVE_001",
        "schema_version": "1.0",
        "evidence_validation": "PASS" if not errors else "FAIL",
        "overall_outcome": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "new_candidate_created": False,
        "t_c_authorized": False,
        "error_count": len(errors),
        "errors": errors,
    }
    return result


def _write_result(evidence: Path, result: Mapping[str, Any]) -> None:
    (evidence / "validation_result.json").write_text(canonical_json(result), encoding="utf-8")
    rows = []
    for path in sorted(evidence.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "checksums.sha256" and not path.name.startswith("._"):
            rows.append(f"{sha256_file(path)}  {path.name}")
    (evidence / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SafeNest Thermal T-B5 real-MI48 quantization corrective evidence")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", default=str(ROOT / EVIDENCE_REL))
    parser.add_argument("--skip-checksums", action="store_true")
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    evidence = Path(args.evidence_dir)
    result = validate_evidence(repo_root=Path(args.repo_root), evidence_dir=evidence, check_checksums=not args.skip_checksums)
    if args.write_result:
        _write_result(evidence, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["evidence_validation"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
