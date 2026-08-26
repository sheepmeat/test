#!/usr/bin/env python3
"""Independently validate B6R-P2 FP32 export, parity, and safety boundaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

from scripts.export_thermal_b6r_p2_public_sdt_fp32_tflite import (
    ROOT,
    audit_files,
    build_models,
    compare_outputs,
    numpy_intermediates,
    refresh_checksums,
    repo_path,
    sha256_file,
    tflite_probabilities,
    verify_source,
    write_json,
)


DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p2_public_sdt_fp32_tflite_contract.json"
ABSOLUTE_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:[\\/]|file://|/Users/)")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: Any) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_checksum_registry(path: Path) -> list[str]:
    errors: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        target = repo_path(relative)
        if not target.is_file():
            errors.append(f"missing:{relative}")
        elif sha256_file(target) != expected:
            errors.append(f"sha256:{relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    contract = read_json(args.contract)
    output_path = repo_path(contract["output"]["artifact_path"])
    manifest_dir = repo_path(contract["output"]["manifest_dir"])
    export_manifest = read_json(manifest_dir / "export_manifest.json")
    tensor_metadata = read_json(manifest_dir / "tensor_metadata.json")
    parity_manifest = read_json(manifest_dir / "parity_manifest.json")
    recorded_parity = read_json(manifest_dir / "parity_results.json")
    determinism = read_json(manifest_dir / "determinism_audit.json")
    legacy = read_json(manifest_dir / "legacy_runtime_audit.json")
    locked_test = read_json(manifest_dir / "locked_test_access_audit.json")
    source_record = read_json(manifest_dir / "source_p1_audit.json")
    tolerances = contract["predefined_tolerances"]
    checks: list[dict[str, Any]] = []

    try:
        weights, live_source = verify_source(contract)
        source_ok = True
        source_detail: Any = live_source
    except Exception as error:  # validator must report rather than hide a source failure
        weights = {}
        source_ok = False
        source_detail = str(error)
    add_check(checks, "p1_source_identity", source_ok, source_detail)
    add_check(
        checks,
        "source_audit_manifest",
        source_ok
        and source_record["p1_model_sha256"] == live_source["p1_model_sha256"]
        and source_record["locked_public_test_access_count"] == 0,
        source_record,
    )
    add_check(
        checks,
        "tflite_artifact_identity",
        output_path.is_file()
        and sha256_file(output_path) == export_manifest["artifact_sha256"]
        and output_path.stat().st_size == export_manifest["artifact_size_bytes"],
        {
            "path": contract["output"]["artifact_path"],
            "sha256": sha256_file(output_path) if output_path.is_file() else None,
            "size_bytes": output_path.stat().st_size if output_path.is_file() else None,
        },
    )

    recomputed: dict[str, Any] = {}
    if source_ok and output_path.is_file():
        fixture_indices = [int(record["development_index"]) for record in parity_manifest["samples"]]
        images = np.load(repo_path(contract["parity_fixture"]["images_path"]), mmap_mode="r")
        fixture_images = np.asarray(images[fixture_indices], dtype=np.float32)
        numpy_outputs = numpy_intermediates(fixture_images, weights)
        _, intermediate = build_models(weights)
        tf_values = intermediate(fixture_images, training=False)
        tensorflow_outputs = {
            name: np.asarray(value.numpy(), dtype=np.float32)
            for name, value in zip(("pooled", "hidden", "logits", "probabilities"), tf_values)
        }
        tflite_outputs, live_tensor_metadata = tflite_probabilities(output_path, fixture_images)
        tflite_outputs_repeat, live_tensor_metadata_repeat = tflite_probabilities(
            output_path, fixture_images
        )
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
        recomputed = {
            "numpy_vs_tensorflow": numpy_tf,
            "tensorflow_vs_tflite": tf_tflite,
            "numpy_vs_tflite": numpy_tflite,
        }
        add_check(
            checks,
            "numpy_tensorflow_intermediate_parity",
            all(value["passed"] for value in numpy_tf.values()),
            numpy_tf,
        )
        add_check(checks, "tensorflow_tflite_parity", tf_tflite["passed"], tf_tflite)
        add_check(checks, "numpy_tflite_parity", numpy_tflite["passed"], numpy_tflite)
        add_check(
            checks,
            "tflite_inference_determinism",
            np.array_equal(tflite_outputs, tflite_outputs_repeat)
            and live_tensor_metadata == live_tensor_metadata_repeat,
            {
                "outputs_equal": bool(np.array_equal(tflite_outputs, tflite_outputs_repeat)),
                "metadata_equal": live_tensor_metadata == live_tensor_metadata_repeat,
            },
        )
        add_check(
            checks,
            "tensor_metadata_live",
            live_tensor_metadata == {
                key: tensor_metadata[key] for key in ("interpreter", "input", "output", "unexpected_quantization")
            }
            and live_tensor_metadata["input"]["shape"] == [1, 62, 80, 1]
            and live_tensor_metadata["input"]["dtype"] == "float32"
            and live_tensor_metadata["output"]["shape"] == [1, 3]
            and live_tensor_metadata["output"]["dtype"] == "float32"
            and live_tensor_metadata["unexpected_quantization"] is False,
            live_tensor_metadata,
        )
    else:
        add_check(checks, "numpy_tensorflow_intermediate_parity", False, "source/artifact unavailable")
        add_check(checks, "tensorflow_tflite_parity", False, "source/artifact unavailable")
        add_check(checks, "numpy_tflite_parity", False, "source/artifact unavailable")
        add_check(checks, "tflite_inference_determinism", False, "source/artifact unavailable")
        add_check(checks, "tensor_metadata_live", False, "source/artifact unavailable")

    recorded_summary_ok = bool(recomputed) and all(
        recorded_parity[name]["passed"]
        for name in ("tensorflow_vs_tflite", "numpy_vs_tflite")
    ) and all(
        recorded_parity["numpy_vs_tensorflow"][name]["passed"]
        for name in ("pooled", "hidden", "logits", "probabilities")
    )
    add_check(checks, "recorded_parity_summary", recorded_summary_ok, recorded_parity["status"])
    add_check(
        checks,
        "fixture_contract",
        parity_manifest["role"] == "DEVELOPMENT"
        and parity_manifest["sample_count"] == contract["parity_fixture"]["total_samples"]
        and len({record["sample_id"] for record in parity_manifest["samples"]}) == parity_manifest["sample_count"]
        and parity_manifest["locked_public_test_access_count"] == 0,
        {
            "role": parity_manifest["role"],
            "sample_count": parity_manifest["sample_count"],
            "selection_policy": parity_manifest["selection_policy"],
        },
    )
    add_check(
        checks,
        "locked_public_test_access_zero",
        locked_test == {
            "array_open_count": 0,
            "metrics_computed": False,
            "path_configured": False,
            "role": "LOCKED_PUBLIC_TEST",
            "sample_read_count": 0,
            "schema_version": "safenest.thermal.b6r_p2.locked_test_access_audit.v1",
            "status": "PASS",
            "used_for_selection_or_tuning": False,
        },
        locked_test,
    )
    current_legacy = audit_files()
    add_check(
        checks,
        "legacy_default_runtime_unchanged",
        legacy["unchanged"] is True
        and legacy["before"] == legacy["after"] == current_legacy
        and legacy["model_manifest_default_update"] is False
        and legacy["runtime_selector_update"] is False
        and legacy["default_activation"] is False
        and legacy["safety_authority"] is False,
        current_legacy,
    )
    add_check(
        checks,
        "export_determinism",
        determinism["inference_determinism"] is True
        and determinism["weight_determinism"] is True
        and determinism["first_export_sha256"] == export_manifest["artifact_sha256"],
        determinism,
    )
    checksum_errors = validate_checksum_registry(manifest_dir / "artifact_checksums.sha256")
    add_check(checks, "artifact_checksums", not checksum_errors, checksum_errors)
    path_violations = []
    for path in sorted(manifest_dir.glob("*.json")):
        if ABSOLUTE_PATH_PATTERN.search(path.read_text(encoding="utf-8")):
            path_violations.append(path.name)
    add_check(checks, "no_absolute_path_persistence", not path_violations, path_violations)
    add_check(
        checks,
        "deployment_boundary",
        all(contract["deployment_boundary"][key] is False for key in (
            "default_activation",
            "safety_authority",
            "legacy_model_overwrite",
            "model_manifest_default_update",
            "runtime_selector_update",
            "mi48_claim",
            "raspberry_pi_validation_claim",
            "physical_validation_claim",
            "competition_lock_claim",
        )),
        contract["deployment_boundary"],
    )
    passed = all(check["passed"] for check in checks)
    result = {
        "schema_version": "safenest.thermal.b6r_p2.validation_result.v1",
        "stage_id": contract["stage_id"],
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "recomputed_parity": recomputed,
        "locked_public_test_access_count": 0,
        "default_activation": False,
        "safety_authority": False,
        "limitations": [
            "PUBLIC_SDT_ONLY; no MI48 or physical sensor validation.",
            "HUMAN_FALL_PROXY is a posture proxy, not a real-fall or safety decision.",
            "No Raspberry Pi latency, memory, replay stability, or runtime integration was executed.",
            "The TensorFlow export environment is project-local and is not a production Raspberry Pi environment.",
        ],
        "next_stage_proposal_only": "B6R-P3 Raspberry Pi FP32 TFLite Replay & Shadow Benchmark",
        "next_stage_executed": False,
    }
    write_json(manifest_dir / "validation_result.json", result)
    refresh_checksums(manifest_dir, output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
