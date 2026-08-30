"""RELATIVE_THERMAL_APPEARANCE_V1 representation for the Thermal V2 Candidate A prototype.

This module defines the only representation in which PUBLIC_SDT physical thermal frames and
Thermal-IM non-radiometric thermal-intensity frames are allowed to meet.

Governance
----------
The common tensor is **not** Celsius and must never be described as Celsius. Thermal-IM is
``NON_RADIOMETRIC_THERMAL_INTENSITY``; no physical unit is fabricated for it. PUBLIC_SDT keeps
its verified physical decode up to the point of geometry canonicalization, after which the
per-frame relative operator removes physical units from both sources symmetrically.

Pipeline
--------
PUBLIC_SDT::

    verified uint16 (Kelvin centiunits)
    -> Celsius decode                       (T-A1 raw unit contract, already applied by T-A6)
    -> G1_FIXED_ASPECT_CROP_BILINEAR        (crop [10,0,630,480] -> bilinear 80x62)
    -> relative within-frame operator
    -> [62,80,1] float32

Thermal-IM::

    decoded RGBT_T.mp4 frame, uint8 288x384x3
    -> BT.601 luma                          (deterministic single channel)
    -> TIM_FIXED_ASPECT_CROP_BILINEAR       (crop [6,0,378,288] -> bilinear 80x62)
    -> relative within-frame operator
    -> [62,80,1] float32

Both geometry profiles are members of the same *policy family* (fixed-aspect centre crop then
bilinear resize to 80x62) but they are deliberately **different profiles** with different crop
coordinates. The SDT crop is never applied to Thermal-IM.
"""

from __future__ import annotations

from typing import Final

import numpy as np

REPRESENTATION_ID: Final[str] = "RELATIVE_THERMAL_APPEARANCE_V1"
REPRESENTATION_UNIT: Final[str] = "RELATIVE_DIMENSIONLESS_NOT_CELSIUS"
CANONICAL_HW: Final[tuple[int, int]] = (62, 80)
CANONICAL_MODEL_INPUT: Final[tuple[int, int, int, int]] = (1, 62, 80, 1)

# Per-frame relative operators. Exactly two candidates are permitted by the task contract.
NORM_MINMAX: Final[str] = "FRAME_MINMAX_V1"
NORM_ROBUST: Final[str] = "FRAME_ROBUST_P2_P98_V1"
NORMALIZATION_CANDIDATES: Final[tuple[str, str]] = (NORM_MINMAX, NORM_ROBUST)

_EPS: Final[float] = 1e-6

# SDT geometry is inherited from the merged T-A2/G1 evidence and is already baked into the
# T-A6 canonical [62,80] Celsius tensors, so this profile is recorded, not re-applied.
SDT_GEOMETRY_PROFILE: Final[dict] = {
    "geometry_profile_id": "G1_FIXED_ASPECT_CROP_BILINEAR",
    "applies_to": "PUBLIC_SDT",
    "source_native_hw": [480, 640],
    "crop_xyxy_half_open": [10, 0, 630, 480],
    "crop_hw": [480, 620],
    "crop_aspect_wh": 620 / 480,
    "resize_to_wh": [80, 62],
    "interpolation": "bilinear_HALF_PIXEL_CENTER_EDGE_CLAMPING",
    "channel_policy": "SINGLE_CHANNEL_THERMAL",
    "orientation_assumption": "SOURCE_AS_STORED_FROZEN_FOR_SDT",
    "application_status": "ALREADY_APPLIED_BY_T_A6_CANONICAL_ARTIFACT",
}

# Thermal-IM geometry is a source-specific adapter derived from its own verified native
# geometry. Aspect is matched by a centre crop first so that the bilinear step introduces
# only 0.10% residual vertical stretch instead of the 3.33% of a direct 288x384 -> 62x80 resize.
THERMAL_IM_GEOMETRY_PROFILE: Final[dict] = {
    "geometry_profile_id": "TIM_FIXED_ASPECT_CROP_BILINEAR_V1",
    "applies_to": "Thermal-IM",
    "source_native_hw": [288, 384],
    "crop_xyxy_half_open": [6, 0, 378, 288],
    "crop_hw": [288, 372],
    "crop_aspect_wh": 372 / 288,
    "resize_to_wh": [80, 62],
    "interpolation": "bilinear_HALF_PIXEL_CENTER_EDGE_CLAMPING",
    "channel_policy": "BT601_LUMA_THEN_SINGLE_CHANNEL",
    "orientation_assumption": "DECODED_TOP_LEFT_ORIGIN_NO_FLIP_METADATA",
    "residual_vertical_stretch": (372 / 288) / (80 / 62) - 1.0,
    "known_loss": "DOWNSAMPLE_110592_TO_4960_PIXELS_PLUS_3.1PCT_HORIZONTAL_FOV_CROP",
    "sdt_crop_reuse": "FORBIDDEN",
}

BT601_LUMA_WEIGHTS_RGB: Final[tuple[float, float, float]] = (0.299, 0.587, 0.114)


def bt601_luma(frame_rgb: np.ndarray) -> np.ndarray:
    """Reduce a decoded 3-channel visual thermal frame to a deterministic single channel.

    Thermal-IM channels are near-identical but not byte-identical (compressed grayscale or
    limited false colour). A fixed ITU-R BT.601 luma keeps the reduction deterministic and
    documented rather than picking an arbitrary channel.
    """
    if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
        raise ValueError(f"expected HxWx3 frame, received {frame_rgb.shape}")
    weights = np.asarray(BT601_LUMA_WEIGHTS_RGB, dtype=np.float32)
    return np.tensordot(frame_rgb.astype(np.float32), weights, axes=([2], [0]))


def _bilinear_resize(source: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Half-pixel-centre bilinear resize with edge clamping, matching the G1 convention."""
    src_h, src_w = source.shape
    row = (np.arange(out_h, dtype=np.float64) + 0.5) * (src_h / out_h) - 0.5
    col = (np.arange(out_w, dtype=np.float64) + 0.5) * (src_w / out_w) - 0.5
    row = np.clip(row, 0.0, src_h - 1.0)
    col = np.clip(col, 0.0, src_w - 1.0)

    r0 = np.floor(row).astype(np.int64)
    c0 = np.floor(col).astype(np.int64)
    r1 = np.minimum(r0 + 1, src_h - 1)
    c1 = np.minimum(c0 + 1, src_w - 1)
    dr = (row - r0).astype(np.float32)[:, None]
    dc = (col - c0).astype(np.float32)[None, :]

    src = source.astype(np.float32)
    top = src[r0][:, c0] * (1.0 - dc) + src[r0][:, c1] * dc
    bottom = src[r1][:, c0] * (1.0 - dc) + src[r1][:, c1] * dc
    return top * (1.0 - dr) + bottom * dr


def thermal_im_geometry(frame_rgb: np.ndarray) -> np.ndarray:
    """Apply ``TIM_FIXED_ASPECT_CROP_BILINEAR_V1`` to one decoded Thermal-IM frame."""
    expected_hw = tuple(THERMAL_IM_GEOMETRY_PROFILE["source_native_hw"])
    if frame_rgb.shape[:2] != expected_hw:
        raise ValueError(f"expected native {expected_hw}, received {frame_rgb.shape[:2]}")
    luma = bt601_luma(frame_rgb)
    x0, y0, x1, y1 = THERMAL_IM_GEOMETRY_PROFILE["crop_xyxy_half_open"]
    cropped = luma[y0:y1, x0:x1]
    out_h, out_w = CANONICAL_HW
    return _bilinear_resize(cropped, out_h, out_w).astype(np.float32)


def relative_appearance(frames: np.ndarray, method: str) -> np.ndarray:
    """Apply the per-frame relative operator that defines ``RELATIVE_THERMAL_APPEARANCE_V1``.

    ``frames`` is ``[N,62,80]`` in any *finite* source-specific scale (Celsius for PUBLIC_SDT,
    uint8-derived luma for Thermal-IM). The operator is strictly within-frame, so no statistic
    ever crosses frames, splits, or sources, and the output carries no physical unit.

    ``FRAME_MINMAX_V1``           ``(x - min) / (max - min)``      clipped to [0,1]
    ``FRAME_ROBUST_P2_P98_V1``    ``(x - p2)  / (p98 - p2)``       clipped to [0,1]
    """
    if frames.ndim != 3 or frames.shape[1:] != CANONICAL_HW:
        raise ValueError(f"expected [N,62,80], received {frames.shape}")
    if not np.isfinite(frames).all():
        raise ValueError("non-finite value reached the relative operator; quality policy is fail-closed")

    data = frames.astype(np.float32, copy=False)
    flat = data.reshape(data.shape[0], -1)
    if method == NORM_MINMAX:
        low = flat.min(axis=1)
        high = flat.max(axis=1)
    elif method == NORM_ROBUST:
        low, high = np.percentile(flat, [2.0, 98.0], axis=1).astype(np.float32)
    else:
        raise ValueError(f"unsupported normalization method {method!r}")

    scale = np.maximum(high - low, _EPS).astype(np.float32)
    out = (data - low[:, None, None]) / scale[:, None, None]
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def to_model_input(frames: np.ndarray) -> np.ndarray:
    """Add the trailing channel axis expected by the ``[N,62,80,1]`` model input."""
    return frames.reshape(frames.shape[0], CANONICAL_HW[0], CANONICAL_HW[1], 1)


def normalize_into(source, destination, method: str, chunk_rows: int = 1024) -> None:
    """Stream ``relative_appearance`` from ``source`` into ``destination`` in row chunks.

    Both operands may be ``numpy.memmap``. The per-frame operator is independent across frames, so
    chunking is exact rather than an approximation, and peak memory stays proportional to
    ``chunk_rows`` instead of the whole split.
    """
    if source.shape[1:] != CANONICAL_HW:
        raise ValueError(f"expected [N,62,80], received {source.shape}")
    if destination.shape != source.shape:
        raise ValueError("destination shape must match source shape")
    total = source.shape[0]
    for start in range(0, total, chunk_rows):
        stop = min(start + chunk_rows, total)
        block = np.asarray(source[start:stop], dtype=np.float32)
        destination[start:stop] = relative_appearance(block, method).astype(destination.dtype)
        del block


def representation_contract(method: str) -> dict:
    """Machine-readable description of the exact representation actually used."""
    if method not in NORMALIZATION_CANDIDATES:
        raise ValueError(f"unsupported normalization method {method!r}")
    return {
        "representation_id": REPRESENTATION_ID,
        "representation_unit": REPRESENTATION_UNIT,
        "celsius_claim": "FORBIDDEN_NOT_CELSIUS",
        "celsius_intensity_raw_concatenation": "FORBIDDEN_NOT_PERFORMED",
        "normalization_method": method,
        "normalization_scope": "PER_FRAME_WITHIN_FRAME_ONLY",
        "normalization_fitted_statistics": "NONE_NO_CROSS_FRAME_OR_CROSS_SPLIT_STATISTIC",
        "output_range": [0.0, 1.0],
        "output_dtype": "float32",
        "canonical_model_input": list(CANONICAL_MODEL_INPUT),
        "source_geometry_profiles": {
            "PUBLIC_SDT": SDT_GEOMETRY_PROFILE,
            "Thermal-IM": THERMAL_IM_GEOMETRY_PROFILE,
        },
        "formula": {
            NORM_MINMAX: "y = clip((x - min_frame(x)) / max(max_frame(x) - min_frame(x), 1e-6), 0, 1)",
            NORM_ROBUST: "y = clip((x - p2_frame(x)) / max(p98_frame(x) - p2_frame(x), 1e-6), 0, 1)",
        }[method],
    }
