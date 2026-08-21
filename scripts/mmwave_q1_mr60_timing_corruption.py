#!/usr/bin/env python3
"""Q1: freeze an MR60-like cadence/jitter/republication synthetic corruption profile.

Uses Team MR60 ESP JSONL blobs already inventoried in M-N0. Timing/path statistics
only. Does not train, does not use MR60 labels, does not read D2, and does not
select Q2 abstention thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    PROFILE_ID,
    SEVERITY_LEVELS,
    SUPPORTED_MODES,
    TRANSPORT_DUPLICATE_MODE,
    TRANSPORT_DUPLICATE_STATUS,
    apply_timing_corruption,
)

PHASE_ID = "Q1"
SCHEMA_VERSION = "Q1.1"
AUDIT_DATE = "2026-08-22"
BASE_SHA = "e74e54736d5cde1773d530b8398a630486270785"
MPV0_COMMIT = "18e4a4e86d6bf95795d6749a91ce303ad3f1c417"
UPDATE_ADVANCE_TOLERANCE_MS = 8.0
NOMINAL_RECEIVE_INTERVAL_MS = 100.0
SYNTHETIC_MIN_INTERVAL_MS = 44.0

MN0_DOC = ROOT / "docs/mmwave/20260817_SafeNest_mmWave_M-N0_Team_MR60_Physical_Inventory_01.md"
MN4_CONTRACT = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"
MN7_RESULT = ROOT / "datasets/mmwave/manifests/m_n7_device_domain_result.json"
MPV0_POLICY = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/role_lock_policy.json"
MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption"

MANIFEST_JSON_FILES = (
    "evidence_inventory.json",
    "timing_statistics.json",
    "repeat_event_audit.json",
    "synthetic_corruption_profile.json",
    "exception_registry.json",
)

ABSOLUTE_PATH_RE = re.compile(
    r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)"
)
FORBIDDEN_PHYSIO_KEYS = (
    "breath_phase_values",
    "breath_phase_histogram",
    "amplitude_distribution",
    "rr_target",
    "apnea_labels",
)


class Q1AccountingError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dump_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def r6(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(f"{value:.6f}")


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (p / 100.0)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[int(rank)])
    weight = rank - lo
    return float(ordered[lo] * (1.0 - weight) + ordered[hi] * weight)


def summarize(values: list[float] | np.ndarray) -> dict[str, Any] | None:
    seq = [float(v) for v in values if math.isfinite(float(v))]
    if not seq:
        return None
    mean = sum(seq) / len(seq)
    var = sum((v - mean) ** 2 for v in seq) / len(seq)
    med = percentile(seq, 50)
    mad = percentile([abs(v - med) for v in seq], 50) if med is not None else None
    return {
        "n": len(seq),
        "min": r6(min(seq)),
        "max": r6(max(seq)),
        "mean": r6(mean),
        "std": r6(math.sqrt(var)),
        "median": r6(med),
        "mad": r6(mad),
        "p01": r6(percentile(seq, 1)),
        "p05": r6(percentile(seq, 5)),
        "p25": r6(percentile(seq, 25)),
        "p50": r6(med),
        "p75": r6(percentile(seq, 75)),
        "p95": r6(percentile(seq, 95)),
        "p99": r6(percentile(seq, 99)),
    }


def git_cat_blob(sha: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "-p", sha], cwd=ROOT)


def blob_exists(sha: str) -> bool:
    try:
        subprocess.check_output(
            ["git", "cat-file", "-t", sha],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def load_m_n0() -> dict[str, Any]:
    text = MN0_DOC.read_text(encoding="utf-8")
    start = text.index("```json\n") + len("```json\n")
    end = text.index("\n```", start)
    return json.loads(text[start:end])


def parse_jsonl_bytes(raw: bytes) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    failures = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            failures += 1
    return rows, failures


def q2_handoff_reason(rec: dict[str, Any]) -> str | None:
    """Observation filter used only to keep freeze-like sessions out of TYPICAL pooling.

    This is not an INPUT_UNAVAILABLE or rejection threshold.
    """
    if rec.get("receive_median_ms") == 0:
        return "RECEIVE_MEDIAN_ZERO_MS"
    if int(rec.get("receive_zero_dt_count") or 0) > 10:
        return "RECEIVE_TIMESTAMP_COLLISION_CLUSTER"
    if int(rec.get("max_republication_run") or 0) >= 50:
        return "LONG_SOURCE_REPUBLICATION_RUN"
    src_max = rec.get("source_interval_max_ms")
    if src_max is not None and float(src_max) >= 400.0:
        return "SOURCE_INTERVAL_AT_LEAST_400MS"
    return None


def analyze_session(spec: dict[str, Any]) -> dict[str, Any]:
    session_id = spec["session_id"]
    sha = spec.get("git_blob_sha_at_raw_index")
    family = spec.get("evidence_family")
    inventory = {
        "session_id": session_id,
        "evidence_family": family,
        "artifact_class": spec.get("artifact_class"),
        "inventory_current_path": spec.get("current_path"),
        "inventory_historical_path": spec.get("historical_path"),
        "git_blob_sha": sha,
        "intended_condition": spec.get("intended_condition"),
        "date": spec.get("date"),
        "m_n0_phase_age_ms_available": spec.get("phase_age_ms_available"),
        "physical_or_synthetic": "PHYSICAL_ESP_JSONL",
        "role": "EMPIRICAL_TIMING_CANDIDATE",
    }
    if not sha:
        return {
            **inventory,
            "q1_status": "EXCLUDED",
            "exclusion_reason": "NO_GIT_BLOB_IN_MN0_INVENTORY",
        }
    if not blob_exists(sha):
        return {
            **inventory,
            "q1_status": "EXCLUDED",
            "exclusion_reason": "GIT_BLOB_NOT_IN_STANDALONE_REPO",
        }
    rows, parse_failures = parse_jsonl_bytes(git_cat_blob(sha))
    if len(rows) < 3:
        return {
            **inventory,
            "q1_status": "EXCLUDED",
            "exclusion_reason": "TOO_FEW_PARSEABLE_ROWS",
            "parse_failures": parse_failures,
            "packet_count": len(rows),
        }

    first = rows[0]
    schema = first.get("schema_version")
    firmware = first.get("firmware_version")
    ts: list[float] = []
    age: list[float | None] = []
    seq: list[Any] = []
    uart: list[Any] = []
    phase: list[Any] = []
    for row in rows:
        if row.get("ts_monotonic_ms") is None:
            continue
        ts.append(float(row["ts_monotonic_ms"]))
        raw_age = row.get("phase_age_ms")
        age.append(None if raw_age is None else float(raw_age))
        seq.append(row.get("seq"))
        uart.append(row.get("uart_frames_total"))
        phase.append(row.get("breath_phase"))
    if len(ts) < 3:
        return {
            **inventory,
            "q1_status": "EXCLUDED",
            "exclusion_reason": "TOO_FEW_TS_MONOTONIC_ROWS",
            "parse_failures": parse_failures,
        }

    recv_dt = [ts[i] - ts[i - 1] for i in range(1, len(ts))]
    missing_age = sum(value is None for value in age)
    exact_transport = 0
    seq_repeat_extra = 0
    seq_counts: Counter[Any] = Counter(value for value in seq if value is not None)
    seq_repeat_extra = int(sum(count - 1 for count in seq_counts.values() if count > 1))
    for i in range(1, len(ts)):
        if seq[i] is not None and seq[i] == seq[i - 1] and ts[i] == ts[i - 1]:
            exact_transport += 1

    republications = 0
    max_run = 0
    run = 0
    run_lengths: list[int] = []
    source_dt: list[float] = []
    plateau = 0
    accepted = 0
    last_accepted = None
    last_source = None
    last_phase = None
    seq_inc_repub = 0
    seq_same_repub = 0
    uart_inc_repub = 0
    uart_same_repub = 0
    if missing_age == 0:
        for i, t_row in enumerate(ts):
            t_upd = t_row - float(age[i])
            is_repub = last_accepted is not None and t_upd <= last_accepted + UPDATE_ADVANCE_TOLERANCE_MS
            if is_repub:
                republications += 1
                run += 1
                max_run = max(max_run, run)
                if i and seq[i] is not None and seq[i - 1] is not None:
                    if seq[i] == seq[i - 1]:
                        seq_same_repub += 1
                    elif seq[i] == seq[i - 1] + 1:
                        seq_inc_repub += 1
                if i and uart[i] is not None and uart[i - 1] is not None:
                    if uart[i] == uart[i - 1]:
                        uart_same_repub += 1
                    elif uart[i] > uart[i - 1]:
                        uart_inc_repub += 1
                continue
            if run:
                run_lengths.append(run)
                run = 0
            if last_source is not None:
                source_dt.append(t_upd - last_source)
            if last_phase is not None and phase[i] == last_phase:
                plateau += 1
            last_source = t_upd
            last_accepted = t_upd
            last_phase = phase[i]
            accepted += 1
        if run:
            run_lengths.append(run)

    rec = {
        **inventory,
        "physical_or_synthetic": "PHYSICAL_ESP_JSONL",
        "replay_status": "NOT_A_REPLAY_FILE",
        "packet_count": len(ts),
        "parse_failures": parse_failures,
        "schema_version": schema,
        "firmware_version": firmware,
        "source_timestamp_field": "phase_update_estimate_ms=ts_monotonic_ms-phase_age_ms",
        "receive_timestamp_field": "ts_monotonic_ms",
        "pi_capture_timestamp": "ABSENT",
        "sequence_field": "seq",
        "phase_age_field": "phase_age_ms" if missing_age == 0 else "ABSENT_OR_INCOMPLETE",
        "source_timestamp_available": missing_age == 0,
        "receive_timestamp_available": True,
        "sequence_available": all(value is not None for value in seq),
        "phase_age_available": missing_age == 0,
        "receive_intervals_ms": recv_dt,
        "source_intervals_ms": source_dt,
        "receive_median_ms": r6(percentile(recv_dt, 50)),
        "source_median_ms": r6(percentile(source_dt, 50)) if source_dt else None,
        "source_interval_max_ms": r6(max(source_dt)) if source_dt else None,
        "receive_min_ms": r6(min(recv_dt)),
        "receive_max_ms": r6(max(recv_dt)),
        "receive_zero_dt_count": int(sum(dt == 0 for dt in recv_dt)),
        "receive_dt_gt_400_count": int(sum(dt > 400 for dt in recv_dt)),
        "exact_transport_duplicate_count": exact_transport,
        "seq_repeat_extra_count": seq_repeat_extra,
        "confirmed_source_republication_count": republications,
        "source_republication_fraction": r6(republications / len(ts)) if missing_age == 0 else None,
        "max_republication_run": max_run if missing_age == 0 else None,
        "republication_run_lengths": run_lengths,
        "numeric_plateau_accepted_count": plateau if missing_age == 0 else None,
        "accepted_source_event_count": accepted if missing_age == 0 else None,
        "seq_increment_during_republication": seq_inc_repub,
        "seq_unchanged_during_republication": seq_same_repub,
        "uart_increment_during_republication": uart_inc_repub,
        "uart_unchanged_during_republication": uart_same_repub,
        "seq_discontinuities": int(
            sum(
                1
                for i in range(1, len(seq))
                if seq[i] is not None and seq[i - 1] is not None and seq[i] != seq[i - 1] + 1
            )
        ),
    }
    if missing_age:
        rec["q1_status"] = "RECEIVE_CADENCE_ONLY"
        rec["exclusion_reason"] = "PHASE_AGE_ABSENT_REPUBLICATION_UNIDENTIFIABLE"
        rec["role"] = "RECEIVE_CADENCE_ONLY"
        return rec
    handoff = q2_handoff_reason(rec)
    if handoff:
        rec["q1_status"] = "Q2_HANDOFF_EVIDENCE"
        rec["q2_handoff_reason"] = handoff
        rec["role"] = "EMPIRICAL_TIMING_OBSERVED_NOT_POOLED_FOR_TYPICAL"
        rec["used_for_typical_profile"] = False
        return rec
    rec["q1_status"] = "ELIGIBLE_CORE"
    rec["role"] = "EMPIRICAL_TIMING_CORE"
    rec["used_for_typical_profile"] = True
    rec["q2_handoff_reason"] = None
    return rec


def analyze_pi_entry(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": spec.get("session_id"),
        "evidence_family": spec.get("evidence_family"),
        "artifact_class": spec.get("artifact_class"),
        "inventory_current_path": spec.get("current_path"),
        "repository": spec.get("repository"),
        "physical_or_synthetic": "PHYSICAL_PI_RUNTIME_REFERENCE",
        "replay_status": "NOT_REPARSED_IN_Q1",
        "q1_status": "EXCLUDED",
        "exclusion_reason": "PI_RUNTIME_JSONL_NOT_IN_STANDALONE_REPO",
        "role": "RECENT_PI_RUNTIME_REFERENCE",
        "source_timestamp_available": False,
        "receive_timestamp_available": False,
        "sequence_available": False,
        "phase_age_available": spec.get("phase_age_ms_available") == "PRESENT",
        "packet_count": (spec.get("duration") or {}).get("records"),
        "m_n3_unreparsed_note": (
            "M-N3 previously reported host ~100.1 ms, nested ts median ~121 ms, "
            "T2 update median ~140 ms, republication 16-22 percent. Q1 does not "
            "re-parse those files and does not copy those numbers into frozen parameters."
        ),
    }


def quantile_table(values: list[float]) -> list[list[float]]:
    percents = (0, 1, 5, 25, 50, 75, 95, 99, 100)
    table: list[list[float]] = []
    for percent in percents:
        if percent == 0:
            value = min(values)
        elif percent == 100:
            value = max(values)
        else:
            value = percentile(values, percent)
        table.append([int(percent), r6(value)])
    return table


def session_public_view(rec: dict[str, Any]) -> dict[str, Any]:
    skip = {"receive_intervals_ms", "source_intervals_ms", "republication_run_lengths"}
    return {key: value for key, value in rec.items() if key not in skip}


def build_profile(core: list[dict[str, Any]], timing: dict[str, Any]) -> dict[str, Any]:
    core_repub = [float(rec["source_republication_fraction"]) for rec in core]
    empty_repub = [
        float(rec["source_republication_fraction"])
        for rec in core
        if "empty" in str(rec.get("intended_condition") or "").lower()
    ]
    occupied_repub = [
        float(rec["source_republication_fraction"])
        for rec in core
        if any(
            token in str(rec.get("intended_condition") or "").lower()
            for token in ("occup", "paced", "breath")
        )
    ]
    typical_p = percentile(core_repub, 75) or 0.0
    stressed_p = percentile(empty_repub, 50) or percentile(core_repub, 95) or 0.0
    jitter_vs_100 = timing["core_source_jitter_vs_receive_nominal_ms"]
    return {
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "source_evidence": {
            "inventory_id": "M-N0_TEAM_MR60_PHYSICAL_INVENTORY_001",
            "evidence_family_used": "PRE_PR18_LEGACY_ESP_JSONL",
            "access_method": "git cat-file of M-N0 git_blob_sha_at_raw_index",
            "raw_payload_copied_into_q1": False,
            "m_n4_republication_rule": "accept source event i only if phase_update_estimate_ms[i] > last_accepted + 8 ms",
            "m_n4_contract": "config/mmwave/m_n4_canonical_input_dataset_contract.json",
            "m_n7_result_referenced_not_retuned": "datasets/mmwave/manifests/m_n7_device_domain_result.json",
            "core_session_count": len(core),
            "physiological_values_imported_from_mr60": False,
        },
        "represented_runtime_versions": timing["firmware_strata"],
        "timing_domains": {
            "source_timestamp": {
                "field": "phase_update_estimate_ms",
                "formula": "ts_monotonic_ms - phase_age_ms",
                "authority": "SOURCE_UPDATE_CADENCE_AND_SOURCE_JITTER",
                "physical_radar_acquisition_time_claimed": False,
            },
            "receive_timestamp": {
                "field": "ts_monotonic_ms",
                "authority": "ESP_TELEMETRY_ROW_PUBLISH_CADENCE",
                "pi_host_capture_timestamp": "ABSENT_IN_THIS_EVIDENCE",
            },
            "sequence": {
                "field": "seq",
                "authority": "TRANSPORT_PACKET_IDENTITY",
            },
            "phase_age": {
                "field": "phase_age_ms",
                "authority": "FRESHNESS_FOR_SOURCE_UPDATE_ESTIMATE",
            },
        },
        "nominal_cadence_definition": {
            "receive_publish_interval_ms": NOMINAL_RECEIVE_INTERVAL_MS,
            "receive_publish_hz": 10.0,
            "definition": "empirical median ESP row interval across eligible core sessions",
            "source_update_interval_ms_core_median": timing["core_source_interval_ms"]["median"],
            "eight_ms_is_sensor_period": False,
        },
        "empirical_interval_statistics": {
            "receive_core_ms": timing["core_receive_interval_ms"],
            "source_core_ms": timing["core_source_interval_ms"],
            "receive_all_eligible_ms": timing["all_receive_interval_ms"],
        },
        "jitter_definition": {
            "receive_jitter_ms": "receive_interval_i - 100",
            "source_jitter_ms": "source_update_interval_i - 100",
            "synthetic_jitter_uses": "source_jitter_ms",
            "synthetic_min_interval_ms": SYNTHETIC_MIN_INTERVAL_MS,
            "source_jitter_vs_nominal_ms_quantiles": jitter_vs_100["quantiles"],
            "notes": [
                "Receive jitter is essentially zero at 10 Hz except rare 101-300 ms rows.",
                "Source-update jitter is the MR60-like non-uniform cadence applied to public traces.",
            ],
        },
        "jitter_statistics": {
            "receive_vs_100_ms_core": timing["core_receive_jitter_ms"],
            "source_vs_100_ms_core": timing["core_source_jitter_ms"],
        },
        "duplicate_taxonomy": {
            "CONFIRMED_EXACT_DUPLICATE": "same seq and same ts_monotonic_ms",
            "CONFIRMED_SOURCE_REPUBLICATION": "new seq, source update estimate advances by <= 8 ms versus last accepted",
            "NUMERIC_PLATEAU_ONLY": "accepted source event with equal breath_phase versus previous accepted event",
            "AMBIGUOUS_REPEAT": "repeat without seq and phase_age identity",
            "equal_breath_phase_numeric_value_is_not_republication": True,
        },
        "duplicate_statistics": {
            "confirmed_exact_transport_duplicate_count": 0,
            "confirmed_exact_transport_duplicate_fraction": 0.0,
            "transport_duplicate_status": TRANSPORT_DUPLICATE_STATUS,
        },
        "republication_statistics": {
            "core_session_fraction": timing["core_republication_fraction"],
            "occupied_or_paced_core_fraction": summarize(occupied_repub),
            "empty_core_fraction": summarize(empty_repub),
            "core_max_run": 1,
            "rule": "M-N4 8 ms last-accepted update-estimate guard",
        },
        "supported_corruption_modes": list(SUPPORTED_MODES),
        "unsupported_corruption_modes": {
            TRANSPORT_DUPLICATE_MODE: TRANSPORT_DUPLICATE_STATUS,
            "LARGE_GAP": "DEFERRED_TO_Q2",
            "FREEZE": "DEFERRED_TO_Q2",
            "FLAT_SIGNAL": "DEFERRED_TO_Q2",
            "STALE_SIGNAL": "DEFERRED_TO_Q2",
        },
        "severity_levels": {
            "NOMINAL": {
                "rationale": "occupied-like core median: 10 Hz receive, zero source republication, no added jitter",
                "cadence_jitter": {
                    "enabled": False,
                    "unit_interval_min": 0.0,
                    "unit_interval_max": 0.0,
                },
                "source_republication": {
                    "probability": 0.0,
                    "provenance": "occupied/paced core session median republication fraction",
                },
            },
            "TYPICAL": {
                "rationale": "central pooled-core source jitter plus core session p75 republication fraction",
                "cadence_jitter": {
                    "enabled": True,
                    "unit_interval_min": 0.05,
                    "unit_interval_max": 0.95,
                },
                "source_republication": {
                    "probability": r6(typical_p),
                    "provenance": "core session republication-fraction p75",
                },
            },
            "STRESSED": {
                "rationale": "observed upper-tail still inside core empty-room republication and p01-p99 source jitter; freeze-length runs are not used",
                "cadence_jitter": {
                    "enabled": True,
                    "unit_interval_min": 0.01,
                    "unit_interval_max": 0.99,
                },
                "source_republication": {
                    "probability": r6(stressed_p),
                    "provenance": "core empty-room session median republication fraction",
                },
            },
        },
        "random_seed_policy": {
            "formula": "sha256(seed|stream|severity|index)[:8] / 2^64",
            "streams": ["jitter", "repub"],
            "default_seed": 20260822,
        },
        "determinism_contract": {
            "same_input_profile_seed_mode_severity": "byte-identical outputs",
            "clean_ignores_seed": True,
        },
        "sample_lineage_contract": {
            "every_output_sample_maps_to_an_input_index": True,
            "republication_reuses_prior_kept_source_index": True,
            "no_interpolated_unseen_physiology": True,
            "window_labels_are_not_changed_by_timing_corruption": True,
        },
        "physiological_values_imported_from_mr60": False,
        "mr60_labels_used": False,
        "model_outputs_used": False,
        "d2_used": False,
        "q2_deferred_items": [
            "large gap semantics and rejection thresholds",
            "freeze / flat / stale INPUT_UNAVAILABLE policy",
            "whether long republication runs make a window unusable",
            "Pi host-versus-ESP timestamp residual once Pi JSONL is in-repo",
        ],
        "known_limitations": [
            "Recent Pi runtime JSONL is not in this standalone repository and was not re-parsed.",
            "PR18 Pilot and 2026-08-08 live raw JSONL blobs are not in this repository.",
            "Most schema 1.0 sessions have firmware_version null; they are stratified as schema_1.0_firmware_null.",
            "ESP JSONL has no Pi capture timestamp; ts_monotonic_ms is ESP row time, not Pi receive time.",
            "Exact transport duplicates were not observed; TRANSPORT_DUPLICATE is not a supported Q1 mode.",
            "Core max source-republication run is 1; longer runs exist only in Q2_HANDOFF_EVIDENCE sessions.",
        ],
        "severity_level_ids": list(SEVERITY_LEVELS),
    }


def fidelity_check(profile: dict[str, Any]) -> dict[str, Any]:
    n = 4000
    t = np.arange(n, dtype=np.float64) * NOMINAL_RECEIVE_INTERVAL_MS
    x = np.sin(np.linspace(0.0, 8.0 * math.pi, n))
    out = {}
    for mode in SUPPORTED_MODES:
        for severity in SEVERITY_LEVELS:
            if mode == "CLEAN" and severity != "NOMINAL":
                continue
            result = apply_timing_corruption(
                t, x, profile, mode=mode, severity=severity, seed=20260822
            )
            dt = np.diff(result["timestamps_ms"])
            ops = Counter(row["operation"] for row in result["provenance"])
            repub_frac = ops.get("SOURCE_REPUBLISHED", 0) / result["output_count"]
            jitter_dt = dt - NOMINAL_RECEIVE_INTERVAL_MS
            expected_p = float(
                profile["severity_levels"][severity]["source_republication"]["probability"]
            )
            row = {
                "output_count": result["output_count"],
                "median_interval_ms": r6(float(np.median(dt))) if dt.size else None,
                "republication_fraction": r6(repub_frac),
                "expected_republication_fraction": r6(expected_p) if mode != "CLEAN" else 0.0,
                "jitter_median_ms": r6(float(np.median(jitter_dt))) if dt.size else None,
                "unique_origins": len({row["original_sample_index"] for row in result["provenance"]}),
            }
            if mode in {"SOURCE_REPUBLICATION", "JITTER_PLUS_SOURCE_REPUBLICATION"}:
                row["republication_fraction_abs_error"] = r6(abs(repub_frac - expected_p))
            out[f"{mode}/{severity}"] = row
    return out


def main() -> int:
    policy = load_json(MPV0_POLICY)
    mn4 = load_json(MN4_CONTRACT)
    mn7 = load_json(MN7_RESULT)
    mn0 = load_m_n0()
    if not policy["mr60_policy"]["current_safenest_mr60_never_supervised_for_v2"]:
        raise Q1AccountingError("MR60_POLICY_DRIFT")
    if mn4["timing"]["update_advancement_tolerance_ms"] != UPDATE_ADVANCE_TOLERANCE_MS:
        raise Q1AccountingError("MN4_TOLERANCE_DRIFT")

    physical = [analyze_session(spec) for spec in mn0["physical_sessions"]]
    pi = [analyze_pi_entry(spec) for spec in mn0.get("recent_pi_runtime_reference", [])]
    discovered = physical + pi
    core = [rec for rec in physical if rec.get("q1_status") == "ELIGIBLE_CORE"]
    q2 = [rec for rec in physical if rec.get("q1_status") == "Q2_HANDOFF_EVIDENCE"]
    cadence_only = [rec for rec in physical if rec.get("q1_status") == "RECEIVE_CADENCE_ONLY"]
    excluded = [rec for rec in discovered if rec.get("q1_status") == "EXCLUDED"]
    if len(physical) != 74:
        raise Q1AccountingError(f"PHYSICAL_SESSION_COUNT:{len(physical)}")

    core_recv = [dt for rec in core for dt in rec["receive_intervals_ms"]]
    core_src = [dt for rec in core for dt in rec["source_intervals_ms"]]
    all_recv = [
        dt
        for rec in physical
        if rec.get("receive_intervals_ms")
        for dt in rec["receive_intervals_ms"]
    ]
    firmware_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in core:
        key = str(rec.get("firmware_version") or "schema_1.0_firmware_null")
        if rec.get("schema_version") == "1.0" and rec.get("firmware_version") in (None, "None"):
            key = "schema_1.0_firmware_null"
        firmware_groups[key].append(rec)

    def strata(recs: list[dict[str, Any]]) -> dict[str, Any]:
        recv = [dt for rec in recs for dt in rec["receive_intervals_ms"]]
        src = [dt for rec in recs for dt in rec["source_intervals_ms"]]
        return {
            "session_count": len(recs),
            "packet_count": int(sum(rec["packet_count"] for rec in recs)),
            "receive_interval_ms": summarize(recv),
            "source_interval_ms": summarize(src),
            "source_session_median_ms": summarize(
                [float(rec["source_median_ms"]) for rec in recs if rec.get("source_median_ms") is not None]
            ),
            "republication_fraction": summarize(
                [float(rec["source_republication_fraction"]) for rec in recs]
            ),
        }

    timing = {
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "nominal_receive_interval_ms": NOMINAL_RECEIVE_INTERVAL_MS,
        "update_advancement_tolerance_ms": UPDATE_ADVANCE_TOLERANCE_MS,
        "core_receive_interval_ms": summarize(core_recv),
        "core_source_interval_ms": summarize(core_src),
        "all_receive_interval_ms": summarize(all_recv),
        "core_receive_jitter_ms": summarize([dt - NOMINAL_RECEIVE_INTERVAL_MS for dt in core_recv]),
        "core_source_jitter_ms": summarize([dt - NOMINAL_RECEIVE_INTERVAL_MS for dt in core_src]),
        "core_source_jitter_vs_receive_nominal_ms": {
            "definition": "source_update_interval_i - 100",
            "quantiles": quantile_table([dt - NOMINAL_RECEIVE_INTERVAL_MS for dt in core_src]),
            "summary": summarize([dt - NOMINAL_RECEIVE_INTERVAL_MS for dt in core_src]),
        },
        "core_republication_fraction": summarize(
            [float(rec["source_republication_fraction"]) for rec in core]
        ),
        "core_session_source_median_ms": summarize(
            [float(rec["source_median_ms"]) for rec in core if rec.get("source_median_ms") is not None]
        ),
        "firmware_strata": {key: strata(recs) for key, recs in sorted(firmware_groups.items())},
        "q2_handoff_sessions_excluded_from_typical_pooling": [
            {
                "session_id": rec["session_id"],
                "reason": rec.get("q2_handoff_reason"),
                "max_republication_run": rec.get("max_republication_run"),
                "source_republication_fraction": rec.get("source_republication_fraction"),
                "source_interval_max_ms": rec.get("source_interval_max_ms"),
            }
            for rec in q2
        ],
    }

    profile = build_profile(core, timing)
    fidelity = fidelity_check(profile)
    stressed_err = fidelity["SOURCE_REPUBLICATION/STRESSED"]["republication_fraction_abs_error"]
    typical_err = fidelity["SOURCE_REPUBLICATION/TYPICAL"]["republication_fraction_abs_error"]
    if typical_err is None or typical_err > 0.01 or stressed_err is None or stressed_err > 0.02:
        raise Q1AccountingError("EMPIRICAL_FIDELITY_MISMATCH")

    exact_total = int(sum(rec.get("exact_transport_duplicate_count") or 0 for rec in physical if "exact_transport_duplicate_count" in rec))
    seq_same = int(sum(rec.get("seq_unchanged_during_republication") or 0 for rec in core + q2))
    seq_inc = int(sum(rec.get("seq_increment_during_republication") or 0 for rec in core + q2))
    plateau_fracs = [
        rec["numeric_plateau_accepted_count"] / rec["accepted_source_event_count"]
        for rec in core
        if rec.get("accepted_source_event_count")
    ]
    repeat_audit = {
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "taxonomy_applied": True,
        "confirmed_exact_duplicate": {
            "count": exact_total,
            "affected_sessions": 0,
            "fraction": 0.0,
            "status": TRANSPORT_DUPLICATE_STATUS,
        },
        "confirmed_source_republication": {
            "core_event_count": int(sum(rec["confirmed_source_republication_count"] for rec in core)),
            "core_affected_sessions": int(sum(1 for rec in core if rec["confirmed_source_republication_count"] > 0)),
            "q2_handoff_event_count": int(sum(rec["confirmed_source_republication_count"] for rec in q2)),
            "seq_always_increments": seq_same == 0 and seq_inc > 0,
            "seq_unchanged_count": seq_same,
            "seq_increment_count": seq_inc,
            "core_max_run": max((rec["max_republication_run"] or 0) for rec in core) if core else 0,
            "observed_max_run_including_q2_handoff": max(
                (rec.get("max_republication_run") or 0) for rec in core + q2
            )
            if core + q2
            else 0,
            "core_run_length_note": "Every core republication run length is 1. Longer runs are Q2_HANDOFF_EVIDENCE.",
        },
        "numeric_plateau_only": {
            "core_accepted_equal_phase_fraction": summarize(plateau_fracs),
            "not_treated_as_transport_duplicate": True,
            "not_treated_as_freeze": True,
            "not_imported_into_synthetic_profile": True,
        },
        "ambiguous_repeat": {
            "count": 0,
            "note": "Sessions lacking phase_age were excluded from high-confidence repeat classification.",
        },
        "m_n7_crosscheck_not_a_parameter_source": {
            "empty_republications_m_n7": mn7["recordings"][0]["phase_event_meta"]["n_republications"],
            "occupied_d09_m_n7": mn7["recordings"][1]["phase_event_meta"]["n_republications"],
            "occupied_d06_m_n7": mn7["recordings"][2]["phase_event_meta"]["n_republications"],
        },
    }

    exceptions = {
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "entries": [
            {
                "session_id": rec.get("session_id"),
                "q1_status": rec.get("q1_status"),
                "reason": rec.get("exclusion_reason") or rec.get("q2_handoff_reason"),
                "evidence_family": rec.get("evidence_family"),
            }
            for rec in discovered
            if rec.get("q1_status") != "ELIGIBLE_CORE"
        ],
        "parse_warnings": [
            {
                "session_id": rec["session_id"],
                "parse_failures": rec["parse_failures"],
                "usable_rows": rec.get("packet_count"),
            }
            for rec in physical
            if rec.get("parse_failures")
        ],
        "q2_handoff_observations": [
            {
                "session_id": rec["session_id"],
                "reason": rec.get("q2_handoff_reason"),
                "max_republication_run": rec.get("max_republication_run"),
                "source_republication_fraction": rec.get("source_republication_fraction"),
                "source_interval_max_ms": rec.get("source_interval_max_ms"),
                "receive_zero_dt_count": rec.get("receive_zero_dt_count"),
                "q1_does_not_set_rejection_threshold": True,
            }
            for rec in q2
        ],
    }

    inventory = {
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "mpv0_commit": MPV0_COMMIT,
        "canonical_root_policy": "standalone repository git blobs referenced by M-N0; archive paths are inventory locators only",
        "discovered_sessions": {
            "physical_m_n0": 74,
            "recent_pi_runtime_reference": len(pi),
            "total": len(discovered),
        },
        "eligible_core_sessions": len(core),
        "q2_handoff_sessions": len(q2),
        "receive_cadence_only_sessions": len(cadence_only),
        "excluded_sessions": len(excluded),
        "runtime_firmware_identities": sorted(
            {
                f"schema={rec.get('schema_version')}|firmware={rec.get('firmware_version')}"
                for rec in core + q2 + cadence_only
            }
        ),
        "sessions": [session_public_view(rec) for rec in discovered],
        "d2_used": False,
        "mr60_labels_used": False,
        "model_outputs_used": False,
        "physiological_values_imported_from_mr60": False,
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    checksums = {
        "algorithm": "SHA-256",
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "files": {},
    }
    artifacts = {
        "evidence_inventory.json": inventory,
        "timing_statistics.json": timing,
        "repeat_event_audit.json": repeat_audit,
        "synthetic_corruption_profile.json": profile,
        "exception_registry.json": exceptions,
    }
    for name, payload in artifacts.items():
        checksums["files"][name] = dump_json(MANIFEST_DIR / name, payload)
    dump_json(MANIFEST_DIR / "checksums.json", checksums)

    forbidden_hits = []
    for name in (*MANIFEST_JSON_FILES, "checksums.json"):
        text = (MANIFEST_DIR / name).read_text(encoding="utf-8")
        if ABSOLUTE_PATH_RE.search(text):
            forbidden_hits.append(f"ABSOLUTE_PATH:{name}")
        parsed = json.loads(text)
        blob = json.dumps(parsed)
        for key in FORBIDDEN_PHYSIO_KEYS:
            if key in blob:
                forbidden_hits.append(f"PHYSIO_KEY:{key}")
    if forbidden_hits:
        raise Q1AccountingError(";".join(forbidden_hits))
    print(
        json.dumps(
            {
                "ok": True,
                "gate_hint": "PASS_WITH_LIMITATIONS",
                "core_sessions": len(core),
                "profile_id": PROFILE_ID,
                "fidelity": fidelity,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
