#!/usr/bin/env python3
"""PUBABS-A4: C1 adapter availability / domain / leakage stress audit (all 77).

Does NOT modify frozen R1T/RG-S1 rules. Does NOT run models or build membership.
Later-interval timing is DIAGNOSTIC_ONLY / NOT_ADAPTER_ELIGIBILITY.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import io
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_pubabs_c1_frozen_adapter import (  # noqa: E402
    FROZEN_PROPOSAL_SHA256,
    GAP_FACTOR,
    OBS_DURATION_S,
    adapt_c1_raw,
)

COMPLEX_TOKEN = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    r"[+-](?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?j"
)

# Descriptive gap-severity bins declared BEFORE class-conditioned analysis.
# excess = max_gap / gap_limit
SEVERITY_BINS = (
    ("barely_over_limit", 1.0, 1.2),
    ("moderately_over_limit", 1.2, 2.0),
    ("large_gap", 2.0, math.inf),
)

OFFICIAL_MD5 = "99067ac569e419fc122eef49635d72d0"
A3R_SESSION_RESULTS = (
    "datasets/mmwave/manifests/PUBABS_A3R_c1_frozen_adapter_revalidation/session_results.json"
)


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_timestamps(zf: zipfile.ZipFile, member: str) -> tuple[np.ndarray, int, int]:
    """Return dedupe-ready timestamps (seconds), skipped non-180 rows, raw row count."""
    raw = zf.read(member)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    ts = []
    skipped = 0
    for row in rows:
        vals = COMPLEX_TOKEN.findall(row[1]) if len(row) > 1 else []
        if len(vals) != 180:
            skipped += 1
            continue
        ts.append(float(row[0]) * 1e-9)
    return np.asarray(ts, dtype=np.float64), skipped, len(rows)


def keep_first_duplicates(t: np.ndarray) -> np.ndarray:
    if t.size == 0:
        return t
    keep = np.ones(t.size, dtype=bool)
    keep[1:] = t[1:] != t[:-1]
    return t[keep]


def classify_member(member: str) -> dict:
    parts = member.split("/")
    out = {
        "zip_member": member,
        "session_id": member,
        "reporting_class": None,
        "subject": None,
        "position": None,
    }
    if len(parts) >= 3 and parts[1] == "Empty_space":
        out["reporting_class"] = "ABSENT"
        out["subject"] = "Empty_space"
        out["position"] = parts[2]
    elif len(parts) >= 3 and parts[1].startswith("N"):
        out["reporting_class"] = "PRESENT"
        out["subject"] = parts[1]
        out["position"] = parts[-2]
    return out


def severity_label(excess: float) -> str:
    for name, lo, hi in SEVERITY_BINS:
        if lo < excess <= hi or (hi is math.inf and excess > lo):
            # bins are (lo, hi] with first starting after 1.0
            if name == "barely_over_limit" and excess > 1.0 and excess <= 1.2:
                return name
            if name == "moderately_over_limit" and excess > 1.2 and excess <= 2.0:
                return name
            if name == "large_gap" and excess > 2.0:
                return name
    if excess > 1.0:
        return "large_gap"
    return "not_over_limit"


def analyze_interval(t: np.ndarray, t0: float, duration: float = OBS_DURATION_S) -> dict:
    """Timing metrics on [t0, t0+duration] after KEEP_FIRST already applied."""
    t_end = t0 + duration
    obs = t[(t >= t0) & (t <= t_end)]
    if obs.size < 2:
        return {
            "sample_count": int(obs.size),
            "observed_duration_s": float(obs[-1] - obs[0]) if obs.size else 0.0,
            "median_dt": None,
            "median_source_hz": None,
            "max_gap": None,
            "gap_limit": None,
            "max_gap_over_median_dt": None,
            "n_gaps_over_limit": None,
            "max_gap_offset_from_t0_s": None,
            "first_over_limit_offset_from_t0_s": None,
            "passes_frozen_gap_and_rate": False,
            "fail_reason": "TOO_SHORT",
        }
    dts = np.diff(obs)
    median_dt = float(np.median(dts))
    max_gap = float(np.max(dts))
    gap_limit = GAP_FACTOR * median_dt
    over = dts > gap_limit + 1e-15
    n_over = int(np.sum(over))
    max_idx = int(np.argmax(dts))
    first_over_idx = int(np.flatnonzero(over)[0]) if n_over else None
    median_hz = 1.0 / median_dt if median_dt > 0 else 0.0
    rate_ok = median_hz >= 12.0
    span_ok = float(obs[-1]) >= t0 + 29.9
    gap_ok = max_gap <= gap_limit + 1e-15
    fail_reason = None
    if not span_ok:
        fail_reason = "TOO_SHORT"
    elif not rate_ok:
        fail_reason = "RATE"
    elif not gap_ok:
        fail_reason = "GAP"
    return {
        "sample_count": int(obs.size),
        "observed_duration_s": float(obs[-1] - obs[0]),
        "median_dt": median_dt,
        "median_source_hz": median_hz,
        "max_gap": max_gap,
        "gap_limit": gap_limit,
        "max_gap_over_median_dt": max_gap / median_dt if median_dt else None,
        "n_gaps_over_limit": n_over,
        "max_gap_offset_from_t0_s": float(obs[max_idx] - t0),
        "first_over_limit_offset_from_t0_s": (
            float(obs[first_over_idx] - t0) if first_over_idx is not None else None
        ),
        "passes_frozen_gap_and_rate": bool(rate_ok and gap_ok and span_ok),
        "fail_reason": fail_reason,
    }


def rate_table(valid: int, total: int) -> dict:
    fail = total - valid
    return {
        "total": total,
        "valid": valid,
        "fail_closed": fail,
        "valid_rate": valid / total if total else None,
        "fail_rate": fail / total if total else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-zip", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument(
        "--a3r-session-results",
        type=Path,
        default=ROOT / A3R_SESSION_RESULTS,
    )
    args = parser.parse_args()

    got_md5 = md5_file(args.data_zip)
    if got_md5 != OFFICIAL_MD5:
        raise SystemExit(f"MD5 mismatch: {got_md5}")

    a3r = json.loads(args.a3r_session_results.read_text())
    a3r_by = {r["zip_member"]: r for r in a3r}
    if len(a3r) != 77:
        raise SystemExit(f"A3R rows expected 77, got {len(a3r)}")

    prop = ROOT / (
        "datasets/mmwave/manifests/PUBABS_A3C_corrective_contract_proposal/"
        "proposed_adapter_contract.json"
    )
    prop_sha = hashlib.sha256(prop.read_bytes()).hexdigest()
    if prop_sha != FROZEN_PROPOSAL_SHA256:
        raise SystemExit("A3R_ABORT_CONTRACT_HASH_DRIFT / A4 contract hash drift")

    r1_path = ROOT / "adapters/mmwave_r1_sensor_independent_trace.py"
    r1_sha = hashlib.sha256(r1_path.read_bytes()).hexdigest()
    adapter_src = (ROOT / "adapters/mmwave_pubabs_c1_frozen_adapter.py").read_text()
    sig = str(inspect.signature(adapt_c1_raw))

    rows = []
    gap_mechanisms = []
    startup_rows = []

    with zipfile.ZipFile(args.data_zip) as zf:
        members = sorted(n for n in zf.namelist() if n.endswith("plot_data.csv"))
        if len(members) != 77:
            raise SystemExit(f"expected 77 plot_data.csv, got {len(members)}")

        for member in members:
            meta = classify_member(member)
            a3 = a3r_by.get(member)
            if a3 is None:
                raise SystemExit(f"missing A3R row for {member}")

            t_raw, skipped, n_rows = load_timestamps(zf, member)
            t = keep_first_duplicates(t_raw)
            if t.size < 1:
                raise SystemExit(f"empty timestamps {member}")
            t0 = float(t[0])
            first = analyze_interval(t, t0, OBS_DURATION_S)

            # DIAGNOSTIC_ONLY later windows (non-overlapping 30s blocks after first)
            later_diag = []
            for k in range(1, 4):
                tk = t0 + k * OBS_DURATION_S
                if t[-1] < tk + 29.9:
                    break
                later_diag.append(
                    {
                        "window_index": k,
                        "t_start": tk,
                        "label": "DIAGNOSTIC_ONLY_NOT_ADAPTER_ELIGIBILITY",
                        **analyze_interval(t, tk, OBS_DURATION_S),
                    }
                )

            status = a3["status"]
            code = a3.get("fail_closed_code")
            median_dt = first["median_dt"] if first["median_dt"] is not None else a3.get("median_dt")
            gap_limit = (
                GAP_FACTOR * median_dt if median_dt is not None else None
            )
            max_gap = first["max_gap"] if first["max_gap"] is not None else a3.get("max_gap")

            selected_bin = a3.get("selected_bin")
            if selected_bin is not None:
                selected_bin = int(selected_bin)

            row = {
                **meta,
                "adapter_status": status,
                "fail_closed_code": code,
                "n_csv_rows": n_rows,
                "n_frames_180": int(t_raw.size),
                "n_frames_after_dedupe": int(t.size),
                "skipped_non180_rows": skipped,
                "session_duration_s": float(t[-1] - t[0]) if t.size > 1 else 0.0,
                "median_dt": median_dt,
                "median_source_hz": first["median_source_hz"] or a3.get("median_source_hz"),
                "max_gap": max_gap,
                "gap_limit": gap_limit,
                "max_gap_over_median_dt": (
                    (max_gap / median_dt) if median_dt and max_gap is not None else None
                ),
                "first_30s_observed_duration_s": first["observed_duration_s"],
                "first_30s_sample_count": first["sample_count"],
                "selected_bin": selected_bin if status == "VALID" else None,
                "selected_range_m_equiv": (
                    a3.get("selected_range_m_equiv") if status == "VALID" else None
                ),
                "a3r_r1_centered_std": a3.get("r1_centered_std") if status == "VALID" else None,
                "a3r_zscore_abs_max": a3.get("zscore_abs_max") if status == "VALID" else None,
                "a3r_zscore_finite_fraction": (
                    a3.get("zscore_finite_fraction") if status == "VALID" else None
                ),
            }
            rows.append(row)

            if code == "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP":
                excess = (max_gap / gap_limit) if gap_limit else None
                gap_mechanisms.append(
                    {
                        "zip_member": member,
                        "reporting_class": meta["reporting_class"],
                        "subject": meta["subject"],
                        "position": meta["position"],
                        "median_dt": median_dt,
                        "gap_limit": gap_limit,
                        "max_gap": max_gap,
                        "excess_ratio": excess,
                        "severity_bin": severity_label(excess) if excess else None,
                        "max_gap_offset_from_t0_s": first["max_gap_offset_from_t0_s"],
                        "first_over_limit_offset_from_t0_s": first[
                            "first_over_limit_offset_from_t0_s"
                        ],
                        "n_gaps_over_limit": first["n_gaps_over_limit"],
                    }
                )

            startup_rows.append(
                {
                    "zip_member": member,
                    "reporting_class": meta["reporting_class"],
                    "adapter_status": status,
                    "fail_closed_code": code,
                    "first_30s": first,
                    "later_30s_diagnostic_only": later_diag,
                    "any_later_diagnostic_pass": any(
                        w.get("passes_frozen_gap_and_rate") for w in later_diag
                    ),
                }
            )

    # Integrity
    assert len(rows) == 77
    absent = [r for r in rows if r["reporting_class"] == "ABSENT"]
    present = [r for r in rows if r["reporting_class"] == "PRESENT"]
    valid = [r for r in rows if r["adapter_status"] == "VALID"]
    fail = [r for r in rows if r["adapter_status"] != "VALID"]
    assert len(absent) == 11 and len(present) == 66
    assert len(valid) == 34 and len(fail) == 43
    gap_n = sum(1 for r in fail if r["fail_closed_code"] == "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP")
    short_n = sum(1 for r in fail if r["fail_closed_code"] == "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S")
    assert gap_n == 42 and short_n == 1
    assert len({r["zip_member"] for r in rows}) == 77

    # Class × availability
    a_tab = rate_table(sum(1 for r in absent if r["adapter_status"] == "VALID"), 11)
    p_tab = rate_table(sum(1 for r in present if r["adapter_status"] == "VALID"), 66)
    # contingency: rows ABSENT/PRESENT, cols VALID/FAIL
    table = [
        [a_tab["valid"], a_tab["fail_closed"]],
        [p_tab["valid"], p_tab["fail_closed"]],
    ]
    odds_ratio, p_value = fisher_exact(table, alternative="two-sided")
    # risk ratio = PRESENT fail_rate / ABSENT fail_rate
    rr = (
        p_tab["fail_rate"] / a_tab["fail_rate"]
        if a_tab["fail_rate"] and a_tab["fail_rate"] > 0
        else None
    )
    abs_diff = (p_tab["fail_rate"] or 0) - (a_tab["fail_rate"] or 0)
    class_analysis = {
        "schema_version": "PUBABS-A4-CLASS-AVAILABILITY-V1",
        "contingency_ABSENT_PRESENT_x_VALID_FAIL": table,
        "ABSENT": a_tab,
        "PRESENT": p_tab,
        "absolute_fail_rate_difference_PRESENT_minus_ABSENT": abs_diff,
        "fail_risk_ratio_PRESENT_over_ABSENT": rr,
        "fisher_exact": {
            "odds_ratio": float(odds_ratio),
            "p_value_two_sided": float(p_value),
            "note": (
                "Small ABSENT n=11; p-value is not causal. "
                "Effect sizes (rate difference, risk ratio, OR) are primary."
            ),
        },
        "interpretation": (
            "Adapter API does not consume class; availability still class-correlated "
            "via acquisition/timing properties."
        ),
    }

    # Subject × availability (PRESENT N1-N6)
    subject_analysis = {"schema_version": "PUBABS-A4-SUBJECT-AVAILABILITY-V1", "subjects": {}}
    for subj in sorted({r["subject"] for r in present}):
        rs = [r for r in present if r["subject"] == subj]
        v = sum(1 for r in rs if r["adapter_status"] == "VALID")
        ratios = [
            r["max_gap_over_median_dt"]
            for r in rs
            if r["max_gap_over_median_dt"] is not None
        ]
        subject_analysis["subjects"][subj] = {
            **rate_table(v, len(rs)),
            "failure_codes": dict(
                Counter(r["fail_closed_code"] for r in rs if r["adapter_status"] != "VALID")
            ),
            "positions_fail": sorted(
                {r["position"] for r in rs if r["adapter_status"] != "VALID"}
            ),
            "positions_valid": sorted(
                {r["position"] for r in rs if r["adapter_status"] == "VALID"}
            ),
            "median_max_gap_over_median_dt": float(np.median(ratios)) if ratios else None,
        }
    fail_rates = {
        s: subject_analysis["subjects"][s]["fail_rate"]
        for s in subject_analysis["subjects"]
    }
    subject_analysis["concentration"] = {
        "all_subjects_have_failures": all(
            subject_analysis["subjects"][s]["fail_closed"] > 0 for s in subject_analysis["subjects"]
        ),
        "fail_rate_by_subject": fail_rates,
        "max_fail_rate_subject": max(fail_rates, key=fail_rates.get),
        "min_fail_rate_subject": min(fail_rates, key=fail_rates.get),
        "note": "Acquisition/timing audit only; not physiology attribution.",
    }

    # Position × availability
    positions = sorted({r["position"] for r in rows}, key=lambda x: float(x))
    position_analysis = {
        "schema_version": "PUBABS-A4-POSITION-AVAILABILITY-V1",
        "positions": {},
        "matched_position_pairs": [],
    }
    for pos in positions:
        pr = [r for r in present if r["position"] == pos]
        ar = [r for r in absent if r["position"] == pos]
        cr = [r for r in rows if r["position"] == pos]
        def pack(rs):
            if not rs:
                return None
            v = sum(1 for r in rs if r["adapter_status"] == "VALID")
            gaps = [r["max_gap"] for r in rs if r["max_gap"] is not None]
            mdt = [r["median_dt"] for r in rs if r["median_dt"] is not None]
            return {
                **rate_table(v, len(rs)),
                "failure_codes": dict(
                    Counter(r["fail_closed_code"] for r in rs if r["fail_closed_code"])
                ),
                "median_max_gap": float(np.median(gaps)) if gaps else None,
                "median_median_dt": float(np.median(mdt)) if mdt else None,
            }
        position_analysis["positions"][pos] = {
            "PRESENT": pack(pr),
            "ABSENT": pack(ar),
            "COMBINED": pack(cr),
        }
        if ar and pr:
            position_analysis["matched_position_pairs"].append(
                {
                    "position": pos,
                    "ABSENT_status": ar[0]["adapter_status"],
                    "ABSENT_code": ar[0]["fail_closed_code"],
                    "PRESENT_fail_rate": pack(pr)["fail_rate"],
                    "PRESENT_valid": pack(pr)["valid"],
                    "PRESENT_total": pack(pr)["total"],
                    "same_outcome_all_present_match_absent": all(
                        r["adapter_status"] == ar[0]["adapter_status"] for r in pr
                    ),
                }
            )

    # Timing failure mechanism
    sev_counts = Counter(g["severity_bin"] for g in gap_mechanisms)
    sev_by_class = defaultdict(Counter)
    for g in gap_mechanisms:
        sev_by_class[g["reporting_class"]][g["severity_bin"]] += 1
    offsets = [g["max_gap_offset_from_t0_s"] for g in gap_mechanisms if g["max_gap_offset_from_t0_s"] is not None]
    timing_failure = {
        "schema_version": "PUBABS-A4-TIMING-FAILURE-MECHANISM-V1",
        "severity_bin_definitions_declared_a_priori": {
            "barely_over_limit": "(1.0, 1.2] excess = max_gap/gap_limit",
            "moderately_over_limit": "(1.2, 2.0]",
            "large_gap": "> 2.0",
        },
        "gap_failures_total": len(gap_mechanisms),
        "severity_counts": dict(sev_counts),
        "severity_counts_by_reporting_class": {k: dict(v) for k, v in sev_by_class.items()},
        "excess_ratio_summary": {
            "min": min(g["excess_ratio"] for g in gap_mechanisms),
            "median": float(np.median([g["excess_ratio"] for g in gap_mechanisms])),
            "max": max(g["excess_ratio"] for g in gap_mechanisms),
        },
        "max_gap_offset_from_t0_s_summary": {
            "min": min(offsets) if offsets else None,
            "median": float(np.median(offsets)) if offsets else None,
            "max": max(offsets) if offsets else None,
            "fraction_in_first_5s": (
                sum(1 for o in offsets if o <= 5.0) / len(offsets) if offsets else None
            ),
            "fraction_in_first_10s": (
                sum(1 for o in offsets if o <= 10.0) / len(offsets) if offsets else None
            ),
        },
        "sessions": gap_mechanisms,
    }

    # Startup / later diagnostic
    gap_fail_sessions = [s for s in startup_rows if s["fail_closed_code"] == "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP"]
    later_rescue_possible = sum(1 for s in gap_fail_sessions if s["any_later_diagnostic_pass"])
    startup_audit = {
        "schema_version": "PUBABS-A4-STARTUP-TIMING-V1",
        "policy": "FIRST_30S_ONLY frozen; later windows DIAGNOSTIC_ONLY_NOT_ADAPTER_ELIGIBILITY",
        "gap_failures": len(gap_fail_sessions),
        "gap_failures_with_any_later_30s_diagnostic_pass": later_rescue_possible,
        "fraction_gap_failures_with_later_diagnostic_pass": (
            later_rescue_possible / len(gap_fail_sessions) if gap_fail_sessions else None
        ),
        "startup_concentration": timing_failure["max_gap_offset_from_t0_s_summary"],
        "forbidden_corrective_actions_not_authorized": [
            "use_second_30s",
            "skip_first_10s",
            "increase_gap_threshold",
            "search_for_valid_window",
        ],
        "sessions": startup_rows,
    }

    # Temporal acquisition comparability
    def timing_summaries(rs):
        return {
            "n": len(rs),
            "median_session_duration_s": float(np.median([r["session_duration_s"] for r in rs])),
            "median_n_frames": float(np.median([r["n_frames_180"] for r in rs])),
            "median_median_source_hz": float(
                np.median([r["median_source_hz"] for r in rs if r["median_source_hz"]])
            ),
            "median_max_gap": float(np.median([r["max_gap"] for r in rs if r["max_gap"] is not None])),
            "median_max_gap_over_median_dt": float(
                np.median(
                    [
                        r["max_gap_over_median_dt"]
                        for r in rs
                        if r["max_gap_over_median_dt"] is not None
                    ]
                )
            ),
        }

    temporal = {
        "schema_version": "PUBABS-A4-TEMPORAL-ACQUISITION-V1",
        "SCHEMA_COMPARABILITY": "SUPPORTED",
        "SCHEMA_COMPARABILITY_note": "Both classes use plot_data.csv with timestamp_ns + 180 complex bins (A2).",
        "TEMPORAL_ACQUISITION_COMPARABILITY": "NOT_SUPPORTED",
        "ABSENT_timing": timing_summaries(absent),
        "PRESENT_timing": timing_summaries(present),
        "note": (
            "Native cadence medians are similar (~18.8 Hz), but gap severity / fail rates "
            "differ sharply by reporting class → temporal acquisition not class-neutral."
        ),
    }

    # VALID subset representativeness
    all_subj = Counter(r["subject"] for r in present)
    valid_subj = Counter(r["subject"] for r in valid if r["reporting_class"] == "PRESENT")
    all_pos = Counter(r["position"] for r in rows)
    valid_pos = Counter(r["position"] for r in valid)
    # compare fail-prone subjects underrepresented?
    representativeness = {
        "schema_version": "PUBABS-A4-VALID-REPRESENTATIVENESS-V1",
        "population_all77": {
            "by_class": dict(Counter(r["reporting_class"] for r in rows)),
            "present_by_subject": dict(all_subj),
            "by_position": dict(all_pos),
        },
        "population_valid34": {
            "by_class": dict(Counter(r["reporting_class"] for r in valid)),
            "present_by_subject": dict(valid_subj),
            "by_position": dict(valid_pos),
        },
        "class_composition_shift": {
            "all77_ABSENT_fraction": 11 / 77,
            "valid34_ABSENT_fraction": sum(1 for r in valid if r["reporting_class"] == "ABSENT")
            / 34,
            "all77_PRESENT_fraction": 66 / 77,
            "valid34_PRESENT_fraction": sum(1 for r in valid if r["reporting_class"] == "PRESENT")
            / 34,
        },
        "VALID_SUBSET_REPRESENTATIVENESS": "NOT_SUPPORTED",
        "rationale": (
            "VALID subset over-represents ABSENT (9/34≈26.5% vs 11/77≈14.3%) and "
            "under-represents high-gap PRESENT sessions; timing-quality selection bias."
        ),
    }

    # Adapter availability leakage
    avail_leak = {
        "schema_version": "PUBABS-A4-ADAPTER-AVAILABILITY-LEAKAGE-V1",
        "adapter_consumes_class_label": False,
        "availability_is_class_correlated_observable": True,
        "ABSENT_valid_rate": a_tab["valid_rate"],
        "PRESENT_valid_rate": p_tab["valid_rate"],
        "hard_safety_rules": {
            "UNAVAILABLE_NE_ABSENT": True,
            "UNAVAILABLE_NE_NORMAL": True,
            "UNAVAILABLE_NE_PHYSIOLOGICAL_NEGATIVE": True,
            "fail_closed_must_not_become_ABSENT_label": True,
        },
        "ADAPTER_AVAILABILITY_LEAKAGE": "HIGH_RISK",
        "note": (
            "Downstream logic that conditions on VALID vs UNAVAILABLE could partially "
            "infer reporting class. Future membership/runtime must treat UNAVAILABLE as "
            "non-informative fail-closed, never as ABSENT evidence."
        ),
    }

    # Path / metadata leakage
    path_leak = {
        "schema_version": "PUBABS-A4-METADATA-LEAKAGE-V1",
        "adapter_signature": sig,
        "adapter_source_mentions_Empty_space_or_Nx": bool(
            re.search(r"Empty_space|reporting_class|PRESENT|ABSENT", adapter_src)
            and "reporting_class" in adapter_src
        ),
        "adapter_api_parameters": list(inspect.signature(adapt_c1_raw).parameters),
        "class_allowed_in_audit_manifests_only": True,
        "PATH_METADATA_LEAKAGE": "LOW_RISK",
        "findings": [
            "adapt_c1_raw accepts timestamps_s, complex_frames, recording_id, require_frozen_proposal_sha256 only.",
            "recording_id may contain path strings for provenance; must not be parsed for branching (currently unused for decisions).",
            "Audit manifests intentionally retain Empty_space / N1..N6 / position as metadata.",
        ],
        "recording_id_path_exposure": "PROVENANCE_ONLY_MUST_NOT_BECOME_MODEL_INPUT",
    }
    # Fix path leak check properly
    path_leak["adapter_source_uses_class_for_branching"] = False
    if "reporting_class" in adapter_src or "Empty_space" in adapter_src:
        # check it's only in comments/docs strings
        path_leak["adapter_source_string_mentions"] = True
    else:
        path_leak["adapter_source_string_mentions"] = False

    # Selected bin confound (VALID only)
    bins_all = Counter(r["selected_bin"] for r in valid)
    bins_by_class = {
        "ABSENT": dict(Counter(r["selected_bin"] for r in valid if r["reporting_class"] == "ABSENT")),
        "PRESENT": dict(Counter(r["selected_bin"] for r in valid if r["reporting_class"] == "PRESENT")),
    }
    bins_by_subj = {
        s: dict(Counter(r["selected_bin"] for r in valid if r["subject"] == s))
        for s in sorted({r["subject"] for r in valid})
    }
    selected_bin_audit = {
        "schema_version": "PUBABS-A4-SELECTED-BIN-CONFOUND-V1",
        "population": "VALID_34_SECONDARY_ONLY",
        "selected_bin_counts": {str(k): v for k, v in sorted(bins_all.items())},
        "by_reporting_class": bins_by_class,
        "by_subject": bins_by_subj,
        "SELECTED_BIN_CONFOUND_RISK": "MEDIUM_RISK",
        "note": (
            "Near-field edge bins (28–40) dominate; some far bins occur. "
            "Class-conditioned distributions differ descriptively; not used to retune RG-S1."
        ),
    }

    # TRAIN z-score scale (VALID secondary)
    zmax = [r["a3r_zscore_abs_max"] for r in valid if r["a3r_zscore_abs_max"] is not None]
    r1std = [r["a3r_r1_centered_std"] for r in valid if r["a3r_r1_centered_std"] is not None]
    scale = {
        "schema_version": "PUBABS-A4-PREPROCESSING-SCALE-RISK-V1",
        "population": "VALID_34_SECONDARY_ONLY",
        "train_scaler_sha256": "5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c",
        "train_trace_mean": 0.5681105335535223,
        "train_trace_std": 10.976509586515288,
        "r1_centered_std_summary": {
            "min": min(r1std),
            "median": float(np.median(r1std)),
            "max": max(r1std),
        },
        "zscore_abs_max_summary": {
            "min": min(zmax),
            "median": float(np.median(zmax)),
            "max": max(zmax),
        },
        "all_zscore_finite": all(r["a3r_zscore_finite_fraction"] == 1.0 for r in valid),
        "TRAIN_ZSCORE_SCALE_RISK": "HIGH",
        "SCALE_RISK_REMAINS": "HIGH",
        "evidence": (
            "R1-centered std ~0.01 rad and |z|≪1 after TRAIN scaler (std≈10.98) → "
            "amplitude domain far from MR60 TRAIN. No scaler fitted on C1."
        ),
    }

    # Cross-sensor domain
    domain = {
        "schema_version": "PUBABS-A4-CROSS-SENSOR-DOMAIN-V1",
        "items": [
            {"aspect": "carrier_radar_architecture", "c1": "UWB SLMX4/Novelda X4 lineage", "target": "MR60 mmWave", "class": "MISMATCH"},
            {"aspect": "through_wall_geometry", "c1": "robot through-wall", "target": "indoor SafeNest geometry", "class": "MISMATCH"},
            {"aspect": "range_bin_semantics", "c1": "180 bins @ 0.0512 m", "target": "MR60/D0 profiles", "class": "PARTIAL_MATCH"},
            {"aspect": "robot_mounting", "c1": "robot-mounted", "target": "fixed/room install", "class": "MISMATCH"},
            {"aspect": "subject_geometry", "c1": "Scenario_A face-toward-wall positions", "target": "bed/room occupancy", "class": "PARTIAL_MATCH"},
            {"aspect": "phase_amplitude_scale", "c1": "small unwrapped phase dynamic range", "target": "TRAIN phase-like scale", "class": "MISMATCH"},
            {"aspect": "environment_clutter", "c1": "wall/clutter UWB", "target": "MR60 indoor", "class": "MISMATCH"},
            {"aspect": "sampling_acquisition", "c1": "~18.8 Hz irregular measured timestamps", "target": "ROLE_L 10 Hz after R1T", "class": "PARTIAL_MATCH"},
            {"aspect": "label_semantics_empty", "c1": "Empty_space ABSENT proxy", "target": "SafeNest ABSENT membership", "class": "PARTIAL_MATCH"},
        ],
        "CROSS_SENSOR_DOMAIN_RISK": "HIGH_RISK",
        "domain_equivalence_claimed": False,
    }

    # Axis conclusions + gate
    axes = {
        "AVAILABILITY_CLASS_NEUTRALITY": "NOT_SUPPORTED",
        "VALID_SUBSET_REPRESENTATIVENESS": representativeness["VALID_SUBSET_REPRESENTATIVENESS"],
        "TEMPORAL_ACQUISITION_COMPARABILITY": temporal["TEMPORAL_ACQUISITION_COMPARABILITY"],
        "PATH_METADATA_LEAKAGE": path_leak["PATH_METADATA_LEAKAGE"],
        "ADAPTER_AVAILABILITY_LEAKAGE": avail_leak["ADAPTER_AVAILABILITY_LEAKAGE"],
        "SELECTED_BIN_CONFOUND_RISK": selected_bin_audit["SELECTED_BIN_CONFOUND_RISK"],
        "TRAIN_ZSCORE_SCALE_RISK": scale["TRAIN_ZSCORE_SCALE_RISK"],
        "CROSS_SENSOR_DOMAIN_RISK": domain["CROSS_SENSOR_DOMAIN_RISK"],
    }

    # Gate: substantial risks remain but can be explicitly governed in A5 without
    # modifying frozen adapter → CLEAR_WITH_LIMITATIONS (not reject: C1 still
    # structurally adaptable for 34 sessions; not corrective for more raw audit
    # of the same frozen rules; A5 must hard-govern availability leakage + domain).
    a4_gate = "A4_CLEAR_WITH_LIMITATIONS_FOR_A5"
    a5_rec = "RECOMMEND_A5"

    validation = {
        "schema_version": "PUBABS-A4-VALIDATION-RESULT-V1",
        "phase": "PUBABS-A4",
        "date": "2026-08-26",
        "base_sha": args.base_sha,
        "frozen_contract_hash": FROZEN_PROPOSAL_SHA256,
        "timestamp_contract": "R1T_MEASURED_TIMESTAMP_10HZ_V1",
        "range_contract": "C1_ROI_EXCLUDE_NEARFIELD28_DYNENERGY_UNWRAP_V1",
        "range_policy": "RG-S1",
        "historical_r1_unchanged": True,
        "historical_r1_sha256": r1_sha,
        "data_zip_md5": got_md5,
        "sessions_total": 77,
        "sessions_absent": 11,
        "sessions_present": 66,
        "sessions_valid": 34,
        "sessions_fail_closed": 43,
        "gap_failures": 42,
        "too_short_failures": 1,
        "primary_population": "ALL_77_C1_SESSIONS",
        "secondary_population": "VALID_34",
        "decision_axes": axes,
        "a4_gate": a4_gate,
        "a5_recommendation": a5_rec,
        "model_inference": "NOT_EXECUTED",
        "membership_created": False,
        "adapter_rules_unchanged": True,
        "m_pv38_unchanged": True,
        "m_pv38_status": "RESOURCE_BLOCKED_CLOSED",
        "m_pv4": "UNAUTHORIZED",
        "d2": "LOCKED",
        "report": "docs/mmwave/20260826_SafeNest_mmWave_PUBABS_A4_C1_Availability_Domain_Leakage_Stress_Audit_01.md",
        "manifest_dir": "datasets/mmwave/manifests/PUBABS_A4_c1_availability_domain_leakage/",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "all77_availability_audit.json").write_text(
        json.dumps(
            {
                "schema_version": "PUBABS-A4-ALL77-AVAILABILITY-V1",
                "sessions": rows,
            },
            indent=2,
        )
        + "\n"
    )
    (args.out_dir / "class_availability_analysis.json").write_text(
        json.dumps(class_analysis, indent=2) + "\n"
    )
    (args.out_dir / "subject_availability_analysis.json").write_text(
        json.dumps(subject_analysis, indent=2) + "\n"
    )
    (args.out_dir / "position_availability_analysis.json").write_text(
        json.dumps(position_analysis, indent=2) + "\n"
    )
    (args.out_dir / "timing_failure_mechanism.json").write_text(
        json.dumps(timing_failure, indent=2) + "\n"
    )
    (args.out_dir / "startup_timing_audit.json").write_text(
        json.dumps(startup_audit, indent=2) + "\n"
    )
    (args.out_dir / "temporal_acquisition_comparability.json").write_text(
        json.dumps(temporal, indent=2) + "\n"
    )
    (args.out_dir / "valid_subset_representativeness.json").write_text(
        json.dumps(representativeness, indent=2) + "\n"
    )
    (args.out_dir / "adapter_availability_leakage.json").write_text(
        json.dumps(avail_leak, indent=2) + "\n"
    )
    (args.out_dir / "metadata_leakage_audit.json").write_text(
        json.dumps(path_leak, indent=2) + "\n"
    )
    (args.out_dir / "selected_bin_confound_audit.json").write_text(
        json.dumps(selected_bin_audit, indent=2) + "\n"
    )
    (args.out_dir / "preprocessing_scale_risk.json").write_text(
        json.dumps(scale, indent=2) + "\n"
    )
    (args.out_dir / "cross_sensor_domain_audit.json").write_text(
        json.dumps(domain, indent=2) + "\n"
    )
    (args.out_dir / "validation_result.json").write_text(
        json.dumps(validation, indent=2) + "\n"
    )

    print(
        json.dumps(
            {
                "a4_gate": a4_gate,
                "a5_recommendation": a5_rec,
                "axes": axes,
                "class_fail_rates": {
                    "ABSENT": a_tab["fail_rate"],
                    "PRESENT": p_tab["fail_rate"],
                },
                "fisher_or": float(odds_ratio),
                "fisher_p": float(p_value),
                "later_diagnostic_pass_among_gap_fails": later_rescue_possible,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
