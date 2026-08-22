"""Pure target-semantics helpers for SafeNest mmWave V2 R3.

R3 deliberately consumes compact, authoritative D0/D1 evidence.  It does
not decode radar payloads, infer labels from radar amplitude, train a model,
or select a representation.  The helpers are kept side-effect free so the
runner and focused safety tests share exactly the same semantics.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


R3_ROW_SCHEMA_VERSION = "MMWAVE_V2_R3_TARGET_ROW_V1"
BREATHING_TARGET_ID = "MMWAVE_V2_R3_BREATHING_EVIDENCE_TARGET_V1"
RR_TARGET_ID = "MMWAVE_V2_R3_RR_TARGET_V1"
TEMPORAL_HOLD_TARGET_ID = "MMWAVE_V2_R3_TEMPORAL_HOLD_TARGET_V1"
SUPERVISION_ELIGIBILITY_ID = "MMWAVE_V2_R3_MODEL_SUPERVISION_ELIGIBILITY_V1"

D0_RR_REFERENCE_METHOD = "INHERITED_A4_MOVESENSE_CHEST_ACC_SPECTRAL_PEAK_V1"
D0_REFERENCE_SOURCE = "D0_MOVESENSE_CHEST_ACC_AND_VOLUNTARY_NON_BREATHING_AUDIT"
D1_REFERENCE_SOURCE = "D1_SYNCHRONIZED_RESPIRATION_CHANNEL"


class R3TargetError(ValueError):
    """Raised when an authoritative target row cannot be interpreted safely."""


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _finite_number(value: Any) -> bool:
    return _finite_float(value) is not None


def _rounded(value: Any, digits: int = 9) -> float | None:
    number = _finite_float(value)
    return round(number, digits) if number is not None else None


def _json_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _window_start_s(window: Mapping[str, Any]) -> float:
    start_index = _finite_float(window.get("source_start_index"))
    if start_index is None:
        start_index = _finite_float(window.get("canonical_start_index"))
    if start_index is None:
        raise R3TargetError("D0 window is missing a finite source start index")
    # A6's authoritative D0 canonical timeline is exact native 10 Hz.
    return start_index / 10.0


def _window_end_s(window: Mapping[str, Any], start_s: float) -> float:
    end_index = _finite_float(window.get("source_end_index_exclusive"))
    if end_index is not None:
        return end_index / 10.0
    duration = _finite_float(window.get("duration_seconds"))
    if duration is None or duration <= 0:
        raise R3TargetError("D0 window is missing a finite duration/end index")
    return start_s + duration


def _event_bounds(window: Mapping[str, Any]) -> tuple[float, float, str] | None:
    events = [event for event in _json_list(window.get("annotation_events_overlapping")) if isinstance(event, Mapping)]
    if not events:
        return None
    ordered = sorted(
        events,
        key=lambda event: (
            _finite_float(event.get("event_start_seconds"))
            if _finite_float(event.get("event_start_seconds")) is not None
            else math.inf,
            str(event.get("event_id", "")),
        ),
    )
    event = ordered[0]
    start = _finite_float(event.get("event_start_seconds"))
    end = _finite_float(event.get("event_end_seconds"))
    event_id = str(event.get("event_id") or "")
    if start is None or end is None or end <= start or not event_id:
        raise R3TargetError("D0 annotation event has invalid onset/offset identity")
    return start, end, event_id


def _radar_input_status(window: Mapping[str, Any]) -> tuple[bool, str, list[str]]:
    reasons: list[str] = []
    metrics = window.get("signal_quality_metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    # A6 ``AMBIGUOUS`` is an annotation/transition state, not a Q2 input
    # failure.  It must remain available for event-relative target audit.
    if window.get("assignment_status") not in {None, "ASSIGNED", "AMBIGUOUS"}:
        reasons.append("WINDOW_NOT_ASSIGNED")
    if window.get("timeline_valid") is False:
        reasons.append("TIMELINE_INVALID")
    if metrics.get("has_nan") is True:
        reasons.append("SIGNAL_NAN")
    if metrics.get("has_inf") is True:
        reasons.append("SIGNAL_INF")
    if _finite_float(window.get("large_gap_count")) not in (None, 0.0):
        reasons.append("LARGE_GAP")
    if _finite_float(window.get("interpolated_sample_count")) not in (None, 0.0):
        reasons.append("INTERPOLATED_INPUT")
    if metrics.get("is_exact_constant") is True:
        reasons.append("SIGNAL_FLAT_EXACT")
    if reasons:
        return False, "INPUT_UNAVAILABLE", sorted(set(reasons))
    return True, "PHYSIOLOGY_ELIGIBLE", []


def _rr_info(window: Mapping[str, Any]) -> Mapping[str, Any]:
    info = window.get("movesense_reference_rr")
    return info if isinstance(info, Mapping) else {}


def _reference_rr_is_valid(info: Mapping[str, Any]) -> bool:
    rr = _finite_float(info.get("rr_bpm"))
    peak = _finite_float(info.get("peak_freq_hz"))
    sample_count = _finite_float(info.get("sample_count"))
    band = info.get("search_band_hz")
    return (
        rr is not None
        and rr > 0
        and peak is not None
        and peak > 0
        and sample_count is not None
        and sample_count > 0
        and isinstance(band, list)
        and len(band) == 2
        and all(_finite_number(item) for item in band)
    )


def _breathing_state(
    window: Mapping[str, Any],
    radar_input_available: bool,
) -> tuple[str, str, bool, float, tuple[float, float]]:
    start_s = _window_start_s(window)
    end_s = _window_end_s(window, start_s)
    duration_s = end_s - start_s
    if duration_s <= 0:
        raise R3TargetError("D0 window has non-positive evaluation duration")
    if not radar_input_available:
        return "TARGET_UNAVAILABLE", "INVALID_RADAR_INPUT", False, 0.0, (start_s, end_s)

    event = _event_bounds(window)
    overlap = max(0.0, _finite_float(window.get("annotation_overlap_seconds")) or 0.0)
    if event is not None or overlap > 0.0:
        if overlap >= duration_s:
            return "BREATHING_REFERENCE_ABSENT", "REFERENCE_HOLD_COVERS_INTERVAL", False, overlap, (start_s, end_s)
        return "BREATHING_REFERENCE_AMBIGUOUS", "REFERENCE_TRANSITION_OR_HOLD_OVERLAP", True, overlap, (start_s, end_s)

    if _reference_rr_is_valid(_rr_info(window)):
        return "BREATHING_REFERENCE_PRESENT", "REFERENCE_RR_ELIGIBLE_WITHOUT_HOLD_OVERLAP", False, 0.0, (start_s, end_s)
    return "TARGET_UNAVAILABLE", "REFERENCE_RR_NOT_AVAILABLE", False, 0.0, (start_s, end_s)


def _provenance_d0(
    window: Mapping[str, Any],
    recording_meta: Mapping[str, Any],
    split: str,
    time_range_s: tuple[float, float],
) -> dict[str, Any]:
    source_recording_id = str(window.get("recording_id") or "")
    subject_id = str(window.get("subject_id") or "")
    return {
        "source_dataset": "dataset-10_5281_zenodo_18599983",
        "dataset_version": "Zenodo_v1.1",
        "subject_id": subject_id,
        "recording_id": source_recording_id,
        "window_id": str(window.get("window_id") or ""),
        "time_range_s": [round(time_range_s[0], 9), round(time_range_s[1], 9)],
        "window_start_index": int(window.get("source_start_index", 0)),
        "window_end_index_exclusive": int(window.get("source_end_index_exclusive", 0)),
        "extraction_profile": str(window.get("phase_profile") or "MMWAVE_PHASE_EXTRACTION_PROFILE_001"),
        "label_mapping_profile": "MMWAVE_LABEL_MAPPING_PROFILE_001",
        "split": split,
        "source_condition": window.get("source_test_condition"),
        "posture": window.get("posture"),
        "source_recording_path": recording_meta.get("source_recording_path"),
        "source_file": "datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl",
        "reference_source": D0_REFERENCE_SOURCE,
        "clinical_apnea_claimed": False,
    }


def _breathing_target_d0(
    window: Mapping[str, Any],
    radar_available: bool,
    radar_state: str,
    radar_reasons: list[str],
    state: str,
    reason: str,
    transition_flag: bool,
    overlap_s: float,
    time_range_s: tuple[float, float],
) -> dict[str, Any]:
    if state == "TARGET_UNAVAILABLE":
        target_status = "TARGET_UNAVAILABLE"
        availability_reason = ";".join(radar_reasons) if radar_reasons else reason
    elif state == "BREATHING_REFERENCE_AMBIGUOUS":
        target_status = "AMBIGUOUS"
        availability_reason = reason
    else:
        target_status = "AVAILABLE"
        availability_reason = None
    return {
        "target_contract": BREATHING_TARGET_ID,
        "target_status": target_status,
        "breathing_reference_state": state,
        "reference_source": D0_REFERENCE_SOURCE,
        "reference_time_range_s": [round(time_range_s[0], 9), round(time_range_s[1], 9)],
        "reference_quality_or_eligibility": "REFERENCE_RR_ELIGIBLE" if _reference_rr_is_valid(_rr_info(window)) else "REFERENCE_UNAVAILABLE",
        "confidence_or_quality_if_authoritative": "AUTHORITATIVE_SOURCE_AUDIT_ONLY",
        "transition_flag": transition_flag,
        "window_overlap_seconds": round(overlap_s, 9),
        "availability_reason": availability_reason,
        "radar_input_available": radar_available,
        "radar_input_availability_state": radar_state,
        "provenance_reference_method": "D0_A6_LABEL_REFERENCE_AUDIT; NO_RADAR_AMPLITUDE_LABELING",
    }


def _rr_target_d0(
    window: Mapping[str, Any],
    breathing_state: str,
    time_range_s: tuple[float, float],
) -> dict[str, Any]:
    info = _rr_info(window)
    valid = _reference_rr_is_valid(info)
    if breathing_state == "BREATHING_REFERENCE_PRESENT" and valid:
        return {
            "target_contract": RR_TARGET_ID,
            "target_status": "AVAILABLE",
            "rr_bpm": _rounded(info.get("rr_bpm"), 6),
            "reference_source": "MOVESENSE_CHEST_ACC",
            "reference_method": D0_RR_REFERENCE_METHOD,
            "reference_duration_s": round(time_range_s[1] - time_range_s[0], 9),
            "cycle_count": None,
            "validity": "VALID_CONTINUOUS_REFERENCE_RR",
            "unavailable_reason": None,
            "search_band_hz": [float(info["search_band_hz"][0]), float(info["search_band_hz"][1])],
            "peak_frequency_hz": _rounded(info.get("peak_freq_hz"), 9),
            "reference_sample_count": int(info["sample_count"]),
            "reference_time_range_s": [round(time_range_s[0], 9), round(time_range_s[1], 9)],
        }
    if breathing_state == "BREATHING_REFERENCE_AMBIGUOUS":
        unavailable_reason = "REFERENCE_TRANSITION_OR_HOLD_OVERLAP"
    elif breathing_state == "BREATHING_REFERENCE_ABSENT":
        unavailable_reason = "BREATHING_REFERENCE_ABSENT"
    elif not valid:
        unavailable_reason = "REFERENCE_RR_NOT_AVAILABLE"
    else:
        unavailable_reason = "INPUT_UNAVAILABLE_OR_REFERENCE_NOT_ELIGIBLE"
    return {
        "target_contract": RR_TARGET_ID,
        "target_status": "TARGET_UNAVAILABLE",
        "rr_bpm": None,
        "reference_source": "MOVESENSE_CHEST_ACC",
        "reference_method": D0_RR_REFERENCE_METHOD,
        "reference_duration_s": round(time_range_s[1] - time_range_s[0], 9),
        "cycle_count": None,
        "validity": "UNAVAILABLE",
        "unavailable_reason": unavailable_reason,
        "search_band_hz": [0.1, 0.7],
        "peak_frequency_hz": None,
        "reference_sample_count": None,
        "reference_time_range_s": [round(time_range_s[0], 9), round(time_range_s[1], 9)],
    }


def _temporal_state(
    window: Mapping[str, Any],
    breathing_state: str,
    time_range_s: tuple[float, float],
) -> dict[str, Any]:
    start_s, end_s = time_range_s
    event = _event_bounds(window)
    if event is None:
        available = breathing_state == "BREATHING_REFERENCE_PRESENT"
        return {
            "target_contract": TEMPORAL_HOLD_TARGET_ID,
            "target_status": "AVAILABLE" if available else "TARGET_UNAVAILABLE",
            "baseline_state": "BASELINE_ESTABLISHED" if available else "BASELINE_NOT_ESTABLISHED",
            "has_previous_valid_breathing": bool(available),
            "event_state": "NO_HOLD_EVENT_IN_WINDOW" if available else "UNAVAILABLE_REFERENCE",
            "event_id": None,
            "event_onset_s": None,
            "event_offset_s": None,
            "event_onset_recording_s": None,
            "event_offset_recording_s": None,
            "hold_event_active": False,
            "elapsed_hold_s": 0.0,
            "hold_onset_distance_s": None,
            "recovery_detected": False,
            "recovery_state": "NOT_APPLICABLE" if available else "UNAVAILABLE_REFERENCE",
            "reference_transition_state": "NO_TRANSITION" if available else "UNAVAILABLE_REFERENCE",
            "transition_ambiguity": "NONE" if available else "REFERENCE_UNAVAILABLE",
            "source_semantics": "NO_VOLUNTARY_NON_BREATHING_EVENT_IN_REFERENCE_INTERVAL",
            "persistence_threshold": "DEFERRED_TO_M_PV1",
        }

    event_start_s, event_end_s, event_id = event
    overlap_s = max(0.0, min(end_s, event_end_s) - max(start_s, event_start_s))
    if overlap_s <= 0.0:
        raise R3TargetError("D0 event is present but has no positive overlap")
    starts_inside = start_s <= event_start_s < end_s
    ends_inside = start_s < event_end_s <= end_s
    if starts_inside and ends_inside:
        event_state = "HOLD_ONSET_AND_RECOVERY_WITHIN_WINDOW"
    elif starts_inside:
        event_state = "HOLD_ONSET_WITHOUT_RECOVERY_IN_WINDOW"
    elif ends_inside:
        event_state = "HOLD_ACTIVE_AT_WINDOW_START_AND_RECOVERY"
    else:
        event_state = "SUSTAINED_HOLD_COVERS_WINDOW"
    baseline_established = event_start_s > 0.0
    recovery_detected = event_end_s <= end_s
    return {
        "target_contract": TEMPORAL_HOLD_TARGET_ID,
        "target_status": "AVAILABLE",
        "baseline_state": "BASELINE_ESTABLISHED" if baseline_established else "BASELINE_NOT_ESTABLISHED",
        "has_previous_valid_breathing": baseline_established,
        "event_state": event_state,
        "event_id": event_id,
        "event_onset_s": round(event_start_s - start_s, 9),
        "event_offset_s": round(event_end_s - start_s, 9),
        "event_onset_recording_s": round(event_start_s, 9),
        "event_offset_recording_s": round(event_end_s, 9),
        "hold_event_active": True,
        "elapsed_hold_s": round(overlap_s, 9),
        "hold_onset_distance_s": round(event_start_s - start_s, 9),
        "recovery_detected": recovery_detected,
        "recovery_state": "RECOVERY_DETECTED" if recovery_detected else "NOT_OBSERVED_WITHIN_WINDOW",
        "reference_transition_state": event_state,
        "transition_ambiguity": "PARTIAL_WINDOW_OR_BOUNDARY",
        "source_semantics": "VOLUNTARY_BREATH_HOLD_PROXY_NOT_CLINICAL_APNEA",
        "persistence_threshold": "DEFERRED_TO_M_PV1",
    }


def _eligibility(
    split: str,
    radar_available: bool,
    breathing_target: Mapping[str, Any],
    rr_target: Mapping[str, Any],
    temporal_target: Mapping[str, Any],
) -> dict[str, Any]:
    breathing_status = breathing_target.get("target_status")
    rr_status = rr_target.get("target_status")
    temporal_status = temporal_target.get("target_status")
    transition_ambiguous = breathing_status == "AMBIGUOUS" or temporal_target.get("transition_ambiguity") not in {None, "NONE"}
    return {
        "contract": SUPERVISION_ELIGIBILITY_ID,
        "reference_target_available": breathing_status != "TARGET_UNAVAILABLE" or temporal_status != "TARGET_UNAVAILABLE",
        "radar_input_available": radar_available,
        "subject_split_allowed": split == "TRAIN",
        "transition_ambiguous": bool(transition_ambiguous),
        "breathing_evidence_supervision_eligible": radar_available and breathing_status == "AVAILABLE",
        "rr_supervision_eligible": radar_available and rr_status == "AVAILABLE",
        "temporal_hold_supervision_eligible": (
            radar_available
            and temporal_status == "AVAILABLE"
            and temporal_target.get("baseline_state") != "BASELINE_NOT_ESTABLISHED"
        ),
        "pure_class_training_eligible": radar_available and breathing_status == "AVAILABLE" and not transition_ambiguous,
        "model_supervision_eligible": (
            radar_available
            and temporal_target.get("baseline_state") != "BASELINE_NOT_ESTABLISHED"
            and (
                breathing_status != "TARGET_UNAVAILABLE"
                or (
                    temporal_status == "AVAILABLE"
                    and temporal_target.get("baseline_state") != "BASELINE_NOT_ESTABLISHED"
                )
            )
        ),
        "retained_for_transition_analysis": bool(transition_ambiguous),
        "ineligible_reason": None if radar_available else "INVALID_RADAR_INPUT_PRECEDES_PHYSIOLOGY",
    }


def build_d0_target_row(
    window: Mapping[str, Any],
    recording_meta: Mapping[str, Any],
    split: str,
) -> dict[str, Any]:
    """Build one D0 TRAIN target row from the authoritative A6 window."""

    if split != "TRAIN":
        raise R3TargetError(f"R3 D0 target construction requires TRAIN, got {split}")
    radar_available, radar_state, radar_reasons = _radar_input_status(window)
    state, reason, transition_flag, overlap_s, time_range_s = _breathing_state(window, radar_available)
    breathing_target = _breathing_target_d0(
        window,
        radar_available,
        radar_state,
        radar_reasons,
        state,
        reason,
        transition_flag,
        overlap_s,
        time_range_s,
    )
    rr_target = _rr_target_d0(window, state, time_range_s)
    temporal_target = _temporal_state(window, state, time_range_s)
    return {
        "schema_version": R3_ROW_SCHEMA_VERSION,
        "source_id": "D0",
        "dataset_id": "dataset-10_5281_zenodo_18599983",
        "subject_id": str(window.get("subject_id") or ""),
        "recording_id": str(window.get("recording_id") or ""),
        "window_id": str(window.get("window_id") or ""),
        "window_index": int(window.get("window_index", 0)),
        "split": split,
        "condition": window.get("source_test_condition"),
        "posture": window.get("posture"),
        "reference_time_range_s": [round(time_range_s[0], 9), round(time_range_s[1], 9)],
        "breathing_evidence": breathing_target,
        "rr_target": rr_target,
        "temporal_hold": temporal_target,
        "supervision_eligibility": _eligibility(split, radar_available, breathing_target, rr_target, temporal_target),
        "source_label_provenance": {
            "a4_label": window.get("safenest_label"),
            "a4_mapping_rule_id": window.get("mapping_rule_id"),
            "a4_mapping_type": window.get("mapping_type"),
            "original_annotation_type": window.get("original_annotation_type"),
            "annotation_overlap_seconds": round(overlap_s, 9),
            "source_term_is_not_direct_r3_target": True,
            "voluntary_breath_hold_proxy_not_clinical_apnea": True,
        },
        "provenance": _provenance_d0(window, recording_meta, split, time_range_s),
    }


def _d1_radar_available(recording: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if recording.get("adaptation_status") != "SUCCESS":
        reasons.append("ADAPTER_NOT_SUCCESS")
    if recording.get("required_channel_lengths_equal") is not True:
        reasons.append("REQUIRED_CHANNEL_LENGTH_MISMATCH")
    required_presence = recording.get("required_channel_presence")
    if isinstance(required_presence, Mapping) and not all(required_presence.get(name) is True for name in ("radar_I", "radar_Q")):
        reasons.append("RADAR_CHANNEL_MISSING")
    output = recording.get("adapter_output")
    if not isinstance(output, Mapping):
        reasons.append("ADAPTER_OUTPUT_MISSING")
    else:
        quality = output.get("quality_flags")
        if isinstance(quality, Mapping):
            if quality.get("required_channels_finite") is not True:
                reasons.append("RADAR_NONFINITE")
            if quality.get("timestamps_valid") is not True:
                reasons.append("TIMESTAMP_INVALID")
    return not reasons, sorted(set(reasons))


def build_d1_target_row(recording: Mapping[str, Any]) -> dict[str, Any]:
    """Build a conservative D1 row without guessing source ``apnea`` timing."""

    radar_available, radar_reasons = _d1_radar_available(recording)
    output = recording.get("adapter_output") if isinstance(recording.get("adapter_output"), Mapping) else {}
    reference = output.get("respiration_reference") if isinstance(output.get("respiration_reference"), Mapping) else {}
    condition = recording.get("condition_metadata") if isinstance(recording.get("condition_metadata"), Mapping) else {}
    scenario = str(condition.get("source_scenario_normalized") or "")
    hold_protocol = bool(condition.get("breath_hold_protocol_present"))
    reference_declared = "respiration" in _json_list((recording.get("observed_signal_fields") or {}).get("required"))
    reference_finite = bool(reference) and isinstance(reference.get("native_stats"), Mapping)
    reference_available_in_compact_input = reference_declared and reference_finite
    time_start = _finite_float(output.get("time_s_start"))
    time_end = _finite_float(output.get("time_s_end"))
    if time_start is None:
        time_start = 0.0
    if time_end is None or time_end <= time_start:
        time_end = None
    target_unavailable_reason = "SYNCHRONIZED_REFERENCE_WAVEFORM_NOT_MATERIALIZED_IN_COMPACT_EVIDENCE"
    if not reference_available_in_compact_input:
        target_unavailable_reason = "SYNCHRONIZED_REFERENCE_CHANNEL_UNAVAILABLE"
    if not radar_available:
        target_unavailable_reason = "INVALID_RADAR_INPUT"

    breathing_target = {
        "target_contract": BREATHING_TARGET_ID,
        "target_status": "TARGET_UNAVAILABLE",
        "breathing_reference_state": "TARGET_UNAVAILABLE",
        "reference_source": D1_REFERENCE_SOURCE,
        "reference_time_range_s": [round(time_start, 9), round(time_end, 9)] if time_end is not None else None,
        "reference_quality_or_eligibility": recording.get("source_quality_ratings", {}).get("breathing_reference"),
        "confidence_or_quality_if_authoritative": "REFERENCE_CHANNEL_DECLARED; PERIODICITY_NOT_REGENERATED",
        "transition_flag": False,
        "availability_reason": target_unavailable_reason,
        "radar_input_available": radar_available,
        "radar_input_availability_state": "PHYSIOLOGY_ELIGIBLE" if radar_available else "INPUT_UNAVAILABLE",
        "provenance_reference_method": "D1_ADAPTER_RESPIRATION_CHANNEL_STATS_ONLY; NO_REFERENCE_WAVEFORM_COPY",
    }
    rr_target = {
        "target_contract": RR_TARGET_ID,
        "target_status": "TARGET_UNAVAILABLE",
        "rr_bpm": None,
        "reference_source": D1_REFERENCE_SOURCE,
        "reference_method": "DEFERRED_UNTIL_D1_REFERENCE_WAVEFORM_ACCESS",
        "reference_duration_s": round(time_end - time_start, 9) if time_end is not None else None,
        "cycle_count": None,
        "validity": "UNAVAILABLE",
        "unavailable_reason": target_unavailable_reason,
        "search_band_hz": [0.1, 0.7],
        "peak_frequency_hz": None,
        "reference_sample_count": int(output.get("sample_count")) if _finite_float(output.get("sample_count")) is not None else None,
        "reference_time_range_s": [round(time_start, 9), round(time_end, 9)] if time_end is not None else None,
    }
    temporal_reason = "D1_SOURCE_APNEA_PROTOCOL_HAS_NO_DEFENSIBLE_ONSET_OFFSET_IN_COMPACT_EVIDENCE" if hold_protocol or scenario.startswith("apnea") else "D1_NO_DEFENSIBLE_TEMPORAL_EVENT_INTERVAL_IN_COMPACT_EVIDENCE"
    temporal_target = {
        "target_contract": TEMPORAL_HOLD_TARGET_ID,
        "target_status": "TARGET_UNAVAILABLE",
        "baseline_state": "UNAVAILABLE_REFERENCE",
        "has_previous_valid_breathing": None,
        "event_state": "SOURCE_HOLD_PROTOCOL_WITHOUT_DEFENSIBLE_INTERVAL" if hold_protocol or scenario.startswith("apnea") else "NO_DEFENSIBLE_EVENT_INTERVAL",
        "event_id": None,
        "event_onset_s": None,
        "event_offset_s": None,
        "event_onset_recording_s": None,
        "event_offset_recording_s": None,
        "hold_event_active": None,
        "elapsed_hold_s": None,
        "hold_onset_distance_s": None,
        "recovery_detected": None,
        "recovery_state": "UNAVAILABLE_REFERENCE",
        "reference_transition_state": "UNAVAILABLE_REFERENCE",
        "transition_ambiguity": "UNAVAILABLE_REFERENCE_BOUNDARY",
        "source_semantics": "D1_SOURCE_CONDITION_PROVENANCE_ONLY; NOT_SAFENEST_APNEA_PROXY",
        "source_condition_preserved": scenario,
        "persistence_threshold": "DEFERRED_TO_M_PV1",
        "unavailable_reason": temporal_reason,
    }
    eligibility = {
        "contract": SUPERVISION_ELIGIBILITY_ID,
        "reference_target_available": False,
        "radar_input_available": radar_available,
        "subject_split_allowed": False,
        "transition_ambiguous": True if hold_protocol or scenario.startswith("apnea") else False,
        "breathing_evidence_supervision_eligible": False,
        "rr_supervision_eligible": False,
        "temporal_hold_supervision_eligible": False,
        "pure_class_training_eligible": False,
        "model_supervision_eligible": False,
        "retained_for_transition_analysis": bool(hold_protocol or scenario.startswith("apnea")),
        "ineligible_reason": "D1_TARGET_NOT_REGENERATED_FROM_REFERENCE_WAVEFORM" if radar_available else "INVALID_RADAR_INPUT_PRECEDES_PHYSIOLOGY",
    }
    return {
        "schema_version": R3_ROW_SCHEMA_VERSION,
        "source_id": "D1",
        "dataset_id": "10.6084/m9.figshare.9691544.v1",
        "subject_id": str(recording.get("subject_id") or ""),
        "recording_id": str(recording.get("recording_id") or ""),
        "window_id": None,
        "window_index": None,
        "split": "D1_AUXILIARY_DEVELOPMENT_POOL",
        "condition": scenario,
        "posture": condition.get("measurement_position_group"),
        "reference_time_range_s": [round(time_start, 9), round(time_end, 9)] if time_end is not None else None,
        "breathing_evidence": breathing_target,
        "rr_target": rr_target,
        "temporal_hold": temporal_target,
        "supervision_eligibility": eligibility,
        "source_label_provenance": {
            "source_condition": scenario,
            "source_protocol_labels": condition.get("source_protocol_labels", []),
            "source_breath_hold_protocol_present": hold_protocol,
            "source_apnea_string_auto_mapped_to_safenest_apnea": False,
            "source_term_is_not_direct_r3_target": True,
        },
        "provenance": {
            "source_dataset": "10.6084/m9.figshare.9691544.v1",
            "subject_id": str(recording.get("subject_id") or ""),
            "recording_id": str(recording.get("recording_id") or ""),
            "time_range_s": [round(time_start, 9), round(time_end, 9)] if time_end is not None else None,
            "extraction_profile": "D1_NATIVE_SIXPORT_PHASE_DISPLACEMENT_V1",
            "reference_channel": "respiration",
            "reference_waveform_materialized_in_compact_input": False,
            "source_file": "datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/recording_inventory.json",
            "source_archive_member": recording.get("archive_member"),
            "source_condition": scenario,
            "source_quality_ratings": recording.get("source_quality_ratings"),
            "clinical_apnea_claimed": False,
        },
    }
