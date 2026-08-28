#!/usr/bin/env python3
"""Run the M-PV3.5 controlled 15 s versus 30 s context ablation.

Only the accepted causal trace length changes between lanes.  This module is
explicitly evaluation-only: it creates no production selection, calibration,
threshold adjustment, quantized artifact, or hardware-performance claim.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
from typing import Any, Mapping, Sequence

import numpy as np

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - validator gives a clearer failure
    raise SystemExit("M-PV3.5 requires torch") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT_REL = Path("config/mmwave/m_pv35_context_isolation_contract.json")
OUTPUT_REL = Path("datasets/mmwave/manifests/M-PV3_5_controlled_context_isolation")
MODEL_ROOT_REL = Path("models/mmwave/m_pv35_context_isolation")
M_PV1_VALIDATION_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/validation_result.json")
M_PV1_D2_LOCK_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/d2_lock_audit.json")

PRESENT = "BREATHING_REFERENCE_PRESENT"
ABSENT = "BREATHING_REFERENCE_ABSENT"
AMBIGUOUS = "BREATHING_REFERENCE_AMBIGUOUS"
TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"
SEEDS = (11, 23, 47)
LANES = (
    ("CONTEXT_15S", 15, 150),
    ("CONTEXT_30S", 30, 300),
)


class ContextIsolationError(RuntimeError):
    """Raised when governed input or experimental parity is invalid."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextIsolationError(f"failed to read JSON {path}: {exc}") from exc


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        _json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


@dataclasses.dataclass(frozen=True)
class ContextRecord:
    source_id: str
    subject_id: str
    recording_id: str
    model_input_id: str
    split: str
    trace_30s: np.ndarray
    breathing_state: str
    breathing_label: float
    breathing_mask: float
    quality_status: str
    provenance: Mapping[str, Any]


def _load_records() -> tuple[list[ContextRecord], dict[str, Any]]:
    """Load the governed M-PV1 membership through the accepted M-PV2 reader."""

    from scripts import mmwave_m_pv2_candidate_training as pv2

    base_records, materialization = pv2._load_materialized_records()
    records: list[ContextRecord] = []
    for base in sorted(base_records, key=lambda item: item.model_input_id):
        if base.source_id == "D0" and base.split != "TRAIN":
            raise ContextIsolationError(f"D0 non-TRAIN input is forbidden: {base.model_input_id}")
        if base.source_id == "D1" and base.split not in {"D1_DEV_TRAIN", "D1_DEV_VAL"}:
            raise ContextIsolationError(f"D1 non-DEV input is forbidden: {base.model_input_id}")
        if base.source_id not in {"D0", "D1"}:
            raise ContextIsolationError(f"unexpected input source: {base.source_id}")
        trace = np.asarray(base.trace, dtype=np.float32)
        if trace.shape != (300,) or not np.all(np.isfinite(trace)):
            raise ContextIsolationError(f"invalid accepted 30-second trace: {base.model_input_id}")
        state = str(base.breathing_state)
        if state not in {PRESENT, ABSENT, AMBIGUOUS}:
            raise ContextIsolationError(f"unexpected inherited breathing state: {state}")
        expected_mask = 1.0 if state in {PRESENT, ABSENT} else 0.0
        if float(base.breathing_mask) != expected_mask:
            raise ContextIsolationError(f"breathing mask/state mismatch: {base.model_input_id}")
        provenance = base.provenance if isinstance(base.provenance, Mapping) else {}
        required = (
            "source_id", "subject_id", "recording_id", "model_input_id", "split",
            "context_start_s", "context_end_s", "target_start_s", "target_end_s",
            "r1_profile", "r2_profile", "breathing_state", "breathing_supervision_eligible",
            "quality_status", "tensor_derivation", "synthetic",
        )
        missing = [name for name in required if name not in provenance]
        if missing:
            raise ContextIsolationError(f"missing provenance {missing}: {base.model_input_id}")
        records.append(ContextRecord(
            source_id=str(base.source_id),
            subject_id=str(base.subject_id),
            recording_id=str(base.recording_id),
            model_input_id=str(base.model_input_id),
            split=str(base.split),
            trace_30s=trace,
            breathing_state=state,
            breathing_label=1.0 if state == PRESENT else 0.0,
            breathing_mask=expected_mask,
            quality_status=str(base.quality_status),
            provenance=dict(provenance),
        ))

    if len(records) != 562 or len({row.model_input_id for row in records}) != 562:
        raise ContextIsolationError("M-PV1 governed membership must contain 562 unique records")
    by_source = {source: sum(row.source_id == source for row in records) for source in ("D0", "D1")}
    by_split = {name: sum(row.split == name for row in records) for name in ("TRAIN", "D1_DEV_TRAIN", "D1_DEV_VAL")}
    if by_source != {"D0": 318, "D1": 244} or by_split != {"TRAIN": 318, "D1_DEV_TRAIN": 185, "D1_DEV_VAL": 59}:
        raise ContextIsolationError(f"governed membership changed: sources={by_source}, splits={by_split}")
    return records, {
        "materialization_counts": materialization.get("counts", {}),
        "by_source": by_source,
        "by_split": by_split,
        "state_counts": {state: sum(row.breathing_state == state for row in records) for state in (PRESENT, ABSENT, AMBIGUOUS)},
        "unique_model_input_count": len({row.model_input_id for row in records}),
    }


def _group(records: Sequence[ContextRecord], name: str) -> list[ContextRecord]:
    if name == "TRAIN":
        return [
            row for row in records
            if (row.source_id == "D0" and row.split == "TRAIN")
            or (row.source_id == "D1" and row.split == "D1_DEV_TRAIN")
        ]
    if name == "D1_DEV_VAL":
        return [row for row in records if row.source_id == "D1" and row.split == "D1_DEV_VAL"]
    if name == "D0_TRAIN_OBSERVE":
        return [row for row in records if row.source_id == "D0" and row.split == "TRAIN"]
    raise ContextIsolationError(f"unknown group {name}")


def _fit_common_scaler(train_records: Sequence[ContextRecord]) -> dict[str, Any]:
    """Fit once on full 30-second train contexts and share it between lanes."""

    values = np.concatenate([row.trace_30s for row in train_records]).astype(np.float64)
    mean, std = float(np.mean(values)), float(np.std(values))
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 1e-8:
        raise ContextIsolationError("invalid common TRAIN-only scaler")
    result = {
        "profile_id": "MMWAVE_V2_M_PV35_COMMON_30S_TRAIN_ZSCORE_V1",
        "fit_scope": ["D0:TRAIN", "D1:D1_DEV_TRAIN"],
        "fit_context_seconds": 30,
        "shared_without_refit_across_lanes": True,
        "window_count": len(train_records),
        "sample_count": int(values.size),
        "mean": mean,
        "std": std,
    }
    result["sha256"] = _sha256_json(result)
    return result


def _lane_matrix(records: Sequence[ContextRecord], samples: int, scaler: Mapping[str, Any]) -> np.ndarray:
    if samples not in {150, 300}:
        raise ContextIsolationError(f"unsupported sample count {samples}")
    matrix = np.stack([row.trace_30s[-samples:] for row in records]).astype(np.float32)
    matrix = (matrix - float(scaler["mean"])) / float(scaler["std"])
    if matrix.shape != (len(records), samples) or not np.all(np.isfinite(matrix)):
        raise ContextIsolationError("lane normalization produced invalid input")
    return matrix[:, :, None]


def _labels(records: Sequence[ContextRecord]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([row.breathing_label for row in records], dtype=np.float32),
        np.asarray([row.breathing_mask for row in records], dtype=np.float32),
    )


def _sample_weights(records: Sequence[ContextRecord], source_weights: Mapping[str, Any]) -> np.ndarray:
    counts: dict[tuple[str, str], int] = {}
    for row in records:
        if row.breathing_mask > 0:
            key = (row.source_id, row.subject_id)
            counts[key] = counts.get(key, 0) + 1
    base: list[float] = []
    for row in records:
        if row.breathing_mask <= 0:
            base.append(0.0)
        else:
            base.append(float(source_weights[row.source_id]) / counts[(row.source_id, row.subject_id)])
    class_mass = {
        label: sum(weight for weight, row in zip(base, records) if row.breathing_mask > 0 and int(row.breathing_label) == label)
        for label in (0, 1)
    }
    if min(class_mass.values()) <= 0:
        raise ContextIsolationError(f"TRAIN has no eligible class: {class_mass}")
    total = sum(class_mass.values())
    class_weights = {label: total / (2.0 * mass) for label, mass in class_mass.items()}
    return np.asarray([
        weight * class_weights[int(row.breathing_label)] if row.breathing_mask > 0 else 0.0
        for weight, row in zip(base, records)
    ], dtype=np.float32)


class ParityTraceCNN(nn.Module):
    """Identical parameterization for both variable-length causal inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(1, 8, kernel_size=5, stride=2, padding=0)
        self.conv2 = nn.Conv1d(8, 16, kernel_size=5, stride=2, padding=0)
        self.conv3 = nn.Conv1d(16, 24, kernel_size=3, stride=2, padding=0)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(24, 16)
        self.head = nn.Linear(16, 1)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        if values.ndim != 3 or values.shape[2] != 1 or values.shape[1] not in {150, 300}:
            raise ValueError(f"expected [B,150|300,1], got {tuple(values.shape)}")
        values = values.transpose(1, 2)
        values = torch.relu(self.conv1(values))
        values = torch.relu(self.conv2(values))
        values = torch.relu(self.conv3(values))
        values = self.pool(values).squeeze(-1)
        values = torch.relu(self.fc(values))
        return self.head(values).squeeze(-1)


def _parameter_count(model: nn.Module) -> int:
    return int(sum(parameter.numel() for parameter in model.parameters()))


def _set_deterministic(seed: int) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    try:
        torch.set_num_threads(1)
    except RuntimeError:
        pass
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    try:
        torch.use_deterministic_algorithms(True)
        deterministic = True
    except Exception:
        deterministic = False
    return {
        "seed": seed,
        "python_hash_seed_requested": os.environ.get("PYTHONHASHSEED", "UNSET"),
        "torch_deterministic_algorithms": deterministic,
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": int(torch.get_num_interop_threads()),
    }


def _masked_bce(logits: torch.Tensor, labels: torch.Tensor, masks: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    loss = nn.functional.binary_cross_entropy_with_logits(logits, labels, reduction="none")
    combined = masks * weights
    denominator = torch.sum(combined)
    if float(denominator.detach().cpu()) <= 0:
        raise ContextIsolationError("no eligible training supervision")
    return torch.sum(loss * combined) / denominator


def _validation_loss(model: nn.Module, records: Sequence[ContextRecord], samples: int, scaler: Mapping[str, Any]) -> float:
    model.eval()
    inputs = torch.from_numpy(_lane_matrix(records, samples, scaler))
    labels, masks = _labels(records)
    with torch.no_grad():
        logits = model(inputs)
        loss = nn.functional.binary_cross_entropy_with_logits(logits, torch.from_numpy(labels), reduction="none")
    active = torch.from_numpy(masks)
    if float(torch.sum(active)) <= 0:
        raise ContextIsolationError("D1 DEV validation contains no eligible breathing supervision")
    return float(torch.sum(loss * active) / torch.sum(active))


def _train_one(
    lane_id: str,
    samples: int,
    seed: int,
    train_records: Sequence[ContextRecord],
    validation_records: Sequence[ContextRecord],
    scaler: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[ParityTraceCNN, dict[str, Any]]:
    optimization = contract["shared_controls"]["optimization"]
    source_weights = contract["shared_controls"]["loss"]["source_weights"]
    deterministic = _set_deterministic(seed)
    model = ParityTraceCNN()
    if _parameter_count(model) != int(contract["shared_controls"]["architecture"]["parameter_count_expected"]):
        raise ContextIsolationError("architecture parameter count changed")
    inputs = torch.from_numpy(_lane_matrix(train_records, samples, scaler))
    labels_np, masks_np = _labels(train_records)
    labels = torch.from_numpy(labels_np)
    masks = torch.from_numpy(masks_np)
    weights = torch.from_numpy(_sample_weights(train_records, source_weights))
    optimizer = torch.optim.Adam(model.parameters(), lr=float(optimization["learning_rate"]), weight_decay=float(optimization["weight_decay"]))
    max_epochs = int(optimization["max_epochs"])
    early = optimization["early_stopping"]
    min_epochs, patience, epsilon = int(early["min_epochs"]), int(early["patience"]), float(early["improvement_epsilon"])
    batch_size = int(optimization["batch_size"])
    clip_norm = float(optimization["gradient_clip_norm"])
    history: list[dict[str, float]] = []
    best_loss, best_epoch, stale = float("inf"), 0, 0
    best_state: dict[str, torch.Tensor] | None = None
    for epoch in range(1, max_epochs + 1):
        model.train()
        generator = torch.Generator(device="cpu")
        generator.manual_seed(seed * 1000 + epoch)
        order = torch.randperm(inputs.shape[0], generator=generator)
        batches: list[float] = []
        for start in range(0, inputs.shape[0], batch_size):
            index = order[start:start + batch_size]
            optimizer.zero_grad(set_to_none=True)
            loss = _masked_bce(model(inputs[index]), labels[index], masks[index], weights[index])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), clip_norm)
            optimizer.step()
            batches.append(float(loss.detach().cpu()))
        val_loss = _validation_loss(model, validation_records, samples, scaler)
        history.append({"epoch": float(epoch), "train_loss": float(statistics.fmean(batches)), "validation_loss": val_loss})
        if val_loss < best_loss - epsilon:
            best_loss, best_epoch, stale = val_loss, epoch, 0
            best_state = {name: parameter.detach().cpu().clone() for name, parameter in model.state_dict().items()}
        else:
            stale += 1
        if epoch >= min_epochs and stale >= patience:
            break
    if best_state is None or not math.isfinite(best_loss):
        raise ContextIsolationError(f"training failed for {lane_id}/{seed}")
    model.load_state_dict(best_state)
    return model, {
        "lane_id": lane_id,
        "seed": seed,
        "best_epoch": best_epoch,
        "epochs_run": len(history),
        "best_validation_loss": best_loss,
        "last_validation_loss": float(history[-1]["validation_loss"]),
        "parameter_count": _parameter_count(model),
        "determinism": deterministic,
        "history": history,
    }


def _predict(model: nn.Module, records: Sequence[ContextRecord], samples: int, scaler: Mapping[str, Any]) -> np.ndarray:
    if not records:
        return np.zeros(0, dtype=np.float64)
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(torch.from_numpy(_lane_matrix(records, samples, scaler)))).cpu().numpy()
    if not np.all(np.isfinite(scores)):
        raise ContextIsolationError("non-finite probabilistic output")
    return np.asarray(scores, dtype=np.float64)


def _safe_divide(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else float(numerator / denominator)


def _breathing_metrics(records: Sequence[ContextRecord], scores: np.ndarray, threshold: float) -> dict[str, Any]:
    if len(records) != len(scores):
        raise ContextIsolationError("prediction/record count mismatch")
    active = np.asarray([row.breathing_mask > 0 for row in records], dtype=bool)
    labels = np.asarray([int(row.breathing_label) for row in records], dtype=np.int64)
    predictions = scores >= threshold
    y, p = labels[active], predictions[active]
    tp, tn = int(np.sum((y == 1) & (p == 1))), int(np.sum((y == 0) & (p == 0)))
    fp, fn = int(np.sum((y == 0) & (p == 1))), int(np.sum((y == 1) & (p == 0)))
    precision = _safe_divide(tp, tp + fp)
    present_recall, absent_recall = _safe_divide(tp, tp + fn), _safe_divide(tn, tn + fp)
    present_f1 = _safe_divide(2 * tp, 2 * tp + fp + fn)
    absent_f1 = _safe_divide(2 * tn, 2 * tn + fn + fp)
    if not np.any(y == 0):
        absent_recall, absent_f1 = None, None
    brier = float(np.mean((scores[active] - y) ** 2)) if y.size else None
    return {
        "status": "DEFINED" if y.size else "UNDEFINED_NO_VALID_SUPERVISION",
        "threshold_fixed_before_training": threshold,
        "record_count": len(records),
        "supervision_eligible_count": int(y.size),
        "present_count": int(np.sum(y == 1)),
        "absent_count": int(np.sum(y == 0)),
        "ambiguous_count": int(sum(row.breathing_state == AMBIGUOUS for row in records)),
        "target_unavailable_count": int(sum(row.breathing_state == TARGET_UNAVAILABLE for row in records)),
        "ambiguous_handling": "EXCLUDED_FROM_LOSS_AND_PURE_CLASS_METRICS_NO_LABEL_REWRITE",
        "confusion": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "present_recall": present_recall,
        "absent_recall": absent_recall,
        "precision": precision,
        "f1": present_f1,
        "present_f1": present_f1,
        "absent_f1": absent_f1,
        "brier": brier,
    }


def _summary(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in keys:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        result[key] = {
            "n": len(values),
            "mean": float(statistics.fmean(values)) if values else None,
            "std": float(statistics.pstdev(values)) if len(values) > 1 else (0.0 if values else None),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return result


def _subject_metrics(records: Sequence[ContextRecord], scores: np.ndarray, threshold: float, lane_id: str, seed: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for subject_id in sorted({row.subject_id for row in records}):
        positions = [index for index, row in enumerate(records) if row.subject_id == subject_id]
        subset = [records[index] for index in positions]
        result.append({
            "lane_id": lane_id,
            "seed": seed,
            "subject_id": subject_id,
            "recording_ids": sorted({row.recording_id for row in subset}),
            "metrics": _breathing_metrics(subset, scores[np.asarray(positions, dtype=np.int64)], threshold),
        })
    return result


def _prediction_sha(scores: np.ndarray) -> str:
    digest = hashlib.sha256()
    values = np.asarray(scores, dtype=np.float32)
    digest.update(np.asarray(values.shape, dtype=np.int64).tobytes())
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _save_checkpoint(model: nn.Module, lane_id: str, seed: int, metadata: Mapping[str, Any]) -> dict[str, Any]:
    relative = MODEL_ROOT_REL / lane_id.lower() / f"seed_{seed}.pt"
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "identity": "MMWAVE_V2_M_PV35_CONTROLLED_CONTEXT_ISOLATION_V1",
        "lane_id": lane_id,
        "seed": seed,
        "state_dict": {name: value.detach().cpu() for name, value in model.state_dict().items()},
        "metadata": dict(metadata),
        "selection_status": "EVALUATION_ONLY_NOT_SELECTED",
        "optimizer_state": None,
    }, path)
    return {"path": relative.as_posix(), "sha256": _sha256_file(path), "bytes": int(path.stat().st_size)}


def _conv_output_length(length: int, kernel: int, stride: int) -> int:
    return (length - kernel) // stride + 1


def _footprint(samples: int, parameter_count: int) -> dict[str, Any]:
    l1 = _conv_output_length(samples, 5, 2)
    l2 = _conv_output_length(l1, 5, 2)
    l3 = _conv_output_length(l2, 3, 2)
    conv_macs = l1 * 8 * 1 * 5 + l2 * 16 * 8 * 5 + l3 * 24 * 16 * 3
    dense_macs = 24 * 16 + 16
    pool_adds = max(l3 - 1, 0) * 24
    macs = int(conv_macs + dense_macs)
    tensor_bytes = samples * 4
    return {
        "parameter_count": parameter_count,
        "parameter_bytes_float32": parameter_count * 4,
        "input_tensor_shape": f"[1,{samples},1]",
        "input_tensor_bytes_float32": tensor_bytes,
        "conv_output_lengths": [l1, l2, l3],
        "estimated_macs_per_inference": macs,
        "adaptive_pool_additions_excluded_from_mac_count": int(pool_adds),
        "estimated_flops_from_macs_only": int(2 * macs),
        "hardware_speed_measured": False,
        "raspberry_pi_speed_claim": False,
    }


def _cycle_table() -> dict[str, Any]:
    rows = []
    for bpm in (6, 8, 12, 20):
        rows.append({
            "rr_bpm": bpm,
            "cycles_in_15s": bpm * 15.0 / 60.0,
            "cycles_in_30s": bpm * 30.0 / 60.0,
        })
    return {
        "rows": rows,
        "frequency_resolution": {
            "15s_delta_f_hz": 1.0 / 15.0,
            "30s_delta_f_hz": 1.0 / 30.0,
            "15s_delta_f_bpm_equivalent": 60.0 / 15.0,
            "30s_delta_f_bpm_equivalent": 60.0 / 30.0,
        },
        "interpretation": "ENGINEERING_CONTEXT_ONLY_NOT_A_PROOF_OF_BREATHING_ACCURACY",
    }


def _recovery_q2_audit() -> dict[str, Any]:
    lanes: dict[str, Any] = {}
    for lane_id, seconds, _ in LANES:
        modes = []
        for mode in ("SOURCE_FREEZE", "LARGE_GAP", "STALE_SOURCE"):
            modes.append({
                "mode": mode,
                "synthetic_q2_only": True,
                "context_refill_time_s": seconds,
                "first_valid_inference_time_s": seconds,
                "invalid_application_state": "INPUT_UNAVAILABLE",
                "model_invocation_when_invalid": "BLOCKED",
                "invalid_emitted_as_present": False,
                "invalid_emitted_as_absent": False,
                "invalid_emitted_as_normal": False,
                "invalid_emitted_as_apnea": False,
                "real_mr60_latency_measured": False,
            })
        lanes[lane_id] = modes
    return {
        "profile": "SYNTHETIC_Q2_INPUT_UNAVAILABLE_ONLY",
        "lanes": lanes,
        "comparison": {
            "context_refill_difference_s_30_minus_15": 15,
            "first_valid_inference_difference_s_30_minus_15": 15,
        },
        "not_a_real_sensor_latency_measurement": True,
    }


def _lineage_rows(records: Sequence[ContextRecord]) -> list[dict[str, Any]]:
    rows = []
    for row in records:
        rows.append({
            "source_id": row.source_id,
            "subject_id": row.subject_id,
            "recording_id": row.recording_id,
            "model_input_id": row.model_input_id,
            "split": row.split,
            "breathing_state": row.breathing_state,
            "breathing_supervision_eligible": row.breathing_mask > 0,
            "quality_status": row.quality_status,
            "base_context_interval_s": [row.provenance["context_start_s"], row.provenance["context_end_s"]],
            "target_interval_s": [row.provenance["target_start_s"], row.provenance["target_end_s"]],
            "context_15s_interval": "[t-15s,t] tail 150 of accepted 300 samples",
            "context_30s_interval": "[t-30s,t] accepted 300 samples",
            "r1_profile": row.provenance["r1_profile"],
            "r2_profile": row.provenance["r2_profile"],
            "synthetic": False,
        })
    return rows


def _checksums() -> dict[str, str]:
    roots = (ROOT / OUTPUT_REL, ROOT / MODEL_ROOT_REL)
    skip = {"checksums.json", "checksums.sha256"}
    result: dict[str, str] = {}
    for root in roots:
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.name not in skip:
                    result[_relative(path)] = _sha256_file(path)
    return result


def refresh_checksums() -> dict[str, Any]:
    output = ROOT / OUTPUT_REL
    checksums = _checksums()
    payload = {"schema_version": "M-PV3.5.1", "files": checksums}
    _write_json(output / "checksums.json", payload)
    lines = [f"{digest}  {name}" for name, digest in checksums.items()]
    (output / "checksums.sha256").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return payload


def run() -> dict[str, Any]:
    contract = _read_json(ROOT / CONTRACT_REL)
    if contract.get("contract_id") != "MMWAVE_V2_M_PV35_CONTROLLED_CONTEXT_ISOLATION_V1" or contract.get("frozen_before_training") is not True:
        raise ContextIsolationError("M-PV3.5 contract is absent or not frozen")
    if tuple(contract["shared_controls"]["optimization"]["seeds"]) != SEEDS:
        raise ContextIsolationError("seed contract changed")
    if tuple((lane["lane_id"], lane["context_seconds"], lane["sample_count"]) for lane in contract["lanes"]) != LANES:
        raise ContextIsolationError("lane context contract changed")
    m_pv1_validation = _read_json(ROOT / M_PV1_VALIDATION_REL)
    d2_lock = _read_json(ROOT / M_PV1_D2_LOCK_REL)
    if m_pv1_validation.get("ok") is not True or d2_lock.get("semantic_access") not in (False, "NO"):
        raise ContextIsolationError("M-PV1 prerequisite or D2 lock is invalid")

    records, accounting = _load_records()
    train, dev, d0_observe = _group(records, "TRAIN"), _group(records, "D1_DEV_VAL"), _group(records, "D0_TRAIN_OBSERVE")
    if len(train) != 503 or len(dev) != 59 or len(d0_observe) != 318:
        raise ContextIsolationError(f"unexpected train/dev accounting: {len(train)}/{len(dev)}/{len(d0_observe)}")
    train_subjects = {row.subject_id for row in train if row.source_id == "D1"}
    dev_subjects = {row.subject_id for row in dev}
    if train_subjects & dev_subjects:
        raise ContextIsolationError("D1 DEV subject leakage detected")
    scaler = _fit_common_scaler(train)
    threshold = float(contract["shared_controls"]["loss"]["threshold_fixed_before_training"])
    output = ROOT / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)

    controls = {
        "identity": contract["contract_id"],
        "contract_path": CONTRACT_REL.as_posix(),
        "contract_sha256": _sha256_file(ROOT / CONTRACT_REL),
        "only_variable": "context_duration_and_corresponding_input_tensor_length",
        "identical_controls": contract["shared_controls"],
        "parameter_count_expected": contract["shared_controls"]["architecture"]["parameter_count_expected"],
        "no_model_selection": True,
        "no_threshold_tuning": True,
        "no_d2_semantic_access": True,
        "no_mr60_supervised_physiology": True,
    }
    _write_json(output / "experimental_controls.json", controls)
    _write_json(output / "common_scaler.json", scaler)
    lineage = _lineage_rows(records)
    _write_json(output / "dataset_accounting.json", {
        "identity": contract["contract_id"],
        "counts": accounting,
        "train_context_count": len(train),
        "d1_dev_val_context_count": len(dev),
        "d1_train_subject_count": len(train_subjects),
        "d1_dev_val_subject_count": len(dev_subjects),
        "d1_subject_intersection_count": len(train_subjects & dev_subjects),
        "d0_val_used": False,
        "d0_subject_heldout_used": False,
        "d2_rows": 0,
        "d2_semantic_access": False,
        "mr60_supervised_physiology_used": False,
        "new_labels_created": False,
        "target_regenerated": False,
        "lineage": lineage,
        "lineage_sha256": _sha256_json(lineage),
    })

    per_lane: dict[str, Any] = {}
    subject_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    parameter_counts: list[int] = []
    for lane_id, seconds, samples in LANES:
        seed_rows = []
        for seed in SEEDS:
            model, training = _train_one(lane_id, samples, seed, train, dev, scaler, contract)
            dev_scores = _predict(model, dev, samples, scaler)
            d0_scores = _predict(model, d0_observe, samples, scaler)
            dev_metrics = _breathing_metrics(dev, dev_scores, threshold)
            d0_metrics = _breathing_metrics(d0_observe, d0_scores, threshold)
            training_compact = {key: value for key, value in training.items() if key != "history"}
            checkpoint = _save_checkpoint(model, lane_id, seed, {
                "contract_sha256": controls["contract_sha256"],
                "common_scaler_sha256": scaler["sha256"],
                "training": training_compact,
                "input_shape": f"[B,{samples},1]",
                "target_interval": "[t-5s,t]",
            })
            parameter_counts.append(training["parameter_count"])
            checkpoint_rows.append({"lane_id": lane_id, "seed": seed, **checkpoint})
            subject_rows.extend(_subject_metrics(dev, dev_scores, threshold, lane_id, seed))
            seed_rows.append({
                "seed": seed,
                "training": training,
                "dev_metrics": dev_metrics,
                "d0_train_observe_metrics": d0_metrics,
                "dev_prediction_sha256": _prediction_sha(dev_scores),
                "d0_train_observe_prediction_sha256": _prediction_sha(d0_scores),
                "checkpoint": checkpoint,
            })
        per_lane[lane_id] = {
            "context_seconds": seconds,
            "input_shape": f"[B,{samples},1]",
            "seed_results": seed_rows,
            "seed_stability_dev": _summary(
                [row["dev_metrics"] for row in seed_rows],
                ("present_recall", "absent_recall", "precision", "f1", "brier"),
            ),
            "footprint": _footprint(samples, parameter_counts[-1]),
        }
    if len(set(parameter_counts)) != 1 or parameter_counts[0] != int(contract["shared_controls"]["architecture"]["parameter_count_expected"]):
        raise ContextIsolationError(f"architecture parity failed: {parameter_counts}")

    _write_json(output / "checkpoint_registry.json", {
        "identity": contract["contract_id"],
        "selection_status": "NO_SELECTION_EVALUATION_ONLY",
        "checkpoints": checkpoint_rows,
    })
    _write_json(output / "subject_metrics.json", {
        "identity": contract["contract_id"],
        "evaluation_group": "D1_DEV_VAL_SUBJECT_DISJOINT",
        "rows": subject_rows,
        "subject_metric_policy": "per_seed_per_subject; unavailable class metrics remain null",
    })
    _write_json(output / "cycle_count_analysis.json", _cycle_table())
    _write_json(output / "recovery_q2_audit.json", _recovery_q2_audit())
    _write_json(output / "footprint_comparison.json", {
        "identity": contract["contract_id"],
        "parameter_count_identical": True,
        "lanes": {lane: payload["footprint"] for lane, payload in per_lane.items()},
        "interpretation": "operation_and_memory_estimates_only_not_a_hardware_benchmark",
    })
    _write_json(output / "evaluation_result.json", {
        "identity": contract["contract_id"],
        "phase": "M-PV3.5",
        "purpose": "CONTROLLED_CONTEXT_DURATION_ISOLATION_ONLY",
        "lanes": per_lane,
        "comparison": {
            "parameter_count_identical": True,
            "common_scaler_sha256": scaler["sha256"],
            "same_target_interval": "[t-5s,t]",
            "same_optimizer_loss_seeds_and_early_stopping_rule": True,
            "combined_score_created": False,
            "selection_created": False,
        },
        "limitations": [
            "D1_DEV_VAL contains no model-ready ABSENT context, so ABSENT recall is undefined there.",
            "D0 TRAIN metrics are observe-only and are not a held-out performance claim.",
            "This controlled comparison is limited to the governed public M-PV1 membership.",
            "Q2 recovery values are synthetic timing/accounting diagnostics, not real MR60 latency.",
            "Frequency-resolution and cycle-count values are engineering interpretation only and do not prove accuracy.",
            "No production model selection, calibration, threshold tuning, TFLite/INT8 artifact, Pi benchmark, or clinical claim was made.",
        ],
        "final_gate": "PASS_WITH_LIMITATIONS",
        "final_statement": "controlled comparison completed",
        "selected_model": None,
        "m_pv4_approved": False,
    })
    _write_json(output / "decision.json", {
        "identity": contract["contract_id"],
        "gate": "PASS_WITH_LIMITATIONS",
        "statement": "controlled comparison completed",
        "selection_result": "NOT_APPLICABLE_NO_MODEL_SELECTION",
        "selected_model": None,
        "m_pv4_approved": False,
        "threshold_tuning": False,
        "calibration": False,
        "tflite_or_int8": False,
    })
    _write_json(output / "provenance_and_safety_audit.json", {
        "identity": contract["contract_id"],
        "d2_lock": {key: d2_lock.get(key) for key in ("semantic_access", "feature_extraction", "target_use", "model_inference_count", "selection")},
        "d2_semantic_access": False,
        "mr60_supervised_physiology": False,
        "target_rewritten": False,
        "apnea_strings_used_as_labels": False,
        "breath_hold_names_used_as_labels": False,
        "radar_amplitude_used_as_labels": False,
        "q2_fail_closed": True,
        "invalid_input_application_state": "INPUT_UNAVAILABLE",
        "invalid_input_does_not_emit": ["PRESENT", "ABSENT", "NORMAL", "APNEA"],
        "quality_gate_modified": False,
    })
    _write_json(output / "run_metadata.json", {
        "identity": contract["contract_id"],
        "source_git_head": _git_head(),
        "contract_sha256": controls["contract_sha256"],
        "common_scaler_sha256": scaler["sha256"],
        "generated_payloads_are_deterministic_under_recorded_cpu_settings": True,
        "checkpoint_parameter_counts": parameter_counts,
    })
    refresh_checksums()
    return {"phase": "M-PV3.5", "gate": "PASS_WITH_LIMITATIONS", "output": OUTPUT_REL.as_posix(), "selected_model": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-checksums", action="store_true", help="refresh checksums for an existing M-PV3.5 evidence directory")
    args = parser.parse_args()
    try:
        result = refresh_checksums() if args.refresh_checksums else run()
    except ContextIsolationError as exc:
        print(f"M-PV3.5 FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
