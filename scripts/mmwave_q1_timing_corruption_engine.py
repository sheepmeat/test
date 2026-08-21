#!/usr/bin/env python3
"""Deterministic MR60-like timing/path corruption for a generic time series.

Delays or repeats existing samples according to a frozen Q1 profile.
Does not interpolate, amplitude-normalize, invent class labels, or embed
MR60 physiological traces.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

PROFILE_ID = "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1"
SUPPORTED_MODES = (
    "CLEAN",
    "CADENCE_JITTER",
    "SOURCE_REPUBLICATION",
    "JITTER_PLUS_SOURCE_REPUBLICATION",
)
SEVERITY_LEVELS = ("NOMINAL", "TYPICAL", "STRESSED")
OPS = {
    "UNCHANGED": "UNCHANGED",
    "TIMING_JITTERED": "TIMING_JITTERED",
    "SOURCE_REPUBLISHED": "SOURCE_REPUBLISHED",
}
TRANSPORT_DUPLICATE_MODE = "TRANSPORT_DUPLICATE"
TRANSPORT_DUPLICATE_STATUS = "NOT_EMPIRICALLY_OBSERVED"


class Q1CorruptionError(ValueError):
    pass


def load_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("profile_id") != PROFILE_ID:
        raise Q1CorruptionError("PROFILE_ID_MISMATCH")
    return profile


def unit_interval(seed: int, *parts: object) -> float:
    material = "|".join([str(seed), *[str(part) for part in parts]]).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def inverse_cdf(u: float, table: list[list[float]]) -> float:
    if not table:
        raise Q1CorruptionError("EMPTY_QUANTILE_TABLE")
    u = min(1.0, max(0.0, float(u)))
    pts = [(float(p) / 100.0, float(v)) for p, v in table]
    if u <= pts[0][0]:
        return pts[0][1]
    for idx in range(1, len(pts)):
        p0, v0 = pts[idx - 1]
        p1, v1 = pts[idx]
        if u <= p1:
            if p1 == p0:
                return v1
            w = (u - p0) / (p1 - p0)
            return v0 + w * (v1 - v0)
    return pts[-1][1]


def jitter_sample(profile: dict[str, Any], severity: str, seed: int, index: int) -> float:
    spec = profile["severity_levels"][severity]["cadence_jitter"]
    if not spec.get("enabled"):
        return 0.0
    lo = float(spec["unit_interval_min"])
    hi = float(spec["unit_interval_max"])
    u = lo + (hi - lo) * unit_interval(seed, "jitter", severity, index)
    return inverse_cdf(u, profile["jitter_definition"]["source_jitter_vs_nominal_ms_quantiles"])


def republication_probability(profile: dict[str, Any], severity: str) -> float:
    return float(profile["severity_levels"][severity]["source_republication"]["probability"])


def _require_mode_severity(mode: str, severity: str) -> None:
    if mode == TRANSPORT_DUPLICATE_MODE:
        raise Q1CorruptionError(TRANSPORT_DUPLICATE_STATUS)
    if mode not in SUPPORTED_MODES:
        raise Q1CorruptionError(f"UNSUPPORTED_MODE:{mode}")
    if severity not in SEVERITY_LEVELS:
        raise Q1CorruptionError(f"UNSUPPORTED_SEVERITY:{severity}")


def apply_timing_corruption(
    timestamps_ms: np.ndarray,
    values: np.ndarray,
    profile: dict[str, Any],
    *,
    mode: str,
    severity: str = "TYPICAL",
    seed: int = 20260822,
    labels: np.ndarray | None = None,
    event_ids: np.ndarray | None = None,
) -> dict[str, Any]:
    """Corrupt timing/path of a generic series. Labels are passed through by lineage."""
    _require_mode_severity(mode, severity)
    t = np.asarray(timestamps_ms, dtype=np.float64)
    x = np.asarray(values, dtype=np.float64)
    if t.ndim != 1 or x.ndim != 1 or t.size != x.size or t.size == 0:
        raise Q1CorruptionError("INPUT_LENGTH_MISMATCH")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(x)):
        raise Q1CorruptionError("NON_FINITE_INPUT")
    if np.any(np.diff(t) <= 0):
        raise Q1CorruptionError("INPUT_TIMESTAMPS_NOT_STRICTLY_INCREASING")
    n = int(t.size)
    label_in = None if labels is None else np.asarray(labels)
    if label_in is not None and label_in.shape[0] != n:
        raise Q1CorruptionError("LABEL_LENGTH_MISMATCH")
    ids_in = None if event_ids is None else np.asarray(event_ids)
    if ids_in is not None and ids_in.shape[0] != n:
        raise Q1CorruptionError("EVENT_ID_LENGTH_MISMATCH")

    apply_jitter = mode in {"CADENCE_JITTER", "JITTER_PLUS_SOURCE_REPUBLICATION"}
    apply_repub = mode in {"SOURCE_REPUBLICATION", "JITTER_PLUS_SOURCE_REPUBLICATION"}
    nominal = float(profile["nominal_cadence_definition"]["receive_publish_interval_ms"])
    dt_min = float(profile["jitter_definition"]["synthetic_min_interval_ms"])
    p_repub = republication_probability(profile, severity) if apply_repub else 0.0

    if mode == "CLEAN":
        apply_jitter = False
        apply_repub = False
        p_repub = 0.0

    src_t = [float(t[0])]
    ops_src = [OPS["UNCHANGED"]]
    for i in range(1, n):
        dt = float(t[i] - t[i - 1])
        op = OPS["UNCHANGED"]
        if apply_jitter:
            dt = max(dt_min, dt + jitter_sample(profile, severity, seed, i))
            op = OPS["TIMING_JITTERED"]
        src_t.append(src_t[-1] + dt)
        ops_src.append(op)

    out_t: list[float] = []
    out_x: list[float] = []
    out_origin: list[int] = []
    out_op: list[str] = []
    dropped: list[int] = []
    last_kept = 0
    for i in range(n):
        republish = (
            apply_repub
            and i > 0
            and unit_interval(seed, "repub", severity, i) < p_repub
        )
        if republish:
            origin = last_kept
            out_t.append(src_t[i])
            out_x.append(float(x[origin]))
            out_origin.append(origin)
            out_op.append(OPS["SOURCE_REPUBLISHED"])
            dropped.append(i)
            continue
        last_kept = i
        out_t.append(src_t[i])
        out_x.append(float(x[i]))
        out_origin.append(i)
        out_op.append(ops_src[i])

    provenance = []
    for out_i, origin in enumerate(out_origin):
        row = {
            "output_index": out_i,
            "original_sample_index": origin,
            "original_timestamp_ms": float(t[origin]),
            "corrupted_timestamp_ms": float(out_t[out_i]),
            "operation": out_op[out_i],
            "duplicate_or_republication_source_index": (
                origin if out_op[out_i] == OPS["SOURCE_REPUBLISHED"] else None
            ),
            "corruption_profile": PROFILE_ID,
            "mode": mode,
            "severity": severity,
            "seed": int(seed),
        }
        if ids_in is not None:
            row["original_event_id"] = ids_in[origin].item() if hasattr(ids_in[origin], "item") else ids_in[origin]
        provenance.append(row)

    out_labels = None
    if label_in is not None:
        out_labels = np.asarray([label_in[i] for i in out_origin])

    return {
        "timestamps_ms": np.asarray(out_t, dtype=np.float64),
        "values": np.asarray(out_x, dtype=np.float64),
        "labels": out_labels,
        "provenance": provenance,
        "dropped_source_indices": dropped,
        "mode": mode,
        "severity": severity,
        "seed": int(seed),
        "profile_id": PROFILE_ID,
        "nominal_receive_interval_ms": nominal,
        "input_count": n,
        "output_count": len(out_t),
    }
