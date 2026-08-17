#!/usr/bin/env python3
"""M-N6 Stage B: evaluate the Stage A locked float candidate on heldout once.

Requires the selection-lock commit to already exist. Does not evaluate any
other M-N5 family or seed. Does not tune thresholds or preprocessing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_m_n4_canonical import (  # noqa: E402
    CLASS_TO_ID,
    CONTRACT_ID,
    CanonicalContractError,
    SAMPLE_COUNT,
    canonical_from_public_native,
)
from scripts.mmwave_m_n5_train_candidates import (  # noqa: E402
    LABEL_NAMES,
    cached_public_series,
    evaluate_val,
    load_jsonl,
    load_train_val_provenance,
    sha256_file,
)
from scripts.mmwave_m_n6_select_lock import LOCK_PATH, SELECTION_ID  # noqa: E402

HELDOUT_SPLIT = "NEW_MODEL_HELDOUT_TEST"
INDEX_PATH = ROOT / "datasets/mmwave/manifests/m_n4_canonical/window_index.jsonl"
SPLIT_PATH = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"
RESULT_PATH = ROOT / "datasets/mmwave/manifests/m_n6_heldout_result.json"
PRED_PATH = ROOT / "datasets/mmwave/manifests/m_n6_heldout_predictions.jsonl"
EXPECTED_HELDOUT_WINDOWS = 74
EXPECTED_HELDOUT_SUBJECTS = 16


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def selection_lock_commit() -> str:
    sha = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(LOCK_PATH.relative_to(ROOT))],
        cwd=ROOT,
        text=True,
    ).strip()
    if not sha:
        raise RuntimeError("SELECTION_LOCK_COMMIT_MISSING")
    return sha


def require_lock() -> dict[str, Any]:
    if not LOCK_PATH.is_file():
        raise RuntimeError("SELECTION_LOCK_MISSING")
    lock = json.loads(LOCK_PATH.read_text())
    if lock["selection_id"] != SELECTION_ID:
        raise RuntimeError("SELECTION_ID_MISMATCH")
    if int(lock["heldout_inference_before_lock"]) != 0:
        raise RuntimeError("HELDOUT_ACCESSED_BEFORE_LOCK")
    if lock["contract_id"] != CONTRACT_ID:
        raise RuntimeError("CONTRACT_MISMATCH")
    path = ROOT / lock["locked_artifact_path"]
    if not path.is_file():
        raise RuntimeError("LOCKED_ARTIFACT_MISSING")
    digest = sha256_file(path)
    if digest != lock["artifact_sha256"]:
        raise RuntimeError("SELECTED_M_N5_ARTIFACT_IDENTITY_MISMATCH")
    return lock


def load_heldout_rows() -> tuple[list[dict[str, Any]], set[str], set[str]]:
    split = json.loads(SPLIT_PATH.read_text())
    held_ids = set(split["subject_ids"][HELDOUT_SPLIT])
    train_ids = set(split["subject_ids"]["TRAIN"])
    val_ids = set(split["subject_ids"]["VAL"])
    if held_ids & train_ids or held_ids & val_ids:
        raise RuntimeError("HELDOUT_SUBJECT_OVERLAP")
    if len(held_ids) != EXPECTED_HELDOUT_SUBJECTS:
        raise RuntimeError(f"HELDOUT_SUBJECT_COUNT:{len(held_ids)}")
    rows: list[dict[str, Any]] = []
    for row in load_jsonl(INDEX_PATH):
        if row["split"] != HELDOUT_SPLIT:
            continue
        if row["subject_id"] not in held_ids:
            raise RuntimeError(f"HELDOUT_SUBJECT_NOT_IN_SPLIT:{row['subject_id']}")
        if not row.get("supervised_eligible"):
            continue
        if row.get("safenest_label") not in CLASS_TO_ID:
            raise RuntimeError(f"NON_CLASS_HELDOUT:{row['window_id']}")
        rows.append(row)
    rows.sort(key=lambda r: r["window_id"])
    return rows, held_ids, train_ids | val_ids


def materialize_heldout(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rec_ids = {r["recording_id"] for r in rows}
    provenance = load_train_val_provenance(rec_ids)
    series_cache: dict[str, Any] = {}
    xs: list[np.ndarray] = []
    ys: list[int] = []
    subjects: list[str] = []
    window_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        if row["split"] != HELDOUT_SPLIT:
            raise RuntimeError("NON_HELDOUT_ROW_IN_STAGE_B")
        if i == 1 or i % 20 == 0 or i == len(rows):
            print(f"  materializing HELDOUT {i}/{len(rows)}", flush=True)
        rid = row["recording_id"]
        if rid not in series_cache:
            series_cache[rid] = cached_public_series(rid, provenance[rid])
        series = series_cache[rid]
        t_start = float(row["source_start_index"]) * float(series.median_dt)
        try:
            win = canonical_from_public_native(series.elapsed_s, series.values, t_start)
        except CanonicalContractError as exc:
            failures.append({"window_id": row["window_id"], "reason": str(exc)})
            continue
        values = np.asarray(win.values, dtype=np.float32)
        if values.shape != (SAMPLE_COUNT,) or not np.all(np.isfinite(values)):
            failures.append({"window_id": row["window_id"], "reason": "BAD_TENSOR"})
            continue
        xs.append(values.reshape(SAMPLE_COUNT, 1))
        ys.append(int(row["safenest_label_id"]))
        subjects.append(row["subject_id"])
        window_ids.append(row["window_id"])
    if failures:
        raise RuntimeError(f"HELDOUT_TRANSFORM_FAILURES:{failures[:8]}")
    x = np.stack(xs, axis=0).astype(np.float32)
    y = np.asarray(ys, dtype=np.int32)
    return {
        "x": x,
        "y": y,
        "subjects": subjects,
        "window_ids": window_ids,
        "class_counts": {LABEL_NAMES[i]: int(np.sum(y == i)) for i in range(3)},
    }


def predict_locked(lock: dict[str, Any], bundle: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    import tensorflow as tf

    model = tf.keras.models.load_model(ROOT / lock["locked_artifact_path"])
    in_shape = tuple(model.inputs[0].shape)
    out_shape = tuple(model.outputs[0].shape)
    if in_shape[1:] != (240, 1) or out_shape[1:] != (3,):
        raise RuntimeError(f"BAD_MODEL_SHAPE:{in_shape}:{out_shape}")
    metrics = evaluate_val(model, bundle["x"], bundle["y"], bundle["subjects"])
    probs = np.asarray(model.predict(bundle["x"], batch_size=32, verbose=0), dtype=np.float64)
    y_pred = np.argmax(probs, axis=1).astype(np.int32)
    del model
    tf.keras.backend.clear_session()
    return probs, y_pred, metrics


def subject_summary(y_true: np.ndarray, y_pred: np.ndarray, subjects: list[str]) -> dict[str, Any]:
    accs: list[float] = []
    n_correct = 0
    for sid in sorted(set(subjects)):
        mask = np.asarray([s == sid for s in subjects])
        acc = float(np.mean(y_true[mask] == y_pred[mask]))
        accs.append(acc)
        if int(np.sum(y_true[mask] == y_pred[mask])) >= 1:
            n_correct += 1
    return {
        "n_heldout_subjects": len(set(subjects)),
        "n_subjects_with_at_least_one_correct": n_correct,
        "median_per_subject_accuracy": round(float(np.median(accs)), 6),
        "minimum_per_subject_accuracy": round(float(np.min(accs)), 6),
        "maximum_per_subject_accuracy": round(float(np.max(accs)), 6),
        "per_subject_macro_f1_invented": False,
    }


def write_predictions(lock: dict[str, Any], bundle: dict[str, Any], probs: np.ndarray, y_pred: np.ndarray) -> None:
    PRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PRED_PATH.open("w") as handle:
        for i, window_id in enumerate(bundle["window_ids"]):
            rec = {
                "sample_id": window_id,
                "window_id": window_id,
                "subject_id": bundle["subjects"][i],
                "true_class": LABEL_NAMES[int(bundle["y"][i])],
                "true_class_id": int(bundle["y"][i]),
                "predicted_class": LABEL_NAMES[int(y_pred[i])],
                "predicted_class_id": int(y_pred[i]),
                "probabilities": {
                    LABEL_NAMES[j]: round(float(probs[i, j]), 6) for j in range(3)
                },
                "selected_artifact_sha256": lock["artifact_sha256"],
                "selection_id": SELECTION_ID,
                "contract_id": CONTRACT_ID,
            }
            handle.write(json.dumps(rec, sort_keys=True) + "\n")


def decide_gate(metrics: dict[str, Any], gap: dict[str, Any]) -> tuple[str, bool]:
    if metrics.get("collapse_status") != "NON_DEGENERATE":
        return "FAIL", False
    if not metrics.get("probability_finite"):
        return "FAIL", False
    rapid = float(metrics["per_class_recall"]["RAPID_OR_ABNORMAL"])
    f1_gap = abs(float(gap["macro_f1_gap"]))
    if rapid < 0.50 or f1_gap >= 0.08:
        return "PASS_WITH_LIMITATIONS", True
    return "PASS", True


def main() -> int:
    lock = require_lock()
    lock_commit = selection_lock_commit()
    print(
        json.dumps(
            {
                "selected_candidate": lock["candidate_id"],
                "selected_seed": lock["seed"],
                "selected_artifact_sha256": lock["artifact_sha256"],
                "selection_lock_commit": lock_commit,
                "heldout_inference_so_far": 0,
            },
            indent=2,
        ),
        flush=True,
    )
    rows, held_ids, train_val_ids = load_heldout_rows()
    if set(r["subject_id"] for r in rows) & train_val_ids:
        raise RuntimeError("HELDOUT_TRAIN_VAL_LEAK")
    print(f"Stage B materializing {len(rows)} heldout windows...", flush=True)
    bundle = materialize_heldout(rows)
    if bundle["x"].shape[0] != EXPECTED_HELDOUT_WINDOWS:
        raise RuntimeError(f"HELDOUT_WINDOW_COUNT:{bundle['x'].shape[0]}")
    if len(set(bundle["subjects"])) != EXPECTED_HELDOUT_SUBJECTS:
        raise RuntimeError(f"HELDOUT_SUBJECTS_IN_TENSORS:{len(set(bundle['subjects']))}")
    probs, y_pred, metrics = predict_locked(lock, bundle)
    subjects = subject_summary(bundle["y"], y_pred, bundle["subjects"])
    metrics["subject_summary"] = subjects
    write_predictions(lock, bundle, probs, y_pred)
    val = lock["val_metrics"]
    gap = {
        "val_accuracy": val["accuracy"],
        "heldout_accuracy": metrics["val_accuracy"],
        "accuracy_gap": round(float(metrics["val_accuracy"]) - float(val["accuracy"]), 6),
        "val_macro_f1": val["macro_f1"],
        "heldout_macro_f1": metrics["val_macro_f1"],
        "macro_f1_gap": round(float(metrics["val_macro_f1"]) - float(val["macro_f1"]), 6),
        "normal_recall": {
            "val": val["per_class_recall"]["NORMAL"],
            "heldout": metrics["per_class_recall"]["NORMAL"],
        },
        "rapid_recall": {
            "val": val["per_class_recall"]["RAPID_OR_ABNORMAL"],
            "heldout": metrics["per_class_recall"]["RAPID_OR_ABNORMAL"],
        },
        "apnea_proxy_recall": {
            "val": val["per_class_recall"]["APNEA"],
            "heldout": metrics["per_class_recall"]["APNEA"],
        },
    }
    gate, credible = decide_gate(metrics, gap)
    result = {
        "phase": "M-N6_STAGE_B",
        "selection_id": SELECTION_ID,
        "selection_lock_path": str(LOCK_PATH.relative_to(ROOT)),
        "selection_lock_commit": lock_commit,
        "contract_id": CONTRACT_ID,
        "candidate_id": lock["candidate_id"],
        "architecture_family": lock["architecture_family"],
        "seed": lock["seed"],
        "artifact_sha256": lock["artifact_sha256"],
        "artifact_sha_unchanged": True,
        "candidate_identities_evaluated": 1,
        "heldout_split": HELDOUT_SPLIT,
        "heldout_subject_count": EXPECTED_HELDOUT_SUBJECTS,
        "heldout_window_count": int(bundle["x"].shape[0]),
        "heldout_class_counts": bundle["class_counts"],
        "heldout_access_state": "CONSUMED_ONCE_FOR_M_N6_FINAL_EVALUATION",
        "heldout_may_be_reused_for_future_model_selection": False,
        "runner_up_evaluated": False,
        "alternative_seed_evaluated": False,
        "threshold_tuned": False,
        "preprocessing_modified": False,
        "train_plus_val_retraining": False,
        "team_mr60_evaluated": False,
        "metrics": {
            "loss": metrics["val_loss"],
            "accuracy": metrics["val_accuracy"],
            "macro_f1": metrics["val_macro_f1"],
            "balanced_accuracy": metrics["val_balanced_accuracy"],
            "per_class": metrics["per_class"],
            "per_class_recall": metrics["per_class_recall"],
            "confusion_matrix": metrics["confusion_matrix"],
            "predicted_class_counts": metrics["predicted_class_counts"],
            "collapse_status": metrics["collapse_status"],
            "probability_finite": metrics["probability_finite"],
            "probability_row_sum_ok": metrics["probability_row_sum_ok"],
        },
        "subject_summary": subjects,
        "val_vs_heldout": gap,
        "predictions_path": str(PRED_PATH.relative_to(ROOT)),
        "evaluation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_git_sha": git_sha(),
        "gate": gate,
        "selected_float_candidate_remains_credible": credible,
        "m_n7_authorized": credible and gate != "FAIL",
        "production_final_model": False,
        "device_validated": False,
        "status": "M_N6_SELECTED_FLOAT_CANDIDATE",
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"gate": gate, "heldout_macro_f1": metrics["val_macro_f1"], "rapid_recall": metrics["per_class_recall"]["RAPID_OR_ABNORMAL"]}, indent=2))
    return 0 if gate != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
