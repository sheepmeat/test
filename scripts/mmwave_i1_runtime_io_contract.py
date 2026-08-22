#!/usr/bin/env python3
"""I1 V2 runtime semantic I/O contract skeleton.

Freezes the machine-readable boundary between sensor/native adapter output,
future V2 preprocessing/model, and runtime/application output. Does not train,
does not choose R1/R2/R3 features, does not implement Q2 detectors, and does
not run a full I2 replay harness.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_ID = "I1"
SCHEMA_VERSION = "I1.1"
AUDIT_DATE = "2026-08-22"
BASE_SHA = "03b0f4c3b5bcff3f066eaf3f29a43d4889ad24b9"

SEMANTIC_CONTRACT_ID = "MMWAVE_V2_I1_RUNTIME_SEMANTIC_CONTRACT_V1"
INPUT_CONTRACT_ID = "MMWAVE_V2_I1_RUNTIME_INPUT_CONTRACT_V1"
OUTPUT_CONTRACT_ID = "MMWAVE_V2_I1_RUNTIME_OUTPUT_CONTRACT_V1"
PROVENANCE_CONTRACT_ID = "MMWAVE_V2_I1_PROVENANCE_CONTRACT_V1"
REPLAY_INTERFACE_ID = "MMWAVE_V2_I1_REPLAY_INTERFACE_SKELETON_V1"
Q2_CONTRACT_ID = "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1"
V1_FORBIDDEN_IDENTITY = "MMWAVE_M_N9_FULL_INT8_V1"

CONFIG_PATH = ROOT / "config/mmwave/i1_runtime_semantic_contract.json"
MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_I1_runtime_io_contract"
MN9_LOCK = ROOT / "config/mmwave/m_n9_full_int8_artifact_lock.json"
Q2_CONFIG = ROOT / "config/mmwave/q2_input_availability_contract.json"

AVAILABILITY_STATES = (
    "PRESENCE_SUPPRESSED",
    "INPUT_UNAVAILABLE",
    "PHYSIOLOGY_ELIGIBLE",
)
OUTPUT_AVAILABILITY_STATES = AVAILABILITY_STATES + ("NOT_EVALUATED",)
COMPONENT_STATUSES = ("available", "unavailable", "not_evaluated")
APPLICATION_STATES = (
    "PRESENCE_SUPPRESSED",
    "INPUT_UNAVAILABLE",
    "RESPIRATION_PRESENT",
    "ABNORMAL_RR",
    "APNEA_PROXY_CANDIDATE",
    "NOT_EVALUATED",
)
DOMAIN_CLASSES = (
    "PRODUCTION_MR60",
    "PUBLIC_OFFLINE",
    "SYNTHETIC_CORRUPTION",
)
TIME_ROLES = (
    "source_native_sample_time",
    "source_update_estimate",
    "transport_publish_time",
    "runtime_receive_time",
    "window_start",
    "window_end",
    "model_evaluation_time",
)
CARRYABLE_REASON_CODES = (
    "PRESENCE_NOT_CONFIRMED",
    "LARGE_GAP",
    "SOURCE_FREEZE",
    "SOURCE_STALE",
    "SIGNAL_FLAT_EXACT",
    "TIMESTAMP_INVALID",
    "TIMESTAMP_NON_MONOTONIC",
    "TIMESTAMP_UNRESOLVED",
    "INSUFFICIENT_INTERVAL_HISTORY",
    "RECOVERY_WARMUP",
    "EXTERNAL_QUALITY_POLICY",
    "NOT_IMPLEMENTED_MODEL_BOUNDARY",
)
PHYSIOLOGY_LABELS = ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA", "APNEA_PROXY")
ABSOLUTE_PATH_RE = re.compile(
    r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)"
)
MANIFEST_JSON_FILES = (
    "runtime_semantic_contract.json",
    "runtime_input_schema.json",
    "runtime_output_schema.json",
    "provenance_contract.json",
    "replay_interface_skeleton.json",
    "exception_registry.json",
)


class I1ContractError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dump_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def check_absolute_paths(obj: object, trail: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            check_absolute_paths(value, f"{trail}.{key}", errors)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            check_absolute_paths(value, f"{trail}[{idx}]", errors)
    elif isinstance(obj, str) and ABSOLUTE_PATH_RE.search(obj):
        errors.append(f"ABSOLUTE_PATH:{trail}")


def timestamp_descriptor(
    *,
    clock_domain: str,
    unit: str,
    monotonic_or_wall: str,
    reconstructed: bool,
    authoritative: bool,
    value: Any = None,
    notes: str | None = None,
) -> dict[str, Any]:
    payload = {
        "authoritative": authoritative,
        "clock_domain": clock_domain,
        "monotonic_or_wall": monotonic_or_wall,
        "reconstructed": reconstructed,
        "unit": unit,
        "value": value,
    }
    if notes is not None:
        payload["notes"] = notes
    return payload


def deterministic_runtime_window_id(parts: dict[str, Any]) -> str:
    payload = {
        "contract_id": INPUT_CONTRACT_ID,
        "event_id": parts.get("event_id"),
        "recording_id": parts.get("recording_id"),
        "session_id": parts.get("session_id"),
        "source_id": parts["source_id"],
        "window_end": parts.get("window_end"),
        "window_start": parts.get("window_start"),
    }
    digest = sha256_bytes(canonical_dumps(payload).encode("utf-8"))
    return f"runtime_window:{digest}"


def _presence_confirmed(value: Any) -> bool:
    return value is True or value == "true"


def presence_gate_applies(domain_class: str, presence_applicability: str | None) -> bool:
    if presence_applicability == "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN":
        return False
    if domain_class == "PUBLIC_OFFLINE" and presence_applicability in (
        "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
        None,
    ):
        return False
    return True


def resolve_precedence(
    *,
    presence: Any,
    declared_quality: str,
    reason_codes: list[str] | None = None,
    class_confidence: float | None = None,
    proposed_physiology: str | None = None,
    domain_class: str = "PUBLIC_OFFLINE",
    production_freshness_present: bool | None = None,
    presence_applicability: str | None = None,
) -> dict[str, Any]:
    """Resolve presence → quality → physiology without executing a model or Q2 detector."""
    reasons = list(reason_codes or [])
    confidence_override_rejected = False
    schema_errors: list[str] = []

    if domain_class not in DOMAIN_CLASSES:
        schema_errors.append("UNKNOWN_DOMAIN_CLASS")

    apply_presence = presence_gate_applies(domain_class, presence_applicability)
    if apply_presence and not _presence_confirmed(presence):
        if "PRESENCE_NOT_CONFIRMED" not in reasons:
            reasons.insert(0, "PRESENCE_NOT_CONFIRMED")
        availability = "PRESENCE_SUPPRESSED"
        application_state = "PRESENCE_SUPPRESSED"
        physiology_boundary_entered = False
        physiology_executed = False
        actionable = False
    elif (
        domain_class == "PRODUCTION_MR60"
        and production_freshness_present is False
        and declared_quality == "PHYSIOLOGY_ELIGIBLE"
    ):
        schema_errors.append("PRODUCTION_MR60_MISSING_FRESHNESS_CANNOT_BE_ELIGIBLE")
        if "SOURCE_STALE" not in reasons:
            reasons.append("SOURCE_STALE")
        availability = "INPUT_UNAVAILABLE"
        application_state = "INPUT_UNAVAILABLE"
        physiology_boundary_entered = False
        physiology_executed = False
        actionable = False
    elif declared_quality == "INPUT_UNAVAILABLE":
        availability = "INPUT_UNAVAILABLE"
        application_state = "INPUT_UNAVAILABLE"
        physiology_boundary_entered = False
        physiology_executed = False
        actionable = False
        if not reasons:
            reasons.append("EXTERNAL_QUALITY_POLICY")
    elif declared_quality == "PHYSIOLOGY_ELIGIBLE":
        availability = "PHYSIOLOGY_ELIGIBLE"
        application_state = "NOT_EVALUATED"
        physiology_boundary_entered = True
        physiology_executed = False
        actionable = False
        if "NOT_IMPLEMENTED_MODEL_BOUNDARY" not in reasons:
            reasons.append("NOT_IMPLEMENTED_MODEL_BOUNDARY")
    elif declared_quality == "NOT_EVALUATED":
        availability = "NOT_EVALUATED"
        application_state = "NOT_EVALUATED"
        physiology_boundary_entered = False
        physiology_executed = False
        actionable = False
        if "NOT_IMPLEMENTED_MODEL_BOUNDARY" not in reasons:
            reasons.append("NOT_IMPLEMENTED_MODEL_BOUNDARY")
    else:
        schema_errors.append("UNDECLARED_QUALITY_STATE")
        availability = "INPUT_UNAVAILABLE"
        application_state = "INPUT_UNAVAILABLE"
        physiology_boundary_entered = False
        physiology_executed = False
        actionable = False
        reasons.append("EXTERNAL_QUALITY_POLICY")

    if availability != "PHYSIOLOGY_ELIGIBLE" and class_confidence is not None:
        confidence_override_rejected = True
        physiology_executed = False
        actionable = False
        if proposed_physiology in PHYSIOLOGY_LABELS:
            schema_errors.append("CONFIDENCE_CANNOT_OVERRIDE_INVALID_AVAILABILITY")

    if availability != "PHYSIOLOGY_ELIGIBLE" and proposed_physiology in PHYSIOLOGY_LABELS:
        schema_errors.append("INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY")

    if availability == "PHYSIOLOGY_ELIGIBLE" and proposed_physiology in PHYSIOLOGY_LABELS:
        schema_errors.append("I1_MUST_NOT_EMIT_REAL_PHYSIOLOGY")

    return {
        "actionable": actionable,
        "application_state": application_state,
        "availability_state": availability,
        "class_confidence_override_rejected": confidence_override_rejected,
        "inference_boundary": "NOT_IMPLEMENTED_MODEL_BOUNDARY",
        "physiology_boundary_entered": physiology_boundary_entered,
        "physiology_executed": physiology_executed,
        "proposed_physiology_accepted": False,
        "reason_codes": reasons,
        "schema_errors": schema_errors,
    }


def mock_inference_result(precedence: dict[str, Any]) -> dict[str, Any]:
    unavailable = precedence["availability_state"] in (
        "PRESENCE_SUPPRESSED",
        "INPUT_UNAVAILABLE",
    )
    status = "unavailable" if unavailable else "not_evaluated"
    component = {
        "confidence": {
            "component": None,
            "status": "not_evaluated",
            "value": None,
        },
        "reason_codes": list(precedence["reason_codes"]),
        "status": status,
        "value": None,
    }

    def named(name: str) -> dict[str, Any]:
        payload = json.loads(json.dumps(component))
        payload["confidence"]["component"] = name
        payload["confidence"]["status"] = status
        return payload

    return {
        "application_state": {
            "confidence": {
                "component": "application_state",
                "status": status,
                "value": None,
            },
            "reason_codes": list(precedence["reason_codes"]),
            "status": status if unavailable else "not_evaluated",
            "value": precedence["application_state"],
        },
        "breathing_evidence": named("breathing_evidence"),
        "inference_kind": "MockInferenceResult",
        "quality": {
            "confidence": {
                "component": "quality_availability",
                "status": "available",
                "value": None,
            },
            "reason_codes": list(precedence["reason_codes"]),
            "status": "available",
            "value": precedence["availability_state"],
        },
        "rr": named("rr"),
        "temporal_hold": named("temporal_hold"),
        "warning": "NOT_IMPLEMENTED_MODEL_BOUNDARY; not a physiological prediction",
    }


def validate_timestamp_map(timestamps: dict[str, Any], errors: list[str], trail: str) -> None:
    if not isinstance(timestamps, dict):
        errors.append(f"{trail}:NOT_OBJECT")
        return
    for role, payload in timestamps.items():
        if role not in TIME_ROLES:
            errors.append(f"{trail}.{role}:UNKNOWN_TIME_ROLE")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{trail}.{role}:NOT_OBJECT")
            continue
        for required in ("clock_domain", "unit", "monotonic_or_wall", "reconstructed", "authoritative"):
            if required not in payload:
                errors.append(f"{trail}.{role}:MISSING_{required.upper()}")
        if payload.get("clock_domain") == "esp_ts_monotonic_ms" and payload.get("authoritative") is True:
            if "physical_radar_acquisition" in str(payload.get("notes", "")).lower():
                errors.append(f"{trail}.{role}:ESP_TS_CLAIMED_AS_PHYSICAL_ACQUISITION")


def validate_runtime_input(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    check_absolute_paths(record, "input", errors)
    if record.get("schema_id") != INPUT_CONTRACT_ID:
        errors.append("INPUT_SCHEMA_ID")
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("INPUT_SCHEMA_VERSION")
    if V1_FORBIDDEN_IDENTITY in json.dumps(record):
        if record.get("schema_id") == V1_FORBIDDEN_IDENTITY or record.get("artifact_id") == V1_FORBIDDEN_IDENTITY:
            errors.append("V1_IDENTITY_REUSED")
    domain = record.get("source", {}).get("domain_class")
    if domain not in DOMAIN_CLASSES:
        errors.append("DOMAIN_CLASS")
    presence = record.get("presence", {})
    if presence.get("field") != "human_detected_raw":
        errors.append("PRESENCE_FIELD")
    if presence.get("inferred_from_amplitude") is True:
        errors.append("PRESENCE_INFERRED_FROM_AMPLITUDE")
    freshness = record.get("freshness", {})
    phase_age = freshness.get("phase_age_ms", {})
    seq = freshness.get("seq", {})
    quality = record.get("quality", {})
    declared = quality.get("declared_availability_state")
    if declared not in AVAILABILITY_STATES and declared != "NOT_EVALUATED":
        errors.append("DECLARED_AVAILABILITY_STATE")
    if quality.get("detection_implemented_in_i1") is True:
        errors.append("I1_MUST_NOT_IMPLEMENT_Q2_DETECTOR")
    if domain == "PUBLIC_OFFLINE":
        if phase_age.get("applicability") not in (
            "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
            "OPTIONAL_IF_PRESENT",
        ):
            errors.append("PUBLIC_FRESHNESS_APPLICABILITY")
        if declared == "INPUT_UNAVAILABLE" and phase_age.get("value") is None:
            if quality.get("reason_codes") == ["SOURCE_STALE"] and not quality.get("external_policy_id"):
                errors.append("PUBLIC_DOMAIN_MR60_METADATA_CONFUSION")
    if domain == "PRODUCTION_MR60":
        if phase_age.get("applicability") != "REQUIRED_FOR_PRODUCTION_MR60":
            errors.append("MR60_FRESHNESS_APPLICABILITY")
        if seq.get("applicability") != "REQUIRED_FOR_PRODUCTION_MR60":
            errors.append("MR60_SEQ_APPLICABILITY")
        if phase_age.get("value") is None and declared == "PHYSIOLOGY_ELIGIBLE":
            errors.append("PRODUCTION_MR60_MISSING_FRESHNESS_CANNOT_BE_ELIGIBLE")
    timestamps = record.get("timestamps")
    if timestamps:
        validate_timestamp_map(timestamps, errors, "timestamps")
    window_id = record.get("provenance", {}).get("runtime_window_id")
    expected = deterministic_runtime_window_id(
        {
            "event_id": record.get("event", {}).get("event_id"),
            "recording_id": record.get("session", {}).get("recording_id"),
            "session_id": record.get("session", {}).get("session_id"),
            "source_id": record.get("source", {}).get("source_id"),
            "window_end": (record.get("timestamps") or {}).get("window_end", {}).get("value"),
            "window_start": (record.get("timestamps") or {}).get("window_start", {}).get("value"),
        }
    )
    if window_id != expected:
        errors.append("RUNTIME_WINDOW_ID_NOT_DETERMINISTIC")
    if record.get("provenance", {}).get("transport_record_id") and window_id == record["provenance"]["transport_record_id"]:
        errors.append("TRANSPORT_UUID_USED_AS_EVIDENCE_IDENTITY")
    model_input = record.get("model_input_boundary")
    if model_input:
        eligible = model_input.get("eligible_for_physiological_inference")
        not_for = model_input.get("not_for_physiological_inference")
        if declared in ("PRESENCE_SUPPRESSED", "INPUT_UNAVAILABLE"):
            if eligible is True:
                errors.append("INVALID_AVAILABILITY_MODEL_INPUT_MARKED_ELIGIBLE")
            if not_for is not True:
                errors.append("INVALID_AVAILABILITY_REQUIRES_NOT_FOR_PHYSIOLOGICAL_INFERENCE")
        if model_input.get("tensor_shape") not in (None, "DEFERRED_TO_M_PV1"):
            errors.append("FINAL_MODEL_TENSOR_SHAPE_FROZEN")
        if model_input.get("feature_schema_id") not in (None, "DEFERRED_TO_R2_M_PV1", "DEFERRED_TO_R1_R2_R3"):
            if str(model_input.get("feature_schema_id", "")).startswith("MMWAVE_M_N"):
                errors.append("FINAL_FEATURE_SCHEMA_FROZEN")
    vendor_rr = (record.get("mr60_telemetry") or {}).get("breath_rate_raw") or {}
    if vendor_rr.get("used_as_v2_supervised_rr_truth") is True:
        errors.append("MR60_SUPERVISED_USE")
    return errors


def validate_runtime_output(record: dict[str, Any], input_record: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    check_absolute_paths(record, "output", errors)
    if record.get("schema_id") != OUTPUT_CONTRACT_ID:
        errors.append("OUTPUT_SCHEMA_ID")
    if "confidence" in record and not isinstance(record.get("confidence"), dict):
        errors.append("AMBIGUOUS_TOP_LEVEL_CONFIDENCE")
    elif isinstance(record.get("confidence"), dict) and record["confidence"].get("component") is None:
        errors.append("AMBIGUOUS_TOP_LEVEL_CONFIDENCE")
    required = (
        "availability_state",
        "reason_codes",
        "physiology_executed",
        "physiology_boundary_entered",
        "actionable",
        "application_state",
    )
    for key in required:
        if key not in record:
            errors.append(f"OUTPUT_MISSING_{key.upper()}")
    availability = record.get("availability_state")
    if availability not in OUTPUT_AVAILABILITY_STATES:
        errors.append("OUTPUT_AVAILABILITY_STATE")
    if record.get("application_state") not in APPLICATION_STATES:
        errors.append("OUTPUT_APPLICATION_STATE")
    if availability in ("PRESENCE_SUPPRESSED", "INPUT_UNAVAILABLE"):
        if record.get("physiology_executed") is not False:
            errors.append("PHYSIOLOGY_EXECUTED_ON_INVALID_INPUT")
        if record.get("actionable") is not False:
            errors.append("ACTIONABLE_ON_INVALID_INPUT")
        if record.get("application_state") not in ("PRESENCE_SUPPRESSED", "INPUT_UNAVAILABLE"):
            errors.append("INVALID_INPUT_FALLBACK_PHYSIOLOGY_STATE")
    for name in ("breathing_evidence", "rr", "temporal_hold"):
        component = record.get(name) or {}
        if component.get("status") not in COMPONENT_STATUSES:
            errors.append(f"{name.upper()}_STATUS")
        if availability != "PHYSIOLOGY_ELIGIBLE" and component.get("status") == "available":
            errors.append(f"{name.upper()}_EMITTED_WHILE_UNAVAILABLE")
        confidence = component.get("confidence") or {}
        if confidence.get("component") not in (None, name) and confidence:
            if confidence.get("component") not in (name, f"{name}_confidence"):
                errors.append(f"{name.upper()}_CONFIDENCE_COMPONENT_MISMATCH")
        if name == "rr" and component.get("value") is not None and availability != "PHYSIOLOGY_ELIGIBLE":
            errors.append("RR_INVENTED_FOR_UNAVAILABLE_INPUT")
    if record.get("inference_kind") not in (None, "MockInferenceResult", "NOT_IMPLEMENTED_MODEL_BOUNDARY"):
        errors.append("REAL_MODEL_INFERENCE")
    if input_record is not None:
        expected = resolve_precedence(
            presence=input_record.get("presence", {}).get("value"),
            declared_quality=input_record.get("quality", {}).get("declared_availability_state"),
            reason_codes=list(input_record.get("quality", {}).get("reason_codes") or []),
            domain_class=input_record.get("source", {}).get("domain_class", "PUBLIC_OFFLINE"),
            production_freshness_present=(
                input_record.get("freshness", {}).get("phase_age_ms", {}).get("value") is not None
            ),
            presence_applicability=input_record.get("presence", {}).get("applicability"),
        )
        if record.get("availability_state") != expected["availability_state"]:
            errors.append("OUTPUT_PRECEDENCE_MISMATCH")
        if record.get("physiology_executed") != expected["physiology_executed"]:
            errors.append("OUTPUT_PHYSIOLOGY_EXECUTED_MISMATCH")
    return errors


def serialize_runtime_record(record: dict[str, Any]) -> str:
    return canonical_dumps(record)


def deserialize_runtime_record(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise I1ContractError("RUNTIME_RECORD_NOT_OBJECT")
    return payload


def build_time_field_schema() -> dict[str, Any]:
    return {
        "additionalProperties": False,
        "properties": {
            "authoritative": {"type": "boolean"},
            "clock_domain": {"type": "string"},
            "monotonic_or_wall": {"enum": ["monotonic", "wall", "index_reconstructed", "unspecified"]},
            "notes": {"type": ["string", "null"]},
            "reconstructed": {"type": "boolean"},
            "unit": {"enum": ["ms", "s", "ns", "index"]},
            "value": {},
        },
        "required": ["clock_domain", "unit", "monotonic_or_wall", "reconstructed", "authoritative"],
        "type": "object",
    }


def build_semantic_contract() -> dict[str, Any]:
    return {
        "audit_date": AUDIT_DATE,
        "availability_states": list(AVAILABILITY_STATES),
        "base_sha": BASE_SHA,
        "carryable_reason_codes": list(CARRYABLE_REASON_CODES),
        "contract_id": SEMANTIC_CONTRACT_ID,
        "d2_used": False,
        "deferred_bindings": {
            "final_feature_schema": "DEFERRED_TO_R1_R2_R3",
            "final_model_architecture": "DEFERRED_TO_M_PV1",
            "final_tensor_shape": "DEFERRED_TO_M_PV1",
            "int8_quantization": "DEFERRED_TO_M_PV2",
            "near_flat_threshold": "DEFERRED_TO_R2_R3_M_PV1",
            "probability_calibration": "DEFERRED_TO_M_PV1",
            "q2_detection_implementation": "OUTSIDE_I1",
            "r1_representation": "DEFERRED_TO_R1_R2_R3",
            "r2_features": "DEFERRED_TO_R1_R2_R3",
            "r3_breathing_rr_temporal_hold": "DEFERRED_TO_R3",
            "runtime_history_duration": "DEFERRED_TO_M_PV1",
            "temporal_hold_algorithm": "DEFERRED_TO_R3_M_PV1",
        },
        "fail_closed": {
            "high_class_confidence_cannot_override_invalid_availability": True,
            "invalid_input_fallback_apnea": False,
            "invalid_input_fallback_normal": False,
            "no_person_is_not_apnea": True,
            "unavailable_input_suppresses_physiology": True,
        },
        "identities": {
            "input": INPUT_CONTRACT_ID,
            "output": OUTPUT_CONTRACT_ID,
            "provenance": PROVENANCE_CONTRACT_ID,
            "replay_interface": REPLAY_INTERFACE_ID,
            "semantic": SEMANTIC_CONTRACT_ID,
            "v1_identity_forbidden": V1_FORBIDDEN_IDENTITY,
        },
        "i2_full_replay_implemented": False,
        "i3_regression_work_performed": False,
        "model_inference": False,
        "model_training": False,
        "mr60_supervised_use": False,
        "phase": PHASE_ID,
        "precedence": {
            "order": [
                "presence gate",
                "input quality / availability gate",
                "physiological inference",
                "application state",
            ],
            "presence_false": "PRESENCE_SUPPRESSED",
            "presence_field": "human_detected_raw",
            "presence_inferred_from_amplitude": False,
            "presence_null_or_unknown": "PRESENCE_SUPPRESSED",
            "presence_true_and_quality_invalid": "INPUT_UNAVAILABLE",
            "presence_true_and_quality_valid": "PHYSIOLOGY_ELIGIBLE",
            "quality_before_physiology": True,
        },
        "q2_relationship": {
            "contract_id": Q2_CONTRACT_ID,
            "detection_implemented_in_i1": False,
            "integration": "EXTERNAL_POLICY_BOUND",
            "merged_on_main": True,
            "numerical_thresholds_copied_into_i1": False,
            "status": "Q2_CONTRACT_INTEGRATION_EXTERNAL_POLICY_BOUND",
        },
        "r1_relationship": {
            "assumed_trace_kind": "NONE",
            "common_rate_hz": "DEFERRED_TO_R1_M_PV1",
            "integration": "DEFERRED_BINDING",
            "payload_fields": [
                "representation_profile_id",
                "representation_payload",
                "time_coverage",
                "quality_metadata",
                "native_scale_descriptors",
            ],
        },
        "r3_relationship": {
            "breathing_evidence": "SEMANTIC_SLOT_ONLY",
            "integration": "DEFERRED_BINDING",
            "rr": "SEMANTIC_SLOT_ONLY",
            "temporal_hold": "SEMANTIC_SLOT_ONLY",
        },
        "reason_codes_are_not_physiological_labels": True,
        "schema_version": SCHEMA_VERSION,
        "v1_artifact_modified": False,
        "v1_observe_only": True,
    }


def build_input_schema() -> dict[str, Any]:
    time_schema = build_time_field_schema()
    return {
        "additionalProperties": False,
        "audit_date": AUDIT_DATE,
        "contract_id": INPUT_CONTRACT_ID,
        "description": "Generic V2 runtime input envelope. Not a final tensor specification.",
        "field_applicability": {
            "breath_phase": "OPTIONAL_MR60_TELEMETRY_NOT_V2_RR_TRUTH",
            "breath_rate_raw": "AUXILIARY_TELEMETRY_NOT_V2_SUPERVISED_RR_TRUTH",
            "human_detected_raw": {
                "PRODUCTION_MR60": "REQUIRED_FOR_PRODUCTION_MR60",
                "PUBLIC_OFFLINE": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
            },
            "phase_age_ms": {
                "PRODUCTION_MR60": "REQUIRED_FOR_PRODUCTION_MR60",
                "PUBLIC_OFFLINE": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
            },
            "seq": {
                "PRODUCTION_MR60": "REQUIRED_FOR_PRODUCTION_MR60",
                "PUBLIC_OFFLINE": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
            },
            "ts_monotonic_ms": {
                "PRODUCTION_MR60": "REQUIRED_FOR_PRODUCTION_MR60_AS_RECEIVE_OR_PUBLISH_CLOCK",
                "PUBLIC_OFFLINE": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
                "not_physical_radar_acquisition_time": True,
            },
        },
        "phase": PHASE_ID,
        "properties": {
            "adapter": {"type": "object"},
            "event": {"type": "object"},
            "freshness": {"type": "object"},
            "model_input_boundary": {"type": "object"},
            "mr60_telemetry": {"type": "object"},
            "presence": {"type": "object"},
            "provenance": {"type": "object"},
            "quality": {"type": "object"},
            "schema_id": {"const": INPUT_CONTRACT_ID},
            "schema_version": {"const": SCHEMA_VERSION},
            "session": {"type": "object"},
            "signal": {"type": "object"},
            "source": {"type": "object"},
            "timestamps": {
                "additionalProperties": False,
                "properties": {role: time_schema for role in TIME_ROLES},
                "type": "object",
            },
        },
        "required": [
            "schema_id",
            "schema_version",
            "source",
            "presence",
            "quality",
            "provenance",
        ],
        "schema_version": SCHEMA_VERSION,
        "title": "MMWAVE_V2_I1_RUNTIME_INPUT_CONTRACT_V1",
        "type": "object",
    }


def build_output_schema() -> dict[str, Any]:
    component = {
        "additionalProperties": False,
        "properties": {
            "confidence": {
                "additionalProperties": False,
                "properties": {
                    "component": {"type": ["string", "null"]},
                    "status": {"enum": list(COMPONENT_STATUSES)},
                    "value": {"type": ["number", "null"]},
                },
                "required": ["component", "status"],
                "type": "object",
            },
            "reason_codes": {"items": {"type": "string"}, "type": "array"},
            "status": {"enum": list(COMPONENT_STATUSES)},
            "value": {},
        },
        "required": ["status"],
        "type": "object",
    }
    return {
        "additionalProperties": False,
        "application_states": list(APPLICATION_STATES),
        "audit_date": AUDIT_DATE,
        "component_statuses": list(COMPONENT_STATUSES),
        "contract_id": OUTPUT_CONTRACT_ID,
        "description": "Semantic V2 runtime output skeleton. Component slots are not neural heads.",
        "phase": PHASE_ID,
        "properties": {
            "actionable": {"type": "boolean"},
            "application_state": {"enum": list(APPLICATION_STATES)},
            "availability_state": {"enum": list(AVAILABILITY_STATES)},
            "breathing_evidence": component,
            "inference_kind": {
                "enum": ["MockInferenceResult", "NOT_IMPLEMENTED_MODEL_BOUNDARY"]
            },
            "physiology_boundary_entered": {"type": "boolean"},
            "physiology_executed": {"type": "boolean"},
            "provenance": {"type": "object"},
            "quality": component,
            "reason_codes": {"items": {"type": "string"}, "type": "array"},
            "rr": component,
            "schema_id": {"const": OUTPUT_CONTRACT_ID},
            "schema_version": {"const": SCHEMA_VERSION},
            "temporal_hold": component,
            "warning": {"type": ["string", "null"]},
        },
        "required": [
            "schema_id",
            "schema_version",
            "availability_state",
            "reason_codes",
            "physiology_executed",
            "physiology_boundary_entered",
            "actionable",
            "application_state",
        ],
        "schema_version": SCHEMA_VERSION,
        "title": "MMWAVE_V2_I1_RUNTIME_OUTPUT_CONTRACT_V1",
        "type": "object",
    }


def build_provenance_contract() -> dict[str, Any]:
    return {
        "absolute_paths_forbidden": True,
        "archive_or_version_snapshot_fallback_forbidden": True,
        "audit_date": AUDIT_DATE,
        "contract_id": PROVENANCE_CONTRACT_ID,
        "deterministic_runtime_window_id": {
            "algorithm": "SHA-256 of canonical JSON",
            "fields": [
                "contract_id",
                "source_id",
                "session_id",
                "recording_id",
                "event_id",
                "window_start",
                "window_end",
            ],
            "prefix": "runtime_window:",
            "random_uuid_alone_forbidden": True,
        },
        "phase": PHASE_ID,
        "required_lineage_fields": [
            "source_id",
            "dataset_or_device_id",
            "session_id",
            "recording_id",
            "event_id",
            "adapter_profile_id",
            "representation_profile_id",
            "software_git_sha",
            "runtime_window_id",
        ],
        "schema_version": SCHEMA_VERSION,
        "synthetic_corruption_profile_id": "required when domain_class=SYNTHETIC_CORRUPTION",
        "transport_record_id": "optional UUID for runtime transport; not evidence identity",
    }


def _public_fixture() -> dict[str, Any]:
    source_id = "dataset-10_5281_zenodo_18599983"
    session_id = "p001"
    recording_id = "p001_rec01"
    event_id = "window-000"
    window_start = 0.0
    window_end = 12.0
    runtime_window_id = deterministic_runtime_window_id(
        {
            "event_id": event_id,
            "recording_id": recording_id,
            "session_id": session_id,
            "source_id": source_id,
            "window_end": window_end,
            "window_start": window_start,
        }
    )
    return {
        "adapter": {
            "adapter_profile_id": "D0_A6_UNFILTERED_UNNORMALIZED_PHASE",
            "software_git_sha": BASE_SHA,
        },
        "event": {"event_id": event_id, "sample_id": "idx-0"},
        "freshness": {
            "phase_age_ms": {
                "applicability": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
                "value": None,
            },
            "seq": {
                "applicability": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
                "value": None,
            },
        },
        "model_input_boundary": {
            "eligible_for_physiological_inference": True,
            "feature_schema_id": "DEFERRED_TO_R2_M_PV1",
            "input_values": None,
            "model_input_contract_id": "DEFERRED_TO_M_PV1",
            "native_amplitude_descriptors": {"native_mad": None},
            "not_for_physiological_inference": False,
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "tensor_shape": "DEFERRED_TO_M_PV1",
            "time_coverage": {"end": window_end, "start": window_start, "unit": "s"},
            "validity_mask": None,
        },
        "mr60_telemetry": {
            "breath_rate_raw": {
                "status": "AUXILIARY_TELEMETRY_NOT_V2_RR_TRUTH",
                "used_as_v2_supervised_rr_truth": False,
                "value": None,
            }
        },
        "presence": {
            "applicability": "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
            "field": "human_detected_raw",
            "inferred_from_amplitude": False,
            "value": None,
        },
        "provenance": {
            "adapter_profile_id": "D0_A6_UNFILTERED_UNNORMALIZED_PHASE",
            "dataset_or_device_id": source_id,
            "event_id": event_id,
            "firmware_config_identity": None,
            "recording_id": recording_id,
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "runtime_window_id": runtime_window_id,
            "session_id": session_id,
            "software_git_sha": BASE_SHA,
            "source_id": source_id,
            "synthetic_corruption_profile_id": None,
            "transport_record_id": None,
        },
        "quality": {
            "declared_availability_state": "PHYSIOLOGY_ELIGIBLE",
            "detection_implemented_in_i1": False,
            "external_policy_id": Q2_CONTRACT_ID,
            "reason_codes": [],
        },
        "schema_id": INPUT_CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "session": {
            "recording_id": recording_id,
            "session_id": session_id,
            "subject_id": "p001",
        },
        "signal": {
            "native_amplitude_descriptors": {},
            "payload": {"kind": "trace_reference", "not_a_final_tensor": True, "values": [0.1, -0.2, 0.15]},
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "sampling": {"rate_hz": None, "rate_status": "DEFERRED_TO_R1_M_PV1"},
            "semantics": "phase_like",
            "units": "phase_like_radian",
        },
        "source": {
            "dataset_or_device_id": source_id,
            "domain_class": "PUBLIC_OFFLINE",
            "radar_domain": "60ghz",
            "source_id": source_id,
        },
        "timestamps": {
            "model_evaluation_time": timestamp_descriptor(
                clock_domain="runtime_eval",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=None,
                notes="DEFERRED_TO_I2",
            ),
            "runtime_receive_time": timestamp_descriptor(
                clock_domain="not_applicable_public_offline",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
            ),
            "source_native_sample_time": timestamp_descriptor(
                clock_domain="native_sample_index_over_fs",
                unit="s",
                monotonic_or_wall="index_reconstructed",
                reconstructed=True,
                authoritative=True,
                value=window_start,
            ),
            "source_update_estimate": timestamp_descriptor(
                clock_domain="not_applicable_public_offline",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
            ),
            "transport_publish_time": timestamp_descriptor(
                clock_domain="not_applicable_public_offline",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
            ),
            "window_end": timestamp_descriptor(
                clock_domain="native_sample_index_over_fs",
                unit="s",
                monotonic_or_wall="index_reconstructed",
                reconstructed=True,
                authoritative=True,
                value=window_end,
            ),
            "window_start": timestamp_descriptor(
                clock_domain="native_sample_index_over_fs",
                unit="s",
                monotonic_or_wall="index_reconstructed",
                reconstructed=True,
                authoritative=True,
                value=window_start,
            ),
        },
    }


def _mr60_missing_freshness_fixture() -> dict[str, Any]:
    source_id = "device-mr60-production"
    session_id = "esp-session-001"
    recording_id = "jsonl-stream"
    event_id = "seq-10"
    window_start = 1000
    window_end = 2000
    runtime_window_id = deterministic_runtime_window_id(
        {
            "event_id": event_id,
            "recording_id": recording_id,
            "session_id": session_id,
            "source_id": source_id,
            "window_end": window_end,
            "window_start": window_start,
        }
    )
    return {
        "adapter": {
            "adapter_profile_id": "MR60_ESP_TELEMETRY_V1",
            "software_git_sha": BASE_SHA,
        },
        "event": {"event_id": event_id, "sample_id": "seq-10"},
        "freshness": {
            "phase_age_ms": {
                "applicability": "REQUIRED_FOR_PRODUCTION_MR60",
                "value": None,
            },
            "seq": {
                "applicability": "REQUIRED_FOR_PRODUCTION_MR60",
                "value": 10,
            },
        },
        "model_input_boundary": {
            "eligible_for_physiological_inference": False,
            "feature_schema_id": "DEFERRED_TO_R2_M_PV1",
            "input_values": None,
            "model_input_contract_id": "DEFERRED_TO_M_PV1",
            "native_amplitude_descriptors": {},
            "not_for_physiological_inference": True,
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "tensor_shape": "DEFERRED_TO_M_PV1",
            "time_coverage": {"end": window_end, "start": window_start, "unit": "ms"},
            "validity_mask": None,
        },
        "mr60_telemetry": {
            "breath_phase": {
                "applicability": "OPTIONAL_MR60_TELEMETRY_NOT_V2_RR_TRUTH",
                "value": None,
            },
            "breath_rate_raw": {
                "status": "AUXILIARY_TELEMETRY_NOT_V2_RR_TRUTH",
                "used_as_v2_supervised_rr_truth": False,
                "value": None,
            },
            "config_hash": "unspecified",
            "firmware_version": "unspecified",
            "schema_version": "unspecified",
            "session_id": session_id,
            "ts_monotonic_ms": {
                "applicability": "REQUIRED_FOR_PRODUCTION_MR60_AS_RECEIVE_OR_PUBLISH_CLOCK",
                "not_physical_radar_acquisition_time": True,
                "value": 2000,
            },
        },
        "presence": {
            "applicability": "REQUIRED_FOR_PRODUCTION_MR60",
            "field": "human_detected_raw",
            "inferred_from_amplitude": False,
            "value": True,
        },
        "provenance": {
            "adapter_profile_id": "MR60_ESP_TELEMETRY_V1",
            "dataset_or_device_id": source_id,
            "event_id": event_id,
            "firmware_config_identity": "unspecified",
            "recording_id": recording_id,
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "runtime_window_id": runtime_window_id,
            "session_id": session_id,
            "software_git_sha": BASE_SHA,
            "source_id": source_id,
            "synthetic_corruption_profile_id": None,
            "transport_record_id": "transport-uuid-not-evidence",
        },
        "quality": {
            "declared_availability_state": "INPUT_UNAVAILABLE",
            "detection_implemented_in_i1": False,
            "external_policy_id": Q2_CONTRACT_ID,
            "reason_codes": ["SOURCE_STALE"],
        },
        "schema_id": INPUT_CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "session": {
            "recording_id": recording_id,
            "session_id": session_id,
            "subject_id": None,
        },
        "signal": {
            "native_amplitude_descriptors": {},
            "payload": {"kind": "trace_reference", "not_a_final_tensor": True, "values": None},
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "sampling": {"rate_hz": None, "rate_status": "DEFERRED_TO_R1_M_PV1"},
            "semantics": "unspecified_native",
            "units": None,
        },
        "source": {
            "dataset_or_device_id": source_id,
            "domain_class": "PRODUCTION_MR60",
            "radar_domain": "mr60",
            "source_id": source_id,
        },
        "timestamps": {
            "model_evaluation_time": timestamp_descriptor(
                clock_domain="runtime_eval",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=None,
                notes="DEFERRED_TO_I2",
            ),
            "runtime_receive_time": timestamp_descriptor(
                clock_domain="pi_receive",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=2000,
                notes="host receive clock; not radar acquisition time",
            ),
            "source_native_sample_time": timestamp_descriptor(
                clock_domain="unknown_physical_radar",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
                notes="ESP ts_monotonic_ms is not claimed as physical radar acquisition time",
            ),
            "source_update_estimate": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms_minus_phase_age_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=True,
                authoritative=False,
                value=None,
                notes="freshness missing; estimate cannot be formed",
            ),
            "transport_publish_time": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=2000,
                notes="ESP publish/receive-side monotonic clock, not physical radar acquisition time",
            ),
            "window_end": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=window_end,
            ),
            "window_start": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=window_start,
            ),
        },
    }


def make_output_from_input(record: dict[str, Any], **precedence_kwargs: Any) -> dict[str, Any]:
    presence = record.get("presence", {}).get("value")
    declared = record.get("quality", {}).get("declared_availability_state")
    reasons = list(record.get("quality", {}).get("reason_codes") or [])
    freshness_present = record.get("freshness", {}).get("phase_age_ms", {}).get("value") is not None
    precedence = resolve_precedence(
        presence=presence,
        declared_quality=declared,
        reason_codes=reasons,
        domain_class=record.get("source", {}).get("domain_class", "PUBLIC_OFFLINE"),
        production_freshness_present=freshness_present,
        presence_applicability=record.get("presence", {}).get("applicability"),
        **precedence_kwargs,
    )
    mock = mock_inference_result(precedence)
    return {
        "actionable": precedence["actionable"],
        "application_state": mock["application_state"]["value"],
        "availability_state": precedence["availability_state"],
        "breathing_evidence": mock["breathing_evidence"],
        "inference_kind": "MockInferenceResult",
        "physiology_boundary_entered": precedence["physiology_boundary_entered"],
        "physiology_executed": precedence["physiology_executed"],
        "provenance": {
            "runtime_window_id": record.get("provenance", {}).get("runtime_window_id"),
            "source_id": record.get("source", {}).get("source_id"),
        },
        "quality": mock["quality"],
        "reason_codes": precedence["reason_codes"],
        "rr": mock["rr"],
        "schema_id": OUTPUT_CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "temporal_hold": mock["temporal_hold"],
        "warning": mock["warning"],
    }


def build_replay_interface() -> dict[str, Any]:
    public_in = _public_fixture()
    mr60_in = _mr60_missing_freshness_fixture()
    return {
        "allowed_in_i1": [
            "serializer/deserializer",
            "schema validator",
            "tiny deterministic fixture",
            "no-op/mock inference boundary",
        ],
        "audit_date": AUDIT_DATE,
        "contract_id": REPLAY_INTERFACE_ID,
        "feeders_for_i2": [
            "historical JSONL",
            "public adapted traces",
            "synthetic corruption fixtures",
        ],
        "forbidden_in_i1": [
            "running V1/V2 across historical sessions",
            "computing replay metrics",
            "MR60 application scoring",
        ],
        "interface": {
            "deserialize_runtime_record": "scripts.mmwave_i1_runtime_io_contract.deserialize_runtime_record",
            "resolve_precedence": "scripts.mmwave_i1_runtime_io_contract.resolve_precedence",
            "serialize_runtime_record": "scripts.mmwave_i1_runtime_io_contract.serialize_runtime_record",
            "validate_runtime_input": "scripts.mmwave_i1_runtime_io_contract.validate_runtime_input",
            "validate_runtime_output": "scripts.mmwave_i1_runtime_io_contract.validate_runtime_output",
        },
        "phase": PHASE_ID,
        "record_kinds": ["runtime_input", "runtime_output"],
        "schema_version": SCHEMA_VERSION,
        "tiny_deterministic_fixture": {
            "mr60_missing_freshness_fail_closed": {
                "input": mr60_in,
                "output": make_output_from_input(mr60_in),
            },
            "public_d0_without_phase_age_eligible": {
                "input": public_in,
                "output": make_output_from_input(public_in),
            },
        },
    }


def build_exception_registry() -> dict[str, Any]:
    return {
        "entries": [],
        "final_feature_schema": "DEFERRED_TO_R1_R2_R3",
        "final_model_architecture": "DEFERRED_TO_M_PV1",
        "final_tensor_shape": "DEFERRED_TO_M_PV1",
        "i2_full_replay": "NOT_IN_I1",
        "i3_regression": "NOT_IN_I1",
        "near_flat_threshold": "DEFERRED_TO_R2_R3_M_PV1",
        "phase": PHASE_ID,
        "q2_detection_implementation": "OUTSIDE_I1",
        "r3_temporal_hold_algorithm": "DEFERRED_TO_R3_M_PV1",
        "runtime_history_duration": "DEFERRED_TO_M_PV1",
        "schema_version": SCHEMA_VERSION,
    }


def generate() -> dict[str, str]:
    if not MN9_LOCK.is_file():
        raise I1ContractError("V1_LOCK_MISSING")
    v1_lock = load_json(MN9_LOCK)
    if v1_lock.get("artifact_id") != V1_FORBIDDEN_IDENTITY:
        raise I1ContractError("V1_LOCK_IDENTITY_CHANGED")
    semantic = build_semantic_contract()
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    artifacts = {
        "runtime_semantic_contract.json": semantic,
        "runtime_input_schema.json": build_input_schema(),
        "runtime_output_schema.json": build_output_schema(),
        "provenance_contract.json": build_provenance_contract(),
        "replay_interface_skeleton.json": build_replay_interface(),
        "exception_registry.json": build_exception_registry(),
    }
    for name, payload in artifacts.items():
        checksums[name] = dump_json(MANIFEST_DIR / name, payload)
    config_digest = dump_json(CONFIG_PATH, semantic)
    checksum_doc = {
        "algorithm": "SHA-256",
        "config_file": {
            "path": "config/mmwave/i1_runtime_semantic_contract.json",
            "sha256": config_digest,
        },
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "files": checksums,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
    }
    dump_json(MANIFEST_DIR / "checksums.json", checksum_doc)
    return checksums


def main() -> int:
    generate()
    print(
        json.dumps(
            {
                "gate_pending_validator": True,
                "manifest": str(MANIFEST_DIR.relative_to(ROOT)),
                "ok": True,
                "phase": PHASE_ID,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
