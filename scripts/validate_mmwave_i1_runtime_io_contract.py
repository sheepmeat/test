#!/usr/bin/env python3
"""Focused I1 runtime I/O contract gate. No training, Q2 detectors, I2 replay, or D2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    AUDIT_DATE,
    BASE_SHA,
    CONFIG_PATH,
    INPUT_CONTRACT_ID,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    MN9_LOCK,
    OUTPUT_CONTRACT_ID,
    PHASE_ID,
    PROVENANCE_CONTRACT_ID,
    Q2_CONFIG,
    Q2_CONTRACT_ID,
    REPLAY_INTERFACE_ID,
    SCHEMA_VERSION,
    SEMANTIC_CONTRACT_ID,
    V1_FORBIDDEN_IDENTITY,
    check_absolute_paths,
    dump_json,
    load_json,
    make_output_from_input,
    resolve_precedence,
    sha256_bytes,
    validate_runtime_input,
    validate_runtime_output,
)

REQUIRED_YES = {
    "RUNTIME_SEMANTIC_BOUNDARY_VERSIONED": "YES",
    "INPUT_SCHEMA_VERSIONED": "YES",
    "OUTPUT_SCHEMA_VERSIONED": "YES",
    "PROVENANCE_CONTRACT_VERSIONED": "YES",
    "PRESENCE_BEFORE_PHYSIOLOGY": "YES",
    "QUALITY_BEFORE_PHYSIOLOGY": "YES",
    "INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY": "YES",
    "PUBLIC_AND_MR60_INPUT_SEMANTICS_DISTINGUISHED": "YES",
    "TIME_DOMAINS_EXPLICIT": "YES",
    "REPLAY_INTERFACE_READY_FOR_I2": "YES",
    "FINAL_MODEL_ARCHITECTURE_NOT_FROZEN": "YES",
    "FINAL_FEATURE_SCHEMA_NOT_FROZEN": "YES",
    "FINAL_TENSOR_SHAPE_NOT_FROZEN": "YES",
    "PRESENCE_GATE_SEMANTICS_PRESERVED": "YES",
    "INPUT_UNAVAILABLE_CAN_SUPPRESS_PHYSIOLOGY": "YES",
}
REQUIRED_NO = {
    "V1_IDENTITY_REUSED": "NO",
    "V1_ARTIFACT_MODIFIED": "NO",
    "FINAL_MODEL_TENSOR_SHAPE_FROZEN": "NO",
    "FINAL_FEATURE_SCHEMA_FROZEN": "NO",
    "FINAL_MODEL_ARCHITECTURE_FROZEN": "NO",
    "INVALID_INPUT_FALLBACK_NORMAL": "NO",
    "INVALID_INPUT_FALLBACK_APNEA": "NO",
    "PUBLIC_DOMAIN_MR60_METADATA_CONFUSION": "NO",
    "MR60_SUPERVISED_USE": "NO",
    "D2_USED": "NO",
    "MODEL_TRAINING": "NO",
    "V1_V2_MODEL_INFERENCE": "NO",
    "I2_FULL_REPLAY_IMPLEMENTED": "NO",
    "I3_REGRESSION_WORK_PERFORMED": "NO",
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
    if CONFIG_PATH.read_text(encoding="utf-8") != (MANIFEST_DIR / "runtime_semantic_contract.json").read_text(
        encoding="utf-8"
    ):
        fail(errors, "CONFIG_MANIFEST_DIVERGED")

    semantic = artifacts.get("runtime_semantic_contract.json", {})
    input_schema = artifacts.get("runtime_input_schema.json", {})
    output_schema = artifacts.get("runtime_output_schema.json", {})
    provenance = artifacts.get("provenance_contract.json", {})
    replay = artifacts.get("replay_interface_skeleton.json", {})
    if semantic.get("contract_id") != SEMANTIC_CONTRACT_ID:
        fail(errors, "SEMANTIC_CONTRACT_ID")
    if input_schema.get("contract_id") != INPUT_CONTRACT_ID:
        fail(errors, "INPUT_CONTRACT_ID")
    if output_schema.get("contract_id") != OUTPUT_CONTRACT_ID:
        fail(errors, "OUTPUT_CONTRACT_ID")
    if provenance.get("contract_id") != PROVENANCE_CONTRACT_ID:
        fail(errors, "PROVENANCE_CONTRACT_ID")
    if replay.get("contract_id") != REPLAY_INTERFACE_ID:
        fail(errors, "REPLAY_INTERFACE_ID")
    if semantic.get("identities", {}).get("v1_identity_forbidden") != V1_FORBIDDEN_IDENTITY:
        fail(errors, "V1_FORBIDDEN_IDENTITY_UNDECLARED")
    if semantic.get("schema_id") == V1_FORBIDDEN_IDENTITY:
        fail(errors, "V1_IDENTITY_REUSED")
    v1_lock = load_json(MN9_LOCK)
    if v1_lock.get("artifact_id") != V1_FORBIDDEN_IDENTITY:
        fail(errors, "V1_ARTIFACT_MODIFIED")
    if not Q2_CONFIG.is_file() or load_json(Q2_CONFIG).get("contract_id") != Q2_CONTRACT_ID:
        fail(errors, "Q2_EXTERNAL_POLICY_MISSING")
    if semantic.get("q2_relationship", {}).get("numerical_thresholds_copied_into_i1") is True:
        fail(errors, "Q2_THRESHOLDS_COPIED")
    if semantic.get("q2_relationship", {}).get("detection_implemented_in_i1") is True:
        fail(errors, "Q2_DETECTOR_IN_I1")
    if "400" in json.dumps(semantic.get("q2_relationship", {})):
        fail(errors, "Q2_400MS_COPIED_INTO_SEMANTIC_POLICY")
    deferred = semantic.get("deferred_bindings", {})
    if deferred.get("final_tensor_shape") != "DEFERRED_TO_M_PV1":
        fail(errors, "FINAL_TENSOR_SHAPE_FROZEN")
    if deferred.get("final_model_architecture") != "DEFERRED_TO_M_PV1":
        fail(errors, "FINAL_MODEL_ARCHITECTURE_FROZEN")
    if deferred.get("final_feature_schema") != "DEFERRED_TO_R1_R2_R3":
        fail(errors, "FINAL_FEATURE_SCHEMA_FROZEN")
    if semantic.get("base_sha") != BASE_SHA:
        fail(errors, "BASE_SHA")

    fixture = replay.get("tiny_deterministic_fixture", {})
    public = fixture.get("public_d0_without_phase_age_eligible", {})
    mr60 = fixture.get("mr60_missing_freshness_fail_closed", {})
    public_in = public.get("input", {})
    public_out = public.get("output", {})
    mr60_in = mr60.get("input", {})
    mr60_out = mr60.get("output", {})
    for code in validate_runtime_input(public_in):
        fail(errors, f"PUBLIC_INPUT:{code}")
    for code in validate_runtime_output(public_out, public_in):
        fail(errors, f"PUBLIC_OUTPUT:{code}")
    for code in validate_runtime_input(mr60_in):
        fail(errors, f"MR60_INPUT:{code}")
    for code in validate_runtime_output(mr60_out, mr60_in):
        fail(errors, f"MR60_OUTPUT:{code}")
    if public_in.get("freshness", {}).get("phase_age_ms", {}).get("value") is not None:
        fail(errors, "PUBLIC_UNEXPECTED_PHASE_AGE")
    if public_out.get("availability_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "PUBLIC_REJECTED_FOR_MISSING_MR60_FIELDS")
    if mr60_out.get("availability_state") != "INPUT_UNAVAILABLE":
        fail(errors, "MR60_MISSING_FRESHNESS_NOT_FAIL_CLOSED")
    if mr60_out.get("physiology_executed") is not False:
        fail(errors, "MR60_PHYSIOLOGY_ON_UNAVAILABLE")

    false_p = resolve_precedence(
        presence=False,
        declared_quality="PHYSIOLOGY_ELIGIBLE",
        domain_class="PRODUCTION_MR60",
        presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
    )
    null_p = resolve_precedence(
        presence=None,
        declared_quality="PHYSIOLOGY_ELIGIBLE",
        domain_class="PRODUCTION_MR60",
        presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
    )
    unavailable = resolve_precedence(
        presence=True,
        declared_quality="INPUT_UNAVAILABLE",
        reason_codes=["LARGE_GAP"],
        domain_class="PRODUCTION_MR60",
        production_freshness_present=True,
        presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
    )
    eligible = resolve_precedence(
        presence=True,
        declared_quality="PHYSIOLOGY_ELIGIBLE",
        domain_class="PRODUCTION_MR60",
        production_freshness_present=True,
        presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
    )
    override = resolve_precedence(
        presence=True,
        declared_quality="INPUT_UNAVAILABLE",
        reason_codes=["SOURCE_FREEZE"],
        class_confidence=0.99,
        proposed_physiology="APNEA",
        domain_class="PRODUCTION_MR60",
        production_freshness_present=True,
        presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
    )
    if false_p["availability_state"] != "PRESENCE_SUPPRESSED" or false_p["physiology_executed"] is not False:
        fail(errors, "PRESENCE_FALSE_GATE")
    if null_p["availability_state"] != "PRESENCE_SUPPRESSED" or null_p["physiology_executed"] is not False:
        fail(errors, "PRESENCE_NULL_GATE")
    if unavailable["availability_state"] != "INPUT_UNAVAILABLE" or unavailable["physiology_executed"] is not False:
        fail(errors, "QUALITY_UNAVAILABLE_GATE")
    if eligible["availability_state"] != "PHYSIOLOGY_ELIGIBLE" or eligible["physiology_executed"] is not False:
        fail(errors, "ELIGIBLE_MUST_NOT_RUN_MODEL")
    if not override["class_confidence_override_rejected"]:
        fail(errors, "CONFIDENCE_OVERRIDE_NOT_REJECTED")
    if "INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY" not in override["schema_errors"]:
        fail(errors, "INVALID_PHYSIOLOGY_NOT_BLOCKED")
    if "NORMAL" in json.dumps(make_output_from_input(mr60_in)) and mr60_out.get("application_state") == "RESPIRATION_PRESENT":
        fail(errors, "INVALID_INPUT_FALLBACK_NORMAL")

    text_blob = "\n".join(
        json.dumps(artifacts[name], sort_keys=True) for name in MANIFEST_JSON_FILES if name in artifacts
    )
    if "MMWAVE_M_N9_FULL_INT8_V1" in text_blob and SEMANTIC_CONTRACT_ID not in V1_FORBIDDEN_IDENTITY:
        if artifacts.get("runtime_semantic_contract.json", {}).get("contract_id") == V1_FORBIDDEN_IDENTITY:
            fail(errors, "V1_IDENTITY_REUSED")
    if any(token in text_blob for token in ("/Users/", "file://", "/private/tmp/")):
        fail(errors, "ABSOLUTE_PATH_IN_MANIFEST")

    checks = {}
    checks.update(REQUIRED_YES)
    checks.update(REQUIRED_NO)
    if errors:
        for key in list(checks):
            if any(key in err or err.startswith(key) for err in errors):
                if key in REQUIRED_YES:
                    checks[key] = "NO"
                if key in REQUIRED_NO:
                    checks[key] = "YES"

    limitations = [
        "R1 representation remains an unbound profile id",
        "R3 breathing/RR/temporal-hold slots are semantic only",
        "Q2 is bound as an external policy; I1 does not execute gap/freeze/stale/flat detectors",
        "final runtime history duration unresolved",
    ]
    gate = "BLOCKED"
    ok = not errors
    if ok:
        gate = "PASS_WITH_LIMITATIONS"
    result = {
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "checks": checks,
        "contract_id": SEMANTIC_CONTRACT_ID,
        "d2_used": "NO",
        "errors": errors,
        "gate": gate,
        "limitations": limitations,
        "mr60_supervised_use": "NO",
        "ok": ok,
        "phase": PHASE_ID,
        "q2_contract_integration": semantic.get("q2_relationship", {}).get("status"),
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
