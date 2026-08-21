#!/usr/bin/env python3
"""Validate compact R1 common-trace evidence without requiring raw arrays."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_records(records: list[dict[str, Any]], source_id: str) -> list[str]:
    errors: list[str] = []
    required = {
        "source_id",
        "dataset_id",
        "subject_id",
        "recording_id",
        "condition",
        "status",
        "provenance",
    }
    provenance_required = {
        "source_id",
        "dataset_id",
        "subject_id",
        "recording_id",
        "condition",
        "original_sampling_rate_hz",
        "adapter_identity",
        "r1_profile_identity",
        "time_range_s",
        "native_trace_unit",
        "common_trace_semantics",
        "validity_gap_flags",
    }
    for index, row in enumerate(records):
        missing = sorted(required - row.keys())
        if missing:
            errors.append(f"{source_id}[{index}] missing fields: {missing}")
            continue
        if row.get("source_id") != source_id:
            errors.append(f"{source_id}[{index}] source_id mismatch")
        provenance = row.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{source_id}[{index}] provenance is not an object")
            continue
        missing_provenance = sorted(provenance_required - provenance.keys())
        if missing_provenance:
            errors.append(f"{source_id}[{index}] missing provenance: {missing_provenance}")
        if row.get("status") == "SUCCESS":
            for field in (
                "source_sampling_rate_hz",
                "output_sampling_rate_hz",
                "output_sample_count",
                "trace_semantics",
                "trace_units",
                "native_trace_semantics",
                "native_trace_unit",
                "native_scale_descriptors",
                "common_trace_descriptors",
                "native_scale_preserved",
                "scale_normalization_applied",
                "sensor_gain_matching_applied",
                "sign_inversion_applied",
                "validity",
            ):
                if field not in row:
                    errors.append(f"{source_id}[{index}] successful record missing {field}")
            if row.get("native_scale_preserved") is not True:
                errors.append(f"{source_id}[{index}] native scale not preserved")
            if row.get("scale_normalization_applied") is not False:
                errors.append(f"{source_id}[{index}] scale normalization was applied")
            if row.get("sensor_gain_matching_applied") is not False:
                errors.append(f"{source_id}[{index}] sensor gain matching was applied")
            if row.get("sign_inversion_applied") is not False:
                errors.append(f"{source_id}[{index}] sign inversion was applied")
            validity = row.get("validity", {})
            if validity.get("all_output_samples_valid") is not True or validity.get("invalid_sample_count") != 0:
                errors.append(f"{source_id}[{index}] invalid output samples present")
        elif not row.get("failure_code"):
            errors.append(f"{source_id}[{index}] excluded record lacks failure_code")
    return errors


def validate(root: Path, evidence_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    contract = _read_json(evidence_root / "common_trace_contract.json")
    candidates = _read_json(evidence_root / "representation_candidates.json")
    d0 = _read_json(evidence_root / "d0_trace_audit.json")
    d1 = _read_json(evidence_root / "d1_trace_audit.json")
    cross = _read_json(evidence_root / "cross_domain_sanity.json")
    exceptions = _read_json(evidence_root / "exception_registry.json")
    result = _read_json(evidence_root / "validation_result.json")
    checksums = _read_json(evidence_root / "checksums.json")

    if contract.get("contract_id") != "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1":
        errors.append("contract identity mismatch")
    if contract.get("time_axis", {}).get("candidate_rate_hz") != 10.0:
        errors.append("common rate candidate is not 10 Hz")
    if contract.get("time_axis", {}).get("final_rate_frozen") is not False:
        errors.append("final common rate was incorrectly frozen")
    if contract.get("time_axis", {}).get("8_Hz_240_sample_forcing") is not False:
        errors.append("8 Hz/240 forcing flag is not false")
    if candidates.get("selected_candidate") is not None:
        errors.append("R1 selected a candidate prematurely")

    d0_rows = d0.get("records", [])
    d1_rows = d1.get("records", [])
    if not isinstance(d0_rows, list) or not isinstance(d1_rows, list):
        errors.append("audit records are not lists")
        d0_rows = []
        d1_rows = []
    errors.extend(_validate_records(d0_rows, "D0"))
    errors.extend(_validate_records(d1_rows, "D1"))

    for audit, source_id in ((d0, "D0"), (d1, "D1")):
        summary = audit.get("summary", {})
        success = sum(row.get("status") == "SUCCESS" for row in audit.get("records", []))
        excluded = sum(row.get("status") != "SUCCESS" for row in audit.get("records", []))
        if summary.get("success") != success or summary.get("excluded") != excluded:
            errors.append(f"{source_id} summary does not account for records")
        if summary.get("native_scale_preserved_count") != success:
            errors.append(f"{source_id} native scale accounting mismatch")
        if summary.get("window_local_MAD_only_normalization_count") != 0:
            errors.append(f"{source_id} local MAD-only normalization detected")

    if cross.get("common_trace_generated_D0") is not True:
        errors.append("D0 common trace was not generated")
    if cross.get("common_trace_generated_D1") is not True:
        errors.append("D1 common trace was not generated")
    safety = cross.get("safety_checks", {})
    for key, expected in {
        "arbitrary_sensor_gain_matching": False,
        "window_local_MAD_only_normalization": False,
        "original_amplitude_information_preserved": True,
        "D0_SUBJECT_HELDOUT_used": False,
        "D0_VAL_used_for_selection": False,
        "M_N6_excluded_heldout_used": False,
        "D2_used": False,
        "MR60_supervised_use": False,
        "model_training": False,
        "feature_family_selected": False,
    }.items():
        if safety.get(key) is not expected:
            errors.append(f"safety check {key} expected {expected}")
    if exceptions.get("blocker_count") != 0:
        errors.append("exception registry contains blockers")
    if result.get("gate") != "PASS_WITH_LIMITATIONS" or result.get("ok") is not True:
        errors.append("recorded validation result is not PASS_WITH_LIMITATIONS")

    evidence_hashes = checksums.get("evidence", {})
    for name, expected_hash in evidence_hashes.items():
        path = evidence_root / name
        if not path.is_file():
            errors.append(f"missing evidence file for checksum: {name}")
        elif _sha256(path) != expected_hash:
            errors.append(f"evidence checksum mismatch: {name}")
    for name, expected_hash in checksums.get("code", {}).items():
        path = root / name
        if not path.is_file():
            errors.append(f"missing code file for checksum: {name}")
        elif _sha256(path) != expected_hash:
            errors.append(f"code checksum mismatch: {name}")

    return {
        "schema_version": "R1.1",
        "ok": not errors,
        "gate": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "errors": errors,
        "D0_records": len(d0_rows),
        "D1_records": len(d1_rows),
        "D0_success": sum(row.get("status") == "SUCCESS" for row in d0_rows),
        "D1_success": sum(row.get("status") == "SUCCESS" for row in d1_rows),
        "checksum_validation": {
            "code_checked": len(checksums.get("code", {})),
            "evidence_checked": len(evidence_hashes),
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
        result = {"schema_version": "R1.1", "ok": False, "gate": "BLOCKED", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
