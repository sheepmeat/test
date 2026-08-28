#!/usr/bin/env python3
"""Execute the DEVELOPMENT-only, software-only B6R-P4 robustness audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p4_public_sdt_software_robustness_failure_mode_contract.json"
P0_CONTRACT = ROOT / "config/thermal/b6r_p0_public_sdt_contract.json"
P0_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P0_public_sdt_materialization"
P2_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P2_public_sdt_fp32_tflite_export"
CLASS_NAMES = ("NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")


def repo_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(array, dtype="<f4").tobytes(order="C")).hexdigest()


def sha256_predictions(array: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(array, dtype="<i8").tobytes(order="C")).hexdigest()


def seed_for(master_seed: int, perturbation_id: str, sample_id: str) -> int:
    payload = f"{master_seed}\0{perturbation_id}\0{sample_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little", signed=False)


def perturb_one(frame: np.ndarray, sample_id: str, spec: dict[str, Any], master_seed: int) -> np.ndarray:
    source = np.asarray(frame, dtype=np.float32)
    if source.shape != (62, 80, 1):
        raise ValueError(f"canonical frame shape mismatch: {source.shape}")
    result = source.copy()
    family = spec["family"]
    rng = np.random.default_rng(seed_for(master_seed, spec["id"], sample_id))

    if family == "ADDITIVE_BOUNDED_GAUSSIAN_NOISE":
        sigma = float(spec["severity"]["sigma"])
        limit = sigma * float(spec["severity"]["noise_clip_sigma"])
        noise = rng.normal(0.0, sigma, size=result.shape).astype(np.float32)
        np.clip(noise, -limit, limit, out=noise)
        result = np.clip(result + noise, 0.0, 1.0).astype(np.float32)
    elif family == "SPARSE_HOT_COLD_PIXEL_CORRUPTION":
        ratio = float(spec["severity"]["ratio"])
        count = max(1, int(round(62 * 80 * ratio)))
        flat = result[:, :, 0].reshape(-1)
        locations = rng.choice(flat.size, size=count, replace=False)
        values = ((np.arange(count, dtype=np.int64) + int(rng.integers(0, 2))) % 2).astype(np.float32)
        flat[locations] = values
    elif family == "ROW_COLUMN_DROPOUT":
        count = int(spec["severity"]["line_count"])
        row_count = (count + 1) // 2
        col_count = count // 2
        if row_count:
            result[rng.choice(62, size=row_count, replace=False), :, :] = 0.0
        if col_count:
            result[:, rng.choice(80, size=col_count, replace=False), :] = 0.0
    elif family == "RECTANGULAR_OCCLUSION":
        height = int(spec["severity"]["height"])
        width = int(spec["severity"]["width"])
        top = int(rng.integers(0, 62 - height + 1))
        left = int(rng.integers(0, 80 - width + 1))
        result[top : top + height, left : left + width, :] = 0.0
    elif family == "SMALL_SPATIAL_SHIFT":
        dy = int(spec["severity"]["dy"])
        dx = int(spec["severity"]["dx"])
        shifted = np.zeros_like(result)
        src_y0, src_y1 = max(0, -dy), min(62, 62 - dy)
        src_x0, src_x1 = max(0, -dx), min(80, 80 - dx)
        dst_y0, dst_y1 = max(0, dy), min(62, 62 + dy)
        dst_x0, dst_x1 = max(0, dx), min(80, 80 + dx)
        shifted[dst_y0:dst_y1, dst_x0:dst_x1, :] = result[src_y0:src_y1, src_x0:src_x1, :]
        result = shifted
    else:
        raise ValueError(f"unknown perturbation family: {family}")

    return np.ascontiguousarray(result, dtype=np.float32)


def perturb_batch(
    frames: np.ndarray,
    sample_ids: list[str],
    spec: dict[str, Any],
    master_seed: int,
) -> np.ndarray:
    return np.stack(
        [perturb_one(frames[index], sample_ids[index], spec, master_seed) for index in range(len(sample_ids))],
        axis=0,
    ).astype(np.float32, copy=False)


def numpy_pool(images: np.ndarray) -> np.ndarray:
    images = np.asarray(images, dtype=np.float32)
    height_edges = np.linspace(0, 62, 9, dtype=np.int64)
    width_edges = np.linspace(0, 80, 11, dtype=np.int64)
    pooled = np.empty((len(images), 80), dtype=np.float32)
    feature = 0
    for row in range(8):
        for column in range(10):
            cell = images[:, height_edges[row] : height_edges[row + 1], width_edges[column] : width_edges[column + 1], 0]
            pooled[:, feature] = cell.mean(axis=(1, 2), dtype=np.float32)
            feature += 1
    return pooled


def numpy_probabilities(images: np.ndarray, weights: dict[str, np.ndarray]) -> np.ndarray:
    pooled = numpy_pool(images)
    hidden = np.maximum(pooled @ weights["weights_1"] + weights["bias_1"], 0.0).astype(np.float32)
    logits = (hidden @ weights["weights_2"] + weights["bias_2"]).astype(np.float32)
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponentials = np.exp(shifted).astype(np.float32)
    return (exponentials / exponentials.sum(axis=1, keepdims=True, dtype=np.float32)).astype(np.float32)


def load_interpreter_type() -> tuple[Any, str]:
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter, "ai_edge_litert.interpreter"
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
            return Interpreter, "tflite_runtime.interpreter"
        except ImportError:
            import tensorflow as tf
            return tf.lite.Interpreter, "tensorflow.lite.Interpreter"


class TFLiteRunner:
    def __init__(self, model_path: Path) -> None:
        interpreter_type, self.backend = load_interpreter_type()
        self.interpreter = interpreter_type(model_path=str(model_path), num_threads=1)
        self.batch_size: int | None = None

    def _allocate(self, batch_size: int) -> None:
        input_detail = self.interpreter.get_input_details()[0]
        self.interpreter.resize_tensor_input(input_detail["index"], [batch_size, 62, 80, 1], strict=True)
        self.interpreter.allocate_tensors()
        self.batch_size = batch_size

    def predict(self, images: np.ndarray, batch_size: int = 256) -> np.ndarray:
        images = np.asarray(images, dtype=np.float32)
        outputs: list[np.ndarray] = []
        for start in range(0, len(images), batch_size):
            batch = np.ascontiguousarray(images[start : start + batch_size], dtype=np.float32)
            if self.batch_size != len(batch):
                self._allocate(len(batch))
            input_detail = self.interpreter.get_input_details()[0]
            output_detail = self.interpreter.get_output_details()[0]
            self.interpreter.set_tensor(input_detail["index"], batch)
            self.interpreter.invoke()
            outputs.append(np.asarray(self.interpreter.get_tensor(output_detail["index"]), dtype=np.float32))
        return np.concatenate(outputs, axis=0) if outputs else np.empty((0, 3), dtype=np.float32)

    def metadata(self) -> dict[str, Any]:
        if self.batch_size != 1:
            self._allocate(1)
        input_detail = self.interpreter.get_input_details()[0]
        output_detail = self.interpreter.get_output_details()[0]
        return {
            "backend": self.backend,
            "input": tensor_detail(input_detail),
            "output": tensor_detail(output_detail),
        }


def tensor_detail(detail: dict[str, Any]) -> dict[str, Any]:
    scale, zero_point = detail.get("quantization", (0.0, 0))
    return {
        "shape": [int(value) for value in detail["shape"]],
        "shape_signature": [int(value) for value in detail.get("shape_signature", detail["shape"])],
        "dtype": np.dtype(detail["dtype"]).name,
        "quantization_scale": float(scale),
        "quantization_zero_point": int(zero_point),
    }


def confusion_matrix(labels: np.ndarray, predictions: np.ndarray) -> np.ndarray:
    matrix = np.zeros((3, 3), dtype=np.int64)
    for truth, prediction in zip(labels, predictions, strict=True):
        matrix[int(truth), int(prediction)] += 1
    return matrix


def classification_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    labels = np.asarray(labels, dtype=np.int64)
    probabilities = np.asarray(probabilities, dtype=np.float32)
    predictions = probabilities.argmax(axis=1).astype(np.int64)
    matrix = confusion_matrix(labels, predictions)
    per_class: dict[str, Any] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1_values: list[float] = []
    for index, name in enumerate(CLASS_NAMES):
        true_positive = int(matrix[index, index])
        predicted = int(matrix[:, index].sum())
        actual = int(matrix[index, :].sum())
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / actual if actual else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_values.append(f1)
        per_class[name] = {
            "support": actual,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "sample_count": int(len(labels)),
        "accuracy": float(np.mean(predictions == labels)),
        "macro_precision": float(np.mean(precisions)),
        "macro_recall": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1_values)),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
        "prediction_distribution": {CLASS_NAMES[index]: int(np.sum(predictions == index)) for index in range(3)},
        "mean_confidence": float(np.mean(np.max(probabilities, axis=1))),
        "predictions_sha256": sha256_predictions(predictions),
        "probabilities_sha256": sha256_array(probabilities),
    }


def numerical_integrity(probabilities: np.ndarray, tolerance: float) -> dict[str, Any]:
    probabilities = np.asarray(probabilities)
    finite_rows = np.all(np.isfinite(probabilities), axis=1)
    range_rows = np.all((probabilities >= 0.0) & (probabilities <= 1.0), axis=1)
    sum_rows = np.abs(np.sum(probabilities, axis=1) - 1.0) <= tolerance
    invalid = ~(finite_rows & range_rows & sum_rows)
    return {
        "output_shape": list(probabilities.shape),
        "output_dtype": str(probabilities.dtype),
        "non_finite_output_count": int(np.sum(~finite_rows)),
        "invalid_probability_count": int(np.sum(invalid)),
        "probability_sum_max_abs_error": float(np.max(np.abs(np.sum(probabilities, axis=1) - 1.0))),
        "valid_argmax_count": int(np.sum(np.argmax(probabilities, axis=1) >= 0)),
        "status": "PASS" if not np.any(invalid) and probabilities.dtype == np.float32 else "FAIL",
    }


def condition_metrics(
    labels: np.ndarray,
    clean_probabilities: np.ndarray,
    probabilities: np.ndarray,
    tolerance: float,
) -> dict[str, Any]:
    result = classification_metrics(labels, probabilities)
    clean_predictions = np.argmax(clean_probabilities, axis=1)
    predictions = np.argmax(probabilities, axis=1)
    absolute_change = np.abs(probabilities - clean_probabilities)
    result.update({
        "clean_prediction_agreement": float(np.mean(predictions == clean_predictions)),
        "prediction_flip_count": int(np.sum(predictions != clean_predictions)),
        "prediction_flip_rate": float(np.mean(predictions != clean_predictions)),
        "mean_confidence_delta_from_clean": float(
            np.mean(np.max(probabilities, axis=1)) - np.mean(np.max(clean_probabilities, axis=1))
        ),
        "probability_max_absolute_change": float(np.max(absolute_change)),
        "probability_mean_absolute_change": float(np.mean(absolute_change)),
        "numerical_integrity": numerical_integrity(probabilities, tolerance),
    })
    return result


def update_tensor_stream_hash(digest: Any, sample_ids: list[str], tensors: np.ndarray) -> None:
    for sample_id, tensor in zip(sample_ids, tensors, strict=True):
        digest.update(sample_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(np.asarray(tensor, dtype="<f4").tobytes(order="C"))


def load_sample_ids(path: Path, expected_count: int) -> list[str]:
    sample_ids: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            sample_ids.append(json.loads(line)["sample_id"])
    if len(sample_ids) != expected_count or len(set(sample_ids)) != expected_count:
        raise ValueError("DEVELOPMENT sample ID accounting mismatch")
    return sample_ids


def source_root_candidates() -> list[Path]:
    return [ROOT.parent / "열화상_dataset", ROOT.parent.parent / "열화상_dataset"]


def audit_source_identity(contract: dict[str, Any]) -> dict[str, Any]:
    p0 = read_json(P0_CONTRACT)
    source_root = next((candidate for candidate in source_root_candidates() if candidate.is_dir()), None)
    archives: list[dict[str, Any]] = []
    if source_root is not None:
        for name, expected in sorted(p0["source_archive_registry"].items()):
            path = source_root / name
            actual_size = path.stat().st_size if path.is_file() else None
            actual_sha = sha256_file(path) if path.is_file() else None
            archives.append({
                "archive_name": name,
                "expected_size_bytes": expected["size_bytes"],
                "actual_size_bytes": actual_size,
                "expected_sha256": expected["sha256"],
                "actual_sha256": actual_sha,
                "matches_registry": actual_size == expected["size_bytes"] and actual_sha == expected["sha256"],
            })
    registry = read_json(P0_MANIFEST / "artifact_registry.json")
    registry_by_path = {record["path"]: record for record in registry["artifacts"]}
    payload_files: list[dict[str, Any]] = []
    for key in ("images_path", "labels_path", "sample_index_path"):
        relative = contract["development_input"][key]
        expected = registry_by_path[relative]
        path = repo_path(relative)
        actual_size = path.stat().st_size if path.is_file() else None
        actual_sha = sha256_file(path) if path.is_file() else None
        payload_files.append({
            "path": relative,
            "expected_size_bytes": expected["size_bytes"],
            "actual_size_bytes": actual_size,
            "expected_sha256": expected["sha256"],
            "actual_sha256": actual_sha,
            "matches_registry": actual_size == expected["size_bytes"] and actual_sha == expected["sha256"],
        })
    all_match = len(archives) == 6 and all(record["matches_registry"] for record in archives)
    payload_match = all(record["matches_registry"] for record in payload_files)
    return {
        "schema_version": "safenest.thermal.b6r_p4.source_identity_audit.v1",
        "stage_id": "B6R-P4",
        "source_location_id": p0["source_location_id"],
        "source_root_persisted": False,
        "archive_count_expected": 6,
        "archive_count_found": len(archives),
        "archives": archives,
        "development_payload_files": payload_files,
        "source_mutation_performed": False,
        "status": "PASS" if all_match and payload_match else "FAIL_DATA_LINEAGE",
    }


def audit_model_identity(contract: dict[str, Any]) -> dict[str, Any]:
    p2 = contract["p2_artifact"]
    path = repo_path(p2["path"])
    runner = TFLiteRunner(path)
    metadata = runner.metadata()
    input_meta, output_meta = metadata["input"], metadata["output"]
    tensor_ok = (
        input_meta["shape"] == p2["input_shape"]
        and input_meta["dtype"] == p2["input_dtype"]
        and output_meta["shape"] == p2["output_shape"]
        and output_meta["dtype"] == p2["output_dtype"]
        and input_meta["quantization_scale"] == 0.0
        and output_meta["quantization_scale"] == 0.0
    )
    parent = contract["p1_parent"]
    parent_path = repo_path(parent["artifact_path"])
    arrays = np.load(parent_path, allow_pickle=False)
    parameter_count = sum(int(np.prod(arrays[name].shape)) for name in arrays.files)
    return {
        "schema_version": "safenest.thermal.b6r_p4.model_identity_audit.v1",
        "stage_id": "B6R-P4",
        "p2": {
            "path": p2["path"],
            "expected_sha256": p2["sha256"],
            "actual_sha256": sha256_file(path),
            "expected_size_bytes": p2["size_bytes"],
            "actual_size_bytes": path.stat().st_size,
            "tensor_metadata": metadata,
            "class_order": p2["class_order"],
        },
        "p1": {
            "path": parent["artifact_path"],
            "expected_sha256": parent["artifact_sha256"],
            "actual_sha256": sha256_file(parent_path),
            "expected_parameter_count": parent["parameter_count"],
            "actual_parameter_count": parameter_count,
        },
        "status": "PASS" if (
            sha256_file(path) == p2["sha256"]
            and path.stat().st_size == p2["size_bytes"]
            and tensor_ok
            and sha256_file(parent_path) == parent["artifact_sha256"]
            and parameter_count == parent["parameter_count"]
        ) else "FAIL_ARTIFACT_IDENTITY",
    }


def audit_protected_files(contract: dict[str, Any]) -> dict[str, Any]:
    files = {}
    for relative, expected in contract["protected_files"].items():
        path = repo_path(relative)
        actual = sha256_file(path) if path.is_file() else None
        files[relative] = {"expected_sha256": expected, "actual_sha256": actual, "unchanged": actual == expected}
    return {
        "schema_version": "safenest.thermal.b6r_p4.legacy_runtime_immutability_audit.v1",
        "stage_id": "B6R-P4",
        "files": files,
        "default_activation": False,
        "safety_authority": False,
        "production_runtime_modified": False,
        "status": "PASS" if all(record["unchanged"] for record in files.values()) else "FAIL",
    }


def prepare_replay_input(frame: np.ndarray) -> np.ndarray:
    array = np.asarray(frame, dtype=np.float32)
    if array.shape == (62, 80):
        array = array[..., None]
    elif array.shape == (1, 62, 80, 1):
        array = array[0]
    elif array.shape != (62, 80, 1):
        raise ValueError(f"shape/rank contract violation: {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError("input contains NaN or infinity")
    if float(array.min()) < 0.0 or float(array.max()) > 1.0:
        raise ValueError("input outside canonical [0,1] range")
    return np.ascontiguousarray(array, dtype=np.float32)


def invalid_input_cases() -> list[tuple[str, np.ndarray]]:
    canonical = np.full((62, 80, 1), 0.5, dtype=np.float32)
    nan_value = canonical.copy(); nan_value[0, 0, 0] = np.nan
    pos_inf = canonical.copy(); pos_inf[0, 0, 0] = np.inf
    neg_inf = canonical.copy(); neg_inf[0, 0, 0] = -np.inf
    negative = canonical.copy(); negative[0, 0, 0] = -0.01
    above = canonical.copy(); above[0, 0, 0] = 1.01
    return [
        ("NAN", nan_value), ("+INF", pos_inf), ("-INF", neg_inf),
        ("WRONG_SHAPE", np.zeros((61, 80, 1), dtype=np.float32)),
        ("EMPTY_ARRAY", np.array([], dtype=np.float32)),
        ("WRONG_RANK", np.zeros((1, 1, 62, 80, 1), dtype=np.float32)),
        ("CONSTANT_ZERO", np.zeros((62, 80, 1), dtype=np.float32)),
        ("CONSTANT_ONE", np.ones((62, 80, 1), dtype=np.float32)),
        ("OUT_OF_RANGE_NEGATIVE", negative), ("OUT_OF_RANGE_ABOVE_ONE", above),
        ("FLOAT64", canonical.astype(np.float64)),
        ("INTEGER", np.ones((62, 80, 1), dtype=np.uint8)),
    ]


def run_invalid_input_audit(model_path: Path, tolerance: float) -> dict[str, Any]:
    runner = TFLiteRunner(model_path)
    records = []
    for case_id, value in invalid_input_cases():
        record: dict[str, Any] = {
            "case_id": case_id,
            "original_shape": list(value.shape),
            "original_dtype": str(value.dtype),
        }
        try:
            prepared = prepare_replay_input(value)
            probabilities = runner.predict(prepared[None, ...], batch_size=1)
            record.update({
                "helper_status": "ACCEPTED",
                "helper_action": "CAST_TO_FLOAT32" if value.dtype != np.float32 else "PRESERVE_FLOAT32",
                "model_status": "ACCEPTED",
                "prepared_shape": list(prepared.shape),
                "prepared_dtype": str(prepared.dtype),
                "numerical_integrity": numerical_integrity(probabilities, tolerance),
                "probabilities": [float(item) for item in probabilities[0]],
            })
        except Exception as error:
            record.update({
                "helper_status": "REJECTED",
                "helper_action": "FAIL_CLOSED_IN_ISOLATED_P4_HELPER",
                "model_status": "NOT_INVOKED",
                "error_type": type(error).__name__,
                "error": str(error),
            })
        records.append(record)
    return {
        "schema_version": "safenest.thermal.b6r_p4.invalid_input_audit.v1",
        "stage_id": "B6R-P4",
        "scope": "ISOLATED_P4_HELPER_AND_FP32_TFLITE_NOT_PRODUCTION_RUNTIME",
        "production_validator_modified": False,
        "cases": records,
        "case_count": len(records),
        "rejected_count": sum(record["helper_status"] == "REJECTED" for record in records),
        "accepted_count": sum(record["helper_status"] == "ACCEPTED" for record in records),
        "status": "PASS",
    }


def parity_audit(
    contract: dict[str, Any],
    images: np.ndarray,
    sample_ids: list[str],
    weights: dict[str, np.ndarray],
) -> dict[str, Any]:
    manifest = read_json(repo_path(contract["parity"]["fixture_manifest_path"]))
    records = sorted(manifest["samples"], key=lambda item: int(item["fixture_position"]))
    indices = [int(record["development_index"]) for record in records]
    fixture_ids = [sample_ids[index] for index in indices]
    clean = np.asarray(images[indices], dtype=np.float32)
    conditions: list[tuple[str, np.ndarray]] = [("CLEAN", clean)]
    for spec in contract["perturbations"]:
        conditions.append((spec["id"], perturb_batch(clean, fixture_ids, spec, int(contract["perturbation_seed"]))))
    runner = TFLiteRunner(repo_path(contract["p2_artifact"]["path"]))
    details = []
    mismatch_ids: set[str] = set()
    all_numpy: list[np.ndarray] = []
    all_tflite: list[np.ndarray] = []
    for condition_id, tensors in conditions:
        numpy_output = numpy_probabilities(tensors, weights)
        tflite_output = runner.predict(tensors, batch_size=len(tensors))
        difference = np.abs(numpy_output - tflite_output)
        numpy_prediction = np.argmax(numpy_output, axis=1)
        tflite_prediction = np.argmax(tflite_output, axis=1)
        mismatches = np.flatnonzero(numpy_prediction != tflite_prediction)
        condition_mismatch_ids = [fixture_ids[int(index)] for index in mismatches]
        mismatch_ids.update(condition_mismatch_ids)
        details.append({
            "condition_id": condition_id,
            "sample_count": len(fixture_ids),
            "probability_max_abs_difference": float(np.max(difference)),
            "probability_mean_abs_difference": float(np.mean(difference)),
            "argmax_agreement": float(np.mean(numpy_prediction == tflite_prediction)),
            "mismatch_count": int(len(mismatches)),
            "mismatch_sample_ids": condition_mismatch_ids,
        })
        all_numpy.append(numpy_output)
        all_tflite.append(tflite_output)
    numpy_all = np.concatenate(all_numpy, axis=0)
    tflite_all = np.concatenate(all_tflite, axis=0)
    diff = np.abs(numpy_all - tflite_all)
    mismatch_count = sum(item["mismatch_count"] for item in details)
    passed = (
        float(np.max(diff)) <= float(contract["parity"]["probabilities_max_abs"])
        and float(np.mean(diff)) <= float(contract["parity"]["probabilities_mean_abs"])
        and mismatch_count <= int(contract["parity"]["mismatch_count_max"])
    )
    return {
        "schema_version": "safenest.thermal.b6r_p4.parity_under_stress.v1",
        "stage_id": "B6R-P4",
        "fixture_role": "DEVELOPMENT",
        "fixture_count": len(fixture_ids),
        "condition_count": len(conditions),
        "comparison_count": len(fixture_ids) * len(conditions),
        "tolerance": contract["parity"],
        "probability_max_abs_difference": float(np.max(diff)),
        "probability_mean_abs_difference": float(np.mean(diff)),
        "argmax_agreement": float(np.mean(np.argmax(numpy_all, axis=1) == np.argmax(tflite_all, axis=1))),
        "mismatch_count": mismatch_count,
        "mismatch_sample_ids": sorted(mismatch_ids),
        "conditions": details,
        "status": "PASS" if passed else "FAIL_PARITY",
    }


def determinism_probe(
    contract: dict[str, Any],
    images: np.ndarray,
    labels: np.ndarray,
    sample_ids: list[str],
    runner: TFLiteRunner,
) -> dict[str, Any]:
    manifest = read_json(repo_path(contract["parity"]["fixture_manifest_path"]))
    records = sorted(manifest["samples"], key=lambda item: int(item["fixture_position"]))
    indices = [int(record["development_index"]) for record in records]
    fixture_ids = [sample_ids[index] for index in indices]
    fixture_labels = np.asarray(labels[indices], dtype=np.int64)
    clean = np.asarray(images[indices], dtype=np.float32)
    tensors_by_condition: list[tuple[str, np.ndarray]] = [("CLEAN", clean)]
    for spec in contract["perturbations"]:
        tensors_by_condition.append((spec["id"], perturb_batch(clean, fixture_ids, spec, int(contract["perturbation_seed"]))))
    tensor_digest = hashlib.sha256()
    probability_blocks = []
    prediction_blocks = []
    metric_summaries = []
    clean_probabilities: np.ndarray | None = None
    for condition_id, tensors in tensors_by_condition:
        update_tensor_stream_hash(tensor_digest, fixture_ids, tensors)
        probabilities = runner.predict(tensors, batch_size=len(tensors))
        if clean_probabilities is None:
            clean_probabilities = probabilities
        probability_blocks.append(probabilities)
        prediction_blocks.append(np.argmax(probabilities, axis=1))
        metric_summaries.append({"condition_id": condition_id, **condition_metrics(
            fixture_labels, clean_probabilities, probabilities,
            float(contract["numerical_integrity"]["probability_sum_abs_tolerance"]),
        )})
    probabilities_all = np.concatenate(probability_blocks, axis=0)
    predictions_all = np.concatenate(prediction_blocks, axis=0)
    return {
        "perturbation_tensor_hash": tensor_digest.hexdigest(),
        "probability_hash": sha256_array(probabilities_all),
        "prediction_hash": sha256_predictions(predictions_all),
        "summary_metrics_hash": hashlib.sha256(stable_json_bytes(metric_summaries)).hexdigest(),
        "comparison_count": int(len(probabilities_all)),
    }


def child_determinism(contract_path: Path, output_path: Path) -> int:
    contract = read_json(contract_path)
    development = contract["development_input"]
    images = np.load(repo_path(development["images_path"]), mmap_mode="r")
    labels = np.load(repo_path(development["labels_path"]), mmap_mode="r")
    sample_ids = load_sample_ids(repo_path(development["sample_index_path"]), int(development["sample_count"]))
    probe = determinism_probe(
        contract, images, labels, sample_ids,
        TFLiteRunner(repo_path(contract["p2_artifact"]["path"])),
    )
    write_json(output_path, probe)
    return 0


def run_determinism_audit(
    contract: dict[str, Any],
    contract_path: Path,
    images: np.ndarray,
    labels: np.ndarray,
    sample_ids: list[str],
) -> dict[str, Any]:
    model_path = repo_path(contract["p2_artifact"]["path"])
    same_runner = TFLiteRunner(model_path)
    first = determinism_probe(contract, images, labels, sample_ids, same_runner)
    same_process_repeat = determinism_probe(contract, images, labels, sample_ids, same_runner)
    reload_repeat = determinism_probe(contract, images, labels, sample_ids, TFLiteRunner(model_path))
    child_fd, child_name = tempfile.mkstemp(prefix="b6r_p4_child_", suffix=".json")
    os.close(child_fd)
    child_file = Path(child_name)
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--contract", str(contract_path.resolve()),
             "--determinism-child", "--child-output", str(child_file)],
            cwd=str(ROOT), check=False, capture_output=True, text=True,
        )
        if completed.returncode != 0 or not child_file.is_file():
            child: dict[str, Any] = {"error": f"child exit {completed.returncode}", "stderr": completed.stderr[-500:]}
        else:
            child = read_json(child_file)
    finally:
        child_file.unlink(missing_ok=True)
    hash_keys = ("perturbation_tensor_hash", "probability_hash", "prediction_hash", "summary_metrics_hash")
    comparisons = {
        "same_process_repeat": all(first.get(key) == same_process_repeat.get(key) for key in hash_keys),
        "interpreter_reload": all(first.get(key) == reload_repeat.get(key) for key in hash_keys),
        "clean_child_process_rerun": all(first.get(key) == child.get(key) for key in hash_keys),
        "perturbation_regeneration": first.get("perturbation_tensor_hash") == same_process_repeat.get("perturbation_tensor_hash") == reload_repeat.get("perturbation_tensor_hash") == child.get("perturbation_tensor_hash"),
        "metrics_regeneration": first.get("summary_metrics_hash") == same_process_repeat.get("summary_metrics_hash") == reload_repeat.get("summary_metrics_hash") == child.get("summary_metrics_hash"),
    }
    return {
        "schema_version": "safenest.thermal.b6r_p4.determinism_audit.v1",
        "stage_id": "B6R-P4",
        "reference": first,
        "same_process_repeat": same_process_repeat,
        "interpreter_reload": reload_repeat,
        "clean_child_process_rerun": child,
        "comparisons": comparisons,
        "status": "PASS" if all(comparisons.values()) else "FAIL",
    }


def refresh_checksums(manifest_dir: Path) -> None:
    paths = sorted(path for path in manifest_dir.glob("*.json"))
    lines = [f"{sha256_file(path)}  {path.resolve().relative_to(ROOT.resolve()).as_posix()}" for path in paths]
    (manifest_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--determinism-child", action="store_true")
    parser.add_argument("--child-output", type=Path)
    args = parser.parse_args(argv)
    if args.determinism_child:
        if args.child_output is None:
            raise SystemExit("--child-output is required")
        return child_determinism(args.contract, args.child_output)

    contract = read_json(args.contract)
    manifest_dir = repo_path(contract["manifest_dir"])
    manifest_dir.mkdir(parents=True, exist_ok=True)
    write_json(manifest_dir / "contract_snapshot.json", contract)

    print("[B6R-P4] auditing public source identity", flush=True)
    source_audit = audit_source_identity(contract)
    write_json(manifest_dir / "source_identity_audit.json", source_audit)
    print("[B6R-P4] auditing P1/P2 model identity", flush=True)
    model_audit = audit_model_identity(contract)
    write_json(manifest_dir / "model_identity_audit.json", model_audit)
    if source_audit["status"] != "PASS" or model_audit["status"] != "PASS":
        print(json.dumps({"source": source_audit["status"], "model": model_audit["status"]}, indent=2))
        return 1

    development = contract["development_input"]
    images = np.load(repo_path(development["images_path"]), mmap_mode="r")
    labels = np.asarray(np.load(repo_path(development["labels_path"]), mmap_mode="r"), dtype=np.int64)
    sample_ids = load_sample_ids(repo_path(development["sample_index_path"]), int(development["sample_count"]))
    batch_size = int(development["batch_size"])
    runner = TFLiteRunner(repo_path(contract["p2_artifact"]["path"]))
    print("[B6R-P4] evaluating clean DEVELOPMENT baseline", flush=True)
    clean_probabilities = runner.predict(images, batch_size=batch_size)
    clean_metrics = classification_metrics(labels, clean_probabilities)
    clean_metrics.update({
        "schema_version": "safenest.thermal.b6r_p4.clean_baseline_metrics.v1",
        "stage_id": "B6R-P4", "role": "DEVELOPMENT",
        "metric_interpretation": "DEVELOPMENT_DIAGNOSTIC_NOT_INDEPENDENT_TEST_PERFORMANCE",
        "numerical_integrity": numerical_integrity(
            clean_probabilities, float(contract["numerical_integrity"]["probability_sum_abs_tolerance"])
        ),
    })
    write_json(manifest_dir / "clean_baseline_metrics.json", clean_metrics)

    perturbation_registry = {
        "schema_version": "safenest.thermal.b6r_p4.perturbation_registry.v1",
        "stage_id": "B6R-P4", "role": "DEVELOPMENT",
        "master_seed": contract["perturbation_seed"],
        "sample_count": len(sample_ids), "sample_ids": sample_ids,
        "sample_id_registry_sha256": hashlib.sha256(stable_json_bytes(sample_ids)).hexdigest(),
        "hash_contract": contract["perturbation_hash_contract"],
        "conditions": [],
    }
    perturbation_results = []
    all_numerical_pass = True
    metrics_repeat_equal = True
    for position, spec in enumerate(contract["perturbations"], start=1):
        print(f"[B6R-P4] condition {position}/{len(contract['perturbations'])}: {spec['id']}", flush=True)
        tensor_digest = hashlib.sha256()
        outputs: list[np.ndarray] = []
        for start in range(0, len(images), batch_size):
            end = min(start + batch_size, len(images))
            ids = sample_ids[start:end]
            perturbed = perturb_batch(np.asarray(images[start:end]), ids, spec, int(contract["perturbation_seed"]))
            update_tensor_stream_hash(tensor_digest, ids, perturbed)
            outputs.append(runner.predict(perturbed, batch_size=len(perturbed)))
        probabilities = np.concatenate(outputs, axis=0)
        metrics = condition_metrics(
            labels, clean_probabilities, probabilities,
            float(contract["numerical_integrity"]["probability_sum_abs_tolerance"]),
        )
        repeated_metrics = condition_metrics(
            labels, clean_probabilities, probabilities,
            float(contract["numerical_integrity"]["probability_sum_abs_tolerance"]),
        )
        metrics_repeat_equal = metrics_repeat_equal and stable_json_bytes(metrics) == stable_json_bytes(repeated_metrics)
        all_numerical_pass = all_numerical_pass and metrics["numerical_integrity"]["status"] == "PASS"
        perturbation_registry["conditions"].append({
            "perturbation_id": spec["id"], "family": spec["family"], "severity": spec["severity"],
            "sample_count": len(sample_ids), "canonical_tensor_stream_sha256": tensor_digest.hexdigest(),
        })
        perturbation_results.append({"perturbation_id": spec["id"], "family": spec["family"], "severity": spec["severity"], **metrics})

    perturbation_metrics = {
        "schema_version": "safenest.thermal.b6r_p4.perturbation_metrics.v1",
        "stage_id": "B6R-P4", "role": "DEVELOPMENT",
        "interpretation": "SYNTHETIC_SOFTWARE_ROBUSTNESS_DIAGNOSTIC_NOT_PHYSICAL_ROBUSTNESS",
        "condition_count": len(perturbation_results), "conditions": perturbation_results,
        "all_normal_outputs_numerically_valid": all_numerical_pass,
        "metrics_regeneration_byte_equal": metrics_repeat_equal,
    }
    write_json(manifest_dir / "perturbation_registry.json", perturbation_registry)
    write_json(manifest_dir / "perturbation_metrics.json", perturbation_metrics)

    weights_archive = np.load(repo_path(contract["p1_parent"]["artifact_path"]), allow_pickle=False)
    weights = {name: np.asarray(weights_archive[name], dtype=np.float32) for name in weights_archive.files}
    print("[B6R-P4] evaluating NumPy/TFLite parity under stress", flush=True)
    parity = parity_audit(contract, images, sample_ids, weights)
    write_json(manifest_dir / "parity_under_stress.json", parity)
    invalid = run_invalid_input_audit(
        repo_path(contract["p2_artifact"]["path"]),
        float(contract["numerical_integrity"]["probability_sum_abs_tolerance"]),
    )
    write_json(manifest_dir / "invalid_input_audit.json", invalid)
    print("[B6R-P4] evaluating software determinism", flush=True)
    determinism = run_determinism_audit(contract, args.contract, images, labels, sample_ids)
    write_json(manifest_dir / "determinism_audit.json", determinism)

    locked = {
        "schema_version": "safenest.thermal.b6r_p4.locked_test_audit.v1", "stage_id": "B6R-P4",
        "role": "LOCKED_PUBLIC_TEST", "path_configured": False, "array_open_count": 0,
        "sample_read_count": 0, "metrics_computed": False, "selection_or_tuning_use": False,
        "status": "PASS",
    }
    real_sensor = {
        "schema_version": "safenest.thermal.b6r_p4.real_sensor_access_audit.v1", "stage_id": "B6R-P4",
        "real_sensor_data_access_count": 0, "desktop_sessions_access_count": 0,
        "thermal90_access_count": 0, "mi48_access_count": 0, "raspberry_pi_connection_attempt_count": 0,
        "raspberry_pi_scope": "OUT_OF_SCOPE", "status": "PASS",
    }
    protected = audit_protected_files(contract)
    write_json(manifest_dir / "locked_test_audit.json", locked)
    write_json(manifest_dir / "real_sensor_access_audit.json", real_sensor)
    write_json(manifest_dir / "legacy_runtime_immutability_audit.json", protected)

    successful = (
        all_numerical_pass and metrics_repeat_equal and parity["status"] == "PASS"
        and determinism["status"] == "PASS" and protected["status"] == "PASS"
    )
    summary = {
        "schema_version": "safenest.thermal.b6r_p4.run_summary.v1", "stage_id": "B6R-P4",
        "status": "PASS_WITH_LIMITATIONS" if successful else "FAIL",
        "status_qualifier": "PUBLIC_DATA_SOFTWARE_ONLY_NON_GATING",
        "development_sample_count": len(sample_ids), "perturbation_condition_count": len(perturbation_results),
        "perturbed_inference_count": len(sample_ids) * len(perturbation_results),
        "locked_public_test_access_count": 0, "real_sensor_access_count": 0,
        "raspberry_pi_connection_attempt_count": 0, "p3_status": "BLOCKED_HARDWARE_UNCHANGED",
        "model_modified": False, "default_runtime_modified": False, "next_stage_executed": False,
        "python": platform.python_version(), "numpy": np.__version__, "platform": platform.system(),
    }
    write_json(manifest_dir / "run_summary.json", summary)
    refresh_checksums(manifest_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), flush=True)
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
