#!/usr/bin/env python3
"""B6R-P0 public SDT thermal-only, read-only streaming materializer."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import sys
import zipfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from PIL import Image, __version__ as pillow_version


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config/thermal/b6r_p0_public_sdt_contract.json"
DEFAULT_SOURCE = ROOT.parent / "열화상_dataset"
DEFAULT_OUTPUT = ROOT / "datasets/thermal/materialized/B6R-P0_public_sdt_v1"
DEFAULT_MANIFEST = ROOT / "datasets/thermal/manifests/B6R-P0_public_sdt_materialization"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_bytes(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


class MultiFileStream(io.BufferedIOBase):
    """Seekable read-only view over byte-concatenated split ZIP parts."""

    def __init__(self, paths: list[Path]):
        super().__init__()
        self.sizes = [path.stat().st_size for path in paths]
        self.total_size = sum(self.sizes)
        self.position = 0
        self.handles = [path.open("rb") for path in paths]

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            target = offset
        elif whence == io.SEEK_CUR:
            target = self.position + offset
        elif whence == io.SEEK_END:
            target = self.total_size + offset
        else:
            raise ValueError(f"Unsupported whence: {whence}")
        if target < 0:
            raise ValueError("Negative seek position")
        self.position = min(target, self.total_size)
        return self.position

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self.total_size - self.position
        remaining = min(size, self.total_size - self.position)
        output = bytearray()
        while remaining > 0:
            local_position = self.position
            part_index = 0
            for index, part_size in enumerate(self.sizes):
                if local_position < part_size:
                    part_index = index
                    break
                local_position -= part_size
            handle = self.handles[part_index]
            handle.seek(local_position)
            chunk = handle.read(min(remaining, self.sizes[part_index] - local_position))
            if not chunk:
                break
            output.extend(chunk)
            self.position += len(chunk)
            remaining -= len(chunk)
        return bytes(output)

    def close(self) -> None:
        if not self.closed:
            for handle in self.handles:
                handle.close()
        super().close()


@contextmanager
def open_split_zip(source_dir: Path, parts: list[str]) -> Iterator[zipfile.ZipFile]:
    paths = [source_dir / name for name in parts]
    if len(paths) == 1:
        with zipfile.ZipFile(paths[0], "r") as archive:
            yield archive
        return
    stream = MultiFileStream(paths)
    try:
        with zipfile.ZipFile(stream, "r") as archive:
            yield archive
    finally:
        stream.close()


def map_source_label(source_token: int, contract: dict[str, Any]) -> int:
    mapping = contract["label_mapping"]["source_token_to_target"]
    if str(source_token) not in mapping:
        raise ValueError(f"Unsupported source label token: {source_token}")
    return int(mapping[str(source_token)])


def normalize_image(image: Image.Image, contract: dict[str, Any]) -> np.ndarray:
    height, width = contract["preprocessing"]["resize_geometry_hw"]
    resized = image.resize((int(width), int(height)), Image.Resampling.BILINEAR)
    values = np.asarray(resized, dtype=np.float32)
    minimum, maximum = np.float32(values.min()), np.float32(values.max())
    if maximum > minimum:
        values = (values - minimum) / (maximum - minimum)
    else:
        values = np.zeros_like(values, dtype=np.float32)
    return np.asarray(values, dtype=np.dtype("<f4"))


def fingerprint_sources(
    source_dir: Path, contract: dict[str, Any], phase: str
) -> list[dict[str, Any]]:
    records = []
    for name, expected in sorted(contract["source_archive_registry"].items()):
        path = source_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing source archive: {name}")
        stat = path.stat()
        print(f"[{phase}] SHA-256 {name}", flush=True)
        digest = sha256_file(path)
        matches = stat.st_size == int(expected["size_bytes"]) and digest == expected["sha256"]
        if not matches:
            raise ValueError(f"Source identity mismatch: {name}")
        records.append(
            {
                "archive_name": name,
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": digest,
                "matches_registry": matches,
            }
        )
    return records


def parse_label_lines(raw: bytes, expected_count: int) -> list[str]:
    lines = [line.strip() for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    if len(lines) != expected_count:
        raise ValueError(f"Label count {len(lines)} != expected {expected_count}")
    return lines


def materialize_split(
    split_name: str,
    split_contract: dict[str, Any],
    source_dir: Path,
    output_root: Path,
    contract: dict[str, Any],
    write_output: bool,
) -> dict[str, Any]:
    count = int(split_contract["sample_count"])
    split_dir = output_root / split_name
    images = labels = source_labels = provenance_handle = None
    if write_output:
        split_dir.mkdir(parents=True, exist_ok=False)
        images = np.lib.format.open_memmap(
            split_dir / "images.npy", mode="w+", dtype="<f4", shape=(count, 62, 80, 1)
        )
        labels = np.lib.format.open_memmap(
            split_dir / "labels.npy", mode="w+", dtype="i1", shape=(count,)
        )
        source_labels = np.lib.format.open_memmap(
            split_dir / "source_labels.npy", mode="w+", dtype="u1", shape=(count,)
        )
        provenance_handle = (split_dir / "sample_index.jsonl").open("wb", buffering=1024 * 1024)

    streams = {name: hashlib.sha256() for name in (
        "tensor_float32_le", "target_labels_int8", "source_labels_uint8", "sample_index_jsonl"
    )}
    source_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    geometries: Counter[str] = Counter()
    field_counts: Counter[str] = Counter()
    try:
        with open_split_zip(source_dir, split_contract["archive_parts"]) as archive:
            names = archive.namelist()
            name_set = set(names)
            if len(name_set) != len(names):
                raise ValueError(f"Duplicate ZIP member names in {split_name}")
            label_member = split_contract["label_member"]
            lines = parse_label_lines(archive.read(label_member), count)
            image_t_count = sum(
                1 for name in names if "/image_t_" in name and name.lower().endswith(".png")
            )
            if image_t_count != count:
                raise ValueError(f"{split_name} image_t count {image_t_count} != {count}")

            for index, line in enumerate(lines):
                fields = [field.strip() for field in line.split(",")]
                field_counts[str(len(fields))] += 1
                source_token = int(fields[0])
                target_label = map_source_label(source_token, contract)
                member_name = split_contract["image_member_template"].format(index=index)
                if member_name not in name_set:
                    raise ValueError(f"Missing source member: {member_name}")
                image_bytes = archive.read(member_name)
                with Image.open(io.BytesIO(image_bytes)) as image:
                    image.load()
                    source_mode, source_size = image.mode, image.size
                    normalized = normalize_image(image, contract)
                if normalized.shape != (62, 80):
                    raise ValueError(f"Unexpected output shape: {normalized.shape}")

                tensor_bytes = normalized.tobytes(order="C")
                record = {
                    "sample_id": f"sdt:{split_name}:{index:05d}",
                    "sample_index": index,
                    "split": split_name,
                    "role": split_contract["role"],
                    "source_archive_id": "+".join(split_contract["archive_parts"]),
                    "source_member_path": member_name,
                    "source_member_crc32": f"{archive.getinfo(member_name).CRC:08x}",
                    "source_png_sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "source_geometry_hw": [source_size[1], source_size[0]],
                    "source_mode": source_mode,
                    "label_member_path": label_member,
                    "label_record_index": index,
                    "source_label_record": line,
                    "source_label_record_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    "source_label_token": source_token,
                    "target_label": target_label,
                    "label_mapping_id": contract["label_mapping"]["mapping_id"],
                    "preprocessing_id": contract["preprocessing"]["preprocessing_id"],
                    "derived_tensor_shape": [62, 80, 1],
                    "derived_tensor_dtype": "float32",
                    "derived_tensor_sha256": hashlib.sha256(tensor_bytes).hexdigest(),
                }
                provenance_bytes = stable_json_bytes(record)
                streams["tensor_float32_le"].update(tensor_bytes)
                streams["target_labels_int8"].update(bytes([target_label]))
                streams["source_labels_uint8"].update(bytes([source_token]))
                streams["sample_index_jsonl"].update(provenance_bytes)
                source_counts[str(source_token)] += 1
                target_counts[str(target_label)] += 1
                modes[source_mode] += 1
                geometries[f"{source_size[1]}x{source_size[0]}"] += 1
                if write_output:
                    assert images is not None and labels is not None
                    assert source_labels is not None and provenance_handle is not None
                    images[index, :, :, 0] = normalized
                    labels[index] = target_label
                    source_labels[index] = source_token
                    provenance_handle.write(provenance_bytes)
                if (index + 1) % 2000 == 0 or index + 1 == count:
                    pass_name = "write" if write_output else "repeat-audit"
                    print(f"[{pass_name}] {split_name}: {index + 1}/{count}", flush=True)
    finally:
        if write_output:
            assert images is not None and labels is not None
            assert source_labels is not None and provenance_handle is not None
            images.flush()
            labels.flush()
            source_labels.flush()
            provenance_handle.close()
            del images, labels, source_labels

    summary: dict[str, Any] = {
        "split": split_name,
        "role": split_contract["role"],
        "sample_count": count,
        "source_archive_parts": split_contract["archive_parts"],
        "label_member": split_contract["label_member"],
        "source_class_counts": dict(sorted(source_counts.items())),
        "target_class_counts": dict(sorted(target_counts.items())),
        "source_modes": dict(sorted(modes.items())),
        "source_geometries_hw": dict(sorted(geometries.items())),
        "label_field_count_histogram": dict(sorted(field_counts.items())),
        "logical_stream_hashes": {name: digest.hexdigest() for name, digest in streams.items()},
    }
    if write_output:
        output_files = []
        for name in ("images.npy", "labels.npy", "source_labels.npy", "sample_index.jsonl"):
            path = split_dir / name
            output_files.append({
                "path": repo_relative(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
        summary["output_files"] = output_files
        write_json(split_dir / "split_manifest.json", summary)
    return summary


def build_artifact_registry(output_root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(item for item in output_root.rglob("*") if item.is_file()):
        records.append({
            "path": repo_relative(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repeat-audit", action="store_true")
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    args.manifest_dir.mkdir(parents=True, exist_ok=True)

    before = fingerprint_sources(args.source_dir, contract, "source-before")
    first_pass: dict[str, Any] = {}
    repeat_pass: dict[str, Any] = {}
    for split_name, split_contract in contract["splits"].items():
        first_pass[split_name] = materialize_split(
            split_name, split_contract, args.source_dir, args.output_dir, contract, True
        )
    if args.repeat_audit:
        for split_name, split_contract in contract["splits"].items():
            repeat_pass[split_name] = materialize_split(
                split_name, split_contract, args.source_dir, args.output_dir, contract, False
            )

    after = fingerprint_sources(args.source_dir, contract, "source-after")
    identity = lambda rows: {
        row["archive_name"]: (row["size_bytes"], row["mtime_ns"], row["sha256"])
        for row in rows
    }
    source_unchanged = identity(before) == identity(after)
    if not source_unchanged:
        raise RuntimeError("Source archive identity changed during materialization")
    repeat_matches = bool(args.repeat_audit) and all(
        first_pass[name]["logical_stream_hashes"] == repeat_pass[name]["logical_stream_hashes"]
        for name in first_pass
    )
    if args.repeat_audit and not repeat_matches:
        raise RuntimeError("Deterministic repeat audit failed")

    total_count = sum(item["sample_count"] for item in first_pass.values())
    dataset_manifest = {
        "schema_version": "safenest.thermal.b6r_p0.materialized_dataset.v1",
        "stage_id": contract["stage_id"],
        "dataset_id": contract["dataset_id"],
        "dataset_authority": contract["dataset_authority"],
        "contract_path": repo_relative(args.contract),
        "materialized_root": repo_relative(args.output_dir),
        "total_sample_count": total_count,
        "splits": first_pass,
        "preprocessing": contract["preprocessing"],
        "label_mapping": contract["label_mapping"],
        "role_policy": contract["role_policy"],
        "claim_boundary": contract["claim_boundary"],
    }
    write_json(args.output_dir / "dataset_manifest.json", dataset_manifest)

    write_json(args.manifest_dir / "source_immutability.json", {
        "schema_version": "safenest.thermal.b6r_p0.source_immutability.v1",
        "source_location_id": contract["source_location_id"],
        "absolute_path_persisted": False,
        "before": before,
        "after": after,
        "source_unchanged": source_unchanged,
        "status": "PASS" if source_unchanged else "FAIL",
    })
    write_json(args.manifest_dir / "determinism_audit.json", {
        "schema_version": "safenest.thermal.b6r_p0.determinism_audit.v1",
        "repeat_audit_executed": bool(args.repeat_audit),
        "first_pass_logical_stream_hashes": {
            name: value["logical_stream_hashes"] for name, value in first_pass.items()
        },
        "repeat_pass_logical_stream_hashes": {
            name: value["logical_stream_hashes"] for name, value in repeat_pass.items()
        },
        "all_stream_hashes_match": repeat_matches,
        "status": "PASS" if repeat_matches else "NOT_RUN",
    })
    write_json(args.manifest_dir / "split_contract.json", {
        "schema_version": "safenest.thermal.b6r_p0.split_contract.v1",
        "dataset_id": contract["dataset_id"],
        "split_roles": {
            name: {
                "role": value["role"],
                "sample_count": value["sample_count"],
                "source_archive_parts": value["source_archive_parts"],
            }
            for name, value in first_pass.items()
        },
        "source_splits_preserved": True,
        "random_resplit_performed": False,
        "test_selection_or_tuning_allowed": False,
        "test_access_in_stage": "MATERIALIZATION_INTEGRITY_PROVENANCE_ONLY",
        "test_metrics_computed": False,
        "subject_or_session_group_isolation_claimed": False,
    })
    write_json(args.manifest_dir / "preprocessing_contract.json", {
        "schema_version": "safenest.thermal.b6r_p0.preprocessing_contract.v1",
        **contract["preprocessing"],
        "source_selection": contract["source_selection"],
        "label_mapping": contract["label_mapping"],
    })
    write_json(args.manifest_dir / "materialization_result.json", {
        "schema_version": "safenest.thermal.b6r_p0.materialization_result.v1",
        "stage_id": contract["stage_id"],
        "dataset_id": contract["dataset_id"],
        "status": "PASS",
        "total_sample_count": total_count,
        "split_sample_counts": {
            name: value["sample_count"] for name, value in first_pass.items()
        },
        "selected_member_family": "image_t",
        "excluded_member_family": "image_d",
        "source_archives_modified": False,
        "source_archives_extracted": False,
        "payload_git_tracked": False,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pillow": pillow_version,
            "platform": platform.system(),
        },
        "claim_boundary": contract["claim_boundary"],
    })
    registry = build_artifact_registry(args.output_dir)
    write_json(args.manifest_dir / "artifact_registry.json", {
        "schema_version": "safenest.thermal.b6r_p0.artifact_registry.v1",
        "materialized_payload_git_tracked": False,
        "artifact_count": len(registry),
        "artifacts": registry,
    })
    print(f"B6R-P0 materialization PASS: {total_count} samples", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
