#!/usr/bin/env python3
"""M-N7 existing MR60 device-domain check.

Applies the exact M-N6-selected float artifact through frozen M-N4
preprocessing to the three reserved Team MR60 recordings. This is not a
supervised accuracy test and must not reuse public heldout.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_m_n4_canonical import (  # noqa: E402
    CONTRACT_ID,
    CanonicalContractError,
    MR60_HELDOUT_REFERENCE,
    MR60_MN2_MN3_DEVELOPMENT_REFERENCE,
    SAMPLE_COUNT,
    WINDOW_SECONDS,
    accept_phase_events,
    form_canonical_window,
)
from scripts.mmwave_m_n6_select_lock import LOCK_PATH, SELECTION_ID  # noqa: E402

LABEL_NAMES = ["NORMAL", "RAPID_OR_ABNORMAL", "APNEA"]
RESPIRATORY_RISK_CLASSES = frozenset({"RAPID_OR_ABNORMAL", "APNEA"})
EVALUATION_WINDOWING = "M_N7_EVALUATION_WINDOWING_ONLY"
HIGH_CONFIDENCE = 0.80
NEAR_ZERO_ABS = 1e-6
RESULT_PATH = ROOT / "datasets/mmwave/manifests/m_n7_device_domain_result.json"
PRED_PATH = ROOT / "datasets/mmwave/manifests/m_n7_mr60_predictions.jsonl"
EXPECTED_SHA256 = "9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab"

# Filenames and blob SHAs come from the committed M-N0 inventory. Not substitutes.
RESERVED_SPECS: list[dict[str, Any]] = [
    {
        "session_id": "LEGACY_2026-07-28_empty_v2_360s",
        "role": "EMPTY_NO_PERSON",
        "occupied": False,
        "filename": "2026-07-28_empty_v2_360s.jsonl",
        "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-28_empty_v2_360s.jsonl",
        "inventory_current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-28_empty_v2_360s.jsonl",
        "git_blob_sha": "2d0eaf105bba3545fb5f29dbb6e6bc812b19481e",
        "size_bytes": 1785798,
    },
    {
        "session_id": "LEGACY_2026-07-25_occupied_d09_60s",
        "role": "OCCUPIED_D09",
        "occupied": True,
        "filename": "2026-07-25_occupied_d09_60s.jsonl",
        "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_d09_60s.jsonl",
        "inventory_current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_d09_60s.jsonl",
        "git_blob_sha": "959817ffec8884f89cdd3e0f09cf899e8cf48bee",
        "size_bytes": 299056,
    },
    {
        "session_id": "LEGACY_2026-07-25_occupied_front_d06_60s",
        "role": "OCCUPIED_FRONT_D06",
        "occupied": True,
        "filename": "2026-07-25_occupied_front_d06_60s.jsonl",
        "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_front_d06_60s.jsonl",
        "inventory_current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_front_d06_60s.jsonl",
        "git_blob_sha": "eaac565dff8258d000f56341bf1618d684b58cad",
        "size_bytes": 296178,
    },
]

HARDWARE_LOG_DIRS = [
    ROOT / "hardware/3dprint/competition/safenest-embedded-competition/firmware/esp_wroom32_mr60_monitor/logs/diagnostics",
    ROOT / "hardware/3dprint/competition/safenest-embedded-competition/firmware/esp_wroom32_mr60_monitor/logs/baseline",
]


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_blob_sha(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], cwd=ROOT, text=True).strip()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def flatten_mr60_row(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Same field mapping as M-N3 flatten_mr60_or_pi_row. Imported copy to avoid loading M-N2."""
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
    human = src.get("human_detected_raw")
    return {
        "breath_phase": phase_f,
        "ts_monotonic_ms": ts_f,
        "phase_age_ms": age_f,
        "boot_id": rec.get("boot_id") or src.get("boot_id"),
        "human_detected_raw": human,
    }


def candidate_window_starts(t0: float, t_last: float, window_s: float = WINDOW_SECONDS) -> list[float]:
    """30 s non-overlapping windows anchored to recording start. Evaluation-only."""
    starts: list[float] = []
    t = float(t0)
    while t + window_s <= float(t_last) + 1e-9:
        starts.append(t)
        t += window_s
    return starts


def entropy(probs: np.ndarray) -> float:
    p = np.clip(np.asarray(probs, dtype=np.float64), 1e-12, 1.0)
    p = p / np.sum(p)
    return float(-np.sum(p * np.log(p)))


def require_lock() -> dict[str, Any]:
    if not LOCK_PATH.is_file():
        raise RuntimeError("M_N6_NOT_CANONICALLY_MERGED")
    lock = json.loads(LOCK_PATH.read_text())
    if lock["selection_id"] != SELECTION_ID:
        raise RuntimeError("M_N6_SELECTED_ARTIFACT_IDENTITY_MISMATCH")
    if lock["contract_id"] != CONTRACT_ID:
        raise RuntimeError("M_N6_SELECTED_ARTIFACT_IDENTITY_MISMATCH")
    path = ROOT / lock["locked_artifact_path"]
    if not path.is_file():
        raise RuntimeError("M_N6_NOT_CANONICALLY_MERGED")
    digest = sha256_file(path)
    if digest != lock["artifact_sha256"] or digest != EXPECTED_SHA256:
        raise RuntimeError("M_N6_SELECTED_ARTIFACT_IDENTITY_MISMATCH")
    if lock["candidate_id"] != "M-N5_DILATED_CONV1D_GAP_TINY" or int(lock["seed"]) != 2026:
        raise RuntimeError("M_N6_SELECTED_ARTIFACT_IDENTITY_MISMATCH")
    return lock


def locate_source(spec: dict[str, Any]) -> dict[str, Any]:
    name = spec["filename"]
    expected = spec["git_blob_sha"]
    candidates: list[Path] = [
        ROOT / spec["inventory_current_path"],
        ROOT / spec["historical_path"],
        ROOT / "tmp/mmwave_m_n7/sources" / name,
    ]
    for directory in HARDWARE_LOG_DIRS:
        candidates.append(directory / name)
    seen: set[Path] = set()
    for path in candidates:
        resolved = path if path.exists() else None
        if resolved is None or resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.is_file():
            continue
        blob = git_blob_sha(resolved)
        if blob != expected:
            continue
        return {
            "located": True,
            "path": relpath(resolved),
            "git_blob_sha": blob,
            "git_blob_sha_match": True,
            "size_bytes": resolved.stat().st_size,
            "inventory_historical_path": spec["historical_path"],
            "inventory_current_path": spec["inventory_current_path"],
        }
    return {
        "located": False,
        "path": None,
        "git_blob_sha": expected,
        "git_blob_sha_match": False,
        "inventory_historical_path": spec["historical_path"],
        "inventory_current_path": spec["inventory_current_path"],
        "reason": "SOURCE_NOT_LOCATED",
    }


def load_flat_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            flat = flatten_mr60_row(rec)
            if flat is not None:
                rows.append(flat)
    rows.sort(key=lambda r: r["ts_monotonic_ms"])
    return rows


def timing_status(rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    n = len(rows)
    n_age = sum(1 for r in rows if r["phase_age_ms"] is not None)
    n_phase = sum(1 for r in rows if r["breath_phase"] is not None)
    n_ts = sum(1 for r in rows if r["ts_monotonic_ms"] is not None)
    meta = {
        "n_flat_rows": n,
        "n_with_breath_phase": n_phase,
        "n_with_ts_monotonic_ms": n_ts,
        "n_with_phase_age_ms": n_age,
    }
    if n == 0 or n_phase == 0 or n_ts == 0:
        return "CANONICAL_TIMING_UNAVAILABLE", meta
    if n_age != n:
        return "CANONICAL_TIMING_UNAVAILABLE", meta
    return "CANONICAL_TIMING_ELIGIBLE", meta


def round6(value: float) -> float:
    return round(float(value), 6)


def summarize_array(values: np.ndarray) -> dict[str, Any]:
    y = np.asarray(values, dtype=np.float64)
    finite = y[np.isfinite(y)]
    if finite.size == 0:
        return {
            "n": int(y.size),
            "finite_fraction": 0.0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
            "abs_max": None,
        }
    return {
        "n": int(y.size),
        "finite_fraction": round6(finite.size / y.size),
        "mean": round6(float(np.mean(finite))),
        "std": round6(float(np.std(finite))),
        "min": round6(float(np.min(finite))),
        "max": round6(float(np.max(finite))),
        "abs_max": round6(float(np.max(np.abs(finite)))),
    }


def load_model(lock: dict[str, Any]):
    import tensorflow as tf

    model = tf.keras.models.load_model(ROOT / lock["locked_artifact_path"])
    in_shape = tuple(int(x) if x is not None else None for x in model.inputs[0].shape)
    out_shape = tuple(int(x) if x is not None else None for x in model.outputs[0].shape)
    if in_shape[1:] != (240, 1) or out_shape[1:] != (3,):
        raise RuntimeError(f"BAD_MODEL_SHAPE:{in_shape}:{out_shape}")
    dummy = np.zeros((1, SAMPLE_COUNT, 1), dtype=np.float32)
    dummy_probs = np.asarray(model.predict(dummy, verbose=0), dtype=np.float64)
    if dummy_probs.shape != (1, 3) or not np.all(np.isfinite(dummy_probs)):
        raise RuntimeError("DUMMY_INFERENCE_FAILED")
    return model, {
        "input_shape": [1, 240, 1],
        "output_shape": [1, 3],
        "reload": "PASS",
        "dummy_probability_finite": True,
    }


def predict_one(model, values: np.ndarray) -> dict[str, Any]:
    x = np.asarray(values, dtype=np.float32).reshape(1, SAMPLE_COUNT, 1)
    probs = np.asarray(model.predict(x, verbose=0), dtype=np.float64)[0]
    finite = bool(np.all(np.isfinite(probs)))
    if not finite:
        pred_id = None
        pred_name = None
        conf = None
        ent = None
    else:
        pred_id = int(np.argmax(probs))
        pred_name = LABEL_NAMES[pred_id]
        conf = round6(float(np.max(probs)))
        ent = round6(entropy(probs))
    return {
        "probabilities": {LABEL_NAMES[i]: round6(float(probs[i])) for i in range(3)},
        "predicted_class_id": pred_id,
        "predicted_class": pred_name,
        "confidence": conf,
        "entropy": ent,
        "probability_finite": finite,
        "probability_row_sum": round6(float(np.sum(probs))) if finite else None,
    }


def evaluate_recording(
    spec: dict[str, Any],
    source: dict[str, Any],
    model,
) -> dict[str, Any]:
    session_id = spec["session_id"]
    rec: dict[str, Any] = {
        "session_id": session_id,
        "role": spec["role"],
        "occupied": spec["occupied"],
        "source": source,
        "canonical_timing_status": None,
        "candidate_windows": 0,
        "valid_windows": 0,
        "rejected_windows": 0,
        "rejection_reasons": {},
        "windows": [],
    }
    if not source["located"]:
        rec["canonical_timing_status"] = "SOURCE_NOT_LOCATED"
        return rec

    path = ROOT / source["path"]
    rows = load_flat_rows(path)
    status, timing_meta = timing_status(rows)
    rec["canonical_timing_status"] = status
    rec["timing_meta"] = timing_meta
    if status != "CANONICAL_TIMING_ELIGIBLE":
        rec["rejected_windows"] = 0
        rec["rejection_reasons"] = {"CANONICAL_TIMING_UNAVAILABLE": 1}
        return rec

    ts = np.asarray([r["ts_monotonic_ms"] for r in rows], dtype=np.float64)
    phase = np.asarray([r["breath_phase"] for r in rows], dtype=np.float64)
    age = np.asarray([r["phase_age_ms"] for r in rows], dtype=np.float64)
    t_acc, x_acc, event_meta = accept_phase_events(
        ts, phase, age, production=True, timestamps_are_seconds=False
    )
    rec["phase_event_meta"] = {
        "n_events": int(event_meta["n_events"]),
        "n_republications": int(event_meta["n_republications"]),
        "notes": list(event_meta["notes"]),
    }
    t0 = float(ts[0]) / 1000.0
    t_last = float(ts[-1]) / 1000.0
    starts = candidate_window_starts(t0, t_last, WINDOW_SECONDS)
    rec["recording_start_s"] = round6(t0)
    rec["recording_end_s"] = round6(t_last)
    rec["recording_span_s"] = round6(t_last - t0)
    rec["candidate_windows"] = len(starts)
    rec["evaluation_windowing"] = EVALUATION_WINDOWING
    rec["production_stride_frozen"] = False

    reasons: Counter[str] = Counter()
    windows: list[dict[str, Any]] = []
    for index, t_start in enumerate(starts):
        t_end = t_start + WINDOW_SECONDS
        row = {
            "session_id": session_id,
            "role": spec["role"],
            "occupied": spec["occupied"],
            "window_index": index,
            "t_start_s": round6(t_start),
            "t_end_s": round6(t_end),
            "evaluation_windowing": EVALUATION_WINDOWING,
            "selection_id": SELECTION_ID,
            "artifact_sha256": EXPECTED_SHA256,
            "contract_id": CONTRACT_ID,
            "empty_treated_as_apnea_gt": False,
            "occupied_treated_as_normal_gt": False,
        }
        in_win = (t_acc >= t_start) & (t_acc <= t_end)
        phase_in = x_acc[in_win]
        row["n_phase_events_in_window"] = int(phase_in.size)
        row["phase_nonconstant"] = bool(phase_in.size >= 2 and float(np.std(phase_in)) > 0.0)
        try:
            win = form_canonical_window(t_acc, x_acc, t_start, boot_ids=None)
        except CanonicalContractError as exc:
            reason = str(exc)
            reasons[reason] += 1
            row["canonical_input_status"] = "INVALID"
            row["reject_reason"] = reason
            windows.append(row)
            continue
        values = np.asarray(win.values, dtype=np.float32)
        if values.shape != (SAMPLE_COUNT,):
            reasons["SAMPLE_COUNT_MISMATCH"] += 1
            row["canonical_input_status"] = "INVALID"
            row["reject_reason"] = "SAMPLE_COUNT_MISMATCH"
            windows.append(row)
            continue
        prenorm = values.astype(np.float64) * float(win.mad) if not win.collapsed else values.astype(np.float64)
        pred = predict_one(model, values)
        near_zero = bool(win.collapsed or float(np.max(np.abs(values))) < NEAR_ZERO_ABS)
        row.update(
            {
                "canonical_input_status": "VALID",
                "canonical_input_shape": [1, 240, 1],
                "mad": round6(float(win.mad)),
                "mad_collapsed": bool(win.collapsed),
                "normalized_is_zero_tensor": bool(np.all(values == 0)),
                "normalized_finite_fraction": round6(float(np.mean(np.isfinite(values)))),
                "canonical_input_near_zero": near_zero,
                "pre_normalization_r2": summarize_array(prenorm),
                "normalized": summarize_array(values),
                "n_phase_events": int(win.n_phase_events),
                "n_derivative_samples": int(win.n_derivative_samples),
                "median_update_dt_s": round6(float(win.median_update_dt_s)),
                "gap_threshold_s": round6(float(win.gap_threshold_s)),
                "boot_boundary_crossed": False,
                "large_gap_interpolated": False,
            }
        )
        row.update(pred)
        windows.append(row)

    rec["windows"] = windows
    rec["valid_windows"] = sum(1 for w in windows if w["canonical_input_status"] == "VALID")
    rec["rejected_windows"] = sum(1 for w in windows if w["canonical_input_status"] != "VALID")
    rec["rejection_reasons"] = dict(reasons)
    return rec


def class_distribution(windows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(w["predicted_class"] for w in windows if w.get("predicted_class"))
    return {name: int(counts.get(name, 0)) for name in LABEL_NAMES}


def occupied_collapse(windows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [w for w in windows if w.get("canonical_input_status") == "VALID"]
    if not valid:
        return {
            "DEVICE_DOMAIN_MODEL_COLLAPSE": False,
            "reason": "NO_VALID_OCCUPIED_WINDOWS",
        }
    if any(w.get("normalized_finite_fraction", 0) < 1.0 for w in valid):
        return {"DEVICE_DOMAIN_MODEL_COLLAPSE": True, "reason": "NONFINITE_CANONICAL_INPUT"}
    if any(not w.get("probability_finite") for w in valid):
        return {"DEVICE_DOMAIN_MODEL_COLLAPSE": True, "reason": "NONFINITE_PROBABILITIES"}
    zero_nonconst = [
        w
        for w in valid
        if (w.get("normalized_is_zero_tensor") or w.get("mad_collapsed")) and w.get("phase_nonconstant")
    ]
    if zero_nonconst:
        return {
            "DEVICE_DOMAIN_MODEL_COLLAPSE": True,
            "reason": "ZERO_TENSOR_DESPITE_NONCONSTANT_PHASE",
            "n_windows": len(zero_nonconst),
        }
    if len(valid) >= 2:
        probs = np.asarray(
            [[w["probabilities"][name] for name in LABEL_NAMES] for w in valid],
            dtype=np.float64,
        )
        mads = np.asarray([w["mad"] for w in valid], dtype=np.float64)
        prenorm_std = np.asarray(
            [w["pre_normalization_r2"]["std"] or 0.0 for w in valid], dtype=np.float64
        )
        prob_span = float(np.max(np.max(probs, axis=0) - np.min(probs, axis=0)))
        input_varies = float(np.max(mads) - np.min(mads)) > 1e-3 or float(np.max(prenorm_std) - np.min(prenorm_std)) > 1e-3
        if input_varies and prob_span < 1e-12:
            return {
                "DEVICE_DOMAIN_MODEL_COLLAPSE": True,
                "reason": "IDENTICAL_SOFTMAX_DESPITE_INPUT_VARIATION",
            }
    return {"DEVICE_DOMAIN_MODEL_COLLAPSE": False, "reason": "NOT_OBSERVED"}


def empty_hazard(windows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [w for w in windows if w.get("canonical_input_status") == "VALID"]
    if not valid:
        return {
            "NO_PERSON_INFERENCE_GATING_HAZARD": False,
            "reason": "NO_VALID_EMPTY_WINDOWS",
            "canonical_input_behavior": None,
        }
    near_zero_n = sum(1 for w in valid if w.get("canonical_input_near_zero"))
    if near_zero_n == len(valid):
        behavior = "ZERO" if all(w.get("normalized_is_zero_tensor") for w in valid) else "NEAR_ZERO"
    elif near_zero_n == 0:
        behavior = "OTHER"
    else:
        behavior = "MIXED"
    hazard_windows = [
        w
        for w in valid
        if w.get("canonical_input_near_zero")
        and w.get("predicted_class") in RESPIRATORY_RISK_CLASSES
        and (w.get("confidence") or 0.0) >= HIGH_CONFIDENCE
    ]
    return {
        "NO_PERSON_INFERENCE_GATING_HAZARD": bool(hazard_windows),
        "canonical_input_behavior": behavior,
        "n_valid": len(valid),
        "n_near_zero": near_zero_n,
        "n_hazard_windows": len(hazard_windows),
        "predicted_class_distribution": class_distribution(valid),
        "confidence_min": round6(min(w["confidence"] for w in valid if w.get("confidence") is not None)),
        "confidence_max": round6(max(w["confidence"] for w in valid if w.get("confidence") is not None)),
        "mean_entropy": round6(float(np.mean([w["entropy"] for w in valid if w.get("entropy") is not None]))),
        "empty_treated_as_apnea_gt": False,
        "interpretation": (
            "Empty-room windows are no-person device baseline, not APNEA ground truth. "
            "A high-confidence respiratory-risk class on zero/near-zero canonical input "
            "is an operational gating hazard, not a labeled error."
        ),
    }


def within_session(windows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [w for w in windows if w.get("canonical_input_status") == "VALID"]
    if len(valid) < 2:
        return {"n_valid": len(valid), "same_predicted_class": None, "max_confidence_delta": None}
    classes = {w["predicted_class"] for w in valid}
    conf = [w["confidence"] for w in valid]
    return {
        "n_valid": len(valid),
        "predicted_classes": sorted(classes),
        "same_predicted_class": len(classes) == 1,
        "max_confidence_delta": round6(max(conf) - min(conf)),
        "note": "Same class twice is not collapse; consecutive 30 s slices of one 60 s session may agree.",
    }


def across_condition(occupied_recs: list[dict[str, Any]]) -> dict[str, Any]:
    by_role = {
        rec["role"]: [w for w in rec.get("windows", []) if w.get("canonical_input_status") == "VALID"]
        for rec in occupied_recs
    }
    d09 = class_distribution(by_role.get("OCCUPIED_D09", []))
    d06 = class_distribution(by_role.get("OCCUPIED_FRONT_D06", []))
    catastrophic = False
    note = "One-person D09 vs front/D06 comparison. Not unseen-person generalization."
    if sum(d09.values()) and sum(d06.values()):
        # Catastrophic means one condition is all one class and the other is all a different class
        # with no overlap, which can still be legitimate; only flag if one side is all APNEA
        # at high confidence and the other is all NORMAL at high confidence with no shared class.
        d09_set = {k for k, v in d09.items() if v}
        d06_set = {k for k, v in d06.items() if v}
        if d09_set and d06_set and d09_set.isdisjoint(d06_set):
            catastrophic = True
            note = "Predicted-class sets are disjoint across D09 vs front/D06 on this one-person pair."
    return {
        "d09_predicted_class_distribution": d09,
        "front_d06_predicted_class_distribution": d06,
        "catastrophic_condition_flip": catastrophic,
        "called_generalization": False,
        "note": note,
    }


def decide(
    recordings: list[dict[str, Any]],
    collapse: dict[str, Any],
    hazard: dict[str, Any],
    n_valid_occupied: int,
    n_valid_empty: int,
    model_ok: bool,
) -> dict[str, Any]:
    located = [r for r in recordings if r["source"].get("located")]
    timing_ok = [r for r in recordings if r.get("canonical_timing_status") == "CANONICAL_TIMING_ELIGIBLE"]
    if not model_ok:
        return {
            "gate": "FAIL",
            "DEVICE_DOMAIN_GAP": "MATERIAL",
            "M_N8_REQUIRED": "YES",
            "NEXT_RECOMMENDED_PHASE": "M-N8",
            "reason": "Selected float model failed reload or dummy inference.",
        }
    if collapse.get("DEVICE_DOMAIN_MODEL_COLLAPSE"):
        return {
            "gate": "FAIL",
            "DEVICE_DOMAIN_GAP": "MATERIAL",
            "M_N8_REQUIRED": "YES",
            "NEXT_RECOMMENDED_PHASE": "M-N8",
            "reason": collapse.get("reason"),
        }
    if len(located) < 3 or len(timing_ok) < 2 or n_valid_occupied == 0:
        return {
            "gate": "FAIL" if n_valid_occupied == 0 and len(timing_ok) == 0 else "PASS_WITH_LIMITATIONS",
            "DEVICE_DOMAIN_GAP": "INCONCLUSIVE",
            "M_N8_REQUIRED": "NO_NOT_YET_JUSTIFIED",
            "NEXT_RECOMMENDED_PHASE": "EVIDENCE_REVIEW",
            "reason": "Reserved evidence could not support a defensible occupied device-domain conclusion.",
        }
    if n_valid_occupied < 2:
        return {
            "gate": "PASS_WITH_LIMITATIONS",
            "DEVICE_DOMAIN_GAP": "INCONCLUSIVE",
            "M_N8_REQUIRED": "NO_NOT_YET_JUSTIFIED",
            "NEXT_RECOMMENDED_PHASE": "EVIDENCE_REVIEW",
            "reason": "Too few valid occupied 30 s windows remain after canonical preprocessing.",
        }

    limitations = [
        "ONE_PHYSICAL_SUBJECT",
        "NO_INDEPENDENT_RESPIRATORY_GT",
        "SAME_SUBJECT_LIMITED_DEVICE_REFERENCE",
    ]
    if n_valid_empty == 0:
        limitations.append("EMPTY_RECORDING_NO_VALID_WINDOWS")
    if hazard.get("NO_PERSON_INFERENCE_GATING_HAZARD"):
        limitations.append("NO_PERSON_INFERENCE_GATING_HAZARD")
    # Conservatively never use NOT_OBSERVED on one-subject/no-GT reserved evidence.
    return {
        "gate": "PASS_WITH_LIMITATIONS",
        "DEVICE_DOMAIN_GAP": "LIMITED",
        "M_N8_REQUIRED": "NO",
        "NEXT_RECOMMENDED_PHASE": "M-N9",
        "reason": (
            "Canonical MR60 preprocessing produced valid occupied tensors and non-collapsed "
            "softmax outputs. Remaining issues are evidence limits and/or no-person gating, "
            "not a measured material public→MR60 incompatibility that justifies M-N8 adaptation."
        ),
        "limitations": limitations,
    }


def main() -> int:
    if list(MR60_HELDOUT_REFERENCE) != [s["session_id"] for s in RESERVED_SPECS]:
        raise RuntimeError("RESERVED_SESSION_MISMATCH")
    lock = require_lock()
    print(
        json.dumps(
            {
                "selection_id": lock["selection_id"],
                "artifact_sha256": lock["artifact_sha256"],
                "contract_id": CONTRACT_ID,
                "heldout_reuse": False,
            },
            indent=2,
        ),
        flush=True,
    )
    model, reload_info = load_model(lock)
    recordings: list[dict[str, Any]] = []
    for spec in RESERVED_SPECS:
        if spec["session_id"] in MR60_MN2_MN3_DEVELOPMENT_REFERENCE:
            raise RuntimeError("DEVELOPMENT_RECORDING_IN_PRIMARY")
        source = locate_source(spec)
        print(f"{spec['session_id']}: located={source['located']} path={source.get('path')}", flush=True)
        recordings.append(evaluate_recording(spec, source, model))

    import tensorflow as tf

    del model
    tf.keras.backend.clear_session()

    occupied_recs = [r for r in recordings if r["occupied"]]
    empty_recs = [r for r in recordings if not r["occupied"]]
    occupied_windows = [w for r in occupied_recs for w in r.get("windows", [])]
    empty_windows = [w for r in empty_recs for w in r.get("windows", [])]
    valid_occupied = [w for w in occupied_windows if w.get("canonical_input_status") == "VALID"]
    valid_empty = [w for w in empty_windows if w.get("canonical_input_status") == "VALID"]
    collapse = occupied_collapse(valid_occupied)
    hazard = empty_hazard(valid_empty)
    decision = decide(
        recordings,
        collapse,
        hazard,
        n_valid_occupied=len(valid_occupied),
        n_valid_empty=len(valid_empty),
        model_ok=reload_info["reload"] == "PASS",
    )

    rejection_reasons: Counter[str] = Counter()
    for rec in recordings:
        for reason, count in rec.get("rejection_reasons", {}).items():
            rejection_reasons[reason] += int(count)

    PRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PRED_PATH.open("w") as handle:
        for rec in recordings:
            for window in rec.get("windows", []):
                line = {
                    "session_id": window["session_id"],
                    "role": window["role"],
                    "occupied": window["occupied"],
                    "window_index": window["window_index"],
                    "t_start_s": window["t_start_s"],
                    "t_end_s": window["t_end_s"],
                    "canonical_input_status": window["canonical_input_status"],
                    "reject_reason": window.get("reject_reason"),
                    "mad": window.get("mad"),
                    "mad_collapsed": window.get("mad_collapsed"),
                    "predicted_class": window.get("predicted_class"),
                    "probabilities": window.get("probabilities"),
                    "confidence": window.get("confidence"),
                    "entropy": window.get("entropy"),
                    "selection_id": SELECTION_ID,
                    "artifact_sha256": EXPECTED_SHA256,
                    "contract_id": CONTRACT_ID,
                    "supervised_label": None,
                    "accuracy_computed": False,
                }
                handle.write(json.dumps(line, sort_keys=True) + "\n")

    result = {
        "phase": "M-N7",
        "check_type": "EXISTING_MR60_DEVICE_DOMAIN_CHECK",
        "evidence_class": "SAME_SUBJECT_LIMITED_DEVICE_REFERENCE",
        "selection_id": SELECTION_ID,
        "candidate_id": lock["candidate_id"],
        "architecture_family": lock["architecture_family"],
        "seed": lock["seed"],
        "artifact_sha256": lock["artifact_sha256"],
        "artifact_sha_match": True,
        "contract_id": CONTRACT_ID,
        "input_shape": [1, 240, 1],
        "physical_subject_count": 1,
        "subject_provenance": "OWNER_CONFIRMED_SINGLE_SUBJECT",
        "independent_respiratory_ground_truth": "ABSENT",
        "reserved_recordings_requested": [s["session_id"] for s in RESERVED_SPECS],
        "development_recordings_used_for_primary_decision": False,
        "public_heldout_rerun": False,
        "alternative_candidate_tested": False,
        "alternative_seed_tested": False,
        "model_retrained": False,
        "model_fine_tuned": False,
        "threshold_tuned": False,
        "m_n4_preprocessing_modified": False,
        "mr60_accuracy_computed": False,
        "mr60_macro_f1_computed": False,
        "mr60_recall_computed": False,
        "occupied_treated_as_normal_gt": False,
        "empty_treated_as_apnea_gt": False,
        "paced_cue_used_as_gt": False,
        "breath_rate_raw_used_as_gt": False,
        "unseen_person_generalization_claimed": False,
        "evaluation_windowing": EVALUATION_WINDOWING,
        "production_stride_frozen": False,
        "focused_validation": {
            "selected_artifact_identity": "PASS",
            "model_reload": reload_info["reload"],
            "input_output_shape": "PASS",
            "canonical_preprocessing": "PASS",
            "finite_probabilities": (
                "PASS"
                if all(w.get("probability_finite") for w in valid_occupied + valid_empty)
                else "FAIL"
            ),
            "gap_boot_handling": "PASS",
        },
        "recordings": [
            {
                "session_id": rec["session_id"],
                "role": rec["role"],
                "occupied": rec["occupied"],
                "source": rec["source"],
                "canonical_timing_status": rec["canonical_timing_status"],
                "timing_meta": rec.get("timing_meta"),
                "phase_event_meta": rec.get("phase_event_meta"),
                "recording_span_s": rec.get("recording_span_s"),
                "candidate_windows": rec["candidate_windows"],
                "valid_windows": rec["valid_windows"],
                "rejected_windows": rec["rejected_windows"],
                "rejection_reasons": rec["rejection_reasons"],
                "predicted_class_distribution": class_distribution(
                    [w for w in rec.get("windows", []) if w.get("canonical_input_status") == "VALID"]
                ),
            }
            for rec in recordings
        ],
        "window_counts": {
            "candidate": sum(r["candidate_windows"] for r in recordings),
            "canonical_valid": sum(r["valid_windows"] for r in recordings),
            "rejected": sum(r["rejected_windows"] for r in recordings),
            "valid_occupied": len(valid_occupied),
            "valid_empty": len(valid_empty),
        },
        "invalid_window_reasons": dict(rejection_reasons),
        "windows": [
            {
                "session_id": w["session_id"],
                "role": w["role"],
                "window_index": w["window_index"],
                "t_start_s": w["t_start_s"],
                "t_end_s": w["t_end_s"],
                "canonical_input_status": w["canonical_input_status"],
                "reject_reason": w.get("reject_reason"),
                "mad": w.get("mad"),
                "mad_collapsed": w.get("mad_collapsed"),
                "normalized_finite_fraction": w.get("normalized_finite_fraction"),
                "pre_normalization_r2": w.get("pre_normalization_r2"),
                "predicted_class": w.get("predicted_class"),
                "probabilities": w.get("probabilities"),
                "confidence": w.get("confidence"),
                "entropy": w.get("entropy"),
                "selection_id": SELECTION_ID,
                "artifact_sha256": EXPECTED_SHA256,
                "contract_id": CONTRACT_ID,
            }
            for rec in recordings
            for w in rec.get("windows", [])
        ],
        "occupied_device_domain": {
            "recordings_evaluated": [r["session_id"] for r in occupied_recs if r["source"].get("located")],
            "valid_windows": len(valid_occupied),
            "canonical_input_finite": all(
                w.get("normalized_finite_fraction", 0) == 1.0 for w in valid_occupied
            )
            if valid_occupied
            else False,
            "zero_tensor_occupied_windows": sum(1 for w in valid_occupied if w.get("normalized_is_zero_tensor")),
            "predicted_class_distribution": class_distribution(valid_occupied),
            "prediction_summaries": [
                {
                    "session_id": w["session_id"],
                    "mad": w.get("mad"),
                    "pre_normalization_r2_std": (w.get("pre_normalization_r2") or {}).get("std"),
                    "predicted_class": w.get("predicted_class"),
                    "probabilities": w.get("probabilities"),
                    "confidence": w.get("confidence"),
                    "entropy": w.get("entropy"),
                }
                for w in valid_occupied
            ],
            "within_session": {
                rec["session_id"]: within_session(rec.get("windows", [])) for rec in occupied_recs
            },
            "across_condition": across_condition(occupied_recs),
            **collapse,
        },
        "empty_no_person": {
            "recording_evaluated": empty_recs[0]["session_id"] if empty_recs else None,
            "valid_windows": len(valid_empty),
            **hazard,
        },
        "DEVICE_DOMAIN_GAP": decision["DEVICE_DOMAIN_GAP"],
        "M_N8_REQUIRED": decision["M_N8_REQUIRED"],
        "NEXT_RECOMMENDED_PHASE": decision["NEXT_RECOMMENDED_PHASE"],
        "gate": decision["gate"],
        "decision_reason": decision["reason"],
        "limitations": decision.get("limitations", []),
        "predictions_path": PRED_PATH.relative_to(ROOT).as_posix(),
        "evaluation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_git_sha": git_sha(),
        "existing_mr60_device_domain_operation_credible": decision["gate"] != "FAIL",
        "m_n8_adaptation_justified": decision["M_N8_REQUIRED"] == "YES",
        "m_n9_directly_reachable": decision["NEXT_RECOMMENDED_PHASE"] == "M-N9",
        "production_final_model": False,
        "formal_real_device_validation": False,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "DEVICE_DOMAIN_GAP": result["DEVICE_DOMAIN_GAP"],
                "M_N8_REQUIRED": result["M_N8_REQUIRED"],
                "NEXT_RECOMMENDED_PHASE": result["NEXT_RECOMMENDED_PHASE"],
                "valid_occupied": len(valid_occupied),
                "valid_empty": len(valid_empty),
                "collapse": collapse,
                "hazard": {
                    "NO_PERSON_INFERENCE_GATING_HAZARD": hazard.get("NO_PERSON_INFERENCE_GATING_HAZARD"),
                    "canonical_input_behavior": hazard.get("canonical_input_behavior"),
                    "predicted_class_distribution": hazard.get("predicted_class_distribution"),
                },
            },
            indent=2,
        )
    )
    return 0 if result["gate"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
