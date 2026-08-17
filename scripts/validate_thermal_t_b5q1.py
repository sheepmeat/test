#!/usr/bin/env python3
"""Validate compact T-B5Q1 TRAIN-domain calibration evidence.

The validator never opens the SSD payload, canonical arrays, checkpoints,
field NPZs, or TFLite binaries.  It validates their recorded identities and
the fail-closed TRAIN_DOMAIN_RANGE_GAP decision.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.thermal.t_b1_preprocessing import canonical_json, sha256_file


PHASE_ID = "T-B5Q1"
REVIEW_ID = "THERMAL_T_B5Q1_TRAIN_DOMAIN_INT8_CALIBRATION_CORRECTIVE_001"
EVIDENCE_REL = "datasets/thermal/manifests/T-B5Q1_train_calibration_corrective"
REPORT_REL = "docs/20260818_Thermal_T-B5Q1_TRAIN_Calibration_Corrective_Experiment_01.md"
REQUIRED_JSON = (
    "decision.json",
    "distribution_comparison.json",
    "execution_environment.json",
    "historical_calibration.json",
    "source_identity.json",
)
CHECKSUM_FILES = REQUIRED_JSON + ("validation_result.json",)


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
    for name in REQUIRED_JSON:
        path = evidence / name
        if not path.is_file():
            _error(errors, "MISSING_EVIDENCE", name, "Required compact T-B5Q1 evidence is missing.")
            continue
        try:
            documents[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _error(errors, "INVALID_JSON", name, str(exc))
    return documents


def _validate_checksums(evidence: Path, errors: list[dict[str, str]]) -> None:
    checksum_path = evidence / "checksums.sha256"
    if not checksum_path.is_file():
        _error(errors, "CHECKSUM_REGISTRY_MISSING", "checksums.sha256", "Checksum registry is required.")
        return
    entries: dict[str, str] = {}
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            _error(errors, "CHECKSUM_LINE_INVALID", f"checksums.sha256:{line_number}", "Expected '<sha256>  <filename>'.")
            continue
        entries[parts[1]] = parts[0]
    for name in CHECKSUM_FILES:
        if name not in entries:
            _error(errors, "CHECKSUM_COVERAGE_MISSING", name, "Required evidence has no checksum coverage.")
        elif (evidence / name).is_file() and sha256_file(evidence / name) != entries[name]:
            _error(errors, "CHECKSUM_MISMATCH", name, "Evidence checksum does not match the current file.")


def _close(actual: Any, expected: float, *, tolerance: float = 1e-12) -> bool:
    try:
        return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def _validate_source(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("phase") != PHASE_ID or doc.get("review_id") != REVIEW_ID:
        _error(errors, "SOURCE_IDENTITY_INVALID", "source_identity.json", "T-B5Q1 source identity is invalid.")
    storage = doc.get("storage", {})
    for key, expected in {"volume_name": "SafeNestssd", "filesystem": "exFAT", "transport": "USB", "used_read_only": True, "ssd_modified": False, "raw_payload_committed": False}.items():
        if storage.get(key) != expected:
            _error(errors, "SSD_SCOPE_INVALID", f"source_identity.json:storage.{key}", f"Expected {expected!r}.")
    train = doc.get("canonical_train", {})
    expected_train = {
        "role": "TRAIN",
        "split": "TRAIN",
        "source_domain": "SYNTHETIC",
        "sha256": "749c847fc9ab50ea5eee8827f0d47b5ebaa48165732a382c59f8b96c565b9d93",
        "size_bytes": 634880128,
        "shape": [32000, 62, 80],
        "dtype": "float32_little_endian",
        "sample_count": 32000,
        "provenance_sha256": "b4ec8228e35703bac3319ca218a69fdef43013ea44b23376da4929b274d24888",
        "conversion_status": "FINALIZED",
        "full_hash_verified": True,
    }
    for key, expected in expected_train.items():
        if train.get(key) != expected:
            _error(errors, "TRAIN_IDENTITY_INVALID", f"source_identity.json:canonical_train.{key}", f"Expected {expected!r}.")
    checkpoint = doc.get("frozen_float_source", {})
    for key, expected in {
        "checkpoint_sha256": "7aba32fe8d0e241546429bdc3e8cd059b10d4d8f548e9e12c4085abeba308a75",
        "checkpoint_size_bytes": 3777416,
        "architecture_fingerprint": "937fceb88900a779d67a8e407cebc3362cc21346721f92cea5ae8de1413aba2a",
        "parameter_count": 312131,
        "seed": 20260813,
        "selected_profile": "P1_TRAIN_FITTED_GLOBAL_ZSCORE",
        "same_selected_weights_proven": True,
        "checkpoint_loaded_into_frozen_architecture": True,
        "loaded_weight_tensor_sha256": "19eec68045e801acd7d33d0ad10776b8cb0eb1f8514a268b9cd4bb3159ada170",
    }.items():
        if checkpoint.get(key) != expected:
            _error(errors, "FLOAT_SOURCE_INVALID", f"source_identity.json:frozen_float_source.{key}", f"Expected {expected!r}.")
    p1 = doc.get("p1_contract", {})
    for key, expected in {"profile_id": "P1_TRAIN_FITTED_GLOBAL_ZSCORE", "mean": 22.769290618485442, "std": 2.8684523405441222, "statistics_checksum": "10b5da044ef33f26715544c3d4bf56e9d999d6c65139e931f6997583b3f5b816", "fit_role": "TRAIN", "refit": False}.items():
        value = p1.get(key)
        valid = _close(value, expected) if isinstance(expected, float) else value == expected
        if not valid:
            _error(errors, "P1_IDENTITY_INVALID", f"source_identity.json:p1_contract.{key}", f"Expected {expected!r}.")
    tflite = doc.get("known_tflite_lineage", {})
    for key, expected in {"float_tflite_sha256": "fbe891520f07e0534b1a7074dc819d8ed44bca58b27e35c78916c3ddae73a779", "historical_full_int8_sha256": "fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be", "historical_full_int8_modified": False}.items():
        if tflite.get(key) != expected:
            _error(errors, "HISTORICAL_ARTIFACT_DRIFT", f"source_identity.json:known_tflite_lineage.{key}", f"Expected {expected!r}.")


def _validate_historical(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("phase") != PHASE_ID or doc.get("source_role") != "TRAIN":
        _error(errors, "HISTORICAL_SCOPE_INVALID", "historical_calibration.json", "Historical calibration must be TRAIN-only.")
    selector = doc.get("historical_selector", {})
    for key, expected in {"policy_id": "T-B4_TRAIN_ONLY_STRATIFIED_CALIBRATION_512", "policy_checksum": "c5ce8a54898a19d0b9dad156aee89feeafbf85f79a64a6e424d7912b24a95179", "manifest_checksum": "51bbced6b40ab14d547e3c80afd99b92a24c016c1853e66c634b69d1dc4b30a4", "sample_count": 512, "selection_reproduced": True, "validation_samples_used": 0, "real_samples_used": 0, "locked_test_used": False}.items():
        if selector.get(key) != expected:
            _error(errors, "HISTORICAL_SELECTOR_INVALID", f"historical_calibration.json:historical_selector.{key}", f"Expected {expected!r}.")
    converter = doc.get("converter_policy", {})
    for key, expected in {"optimizations": ["DEFAULT"], "representative_dataset_attached": True, "supported_ops": ["TFLITE_BUILTINS_INT8"], "inference_input_type": "int8", "inference_output_type": "int8", "float16_enabled": False, "dynamic_range_quantization": False, "quantization_mode": "FULL_INT8", "strict_full_int8": True}.items():
        if converter.get(key) != expected:
            _error(errors, "HISTORICAL_CONVERTER_INVALID", f"historical_calibration.json:converter_policy.{key}", f"Expected {expected!r}.")
    quant = doc.get("historical_input_quantizer", {})
    for key, expected in {"scale": 0.31791284680366516, "zero_point": -125, "lower_representable_p1": -0.9537385404109955}.items():
        valid = _close(quant.get(key), expected) if isinstance(expected, float) else quant.get(key) == expected
        if not valid:
            _error(errors, "HISTORICAL_QUANTIZER_INVALID", f"historical_calibration.json:historical_input_quantizer.{key}", f"Expected {expected!r}.")
    dist = doc.get("pixel_distribution_p1", {})
    for key, expected in {"min": -0.827001036248923, "fraction_below_historical_lower_range": 0.0, "pixels_below_historical_lower_range": 0}.items():
        valid = _close(dist.get(key), expected) if isinstance(expected, float) else dist.get(key) == expected
        if not valid:
            _error(errors, "HISTORICAL_DISTRIBUTION_INVALID", f"historical_calibration.json:pixel_distribution_p1.{key}", f"Expected {expected!r}.")


def _validate_comparison(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("phase") != PHASE_ID:
        _error(errors, "COMPARISON_IDENTITY_INVALID", "distribution_comparison.json", "Distribution comparison phase is invalid.")
    p1 = doc.get("p1_contract", {})
    if p1.get("profile_id") != "P1_TRAIN_FITTED_GLOBAL_ZSCORE" or p1.get("refit") is not False:
        _error(errors, "P1_REFIT_OR_PROFILE_INVALID", "distribution_comparison.json:p1_contract", "P1 must remain frozen and TRAIN-fitted.")
    ranges = doc.get("historical_int8_range", {})
    if not _close(ranges.get("lower_representable_p1"), -0.9537385404109955):
        _error(errors, "RANGE_CONTRACT_INVALID", "distribution_comparison.json:historical_int8_range", "Historical lower representable range changed.")
    distributions = doc.get("distributions_p1", {})
    expected = {
        "historical_512": {"min": -0.827001036248923, "p1": -0.3412038684685841},
        "full_train": {"min": -1.3676012270382902, "p1": -0.34097180441667607},
        "real_mi48_o2_6": {"min": -30.441251254985268, "p1": -8.791943987172775},
    }
    for name, fields in expected.items():
        for key, value in fields.items():
            if not _close(distributions.get(name, {}).get(key), value):
                _error(errors, "DISTRIBUTION_VALUE_INVALID", f"distribution_comparison.json:distributions_p1.{name}.{key}", f"Expected {value!r}.")
    metrics = doc.get("range_metrics", {})
    for key, expected_value in {"historical_512_pixels_below_historical_lower": 0.0, "full_train_pixels_below_historical_lower": 2.0161290322580645e-07, "full_train_pixels_below_historical_lower_count": 32, "real_mi48_pixels_below_historical_lower": 0.4816636992040218, "real_mi48_pixels_below_full_train_min": 0.405579702555509, "real_mi48_pixels_outside_full_train_range": 0.405579702555509, "real_mi48_pixels_above_full_train_max": 0.0}.items():
        valid = _close(metrics.get(key), expected_value) if isinstance(expected_value, float) else metrics.get(key) == expected_value
        if not valid:
            _error(errors, "RANGE_METRIC_INVALID", f"distribution_comparison.json:range_metrics.{key}", f"Expected {expected_value!r}.")
    real = doc.get("real_evaluation_boundary", {})
    for key, expected_value in {"frame_count": 154, "same_frozen_o2_6_identities": True, "used_for_calibration": False, "used_for_selector_design": False, "ground_truth_available": False}.items():
        if real.get(key) != expected_value:
            _error(errors, "REAL_BOUNDARY_INVALID", f"distribution_comparison.json:real_evaluation_boundary.{key}", f"Expected {expected_value!r}.")
    eq = doc.get("historical_o2_6_equivalence", {})
    for key, expected_value in {"top1_agreement": 0.9025974025974026, "top1_agree": 139, "top1_disagree": 15, "low_side_saturation_median": 0.4344758064516129, "low_side_saturation_p95": 0.8314516129032258, "high_side_saturation_max": 0.0, "accuracy_claim": False}.items():
        valid = _close(eq.get(key), expected_value) if isinstance(expected_value, float) else eq.get(key) == expected_value
        if not valid:
            _error(errors, "HISTORICAL_EQUIVALENCE_INVALID", f"distribution_comparison.json:historical_o2_6_equivalence.{key}", f"Expected {expected_value!r}.")
    canonical = doc.get("canonical_historical_equivalence", {})
    for key, expected_value in {
        "source_logical_path": "datasets/thermal/manifests/T-B5_robustness_latency_candidate_lock/parity_summary.json",
        "source_sha256": "18246ee6f34a64bfaefdacf5ee6429853dcf80887da476ebaa984acf12bc5261",
        "role": "VALIDATION",
        "sample_count": 512,
        "locked_test_used": False,
        "real_used_for_selection": False,
        "new_candidate_compared": False,
        "ranking_agreement": "NOT_RECORDED_BY_INHERITED_T_B5_SCHEMA",
        "evidence_status": "INHERITED_IMMUTABLE_T_B5_EVIDENCE_NO_NEW_CANDIDATE",
    }.items():
        if canonical.get(key) != expected_value:
            _error(errors, "CANONICAL_EQUIVALENCE_SCOPE_INVALID", f"distribution_comparison.json:canonical_historical_equivalence.{key}", f"Expected {expected_value!r}.")
    expected_pairs = {
        "FLOAT_KERAS__TFLITE_FP32": {"argmax_agreement": 1.0, "disagreement_count": 0, "probability_mae": 5.011796603787694e-09, "probability_max_absolute_error": 7.152557373046875e-07},
        "TFLITE_FP32__FULL_INT8": {"argmax_agreement": 0.99609375, "disagreement_count": 2, "probability_mae": 0.0033456996413038435, "probability_max_absolute_error": 0.5893600583076477},
        "FLOAT_KERAS__FULL_INT8": {"argmax_agreement": 0.99609375, "disagreement_count": 2, "probability_mae": 0.0033457006260881245, "probability_max_absolute_error": 0.5893602967262268},
    }
    for pair, fields in expected_pairs.items():
        actual = canonical.get("pairs", {}).get(pair, {})
        for key, expected_value in fields.items():
            valid = _close(actual.get(key), expected_value) if isinstance(expected_value, float) else actual.get(key) == expected_value
            if not valid:
                _error(errors, "CANONICAL_EQUIVALENCE_INVALID", f"distribution_comparison.json:canonical_historical_equivalence.pairs.{pair}.{key}", f"Expected {expected_value!r}.")
    expected_matrices = {
        "FLOAT_KERAS__TFLITE_FP32": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
        "TFLITE_FP32__FULL_INT8": [[0, 0, 0], [0, 0, 0], [0, 2, -2]],
        "FLOAT_KERAS__FULL_INT8": [[0, 0, 0], [0, 0, 0], [0, 2, -2]],
    }
    for pair, expected_matrix in expected_matrices.items():
        if canonical.get("pairs", {}).get(pair, {}).get("confusion_matrix_difference") != expected_matrix:
            _error(errors, "CANONICAL_TRANSITION_INVALID", f"distribution_comparison.json:canonical_historical_equivalence.pairs.{pair}.confusion_matrix_difference", "Inherited T-B5 transition matrix changed.")
    if doc.get("interpretation", {}).get("root_cause_supported") != "TRAIN_DOMAIN_RANGE_GAP" or doc.get("interpretation", {}).get("candidate_generation_authorized") is not False:
        _error(errors, "ROOT_CAUSE_INVALID", "distribution_comparison.json:interpretation", "TRAIN_DOMAIN_RANGE_GAP must gate candidate generation.")


def _validate_decision(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("phase") != PHASE_ID or doc.get("status") != "FINALIZED_WITH_LIMITATIONS" or doc.get("root_cause") != "TRAIN_DOMAIN_RANGE_GAP":
        _error(errors, "DECISION_INVALID", "decision.json", "Decision must be finalized as TRAIN_DOMAIN_RANGE_GAP.")
    candidate = doc.get("candidate_generation", {})
    for key, expected in {"authorized": False, "created": False, "canonical_equivalence_run": False, "o2_6_one_shot_run": False}.items():
        if candidate.get(key) != expected:
            _error(errors, "CANDIDATE_SCOPE_INVALID", f"decision.json:candidate_generation.{key}", f"Expected {expected!r}.")
    frozen = doc.get("frozen_contracts", {})
    for key in ("float_weights_changed", "p1_changed", "geometry_changed", "class_mapping_changed", "thresholds_changed", "training_performed", "real_mi48_used_for_calibration", "validation_used_for_calibration", "locked_test_used", "field_evidence_used_for_tuning"):
        if frozen.get(key) is not False:
            _error(errors, "FROZEN_SCOPE_INVALID", f"decision.json:frozen_contracts.{key}", "Frozen contract or field boundary was changed.")
    if doc.get("historical_preservation", {}).get("historical_full_int8_modified") is not False:
        _error(errors, "HISTORICAL_ARTIFACT_MODIFIED", "decision.json:historical_preservation", "Historical T-B5 FULL_INT8 must remain untouched.")
    gates = doc.get("gates", {})
    for key, expected in {"thermal_t_b5q1_train_calibration_corrective": "PASS_WITH_LIMITATIONS", "new_int8_candidate_eligible_for_integration_review": False, "pi_o3_authorized": False, "production_activation": False, "next_phase_started": False}.items():
        if gates.get(key) != expected:
            _error(errors, "GATE_INVALID", f"decision.json:gates.{key}", f"Expected {expected!r}.")


def validate_evidence(*, repo_root: Path = ROOT, evidence_dir: Path | None = None, check_checksums: bool = True) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    evidence = Path(evidence_dir or repo / EVIDENCE_REL).resolve()
    errors: list[dict[str, str]] = []
    documents = _read_documents(evidence, errors)
    if all(name in documents for name in REQUIRED_JSON):
        _validate_source(documents["source_identity.json"], errors)
        _validate_historical(documents["historical_calibration.json"], errors)
        _validate_comparison(documents["distribution_comparison.json"], errors)
        _validate_decision(documents["decision.json"], errors)
        env = documents["execution_environment.json"]
        if env.get("phase") != PHASE_ID or env.get("ssd", {}).get("used_read_only") is not True or env.get("ssd", {}).get("modified") is not False or env.get("analysis", {}).get("tflite_conversion_performed") is not False:
            _error(errors, "EXECUTION_SCOPE_INVALID", "execution_environment.json", "SSD and no-conversion boundaries are invalid.")
    for name, document in documents.items():
        for location, value in _walk_strings(document):
            if not _portable(value):
                _error(errors, "ABSOLUTE_PATH_LEAK", f"{name}:{location}", "Tracked evidence must use portable logical paths.")
            if "archive/" in value.lower() and "historical" not in value.lower() and "diagnostic" not in value.lower():
                _error(errors, "ARCHIVE_TREATED_AS_ACTIVE", f"{name}:{location}", "Archive paths cannot be active evidence sources.")
    if check_checksums:
        _validate_checksums(evidence, errors)
    report = repo / REPORT_REL
    if not report.is_file():
        _error(errors, "REPORT_MISSING", REPORT_REL, "T-B5Q1 report is required.")
    errors.sort(key=lambda item: (item["code"], item["location"], item["message"]))
    return {
        "phase": PHASE_ID,
        "review_id": REVIEW_ID,
        "schema_version": "1.0",
        "evidence_validation": "PASS" if not errors else "FAIL",
        "overall_outcome": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "root_cause": "TRAIN_DOMAIN_RANGE_GAP",
        "candidate_created": False,
        "new_int8_candidate_eligible_for_integration_review": False,
        "t_c_authorized": False,
        "error_count": len(errors),
        "errors": errors,
    }


def _write_result(evidence: Path, result: Mapping[str, Any]) -> None:
    (evidence / "validation_result.json").write_text(canonical_json(result), encoding="utf-8")
    rows = []
    for path in sorted(evidence.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "checksums.sha256" and not path.name.startswith("._"):
            rows.append(f"{sha256_file(path)}  {path.name}")
    (evidence / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SafeNest Thermal T-B5Q1 TRAIN-domain calibration evidence")
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
