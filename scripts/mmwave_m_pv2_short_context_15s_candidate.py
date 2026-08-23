#!/usr/bin/env python3
"""Build the bounded SafeNest mmWave M-PV2 15-second breathing candidate.

This is an experimental ablation lane.  It reads the frozen M-PV1 model-ready
membership and the accepted R1 traces, derives the final 150 samples of each
30-second causal context, trains only a small breathing-evidence CNN, and
writes compact evidence under a new manifest directory.  The existing
30-second M-PV2 lane is read-only and is used only as a descriptive baseline.

The script intentionally does not:

* reconstruct D0 VAL, D0_SUBJECT_HELDOUT, D2, or MR60 physiology labels;
* train RR or temporal-hold heads;
* turn ambiguous, apnea-protocol, breath-hold, amplitude, or model-output
  information into physiological labels;
* modify the existing M-PV2 30-second artifacts or runtime contracts.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - the focused validator reports this
    raise SystemExit("M-PV2 short candidate requires torch") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_REL = Path("datasets/mmwave/manifests/M-PV2_short_context_15s_candidate")
MODEL_ROOT_REL = Path("models/mmwave/m_pv2_short_context_15s_candidate")
M_PV1_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/m_pv2_example_manifest.json")
M_PV1_VALIDATION_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/validation_result.json")
M_PV1_D1_SPLIT_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/d1_subject_split.json")
M_PV1_QUALITY_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/quality_abstention_contract.json")
D0_SPLIT_REL = Path("datasets/mmwave/splits/mmwave_v2_d0_subject_split_v1.json")
BASELINE_ROOT_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training")
BASELINE_BREATHING_REL = BASELINE_ROOT_REL / "breathing_metrics.json"
BASELINE_REGISTRY_REL = BASELINE_ROOT_REL / "candidate_registry.json"
BASELINE_MODEL_ROOT_REL = Path("models/mmwave/m_pv2")

SEEDS = (11, 23, 47)
SAMPLE_RATE_HZ = 10
SHORT_SECONDS = 15
SHORT_SAMPLES = 150
BASE_SECONDS = 30
BASE_SAMPLES = 300
TARGET_SECONDS = 5
TARGET_START_SAMPLE = SHORT_SAMPLES - TARGET_SECONDS * SAMPLE_RATE_HZ
TARGET_END_SAMPLE = SHORT_SAMPLES
THRESHOLD = 0.5

PRESENT = "BREATHING_REFERENCE_PRESENT"
ABSENT = "BREATHING_REFERENCE_ABSENT"
AMBIGUOUS = "BREATHING_REFERENCE_AMBIGUOUS"
TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"

STATE_TO_LABEL = {PRESENT: 1.0, ABSENT: 0.0, AMBIGUOUS: 0.0}
SOURCE_WEIGHTS = {"D0": 0.75, "D1": 0.25}


class ShortCandidateError(RuntimeError):
    """Fail-closed short-candidate input or evidence error."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShortCandidateError(f"failed to read JSON {path}: {exc}") from exc


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


def _relative_file_hashes(root: Path) -> Dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(ROOT).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _protected_artifact_hashes() -> Dict[str, str]:
    """Snapshot the 30-second lane and its compact model files for immutability."""

    protected: Dict[str, str] = {}
    for relative in (
        BASELINE_BREATHING_REL,
        BASELINE_REGISTRY_REL,
        BASELINE_ROOT_REL / "tensor_materialization_audit.json",
        BASELINE_ROOT_REL / "scaler_statistics.json",
        BASELINE_ROOT_REL / "validation_result.json",
    ):
        path = ROOT / relative
        if path.is_file():
            protected[relative.as_posix()] = _sha256_file(path)
    protected.update(_relative_file_hashes(ROOT / BASELINE_MODEL_ROOT_REL))
    return dict(sorted(protected.items()))


@dataclasses.dataclass
class ShortRecord:
    source_id: str
    subject_id: str
    recording_id: str
    model_input_id: str
    split: str
    trace: np.ndarray
    trace_mask: np.ndarray
    breathing_state: str
    breathing_label: float
    breathing_mask: float
    quality_status: str
    rr_bpm: Optional[float]
    provenance: Dict[str, Any]


def _load_short_records() -> Tuple[List[ShortRecord], Dict[str, Any]]:
    """Derive [t-15s,t] from accepted M-PV1/R1 rows without new labels."""

    from scripts.mmwave_m_pv2_candidate_training import _load_materialized_records

    manifest = _read_json(ROOT / M_PV1_REL)
    rows = {
        str(row.get("model_input_id")): row
        for row in manifest.get("examples", [])
        if row.get("model_ready") is True
    }
    base_records, source_scope = _load_materialized_records()
    records: List[ShortRecord] = []
    for base in sorted(base_records, key=lambda item: item.model_input_id):
        if base.model_input_id not in rows:
            raise ShortCandidateError(f"M-PV1 row missing for {base.model_input_id}")
        row = rows[base.model_input_id]
        source = str(row.get("source_id"))
        split = str(row.get("split"))
        if source == "D0" and split != "TRAIN":
            raise ShortCandidateError(f"forbidden D0 split selected: {split}")
        if source == "D1" and split not in {"D1_DEV_TRAIN", "D1_DEV_VAL"}:
            raise ShortCandidateError(f"forbidden D1 split selected: {split}")
        if source not in {"D0", "D1"}:
            raise ShortCandidateError(f"unexpected source selected: {source}")
        if base.trace.shape != (BASE_SAMPLES,):
            raise ShortCandidateError(
                f"expected accepted 30-second trace for {base.model_input_id}: {base.trace.shape}"
            )

        target_state = str(row.get("breathing_reference_state"))
        if target_state not in {PRESENT, ABSENT, AMBIGUOUS}:
            raise ShortCandidateError(
                f"unexpected inherited breathing state for {base.model_input_id}: {target_state}"
            )
        if bool(row.get("breathing_supervision_eligible")) != (target_state != AMBIGUOUS):
            raise ShortCandidateError(
                f"breathing eligibility/state mismatch for {base.model_input_id}"
            )

        source_provenance = row.get("provenance")
        if not isinstance(source_provenance, Mapping):
            raise ShortCandidateError(f"missing source provenance for {base.model_input_id}")
        context_start = float(row.get("context_start_s"))
        context_end = float(row.get("context_end_s"))
        target_start = float(row.get("target_start_s"))
        target_end = float(row.get("target_end_s"))
        if (
            abs((context_end - context_start) - BASE_SECONDS) > 1e-6
            or abs((target_end - target_start) - TARGET_SECONDS) > 1e-6
            or abs(target_end - context_end) > 1e-6
        ):
            raise ShortCandidateError(
                f"unexpected base timing for {base.model_input_id}: "
                f"context=({context_start},{context_end}) target=({target_start},{target_end})"
            )
        short_start = context_end - SHORT_SECONDS
        short_end = context_end
        local_target_start = target_start - short_start
        local_target_end = target_end - short_start
        if abs(local_target_start - TARGET_START_SAMPLE / SAMPLE_RATE_HZ) > 1e-6:
            raise ShortCandidateError(f"short target start mismatch for {base.model_input_id}")
        if abs(local_target_end - SHORT_SECONDS) > 1e-6:
            raise ShortCandidateError(f"short target end mismatch for {base.model_input_id}")

        trace = np.asarray(base.trace[-SHORT_SAMPLES:], dtype=np.float32)
        trace_mask = np.asarray(base.trace_mask[-SHORT_SAMPLES:], dtype=bool)
        if trace.shape != (SHORT_SAMPLES,) or trace_mask.shape != (SHORT_SAMPLES,):
            raise ShortCandidateError(f"short tensor derivation failed for {base.model_input_id}")
        if not np.all(np.isfinite(trace)):
            raise ShortCandidateError(f"non-finite clean short trace for {base.model_input_id}")

        breathing_label = STATE_TO_LABEL[target_state]
        breathing_mask = 1.0 if target_state in {PRESENT, ABSENT} else 0.0
        rr_value = row.get("rr_bpm")
        rr_bpm = float(rr_value) if rr_value is not None else None
        lineage = {
            "source_id": source,
            "source_dataset": source_provenance.get("source_dataset"),
            "source_file": source_provenance.get("source_file"),
            "subject_id": str(row.get("subject_id")),
            "recording_id": str(row.get("recording_id")),
            "window_id": source_provenance.get("window_id", row.get("window_id")),
            "model_input_id": str(row.get("model_input_id")),
            "split": split,
            "reference_method": source_provenance.get("reference_method"),
            "dataset_version": source_provenance.get("dataset_version"),
            "base_context_interval_s": [context_start, context_end],
            "short_context_interval_s": [short_start, short_end],
            "base_target_interval_s": [target_start, target_end],
            "short_target_interval_s": [local_target_start, local_target_end],
            "short_target_sample_range": [TARGET_START_SAMPLE, TARGET_END_SAMPLE],
            "target_anchor": str(row.get("target_anchor")),
            "breathing_reference_state": target_state,
            "breathing_supervision_eligible": bool(
                row.get("breathing_supervision_eligible")
            ),
            "quality_status": str(row.get("quality_status")),
            "rr_target_status": str(row.get("rr_target_status")),
            "rr_supervision_eligible": bool(row.get("rr_supervision_eligible")),
            "rr_use": "METADATA_ONLY_NOT_TRAINED_NOT_EVALUATED",
            "clinical_apnea_claimed": bool(
                source_provenance.get("clinical_apnea_claimed", False)
            ),
            "r1_profile": "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1",
            "r2_profile": "MMWAVE_V2_R2_F2_SPECTRAL_AUTOCORR_V1",
            "short_context_derivation": (
                "accepted M-PV1/R1 30-second trace; tail samples "
                "150:300; no re-alignment; no future samples"
            ),
            "label_source": "M-PV1.breathing_reference_state",
            "label_from_radar_amplitude": False,
            "label_from_apnea_protocol_string": False,
            "label_from_breath_hold_name": False,
            "label_from_model_output": False,
            "synthetic": False,
        }
        records.append(
            ShortRecord(
                source_id=source,
                subject_id=str(row.get("subject_id")),
                recording_id=str(row.get("recording_id")),
                model_input_id=str(row.get("model_input_id")),
                split=split,
                trace=trace,
                trace_mask=trace_mask,
                breathing_state=target_state,
                breathing_label=breathing_label,
                breathing_mask=breathing_mask,
                quality_status=str(row.get("quality_status")),
                rr_bpm=rr_bpm,
                provenance=lineage,
            )
        )

    if len(records) != 562:
        raise ShortCandidateError(f"short membership changed: {len(records)}")
    counts = {
        "model_ready_unique": len(records),
        "by_source": {
            source: sum(record.source_id == source for record in records)
            for source in ("D0", "D1")
        },
        "by_split": {
            split: sum(record.split == split for record in records)
            for split in sorted({record.split for record in records})
        },
        "by_state": {
            state: sum(record.breathing_state == state for record in records)
            for state in (PRESENT, ABSENT, AMBIGUOUS)
        },
        "breathing_supervision_eligible": int(
            sum(record.breathing_mask > 0 for record in records)
        ),
        "quality_clean": int(
            sum(record.quality_status == "CLEAN" for record in records)
        ),
    }
    if counts["by_source"] != {"D0": 318, "D1": 244}:
        raise ShortCandidateError(f"source membership changed: {counts['by_source']}")
    return records, {"counts": counts, "source_scope": source_scope}


def _record_group(records: Sequence[ShortRecord], name: str) -> List[ShortRecord]:
    if name == "TRAIN":
        return [
            record
            for record in records
            if (record.source_id == "D0" and record.split == "TRAIN")
            or (record.source_id == "D1" and record.split == "D1_DEV_TRAIN")
        ]
    if name == "D0_TRAIN":
        return [record for record in records if record.source_id == "D0"]
    if name == "D1_DEV_TRAIN":
        return [
            record
            for record in records
            if record.source_id == "D1" and record.split == "D1_DEV_TRAIN"
        ]
    if name == "D1_DEV_VAL":
        return [
            record
            for record in records
            if record.source_id == "D1" and record.split == "D1_DEV_VAL"
        ]
    raise ShortCandidateError(f"unknown record group: {name}")


def _fit_trace_scaler(train_records: Sequence[ShortRecord]) -> Dict[str, Any]:
    traces = np.concatenate([record.trace for record in train_records])
    mean = float(np.mean(traces))
    std = float(np.std(traces))
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 1e-8:
        raise ShortCandidateError("invalid TRAIN-only trace scaler")
    base = {
        "profile_id": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_TRACE_ZSCORE_TRAIN_ONLY_V1",
        "fit_scope": ["D0:TRAIN", "D1:D1_DEV_TRAIN"],
        "sample_count": int(traces.size),
        "window_count": len(train_records),
        "mean": mean,
        "std": std,
    }
    base["sha256"] = _sha256_json(base)
    return base


def _normalized_matrix(
    records: Sequence[ShortRecord], scaler: Mapping[str, Any]
) -> np.ndarray:
    values = np.stack([record.trace for record in records]).astype(np.float32)
    values = (values - float(scaler["mean"])) / float(scaler["std"])
    if not np.all(np.isfinite(values)):
        raise ShortCandidateError("non-finite normalized short input")
    return values[:, :, None]


def _set_deterministic(seed: int) -> Dict[str, Any]:
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
        "seed": int(seed),
        "deterministic_algorithms": deterministic,
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": int(torch.get_num_interop_threads()),
    }


class ShortBreathingCNN(nn.Module):
    """Small valid-convolution model with one binary breathing head."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(1, 8, kernel_size=5, stride=2, padding=0)
        self.conv2 = nn.Conv1d(8, 16, kernel_size=5, stride=2, padding=0)
        self.conv3 = nn.Conv1d(16, 24, kernel_size=3, stride=2, padding=0)
        self.fc = nn.Linear(24, 16)
        self.head = nn.Linear(16, 1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim != 3 or tuple(inputs.shape[1:]) != (SHORT_SAMPLES, 1):
            raise ValueError(
                f"expected [B,{SHORT_SAMPLES},1], got {tuple(inputs.shape)}"
            )
        values = inputs.transpose(1, 2)
        values = torch.relu(self.conv1(values))
        values = torch.relu(self.conv2(values))
        values = torch.relu(self.conv3(values))
        # The target is the fixed newest 5 seconds.  Pooling the newest
        # feature positions preserves that causal target location without
        # adding a temporal-history or event-position input.
        values = torch.mean(values[:, :, -5:], dim=2)
        values = torch.relu(self.fc(values))
        return self.head(values).squeeze(-1)


def _parameter_count(model: nn.Module) -> int:
    return int(sum(parameter.numel() for parameter in model.parameters()))


def _flops_estimate() -> Dict[str, Any]:
    """Return a deterministic multiply/add estimate for one [150,1] inference."""

    lengths = [
        (SHORT_SAMPLES - 5) // 2 + 1,
        (((SHORT_SAMPLES - 5) // 2 + 1) - 5) // 2 + 1,
    ]
    length3 = (lengths[1] - 3) // 2 + 1
    macs = (
        lengths[0] * 8 * 1 * 5
        + lengths[1] * 16 * 8 * 5
        + length3 * 24 * 16 * 3
        + 24 * 16
        + 16
    )
    flops = int(2 * macs)
    return {
        "conv_output_lengths": [int(lengths[0]), int(lengths[1]), int(length3)],
        "multiply_accumulates": int(macs),
        "estimated_flops": flops,
        "latency_estimate_ms_at_1_gflop_s": float(flops / 1_000_000.0),
        "latency_estimate_is_not_raspberry_pi_measurement": True,
    }


def _labels(records: Sequence[ShortRecord]) -> Tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(
        [record.breathing_label for record in records], dtype=np.float32
    )
    masks = np.asarray(
        [record.breathing_mask for record in records], dtype=np.float32
    )
    return labels, masks


def _sample_weights(records: Sequence[ShortRecord]) -> np.ndarray:
    eligible_counts: Dict[Tuple[str, str], int] = {}
    for record in records:
        if record.breathing_mask > 0:
            key = (record.source_id, record.subject_id)
            eligible_counts[key] = eligible_counts.get(key, 0) + 1
    base_weights: List[float] = []
    for record in records:
        if record.breathing_mask <= 0:
            base_weights.append(0.0)
            continue
        denominator = float(eligible_counts[(record.source_id, record.subject_id)])
        base_weights.append(SOURCE_WEIGHTS[record.source_id] / denominator)
    base_class_totals = {
        0: float(
            sum(
                weight
                for weight, record in zip(base_weights, records)
                if record.breathing_mask > 0 and record.breathing_label == 0.0
            )
        ),
        1: float(
            sum(
                weight
                for weight, record in zip(base_weights, records)
                if record.breathing_mask > 0 and record.breathing_label == 1.0
            )
        ),
    }
    total = base_class_totals[0] + base_class_totals[1]
    class_weights = {
        label: float(total / (2 * class_total))
        for label, class_total in base_class_totals.items()
        if class_total > 0
    }
    return np.asarray(
        [
            weight * class_weights[int(record.breathing_label)]
            if record.breathing_mask > 0
            else 0.0
            for weight, record in zip(base_weights, records)
        ],
        dtype=np.float32,
    )


def _masked_bce(
    logits: torch.Tensor, labels: torch.Tensor, masks: torch.Tensor, weights: torch.Tensor
) -> torch.Tensor:
    values = nn.functional.binary_cross_entropy_with_logits(
        logits, labels, reduction="none"
    )
    combined = masks * weights
    denominator = torch.sum(combined)
    if float(denominator.detach().cpu()) <= 0:
        raise ShortCandidateError("no valid breathing supervision in batch")
    return torch.sum(values * combined) / denominator


def _validation_loss(
    model: nn.Module, records: Sequence[ShortRecord], scaler: Mapping[str, Any]
) -> float:
    model.eval()
    values = torch.from_numpy(_normalized_matrix(records, scaler))
    labels, masks = _labels(records)
    with torch.no_grad():
        logits = model(values)
        active = torch.from_numpy(masks)
        if float(torch.sum(active)) <= 0:
            raise ShortCandidateError("D1_DEV_VAL has no breathing supervision")
        loss = nn.functional.binary_cross_entropy_with_logits(
            logits, torch.from_numpy(labels), reduction="none"
        )
        return float(torch.sum(loss * active) / torch.sum(active))


def _train_one(
    seed: int,
    train_records: Sequence[ShortRecord],
    validation_records: Sequence[ShortRecord],
    scaler: Mapping[str, Any],
    training_config: Mapping[str, Any],
) -> Tuple[ShortBreathingCNN, Dict[str, Any]]:
    deterministic = _set_deterministic(seed)
    model = ShortBreathingCNN()
    inputs = torch.from_numpy(_normalized_matrix(train_records, scaler))
    labels_np, masks_np = _labels(train_records)
    weights_np = _sample_weights(train_records)
    labels = torch.from_numpy(labels_np)
    masks = torch.from_numpy(masks_np)
    weights = torch.from_numpy(weights_np)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(training_config["optimizer"]["learning_rate"]),
        weight_decay=float(training_config["optimizer"]["weight_decay"]),
    )
    max_epochs = int(training_config["optimizer"]["max_epochs"])
    min_epochs = int(training_config["optimizer"]["early_stopping"]["min_epochs"])
    patience = int(training_config["optimizer"]["early_stopping"]["patience"])
    clip_norm = float(training_config["optimizer"]["gradient_clip_norm"])
    best_loss = float("inf")
    best_epoch = 0
    stale_epochs = 0
    best_state: Optional[Dict[str, torch.Tensor]] = None
    history: List[Dict[str, float]] = []

    for epoch in range(1, max_epochs + 1):
        model.train()
        generator = torch.Generator(device="cpu")
        generator.manual_seed(seed * 1000 + epoch)
        order = torch.randperm(inputs.shape[0], generator=generator)
        batch_size = int(training_config["optimizer"]["batch_size"])
        batch_losses: List[float] = []
        for start in range(0, inputs.shape[0], batch_size):
            index = order[start : start + batch_size]
            optimizer.zero_grad(set_to_none=True)
            loss = _masked_bce(
                model(inputs[index]),
                labels[index],
                masks[index],
                weights[index],
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), clip_norm)
            optimizer.step()
            batch_losses.append(float(loss.detach().cpu()))
        validation_loss = _validation_loss(model, validation_records, scaler)
        history.append(
            {
                "epoch": float(epoch),
                "train_loss": float(statistics.fmean(batch_losses)),
                "validation_loss": validation_loss,
            }
        )
        if validation_loss < best_loss - 1e-10:
            best_loss = validation_loss
            best_epoch = epoch
            stale_epochs = 0
            best_state = {
                name: parameter.detach().cpu().clone()
                for name, parameter in model.state_dict().items()
            }
        else:
            stale_epochs += 1
        if epoch >= min_epochs and stale_epochs >= patience:
            break

    if best_state is None or not math.isfinite(best_loss):
        raise ShortCandidateError(f"training failed for seed {seed}")
    model.load_state_dict(best_state)
    return model, {
        "seed": int(seed),
        "best_epoch": int(best_epoch),
        "epochs_run": len(history),
        "best_validation_loss": float(best_loss),
        "last_validation_loss": float(history[-1]["validation_loss"]),
        "parameter_count": _parameter_count(model),
        "determinism": deterministic,
        "history": history,
    }


def _predict(
    model: nn.Module, records: Sequence[ShortRecord], scaler: Mapping[str, Any]
) -> np.ndarray:
    if not records:
        return np.zeros(0, dtype=np.float64)
    model.eval()
    values = torch.from_numpy(_normalized_matrix(records, scaler))
    with torch.no_grad():
        scores = torch.sigmoid(model(values)).cpu().numpy()
    if not np.all(np.isfinite(scores)):
        raise ShortCandidateError("non-finite breathing scores")
    return np.asarray(scores, dtype=np.float64)


def _safe_divide(numerator: float, denominator: float) -> Optional[float]:
    if denominator == 0:
        return None
    return float(numerator / denominator)


def _breathing_metrics(
    records: Sequence[ShortRecord], scores: np.ndarray
) -> Dict[str, Any]:
    if len(records) != len(scores):
        raise ShortCandidateError("prediction/record count mismatch")
    active = np.asarray([record.breathing_mask > 0 for record in records], dtype=bool)
    labels = np.asarray(
        [1 if record.breathing_state == PRESENT else 0 for record in records],
        dtype=np.int64,
    )
    predicted = scores >= THRESHOLD
    y = labels[active]
    p = predicted[active]
    tp = int(np.sum((y == 1) & (p == 1)))
    tn = int(np.sum((y == 0) & (p == 0)))
    fp = int(np.sum((y == 0) & (p == 1)))
    fn = int(np.sum((y == 1) & (p == 0)))
    present_recall = _safe_divide(tp, tp + fn)
    absent_recall = _safe_divide(tn, tn + fp)
    present_f1 = _safe_divide(2 * tp, 2 * tp + fp + fn)
    absent_f1 = _safe_divide(2 * tn, 2 * tn + fn + fp)
    has_both_classes = bool(np.any(y == 1) and np.any(y == 0))
    if not np.any(y == 0):
        absent_f1 = None
    f1_values = [value for value in (present_f1, absent_f1) if value is not None]
    macro_f1 = (
        float(statistics.fmean(f1_values))
        if len(f1_values) == 2 and y.size and has_both_classes
        else None
    )
    brier = float(np.mean((scores[active] - labels[active]) ** 2)) if y.size else None
    ambiguous_count = int(
        sum(record.breathing_state == AMBIGUOUS for record in records)
    )
    unavailable_count = int(
        sum(
            record.breathing_state == TARGET_UNAVAILABLE
            or record.quality_status == "INPUT_UNAVAILABLE"
            for record in records
        )
    )
    return {
        "status": "DEFINED" if y.size else "UNDEFINED_NO_VALID_SUPERVISION",
        "threshold": THRESHOLD,
        "record_count": len(records),
        "supervision_eligible_count": int(y.size),
        "present_count": int(np.sum(y == 1)),
        "absent_count": int(np.sum(y == 0)),
        "ambiguous_count": ambiguous_count,
        "target_unavailable_count": unavailable_count,
        "ambiguous_handling": "EXCLUDED_FROM_LOSS_AND_METRICS_NO_LABEL_REWRITE",
        "confusion": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "macro_f1": macro_f1,
        "present_recall": present_recall,
        "absent_recall": absent_recall,
        "present_f1": present_f1,
        "absent_f1": absent_f1,
        "brier": brier,
    }


def _save_checkpoint(
    model: ShortBreathingCNN, seed: int, metadata: Mapping[str, Any]
) -> Dict[str, Any]:
    directory = ROOT / MODEL_ROOT_REL
    directory.mkdir(parents=True, exist_ok=True)
    relative = MODEL_ROOT_REL / f"candidate_seed_{seed}.pt"
    path = ROOT / relative
    payload = {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "seed": int(seed),
        "state_dict": {
            name: value.detach().cpu() for name, value in model.state_dict().items()
        },
        "metadata": dict(metadata),
        "optimizer_state": None,
        "selection_status": "NOT_SELECTED",
    }
    torch.save(payload, path)
    return {
        "path": relative.as_posix(),
        "sha256": _sha256_file(path),
        "bytes": int(path.stat().st_size),
    }


def _aggregate_metric_rows(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    names = (
        "macro_f1",
        "present_recall",
        "absent_recall",
        "present_f1",
        "absent_f1",
        "brier",
    )
    result: Dict[str, Any] = {}
    for name in names:
        values = [
            float(row[name])
            for row in rows
            if row.get(name) is not None and math.isfinite(float(row[name]))
        ]
        result[name] = (
            {
                "n": len(values),
                "mean": float(statistics.fmean(values)),
                "std": float(np.std(values)),
                "min": float(min(values)),
                "max": float(max(values)),
            }
            if values
            else None
        )
    return result


def _baseline_metrics(records: Sequence[ShortRecord]) -> Dict[str, Any]:
    """Summarize the immutable breathing-capable 30-second M-PV2 lane."""

    stored = _read_json(ROOT / BASELINE_BREATHING_REL)
    baseline_keys = [
        key
        for key in sorted(stored)
        if key.startswith("family_b/") or key.startswith("family_c/")
    ]
    result: Dict[str, Any] = {
        "lane": "M-PV2_candidate_training",
        "context_duration_s": BASE_SECONDS,
        "input_samples": BASE_SAMPLES,
        "source_evidence": BASELINE_BREATHING_REL.as_posix(),
        "candidate_keys": baseline_keys,
        "selection_status": "NO_SELECTED_MODEL_IN_BASELINE_LANE",
        "selection_use": False,
        "groups": {},
    }
    for group in ("D0_TRAIN_OBSERVE", "D1_DEV_VAL"):
        rows: List[Dict[str, Any]] = []
        for key in baseline_keys:
            metric = stored[key].get(group)
            if not isinstance(metric, Mapping) or metric.get("status") != "DEFINED":
                continue
            confusion = metric.get("confusion", {})
            tp = float(confusion.get("TP", 0))
            tn = float(confusion.get("TN", 0))
            fp = float(confusion.get("FP", 0))
            fn = float(confusion.get("FN", 0))
            present_f1 = _safe_divide(2 * tp, 2 * tp + fp + fn)
            absent_f1 = _safe_divide(2 * tn, 2 * tn + fn + fp)
            if int(metric.get("absent_count", 0) or 0) == 0:
                absent_f1 = None
            rows.append(
                {
                    "candidate": key,
                    "macro_f1": (
                        float(statistics.fmean([present_f1, absent_f1]))
                        if present_f1 is not None and absent_f1 is not None
                        else None
                    ),
                    "present_recall": metric.get("recall"),
                    "absent_recall": _safe_divide(tn, tn + fp),
                    "present_f1": present_f1,
                    "absent_f1": absent_f1,
                    "brier": metric.get("Brier"),
                    "eligible_count": metric.get("eligible_count"),
                    "present_count": metric.get("present_count"),
                    "absent_count": metric.get("absent_count"),
                }
            )
        group_records = _record_group(records, "D0_TRAIN" if group.startswith("D0") else "D1_DEV_VAL")
        result["groups"][group] = {
            "per_candidate": rows,
            "aggregate": _aggregate_metric_rows(rows),
            "ambiguous_count_in_governed_membership": int(
                sum(record.breathing_state == AMBIGUOUS for record in group_records)
            ),
            "ambiguous_handling": "EXCLUDED_BY_FROZEN_M_PV2_TARGET_MASK",
        }
    return result


def _availability_scenario(context_seconds: int, mode: str) -> Dict[str, Any]:
    """Quality-only stream diagnostic with one one-second interruption."""

    stream_end = 120
    step = 1
    event_start = 40
    event_end = 41
    decision_times = list(range(0, stream_end + 1, step))
    available_times = [
        time for time in decision_times if time >= context_seconds
    ]
    unavailable_times = [
        time
        for time in available_times
        if event_start < time and event_end > (time - context_seconds)
    ]
    usable_times = [time for time in available_times if time not in unavailable_times]
    post_event = [
        time for time in usable_times if time > event_end
    ]
    recovery_time = (
        float(min(post_event) - event_end) if post_event else None
    )
    return {
        "mode": mode,
        "profile_id": "MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1",
        "synthetic_quality_only": True,
        "physiology_targets_created_or_rewritten": False,
        "presence_state": "PRESENT_ASSUMED_FOR_ORDERING_DIAGNOSTIC",
        "stream_duration_s": stream_end,
        "decision_step_s": step,
        "interruption_interval_s": [event_start, event_end],
        "context_requirement_s": context_seconds,
        "first_valid_decision_time_s": float(context_seconds),
        "decision_slots_after_context": len(available_times),
        "usable_prediction_count": len(usable_times),
        "input_unavailable_count": len(unavailable_times),
        "usable_prediction_ratio": float(
            len(usable_times) / len(available_times)
        ),
        "input_unavailable_ratio": float(
            len(unavailable_times) / len(available_times)
        ),
        "recovery_time_after_event_s": recovery_time,
        "runtime_order": [
            "presence",
            "input_availability",
            "breathing_evidence",
        ],
        "invalid_mapping": {
            "model_invocation": "BLOCKED",
            "application_state": "INPUT_UNAVAILABLE",
            "physiology_label": TARGET_UNAVAILABLE,
            "PRESENT_or_ABSENT_emitted": False,
        },
    }


def _availability_evidence() -> Dict[str, Any]:
    modes = {
        "gap": "LARGE_GAP",
        "freeze": "SOURCE_FREEZE",
        "stale_source": "STALE_SOURCE",
    }
    short = {
        mode: _availability_scenario(SHORT_SECONDS, q2_mode)
        for mode, q2_mode in modes.items()
    }
    baseline = {
        mode: _availability_scenario(BASE_SECONDS, q2_mode)
        for mode, q2_mode in modes.items()
    }
    return {
        "status": "SYNTHETIC_QUALITY_ONLY_DIAGNOSTIC",
        "short_context": short,
        "baseline_30s_context": baseline,
        "context_difference_s": BASE_SECONDS - SHORT_SECONDS,
        "recovery_difference_s_by_mode": {
            mode: float(
                baseline[mode]["recovery_time_after_event_s"]
                - short[mode]["recovery_time_after_event_s"]
            )
            for mode in modes
        },
        "real_sensor_recovery_measured": False,
        "threshold_tuning_on_corruption": False,
    }


def _dataset_audit(
    records: Sequence[ShortRecord],
    source_scope: Mapping[str, Any],
    protected_hashes: Mapping[str, str],
) -> Dict[str, Any]:
    d0_split = _read_json(ROOT / D0_SPLIT_REL)
    d1_split = _read_json(ROOT / M_PV1_D1_SPLIT_REL)
    d1_train_subjects = {
        record.subject_id
        for record in records
        if record.source_id == "D1" and record.split == "D1_DEV_TRAIN"
    }
    d1_val_subjects = {
        record.subject_id
        for record in records
        if record.source_id == "D1" and record.split == "D1_DEV_VAL"
    }
    lineage = [record.provenance for record in records]
    d0_subject_ids = d0_split.get("subject_ids", {})
    d0_val_subjects = set(d0_subject_ids.get("VAL", []))
    d0_heldout_subjects = set(d0_subject_ids.get("D0_SUBJECT_HELDOUT", []))
    d0_excluded_subjects = set(d0_split.get("excluded_subject_ids", []))
    selected_d0_subjects = {
        record.subject_id for record in records if record.source_id == "D0"
    }
    selected_d0_rows = [record for record in records if record.source_id == "D0"]
    d1_train_recordings = {
        record.recording_id
        for record in records
        if record.source_id == "D1" and record.split == "D1_DEV_TRAIN"
    }
    d1_val_recordings = {
        record.recording_id
        for record in records
        if record.source_id == "D1" and record.split == "D1_DEV_VAL"
    }
    target_end_matches = all(
        row["short_context_interval_s"][1] == row["base_target_interval_s"][1]
        and row["short_target_interval_s"][1] == SHORT_SECONDS
        for row in lineage
    )
    target_start_matches = all(
        row["short_target_sample_range"] == [TARGET_START_SAMPLE, TARGET_END_SAMPLE]
        for row in lineage
    )
    d0_rows = [record for record in records if record.source_id == "D0"]
    d1_rows = [record for record in records if record.source_id == "D1"]
    return {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "status": "PASS_WITH_LIMITATIONS",
        "source_membership": {
            "D0": {
                "selected_split": "TRAIN",
                "context_count": len(d0_rows),
                "subject_count": len({record.subject_id for record in d0_rows}),
                "expected_subject_count": 66,
                "expected_context_count": 318,
                "VAL_rows_selected": sum(
                    record.subject_id in d0_val_subjects
                    for record in selected_d0_rows
                ),
                "D0_SUBJECT_HELDOUT_rows_selected": sum(
                    record.subject_id in d0_heldout_subjects
                    for record in selected_d0_rows
                ),
                "M_N6_excluded_subjects_selected": sum(
                    record.subject_id in d0_excluded_subjects
                    for record in selected_d0_rows
                ),
                "selected_subjects_outside_frozen_train": len(
                    selected_d0_subjects
                    - set(d0_subject_ids.get("TRAIN", []))
                ),
                "split_identity": d0_split.get("split_identity"),
            },
            "D1": {
                "selected_splits": ["D1_DEV_TRAIN", "D1_DEV_VAL"],
                "context_count": len(d1_rows),
                "subject_count": len({record.subject_id for record in d1_rows}),
                "train_context_count": len(
                    [record for record in d1_rows if record.split == "D1_DEV_TRAIN"]
                ),
                "val_context_count": len(
                    [record for record in d1_rows if record.split == "D1_DEV_VAL"]
                ),
                "train_subject_count": len(d1_train_subjects),
                "val_subject_count": len(d1_val_subjects),
                "subject_intersection_count": len(d1_train_subjects & d1_val_subjects),
                "recording_intersection_count": len(
                    d1_train_recordings & d1_val_recordings
                ),
                "split_identity": d1_split.get("split_identity"),
                "recording_level_leakage": d1_split.get("recording_level_leakage"),
            },
            "total_model_ready_unique": len(records),
            "duplicate_model_input_count": len(records)
            - len({record.model_input_id for record in records}),
        },
        "target_state_counts": {
            source: {
                state: sum(
                    record.source_id == source
                    and record.breathing_state == state
                    for record in records
                )
                for state in (PRESENT, ABSENT, AMBIGUOUS)
            }
            for source in ("D0", "D1")
        },
        "supervision": {
            "train_rows": len(_record_group(records, "TRAIN")),
            "train_breathing_eligible_rows": int(
                sum(
                    record.breathing_mask > 0
                    for record in _record_group(records, "TRAIN")
                )
            ),
            "d1_dev_val_rows": len(_record_group(records, "D1_DEV_VAL")),
            "d1_dev_val_breathing_eligible_rows": int(
                sum(
                    record.breathing_mask > 0
                    for record in _record_group(records, "D1_DEV_VAL")
                )
            ),
            "ambiguous_rows_retained_for_provenance": int(
                sum(record.breathing_state == AMBIGUOUS for record in records)
            ),
            "ambiguous_rows_used_for_learning": 0,
            "target_unavailable_rows_used_for_learning": 0,
        },
        "provenance_requirements": {
            "row_lineage_count": len(lineage),
            "required_fields_present": all(
                all(
                    row.get(field) is not None
                    for field in (
                        "source_id",
                        "source_dataset",
                        "source_file",
                        "subject_id",
                        "recording_id",
                        "model_input_id",
                        "split",
                        "short_context_interval_s",
                        "short_target_interval_s",
                        "reference_method",
                        "breathing_reference_state",
                    )
                )
                for row in lineage
            ),
            "source_scope": source_scope,
        },
        "label_lineage_audit": {
            "label_source": "M-PV1.breathing_reference_state",
            "reference_semantics_preserved": True,
            "apnea_protocol_strings_used": False,
            "breath_hold_names_used": False,
            "low_amplitude_as_label_used": False,
            "radar_amplitude_as_label_used": False,
            "model_output_as_label_used": False,
            "clinical_apnea_claimed": False,
            "A4_labels_are_safenest_proxies_only": True,
        },
        "leakage_audit": {
            "future_samples_used": False,
            "random_target_alignment": False,
            "internal_event_position_used": False,
            "short_target_end_equals_context_end": target_end_matches,
            "short_target_sample_range_fixed": target_start_matches,
            "d0_val_or_heldout_used": False,
            "d1_dev_val_used_for_training": False,
            "d2_accessed": False,
            "mr60_supervised_physiology_used": False,
            "d2_rows": 0,
            "mr60_rows": 0,
        },
        "protected_30s_artifact_hashes_before_run": dict(protected_hashes),
        "protected_30s_artifacts_are_read_only": True,
        "records": lineage,
    }


def _input_contract() -> Dict[str, Any]:
    return {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "profile_id": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_INPUT_PROFILE_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "context": {
            "duration_s": SHORT_SECONDS,
            "sampling_rate_hz": SAMPLE_RATE_HZ,
            "samples": SHORT_SAMPLES,
            "shape": "[B,150,1]",
            "ordering": "OLDEST_TO_NEWEST",
            "interval": "[t-15s,t]",
            "target_interval": "[t-5s,t]",
            "target_start_sample_in_short_context": TARGET_START_SAMPLE,
            "target_end_sample_exclusive_in_short_context": TARGET_END_SAMPLE,
        },
        "causal_rules": {
            "future_samples_forbidden": True,
            "internal_event_position_forbidden": True,
            "random_target_alignment_forbidden": True,
            "context_end_equals_target_end": True,
        },
        "representation": {
            "input_channel": "accepted R1 sensor-independent relative-motion trace",
            "derivation": "tail 150 samples from accepted 300-sample M-PV1/R1 context",
            "trace_scaler": "one global mean/std fit on D0 TRAIN plus D1_DEV_TRAIN only",
            "mask_channel": False,
            "runtime_invalid_input": "hard Q2 pre-gate; do not zero-fill invalid input into physiology",
        },
        "task_contract": {
            "primary_task": "breathing_evidence",
            "target_states": [
                "PRESENT",
                "ABSENT",
                "AMBIGUOUS",
                "TARGET_UNAVAILABLE",
            ],
            "inherited_reference_states": [PRESENT, ABSENT, AMBIGUOUS],
            "reference_state_mapping": {
                PRESENT: "PRESENT",
                ABSENT: "ABSENT",
                AMBIGUOUS: "AMBIGUOUS",
                "runtime_invalid_input": "TARGET_UNAVAILABLE",
            },
            "training_states": [PRESENT, ABSENT],
            "ambiguous_policy": "retain provenance; mask from training and accuracy metrics",
            "target_unavailable_policy": "no physiological label; runtime application state INPUT_UNAVAILABLE",
            "rr_primary_target": False,
            "rr_analysis": "METADATA_ONLY",
            "temporal_hold_training": False,
        },
        "quality_order": [
            "presence",
            "input_availability",
            "breathing_evidence",
        ],
        "invalid_input_must_not_become": ["PRESENT", "ABSENT", "APNEA"],
        "inheritance_boundaries": {
            "m_pv1_frozen_contract_modified": False,
            "m_pv2_30s_contract_modified": False,
            "d0_d1_governance_modified": False,
            "q2_policy_modified": False,
            "i1_i2_i3_runtime_contracts_modified": False,
        },
    }


def _target_alignment(records: Sequence[ShortRecord]) -> Dict[str, Any]:
    return {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_TARGET_ALIGNMENT_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "base_target_contract": {
            "source": M_PV1_REL.as_posix(),
            "base_context_interval_s": "[t-30s,t]",
            "base_target_interval_s": "[t-5s,t]",
            "base_target_anchor": "FINAL_FIXED_INTERVAL_OF_CAUSAL_CONTEXT",
        },
        "short_target_contract": {
            "short_context_interval_s": "[t-15s,t]",
            "short_target_interval_s": "[t-5s,t]",
            "relative_target_interval_s": "[10s,15s]",
            "relative_target_sample_range": [TARGET_START_SAMPLE, TARGET_END_SAMPLE],
            "causal": True,
            "future_information_used": False,
        },
        "alignment_validation": {
            "row_count": len(records),
            "context_end_equals_target_end": all(
                abs(
                    float(record.provenance["short_context_interval_s"][1])
                    - float(record.provenance["base_target_interval_s"][1])
                )
                < 1e-6
                for record in records
            ),
            "fixed_target_start_sample": all(
                record.provenance["short_target_sample_range"]
                == [TARGET_START_SAMPLE, TARGET_END_SAMPLE]
                for record in records
            ),
            "random_alignment": False,
            "internal_event_position": False,
            "future_samples": False,
        },
        "label_semantics": {
            "present_absent_inherited_from": "M-PV1 breathing_reference_state",
            "ambiguous_rows": int(
                sum(record.breathing_state == AMBIGUOUS for record in records)
            ),
            "ambiguous_learning_mask": 0,
            "target_unavailable_rows": 0,
            "apnea_protocol_to_label": False,
            "breath_hold_name_to_label": False,
            "radar_amplitude_to_label": False,
            "clinical_apnea_claim": False,
        },
        "excluded_task_alignment": {
            "rr": {
                "status": "METADATA_ONLY",
                "trained": False,
                "evaluated": False,
                "reason": "15 seconds is not a robust multi-cycle RR context at low rates",
            },
            "temporal_hold": {
                "status": "NOT_TRAINED",
                "reason": "history/persistence belongs to later model decisions",
            },
        },
    }


def _training_config() -> Dict[str, Any]:
    config = {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "frozen_before_training": True,
        "seeds": list(SEEDS),
        "primary_run_count": len(SEEDS),
        "model": {
            "architecture": "Conv1D(1->8,k5,s2) -> Conv1D(8->16,k5,s2) -> Conv1D(16->24,k3,s2) -> newest-5-position mean pool -> Linear(24->16) -> breathing logit",
            "input_shape": "[B,150,1]",
            "output": "breathing_evidence_logit_only",
            "edge_candidate": True,
            "quality_head": False,
            "rr_head": False,
            "temporal_hold_head": False,
        },
        "optimizer": {
            "name": "Adam",
            "learning_rate": 0.001,
            "weight_decay": 0.0001,
            "batch_size": 32,
            "max_epochs": 150,
            "gradient_clip_norm": 1.0,
            "early_stopping": {
                "monitor": "D1_DEV_VAL_masked_breathing_bce",
                "min_epochs": 30,
                "patience": 20,
            },
        },
        "loss": {
            "name": "masked_binary_cross_entropy_with_logits",
            "present": 1,
            "absent": 0,
            "ambiguous_mask": 0,
            "target_unavailable_mask": 0,
            "source_weights": dict(SOURCE_WEIGHTS),
            "class_weighting": "inverse class mass after source/subject weighting, fit on TRAIN membership only",
            "subject_weighting": "inverse eligible breathing-example count within source and split",
        },
        "preprocessing": {
            "trace_scaler": "global z-score",
            "fit_scope": ["D0:TRAIN", "D1:D1_DEV_TRAIN"],
            "validation_statistics_used": False,
            "d0_val_used": False,
            "d0_subject_heldout_used": False,
            "d2_used": False,
            "mr60_supervised_labels_used": False,
        },
        "quality": {
            "hard_q2_pre_gate": True,
            "invalid_application_state": "INPUT_UNAVAILABLE",
            "synthetic_corruption": {
                "used_for_physiology_labels": False,
                "used_for_threshold_tuning": False,
                "used_only_for_availability_diagnostic": True,
                "profile_id": "MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1",
            },
        },
        "evaluation": {
            "accuracy_groups": ["D0_TRAIN_OBSERVE", "D1_DEV_VAL"],
            "metrics": [
                "macro_f1",
                "present_recall",
                "absent_recall",
                "ambiguous_handling",
            ],
            "baseline_reference": BASELINE_BREATHING_REL.as_posix(),
            "selection_during_phase": False,
        },
        "forbidden_or_deferred": [
            "RR_LEARNING",
            "TEMPORAL_HOLD_LEARNING",
            "D0_VAL",
            "D0_SUBJECT_HELDOUT",
            "D2",
            "MR60_SUPERVISED_PHYSIOLOGY",
            "CALIBRATION",
            "THRESHOLD_TUNING_ON_CORRUPTION",
            "INT8_OR_TFLITE",
            "RASPBERRY_PI_VALIDATION",
            "FINAL_SELECTION",
        ],
    }
    config["configuration_sha256"] = _sha256_json(config)
    return config


def _model_card(
    checkpoints: Sequence[Mapping[str, Any]],
    training_summaries: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    model = ShortBreathingCNN()
    footprint = _flops_estimate()
    return {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "status": "CANDIDATE_ONLY_NOT_SELECTED",
        "architecture": {
            "family": "SHORT_CONTEXT_TRACE_CNN",
            "description": "lightweight valid Conv1D breathing-evidence classifier",
            "input_shape": "[B,150,1]",
            "output_shape": "[B,1]",
            "parameter_count": _parameter_count(model),
            "float32_parameter_bytes": _parameter_count(model) * 4,
            "flops_estimate": footprint,
            "edge_deployable_candidate": True,
        },
        "input_contract": "datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/input_contract.json",
        "training_config": "datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/training_config.json",
        "target": {
            "primary": "breathing_evidence",
            "states": ["PRESENT", "ABSENT"],
            "inherited_reference_states": [PRESENT, ABSENT, AMBIGUOUS],
            "ambiguous": "masked_and_not_rewritten",
            "target_unavailable": "hard_abstention_state",
        },
        "runtime_safety": {
            "presence_gate_precedes_availability": True,
            "hard_q2_invalid_blocks_model_invocation": True,
            "invalid_input_cannot_emit_present_absent_apnea": True,
            "temporal_hold": "not_present",
            "rr": "not_present",
        },
        "latency_estimate": {
            "method": "deterministic operation count at declared 1 GFLOP/s reference only",
            "estimated_inference_latency_ms": footprint[
                "latency_estimate_ms_at_1_gflop_s"
            ],
            "hardware_measurement": False,
            "raspberry_pi_measurement": False,
        },
        "checkpoints": list(checkpoints),
        "training_summaries": list(training_summaries),
        "quantization": "NOT_GENERATED",
        "tflite": "NOT_GENERATED",
        "selection": {
            "final_selection": False,
            "selected_float_model": False,
            "selection_status": "NOT_SELECTED",
        },
    }


def _evaluate_short_candidates(
    models: Mapping[int, ShortBreathingCNN],
    records: Sequence[ShortRecord],
    scaler: Mapping[str, Any],
    training_summaries: Mapping[int, Mapping[str, Any]],
    checkpoints: Mapping[int, Mapping[str, Any]],
) -> Dict[str, Any]:
    groups = {
        "D0_TRAIN_OBSERVE": _record_group(records, "D0_TRAIN"),
        "D1_DEV_VAL": _record_group(records, "D1_DEV_VAL"),
    }
    per_seed: Dict[str, Any] = {}
    for seed in SEEDS:
        seed_groups: Dict[str, Any] = {}
        for group_name, group_records in groups.items():
            scores = _predict(models[seed], group_records, scaler)
            seed_groups[group_name] = _breathing_metrics(group_records, scores)
        per_seed[str(seed)] = {
            "seed": seed,
            "checkpoint": checkpoints[seed],
            "training": {
                key: value
                for key, value in training_summaries[seed].items()
                if key != "history"
            },
            "groups": seed_groups,
        }
    aggregate = {}
    for group_name in groups:
        rows = [
            per_seed[str(seed)]["groups"][group_name]
            for seed in SEEDS
        ]
        first = rows[0]
        aggregate[group_name] = {
            "record_count": first["record_count"],
            "supervision_eligible_count": first["supervision_eligible_count"],
            "present_count": first["present_count"],
            "absent_count": first["absent_count"],
            "ambiguous_count": first["ambiguous_count"],
            "ambiguous_handling": first["ambiguous_handling"],
            "metrics_across_seeds": _aggregate_metric_rows(rows),
        }
    return {
        "per_seed": per_seed,
        "aggregate": aggregate,
    }


def _comparison_deltas(
    short: Mapping[str, Any], baseline: Mapping[str, Any]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for group in ("D0_TRAIN_OBSERVE", "D1_DEV_VAL"):
        result[group] = {}
        short_metrics = short["aggregate"][group]["metrics_across_seeds"]
        base_metrics = baseline["groups"][group]["aggregate"]
        for name in ("macro_f1", "present_recall", "absent_recall"):
            short_value = short_metrics.get(name)
            base_value = base_metrics.get(name)
            if (
                isinstance(short_value, Mapping)
                and isinstance(base_value, Mapping)
                and short_value.get("mean") is not None
                and base_value.get("mean") is not None
            ):
                result[group][name] = float(
                    short_value["mean"] - base_value["mean"]
                )
            else:
                result[group][name] = None
    return result


def _evaluation_result(
    short_results: Mapping[str, Any],
    records: Sequence[ShortRecord],
) -> Dict[str, Any]:
    baseline = _baseline_metrics(records)
    availability = _availability_evidence()
    return {
        "identity": "SHORT_CONTEXT_CANDIDATE_RESULT",
        "candidate_identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "gate": "PASS_WITH_LIMITATIONS",
        "status": "EVIDENCE_PRODUCED_NO_SELECTION",
        "selection": {
            "performed": False,
            "final_selection": False,
            "selected_model": None,
            "interpretation_rule": "descriptive comparison only; defer selection to later M-PV3 evaluation",
        },
        "breathing_evidence": {
            "short_context_metrics": short_results,
            "required_metrics": [
                "macro_f1",
                "present_recall",
                "absent_recall",
                "ambiguous_handling",
            ],
        },
        "baseline_30s_comparison": {
            "baseline": baseline,
            "short_minus_baseline_mean_delta": _comparison_deltas(
                short_results, baseline
            ),
            "comparison_is_not_selection": True,
        },
        "availability": availability,
        "latency": {
            "short_context_requirement_s": SHORT_SECONDS,
            "baseline_30s_context_requirement_s": BASE_SECONDS,
            "first_valid_decision_time_s": {
                "short_context": SHORT_SECONDS,
                "baseline_30s": BASE_SECONDS,
                "short_minus_baseline_s": SHORT_SECONDS - BASE_SECONDS,
            },
            "recovery_time_comparison_is_synthetic_quality_only": True,
            "runtime_latency_hardware_validated": False,
        },
        "excluded_tasks": {
            "rr": {
                "trained": False,
                "evaluated": False,
                "status": "METADATA_ONLY",
            },
            "temporal_hold": {"trained": False, "status": "EXCLUDED"},
        },
        "ambiguous_handling": {
            "policy": "retain provenance and exclude from pure-class loss/metrics",
            "D0_TRAIN_count": int(
                sum(
                    record.breathing_state == AMBIGUOUS
                    for record in _record_group(records, "D0_TRAIN")
                )
            ),
            "D1_DEV_VAL_count": int(
                sum(
                    record.breathing_state == AMBIGUOUS
                    for record in _record_group(records, "D1_DEV_VAL")
                )
            ),
            "converted_to_present_or_absent": False,
        },
        "safety_checks": {
            "d2_accessed": False,
            "mr60_supervised_physiology_used": False,
            "future_leakage": False,
            "radar_amplitude_label_generation": False,
            "existing_30s_artifacts_modified": False,
            "q2_invalid_can_emit_physiology": False,
        },
    }


def _limitations() -> Dict[str, Any]:
    return {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_LIMITATIONS_V1",
        "gate": "PASS_WITH_LIMITATIONS",
        "limitations": [
            {
                "code": "D0_TRAIN_OBSERVE_ONLY",
                "severity": "LIMITATION",
                "detail": "D0 VAL and D0_SUBJECT_HELDOUT were not used; D0 accuracy is not held-out evidence.",
            },
            {
                "code": "D1_ABSENT_CLASS_UNAVAILABLE",
                "severity": "LIMITATION",
                "detail": "D1_DEV_VAL contains PRESENT and AMBIGUOUS rows but no supervised ABSENT rows; D1 absent recall and macro F1 are undefined.",
            },
            {
                "code": "AMBIGUOUS_MASKED",
                "severity": "INVARIANT",
                "detail": "AMBIGUOUS rows remain provenance/transition evidence and are not converted into a pure class.",
            },
            {
                "code": "SYNTHETIC_AVAILABILITY_ONLY",
                "severity": "LIMITATION",
                "detail": "Gap/freeze/stale recovery is a Q2 quality-only synthetic timing diagnostic, not real MR60 or Pi measurement.",
            },
            {
                "code": "NO_RR_LEARNING",
                "severity": "INVARIANT",
                "detail": "RR is metadata-only because a 15-second context may contain too few cycles at low rates.",
            },
            {
                "code": "NO_TEMPORAL_HOLD",
                "severity": "INVARIANT",
                "detail": "Temporal hold/history is excluded from this candidate.",
            },
            {
                "code": "NO_DEPLOYMENT_VALIDATION",
                "severity": "LIMITATION",
                "detail": "No INT8/TFLite conversion, Raspberry Pi latency, or real-sensor validation was performed.",
            },
            {
                "code": "PROXY_NOT_CLINICAL",
                "severity": "INVARIANT",
                "detail": "Inherited A4 reference semantics are SafeNest breathing proxies and are not clinical apnea.",
            },
        ],
        "claims_not_permitted": [
            "15 seconds replaces the existing 30-second M-PV2 contract",
            "15 seconds is better than 30 seconds",
            "30 seconds is better than 15 seconds",
            "clinical apnea detection",
            "MR60 supervised physiology performance",
            "Raspberry Pi performance",
        ],
        "next_gate": "M-PV3_OR_LATER_SELECTION_AND_RUNTIME_EVALUATION",
    }


def _write_checksums(
    output: Path, checkpoint_paths: Sequence[str]
) -> Dict[str, Any]:
    required = (
        "input_contract.json",
        "target_alignment.json",
        "dataset_audit.json",
        "training_config.json",
        "model_card.json",
        "evaluation_result.json",
        "limitations.json",
    )
    files: Dict[str, str] = {}
    for name in required:
        path = output / name
        if not path.is_file():
            raise ShortCandidateError(f"required output missing before checksums: {path}")
        files[(OUTPUT_REL / name).as_posix()] = _sha256_file(path)
    for relative in sorted(checkpoint_paths):
        path = ROOT / relative
        files[relative] = _sha256_file(path)
    result = {
        "identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_CHECKSUMS_V1",
        "schema_version": "M-PV2-SHORT-15S.1",
        "self_checksum_excluded": True,
        "files": dict(sorted(files.items())),
    }
    _write_json(output / "checksums.json", result)
    return result


def run_phase() -> Dict[str, Any]:
    protected_before = _protected_artifact_hashes()
    records, scope = _load_short_records()
    output = ROOT / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)

    input_contract = _input_contract()
    target_alignment = _target_alignment(records)
    dataset_audit = _dataset_audit(records, scope["source_scope"], protected_before)
    training_config = _training_config()
    train_records = _record_group(records, "TRAIN")
    validation_records = _record_group(records, "D1_DEV_VAL")
    scaler = _fit_trace_scaler(train_records)

    _write_json(output / "input_contract.json", input_contract)
    _write_json(output / "target_alignment.json", target_alignment)
    _write_json(output / "dataset_audit.json", dataset_audit)
    _write_json(
        output / "training_config.json",
        {**training_config, "trace_scaler": scaler},
    )

    models: Dict[int, ShortBreathingCNN] = {}
    training_summaries: Dict[int, Dict[str, Any]] = {}
    checkpoints: Dict[int, Dict[str, Any]] = {}
    footprint = _flops_estimate()
    for seed in SEEDS:
        model, summary = _train_one(
            seed, train_records, validation_records, scaler, training_config
        )
        models[seed] = model
        training_summaries[seed] = summary
        checkpoints[seed] = _save_checkpoint(
            model,
            seed,
            {
                "candidate_identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
                "input_shape": "[B,150,1]",
                "scaler_sha256": scaler["sha256"],
                "configuration_sha256": training_config["configuration_sha256"],
                "parameter_count": summary["parameter_count"],
                "estimated_flops": footprint["estimated_flops"],
                "selection_status": "NOT_SELECTED",
            },
        )

    model_card = _model_card(
        list(checkpoints.values()),
        [
            {
                key: value
                for key, value in summary.items()
                if key != "history"
            }
            for summary in training_summaries.values()
        ],
    )
    short_results = _evaluate_short_candidates(
        models, records, scaler, training_summaries, checkpoints
    )
    evaluation_result = _evaluation_result(short_results, records)
    limitations = _limitations()
    _write_json(output / "model_card.json", model_card)
    _write_json(output / "evaluation_result.json", evaluation_result)
    _write_json(output / "limitations.json", limitations)
    _write_checksums(
        output,
        [checkpoint["path"] for checkpoint in checkpoints.values()],
    )

    protected_after = _protected_artifact_hashes()
    if protected_after != protected_before:
        raise ShortCandidateError(
            "existing 30-second M-PV2 artifacts changed during short-candidate run"
        )
    return {
        "output": OUTPUT_REL.as_posix(),
        "candidate_identity": "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1",
        "gate": "PASS_WITH_LIMITATIONS",
        "status": "SHORT_CONTEXT_CANDIDATE_RESULT",
        "record_count": len(records),
        "seed_count": len(SEEDS),
        "selection": False,
        "protected_30s_artifacts_unchanged": True,
    }


def main() -> int:
    try:
        result = run_phase()
    except Exception as exc:
        print(f"M-PV2 SHORT 15S FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
