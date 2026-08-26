"""Focused PUBABS-A3 tests: contract recovery + R1 incompatibility codes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from adapters.mmwave_r1_sensor_independent_trace import (
    NativeTraceInput,
    R1TraceError,
    adapt_native_trace,
)

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "datasets/mmwave/manifests/PUBABS_A3_c1_canonical_feasibility"


def test_a3_validation_gate_is_corrective_required():
    result = json.loads((MAN / "validation_result.json").read_text())
    assert result["a3_gate"] == "A3_CORRECTIVE_REQUIRED"
    assert result["a4_recommendation"] == "CORRECTIVE_BEFORE_A4"
    assert result["authorizations"]["model_inference"] is False
    assert result["authorizations"]["membership_construction"] is False
    assert result["m_pv38_status"] == "RESOURCE_BLOCKED_CLOSED"


def test_role_l_contract_recovered_phase_like():
    recovery = json.loads((MAN / "role_l_representation_contract_recovery.json").read_text())
    assert recovery["status"] == "RECOVERED"
    assert "PHASE_LIKE" in recovery["expected_trace_semantics"]
    assert recovery["rate_hz"] == 10.0
    assert recovery["context_samples"] == 300


def test_timing_contract_incompatible_recorded():
    resampling = json.loads((MAN / "c1_resampling_contract.json").read_text())
    assert resampling["status"] == "TIMING_CONTRACT_INCOMPATIBLE"


def test_r1_rejects_irregular_noninteger_rate_grid():
    # Synthetic irregular ~18.8 Hz phase-like series (C1-like timing pathology).
    n = 400
    t = np.cumsum(np.full(n, 1.0 / 18.8)) 
    t = t - t[0]
    # inject a slightly larger gap to mirror measured C1 jitter/gaps vs declared rate
    t[200:] += 0.2
    trace = np.sin(2 * np.pi * 0.25 * t)
    native = NativeTraceInput(
        source_id="synthetic",
        dataset_id="probe",
        subject_id="s",
        recording_id="r",
        condition="FEASIBILITY_ONLY",
        trace=trace,
        time_s=t,
        sampling_rate_hz=18.8,
        native_trace_semantics="phase_like",
        native_trace_unit="radian",
        source_scale_metadata={},
        provenance={},
    )
    with pytest.raises(R1TraceError) as exc:
        adapt_native_trace(native)
    assert exc.value.code in {
        "NON_INTEGER_SOURCE_RATE_UNSUPPORTED",
        "UNRESOLVABLE_TIME_GAP",
        "TIMESTAMP_GRID_INCONSISTENT",
        "NON_INTEGER_RESAMPLING_RATIO",
    }
