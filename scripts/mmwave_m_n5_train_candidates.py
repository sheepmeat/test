#!/usr/bin/env python3
"""M-N5 small candidate training on the frozen M-N4 input/dataset contract.

PUBLIC TRAIN/VAL only. NEW_MODEL_HELDOUT_TEST is never loaded, inferred, or
ranked on. Team MR60 is not used as supervised TRAIN. No final model selection.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_m_n2_common_representation import load_public_series  # noqa: E402
from scripts.mmwave_m_n4_canonical import (  # noqa: E402
    CLASS_TO_ID,
    CONTRACT_ID,
    CanonicalContractError,
    SAMPLE_COUNT,
    canonical_from_public_native,
)

LABEL_NAMES = ["NORMAL", "RAPID_OR_ABNORMAL", "APNEA"]
ALLOWED_SPLITS = frozenset({"TRAIN", "VAL"})
FORBIDDEN_SPLIT = "NEW_MODEL_HELDOUT_TEST"
NEW_MODEL_HELDOUT_TEST_INFERENCE = 0
PRIMARY_CANDIDATES = (
    "M-N5_SMALL_MLP_BASELINE",
    "M-N5_CONV1D_GAP_TINY",
    "M-N5_DILATED_CONV1D_GAP_TINY",
)
DIAGNOSTIC_CANDIDATE = "M-N5_LINEAR_DIAGNOSTIC"
SEEDS = (42, 2026)
LEARNING_RATE = 1e-3
BATCH_SIZE = 32
MAX_EPOCHS = 120
PATIENCE = 15
PARAM_BUDGET = 50_000
INPUT_LEN = SAMPLE_COUNT
N_CLASSES = 3

CONTRACT_PATH = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"
RECIPE_PATH = ROOT / "config/mmwave/m_n5_training_recipe.json"
INDEX_PATH = ROOT / "datasets/mmwave/manifests/m_n4_canonical/window_index.jsonl"
SPLIT_PATH = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"
PROVENANCE_PATH = ROOT / "datasets/mmwave/manifests/a6_full_conversion/full_provenance_manifest.jsonl"
MANIFEST_PATH = ROOT / "datasets/mmwave/manifests/m_n5_candidate_runs.json"
OUT_DIR = ROOT / "tmp/mmwave_m_n5"
CACHE_DIR = OUT_DIR / "public_phase_cache"
TENSOR_DIR = OUT_DIR / "tensors"
MODEL_DIR = OUT_DIR / "models"
MN3_CACHE = ROOT / "tmp/mmwave_m_n3/public_phase_cache"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def assert_frozen_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    if contract["contract_id"] != CONTRACT_ID:
        raise RuntimeError("M_N4_CONTRACT_ID_MISMATCH")
    shape = contract["resampling"]["input_shape"]
    if shape != [1, 240, 1]:
        raise RuntimeError(f"UNEXPECTED_INPUT_SHAPE:{shape}")
    if contract["resampling"]["sample_count"] != 240:
        raise RuntimeError("UNEXPECTED_SAMPLE_COUNT")
    if contract["resampling"]["target_rate_hz"] != 8.0:
        raise RuntimeError("UNEXPECTED_RATE")
    if contract["scale"]["method"] != "WINDOW_LOCAL_MAD":
        raise RuntimeError("UNEXPECTED_SCALE")
    if contract["derivative"]["representation"] != "TIME_AWARE_FIRST_DERIVATIVE":
        raise RuntimeError("UNEXPECTED_REPRESENTATION")
    return contract


def load_supervised_index() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Load TRAIN/VAL supervised rows only. Heldout rows are counted, never materialized."""
    split = load_json(SPLIT_PATH)
    assignment = {sid: name for name, ids in split["subject_ids"].items() for sid in ids}
    train_rows: list[dict[str, Any]] = []
    val_rows: list[dict[str, Any]] = []
    heldout_supervised = 0
    heldout_rows_seen = 0
    for row in load_jsonl(INDEX_PATH):
        expected = assignment[row["subject_id"]]
        if row["split"] != expected:
            raise RuntimeError(f"SPLIT_INDEX_MISMATCH:{row['window_id']}")
        if row["split"] == FORBIDDEN_SPLIT:
            heldout_rows_seen += 1
            if row.get("supervised_eligible"):
                heldout_supervised += 1
            continue
        if row["split"] not in ALLOWED_SPLITS:
            raise RuntimeError(f"UNEXPECTED_SPLIT:{row['split']}")
        if not row.get("supervised_eligible"):
            continue
        if row.get("safenest_label") not in CLASS_TO_ID:
            raise RuntimeError(f"NON_CLASS_SUPERVISED:{row['window_id']}")
        if row["split"] == "TRAIN":
            train_rows.append(row)
        else:
            val_rows.append(row)
    train_rows.sort(key=lambda r: r["window_id"])
    val_rows.sort(key=lambda r: r["window_id"])
    meta = {
        "heldout_rows_seen_in_index": heldout_rows_seen,
        "heldout_supervised_eligible_count": heldout_supervised,
        "heldout_tensors_materialized": 0,
        "heldout_inference_runs": NEW_MODEL_HELDOUT_TEST_INFERENCE,
        "team_mr60_supervised": False,
    }
    return train_rows, val_rows, meta


def _cache_path(recording_id: str) -> Path:
    safe = recording_id.replace("/", "_")
    return CACHE_DIR / f"{safe}.npz"


def cached_public_series(recording_id: str, prow: dict[str, Any]):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _cache_path(recording_id)
    if dest.exists():
        blob = np.load(dest)
        from scripts.mmwave_m_n2_common_representation import Series

        return Series(
            blob["values"],
            blob["elapsed"],
            float(blob["median_dt"][0]),
            int(blob["large_gap_count"][0]),
            0,
            ["CACHED_A2_NATIVE_UNWRAP"],
        )
    mn3 = MN3_CACHE / f"{recording_id}.npz"
    if mn3.exists():
        blob = np.load(mn3)
        np.savez(
            dest,
            values=blob["values"],
            elapsed=blob["elapsed"],
            median_dt=np.array([float(blob["median_dt"][0])]),
            large_gap_count=np.array([int(blob["large_gap_count"][0])]),
        )
        from scripts.mmwave_m_n2_common_representation import Series

        return Series(
            blob["values"],
            blob["elapsed"],
            float(blob["median_dt"][0]),
            int(blob["large_gap_count"][0]),
            0,
            ["REUSED_MN3_A2_NATIVE_UNWRAP_CACHE"],
        )
    series = load_public_series(recording_id, prow)
    np.savez(
        dest,
        values=series.values,
        elapsed=series.elapsed_s,
        median_dt=np.array([series.median_dt]),
        large_gap_count=np.array([series.large_gap_count]),
    )
    return series


def load_train_val_provenance(recording_ids: set[str]) -> dict[str, dict[str, Any]]:
    wanted = set(recording_ids)
    found: dict[str, dict[str, Any]] = {}
    with PROVENANCE_PATH.open() as handle:
        for line in handle:
            row = json.loads(line)
            rid = row["recording_id"]
            if rid in wanted and rid not in found:
                found[rid] = row
                if len(found) == len(wanted):
                    break
    missing = wanted - set(found)
    if missing:
        raise RuntimeError(f"PROVENANCE_MISSING:{sorted(missing)[:8]}")
    return found


def _materialize_split(
    rows: list[dict[str, Any]],
    provenance: dict[str, dict[str, Any]],
    series_cache: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, list[str], list[str], list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[int] = []
    subjects: list[str] = []
    window_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        if row["split"] == FORBIDDEN_SPLIT:
            raise RuntimeError("HELDOUT_MATERIALIZATION_ATTEMPTED")
        if i == 1 or i % 20 == 0 or i == len(rows):
            print(f"  materializing {row['split']} {i}/{len(rows)}", flush=True)
        rid = row["recording_id"]
        if rid not in series_cache:
            series_cache[rid] = cached_public_series(rid, provenance[rid])
        series = series_cache[rid]
        t_start = float(row["source_start_index"]) * float(series.median_dt)
        try:
            win = canonical_from_public_native(series.elapsed_s, series.values, t_start)
        except CanonicalContractError as exc:
            failures.append(
                {
                    "window_id": row["window_id"],
                    "split": row["split"],
                    "reason": str(exc),
                }
            )
            continue
        values = np.asarray(win.values, dtype=np.float32)
        if values.shape != (INPUT_LEN,):
            failures.append({"window_id": row["window_id"], "split": row["split"], "reason": "SHAPE"})
            continue
        if not np.all(np.isfinite(values)):
            failures.append({"window_id": row["window_id"], "split": row["split"], "reason": "NONFINITE"})
            continue
        xs.append(values.reshape(INPUT_LEN, 1))
        ys.append(int(row["safenest_label_id"]))
        subjects.append(row["subject_id"])
        window_ids.append(row["window_id"])
    if not xs:
        raise RuntimeError("NO_TENSORS_MATERIALIZED")
    x = np.stack(xs, axis=0).astype(np.float32)
    y = np.asarray(ys, dtype=np.int32)
    return x, y, subjects, window_ids, failures


def generate_train_val_tensors(force: bool = False) -> dict[str, Any]:
    TENSOR_DIR.mkdir(parents=True, exist_ok=True)
    cache_npz = TENSOR_DIR / "train_val.npz"
    cache_meta = TENSOR_DIR / "sanity.json"
    index_sha = sha256_file(INDEX_PATH)
    split_sha = sha256_file(SPLIT_PATH)
    if cache_npz.exists() and cache_meta.exists() and not force:
        meta = load_json(cache_meta)
        if (
            meta.get("contract_id") == CONTRACT_ID
            and meta.get("window_index_sha256") == index_sha
            and meta.get("split_sha256") == split_sha
            and meta.get("heldout_tensors_materialized") == 0
        ):
            blob = np.load(cache_npz, allow_pickle=False)
            meta["x_train"] = blob["x_train"]
            meta["y_train"] = blob["y_train"]
            meta["subjects_train"] = blob["subjects_train"].astype(str).tolist()
            meta["window_ids_train"] = blob["window_ids_train"].astype(str).tolist()
            meta["x_val"] = blob["x_val"]
            meta["y_val"] = blob["y_val"]
            meta["subjects_val"] = blob["subjects_val"].astype(str).tolist()
            meta["window_ids_val"] = blob["window_ids_val"].astype(str).tolist()
            meta["cache_hit"] = True
            return meta

    train_rows, val_rows, heldout_meta = load_supervised_index()
    train_ids = {r["recording_id"] for r in train_rows}
    val_ids = {r["recording_id"] for r in val_rows}
    if train_ids & val_ids:
        raise RuntimeError("TRAIN_VAL_RECORDING_OVERLAP")
    provenance = load_train_val_provenance(train_ids | val_ids)
    series_cache: dict[str, Any] = {}
    x_train, y_train, sub_train, win_train, fail_train = _materialize_split(
        train_rows, provenance, series_cache
    )
    x_val, y_val, sub_val, win_val, fail_val = _materialize_split(
        val_rows, provenance, series_cache
    )
    if set(sub_train) & set(sub_val):
        raise RuntimeError("SUBJECT_OVERLAP_IN_TENSORS")

    meta = {
        "contract_id": CONTRACT_ID,
        "window_index_sha256": index_sha,
        "split_sha256": split_sha,
        "cache_hit": False,
        "x_train_shape": list(x_train.shape),
        "x_val_shape": list(x_val.shape),
        "dtype": str(x_train.dtype),
        "finite_fraction_train": float(np.mean(np.isfinite(x_train))),
        "finite_fraction_val": float(np.mean(np.isfinite(x_val))),
        "train_window_count": int(x_train.shape[0]),
        "val_window_count": int(x_val.shape[0]),
        "train_subject_count": len(set(sub_train)),
        "val_subject_count": len(set(sub_val)),
        "subject_overlap": 0,
        "train_class_counts": {LABEL_NAMES[i]: int(np.sum(y_train == i)) for i in range(N_CLASSES)},
        "val_class_counts": {LABEL_NAMES[i]: int(np.sum(y_val == i)) for i in range(N_CLASSES)},
        "expected_train_windows": 337,
        "expected_val_windows": 70,
        "transform_failures": fail_train + fail_val,
        "ambiguous_used_in_supervised_training": False,
        **heldout_meta,
    }
    np.savez(
        cache_npz,
        x_train=x_train,
        y_train=y_train,
        subjects_train=np.asarray(sub_train),
        window_ids_train=np.asarray(win_train),
        x_val=x_val,
        y_val=y_val,
        subjects_val=np.asarray(sub_val),
        window_ids_val=np.asarray(win_val),
    )
    serializable = {k: v for k, v in meta.items() if k not in {"x_train", "y_train", "x_val", "y_val"}}
    cache_meta.write_text(json.dumps(serializable, indent=2) + "\n")
    meta["x_train"] = x_train
    meta["y_train"] = y_train
    meta["subjects_train"] = sub_train
    meta["window_ids_train"] = win_train
    meta["x_val"] = x_val
    meta["y_val"] = y_val
    meta["subjects_val"] = sub_val
    meta["window_ids_val"] = win_val
    return meta


def dataset_sanity(bundle: dict[str, Any]) -> dict[str, Any]:
    x_train = bundle["x_train"]
    x_val = bundle["x_val"]
    y_train = bundle["y_train"]
    y_val = bundle["y_val"]
    checks = {
        "train_tensor_count": int(x_train.shape[0]),
        "val_tensor_count": int(x_val.shape[0]),
        "shape_train": list(x_train.shape),
        "shape_val": list(x_val.shape),
        "finite_fraction_train": float(np.mean(np.isfinite(x_train))),
        "finite_fraction_val": float(np.mean(np.isfinite(x_val))),
        "train_class_counts": {LABEL_NAMES[i]: int(np.sum(y_train == i)) for i in range(N_CLASSES)},
        "val_class_counts": {LABEL_NAMES[i]: int(np.sum(y_val == i)) for i in range(N_CLASSES)},
        "unique_train_subjects": len(set(bundle["subjects_train"])),
        "unique_val_subjects": len(set(bundle["subjects_val"])),
        "subject_overlap": len(set(bundle["subjects_train"]) & set(bundle["subjects_val"])),
        "heldout_inference_runs": NEW_MODEL_HELDOUT_TEST_INFERENCE,
    }
    if checks["shape_train"][1:] != [240, 1] or checks["shape_val"][1:] != [240, 1]:
        raise RuntimeError(f"BAD_TENSOR_SHAPE:{checks['shape_train']}/{checks['shape_val']}")
    if checks["finite_fraction_train"] != 1.0 or checks["finite_fraction_val"] != 1.0:
        raise RuntimeError("NONFINITE_TENSORS")
    if checks["unique_train_subjects"] != 77 or checks["unique_val_subjects"] != 17:
        raise RuntimeError("SUBJECT_COUNT_MISMATCH")
    if checks["subject_overlap"] != 0:
        raise RuntimeError("SUBJECT_OVERLAP")
    for name in LABEL_NAMES:
        if checks["train_class_counts"][name] == 0 or checks["val_class_counts"][name] == 0:
            raise RuntimeError(f"MISSING_CLASS:{name}")
    return checks


def _tf():
    import tensorflow as tf

    return tf


def configure_determinism(seed: int) -> dict[str, Any]:
    tf = _tf()
    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["TF_DETERMINISTIC_OPS"] = "1"
    random.seed(seed)
    np.random.seed(seed)
    tf.keras.backend.clear_session()
    gc.collect()
    tf.random.set_seed(seed)
    note = "DETERMINISM_REQUESTED"
    op_enabled = False
    try:
        tf.config.experimental.enable_op_determinism()
        op_enabled = True
        note = "TF_OP_DETERMINISM_ENABLED"
    except Exception as exc:  # noqa: BLE001
        note = f"TF_OP_DETERMINISM_UNAVAILABLE:{type(exc).__name__}"
    try:
        tf.config.threading.set_inter_op_parallelism_threads(1)
        tf.config.threading.set_intra_op_parallelism_threads(1)
    except RuntimeError:
        note += ";THREAD_POOL_ALREADY_INITIALIZED"
    return {"seed": seed, "determinism_note": note, "tf_op_determinism": op_enabled}


def build_candidate(candidate_id: str):
    tf = _tf()
    inp = tf.keras.Input(shape=(INPUT_LEN, 1), dtype="float32", name="r2_window")
    if candidate_id == "M-N5_SMALL_MLP_BASELINE":
        x = tf.keras.layers.Flatten(name="flatten")(inp)
        x = tf.keras.layers.Dense(32, activation="relu", name="dense_32")(x)
        x = tf.keras.layers.Dropout(0.20, name="dropout_0_20")(x)
        out = tf.keras.layers.Dense(N_CLASSES, activation="softmax", name="softmax_3")(x)
    elif candidate_id == "M-N5_CONV1D_GAP_TINY":
        x = tf.keras.layers.Conv1D(16, 7, padding="same", activation="relu", name="conv1d_16_k7")(inp)
        x = tf.keras.layers.Conv1D(24, 5, strides=2, padding="same", activation="relu", name="conv1d_24_k5_s2")(x)
        x = tf.keras.layers.Conv1D(24, 5, padding="same", activation="relu", name="conv1d_24_k5")(x)
        x = tf.keras.layers.GlobalAveragePooling1D(name="gap")(x)
        out = tf.keras.layers.Dense(N_CLASSES, activation="softmax", name="softmax_3")(x)
    elif candidate_id == "M-N5_DILATED_CONV1D_GAP_TINY":
        x = tf.keras.layers.Conv1D(
            16, 5, dilation_rate=1, padding="same", activation="relu", name="conv1d_16_k5_d1"
        )(inp)
        x = tf.keras.layers.Conv1D(
            24, 5, dilation_rate=2, padding="same", activation="relu", name="conv1d_24_k5_d2"
        )(x)
        x = tf.keras.layers.Conv1D(
            24, 5, dilation_rate=4, padding="same", activation="relu", name="conv1d_24_k5_d4"
        )(x)
        x = tf.keras.layers.GlobalAveragePooling1D(name="gap")(x)
        out = tf.keras.layers.Dense(N_CLASSES, activation="softmax", name="softmax_3")(x)
    elif candidate_id == DIAGNOSTIC_CANDIDATE:
        x = tf.keras.layers.Flatten(name="flatten")(inp)
        out = tf.keras.layers.Dense(N_CLASSES, activation="softmax", name="softmax_3")(x)
    else:
        raise ValueError(f"UNKNOWN_CANDIDATE:{candidate_id}")
    model = tf.keras.Model(inp, out, name=candidate_id)
    n_train = int(sum(int(np.prod(w.shape)) for w in model.trainable_weights))
    if candidate_id in PRIMARY_CANDIDATES and n_train > PARAM_BUDGET:
        raise RuntimeError(f"PARAM_BUDGET_EXCEEDED:{candidate_id}:{n_train}")
    return model


def trainable_parameter_count(model) -> int:
    return int(sum(int(np.prod(w.shape)) for w in model.trainable_weights))


def _dataset(x: np.ndarray, y: np.ndarray, batch_size: int, seed: int, shuffle: bool):
    tf = _tf()
    ds = tf.data.Dataset.from_tensor_slices((x, y))
    if shuffle:
        ds = ds.shuffle(buffer_size=int(x.shape[0]), seed=seed, reshuffle_each_iteration=True)
    return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)


def evaluate_val(
    model,
    x_val: np.ndarray,
    y_val: np.ndarray,
    subjects_val: list[str],
) -> dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        precision_recall_fscore_support,
    )

    probs = model.predict(x_val, batch_size=BATCH_SIZE, verbose=0)
    probs = np.asarray(probs, dtype=np.float64)
    finite = bool(np.all(np.isfinite(probs)))
    row_sums = np.sum(probs, axis=1) if probs.ndim == 2 else np.array([])
    sum_ok = bool(row_sums.size and np.allclose(row_sums, 1.0, atol=1e-5))
    if not finite or probs.shape != (x_val.shape[0], N_CLASSES):
        return {
            "val_loss": None,
            "val_accuracy": None,
            "val_macro_f1": None,
            "val_balanced_accuracy": None,
            "per_class": {},
            "confusion_matrix": [],
            "predicted_class_counts": {},
            "collapse_status": "NUMERICAL_FAILURE",
            "probability_finite": finite,
            "probability_row_sum_ok": False,
            "n_predicted_classes": 0,
            "subject_summary": {},
        }

    y_pred = np.argmax(probs, axis=1).astype(np.int32)
    eps = 1e-12
    clipped = np.clip(probs[np.arange(len(y_val)), y_val], eps, 1.0)
    val_loss = float(-np.mean(np.log(clipped)))
    acc = float(accuracy_score(y_val, y_pred))
    macro_f1 = float(f1_score(y_val, y_pred, average="macro", labels=[0, 1, 2], zero_division=0))
    bal_acc = float(balanced_accuracy_score(y_val, y_pred))
    prec, rec, f1, support = precision_recall_fscore_support(
        y_val, y_pred, labels=[0, 1, 2], zero_division=0
    )
    per_class = {}
    for i, name in enumerate(LABEL_NAMES):
        per_class[name] = {
            "precision": round(float(prec[i]), 6),
            "recall": round(float(rec[i]), 6),
            "f1": round(float(f1[i]), 6),
            "support": int(support[i]),
        }
    cm = confusion_matrix(y_val, y_pred, labels=[0, 1, 2]).astype(int)
    pred_counts = {LABEL_NAMES[i]: int(np.sum(y_pred == i)) for i in range(N_CLASSES)}
    n_pred_classes = int(sum(1 for v in pred_counts.values() if v > 0))
    n_true_classes = int(sum(1 for i in range(N_CLASSES) if int(np.sum(y_val == i)) > 0))
    if n_pred_classes < n_true_classes:
        collapse = "CLASS_COLLAPSE"
    else:
        collapse = "NON_DEGENERATE"

    per_subject_acc: list[float] = []
    n_correct_subjects = 0
    for sid in sorted(set(subjects_val)):
        mask = np.asarray([s == sid for s in subjects_val])
        yt = y_val[mask]
        yp = y_pred[mask]
        acc_s = float(np.mean(yt == yp)) if yt.size else 0.0
        per_subject_acc.append(acc_s)
        if int(np.sum(yt == yp)) >= 1:
            n_correct_subjects += 1
    subject_summary = {
        "n_val_subjects": len(set(subjects_val)),
        "n_subjects_with_at_least_one_correct": n_correct_subjects,
        "median_per_subject_accuracy": round(float(np.median(per_subject_acc)), 6) if per_subject_acc else None,
        "minimum_per_subject_accuracy": round(float(np.min(per_subject_acc)), 6) if per_subject_acc else None,
        "per_subject_macro_f1_invented": False,
    }
    return {
        "val_loss": round(val_loss, 6),
        "val_accuracy": round(acc, 6),
        "val_macro_f1": round(macro_f1, 6),
        "val_balanced_accuracy": round(bal_acc, 6),
        "per_class": per_class,
        "per_class_recall": {name: per_class[name]["recall"] for name in LABEL_NAMES},
        "confusion_matrix": cm.tolist(),
        "predicted_class_counts": pred_counts,
        "collapse_status": collapse,
        "probability_finite": True,
        "probability_row_sum_ok": sum_ok,
        "n_predicted_classes": n_pred_classes,
        "subject_summary": subject_summary,
    }


def classify_run(history: dict[str, list[float]], metrics: dict[str, Any]) -> str:
    if metrics.get("collapse_status") == "NUMERICAL_FAILURE":
        return "NUMERICAL_FAILURE"
    val_loss = history.get("val_loss") or []
    if not val_loss or not all(np.isfinite(v) for v in val_loss):
        return "NUMERICAL_FAILURE"
    improved = float(np.min(val_loss)) < float(val_loss[0]) - 1e-4
    if metrics.get("collapse_status") == "CLASS_COLLAPSE":
        return "CLASS_COLLAPSE"
    if not improved and metrics.get("n_predicted_classes", 0) < N_CLASSES:
        return "TRAINING_FAILURE"
    if not improved and float(metrics.get("val_macro_f1") or 0) <= 0.34:
        return "TRAINING_FAILURE"
    return "NON_DEGENERATE"


def viability(collapse_status: str) -> str:
    if collapse_status == "NON_DEGENERATE":
        return "VIABLE_FOR_M_N6"
    return "NOT_VIABLE"


def train_one(
    candidate_id: str,
    seed: int,
    bundle: dict[str, Any],
    *,
    diagnostic: bool = False,
) -> dict[str, Any]:
    tf = _tf()
    det = configure_determinism(seed)
    model = build_candidate(candidate_id)
    n_params = trainable_parameter_count(model)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=["accuracy"],
    )
    stopper = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=PATIENCE,
        restore_best_weights=True,
        verbose=0,
    )
    train_ds = _dataset(bundle["x_train"], bundle["y_train"], BATCH_SIZE, seed, shuffle=True)
    val_ds = _dataset(bundle["x_val"], bundle["y_val"], BATCH_SIZE, seed, shuffle=False)
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=MAX_EPOCHS,
        callbacks=[stopper],
        verbose=0,
    )
    hist = {k: [float(v) for v in vals] for k, vals in history.history.items()}
    best_epoch = int(np.argmin(hist["val_loss"])) + 1 if hist.get("val_loss") else None
    metrics = evaluate_val(model, bundle["x_val"], bundle["y_val"], bundle["subjects_val"])
    collapse = classify_run(hist, metrics)
    metrics["collapse_status"] = collapse

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{candidate_id}_seed{seed}"
    model_path = MODEL_DIR / f"{stem}.keras"
    model.save(model_path)
    artifact_sha = sha256_file(model_path)
    run = {
        "candidate_id": candidate_id,
        "architecture_family": candidate_id.replace("M-N5_", ""),
        "role": "DIAGNOSTIC_ONLY" if diagnostic else "PRIMARY",
        "seed": seed,
        "input_contract": CONTRACT_ID,
        "train_subject_count": bundle["train_subject_count"],
        "val_subject_count": bundle["val_subject_count"],
        "train_window_count": bundle["train_window_count"],
        "val_window_count": bundle["val_window_count"],
        "parameter_count": n_params,
        "best_epoch": best_epoch,
        "epochs_run": len(hist.get("loss", [])),
        "artifact_path": str(model_path.relative_to(ROOT)),
        "artifact_sha256": artifact_sha,
        "artifact_size": int(model_path.stat().st_size),
        "val_loss": metrics["val_loss"],
        "val_accuracy": metrics["val_accuracy"],
        "val_macro_f1": metrics["val_macro_f1"],
        "val_balanced_accuracy": metrics["val_balanced_accuracy"],
        "per_class": metrics["per_class"],
        "per_class_recall": metrics["per_class_recall"],
        "confusion_matrix": metrics["confusion_matrix"],
        "predicted_class_counts": metrics["predicted_class_counts"],
        "collapse_status": collapse,
        "viability": "DIAGNOSTIC_ONLY" if diagnostic else viability(collapse),
        "subject_summary": metrics["subject_summary"],
        "probability_finite": metrics["probability_finite"],
        "probability_row_sum_ok": metrics["probability_row_sum_ok"],
        "training_history": {
            "loss": hist.get("loss", []),
            "val_loss": hist.get("val_loss", []),
            "accuracy": hist.get("accuracy", []),
            "val_accuracy": hist.get("val_accuracy", []),
        },
        "tensorflow_version": str(tf.__version__),
        "source_git_sha": git_sha(),
        "determinism": det,
        "class_weighting": "UNWEIGHTED",
        "heldout_inference_runs": NEW_MODEL_HELDOUT_TEST_INFERENCE,
        "final_model_selected": False,
    }
    (MODEL_DIR / f"{stem}.meta.json").write_text(json.dumps(run, indent=2) + "\n")
    del model
    tf.keras.backend.clear_session()
    gc.collect()
    return run


def reload_and_check(run: dict[str, Any], x_val: np.ndarray) -> dict[str, str]:
    tf = _tf()
    path = ROOT / run["artifact_path"]
    model = tf.keras.models.load_model(path)
    in_shape = tuple(model.inputs[0].shape)
    out_shape = tuple(model.outputs[0].shape)
    probs = model.predict(x_val[: min(8, x_val.shape[0])], verbose=0)
    finite = bool(np.all(np.isfinite(probs)))
    sums = np.sum(probs, axis=1)
    sum_ok = bool(np.allclose(sums, 1.0, atol=1e-5))
    del model
    tf.keras.backend.clear_session()
    return {
        "input_shape": "PASS" if in_shape[1:] == (240, 1) else "FAIL",
        "output_shape": "PASS" if out_shape[1:] == (3,) else "FAIL",
        "reload": "PASS" if path.is_file() else "FAIL",
        "probability_sanity": "PASS" if finite and sum_ok else "FAIL",
    }


def focused_validation(bundle: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, str]:
    checks = {
        "input_shape": "PASS"
        if bundle["x_train"].shape[1:] == (240, 1) and bundle["x_val"].shape[1:] == (240, 1)
        else "FAIL",
        "finite_tensors": "PASS"
        if float(np.mean(np.isfinite(bundle["x_train"]))) == 1.0
        and float(np.mean(np.isfinite(bundle["x_val"]))) == 1.0
        else "FAIL",
        "subject_isolation": "PASS"
        if not (set(bundle["subjects_train"]) & set(bundle["subjects_val"]))
        else "FAIL",
        "three_class_presence": "PASS"
        if all(int(np.sum(bundle["y_train"] == i)) > 0 and int(np.sum(bundle["y_val"] == i)) > 0 for i in range(3))
        else "FAIL",
        "model_reload": "PASS",
        "probability_sanity": "PASS",
        "heldout_inference": "PASS" if NEW_MODEL_HELDOUT_TEST_INFERENCE == 0 else "FAIL",
        "manifest_code_consistency": "PASS",
    }
    for run in runs:
        if run.get("role") == "DIAGNOSTIC_ONLY":
            continue
        reload = reload_and_check(run, bundle["x_val"])
        if reload["reload"] != "PASS" or reload["input_shape"] != "PASS" or reload["output_shape"] != "PASS":
            checks["model_reload"] = "FAIL"
        if reload["probability_sanity"] != "PASS":
            checks["probability_sanity"] = "FAIL"
        if run["input_contract"] != CONTRACT_ID:
            checks["manifest_code_consistency"] = "FAIL"
        if run["candidate_id"] not in PRIMARY_CANDIDATES:
            checks["manifest_code_consistency"] = "FAIL"
    return checks


def architecture_family(candidate_id: str) -> str:
    return {
        "M-N5_SMALL_MLP_BASELINE": "SMALL_MLP",
        "M-N5_CONV1D_GAP_TINY": "CONV1D_GAP",
        "M-N5_DILATED_CONV1D_GAP_TINY": "DILATED_CONV1D_GAP",
        DIAGNOSTIC_CANDIDATE: "LINEAR_DIAGNOSTIC",
    }[candidate_id]


def write_manifest(bundle: dict[str, Any], runs: list[dict[str, Any]], checks: dict[str, str]) -> dict[str, Any]:
    primary = [r for r in runs if r["role"] == "PRIMARY"]
    families = {cid: [] for cid in PRIMARY_CANDIDATES}
    for run in primary:
        families[run["candidate_id"]].append(run)
    viable = sorted({r["candidate_id"] for r in primary if r["viability"] == "VIABLE_FOR_M_N6"})
    not_viable = sorted(set(PRIMARY_CANDIDATES) - set(viable))
    nondeg = sum(1 for r in primary if r["collapse_status"] == "NON_DEGENERATE")
    trained_ok = len(primary) == 6 and all(r.get("best_epoch") is not None for r in primary)
    major_weakness = False
    for run in primary:
        rec = run.get("per_class_recall") or {}
        if rec.get("RAPID_OR_ABNORMAL", 1.0) < 0.25:
            major_weakness = True
    f1s = [r["val_macro_f1"] for r in primary if r.get("val_macro_f1") is not None]
    seed_sensitive = False
    for cid, group in families.items():
        if len(group) == 2 and None not in (group[0].get("val_macro_f1"), group[1].get("val_macro_f1")):
            if abs(group[0]["val_macro_f1"] - group[1]["val_macro_f1"]) >= 0.08:
                seed_sensitive = True
    if not trained_ok or nondeg == 0 or not viable:
        gate = "FAIL"
    elif seed_sensitive or major_weakness or nondeg < 6:
        gate = "PASS_WITH_LIMITATIONS"
    else:
        gate = "PASS"

    manifest = {
        "phase": "M-N5",
        "contract_id": CONTRACT_ID,
        "input_shape": [1, 240, 1],
        "representation": "R2_TIME_AWARE_FIRST_DERIVATIVE",
        "scale": "WINDOW_LOCAL_MAD",
        "window_seconds": 30.0,
        "rate_hz": 8.0,
        "source_git_sha": git_sha(),
        "tensorflow_version": primary[0]["tensorflow_version"] if primary else None,
        "training_recipe": {
            "optimizer": "Adam",
            "learning_rate": LEARNING_RATE,
            "loss": "SparseCategoricalCrossentropy",
            "class_weighting": "UNWEIGHTED",
            "batch_size": BATCH_SIZE,
            "maximum_epochs": MAX_EPOCHS,
            "early_stopping": {"monitor": "val_loss", "patience": PATIENCE, "restore_best_weights": True},
            "seeds": list(SEEDS),
        },
        "dataset": {
            "train_subject_count": bundle["train_subject_count"],
            "val_subject_count": bundle["val_subject_count"],
            "train_window_count": bundle["train_window_count"],
            "val_window_count": bundle["val_window_count"],
            "train_class_counts": bundle["train_class_counts"],
            "val_class_counts": bundle["val_class_counts"],
            "subject_overlap": 0,
            "ambiguous_used_in_supervised_training": False,
            "transform_failures": bundle.get("transform_failures", []),
        },
        "heldout": {
            "NEW_MODEL_HELDOUT_TEST_INFERENCE": 0,
            "heldout_performance_inspected": False,
            "heldout_used_for_architecture_or_seed_selection": False,
            "heldout_tensors_materialized": 0,
        },
        "team_mr60": {
            "included_in_supervised_train": False,
            "included_in_val": False,
            "breath_rate_raw_used_as_gt": False,
            "paced_cue_used_as_gt": False,
        },
        "runs": [
            {
                "candidate_id": r["candidate_id"],
                "architecture_family": architecture_family(r["candidate_id"]),
                "role": r["role"],
                "seed": r["seed"],
                "input_contract": r["input_contract"],
                "train_subject_count": r["train_subject_count"],
                "val_subject_count": r["val_subject_count"],
                "train_window_count": r["train_window_count"],
                "val_window_count": r["val_window_count"],
                "parameter_count": r["parameter_count"],
                "best_epoch": r["best_epoch"],
                "artifact_path": r["artifact_path"],
                "artifact_sha256": r["artifact_sha256"],
                "artifact_size": r["artifact_size"],
                "val_accuracy": r["val_accuracy"],
                "val_macro_f1": r["val_macro_f1"],
                "val_loss": r["val_loss"],
                "val_balanced_accuracy": r["val_balanced_accuracy"],
                "per_class_recall": r["per_class_recall"],
                "per_class": r["per_class"],
                "confusion_matrix": r["confusion_matrix"],
                "predicted_class_counts": r["predicted_class_counts"],
                "collapse_status": r["collapse_status"],
                "viability": r["viability"],
                "subject_summary": r["subject_summary"],
                "tensorflow_version": r["tensorflow_version"],
                "source_git_sha": r["source_git_sha"],
                "determinism": r["determinism"],
            }
            for r in runs
        ],
        "candidate_viability": {
            "VIABLE_FOR_M_N6": viable,
            "NOT_VIABLE": not_viable,
            "FINAL_SELECTED_MODEL": None,
        },
        "val_macro_f1_range": {
            "min": min(f1s) if f1s else None,
            "max": max(f1s) if f1s else None,
        },
        "seed_sensitivity_flagged": seed_sensitive,
        "major_class_weakness_flagged": major_weakness,
        "focused_validation": checks,
        "gate": gate,
        "at_least_one_credible_candidate_for_m_n6": bool(viable),
        "m_n6_authorized": bool(viable) and gate != "FAIL",
        "candidate_binaries_committed": False,
        "m_n4_contract_modified": False,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> int:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    assert_frozen_contract()
    print("M-N5 generating TRAIN/VAL canonical tensors (heldout excluded)...", flush=True)
    bundle = generate_train_val_tensors()
    sanity = dataset_sanity(bundle)
    print(json.dumps({"dataset_sanity": sanity, "failures": bundle.get("transform_failures", [])}, indent=2), flush=True)
    runs: list[dict[str, Any]] = []
    for candidate_id in PRIMARY_CANDIDATES:
        for seed in SEEDS:
            print(f"Training {candidate_id} seed={seed}", flush=True)
            run = train_one(candidate_id, seed, bundle, diagnostic=False)
            print(
                json.dumps(
                    {
                        "candidate_id": candidate_id,
                        "seed": seed,
                        "params": run["parameter_count"],
                        "best_epoch": run["best_epoch"],
                        "val_macro_f1": run["val_macro_f1"],
                        "collapse_status": run["collapse_status"],
                        "viability": run["viability"],
                    }
                ),
                flush=True,
            )
            runs.append(run)
    print(f"Training diagnostic {DIAGNOSTIC_CANDIDATE} seed=42", flush=True)
    runs.append(train_one(DIAGNOSTIC_CANDIDATE, 42, bundle, diagnostic=True))
    checks = focused_validation(bundle, runs)
    manifest = write_manifest(bundle, runs, checks)
    print(json.dumps({"gate": manifest["gate"], "focused_validation": checks, "manifest": str(MANIFEST_PATH.relative_to(ROOT))}, indent=2))
    return 0 if manifest["gate"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
