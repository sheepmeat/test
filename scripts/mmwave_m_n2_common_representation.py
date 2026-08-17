#!/usr/bin/env python3
"""M-N2 exploratory public ↔ MR60 common-representation comparison.

This script is a one-off study helper. It does not freeze timing/window
contracts, does not train a model, and must not read LOCKED_TEST / future
held-out subjects. Derived arrays stay under tmp/mmwave_m_n2/.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import butter, filtfilt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mmwave_phase_extractor import diagnostic_periodogram  # noqa: E402
from mmwave_rfft_reader import SafeRFFTReader  # noqa: E402

ARCHIVE = ROOT / "datasets/raw_archives/external_datasets/db_records.zip"
PROVENANCE = ROOT / "datasets/mmwave/manifests/a6_full_conversion/full_provenance_manifest.jsonl"
WINDOWS = ROOT / "datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl"
SPLIT = ROOT / "datasets/mmwave/splits/mmwave_real_subject_split_v1.json"
MR60_DIR = ROOT / "tmp/mmwave_m_n2/mr60"
OUT_DIR = ROOT / "tmp/mmwave_m_n2"
STALE_PHASE_AGE_MS = 2000.0
GAP_FACTOR = 2.5
NEW_RESP_BAND_HZ = (0.10, 0.70)  # A4 ACC search band 0.1–0.7 Hz / 6–42 bpm. Not historical B 0.1–0.5.
TOTAL_BAND_HZ = (0.05, 2.0)
MAD_FLOOR = 1e-9
EXPLORATORY_SLICE_S = 30.0  # EXPLORATORY_ONLY; not the M-N3 window.

PUBLIC_RECORDING_IDS = [
    "dataset-10_5281_zenodo_18599983-p001-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p002-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p004-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p005-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p007-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p008-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p010-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p011-sitting-post_exercise",
    "dataset-10_5281_zenodo_18599983-p001-lying-post_exercise",
    "dataset-10_5281_zenodo_18599983-p004-lying-post_exercise",
    "dataset-10_5281_zenodo_18599983-p007-lying-post_exercise",
    "dataset-10_5281_zenodo_18599983-p008-lying-post_exercise",
]


@dataclass
class Series:
    values: np.ndarray
    elapsed_s: np.ndarray
    median_dt: float
    large_gap_count: int
    dropped_stale: int
    notes: list[str]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _elapsed_from_dt(dt: np.ndarray) -> tuple[np.ndarray, float, int]:
    elapsed = np.concatenate([[0.0], np.cumsum(dt)])
    median_dt = float(np.median(dt)) if dt.size else float("nan")
    gap_thr = GAP_FACTOR * median_dt if math.isfinite(median_dt) and median_dt > 0 else None
    gaps = int(np.sum(dt > gap_thr)) if gap_thr is not None else 0
    return elapsed, median_dt, gaps


def _longest_contiguous(values: np.ndarray, elapsed: np.ndarray, median_dt: float) -> tuple[np.ndarray, np.ndarray]:
    if values.size < 4 or not math.isfinite(median_dt) or median_dt <= 0:
        return values, elapsed
    dt = np.diff(elapsed)
    breaks = np.flatnonzero(dt > GAP_FACTOR * median_dt)
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks + 1, [values.size]])
    lengths = ends - starts
    i = int(np.argmax(lengths))
    return values[starts[i]:ends[i]], elapsed[starts[i]:ends[i]] - elapsed[starts[i]]


def load_public_series(recording_id: str, provenance_row: dict[str, Any]) -> Series:
    radar = provenance_row["source_radar_member"]
    ts_member = provenance_row["source_timestamp_member"]
    chirp = radar.replace("radar_rFFTs.zlib", "radar_chirpConfig.json")
    decoded = SafeRFFTReader().read_recording(
        archive_path=str(ARCHIVE),
        radar_member=radar,
        timestamp_member=ts_member,
        chirp_config_member=chirp,
    )
    if decoded["errors"]:
        raise RuntimeError(f"A1 errors for {recording_id}: {decoded['errors']}")
    tensor = decoded["tensor"]
    bin_index = int(provenance_row["selected_range_bin_index"])
    channel = int(provenance_row["selected_virtual_channel"])
    complex_signal = np.asarray(tensor[:, channel, bin_index])
    phase = np.unwrap(np.angle(complex_signal)).astype(np.float64)
    median_dt = float(decoded["timestamp_metadata"]["timestamp_median_dt_seconds"])
    elapsed = np.arange(phase.size, dtype=np.float64) * median_dt
    notes = [
        "A2_NATIVE_UNWRAP_REUSED_A6_BIN_CHANNEL",
        f"a1_alignment={decoded['structural_metadata']['alignment_status']}",
    ]
    if decoded["timestamp_metadata"]["large_gap_count"]:
        notes.append(f"public_large_gaps={decoded['timestamp_metadata']['large_gap_count']}")
    return Series(phase, elapsed, median_dt, int(decoded["timestamp_metadata"]["large_gap_count"]), 0, notes)


def load_mr60_series(path: Path) -> Series:
    phases: list[float] = []
    times: list[float] = []
    dropped_stale = 0
    dropped_bad = 0
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                dropped_bad += 1
                continue
            phase = rec.get("breath_phase")
            ts = rec.get("ts_monotonic_ms")
            age = rec.get("phase_age_ms")
            if phase is None or ts is None or not math.isfinite(float(phase)) or not math.isfinite(float(ts)):
                dropped_bad += 1
                continue
            if age is not None and math.isfinite(float(age)) and float(age) > STALE_PHASE_AGE_MS:
                dropped_stale += 1
                continue
            phases.append(float(phase))
            times.append(float(ts) / 1000.0)
    values = np.asarray(phases, dtype=np.float64)
    t = np.asarray(times, dtype=np.float64)
    notes = [f"dropped_bad={dropped_bad}"]
    if values.size < 4:
        return Series(values, np.zeros_like(values), float("nan"), 0, dropped_stale, notes + ["TOO_SHORT"])
    order = np.argsort(t)
    values, t = values[order], t[order]
    dt = np.diff(t)
    elapsed, median_dt, gaps = _elapsed_from_dt(dt)
    values, elapsed = _longest_contiguous(values, elapsed, median_dt)
    notes.append(f"longest_contiguous_n={int(values.size)}")
    return Series(values, elapsed, median_dt, gaps, dropped_stale, notes)


def linear_detrend(values: np.ndarray, elapsed: np.ndarray) -> np.ndarray:
    y = np.asarray(values, dtype=np.float64)
    t = np.asarray(elapsed, dtype=np.float64)
    if y.size < 2 or not np.all(np.isfinite(y)) or not np.all(np.isfinite(t)):
        return np.full_like(y, np.nan)
    slope, intercept = np.polyfit(t, y, 1)
    return y - (slope * t + intercept)


def r1_centered_detrended(series: Series) -> np.ndarray:
    return linear_detrend(series.values, series.elapsed_s)


def r2_time_aware_derivative(series: Series) -> np.ndarray:
    y = np.asarray(series.values, dtype=np.float64)
    t = np.asarray(series.elapsed_s, dtype=np.float64)
    if y.size < 3:
        return np.full_like(y, np.nan)
    dt = np.diff(t)
    dy = np.diff(y)
    deriv = np.empty_like(y)
    deriv[0] = np.nan
    good = dt > 1e-6
    deriv[1:] = np.where(good, dy / dt, np.nan)
    # Keep length by dropping the leading NaN for downstream spectra.
    return deriv[1:]


def r2_elapsed(series: Series) -> np.ndarray:
    return np.asarray(series.elapsed_s[1:], dtype=np.float64)


def _mad(values: np.ndarray) -> float:
    y = values[np.isfinite(values)]
    if y.size == 0:
        return 0.0
    return float(np.median(np.abs(y - np.median(y))))


def r3_band_scale_robust(series: Series, values: np.ndarray | None = None) -> tuple[np.ndarray, list[str]]:
    notes: list[str] = []
    y = linear_detrend(series.values if values is None else values, series.elapsed_s if values is None else series.elapsed_s)
    dt = np.diff(series.elapsed_s)
    median_dt = series.median_dt
    if y.size < 16 or not math.isfinite(median_dt) or median_dt <= 0:
        return np.full_like(y, np.nan), ["R3_SKIPPED_TOO_SHORT"]
    irregular = bool(dt.size and (float(np.max(dt) / median_dt) > 1.8))
    fs = 1.0 / median_dt
    nyquist = 0.5 * fs
    lo, hi = NEW_RESP_BAND_HZ
    if hi >= nyquist:
        return np.full_like(y, np.nan), [f"R3_SKIPPED_NYQUIST fs={fs:.3f}"]
    if irregular:
        notes.append("R3_EXPLORATORY_FILTER_ON_NATIVE_SAMPLES")
    b, a = butter(2, [lo / nyquist, hi / nyquist], btype="band")
    finite = np.isfinite(y)
    if not np.all(finite):
        y = y.copy()
        y[~finite] = 0.0
        notes.append("R3_NONFINITE_ZEROED_BEFORE_FILTER")
    filtered = filtfilt(b, a, y)
    mad = _mad(filtered)
    if mad < MAD_FLOOR:
        notes.append("R3_MAD_TOO_SMALL_UNSCALED")
        return filtered, notes
    notes.append("R3_PER_RECORDING_MAD_SCALE")
    return filtered / mad, notes


def slice_exploratory(values: np.ndarray, elapsed: np.ndarray, duration_s: float = EXPLORATORY_SLICE_S) -> tuple[np.ndarray, np.ndarray]:
    mask = elapsed <= duration_s + 1e-9
    if int(np.sum(mask)) < 8:
        return values, elapsed
    return values[mask], elapsed[mask]


def dominant_and_band(values: np.ndarray, elapsed: np.ndarray) -> dict[str, Any]:
    y = np.asarray(values, dtype=np.float64)
    t = np.asarray(elapsed, dtype=np.float64)
    finite = np.isfinite(y) & np.isfinite(t)
    y, t = y[finite], t[finite]
    out = {
        "n": int(y.size),
        "finite_fraction": float(np.mean(np.isfinite(values))) if values.size else 0.0,
        "max_abs": float(np.nanmax(np.abs(y))) if y.size else None,
        "std": float(np.nanstd(y)) if y.size else None,
        "dominant_hz": None,
        "dominant_bpm": None,
        "band_fraction": None,
        "autocorr_lag_s": None,
        "autocorr_peak": None,
    }
    if y.size < 16:
        return out
    dt = float(np.median(np.diff(t))) if t.size > 1 else float("nan")
    fs = 1.0 / dt if math.isfinite(dt) and dt > 0 else float("nan")
    if not math.isfinite(fs):
        return out
    spec = diagnostic_periodogram(y, fs, respiration_band_hz=NEW_RESP_BAND_HZ, total_band_hz=TOTAL_BAND_HZ)
    # Peak inside the respiration band only. A2's diagnostic peak uses a wider
    # total band and can lock onto residual drift; that is not a respiration test.
    y_d = linear_detrend(y, t)
    windowed = y_d * np.hanning(y_d.size)
    frequencies = np.fft.rfftfreq(y_d.size, d=1.0 / fs)
    power = np.abs(np.fft.rfft(windowed)) ** 2
    in_band = (frequencies >= NEW_RESP_BAND_HZ[0]) & (frequencies <= NEW_RESP_BAND_HZ[1])
    if np.any(in_band) and float(np.sum(power[in_band])) > 0:
        eligible = np.flatnonzero(in_band)
        peak_hz = float(frequencies[eligible[int(np.argmax(power[eligible]))]])
        out["dominant_hz"] = peak_hz
        out["dominant_bpm"] = float(peak_hz * 60.0)
    out["band_fraction"] = spec["respiration_band_fraction"]
    y0 = y - np.mean(y)
    denom = float(np.dot(y0, y0))
    if denom > 0:
        ac = np.correlate(y0, y0, mode="full")[y.size - 1 :] / denom
        min_lag = max(1, int(round(0.5 / (NEW_RESP_BAND_HZ[1] * dt))))
        max_lag = min(ac.size - 1, int(round(2.0 / (NEW_RESP_BAND_HZ[0] * dt))))
        if max_lag > min_lag:
            region = ac[min_lag : max_lag + 1]
            k = int(np.argmax(region))
            out["autocorr_lag_s"] = float((min_lag + k) * dt)
            out["autocorr_peak"] = float(region[k])
    return out


def apply_all(series: Series) -> dict[str, Any]:
    r1 = r1_centered_detrended(series)
    r2 = r2_time_aware_derivative(series)
    r2_t = r2_elapsed(series)
    r3, r3_notes = r3_band_scale_robust(series)
    r1_s, r1_t = slice_exploratory(r1, series.elapsed_s)
    r2_s, r2_st = slice_exploratory(r2, r2_t)
    r3_s, r3_t = slice_exploratory(r3, series.elapsed_s)
    return {
        "median_dt": series.median_dt,
        "n_full": int(series.values.size),
        "large_gap_count": series.large_gap_count,
        "dropped_stale": series.dropped_stale,
        "notes": series.notes + r3_notes,
        "raw_max_abs": float(np.nanmax(np.abs(series.values))) if series.values.size else None,
        "R1": dominant_and_band(r1_s, r1_t),
        "R2": dominant_and_band(r2_s, r2_st),
        "R3": dominant_and_band(r3_s, r3_t),
        "R1_full": dominant_and_band(r1, series.elapsed_s),
        "R2_full": dominant_and_band(r2, r2_t),
        "R3_full": dominant_and_band(r3, series.elapsed_s),
    }


def _summarize_errors(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    abs_err = []
    within2 = 0
    within4 = 0
    n = 0
    band = []
    finite = []
    for row in rows:
        ref = row.get("ref_rr_bpm")
        pred = row["metrics"][key].get("dominant_bpm")
        if ref is None or pred is None:
            continue
        n += 1
        err = abs(pred - ref)
        abs_err.append(err)
        within2 += int(err <= 2.0)
        within4 += int(err <= 4.0)
        if row["metrics"][key].get("band_fraction") is not None:
            band.append(row["metrics"][key]["band_fraction"])
        finite.append(row["metrics"][key].get("finite_fraction"))
    return {
        "n_compared": n,
        "median_abs_bpm_error": float(np.median(abs_err)) if abs_err else None,
        "mean_abs_bpm_error": float(np.mean(abs_err)) if abs_err else None,
        "frac_within_2bpm": (within2 / n) if n else None,
        "frac_within_4bpm": (within4 / n) if n else None,
        "median_band_fraction": float(np.median(band)) if band else None,
        "median_finite_fraction": float(np.median(finite)) if finite else None,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    split = json.loads(SPLIT.read_text())
    locked = set(split["subject_ids"]["LOCKED_TEST"])
    train = set(split["subject_ids"]["TRAIN"])

    provenance = {}
    for row in _load_jsonl(PROVENANCE):
        if row["window_id"].endswith("__W0000"):
            provenance[row["recording_id"]] = row
    windows = {row["window_id"]: row for row in _load_jsonl(WINDOWS)}

    public_rows = []
    for rec_id in PUBLIC_RECORDING_IDS:
        prow = provenance[rec_id]
        if prow["split"] != "TRAIN" or prow["subject_id"] not in train:
            raise RuntimeError(f"non-TRAIN recording slipped in: {rec_id} split={prow['split']}")
        if prow["subject_id"] in locked:
            raise RuntimeError(f"LOCKED_TEST accessed: {rec_id}")
        series = load_public_series(rec_id, prow)
        win = windows[prow["window_id"]]
        metrics = apply_all(series)
        public_rows.append({
            "recording_id": rec_id,
            "subject_id": prow["subject_id"],
            "split": prow["split"],
            "source_radar_member": prow["source_radar_member"],
            "selected_range_bin_index": prow["selected_range_bin_index"],
            "selected_virtual_channel": prow["selected_virtual_channel"],
            "ref_rr_bpm": win.get("movesense_reference_rr", {}).get("rr_bpm"),
            "safenest_label": win.get("safenest_label"),
            "metrics": metrics,
        })

    mr60_specs = [
        ("LEGACY_2026-07-25_occupied_d06_v1_360s", "occupied_d06", "DEVICE_DOMAIN", None),
        ("LEGACY_2026-07-25_occupied_d09_v1_360s", "occupied_d09", "DEVICE_DOMAIN", None),
        ("LEGACY_2026-07-28_occupied_d09_v2_360s", "occupied_d09_v2", "DEVICE_DOMAIN", None),
        ("LEGACY_2026-08-01_occupied_d09_v120_31min", "occupied_d09_31min_attempt01", "DEVICE_DOMAIN", None),
        ("LEGACY_2026-08-01_empty_v120_30min", "empty_30min", "DEVICE_DOMAIN_EMPTY", None),
        ("LEGACY_2026-07-25_empty_gate_v1_360s", "empty_gate_360s", "DEVICE_DOMAIN_EMPTY", None),
        ("M-C0-PILOT-DESKWORK-001", "pr18_deskwork", "DEVICE_DOMAIN", None),
        ("LEGACY_2026-07-26_breath_paced_15rpm", "paced_15", "WEAK_PACED", 15.0),
        ("LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt03", "paced_12_valid", "WEAK_PACED", 12.0),
        ("LEGACY_2026-07-26_breath_paced_20rpm_deep", "paced_20_deep", "WEAK_PACED", 20.0),
    ]
    files = {
        "LEGACY_2026-07-25_occupied_d06_v1_360s": "2026-07-25_occupied_d06_v1_360s.jsonl",
        "LEGACY_2026-07-25_occupied_d09_v1_360s": "2026-07-25_occupied_d09_v1_360s.jsonl",
        "LEGACY_2026-07-28_occupied_d09_v2_360s": "2026-07-28_occupied_d09_v2_360s.jsonl",
        "LEGACY_2026-08-01_occupied_d09_v120_31min": "2026-08-01_occupied_d09_v120_31min.jsonl",
        "LEGACY_2026-08-01_empty_v120_30min": "2026-08-01_empty_v120_30min.jsonl",
        "LEGACY_2026-07-25_empty_gate_v1_360s": "2026-07-25_empty_gate_v1_360s.jsonl",
        "M-C0-PILOT-DESKWORK-001": "M-C0-PILOT-DESKWORK-001.raw.jsonl",
        "LEGACY_2026-07-26_breath_paced_15rpm": "2026-07-26_breath_paced_15rpm.jsonl",
        "LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt03": "2026-07-28_breath_paced_12rpm_explicit_v2_attempt03.jsonl",
        "LEGACY_2026-07-26_breath_paced_20rpm_deep": "2026-07-26_breath_paced_20rpm_deep.jsonl",
    }
    mr60_rows = []
    for session_id, short, role, cue in mr60_specs:
        series = load_mr60_series(MR60_DIR / files[session_id])
        metrics = apply_all(series)
        mr60_rows.append({
            "session_id": session_id,
            "short": short,
            "role": role,
            "paced_cue_rpm": cue,
            "primary_selection": role != "WEAK_PACED",
            "metrics": metrics,
        })

    public_summary = {key: _summarize_errors(public_rows, key) for key in ("R1", "R2", "R3")}
    occupied = [r for r in mr60_rows if r["role"] == "DEVICE_DOMAIN"]
    empty = [r for r in mr60_rows if r["role"] == "DEVICE_DOMAIN_EMPTY"]
    paced = [r for r in mr60_rows if r["role"] == "WEAK_PACED"]

    def pack_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
        packed = {}
        for key in ("R1", "R2", "R3"):
            bpm = [r["metrics"][key].get("dominant_bpm") for r in rows if r["metrics"][key].get("dominant_bpm") is not None]
            band = [r["metrics"][key].get("band_fraction") for r in rows if r["metrics"][key].get("band_fraction") is not None]
            mx = [r["metrics"][key].get("max_abs") for r in rows if r["metrics"][key].get("max_abs") is not None]
            finite = [r["metrics"][key].get("finite_fraction") for r in rows]
            packed[key] = {
                "n": len(rows),
                "median_bpm": float(np.median(bpm)) if bpm else None,
                "bpm_values": bpm,
                "median_band_fraction": float(np.median(band)) if band else None,
                "max_abs_median": float(np.median(mx)) if mx else None,
                "max_abs_max": float(np.max(mx)) if mx else None,
                "median_finite": float(np.median(finite)) if finite else None,
            }
        packed["raw_max_abs"] = [r["metrics"]["raw_max_abs"] for r in rows]
        packed["median_dt"] = [r["metrics"]["median_dt"] for r in rows]
        packed["dropped_stale"] = [r["metrics"]["dropped_stale"] for r in rows]
        return packed

    paced_err = {}
    for key in ("R1", "R2", "R3"):
        errs = []
        for row in paced:
            pred = row["metrics"][key].get("dominant_bpm")
            cue = row["paced_cue_rpm"]
            if pred is not None and cue is not None:
                errs.append(abs(pred - cue))
        paced_err[key] = {
            "median_abs_cue_error_bpm": float(np.median(errs)) if errs else None,
            "errors": errs,
        }

    payload = {
        "study_id": "M-N2_COMMON_REPRESENTATION_001",
        "exploratory_slice_s": EXPLORATORY_SLICE_S,
        "new_resp_band_hz": list(NEW_RESP_BAND_HZ),
        "historical_bpf_zscore_used": False,
        "historical_b_scaler_used": False,
        "locked_test_accessed": False,
        "new_model_heldout_accessed": False,
        "public_entry": "A2_NATIVE_UNWRAPPED_PHASE",
        "public_summary": public_summary,
        "public_rows": [
            {
                "recording_id": r["recording_id"],
                "subject_id": r["subject_id"],
                "ref_rr_bpm": r["ref_rr_bpm"],
                "label": r["safenest_label"],
                "R1_bpm": r["metrics"]["R1"].get("dominant_bpm"),
                "R2_bpm": r["metrics"]["R2"].get("dominant_bpm"),
                "R3_bpm": r["metrics"]["R3"].get("dominant_bpm"),
                "R1_band": r["metrics"]["R1"].get("band_fraction"),
                "R2_band": r["metrics"]["R2"].get("band_fraction"),
                "R3_band": r["metrics"]["R3"].get("band_fraction"),
                "median_dt": r["metrics"]["median_dt"],
                "notes": r["metrics"]["notes"],
            }
            for r in public_rows
        ],
        "mr60_occupied": pack_group(occupied),
        "mr60_empty": pack_group(empty),
        "mr60_paced_cue_diagnostic_only": paced_err,
        "mr60_rows": [
            {
                "session_id": r["session_id"],
                "role": r["role"],
                "paced_cue_rpm": r["paced_cue_rpm"],
                "primary_selection": r["primary_selection"],
                "median_dt": r["metrics"]["median_dt"],
                "n_full": r["metrics"]["n_full"],
                "dropped_stale": r["metrics"]["dropped_stale"],
                "raw_max_abs": r["metrics"]["raw_max_abs"],
                "R1": r["metrics"]["R1"],
                "R2": r["metrics"]["R2"],
                "R3": r["metrics"]["R3"],
                "notes": r["metrics"]["notes"],
            }
            for r in mr60_rows
        ],
    }
    out = OUT_DIR / "m_n2_summary.json"
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"wrote": str(out.relative_to(ROOT)), "public_summary": public_summary, "occupied": pack_group(occupied), "empty": pack_group(empty), "paced": paced_err}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
