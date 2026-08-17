#!/usr/bin/env python3
"""M-N6 Stage A: VAL-only candidate lock. Heldout tensors are never loaded here."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_m_n4_canonical import CONTRACT_ID  # noqa: E402

SELECTION_ID = "MMWAVE_M_N6_SELECTED_FLOAT_V1"
PRIMARY_FAMILIES = (
    "M-N5_SMALL_MLP_BASELINE",
    "M-N5_CONV1D_GAP_TINY",
    "M-N5_DILATED_CONV1D_GAP_TINY",
)
SEEDS = (42, 2026)
HELDOUT_INFERENCE_BEFORE_SELECTION_LOCK = 0
MANIFEST_PATH = ROOT / "datasets/mmwave/manifests/m_n5_candidate_runs.json"
LOCK_PATH = ROOT / "config/mmwave/m_n6_selected_candidate_lock.json"
LOCKED_DIR = ROOT / "models/mmwave/m_n6"
LOCKED_ARTIFACT_NAME = "MMWAVE_M_N6_SELECTED_FLOAT_V1.keras"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_primary_runs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    runs = [
        row
        for row in manifest["runs"]
        if row.get("role") == "PRIMARY" and row.get("candidate_id") in PRIMARY_FAMILIES
    ]
    if len(runs) != 6:
        raise RuntimeError(f"EXPECTED_SIX_PRIMARY_RUNS:{len(runs)}")
    return runs


def family_summary(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in PRIMARY_FAMILIES:
        group = [r for r in runs if r["candidate_id"] == family]
        seeds = sorted(int(r["seed"]) for r in group)
        if seeds != list(SEEDS):
            raise RuntimeError(f"MISSING_FIXED_SEEDS:{family}:{seeds}")
        if any(r.get("collapse_status") != "NON_DEGENERATE" for r in group):
            continue
        f1s = [float(r["val_macro_f1"]) for r in group]
        rapids = [float(r["per_class_recall"]["RAPID_OR_ABNORMAL"]) for r in group]
        mean_f1 = float(sum(f1s) / len(f1s))
        rows.append(
            {
                "candidate_id": family,
                "architecture_family": group[0]["architecture_family"],
                "n_nondegenerate_seeds": len(group),
                "mean_val_macro_f1": round(mean_f1, 6),
                "seed_macro_f1": {str(r["seed"]): r["val_macro_f1"] for r in group},
                "seed_f1_abs_delta": round(abs(f1s[0] - f1s[1]), 6),
                "mean_rapid_recall": round(float(sum(rapids) / len(rapids)), 6),
                "min_rapid_recall": round(min(rapids), 6),
                "parameter_count": int(group[0]["parameter_count"]),
            }
        )
    if not rows:
        raise RuntimeError("NO_NONDEGENERATE_FAMILY")
    rows.sort(
        key=lambda r: (
            -r["mean_val_macro_f1"],
            -r["min_rapid_recall"],
            r["seed_f1_abs_delta"],
            r["parameter_count"],
            r["candidate_id"],
        )
    )
    return rows


def select_exact_run(runs: list[dict[str, Any]], family: str) -> dict[str, Any]:
    group = [r for r in runs if r["candidate_id"] == family]
    def sort_key(r: dict[str, Any]) -> tuple:
        rec = r["per_class_recall"]
        min_rec = min(float(rec[name]) for name in ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA"))
        return (
            -float(r["val_macro_f1"]),
            -float(rec["RAPID_OR_ABNORMAL"]),
            -min_rec,
            int(r["parameter_count"]),
            int(r["seed"]),
        )
    group.sort(key=sort_key)
    return group[0]


def verify_artifact(run: dict[str, Any]) -> Path:
    path = ROOT / run["artifact_path"]
    if not path.is_file():
        raise RuntimeError("SELECTED_M_N5_ARTIFACT_NOT_AVAILABLE")
    digest = sha256_file(path)
    size = int(path.stat().st_size)
    if digest != run["artifact_sha256"] or size != int(run["artifact_size"]):
        raise RuntimeError("SELECTED_M_N5_ARTIFACT_IDENTITY_MISMATCH")
    return path


def reload_shape_check(path: Path) -> dict[str, str]:
    import numpy as np
    import tensorflow as tf

    model = tf.keras.models.load_model(path)
    in_shape = tuple(model.inputs[0].shape)
    out_shape = tuple(model.outputs[0].shape)
    dummy = np.zeros((1, 240, 1), dtype=np.float32)
    probs = np.asarray(model.predict(dummy, verbose=0), dtype=np.float64)
    finite = bool(np.all(np.isfinite(probs)))
    sum_ok = bool(np.allclose(probs.sum(axis=1), 1.0, atol=1e-5))
    del model
    tf.keras.backend.clear_session()
    if in_shape[1:] != (240, 1) or out_shape[1:] != (3,):
        raise RuntimeError(f"BAD_MODEL_SHAPE:{in_shape}:{out_shape}")
    if not finite or not sum_ok:
        raise RuntimeError("DUMMY_PROBABILITY_SANITY_FAIL")
    return {
        "input_shape": "PASS",
        "output_shape": "PASS",
        "reload": "PASS",
        "dummy_probability_sanity": "PASS",
    }


def write_lock(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest["contract_id"] != CONTRACT_ID:
        raise RuntimeError("M_N4_CONTRACT_ID_MISMATCH")
    if int(manifest["heldout"]["NEW_MODEL_HELDOUT_TEST_INFERENCE"]) != 0:
        raise RuntimeError("M_N5_HELDOUT_ALREADY_USED")
    runs = load_primary_runs(manifest)
    families = family_summary(runs)
    selected_family = families[0]["candidate_id"]
    selected = select_exact_run(runs, selected_family)
    src = verify_artifact(selected)
    shapes = reload_shape_check(src)
    LOCKED_DIR.mkdir(parents=True, exist_ok=True)
    dest = LOCKED_DIR / LOCKED_ARTIFACT_NAME
    shutil.copy2(src, dest)
    dest_sha = sha256_file(dest)
    if dest_sha != selected["artifact_sha256"]:
        raise RuntimeError("LOCKED_COPY_SHA_MISMATCH")
    lock = {
        "selection_id": SELECTION_ID,
        "phase": "M-N6_STAGE_A",
        "status": "LOCKED_BEFORE_HELDOUT",
        "contract_id": CONTRACT_ID,
        "candidate_id": selected["candidate_id"],
        "architecture_family": selected["architecture_family"],
        "seed": int(selected["seed"]),
        "source_m_n5_manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "source_artifact_path": selected["artifact_path"],
        "locked_artifact_path": str(dest.relative_to(ROOT)),
        "artifact_sha256": selected["artifact_sha256"],
        "artifact_size": int(selected["artifact_size"]),
        "parameter_count": int(selected["parameter_count"]),
        "val_metrics": {
            "accuracy": selected["val_accuracy"],
            "macro_f1": selected["val_macro_f1"],
            "loss": selected["val_loss"],
            "balanced_accuracy": selected["val_balanced_accuracy"],
            "per_class": selected["per_class"],
            "per_class_recall": selected["per_class_recall"],
            "confusion_matrix": selected["confusion_matrix"],
            "predicted_class_counts": selected["predicted_class_counts"],
        },
        "family_ranking": families,
        "selection_rule": {
            "family": "MEAN_VAL_MACRO_F1_ACROSS_FIXED_SEEDS",
            "exact_run": "HIGHEST_VAL_MACRO_F1_WITHIN_SELECTED_FAMILY",
            "family_tie_break": [
                "less_severe_RAPID_OR_ABNORMAL_weakness",
                "less_seed_instability",
                "smaller_parameter_count",
            ],
            "run_tie_break": [
                "higher_RAPID_OR_ABNORMAL_recall",
                "higher_minimum_class_recall",
                "lower_parameter_count",
            ],
        },
        "selection_reason": (
            f"{selected_family} had the highest mean VAL Macro F1 across seeds 42/2026 "
            f"({families[0]['mean_val_macro_f1']}); seed {selected['seed']} had the highest "
            f"VAL Macro F1 inside that family ({selected['val_macro_f1']}) and the highest "
            "RAPID_OR_ABNORMAL recall of the two fixed seeds."
        ),
        "heldout_inference_before_lock": HELDOUT_INFERENCE_BEFORE_SELECTION_LOCK,
        "heldout_tensors_materialized_before_lock": 0,
        "heldout_status": "FROZEN_UNACCESSED",
        "architecture_change_allowed_after_lock": False,
        "seed_change_allowed_after_lock": False,
        "artifact_change_allowed_after_lock": False,
        "train_plus_val_retraining": False,
        "threshold_tuning": False,
        "team_mr60_evaluated": False,
        "production_final_model": False,
        "selection_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_git_sha": git_sha(),
        "tensorflow_version": selected.get("tensorflow_version"),
        "focused_validation": shapes,
        "selected_artifact_sha_match": True,
        "binary_storage": "GIT_TRACKED",
        "binary_storage_note": "selected float keras copied under models/mmwave/m_n6/; other M-N5 candidate binaries remain local/gitignored",
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    lock = write_lock(manifest)
    print(
        json.dumps(
            {
                "selection_id": lock["selection_id"],
                "candidate_id": lock["candidate_id"],
                "seed": lock["seed"],
                "artifact_sha256": lock["artifact_sha256"],
                "heldout_inference_before_lock": lock["heldout_inference_before_lock"],
                "lock_path": str(LOCK_PATH.relative_to(ROOT)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
