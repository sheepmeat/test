"""Training and evaluation runner for the Thermal V2 Candidate A data-corrective prototype.

Experiment arms
---------------
``A0``    PUBLIC_SDT TRAIN only.
``A1``    PUBLIC_SDT TRAIN + verified Thermal-IM seated ``HUMAN_NORMAL`` hard negatives.
``A0R``   PUBLIC_SDT TRAIN + the *same number* of duplicated SDT ``HUMAN_NORMAL`` frames.

``A0R`` exists so that any A1 gain can be separated from the pure class-prior shift that adding
``HUMAN_NORMAL`` rows causes on its own. Architecture, representation, optimizer, schedule,
augmentation policy, early stopping and evaluation protocol are identical across all arms; the
only experimental factor is which extra ``HUMAN_NORMAL`` rows are appended.

Memory policy
-------------
The host has 8 GB of RAM, so normalized splits are materialized once as on-disk float16 memmaps
and every arm is expressed as an *index map* over those memmaps. Nothing concatenates or
duplicates frame payloads in RAM; batches are gathered and cast to float32 on demand.

``LOCKED_PUBLIC_TEST`` is never loaded, materialized, scored, or used for any statistic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import numpy as np

from datasets.thermal import tv2_ca_metrics as metrics
from datasets.thermal import tv2_ca_model as arch
from datasets.thermal import tv2_ca_representation as rep
from datasets.thermal import tv2_ca_sdt_source as sdt

ARM_A0: Final[str] = "A0"
ARM_A1: Final[str] = "A1"
ARM_A0R: Final[str] = "A0R"

CACHE_DTYPE: Final[str] = "float16"

TRAINING_POLICY: Final[dict] = {
    "optimizer": "adam",
    "learning_rate": 1e-3,
    "loss": "sparse_categorical_crossentropy",
    "batch_size": 256,
    "max_epochs": 30,
    "early_stopping_monitor": "val_loss",
    "early_stopping_patience": 5,
    "restore_best_weights": True,
    "class_weighting": "NONE",
    "augmentation": "NONE",
    "shuffle": "SEEDED_PERMUTATION_PER_EPOCH",
    "validation_role": "PUBLIC_SDT_DEVELOPMENT_8000",
    "cache_storage_dtype": CACHE_DTYPE,
    "compute_dtype": "float32",
    "locked_public_test_access": "NONE",
}


class RunnerContractError(RuntimeError):
    """Raised when a Candidate A precondition cannot be satisfied."""


# --------------------------------------------------------------------------------------- caches


def cache_path(work_root: Path, key: str, normalization: str) -> Path:
    return work_root / "cache" / f"{key}__{normalization}.f16.npy"


def build_sdt_cache(work_root: Path, canonical_root: Path, role: str, normalization: str,
                    verify_checksums: bool = False) -> dict:
    """Materialize one normalized SDT role as an on-disk float16 memmap."""
    identity = sdt.verify_role(canonical_root, role, verify_checksums=verify_checksums)
    spec = sdt.CANONICAL_ARTIFACTS[role]
    target = cache_path(work_root, f"sdt_{role}", normalization)
    target.parent.mkdir(parents=True, exist_ok=True)

    provenance = sdt.load_provenance(canonical_root, role)
    pose_names = [row["source_pose_name"] for row in provenance]
    labels = np.asarray([sdt.POSE_TO_CLASS[name] for name in pose_names], dtype=np.int64)

    if not target.is_file():
        source = np.load(canonical_root / spec["tensor_relpath"], mmap_mode="r")
        if source.shape != (spec["rows"], 62, 80):
            raise RunnerContractError(f"SDT {role} tensor shape {source.shape} unexpected")
        destination = np.lib.format.open_memmap(
            target, mode="w+", dtype=np.float16, shape=source.shape
        )
        rep.normalize_into(source, destination, normalization)
        destination.flush()
        del destination, source

    frames = np.load(target, mmap_mode="r")
    return {"identity": identity, "frames": frames, "labels": labels, "pose_names": pose_names}


def build_thermal_im_cache(work_root: Path, normalization: str) -> dict | None:
    """Materialize the normalized Thermal-IM hard-negative pool as an on-disk float16 memmap."""
    pool_path = work_root / "thermal_im" / "hard_negative_pool.npz"
    manifest_path = work_root / "thermal_im" / "hard_negative_manifest.json"
    if not pool_path.is_file() or not manifest_path.is_file():
        return None

    target = cache_path(work_root, "thermal_im_pool", normalization)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = np.load(pool_path, allow_pickle=False)
    roles = payload["training_eval_role"].astype(str)
    groups = payload["recording_group_id"].astype(str)
    clips = payload["clip_id"].astype(str)
    frame_index = payload["source_frame_index"]

    if not target.is_file():
        source = payload["frames_intensity"]
        destination = np.lib.format.open_memmap(
            target, mode="w+", dtype=np.float16, shape=source.shape
        )
        rep.normalize_into(source, destination, normalization)
        destination.flush()
        del destination, source
    payload.close()

    return {
        "frames": np.load(target, mmap_mode="r"),
        "role": roles,
        "recording_group_id": groups,
        "clip_id": clips,
        "source_frame_index": frame_index,
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
    }


# ------------------------------------------------------------------------------- hard negatives


def select_hard_negatives(pool: dict, target_count: int) -> np.ndarray:
    """Deterministically select ``target_count`` training hard negatives.

    Selection is quota-proportional across clips and temporally spread inside each clip, so the
    pool is not dominated by one clip and consecutive near-duplicate frames are avoided.
    """
    candidate_indices = np.flatnonzero(pool["role"] == "HN_TRAIN_POOL")
    if target_count > candidate_indices.size:
        raise RunnerContractError(
            f"requested {target_count} Thermal-IM hard negatives but only "
            f"{candidate_indices.size} training-pool frames are available"
        )
    if target_count == candidate_indices.size:
        return candidate_indices

    clip_ids = pool["clip_id"][candidate_indices]
    frame_order = pool["source_frame_index"][candidate_indices]
    unique_clips = sorted(set(clip_ids.tolist()))

    per_clip: dict[str, np.ndarray] = {}
    for clip in unique_clips:
        local = np.flatnonzero(clip_ids == clip)
        per_clip[clip] = local[np.argsort(frame_order[local], kind="stable")]

    total = candidate_indices.size
    quotas = {clip: int(np.floor(target_count * per_clip[clip].size / total)) for clip in unique_clips}
    shortfall = target_count - sum(quotas.values())
    for clip in sorted(unique_clips, key=lambda name: (-per_clip[name].size, name)):
        if shortfall <= 0:
            break
        if quotas[clip] < per_clip[clip].size:
            quotas[clip] += 1
            shortfall -= 1

    chosen: list[int] = []
    for clip in unique_clips:
        quota = quotas[clip]
        if quota <= 0:
            continue
        ordered = per_clip[clip]
        picks = np.unique(np.linspace(0, ordered.size - 1, quota).round().astype(np.int64))
        chosen.extend(ordered[picks].tolist())
    return candidate_indices[np.asarray(sorted(chosen), dtype=np.int64)]


# ------------------------------------------------------------------------------------ arm build

SOURCE_SDT: Final[int] = 0
SOURCE_TIM: Final[int] = 1


def build_arm(sdt_train: dict, pool: dict | None, arm: str, hn_ratio: float, seed: int) -> dict:
    """Express one arm as an index map over the cached memmaps."""
    labels = sdt_train["labels"]
    sdt_rows = int(labels.size)
    normal_count = int((labels == sdt.HUMAN_NORMAL).sum())
    extra_target = int(round(normal_count * hn_ratio))

    membership = {
        "arm": arm,
        "sdt_train_frames": sdt_rows,
        "sdt_class_counts": {sdt.CLASS_NAMES[i]: int((labels == i).sum()) for i in range(3)},
        "sdt_human_normal_population": normal_count,
        "hn_ratio_definition": "extra_HUMAN_NORMAL_rows / SDT_TRAIN_HUMAN_NORMAL_population",
        "hn_ratio": hn_ratio,
        "extra_human_normal_target": extra_target,
    }

    source_ids = np.full(sdt_rows, SOURCE_SDT, dtype=np.int8)
    row_indices = np.arange(sdt_rows, dtype=np.int64)
    arm_labels = labels.copy()

    if arm == ARM_A0 or extra_target == 0:
        membership.update({
            "thermal_im_frames_used": 0,
            "duplicated_sdt_normal_frames": 0,
            "source_id_counts": {"PUBLIC_SDT": sdt_rows},
        })
    elif arm == ARM_A1:
        if pool is None:
            raise RunnerContractError("A1 requires a built Thermal-IM hard-negative pool")
        selected = select_hard_negatives(pool, extra_target)
        source_ids = np.concatenate([source_ids, np.full(selected.size, SOURCE_TIM, dtype=np.int8)])
        row_indices = np.concatenate([row_indices, selected])
        arm_labels = np.concatenate([arm_labels, np.full(selected.size, sdt.HUMAN_NORMAL, dtype=np.int64)])
        membership.update({
            "thermal_im_frames_used": int(selected.size),
            "duplicated_sdt_normal_frames": 0,
            "thermal_im_clip_count": len(set(pool["clip_id"][selected].tolist())),
            "thermal_im_clips": sorted(set(pool["clip_id"][selected].tolist())),
            "thermal_im_recording_groups": sorted(set(pool["recording_group_id"][selected].tolist())),
            "thermal_im_mapped_class": "HUMAN_NORMAL",
            "thermal_im_fall_proxy_contribution": 0,
            "thermal_im_not_human_contribution": 0,
            "thermal_im_train_pool_available": int((pool["role"] == "HN_TRAIN_POOL").sum()),
            "source_id_counts": {"PUBLIC_SDT": sdt_rows, "Thermal-IM": int(selected.size)},
        })
    elif arm == ARM_A0R:
        rng = np.random.default_rng(20260830 + seed)
        normal_indices = np.flatnonzero(labels == sdt.HUMAN_NORMAL)
        picks = rng.choice(normal_indices, size=extra_target, replace=extra_target > normal_indices.size)
        source_ids = np.concatenate([source_ids, np.full(extra_target, SOURCE_SDT, dtype=np.int8)])
        row_indices = np.concatenate([row_indices, picks.astype(np.int64)])
        arm_labels = np.concatenate([arm_labels, np.full(extra_target, sdt.HUMAN_NORMAL, dtype=np.int64)])
        membership.update({
            "thermal_im_frames_used": 0,
            "duplicated_sdt_normal_frames": int(extra_target),
            "control_purpose": "ISOLATE_CLASS_PRIOR_SHIFT_FROM_THERMAL_IM_CONTENT",
            "source_id_counts": {"PUBLIC_SDT": sdt_rows + int(extra_target)},
        })
    else:
        raise RunnerContractError(f"unsupported arm {arm!r}")

    membership["final_train_frames"] = int(arm_labels.size)
    membership["final_class_counts"] = {
        sdt.CLASS_NAMES[i]: int((arm_labels == i).sum()) for i in range(3)
    }
    return {
        "source_ids": source_ids,
        "row_indices": row_indices,
        "labels": arm_labels,
        "membership": membership,
    }


# -------------------------------------------------------------------------------------- batching


def make_sequence(arm_data: dict, sdt_frames, tim_frames, batch_size: int, seed: int):
    """Keras ``Sequence`` that gathers batches from the on-disk memmaps."""
    from tensorflow import keras

    class CandidateASequence(keras.utils.Sequence):
        def __init__(self) -> None:
            super().__init__()
            self.source_ids = arm_data["source_ids"]
            self.row_indices = arm_data["row_indices"]
            self.labels = arm_data["labels"]
            self.batch_size = batch_size
            self.rng = np.random.default_rng(seed)
            self.order = self.rng.permutation(self.labels.size)

        def __len__(self) -> int:
            return int(np.ceil(self.labels.size / self.batch_size))

        def __getitem__(self, index: int):
            slice_ = self.order[index * self.batch_size:(index + 1) * self.batch_size]
            batch = np.empty((slice_.size, 62, 80, 1), dtype=np.float32)
            sources = self.source_ids[slice_]
            rows = self.row_indices[slice_]
            for position, (source, row) in enumerate(zip(sources, rows)):
                store = sdt_frames if source == SOURCE_SDT else tim_frames
                batch[position, :, :, 0] = store[row]
            return batch, self.labels[slice_]

        def on_epoch_end(self) -> None:
            self.order = self.rng.permutation(self.labels.size)

    return CandidateASequence()


def gather_eval(frames, batch_size: int = 1024):
    """Yield float32 model-input batches from a float16 memmap without materializing it."""
    total = frames.shape[0]
    for start in range(0, total, batch_size):
        stop = min(start + batch_size, total)
        block = np.asarray(frames[start:stop], dtype=np.float32)
        yield block.reshape(block.shape[0], 62, 80, 1)


def predict_classes(model, frames) -> np.ndarray:
    if frames.shape[0] == 0:
        return np.zeros((0,), dtype=np.int64)
    parts = [np.argmax(model.predict(batch, verbose=0), axis=1) for batch in gather_eval(frames)]
    return np.concatenate(parts).astype(np.int64)


# -------------------------------------------------------------------------------------- training


def train_and_evaluate(arm_data: dict, sdt_train_frames, tim_frames, dev_frames, dev_labels,
                       hn_eval_frames, head_variant: str, seed: int):
    from tensorflow import keras

    keras.utils.set_random_seed(seed)
    model = arch.build_model(head_variant, seed)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=TRAINING_POLICY["learning_rate"]),
        loss=TRAINING_POLICY["loss"],
        metrics=["accuracy"],
    )

    sequence = make_sequence(arm_data, sdt_train_frames, tim_frames,
                             TRAINING_POLICY["batch_size"], seed)
    dev_input = np.asarray(dev_frames, dtype=np.float32).reshape(dev_frames.shape[0], 62, 80, 1)
    history = model.fit(
        sequence,
        validation_data=(dev_input, dev_labels),
        epochs=TRAINING_POLICY["max_epochs"],
        verbose=0,
        callbacks=[keras.callbacks.EarlyStopping(
            monitor=TRAINING_POLICY["early_stopping_monitor"],
            patience=TRAINING_POLICY["early_stopping_patience"],
            restore_best_weights=True,
        )],
    )

    dev_pred = np.argmax(model.predict(dev_input, batch_size=512, verbose=0), axis=1)
    result = {
        "head_variant": head_variant,
        "seed": seed,
        "parameter_count": int(model.count_params()),
        "epochs_run": len(history.history["loss"]),
        "best_val_loss": float(min(history.history["val_loss"])),
        "sdt_development": metrics.evaluate(dev_labels, dev_pred),
    }
    del dev_input
    if hn_eval_frames is not None and hn_eval_frames.shape[0] > 0:
        result["thermal_im_holdout_hard_negative"] = metrics.evaluate_hard_negatives(
            predict_classes(model, hn_eval_frames)
        )
    return result, model
