#!/usr/bin/env python3
"""Validate B6R-P0 materialized public SDT payload and tracked evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p0_public_sdt_contract.json"
DEFAULT_OUTPUT = ROOT / "datasets/thermal/materialized/B6R-P0_public_sdt_v1"
DEFAULT_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P0_public_sdt_materialization"


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


def validate_split(
    split_name: str,
    split_contract: dict[str, Any],
    output_root: Path,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    split_dir = output_root / split_name
    count = int(split_contract["sample_count"])
    images = np.load(split_dir / "images.npy", mmap_mode="r")
    labels = np.load(split_dir / "labels.npy", mmap_mode="r")
    source_labels = np.load(split_dir / "source_labels.npy", mmap_mode="r")
    errors: list[str] = []
    if images.shape != (count, 62, 80, 1) or images.dtype != np.dtype("float32"):
        errors.append(f"images contract mismatch: {images.shape}/{images.dtype}")
    if labels.shape != (count,) or labels.dtype != np.dtype("int8"):
        errors.append(f"labels contract mismatch: {labels.shape}/{labels.dtype}")
    if source_labels.shape != (count,) or source_labels.dtype != np.dtype("uint8"):
        errors.append(f"source_labels contract mismatch: {source_labels.shape}/{source_labels.dtype}")
    if not np.isfinite(images).all() or float(images.min()) < 0.0 or float(images.max()) > 1.0:
        errors.append("image range/non-finite validation failed")

    source_counts = Counter(str(int(value)) for value in source_labels)
    target_counts = Counter(str(int(value)) for value in labels)
    sample_ids: set[str] = set()
    provenance_count = 0
    tensor_hash_matches = 0
    with (split_dir / "sample_index.jsonl").open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            record = json.loads(line)
            provenance_count += 1
            sample_ids.add(record["sample_id"])
            expected_member = split_contract["image_member_template"].format(index=index)
            if record["sample_index"] != index or record["source_member_path"] != expected_member:
                errors.append(f"provenance index/member mismatch at {index}")
                break
            if record["split"] != split_name or record["role"] != split_contract["role"]:
                errors.append(f"provenance split/role mismatch at {index}")
                break
            source_token = int(source_labels[index])
            target_label = int(labels[index])
            expected_target = int(
                contract["label_mapping"]["source_token_to_target"][str(source_token)]
            )
            if record["source_label_token"] != source_token or target_label != expected_target:
                errors.append(f"label mapping mismatch at {index}")
                break
            tensor_hash = hashlib.sha256(
                np.asarray(images[index, :, :, 0], dtype="<f4").tobytes(order="C")
            ).hexdigest()
            if tensor_hash == record["derived_tensor_sha256"]:
                tensor_hash_matches += 1
            else:
                errors.append(f"tensor provenance hash mismatch at {index}")
                break
    if provenance_count != count or len(sample_ids) != count:
        errors.append(f"provenance accounting mismatch: {provenance_count}/{len(sample_ids)}/{count}")
    if tensor_hash_matches != count:
        errors.append(f"tensor provenance matches {tensor_hash_matches}/{count}")

    return ({
        "split": split_name,
        "role": split_contract["role"],
        "expected_count": count,
        "provenance_count": provenance_count,
        "unique_sample_id_count": len(sample_ids),
        "tensor_provenance_hash_match_count": tensor_hash_matches,
        "source_class_counts": dict(sorted(source_counts.items())),
        "target_class_counts": dict(sorted(target_counts.items())),
        "images_shape": list(images.shape),
        "images_dtype": str(images.dtype),
        "images_min": float(images.min()),
        "images_max": float(images.max()),
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }, sample_ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    materialized = json.loads((args.output_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    registry = json.loads((args.manifest_dir / "artifact_registry.json").read_text(encoding="utf-8"))
    source_audit = json.loads((args.manifest_dir / "source_immutability.json").read_text(encoding="utf-8"))
    determinism = json.loads((args.manifest_dir / "determinism_audit.json").read_text(encoding="utf-8"))
    split_policy = json.loads((args.manifest_dir / "split_contract.json").read_text(encoding="utf-8"))

    checks: list[dict[str, Any]] = []
    add_check(checks, "dataset_identity", materialized["dataset_id"] == contract["dataset_id"], materialized["dataset_id"])
    add_check(checks, "public_not_mi48", materialized["dataset_authority"] == "PUBLIC_SDT_ONLY_NOT_MI48", materialized["dataset_authority"])
    add_check(checks, "total_accounting", materialized["total_sample_count"] == 48000, materialized["total_sample_count"])
    add_check(checks, "source_immutability", source_audit["source_unchanged"], source_audit["status"])
    add_check(checks, "deterministic_repeat", determinism["all_stream_hashes_match"], determinism["status"])
    test_locked = (
        split_policy["test_selection_or_tuning_allowed"] is False
        and split_policy["test_metrics_computed"] is False
        and split_policy["split_roles"]["test"]["role"] == "LOCKED_PUBLIC_TEST"
    )
    add_check(checks, "test_role_lock", test_locked, split_policy["test_access_in_stage"])

    split_results: dict[str, Any] = {}
    split_ids: dict[str, set[str]] = {}
    for name, split_contract in contract["splits"].items():
        print(f"[validate] {name}", flush=True)
        split_results[name], split_ids[name] = validate_split(
            name, split_contract, args.output_dir, contract
        )
        add_check(checks, f"split_{name}", split_results[name]["status"] == "PASS", split_results[name])
    intersections = {
        "train_validation": len(split_ids["train"] & split_ids["validation"]),
        "train_test": len(split_ids["train"] & split_ids["test"]),
        "validation_test": len(split_ids["validation"] & split_ids["test"]),
    }
    add_check(checks, "sample_id_role_isolation", all(value == 0 for value in intersections.values()), intersections)

    registry_errors = []
    for record in registry["artifacts"]:
        path = ROOT / record["path"]
        if not path.is_file() or path.stat().st_size != record["size_bytes"] or sha256_file(path) != record["sha256"]:
            registry_errors.append(record["path"])
    add_check(checks, "artifact_registry", not registry_errors, registry_errors)

    machine_files = list(args.manifest_dir.glob("*.json")) + [args.contract, args.output_dir / "dataset_manifest.json"]
    absolute_pattern = re.compile(r"[A-Za-z]:[\\/]|file://", re.IGNORECASE)
    leaking_files = [
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in machine_files
        if absolute_pattern.search(path.read_text(encoding="utf-8"))
    ]
    add_check(checks, "no_absolute_path_persistence", not leaking_files, leaking_files)

    all_passed = all(item["passed"] for item in checks)
    result = {
        "schema_version": "safenest.thermal.b6r_p0.validation_result.v1",
        "stage_id": "B6R-P0",
        "status": "PASS_WITH_LIMITATIONS" if all_passed else "FAIL",
        "checks": checks,
        "split_results": split_results,
        "limitations": [
            "PUBLIC_SDT_ONLY; no MI48 sensor identity or physical validation.",
            "No subject/session/recording identity; source archive partition is preserved but group isolation is not claimed.",
            "HUMAN_FALL_PROXY is a posture proxy, not a measured real fall event.",
            "B6R-1 and B6R-2 remain blocked; B6R-11/13/14 physical and competition locks remain unavailable.",
            "Materialized payload is local and intentionally not Git-tracked.",
        ],
        "next_stage": "B6R-P1_PUBLIC_SDT_CONTROLLED_TRAINING_ONLY_REQUIRES_USER_APPROVAL",
    }
    write_json(args.manifest_dir / "validation_result.json", result)
    checksum_lines = []
    for path in sorted(args.manifest_dir.glob("*.json")):
        relative = path.relative_to(ROOT).as_posix()
        checksum_lines.append(f"{sha256_file(path)}  {relative}")
    (args.manifest_dir / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"B6R-P0 validation: {result['status']}", flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
