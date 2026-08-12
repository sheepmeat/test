#!/usr/bin/env python3
"""Fail-closed validator for M-B10R0 holdout reuse policy evidence.

Never calls the LOCKED_TEST final accessor. Independently recomputes reuse
gates R1–R10 and the policy decision from upstream evidence.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.mmwave_m_b10r0_holdout_policy import (  # noqa: E402
    EXPECTED_CONTRACT_MODEL_IDS,
    INCIDENT_CLOSURE_COMMIT,
    M_B10A_CONTRACT_SHA,
    MODEL_SPECS,
    RECOVERY_CONTRACT_STATUS,
    REQUIRED_OUTPUTS,
    RESULT_LIMITATION,
    ROOT_CAUSE_ID,
    RUNTIME_DETECTION,
    SELECTED_CANDIDATE_ID,
    SELECTED_MODEL_ID,
    SELECTED_PRETEST_SHA,
    SELECTED_SHA,
    _a5_inventory,
    _a6_eligible_subject_coverage,
    _exposure_assessment,
    _policy_decision,
    _reuse_gates,
    sha256_file,
)

OUT_DIR_REL = Path("datasets/mmwave/manifests/M-B10R0_holdout_policy_review")
M_B10B_DIR_REL = Path("datasets/mmwave/manifests/M-B10B_locked_test_final_evaluation")
INCIDENT_VALIDATOR = Path("scripts/validate_mmwave_m_b10b_incident.py")
REPORT_REL = Path("docs/reports/20260812_Cursor_M-B10R0_Holdout_Reuse_Policy_01.md")


class MB10R0ValidationError(RuntimeError):
    """Raised when M-B10R0 policy evidence fails closed."""


def _raise(message: str) -> None:
    raise MB10R0ValidationError(message)


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _raise(f"JSON_PARSE_ERROR:{path.as_posix()}:{exc}")


def _hex_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value.lower()))


def _safe_relative(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or relative.startswith("~") or "file://" in relative:
        _raise(f"ABSOLUTE_OR_TRAVERSAL_PATH:{relative}")
    return path


def _validate_checksums(out: Path) -> None:
    manifest = out / "checksums.sha256"
    if not manifest.is_file():
        _raise("CHECKSUM_MANIFEST_MISSING")
    seen: set[str] = set()
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not _hex_digest(parts[0]):
            _raise(f"CHECKSUM_SYNTAX:{line_number}")
        digest, relative = parts[0].lower(), parts[1].strip()
        _safe_relative(relative)
        if relative in seen:
            _raise(f"CHECKSUM_DUPLICATE:{relative}")
        seen.add(relative)
        target = out / relative
        if target.parent.resolve() != out.resolve() or not target.is_file():
            _raise(f"CHECKSUM_TARGET_INVALID:{relative}")
        if sha256_file(target) != digest:
            _raise(f"CHECKSUM_MISMATCH:{relative}")
    expected = REQUIRED_OUTPUTS - {"checksums.sha256"}
    if seen != expected:
        _raise(f"CHECKSUM_COVERAGE:missing={sorted(expected - seen)}:extra={sorted(seen - expected)}")
    actual = {p.name for p in out.iterdir() if p.is_file() and p.name != "checksums.sha256"}
    if actual != expected:
        _raise(f"UNREGISTERED_OUTPUT_FILES:{sorted(actual ^ expected)}")


def _validate_machine_paths(out: Path) -> None:
    for path in out.iterdir():
        if path.suffix not in {".json", ".sha256"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "/Users/" in text or "/private/" in text or "file://" in text or "\\\\" in text:
            _raise(f"LOCAL_ABSOLUTE_PATH:{path.name}")


def _incident_closure_merged(root: Path) -> None:
    if not INCIDENT_VALIDATOR.is_file():
        _raise("INCIDENT_VALIDATOR_MISSING")
    proc = subprocess.run(
        [sys.executable, str(INCIDENT_VALIDATOR)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        _raise(f"M_B10B_INCIDENT_VALIDATOR_FAILED:{proc.stderr.strip()}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", INCIDENT_CLOSURE_COMMIT, "origin/main"], cwd=root).returncode != 0:
        _raise("INCIDENT_CLOSURE_NOT_IN_ORIGIN_MAIN")


def _validator_has_no_final_accessor_calls() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=__file__)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
            if name in {"get_locked_test_final_evaluation_dataset", "PhaseBAccessGuard"}:
                _raise("VALIDATOR_CALLS_FINAL_ACCESSOR")


def validate_m_b10r0_artifacts(root_dir: Path = ROOT_DIR, output_dir: Path | None = None) -> dict[str, Any]:
    root = root_dir.resolve()
    out = (output_dir or root / OUT_DIR_REL).resolve()
    if not out.is_dir():
        _raise("OUTPUT_DIRECTORY_MISSING")

    _incident_closure_merged(root)
    _validator_has_no_final_accessor_calls()
    _validate_checksums(out)
    _validate_machine_paths(out)

    holdout_inventory = _a5_inventory(root)
    eligible_coverage = _a6_eligible_subject_coverage(root)
    exposure = _exposure_assessment(root)
    gate_results = _reuse_gates(root)
    expected_policy = _policy_decision(root, holdout_inventory, gate_results)

    stored_inventory = _load(out / "existing_unused_holdout_inventory.json")
    stored_exposure = _load(out / "exposure_assessment.json")
    stored_gates = _load(out / "reuse_exception_gate_results.json")
    stored_policy = _load(out / "policy_decision.json")
    stored_recovery = _load(out / "proposed_recovery_evaluation_contract.json")
    stored_access = _load(out / "locked_test_access_audit.json")
    stored_summary = _load(out / "m_b10r0_summary.json")
    stored_incident = _load(out / "incident_identity.json")
    audit_mb10b = _load(root / M_B10B_DIR_REL / "one_time_access_audit.json")

    if stored_inventory != holdout_inventory:
        _raise("HOLDOUT_INVENTORY_RECOMPUTATION_MISMATCH")
    if stored_exposure["summary"] != exposure["summary"]:
        _raise("EXPOSURE_ASSESSMENT_RECOMPUTATION_MISMATCH")
    if stored_gates["failed_gates"] != gate_results["failed_gates"] or stored_gates["all_r1_r10_pass"] != gate_results["all_r1_r10_pass"]:
        _raise("GATE_RESULTS_RECOMPUTATION_MISMATCH")
    for gate_name, gate_body in gate_results["gates"].items():
        stored_gate = stored_gates["gates"].get(gate_name)
        if not stored_gate or stored_gate.get("pass") != gate_body.get("pass"):
            _raise(f"GATE_MISMATCH:{gate_name}")

    # Independently verify individual R4 fields
    r4 = gate_results["gates"]["R4_no_persisted_sample_level_payload"]
    if r4.get("actual_registry_rows", -1) != 0:
        _raise("R4_REGISTRY_ROWS_NONZERO")
    if r4.get("prediction_ledger_rows", -1) != 0:
        _raise("R4_PREDICTION_LEDGER_NONZERO")
    if r4.get("raw_tensors_persisted") is not False:
        _raise("R4_RAW_TENSORS_PERSISTED")
    if r4.get("input_id_labels_tensors_not_persisted") is not True:
        _raise("R4_LABELS_TENSORS_PERSISTED")
    if r4.get("metrics_results_available") is not False:
        _raise("R4_METRICS_RESULTS_AVAILABLE")

    # Independently verify R6 details
    r6 = gate_results["gates"]["R6_baselines_immutable"]
    if not r6.get("pass"):
        _raise("R6_BASELINES_NOT_IMMUTABLE")
    for model_id, detail in r6.get("details", {}).items():
        if not detail.get("exists"):
            _raise(f"R6_BASELINE_MISSING:{model_id}")
        if not detail.get("sha256_match"):
            _raise(f"R6_BASELINE_SHA_MISMATCH:{model_id}")

    # Independently verify R8 fields
    r8 = gate_results["gates"]["R8_no_post_access_tuning"]
    if not r8.get("pass"):
        _raise("R8_POST_ACCESS_TUNING_DETECTED")

    # Independently verify R9 fields
    r9 = gate_results["gates"]["R9_future_contract_unchanged_models_metrics"]
    if not r9.get("pass"):
        _raise("R9_CONTRACT_MODELS_METRICS_CHANGED")
    if not r9.get("exactly_3_models"):
        _raise("R9_NOT_EXACTLY_3_MODELS")
    if not r9.get("model_ids_match"):
        _raise("R9_MODEL_IDS_MISMATCH")
    if not r9.get("no_seed43_seed44"):
        _raise("R9_SEED43_OR_SEED44_PRESENT")
    if not r9.get("contract_sha_match"):
        _raise("R9_CONTRACT_SHA_MISMATCH")

    # Independently verify R10 fields
    r10 = gate_results["gates"]["R10_contamination_disclosure_accepted"]
    if not r10.get("pass"):
        _raise("R10_CONTAMINATION_DISCLOSURE_FAILED")
    if r10.get("required_future_designation") != RESULT_LIMITATION:
        _raise("R10_WRONG_RESULT_DESIGNATION")
    if r10.get("result_not_pristine") is not True:
        _raise("R10_RESULT_NOT_PRISTINE_FALSE")
    if r10.get("recovery_contract_status") != RECOVERY_CONTRACT_STATUS:
        _raise("R10_RECOVERY_CONTRACT_STATUS_WRONG")

    if stored_policy["decision"] != expected_policy["decision"]:
        _raise("POLICY_DECISION_RECOMPUTATION_MISMATCH")
    for key in (
        "recovery_execution_authorized",
        "locked_test_reopen_authorized",
        "m_b11_authorized",
        "original_predictions_generated",
        "original_metrics_generated",
        "candidate_changed_after_access",
        "new_performance_information_used_for_policy",
    ):
        if stored_policy.get(key) is not False:
            _raise(f"POLICY_DECISION_FORBIDDEN_FLAG:{key}")

    if stored_recovery.get("status") != RECOVERY_CONTRACT_STATUS:
        _raise("RECOVERY_CONTRACT_NOT_PROPOSED_NOT_AUTHORIZED")
    if stored_recovery.get("expected_model_inference_count") != 225:
        _raise("RECOVERY_CONTRACT_INFERENCE_COUNT")
    if stored_recovery.get("required_result_designation") != RESULT_LIMITATION:
        _raise("RECOVERY_CONTRACT_DESIGNATION")

    if stored_access.get("new_m_b10r0_accessor_invocations") != 0 or stored_access.get("recovery_runner_executions") != 0:
        _raise("ACCESS_AUDIT_NONZERO_DURING_M_B10R0")

    if (
        stored_incident.get("original_accessor_invocations") != 1
        or stored_incident.get("rows_returned") != 75
        or stored_incident.get("model_inference_invocations") != audit_mb10b.get("completed_model_inference_invocations")
    ):
        _raise("INCIDENT_IDENTITY_MISMATCH")
    if audit_mb10b.get("accessor_invocation_count") != 1 or audit_mb10b.get("completed_model_inference_invocations") != 0:
        _raise("M_B10B_AUDIT_MISMATCH")

    if eligible_coverage["eligible_window_count"] != 75 or eligible_coverage["eligible_subject_count"] != 16:
        _raise("A6_ELIGIBLE_COVERAGE_MISMATCH")

    report = root / REPORT_REL
    if not report.is_file():
        _raise("REPORT_MISSING")
    report_text = report.read_text(encoding="utf-8")
    for phrase in ("LOCKED_TEST REOPENED: NO", "RECOVERY EVALUATION RUN: NO", "MODEL INFERENCE: 0", stored_policy["decision"]):
        if phrase not in report_text:
            _raise(f"REPORT_MISSING_PHRASE:{phrase}")

    if stored_summary.get("policy_decision") != expected_policy["decision"]:
        _raise("SUMMARY_DECISION_MISMATCH")

    return {
        "validation_status": "PASS",
        "phase_id": "M-B10R0",
        "policy_decision": expected_policy["decision"],
        "reuse_exception_eligible": expected_policy["reuse_exception_eligible"],
        "existing_independent_holdout_available": expected_policy["existing_independent_holdout_available"],
        "failed_reuse_gates": expected_policy["failed_reuse_gates"],
        "recovery_execution_authorized": False,
        "locked_test_reopen_authorized": False,
        "m_b11_authorized": False,
        "m_b10r0_accessor_invocations": 0,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        result = validate_m_b10r0_artifacts()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except MB10R0ValidationError as exc:
        print(f"M-B10R0 validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
