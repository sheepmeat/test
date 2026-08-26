"""PUBABS-A3R frozen C1 → ROLE_L structural adapter.

Contracts (Sol-frozen via PUBABS-A3C receipt):
  R1T_MEASURED_TIMESTAMP_10HZ_V1
  C1_ROI_EXCLUDE_NEARFIELD28_DYNENERGY_UNWRAP_V1  (RG-S1)

Historical R1 is unchanged and is only used for already-at-10Hz median centering.
Adapter API intentionally omits class labels.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np
from scipy.signal import butter, filtfilt

from adapters.mmwave_r1_sensor_independent_trace import (
    NativeTraceInput,
    R1TraceError,
    adapt_native_trace,
)

FROZEN_PROPOSAL_SHA256 = (
    "cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446"
)
TIMESTAMP_CONTRACT_ID = "R1T_MEASURED_TIMESTAMP_10HZ_V1"
RANGE_CONTRACT_ID = "C1_ROI_EXCLUDE_NEARFIELD28_DYNENERGY_UNWRAP_V1"
RANGE_POLICY = "RG-S1"
HISTORICAL_R1_PROFILE = "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1"

N_BINS = 180
ROI_LO = 28
ROI_HI = 179  # inclusive
RANGE_RES_M = 0.0512
OBS_DURATION_S = 30.0
LAST_GRID_OFFSET_S = 29.9
MIN_MEDIAN_SOURCE_HZ = 12.0
GAP_FACTOR = 2.5
INTERMEDIATE_HZ = 20.0
TARGET_HZ = 10.0
INTERMEDIATE_LEN = 599
TARGET_LEN = 300
BUTTER_ORDER = 4
BUTTER_FC_HZ = 4.0
FILTFILT_PADTYPE = "odd"
FILTFILT_PADLEN = 15

# Frozen TRAIN trace scaler (M-PV2); never refit on C1.
TRAIN_TRACE_MEAN = 0.5681105335535223
TRAIN_TRACE_STD = 10.976509586515288
TRAIN_SCALER_SHA256 = (
    "5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c"
)


class C1AdapterError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class C1AdapterResult:
    selected_bin: int
    selected_range_m_equiv: float
    median_dt: float
    median_source_hz: float
    max_gap: float
    t0: float
    time_10hz: np.ndarray
    phase_native_obs: np.ndarray
    intermediate_20hz: np.ndarray
    filtered_20hz: np.ndarray
    r1t_10hz: np.ndarray
    r1_centered: np.ndarray
    train_zscore_trace: np.ndarray
    r1_metadata: dict[str, Any]

    def output_hashes(self) -> dict[str, str]:
        def h(arr: np.ndarray) -> str:
            return hashlib.sha256(np.ascontiguousarray(arr, dtype=np.float64).tobytes()).hexdigest()

        return {
            "r1t_10hz_sha256": h(self.r1t_10hz),
            "r1_centered_sha256": h(self.r1_centered),
            "train_zscore_trace_sha256": h(self.train_zscore_trace),
            "selected_bin": str(self.selected_bin),
        }


def _keep_first_duplicates(t: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if t.size == 0:
        return t, z
    keep = np.ones(t.size, dtype=bool)
    keep[1:] = t[1:] != t[:-1]
    return t[keep], z[keep]


def adapt_c1_raw(
    timestamps_s: np.ndarray,
    complex_frames: np.ndarray,
    *,
    recording_id: str = "c1_session",
    require_frozen_proposal_sha256: str | None = FROZEN_PROPOSAL_SHA256,
) -> C1AdapterResult:
    """Adapt one C1 session. Does not accept or use a class label."""
    if require_frozen_proposal_sha256 is not None:
        if require_frozen_proposal_sha256 != FROZEN_PROPOSAL_SHA256:
            raise C1AdapterError(
                "A3R_ABORT_CONTRACT_HASH_DRIFT",
                require_frozen_proposal_sha256,
            )

    t = np.asarray(timestamps_s, dtype=np.float64).reshape(-1)
    z = np.asarray(complex_frames, dtype=np.complex128)
    if z.ndim != 2 or z.shape[0] != t.size:
        raise C1AdapterError("SOURCE_INVALID_SHAPE", f"t={t.shape} z={z.shape}")
    if z.shape[1] != N_BINS:
        raise C1AdapterError("SOURCE_INVALID_BIN_COUNT", str(z.shape[1]))
    if not np.all(np.isfinite(t)):
        raise C1AdapterError("SOURCE_INVALID_TIMESTAMP_NONFINITE")
    if not np.all(np.isfinite(z.real)) or not np.all(np.isfinite(z.imag)):
        raise C1AdapterError("SOURCE_INVALID_COMPLEX_NONFINITE")

    t, z = _keep_first_duplicates(t, z)
    if t.size < 2:
        raise C1AdapterError("INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S", "after_dedupe")
    deltas_all = np.diff(t)
    if np.any(deltas_all <= 0.0):
        raise C1AdapterError("SOURCE_INVALID_TIMESTAMP_NOT_INCREASING")

    t0 = float(t[0])
    t_end = t0 + OBS_DURATION_S
    obs_mask = (t >= t0) & (t <= t_end)
    t_obs = t[obs_mask]
    z_obs = z[obs_mask]
    if t_obs.size < 2:
        raise C1AdapterError("INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S", "obs_interval")
    if float(t_obs[-1]) < t0 + LAST_GRID_OFFSET_S:
        raise C1AdapterError(
            "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S",
            f"last_obs={t_obs[-1]}; need>={t0 + LAST_GRID_OFFSET_S}",
        )

    dts = np.diff(t_obs)
    if np.any(dts <= 0.0):
        raise C1AdapterError("SOURCE_INVALID_TIMESTAMP_NOT_INCREASING", "obs")
    median_dt = float(np.median(dts))
    if not np.isfinite(median_dt) or median_dt <= 0.0:
        raise C1AdapterError("SOURCE_INVALID_MEDIAN_RATE_TOO_LOW", "median_dt")
    median_hz = 1.0 / median_dt
    if median_hz < MIN_MEDIAN_SOURCE_HZ:
        raise C1AdapterError(
            "SOURCE_INVALID_MEDIAN_RATE_TOO_LOW",
            f"median_hz={median_hz}",
        )
    max_gap = float(np.max(dts))
    if max_gap > GAP_FACTOR * median_dt + 1e-15:
        raise C1AdapterError(
            "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP",
            f"max_gap={max_gap}; limit={GAP_FACTOR * median_dt}",
        )

    # RG-S1 range selection on first 30 s only, session lock.
    roi = slice(ROI_LO, ROI_HI + 1)
    mu = z_obs[:, roi].mean(axis=0)
    dyn = z_obs[:, roi] - mu
    energy = np.mean(np.abs(dyn) ** 2, axis=0)
    # lowest index among argmax ties
    selected_local = int(np.flatnonzero(energy == np.max(energy))[0])
    selected_bin = ROI_LO + selected_local
    selected_range_m = selected_bin * RANGE_RES_M

    phase = np.unwrap(np.angle(z_obs[:, selected_bin]))
    if not np.all(np.isfinite(phase)):
        raise C1AdapterError("INPUT_UNAVAILABLE_NONFINITE_FILTER_OUTPUT", "phase")

    tau = t0 + np.arange(INTERMEDIATE_LEN, dtype=np.float64) / INTERMEDIATE_HZ
    t_first = float(t_obs[0])
    t_last = float(t_obs[-1])
    if np.any(tau < t_first - 1e-15) or np.any(tau > t_last + 1e-15):
        raise C1AdapterError(
            "INPUT_UNAVAILABLE_INTERP_EXTRAPOLATION_FORBIDDEN",
            f"support=[{t_first},{t_last}] grid=[{tau[0]},{tau[-1]}]",
        )
    # numpy.interp without left/right fill: values only used when inside support
    intermediate = np.interp(tau, t_obs, phase)
    if not np.all(np.isfinite(intermediate)):
        raise C1AdapterError("INPUT_UNAVAILABLE_NONFINITE_FILTER_OUTPUT", "interp")

    b, a = butter(BUTTER_ORDER, BUTTER_FC_HZ, btype="low", fs=INTERMEDIATE_HZ, output="ba")
    filtered = filtfilt(
        b,
        a,
        intermediate,
        method="pad",
        padtype=FILTFILT_PADTYPE,
        padlen=FILTFILT_PADLEN,
    )
    if not np.all(np.isfinite(filtered)):
        raise C1AdapterError("INPUT_UNAVAILABLE_NONFINITE_FILTER_OUTPUT", "filtfilt")
    if filtered.size != INTERMEDIATE_LEN:
        raise C1AdapterError("INPUT_UNAVAILABLE_NONFINITE_FILTER_OUTPUT", "filt_len")

    r1t = filtered[0:INTERMEDIATE_LEN:2].astype(np.float64, copy=False)
    if r1t.size != TARGET_LEN:
        raise C1AdapterError("INPUT_UNAVAILABLE_NONFINITE_FILTER_OUTPUT", f"decim={r1t.size}")
    time_10 = t0 + np.arange(TARGET_LEN, dtype=np.float64) / TARGET_HZ

    native = NativeTraceInput(
        source_id="C1",
        dataset_id="zenodo_15032859",
        subject_id="adapter",
        recording_id=recording_id,
        condition="STRUCTURAL_ONLY",
        trace=r1t,
        time_s=time_10,
        sampling_rate_hz=TARGET_HZ,
        native_trace_semantics="UNWRAPPED_PHASE_RAD_C1_RG_S1",
        native_trace_unit="radian",
        source_scale_metadata={
            "selected_bin": selected_bin,
            "timestamp_contract": TIMESTAMP_CONTRACT_ID,
            "range_contract": RANGE_CONTRACT_ID,
            "range_policy": RANGE_POLICY,
        },
        provenance={
            "frozen_proposal_sha256": FROZEN_PROPOSAL_SHA256,
            "historical_r1": HISTORICAL_R1_PROFILE,
        },
    )
    try:
        common = adapt_native_trace(native)
    except R1TraceError as exc:
        raise C1AdapterError(f"R1_{exc.code}", exc.detail) from exc

    centered = np.asarray(common.trace, dtype=np.float64)
    if centered.size != TARGET_LEN:
        raise C1AdapterError("R1_OUTPUT_LENGTH", str(centered.size))
    zscore = (centered - TRAIN_TRACE_MEAN) / TRAIN_TRACE_STD
    if not np.all(np.isfinite(zscore)):
        raise C1AdapterError("INPUT_UNAVAILABLE_NONFINITE_FILTER_OUTPUT", "zscore")

    return C1AdapterResult(
        selected_bin=selected_bin,
        selected_range_m_equiv=selected_range_m,
        median_dt=median_dt,
        median_source_hz=median_hz,
        max_gap=max_gap,
        t0=t0,
        time_10hz=time_10,
        phase_native_obs=phase,
        intermediate_20hz=intermediate,
        filtered_20hz=filtered,
        r1t_10hz=r1t,
        r1_centered=centered,
        train_zscore_trace=zscore,
        r1_metadata=dict(common.metadata),
    )
