#!/usr/bin/env python3
"""Validate the compact R2 candidate evidence and its deterministic checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features")
EXPECTED_FILES = (
    "feature_candidate_set.json",
    "f1_feature_contract.json",
    "f2_feature_contract.json",
    "f3_descriptor_contract.json",
    "d0_feature_audit.json",
    "d1_feature_audit.json",
    "cross_domain_sanity.json",
    "scale_preservation_audit.json",
    "exception_registry.json",
    "validation_result.json",
    "checksums.json",
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [item for key, child in value.items() for item in _walk_strings(key)] + [
            item for child in value.values() for item in _walk_strings(child)
        ]
    if isinstance(value, list):
        return [item for child in value for item in _walk_strings(child)]
    return []


def _validate_audit(audit: dict[str, Any], source_id: str, expected_count: int) -> list[str]:
    errors: list[str] = []
    if audit.get("source_id") != source_id:
        errors.append(f"{source_id}: source_id mismatch")
    records = audit.get("records")
    if not isinstance(records, list):
        return [f"{source_id}: records is not a list"]
    summary = audit.get("summary", {})
    successful = [row for row in records if row.get("status") == "SUCCESS"]
    excluded = [row for row in records if row.get("status") != "SUCCESS"]
    if len(records) != expected_count:
        errors.append(f"{source_id}: expected {expected_count} records, observed {len(records)}")
    if summary.get("records_considered") != len(records):
        errors.append(f"{source_id}: records_considered mismatch")
    if summary.get("success") != len(successful) or summary.get("excluded") != len(excluded):
        errors.append(f"{source_id}: success/excluded summary mismatch")
    if excluded:
        errors.append(f"{source_id}: record-level exclusions present")
    ids = [str(row.get("recording_id")) for row in records]
    if len(set(ids)) != len(ids):
        errors.append(f"{source_id}: duplicate recording_id")
    required = {
        "source_id",
        "dataset_id",
        "subject_id",
        "recording_id",
        "condition",
        "status",
        "source_sampling_rate_hz",
        "output_sampling_rate_hz",
        "output_sample_count",
        "feature_status",
        "feature_unavailable_reasons",
        "features",
        "feature_units",
        "provenance",
        "trace_persisted",
        "native_scale_preserved",
        "window_local_scale_normalization",
        "cross_domain_gain_matching",
        "reference_used_for_feature_selection",
    }
    for index, row in enumerate(successful):
        missing = sorted(required - row.keys())
        if missing:
            errors.append(f"{source_id}[{index}]: missing fields {missing}")
            continue
        if row.get("trace_persisted") is not False:
            errors.append(f"{source_id}[{index}]: trace persisted")
        if row.get("native_scale_preserved") is not True:
            errors.append(f"{source_id}[{index}]: native scale not preserved")
        if row.get("window_local_scale_normalization") is not False:
            errors.append(f"{source_id}[{index}]: local scale normalization applied")
        if row.get("cross_domain_gain_matching") is not False:
            errors.append(f"{source_id}[{index}]: cross-domain gain matching applied")
        if row.get("reference_used_for_feature_selection") is not False:
            errors.append(f"{source_id}[{index}]: reference used for selection")
        provenance = row.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{source_id}[{index}]: provenance missing")
        for candidate in ("F1", "F2", "F3"):
            status = row.get("feature_status", {}).get(candidate)
            if status not in {"AVAILABLE", "FEATURE_UNAVAILABLE_FLAT_TRACE", "FEATURE_UNAVAILABLE_SHORT_TRACE", "FEATURE_UNAVAILABLE_NO_RESPIRATORY_BAND_ENERGY", "FEATURE_UNAVAILABLE_NO_RESPIRATORY_BAND_BINS", "FEATURE_UNAVAILABLE_ZERO_LAG_ENERGY", "FEATURE_UNAVAILABLE_NO_AUTOCORR_LAG_RANGE"}:
                errors.append(f"{source_id}[{index}]: invalid {candidate} status {status}")
            values = row.get("features", {}).get(candidate, {})
            if not isinstance(values, dict):
                errors.append(f"{source_id}[{index}]: {candidate} features not an object")
                continue
            for name, value in values.items():
                if not isinstance(value, (int, float)) or not __import__("math").isfinite(float(value)):
                    errors.append(f"{source_id}[{index}]: nonfinite {candidate}.{name}")
        text = " ".join(_walk_strings(row.get("features", {}))).lower()
        if "apnea" in text or "clinical" in text:
            errors.append(f"{source_id}[{index}]: forbidden target-like feature text")
    return errors


def validate(root: Path, evidence_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    for name in EXPECTED_FILES:
        if not (evidence_root / name).is_file():
            errors.append(f"missing evidence file: {name}")
    if errors:
        return {"schema_version": "R2.1", "ok": False, "gate": "BLOCKED", "errors": errors}

    candidate_set = _read_json(evidence_root / "feature_candidate_set.json")
    f1 = _read_json(evidence_root / "f1_feature_contract.json")
    f2 = _read_json(evidence_root / "f2_feature_contract.json")
    f3 = _read_json(evidence_root / "f3_descriptor_contract.json")
    d0 = _read_json(evidence_root / "d0_feature_audit.json")
    d1 = _read_json(evidence_root / "d1_feature_audit.json")
    cross = _read_json(evidence_root / "cross_domain_sanity.json")
    scale = _read_json(evidence_root / "scale_preservation_audit.json")
    exceptions = _read_json(evidence_root / "exception_registry.json")
    recorded_validation = _read_json(evidence_root / "validation_result.json")
    checksums = _read_json(evidence_root / "checksums.json")

    if candidate_set.get("candidate_set_id") != "MMWAVE_V2_R2_REPRESENTATION_CANDIDATE_SET_V1":
        errors.append("candidate set identity mismatch")
    if candidate_set.get("selected_candidate") is not None or candidate_set.get("selection_performed") is not False:
        errors.append("candidate selection occurred")
    for contract, schema_id in ((f1, "MMWAVE_V2_R2_F1_NORMALIZED_SPECTRAL_V1"), (f2, "MMWAVE_V2_R2_F2_SPECTRAL_AUTOCORR_V1"), (f3, "MMWAVE_V2_R2_F3_TRACE_PLUS_QUALITY_DESCRIPTOR_V1")):
        if contract.get("schema_id") != schema_id:
            errors.append(f"contract identity mismatch: {schema_id}")
        if contract.get("status") != "BOUNDED_CANDIDATE_FOR_M_PV1_NOT_SELECTED":
            errors.append(f"contract selection status mismatch: {schema_id}")
    errors.extend(_validate_audit(d0, "D0", 318))
    errors.extend(_validate_audit(d1, "D1", 265))

    if d0.get("scope", {}).get("VAL_used") is not False or d0.get("scope", {}).get("D0_SUBJECT_HELDOUT_used") is not False:
        errors.append("D0 non-TRAIN scope was used")
    if d0.get("scope", {}).get("selection_scope") != "TRAIN_ONLY":
        errors.append("D0 selection scope is not TRAIN_ONLY")
    if d1.get("scope", {}).get("selection_scope") != "FULL_DEVELOPMENT_POOL":
        errors.append("D1 selection scope mismatch")

    safety = cross.get("safety_checks", {})
    expected_false = (
        "D0_VAL_used",
        "D0_SUBJECT_HELDOUT_used",
        "M_N6_excluded_subjects_used",
        "D2_used",
        "D3_used",
        "MR60_supervised_use",
        "model_training",
        "candidate_selected",
        "cross_domain_scaler_fit",
        "window_local_normalization",
        "sign_flip",
        "source_adapter_reimplemented",
    )
    for key in expected_false:
        if safety.get(key) is not False:
            errors.append(f"safety check {key} is not false")
    if exceptions.get("blocker_count") != 0:
        errors.append("exception registry has blockers")
    if scale.get("policy", {}).get("window_local_MAD_division") is not False:
        errors.append("scale audit permits local MAD division")
    if scale.get("policy", {}).get("cross_domain_gain_matching") is not False:
        errors.append("scale audit permits gain matching")
    synthetic = scale.get("synthetic_tests", {}).get("tests", {})
    for name, test in synthetic.items():
        if test.get("pass") is not True:
            errors.append(f"synthetic scale test failed: {name}")
    if recorded_validation.get("ok") is not True or recorded_validation.get("gate") != "PASS_WITH_LIMITATIONS":
        errors.append("recorded validation result is not PASS_WITH_LIMITATIONS")

    for name, expected_hash in checksums.get("evidence", {}).items():
        path = evidence_root / name
        if not path.is_file():
            errors.append(f"checksum evidence path missing: {name}")
        elif _sha256(path) != expected_hash:
            errors.append(f"checksum mismatch: evidence/{name}")
    for name, expected_hash in checksums.get("code", {}).items():
        path = root / name
        if not path.is_file():
            errors.append(f"checksum code path missing: {name}")
        elif _sha256(path) != expected_hash:
            errors.append(f"checksum mismatch: code/{name}")

    machine_values = [candidate_set, f1, f2, f3, d0, d1, cross, scale, exceptions, recorded_validation]
    forbidden_path_fragments = ("/Users/", "file://", "\\\\")
    for artifact in machine_values:
        for value in _walk_strings(artifact):
            if any(fragment in value for fragment in forbidden_path_fragments):
                errors.append(f"machine artifact contains non-repository path: {value}")
                break

    return {
        "schema_version": "R2.1",
        "ok": not errors,
        "gate": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "errors": errors,
        "D0_records": len(d0.get("records", [])),
        "D1_records": len(d1.get("records", [])),
        "D0_success": d0.get("summary", {}).get("success", 0),
        "D1_success": d1.get("summary", {}).get("success", 0),
        "checksum_validation": {
            "code_checked": len(checksums.get("code", {})),
            "evidence_checked": len(checksums.get("evidence", {})),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--evidence-root", type=Path, default=ROOT / EVIDENCE_RELATIVE_ROOT)
    args = parser.parse_args()
    try:
        result = validate(args.root.resolve(), args.evidence_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": "R2.1", "ok": False, "gate": "BLOCKED", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
