"""PUBLIC_SDT source access for the Thermal V2 Candidate A prototype.

Reads the verified T-A6 canonical artifacts (``[N,62,80]`` float32 Celsius, geometry profile
``G1_FIXED_ASPECT_CROP_BILINEAR``) plus their per-sample provenance, and exposes the frozen
SDT posture -> SafeNest 3-class mapping.

Only the official TRAIN and DEVELOPMENT roles are reachable from here. ``LOCKED_PUBLIC_TEST`` has
no loader, no path, and no code path in this module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

import numpy as np

SOURCE_ID: Final[str] = "PUBLIC_SDT"
DATASET_ID: Final[str] = "PUBLIC_SDT_48000_THERMAL_ONLY_V1"
SOURCE_DOI: Final[str] = "doi:10.5281/zenodo.4124309"

# Frozen T-A6 canonical artifact identities (verified against the on-disk conversion ledgers).
CANONICAL_ARTIFACTS: Final[dict] = {
    "TRAIN": {
        "tensor_relpath": "TRAIN/train_canonical.npy",
        "provenance_relpath": "TRAIN/train_provenance.jsonl",
        "tensor_sha256": "749c847fc9ab50ea5eee8827f0d47b5ebaa48165732a382c59f8b96c565b9d93",
        "provenance_sha256": "b4ec8228e35703bac3319ca218a69fdef43013ea44b23376da4929b274d24888",
        "rows": 32000,
    },
    "DEVELOPMENT": {
        "tensor_relpath": "VALIDATION/validation_canonical.npy",
        "provenance_relpath": "VALIDATION/validation_provenance.jsonl",
        "tensor_sha256": "5d16451702c1bccfa945d9188d9b29a26ce11c8b33bf7a0dfbb25bfa86d74610",
        "provenance_sha256": "48ebd03ca6f8d738ad7048aa72d4c454fd821140aa887971c27c5b49c1d7ec63",
        "rows": 8000,
    },
}

# Canonical multipart TRAIN archive identities recorded by the Thermal V2 source contract.
TRAIN_ARCHIVE_SHA256: Final[dict] = {
    "train.zip.001": "9dd2f944f43209dd44463956b7b34030daecc22bf49050478e77aae27c48dbc4",
    "train.zip.002": "91be187a432e21c6020928d115d1394ccf540cc6addac8f064a7b181cabe2259",
    "train.zip.003": "a2e263e0a9024363d787a335ad8641d2a73ee61129d7cb2eb1cffa32b16e1187",
    "train.zip.004": "406160460568f387b9a84e392430ed2afe57aeb055d073ba93f722c3b0d3b071",
}

SOURCE_POSE_LABELS: Final[dict] = {0: "LYING", 1: "SITTING", 2: "STANDING", 3: "EMPTY_ROOM"}

CLASS_NAMES: Final[tuple[str, str, str]] = ("NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY")
NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY = 0, 1, 2

POSE_TO_CLASS: Final[dict] = {
    "EMPTY_ROOM": NOT_HUMAN,
    "SITTING": HUMAN_NORMAL,
    "STANDING": HUMAN_NORMAL,
    "LYING": HUMAN_FALL_PROXY,
}

POSE_SEMANTIC_SUBTYPE: Final[dict] = {
    "EMPTY_ROOM": "NO_ANNOTATED_HUMAN_IN_REPRESENTED_FRAME",
    "SITTING": "NORMAL_SEATED",
    "STANDING": "NORMAL_UPRIGHT",
    "LYING": "STATIC_LYING_POSTURE",
}

POSE_MAPPING_RULE: Final[dict] = {
    "EMPTY_ROOM": "THERMAL_MAP_EMPTY_ROOM_TO_NO_HUMAN_001",
    "SITTING": "THERMAL_MAP_SITTING_TO_NON_LYING_PROXY_001",
    "STANDING": "THERMAL_MAP_STANDING_TO_NON_LYING_PROXY_001",
    "LYING": "THERMAL_MAP_LYING_TO_FALL_COMPAT_PROXY_001",
}

LOCKED_TEST_POLICY: Final[dict] = {
    "role": "LOCKED_PUBLIC_TEST",
    "access": "FORBIDDEN",
    "loader_present": False,
    "materialized": False,
    "scored": False,
    "used_for_preprocessing": False,
    "used_for_selection": False,
}


class SdtSourceError(RuntimeError):
    """Raised when the PUBLIC_SDT canonical artifacts cannot be verified."""


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_role(canonical_root: Path, role: str, verify_checksums: bool = True) -> dict:
    """Verify one canonical role's artifact identity against the frozen T-A6 hashes."""
    if role not in CANONICAL_ARTIFACTS:
        raise SdtSourceError(f"unsupported SDT role {role!r}; LOCKED_PUBLIC_TEST has no loader")
    spec = CANONICAL_ARTIFACTS[role]
    tensor_path = canonical_root / spec["tensor_relpath"]
    provenance_path = canonical_root / spec["provenance_relpath"]
    for path in (tensor_path, provenance_path):
        if not path.is_file():
            raise SdtSourceError(f"missing canonical artifact: {path}")

    record = {
        "role": role,
        "tensor_path": spec["tensor_relpath"],
        "provenance_path": spec["provenance_relpath"],
        "expected_tensor_sha256": spec["tensor_sha256"],
        "expected_provenance_sha256": spec["provenance_sha256"],
        "expected_rows": spec["rows"],
    }
    if verify_checksums:
        record["observed_tensor_sha256"] = sha256_file(tensor_path)
        record["observed_provenance_sha256"] = sha256_file(provenance_path)
        record["identity_match"] = (
            record["observed_tensor_sha256"] == spec["tensor_sha256"]
            and record["observed_provenance_sha256"] == spec["provenance_sha256"]
        )
        if not record["identity_match"]:
            raise SdtSourceError(f"SDT {role} canonical artifact identity mismatch")
    else:
        record["identity_match"] = None
    return record


def load_provenance(canonical_root: Path, role: str) -> list[dict]:
    """Load the per-sample lineage fields needed by the Candidate A manifest."""
    spec = CANONICAL_ARTIFACTS[role]
    path = canonical_root / spec["provenance_relpath"]
    keep = (
        "canonical_sample_index",
        "stable_sample_id",
        "source_member",
        "source_frame_index",
        "source_pose_name",
        "source_pose_label",
        "source_split",
        "conversion_status",
        "quality_status",
        "t_a2_geometry_profile_id",
    )
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            rows.append({key: record.get(key) for key in keep})
    if len(rows) != spec["rows"]:
        raise SdtSourceError(f"SDT {role} provenance row count {len(rows)} != {spec['rows']}")
    if any(row["conversion_status"] != "SUCCESS" for row in rows):
        raise SdtSourceError(f"SDT {role} contains non-SUCCESS conversion rows")
    return rows


def load_role(canonical_root: Path, role: str, verify_checksums: bool = True) -> dict:
    """Load one SDT role as canonical Celsius frames plus labels and lineage."""
    identity = verify_role(canonical_root, role, verify_checksums=verify_checksums)
    spec = CANONICAL_ARTIFACTS[role]
    frames = np.load(canonical_root / spec["tensor_relpath"], mmap_mode="r")
    frames = np.asarray(frames, dtype=np.float32)
    if frames.shape != (spec["rows"], 62, 80):
        raise SdtSourceError(f"SDT {role} tensor shape {frames.shape} unexpected")
    if not np.isfinite(frames).all():
        raise SdtSourceError(f"SDT {role} tensor contains non-finite values; policy is fail-closed")

    provenance = load_provenance(canonical_root, role)
    pose_names = [row["source_pose_name"] for row in provenance]
    unknown = sorted({name for name in pose_names if name not in POSE_TO_CLASS})
    if unknown:
        raise SdtSourceError(f"unmapped SDT pose tokens {unknown}")
    labels = np.asarray([POSE_TO_CLASS[name] for name in pose_names], dtype=np.int64)

    return {
        "identity": identity,
        "frames_celsius": frames,
        "labels": labels,
        "pose_names": pose_names,
        "provenance": provenance,
    }
