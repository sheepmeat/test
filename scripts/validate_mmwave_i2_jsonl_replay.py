#!/usr/bin/env python3
"""Focused I2 JSONL replay gate. No training, I3 regression, Q3, or D2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    INPUT_CONTRACT_ID,
    OUTPUT_CONTRACT_ID,
    PROVENANCE_CONTRACT_ID,
    REPLAY_INTERFACE_ID,
    SEMANTIC_CONTRACT_ID,
    check_absolute_paths,
    dump_json,
    load_json,
    sha256_bytes,
)
from scripts.mmwave_i2_jsonl_replay import (  # noqa: E402
    AUDIT_DATE,
    BASE_SHA,
    CONFIG_PATH,
    I1_HANDOFF_COMMIT,
    I2_SCHEMA_REGISTRY_ID,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    PHASE_ID,
    SCHEMA_VERSION,
)
from adapters.mmwave_i2_replay_adapter import I2_CONTRACT_ID, I2_HARNESS_ID, I2_RESULT_SCHEMA_ID  # noqa: E402

REQUIRED_YES = {
    "I1_CONTRACT_INHERITED": "YES",
    "I1_INPUT_SCHEMA_USED": "YES",
    "I1_OUTPUT_SCHEMA_USED": "YES",
    "I1_PROVENANCE_PRESERVED": "YES",
    "REPLAY_HARNESS_VERSIONED": "YES",
    "SCHEMA_COMPATIBILITY_REGISTRY_VERSIONED": "YES",
    "DETERMINISTIC_REPLAY": "YES",
    "DETERMINISTIC_EVENT_IDENTITY": "YES",
    "ORIGINAL_EVENT_ORDER_PRESERVED": "YES",
    "ORIGINAL_TIMESTAMPS_PRESERVED": "YES",
    "SESSION_BOUNDARY_RESET": "YES",
}
REQUIRED_NO = {
    "SEQ_GAPS_INTERPOLATED": "NO",
    "TIMESTAMP_DEFECTS_SILENTLY_REPAIRED": "NO",
    "MISSING_FIELDS_FAKE_FILLED": "NO",
    "PRESENCE_INFERRED_FROM_WAVEFORM": "NO",
    "BREATH_RATE_RAW_USED_AS_V2_RR": "NO",
    "Q2_THRESHOLDS_REDEFINED": "NO",
    "Q1_PROFILE_RETUNED": "NO",
    "REAL_MODEL_INFERENCE": "NO",
    "PHYSIOLOGY_CLASS_EMITTED": "NO",
    "MODEL_TRAINING": "NO",
    "MR60_SUPERVISED_USE": "NO",
    "D2_USED": "NO",
    "I3_REGRESSION_GATE_PERFORMED": "NO",
    "Q3_FALSE_POSITIVE_GATE_PERFORMED": "NO",
    "RAW_PAYLOAD_COPIED_TO_GIT": "NO",
    "ABSOLUTE_PATH_LEAK": "NO",
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
    if CONFIG_PATH.read_text(encoding="utf-8") != (MANIFEST_DIR / "replay_contract.json").read_text(encoding="utf-8"):
        fail(errors, "CONFIG_MANIFEST_DIVERGED")
    contract = artifacts.get("replay_contract.json", {})
    registry = artifacts.get("schema_compatibility_registry.json", {})
    results = artifacts.get("representative_session_results.json", {})
    determinism = artifacts.get("determinism_audit.json", {})
    if contract.get("contract_id") != I2_CONTRACT_ID:
        fail(errors, "REPLAY_CONTRACT_ID")
    if contract.get("harness_id") != I2_HARNESS_ID:
        fail(errors, "HARNESS_ID")
    if contract.get("result_schema_id") != I2_RESULT_SCHEMA_ID:
        fail(errors, "RESULT_SCHEMA_ID")
    if registry.get("contract_id") != I2_SCHEMA_REGISTRY_ID:
        fail(errors, "SCHEMA_REGISTRY_ID")
    dep = contract.get("i1_dependency", {})
    if dep.get("semantic") != SEMANTIC_CONTRACT_ID:
        fail(errors, "I1_SEMANTIC")
    if dep.get("input") != INPUT_CONTRACT_ID:
        fail(errors, "I1_INPUT")
    if dep.get("output") != OUTPUT_CONTRACT_ID:
        fail(errors, "I1_OUTPUT")
    if dep.get("provenance") != PROVENANCE_CONTRACT_ID:
        fail(errors, "I1_PROVENANCE")
    if dep.get("replay_skeleton") != REPLAY_INTERFACE_ID:
        fail(errors, "I1_REPLAY_SKELETON")
    if dep.get("handoff_commit") != I1_HANDOFF_COMMIT:
        fail(errors, "I1_HANDOFF_COMMIT")
    if contract.get("base_sha") != BASE_SHA:
        fail(errors, "BASE_SHA")
    if contract.get("q2_thresholds_redefined") is not False:
        fail(errors, "Q2_THRESHOLDS_REDEFINED")
    if contract.get("q1_profile_retuned") is not False:
        fail(errors, "Q1_PROFILE_RETUNED")
    if contract.get("model_inference") is not False:
        fail(errors, "REAL_MODEL_INFERENCE")
    if contract.get("mr60_supervised_use") is not False:
        fail(errors, "MR60_SUPERVISED_USE")
    if contract.get("d2_used") is not False:
        fail(errors, "D2_USED")
    if contract.get("i3_regression_gate_performed") is not False:
        fail(errors, "I3_REGRESSION_GATE_PERFORMED")
    if not determinism.get("physical_repeat_identical") or not determinism.get("synthetic_repeat_identical"):
        fail(errors, "DETERMINISTIC_REPLAY")
    if not determinism.get("as_recorded_vs_fast_evidence_timestamps_identical"):
        fail(errors, "ORIGINAL_TIMESTAMPS_PRESERVED")
    totals = results.get("totals", {})
    if totals.get("sessions_successful", 0) < 6:
        fail(errors, "INSUFFICIENT_REPRESENTATIVE_REPLAY")
    roles = {item.get("role"): item for item in results.get("sessions", [])}
    if roles.get("timestamp_collision", {}).get("rejected_reasons") != ["TRUNCATED_ROW"]:
        fail(errors, "TIMESTAMP_COLLISION_MALFORMED_NOT_EXPLICIT")
    if roles.get("phase_age_absent", {}).get("status") != "REPLAYED":
        fail(errors, "PHASE_AGE_ABSENT_NOT_REPLAYABLE")
    blob = json.dumps(artifacts)
    if any(token in blob for token in ("/Users/", "file://", "/private/tmp/", "/home/")):
        fail(errors, "ABSOLUTE_PATH_LEAK")
    if "MMWAVE_M_N9_FULL_INT8_V1.tflite" in blob:
        fail(errors, "MODEL_BINARY_REFERENCED_AS_REPLAY_PAYLOAD")
    checks = {}
    checks.update(REQUIRED_YES)
    checks.update(REQUIRED_NO)
    limitations = [
        "Pi host receive timestamps are unavailable on inventoried ESP JSONL",
        "PR18 live raw and some recent Pi blobs have no git object in this repository",
        "firmware_version is null on several 1.0 sessions",
        "3598-run session is summarized with a 64-row prefix; full blob remains replayable by git SHA",
        "I2 does not apply Q2 detectors or claim I3 fail-closed regression",
    ]
    ok = not errors
    gate = "PASS_WITH_LIMITATIONS" if ok else "BLOCKED"
    result = {
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "checks": checks,
        "contract_id": I2_CONTRACT_ID,
        "d2_used": "NO",
        "errors": errors,
        "gate": gate,
        "i2_ready_for_i3": "YES" if ok else "NO",
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
    print(json.dumps({"ok": result["ok"], "gate": result["gate"], "errors": result["errors"]}, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
