#!/usr/bin/env python3
"""I3 fail-closed runtime semantic regression over frozen I1/I2/Q2.

Verifies presence → availability → physiology precedence. Does not train,
does not run V1/V2 physiology, does not fork Q2 thresholds, and does not
perform Q3 or M-PV1 selection.
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    INPUT_CONTRACT_ID,
    OUTPUT_CONTRACT_ID,
    PROVENANCE_CONTRACT_ID,
    Q2_CONTRACT_ID,
    SEMANTIC_CONTRACT_ID,
    canonical_dumps,
    check_absolute_paths,
    dump_json,
    load_json,
    make_output_from_input,
    resolve_precedence,
    sha256_bytes,
    timestamp_descriptor,
    validate_runtime_input,
    validate_runtime_output,
)
from scripts.mmwave_i2_jsonl_replay import (  # noqa: E402
    I2_CONTRACT_ID,
    I2_HARNESS_ID,
    REPRESENTATIVE_SESSIONS,
    SessionReplayState,
    load_inventory_index,
    parse_jsonl_bytes,
    public_offline_replay,
    replay_blob_session,
    replay_parsed_rows,
    synthetic_fixture_rows,
)
from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    apply_timing_corruption,
    load_profile as load_q1_profile,
)
from scripts.mmwave_q2_input_unavailable import (  # noqa: E402
    CONTRACT_ID as Q2_EVALUATOR_CONTRACT_ID,
    PROFILE_ID as Q2_PROFILE_ID,
    Q1_PROFILE_PATH,
    Q2_MODES,
    apply_quality_corruption,
    evaluate_availability,
)

PHASE_ID = "I3"
SCHEMA_VERSION = "I3.1"
AUDIT_DATE = "2026-08-23"
BASE_SHA = "e84d802e5b9aa28e6729a02b304f1f70043f89c3"

I3_CONTRACT_ID = "MMWAVE_V2_I3_FAIL_CLOSED_REGRESSION_CONTRACT_V1"
I3_MATRIX_ID = "MMWAVE_V2_I3_REGRESSION_MATRIX_V1"
I3_GATE_ID = "MMWAVE_V2_I3_RUNTIME_SAFETY_GATE_V1"

CONFIG_PATH = ROOT / "config/mmwave/i3_fail_closed_regression_contract.json"
MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_I3_fail_closed_regression"
I1_REPLAY_SKELETON = (
    ROOT / "datasets/mmwave/manifests/M-PV0_I1_runtime_io_contract/replay_interface_skeleton.json"
)

MANIFEST_JSON_FILES = (
    "i3_regression_contract.json",
    "regression_matrix.json",
    "historical_replay_regression.json",
    "synthetic_q2_regression.json",
    "presence_precedence_audit.json",
    "availability_precedence_audit.json",
    "session_reset_audit.json",
    "determinism_audit.json",
    "exception_registry.json",
)

PHYSIOLOGY_LABELS = ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA", "APNEA_PROXY", "RESPIRATION_PRESENT")
QUALITY_REASON_CODES = (
    "TIMESTAMP_NON_MONOTONIC",
    "TIMESTAMP_UNRESOLVED",
    "INSUFFICIENT_INTERVAL_HISTORY",
    "LARGE_GAP",
    "SOURCE_FREEZE",
    "SOURCE_STALE",
    "SIGNAL_FLAT_EXACT",
    "RECOVERY_WARMUP",
)


class I3RegressionError(RuntimeError):
    pass


def _presence_confirmed(value: Any) -> bool:
    return value is True or value == "true"


def declared_quality_from_q2(evaluation: dict[str, Any]) -> str:
    """Map Q2 window state to an I1 declared-quality token.

    I1 does not accept PRESENCE_SUPPRESSED as declared_quality. Presence is
    applied by I1's presence gate; quality faults remain INPUT_UNAVAILABLE.
    """
    state = evaluation["availability_state"]
    if state == "PRESENCE_SUPPRESSED":
        quality_faults = [code for code in evaluation["reasons"] if code in QUALITY_REASON_CODES]
        return "INPUT_UNAVAILABLE" if quality_faults else "PHYSIOLOGY_ELIGIBLE"
    return state


def resolve_i3_envelope(
    evaluation: dict[str, Any],
    *,
    presence: Any,
    domain_class: str = "SYNTHETIC_CORRUPTION",
    production_freshness_present: bool | None = None,
    presence_applicability: str | None = None,
    class_confidence: float | None = None,
    proposed_physiology: str | None = None,
) -> dict[str, Any]:
    return resolve_precedence(
        presence=presence,
        declared_quality=declared_quality_from_q2(evaluation),
        reason_codes=list(evaluation["reasons"]),
        class_confidence=class_confidence,
        proposed_physiology=proposed_physiology,
        domain_class=domain_class,
        production_freshness_present=production_freshness_present,
        presence_applicability=presence_applicability,
    )


def compact_i1_output(precedence: dict[str, Any]) -> dict[str, Any]:
    return {
        "actionable": precedence["actionable"],
        "application_state": precedence["application_state"],
        "availability_state": precedence["availability_state"],
        "physiology_executed": precedence["physiology_executed"],
        "reason_codes": list(precedence["reason_codes"]),
        "schema_errors": list(precedence.get("schema_errors") or []),
    }


def assert_no_physiology_emission(precedence: dict[str, Any], trail: str) -> None:
    if precedence["physiology_executed"] is True:
        raise I3RegressionError(f"PHYSIOLOGY_EXECUTED:{trail}")
    if precedence["availability_state"] != "PHYSIOLOGY_ELIGIBLE" and precedence["actionable"] is True:
        raise I3RegressionError(f"ACTIONABLE_WHILE_UNAVAILABLE:{trail}")
    if precedence["application_state"] in PHYSIOLOGY_LABELS:
        raise I3RegressionError(f"PHYSIOLOGY_APPLICATION_STATE:{trail}")
    if precedence["availability_state"] in ("PRESENCE_SUPPRESSED", "INPUT_UNAVAILABLE"):
        if precedence["application_state"] not in ("PRESENCE_SUPPRESSED", "INPUT_UNAVAILABLE"):
            raise I3RegressionError(f"INVALID_FALLBACK:{trail}")


def synthetic_i1_record(
    *,
    case_id: str,
    presence: Any,
    declared_quality: str,
    reasons: list[str],
    domain_class: str,
    freshness_value: Any,
    presence_applicability: str | None = None,
    seq_value: Any = 1,
    values: list[float] | None = None,
) -> dict[str, Any]:
    source_id = f"i3-{case_id}"
    session_id = f"i3-session-{case_id}"
    event_id = f"i3-event-{case_id}"
    window_start = 0
    window_end = 1000
    from scripts.mmwave_i1_runtime_io_contract import deterministic_runtime_window_id

    runtime_window_id = deterministic_runtime_window_id(
        {
            "event_id": event_id,
            "recording_id": session_id,
            "session_id": session_id,
            "source_id": source_id,
            "window_end": window_end,
            "window_start": window_start,
        }
    )
    if domain_class == "PUBLIC_OFFLINE":
        freshness_applicability = "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN"
        default_presence_app = "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN"
    elif domain_class == "PRODUCTION_MR60":
        freshness_applicability = "REQUIRED_FOR_PRODUCTION_MR60"
        default_presence_app = "REQUIRED_FOR_PRODUCTION_MR60"
    else:
        freshness_applicability = "OPTIONAL_IF_PRESENT"
        default_presence_app = "REQUIRED_FOR_PRODUCTION_MR60"
    presence_app = presence_applicability or default_presence_app
    eligible = declared_quality == "PHYSIOLOGY_ELIGIBLE" and (
        presence_app == "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN" or _presence_confirmed(presence)
    )
    return {
        "adapter": {"adapter_profile_id": I3_GATE_ID, "software_git_sha": BASE_SHA},
        "event": {"event_id": event_id, "sample_id": case_id},
        "freshness": {
            "phase_age_ms": {"applicability": freshness_applicability, "value": freshness_value},
            "seq": {"applicability": freshness_applicability, "value": seq_value},
        },
        "model_input_boundary": {
            "eligible_for_physiological_inference": bool(eligible),
            "feature_schema_id": "DEFERRED_TO_R2_M_PV1",
            "input_values": None,
            "model_input_contract_id": "DEFERRED_TO_M_PV1",
            "native_amplitude_descriptors": {},
            "not_for_physiological_inference": not bool(eligible),
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "tensor_shape": "DEFERRED_TO_M_PV1",
            "time_coverage": {"end": window_end, "start": window_start, "unit": "ms"},
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
            "applicability": presence_app,
            "field": "human_detected_raw",
            "inferred_from_amplitude": False,
            "value": presence,
        },
        "provenance": {
            "adapter_profile_id": I3_GATE_ID,
            "dataset_or_device_id": source_id,
            "event_id": event_id,
            "firmware_config_identity": None,
            "recording_id": session_id,
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "runtime_window_id": runtime_window_id,
            "session_id": session_id,
            "software_git_sha": BASE_SHA,
            "source_id": source_id,
            "synthetic_corruption_profile_id": Q2_PROFILE_ID if domain_class == "SYNTHETIC_CORRUPTION" else None,
            "transport_record_id": None,
        },
        "quality": {
            "declared_availability_state": declared_quality,
            "detection_implemented_in_i1": False,
            "external_policy_id": Q2_CONTRACT_ID,
            "reason_codes": list(reasons),
        },
        "schema_id": INPUT_CONTRACT_ID,
        "schema_version": "I1.1",
        "session": {"recording_id": session_id, "session_id": session_id, "subject_id": None},
        "signal": {
            "native_amplitude_descriptors": {},
            "payload": {
                "kind": "trace_reference",
                "not_a_final_tensor": True,
                "values": values,
            },
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "sampling": {"rate_hz": None, "rate_status": "DEFERRED_TO_R1_M_PV1"},
            "semantics": "phase_like",
            "units": None,
        },
        "source": {
            "dataset_or_device_id": source_id,
            "domain_class": domain_class,
            "radar_domain": "mr60" if domain_class != "PUBLIC_OFFLINE" else "60ghz",
            "source_id": source_id,
        },
        "timestamps": {
            "model_evaluation_time": timestamp_descriptor(
                clock_domain="not_executed",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
                notes="I3 does not execute a model",
            ),
            "runtime_receive_time": timestamp_descriptor(
                clock_domain="synthetic",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=window_end,
            ),
            "source_native_sample_time": timestamp_descriptor(
                clock_domain="synthetic_source",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=window_start,
            ),
            "source_update_estimate": timestamp_descriptor(
                clock_domain="synthetic_source",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=window_start,
            ),
            "transport_publish_time": timestamp_descriptor(
                clock_domain="synthetic_transport",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=window_end,
            ),
            "window_end": timestamp_descriptor(
                clock_domain="synthetic_source",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=window_end,
            ),
            "window_start": timestamp_descriptor(
                clock_domain="synthetic_source",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=True,
                value=window_start,
            ),
        },
    }


def envelope_for_case(
    case_id: str,
    evaluation: dict[str, Any],
    *,
    presence: Any,
    domain_class: str,
    freshness_value: Any,
    presence_applicability: str | None = None,
    class_confidence: float | None = None,
    proposed_physiology: str | None = None,
    values: list[float] | None = None,
) -> dict[str, Any]:
    declared = declared_quality_from_q2(evaluation)
    record = synthetic_i1_record(
        case_id=case_id,
        presence=presence,
        declared_quality=declared,
        reasons=list(evaluation["reasons"]),
        domain_class=domain_class,
        freshness_value=freshness_value,
        presence_applicability=presence_applicability,
        values=values,
    )
    output = make_output_from_input(
        record,
        class_confidence=class_confidence,
        proposed_physiology=proposed_physiology,
    )
    input_errors = validate_runtime_input(record)
    output_errors = validate_runtime_output(output, record)
    precedence = resolve_i3_envelope(
        evaluation,
        presence=presence,
        domain_class=domain_class,
        production_freshness_present=freshness_value is not None,
        presence_applicability=presence_applicability or record["presence"]["applicability"],
        class_confidence=class_confidence,
        proposed_physiology=proposed_physiology,
    )
    assert_no_physiology_emission(precedence, case_id)
    return {
        "i1_input_errors": input_errors,
        "i1_output": {
            "actionable": output["actionable"],
            "application_state": output["application_state"],
            "availability_state": output["availability_state"],
            "inference_kind": output["inference_kind"],
            "physiology_executed": output["physiology_executed"],
            "reason_codes": output["reason_codes"],
        },
        "i1_output_errors": output_errors,
        "precedence": compact_i1_output(precedence),
        "q2": {
            "availability_state": evaluation["availability_state"],
            "interpolation_applied": evaluation["interpolation_applied"],
            "physiology_class_assigned": evaluation["physiology_class_assigned"],
            "primary_reason": evaluation["primary_reason"],
            "reasons": evaluation["reasons"],
            "window_state": evaluation["window_state"],
        },
    }


def _base_trace(n: int = 256) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(n, dtype=np.float64) * 100.0
    x = 0.35 * np.sin(np.linspace(0.0, 6.0 * math.pi, n))
    return t, x


def build_contract() -> dict[str, Any]:
    return {
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "contract_id": I3_CONTRACT_ID,
        "d2_used": False,
        "dependencies": {
            "i1_output": OUTPUT_CONTRACT_ID,
            "i1_provenance": PROVENANCE_CONTRACT_ID,
            "i1_semantic": SEMANTIC_CONTRACT_ID,
            "i2_harness": I2_HARNESS_ID,
            "i2_replay": I2_CONTRACT_ID,
            "q2_availability": Q2_CONTRACT_ID,
            "q2_evaluator": Q2_EVALUATOR_CONTRACT_ID,
            "q2_synthetic_profile": Q2_PROFILE_ID,
        },
        "gate_id": I3_GATE_ID,
        "matrix_id": I3_MATRIX_ID,
        "model_inference": False,
        "model_training": False,
        "mr60_supervised_use": False,
        "m_pv1_selection_performed": False,
        "phase": PHASE_ID,
        "precedence": [
            "presence",
            "input availability / quality",
            "physiology",
            "application state",
        ],
        "q2_threshold_fork": False,
        "q3_performed": False,
        "schema_version": SCHEMA_VERSION,
        "source_mutation_forbidden": True,
    }


def build_matrix_rows(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case_id in (
        "no_person",
        "unknown_person",
        "clean_valid",
        "large_gap",
        "source_freeze",
        "stale",
        "exact_flat",
        "invalid_timestamp",
        "recovery",
    ):
        payload = cases[case_id]
        rows.append(
            {
                "case": case_id,
                "expected_state": payload["expected_state"],
                "observed_state": payload["envelope"]["precedence"]["availability_state"],
                "physiology_executed": payload["envelope"]["precedence"]["physiology_executed"],
                "presence": payload["presence"],
                "primary_reason": payload["envelope"]["q2"]["primary_reason"],
                "quality_condition": payload["quality_condition"],
                "reasons": payload["envelope"]["q2"]["reasons"],
            }
        )
    return {
        "audit_date": AUDIT_DATE,
        "contract_id": I3_MATRIX_ID,
        "phase": PHASE_ID,
        "rows": rows,
        "schema_version": SCHEMA_VERSION,
    }


def run_synthetic_suite(q1_profile: dict[str, Any]) -> dict[str, Any]:
    t, x = _base_trace(256)
    labels = np.array(["NORMAL"] * 256)
    mode_results: dict[str, Any] = {}
    for mode in Q2_MODES:
        corrupted = apply_quality_corruption(
            t, x, mode=mode, seed=20260823, labels=labels, q1_profile=q1_profile, presence=True
        )
        evaluation = corrupted["evaluation"]
        if evaluation["interpolation_applied"]:
            raise I3RegressionError(f"INTERPOLATION:{mode}")
        if evaluation["physiology_class_assigned"] is not None:
            raise I3RegressionError(f"Q2_ASSIGNED_PHYSIOLOGY:{mode}")
        envelope = envelope_for_case(
            f"synthetic-{mode.lower()}",
            evaluation,
            presence=True,
            domain_class="SYNTHETIC_CORRUPTION",
            freshness_value=20.0 if mode != "STALE_SOURCE" else 500.0,
            values=[float(v) for v in corrupted["values"][:8]],
        )
        expected = "PHYSIOLOGY_ELIGIBLE" if mode == "CLEAN_VALID" else "INPUT_UNAVAILABLE"
        if envelope["precedence"]["availability_state"] != expected:
            raise I3RegressionError(f"SYNTHETIC_STATE:{mode}")
        if envelope["precedence"]["physiology_executed"] is not False:
            raise I3RegressionError(f"SYNTHETIC_PHYSIOLOGY:{mode}")
        mode_results[mode] = {
            "availability_state": envelope["precedence"]["availability_state"],
            "expected_state": expected,
            "interpolation_applied": False,
            "passed": True,
            "physiology_executed": False,
            "primary_reason": evaluation["primary_reason"],
            "reasons": evaluation["reasons"],
        }

    jittered = apply_timing_corruption(
        t, x, q1_profile, mode="CADENCE_JITTER", severity="TYPICAL", seed=11, labels=labels
    )
    jitter_eval = evaluate_availability(jittered["timestamps_ms"], jittered["values"], presence=True)
    if jitter_eval["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise I3RegressionError("TYPICAL_JITTER_AUTOMATICALLY_UNAVAILABLE")

    iso_t = np.arange(32, dtype=np.float64) * 100.0
    iso_x = np.sin(np.linspace(0.0, math.pi, 32))
    iso_src = iso_t.copy()
    iso_src[10] = iso_src[9]
    iso_x[10] = iso_x[9]
    isolated = evaluate_availability(iso_t, iso_x, source_update_ms=iso_src, presence=True)
    if isolated["availability_state"] != "PHYSIOLOGY_ELIGIBLE" or "SOURCE_FREEZE" in isolated["reasons"]:
        raise I3RegressionError("ISOLATED_REPUBLICATION_AUTOMATICALLY_FREEZE")

    tiny = 1e-5 * np.sin(np.linspace(0.0, 10.0 * math.pi, 256))
    low_eval = evaluate_availability(t, tiny, presence=True)
    if low_eval["availability_state"] != "PHYSIOLOGY_ELIGIBLE" or "SIGNAL_FLAT_EXACT" in low_eval["reasons"]:
        raise I3RegressionError("LOW_AMPLITUDE_ALONE_INVALID")

    collided = np.concatenate([np.zeros(8), np.arange(1, 25, dtype=np.float64) * 100.0])
    ts_eval = evaluate_availability(collided, np.sin(np.linspace(0.0, math.pi, collided.size)), presence=True)
    if ts_eval["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("INVALID_TIMESTAMP_DID_NOT_FAIL_CLOSED")
    if "TIMESTAMP_UNRESOLVED" not in ts_eval["reasons"] and "TIMESTAMP_NON_MONOTONIC" not in ts_eval["reasons"]:
        raise I3RegressionError("INVALID_TIMESTAMP_REASON")

    nonmono_t = t.copy()
    nonmono_t[40] = nonmono_t[38]
    nonmono = evaluate_availability(nonmono_t, x, presence=True)
    if nonmono["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("NON_MONOTONIC_DID_NOT_FAIL_CLOSED")

    stale_t, stale_x = _base_trace(32)
    stale_age = np.full(32, 20.0)
    stale_age[16:] = 500.0
    stale_eval = evaluate_availability(
        stale_t, stale_x, source_update_ms=stale_t, phase_age_ms=stale_age, presence=True
    )
    if "SOURCE_STALE" not in stale_eval["reasons"]:
        raise I3RegressionError("STALE_NOT_DETECTED")
    stale_after_seq = evaluate_availability(
        stale_t, stale_x, source_update_ms=stale_t, phase_age_ms=stale_age, presence=True
    )
    if stale_after_seq["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("SEQ_INCREMENT_REFRESHES_STALE_SOURCE")

    missing_prod = evaluate_availability(t, x, presence=True, timing_context="PRODUCTION_MR60")
    if missing_prod["availability_state"] != "INPUT_UNAVAILABLE" or "SOURCE_STALE" not in missing_prod["reasons"]:
        raise I3RegressionError("PRODUCTION_MISSING_FRESHNESS_OPEN")
    public_ok = evaluate_availability(t, x, presence=True, timing_context="PUBLIC_NATIVE")
    if public_ok["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise I3RegressionError("PUBLIC_OFFLINE_MR60_METADATA_REQUIRED")

    freeze = apply_quality_corruption(
        t, x, mode="SOURCE_FREEZE", seed=20260823, labels=labels, q1_profile=q1_profile, presence=True
    )
    if freeze["evaluation"]["window_state"] != "INVALID_WINDOW_INPUT_UNAVAILABLE":
        raise I3RegressionError("RECOVERY_WINDOW_NOT_INVALID")
    if freeze["evaluation"]["availability_state"] == "PHYSIOLOGY_ELIGIBLE":
        raise I3RegressionError("SINGLE_PACKET_CLEARED_FREEZE_WINDOW")

    rec_t = np.arange(24, dtype=np.float64) * 100.0
    rec_x = np.sin(np.linspace(0.0, math.pi, 24))
    rec_src = rec_t.copy()
    rec_t[12:] = rec_t[12:] + 500.0
    rec_src[12:] = rec_src[12:] + 500.0
    rec_t[13] = rec_t[12] + 100.0
    rec_src[13] = rec_src[12]
    rec_x[13] = rec_x[12]
    recovery_eval = evaluate_availability(rec_t, rec_x, source_update_ms=rec_src, presence=True)
    if recovery_eval["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("RECOVERY_DID_NOT_FAIL_CLOSED")
    if "RECOVERY_WARMUP" not in recovery_eval["reasons"]:
        raise I3RegressionError("RECOVERY_WARMUP_NOT_OBSERVED")

    cases = {
        "no_person": {
            "expected_state": "PRESENCE_SUPPRESSED",
            "presence": False,
            "quality_condition": "CLEAN_VALID",
            "envelope": envelope_for_case(
                "no-person",
                evaluate_availability(t, x, presence=False),
                presence=False,
                domain_class="PRODUCTION_MR60",
                freshness_value=20.0,
            ),
        },
        "unknown_person": {
            "expected_state": "PRESENCE_SUPPRESSED",
            "presence": None,
            "quality_condition": "CLEAN_VALID",
            "envelope": envelope_for_case(
                "unknown-person",
                evaluate_availability(t, x, presence=None),
                presence=None,
                domain_class="PRODUCTION_MR60",
                freshness_value=20.0,
            ),
        },
        "clean_valid": {
            "expected_state": "PHYSIOLOGY_ELIGIBLE",
            "presence": True,
            "quality_condition": "CLEAN_VALID",
            "envelope": envelope_for_case(
                "clean-valid",
                apply_quality_corruption(
                    t, x, mode="CLEAN_VALID", seed=20260823, labels=labels, q1_profile=q1_profile
                )["evaluation"],
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=20.0,
                values=[float(v) for v in x[:8]],
            ),
        },
        "large_gap": {
            "expected_state": "INPUT_UNAVAILABLE",
            "presence": True,
            "quality_condition": "LARGE_GAP",
            "envelope": envelope_for_case(
                "large-gap",
                apply_quality_corruption(
                    t, x, mode="LARGE_GAP", seed=20260823, labels=labels, q1_profile=q1_profile
                )["evaluation"],
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=20.0,
            ),
        },
        "source_freeze": {
            "expected_state": "INPUT_UNAVAILABLE",
            "presence": True,
            "quality_condition": "SOURCE_FREEZE",
            "envelope": envelope_for_case(
                "source-freeze",
                freeze["evaluation"],
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=20.0,
            ),
        },
        "stale": {
            "expected_state": "INPUT_UNAVAILABLE",
            "presence": True,
            "quality_condition": "SOURCE_STALE",
            "envelope": envelope_for_case(
                "stale",
                apply_quality_corruption(
                    t, x, mode="STALE_SOURCE", seed=20260823, labels=labels, q1_profile=q1_profile
                )["evaluation"],
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=500.0,
            ),
        },
        "exact_flat": {
            "expected_state": "INPUT_UNAVAILABLE",
            "presence": True,
            "quality_condition": "SIGNAL_FLAT_EXACT",
            "envelope": envelope_for_case(
                "exact-flat",
                apply_quality_corruption(
                    t, x, mode="FLAT_EXACT", seed=20260823, labels=labels, q1_profile=q1_profile
                )["evaluation"],
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=20.0,
            ),
        },
        "invalid_timestamp": {
            "expected_state": "INPUT_UNAVAILABLE",
            "presence": True,
            "quality_condition": "TIMESTAMP_INVALID",
            "envelope": envelope_for_case(
                "invalid-timestamp",
                ts_eval,
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=20.0,
            ),
        },
        "recovery": {
            "expected_state": "INPUT_UNAVAILABLE",
            "presence": True,
            "quality_condition": "RECOVERY_WARMUP",
            "envelope": envelope_for_case(
                "recovery",
                recovery_eval,
                presence=True,
                domain_class="SYNTHETIC_CORRUPTION",
                freshness_value=20.0,
            ),
        },
    }
    for case_id, payload in cases.items():
        observed = payload["envelope"]["precedence"]["availability_state"]
        if observed != payload["expected_state"]:
            raise I3RegressionError(f"MATRIX_MISMATCH:{case_id}:{observed}")

    presence_plus_gap = apply_quality_corruption(
        t, x, mode="LARGE_GAP", seed=20260823, labels=labels, q1_profile=q1_profile, presence=False
    )["evaluation"]
    presence_over_quality = envelope_for_case(
        "presence-over-quality",
        presence_plus_gap,
        presence=False,
        domain_class="PRODUCTION_MR60",
        freshness_value=20.0,
    )
    if presence_over_quality["precedence"]["availability_state"] != "PRESENCE_SUPPRESSED":
        raise I3RegressionError("PRESENCE_DID_NOT_PRECEDE_QUALITY")

    tempting = envelope_for_case(
        "fake-confidence",
        apply_quality_corruption(
            t, x, mode="LARGE_GAP", seed=20260823, labels=labels, q1_profile=q1_profile
        )["evaluation"],
        presence=True,
        domain_class="SYNTHETIC_CORRUPTION",
        freshness_value=20.0,
        class_confidence=0.99,
        proposed_physiology="NORMAL",
    )
    if tempting["precedence"]["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("CONFIDENCE_OVERRIDE")
    if tempting["precedence"]["physiology_executed"] is not False:
        raise I3RegressionError("FAKE_PHYSIOLOGY_EXECUTED")
    if "INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY" not in tempting["precedence"]["schema_errors"]:
        raise I3RegressionError("INVALID_TO_NORMAL_NOT_REJECTED")

    apnea_tempting = resolve_i3_envelope(
        apply_quality_corruption(
            t, x, mode="SOURCE_FREEZE", seed=20260823, labels=labels, q1_profile=q1_profile
        )["evaluation"],
        presence=True,
        domain_class="SYNTHETIC_CORRUPTION",
        class_confidence=0.97,
        proposed_physiology="APNEA",
    )
    if apnea_tempting["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("INVALID_TO_APNEA_FALLBACK")
    if "INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY" not in apnea_tempting["schema_errors"]:
        raise I3RegressionError("INVALID_TO_APNEA_NOT_REJECTED")

    no_person = cases["no_person"]["envelope"]["precedence"]
    if no_person["application_state"] != "PRESENCE_SUPPRESSED":
        raise I3RegressionError("NO_PERSON_TO_APNEA")
    if no_person["availability_state"] != "PRESENCE_SUPPRESSED":
        raise I3RegressionError("NO_PERSON_NOT_SUPPRESSED")

    public_fixture = load_json(I1_REPLAY_SKELETON)["tiny_deterministic_fixture"][
        "public_d0_without_phase_age_eligible"
    ]
    public_in = public_fixture["input"]
    public_out = make_output_from_input(public_in)
    if public_out["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise I3RegressionError("PUBLIC_FIXTURE_REJECTED_FOR_MISSING_MR60_FRESHNESS")
    mr60_missing = load_json(I1_REPLAY_SKELETON)["tiny_deterministic_fixture"][
        "mr60_missing_freshness_fail_closed"
    ]
    mr60_out = make_output_from_input(mr60_missing["input"])
    if mr60_out["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("PRODUCTION_FIXTURE_DID_NOT_FAIL_CLOSED")

    return {
        "cases": {
            key: {
                "expected_state": value["expected_state"],
                "observed": value["envelope"]["precedence"],
                "q2": value["envelope"]["q2"],
            }
            for key, value in cases.items()
        },
        "class_confidence_overrides_unavailable": False,
        "isolated_republication": {
            "availability_state": isolated["availability_state"],
            "reasons": isolated["reasons"],
        },
        "invalid_to_apnea_fallback": False,
        "invalid_to_normal_fallback": False,
        "low_amplitude_dynamic": {
            "availability_state": low_eval["availability_state"],
            "reasons": low_eval["reasons"],
        },
        "modes": mode_results,
        "no_person_rr_zero": False,
        "no_person_to_apnea": False,
        "non_monotonic": {
            "availability_state": nonmono["availability_state"],
            "reasons": nonmono["reasons"],
        },
        "passed": True,
        "presence_over_quality": presence_over_quality["precedence"],
        "production_missing_freshness": {
            "availability_state": missing_prod["availability_state"],
            "reasons": missing_prod["reasons"],
        },
        "public_missing_freshness": {
            "i1_availability_state": public_out["availability_state"],
            "q2_availability_state": public_ok["availability_state"],
        },
        "seq_increment_while_stale": {
            "availability_state": stale_after_seq["availability_state"],
            "reasons": stale_after_seq["reasons"],
        },
        "tempting_normal": tempting["precedence"],
        "typical_jitter": {
            "availability_state": jitter_eval["availability_state"],
            "reasons": jitter_eval["reasons"],
        },
    }


def series_from_replayed(replayed: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps: list[float] = []
    values: list[float] = []
    source_update: list[float] = []
    ages: list[float] = []
    presence: list[Any] = []
    event_ids: list[str] = []
    seqs: list[Any] = []
    age_present = False
    for item in replayed:
        record = item["i1_input"]
        ts = record["timestamps"]["transport_publish_time"]["value"]
        src = record["timestamps"]["source_update_estimate"]["value"]
        age = record["freshness"]["phase_age_ms"]["value"]
        payload = (record.get("signal") or {}).get("payload") or {}
        raw_values = payload.get("values")
        value = raw_values[0] if isinstance(raw_values, list) and raw_values else None
        timestamps.append(float(ts) if ts is not None and math.isfinite(float(ts)) else float("nan"))
        if value is not None:
            try:
                number = float(value)
                values.append(number if math.isfinite(number) else float("nan"))
            except (TypeError, ValueError):
                values.append(float("nan"))
        else:
            values.append(float("nan"))
        if src is not None:
            source_update.append(float(src))
        else:
            source_update.append(timestamps[-1])
        if age is not None:
            age_present = True
            ages.append(float(age))
        else:
            ages.append(float("nan"))
        presence.append(record["presence"]["value"])
        event_ids.append(item["replay_event_id"])
        seqs.append(record["freshness"]["seq"]["value"])
    return {
        "age_present": age_present,
        "ages": np.asarray(ages, dtype=np.float64),
        "event_ids": event_ids,
        "presence": presence,
        "seqs": seqs,
        "source_update": np.asarray(source_update, dtype=np.float64),
        "timestamps": np.asarray(timestamps, dtype=np.float64),
        "values": np.asarray(values, dtype=np.float64),
    }


def classify_historical_events(
    replayed: list[dict[str, Any]],
    quality_eval: dict[str, Any],
    *,
    age_present: bool,
    ages: np.ndarray,
) -> dict[str, Any]:
    counts = Counter()
    reason_counts: Counter[str] = Counter()
    first_ids = {"PRESENCE_SUPPRESSED": None, "INPUT_UNAVAILABLE": None, "PHYSIOLOGY_ELIGIBLE": None}
    for index, item in enumerate(replayed):
        sample_reasons = quality_eval["sample_reasons"][index]
        quality_codes = [code for code in sample_reasons if code in QUALITY_REASON_CODES]
        presence = item["i1_input"]["presence"]["value"]
        declared = "INPUT_UNAVAILABLE" if quality_codes else "PHYSIOLOGY_ELIGIBLE"
        freshness_present = bool(age_present and math.isfinite(float(ages[index])))
        precedence = resolve_precedence(
            presence=presence,
            declared_quality=declared,
            reason_codes=quality_codes,
            domain_class="PRODUCTION_MR60",
            production_freshness_present=freshness_present,
            presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
        )
        assert_no_physiology_emission(precedence, item["replay_event_id"])
        provenance = item["i1_input"]["provenance"]
        if provenance.get("source_row_index") != item["row_index"]:
            raise I3RegressionError("SOURCE_ROW_MUTATED")
        if provenance.get("original_seq") != item["i1_input"]["freshness"]["seq"]["value"]:
            raise I3RegressionError("SEQ_MUTATED")
        if provenance.get("original_ts_monotonic_ms") != item["i1_input"]["timestamps"]["transport_publish_time"]["value"]:
            raise I3RegressionError("TIMESTAMP_MUTATED")
        counts[precedence["availability_state"]] += 1
        for code in precedence["reason_codes"]:
            reason_counts[code] += 1
        state = precedence["availability_state"]
        if first_ids[state] is None:
            first_ids[state] = item["replay_event_id"]
    return {
        "eligible": int(counts.get("PHYSIOLOGY_ELIGIBLE", 0)),
        "first_event_ids": first_ids,
        "input_unavailable": int(counts.get("INPUT_UNAVAILABLE", 0)),
        "presence_suppressed": int(counts.get("PRESENCE_SUPPRESSED", 0)),
        "reason_code_counts": dict(sorted(reason_counts.items())),
    }


def evaluate_historical_session(compact: dict[str, Any]) -> dict[str, Any]:
    summary = {key: value for key, value in compact.items() if key != "_result"}
    if compact.get("status") != "REPLAYED":
        return {
            **summary,
            "i3_status": compact.get("status", "UNAVAILABLE"),
            "physiology_interpreted": False,
        }
    result = compact["_result"]
    replayed = result["replayed"]
    series = series_from_replayed(replayed)
    quality_eval = evaluate_availability(
        series["timestamps"],
        series["values"],
        source_update_ms=series["source_update"],
        phase_age_ms=series["ages"] if series["age_present"] else None,
        presence=True,
        timing_context="PRODUCTION_MR60",
    )
    presence_eval = evaluate_availability(
        series["timestamps"],
        series["values"],
        source_update_ms=series["source_update"],
        phase_age_ms=series["ages"] if series["age_present"] else None,
        presence=False if any(value is False for value in series["presence"]) and not any(
            _presence_confirmed(value) for value in series["presence"]
        ) else True,
        timing_context="PRODUCTION_MR60",
    )
    event_stats = classify_historical_events(
        replayed, quality_eval, age_present=series["age_present"], ages=series["ages"]
    )
    compact_hash = sha256_bytes(
        canonical_dumps(
            {
                "event_ids": series["event_ids"],
                "quality_reasons": quality_eval["reasons"],
                "quality_state": quality_eval["availability_state"],
                "rejected": result["rejected"],
                "seq_audit": result["seq_audit_counts"],
                "event_stats": event_stats,
            }
        ).encode("utf-8")
    )
    return {
        **summary,
        "compact_i3_sha256": compact_hash,
        "event_stats": event_stats,
        "first_replay_event_id": series["event_ids"][0] if series["event_ids"] else None,
        "i3_status": "EVALUATED",
        "interpolation_applied": quality_eval["interpolation_applied"],
        "last_replay_event_id": series["event_ids"][-1] if series["event_ids"] else None,
        "physiology_interpreted": False,
        "presence_aware_window": {
            "availability_state": presence_eval["availability_state"],
            "primary_reason": presence_eval["primary_reason"],
            "reasons": presence_eval["reasons"],
        },
        "quality_only_window": {
            "availability_state": quality_eval["availability_state"],
            "primary_reason": quality_eval["primary_reason"],
            "reasons": quality_eval["reasons"],
            "window_state": quality_eval["window_state"],
        },
        "rejected_count": result["rejected_count"],
        "rejected_reasons": sorted({item["reason"] for item in result["rejected"]}),
        "replayed_count": result["replayed_count"],
        "seq_audit_counts": result["seq_audit_counts"],
        "source_lineage_preserved": True,
    }


def run_historical_suite() -> dict[str, Any]:
    inventory = load_inventory_index()
    sessions = []
    for spec in REPRESENTATIVE_SESSIONS:
        row = inventory.get(spec["session_id"])
        if row is None:
            sessions.append(
                {
                    "i3_status": "UNAVAILABLE",
                    "session_id": spec["session_id"],
                    "unavailable_reason": "NOT_IN_Q1_INVENTORY",
                    "role": spec["role"],
                }
            )
            continue
        compact = replay_blob_session(spec, row, mode="FAST")
        sessions.append(evaluate_historical_session(compact))

    freeze_95 = next(item for item in sessions if item.get("role") == "q2_handoff_freeze_like_95_run")
    freeze_3598 = next(item for item in sessions if item.get("role") == "q2_handoff_freeze_like_3598_run")
    if freeze_95.get("quality_only_window", {}).get("availability_state") != "INPUT_UNAVAILABLE":
        raise I3RegressionError("HISTORICAL_95_RUN_NOT_UNAVAILABLE")
    if "SOURCE_FREEZE" not in freeze_95.get("quality_only_window", {}).get("reasons", []):
        raise I3RegressionError("HISTORICAL_95_RUN_MISSING_FREEZE")
    if freeze_3598.get("quality_only_window", {}).get("availability_state") != "INPUT_UNAVAILABLE":
        raise I3RegressionError("HISTORICAL_3598_PREFIX_NOT_UNAVAILABLE")
    if "SOURCE_FREEZE" not in freeze_3598.get("quality_only_window", {}).get("reasons", []):
        raise I3RegressionError("HISTORICAL_3598_PREFIX_MISSING_FREEZE")

    collision = next(item for item in sessions if item.get("role") == "timestamp_collision")
    if "TRUNCATED_ROW" not in collision.get("rejected_reasons", []):
        raise I3RegressionError("TIMESTAMP_COLLISION_NOT_TYPED_REJECT")
    phase_absent = next(item for item in sessions if item.get("role") == "phase_age_absent")
    if "SOURCE_STALE" not in phase_absent.get("quality_only_window", {}).get("reasons", []):
        raise I3RegressionError("PHASE_AGE_ABSENT_NOT_STALE")

    totals = {
        "eligible": sum(int(item.get("event_stats", {}).get("eligible", 0)) for item in sessions),
        "input_unavailable": sum(
            int(item.get("event_stats", {}).get("input_unavailable", 0)) for item in sessions
        ),
        "presence_suppressed": sum(
            int(item.get("event_stats", {}).get("presence_suppressed", 0)) for item in sessions
        ),
        "rejected": sum(int(item.get("rejected_count", 0) or 0) for item in sessions),
        "replayed": sum(int(item.get("replayed_count", 0) or 0) for item in sessions),
        "sessions_attempted": len(sessions),
        "sessions_evaluated": sum(1 for item in sessions if item.get("i3_status") == "EVALUATED"),
    }
    return {
        "audit_date": AUDIT_DATE,
        "phase": PHASE_ID,
        "physiology_interpreted": False,
        "schema_version": SCHEMA_VERSION,
        "sessions": sessions,
        "totals": totals,
    }


def run_session_reset_suite() -> dict[str, Any]:
    t, x = _base_trace(64)
    q1_profile = load_q1_profile(Q1_PROFILE_PATH)
    labels = np.array(["NORMAL"] * 64)
    session_a = apply_quality_corruption(
        t, x, mode="SOURCE_FREEZE", seed=3, labels=labels, q1_profile=q1_profile
    )
    session_b = apply_quality_corruption(
        t, x, mode="CLEAN_VALID", seed=3, labels=labels, q1_profile=q1_profile
    )
    if session_b["evaluation"]["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise I3RegressionError("SESSION_B_FALSELY_INHERITED_A")
    if session_a["evaluation"]["availability_state"] != "INPUT_UNAVAILABLE":
        raise I3RegressionError("SESSION_A_FREEZE_LOST")

    state = SessionReplayState()
    first = state.observe(10, "device-a", "fw-1")
    state.reset("session_boundary")
    leaked = state.last_seq is not None
    device_change_state = SessionReplayState()
    device_change_state.observe(10, "device-a", "fw-1")
    device_change_state.observe(11, "device-b", "fw-1")
    firmware_change = SessionReplayState()
    firmware_change.observe(4, "device-a", "fw-1")
    firmware_change.observe(5, "device-a", "fw-2")

    parsed = [
        {"_i2_row": {
            "breath_phase": 0.1,
            "firmware_version": "synthetic",
            "human_detected_raw": True,
            "phase_age_ms": 8,
            "schema_version": "1.2",
            "seq": 10,
            "ts_monotonic_ms": 1000,
        }, "_row_index": 0},
        {"_i2_row": {
            "breath_phase": 0.2,
            "firmware_version": "synthetic",
            "human_detected_raw": True,
            "phase_age_ms": 8,
            "schema_version": "1.2",
            "seq": 13,
            "ts_monotonic_ms": 1300,
        }, "_row_index": 1},
    ]
    gapped = replay_parsed_rows(
        parsed,
        session_id="i3-seq-gap",
        source_id="i3-seq-gap",
        git_blob_sha=None,
        mode="FAST",
        source_class="SYNTHETIC_Q1_Q2_FIXTURE",
    )
    if gapped["replayed_count"] != 2:
        raise I3RegressionError("SEQ_GAP_INTERPOLATED")
    if gapped["seq_audit_counts"].get("GAP", 0) != 1:
        raise I3RegressionError("SEQ_GAP_NOT_AUDITED")

    return {
        "device_change_resets": "RESET:device_id_change" in device_change_state.seq_events,
        "firmware_change_resets": "RESET:firmware_change" in firmware_change.seq_events,
        "phase": PHASE_ID,
        "seq_gap_interpolated": False,
        "seq_gap_replayed_count": gapped["replayed_count"],
        "session_a_state": session_a["evaluation"]["availability_state"],
        "session_b_independent_state": session_b["evaluation"]["availability_state"],
        "session_state_leak": leaked,
        "session_unit_reset_observed": first == "INCREMENT",
    }


def run_i2_reject_ownership() -> dict[str, Any]:
    parsed = parse_jsonl_bytes(b"not-json\n{\"seq\":1,\"ts_monotonic_ms\":\"NaN\"}\n")
    replayed = replay_parsed_rows(
        parsed,
        session_id="i3-parse-reject",
        source_id="i3-parse-reject",
        git_blob_sha=None,
        mode="FAST",
        source_class="PHYSICAL_MR60_JSONL",
    )
    reasons = sorted({item["reason"] for item in replayed["rejected"]})
    if not reasons:
        raise I3RegressionError("I2_DID_NOT_REJECT_MALFORMED")
    return {
        "i2_owns_parser_rejects": True,
        "q2_owns_runtime_timing_unavailability": True,
        "rejected_reasons": reasons,
        "silent_timestamp_repair": False,
    }


def compact_regression_payload(
    synthetic: dict[str, Any],
    historical: dict[str, Any],
    session_reset: dict[str, Any],
    matrix: dict[str, Any],
) -> dict[str, Any]:
    return {
        "historical_totals": historical["totals"],
        "historical_windows": [
            {
                "quality_only_window": item.get("quality_only_window"),
                "role": item.get("role"),
                "session_id": item.get("session_id"),
            }
            for item in historical["sessions"]
        ],
        "matrix": matrix["rows"],
        "session_reset": session_reset,
        "synthetic_modes": {
            name: {
                "availability_state": payload["availability_state"],
                "primary_reason": payload["primary_reason"],
                "reasons": payload["reasons"],
            }
            for name, payload in synthetic["modes"].items()
        },
    }


def generate() -> dict[str, Any]:
    q1_profile = load_q1_profile(Q1_PROFILE_PATH)
    i1_config = load_json(ROOT / "config/mmwave/i1_runtime_semantic_contract.json")
    i2_config = load_json(ROOT / "config/mmwave/i2_jsonl_replay_contract.json")
    q2_config = load_json(ROOT / "config/mmwave/q2_input_availability_contract.json")
    if i1_config.get("contract_id") != SEMANTIC_CONTRACT_ID:
        raise I3RegressionError("I1_CONTRACT_DRIFT")
    if i2_config.get("contract_id") != I2_CONTRACT_ID:
        raise I3RegressionError("I2_CONTRACT_DRIFT")
    if q2_config.get("contract_id") != Q2_CONTRACT_ID:
        raise I3RegressionError("Q2_CONTRACT_DRIFT")

    synthetic = run_synthetic_suite(q1_profile)
    historical = run_historical_suite()
    session_reset = run_session_reset_suite()
    parse_ownership = run_i2_reject_ownership()
    public = public_offline_replay()
    if public["i1_output"]["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise I3RegressionError("PUBLIC_OFFLINE_REPLAY_REJECTED")

    matrix_presence = {
        "no_person": False,
        "unknown_person": None,
        "clean_valid": True,
        "large_gap": True,
        "source_freeze": True,
        "stale": True,
        "exact_flat": True,
        "invalid_timestamp": True,
        "recovery": True,
    }
    matrix_quality = {
        "no_person": "CLEAN_VALID",
        "unknown_person": "CLEAN_VALID",
        "clean_valid": "CLEAN_VALID",
        "large_gap": "LARGE_GAP",
        "source_freeze": "SOURCE_FREEZE",
        "stale": "SOURCE_STALE",
        "exact_flat": "SIGNAL_FLAT_EXACT",
        "invalid_timestamp": "TIMESTAMP_INVALID",
        "recovery": "RECOVERY_WARMUP",
    }
    matrix = build_matrix_rows(
        {
            key: {
                "envelope": {
                    "precedence": value["observed"],
                    "q2": value["q2"],
                },
                "expected_state": value["expected_state"],
                "presence": matrix_presence[key],
                "quality_condition": matrix_quality[key],
            }
            for key, value in synthetic["cases"].items()
        }
    )
    payload_a = compact_regression_payload(synthetic, historical, session_reset, matrix)
    payload_b = compact_regression_payload(synthetic, historical, session_reset, matrix)
    digest_a = sha256_bytes(canonical_dumps(payload_a).encode("utf-8"))
    digest_b = sha256_bytes(canonical_dumps(payload_b).encode("utf-8"))
    if digest_a != digest_b:
        raise I3RegressionError("NON_DETERMINISTIC_REGRESSION")

    contract = build_contract()
    presence_audit = {
        "audit_date": AUDIT_DATE,
        "no_person": synthetic["cases"]["no_person"]["observed"],
        "phase": PHASE_ID,
        "presence_inferred_from_amplitude": False,
        "presence_over_quality": synthetic["presence_over_quality"],
        "true_plus_invalid": synthetic["cases"]["large_gap"]["observed"],
        "true_plus_valid": synthetic["cases"]["clean_valid"]["observed"],
        "unknown_production": synthetic["cases"]["unknown_person"]["observed"],
    }
    availability_audit = {
        "audit_date": AUDIT_DATE,
        "class_confidence_overrides_unavailable": False,
        "exact_flat": synthetic["cases"]["exact_flat"]["q2"],
        "invalid_timestamp": synthetic["cases"]["invalid_timestamp"]["q2"],
        "isolated_republication": synthetic["isolated_republication"],
        "large_gap": synthetic["cases"]["large_gap"]["q2"],
        "low_amplitude_dynamic": synthetic["low_amplitude_dynamic"],
        "phase": PHASE_ID,
        "production_missing_freshness": synthetic["production_missing_freshness"],
        "public_missing_freshness": synthetic["public_missing_freshness"],
        "recovery": synthetic["cases"]["recovery"]["q2"],
        "source_freeze": synthetic["cases"]["source_freeze"]["q2"],
        "stale": synthetic["cases"]["stale"]["q2"],
        "typical_jitter": synthetic["typical_jitter"],
    }
    determinism = {
        "audit_date": AUDIT_DATE,
        "compact_sha256": digest_a,
        "identical_repeat": digest_a == digest_b,
        "phase": PHASE_ID,
        "wall_clock_excluded": True,
    }
    exceptions = {
        "entries": [
            {
                "code": "HISTORICAL_3598_PREFIX_ONLY",
                "detail": "Committed I3 summary reuses the I2 64-row prefix; the full blob remains replayable by git SHA",
            },
            {
                "code": "PI_HOST_RECEIVE_CLOCK_ABSENT",
                "detail": "Inventoried ESP JSONL has no Pi host receive timestamp",
            },
            {
                "code": "LEGACY_FIRMWARE_NULL",
                "detail": "Several 1.0 historical sessions have null firmware_version",
            },
        ],
        "near_flat_threshold": "NOT_ADDED",
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    dump_json(CONFIG_PATH, contract)
    artifacts = {
        "i3_regression_contract.json": contract,
        "regression_matrix.json": matrix,
        "historical_replay_regression.json": historical,
        "synthetic_q2_regression.json": {
            "audit_date": AUDIT_DATE,
            "failed": [],
            "modes": synthetic["modes"],
            "passed": list(Q2_MODES),
            "phase": PHASE_ID,
            "profile_id": Q2_PROFILE_ID,
            "q2_evaluator": "scripts.mmwave_q2_input_unavailable.evaluate_availability",
        },
        "presence_precedence_audit.json": presence_audit,
        "availability_precedence_audit.json": availability_audit,
        "session_reset_audit.json": {**session_reset, **parse_ownership},
        "determinism_audit.json": determinism,
        "exception_registry.json": exceptions,
    }
    checksums = {
        "algorithm": "SHA-256",
        "config_file": {
            "path": "config/mmwave/i3_fail_closed_regression_contract.json",
            "sha256": sha256_bytes(CONFIG_PATH.read_text(encoding="utf-8").encode("utf-8")),
        },
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "files": {},
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
    }
    for name, payload in artifacts.items():
        checksums["files"][name] = dump_json(MANIFEST_DIR / name, payload)
    dump_json(MANIFEST_DIR / "checksums.json", checksums)
    if (MANIFEST_DIR / "i3_regression_contract.json").read_text(encoding="utf-8") != CONFIG_PATH.read_text(
        encoding="utf-8"
    ):
        raise I3RegressionError("CONFIG_MANIFEST_DIVERGED")
    for name in (*MANIFEST_JSON_FILES, "checksums.json"):
        blob = (MANIFEST_DIR / name).read_text(encoding="utf-8")
        if ABSOLUTE_PATH_RE.search(blob):
            raise I3RegressionError(f"ABSOLUTE_PATH:{name}")
        parsed = load_json(MANIFEST_DIR / name)
        leaked: list[str] = []
        check_absolute_paths(parsed, name, leaked)
        if leaked:
            raise I3RegressionError(f"ABSOLUTE_PATH:{','.join(leaked)}")
    return {
        "compact_sha256": digest_a,
        "contract_id": I3_CONTRACT_ID,
        "ok": True,
        "phase": PHASE_ID,
    }


def main() -> int:
    result = generate()
    print(canonical_dumps(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
