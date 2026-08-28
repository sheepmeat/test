#!/usr/bin/env python3
"""B6R-P2: reconstruct the frozen P1 NumPy model and export FP32 TFLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np
import tensorflow as tf


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p2_public_sdt_fp32_tflite_contract.json"
P1_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P1_public_sdt_controlled_training"
P0_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P0_public_sdt_materialization"
LEGACY_AUDIT_PATHS = (
    "models/model_manifest.json",
    "models/thermal/thermal_fall_int8_v0.1.0.tflite",
    "inference/thermal_interpreter.py",
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(array, dtype="<f4").tobytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def repo_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def numpy_adaptive_mean_pool(images: np.ndarray) -> np.ndarray:
    """Canonical P1 integer-linspace adaptive mean pool."""
    array = np.asarray(images, dtype=np.float32)
    if array.ndim != 4 or array.shape[1:] != (62, 80, 1):
        raise ValueError(f"Expected (N,62,80,1), got {array.shape}")
    height_edges = np.linspace(0, 62, 9, dtype=np.int64)
    width_edges = np.linspace(0, 80, 11, dtype=np.int64)
    features = np.empty((array.shape[0], 80), dtype=np.float32)
    index = 0
    for row in range(8):
        for column in range(10):
            block = array[
                :,
                height_edges[row] : height_edges[row + 1],
                width_edges[column] : width_edges[column + 1],
                0,
            ]
            features[:, index] = block.mean(axis=(1, 2), dtype=np.float32)
            index += 1
    return features


def numpy_softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponent = np.exp(shifted, dtype=np.float64)
    return (exponent / exponent.sum(axis=1, keepdims=True)).astype(np.float32)


def numpy_intermediates(images: np.ndarray, weights: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    pooled = numpy_adaptive_mean_pool(images)
    hidden = np.maximum(0.0, pooled @ weights["weights_1"] + weights["bias_1"])
    logits = hidden @ weights["weights_2"] + weights["bias_2"]
    probabilities = numpy_softmax(logits)
    return {
        "pooled": pooled.astype(np.float32),
        "hidden": hidden.astype(np.float32),
        "logits": logits.astype(np.float32),
        "probabilities": probabilities,
    }


class AdaptiveMeanPoolP1(tf.keras.layers.Layer):
    """TensorFlow equivalent of P1's integer-linspace adaptive mean pool."""

    def call(self, inputs: tf.Tensor) -> tf.Tensor:
        height_edges = (0, 7, 15, 23, 31, 38, 46, 54, 62)
        width_edges = (0, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80)
        cells = []
        for row in range(8):
            for column in range(10):
                block = inputs[
                    :,
                    height_edges[row] : height_edges[row + 1],
                    width_edges[column] : width_edges[column + 1],
                    0,
                ]
                cells.append(tf.reduce_mean(block, axis=(1, 2)))
        return tf.stack(cells, axis=1)

    def compute_output_shape(self, input_shape: tuple[int | None, ...]) -> tuple[int | None, int]:
        return input_shape[0], 80


def build_models(weights: dict[str, np.ndarray]) -> tuple[tf.keras.Model, tf.keras.Model]:
    inputs = tf.keras.Input(shape=(62, 80, 1), dtype=tf.float32, name="thermal_frame")
    pooled = AdaptiveMeanPoolP1(name="adaptive_mean_pool_p1")(inputs)
    hidden = tf.keras.layers.Dense(32, activation="relu", name="hidden_relu")(pooled)
    logits = tf.keras.layers.Dense(3, activation=None, name="class_logits")(hidden)
    probabilities = tf.keras.layers.Softmax(name="class_probabilities")(logits)
    model = tf.keras.Model(inputs=inputs, outputs=probabilities, name="public_sdt_pooled_mlp_fp32")
    model.get_layer("hidden_relu").set_weights([weights["weights_1"], weights["bias_1"]])
    model.get_layer("class_logits").set_weights([weights["weights_2"], weights["bias_2"]])
    intermediate = tf.keras.Model(
        inputs=inputs,
        outputs=[pooled, hidden, logits, probabilities],
        name="public_sdt_pooled_mlp_fp32_intermediates",
    )
    return model, intermediate


def convert_fp32(model: tf.keras.Model) -> bytes:
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = []
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    converter.inference_input_type = tf.float32
    converter.inference_output_type = tf.float32
    return converter.convert()


def _tensor_detail(detail: dict[str, Any]) -> dict[str, Any]:
    quantization_parameters = detail["quantization_parameters"]
    return {
        "name": str(detail["name"]),
        "index": int(detail["index"]),
        "shape": [int(value) for value in detail["shape"]],
        "shape_signature": [int(value) for value in detail["shape_signature"]],
        "dtype": np.dtype(detail["dtype"]).name,
        "quantization": {
            "scale": float(detail["quantization"][0]),
            "zero_point": int(detail["quantization"][1]),
            "scales": [float(value) for value in quantization_parameters["scales"]],
            "zero_points": [int(value) for value in quantization_parameters["zero_points"]],
            "quantized_dimension": int(quantization_parameters["quantized_dimension"]),
        },
    }


def tflite_probabilities(model_path: Path, images: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    outputs = np.empty((images.shape[0], 3), dtype=np.float32)
    for index, image in enumerate(images):
        interpreter.set_tensor(input_detail["index"], image[None].astype(np.float32))
        interpreter.invoke()
        outputs[index] = interpreter.get_tensor(output_detail["index"])[0]
    metadata = {
        "interpreter": "tensorflow.lite.Interpreter",
        "input": _tensor_detail(input_detail),
        "output": _tensor_detail(output_detail),
        "unexpected_quantization": bool(
            input_detail["quantization"][0] != 0.0
            or output_detail["quantization"][0] != 0.0
            or not np.issubdtype(input_detail["dtype"], np.floating)
            or not np.issubdtype(output_detail["dtype"], np.floating)
        ),
    }
    return outputs, metadata


def select_fixture(
    labels: np.ndarray, probabilities: np.ndarray, samples_per_class: int
) -> tuple[list[int], dict[int, str]]:
    typical_count = samples_per_class // 2
    boundary_count = samples_per_class - typical_count
    order = np.sort(probabilities, axis=1)
    margins = order[:, -1] - order[:, -2]
    selected: list[int] = []
    reasons: dict[int, str] = {}
    for class_index in range(3):
        candidates = np.flatnonzero(labels == class_index)
        typical = sorted(
            (int(index) for index in candidates),
            key=lambda index: (-float(probabilities[index, class_index]), index),
        )[:typical_count]
        for index in typical:
            selected.append(index)
            reasons[index] = f"class_{class_index}_typical_high_true_probability"
        boundary = sorted(
            (int(index) for index in candidates if int(index) not in reasons),
            key=lambda index: (float(margins[index]), index),
        )[:boundary_count]
        for index in boundary:
            selected.append(index)
            reasons[index] = f"class_{class_index}_boundary_small_top1_margin"
    return selected, reasons


def load_sample_ids(path: Path, selected: set[int]) -> dict[int, str]:
    result: dict[int, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle):
            if line_number not in selected:
                continue
            record = json.loads(line)
            if record["role"] != "DEVELOPMENT" or int(record["sample_index"]) != line_number:
                raise ValueError("DEVELOPMENT provenance identity mismatch")
            result[line_number] = str(record["sample_id"])
    if set(result) != selected:
        raise ValueError("Fixture sample IDs are incomplete")
    return result


def difference(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    absolute = np.abs(np.asarray(reference, dtype=np.float32) - np.asarray(candidate, dtype=np.float32))
    return {
        "max_abs_difference": float(absolute.max(initial=0.0)),
        "mean_abs_difference": float(absolute.mean()) if absolute.size else 0.0,
    }


def compare_outputs(
    reference: np.ndarray,
    candidate: np.ndarray,
    max_abs_tolerance: float,
    mean_abs_tolerance: float | None = None,
) -> dict[str, Any]:
    stats = difference(reference, candidate)
    reference_predictions = np.argmax(reference, axis=1)
    candidate_predictions = np.argmax(candidate, axis=1)
    mismatch_indices = np.flatnonzero(reference_predictions != candidate_predictions)
    passed = stats["max_abs_difference"] <= max_abs_tolerance and mismatch_indices.size == 0
    if mean_abs_tolerance is not None:
        passed = passed and stats["mean_abs_difference"] <= mean_abs_tolerance
    return {
        **stats,
        "max_abs_tolerance": max_abs_tolerance,
        "mean_abs_tolerance": mean_abs_tolerance,
        "prediction_agreement": float(np.mean(reference_predictions == candidate_predictions)),
        "mismatch_count": int(mismatch_indices.size),
        "mismatch_fixture_positions": [int(value) for value in mismatch_indices],
        "passed": bool(passed),
    }


def audit_files() -> dict[str, dict[str, Any]]:
    return {
        relative: {
            "exists": repo_path(relative).is_file(),
            "size_bytes": repo_path(relative).stat().st_size if repo_path(relative).is_file() else None,
            "sha256": sha256_file(repo_path(relative)) if repo_path(relative).is_file() else None,
        }
        for relative in LEGACY_AUDIT_PATHS
    }


def verify_source(contract: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    source = contract["source_model"]
    model_path = repo_path(source["artifact_path"])
    metadata_path = repo_path(source["metadata_path"])
    if sha256_file(model_path) != source["artifact_sha256"]:
        raise ValueError("P1 model artifact SHA-256 mismatch")
    if sha256_file(metadata_path) != source["metadata_sha256"]:
        raise ValueError("P1 model metadata SHA-256 mismatch")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    training_result = json.loads((P1_MANIFEST / "training_result.json").read_text(encoding="utf-8"))
    training_contract = json.loads(
        (P1_MANIFEST / "training_contract_snapshot.json").read_text(encoding="utf-8")
    )
    validation_result = json.loads((P1_MANIFEST / "validation_result.json").read_text(encoding="utf-8"))
    test_access = json.loads((P1_MANIFEST / "test_access_audit.json").read_text(encoding="utf-8"))
    p0_split = json.loads((P0_MANIFEST / "split_contract.json").read_text(encoding="utf-8"))
    p0_preprocessing = json.loads((P0_MANIFEST / "preprocessing_contract.json").read_text(encoding="utf-8"))
    inherited = contract["required_inheritance"]
    required_equalities = {
        "model_id": metadata["model_id"] == source["model_id"],
        "architecture_id": metadata["architecture"]["architecture_id"] == source["architecture_id"],
        "input_shape": metadata["architecture"]["input_shape"] == source["input_shape"],
        "class_order": metadata["architecture"]["class_order"] == source["class_order"],
        "dataset_id": metadata["dataset_id"] == inherited["dataset_id"] == p0_split["dataset_id"],
        "preprocessing_id": metadata["preprocessing_id"] == inherited["preprocessing_id"] == p0_preprocessing["preprocessing_id"],
        "label_mapping_id": metadata["label_mapping_id"] == inherited["label_mapping_id"] == p0_preprocessing["label_mapping"]["mapping_id"],
        "parameter_count": metadata["architecture"]["parameter_count"] == source["parameter_count"],
        "training_seed": int(training_contract["training"]["seed"]) == source["training_seed"],
        "p1_status": validation_result["status"] == "PASS_WITH_LIMITATIONS",
        "locked_test_access_zero": test_access["test_sample_count_read"] == 0 and test_access["test_array_open_count"] == 0,
        "default_activation_false": metadata["deployment_boundary"]["default_activation"] is False,
        "safety_authority_false": metadata["deployment_boundary"]["safety_authority"] is False,
    }
    failures = [name for name, passed in required_equalities.items() if not passed]
    if failures:
        raise ValueError(f"P1/P0 inherited identity mismatch: {failures}")
    with np.load(model_path, allow_pickle=False) as archive:
        weights = {name: np.asarray(archive[name], dtype=np.float32) for name in archive.files}
    expected_shapes = {
        "weights_1": (80, 32),
        "bias_1": (32,),
        "weights_2": (32, 3),
        "bias_2": (3,),
    }
    if set(weights) != set(expected_shapes):
        raise ValueError("P1 weight names mismatch")
    if any(weights[name].shape != shape for name, shape in expected_shapes.items()):
        raise ValueError("P1 weight shape mismatch")
    if any(weights[name].dtype != np.float32 for name in weights):
        raise ValueError("P1 weight dtype mismatch")
    if sum(array.size for array in weights.values()) != source["parameter_count"]:
        raise ValueError("P1 parameter count mismatch")
    return weights, {
        "checks": required_equalities,
        "p1_status": validation_result["status"],
        "p1_model_sha256": sha256_file(model_path),
        "p1_metadata_sha256": sha256_file(metadata_path),
        "development_metrics": metadata["development_metrics"],
        "weight_shapes": {name: list(weights[name].shape) for name in sorted(weights)},
        "weight_sha256": {name: sha256_array(weights[name]) for name in sorted(weights)},
        "training_seed": source["training_seed"],
        "locked_public_test_access_count": 0,
    }


def refresh_checksums(manifest_dir: Path, artifact_path: Path) -> None:
    paths = [artifact_path]
    paths.extend(
        path for path in sorted(manifest_dir.iterdir())
        if path.is_file() and path.name != "artifact_checksums.sha256"
    )
    lines = [f"{sha256_file(path)}  {path.resolve().relative_to(ROOT.resolve()).as_posix()}" for path in paths]
    (manifest_dir / "artifact_checksums.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    tolerances = contract["predefined_tolerances"]
    legacy_before = audit_files()
    weights, source_audit = verify_source(contract)

    images_path = repo_path(contract["parity_fixture"]["images_path"])
    labels_path = repo_path(contract["parity_fixture"]["labels_path"])
    sample_index_path = repo_path(contract["parity_fixture"]["sample_index_path"])
    development_images = np.load(images_path, mmap_mode="r")
    development_labels = np.asarray(np.load(labels_path, mmap_mode="r"), dtype=np.int8)
    all_numpy = numpy_intermediates(development_images, weights)
    selected, reasons = select_fixture(
        development_labels,
        all_numpy["probabilities"],
        int(contract["parity_fixture"]["samples_per_class"]),
    )
    if len(selected) != int(contract["parity_fixture"]["total_samples"]):
        raise ValueError("Parity fixture count mismatch")
    sample_ids = load_sample_ids(sample_index_path, set(selected))
    fixture_images = np.asarray(development_images[selected], dtype=np.float32)
    fixture_labels = development_labels[selected]
    numpy_outputs = numpy_intermediates(fixture_images, weights)

    model, intermediate_model = build_models(weights)
    tf_values = intermediate_model(fixture_images, training=False)
    tensorflow_outputs = {
        name: np.asarray(value.numpy(), dtype=np.float32)
        for name, value in zip(("pooled", "hidden", "logits", "probabilities"), tf_values)
    }

    output_path = repo_path(contract["output"]["artifact_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    first_export = convert_fp32(model)
    second_export = convert_fp32(model)
    output_path.write_bytes(first_export)
    export_hash = sha256_file(output_path)
    second_export_hash = hashlib.sha256(second_export).hexdigest()
    tflite_outputs, tensor_metadata = tflite_probabilities(output_path, fixture_images)
    tflite_outputs_repeat, tensor_metadata_repeat = tflite_probabilities(output_path, fixture_images)
    inference_deterministic = np.array_equal(tflite_outputs, tflite_outputs_repeat)

    numpy_tf = {
        name: compare_outputs(
            numpy_outputs[name],
            tensorflow_outputs[name],
            float(tolerances[f"{name if name != 'pooled' else 'pooling'}_max_abs"]),
            float(tolerances["probabilities_mean_abs"]) if name == "probabilities" else None,
        )
        for name in ("pooled", "hidden", "logits", "probabilities")
    }
    tf_tflite = compare_outputs(
        tensorflow_outputs["probabilities"],
        tflite_outputs,
        float(tolerances["probabilities_max_abs"]),
        float(tolerances["probabilities_mean_abs"]),
    )
    numpy_tflite = compare_outputs(
        numpy_outputs["probabilities"],
        tflite_outputs,
        float(tolerances["probabilities_max_abs"]),
        float(tolerances["probabilities_mean_abs"]),
    )
    mismatch_positions = numpy_tflite["mismatch_fixture_positions"]
    mismatch_ids = [sample_ids[selected[position]] for position in mismatch_positions]
    gates_passed = (
        all(result["passed"] for result in numpy_tf.values())
        and tf_tflite["passed"]
        and numpy_tflite["passed"]
        and not tensor_metadata["unexpected_quantization"]
        and tensor_metadata == tensor_metadata_repeat
        and inference_deterministic
    )
    if not gates_passed:
        raise RuntimeError("B6R-P2 predefined parity gate failed")

    manifest_dir = repo_path(contract["output"]["manifest_dir"])
    manifest_dir.mkdir(parents=True, exist_ok=True)
    export_timestamp = datetime.now(timezone.utc).isoformat()
    export_manifest = {
        "schema_version": "safenest.thermal.b6r_p2.export_manifest.v1",
        "stage_id": contract["stage_id"],
        "status": "PASS",
        "model_id": contract["output"]["model_id"],
        "source_p1_model_id": contract["source_model"]["model_id"],
        "source_p1_model_sha256": source_audit["p1_model_sha256"],
        "source_p1_metadata_sha256": source_audit["p1_metadata_sha256"],
        "architecture_id": contract["source_model"]["architecture_id"],
        "dataset_id": contract["required_inheritance"]["dataset_id"],
        "preprocessing_id": contract["required_inheritance"]["preprocessing_id"],
        "label_mapping_id": contract["required_inheritance"]["label_mapping_id"],
        "class_order": contract["source_model"]["class_order"],
        "input_shape": [1, 62, 80, 1],
        "input_dtype": "float32",
        "output_shape": [1, 3],
        "output_dtype": "float32",
        "parameter_count": contract["source_model"]["parameter_count"],
        "weight_shapes": source_audit["weight_shapes"],
        "weight_sha256": source_audit["weight_sha256"],
        "training_seed": source_audit["training_seed"],
        "tensorflow_version": tf.__version__,
        "conversion_settings": contract["output"]["conversion"],
        "export_timestamp_utc": export_timestamp,
        "artifact_path": contract["output"]["artifact_path"],
        "artifact_sha256": export_hash,
        "artifact_size_bytes": output_path.stat().st_size,
        "default_activation": False,
        "safety_authority": False,
        "deployment_mode": "SHADOW_ONLY",
    }
    fixture_records = [
        {
            "fixture_position": position,
            "development_index": index,
            "sample_id": sample_ids[index],
            "target_class_index": int(fixture_labels[position]),
            "target_class": contract["source_model"]["class_order"][int(fixture_labels[position])],
            "selection_reason": reasons[index],
        }
        for position, index in enumerate(selected)
    ]
    parity_manifest = {
        "schema_version": "safenest.thermal.b6r_p2.parity_manifest.v1",
        "stage_id": contract["stage_id"],
        "role": "DEVELOPMENT",
        "purpose": contract["parity_fixture"]["purpose"],
        "selection_policy": contract["parity_fixture"]["selection_policy"],
        "sample_count": len(selected),
        "samples": fixture_records,
        "predefined_tolerances": tolerances,
        "locked_public_test_access_count": 0,
    }
    per_sample = []
    for position, index in enumerate(selected):
        per_sample.append({
            "fixture_position": position,
            "development_index": index,
            "sample_id": sample_ids[index],
            "numpy_probabilities": [float(value) for value in numpy_outputs["probabilities"][position]],
            "tensorflow_probabilities": [float(value) for value in tensorflow_outputs["probabilities"][position]],
            "tflite_probabilities": [float(value) for value in tflite_outputs[position]],
            "numpy_prediction": int(np.argmax(numpy_outputs["probabilities"][position])),
            "tensorflow_prediction": int(np.argmax(tensorflow_outputs["probabilities"][position])),
            "tflite_prediction": int(np.argmax(tflite_outputs[position])),
        })
    parity_results = {
        "schema_version": "safenest.thermal.b6r_p2.parity_results.v1",
        "stage_id": contract["stage_id"],
        "status": "PASS",
        "numpy_vs_tensorflow": numpy_tf,
        "tensorflow_vs_tflite": tf_tflite,
        "numpy_vs_tflite": {**numpy_tflite, "mismatch_sample_ids": mismatch_ids},
        "per_sample": per_sample,
    }
    environment = {
        "schema_version": "safenest.thermal.b6r_p2.environment.v1",
        "os": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "tensorflow": tf.__version__,
        "tflite_interpreter": "tensorflow.lite.Interpreter",
        "environment_policy": "project-local ignored .venv; no global package modification",
        "reproduction_install": "python -m venv .venv && .venv/Scripts/python.exe -m pip install tensorflow==2.20.0",
    }
    determinism = {
        "schema_version": "safenest.thermal.b6r_p2.determinism_audit.v1",
        "inference_determinism": inference_deterministic,
        "inference_repeat_outputs_sha256": [
            hashlib.sha256(tflite_outputs.astype("<f4").tobytes()).hexdigest(),
            hashlib.sha256(tflite_outputs_repeat.astype("<f4").tobytes()).hexdigest(),
        ],
        "weight_determinism": True,
        "export_byte_level_determinism": first_export == second_export,
        "first_export_sha256": export_hash,
        "second_export_sha256": second_export_hash,
        "status": "PASS" if first_export == second_export else "PASS_WITH_LIMITATIONS",
    }
    legacy_after = audit_files()
    legacy_audit = {
        "schema_version": "safenest.thermal.b6r_p2.legacy_runtime_audit.v1",
        "before": legacy_before,
        "after": legacy_after,
        "unchanged": legacy_before == legacy_after,
        "model_manifest_default_update": False,
        "runtime_selector_update": False,
        "default_activation": False,
        "safety_authority": False,
        "status": "PASS" if legacy_before == legacy_after else "FAIL",
    }
    locked_test = {
        "schema_version": "safenest.thermal.b6r_p2.locked_test_access_audit.v1",
        "role": "LOCKED_PUBLIC_TEST",
        "path_configured": False,
        "array_open_count": 0,
        "sample_read_count": 0,
        "metrics_computed": False,
        "used_for_selection_or_tuning": False,
        "status": "PASS",
    }
    source_audit_document = {
        "schema_version": "safenest.thermal.b6r_p2.source_p1_audit.v1",
        "stage_id": contract["stage_id"],
        **source_audit,
        "status": "PASS",
    }
    documents = {
        "export_manifest.json": export_manifest,
        "tensor_metadata.json": {
            "schema_version": "safenest.thermal.b6r_p2.tensor_metadata.v1",
            "stage_id": contract["stage_id"],
            **tensor_metadata,
            "status": "PASS",
        },
        "parity_manifest.json": parity_manifest,
        "parity_results.json": parity_results,
        "environment.json": environment,
        "determinism_audit.json": determinism,
        "legacy_runtime_audit.json": legacy_audit,
        "locked_test_access_audit.json": locked_test,
        "source_p1_audit.json": source_audit_document,
    }
    for filename, document in documents.items():
        write_json(manifest_dir / filename, document)
    refresh_checksums(manifest_dir, output_path)
    print(
        json.dumps(
            {
                "stage": contract["stage_id"],
                "status": "PASS",
                "artifact": contract["output"]["artifact_path"],
                "sha256": export_hash,
                "size_bytes": output_path.stat().st_size,
                "fixture_count": len(selected),
                "numpy_tflite_max_abs": numpy_tflite["max_abs_difference"],
                "numpy_tflite_mean_abs": numpy_tflite["mean_abs_difference"],
                "mismatch_count": numpy_tflite["mismatch_count"],
                "byte_deterministic": first_export == second_export,
                "inference_deterministic": inference_deterministic,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
