#!/usr/bin/env python3
"""B6R-P1: train a separate public-SDT-only model without touching legacy runtime."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p1_public_sdt_training_contract.json"
DEFAULT_P0_OUTPUT = ROOT / "datasets/thermal/materialized/B6R-P0_public_sdt_v1"
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Write an NPZ with fixed ZIP timestamps and sorted member names."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(
                buffer, np.asarray(arrays[name]), allow_pickle=False, version=(1, 0)
            )
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0
            archive.writestr(info, buffer.getvalue(), compresslevel=9)


def adaptive_mean_pool(images: np.ndarray, output_hw: tuple[int, int] = (8, 10)) -> np.ndarray:
    """Convert (N,62,80,1) into deterministic (N,80) pooled features."""
    if images.ndim != 4 or images.shape[1:] != (62, 80, 1):
        raise ValueError(f"Expected (N,62,80,1), got {images.shape}")
    output_h, output_w = output_hw
    h_edges = np.linspace(0, 62, output_h + 1, dtype=np.int64)
    w_edges = np.linspace(0, 80, output_w + 1, dtype=np.int64)
    features = np.empty((images.shape[0], output_h * output_w), dtype=np.float32)
    feature_index = 0
    for row in range(output_h):
        for col in range(output_w):
            block = images[:, h_edges[row] : h_edges[row + 1], w_edges[col] : w_edges[col + 1], 0]
            features[:, feature_index] = block.mean(axis=(1, 2), dtype=np.float32)
            feature_index += 1
    return features


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponent = np.exp(shifted, dtype=np.float64)
    return (exponent / exponent.sum(axis=1, keepdims=True)).astype(np.float32)


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, class_count: int = 3) -> float:
    scores = []
    for label in range(class_count):
        true_positive = np.sum((y_true == label) & (y_pred == label))
        false_positive = np.sum((y_true != label) & (y_pred == label))
        false_negative = np.sum((y_true == label) & (y_pred != label))
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        scores.append(2.0 * precision * recall / max(1e-12, precision + recall))
    return float(np.mean(scores))


def evaluate(
    features: np.ndarray,
    labels: np.ndarray,
    weights_1: np.ndarray,
    bias_1: np.ndarray,
    weights_2: np.ndarray,
    bias_2: np.ndarray,
    l2: float,
) -> dict[str, Any]:
    hidden = np.maximum(0.0, features @ weights_1 + bias_1)
    probabilities = softmax(hidden @ weights_2 + bias_2)
    sample_count = labels.shape[0]
    loss = -np.log(np.clip(probabilities[np.arange(sample_count), labels], 1e-7, 1.0)).mean()
    loss += 0.5 * l2 * float(np.sum(weights_1 * weights_1) + np.sum(weights_2 * weights_2))
    predictions = probabilities.argmax(axis=1).astype(np.int8)
    return {
        "loss": float(loss),
        "accuracy": float(np.mean(predictions == labels)),
        "macro_f1": macro_f1(labels, predictions),
        "predictions_sha256": hashlib.sha256(predictions.tobytes()).hexdigest(),
        "probabilities_sha256": hashlib.sha256(probabilities.astype("<f4").tobytes()).hexdigest(),
    }


def train_once(
    train_features: np.ndarray,
    train_labels: np.ndarray,
    development_features: np.ndarray,
    development_labels: np.ndarray,
    config: dict[str, Any],
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], int]:
    training = config["training"]
    model = config["model"]
    seed = int(training["seed"])
    rng = np.random.default_rng(seed)
    weights_1 = rng.normal(0.0, 0.02, (80, int(model["hidden_units"]))).astype("<f4")
    bias_1 = np.zeros((int(model["hidden_units"]),), dtype="<f4")
    weights_2 = rng.normal(0.0, 0.02, (int(model["hidden_units"]), 3)).astype("<f4")
    bias_2 = np.zeros((3,), dtype="<f4")
    order = rng.permutation(train_features.shape[0])
    batch_size = int(training["batch_size"])
    learning_rate = float(training["learning_rate"])
    l2 = float(training["l2"])
    patience = int(training["early_stopping_patience"])
    min_delta = float(training["early_stopping_min_delta"])
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    best = {
        "weights_1": weights_1.copy(),
        "bias_1": bias_1.copy(),
        "weights_2": weights_2.copy(),
        "bias_2": bias_2.copy(),
    }
    history: list[dict[str, Any]] = []

    for epoch in range(1, int(training["epochs_max"]) + 1):
        for start in range(0, order.shape[0], batch_size):
            indices = order[start : start + batch_size]
            features = train_features[indices]
            labels = train_labels[indices]
            hidden_pre = features @ weights_1 + bias_1
            hidden = np.maximum(0.0, hidden_pre)
            probabilities = softmax(hidden @ weights_2 + bias_2)
            probabilities[np.arange(labels.shape[0]), labels] -= 1.0
            probabilities /= labels.shape[0]
            gradient_w2 = hidden.T @ probabilities + l2 * weights_2
            gradient_b2 = probabilities.sum(axis=0)
            gradient_hidden = (probabilities @ weights_2.T) * (hidden_pre > 0.0)
            gradient_w1 = features.T @ gradient_hidden + l2 * weights_1
            gradient_b1 = gradient_hidden.sum(axis=0)
            weights_1 -= learning_rate * gradient_w1.astype("<f4")
            bias_1 -= learning_rate * gradient_b1.astype("<f4")
            weights_2 -= learning_rate * gradient_w2.astype("<f4")
            bias_2 -= learning_rate * gradient_b2.astype("<f4")

        train_metrics = evaluate(
            train_features, train_labels, weights_1, bias_1, weights_2, bias_2, l2
        )
        development_metrics = evaluate(
            development_features,
            development_labels,
            weights_1,
            bias_1,
            weights_2,
            bias_2,
            l2,
        )
        row = {
            "epoch": epoch,
            "train_loss": train_metrics["loss"],
            "train_accuracy": train_metrics["accuracy"],
            "development_loss": development_metrics["loss"],
            "development_accuracy": development_metrics["accuracy"],
            "development_macro_f1": development_metrics["macro_f1"],
        }
        history.append(row)
        current_loss = float(development_metrics["loss"])
        if current_loss < best_loss - min_delta:
            best_loss = current_loss
            best_epoch = epoch
            stale_epochs = 0
            best = {
                "weights_1": weights_1.copy(),
                "bias_1": bias_1.copy(),
                "weights_2": weights_2.copy(),
                "bias_2": bias_2.copy(),
            }
        else:
            stale_epochs += 1
            if stale_epochs >= patience:
                break

    return best, history, best_epoch


def load_training_inputs(
    p0_output: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load only P0 TRAIN and DEVELOPMENT arrays. This function has no test path."""
    train_images = np.load(p0_output / "train/images.npy", mmap_mode="r")
    train_labels = np.load(p0_output / "train/labels.npy", mmap_mode="r")
    development_images = np.load(p0_output / "validation/images.npy", mmap_mode="r")
    development_labels = np.load(p0_output / "validation/labels.npy", mmap_mode="r")
    train_features = adaptive_mean_pool(train_images)
    development_features = adaptive_mean_pool(development_images)
    return (
        train_features,
        np.asarray(train_labels, dtype=np.int8),
        development_features,
        np.asarray(development_labels, dtype=np.int8),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--p0-output", type=Path, default=DEFAULT_P0_OUTPUT)
    parser.add_argument("--p0-manifest", type=Path, default=DEFAULT_P0_MANIFEST)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repeat-audit", action="store_true", default=True)
    args = parser.parse_args()

    config = json.loads(args.contract.read_text(encoding="utf-8"))
    p0_result_path = args.p0_manifest / "validation_result.json"
    p0_result = json.loads(p0_result_path.read_text(encoding="utf-8"))
    p0_hash = sha256_file(p0_result_path)
    if p0_hash != config["predecessor_validation_sha256"]:
        raise ValueError("P0 validation artifact hash does not match P1 contract")
    if p0_result["status"] not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        raise ValueError("P0 validation is not usable for P1")

    required = [
        args.p0_output / "train/images.npy",
        args.p0_output / "train/labels.npy",
        args.p0_output / "validation/images.npy",
        args.p0_output / "validation/labels.npy",
    ]
    if any(not path.is_file() for path in required):
        raise FileNotFoundError("P0 TRAIN/DEVELOPMENT materialization is incomplete")
    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.manifest_dir.mkdir(parents=True, exist_ok=True)

    legacy_manifest = ROOT / "models/model_manifest.json"
    legacy_manifest_before = sha256_file(legacy_manifest) if legacy_manifest.is_file() else None
    print("[P1] loading P0 TRAIN/DEVELOPMENT only", flush=True)
    train_features, train_labels, development_features, development_labels = load_training_inputs(args.p0_output)
    print(f"[P1] features train={train_features.shape} development={development_features.shape}", flush=True)

    print("[P1] deterministic training pass 1", flush=True)
    best, history, best_epoch = train_once(
        train_features, train_labels, development_features, development_labels, config
    )
    repeat_best, repeat_history, repeat_epoch = train_once(
        train_features, train_labels, development_features, development_labels, config
    )
    arrays_match = all(np.array_equal(best[key], repeat_best[key]) for key in best)
    history_match = history == repeat_history and best_epoch == repeat_epoch
    if not arrays_match or not history_match:
        raise RuntimeError("P1 deterministic repeat audit failed")

    final_development = evaluate(
        development_features,
        development_labels,
        best["weights_1"],
        best["bias_1"],
        best["weights_2"],
        best["bias_2"],
        float(config["training"]["l2"]),
    )
    train_final = evaluate(
        train_features,
        train_labels,
        best["weights_1"],
        best["bias_1"],
        best["weights_2"],
        best["bias_2"],
        float(config["training"]["l2"]),
    )
    model_path = args.model_dir / "public_sdt_pooled_mlp_v1.npz"
    write_deterministic_npz(model_path, best)
    model_hash = sha256_file(model_path)
    metadata = {
        "schema_version": "safenest.thermal.b6r_p1.public_sdt_model_metadata.v1",
        "stage_id": config["stage_id"],
        "model_id": config["model"]["model_id"],
        "dataset_id": config["dataset_id"],
        "dataset_authority": config["dataset_authority"],
        "architecture": config["model"],
        "preprocessing_id": "PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1",
        "label_mapping_id": "SDT_POSTURE_TO_SAFENEST_3CLASS_PROXY_V1",
        "best_epoch": best_epoch,
        "train_sample_count": int(train_labels.shape[0]),
        "development_sample_count": int(development_labels.shape[0]),
        "train_metrics": train_final,
        "development_metrics": final_development,
        "artifact_path": repo_relative(model_path),
        "artifact_sha256": model_hash,
        "test_access_count": 0,
        "test_metrics_computed": False,
        "deployment_boundary": config["deployment_boundary"],
        "legacy_model_overwrite": False,
        "model_manifest_default_update": False,
    }
    metadata_path = args.model_dir / "public_sdt_pooled_mlp_v1.json"
    write_json(metadata_path, metadata)
    legacy_manifest_after = sha256_file(legacy_manifest) if legacy_manifest.is_file() else None

    history_digest = hashlib.sha256(stable_json_bytes(history)).hexdigest()
    training_result = {
        "schema_version": "safenest.thermal.b6r_p1.training_result.v1",
        "stage_id": config["stage_id"],
        "status": "PASS_WITH_LIMITATIONS",
        "dataset_id": config["dataset_id"],
        "model_id": config["model"]["model_id"],
        "model_artifact_path": repo_relative(model_path),
        "model_metadata_path": repo_relative(metadata_path),
        "model_artifact_sha256": model_hash,
        "train_sample_count": int(train_labels.shape[0]),
        "development_sample_count": int(development_labels.shape[0]),
        "test_sample_count_read": 0,
        "test_metrics_computed": False,
        "best_epoch": best_epoch,
        "history_sha256": history_digest,
        "train_metrics": train_final,
        "development_metrics": final_development,
        "parameter_count": int(config["model"]["parameter_count"]),
        "training_runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.system(),
        },
        "legacy_model_manifest_sha256_before": legacy_manifest_before,
        "legacy_model_manifest_sha256_after": legacy_manifest_after,
        "legacy_model_manifest_unchanged": legacy_manifest_before == legacy_manifest_after,
        "repeat_audit": {
            "executed": True,
            "weights_equal": arrays_match,
            "history_equal": history_match,
            "best_epoch_equal": best_epoch == repeat_epoch,
        },
        "deployment_boundary": config["deployment_boundary"],
    }
    write_json(args.manifest_dir / "training_result.json", training_result)
    write_json(args.manifest_dir / "training_contract_snapshot.json", config)
    write_json(args.manifest_dir / "training_history.json", {
        "schema_version": "safenest.thermal.b6r_p1.training_history.v1",
        "model_id": config["model"]["model_id"],
        "history": history,
    })
    write_json(args.manifest_dir / "determinism_audit.json", {
        "schema_version": "safenest.thermal.b6r_p1.determinism_audit.v1",
        "seed": config["training"]["seed"],
        "weights_equal": arrays_match,
        "history_equal": history_match,
        "best_epoch_equal": best_epoch == repeat_epoch,
        "history_sha256": history_digest,
        "status": "PASS" if arrays_match and history_match else "FAIL",
    })
    write_json(args.manifest_dir / "test_access_audit.json", {
        "schema_version": "safenest.thermal.b6r_p1.test_access_audit.v1",
        "test_path_configured": False,
        "test_array_open_count": 0,
        "test_sample_count_read": 0,
        "test_metrics_computed": False,
        "test_used_for_selection_or_tuning": False,
        "status": "PASS",
    })
    write_json(args.manifest_dir / "deployment_boundary.json", config["deployment_boundary"])
    print(
        f"B6R-P1 training PASS_WITH_LIMITATIONS: best_epoch={best_epoch}, "
        f"development_accuracy={final_development['accuracy']:.6f}, "
        f"development_macro_f1={final_development['macro_f1']:.6f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
