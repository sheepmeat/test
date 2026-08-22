#!/usr/bin/env python3
"""I2 mapping from historical MR60 JSONL rows into frozen I1 envelopes.

Parsing stays here. Q2 detectors, R1 traces, and model inference stay outside.
"""

from __future__ import annotations

import math
from typing import Any

from scripts.mmwave_i1_runtime_io_contract import (
    BASE_SHA as I1_DOCUMENTED_BASE_SHA,
    INPUT_CONTRACT_ID,
    Q2_CONTRACT_ID,
    SCHEMA_VERSION as I1_SCHEMA_VERSION,
    deterministic_runtime_window_id,
    make_output_from_input,
    timestamp_descriptor,
)

I2_CONTRACT_ID = "MMWAVE_V2_I2_HISTORICAL_JSONL_REPLAY_CONTRACT_V1"
I2_HARNESS_ID = "MMWAVE_V2_I2_REPLAY_HARNESS_V1"
I2_RESULT_SCHEMA_ID = "MMWAVE_V2_I2_REPLAY_RESULT_SCHEMA_V1"

KNOWN_MR60_FIELDS = {
    "breath_age_ms",
    "breath_filtered_valid",
    "breath_phase",
    "breath_phase_std",
    "breath_rate_filtered",
    "breath_rate_raw",
    "breath_rate_raw_trusted",
    "breath_raw_valid",
    "breath_window_ready",
    "checksum_errors",
    "checksum_ok",
    "config_hash",
    "consecutive_uart_errors",
    "device_id",
    "distance_age_ms",
    "distance_cm_raw",
    "distance_std_cm",
    "error_code",
    "firmware_version",
    "freeze_detected",
    "heart_age_ms",
    "heart_phase",
    "heart_rate_raw",
    "heart_raw_valid",
    "heart_verified",
    "human_detected_raw",
    "human_detected_stable",
    "parse_errors",
    "phase_age_ms",
    "presence_age_ms",
    "schema_version",
    "sensor_firmware_version",
    "sensor_state",
    "seq",
    "session_id",
    "total_phase",
    "ts_monotonic_ms",
    "uart_frame_ok",
    "uart_frames_total",
    "vital_presence_detected",
}

PHYSIOLOGY_LABELS = {"NORMAL", "RAPID_OR_ABNORMAL", "APNEA", "APNEA_PROXY"}


def field_status(row: dict[str, Any], name: str, *, production_required: bool) -> tuple[str, Any]:
    if name not in row:
        if production_required:
            return "FIELD_REQUIRED_BUT_MISSING_FOR_PRODUCTION", None
        return "FIELD_ABSENT_LEGACY", None
    return "FIELD_PRESENT", row[name]


def classify_schema(row: dict[str, Any]) -> str:
    raw = row.get("schema_version")
    if raw in (None, ""):
        return "legacy_unversioned"
    text = str(raw)
    if text in ("1.0", "1.1", "1.2"):
        return text
    return "unsupported"


def finite_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def parse_status_for_row(row: dict[str, Any] | None, raw_line: str | None = None) -> str | None:
    if row is None:
        text = (raw_line or "").strip()
        if text and not text.startswith("{"):
            return "TRUNCATED_ROW"
        return "INVALID_JSON"
    if classify_schema(row) == "unsupported":
        return "UNSUPPORTED_SCHEMA"
    if "ts_monotonic_ms" not in row and "seq" not in row:
        return "MISSING_REQUIRED_EVENT_IDENTITY"
    if "ts_monotonic_ms" in row and not finite_number(row.get("ts_monotonic_ms")):
        return "NON_NUMERIC_TIMESTAMP"
    for signal_key in ("breath_phase", "total_phase"):
        if signal_key in row and row[signal_key] is not None and not finite_number(row[signal_key]):
            return "NON_FINITE_SIGNAL"
    return None


def replay_event_id(
    *,
    source_id: str,
    session_id: str,
    row_index: int,
    seq: Any,
    timestamp_ms: Any,
    git_blob_sha: str | None,
) -> str:
    from scripts.mmwave_i1_runtime_io_contract import canonical_dumps, sha256_bytes

    payload = {
        "git_blob_sha": git_blob_sha,
        "i2_contract_id": I2_CONTRACT_ID,
        "row_index": row_index,
        "seq": seq,
        "session_id": session_id,
        "source_id": source_id,
        "ts_monotonic_ms": timestamp_ms,
    }
    digest = sha256_bytes(canonical_dumps(payload).encode("utf-8"))
    return f"replay_event:{digest}"


def map_mr60_row_to_i1(
    row: dict[str, Any],
    *,
    session_id: str,
    row_index: int,
    git_blob_sha: str | None,
    source_id: str,
    replay_harness_sha: str,
    synthetic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema = classify_schema(row)
    production_required_freshness = schema in ("1.0", "1.1", "1.2")
    ts_status, ts_value = field_status(row, "ts_monotonic_ms", production_required=True)
    age_status, age_value = field_status(
        row, "phase_age_ms", production_required=production_required_freshness
    )
    if schema == "legacy_unversioned" and age_status != "FIELD_PRESENT":
        age_status = "FIELD_ABSENT_LEGACY"
    seq_status, seq_value = field_status(row, "seq", production_required=True)
    presence_status, presence_value = field_status(
        row, "human_detected_raw", production_required=False
    )
    source_update = None
    source_update_authoritative = False
    if ts_status == "FIELD_PRESENT" and age_status == "FIELD_PRESENT":
        source_update = float(ts_value) - float(age_value)
        source_update_authoritative = False
    event_id = f"row-{row_index}"
    window_start = ts_value if ts_status == "FIELD_PRESENT" else None
    runtime_window_id = deterministic_runtime_window_id(
        {
            "event_id": event_id,
            "recording_id": git_blob_sha or session_id,
            "session_id": session_id,
            "source_id": source_id,
            "window_end": window_start,
            "window_start": window_start,
        }
    )
    auxiliary = {key: value for key, value in row.items() if key not in KNOWN_MR60_FIELDS}
    domain = "SYNTHETIC_CORRUPTION" if synthetic else "PRODUCTION_MR60"
    envelope = {
        "adapter": {
            "adapter_profile_id": I2_HARNESS_ID,
            "software_git_sha": replay_harness_sha,
        },
        "event": {"event_id": event_id, "sample_id": seq_value, "source_row_index": row_index},
        "freshness": {
            "phase_age_ms": {"applicability": "REQUIRED_FOR_PRODUCTION_MR60", "status": age_status, "value": age_value},
            "seq": {"applicability": "REQUIRED_FOR_PRODUCTION_MR60", "status": seq_status, "value": seq_value},
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
            "time_coverage": {"end": window_start, "start": window_start, "unit": "ms"},
            "validity_mask": None,
        },
        "mr60_telemetry": {
            "auxiliary": auxiliary,
            "breath_phase": {"applicability": "OPTIONAL_MR60_TELEMETRY_NOT_V2_RR_TRUTH", "value": row.get("breath_phase")},
            "breath_rate_raw": {
                "status": "AUXILIARY_TELEMETRY_NOT_V2_RR_TRUTH",
                "used_as_v2_supervised_rr_truth": False,
                "value": row.get("breath_rate_raw") if "breath_rate_raw" in row else None,
            },
            "config_hash": row.get("config_hash"),
            "device_id": row.get("device_id"),
            "firmware_version": row.get("firmware_version"),
            "schema_version": row.get("schema_version"),
            "session_id_field": row.get("session_id"),
            "ts_monotonic_ms": {
                "applicability": "REQUIRED_FOR_PRODUCTION_MR60_AS_RECEIVE_OR_PUBLISH_CLOCK",
                "not_physical_radar_acquisition_time": True,
                "status": ts_status,
                "value": ts_value,
            },
        },
        "presence": {
            "applicability": "REQUIRED_FOR_PRODUCTION_MR60",
            "field": "human_detected_raw",
            "inferred_from_amplitude": False,
            "status": presence_status,
            "value": presence_value,
        },
        "provenance": {
            "adapter_profile_id": I2_HARNESS_ID,
            "dataset_or_device_id": source_id,
            "event_id": event_id,
            "firmware_config_identity": row.get("firmware_version"),
            "git_blob_sha": git_blob_sha,
            "i1_documented_base_sha": I1_DOCUMENTED_BASE_SHA,
            "original_seq": seq_value,
            "original_ts_monotonic_ms": ts_value,
            "recording_id": git_blob_sha or session_id,
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "runtime_window_id": runtime_window_id,
            "session_id": session_id,
            "software_git_sha": replay_harness_sha,
            "source_id": source_id,
            "source_row_index": row_index,
            "synthetic_corruption_profile_id": None if not synthetic else synthetic.get("profile_id"),
            "transport_record_id": None,
        },
        "quality": {
            "declared_availability_state": "NOT_EVALUATED",
            "detection_implemented_in_i1": False,
            "external_policy_id": Q2_CONTRACT_ID,
            "reason_codes": [],
        },
        "schema_id": INPUT_CONTRACT_ID,
        "schema_version": I1_SCHEMA_VERSION,
        "session": {
            "recording_id": git_blob_sha or session_id,
            "session_id": session_id,
            "subject_id": None,
        },
        "signal": {
            "native_amplitude_descriptors": {},
            "payload": {
                "kind": "trace_reference",
                "not_a_final_tensor": True,
                "values": [row.get("breath_phase")] if "breath_phase" in row else None,
            },
            "representation_profile_id": "DEFERRED_TO_R1_R2_R3",
            "sampling": {"rate_hz": None, "rate_status": "DEFERRED_TO_R1_M_PV1"},
            "semantics": "unspecified_native",
            "units": None,
        },
        "source": {
            "dataset_or_device_id": source_id,
            "domain_class": domain,
            "radar_domain": "mr60",
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
                notes="I2 does not execute a model",
            ),
            "runtime_receive_time": timestamp_descriptor(
                clock_domain="pi_receive",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
                notes="Pi host receive timestamp UNAVAILABLE in inventoried ESP JSONL",
            ),
            "source_native_sample_time": timestamp_descriptor(
                clock_domain="unknown_physical_radar",
                unit="ms",
                monotonic_or_wall="unspecified",
                reconstructed=False,
                authoritative=False,
                value=None,
                notes="ESP ts_monotonic_ms is not physical radar acquisition time",
            ),
            "source_update_estimate": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms_minus_phase_age_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=True,
                authoritative=source_update_authoritative,
                value=source_update,
                notes="carried only when ts_monotonic_ms and phase_age_ms are present; not physical acquisition time",
            ),
            "transport_publish_time": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=ts_status == "FIELD_PRESENT",
                value=ts_value,
                notes="ESP publish/monotonic clock, not physical radar acquisition time",
            ),
            "window_end": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=window_start,
                notes="row-level replay; not a physiological model window",
            ),
            "window_start": timestamp_descriptor(
                clock_domain="esp_ts_monotonic_ms",
                unit="ms",
                monotonic_or_wall="monotonic",
                reconstructed=False,
                authoritative=False,
                value=window_start,
                notes="row-level replay; not a physiological model window",
            ),
        },
    }
    if synthetic:
        envelope["provenance"].update(
            {
                "original_sample_index": synthetic.get("original_sample_index"),
                "synthetic_corruption_mode": synthetic.get("mode"),
                "synthetic_corruption_seed": synthetic.get("seed"),
                "synthetic_corruption_severity": synthetic.get("severity"),
            }
        )
    return envelope


def i1_output_for_replay(i1_input: dict[str, Any]) -> dict[str, Any]:
    output = make_output_from_input(i1_input)
    if any(
        str(output.get(key, "")).upper() in PHYSIOLOGY_LABELS
        or (isinstance(output.get(key), dict) and str(output[key].get("value")).upper() in PHYSIOLOGY_LABELS)
        for key in ("application_state", "breathing_evidence", "rr", "temporal_hold")
    ):
        raise RuntimeError("PHYSIOLOGY_CLASS_EMITTED")
    if output.get("physiology_executed") is not False:
        raise RuntimeError("REAL_MODEL_INFERENCE")
    return output
