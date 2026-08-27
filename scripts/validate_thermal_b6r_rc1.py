#!/usr/bin/env python3
"""Fail-closed validator for the B6R-RC1 Thermal-90 remediation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_rc1_thermal90_capture_remediation_contract.json"


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _at(value: dict[str, Any], *path: str) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _has_nonportable_path(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    patterns = (r"[A-Za-z]:[\\/]", r"/Users/", r"file://", r"(?:^|[\s\"'])~[/\\]")
    return any(re.search(pattern, text) for pattern in patterns)


def validate_contract(contract_path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    try:
        raw = contract_path.read_bytes()
        canonical_raw = raw.replace(b"\r\n", b"\n")
        contract = json.loads(canonical_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "schema_version": "safenest.thermal.b6r.rc1.validation.v1",
            "package_id": "B6R-RC1",
            "status": "FAIL",
            "error_count": 1,
            "errors": [_error("CONTRACT_UNREADABLE", str(exc))],
        }

    required_exact = {
        ("schema_version",): "safenest.thermal.b6r.rc1.capture_remediation.v1",
        ("package_id",): "B6R-RC1",
        ("status",): "PLAN_FROZEN_EXECUTION_NOT_STARTED",
        ("identity_decision", "candidate_name"): "Thermal-90",
        ("identity_decision", "treatment"): "DISTINCT_TARGET_SENSOR_CANDIDATE",
        ("identity_decision", "equivalent_to_mi48_claimed"): False,
        ("identity_decision", "approval_status"): "EVIDENCE_PENDING_OWNER_ACCEPTANCE",
        ("holdout_contract", "assignment_unit"): "SUBJECT",
        ("holdout_contract", "existing_s000_eligible_for_locked_holdout"): False,
        ("holdout_contract", "role"): "REAL_LOCKED_TEST",
        ("holdout_contract", "locked_test_access"): "UNTOUCHED",
        ("holdout_contract", "model_training_tuning_calibration_debugging_access_allowed"): False,
        ("holdout_contract", "reuse_after_tuning_allowed"): False,
        ("holdout_contract", "unlock_stage"): "B6R-11",
        ("label_contract", "lying_semantics"): "POSTURE_PROXY_NOT_TEMPORAL_FALL_GROUND_TRUTH",
        ("label_contract", "model_output_must_not_be_label_source"): True,
        ("label_contract", "operator_and_independent_reviewer_required"): True,
        ("label_contract", "uncontrolled_free_fall_capture_allowed"): False,
        ("capture_waves", "wave_b_role_separated_acquisition", "frame_random_split_allowed"): False,
        ("capture_waves", "wave_b_role_separated_acquisition", "same_subject_cross_role"): False,
        ("authorized_scope", "actual_capture_performed"): False,
        ("authorized_scope", "b6r_1_executed"): False,
        ("authorized_scope", "b6r_2_executed"): False,
        ("authorized_scope", "model_or_runtime_changed"): False,
        ("authorized_scope", "safety_authority_changed"): False,
        ("claim_boundary", "sensor_identity_approved_claim_allowed_now"): False,
        ("claim_boundary", "model_training_allowed_now"): False,
        ("next_formal_stage", "stage"): "B6R-1",
    }
    for path, expected in required_exact.items():
        actual = _at(contract, *path)
        if actual != expected:
            errors.append(_error("INVARIANT_MISMATCH", f"{'.'.join(path)} must be {expected!r}, got {actual!r}"))

    if _has_nonportable_path(contract):
        errors.append(_error("NONPORTABLE_PATH", "Contract contains an absolute, home-relative, or file URI path."))

    wave_a = _at(contract, "capture_waves", "wave_a_contract_verification") or {}
    if wave_a.get("minimum_independent_subjects", 0) < 3:
        errors.append(_error("MULTI_SUBJECT_FLOOR_WEAKENED", "Wave A requires at least three independent subjects."))
    if wave_a.get("minimum_sessions_per_subject", 0) < 2:
        errors.append(_error("SESSION_VARIATION_FLOOR_WEAKENED", "Wave A requires at least two sessions per subject."))
    wave_b = _at(contract, "capture_waves", "wave_b_role_separated_acquisition") or {}
    if wave_b.get("minimum_new_locked_holdout_subjects", 0) < 2:
        errors.append(_error("HOLDOUT_SUBJECT_FLOOR_WEAKENED", "At least two new holdout subjects are required as an operational floor."))
    if wave_b.get("statistical_adequacy_claimed_by_minimum") is not False:
        errors.append(_error("UNSUPPORTED_ADEQUACY_CLAIM", "Operational minimums must not claim statistical adequacy."))

    fps_acceptance = _at(contract, "sensor_semantic_verification", "timing_and_fps", "acceptance") or {}
    if fps_acceptance.get("counter_reversal_count") != 0 or fps_acceptance.get("duplicate_count") != 0:
        errors.append(_error("TIMING_FAIL_CLOSED_WEAKENED", "Counter reversals and duplicates must be zero for accepted sessions."))
    if _at(contract, "sensor_semantic_verification", "raw_preservation", "silent_bad_frame_deletion_allowed") is not False:
        errors.append(_error("RAW_ACCOUNTING_WEAKENED", "Invalid frames must remain accounted for."))

    required_exit = set(contract.get("exit_criteria", []))
    expected_exit = {
        "IDENTITY_OWNER_DECISION_RECORDED",
        "UNIT_VERIFIED_OR_EXPLICITLY_REJECTED",
        "ORIENTATION_AND_MOUNT_FROZEN",
        "FPS_AND_PACKET_QUALITY_GATE_PASS",
        "WAVE_A_MULTI_SUBJECT_ACCOUNTING_COMPLETE",
        "LABEL_DUAL_REVIEW_AND_REVISION_PROVENANCE_PASS",
        "ROLE_SEPARATED_HOLDOUT_PREREGISTERED_AND_SEALED",
        "STANDALONE_CAPTURE_VALIDATOR_PASS",
    }
    if not expected_exit.issubset(required_exit):
        errors.append(_error("EXIT_CRITERIA_INCOMPLETE", "One or more mandatory remediation exit criteria are missing."))

    required_stop = set(contract.get("stop_conditions", []))
    if "EXISTING_S000_PROMOTED_TO_LOCKED_HOLDOUT" not in required_stop:
        errors.append(_error("S000_HOLDOUT_GUARD_MISSING", "The inspected S000 pilot must be barred from locked holdout."))
    if "MODEL_TRAINING_OR_RUNTIME_ACTIVATION_STARTED_FROM_THIS_PACKAGE" not in required_stop:
        errors.append(_error("SCOPE_STOP_MISSING", "The package must stop before model/runtime work."))

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "safenest.thermal.b6r.rc1.validation.v1",
        "package_id": "B6R-RC1",
        "status": status,
        "contract_path": "config/thermal/b6r_rc1_thermal90_capture_remediation_contract.json",
        "contract_sha256": hashlib.sha256(canonical_raw).hexdigest(),
        "contract_hash_normalization": "UTF8_CRLF_TO_LF",
        "error_count": len(errors),
        "errors": errors,
        "plan_status": contract.get("status"),
        "identity_approval_status": _at(contract, "identity_decision", "approval_status"),
        "capture_execution_status": "NOT_STARTED",
        "b6r_mainline_status_changed": False,
        "model_or_runtime_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", nargs="?", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_contract(args.contract)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
