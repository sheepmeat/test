#!/usr/bin/env python3
"""Fail-closed M-B12 Phase-B offline final-report validator.

Validates stored M-B11 lock evidence and M-B12 closure artifacts only.
Never calls LOCKED_TEST or recovery accessors, never invokes TFLite,
never trains, converts, calibrates, or begins M-C.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.mmwave_m_b10r1_result_writer import sha256_file as _sha256_file  # noqa: E402
from scripts.mmwave_m_b11_artifact_lock import (  # noqa: E402
    ARTIFACT_STATUS,
    CLASS_MAP,
    RESULT_LIMITATION,
    RUNTIME_MODEL_ID,
    SELECTED_CANDIDATE_ID,
    SELECTED_TFLITE_REL,
    SENSOR_LOCK_REL,
    load_json,
    require_repo_relative,
)
from scripts.mmwave_m_b12_phase_b_closure import (  # noqa: E402
    CLOSURE_DIR_REL,
    CLOSURE_JSON_FILES,
    EXPECTED_ELIGIBLE,
    EXPECTED_HISTORICAL_RELEASES,
    EXPECTED_MACRO_F1,
    EXPECTED_MODEL_BYTES,
    EXPECTED_MODEL_SHA,
    EXPECTED_MODELS,
    EXPECTED_PAIRS,
    EXPECTED_RECOVERY_INFERENCE,
    EXPECTED_V01_F1,
    EXPECTED_V02_F1,
    M_B11_DIR_REL,
    PROPOSED_TAG,
    SCHEMA,
    STATUS_LABEL,
)
from scripts.validate_mmwave_m_b11 import validate_m_b11  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_DESIGNATION_TOKENS = {
    "pristine_locked_test",
    "first_locked_test_evaluation",
}
FORBIDDEN_TRUE_KEY_TOKENS = {
    "pristine_locked_test",
    "first_locked_test_evaluation",
    "deployment_ready",
    "production_ready",
    "clinical_apnea_validated",
    "mr60_device_validation_complete",
    "mr60_validated",
    "mr60_validation_complete",
    "raspberry_pi_validation_complete",
    "raspberry_pi_validated",
    "rpi_validated",
    "rpi_validation_complete",
    "locked_test_reopen_allowed",
    "recovery_reopen_allowed",
    "phase_b_release_ready",
    "git_tag_created",
    "github_release_created",
    "m_c_started",
    "m_c_begun",
}
TRUTHY_TOKENS = {"true", "yes", "validated", "complete"}
FORBIDDEN_POSITIVE_VALUE_TOKENS = FORBIDDEN_DESIGNATION_TOKENS | FORBIDDEN_TRUE_KEY_TOKENS
ALLOWED_GENERATOR_IMPORTS = {
    "CLOSURE_DIR_REL",
    "CLOSURE_JSON_FILES",
    "EXPECTED_ELIGIBLE",
    "EXPECTED_HISTORICAL_RELEASES",
    "EXPECTED_MACRO_F1",
    "EXPECTED_MODEL_BYTES",
    "EXPECTED_MODEL_SHA",
    "EXPECTED_MODELS",
    "EXPECTED_PAIRS",
    "EXPECTED_RECOVERY_INFERENCE",
    "EXPECTED_V01_F1",
    "EXPECTED_V02_F1",
    "M_B11_DIR_REL",
    "PROPOSED_TAG",
    "SCHEMA",
    "STATUS_LABEL",
}


class MB12ValidationError(Exception):
    """Fail-closed M-B12 validation failure."""


def _raise(code: str) -> None:
    raise MB12ValidationError(code)


def _inspect_no_accessor_or_invoke() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "get_locked_test_recovery_evaluation_dataset",
        "get_locked_test_final_evaluation_dataset",
        "invoke",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "scripts.mmwave_m_b12_phase_b_closure":
            for alias in node.names:
                if alias.name == "*" or alias.name not in ALLOWED_GENERATOR_IMPORTS:
                    _raise(f"VALIDATOR_IMPORTS_GENERATOR:{alias.name}")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in forbidden:
                _raise(f"M_B12_VALIDATOR_FORBIDDEN_CALL:{name}")


def _validate_checksums(out: Path) -> None:
    checksum_path = out / "checksums.sha256"
    if not checksum_path.is_file():
        _raise("CHECKSUMS_MISSING")
    mapped: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or not HEX64.fullmatch(parts[0]):
            _raise(f"CHECKSUM_LINE_INVALID:{line}")
        rel = parts[1]
        if ".." in rel or rel.startswith("/") or "\\" in rel:
            _raise(f"CHECKSUM_UNSAFE_PATH:{rel}")
        if rel in mapped and mapped[rel] != parts[0]:
            _raise(f"CHECKSUM_DUPLICATE_INCONSISTENT:{rel}")
        mapped[rel] = parts[0]
        target = out / rel
        if not target.is_file():
            _raise(f"CHECKSUM_TARGET_MISSING:{rel}")
        if _sha256_file(target) != parts[0]:
            _raise(f"CHECKSUM_MISMATCH:{rel}")
    expected = set(CLOSURE_JSON_FILES)
    if set(mapped) != expected:
        missing = sorted(expected - set(mapped))
        extra = sorted(set(mapped) - expected)
        _raise(f"CHECKSUM_ENTRY_SET_MISMATCH:missing={missing}:extra={extra}")
    if "checksums.sha256" in mapped:
        _raise("CHECKSUM_SELF_HASH")


def _walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item))
    return found


def _reject_unsafe_paths(payload: Any, *, context: str) -> None:
    for text in _walk_strings(payload):
        if text.startswith("/") or text.startswith("file:") or "\\" in text:
            _raise(f"UNSAFE_PATH:{context}:{text}")
        if ".." in Path(text).parts:
            _raise(f"UNSAFE_PATH:{context}:{text}")


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _is_truthy_claim(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and _normalize_token(value) in TRUTHY_TOKENS:
        return True
    return False


def _reject_forbidden_claims(payload: Any, *, context: str) -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{path}.{key}"
                token = _normalize_token(key)
                if token in FORBIDDEN_TRUE_KEY_TOKENS and _is_truthy_claim(value):
                    _raise(f"FORBIDDEN_POSITIVE_CLAIM:{context}:{child}:{value}")
                if isinstance(value, str) and _normalize_token(value) in FORBIDDEN_POSITIVE_VALUE_TOKENS:
                    _raise(f"FORBIDDEN_POSITIVE_CLAIM:{context}:{child}:{value}")
                walk(value, child)
            return
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")
            return
        if isinstance(node, str) and _normalize_token(node) in FORBIDDEN_POSITIVE_VALUE_TOKENS:
            _raise(f"FORBIDDEN_POSITIVE_CLAIM:{context}:{path}:{node}")

    walk(payload, "$")


def _require_equal(actual: Any, expected: Any, code: str) -> None:
    if actual != expected:
        _raise(f"{code}:{actual}!={expected}")


def _require_non_pristine_fields(payload: dict[str, Any], *, context: str) -> None:
    if "result_limitation" in payload:
        _require_equal(payload.get("result_limitation"), RESULT_LIMITATION, f"LIMITATION:{context}")
    if "result_designation" in payload:
        _require_equal(payload.get("result_designation"), RESULT_LIMITATION, f"DESIGNATION:{context}")
    if "result_not_pristine" in payload and payload.get("result_not_pristine") is not True:
        _raise(f"RESULT_NOT_PRISTINE_FALSE:{context}")


def validate_m_b12(
    root: Path | None = None,
    *,
    closure_dir: Path | None = None,
    skip_m_b11: bool = False,
) -> dict[str, Any]:
    _inspect_no_accessor_or_invoke()
    root = Path(root) if root is not None else ROOT_DIR
    closure_dir = Path(closure_dir) if closure_dir is not None else root / CLOSURE_DIR_REL
    if not closure_dir.is_dir():
        _raise("CLOSURE_DIR_MISSING")
    if not skip_m_b11:
        m11 = validate_m_b11(root)
        if m11.get("status") != "PASS":
            _raise(f"M_B11_VALIDATOR_NOT_PASS:{m11.get('status')}")
        _require_equal(m11.get("model_sha256"), EXPECTED_MODEL_SHA, "M11_LIVE_MODEL_SHA")
        _require_equal(m11.get("macro_f1"), EXPECTED_MACRO_F1, "M11_LIVE_MACRO_F1")
        _require_equal(m11.get("generator_ledger_analyzer_reused"), False, "M11_ANALYZER_REUSED")
        source_ledger = m11.get("source_ledger") or {}
        _require_equal(source_ledger.get("unique_ids"), EXPECTED_ELIGIBLE, "M11_UNIQUE")
        _require_equal(source_ledger.get("models"), EXPECTED_MODELS, "M11_MODELS")
        _require_equal(source_ledger.get("pairs"), EXPECTED_PAIRS, "M11_PAIRS")
        _require_equal(source_ledger.get("duplicates"), 0, "M11_DUP")
        _require_equal(source_ledger.get("missing"), 0, "M11_MISSING")
        _require_equal(source_ledger.get("unexpected"), 0, "M11_UNEXPECTED")
        _require_equal(source_ledger.get("label_mismatches"), 0, "M11_LABEL")
        _require_equal(source_ledger.get("subject_mismatches"), 0, "M11_SUBJECT")
        _require_equal(source_ledger.get("recording_mismatches"), 0, "M11_RECORDING")
    _validate_checksums(closure_dir)

    artifacts = {name: load_json(closure_dir / name) for name in CLOSURE_JSON_FILES}
    for name, payload in artifacts.items():
        _reject_unsafe_paths(payload, context=name)
        if isinstance(payload, dict):
            _reject_forbidden_claims(payload, context=name)
            _require_non_pristine_fields(payload, context=name)

    identity = artifacts["phase_b_closure_identity.json"]
    predecessor = artifacts["predecessor_gate.json"]
    population = artifacts["source_and_population_summary.json"]
    lineage = artifacts["selected_path_lineage.json"]
    candidate = artifacts["locked_candidate_summary.json"]
    evaluation = artifacts["final_evaluation_summary.json"]
    claims = artifacts["claim_boundary.json"]
    readiness = artifacts["release_readiness_manifest.json"]
    handoff = artifacts["device_domain_handoff.json"]
    evidence = artifacts["immutable_evidence_registry.json"]
    summary = artifacts["phase_b_closure_summary.json"]

    m11_dir = root / M_B11_DIR_REL
    m11_identity = load_json(m11_dir / "artifact_lock_identity.json")
    m11_metrics = load_json(m11_dir / "final_metric_lock.json")
    m11_registry = load_json(m11_dir / "final_sample_registry_lock.json")
    m11_history = load_json(m11_dir / "recovery_access_history_lock.json")
    m11_model = load_json(m11_dir / "model_artifact_lock.json")
    m11_source = load_json(m11_dir / "source_lineage_lock.json")
    m11_baselines = load_json(m11_dir / "baseline_comparison_lock.json")

    _require_equal(identity.get("schema_version"), SCHEMA, "SCHEMA")
    _require_equal(identity.get("artifact_status"), ARTIFACT_STATUS, "ARTIFACT_STATUS")
    _require_equal(identity.get("result_limitation"), RESULT_LIMITATION, "RESULT_LIMITATION")
    _require_equal(identity.get("candidate_id"), SELECTED_CANDIDATE_ID, "CANDIDATE_ID")
    _require_equal(identity.get("runtime_model_id"), RUNTIME_MODEL_ID, "RUNTIME_MODEL_ID")
    _require_equal(identity.get("class_map"), CLASS_MAP, "CLASS_MAP")
    if identity.get("m_b12_creates_new_model") is not False:
        _raise("CREATES_NEW_MODEL")
    if identity.get("m_c_started") is not False:
        _raise("M_C_STARTED")
    if identity.get("selected_candidate_changed") is not False:
        _raise("CANDIDATE_CHANGED")

    _require_equal(candidate.get("sha256"), EXPECTED_MODEL_SHA, "CANDIDATE_SHA")
    _require_equal(candidate.get("bytes"), EXPECTED_MODEL_BYTES, "CANDIDATE_BYTES")
    _require_equal(candidate.get("candidate_id"), SELECTED_CANDIDATE_ID, "CANDIDATE_ID")
    _require_equal(candidate.get("seed"), 42, "CANDIDATE_SEED")
    live_model = root / require_repo_relative(SELECTED_TFLITE_REL, context="model")
    _require_equal(_sha256_file(live_model), EXPECTED_MODEL_SHA, "LIVE_MODEL_SHA")
    _require_equal(int(live_model.stat().st_size), EXPECTED_MODEL_BYTES, "LIVE_MODEL_BYTES")
    _require_equal(m11_model.get("sha256"), candidate.get("sha256"), "M11_MODEL_SHA")
    _require_equal(evaluation.get("macro_f1"), EXPECTED_MACRO_F1, "MACRO_F1")
    _require_equal(evaluation.get("macro_f1"), m11_metrics.get("macro_f1"), "M11_MACRO_F1")
    _require_equal(evaluation.get("v0_1_macro_f1"), EXPECTED_V01_F1, "V01_F1")
    _require_equal(evaluation.get("v0_2_macro_f1"), EXPECTED_V02_F1, "V02_F1")
    _require_equal(evaluation.get("v0_1_macro_f1"), m11_baselines["v0_1"]["macro_f1"], "M11_V01")
    _require_equal(evaluation.get("v0_2_macro_f1"), m11_baselines["v0_2"]["macro_f1"], "M11_V02")
    _require_equal(evaluation.get("unique_eligible_window_ids"), EXPECTED_ELIGIBLE, "UNIQUE_IDS")
    _require_equal(evaluation.get("models"), EXPECTED_MODELS, "MODELS")
    _require_equal(evaluation.get("actual_pairs"), EXPECTED_PAIRS, "PAIRS")
    _require_equal(evaluation.get("duplicates"), 0, "DUP")
    _require_equal(evaluation.get("missing"), 0, "MISSING")
    _require_equal(evaluation.get("unexpected"), 0, "UNEXPECTED")
    _require_equal(evaluation.get("cross_model_label_mismatches"), 0, "LABEL")
    _require_equal(evaluation.get("cross_model_subject_mismatches"), 0, "SUBJECT")
    _require_equal(evaluation.get("cross_model_recording_mismatches"), 0, "RECORDING")
    _require_equal(evaluation.get("unique_eligible_window_ids"), m11_registry.get("unique_eligible_window_ids"), "M11_UNIQUE")
    _require_equal(evaluation.get("actual_pairs"), m11_registry.get("actual_pairs"), "M11_PAIRS")
    _require_equal(evaluation.get("cross_model_recording_mismatches"), m11_registry.get("cross_model_recording_mismatches"), "M11_RECORDING")
    _require_equal(evaluation.get("historical_total_payload_releases"), EXPECTED_HISTORICAL_RELEASES, "HIST_TOTAL")
    _require_equal(evaluation.get("recovery_model_inference"), EXPECTED_RECOVERY_INFERENCE, "REC_INFER")
    _require_equal(evaluation.get("historical_total_payload_releases"), m11_history.get("historical_total_payload_releases"), "M11_HIST")
    if evaluation.get("rerun") is not False:
        _raise("RERUN_TRUE")
    if evaluation.get("second_recovery") is not False:
        _raise("SECOND_RECOVERY_TRUE")
    if evaluation.get("inference_rerun_in_m_b12") is not False:
        _raise("M12_INFERENCE_RERUN")
    if evaluation.get("new_model_selection_event") is not False:
        _raise("NEW_SELECTION")
    _require_equal(evaluation.get("confusion_matrix"), m11_metrics.get("confusion_matrix"), "CONFUSION")
    _require_equal(population.get("raw_archive_sha256"), m11_source.get("raw_archive_sha256"), "RAW_SHA")

    required_phases = {
        "M-B0", "M-B1", "M-B2", "M-B3", "M-B4", "M-B5", "M-B6", "M-B7", "M-B8", "M-B9",
        "M-B10A", "M-B10B", "M-B10R0", "M-B10R1-A", "M-B10R1-B",
    }
    selected_path = lineage.get("selected_path") or {}
    missing_phases = sorted(required_phases - set(selected_path))
    if missing_phases:
        _raise(f"LINEAGE_MISSING:{missing_phases}")
    for key in ("A0", "A1", "A2", "A3", "A4", "A5", "A6"):
        if key not in (lineage.get("a_series") or {}):
            _raise(f"A_SERIES_MISSING:{key}")
    if lineage.get("m_b12", {}).get("begins_m_c") is not False:
        _raise("LINEAGE_BEGINS_MC")
    if lineage.get("m_b12", {}).get("creates_git_tag") is not False:
        _raise("LINEAGE_CREATES_TAG")

    if claims.get("phase_b_offline_final_report_complete") is not True:
        _raise("REPORT_INCOMPLETE")
    if claims.get("phase_b_offline_intermediate_release_ready_after_merge") is not True:
        _raise("INTERMEDIATE_READY_FALSE")
    if claims.get("Phase_B_release_ready") is not False:
        _raise("UNQUALIFIED_PHASE_B_RELEASE_TRUE")
    if claims.get("git_tag_created") is not False:
        _raise("GIT_TAG_CREATED")
    if claims.get("github_release_created") is not False:
        _raise("GITHUB_RELEASE_CREATED")
    if claims.get("m_c_started") is not False:
        _raise("CLAIM_MC_STARTED")
    _require_equal(readiness.get("status_label"), STATUS_LABEL, "STATUS_LABEL")
    _require_equal(readiness.get("proposed_release_tag"), PROPOSED_TAG, "PROPOSED_TAG")
    if readiness.get("git_tag_created") is not False or readiness.get("github_release_created") is not False:
        _raise("READINESS_CREATED_RELEASE")
    if readiness.get("do_not_create_tag_or_github_release_in_this_pr") is not True:
        _raise("READINESS_ALLOWS_TAG")
    if handoff.get("m_c_started") is not False:
        _raise("HANDOFF_MC_STARTED")
    if summary.get("new_locked_test_access") != 0 or summary.get("new_recovery_access") != 0:
        _raise("SUMMARY_NEW_ACCESS")
    if summary.get("new_model_inference") != 0:
        _raise("SUMMARY_NEW_INFERENCE")
    _require_equal(predecessor.get("new_locked_test_access"), 0, "PRED_LOCKED")
    _require_equal(predecessor.get("new_model_inference"), 0, "PRED_INFER")
    _require_equal(
        predecessor.get("m_b11_checksums_sha256"),
        _sha256_file(m11_dir / "checksums.sha256"),
        "M11_CHECKSUMS_SHA",
    )

    artifacts_list = evidence.get("artifacts") or []
    if not artifacts_list:
        _raise("EVIDENCE_EMPTY")
    for item in artifacts_list:
        rel = require_repo_relative(str(item.get("repo_relative_path")), context=str(item.get("artifact_role")))
        target = root / rel
        if not target.is_file():
            _raise(f"EVIDENCE_MISSING:{rel}")
        if _sha256_file(target) != item.get("sha256"):
            _raise(f"EVIDENCE_SHA_MISMATCH:{rel}")
        if item.get("immutable") is not True:
            _raise(f"EVIDENCE_NOT_IMMUTABLE:{rel}")

    sensor = load_json(root / SENSOR_LOCK_REL)
    _reject_forbidden_claims(sensor, context="sensor_lock")
    _require_equal(sensor.get("sha256"), EXPECTED_MODEL_SHA, "SENSOR_SHA")
    if sensor.get("deployment_ready") is True:
        _raise("SENSOR_DEPLOYMENT_READY")

    return {
        "status": "PASS",
        "candidate_id": SELECTED_CANDIDATE_ID,
        "model_sha256": EXPECTED_MODEL_SHA,
        "macro_f1": EXPECTED_MACRO_F1,
        "status_label": STATUS_LABEL,
        "result_limitation": RESULT_LIMITATION,
        "phase_b_offline_intermediate_release_ready_after_merge": True,
        "Phase_B_release_ready": False,
        "git_tag_created": False,
        "github_release_created": False,
        "m_c_started": False,
        "new_locked_test_access": 0,
        "new_recovery_access": 0,
        "new_model_inference": 0,
        "source_ledger": {
            "unique_ids": EXPECTED_ELIGIBLE,
            "models": EXPECTED_MODELS,
            "pairs": EXPECTED_PAIRS,
            "duplicates": 0,
            "missing": 0,
            "unexpected": 0,
            "label_mismatches": 0,
            "subject_mismatches": 0,
            "recording_mismatches": 0,
        },
    }


def main() -> int:
    try:
        result = validate_m_b12()
    except MB12ValidationError as exc:
        print(f"M-B12 VALIDATION FAIL: {exc}", file=sys.stderr)
        return 1
    print("M-B12 VALIDATION PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
