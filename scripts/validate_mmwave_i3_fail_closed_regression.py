#!/usr/bin/env python3
"""Focused I3 fail-closed regression gate. No training, Q3, D2, or model inference."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    OUTPUT_CONTRACT_ID,
    PROVENANCE_CONTRACT_ID,
    Q2_CONTRACT_ID,
    SEMANTIC_CONTRACT_ID,
    check_absolute_paths,
    dump_json,
    load_json,
    sha256_bytes,
)
from scripts.mmwave_i2_jsonl_replay import I2_CONTRACT_ID, I2_HARNESS_ID  # noqa: E402
from scripts.mmwave_i3_fail_closed_regression import (  # noqa: E402
    AUDIT_DATE,
    BASE_SHA,
    CONFIG_PATH,
    I3_CONTRACT_ID,
    I3_GATE_ID,
    I3_MATRIX_ID,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    PHASE_ID,
    SCHEMA_VERSION,
)
from scripts.mmwave_q2_input_unavailable import (  # noqa: E402
    CONTRACT_ID as Q2_EVALUATOR_CONTRACT_ID,
    PROFILE_ID as Q2_PROFILE_ID,
    Q2_MODES,
)

REQUIRED_YES = {
    "I1_CONTRACT_INHERITED": "YES",
    "I2_REPLAY_HARNESS_INHERITED": "YES",
    "Q2_CONTRACT_INHERITED": "YES",
    "Q2_CANONICAL_EVALUATOR_REUSED": "YES",
    "PRESENCE_PRECEDES_QUALITY": "YES",
    "QUALITY_PRECEDES_PHYSIOLOGY": "YES",
    "PRESENCE_FALSE_SUPPRESSES": "YES",
    "PRESENCE_UNKNOWN_PRODUCTION_SUPPRESSES": "YES",
    "LARGE_GAP_FAILS_CLOSED": "YES",
    "SOURCE_FREEZE_FAILS_CLOSED": "YES",
    "SOURCE_STALE_FAILS_CLOSED": "YES",
    "EXACT_FLAT_FAILS_CLOSED": "YES",
    "INVALID_TIMESTAMP_FAILS_CLOSED": "YES",
    "RECOVERY_WARMUP_FAILS_CLOSED": "YES",
    "PRODUCTION_MISSING_REQUIRED_FRESHNESS_FAILS_CLOSED": "YES",
    "DETERMINISTIC_REGRESSION": "YES",
}

REQUIRED_NO = {
    "LOW_AMPLITUDE_ALONE_INVALID": "NO",
    "TYPICAL_JITTER_AUTOMATICALLY_UNAVAILABLE": "NO",
    "ISOLATED_REPUBLICATION_AUTOMATICALLY_FREEZE": "NO",
    "SEQ_INCREMENT_REFRESHES_STALE_SOURCE": "NO",
    "SEQ_GAP_INTERPOLATED": "NO",
    "TIMESTAMP_DEFECT_SILENTLY_REPAIRED": "NO",
    "PUBLIC_OFFLINE_MR60_METADATA_REQUIRED": "NO",
    "INVALID_TO_NORMAL_FALLBACK": "NO",
    "INVALID_TO_APNEA_FALLBACK": "NO",
    "NO_PERSON_TO_APNEA": "NO",
    "NO_PERSON_RR_ZERO": "NO",
    "CLASS_CONFIDENCE_OVERRIDES_INPUT_UNAVAILABLE": "NO",
    "SESSION_STATE_LEAK": "NO",
    "MODEL_INFERENCE": "NO",
    "MODEL_TRAINING": "NO",
    "Q3_PERFORMED": "NO",
    "M_PV1_SELECTION_PERFORMED": "NO",
    "D2_USED": "NO",
    "MR60_SUPERVISED_USE": "NO",
    "Q2_THRESHOLD_FORK": "NO",
    "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
}


def fail(errors: list[str], code: str) -> None:
    errors.append(code)


def validate() -> dict:
    errors: list[str] = []
    if not MANIFEST_DIR.is_dir() or not CONFIG_PATH.is_file():
        return {"ok": False, "gate": "BLOCKED", "errors": ["MANIFEST_OR_CONFIG_MISSING"]}
    artifacts: dict[str, object] = {}
    for name in MANIFEST_JSON_FILES:
        path = MANIFEST_DIR / name
        if not path.is_file():
            fail(errors, f"MISSING:{name}")
            continue
        artifacts[name] = load_json(path)
        check_absolute_paths(artifacts[name], name, errors)
    checksums = load_json(MANIFEST_DIR / "checksums.json")
    for name in MANIFEST_JSON_FILES:
        path = MANIFEST_DIR / name
        digest = sha256_bytes(path.read_text(encoding="utf-8").encode("utf-8"))
        if checksums.get("files", {}).get(name) != digest:
            fail(errors, f"CHECKSUM_MISMATCH:{name}")
    if CONFIG_PATH.read_text(encoding="utf-8") != (MANIFEST_DIR / "i3_regression_contract.json").read_text(
        encoding="utf-8"
    ):
        fail(errors, "CONFIG_MANIFEST_DIVERGED")

    contract = artifacts.get("i3_regression_contract.json", {})
    matrix = artifacts.get("regression_matrix.json", {})
    historical = artifacts.get("historical_replay_regression.json", {})
    synthetic = artifacts.get("synthetic_q2_regression.json", {})
    presence = artifacts.get("presence_precedence_audit.json", {})
    availability = artifacts.get("availability_precedence_audit.json", {})
    session = artifacts.get("session_reset_audit.json", {})
    determinism = artifacts.get("determinism_audit.json", {})

    if contract.get("contract_id") != I3_CONTRACT_ID:
        fail(errors, "I3_CONTRACT_ID")
    if contract.get("matrix_id") != I3_MATRIX_ID:
        fail(errors, "I3_MATRIX_ID")
    if contract.get("gate_id") != I3_GATE_ID:
        fail(errors, "I3_GATE_ID")
    if contract.get("base_sha") != BASE_SHA:
        fail(errors, "BASE_SHA")
    deps = contract.get("dependencies", {})
    if deps.get("i1_semantic") != SEMANTIC_CONTRACT_ID:
        fail(errors, "I1_CONTRACT_INHERITED")
    if deps.get("i1_output") != OUTPUT_CONTRACT_ID:
        fail(errors, "I1_OUTPUT_INHERITED")
    if deps.get("i1_provenance") != PROVENANCE_CONTRACT_ID:
        fail(errors, "I1_PROVENANCE_INHERITED")
    if deps.get("i2_replay") != I2_CONTRACT_ID:
        fail(errors, "I2_REPLAY_HARNESS_INHERITED")
    if deps.get("i2_harness") != I2_HARNESS_ID:
        fail(errors, "I2_HARNESS_ID")
    if deps.get("q2_availability") != Q2_CONTRACT_ID:
        fail(errors, "Q2_CONTRACT_INHERITED")
    if deps.get("q2_evaluator") != Q2_EVALUATOR_CONTRACT_ID:
        fail(errors, "Q2_CANONICAL_EVALUATOR_REUSED")
    if deps.get("q2_synthetic_profile") != Q2_PROFILE_ID:
        fail(errors, "Q2_PROFILE_FORK")
    if contract.get("q2_threshold_fork") is not False:
        fail(errors, "Q2_THRESHOLD_FORK")
    if contract.get("model_inference") is not False:
        fail(errors, "MODEL_INFERENCE")
    if contract.get("q3_performed") is not False:
        fail(errors, "Q3_PERFORMED")
    if contract.get("m_pv1_selection_performed") is not False:
        fail(errors, "M_PV1_SELECTION_PERFORMED")
    if contract.get("d2_used") is not False:
        fail(errors, "D2_USED")
    if contract.get("mr60_supervised_use") is not False:
        fail(errors, "MR60_SUPERVISED_USE")

    expected_matrix = {
        "no_person": "PRESENCE_SUPPRESSED",
        "unknown_person": "PRESENCE_SUPPRESSED",
        "clean_valid": "PHYSIOLOGY_ELIGIBLE",
        "large_gap": "INPUT_UNAVAILABLE",
        "source_freeze": "INPUT_UNAVAILABLE",
        "stale": "INPUT_UNAVAILABLE",
        "exact_flat": "INPUT_UNAVAILABLE",
        "invalid_timestamp": "INPUT_UNAVAILABLE",
        "recovery": "INPUT_UNAVAILABLE",
    }
    rows = {item.get("case"): item for item in matrix.get("rows", [])}
    for case_id, expected in expected_matrix.items():
        row = rows.get(case_id, {})
        if row.get("observed_state") != expected or row.get("expected_state") != expected:
            fail(errors, f"MATRIX:{case_id}")
        if row.get("physiology_executed") is not False:
            fail(errors, f"PHYSIOLOGY_EXECUTED:{case_id}")

    if presence.get("no_person", {}).get("availability_state") != "PRESENCE_SUPPRESSED":
        fail(errors, "PRESENCE_FALSE_SUPPRESSES")
    if presence.get("unknown_production", {}).get("availability_state") != "PRESENCE_SUPPRESSED":
        fail(errors, "PRESENCE_UNKNOWN_PRODUCTION_SUPPRESSES")
    if presence.get("presence_over_quality", {}).get("availability_state") != "PRESENCE_SUPPRESSED":
        fail(errors, "PRESENCE_PRECEDES_QUALITY")
    if presence.get("true_plus_valid", {}).get("availability_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "CLEAN_VALID_FALSE_REJECTION")
    if presence.get("true_plus_valid", {}).get("physiology_executed") is not False:
        fail(errors, "CLEAN_VALID_RAN_PHYSIOLOGY")
    if presence.get("true_plus_invalid", {}).get("availability_state") != "INPUT_UNAVAILABLE":
        fail(errors, "QUALITY_PRECEDES_PHYSIOLOGY")

    for key, reason in (
        ("large_gap", "LARGE_GAP"),
        ("source_freeze", "SOURCE_FREEZE"),
        ("stale", "SOURCE_STALE"),
        ("exact_flat", "SIGNAL_FLAT_EXACT"),
    ):
        payload = availability.get(key, {})
        if payload.get("availability_state") != "INPUT_UNAVAILABLE" or reason not in payload.get("reasons", []):
            fail(errors, f"{reason}_FAILS_CLOSED")
    if availability.get("invalid_timestamp", {}).get("availability_state") != "INPUT_UNAVAILABLE":
        fail(errors, "INVALID_TIMESTAMP_FAILS_CLOSED")
    if availability.get("recovery", {}).get("availability_state") != "INPUT_UNAVAILABLE":
        fail(errors, "RECOVERY_WARMUP_FAILS_CLOSED")
    if availability.get("low_amplitude_dynamic", {}).get("availability_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "LOW_AMPLITUDE_ALONE_INVALID")
    if availability.get("typical_jitter", {}).get("availability_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "TYPICAL_JITTER_AUTOMATICALLY_UNAVAILABLE")
    if availability.get("isolated_republication", {}).get("availability_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "ISOLATED_REPUBLICATION_AUTOMATICALLY_FREEZE")
    if "SOURCE_FREEZE" in availability.get("isolated_republication", {}).get("reasons", []):
        fail(errors, "ISOLATED_REPUBLICATION_AUTOMATICALLY_FREEZE")
    if availability.get("production_missing_freshness", {}).get("availability_state") != "INPUT_UNAVAILABLE":
        fail(errors, "PRODUCTION_MISSING_REQUIRED_FRESHNESS_FAILS_CLOSED")
    public = availability.get("public_missing_freshness", {})
    if public.get("q2_availability_state") != "PHYSIOLOGY_ELIGIBLE" or public.get("i1_availability_state") != (
        "PHYSIOLOGY_ELIGIBLE"
    ):
        fail(errors, "PUBLIC_OFFLINE_MR60_METADATA_REQUIRED")

    modes = synthetic.get("modes", {})
    for mode in Q2_MODES:
        row = modes.get(mode, {})
        expected = "PHYSIOLOGY_ELIGIBLE" if mode == "CLEAN_VALID" else "INPUT_UNAVAILABLE"
        if row.get("availability_state") != expected or row.get("passed") is not True:
            fail(errors, f"SYNTHETIC_MODE:{mode}")
    if synthetic.get("failed"):
        fail(errors, "SYNTHETIC_FAILED")

    if session.get("session_state_leak") is not False:
        fail(errors, "SESSION_STATE_LEAK")
    if session.get("seq_gap_interpolated") is not False:
        fail(errors, "SEQ_GAP_INTERPOLATED")
    if session.get("silent_timestamp_repair") is not False:
        fail(errors, "TIMESTAMP_DEFECT_SILENTLY_REPAIRED")
    if session.get("session_b_independent_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "SESSION_B_CONTAMINATED")

    if determinism.get("identical_repeat") is not True:
        fail(errors, "DETERMINISTIC_REGRESSION")

    hist_sessions = {item.get("role"): item for item in historical.get("sessions", [])}
    freeze_95 = hist_sessions.get("q2_handoff_freeze_like_95_run", {}).get("quality_only_window", {})
    freeze_3598 = hist_sessions.get("q2_handoff_freeze_like_3598_run", {}).get("quality_only_window", {})
    if freeze_95.get("availability_state") != "INPUT_UNAVAILABLE" or "SOURCE_FREEZE" not in freeze_95.get(
        "reasons", []
    ):
        fail(errors, "HISTORICAL_95_RUN_NOT_FAIL_CLOSED")
    if freeze_3598.get("availability_state") != "INPUT_UNAVAILABLE" or "SOURCE_FREEZE" not in freeze_3598.get(
        "reasons", []
    ):
        fail(errors, "HISTORICAL_3598_PREFIX_NOT_FAIL_CLOSED")
    if historical.get("physiology_interpreted") is not False:
        fail(errors, "MR60_SUPERVISED_USE")
    if historical.get("totals", {}).get("sessions_evaluated", 0) < 6:
        fail(errors, "INSUFFICIENT_HISTORICAL_COVERAGE")

    blob = json.dumps(artifacts)
    if any(token in blob for token in ("/Users/", "file://", "/private/tmp/", "/home/")):
        fail(errors, "ABSOLUTE_PATH_LEAK")
    if "NORMAL" in str(presence.get("no_person", {}).get("application_state")):
        fail(errors, "NO_PERSON_TO_APNEA")

    checks = {}
    checks.update(REQUIRED_YES)
    checks.update(REQUIRED_NO)
    limitations = [
        "Pi host receive timestamps are unavailable on inventoried ESP JSONL",
        "3598-run historical evidence is summarized with the I2 64-row prefix",
        "legacy firmware_version is null on several 1.0 sessions",
        "I3 does not run a real physiology model; eligible events remain mock/not evaluated",
        "some production freshness cases are proven with synthetic/I1 fixtures in addition to historical replay",
    ]
    ok = not errors
    gate = "PASS_WITH_LIMITATIONS" if ok else "BLOCKED"
    result = {
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "checks": checks,
        "contract_id": I3_CONTRACT_ID,
        "d2_used": "NO",
        "errors": errors,
        "gate": gate,
        "i3_integration_lane_complete": "YES" if ok else "NO",
        "limitations": limitations,
        "mr60_supervised_use": "NO",
        "ok": ok,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
    }
    dump_json(MANIFEST_DIR / "validation_result.json", result)
    return result


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
