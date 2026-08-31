"""Standalone Thermal V2 Candidate A A0 inference adapter.

Primary artifact: committed FP32 TFLite.
Preprocessing: exact Candidate A ``RELATIVE_THERMAL_APPEARANCE_V1`` /
``FRAME_ROBUST_P2_P98_V1`` via ``datasets.thermal.tv2_ca_representation``.

This adapter accepts a **canonical** finite ``[62,80]`` scalar frame whose
source-specific geometry is already applied upstream. It does not convert
MI48 raw bytes, UDP packets, or arbitrary camera geometry.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final

import numpy as np

from datasets.thermal import tv2_ca_representation as rep

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config/thermal/tv2_a0_standalone_prototype_manifest.json"

CLASS_NAMES: Final[tuple[str, str, str]] = ("NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY")
CANONICAL_HW: Final[tuple[int, int]] = (62, 80)
SUPPORTED_SOURCE_PROFILES: Final[frozenset[str]] = frozenset({
    "CANONICAL_62X80_ALREADY_APPLIED",
    "PUBLIC_SDT_T_A6_G1_CANONICAL",
})


class ThermalTv2A0Error(ValueError):
    """Fail-closed adapter error."""


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path | None = None) -> dict:
    manifest_path = Path(path) if path is not None else DEFAULT_MANIFEST
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _reject_non_canonical(frame: np.ndarray) -> np.ndarray:
    if frame.size == 0:
        raise ThermalTv2A0Error("empty frame rejected")
    if frame.dtype == object or not np.issubdtype(np.asarray(frame).dtype, np.number):
        raise ThermalTv2A0Error("non-numeric frame rejected")
    array = np.asarray(frame)
    if array.ndim == 3 and array.shape == (62, 80, 1):
        array = array[:, :, 0]
    if array.ndim != 2 or tuple(array.shape) != CANONICAL_HW:
        raise ThermalTv2A0Error(
            f"canonical frame must be [62,80] (or [62,80,1]); got {tuple(array.shape)}. "
            "Arbitrary geometry is not resized at this adapter."
        )
    if not np.isfinite(array).all():
        raise ThermalTv2A0Error("NaN/Inf frame rejected; quality policy is fail-closed")
    return array.astype(np.float32, copy=False)


def preprocess_canonical_frame(
    frame: np.ndarray,
    *,
    source_profile: str | None = "CANONICAL_62X80_ALREADY_APPLIED",
) -> np.ndarray:
    """Return model input ``[1,62,80,1]`` float32 in ``[0,1]``.

    ``source_profile`` documents that geometry is already canonical. Unknown
    profiles are rejected rather than silently treated as equivalent.
    """
    if source_profile is not None and source_profile not in SUPPORTED_SOURCE_PROFILES:
        raise ThermalTv2A0Error(
            f"unsupported source_profile {source_profile!r}; "
            "this adapter does not accept MI48 raw, UDP, or uncanonicalized geometry"
        )
    canonical = _reject_non_canonical(frame)
    relative = rep.relative_appearance(canonical[None, ...], rep.NORM_ROBUST)
    return rep.to_model_input(relative).astype(np.float32, copy=False)


def preprocess_canonical_batch(frames: np.ndarray) -> np.ndarray:
    """Vectorized preprocess for ``[N,62,80]`` canonical frames."""
    array = np.asarray(frames)
    if array.ndim != 3 or array.shape[1:] != CANONICAL_HW:
        raise ThermalTv2A0Error(f"expected [N,62,80], got {array.shape}")
    if array.size == 0:
        raise ThermalTv2A0Error("empty batch rejected")
    if not np.issubdtype(array.dtype, np.number):
        raise ThermalTv2A0Error("non-numeric batch rejected")
    if not np.isfinite(array).all():
        raise ThermalTv2A0Error("NaN/Inf batch rejected; quality policy is fail-closed")
    relative = rep.relative_appearance(np.asarray(array, dtype=np.float32), rep.NORM_ROBUST)
    return rep.to_model_input(relative).astype(np.float32, copy=False)


def _tflite_module():
    try:
        import tensorflow.lite as tflite  # type: ignore
        return tflite
    except ImportError:
        try:
            import tflite_runtime.interpreter as tflite  # type: ignore
            return tflite
        except ImportError as exc:
            raise ThermalTv2A0Error("no TFLite interpreter available") from exc


def load_tflite_interpreter(
    project_root: Path | None = None,
    manifest: dict | None = None,
    verify_hash: bool = True,
):
    root = Path(project_root) if project_root is not None else ROOT
    spec = manifest if manifest is not None else load_manifest()
    rel = spec["tflite"]["repository_relative_path"]
    path = root / rel
    if not path.is_file():
        raise ThermalTv2A0Error(f"missing TFLite artifact: {rel}")
    digest = sha256_file(path)
    expected = spec["tflite"]["sha256"]
    if verify_hash and digest != expected:
        raise ThermalTv2A0Error(f"TFLite SHA-256 mismatch: {digest} != {expected}")
    tflite = _tflite_module()
    interpreter = tflite.Interpreter(model_path=str(path))
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    if list(inp["shape"]) != [1, 62, 80, 1]:
        raise ThermalTv2A0Error(f"unexpected TFLite input shape {inp['shape']}")
    if list(out["shape"]) != [1, 3]:
        raise ThermalTv2A0Error(f"unexpected TFLite output shape {out['shape']}")
    if np.dtype(inp["dtype"]) != np.float32 or np.dtype(out["dtype"]) != np.float32:
        raise ThermalTv2A0Error("TFLite tensors must be float32")
    return interpreter, inp, out, digest


def infer_preprocessed(
    interpreter,
    input_detail: dict,
    output_detail: dict,
    model_input: np.ndarray,
) -> dict[str, Any]:
    tensor = np.asarray(model_input, dtype=np.float32)
    if tensor.shape != (1, 62, 80, 1):
        raise ThermalTv2A0Error(f"model input must be [1,62,80,1], got {tensor.shape}")
    if not np.isfinite(tensor).all():
        raise ThermalTv2A0Error("non-finite model input rejected")
    interpreter.set_tensor(input_detail["index"], tensor)
    interpreter.invoke()
    probabilities = np.asarray(interpreter.get_tensor(output_detail["index"]), dtype=np.float32)
    if probabilities.shape != (1, 3):
        raise ThermalTv2A0Error(f"unexpected output shape {probabilities.shape}")
    if not np.isfinite(probabilities).all():
        raise ThermalTv2A0Error("non-finite TFLite output")
    index = int(np.argmax(probabilities[0]))
    return {
        "probabilities": probabilities[0].tolist(),
        "predicted_index": index,
        "predicted_label": CLASS_NAMES[index],
    }


def infer_canonical_frame(
    frame: np.ndarray,
    interpreter=None,
    *,
    project_root: Path | None = None,
    source_profile: str | None = "CANONICAL_62X80_ALREADY_APPLIED",
) -> dict[str, Any]:
    if interpreter is None:
        interpreter, inp, out, _ = load_tflite_interpreter(project_root)
    else:
        inp = interpreter.get_input_details()[0]
        out = interpreter.get_output_details()[0]
    model_input = preprocess_canonical_frame(frame, source_profile=source_profile)
    return infer_preprocessed(interpreter, inp, out, model_input)
