#!/usr/bin/env python3
"""Validate the B6R-P1 public-SDT-only model and its deployment boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p1_public_sdt_training_contract.json"
DEFAULT_P0_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P0_public_sdt_materialization"
DEFAULT_MODEL_DIR = ROOT / "models/thermal/public_sdt"
DEFAULT_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P1_public_sdt_controlled_training"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--p0-manifest", type=Path, default=DEFAULT_P0_MANIFEST)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    p0_validation_path = args.p0_manifest / "validation_result.json"
    p0_validation_hash = sha256_file(p0_validation_path)
    p0_validation = json.loads(p0_validation_path.read_text(encoding="utf-8"))
    training_result = json.loads((args.manifest_dir / "training_result.json").read_text(encoding="utf-8"))
    history = json.loads((args.manifest_dir / "training_history.json").read_text(encoding="utf-8"))
    repeat = json.loads((args.manifest_dir / "determinism_audit.json").read_text(encoding="utf-8"))
    test_access = json.loads((args.manifest_dir / "test_access_audit.json").read_text(encoding="utf-8"))
    boundary = json.loads((args.manifest_dir / "deployment_boundary.json").read_text(encoding="utf-8"))
    metadata_path = args.model_dir / "public_sdt_pooled_mlp_v1.json"
    model_path = args.model_dir / "public_sdt_pooled_mlp_v1.npz"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    model_hash = sha256_file(model_path)
    arrays = np.load(model_path, allow_pickle=False)

    checks: list[dict[str, Any]] = []
    add_check(checks, "p0_identity", p0_validation_hash == contract["predecessor_validation_sha256"], p0_validation_hash)
    add_check(checks, "p0_usable", p0_validation["status"] in {"PASS", "PASS_WITH_LIMITATIONS"}, p0_validation["status"])
    add_check(checks, "dataset_identity", training_result["dataset_id"] == contract["dataset_id"], training_result["dataset_id"])
    add_check(checks, "model_identity", metadata["model_id"] == contract["model"]["model_id"], metadata["model_id"])
    expected_shapes = {"weights_1": (80, 32), "bias_1": (32,), "weights_2": (32, 3), "bias_2": (3,)}
    shape_result = {name: list(arrays[name].shape) if name in arrays else None for name in expected_shapes}
    shape_ok = all(name in arrays and tuple(arrays[name].shape) == shape for name, shape in expected_shapes.items())
    parameter_count = sum(int(np.prod(arrays[name].shape)) for name in expected_shapes if name in arrays)
    add_check(checks, "model_tensor_shapes", shape_ok, shape_result)
    add_check(checks, "parameter_count", parameter_count == int(contract["model"]["parameter_count"]), parameter_count)
    add_check(checks, "model_hash", model_hash == metadata["artifact_sha256"], model_hash)
    add_check(checks, "train_development_only", training_result["train_sample_count"] == 32000 and training_result["development_sample_count"] == 8000, training_result)
    test_ok = (
        test_access["test_path_configured"] is False
        and test_access["test_array_open_count"] == 0
        and test_access["test_sample_count_read"] == 0
        and test_access["test_metrics_computed"] is False
        and test_access["test_used_for_selection_or_tuning"] is False
    )
    add_check(checks, "test_inaccessible", test_ok, test_access)
    add_check(checks, "deterministic_repeat", repeat["status"] == "PASS" and repeat["weights_equal"] and repeat["history_equal"], repeat)
    boundary_ok = (
        boundary["deployment_mode"] == "SHADOW_ONLY"
        and boundary["default_activation"] is False
        and boundary["safety_authority"] is False
        and boundary["legacy_model_overwrite"] is False
        and boundary["model_manifest_default_update"] is False
        and boundary["mi48_claim"] is False
    )
    add_check(checks, "deployment_boundary", boundary_ok, boundary)
    add_check(checks, "legacy_manifest_unchanged", training_result["legacy_model_manifest_unchanged"], training_result["legacy_model_manifest_unchanged"])
    history_ok = (
        history["model_id"] == contract["model"]["model_id"]
        and 1 <= len(history["history"]) <= int(contract["training"]["epochs_max"])
    )
    add_check(checks, "training_history", history_ok, len(history["history"]))

    json_paths = list(args.manifest_dir.glob("*.json")) + [args.contract, metadata_path]
    absolute_pattern = re.compile(r"[A-Za-z]:[\\/]|file://", re.IGNORECASE)
    leaking = [path.name for path in json_paths if absolute_pattern.search(path.read_text(encoding="utf-8"))]
    add_check(checks, "no_absolute_path_persistence", not leaking, leaking)

    all_passed = all(item["passed"] for item in checks)
    result = {
        "schema_version": "safenest.thermal.b6r_p1.validation_result.v1",
        "stage_id": "B6R-P1",
        "status": "PASS_WITH_LIMITATIONS" if all_passed else "FAIL",
        "checks": checks,
        "model_id": contract["model"]["model_id"],
        "model_artifact_path": contract["model"]["artifact_path"],
        "model_artifact_sha256": model_hash,
        "validation_metrics_source": "DEVELOPMENT_ONLY",
        "test_metrics_computed": False,
        "limitations": [
            "PUBLIC_SDT_ONLY; not MI48 and no physical sensor validation.",
            "Model is a NumPy-only pooled MLP baseline, not SMALL_CNN_BASELINE_V1 and not exported to TFLite.",
            "No subject/session/recording identity; validation metrics are public split metrics only.",
            "HUMAN_FALL_PROXY is a posture proxy, not a real-fall or safety decision.",
            "Legacy default model and model_manifest.json were not changed.",
        ],
        "next_stage": "B6R-P1_REPORT_ONLY; any TFLite/Pi/runtime work requires a separately approved stage",
    }
    write_json(args.manifest_dir / "validation_result.json", result)
    artifact_paths = [model_path, metadata_path]
    artifact_paths += sorted(path for path in args.manifest_dir.glob("*.json") if path.name != "artifact_registry.json")
    registry = [
        {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in artifact_paths
    ]
    write_json(args.manifest_dir / "artifact_registry.json", {
        "schema_version": "safenest.thermal.b6r_p1.artifact_registry.v1",
        "artifacts": registry,
        "model_payload_git_tracked": True,
        "test_payload_included": False,
    })
    checksum_lines = []
    for path in sorted(args.manifest_dir.glob("*.json")):
        checksum_lines.append(f"{sha256_file(path)}  {path.relative_to(ROOT).as_posix()}")
    checksum_lines += [f"{sha256_file(model_path)}  {model_path.relative_to(ROOT).as_posix()}", f"{sha256_file(metadata_path)}  {metadata_path.relative_to(ROOT).as_posix()}"]
    (args.manifest_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n")
    print(f"B6R-P1 validation: {result['status']}", flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
