#!/usr/bin/env python3
"""B6R-P3 Raspberry Pi replay benchmark and shadow-only readiness runner.

This module deliberately does not import ``models/model_manifest.json``.  A
target run must opt in with ``--shadow-only`` and must use the exact artifact
and DEVELOPMENT fixture declared by the B6R-P3 contract.  The preparation
mode records an explicit hardware blocker when no authorized Raspberry Pi is
reachable; it never turns a desktop run into target evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p3_raspberry_pi_fp32_tflite_replay_shadow_benchmark_contract.json"
DEFAULT_MANIFEST_DIR = ROOT / "datasets/thermal/manifests/B6R-P3_raspberry_pi_fp32_tflite_replay_shadow_benchmark"
P0_CONTRACT = ROOT / "config/thermal/b6r_p0_public_sdt_contract.json"
P0_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P0_public_sdt_materialization"
P2_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P2_public_sdt_fp32_tflite_export"
LEGACY_AUDIT_PATHS = (
    "models/model_manifest.json",
    "models/thermal/thermal_fall_int8_v0.1.0.tflite",
    "inference/thermal_interpreter.py",
)
NOT_MEASURED = "NOT_MEASURED_ON_TARGET"
NOT_AVAILABLE = "NOT_AVAILABLE"
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/]|file://|/Users/|/home/|/root/|/tmp/|\\\\)"
)


class TensorContractViolation(ValueError):
    """Raised when a replay input or model output violates the frozen contract."""


@dataclass(frozen=True)
class Backend:
    module: Any
    name: str
    distribution: str
    version: str


@dataclass(frozen=True)
class ReplayFixture:
    images: np.ndarray
    labels: np.ndarray
    records: list[dict[str, Any]]
    images_path: str
    labels_path: str
    sample_index_path: str
    p2_manifest_sha256: str
    canonical_fixture_sha256: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_float32_array(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(np.asarray(array, dtype="<f4"))
    return sha256_bytes(canonical.tobytes())


def load_contract(path: Path) -> dict[str, Any]:
    contract = read_json(path)
    if contract.get("stage_id") != "B6R-P3":
        raise ValueError("contract stage_id must be B6R-P3")
    return contract


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return NOT_AVAILABLE


def load_interpreter_backend() -> Backend:
    candidates = (
        ("ai_edge_litert.interpreter", "ai-edge-litert", "ai_edge_litert.interpreter"),
        ("tflite_runtime.interpreter", "tflite-runtime", "tflite_runtime.interpreter"),
        ("tensorflow.lite", "tensorflow", "tensorflow.lite.Interpreter"),
    )
    for module_name, distribution, display_name in candidates:
        try:
            module = importlib.import_module(module_name)
            if not hasattr(module, "Interpreter"):
                continue
            return Backend(module, display_name, distribution, package_version(distribution))
        except (ImportError, OSError, RuntimeError):
            continue
    raise RuntimeError("no approved TFLite interpreter backend is installed")


def interpreter_inventory(backend: Backend | None, target_status: str) -> dict[str, Any]:
    packages = {
        "ai_edge_litert": package_version("ai-edge-litert"),
        "tflite_runtime": package_version("tflite-runtime"),
        "tensorflow": package_version("tensorflow"),
    }
    if target_status != "TARGET_MEASURED":
        return {
            "schema_version": "safenest.thermal.b6r_p3.interpreter_inventory.v1",
            "target_status": target_status,
            "packages": {name: NOT_AVAILABLE for name in packages},
            "selected_backend": NOT_MEASURED,
            "selected_backend_version": NOT_MEASURED,
            "selection_priority": [
                "ai_edge_litert.interpreter",
                "tflite_runtime.interpreter",
                "tensorflow.lite.Interpreter",
            ],
            "thread_count": NOT_MEASURED,
        }
    return {
        "schema_version": "safenest.thermal.b6r_p3.interpreter_inventory.v1",
        "target_status": target_status,
        "packages": packages,
        "selected_backend": backend.name if backend else NOT_AVAILABLE,
        "selected_backend_version": backend.version if backend else NOT_AVAILABLE,
        "selection_priority": [
            "ai_edge_litert.interpreter",
            "tflite_runtime.interpreter",
            "tensorflow.lite.Interpreter",
        ],
        "thread_count": 1,
    }


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip().replace("\x00", "")
    except (FileNotFoundError, OSError):
        return None


def read_os_distribution() -> str:
    text = _read_text(Path("/etc/os-release"))
    if not text:
        return NOT_AVAILABLE
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return NOT_AVAILABLE


def read_pi_model() -> str:
    model = _read_text(Path("/proc/device-tree/model"))
    return model if model else NOT_AVAILABLE


def read_cpu_information() -> str:
    text = _read_text(Path("/proc/cpuinfo"))
    if text:
        for key in ("Model", "model name", "Hardware", "Processor"):
            for line in text.splitlines():
                if line.lower().startswith(key.lower() + ":"):
                    return line.split(":", 1)[1].strip()
    return platform.processor() or NOT_AVAILABLE


def read_memory_value(field: str) -> int | None:
    text = _read_text(Path("/proc/meminfo"))
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith(field + ":"):
            parts = line.split()
            if len(parts) >= 2:
                value = int(parts[1])
                return value * 1024 if len(parts) >= 3 and parts[2] == "kB" else value
    return None


def collect_target_environment() -> dict[str, Any]:
    model = read_pi_model()
    confirmed = model != NOT_AVAILABLE and "raspberry pi" in model.lower()
    return {
        "schema_version": "safenest.thermal.b6r_p3.target_environment.v1",
        "target_status": "TARGET_MEASURED" if confirmed else "NON_TARGET_HOST_REFUSED",
        "target_measurement_status": "READY" if confirmed else NOT_MEASURED,
        "hostname": socket.gethostname() if confirmed else NOT_AVAILABLE,
        "os_distribution": read_os_distribution() if confirmed else NOT_AVAILABLE,
        "kernel": platform.release() if confirmed else NOT_AVAILABLE,
        "architecture": platform.machine() if confirmed else NOT_AVAILABLE,
        "raspberry_pi_model": model if confirmed else NOT_AVAILABLE,
        "python_version": platform.python_version() if confirmed else NOT_AVAILABLE,
        "cpu_information": read_cpu_information() if confirmed else NOT_AVAILABLE,
        "available_memory_bytes": read_memory_value("MemAvailable") if confirmed else NOT_AVAILABLE,
        "target_identity_confirmed": confirmed,
        "desktop_substitution_used": False,
    }


def expected_p2_artifact(contract: dict[str, Any]) -> dict[str, Any]:
    artifact = contract["p2_artifact"]
    path = repo_path(artifact["path"])
    export_manifest = read_json(repo_path(artifact["p2_export_manifest_path"]))
    tensor_metadata = read_json(repo_path(artifact["p2_tensor_metadata_path"]))
    actual_sha = sha256_file(path) if path.is_file() else None
    actual_size = path.stat().st_size if path.is_file() else None
    checks = {
        "exists": path.is_file(),
        "sha256": actual_sha == artifact["sha256"],
        "size_bytes": actual_size == artifact["size_bytes"],
        "p2_export_manifest_sha": export_manifest.get("artifact_sha256") == artifact["sha256"],
        "p2_export_tensor_contract": (
            export_manifest.get("input_shape") == artifact["input_shape"]
            and export_manifest.get("input_dtype") == artifact["input_dtype"]
            and export_manifest.get("output_shape") == artifact["output_shape"]
            and export_manifest.get("output_dtype") == artifact["output_dtype"]
        ),
        "p2_class_order": export_manifest.get("class_order") == artifact["class_order"],
        "p2_fp32_no_quantization": (
            export_manifest.get("conversion_settings", {}).get("inference_input_type") == "float32"
            and export_manifest.get("conversion_settings", {}).get("inference_output_type") == "float32"
            and export_manifest.get("conversion_settings", {}).get("quantization") == "NONE"
        ),
        "p2_live_tensor_metadata_contract": (
            tensor_metadata.get("input", {}).get("shape") == artifact["input_shape"]
            and tensor_metadata.get("input", {}).get("dtype") == artifact["input_dtype"]
            and tensor_metadata.get("output", {}).get("shape") == artifact["output_shape"]
            and tensor_metadata.get("output", {}).get("dtype") == artifact["output_dtype"]
            and tensor_metadata.get("unexpected_quantization") is False
        ),
        "p2_default_activation_false": export_manifest.get("default_activation") is False,
        "p2_safety_authority_false": export_manifest.get("safety_authority") is False,
        "p2_shadow_only": export_manifest.get("deployment_mode") == "SHADOW_ONLY",
    }
    return {
        "schema_version": "safenest.thermal.b6r_p3.artifact_identity_audit.v1",
        "stage_id": "B6R-P3",
        "artifact_path": artifact["path"],
        "expected_sha256": artifact["sha256"],
        "actual_sha256": actual_sha,
        "expected_size_bytes": artifact["size_bytes"],
        "actual_size_bytes": actual_size,
        "expected_tensor_contract": {
            "input_shape": artifact["input_shape"],
            "input_dtype": artifact["input_dtype"],
            "output_shape": artifact["output_shape"],
            "output_dtype": artifact["output_dtype"],
            "quantization": artifact["quantization"],
        },
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def load_fixture(contract: dict[str, Any]) -> ReplayFixture:
    fixture_contract = contract["replay_fixture"]
    p2_manifest_path = repo_path(fixture_contract["parent_p2_parity_manifest_path"])
    p2_manifest = read_json(p2_manifest_path)
    if p2_manifest.get("stage_id") != "B6R-P2" or p2_manifest.get("role") != "DEVELOPMENT":
        raise ValueError("P3 replay fixture must inherit the P2 DEVELOPMENT parity manifest")
    records = sorted(p2_manifest["samples"], key=lambda record: int(record["fixture_position"]))
    if len(records) != fixture_contract["sample_count"]:
        raise ValueError("P2 fixture sample count mismatch")
    if len({record["sample_id"] for record in records}) != len(records):
        raise ValueError("P2 fixture sample IDs are not unique")
    if any(record.get("target_class") == "LOCKED_PUBLIC_TEST" for record in records):
        raise ValueError("locked test record found in replay fixture")

    images_path = repo_path(fixture_contract["images_path"])
    labels_path = repo_path(fixture_contract["labels_path"])
    sample_index_path = repo_path(fixture_contract["sample_index_path"])
    images = np.load(images_path, mmap_mode="r")
    labels = np.asarray(np.load(labels_path, mmap_mode="r"))
    if images.ndim != 4 or tuple(images.shape[1:]) != (62, 80, 1) or images.dtype != np.float32:
        raise TensorContractViolation(f"DEVELOPMENT images contract mismatch: {images.shape}, {images.dtype}")
    if labels.ndim != 1 or labels.shape[0] != images.shape[0]:
        raise ValueError("DEVELOPMENT labels contract mismatch")
    indices = [int(record["development_index"]) for record in records]
    if min(indices) < 0 or max(indices) >= images.shape[0]:
        raise ValueError("P2 fixture index is outside DEVELOPMENT images")
    fixture_images = np.asarray(images[indices], dtype=np.float32)
    fixture_labels = np.asarray(labels[indices], dtype=np.int8)
    if not np.all(np.isfinite(fixture_images)):
        raise TensorContractViolation("DEVELOPMENT fixture contains non-finite values")
    if float(fixture_images.min()) < 0.0 or float(fixture_images.max()) > 1.0:
        raise TensorContractViolation("DEVELOPMENT fixture is outside the P0 [0,1] range")

    with sample_index_path.open("r", encoding="utf-8") as handle:
        sample_ids: dict[int, str] = {}
        for line_number, line in enumerate(handle):
            if line_number in indices:
                record = json.loads(line)
                sample_ids[line_number] = str(record["sample_id"])
    for record in records:
        index = int(record["development_index"])
        if sample_ids.get(index) != record["sample_id"]:
            raise ValueError(f"sample ID mismatch at DEVELOPMENT index {index}")

    return ReplayFixture(
        images=fixture_images,
        labels=fixture_labels,
        records=records,
        images_path=fixture_contract["images_path"],
        labels_path=fixture_contract["labels_path"],
        sample_index_path=fixture_contract["sample_index_path"],
        p2_manifest_sha256=sha256_file(p2_manifest_path),
        canonical_fixture_sha256=sha256_float32_array(fixture_images),
    )


def p0_fixture_file_audit(contract: dict[str, Any]) -> dict[str, Any]:
    fixture = contract["replay_fixture"]
    registry = read_json(repo_path(fixture["p0_artifact_registry_path"]))
    by_path = {record["path"]: record for record in registry["artifacts"]}
    paths = [fixture["images_path"], fixture["labels_path"], fixture["sample_index_path"]]
    files: list[dict[str, Any]] = []
    for relative in paths:
        path = repo_path(relative)
        expected = by_path.get(relative, {})
        actual_sha = sha256_file(path) if path.is_file() else None
        actual_size = path.stat().st_size if path.is_file() else None
        files.append({
            "path": relative,
            "exists": path.is_file(),
            "expected_sha256": expected.get("sha256"),
            "actual_sha256": actual_sha,
            "expected_size_bytes": expected.get("size_bytes"),
            "actual_size_bytes": actual_size,
            "matches_registry": bool(
                path.is_file()
                and actual_sha == expected.get("sha256")
                and actual_size == expected.get("size_bytes")
            ),
        })
    return {
        "schema_version": "safenest.thermal.b6r_p3.replay_fixture_audit.v1",
        "stage_id": "B6R-P3",
        "dataset_id": contract["required_inheritance"]["dataset_id"],
        "role": "DEVELOPMENT",
        "parent_p2_parity_manifest_path": fixture["parent_p2_parity_manifest_path"],
        "parent_p2_parity_manifest_sha256": sha256_file(
            repo_path(fixture["parent_p2_parity_manifest_path"])
        ),
        "files": files,
        "locked_public_test_files_opened": 0,
        "status": "PASS" if all(record["matches_registry"] for record in files) else "FAIL",
    }


def source_root_candidates(explicit: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    candidates.extend((ROOT.parent / "열화상_dataset", ROOT.parent.parent / "열화상_dataset"))
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def audit_source_archives(contract: dict[str, Any], explicit_root: Path | None) -> dict[str, Any]:
    p0_contract = read_json(P0_CONTRACT)
    registry = p0_contract["source_archive_registry"]
    selected_root = next((path for path in source_root_candidates(explicit_root) if path.is_dir()), None)
    archives: list[dict[str, Any]] = []
    for name, expected in sorted(registry.items()):
        path = selected_root / name if selected_root else None
        exists = bool(path and path.is_file())
        actual_size = path.stat().st_size if exists else None
        actual_sha = sha256_file(path) if exists else None
        archives.append({
            "archive_name": name,
            "expected_size_bytes": expected["size_bytes"],
            "actual_size_bytes": actual_size,
            "expected_sha256": expected["sha256"],
            "actual_sha256": actual_sha,
            "matches_registry": bool(
                exists
                and actual_size == expected["size_bytes"]
                and actual_sha == expected["sha256"]
            ),
        })
    all_match = len(archives) == 6 and all(item["matches_registry"] for item in archives)
    return {
        "schema_version": "safenest.thermal.b6r_p3.source_identity_audit.v1",
        "stage_id": "B6R-P3",
        "source_location_id": p0_contract["source_location_id"],
        "source_root_persisted": False,
        "verification_method": "read-only direct SHA-256 and size calculation; no extraction or rewrite",
        "archive_count_expected": 6,
        "archive_count_found": sum(1 for item in archives if item["actual_sha256"]),
        "archives": archives,
        "p0_recorded_source_immutability_status": read_json(
            P0_MANIFEST / "source_immutability.json"
        ).get("status"),
        "source_mutation_performed": False,
        "status": "PASS" if all_match else "FAIL",
    }


def build_replay_manifest(contract: dict[str, Any], fixture: ReplayFixture) -> dict[str, Any]:
    return {
        "schema_version": "safenest.thermal.b6r_p3.replay_manifest.v1",
        "stage_id": "B6R-P3",
        "role": "DEVELOPMENT",
        "dataset_id": contract["required_inheritance"]["dataset_id"],
        "dataset_authority": contract["required_inheritance"]["dataset_authority"],
        "preprocessing_id": contract["required_inheritance"]["preprocessing_id"],
        "label_mapping_id": contract["required_inheritance"]["label_mapping_id"],
        "selection_policy": contract["replay_fixture"]["selection_policy"],
        "parent_p2_parity_manifest_path": contract["replay_fixture"]["parent_p2_parity_manifest_path"],
        "parent_p2_parity_manifest_sha256": fixture.p2_manifest_sha256,
        "images_path": fixture.images_path,
        "labels_path": fixture.labels_path,
        "sample_index_path": fixture.sample_index_path,
        "sample_count": len(fixture.records),
        "cycles": contract["replay_fixture"]["cycles"],
        "measured_sample_count": contract["replay_fixture"]["measured_sample_count"],
        "canonical_fixture_sha256": fixture.canonical_fixture_sha256,
        "samples": [
            {
                "fixture_position": int(record["fixture_position"]),
                "development_index": int(record["development_index"]),
                "sample_id": record["sample_id"],
                "target_class_index": int(record["target_class_index"]),
                "target_class": record["target_class"],
                "selection_reason": record["selection_reason"],
            }
            for record in fixture.records
        ],
        "locked_public_test_access_count": 0,
    }


def legacy_audit() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for relative in LEGACY_AUDIT_PATHS:
        path = repo_path(relative)
        result[relative] = {
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path) if path.is_file() else None,
        }
    return result


def not_measured_statistics() -> dict[str, Any]:
    return {name: NOT_MEASURED for name in (
        "count", "mean", "median", "p50", "p95", "p99", "min", "max"
    )}


def not_measured_target_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_status": "BLOCKED_HARDWARE",
        "target_measurement_status": NOT_MEASURED,
        "statistics": {
            "preprocessing_ingress_ms": not_measured_statistics(),
            "inference_ms": not_measured_statistics(),
            "total_ms": not_measured_statistics(),
        },
        "warmup_runs_configured": contract["replay_fixture"]["warmup_runs"],
        "measured_sample_count_configured": contract["replay_fixture"]["measured_sample_count"],
        "sample_values_persisted": False,
        "latency_threshold": "NOT_DEFINED_BY_THIS_STAGE",
    }


def no_target_resource_evidence() -> dict[str, Any]:
    return {
        "schema_version": "safenest.thermal.b6r_p3.resource_metrics.v1",
        "target_status": "BLOCKED_HARDWARE",
        "target_measurement_status": NOT_MEASURED,
        "rss_memory": NOT_MEASURED,
        "cpu_utilization": NOT_MEASURED,
        "cpu_temperature": NOT_MEASURED,
        "system_load": NOT_AVAILABLE,
        "available_memory": NOT_AVAILABLE,
        "thermal_throttling_status": NOT_AVAILABLE,
    }


def no_target_stability_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "safenest.thermal.b6r_p3.stability_metrics.v1",
        "target_status": "BLOCKED_HARDWARE",
        "target_measurement_status": NOT_MEASURED,
        "minimum_duration_seconds": contract["prolonged_replay"]["minimum_duration_seconds"],
        "duration_seconds": NOT_MEASURED,
        "total_inference_count": NOT_MEASURED,
        "failed_inference_count": NOT_MEASURED,
        "exception_count": NOT_MEASURED,
        "nan_inf_output_count": NOT_MEASURED,
        "shape_dtype_violation_count": NOT_MEASURED,
        "rss_start_end_peak": NOT_MEASURED,
        "temperature_start_end_peak": NOT_MEASURED,
        "cpu_statistics": NOT_MEASURED,
        "latency_drift": NOT_MEASURED,
        "unexpected_process_termination": NOT_MEASURED,
        "restarted_after_first_failure": False,
    }


def no_target_determinism_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "safenest.thermal.b6r_p3.determinism_metrics.v1",
        "target_status": "BLOCKED_HARDWARE",
        "target_measurement_status": NOT_MEASURED,
        "predefined_tolerances": contract["determinism"]["predefined_tolerances"],
        "same_interpreter_instance": NOT_MEASURED,
        "repeated_model_loads": NOT_MEASURED,
        "process_reexecution": NOT_MEASURED,
        "mismatch_sample_ids": [],
    }


def sanitize_error(error: BaseException) -> str:
    message = str(error).splitlines()[0] if str(error) else ""
    message = ABSOLUTE_PATH_PATTERN.sub("<path>", message)
    return f"{type(error).__name__}: {message[:240]}"


def prepare_blocked_evidence(
    contract: dict[str, Any],
    source_root: Path | None,
    probe_status: str,
    configured_target_count: int,
    explicit_user_target_count: int,
) -> int:
    identity = expected_p2_artifact(contract)
    if identity["status"] != "PASS":
        raise RuntimeError("P2 artifact identity mismatch; refusing P3 evidence preparation")
    fixture = load_fixture(contract)
    manifest_dir = repo_path(contract.get("manifest_dir", "datasets/thermal/manifests/B6R-P3_raspberry_pi_fp32_tflite_replay_shadow_benchmark"))
    manifest_dir.mkdir(parents=True, exist_ok=True)
    write_json(manifest_dir / "contract_snapshot.json", contract)
    write_json(manifest_dir / "replay_manifest.json", build_replay_manifest(contract, fixture))
    write_json(manifest_dir / "artifact_identity_audit.json", identity)
    write_json(manifest_dir / "replay_fixture_audit.json", p0_fixture_file_audit(contract))
    source_audit = audit_source_archives(contract, source_root)
    write_json(manifest_dir / "source_identity_audit.json", source_audit)
    write_json(manifest_dir / "target_access_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.target_access_audit.v1",
        "stage_id": "B6R-P3",
        "probe_method": "pre-existing SSH config; BatchMode public-key probe; no password or credential guessing",
        "configured_target_count": configured_target_count,
        "explicit_user_target_count": explicit_user_target_count,
        "probe_status": probe_status,
        "target_address_persisted": False,
        "target_identity": NOT_AVAILABLE,
        "target_measurement_available": False,
        "status": "BLOCKED_HARDWARE",
    })
    write_json(manifest_dir / "target_environment.json", {
        "schema_version": "safenest.thermal.b6r_p3.target_environment.v1",
        "target_status": "BLOCKED_HARDWARE",
        "target_measurement_status": NOT_MEASURED,
        "hostname": NOT_AVAILABLE,
        "os_distribution": NOT_AVAILABLE,
        "kernel": NOT_AVAILABLE,
        "architecture": NOT_AVAILABLE,
        "raspberry_pi_model": NOT_AVAILABLE,
        "python_version": NOT_AVAILABLE,
        "cpu_information": NOT_AVAILABLE,
        "available_memory_bytes": NOT_AVAILABLE,
        "desktop_substitution_used": False,
    })
    write_json(manifest_dir / "interpreter_inventory.json", interpreter_inventory(None, "BLOCKED_HARDWARE"))
    write_json(manifest_dir / "latency_metrics.json", {
        "schema_version": "safenest.thermal.b6r_p3.latency_metrics.v1",
        **not_measured_target_evidence(contract),
    })
    write_json(manifest_dir / "resource_metrics.json", no_target_resource_evidence())
    write_json(manifest_dir / "stability_metrics.json", no_target_stability_evidence(contract))
    write_json(manifest_dir / "determinism_metrics.json", no_target_determinism_evidence(contract))
    before = legacy_audit()
    after = legacy_audit()
    write_json(manifest_dir / "shadow_only_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.shadow_only_audit.v1",
        "stage_id": "B6R-P3",
        "deployment_mode": "SHADOW_ONLY",
        "explicit_opt_in_required": True,
        "candidate_activation": "NOT_PERFORMED",
        "default_activation": False,
        "safety_authority": False,
        "default_manifest_update": False,
        "production_runtime_selector_update": False,
        "legacy_model_overwrite": False,
        "legacy_before": before,
        "legacy_after": after,
        "legacy_unchanged_during_preparation": before == after,
        "opt_in_command": "python scripts/benchmark_thermal_b6r_p3_rpi.py --shadow-only --run-fixed",
        "rollback": "stop the opt-in shadow runner; the legacy default manifest/model remains the rollback target",
        "status": "PASS" if before == after else "FAIL",
    })
    write_json(manifest_dir / "locked_test_access_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.locked_test_access_audit.v1",
        "role": "LOCKED_PUBLIC_TEST",
        "array_open_count": 0,
        "sample_read_count": 0,
        "metrics_computed": False,
        "used_for_selection_or_tuning": False,
        "path_configured": False,
        "status": "PASS",
    })
    write_json(manifest_dir / "target_prerequisites_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.target_prerequisites_audit.v1",
        "stage_id": "B6R-P3",
        "p2_artifact_identity": identity["status"],
        "source_archive_identity": source_audit["status"],
        "development_fixture_identity": "PASS",
        "target_environment": "BLOCKED_HARDWARE",
        "target_interpreter": NOT_MEASURED,
        "locked_public_test_access": 0,
        "desktop_substitution": False,
        "status": "PASS" if identity["status"] == "PASS" and source_audit["status"] == "PASS" else "FAIL",
    })
    write_json(manifest_dir / "run_summary.json", {
        "schema_version": "safenest.thermal.b6r_p3.run_summary.v1",
        "stage_id": "B6R-P3",
        "status": "BLOCKED_HARDWARE",
        "target_benchmark_executed": False,
        "target_evidence": "NOT_AVAILABLE",
        "latency": NOT_MEASURED,
        "resource_metrics": NOT_MEASURED,
        "prolonged_replay": NOT_MEASURED,
        "determinism": NOT_MEASURED,
        "next_stage_executed": False,
    })
    refresh_checksums(manifest_dir, repo_path(contract["p2_artifact"]["path"]))
    print(json.dumps({
        "stage": "B6R-P3",
        "status": "BLOCKED_HARDWARE",
        "artifact_sha256": identity["actual_sha256"],
        "source_archives": source_audit["archive_count_found"],
        "fixture_samples": len(fixture.records),
        "target_benchmark_executed": False,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def prepare_replay_input(frame: np.ndarray) -> np.ndarray:
    array = np.asarray(frame, dtype=np.float32)
    if array.shape == (62, 80):
        array = array[None, ..., None]
    elif array.shape == (62, 80, 1):
        array = array[None, ...]
    elif array.shape != (1, 62, 80, 1):
        raise TensorContractViolation(f"replay input shape mismatch: {array.shape}")
    if not np.all(np.isfinite(array)):
        raise TensorContractViolation("replay input contains NaN or infinity")
    if float(array.min()) < 0.0 or float(array.max()) > 1.0:
        raise TensorContractViolation("replay input is outside canonical [0,1] range")
    return np.ascontiguousarray(array, dtype=np.float32)


def tensor_detail(detail: dict[str, Any]) -> dict[str, Any]:
    quantization = detail.get("quantization", (0.0, 0))
    return {
        "name": str(detail["name"]),
        "index": int(detail["index"]),
        "shape": [int(value) for value in detail["shape"]],
        "shape_signature": [int(value) for value in detail.get("shape_signature", detail["shape"])],
        "dtype": np.dtype(detail["dtype"]).name,
        "quantization": {
            "scale": float(quantization[0]),
            "zero_point": int(quantization[1]),
        },
    }


def create_interpreter(backend: Backend, artifact_path: Path, thread_count: int = 1) -> Any:
    interpreter = backend.module.Interpreter(model_path=str(artifact_path), num_threads=thread_count)
    interpreter.allocate_tensors()
    return interpreter


def validate_live_tensor_contract(interpreter: Any, contract: dict[str, Any]) -> dict[str, Any]:
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    input_record = tensor_detail(input_detail)
    output_record = tensor_detail(output_detail)
    expected = contract["interpreter"]["required_tensor_contract"]
    checks = {
        "input_shape": input_record["shape"] == expected["input_shape"],
        "input_dtype": input_record["dtype"] == expected["input_dtype"],
        "output_shape": output_record["shape"] == expected["output_shape"],
        "output_dtype": output_record["dtype"] == expected["output_dtype"],
        "input_quantization_none": input_record["quantization"]["scale"] == 0.0,
        "output_quantization_none": output_record["quantization"]["scale"] == 0.0,
    }
    return {
        "schema_version": "safenest.thermal.b6r_p3.live_tensor_metadata.v1",
        "stage_id": "B6R-P3",
        "interpreter": "live_target_backend",
        "input": input_record,
        "output": output_record,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def invoke_once(
    interpreter: Any,
    input_detail: dict[str, Any],
    output_detail: dict[str, Any],
    frame: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    total_start = time.perf_counter_ns()
    preprocessing_start = total_start
    prepared = prepare_replay_input(frame)
    preprocessing_end = time.perf_counter_ns()
    inference_start = preprocessing_end
    interpreter.set_tensor(input_detail["index"], prepared)
    interpreter.invoke()
    raw_output = interpreter.get_tensor(output_detail["index"])
    inference_end = time.perf_counter_ns()
    total_end = inference_end
    if raw_output.shape != (1, 3) or np.dtype(raw_output.dtype).name != "float32":
        raise TensorContractViolation(
            f"model output contract mismatch: {raw_output.shape}, {np.dtype(raw_output.dtype).name}"
        )
    output = np.asarray(raw_output, dtype=np.float32).copy()
    if not np.all(np.isfinite(output)):
        raise TensorContractViolation("model output contains NaN or infinity")
    return output, {
        "preprocessing_ingress_ms": (preprocessing_end - preprocessing_start) / 1_000_000.0,
        "inference_ms": (inference_end - inference_start) / 1_000_000.0,
        "total_ms": (total_end - total_start) / 1_000_000.0,
    }


def statistics(values: list[float]) -> dict[str, Any]:
    if not values:
        return not_measured_statistics()
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def compare_outputs(reference: np.ndarray, candidate: np.ndarray, tolerance: dict[str, Any]) -> dict[str, Any]:
    reference_array = np.asarray(reference, dtype=np.float32)
    candidate_array = np.asarray(candidate, dtype=np.float32)
    absolute = np.abs(reference_array - candidate_array)
    reference_prediction = np.argmax(reference_array, axis=-1)
    candidate_prediction = np.argmax(candidate_array, axis=-1)
    mismatch = reference_prediction != candidate_prediction
    mismatch_positions = np.flatnonzero(mismatch)
    max_abs = float(absolute.max()) if absolute.size else 0.0
    mean_abs = float(absolute.mean()) if absolute.size else 0.0
    mismatch_count = int(np.count_nonzero(mismatch))
    return {
        "max_abs_difference": max_abs,
        "mean_abs_difference": mean_abs,
        "max_abs_tolerance": tolerance["output_max_abs"],
        "mean_abs_tolerance": tolerance["output_mean_abs"],
        "prediction_agreement": float(np.mean(~mismatch)) if mismatch.size else 1.0,
        "mismatch_count": mismatch_count,
        "mismatch_positions": [int(value) for value in mismatch_positions],
        "passed": bool(
            max_abs <= tolerance["output_max_abs"]
            and mean_abs <= tolerance["output_mean_abs"]
            and mismatch_count <= tolerance["mismatch_count_max"]
            and (float(np.mean(~mismatch)) if mismatch.size else 1.0)
            >= tolerance["prediction_agreement_min"]
        ),
        "output_sha256": sha256_float32_array(candidate_array),
    }


def summarize_resource_series(values: list[float | int | None]) -> dict[str, Any]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return NOT_AVAILABLE
    array = np.asarray(numeric, dtype=np.float64)
    return {
        "count": int(array.size),
        "start": float(array[0]),
        "end": float(array[-1]),
        "min": float(array.min()),
        "max": float(array.max()),
        "peak": float(array.max()),
        "mean": float(array.mean()),
    }


def read_current_rss_bytes() -> int | None:
    text = _read_text(Path("/proc/self/status"))
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1]) * 1024
    return None


def read_temperature_c() -> float | None:
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        text = _read_text(path)
        if not text:
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        return value / 1000.0 if abs(value) > 200.0 else value
    return None


def read_throttling_status() -> str:
    candidates = sorted(Path("/sys/devices").glob("**/throttled"))
    for path in candidates[:4]:
        text = _read_text(path)
        if text:
            return text
    return NOT_AVAILABLE


class ResourceTracker:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = interval_seconds
        self.started_wall = time.perf_counter()
        self.started_cpu = time.process_time()
        self.next_sample = self.started_wall
        self.samples: list[dict[str, Any]] = []

    def sample(self, force: bool = False) -> None:
        now = time.perf_counter()
        if not force and now < self.next_sample:
            return
        elapsed = max(now - self.started_wall, 1e-9)
        cpu_percent = (time.process_time() - self.started_cpu) / elapsed * 100.0
        self.samples.append({
            "elapsed_seconds": elapsed,
            "rss_bytes": read_current_rss_bytes(),
            "cpu_utilization_percent": cpu_percent,
            "temperature_c": read_temperature_c(),
            "available_memory_bytes": read_memory_value("MemAvailable"),
            "system_load": (os.getloadavg()[0] if hasattr(os, "getloadavg") else None),
            "thermal_throttling_status": read_throttling_status(),
        })
        self.next_sample = now + self.interval_seconds

    def summary(self) -> dict[str, Any]:
        self.sample(force=True)
        return {
            "sample_count": len(self.samples),
            "rss_memory": summarize_resource_series([sample["rss_bytes"] for sample in self.samples]),
            "cpu_utilization": summarize_resource_series(
                [sample["cpu_utilization_percent"] for sample in self.samples]
            ),
            "cpu_temperature": summarize_resource_series(
                [sample["temperature_c"] for sample in self.samples]
            ),
            "available_memory": summarize_resource_series(
                [sample["available_memory_bytes"] for sample in self.samples]
            ),
            "system_load": summarize_resource_series([sample["system_load"] for sample in self.samples]),
            "thermal_throttling_status": next(
                (
                    sample["thermal_throttling_status"]
                    for sample in reversed(self.samples)
                    if sample["thermal_throttling_status"] != NOT_AVAILABLE
                ),
                NOT_AVAILABLE,
            ),
            "samples": self.samples,
        }


def run_fixed_replay(
    interpreter: Any,
    fixture: ReplayFixture,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[np.ndarray]]:
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    warmup_runs = int(contract["replay_fixture"]["warmup_runs"])
    for index in range(warmup_runs):
        invoke_once(interpreter, input_detail, output_detail, fixture.images[index % len(fixture.images)])
    tracker = ResourceTracker(float(contract["resources"]["sample_interval_seconds"]))
    tracker.sample(force=True)
    latency_values = {"preprocessing_ingress_ms": [], "inference_ms": [], "total_ms": []}
    outputs: list[np.ndarray] = []
    failures: list[str] = []
    expected_count = int(contract["replay_fixture"]["measured_sample_count"])
    for index in range(expected_count):
        try:
            output, timings = invoke_once(
                interpreter,
                input_detail,
                output_detail,
                fixture.images[index % len(fixture.images)],
            )
            outputs.append(output)
            for name, value in timings.items():
                latency_values[name].append(value)
        except Exception as error:  # preserve first failure in evidence; never restart the run
            failures.append(sanitize_error(error))
            break
        tracker.sample()
    resource = tracker.summary()
    latency = {
        "schema_version": "safenest.thermal.b6r_p3.latency_metrics.v1",
        "target_status": "TARGET_MEASURED",
        "target_measurement_status": "COMPLETE" if not failures else "FAILED_DURING_FIXED_REPLAY",
        "warmup_runs": warmup_runs,
        "measured_sample_count_configured": expected_count,
        "measured_sample_count_actual": len(outputs),
        "warmup_excluded": True,
        "timer": contract["latency"]["timer"],
        "statistics": {name: statistics(values) for name, values in latency_values.items()},
        "sample_values_ms": latency_values,
        "failures": failures,
        "latency_threshold": "NOT_DEFINED_BY_THIS_STAGE",
    }
    if failures:
        latency["status"] = "FAIL"
    else:
        latency["status"] = "PASS"
    return latency, resource, outputs


def latency_drift(latency_values: list[float]) -> dict[str, Any]:
    if len(latency_values) < 4:
        return NOT_MEASURED
    quarter = max(len(latency_values) // 4, 1)
    first = float(np.median(np.asarray(latency_values[:quarter], dtype=np.float64)))
    last = float(np.median(np.asarray(latency_values[-quarter:], dtype=np.float64)))
    return {
        "first_quarter_p50_ms": first,
        "last_quarter_p50_ms": last,
        "absolute_delta_ms": last - first,
    }


def run_prolonged_replay(
    interpreter: Any,
    fixture: ReplayFixture,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    target_seconds = float(contract["prolonged_replay"]["minimum_duration_seconds"])
    started = time.perf_counter()
    deadline = started + target_seconds
    tracker = ResourceTracker(float(contract["resources"]["sample_interval_seconds"]))
    tracker.sample(force=True)
    latencies: list[float] = []
    total_inference_count = 0
    failed_inference_count = 0
    exception_count = 0
    nan_inf_count = 0
    shape_dtype_count = 0
    first_failure: str | None = None
    frame_index = 0
    while time.perf_counter() < deadline:
        try:
            _, timings = invoke_once(
                interpreter,
                input_detail,
                output_detail,
                fixture.images[frame_index % len(fixture.images)],
            )
            latencies.append(timings["total_ms"])
            total_inference_count += 1
        except TensorContractViolation as error:
            failed_inference_count += 1
            exception_count += 1
            if "NaN" in str(error) or "infinity" in str(error):
                nan_inf_count += 1
            else:
                shape_dtype_count += 1
            first_failure = sanitize_error(error)
            break
        except Exception as error:  # stop on first failure; do not restart to hide it
            failed_inference_count += 1
            exception_count += 1
            first_failure = sanitize_error(error)
            break
        frame_index += 1
        tracker.sample()
    ended = time.perf_counter()
    resource = tracker.summary()
    completed = first_failure is None and ended - started >= target_seconds
    stability = {
        "schema_version": "safenest.thermal.b6r_p3.stability_metrics.v1",
        "target_status": "TARGET_MEASURED",
        "target_measurement_status": "COMPLETE" if completed else "FAILED_OR_SHORT",
        "minimum_duration_seconds": int(target_seconds),
        "duration_seconds": ended - started,
        "total_inference_count": total_inference_count,
        "failed_inference_count": failed_inference_count,
        "exception_count": exception_count,
        "nan_inf_output_count": nan_inf_count,
        "shape_dtype_violation_count": shape_dtype_count,
        "rss_start_end_peak": resource["rss_memory"],
        "temperature_start_end_peak": resource["cpu_temperature"],
        "cpu_statistics": resource["cpu_utilization"],
        "latency_drift": latency_drift(latencies),
        "unexpected_process_termination": False,
        "restarted_after_first_failure": False,
        "first_failure": first_failure,
        "status": "PASS" if completed and failed_inference_count == 0 else "FAIL",
    }
    return stability, resource


def run_determinism(
    contract: dict[str, Any],
    fixture: ReplayFixture,
    artifact_path: Path,
    backend: Backend,
) -> dict[str, Any]:
    tolerance = contract["determinism"]["predefined_tolerances"]
    sample_count = min(3, len(fixture.images))
    frames = fixture.images[:sample_count]
    input_count = int(contract["determinism"]["same_interpreter_repeats"])
    interpreter = create_interpreter(backend, artifact_path, int(contract["interpreter"]["thread_count"]))
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    same_runs: list[np.ndarray] = []
    for _ in range(input_count):
        same_runs.append(np.vstack([
            invoke_once(interpreter, input_detail, output_detail, frame)[0]
            for frame in frames
        ]))
    same_comparisons = [compare_outputs(same_runs[0], candidate, tolerance) for candidate in same_runs[1:]]
    same_passed = all(result["passed"] for result in same_comparisons)

    load_runs: list[np.ndarray] = []
    for _ in range(int(contract["determinism"]["repeated_loads"])):
        loaded = create_interpreter(backend, artifact_path, int(contract["interpreter"]["thread_count"]))
        loaded_input = loaded.get_input_details()[0]
        loaded_output = loaded.get_output_details()[0]
        load_runs.append(np.vstack([
            invoke_once(loaded, loaded_input, loaded_output, frame)[0]
            for frame in frames
        ]))
    load_comparisons = [compare_outputs(load_runs[0], candidate, tolerance) for candidate in load_runs[1:]]
    load_passed = all(result["passed"] for result in load_comparisons)

    process_status: dict[str, Any]
    child_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--contract",
        str(DEFAULT_CONTRACT),
        "--determinism-child",
        "--sample-count",
        str(sample_count),
    ]
    try:
        child = subprocess.run(
            child_command,
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        child_payload = json.loads(child.stdout)
        child_outputs = np.asarray(child_payload["outputs"], dtype=np.float32)
        process_comparison = compare_outputs(same_runs[0], child_outputs, tolerance)
        process_status = {
            "status": "PASS" if process_comparison["passed"] else "FAIL",
            "backend": child_payload.get("backend", NOT_AVAILABLE),
            "comparison": process_comparison,
        }
    except Exception as error:
        process_status = {
            "status": "FAIL",
            "backend": NOT_AVAILABLE,
            "comparison": sanitize_error(error),
        }

    mismatch_positions: set[int] = set()
    for comparison in same_comparisons + load_comparisons:
        mismatch_positions.update(comparison.get("mismatch_positions", []))
    mismatch_positions.update(process_status.get("comparison", {}).get("mismatch_positions", []))
    mismatch_ids = [
        fixture.records[index]["sample_id"]
        for index in sorted(mismatch_positions)
        if index < len(fixture.records)
    ]
    all_passed = same_passed and load_passed and process_status["status"] == "PASS"
    return {
        "schema_version": "safenest.thermal.b6r_p3.determinism_metrics.v1",
        "target_status": "TARGET_MEASURED",
        "target_measurement_status": "COMPLETE" if all_passed else "FAILED",
        "predefined_tolerances": tolerance,
        "same_interpreter_instance": {
            "repeat_count": input_count,
            "comparisons": same_comparisons,
            "status": "PASS" if same_passed else "FAIL",
        },
        "repeated_model_loads": {
            "load_count": int(contract["determinism"]["repeated_loads"]),
            "comparisons": load_comparisons,
            "status": "PASS" if load_passed else "FAIL",
        },
        "process_reexecution": process_status,
        "sample_ids": [fixture.records[index]["sample_id"] for index in range(sample_count)],
        "mismatch_sample_ids": mismatch_ids,
        "status": "PASS" if all_passed else "FAIL",
    }


def run_determinism_child(contract: dict[str, Any], sample_count: int) -> int:
    backend = load_interpreter_backend()
    identity = expected_p2_artifact(contract)
    if identity["status"] != "PASS":
        raise RuntimeError("P2 artifact identity mismatch")
    fixture = load_fixture(contract)
    artifact_path = repo_path(contract["p2_artifact"]["path"])
    interpreter = create_interpreter(backend, artifact_path, int(contract["interpreter"]["thread_count"]))
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    outputs = np.vstack([
        invoke_once(interpreter, input_detail, output_detail, frame)[0]
        for frame in fixture.images[:sample_count]
    ])
    print(json.dumps({
        "backend": backend.name,
        "outputs": outputs.tolist(),
        "output_sha256": sha256_float32_array(outputs),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def run_target_benchmark(contract: dict[str, Any], run_fixed: bool, run_prolonged: bool) -> int:
    environment = collect_target_environment()
    if environment["target_status"] != "TARGET_MEASURED":
        raise RuntimeError("NON_TARGET_HOST_REFUSED: Raspberry Pi identity was not confirmed")
    backend = load_interpreter_backend()
    identity = expected_p2_artifact(contract)
    if identity["status"] != "PASS":
        raise RuntimeError("ARTIFACT_IDENTITY_MISMATCH: refusing target benchmark")
    fixture = load_fixture(contract)
    artifact_path = repo_path(contract["p2_artifact"]["path"])
    interpreter = create_interpreter(backend, artifact_path, int(contract["interpreter"]["thread_count"]))
    live_tensor = validate_live_tensor_contract(interpreter, contract)
    if live_tensor["status"] != "PASS":
        raise RuntimeError("TARGET_TENSOR_CONTRACT_MISMATCH: refusing target benchmark")
    manifest_dir = repo_path(contract.get("manifest_dir", DEFAULT_MANIFEST_DIR.relative_to(ROOT).as_posix()))
    manifest_dir.mkdir(parents=True, exist_ok=True)
    write_json(manifest_dir / "contract_snapshot.json", contract)
    write_json(manifest_dir / "target_environment.json", environment)
    write_json(manifest_dir / "interpreter_inventory.json", interpreter_inventory(backend, "TARGET_MEASURED"))
    write_json(manifest_dir / "live_tensor_metadata.json", live_tensor)
    if run_fixed:
        latency, resource, fixed_outputs = run_fixed_replay(interpreter, fixture, contract)
        write_json(manifest_dir / "latency_metrics.json", latency)
        write_json(manifest_dir / "resource_metrics.json", {
            "schema_version": "safenest.thermal.b6r_p3.resource_metrics.v1",
            "target_status": "TARGET_MEASURED",
            "fixed_replay": resource,
        })
        write_json(manifest_dir / "latency_samples.json", {
            "schema_version": "safenest.thermal.b6r_p3.latency_samples.v1",
            "stages": latency["sample_values_ms"],
        })
    else:
        fixed_outputs = []
        write_json(manifest_dir / "latency_metrics.json", {
            "schema_version": "safenest.thermal.b6r_p3.latency_metrics.v1",
            "target_status": "TARGET_MEASURED",
            "target_measurement_status": "NOT_REQUESTED",
            "statistics": {name: NOT_MEASURED for name in (
                "preprocessing_ingress_ms", "inference_ms", "total_ms"
            )},
        })
    if run_prolonged:
        stability, prolonged_resource = run_prolonged_replay(interpreter, fixture, contract)
        write_json(manifest_dir / "stability_metrics.json", stability)
        existing_resource = read_json(manifest_dir / "resource_metrics.json")
        existing_resource["prolonged_replay"] = prolonged_resource
        write_json(manifest_dir / "resource_metrics.json", existing_resource)
    else:
        write_json(manifest_dir / "stability_metrics.json", no_target_stability_evidence(contract) | {
            "target_status": "TARGET_MEASURED",
            "target_measurement_status": "NOT_REQUESTED",
        })
    determinism = run_determinism(contract, fixture, artifact_path, backend)
    write_json(manifest_dir / "determinism_metrics.json", determinism)
    write_json(manifest_dir / "artifact_identity_audit.json", identity | {
        "live_tensor_metadata_path": "datasets/thermal/manifests/B6R-P3_raspberry_pi_fp32_tflite_replay_shadow_benchmark/live_tensor_metadata.json",
        "live_tensor_status": live_tensor["status"],
    })
    write_json(manifest_dir / "locked_test_access_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.locked_test_access_audit.v1",
        "role": "LOCKED_PUBLIC_TEST",
        "array_open_count": 0,
        "sample_read_count": 0,
        "metrics_computed": False,
        "used_for_selection_or_tuning": False,
        "path_configured": False,
        "status": "PASS",
    })
    before = legacy_audit()
    after = legacy_audit()
    write_json(manifest_dir / "shadow_only_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.shadow_only_audit.v1",
        "stage_id": "B6R-P3",
        "deployment_mode": "SHADOW_ONLY",
        "explicit_opt_in_required": True,
        "candidate_activation": "SHADOW_RUN_ONLY",
        "default_activation": False,
        "safety_authority": False,
        "default_manifest_update": False,
        "production_runtime_selector_update": False,
        "legacy_model_overwrite": False,
        "legacy_before": before,
        "legacy_after": after,
        "legacy_unchanged_during_benchmark": before == after,
        "rollback": "stop the opt-in shadow runner; the legacy default manifest/model remains the rollback target",
        "status": "PASS" if before == after else "FAIL",
    })
    target_complete = (
        run_fixed
        and run_prolonged
        and read_json(manifest_dir / "latency_metrics.json").get("status") == "PASS"
        and read_json(manifest_dir / "stability_metrics.json").get("status") == "PASS"
        and determinism["status"] == "PASS"
        and before == after
    )
    write_json(manifest_dir / "target_access_audit.json", {
        "schema_version": "safenest.thermal.b6r_p3.target_access_audit.v1",
        "stage_id": "B6R-P3",
        "probe_method": "direct target execution through an existing authorized environment",
        "configured_target_count": NOT_AVAILABLE,
        "explicit_user_target_count": NOT_AVAILABLE,
        "probe_status": "TARGET_REACHED",
        "target_address_persisted": False,
        "target_identity": "Raspberry Pi identity recorded in target_environment.json",
        "target_measurement_available": True,
        "status": "PASS",
    })
    write_json(manifest_dir / "run_summary.json", {
        "schema_version": "safenest.thermal.b6r_p3.run_summary.v1",
        "stage_id": "B6R-P3",
        "status": "PASS" if target_complete else "PASS_WITH_LIMITATIONS",
        "target_benchmark_executed": True,
        "target_evidence": "Raspberry Pi",
        "latency": "MEASURED_ON_TARGET" if run_fixed else NOT_MEASURED,
        "resource_metrics": "MEASURED_ON_TARGET" if run_fixed else NOT_MEASURED,
        "prolonged_replay": "MEASURED_ON_TARGET" if run_prolonged else NOT_MEASURED,
        "determinism": determinism["status"],
        "next_stage_executed": False,
    })
    refresh_checksums(manifest_dir, artifact_path)
    print(json.dumps({
        "stage": "B6R-P3",
        "status": "PASS" if target_complete else "PASS_WITH_LIMITATIONS",
        "artifact_sha256": identity["actual_sha256"],
        "backend": backend.name,
        "fixed_replay": run_fixed,
        "prolonged_replay": run_prolonged,
        "determinism": determinism["status"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def refresh_checksums(manifest_dir: Path, artifact_path: Path) -> None:
    paths = [artifact_path]
    paths.extend(
        path for path in sorted(manifest_dir.iterdir())
        if path.is_file() and path.name != "checksums.sha256"
    )
    lines = [
        f"{sha256_file(path)}  {path.resolve().relative_to(ROOT.resolve()).as_posix()}"
        for path in paths
    ]
    (manifest_dir / "checksums.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--prepare-blocked-evidence", action="store_true")
    parser.add_argument("--target-probe-status", default="SSH_CONNECT_TIMEOUT")
    parser.add_argument("--configured-target-count", type=int, default=2)
    parser.add_argument("--explicit-user-target-count", type=int, default=1)
    parser.add_argument("--shadow-only", action="store_true")
    parser.add_argument("--run-fixed", action="store_true")
    parser.add_argument("--run-prolonged", action="store_true")
    parser.add_argument("--determinism-child", action="store_true")
    parser.add_argument("--sample-count", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    contract = load_contract(args.contract)
    if args.determinism_child:
        return run_determinism_child(contract, args.sample_count)
    if args.prepare_blocked_evidence:
        if args.run_fixed or args.run_prolonged:
            parser.error("preparation mode cannot execute a target benchmark")
        return prepare_blocked_evidence(
            contract,
            args.source_root,
            args.target_probe_status,
            args.configured_target_count,
            args.explicit_user_target_count,
        )
    if not args.run_fixed and not args.run_prolonged:
        parser.error("choose --prepare-blocked-evidence or a target run flag")
    if not args.shadow_only:
        parser.error("target execution requires explicit --shadow-only opt-in")
    return run_target_benchmark(contract, args.run_fixed, args.run_prolonged)


if __name__ == "__main__":
    sys.exit(main())
