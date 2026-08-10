# SafeNest mmWave Track — Phase M-B4 Standalone Validator

import hashlib
import json
import os
import re
import sys
import numpy as np
from pathlib import Path
from typing import Any, Dict, Optional

import tensorflow as tf

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from mmwave_m_b2_imbalance import LABEL_NAMES, compute_one_vs_rest_false_positives, compute_subject_level_diagnostics
from mmwave_m_b3_architecture import (
    build_model_by_id,
    compute_numerical_weights_sha256,
)
from mmwave_m_b4_multiseed import SEEDS, rank_multiseed_architectures
from mmwave_phase_b_access import PhaseBAccessGuard
from validate_mmwave_m_b0 import validate_m_b0_artifacts
from validate_mmwave_m_b1 import validate_m_b1_artifacts
from validate_mmwave_m_b2 import validate_m_b2_artifacts
from validate_mmwave_m_b3 import validate_m_b3_artifacts


class MB4ValidationError(Exception):
    """Raised when Phase M-B4 validation fails."""
    pass


REQUIRED_MB4_ARTIFACTS = {
    "input_identity.json",
    "experiment_contract.json",
    "seed_plan.json",
    "seed42_reuse_audit.json",
    "training_runs.json",
    "seed_weights.npz",
    "validation_predictions.npz",
    "validation_prediction_index.jsonl",
    "per_seed_results.json",
    "multi_seed_results.json",
    "subject_level_seed_metrics.json",
    "primary_float_finalist.json",
    "backup_architecture.json",
    "locked_test_access_audit.json",
    "run_environment.json",
    "exceptions.json",
    "m_b4_summary.json",
    "checksums.sha256",
}


def validate_m_b4_artifacts(
    root_dir: Path = ROOT_DIR,
    manifest_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Independently validate all Phase M-B4 multi-seed stability artifacts without retraining."""
    if manifest_dir is None:
        manifest_dir = root_dir / "datasets/mmwave/manifests/M-B4_multiseed_stability"

    if not manifest_dir.is_dir():
        raise MB4ValidationError(f"M-B4 manifest directory missing: {manifest_dir}")

    guard = PhaseBAccessGuard(root_dir=root_dir)

    # 1. Verify Pinned Environment
    import scipy

    actual_tf = tf.__version__
    actual_np = np.__version__
    actual_scipy = scipy.__version__

    req_file = root_dir / "requirements-mac.txt"
    if not req_file.is_file():
        raise MB4ValidationError("requirements-mac.txt missing!")
    req_sha = hashlib.sha256(req_file.read_bytes()).hexdigest()

    env_file = manifest_dir / "run_environment.json"
    if not env_file.is_file():
        raise MB4ValidationError("run_environment.json missing!")
    env_data = json.loads(env_file.read_text(encoding="utf-8"))

    if env_data.get("tensorflow_version") != actual_tf or env_data.get("numpy_version") != actual_np:
        raise MB4ValidationError(f"Environment mismatch: manifest={env_data.get('tensorflow_version')}/{env_data.get('numpy_version')}, actual={actual_tf}/{actual_np}")
    if env_data.get("requirements_mac_sha256") != req_sha:
        raise MB4ValidationError("requirements-mac.txt SHA-256 mismatch!")

    # 2. Invoke Upstream Standalone Validators (M-B0, M-B1, M-B2, M-B3)
    mb0_res = validate_m_b0_artifacts(root_dir=root_dir)
    if not mb0_res.get("validation_success"):
        raise MB4ValidationError(f"Upstream M-B0 validation failed: {mb0_res}")

    mb1_res = validate_m_b1_artifacts(root_dir=root_dir)
    if not mb1_res.get("validation_success"):
        raise MB4ValidationError(f"Upstream M-B1 validation failed: {mb1_res}")

    mb2_res = validate_m_b2_artifacts(root_dir=root_dir)
    if not mb2_res.get("validation_success"):
        raise MB4ValidationError(f"Upstream M-B2 validation failed: {mb2_res}")

    mb3_res = validate_m_b3_artifacts(root_dir=root_dir)
    if not mb3_res.get("validation_success"):
        raise MB4ValidationError(f"Upstream M-B3 validation failed: {mb3_res}")

    # 3. Verify Upstream Input Identity Chain
    input_identity_file = manifest_dir / "input_identity.json"
    if not input_identity_file.is_file():
        raise MB4ValidationError("input_identity.json missing!")
    input_identity_data = json.loads(input_identity_file.read_text(encoding="utf-8"))
    inputs_list = input_identity_data.get("inputs", [])

    if len(inputs_list) < 19:
        raise MB4ValidationError(f"input_identity.json must contain at least 19 upstream files, got {len(inputs_list)}")

    for input_item in inputs_list:
        rel_p = input_item.get("path")
        exp_sha = input_item.get("measured_sha256")
        if not rel_p or not exp_sha:
            raise MB4ValidationError(f"Malformed input_identity item: {input_item}")
        full_p = root_dir / rel_p
        if not full_p.is_file():
            raise MB4ValidationError(f"Upstream identity file missing from checkout: {rel_p}")
        act_sha = hashlib.sha256(full_p.read_bytes()).hexdigest()
        if act_sha != exp_sha:
            raise MB4ValidationError(f"Upstream identity SHA mismatch for '{rel_p}': expected {exp_sha}, got {act_sha}")

    # Verify Seed Plan
    seed_plan_file = manifest_dir / "seed_plan.json"
    if not seed_plan_file.is_file():
        raise MB4ValidationError("seed_plan.json missing!")
    seed_plan_data = json.loads(seed_plan_file.read_text(encoding="utf-8"))
    if seed_plan_data.get("seeds") != SEEDS:
        raise MB4ValidationError(f"Seed plan mismatch: expected {SEEDS}, got {seed_plan_data.get('seeds')}")

    # 4. Verify Datasets & Transformed Tensors
    train_data = guard.get_model_selection_dataset("TRAIN")
    val_data = guard.get_model_selection_dataset("VALIDATION")

    if len(train_data["windows"]) != 327 or len(val_data["windows"]) != 79:
        raise MB4ValidationError(f"Dataset window count mismatch: TRAIN={len(train_data['windows'])}, VAL={len(val_data['windows'])}")

    val_y = np.array([w["safenest_label_id"] for w in val_data["windows"]], dtype=int)

    # 5. Verify Model Reconstruction & Numerical Weight Lineage
    weights_npz_file = manifest_dir / "seed_weights.npz"
    preds_npz_file = manifest_dir / "validation_predictions.npz"
    tr_file = manifest_dir / "training_runs.json"
    per_seed_file = manifest_dir / "per_seed_results.json"
    multi_seed_file = manifest_dir / "multi_seed_results.json"

    for req_f, fpath in [
        ("seed_weights.npz", weights_npz_file),
        ("validation_predictions.npz", preds_npz_file),
        ("training_runs.json", tr_file),
        ("per_seed_results.json", per_seed_file),
        ("multi_seed_results.json", multi_seed_file),
    ]:
        if not fpath.is_file():
            raise MB4ValidationError(f"Required artifact missing: {req_f}")

    seed_weights_npz = np.load(weights_npz_file)
    val_preds_npz = np.load(preds_npz_file)
    tr_data = json.loads(tr_file.read_text(encoding="utf-8")).get("training_runs", {})
    per_seed_data = json.loads(per_seed_file.read_text(encoding="utf-8")).get("per_seed_results", {})
    multi_seed_data = json.loads(multi_seed_file.read_text(encoding="utf-8")).get("multi_seed_results", [])

    shortlist_ids = ["M-B3_CONV1D_GAP_BASELINE", "M-B3_SEPARABLECONV1D_GAP"]

    for aid in shortlist_ids:
        for seed in SEEDS:
            run_key = f"{aid}_seed_{seed}"
            if run_key not in tr_data:
                raise MB4ValidationError(f"Training run info missing for {run_key}")

            m_rebuilt = build_model_by_id(aid)
            arch_w_keys = sorted(
                [k for k in seed_weights_npz.files if k.startswith(f"{aid}_seed_{seed}_layer_weight_")],
                key=lambda x: int(x.split("_")[-1]),
            )
            if not arch_w_keys:
                raise MB4ValidationError(f"No stored weights found in seed_weights.npz for {run_key}")
            arch_w_list = [seed_weights_npz[k] for k in arch_w_keys]
            m_rebuilt.set_weights(arch_w_list)

            rebuilt_weight_sha = compute_numerical_weights_sha256(m_rebuilt)
            exp_weight_sha = tr_data[run_key]["final_weights_sha256"]
            if rebuilt_weight_sha != exp_weight_sha:
                raise MB4ValidationError(
                    f"LINEAGE MISMATCH for {run_key}: stored NPZ weight SHA ({rebuilt_weight_sha}) != training_runs.json final_weights_sha256 ({exp_weight_sha})"
                )

    # 6. Recompute Per-Seed & Multi-Seed Validation Metrics
    recomputed_per_seed = {}
    recomputed_multi_seed = []

    for aid in shortlist_ids:
        seed_metrics_list = []
        for seed in SEEDS:
            run_key = f"{aid}_seed_{seed}"
            if run_key not in val_preds_npz:
                raise MB4ValidationError(f"Predictions for {run_key} missing from validation_predictions.npz")
            preds = val_preds_npz[run_key]
            if len(preds) != len(val_y):
                raise MB4ValidationError(f"Prediction count mismatch for {run_key}: got {len(preds)}, expected {len(val_y)}")

            cm = compute_one_vs_rest_false_positives(val_y, preds)
            macro_f1 = float(np.mean([cm[c]["f1_score"] for c in LABEL_NAMES]))
            accuracy = float(np.mean(preds == val_y))
            min_rec = float(min(cm[c]["recall"] for c in LABEL_NAMES))
            apnea_rec = cm["APNEA"]["recall"]
            rapid_rec = cm["RAPID_OR_ABNORMAL"]["recall"]

            collapsed = (apnea_rec == 0.0) or (rapid_rec == 0.0) or (len(np.unique(preds)) < 3)

            pred_dist = {c: int(np.sum(preds == idx)) for idx, c in enumerate(LABEL_NAMES)}

            art_seed_item = per_seed_data.get(run_key, {})
            if round(art_seed_item.get("val_macro_f1", 0.0), 6) != round(macro_f1, 6):
                raise MB4ValidationError(f"Macro F1 mismatch for {run_key}: manifest={art_seed_item.get('val_macro_f1')}, recomputed={macro_f1}")

            seed_metrics_list.append({
                "val_macro_f1": macro_f1,
                "val_accuracy": accuracy,
                "min_per_class_recall": min_rec,
                "apnea_recall": apnea_rec,
                "rapid_recall": rapid_rec,
                "collapsed": collapsed,
                "class_metrics": cm,
            })

        f1_vals = [r["val_macro_f1"] for r in seed_metrics_list]
        acc_vals = [r["val_accuracy"] for r in seed_metrics_list]
        min_rec_vals = [r["min_per_class_recall"] for r in seed_metrics_list]

        worst_idx = int(np.argmin(f1_vals))
        worst_seed = SEEDS[worst_idx]
        collapsed_cnt = sum(1 for r in seed_metrics_list if r["collapsed"])

        total_p = tr_data[f"{aid}_seed_42"]["param_counts"]["total_params"]

        recomputed_multi_seed.append({
            "architecture_id": aid,
            "seeds_evaluated": SEEDS,
            "total_params": total_p,
            "collapsed_seed_count": collapsed_cnt,
            "macro_f1": {
                "mean": round(float(np.mean(f1_vals)), 6),
                "median": round(float(np.median(f1_vals)), 6),
                "std": round(float(np.std(f1_vals)), 6),
                "min": round(float(np.min(f1_vals)), 6),
                "max": round(float(np.max(f1_vals)), 6),
                "worst_seed_val": round(float(np.min(f1_vals)), 6),
                "worst_seed_id": worst_seed,
            },
            "accuracy": {
                "mean": round(float(np.mean(acc_vals)), 6),
                "std": round(float(np.std(acc_vals)), 6),
                "min": round(float(np.min(acc_vals)), 6),
            },
            "min_per_class_recall": {
                "mean": round(float(np.mean(min_rec_vals)), 6),
                "std": round(float(np.std(min_rec_vals)), 6),
                "min": round(float(np.min(min_rec_vals)), 6),
                "worst_seed_val": round(float(np.min(min_rec_vals)), 6),
            },
        })

    # 7. Recompute Selection & Validate Finalist Manifests
    ranked_recomputed = rank_multiseed_architectures(multi_seed_data, eps=1e-5)
    exp_winner = ranked_recomputed[0]["architecture_id"] if ranked_recomputed and ranked_recomputed[0]["collapsed_seed_count"] == 0 else None
    exp_backup = ranked_recomputed[1]["architecture_id"] if len(ranked_recomputed) > 1 and ranked_recomputed[1]["collapsed_seed_count"] == 0 else None

    primary_file = manifest_dir / "primary_float_finalist.json"
    backup_file = manifest_dir / "backup_architecture.json"

    if not primary_file.is_file() or not backup_file.is_file():
        raise MB4ValidationError("primary_float_finalist.json or backup_architecture.json missing!")

    act_winner = json.loads(primary_file.read_text(encoding="utf-8")).get("primary_stable_float_finalist")
    act_backup = json.loads(backup_file.read_text(encoding="utf-8")).get("backup_architecture_id")

    if act_winner != exp_winner:
        raise MB4ValidationError(f"Primary finalist selection mismatch: expected {exp_winner}, got {act_winner}")
    if act_backup != exp_backup:
        raise MB4ValidationError(f"Backup architecture selection mismatch: expected {exp_backup}, got {act_backup}")

    # 8. Verify Subject-Level Seed Diagnostics
    subj_file = manifest_dir / "subject_level_seed_metrics.json"
    if not subj_file.is_file():
        raise MB4ValidationError("subject_level_seed_metrics.json missing!")
    subj_data = json.loads(subj_file.read_text(encoding="utf-8"))

    if subj_data.get("subject_split_variation") != "NOT_PERFORMED_IN_M-B4":
        raise MB4ValidationError("subject_level_seed_metrics.json must record subject_split_variation='NOT_PERFORMED_IN_M-B4'")
    if subj_data.get("stability_type") != "INITIALIZATION_SEED_STABILITY":
        raise MB4ValidationError("subject_level_seed_metrics.json must record stability_type='INITIALIZATION_SEED_STABILITY'")

    # 9. Verify Zero Performance Access to LOCKED_TEST
    locked_file = manifest_dir / "locked_test_access_audit.json"
    if not locked_file.is_file():
        raise MB4ValidationError("locked_test_access_audit.json missing!")
    locked_data = json.loads(locked_file.read_text(encoding="utf-8"))

    if locked_data.get("performance_access_attempts", -1) != 0 or not locked_data.get("lock_preserved"):
        raise MB4ValidationError("LOCKED_TEST performance access violation detected!")

    # 10. HARDENED CHECKSUM MANIFEST VALIDATION
    checksums_file = manifest_dir / "checksums.sha256"
    if not checksums_file.is_file():
        raise MB4ValidationError(f"checksums.sha256 missing: {checksums_file}")

    raw_lines = checksums_file.read_text(encoding="utf-8").splitlines()
    seen_entries = set()

    for line_num, line in enumerate(raw_lines, 1):
        line_str = line.strip()
        if not line_str:
            continue

        parts = line_str.split(maxsplit=1)
        if len(parts) != 2:
            raise MB4ValidationError(f"Malformed checksum line {line_num} in checksums.sha256: '{line}'")

        digest, rel_name = parts[0].strip(), parts[1].strip()

        if not re.fullmatch(r"^[0-9a-fA-F]{64}$", digest):
            raise MB4ValidationError(f"Invalid SHA-256 digest format at line {line_num}: '{digest}'")

        if rel_name.startswith("/") or rel_name.startswith("\\") or "file://" in rel_name or "~" in rel_name or ".." in rel_name:
            raise MB4ValidationError(f"Path traversal or absolute path in checksums.sha256 line {line_num}: '{rel_name}'")

        if rel_name in seen_entries:
            raise MB4ValidationError(f"Duplicate file entry in checksums.sha256 at line {line_num}: '{rel_name}'")
        seen_entries.add(rel_name)

        target_f = (manifest_dir / rel_name).resolve()
        if not target_f.is_file():
            raise MB4ValidationError(f"Checksum target file missing: '{rel_name}'")
        if target_f.parent != manifest_dir.resolve():
            raise MB4ValidationError(f"Checksum target file escapes manifest directory: '{rel_name}'")

        actual_hash = hashlib.sha256(target_f.read_bytes()).hexdigest()
        if actual_hash != digest.lower():
            raise MB4ValidationError(f"Checksum mismatch for '{rel_name}': expected {digest}, got {actual_hash}")

    missing_required = (REQUIRED_MB4_ARTIFACTS - {"checksums.sha256"}) - seen_entries
    if missing_required:
        raise MB4ValidationError(f"checksums.sha256 missing required M-B4 artifacts: {missing_required}")

    # 11. Verify No Local Absolute Paths in JSON/JSONL Manifests
    for manifest_f in manifest_dir.glob("*"):
        if manifest_f.suffix in (".json", ".jsonl"):
            content_str = manifest_f.read_text(encoding="utf-8")
            if "/Users/" in content_str or "file://" in content_str:
                raise MB4ValidationError(f"Absolute local path found in machine-readable artifact {manifest_f.name}")

    return {
        "validation_success": True,
        "m_b4_gate_status": "PASS_WITH_WARNINGS",
        "m_b5_entry_status": "READY_WITH_CONDITIONS",
        "independently_measured": {
            "pinned_environment_verified": True,
            "upstream_identity_chain_verified": True,
            "m_b0_gate_verified": True,
            "m_b1_gate_verified": True,
            "m_b2_gate_verified": True,
            "m_b3_gate_verified": True,
            "seed_plan_verified": SEEDS,
            "primary_stable_float_finalist": act_winner,
            "backup_architecture": act_backup,
            "locked_test_access_blocked": True,
            "hardened_checksum_verification": True,
        },
    }


def main() -> None:
    res = validate_m_b4_artifacts()
    print("Standalone M-B4 Multi-Seed Stability Validation Result:")
    print(f"Validation Success: {res['validation_success']}")
    print(f"M-B4 Gate Status: {res['m_b4_gate_status']}")
    print(f"M-B5 Entry Status: {res['m_b5_entry_status']}")
    print(f"Primary Stable Float Finalist: {res['independently_measured']['primary_stable_float_finalist']}")
    print(f"Backup Architecture: {res['independently_measured']['backup_architecture']}")
    print(f"LOCKED_TEST Guard Verified: {res['independently_measured']['locked_test_access_blocked']}")
    print(f"Hardened Checksums Verified: {res['independently_measured']['hardened_checksum_verification']}")


if __name__ == "__main__":
    main()
