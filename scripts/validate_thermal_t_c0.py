#!/usr/bin/env python3
"""Validate the compact, offline T-C0 MI48 acquisition readiness contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
PHASE = "T-C0"
EVIDENCE_REL = "datasets/thermal/manifests/T-C0_mi48_device_domain_acquisition"
REPORT_REL = "docs/20260818_Thermal_MI48_Device_Domain_Acquisition_and_Evaluation_Contract_01.md"
REQUIRED_JSON = (
    "contract.json",
    "scenario_matrix.json",
    "retraining_gate.json",
    "legacy_snapshot_dry_run.json",
    "capture_contract.schema.json",
    "session_manifest.schema.json",
    "label_record.schema.json",
    "sample_record.schema.json",
    "dataset_build_summary.schema.json",
)
CHECKSUM_FILES = REQUIRED_JSON + ("readiness_result.json",)
REQUIRED_TOOLS = (
    "scripts/validate_thermal_real_capture.py",
    "scripts/thermal_mi48_device_domain.py",
    "scripts/build_thermal_mi48_dataset.py",
    "scripts/compare_thermal_mi48_domain.py",
    "scripts/evaluate_thermal_mi48_float.py",
    "scripts/dry_run_thermal_mi48_legacy_snapshot.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _error(errors: list[dict[str, str]], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _walk_strings(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key in sorted(value):
            child = f"{path}.{key}" if path else str(key)
            yield from _walk_strings(value[key], child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")


def _portable(value: str) -> bool:
    lower = value.lower()
    return not (
        value.startswith(("/", "~/", "file://"))
        or "\\" in value
        or "/users/" in lower
        or "/private/" in lower
        or lower.startswith(("/volumes/", "/content/"))
    )


def _load(evidence: Path, name: str, errors: list[dict[str, str]]) -> dict[str, Any] | None:
    path = evidence / name
    if not path.is_file():
        _error(errors, "REQUIRED_EVIDENCE_MISSING", name, "Required T-C0 compact evidence is missing.")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _error(errors, "JSON_INVALID", name, str(exc))
        return None
    if not isinstance(value, dict):
        _error(errors, "JSON_NOT_OBJECT", name, "T-C0 evidence JSON must be an object.")
        return None
    return value


def _validate_contract(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("schema_version") != "safenest.thermal.mi48.capture.v1" or doc.get("phase") != PHASE or doc.get("contract_id") != "safenest.thermal.mi48.capture.v1":
        _error(errors, "CONTRACT_ID_INVALID", "contract.json", "The T-C0 capture contract identity is invalid.")
    for key, expected in {"hardware_available": False, "new_data_collected": False}.items():
        if doc.get(key) != expected:
            _error(errors, "SCOPE_INVALID", f"contract.json:{key}", f"Expected {expected!r}.")
    raw = doc.get("raw_acquisition_contract", {})
    for key, expected in {"native_shape": [62, 80], "native_dtype": "uint16", "native_unit": "0.1_K", "physical_conversion": "celsius = raw_uint16 / 10.0 - 273.15", "raw_values_must_be_preserved": True, "sole_scalar_or_screenshot_is_insufficient": True}.items():
        if raw.get(key) != expected:
            _error(errors, "RAW_CONTRACT_INVALID", f"contract.json:raw_acquisition_contract.{key}", f"Expected {expected!r}.")
    if raw.get("native_byte_order") != "T-C_MUST_VERIFY_FROM_DEVICE_EVIDENCE":
        _error(errors, "BYTE_ORDER_GUESS", "contract.json:raw_acquisition_contract.native_byte_order", "Byte order must remain an explicit T-C verification item.")
    session = doc.get("session_contract", {})
    if session.get("empty_room_subject_id") != "NONE" or "subject_id_or_NONE" not in session.get("required_fields", []):
        _error(errors, "SESSION_PRIVACY_CONTRACT_INVALID", "contract.json:session_contract", "Session/empty-room identity policy is incomplete.")
    labels = doc.get("label_contract", {})
    for value in ("ABSENT", "PRESENT", "UNKNOWN"):
        if value not in labels.get("presence_labels", []):
            _error(errors, "LABEL_VOCABULARY_INVALID", "contract.json:label_contract.presence_labels", f"Missing presence label {value!r}.")
    if labels.get("human_fall_semantics") != "LYING_DERIVED_POSTURE_PROXY_NOT_TEMPORAL_EVENT_GROUND_TRUTH":
        _error(errors, "FALL_SEMANTICS_ESCALATED", "contract.json:label_contract.human_fall_semantics", "HUMAN_FALL must remain a lying-derived posture proxy.")
    mapping = labels.get("model_target_mapping", {})
    for key, expected in {"ABSENT": "NOT_HUMAN", "PRESENT_STANDING": "HUMAN_NORMAL", "PRESENT_SITTING": "HUMAN_NORMAL", "PRESENT_CROUCHING": "HUMAN_NORMAL", "PRESENT_LYING": "HUMAN_FALL"}.items():
        if mapping.get(key) != expected:
            _error(errors, "MODEL_MAPPING_INVALID", f"contract.json:label_contract.model_target_mapping.{key}", f"Expected {expected!r}.")
    split = doc.get("split_policy", {})
    for key, expected in {"frame_random_split_allowed": False, "frame_hash_split_allowed": False, "split_frozen_before_model_evaluation": True, "same_group_cross_role": False, "output_dependent_allocation": False}.items():
        if split.get(key) != expected:
            _error(errors, "SPLIT_POLICY_INVALID", f"contract.json:split_policy.{key}", f"Expected {expected!r}.")
    if split.get("assignment_unit") != "SUBJECT_PREFERRED_SESSION_FALLBACK":
        _error(errors, "GROUPING_POLICY_INVALID", "contract.json:split_policy.assignment_unit", "Subject/session group isolation policy is invalid.")
    sampling = doc.get("sampling_policy", {})
    if sampling.get("implemented_method") != "SEQUENCE_INDEX_MODULO" or sampling.get("default_sample_stride") != 1 or sampling.get("adjacent_frame_random_sampling") is not False:
        _error(errors, "SAMPLING_POLICY_INVALID", "contract.json:sampling_policy", "Canonical sampling must be deterministic and non-random.")
    lineage = doc.get("lineage_contract", {})
    for key in ("raw_to_canonical_traceability_required", "array_index_is_not_identity", "raw_artifacts_immutable_after_finalization", "derived_outputs_must_be_separate"):
        if lineage.get(key) is not True:
            _error(errors, "LINEAGE_POLICY_INVALID", f"contract.json:lineage_contract.{key}", "Lineage/immutability requirement is missing.")
    model = doc.get("frozen_float_evaluation_contract", {})
    for key, expected in {"artifact_sha256": "fbe891520f07e0534b1a7074dc819d8ed44bca58b27e35c78916c3ddae73a779", "input_shape": [1, 62, 80, 1], "output_shape": [1, 3], "input_dtype": "float32", "output_dtype": "float32", "p1_profile_id": "P1_TRAIN_FITTED_GLOBAL_ZSCORE", "p1_mean": 22.769290618485442, "p1_std": 2.8684523405441222, "p1_refit": False}.items():
        if model.get(key) != expected:
            _error(errors, "FLOAT_CONTRACT_INVALID", f"contract.json:frozen_float_evaluation_contract.{key}", f"Expected {expected!r}.")
    if doc.get("scope_exclusions", {}).get("float_retraining") is not False or doc.get("scope_exclusions", {}).get("new_int8_generation") is not False:
        _error(errors, "MODEL_SCOPE_INVALID", "contract.json:scope_exclusions", "This phase must not retrain or generate INT8.")


def _validate_matrix(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("schema_version") != "safenest.thermal.mi48.scenario_matrix.v1" or doc.get("phase") != PHASE:
        _error(errors, "SCENARIO_MATRIX_INVALID", "scenario_matrix.json", "Scenario matrix identity is invalid.")
    if doc.get("status") != "PLANNED_NOT_YET_COLLECTED" or doc.get("not_collected") is not True or doc.get("not_a_completed_dataset") is not True:
        _error(errors, "SCENARIO_MATRIX_SCOPE_INVALID", "scenario_matrix.json", "Scenario matrix must remain planned-only.")
    cells = doc.get("planned_cells", [])
    if not isinstance(cells, list) or not cells:
        _error(errors, "SCENARIO_MATRIX_EMPTY", "scenario_matrix.json:planned_cells", "At least one planned scenario cell is required.")
    for index, cell in enumerate(cells):
        if cell.get("status") != "PLANNED_NOT_YET_COLLECTED":
            _error(errors, "SCENARIO_CELL_STATUS_INVALID", f"scenario_matrix.json:planned_cells[{index}]", "No scenario may be reported as collected in T-C0.")


def _validate_gate(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("schema_version") != "safenest.thermal.mi48.retraining_gate.v1" or doc.get("phase") != PHASE:
        _error(errors, "RETRAINING_GATE_INVALID", "retraining_gate.json", "Retraining gate identity is invalid.")
    outcomes = doc.get("outcomes", {})
    required = {"EXISTING_FLOAT_DEVICE_DOMAIN_ACCEPTABLE", "EXISTING_FLOAT_DEVICE_DOMAIN_INADEQUATE", "INCONCLUSIVE_DEVICE_DOMAIN_EVIDENCE"}
    if set(outcomes) != required:
        _error(errors, "RETRAINING_OUTCOMES_INCOMPLETE", "retraining_gate.json:outcomes", "All three future decision outcomes are required.")
    if doc.get("threshold_policy", {}).get("canonical_absolute_threshold_exists") is not False or doc.get("threshold_policy", {}).get("do_not_invent_universal_safety_threshold") is not True:
        _error(errors, "THRESHOLD_POLICY_INVALID", "retraining_gate.json:threshold_policy", "No unsupported universal threshold may be invented.")
    if doc.get("current_result", {}).get("float_retraining_required") != "UNRESOLVED":
        _error(errors, "CURRENT_RETRAINING_STATUS_INVALID", "retraining_gate.json:current_result", "Without labelled MI48 data, retraining remains unresolved.")


def _validate_legacy(doc: Mapping[str, Any], errors: list[dict[str, str]]) -> None:
    if doc.get("schema_version") != "safenest.thermal.mi48.legacy_snapshot_dry_run.v1" or doc.get("used") != "READ_ONLY_DRY_RUN":
        _error(errors, "LEGACY_DRY_RUN_INVALID", "legacy_snapshot_dry_run.json", "Legacy snapshot must be read-only dry-run evidence.")
    for key in ("modified", "new_data_collected", "synthetic_labels_assigned", "used_as_training", "model_evaluation_performed", "model_outputs_used_as_labels"):
        if doc.get(key) is not False:
            _error(errors, "LEGACY_BOUNDARY_VIOLATION", f"legacy_snapshot_dry_run.json:{key}", "Legacy snapshot must not be mutated, labelled, trained, or evaluated.")
    if doc.get("compatibility") not in {"PARTIAL", "NOT_AVAILABLE"}:
        _error(errors, "LEGACY_COMPATIBILITY_OVERCLAIM", "legacy_snapshot_dry_run.json:compatibility", "Legacy snapshot compatibility must remain partial/unavailable.")


def _validate_schema_documents(documents: Mapping[str, Mapping[str, Any]], errors: list[dict[str, str]]) -> None:
    expected = {
        "capture_contract.schema.json": "safenest.thermal.mi48.capture.v1",
        "session_manifest.schema.json": "safenest.thermal.mi48.session.v1",
        "label_record.schema.json": "safenest.thermal.mi48.label.v1",
        "sample_record.schema.json": "safenest.thermal.mi48.sample.v1",
        "dataset_build_summary.schema.json": "safenest.thermal.mi48.dataset.v1",
    }
    for name, schema_version in expected.items():
        document = documents.get(name)
        if document is None:
            continue
        properties = document.get("properties")
        schema_const = properties.get("schema_version", {}).get("const") if isinstance(properties, Mapping) else None
        if schema_const != schema_version:
            _error(errors, "SCHEMA_IDENTITY_INVALID", f"{name}:properties.schema_version", f"Expected schema const {schema_version!r}.")


def _validate_checksums(evidence: Path, errors: list[dict[str, str]]) -> None:
    checksum = evidence / "checksums.sha256"
    if not checksum.is_file():
        _error(errors, "CHECKSUM_REGISTRY_MISSING", "checksums.sha256", "T-C0 checksum registry is required.")
        return
    entries: dict[str, str] = {}
    for line_number, line in enumerate(checksum.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64 or not parts[1].strip() or not _portable(parts[1]):
            _error(errors, "CHECKSUM_LINE_INVALID", f"checksums.sha256:{line_number}", "Expected a portable '<sha256>  <relative path>' entry.")
            continue
        entries[parts[1]] = parts[0].lower()
    for name in CHECKSUM_FILES:
        path = evidence / name
        if name not in entries:
            _error(errors, "CHECKSUM_COVERAGE_MISSING", name, "Required T-C0 evidence has no checksum.")
        elif path.is_file() and _sha256(path) != entries[name]:
            _error(errors, "CHECKSUM_MISMATCH", name, "Checksum does not match the current evidence file.")


def validate_evidence(*, repo_root: Path = ROOT, evidence_dir: Path | None = None, check_checksums: bool = True) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    evidence = Path(evidence_dir or repo / EVIDENCE_REL).resolve()
    errors: list[dict[str, str]] = []
    documents: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_JSON:
        value = _load(evidence, name, errors)
        if value is not None:
            documents[name] = value
    if "contract.json" in documents:
        _validate_contract(documents["contract.json"], errors)
    if "scenario_matrix.json" in documents:
        _validate_matrix(documents["scenario_matrix.json"], errors)
    if "retraining_gate.json" in documents:
        _validate_gate(documents["retraining_gate.json"], errors)
    if "legacy_snapshot_dry_run.json" in documents:
        _validate_legacy(documents["legacy_snapshot_dry_run.json"], errors)
    _validate_schema_documents(documents, errors)
    for tool in REQUIRED_TOOLS:
        if not (repo / tool).is_file():
            _error(errors, "TOOLING_MISSING", tool, "Required offline tooling is missing.")
    report = repo / REPORT_REL
    if not report.is_file():
        _error(errors, "REPORT_MISSING", REPORT_REL, "T-C0 authoritative report is missing.")
    for name, document in documents.items():
        for location, value in _walk_strings(document):
            if not _portable(value):
                _error(errors, "ABSOLUTE_PATH_LEAK", f"{name}:{location}", "Tracked T-C0 evidence must use portable logical paths.")
    if check_checksums:
        _validate_checksums(evidence, errors)
    errors.sort(key=lambda item: (item["code"], item["path"], item["message"]))
    return {
        "schema_version": "safenest.thermal.mi48.readiness_result.v1",
        "phase": PHASE,
        "evidence_validation": "PASS" if not errors else "FAIL",
        "overall_outcome": "PASS_WITH_LIMITATIONS" if not errors else "FAIL",
        "readiness_gate": "THERMAL_MI48_DEVICE_DOMAIN_ACQUISITION_READINESS",
        "readiness_status": "PASS_WITH_LIMITATIONS" if not errors else "FAIL",
        "new_mi48_data_collected": False,
        "real_sensor_required_for_next_phase": True,
        "float_retraining_required": "UNRESOLVED",
        "new_float_model_created": False,
        "new_int8_model_created": False,
        "existing_t_b5_modified": False,
        "pi_o3_authorized": False,
        "thermal_production_activation": False,
        "error_count": len(errors),
        "errors": errors,
    }


def _write_result(evidence: Path, result: Mapping[str, Any]) -> None:
    (evidence / "readiness_result.json").write_text(_canonical(dict(result)), encoding="utf-8")
    rows = []
    for path in sorted(evidence.glob("*.json"), key=lambda p: p.name):
        rows.append(f"{_sha256(path)}  {path.name}")
    (evidence / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SafeNest Thermal T-C0 MI48 acquisition readiness")
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
