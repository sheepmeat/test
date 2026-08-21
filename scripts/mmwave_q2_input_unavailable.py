#!/usr/bin/env python3
"""Q2 input-availability contract: gap/freeze/stale/flat fail-closed semantics.

Inherits Q1 timing evidence. Does not train, does not use MR60 labels, does not
tune thresholds from model scores, and does not implement Q3 APNEA false-positive
evaluation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    PROFILE_ID as Q1_PROFILE_ID,
    apply_timing_corruption,
    load_profile as load_q1_profile,
)

PHASE_ID = "Q2"
SCHEMA_VERSION = "Q2.1"
AUDIT_DATE = "2026-08-22"
Q1_COMMIT = "b643bbfa48c07897406fa168f959b2037ad9adae"
CONTRACT_ID = "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1"
PROFILE_ID = "MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1"

Q1_MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption"
Q1_PROFILE_PATH = Q1_MANIFEST / "synthetic_corruption_profile.json"
MN4_CONTRACT = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"
MPV0_POLICY = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/role_lock_policy.json"
CONFIG_PATH = ROOT / "config/mmwave/q2_input_availability_contract.json"
MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_Q2_input_unavailable_contract"

LARGE_GAP_FLOOR_MS = 400.0
LARGE_GAP_MEDIAN_MULTIPLIER = 4.0
LARGE_GAP_MIN_INTERVALS = 8
SOURCE_ADVANCE_TOLERANCE_MS = 8.0
NOMINAL_RECEIVE_MS = 100.0
SYNTHETIC_GAP_MS = 500.0
SYNTHETIC_FREEZE_HOLD_MS = 1000.0
SYNTHETIC_STALE_AGE_MS = 500.0

AVAILABILITY_STATES = (
    "PRESENCE_SUPPRESSED",
    "INPUT_UNAVAILABLE",
    "PHYSIOLOGY_ELIGIBLE",
)
WINDOW_STATES = (
    "PRESENCE_SUPPRESSED_WINDOW",
    "INVALID_WINDOW_INPUT_UNAVAILABLE",
    "VALID_WINDOW",
)
REASON_PRECEDENCE = (
    "PRESENCE_NOT_CONFIRMED",
    "TIMESTAMP_NON_MONOTONIC",
    "TIMESTAMP_UNRESOLVED",
    "INSUFFICIENT_INTERVAL_HISTORY",
    "LARGE_GAP",
    "SOURCE_FREEZE",
    "SOURCE_STALE",
    "SIGNAL_FLAT_EXACT",
    "RECOVERY_WARMUP",
)
Q2_MODES = (
    "CLEAN_VALID",
    "LARGE_GAP",
    "SOURCE_FREEZE",
    "STALE_SOURCE",
    "FLAT_EXACT",
    "JITTER_PLUS_LARGE_GAP",
    "REPUBLICATION_TO_FREEZE",
)
PHYSIOLOGY_CLASSES = ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA")
ABSOLUTE_PATH_RE = re.compile(
    r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)"
)

MANIFEST_JSON_FILES = (
    "input_availability_contract.json",
    "synthetic_quality_profile.json",
    "q1_handoff_audit.json",
    "failure_reason_taxonomy.json",
    "corruption_validation_summary.json",
    "exception_registry.json",
)


class Q2ContractError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dump_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def build_contract() -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "q1_dependency": {
            "profile_id": Q1_PROFILE_ID,
            "commit": Q1_COMMIT,
            "manifest": "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption/",
            "rewrite_q1_history": False,
        },
        "availability_states": list(AVAILABILITY_STATES),
        "window_states": list(WINDOW_STATES),
        "quality_targets": {
            "valid": "QUALITY_VALID",
            "invalid": "INPUT_UNAVAILABLE",
            "presence_suppressed": "PRESENCE_SUPPRESSED",
        },
        "physiological_classes_not_used_as_quality_targets": list(PHYSIOLOGY_CLASSES),
        "precedence": {
            "order": [
                "presence gate",
                "input quality / availability gate",
                "breathing evidence / RR / temporal-hold reasoning",
            ],
            "presence_false": "PRESENCE_SUPPRESSED",
            "presence_null_or_unknown": "PRESENCE_SUPPRESSED",
            "presence_true_and_quality_invalid": "INPUT_UNAVAILABLE",
            "presence_true_and_quality_valid": "PHYSIOLOGY_ELIGIBLE",
            "presence_field": "human_detected_raw",
            "presence_inferred_from_amplitude": False,
            "invalid_quality_precedes_physiology": True,
            "reason_precedence": list(REASON_PRECEDENCE),
            "multiple_faults_preserve_all_reasons": True,
            "majority_vote_of_valid_seconds": False,
        },
        "large_gap": {
            "definition": "any accepted source-update interval in the candidate window exceeds max(400 ms, 4 * window median source-update interval)",
            "timestamp_domain": "source-update estimate when available, otherwise native strictly-increasing sample time",
            "floor_ms": LARGE_GAP_FLOOR_MS,
            "median_multiplier": LARGE_GAP_MEDIAN_MULTIPLIER,
            "minimum_intervals": LARGE_GAP_MIN_INTERVALS,
            "initialization_if_fewer_intervals": "INPUT_UNAVAILABLE reason INSUFFICIENT_INTERVAL_HISTORY",
            "window_containing_large_gap": "INVALID_WINDOW_INPUT_UNAVAILABLE",
            "interpolation_allowed": False,
            "recovery_requires_new_continuous_segment": True,
            "provenance": {
                "value": LARGE_GAP_FLOOR_MS,
                "unit": "ms",
                "time_domain": "source-update interval",
                "category": "INHERITED_FROZEN_RUNTIME_CONTRACT",
                "evidence_path": "config/mmwave/m_n4_canonical_input_dataset_contract.json",
                "reason": "M-N4 already rejects a completed window when any accepted interval exceeds max(0.40 s, 4 * median_update_dt); V2 does not supersede that fail-closed bound. Roadmap 0.5 s is the synthetic example duration, not a looser detector.",
            },
        },
        "source_freeze": {
            "definition": "transport/receive time continues while the underlying source-update estimate does not advance by more than 8 ms for at least 400 ms",
            "not_defined_as": "breath_phase[i] == breath_phase[i-1]",
            "isolated_q1_republication_is_not_freeze": True,
            "q1_core_max_run": 1,
            "hold_ms": LARGE_GAP_FLOOR_MS,
            "advance_tolerance_ms": SOURCE_ADVANCE_TOLERANCE_MS,
            "source_identity_evidence": [
                "source-update estimate ts_monotonic_ms - phase_age_ms",
                "source-event lineage / original_sample_index",
                "seq may continue while the source event remains unrefreshed",
            ],
            "provenance": {
                "value": LARGE_GAP_FLOOR_MS,
                "unit": "ms",
                "time_domain": "elapsed receive/publish time while source event does not advance",
                "category": "INHERITED_FROZEN_RUNTIME_CONTRACT",
                "evidence_path": [
                    "config/mmwave/m_n4_canonical_input_dataset_contract.json",
                    "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption/repeat_event_audit.json",
                ],
                "reason": "A held source sample spanning the same 400 ms integrity floor as a large gap is unusable. Q1 core republication runs never exceeded 1 (~100 ms), so this bound does not convert ordinary Q1 republication into freeze. Handoff runs 95-3598 are validation evidence, not the threshold.",
            },
        },
        "stale_source": {
            "definition": "authoritative freshness (phase_age_ms) shows the published source sample is at least as old as the large-gap floor",
            "freshness_field": "phase_age_ms",
            "threshold_ms": LARGE_GAP_FLOOR_MS,
            "fresh_transport_packet_is_not_fresh_source": True,
            "new_seq_does_not_refresh_stale_source": True,
            "production_mr60_if_freshness_unavailable": "INPUT_UNAVAILABLE",
            "public_native_if_freshness_absent": "NOT_APPLICABLE",
            "not_inferred_from_amplitude": True,
            "m_n3_phase_age_gt_2000_inherited": False,
            "provenance": {
                "value": LARGE_GAP_FLOOR_MS,
                "unit": "ms",
                "time_domain": "phase_age_ms freshness",
                "category": "INHERITED_FROZEN_RUNTIME_CONTRACT",
                "evidence_path": "config/mmwave/m_n4_canonical_input_dataset_contract.json",
                "reason": "M-N4 requires freshness in production and maps missing freshness to WINDOW_UNAVAILABLE. Age at or above the 400 ms integrity floor means the published sample is older than a permitted gap. M-N3 2000 ms was explicitly not inherited.",
            },
        },
        "flat_signal": {
            "exact_flat_rule": "window unique finite values == 1, or any non-finite value, or a contiguous exact-equal span lasting >= 400 ms while source events continue to advance",
            "near_flat_rule": "DEFERRED_TO_R2_R3_M_PV1",
            "low_amplitude_alone_invalid": False,
            "mad_cutoff_frozen": False,
            "numeric_plateau_of_two_samples_is_not_flat": True,
            "provenance": {
                "value": "exact equality / non-finite / unique-count==1",
                "unit": None,
                "time_domain": "candidate window values, with equal-span duration compared to 400 ms source time",
                "category": "DETERMINISTIC_ENGINEERING_INVARIANT",
                "evidence_path": "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/v1_failure_baseline.json",
                "reason": "V1 local-MAD amplification of tiny windows must not be replaced by an arbitrary MAD<eps unavailability cutoff. Only machine-degenerate exact flatness is frozen; subtle near-flat quality is deferred.",
            },
        },
        "timestamp_invalid": {
            "definition": "non-monotonic source/receive time, non-positive interval, or unresolvable timestamp collision",
            "missing_required_production_freshness": "handled as SOURCE_STALE",
            "provenance": {
                "value": "dt <= 0 or non-finite timestamps",
                "unit": "ms",
                "time_domain": "evaluated timestamp series",
                "category": "DETERMINISTIC_ENGINEERING_INVARIANT",
                "evidence_path": "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption/exception_registry.json",
                "reason": "Q1 handed off a receive-median 0 ms collision session. Ordering that cannot be resolved cannot support physiological inference.",
            },
        },
        "recovery": {
            "after_fault": "RECOVERY_WARMUP until the next advancing source event after the fault span ends",
            "requires_fresh_source_advancement": True,
            "requires_monotonic_timing": True,
            "requires_no_active_large_gap": True,
            "window_with_any_severe_fault": "INVALID_WINDOW_INPUT_UNAVAILABLE",
            "model_ready_history_seconds": "DEFERRED_TO_M_PV1",
            "do_not_freeze_30s_model_window_here": True,
        },
        "q1_vs_q2": {
            "q1_typical_jitter_potentially_valid": True,
            "isolated_q1_source_republication_not_automatic_freeze": True,
            "q2_invalid_modes_target": "INPUT_UNAVAILABLE",
        },
        "architecture_deferred_to_m_pv1": [
            "neural vs rule vs hybrid quality head",
            "final feature schema",
            "final 30 s tensor contract",
            "breathing-evidence / RR / temporal-hold implementation",
        ],
        "d2_used": False,
        "mr60_supervised_use": False,
        "model_output_tuning": False,
        "q3_work": False,
        "interpolation_forbidden": True,
        "synthetic_apnea_forbidden": True,
    }


def build_taxonomy() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "reason_codes": list(REASON_PRECEDENCE),
        "not_reason_codes": list(PHYSIOLOGY_CLASSES),
        "distinctions": {
            "SOURCE_REPUBLICATION": "short Q1 reuse of a previous source sample; core max run 1; not automatically unavailable",
            "SOURCE_FREEZE": "source event fails to advance for >= 400 ms while transport continues",
            "NUMERIC_PLATEAU": "accepted advancing source samples happen to share equal numeric values; not freeze by itself",
            "FLAT_SIGNAL": "machine-degenerate exact constancy over the window or a >= 400 ms advancing exact-equal span",
            "LARGE_GAP": "source-update interval exceeds the inherited M-N4 bound",
            "STALE_SOURCE": "phase_age_ms at or above 400 ms, or production freshness missing",
        },
        "reason_precedence": list(REASON_PRECEDENCE),
    }


def build_quality_profile() -> dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "builds_on": Q1_PROFILE_ID,
        "supported_modes": list(Q2_MODES),
        "invalid_target": "INPUT_UNAVAILABLE",
        "physiology_labels_modified": False,
        "synthetic_apnea_created": False,
        "interpolation": False,
        "mode_notes": {
            "CLEAN_VALID": "identity; Q2 quality remains QUALITY_VALID",
            "LARGE_GAP": "delay later samples to create a 500 ms source hole; no interpolation",
            "SOURCE_FREEZE": "republish one existing source sample for 1000 ms of receive time",
            "STALE_SOURCE": "attach phase_age_ms=500 on a mid-window segment",
            "FLAT_EXACT": "overwrite a mid-window advancing segment with an exact constant; marked synthetic",
            "JITTER_PLUS_LARGE_GAP": "Q1 TYPICAL CADENCE_JITTER then LARGE_GAP",
            "REPUBLICATION_TO_FREEZE": "one isolated republication then extend the hold across the freeze bound",
        },
        "synthetic_gap_ms": {
            "value": SYNTHETIC_GAP_MS,
            "unit": "ms",
            "time_domain": "source interval",
            "category": "ROADMAP_EXPLICIT_POLICY",
            "evidence_path": "docs/20260822_SafeNest_mmWave_Public_Multidomain_V2_Development_Roadmap_01.md",
            "reason": "Roadmap names synthetic gaps on the order of 0.5 s. Detection remains the inherited 400 ms M-N4 floor.",
        },
        "d2_used": False,
        "mr60_labels_used": False,
        "model_outputs_used": False,
        "class_balance_not_frozen": True,
    }


def _primary_reason(reasons: set[str]) -> str | None:
    for code in REASON_PRECEDENCE:
        if code in reasons:
            return code
    return None


def evaluate_availability(
    timestamps_ms: np.ndarray,
    values: np.ndarray,
    *,
    source_update_ms: np.ndarray | None = None,
    phase_age_ms: np.ndarray | None = None,
    presence: bool | None = True,
    timing_context: str = "PUBLIC_NATIVE",
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail-closed availability for a candidate window / event series."""
    contract = contract or build_contract()
    t = np.asarray(timestamps_ms, dtype=np.float64)
    x = np.asarray(values, dtype=np.float64)
    n = int(t.size)
    if x.size != n or n == 0:
        raise Q2ContractError("INPUT_LENGTH_MISMATCH")
    src = t if source_update_ms is None else np.asarray(source_update_ms, dtype=np.float64)
    if src.size != n:
        raise Q2ContractError("SOURCE_UPDATE_LENGTH_MISMATCH")
    age = None if phase_age_ms is None else np.asarray(phase_age_ms, dtype=np.float64)
    if age is not None and age.size != n:
        raise Q2ContractError("PHASE_AGE_LENGTH_MISMATCH")

    reasons: set[str] = set()
    sample_reasons: list[set[str]] = [set() for _ in range(n)]

    if presence is not True:
        reasons.add("PRESENCE_NOT_CONFIRMED")
        for i in range(n):
            sample_reasons[i].add("PRESENCE_NOT_CONFIRMED")

    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(src)):
        reasons.add("TIMESTAMP_UNRESOLVED")
        for i in range(n):
            if not math.isfinite(float(t[i])) or not math.isfinite(float(src[i])):
                sample_reasons[i].add("TIMESTAMP_UNRESOLVED")
    dts = np.diff(t)
    src_dts = np.diff(src)
    if np.any(dts < 0) or np.any(src_dts < 0):
        reasons.add("TIMESTAMP_NON_MONOTONIC")
        for i in range(1, n):
            if dts[i - 1] < 0 or src_dts[i - 1] < 0:
                sample_reasons[i].add("TIMESTAMP_NON_MONOTONIC")
    if np.any(dts == 0):
        reasons.add("TIMESTAMP_UNRESOLVED")
        for i in range(1, n):
            if dts[i - 1] == 0:
                sample_reasons[i].add("TIMESTAMP_UNRESOLVED")

    advancing_src = src_dts > SOURCE_ADVANCE_TOLERANCE_MS
    source_intervals = [float(d) for d in src_dts if d > SOURCE_ADVANCE_TOLERANCE_MS]
    if len(source_intervals) < LARGE_GAP_MIN_INTERVALS:
        reasons.add("INSUFFICIENT_INTERVAL_HISTORY")
        for i in range(n):
            sample_reasons[i].add("INSUFFICIENT_INTERVAL_HISTORY")
        gap_threshold = LARGE_GAP_FLOOR_MS
    else:
        gap_threshold = max(LARGE_GAP_FLOOR_MS, LARGE_GAP_MEDIAN_MULTIPLIER * _median(source_intervals))
        for i, dt in enumerate(src_dts, start=1):
            if dt > SOURCE_ADVANCE_TOLERANCE_MS and dt > gap_threshold:
                reasons.add("LARGE_GAP")
                sample_reasons[i].add("LARGE_GAP")

    last_accepted = float(src[0])
    run_start_recv = float(t[0])
    for i in range(1, n):
        if float(src[i]) <= last_accepted + SOURCE_ADVANCE_TOLERANCE_MS:
            hold = float(t[i]) - run_start_recv
            if hold >= LARGE_GAP_FLOOR_MS:
                reasons.add("SOURCE_FREEZE")
                sample_reasons[i].add("SOURCE_FREEZE")
        else:
            last_accepted = float(src[i])
            run_start_recv = float(t[i])

    if age is not None:
        for i, value in enumerate(age):
            if not math.isfinite(float(value)) or float(value) >= LARGE_GAP_FLOOR_MS:
                reasons.add("SOURCE_STALE")
                sample_reasons[i].add("SOURCE_STALE")
    elif timing_context == "PRODUCTION_MR60":
        reasons.add("SOURCE_STALE")
        for i in range(n):
            sample_reasons[i].add("SOURCE_STALE")

    finite = np.isfinite(x)
    if not np.all(finite):
        reasons.add("SIGNAL_FLAT_EXACT")
        for i in range(n):
            if not finite[i]:
                sample_reasons[i].add("SIGNAL_FLAT_EXACT")
    unique = np.unique(x[finite]) if np.any(finite) else np.array([])
    if unique.size == 1:
        reasons.add("SIGNAL_FLAT_EXACT")
        for i in range(n):
            sample_reasons[i].add("SIGNAL_FLAT_EXACT")
    else:
        span_start = 0
        for i in range(1, n + 1):
            same = i < n and finite[i] and finite[i - 1] and float(x[i]) == float(x[i - 1])
            advanced = i < n and i > 0 and advancing_src[i - 1]
            if same and advanced:
                continue
            if i - span_start >= 2:
                duration = float(src[i - 1] - src[span_start])
                if duration >= LARGE_GAP_FLOOR_MS:
                    reasons.add("SIGNAL_FLAT_EXACT")
                    for j in range(span_start, i):
                        sample_reasons[j].add("SIGNAL_FLAT_EXACT")
            span_start = i

    quality_faults = reasons - {"PRESENCE_NOT_CONFIRMED", "RECOVERY_WARMUP"}
    in_warmup = False
    for i in range(n):
        fault = bool(sample_reasons[i] - {"PRESENCE_NOT_CONFIRMED", "RECOVERY_WARMUP"})
        if fault:
            in_warmup = True
            continue
        if in_warmup:
            if i > 0 and float(src[i]) > float(src[i - 1]) + SOURCE_ADVANCE_TOLERANCE_MS:
                in_warmup = False
            else:
                sample_reasons[i].add("RECOVERY_WARMUP")
                reasons.add("RECOVERY_WARMUP")

    if "PRESENCE_NOT_CONFIRMED" in reasons:
        availability = "PRESENCE_SUPPRESSED"
        window = "PRESENCE_SUPPRESSED_WINDOW"
        quality_target = "PRESENCE_SUPPRESSED"
    elif quality_faults or "RECOVERY_WARMUP" in reasons:
        availability = "INPUT_UNAVAILABLE"
        window = "INVALID_WINDOW_INPUT_UNAVAILABLE"
        quality_target = "INPUT_UNAVAILABLE"
    else:
        availability = "PHYSIOLOGY_ELIGIBLE"
        window = "VALID_WINDOW"
        quality_target = "QUALITY_VALID"

    ordered_reasons = [code for code in REASON_PRECEDENCE if code in reasons]
    return {
        "availability_state": availability,
        "window_state": window,
        "quality_target": quality_target,
        "reasons": ordered_reasons,
        "primary_reason": _primary_reason(reasons),
        "gap_threshold_ms": gap_threshold,
        "sample_reasons": [[code for code in REASON_PRECEDENCE if code in row] for row in sample_reasons],
        "timing_context": timing_context,
        "contract_id": CONTRACT_ID,
        "physiology_class_assigned": None,
        "interpolation_applied": False,
    }


def _base_trace(n: int = 256) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(n, dtype=np.float64) * NOMINAL_RECEIVE_MS
    x = 0.35 * np.sin(np.linspace(0.0, 6.0 * math.pi, n))
    return t, x


def apply_quality_corruption(
    timestamps_ms: np.ndarray,
    values: np.ndarray,
    *,
    mode: str,
    seed: int = 20260822,
    labels: np.ndarray | None = None,
    q1_profile: dict[str, Any] | None = None,
    presence: bool | None = True,
) -> dict[str, Any]:
    if mode not in Q2_MODES:
        raise Q2ContractError(f"UNSUPPORTED_MODE:{mode}")
    t = np.asarray(timestamps_ms, dtype=np.float64).copy()
    x = np.asarray(values, dtype=np.float64).copy()
    n = int(t.size)
    mid = n // 2
    ops = ["UNCHANGED"] * n
    origin = list(range(n))
    src = t.copy()
    age = np.full(n, 20.0, dtype=np.float64)
    dropped: list[int] = []

    if mode == "JITTER_PLUS_LARGE_GAP":
        if q1_profile is None:
            raise Q2ContractError("Q1_PROFILE_REQUIRED")
        jittered = apply_timing_corruption(
            t, x, q1_profile, mode="CADENCE_JITTER", severity="TYPICAL", seed=seed, labels=labels
        )
        t = jittered["timestamps_ms"]
        x = jittered["values"]
        origin = [row["original_sample_index"] for row in jittered["provenance"]]
        ops = [row["operation"] for row in jittered["provenance"]]
        src = t.copy()
        mode_after = "LARGE_GAP"
        labels = jittered["labels"]
    else:
        mode_after = mode

    if mode_after == "CLEAN_VALID":
        pass
    elif mode_after == "LARGE_GAP":
        extra = SYNTHETIC_GAP_MS - float(t[mid] - t[mid - 1])
        t[mid:] = t[mid:] + extra
        src = t.copy()
        ops[mid] = "LARGE_GAP_INSERTED"
    elif mode_after in {"SOURCE_FREEZE", "REPUBLICATION_TO_FREEZE"}:
        hold_ms = SYNTHETIC_FREEZE_HOLD_MS
        steps = int(round(hold_ms / NOMINAL_RECEIVE_MS))
        t_out = list(t[:mid])
        x_out = list(x[:mid])
        src_out = list(src[:mid])
        origin_out = list(origin[:mid])
        ops_out = list(ops[:mid])
        age_out = list(age[:mid])
        if mode_after == "REPUBLICATION_TO_FREEZE":
            t_out.append(t_out[-1] + NOMINAL_RECEIVE_MS)
            x_out.append(x_out[-1])
            src_out.append(src_out[-1])
            origin_out.append(origin_out[-1])
            ops_out.append("SOURCE_REPUBLISHED")
            age_out.append(age_out[-1] + NOMINAL_RECEIVE_MS)
            steps = max(steps - 1, 1)
        freeze_origin = origin_out[-1]
        freeze_value = x_out[-1]
        freeze_src = src_out[-1]
        for _ in range(steps):
            t_out.append(t_out[-1] + NOMINAL_RECEIVE_MS)
            x_out.append(freeze_value)
            src_out.append(freeze_src)
            origin_out.append(freeze_origin)
            ops_out.append("SOURCE_FROZEN")
            age_out.append(age_out[-1] + NOMINAL_RECEIVE_MS)
        recv_resume = t_out[-1] + NOMINAL_RECEIVE_MS
        src_resume = freeze_src + NOMINAL_RECEIVE_MS
        src_base = float(src[mid])
        t_base = float(t[mid])
        for i in range(mid, n):
            t_out.append(recv_resume + (float(t[i]) - t_base))
            x_out.append(float(x[i]))
            src_out.append(src_resume + (float(src[i]) - src_base))
            origin_out.append(origin[i])
            ops_out.append(ops[i])
            age_out.append(20.0)
        t = np.asarray(t_out)
        x = np.asarray(x_out)
        src = np.asarray(src_out)
        origin = origin_out
        ops = ops_out
        age = np.asarray(age_out)
    elif mode_after == "STALE_SOURCE":
        age[mid : mid + 8] = SYNTHETIC_STALE_AGE_MS
        for i in range(mid, min(mid + 8, n)):
            ops[i] = "SOURCE_STALED"
    elif mode_after == "FLAT_EXACT":
        width = 8
        constant = 0.0
        x[mid : mid + width] = constant
        for i in range(mid, min(mid + width, n)):
            ops[i] = "FLAT_EXACT_SYNTHETIC"
            origin[i] = mid
    else:
        raise Q2ContractError(f"UNHANDLED_MODE:{mode_after}")

    eval_ctx = "PUBLIC_NATIVE"
    eval_age = age if mode in {"STALE_SOURCE"} or mode_after == "STALE_SOURCE" else None
    evaluation = evaluate_availability(
        t,
        x,
        source_update_ms=src,
        phase_age_ms=eval_age,
        presence=presence,
        timing_context=eval_ctx,
    )
    if mode != "CLEAN_VALID" and evaluation["quality_target"] != "INPUT_UNAVAILABLE" and presence is True:
        raise Q2ContractError(f"INVALID_MODE_DID_NOT_FAIL_CLOSED:{mode}")
    if evaluation["physiology_class_assigned"] in PHYSIOLOGY_CLASSES:
        raise Q2ContractError("SYNTHETIC_PHYSIOLOGY_CLASS")

    out_labels = None
    if labels is not None:
        label_arr = np.asarray(labels)
        out_labels = np.asarray([label_arr[min(i, label_arr.size - 1)] for i in origin])

    provenance = []
    for i, orig in enumerate(origin):
        provenance.append(
            {
                "output_index": i,
                "original_sample_index": int(orig),
                "original_timestamp_ms": float(timestamps_ms[min(int(orig), len(timestamps_ms) - 1)]),
                "corrupted_timestamp_ms": float(t[i]),
                "operation": ops[i],
                "source_sample_lineage": int(orig),
                "corruption_mode": mode,
                "seed": int(seed),
                "availability_target": evaluation["quality_target"],
                "reason_code": evaluation["sample_reasons"][i][0] if evaluation["sample_reasons"][i] else None,
                "corruption_profile": PROFILE_ID,
            }
        )
    return {
        "timestamps_ms": t,
        "values": x,
        "source_update_ms": src,
        "phase_age_ms": eval_age,
        "labels": out_labels,
        "provenance": provenance,
        "dropped_source_indices": dropped,
        "mode": mode,
        "seed": int(seed),
        "evaluation": evaluation,
        "profile_id": PROFILE_ID,
        "input_count": n,
        "output_count": int(t.size),
    }


def _handoff_cases() -> dict[str, Any]:
    results = {}

    def pack(name: str, evaluation: dict[str, Any]) -> dict[str, Any]:
        return {
            "availability_state": evaluation["availability_state"],
            "window_state": evaluation["window_state"],
            "quality_target": evaluation["quality_target"],
            "reasons": evaluation["reasons"],
            "primary_reason": evaluation["primary_reason"],
            "physiology_interpreted": False,
        }

    freeze_steps = {3598: 40, 2884: 30, 1582: 20, 683: 16, 598: 14, 425: 12, 95: 10}
    # Compact traces: hold exceeds 400 ms. Run lengths label Q1 handoff identity, not the threshold.
    for run, steps in freeze_steps.items():
        recv: list[float] = []
        src: list[float] = []
        vals: list[float] = []
        for k in range(16):
            recv.append(100.0 * k)
            src.append(100.0 * k)
            vals.append(float(np.sin(0.4 * k)))
        freeze_src = src[-1]
        freeze_val = vals[-1]
        for _ in range(steps):
            recv.append(recv[-1] + 100.0)
            src.append(freeze_src)
            vals.append(freeze_val)
        for k in range(16):
            recv.append(recv[-1] + 100.0)
            src.append(src[-1] + 100.0)
            vals.append(float(np.sin(0.4 * (k + 3))))
        ev = evaluate_availability(np.asarray(recv), np.asarray(vals), source_update_ms=np.asarray(src))
        results[f"run_{run}"] = pack(f"run_{run}", ev)

    for gap_ms, key in ((158380.0, "gap_158380_ms"), (42637.0, "gap_42637_ms")):
        t_gap, x_gap = _base_trace(24)
        t_gap[12:] = t_gap[12:] + (gap_ms - 100.0)
        ev = evaluate_availability(t_gap, x_gap, source_update_ms=t_gap)
        results[key] = pack(key, ev)

    t_col = np.zeros(32, dtype=np.float64)
    t_col[16:] = np.arange(16, dtype=np.float64) * 100.0
    x_col = np.sin(np.linspace(0.0, 2.0 * math.pi, 32))
    ev = evaluate_availability(t_col, x_col, source_update_ms=t_col)
    results["timestamp_collision"] = pack("timestamp_collision", ev)
    return results


def main() -> int:
    policy = load_json(MPV0_POLICY)
    mn4 = load_json(MN4_CONTRACT)
    q1_profile = load_q1_profile(Q1_PROFILE_PATH)
    q1_val = load_json(Q1_MANIFEST / "validation_result.json")
    if q1_profile["profile_id"] != Q1_PROFILE_ID:
        raise Q2ContractError("Q1_PROFILE_MISMATCH")
    if q1_val["profile_id"] != Q1_PROFILE_ID:
        raise Q2ContractError("Q1_VALIDATION_MISMATCH")
    if mn4["gap"]["window_containing_large_gap"] != "REJECT_ENTIRE_WINDOW":
        raise Q2ContractError("MN4_GAP_DRIFT")
    if mn4["timing"]["update_advancement_tolerance_ms"] != SOURCE_ADVANCE_TOLERANCE_MS:
        raise Q2ContractError("MN4_TOLERANCE_DRIFT")
    if not policy["fail_closed_policy"]["later_stages_must_provide_abstention_or_INPUT_UNAVAILABLE"]:
        raise Q2ContractError("MPV0_FAIL_CLOSED_DRIFT")

    contract = build_contract()
    taxonomy = build_taxonomy()
    quality_profile = build_quality_profile()
    t, x = _base_trace(256)
    labels = np.array(["NORMAL"] * 256)
    q1_jitter = apply_timing_corruption(
        t, x, q1_profile, mode="CADENCE_JITTER", severity="TYPICAL", seed=7, labels=labels
    )
    q1_jitter_eval = evaluate_availability(q1_jitter["timestamps_ms"], q1_jitter["values"])
    iso_t = np.arange(16, dtype=np.float64) * 100.0
    iso_x = np.sin(np.linspace(0.0, math.pi, 16))
    iso_src = iso_t.copy()
    iso_src[8] = iso_src[7]
    iso_x[8] = iso_x[7]
    iso_eval = evaluate_availability(iso_t, iso_x, source_update_ms=iso_src)
    low_amp = 1e-4 * np.sin(np.linspace(0.0, 8.0 * math.pi, 256))
    low_eval = evaluate_availability(t, low_amp)

    summaries = {}
    for mode in Q2_MODES:
        result = apply_quality_corruption(t, x, mode=mode, seed=20260822, labels=labels, q1_profile=q1_profile)
        summaries[mode] = {
            "availability_state": result["evaluation"]["availability_state"],
            "quality_target": result["evaluation"]["quality_target"],
            "primary_reason": result["evaluation"]["primary_reason"],
            "reasons": result["evaluation"]["reasons"],
            "physiology_labels_unique": sorted(set(result["labels"].tolist())) if result["labels"] is not None else [],
            "output_count": result["output_count"],
        }
        if mode != "CLEAN_VALID" and result["evaluation"]["quality_target"] != "INPUT_UNAVAILABLE":
            raise Q2ContractError(f"MODE_NOT_UNAVAILABLE:{mode}")
        if result["labels"] is not None and "APNEA" in result["labels"].tolist():
            raise Q2ContractError("SYNTHETIC_APNEA")

    handoff = _handoff_cases()
    for key, row in handoff.items():
        if row["quality_target"] != "INPUT_UNAVAILABLE":
            raise Q2ContractError(f"HANDOFF_NOT_UNAVAILABLE:{key}")

    if q1_jitter_eval["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise Q2ContractError("Q1_JITTER_MARKED_UNAVAILABLE")
    if iso_eval["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise Q2ContractError("ISOLATED_REPUBLICATION_MARKED_FREEZE")
    if low_eval["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        raise Q2ContractError("LOW_AMPLITUDE_MARKED_UNAVAILABLE")
    if q1_jitter_eval["quality_target"] != "QUALITY_VALID":
        raise Q2ContractError("Q1_JITTER_TARGET")

    exceptions = {
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "near_flat_threshold": "DEFERRED_TO_R2_R3_M_PV1",
        "recovery_model_history_seconds": "DEFERRED_TO_M_PV1",
        "pi_host_timestamp_residual": "UNAVAILABLE_Q1_LIMITATION",
        "exact_transport_duplicate_mode": "NOT_EMPIRICALLY_OBSERVED_IN_Q1",
        "q3_apnea_false_positive_gate": "NOT_IN_Q2",
        "entries": [],
    }
    validation_summary = {
        "phase": PHASE_ID,
        "q1_typical_jitter_state": q1_jitter_eval["availability_state"],
        "isolated_republication_state": iso_eval["availability_state"],
        "low_amplitude_dynamic_state": low_eval["availability_state"],
        "mode_results": summaries,
        "q1_handoff": handoff,
        "no_interpolation": True,
        "no_synthetic_apnea": True,
        "d2_used": False,
        "mr60_supervised_use": False,
        "model_output_tuning": False,
        "d0_subject_heldout_used": False,
        "m_n6_excluded_heldout_used": False,
        "q3_work": False,
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    dump_json(CONFIG_PATH, contract)
    artifacts = {
        "input_availability_contract.json": contract,
        "synthetic_quality_profile.json": quality_profile,
        "q1_handoff_audit.json": {
            "phase": PHASE_ID,
            "q1_commit": Q1_COMMIT,
            "q1_profile_id": Q1_PROFILE_ID,
            "inherited_facts": {
                "nominal_receive_ms": NOMINAL_RECEIVE_MS,
                "source_advance_tolerance_ms": SOURCE_ADVANCE_TOLERANCE_MS,
                "core_source_interval_median_ms": 101.0,
                "core_source_interval_p95_ms": 128.0,
                "core_source_interval_p99_ms": 197.0,
                "exact_transport_duplicates": 0,
                "core_max_republication_run": 1,
                "q1_modes_remain_potentially_valid": [
                    "CLEAN",
                    "CADENCE_JITTER",
                    "SOURCE_REPUBLICATION",
                    "JITTER_PLUS_SOURCE_REPUBLICATION",
                ],
            },
            "handoff_validation": handoff,
            "physiology_interpreted": False,
        },
        "failure_reason_taxonomy.json": taxonomy,
        "corruption_validation_summary.json": validation_summary,
        "exception_registry.json": exceptions,
    }
    checksums = {
        "algorithm": "SHA-256",
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "files": {},
        "config_file": {
            "path": "config/mmwave/q2_input_availability_contract.json",
            "sha256": sha256_bytes(CONFIG_PATH.read_text(encoding="utf-8").encode("utf-8")),
        },
    }
    for name, payload in artifacts.items():
        checksums["files"][name] = dump_json(MANIFEST_DIR / name, payload)
    dump_json(MANIFEST_DIR / "checksums.json", checksums)
    text = (MANIFEST_DIR / "input_availability_contract.json").read_text(encoding="utf-8")
    if text != CONFIG_PATH.read_text(encoding="utf-8"):
        raise Q2ContractError("CONFIG_MANIFEST_CONTRACT_DIVERGED")
    for name in (*MANIFEST_JSON_FILES, "checksums.json"):
        blob = (MANIFEST_DIR / name).read_text(encoding="utf-8")
        if ABSOLUTE_PATH_RE.search(blob):
            raise Q2ContractError(f"ABSOLUTE_PATH:{name}")
    print(json.dumps({"ok": True, "contract_id": CONTRACT_ID, "profile_id": PROFILE_ID}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
