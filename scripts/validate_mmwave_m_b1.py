#!/usr/bin/env python3
"""SafeNest Phase M-B1 — Standalone Validator.

Independently validates M-B1 real-data preprocessing full-factorial ablation,
recomputing Z-score statistics, transformed tensor fingerprints, validation metrics,
class-collapse rejection, pre-registered winner ranking, and fail-closed checksum manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from mmwave_m_b1_preprocessing import (
    PROFILES,
    compute_tensor_fingerprint,
    fit_train_zscore_statistics,
    transform_signals,
)
from mmwave_phase_b_access import LOCKED_TEST_AccessError, PhaseBAccessGuard

REQUIRED_MB1_ARTIFACTS = {
    "input_identity.json",
    "experiment_contract.json",
    "preprocessing_profiles.json",
    "train_fit_statistics.json",
    "preprocessing_fingerprints.json",
    "training_runs.json",
    "ablation_results.json",
    "signal_diagnostics.json",
    "bpf_frequency_diagnostic.json",
    "apnea_proxy_preprocessing_diagnostic.json",
    "validation_predictions.npz",
    "selected_preprocessing_profile.json",
    "locked_test_access_audit.json",
    "determinism_audit.json",
    "run_environment.json",
    "exceptions.json",
    "m_b1_summary.json",
}

LABEL_ID_TO_NAME = {0: "NORMAL", 1: "RAPID_OR_ABNORMAL", 2: "APNEA"}


class MB1ValidationError(Exception):
    """Raised when Phase M-B1 validation fails."""


def validate_m_b1_artifacts(
    root_dir: Path = ROOT_DIR,
    manifest_dir: Path | None = None,
) -> dict[str, Any]:
    """Independently validate all Phase M-B1 artifacts against strict contracts."""
    if manifest_dir is None:
        manifest_dir = root_dir / "datasets/mmwave/manifests/M-B1_preprocessing_ablation"

    if not manifest_dir.is_dir():
        raise MB1ValidationError(f"M-B1 manifest directory missing: {manifest_dir}")

    # 1. Verify Upstream Immutable Artifacts
    canonical_npy = root_dir / "datasets/mmwave/processed/mmwave_canonical_real_v1.npy"
    if not canonical_npy.is_file():
        raise MB1ValidationError("Canonical matrix missing!")
    actual_npy_sha = hashlib.sha256(canonical_npy.read_bytes()).hexdigest()
    if actual_npy_sha != "c2e2cd1615c7af0f0e21700f291ee12ac0347a9f7fc6ccc9f337433c16868f0e":
        raise MB1ValidationError(f"Canonical NPY SHA changed! Got {actual_npy_sha}")

    mb0_dir = root_dir / "datasets/mmwave/manifests/M-B0_evaluation_protocol"
    if not (mb0_dir / "m_b0_summary.json").is_file():
        raise MB1ValidationError("M-B0 summary missing!")

    # 2. Test PhaseBAccessGuard LOCKED_TEST Fail-Closed Guard
    guard = PhaseBAccessGuard(root_dir=root_dir)
    try:
        guard.get_model_selection_dataset("LOCKED_TEST")
        raise MB1ValidationError("PhaseBAccessGuard failed to block LOCKED_TEST model selection access!")
    except LOCKED_TEST_AccessError:
        pass

    # 3. Load Pure-Class Datasets
    train_data = guard.get_train_data(include_ambiguous=False)
    val_data = guard.get_validation_data(include_ambiguous=False)

    if train_data["total_count"] != 327 or val_data["total_count"] != 79:
        raise MB1ValidationError(f"Dataset population mismatch! TRAIN={train_data['total_count']}, VAL={val_data['total_count']}")

    train_signals = train_data["signals"]
    val_signals = val_data["signals"]

    # 4. Verify 8 Preprocessing Profiles (2^3 Factorial)
    prof_file = manifest_dir / "preprocessing_profiles.json"
    if not prof_file.is_file():
        raise MB1ValidationError(f"preprocessing_profiles.json missing: {prof_file}")
    loaded_profiles = json.loads(prof_file.read_text(encoding="utf-8")).get("profiles", [])

    if len(loaded_profiles) != 8:
        raise MB1ValidationError(f"Expected 8 profiles, got {len(loaded_profiles)}")

    profile_ids = [p["profile_id"] for p in loaded_profiles]
    expected_ids = [p["profile_id"] for p in PROFILES]
    if profile_ids != expected_ids:
        raise MB1ValidationError(f"Profile ID mismatch! Expected {expected_ids}, got {profile_ids}")

    # 5. Independently Recompute Z-Score Statistics & Tensor Fingerprints
    zstat_file = manifest_dir / "train_fit_statistics.json"
    fingerprint_file = manifest_dir / "preprocessing_fingerprints.json"
    if not zstat_file.is_file() or not fingerprint_file.is_file():
        raise MB1ValidationError("train_fit_statistics.json or preprocessing_fingerprints.json missing!")

    loaded_zstats = json.loads(zstat_file.read_text(encoding="utf-8")).get("zscore_statistics", {})
    loaded_fingerprints = json.loads(fingerprint_file.read_text(encoding="utf-8")).get("fingerprints", {})

    for prof in PROFILES:
        pid = prof["profile_id"]
        detrend, bpf, zscore = prof["detrend"], prof["bpf"], prof["zscore"]

        # Recompute Z-score stats if zscore is True
        if zscore:
            calc_zstats = fit_train_zscore_statistics(train_signals, detrend=detrend, bpf=bpf)
            manif_z = loaded_zstats.get(pid, {})
            if abs(calc_zstats["mean"] - manif_z.get("mean", 0.0)) > 1e-6 or abs(calc_zstats["std"] - manif_z.get("std", 1.0)) > 1e-6:
                raise MB1ValidationError(f"Z-score stat mismatch for {pid}! Calc={calc_zstats}, Manifest={manif_z}")
            stats_to_use = calc_zstats
        else:
            stats_to_use = None

        # Recompute transformed tensors
        calc_train_t = transform_signals(train_signals, detrend=detrend, bpf=bpf, zscore=zscore, zscore_stats=stats_to_use)
        calc_val_t = transform_signals(val_signals, detrend=detrend, bpf=bpf, zscore=zscore, zscore_stats=stats_to_use)

        train_fp = compute_tensor_fingerprint(calc_train_t)
        val_fp = compute_tensor_fingerprint(calc_val_t)

        manif_fp = loaded_fingerprints.get(pid, {})
        if train_fp != manif_fp.get("train_tensor_sha256") or val_fp != manif_fp.get("validation_tensor_sha256"):
            raise MB1ValidationError(f"Tensor fingerprint mismatch for {pid}!")

    # 6. Verify Validation Predictions & Recompute Metrics
    npz_file = manifest_dir / "validation_predictions.npz"
    ablation_file = manifest_dir / "ablation_results.json"
    if not npz_file.is_file() or not ablation_file.is_file():
        raise MB1ValidationError("validation_predictions.npz or ablation_results.json missing!")

    val_preds_npz = np.load(npz_file)
    loaded_ablation = json.loads(ablation_file.read_text(encoding="utf-8")).get("results", {})

    val_true_ids = np.array([w["safenest_label_id"] for w in val_data["windows"]], dtype=int)

    recomputed_ranking = []

    for prof in PROFILES:
        pid = prof["profile_id"]
        if pid not in val_preds_npz:
            raise MB1ValidationError(f"Predictions for {pid} missing from NPZ!")

        preds = val_preds_npz[pid]
        if len(preds) != len(val_true_ids):
            raise MB1ValidationError(f"Prediction count mismatch for {pid}: got {len(preds)}, expected {len(val_true_ids)}")

        # Recompute Per-Class Metrics & Macro F1
        per_class = {}
        for cid in (0, 1, 2):
            cname = LABEL_ID_TO_NAME[cid]
            tp = int(np.sum((preds == cid) & (val_true_ids == cid)))
            fp = int(np.sum((preds == cid) & (val_true_ids != cid)))
            fn = int(np.sum((preds != cid) & (val_true_ids == cid)))

            prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
            rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
            f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

            per_class[cname] = {"precision": round(prec, 6), "recall": round(rec, 6), "f1": round(f1, 6), "tp": tp, "fp": fp, "fn": fn}

        macro_f1 = float(np.mean([per_class[c]["f1"] for c in ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA")]))
        min_rec = float(min(per_class[c]["recall"] for c in ("NORMAL", "RAPID_OR_ABNORMAL", "APNEA")))
        apnea_rec = per_class["APNEA"]["recall"]
        apnea_miss = 1.0 - apnea_rec

        # Class Collapse Detection
        is_collapsed = (apnea_rec == 0.0) or (per_class["RAPID_OR_ABNORMAL"]["recall"] == 0.0)

        # Check against manifest
        manif_res = loaded_ablation.get(pid, {})
        if abs(macro_f1 - manif_res.get("macro_f1", 0.0)) > 1e-4:
            raise MB1ValidationError(f"Macro F1 mismatch for {pid}: calc={macro_f1:.6f}, manifest={manif_res.get('macro_f1')}")

        recomputed_ranking.append({
            "profile_id": pid,
            "is_collapsed": is_collapsed,
            "macro_f1": round(macro_f1, 6),
            "min_recall": round(min_rec, 6),
            "apnea_recall": round(apnea_rec, 6),
            "num_operations": int(prof["detrend"]) + int(prof["bpf"]) + int(prof["zscore"]),
        })

    # 7. Pre-Registered Winner Selection Ranking
    # Sort according to 6-step rule
    eligible_candidates = [r for r in recomputed_ranking if not r["is_collapsed"]]
    if not eligible_candidates:
        raise MB1ValidationError("ALL 8 PREPROCESSING PROFILES COLLAPSED! No valid candidate winner.")

    eligible_candidates.sort(
        key=lambda r: (
            r["macro_f1"],
            r["min_recall"],
            r["apnea_recall"],
            -r["num_operations"],  # Prefer fewer operations (higher negative value)
            r["profile_id"],  # Lexicographic tie-breaker
        ),
        reverse=True,
    )

    recomputed_winner = eligible_candidates[0]["profile_id"]

    sel_file = manifest_dir / "selected_preprocessing_profile.json"
    if not sel_file.is_file():
        raise MB1ValidationError(f"selected_preprocessing_profile.json missing: {sel_file}")
    loaded_winner = json.loads(sel_file.read_text(encoding="utf-8")).get("selected_profile_id")

    if loaded_winner != recomputed_winner:
        raise MB1ValidationError(f"Winner selection mismatch! Recomputed winner={recomputed_winner}, Loaded={loaded_winner}")

    # 8. HARDENED CHECKSUM MANIFEST VALIDATION
    checksums_file = manifest_dir / "checksums.sha256"
    if not checksums_file.is_file():
        raise MB1ValidationError(f"checksums.sha256 missing: {checksums_file}")

    raw_lines = checksums_file.read_text(encoding="utf-8").splitlines()
    seen_entries = set()

    for line_num, line in enumerate(raw_lines, 1):
        line_str = line.strip()
        if not line_str:
            continue

        parts = line_str.split(maxsplit=1)
        if len(parts) != 2:
            raise MB0ValidationError(f"Malformed checksum line {line_num} in checksums.sha256: '{line}'")

        digest, rel_name = parts[0].strip(), parts[1].strip()

        if not re.fullmatch(r"^[0-9a-fA-F]{64}$", digest):
            raise MB1ValidationError(f"Invalid SHA-256 digest format at line {line_num}: '{digest}'")

        if rel_name.startswith("/") or rel_name.startswith("\\") or "file://" in rel_name or "~" in rel_name or ".." in rel_name:
            raise MB1ValidationError(f"Path traversal or absolute path in checksums.sha256 line {line_num}: '{rel_name}'")

        if rel_name in seen_entries:
            raise MB1ValidationError(f"Duplicate file entry in checksums.sha256 at line {line_num}: '{rel_name}'")
        seen_entries.add(rel_name)

        target_f = (manifest_dir / rel_name).resolve()
        if not target_f.is_file():
            raise MB1ValidationError(f"Checksum target file missing: '{rel_name}'")
        if target_f.parent != manifest_dir.resolve():
            raise MB1ValidationError(f"Checksum target file escapes manifest directory: '{rel_name}'")

        actual_hash = hashlib.sha256(target_f.read_bytes()).hexdigest()
        if actual_hash != digest.lower():
            raise MB1ValidationError(f"Checksum mismatch for '{rel_name}': expected {digest}, got {actual_hash}")

    missing_required = REQUIRED_MB1_ARTIFACTS - seen_entries
    if missing_required:
        raise MB1ValidationError(f"checksums.sha256 missing required M-B1 artifacts: {missing_required}")

    # 9. Verify No Local Absolute Paths in JSON Manifests
    for manifest_f in manifest_dir.glob("*.json"):
        content_str = manifest_f.read_text(encoding="utf-8")
        if "/Users/" in content_str or "file://" in content_str:
            raise MB1ValidationError(f"Absolute local path found in machine-readable artifact {manifest_f.name}")

    return {
        "validation_success": True,
        "m_b1_gate_status": "PASS_WITH_WARNINGS",
        "m_b2_entry_status": "READY_WITH_CONDITIONS",
        "independently_measured": {
            "canonical_npy_sha": actual_npy_sha,
            "train_window_count": len(train_data["windows"]),
            "validation_window_count": len(val_data["windows"]),
            "profiles_audited": len(PROFILES),
            "zscore_statistics_verified": True,
            "tensor_fingerprints_verified": True,
            "validation_metrics_recomputed": True,
            "recomputed_winner_profile": recomputed_winner,
            "locked_test_access_blocked": True,
            "hardened_checksum_verification": True,
        },
        "declared_policy_attributes": {
            "fixed_probe_architecture": "Conv1D_16_32_64_GAP_Dense3",
            "fixed_initialization_seed": 42,
            "fixed_imbalance_strategy": "UNWEIGHTED_SPARSE_CATEGORICAL_CROSSENTROPY",
        },
    }


def main() -> None:
    res = validate_m_b1_artifacts()
    print("Standalone M-B1 Preprocessing Ablation Validation Result:")
    print(f"Validation Success: {res['validation_success']}")
    print(f"M-B1 Gate Status: {res['m_b1_gate_status']}")
    print(f"M-B2 Entry Status: {res['m_b2_entry_status']}")
    print(f"Profiles Audited: {res['independently_measured']['profiles_audited']}")
    print(f"Recomputed Winner: {res['independently_measured']['recomputed_winner_profile']}")
    print(f"LOCKED_TEST Guard Verified: {res['independently_measured']['locked_test_access_blocked']}")
    print(f"Hardened Checksums Verified: {res['independently_measured']['hardened_checksum_verification']}")


if __name__ == "__main__":
    main()
