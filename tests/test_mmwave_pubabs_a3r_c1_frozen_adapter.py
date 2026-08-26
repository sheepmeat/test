"""Focused tests for PUBABS-A3R frozen C1 adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from adapters.mmwave_pubabs_c1_frozen_adapter import (
    FROZEN_PROPOSAL_SHA256,
    INTERMEDIATE_LEN,
    TARGET_LEN,
    C1AdapterError,
    adapt_c1_raw,
)
from adapters import mmwave_r1_sensor_independent_trace as r1mod

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = (
    ROOT
    / "datasets/mmwave/manifests/PUBABS_A3C_corrective_contract_proposal/proposed_adapter_contract.json"
)


def _synth_session(
    *,
    hz: float = 20.0,
    duration_s: float = 35.0,
    n_bins: int = 180,
    peak_bin: int = 40,
    dup_at: int | None = None,
    gap_at: int | None = None,
    gap_scale: float = 10.0,
):
    n = int(duration_s * hz) + 5
    t = np.arange(n, dtype=np.float64) / hz
    if dup_at is not None and 0 < dup_at < n:
        t[dup_at] = t[dup_at - 1]
    if gap_at is not None and 0 < gap_at < n:
        t[gap_at:] += (gap_scale - 1.0) / hz
    z = np.zeros((n, n_bins), dtype=np.complex128)
    # dynamic energy concentrated at peak_bin inside ROI
    phase = 0.2 * np.sin(2 * np.pi * 0.25 * t)
    z[:, peak_bin] = np.exp(1j * phase) * (1.0 + 0.05 * np.sin(2 * np.pi * 0.3 * t))
    # weak energy elsewhere in ROI
    for b in range(28, 180):
        if b == peak_bin:
            continue
        z[:, b] = 0.01 * np.exp(1j * 0.01 * np.sin(2 * np.pi * 0.1 * t))
    return t, z


def test_frozen_proposal_hash_matches_canonical():
    h = hashlib.sha256(PROPOSAL.read_bytes()).hexdigest()
    assert h == FROZEN_PROPOSAL_SHA256


def test_duplicate_keep_first_and_valid_path():
    t, z = _synth_session(dup_at=5)
    out = adapt_c1_raw(t, z, recording_id="dup")
    assert out.r1_centered.size == TARGET_LEN
    assert out.intermediate_20hz.size == INTERMEDIATE_LEN
    assert out.selected_bin == 40


def test_non_monotonic_fails():
    t, z = _synth_session()
    t[10] = t[9] - 1e-3
    with pytest.raises(C1AdapterError) as exc:
        adapt_c1_raw(t, z)
    assert exc.value.code == "SOURCE_INVALID_TIMESTAMP_NOT_INCREASING"


def test_median_rate_too_low_fails():
    t, z = _synth_session(hz=10.0)  # median 10 < 12
    with pytest.raises(C1AdapterError) as exc:
        adapt_c1_raw(t, z)
    assert exc.value.code == "SOURCE_INVALID_MEDIAN_RATE_TOO_LOW"


def test_gap_fail_closed():
    t, z = _synth_session(gap_at=50, gap_scale=20.0)
    with pytest.raises(C1AdapterError) as exc:
        adapt_c1_raw(t, z)
    assert exc.value.code == "INPUT_UNAVAILABLE_UNRESOLVABLE_TIME_GAP"


def test_too_short_fails():
    t, z = _synth_session(duration_s=10.0)
    with pytest.raises(C1AdapterError) as exc:
        adapt_c1_raw(t, z)
    assert exc.value.code == "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S"


def test_tie_lowest_bin():
    t, z = _synth_session(peak_bin=50)
    # make bin 45 and 50 equal energy by copying
    z[:, 45] = z[:, 50]
    out = adapt_c1_raw(t, z)
    assert out.selected_bin == 45


def test_class_metadata_does_not_exist_in_api():
    # API signature has no class parameter; changing unused external metadata cannot affect.
    t, z = _synth_session()
    a = adapt_c1_raw(t, z, recording_id="A")
    b = adapt_c1_raw(t, z, recording_id="B")
    assert a.selected_bin == b.selected_bin
    assert np.array_equal(a.r1_centered, b.r1_centered)
    assert np.array_equal(a.train_zscore_trace, b.train_zscore_trace)


def test_determinism_replay():
    t, z = _synth_session()
    a = adapt_c1_raw(t, z)
    b = adapt_c1_raw(t, z)
    assert a.output_hashes() == b.output_hashes()


def test_contract_hash_drift_aborts():
    t, z = _synth_session()
    with pytest.raises(C1AdapterError) as exc:
        adapt_c1_raw(t, z, require_frozen_proposal_sha256="0" * 64)
    assert exc.value.code == "A3R_ABORT_CONTRACT_HASH_DRIFT"


def test_historical_r1_module_identity_unchanged():
    # Guard against accidental R1 edits in this branch.
    text = Path(r1mod.__file__).read_text()
    assert "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1" in text
    assert "SCIPY_RESAMPLE_POLY" in text
    assert "median" in text


def test_no_extrapolation_and_exact_lengths():
    t, z = _synth_session()
    out = adapt_c1_raw(t, z)
    assert out.intermediate_20hz.size == INTERMEDIATE_LEN
    assert out.r1t_10hz.size == TARGET_LEN
    assert out.r1_centered.size == TARGET_LEN
    assert out.train_zscore_trace.size == TARGET_LEN


def test_session_bin_lock_uses_first_30s_only():
    t, z = _synth_session(peak_bin=40, duration_s=60.0)
    # After the frozen observation interval (t > t0+30), put huge energy at bin 100.
    late = t > 30.0
    z[late, 100] = 10.0 * np.exp(1j * np.linspace(0, 20, int(late.sum())))
    out = adapt_c1_raw(t, z)
    assert out.selected_bin == 40


def test_extrapolation_forbidden():
    # Exactly 29.0 s of support after t0 → grid needs 29.9 → fail.
    t, z = _synth_session(duration_s=29.0)
    with pytest.raises(C1AdapterError) as exc:
        adapt_c1_raw(t, z)
    assert exc.value.code in {
        "INPUT_UNAVAILABLE_TOO_SHORT_FOR_30S",
        "INPUT_UNAVAILABLE_INTERP_EXTRAPOLATION_FORBIDDEN",
    }


def test_filtfilt_constants():
    from adapters.mmwave_pubabs_c1_frozen_adapter import (
        BUTTER_FC_HZ,
        BUTTER_ORDER,
        FILTFILT_PADLEN,
        FILTFILT_PADTYPE,
    )

    assert BUTTER_ORDER == 4
    assert BUTTER_FC_HZ == 4.0
    assert FILTFILT_PADTYPE == "odd"
    assert FILTFILT_PADLEN == 15
