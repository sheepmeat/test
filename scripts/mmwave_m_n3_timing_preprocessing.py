#!/usr/bin/env python3
"""M-N3 staged timing / window / preprocessing selection.

One-off study helper. Does not freeze the canonical M-N4 input contract,
does not train, and must not read LOCKED_TEST or a future held-out split.
Derived arrays stay under tmp/mmwave_m_n3/.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mmwave_m_n2_common_representation import (  # noqa: E402
    PUBLIC_ROBUSTNESS_RECORDING_IDS,
    SPLIT,
    WINDOWS,
    PROVENANCE,
    Series,
    load_public_series,
)
from mmwave_phase_extractor import diagnostic_periodogram  # noqa: E402

MR60_DIR = ROOT / "tmp/mmwave_m_n2/mr60"
OUT_DIR = ROOT / "tmp/mmwave_m_n3"
CACHE_DIR = OUT_DIR / "public_phase_cache"

# Approximate firmware dequeue/update time. NOT physical radar acquisition time.
UPDATE_JITTER_MS = 8.0
# Relative gap: four missed updates, never the M-N2 2000 ms exploratory cut.
GAP_MULTIPLE = 4.0
GAP_FLOOR_S = 0.40
EMA_TAU_S = 0.15
MAD_FLOOR = 1e-6
WIDE_DIAGNOSTIC_BAND_HZ = (0.08, 1.00)  # DIAGNOSTIC_ONLY; not a model filter.
NARROW_DIAGNOSTIC_BAND_HZ = (0.10, 0.70)
TOTAL_BAND_HZ = (0.05, 2.0)
FUNDAMENTAL_HALFWIDTH_HZ = 0.045

MR60_FILES = {
    "LEGACY_2026-07-25_occupied_d06_v1_360s": ("2026-07-25_occupied_d06_v1_360s.jsonl", "DEVICE_DOMAIN"),
    "LEGACY_2026-07-25_occupied_d09_v1_360s": ("2026-07-25_occupied_d09_v1_360s.jsonl", "DEVICE_DOMAIN"),
    "LEGACY_2026-07-28_occupied_d09_v2_360s": ("2026-07-28_occupied_d09_v2_360s.jsonl", "DEVICE_DOMAIN"),
    "LEGACY_2026-08-01_occupied_d09_v120_31min": ("2026-08-01_occupied_d09_v120_31min.jsonl", "DEVICE_DOMAIN"),
    "LEGACY_2026-08-01_empty_v120_30min": ("2026-08-01_empty_v120_30min.jsonl", "DEVICE_DOMAIN_EMPTY"),
    "LEGACY_2026-07-25_empty_gate_v1_360s": ("2026-07-25_empty_gate_v1_360s.jsonl", "DEVICE_DOMAIN_EMPTY"),
    "M-C0-PILOT-DESKWORK-001": ("M-C0-PILOT-DESKWORK-001.raw.jsonl", "DEVICE_DOMAIN"),
    "LEGACY_2026-07-26_breath_paced_15rpm": ("2026-07-26_breath_paced_15rpm.jsonl", "WEAK_PACED"),
    "LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt03": (
        "2026-07-28_breath_paced_12rpm_explicit_v2_attempt03.jsonl",
        "WEAK_PACED",
    ),
    "LEGACY_2026-07-26_breath_paced_20rpm_deep": ("2026-07-26_breath_paced_20rpm_deep.jsonl", "WEAK_PACED"),
}


@dataclass
class PhaseEvents:
    t_s: np.ndarray
    phase: np.ndarray
    timing_basis: str
    n_rows: int
    n_events: int
    n_republications: int
    n_equal_phase_new_updates: int
    median_row_dt_s: float | None
    median_update_dt_s: float | None
    gap_threshold_s: float | None
    n_gaps: int
    notes: list[str] = field(default_factory=list)
    boot_id: str | None = None


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    n_bad = 0
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                n_bad += 1
    return rows, n_bad


def _median_dt(t: np.ndarray) -> float | None:
    if t.size < 2:
        return None
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    if dt.size == 0:
        return None
    return float(np.median(dt))


def _gap_threshold(median_dt: float | None) -> float:
    if median_dt is None or not math.isfinite(median_dt) or median_dt <= 0:
        return GAP_FLOOR_S
    return max(GAP_FLOOR_S, GAP_MULTIPLE * median_dt)


def flatten_mr60_or_pi_row(rec: dict[str, Any]) -> dict[str, Any] | None:
    nested = rec.get("mmwave") if isinstance(rec.get("mmwave"), dict) else None
    src = nested if nested is not None else rec
    phase = src.get("breath_phase")
    ts = src.get("ts_monotonic_ms")
    if phase is None or ts is None:
        return None
    try:
        phase_f = float(phase)
        ts_f = float(ts)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(phase_f) or not math.isfinite(ts_f):
        return None
    age = src.get("phase_age_ms")
    age_f = None
    if age is not None:
        try:
            age_f = float(age)
            if not math.isfinite(age_f):
                age_f = None
        except (TypeError, ValueError):
            age_f = None
    return {
        "breath_phase": phase_f,
        "ts_monotonic_ms": ts_f,
        "phase_age_ms": age_f,
        "boot_id": rec.get("boot_id") or src.get("boot_id"),
        "host_ts": rec.get("receive_monotonic") or rec.get("timestamp"),
    }


def extract_events(flat_rows: list[dict[str, Any]], *, timing: str, boot_id: str | None = None) -> PhaseEvents:
    notes: list[str] = []
    n_rows = len(flat_rows)
    row_times = np.asarray([r["ts_monotonic_ms"] / 1000.0 for r in flat_rows], dtype=np.float64)
    median_row = _median_dt(row_times)

    t_list: list[float] = []
    p_list: list[float] = []
    n_repub = 0
    n_equal_new = 0
    last_update_ms: float | None = None
    last_phase: float | None = None
    used_age = 0
    used_row = 0

    for rec in flat_rows:
        ts_ms = rec["ts_monotonic_ms"]
        age = rec["phase_age_ms"]
        phase = rec["breath_phase"]
        if timing == "T1":
            t_ms = ts_ms
            used_row += 1
            basis = "ROW_TS_MONOTONIC"
        else:
            if age is None:
                t_ms = ts_ms
                used_row += 1
                basis = "ROW_TS_FALLBACK_NO_PHASE_AGE"
            else:
                t_ms = ts_ms - age
                used_age += 1
                basis = "PHASE_UPDATE_ESTIMATE_TS_MINUS_AGE"
            if last_update_ms is not None and t_ms <= last_update_ms + UPDATE_JITTER_MS:
                n_repub += 1
                continue
        if last_phase is not None and phase == last_phase and timing != "T1":
            n_equal_new += 1
        t_list.append(t_ms / 1000.0)
        p_list.append(phase)
        last_update_ms = t_ms
        last_phase = phase

    t = np.asarray(t_list, dtype=np.float64)
    p = np.asarray(p_list, dtype=np.float64)
    if t.size >= 2:
        order = np.argsort(t, kind="mergesort")
        t, p = t[order], p[order]
    median_upd = _median_dt(t)
    gap_thr = _gap_threshold(median_upd)
    n_gaps = 0
    if t.size >= 2:
        n_gaps = int(np.sum(np.diff(t) > gap_thr))
    if used_row and used_age:
        notes.append("MIXED_UPDATE_AND_ROW_FALLBACK")
    if used_row and not used_age and timing != "T1":
        notes.append("LEGACY_ROW_TS_FALLBACK")
    timing_basis = (
        "ROW_TS_MONOTONIC"
        if timing == "T1"
        else ("PHASE_UPDATE_ESTIMATE_TS_MINUS_AGE" if used_age else "ROW_TS_FALLBACK_NO_PHASE_AGE")
    )
    notes.append(basis if t.size else "EMPTY")
    return PhaseEvents(
        t_s=t,
        phase=p,
        timing_basis=timing_basis,
        n_rows=n_rows,
        n_events=int(t.size),
        n_republications=n_repub,
        n_equal_phase_new_updates=n_equal_new,
        median_row_dt_s=median_row,
        median_update_dt_s=median_upd,
        gap_threshold_s=gap_thr,
        n_gaps=n_gaps,
        notes=notes,
        boot_id=boot_id,
    )


def split_segments(events: PhaseEvents) -> list[tuple[np.ndarray, np.ndarray]]:
    t, p = events.t_s, events.phase
    if t.size < 4:
        return []
    gap_thr = events.gap_threshold_s or GAP_FLOOR_S
    dt = np.diff(t)
    breaks = np.flatnonzero(dt > gap_thr)
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks + 1, [t.size]])
    segs = []
    for s, e in zip(starts, ends):
        if e - s >= 8:
            segs.append((t[s:e] - t[s], p[s:e]))
    return segs


def causal_ema(values: np.ndarray, t: np.ndarray, tau_s: float) -> np.ndarray:
    y = np.asarray(values, dtype=np.float64)
    out = np.empty_like(y)
    if y.size == 0:
        return out
    out[0] = y[0]
    for i in range(1, y.size):
        dt = float(t[i] - t[i - 1])
        if dt <= 0 or not math.isfinite(dt):
            out[i] = out[i - 1]
            continue
        alpha = 1.0 - math.exp(-dt / tau_s)
        out[i] = out[i - 1] + alpha * (y[i] - out[i - 1])
    return out


def r2_derivative(phase: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(phase, dtype=np.float64)
    tt = np.asarray(t, dtype=np.float64)
    if y.size < 3:
        return np.array([]), np.array([])
    dt = np.diff(tt)
    dy = np.diff(y)
    good = dt > 1e-6
    deriv = np.where(good, dy / dt, np.nan)
    td = tt[1:]
    finite = np.isfinite(deriv)
    return deriv[finite], td[finite]


def window_mad_scale(y: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    finite = y[np.isfinite(y)]
    info = {"mad": 0.0, "collapsed": False, "n_finite": int(finite.size)}
    if finite.size == 0:
        info["collapsed"] = True
        return np.zeros_like(y), info
    mad = float(np.median(np.abs(finite - np.median(finite))))
    info["mad"] = mad
    if mad < MAD_FLOOR:
        info["collapsed"] = True
        return np.zeros_like(y), info
    return y / mad, info


def resample_linear(t_src: np.ndarray, y_src: np.ndarray, t_grid: np.ndarray) -> np.ndarray:
    if t_src.size < 2:
        return np.full_like(t_grid, np.nan)
    return np.interp(t_grid, t_src, y_src, left=np.nan, right=np.nan)


def build_r2(
    phase: np.ndarray,
    t: np.ndarray,
    *,
    noise: str,
    scale: str,
    train_mad: float | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    notes: dict[str, Any] = {"noise": noise, "scale": scale}
    ph, tt = phase, t
    if noise == "N1":
        ph = causal_ema(ph, tt, EMA_TAU_S)
        notes["ema_tau_s"] = EMA_TAU_S
        notes["ema_domain"] = "phase_before_derivative"
    deriv, td = r2_derivative(ph, tt)
    if deriv.size == 0:
        return deriv, td, notes
    if noise == "N2":
        deriv = causal_ema(deriv, td, EMA_TAU_S)
        notes["ema_tau_s"] = EMA_TAU_S
        notes["ema_domain"] = "derivative"
    if scale == "S0":
        notes["scale_info"] = {"collapsed": False, "mad": None}
        return deriv, td, notes
    if scale == "S2":
        if train_mad is None or train_mad < MAD_FLOOR:
            notes["scale_info"] = {"collapsed": True, "mad": train_mad, "reason": "TRAIN_MAD_UNUSABLE"}
            return np.zeros_like(deriv), td, notes
        notes["scale_info"] = {"collapsed": False, "mad": train_mad, "source": "TRAIN_ONLY"}
        return deriv / train_mad, td, notes
    scaled, info = window_mad_scale(deriv)
    notes["scale_info"] = info
    return scaled, td, notes


def to_fixed_grid(
    deriv: np.ndarray,
    t: np.ndarray,
    *,
    window_s: float,
    hz: float,
    t0: float = 0.0,
) -> dict[str, Any]:
    n = int(round(window_s * hz))
    grid = t0 + np.arange(n, dtype=np.float64) / hz
    if deriv.size < 4:
        return {"ok": False, "reason": "TOO_SHORT", "n": n, "values": None, "grid": grid}
    # R2 exists only after the first accepted update interval, so the first
    # derivative sample is typically ~1 native Δt after the segment start.
    # Allow at most two model bins of edge overhang; do not interpolate a gap.
    edge = 2.0 / hz
    t_end = t0 + (n - 1) / hz
    if t[0] - t0 > edge or t_end - t[-1] > edge:
        return {"ok": False, "reason": "INSUFFICIENT_COVERAGE", "n": n, "values": None, "grid": grid}
    y = np.interp(grid, t, deriv)
    if not np.all(np.isfinite(y)):
        return {"ok": False, "reason": "GRID_NONFINITE", "n": n, "values": None, "grid": grid}
    return {"ok": True, "reason": None, "n": n, "values": y, "grid": grid, "max_abs": float(np.max(np.abs(y)))}


def periodogram_detail(y: np.ndarray, hz: float, ref_hz: float | None) -> dict[str, Any]:
    y = np.asarray(y, dtype=np.float64)
    out: dict[str, Any] = {
        "dominant_hz_wide": None,
        "dominant_bpm_wide": None,
        "dominant_hz_narrow": None,
        "energy_at_ref": None,
        "energy_at_half": None,
        "energy_ratio_ref_over_half": None,
        "wide_band_fraction_0p08_1p00": None,
        "narrow_band_fraction_0p10_0p70": None,
        "std": float(np.std(y)) if y.size else None,
        "max_abs": float(np.max(np.abs(y))) if y.size else None,
    }
    if y.size < 16 or not math.isfinite(hz) or hz <= 0:
        return out
    y0 = y - np.mean(y)
    windowed = y0 * np.hanning(y0.size)
    freqs = np.fft.rfftfreq(y0.size, d=1.0 / hz)
    power = np.abs(np.fft.rfft(windowed)) ** 2
    wide = (freqs >= WIDE_DIAGNOSTIC_BAND_HZ[0]) & (freqs <= WIDE_DIAGNOSTIC_BAND_HZ[1])
    narrow = (freqs >= NARROW_DIAGNOSTIC_BAND_HZ[0]) & (freqs <= NARROW_DIAGNOSTIC_BAND_HZ[1])
    total = (freqs >= TOTAL_BAND_HZ[0]) & (freqs <= TOTAL_BAND_HZ[1])
    tot = float(np.sum(power[total])) if np.any(total) else 0.0
    if tot > 0:
        out["wide_band_fraction_0p08_1p00"] = float(np.sum(power[wide]) / tot) if np.any(wide) else 0.0
        out["narrow_band_fraction_0p10_0p70"] = float(np.sum(power[narrow]) / tot) if np.any(narrow) else 0.0
    if np.any(wide) and float(np.sum(power[wide])) > 0:
        elig = np.flatnonzero(wide)
        peak = float(freqs[elig[int(np.argmax(power[elig]))]])
        out["dominant_hz_wide"] = peak
        out["dominant_bpm_wide"] = peak * 60.0
    if np.any(narrow) and float(np.sum(power[narrow])) > 0:
        elig = np.flatnonzero(narrow)
        out["dominant_hz_narrow"] = float(freqs[elig[int(np.argmax(power[elig]))]])
    if ref_hz is not None and math.isfinite(ref_hz) and ref_hz > 0:
        e_ref = float(np.sum(power[np.abs(freqs - ref_hz) <= FUNDAMENTAL_HALFWIDTH_HZ]))
        e_half = float(np.sum(power[np.abs(freqs - 0.5 * ref_hz) <= FUNDAMENTAL_HALFWIDTH_HZ]))
        out["energy_at_ref"] = e_ref
        out["energy_at_half"] = e_half
        out["energy_ratio_ref_over_half"] = (e_ref / e_half) if e_half > 0 else (math.inf if e_ref > 0 else None)
    spec = diagnostic_periodogram(y, hz, respiration_band_hz=NARROW_DIAGNOSTIC_BAND_HZ, total_band_hz=TOTAL_BAND_HZ)
    out["legacy_narrow_band_fraction"] = spec["respiration_band_fraction"]
    return out


def _load_split_guard() -> tuple[set[str], set[str]]:
    split = json.loads(SPLIT.read_text())
    locked = set(split["subject_ids"]["LOCKED_TEST"])
    train = set(split["subject_ids"]["TRAIN"])
    if "NEW_MODEL_HELDOUT_TEST" in split.get("subject_ids", {}):
        raise RuntimeError("NEW_MODEL_HELDOUT_TEST present; M-N3 must not access it")
    return train, locked


def cached_public_series(rec_id: str, prow: dict[str, Any]):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    npy = CACHE_DIR / f"{rec_id}.npz"
    if npy.exists():
        blob = np.load(npy)
        return Series(
            blob["values"],
            blob["elapsed"],
            float(blob["median_dt"][0]),
            int(blob["large_gap_count"][0]),
            0,
            ["CACHED_A2_NATIVE_UNWRAP"],
        )
    series = load_public_series(rec_id, prow)
    np.savez(
        npy,
        values=series.values,
        elapsed=series.elapsed_s,
        median_dt=np.array([series.median_dt]),
        large_gap_count=np.array([series.large_gap_count]),
    )
    return series


def public_events_from_series(series) -> PhaseEvents:
    return PhaseEvents(
        t_s=np.asarray(series.elapsed_s, dtype=np.float64),
        phase=np.asarray(series.values, dtype=np.float64),
        timing_basis="PUBLIC_NATIVE_FRAME_TIME",
        n_rows=int(series.values.size),
        n_events=int(series.values.size),
        n_republications=0,
        n_equal_phase_new_updates=0,
        median_row_dt_s=series.median_dt,
        median_update_dt_s=series.median_dt,
        gap_threshold_s=_gap_threshold(series.median_dt),
        n_gaps=int(series.large_gap_count),
        notes=["PUBLIC_EACH_FRAME_IS_NEW_SAMPLE", f"a2_notes={series.notes}"],
    )


def first_segment_window(events: PhaseEvents, noise: str, scale: str, window_s: float, hz: float, train_mad: float | None = None):
    segs = split_segments(events)
    if not segs:
        t, p = events.t_s, events.phase
        if t.size:
            t = t - t[0]
            segs = [(t, p)]
    if not segs:
        return {"ok": False, "reason": "NO_SEGMENT"}
    t, p = segs[0]
    deriv, td, notes = build_r2(p, t, noise=noise, scale="S0", train_mad=None)
    grid = to_fixed_grid(deriv, td, window_s=window_s, hz=hz, t0=0.0)
    if not grid["ok"]:
        return {"ok": False, "reason": grid["reason"], "notes": notes, "n": grid["n"]}
    y = grid["values"]
    scale_info: dict[str, Any]
    if scale == "S1":
        y, scale_info = window_mad_scale(y)
    elif scale == "S2":
        if train_mad is None or train_mad < MAD_FLOOR:
            y = np.zeros_like(y)
            scale_info = {"collapsed": True, "mad": train_mad}
        else:
            y = y / train_mad
            scale_info = {"collapsed": False, "mad": train_mad, "source": "TRAIN_ONLY"}
    else:
        scale_info = {"collapsed": False, "mad": None}
    return {
        "ok": True,
        "values": y,
        "n": grid["n"],
        "notes": notes,
        "scale_info": scale_info,
        "unscaled_std": float(np.std(grid["values"])),
        "unscaled_max_abs": float(np.max(np.abs(grid["values"]))),
        "median_dt_src": events.median_update_dt_s,
        "timing_basis": events.timing_basis,
    }


def summarize_errors(rows: list[dict[str, Any]], bpm_key: str) -> dict[str, Any]:
    err = []
    n = 0
    for r in rows:
        ref, pred = r.get("ref_rr_bpm"), r.get(bpm_key)
        if ref is None or pred is None:
            continue
        n += 1
        err.append(abs(pred - ref))
    return {
        "n_compared": n,
        "median_abs_bpm_error": float(np.median(err)) if err else None,
        "frac_within_4bpm": (sum(e <= 4 for e in err) / n) if n else None,
    }


def resolve_pi_path() -> tuple[Path | None, str]:
    named = ROOT / "tmp/mmwave_m_n3/20260817_08_mmwave.jsonl"
    if named.is_file():
        return named, "tmp/mmwave_m_n3/20260817_08_mmwave.jsonl"
    for rel in (
        Path("../safenest-integration/data/mmwave/20260817_08_mmwave.jsonl"),
        Path("../safenest-pi-integration-snapshot/data/mmwave/20260817_08_mmwave.jsonl"),
    ):
        cand = (ROOT / rel).resolve()
        if cand.is_file():
            return cand, "RECENT_PI_RUNTIME_REFERENCE:data/mmwave/20260817_08_mmwave.jsonl"
    return None, "UNAVAILABLE"


def load_pi_by_boot(path: Path) -> tuple[dict[str, list[dict[str, Any]]], int]:
    rows, n_bad = load_jsonl(path)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for rec in rows:
        flat = flatten_mr60_or_pi_row(rec)
        if flat is None:
            continue
        boot = str(flat.get("boot_id") or "UNKNOWN_BOOT")
        grouped.setdefault(boot, []).append(flat)
    return grouped, n_bad


def load_mr60_flat(path: Path) -> list[dict[str, Any]]:
    rows, _ = load_jsonl(path)
    out = []
    for rec in rows:
        flat = flatten_mr60_or_pi_row(rec)
        if flat is not None:
            out.append(flat)
    return out


def dt_stats(values: list[float] | np.ndarray) -> dict[str, Any]:
    x = np.asarray(values, dtype=np.float64)
    x = x[np.isfinite(x) & (x > 0)]
    if x.size == 0:
        return {"n": 0}
    return {
        "n": int(x.size),
        "median_s": float(np.median(x)),
        "p95_s": float(np.percentile(x, 95)),
        "max_s": float(np.max(x)),
        "approx_hz": float(1.0 / np.median(x)),
    }


def stage_a(pi_path: Path | None) -> dict[str, Any]:
    report: dict[str, Any] = {"sessions": {}, "pi": {}, "decision": {}}
    for sid, (fname, role) in MR60_FILES.items():
        path = MR60_DIR / fname
        flat = load_mr60_flat(path)
        host_dt = dt_stats(np.diff([r["ts_monotonic_ms"] / 1000.0 for r in flat])) if len(flat) > 1 else {}
        t1 = extract_events(flat, timing="T1")
        t2 = extract_events(flat, timing="T2")
        equal_phase_row = 0
        for a, b in zip(flat, flat[1:]):
            if a["breath_phase"] == b["breath_phase"]:
                equal_phase_row += 1
        report["sessions"][sid] = {
            "role": role,
            "n_rows": len(flat),
            "has_phase_age": any(r["phase_age_ms"] is not None for r in flat),
            "row_dt": host_dt,
            "T1": {
                "n_events": t1.n_events,
                "median_dt_s": t1.median_update_dt_s,
                "n_gaps": t1.n_gaps,
                "gap_thr_s": t1.gap_threshold_s,
                "timing_basis": t1.timing_basis,
            },
            "T2": {
                "n_events": t2.n_events,
                "n_republications": t2.n_republications,
                "republication_frac": t2.n_republications / t2.n_rows if t2.n_rows else None,
                "n_equal_phase_new_updates": t2.n_equal_phase_new_updates,
                "median_dt_s": t2.median_update_dt_s,
                "n_gaps": t2.n_gaps,
                "gap_thr_s": t2.gap_threshold_s,
                "timing_basis": t2.timing_basis,
            },
            "consecutive_equal_phase_rows": equal_phase_row,
        }
        # T1 vs T2 derivative noise on first 30 s of first segment.
        for label, ev in (("T1", t1), ("T2", t2)):
            built = first_segment_window(ev, "N0", "S0", 30.0, 10.0)
            report["sessions"][sid][f"{label}_r2_30s_10hz"] = {
                "ok": built.get("ok"),
                "reason": built.get("reason"),
                "unscaled_std": built.get("unscaled_std"),
                "unscaled_max_abs": built.get("unscaled_max_abs"),
                "collapsed_if_s1": None,
            }
            if built.get("ok"):
                _, info = window_mad_scale(built["values"])
                report["sessions"][sid][f"{label}_r2_30s_10hz"]["collapsed_if_s1"] = info["collapsed"]
                report["sessions"][sid][f"{label}_r2_30s_10hz"]["s1_mad"] = info["mad"]

    if pi_path is None:
        report["pi"] = {"available": False}
        report["decision"]["selected_timing"] = "T2"
        report["decision"]["why"] = "PR18/legacy update-aware; Pi file unavailable this run"
        return report

    grouped, n_bad = load_pi_by_boot(pi_path)
    pi_out = {"available": True, "n_bad_lines": n_bad, "n_boots": 0, "boots": {}, "boot_crossings_constructed": False}
    boot_ids = [k for k in grouped if not str(k).startswith("_")]
    pi_out["n_boots"] = len(boot_ids)
    for boot in boot_ids:
        flat = grouped[boot]
        host = [r["host_ts"] for r in flat if r.get("host_ts") is not None]
        host_dt = dt_stats(np.diff(np.asarray(host, dtype=np.float64))) if len(host) > 1 else {}
        t1 = extract_events(flat, timing="T1", boot_id=boot)
        t2 = extract_events(flat, timing="T2", boot_id=boot)
        span300 = None
        if t2.n_events >= 300:
            span300 = float(t2.t_s[299] - t2.t_s[0])
        pi_out["boots"][boot[:12]] = {
            "n_rows": len(flat),
            "host_publication_dt": host_dt,
            "T1_row_dt": {"median_s": t1.median_update_dt_s, "n": t1.n_events},
            "T2_update_dt": {
                "median_s": t2.median_update_dt_s,
                "n_events": t2.n_events,
                "n_republications": t2.n_republications,
                "republication_frac": t2.n_republications / t2.n_rows if t2.n_rows else None,
                "n_equal_phase_new_updates": t2.n_equal_phase_new_updates,
                "n_gaps": t2.n_gaps,
                "gap_thr_s": t2.gap_threshold_s,
            },
            "span_300_update_samples_s": span300,
        }
    pi_out["never_window_across_boot"] = True
    report["pi"] = pi_out
    report["decision"] = {
        "selected_timing": "T2_THEN_FIXED_GRID",
        "timing_ids": "T3 = T2 phase-update events, then R2, then fixed-grid resample",
        "why": (
            "Publication rows are not always new phase updates. T2 uses "
            "ts_monotonic_ms-phase_age_ms as an update estimate, drops "
            "republications, and keeps equal numeric phase when the update "
            "time advances. T3 is that event sequence on a fixed model grid."
        ),
        "exact_physical_acquisition_time_claimed": False,
        "m_n2_2000ms_inherited": False,
        "gap_rule": f"segment/invalidate if Δt_update > max({GAP_FLOOR_S}s, {GAP_MULTIPLE}×median_update_dt)",
    }
    return report


def evaluate_public_contract(
    rec_ids: list[str],
    provenance: dict[str, dict[str, Any]],
    windows: dict[str, dict[str, Any]],
    train: set[str],
    locked: set[str],
    *,
    noise: str,
    scale: str,
    window_s: float,
    hz: float,
    train_mad: float | None,
) -> list[dict[str, Any]]:
    rows = []
    for rec_id in rec_ids:
        prow = provenance[rec_id]
        if prow["split"] != "TRAIN" or prow["subject_id"] not in train:
            raise RuntimeError(f"non-TRAIN recording: {rec_id}")
        if prow["subject_id"] in locked:
            raise RuntimeError(f"LOCKED_TEST accessed: {rec_id}")
        series = cached_public_series(rec_id, prow)
        events = public_events_from_series(series)
        built = first_segment_window(events, noise, scale, window_s, hz, train_mad=train_mad)
        win = windows[prow["window_id"]]
        ref = win.get("movesense_reference_rr", {}).get("rr_bpm")
        ref_hz = (ref / 60.0) if ref is not None else None
        spec = periodogram_detail(built["values"], hz, ref_hz) if built.get("ok") else {}
        nb = float(win.get("annotation_overlap_seconds") or 0) > 0 or win.get("original_annotation_type") == "VOLUNTARY_NON_BREATHING"
        rows.append({
            "recording_id": rec_id,
            "subject_id": prow["subject_id"],
            "posture": win.get("posture"),
            "condition": win.get("source_test_condition"),
            "ref_rr_bpm": ref,
            "non_breathing": bool(nb),
            "ok": bool(built.get("ok")),
            "reason": built.get("reason"),
            "public_native_median_dt_s": series.median_dt,
            "scale_collapsed": bool(built.get("scale_info", {}).get("collapsed")) if built.get("ok") else None,
            "unscaled_std": built.get("unscaled_std"),
            "dominant_bpm_wide": spec.get("dominant_bpm_wide"),
            "dominant_hz_narrow": spec.get("dominant_hz_narrow"),
            "energy_ratio_ref_over_half": spec.get("energy_ratio_ref_over_half"),
            "energy_at_ref": spec.get("energy_at_ref"),
            "energy_at_half": spec.get("energy_at_half"),
            "wide_band_fraction_0p08_1p00": spec.get("wide_band_fraction_0p08_1p00"),
        })
    return rows


def classify_high_rr(row: dict[str, Any]) -> str | None:
    ref = row.get("ref_rr_bpm")
    if ref is None or ref < 25 or not row.get("ok"):
        return None
    pred = row.get("dominant_bpm_wide")
    ratio = row.get("energy_ratio_ref_over_half")
    if pred is not None and abs(pred - ref) <= 4:
        return "PEAK_MATCH"
    if ratio is not None and math.isfinite(ratio) and ratio >= 0.75:
        return "FUNDAMENTAL_ENERGY_RETAINED_PEAK_MISMATCH"
    if pred is not None and abs(pred - 0.5 * ref) <= 4:
        return "SUBHARMONIC_PEAK"
    if ref >= 40:
        return "NEAR_OR_ABOVE_0p70HZ"
    return "UNDERESTIMATE_OR_WEAK"


def stage_b_c(stage_a_report: dict[str, Any]) -> dict[str, Any]:
    train, locked = _load_split_guard()
    provenance = {}
    for row in load_jsonl(PROVENANCE)[0]:
        if row["window_id"].endswith("__W0000"):
            provenance[row["recording_id"]] = row
    windows = {row["window_id"]: row for row in load_jsonl(WINDOWS)[0]}

    public_native = []
    for rec_id in PUBLIC_ROBUSTNESS_RECORDING_IDS:
        series = cached_public_series(rec_id, provenance[rec_id])
        public_native.append(series.median_dt)

    # TRAIN MAD for S2 from N0 unscaled 30 s / 10 Hz on the same TRAIN sample.
    s2_mads = []
    for rec_id in PUBLIC_ROBUSTNESS_RECORDING_IDS:
        series = cached_public_series(rec_id, provenance[rec_id])
        built = first_segment_window(public_events_from_series(series), "N0", "S0", 30.0, 10.0)
        if built.get("ok"):
            y = built["values"]
            mad = float(np.median(np.abs(y - np.median(y))))
            if mad >= MAD_FLOOR:
                s2_mads.append(mad)
    train_mad = float(np.median(s2_mads)) if s2_mads else None

    noise_scale_rows = {}
    for noise in ("N0", "N1", "N2"):
        for scale in ("S0", "S1"):
            key = f"{noise}_{scale}"
            rows = evaluate_public_contract(
                PUBLIC_ROBUSTNESS_RECORDING_IDS,
                provenance,
                windows,
                train,
                locked,
                noise=noise,
                scale=scale,
                window_s=30.0,
                hz=10.0,
                train_mad=None,
            )
            noise_scale_rows[key] = rows

    s2_rows = evaluate_public_contract(
        PUBLIC_ROBUSTNESS_RECORDING_IDS,
        provenance,
        windows,
        train,
        locked,
        noise="N0",
        scale="S2",
        window_s=30.0,
        hz=10.0,
        train_mad=train_mad,
    )
    noise_scale_rows["N0_S2"] = s2_rows

    def pack_public(rows: list[dict[str, Any]]) -> dict[str, Any]:
        ok = [r for r in rows if r["ok"]]
        cont = [r for r in ok if not r["non_breathing"]]
        nb = [r for r in ok if r["non_breathing"]]
        low = [r for r in cont if r["ref_rr_bpm"] is not None and r["ref_rr_bpm"] < 25]
        high = [r for r in ok if r["ref_rr_bpm"] is not None and r["ref_rr_bpm"] >= 25]
        high_classes = [classify_high_rr(r) for r in high]
        fund = [r for r in high if classify_high_rr(r) in {"PEAK_MATCH", "FUNDAMENTAL_ENERGY_RETAINED_PEAK_MISMATCH"}]
        return {
            "n_ok": len(ok),
            "n_subjects": len({r["subject_id"] for r in rows}),
            "n_recordings": len(rows),
            "all": summarize_errors(ok, "dominant_bpm_wide"),
            "continuous_breathing": summarize_errors(cont, "dominant_bpm_wide"),
            "non_breathing_overlap": {
                "n": len(nb),
                "median_wide_band_fraction": float(np.median([r["wide_band_fraction_0p08_1p00"] for r in nb if r["wide_band_fraction_0p08_1p00"] is not None])) if nb else None,
                "median_std": float(np.median([r["unscaled_std"] for r in nb if r["unscaled_std"] is not None])) if nb else None,
                "n_collapsed": sum(bool(r["scale_collapsed"]) for r in nb),
            },
            "rr_lt_25_continuous": summarize_errors(low, "dominant_bpm_wide"),
            "rr_ge_25": summarize_errors(high, "dominant_bpm_wide"),
            "high_rr_classes": {k: high_classes.count(k) for k in sorted({c for c in high_classes if c})},
            "high_rr_fundamental_retained_frac": (len(fund) / len(high)) if high else None,
            "median_energy_ratio_high_rr": float(np.median([r["energy_ratio_ref_over_half"] for r in high if r["energy_ratio_ref_over_half"] not in (None, float("inf"))])) if high else None,
        }

    public_summaries = {k: pack_public(v) for k, v in noise_scale_rows.items()}

    mr60_preproc = {}
    for sid, (fname, role) in MR60_FILES.items():
        if role == "WEAK_PACED":
            continue
        flat = load_mr60_flat(MR60_DIR / fname)
        ev = extract_events(flat, timing="T2")
        sid_out = {"role": role, "timing": ev.timing_basis, "n_events": ev.n_events, "n_repub": ev.n_republications}
        for noise in ("N0", "N1", "N2"):
            for scale in ("S0", "S1"):
                built = first_segment_window(ev, noise, scale, 30.0, 10.0)
                spec = periodogram_detail(built["values"], 10.0, None) if built.get("ok") else {}
                sid_out[f"{noise}_{scale}"] = {
                    "ok": built.get("ok"),
                    "collapsed": built.get("scale_info", {}).get("collapsed") if built.get("ok") else None,
                    "unscaled_std": built.get("unscaled_std"),
                    "std": spec.get("std"),
                    "dominant_bpm_wide": spec.get("dominant_bpm_wide"),
                    "wide_band_fraction": spec.get("wide_band_fraction_0p08_1p00"),
                    "max_abs": spec.get("max_abs"),
                }
        built_s2 = first_segment_window(ev, "N0", "S2", 30.0, 10.0, train_mad=train_mad)
        spec_s2 = periodogram_detail(built_s2["values"], 10.0, None) if built_s2.get("ok") else {}
        sid_out["N0_S2"] = {
            "ok": built_s2.get("ok"),
            "std": spec_s2.get("std"),
            "max_abs": spec_s2.get("max_abs"),
            "dominant_bpm_wide": spec_s2.get("dominant_bpm_wide"),
            "train_mad": train_mad,
        }
        mr60_preproc[sid] = sid_out

    # Stage C: selected N0_S1 vs fallback N2_S1 across windows/rates.
    window_rate = {}
    for noise, scale in (("N0", "S1"), ("N2", "S1")):
        for window_s in (20.0, 30.0, 40.0):
            for hz in (8.0, 10.0):
                key = f"{noise}_{scale}_{int(window_s)}s_{int(hz)}Hz"
                rows = evaluate_public_contract(
                    PUBLIC_ROBUSTNESS_RECORDING_IDS,
                    provenance,
                    windows,
                    train,
                    locked,
                    noise=noise,
                    scale=scale,
                    window_s=window_s,
                    hz=hz,
                    train_mad=None,
                )
                mr60_ok = {}
                for sid, (fname, role) in MR60_FILES.items():
                    if role == "WEAK_PACED":
                        continue
                    ev = extract_events(load_mr60_flat(MR60_DIR / fname), timing="T2")
                    built = first_segment_window(ev, noise, scale, window_s, hz)
                    spec = periodogram_detail(built["values"], hz, None) if built.get("ok") else {}
                    mr60_ok[sid] = {
                        "ok": built.get("ok"),
                        "reason": built.get("reason"),
                        "n": int(round(window_s * hz)),
                        "collapsed": built.get("scale_info", {}).get("collapsed") if built.get("ok") else None,
                        "dominant_bpm_wide": spec.get("dominant_bpm_wide"),
                        "wide_band_fraction": spec.get("wide_band_fraction_0p08_1p00"),
                        "std": spec.get("std"),
                    }
                window_rate[key] = {
                    "sample_count": int(round(window_s * hz)),
                    "public": pack_public(rows),
                    "mr60": mr60_ok,
                }

    high_rr_examples = []
    for r in noise_scale_rows["N0_S1"]:
        if r.get("ref_rr_bpm") is not None and r["ref_rr_bpm"] >= 25:
            high_rr_examples.append({
                "recording_id": r["recording_id"].split("18599983-")[-1],
                "ref_rr_bpm": r["ref_rr_bpm"],
                "non_breathing": r["non_breathing"],
                "dominant_bpm_wide": r["dominant_bpm_wide"],
                "energy_ratio_ref_over_half": r["energy_ratio_ref_over_half"],
                "class": classify_high_rr(r),
            })

    return {
        "public_native_median_dt_s": {
            "median": float(np.median(public_native)),
            "min": float(np.min(public_native)),
            "max": float(np.max(public_native)),
            "n": len(public_native),
        },
        "train_mad_n0_30s_10hz": train_mad,
        "n_train_mad_windows": len(s2_mads),
        "stage_b_public": public_summaries,
        "stage_b_mr60": mr60_preproc,
        "stage_c_window_rate": window_rate,
        "high_rr_examples_N0_S1_30s_10hz": high_rr_examples,
        "locked_test_accessed": False,
        "new_model_heldout_accessed": False,
        "public_subjects": sorted({provenance[i]["subject_id"] for i in PUBLIC_ROBUSTNESS_RECORDING_IDS}),
        "n_public_recordings": len(PUBLIC_ROBUSTNESS_RECORDING_IDS),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pi_path, pi_label = resolve_pi_path()
    stage_a_report = stage_a(pi_path)
    stage_a_report["pi"]["source_label"] = pi_label
    bc = stage_b_c(stage_a_report)
    payload = {
        "study_id": "M-N3_TIMING_WINDOW_PREPROCESSING_001",
        "r2_amplitude_scale_contract_before": "UNRESOLVED",
        "historical_bpf_zscore_used": False,
        "historical_b_scaler_used": False,
        "public_mr60_std_matching_used": False,
        "mr60_arbitrary_gain_used": False,
        "inherited_2000ms": False,
        "inherited_shape_1_300_1": False,
        "pi_role": "RECENT_PI_RUNTIME_REFERENCE",
        "stage_a": stage_a_report,
        "stage_b_c": bc,
        "selected": {
            "representation": "R2",
            "timing_basis": "PHASE_UPDATE_ESTIMATE_TS_MINUS_AGE then fixed grid (T3)",
            "duplicate_handling": "drop rows whose update estimate does not advance by >8 ms",
            "gap_handling": f"invalidate/segment if Δt_update > max({GAP_FLOOR_S}s, {GAP_MULTIPLE}×median_update_dt); no long-gap interpolation",
            "derivative": "(x[i]-x[i-1]) / Δt_update on accepted phase events",
            "noise_handling": "N0 raw derivative",
            "amplitude_scaling": "S1 window-local MAD; MAD<1e-6 → zeros (no empty amplification)",
            "window_s": 30.0,
            "rate_hz": 8.0,
            "sample_count": 240,
            "resampling": "linear interpolation of R2 onto uniform grid after phase-event derivative",
            "runtime_causal": True,
            "r2_amplitude_scale_contract": "RESOLVED_S1_WINDOW_MAD",
            "why": (
                "30 s keeps high-RR fundamental energy without 40 s latency. "
                "8 Hz matches Pi genuine update cadence (~7.1 Hz) better than 10 Hz. "
                "Not inherited from historical [1,300,1]."
            ),
        },
        "fallback": {
            "representation": "R2",
            "timing_basis": "same T3",
            "noise_handling": "N0",
            "amplitude_scaling": "S1 window-local MAD",
            "window_s": 30.0,
            "rate_hz": 10.0,
            "sample_count": 300,
            "why": "public-native 10 Hz grid. Not inherited from historical [1,300,1]. Use if M-N4 prefers matching public radar cadence over Pi update cadence.",
        },
    }
    out = OUT_DIR / "m_n3_summary.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({
        "wrote": str(out.relative_to(ROOT)),
        "pi_source": pi_label,
        "stage_a_decision": stage_a_report.get("decision"),
        "public_native_dt": bc["public_native_median_dt_s"],
        "stage_b_public_keys": {k: v["rr_lt_25_continuous"] for k, v in bc["stage_b_public"].items()},
        "high_rr_N0_S1": bc["stage_b_public"]["N0_S1"]["high_rr_classes"],
        "stage_c_public_lt25": {
            k: v["public"]["rr_lt_25_continuous"] for k, v in bc["stage_c_window_rate"].items()
        },
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
