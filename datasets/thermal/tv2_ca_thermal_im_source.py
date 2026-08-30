"""Thermal-IM hard-negative extraction for the Thermal V2 Candidate A prototype.

Thermal-IM contributes **only** ``HUMAN_NORMAL`` seated hard negatives. It never contributes a
``HUMAN_FALL_PROXY`` positive and never contributes ``NOT_HUMAN``.

Admitted tokens (TV2-D1 verified action-object vocabulary, TV2-D2 recommended mapping)::

    sit sofa / sit chair / sit stool / sit desk
        -> HUMAN_NORMAL, semantic subtype NORMAL_SEATED,
           event provenance NON_FALL_ACTIVITY_OR_POSTURE

Everything else is excluded with a recorded reason::

    lie sofa                     STATIC_LYING_POSTURE, excluded from both NORMAL and FALL_PROXY
    touch <object>               object interaction, not a clean posture class
    push-ups / sit-ups /
    leg-stretching               floor exercise, ambiguous activity
    take-off clothes / shoes     garment action, ambiguous activity
    step scale                   transient, not a verified posture class
    empty annotation.json        UNKNOWN; explicitly not NOT_HUMAN
    outside annotated intervals  UNLABELED

Frames are expanded from annotated ``[start, end]`` second intervals using the verified 15 FPS
timing contract. Frames from one clip are never split across roles: splitting is done at
recording-group level (``<capture_date>_<recording>``), which is strictly coarser than clip.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Final
import zipfile

import numpy as np

SOURCE_ID: Final[str] = "Thermal-IM"
NATIVE_FPS: Final[float] = 15.0
NATIVE_HW: Final[tuple[int, int]] = (288, 384)
THERMAL_MEMBER: Final[str] = "RGBT_T.mp4"
ANNOTATION_MEMBER: Final[str] = "annotation.json"

ADMITTED_SIT_OBJECTS: Final[frozenset] = frozenset({"sofa", "chair", "stool", "desk"})
ADMITTED_ACTION: Final[str] = "sit"

HUMAN_NORMAL: Final[int] = 1
SEMANTIC_SUBTYPE: Final[str] = "NORMAL_SEATED"
EVENT_PROVENANCE: Final[str] = "NON_FALL_ACTIVITY_OR_POSTURE"
MAPPING_RULE_ID: Final[str] = "TV2_CA_MAP_THERMAL_IM_SIT_TO_HUMAN_NORMAL_HARD_NEGATIVE_001"

EXCLUSION_REASONS: Final[dict] = {
    "lie": "STATIC_LYING_POSTURE_EXCLUDED_NOT_NORMAL_NOT_FALL_PROXY",
    "touch": "OBJECT_INTERACTION_NOT_CLEAN_POSTURE_CLASS",
    "push-ups": "FLOOR_EXERCISE_AMBIGUOUS_ACTIVITY",
    "sit-ups": "FLOOR_EXERCISE_AMBIGUOUS_ACTIVITY",
    "leg-stretching": "FLOOR_EXERCISE_AMBIGUOUS_ACTIVITY",
    "take-off": "GARMENT_ACTION_AMBIGUOUS_ACTIVITY",
    "step": "TRANSIENT_ACTION_NOT_VERIFIED_POSTURE_CLASS",
}

FALL_PROXY_FROM_THERMAL_IM: Final[str] = "FORBIDDEN_NO_FABRICATED_POSITIVE"
NOT_HUMAN_FROM_THERMAL_IM: Final[str] = "FORBIDDEN_EMPTY_ANNOTATION_IS_NOT_NOT_HUMAN"


class ThermalImSourceError(RuntimeError):
    """Raised when a Thermal-IM archive cannot be decoded or reconciled."""


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def classify_interval(action: str, obj: str | None) -> tuple[bool, str, str]:
    """Return ``(admitted, mapped_class_or_none, reason)`` for one annotation interval."""
    action_token = (action or "").strip().lower()
    object_token = (obj or "").strip().lower()
    token = f"{action_token} {object_token}".strip()
    if action_token == ADMITTED_ACTION and object_token in ADMITTED_SIT_OBJECTS:
        return True, "HUMAN_NORMAL", f"ADMITTED_VERIFIED_SEATED_TOKEN::{token}"
    for prefix, reason in EXCLUSION_REASONS.items():
        if action_token.startswith(prefix):
            return False, "NONE", f"{reason}::{token}"
    return False, "NONE", f"UNRECOGNISED_TOKEN_CONSERVATIVE_EXCLUDE::{token}"


def interval_to_frame_indices(start_s: float, end_s: float, frame_count: int) -> list[int]:
    """Deterministically expand a ``[start, end]`` second interval to frame indices at 15 FPS.

    A frame index ``i`` covers ``[i / fps, (i + 1) / fps)``. A frame is admitted only when its
    whole sample period lies inside the annotated interval, so partially-covered boundary frames
    are dropped rather than optimistically labelled.
    """
    if not (np.isfinite(start_s) and np.isfinite(end_s)) or end_s <= start_s:
        return []
    first = int(np.ceil(start_s * NATIVE_FPS - 1e-9))
    last = int(np.floor(end_s * NATIVE_FPS - 1e-9)) - 1
    first = max(first, 0)
    last = min(last, frame_count - 1)
    return list(range(first, last + 1)) if last >= first else []


def decode_thermal_frames(video_path: Path) -> np.ndarray:
    """Decode ``RGBT_T.mp4`` to ``[N,288,384,3]`` uint8 RGB."""
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ThermalImSourceError(f"cannot open thermal stream {video_path}")
    frames: list[np.ndarray] = []
    while True:
        ok, frame_bgr = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    capture.release()
    if not frames:
        raise ThermalImSourceError(f"decoded zero frames from {video_path}")
    stack = np.stack(frames).astype(np.uint8)
    if stack.shape[1:3] != NATIVE_HW:
        raise ThermalImSourceError(f"unexpected native geometry {stack.shape[1:3]} in {video_path}")
    return stack


def extract_clip(archive_path: Path, entry: dict) -> dict:
    """Extract admitted seated hard-negative frames from one official clip archive.

    Returns the canonicalized relative-appearance-ready frames (post geometry, pre normalization)
    plus per-frame lineage and a full interval decision ledger.
    """
    from datasets.thermal.tv2_ca_representation import thermal_im_geometry

    clip_id = entry["clip_id"]
    workdir = Path(tempfile.mkdtemp(prefix=f"tv2ca-{clip_id}-"))
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            names = bundle.namelist()
            video_name = next((n for n in names if n.endswith(THERMAL_MEMBER)), None)
            annotation_name = next((n for n in names if n.endswith(ANNOTATION_MEMBER)), None)
            if video_name is None:
                raise ThermalImSourceError(f"{archive_path.name} has no {THERMAL_MEMBER}")
            if annotation_name is None:
                raise ThermalImSourceError(f"{archive_path.name} has no {ANNOTATION_MEMBER}")
            bundle.extract(video_name, workdir)
            annotation_bytes = bundle.read(annotation_name)

        annotation = json.loads(annotation_bytes.decode("utf-8"))
        frames_rgb = decode_thermal_frames(workdir / video_name)
        frame_count = int(frames_rgb.shape[0])

        ledger: list[dict] = []
        admitted_indices: list[int] = []
        for position, interval in enumerate(annotation):
            action = interval.get("action")
            obj = interval.get("object")
            start_s = float(interval.get("start", float("nan")))
            end_s = float(interval.get("end", float("nan")))
            admitted, mapped, reason = classify_interval(action, obj)
            indices = interval_to_frame_indices(start_s, end_s, frame_count) if admitted else []
            ledger.append({
                "interval_position": position,
                "source_action": action,
                "source_object": obj,
                "source_token": f"{action} {obj}".strip(),
                "start_s": start_s,
                "end_s": end_s,
                "admitted": admitted,
                "mapped_class": mapped,
                "decision_reason": reason,
                "expanded_frame_count": len(indices),
            })
            admitted_indices.extend(indices)

        annotation_status = "EMPTY_ANNOTATION_UNKNOWN_NOT_NOT_HUMAN" if not annotation else "ANNOTATED"
        unique_indices = sorted(set(admitted_indices))
        if unique_indices:
            canonical = np.stack([thermal_im_geometry(frames_rgb[i]) for i in unique_indices])
        else:
            canonical = np.zeros((0, 62, 80), dtype=np.float32)

        lineage = [{
            "sample_id": f"{SOURCE_ID}:{clip_id}:frame{index:05d}",
            "source_id": SOURCE_ID,
            "source_asset_id": entry["archive_name"],
            "source_asset_sha256": entry["observed_sha256"],
            "clip_id": clip_id,
            "recording_group_id": entry["recording_group_id"],
            "capture_date_token": entry["capture_date_token"],
            "source_frame_index": int(index),
            "frame_time_s": round(index / NATIVE_FPS, 6),
            "source_label": "sit <admitted object>",
            "mapped_class": HUMAN_NORMAL,
            "mapped_class_name": "HUMAN_NORMAL",
            "semantic_subtype": SEMANTIC_SUBTYPE,
            "event_provenance": EVENT_PROVENANCE,
            "mapping_rule_id": MAPPING_RULE_ID,
            "representation_lane": "R_RELATIVE_APPEARANCE_PROTOTYPE_LANE",
            "native_geometry": list(NATIVE_HW),
            "geometry_profile": "TIM_FIXED_ASPECT_CROP_BILINEAR_V1",
            "quality_flags": ["COMPRESSION_VISUAL_STREAM", "NON_RADIOMETRIC_INTENSITY"],
        } for index in unique_indices]

        return {
            "clip_id": clip_id,
            "archive_name": entry["archive_name"],
            "recording_group_id": entry["recording_group_id"],
            "decoded_frame_count": frame_count,
            "annotation_status": annotation_status,
            "annotation_interval_count": len(annotation),
            "interval_ledger": ledger,
            "admitted_frame_count": len(unique_indices),
            "frames_intensity": canonical,
            "lineage": lineage,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def split_groups(group_ids: list[str], holdout_group_count: int, seed: int = 42) -> dict:
    """Deterministic recording-group-disjoint split for Thermal-IM hard negatives.

    Grouping is at ``<capture_date>_<recording>`` level, which is strictly coarser than the clip
    (``split<N>``) level, so no clip and no frame is shared between training and held-out eval.
    Actor identity is not distributed in the clip archives (release ``meta.csv`` is absent), so
    this is a documented recording-group approximation, not a verified actor-disjoint split.
    """
    ordered = sorted(set(group_ids))
    if holdout_group_count >= len(ordered):
        raise ThermalImSourceError("holdout group count must leave at least one training group")
    rng = np.random.default_rng(seed)
    permuted = list(rng.permutation(np.asarray(ordered, dtype=object)))
    holdout = sorted(str(item) for item in permuted[:holdout_group_count])
    train = sorted(str(item) for item in permuted[holdout_group_count:])
    return {
        "grouping_key": "recording_group_id",
        "grouping_level": "CAPTURE_DATE_PLUS_RECORDING",
        "grouping_status": "RECORDING_GROUP_DISJOINT",
        "actor_disjoint_status": "NOT_VERIFIABLE_RELEASE_META_CSV_ABSENT",
        "random_frame_split": "FORBIDDEN_NOT_PERFORMED",
        "seed": seed,
        "train_groups": train,
        "holdout_groups": holdout,
    }
