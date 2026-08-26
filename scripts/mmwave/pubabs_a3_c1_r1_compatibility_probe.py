#!/usr/bin/env python3
"""PUBABS-A3 C1↔R1 compatibility probe (evidence only; not a canonical adapter).

Demonstrates that frozen R1 cannot ingest C1 measured timestamps / ~18.8 Hz
irregular grids, without using class labels or loading ROLE_L models.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np

from adapters.mmwave_r1_sensor_independent_trace import (
    NativeTraceInput,
    R1TraceError,
    adapt_native_trace,
)

COMPLEX_TOKEN = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    r"[+-](?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?j"
)
RANGE_SPACING_M = 0.0512  # SciData / extended-lineage documentation


DEFAULT_MEMBERS = [
    "Data/Empty_space/0/plot_data.csv",
    "Data/Empty_space/-5/plot_data.csv",
    "Data/Empty_space/5/plot_data.csv",
    "Data/N1/Scenario_A/1_Meter/Face_toward_wall/0/plot_data.csv",
    "Data/N2/Scenario_A/1_Meter/Face_toward_wall/-3/plot_data.csv",
    "Data/N3/Scenario_A/1_Meter/Face_toward_wall/2/plot_data.csv",
    "Data/N6/Scenario_A/1_Meter/Face_toward_wall/5/plot_data.csv",
]


def load_complex_csv(zf: zipfile.ZipFile, member: str, expect_bins: int = 180):
    raw = zf.read(member)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    ts = []
    frames = []
    skipped = 0
    for row in rows:
        vals = [complex(tok) for tok in COMPLEX_TOKEN.findall(row[1])]
        if len(vals) != expect_bins:
            skipped += 1
            continue
        ts.append(float(row[0]) * 1e-9)
        frames.append(vals)
    x = np.asarray(frames, dtype=np.complex128)
    t = np.asarray(ts, dtype=np.float64)
    t = t - t[0]
    return t, x, skipped


def dynamic_energy_bin(x: np.ndarray, rmin: float = 0.5, rmax: float = 4.0) -> tuple[int, float]:
    """Label-independent PROFILE_001-like probe (NOT a frozen C1 registration)."""
    n_bins = x.shape[1]
    ranges = np.arange(n_bins) * RANGE_SPACING_M
    mask = (ranges >= rmin) & (ranges <= rmax)
    static = x.mean(axis=0)
    energy = np.mean(np.abs(x - static) ** 2, axis=0)
    local = energy.copy()
    local[~mask] = -np.inf
    idx = int(np.argmax(local))
    return idx, float(ranges[idx])


def probe_member(zf: zipfile.ZipFile, member: str) -> dict:
    t, x, skipped = load_complex_csv(zf, member)
    med = float(np.median(np.diff(t)))
    hz = 1.0 / med
    bidx, rm = dynamic_energy_bin(x)
    phase = np.unwrap(np.angle(x[:, bidx]))

    def r1_attempt(rate: float, trace=None, time_s=None, note: str = "") -> str:
        native = NativeTraceInput(
            source_id="C1",
            dataset_id="zenodo_15032859",
            subject_id="probe",
            recording_id=member,
            condition="FEASIBILITY_ONLY",
            trace=phase if trace is None else trace,
            time_s=t if time_s is None else time_s,
            sampling_rate_hz=rate,
            native_trace_semantics="UNWRAPPED_PHASE_RAD_FROM_COMPLEX_RANGE_BIN",
            native_trace_unit="radian",
            source_scale_metadata={"selected_bin_probe_only": bidx},
            provenance={"member": member, "note": note, "skipped_rows": skipped},
        )
        try:
            out = adapt_native_trace(native)
            return f"ACCEPT:len={int(out.trace.size)}"
        except R1TraceError as exc:
            return exc.code

    # Non-canonical linear probe (explicitly not frozen-path).
    t10 = np.arange(0.0, float(t[-1]), 0.1, dtype=np.float64)
    if t10.size >= 300:
        ph10 = np.interp(t10, t, phase)
        noncanonical = r1_attempt(
            10.0, trace=ph10, time_s=t10, note="NONCANONICAL_LINEAR_INTERP_PROBE"
        )
    else:
        noncanonical = "TOO_SHORT"

    return {
        "member": member,
        "skipped_rows": skipped,
        "n_frames": int(x.shape[0]),
        "measured_hz": hz,
        "duration_s": float(t[-1] - t[0]),
        "selected_bin_probe_only": bidx,
        "selected_range_m_probe_only": rm,
        "phase_finite_fraction": float(np.isfinite(phase).mean()),
        "phase_std": float(np.std(phase)),
        "r1_measured_rate": r1_attempt(hz, note="measured_median_hz"),
        "r1_integer_19hz": r1_attempt(19.0, note="rounded_19hz"),
        "r1_after_noncanonical_linear_10hz": noncanonical,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-zip", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--members", nargs="*", default=DEFAULT_MEMBERS)
    args = parser.parse_args()

    results = []
    with zipfile.ZipFile(args.data_zip) as zf:
        for member in args.members:
            results.append(probe_member(zf, member))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"sessions": len(results), "out": str(args.out_json)}))


if __name__ == "__main__":
    main()
