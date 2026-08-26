#!/usr/bin/env python3
"""Run frozen C1 adapter over all Data.zip plot_data.csv sessions (PUBABS-A3R)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_pubabs_c1_frozen_adapter import (
    FROZEN_PROPOSAL_SHA256,
    C1AdapterError,
    adapt_c1_raw,
)

COMPLEX_TOKEN = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    r"[+-](?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?j"
)


def load_member(zf: zipfile.ZipFile, member: str):
    raw = zf.read(member)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    ts = []
    frames = []
    skipped = 0
    for row in rows:
        vals = [complex(tok) for tok in COMPLEX_TOKEN.findall(row[1])]
        if len(vals) != 180:
            skipped += 1
            continue
        ts.append(float(row[0]) * 1e-9)
        frames.append(vals)
    return np.asarray(ts, dtype=np.float64), np.asarray(frames, dtype=np.complex128), skipped


def classify_member(member: str) -> dict:
    parts = member.split("/")
    out = {"zip_member": member, "reporting_class": None, "subject": None, "position": None}
    if len(parts) >= 3 and parts[1] == "Empty_space":
        out["reporting_class"] = "ABSENT"
        out["subject"] = "Empty_space"
        out["position"] = parts[2]
    elif len(parts) >= 3 and parts[1].startswith("N"):
        out["reporting_class"] = "PRESENT"
        out["subject"] = parts[1]
        out["position"] = parts[-2]
    return out


def process_once(data_zip: Path) -> list[dict]:
    results = []
    with zipfile.ZipFile(data_zip) as zf:
        members = sorted(n for n in zf.namelist() if n.endswith("plot_data.csv"))
        for member in members:
            meta = classify_member(member)
            try:
                t, z, skipped = load_member(zf, member)
                # Adapter must ignore reporting class: only pass raw arrays.
                out = adapt_c1_raw(t, z, recording_id=member)
                hashes = out.output_hashes()
                results.append(
                    {
                        **meta,
                        "status": "VALID",
                        "fail_closed_code": None,
                        "skipped_non180_rows": skipped,
                        "n_frames": int(t.size),
                        "selected_bin": out.selected_bin,
                        "selected_range_m_equiv": out.selected_range_m_equiv,
                        "median_dt": out.median_dt,
                        "median_source_hz": out.median_source_hz,
                        "max_gap": out.max_gap,
                        "t0": out.t0,
                        "r1_output_len": int(out.r1_centered.size),
                        "r1t_finite_fraction": float(np.isfinite(out.r1t_10hz).mean()),
                        "r1_centered_finite_fraction": float(np.isfinite(out.r1_centered).mean()),
                        "zscore_finite_fraction": float(np.isfinite(out.train_zscore_trace).mean()),
                        "r1_centered_median": float(np.median(out.r1_centered)),
                        "r1_centered_std": float(np.std(out.r1_centered)),
                        "zscore_abs_max": float(np.max(np.abs(out.train_zscore_trace))),
                        "r1_profile_id": out.r1_metadata.get("profile_id"),
                        "r1_resampling_method": (
                            (out.r1_metadata.get("resampling_metadata") or {}).get(
                                "resampling_method"
                            )
                        ),
                        "r1_resampling_performed": (
                            (out.r1_metadata.get("resampling_metadata") or {}).get(
                                "resampling_performed"
                            )
                        ),
                        **hashes,
                    }
                )
            except C1AdapterError as exc:
                results.append(
                    {
                        **meta,
                        "status": "FAIL_CLOSED",
                        "fail_closed_code": exc.code,
                        "fail_closed_detail": exc.detail,
                    }
                )
            except Exception as exc:  # noqa: BLE001 — inventory must not abort mid-run
                results.append(
                    {
                        **meta,
                        "status": "FAIL_CLOSED",
                        "fail_closed_code": "UNEXPECTED_EXCEPTION",
                        "fail_closed_detail": f"{type(exc).__name__}: {exc}",
                    }
                )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-zip", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--official-md5", default="99067ac569e419fc122eef49635d72d0")
    args = parser.parse_args()

    md5 = hashlib.md5()
    with args.data_zip.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            md5.update(chunk)
    got = md5.hexdigest()
    if got != args.official_md5:
        raise SystemExit(f"MD5 mismatch: {got}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    run1 = process_once(args.data_zip)
    run2 = process_once(args.data_zip)

    def canon(rows):
        return [
            {
                k: r.get(k)
                for k in (
                    "zip_member",
                    "status",
                    "fail_closed_code",
                    "selected_bin",
                    "r1t_10hz_sha256",
                    "r1_centered_sha256",
                    "train_zscore_trace_sha256",
                )
            }
            for r in rows
        ]

    determinism_ok = canon(run1) == canon(run2)
    (args.out_dir / "session_results_run1.json").write_text(json.dumps(run1, indent=2) + "\n")
    (args.out_dir / "session_results_run2.json").write_text(json.dumps(run2, indent=2) + "\n")
    summary = {
        "frozen_proposal_sha256": FROZEN_PROPOSAL_SHA256,
        "data_zip_md5": got,
        "sessions_total": len(run1),
        "sessions_valid": sum(1 for r in run1 if r["status"] == "VALID"),
        "sessions_fail_closed": sum(1 for r in run1 if r["status"] != "VALID"),
        "empty_total": sum(1 for r in run1 if r.get("reporting_class") == "ABSENT"),
        "present_total": sum(1 for r in run1 if r.get("reporting_class") == "PRESENT"),
        "determinism_ok": determinism_ok,
        "fail_closed_codes": sorted(
            {
                r["fail_closed_code"]
                for r in run1
                if r.get("fail_closed_code")
            }
        ),
    }
    (args.out_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
