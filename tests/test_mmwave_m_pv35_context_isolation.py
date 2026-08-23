"""Regression checks for the M-PV3.5 controlled context isolation evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import mmwave_m_pv35_context_isolation as phase
from scripts import validate_mmwave_m_pv35_context_isolation as validator


def test_contract_declares_only_two_context_lengths() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv35_context_isolation_contract.json").read_text(encoding="utf-8"))
    assert contract["frozen_before_training"] is True
    assert [(lane["context_seconds"], lane["input_shape"]) for lane in contract["lanes"]] == [
        (15, "[B,150,1]"),
        (30, "[B,300,1]"),
    ]
    assert contract["decision_boundary"]["production_model_selection"] is False


def test_parity_model_accepts_both_lengths_with_exact_parameter_count() -> None:
    model = phase.ParityTraceCNN()
    assert phase._parameter_count(model) == 2297
    assert tuple(model(torch.zeros((2, 150, 1), dtype=torch.float32)).shape) == (2,)
    assert tuple(model(torch.zeros((2, 300, 1), dtype=torch.float32)).shape) == (2,)


def test_q2_audit_is_hard_fail_closed_and_synthetic_only() -> None:
    audit = phase._recovery_q2_audit()
    assert audit["not_a_real_sensor_latency_measurement"] is True
    for rows in audit["lanes"].values():
        for row in rows:
            assert row["invalid_application_state"] == "INPUT_UNAVAILABLE"
            assert row["model_invocation_when_invalid"] == "BLOCKED"
            assert not row["invalid_emitted_as_present"]
            assert not row["invalid_emitted_as_absent"]
            assert not row["invalid_emitted_as_normal"]
            assert not row["invalid_emitted_as_apnea"]


def test_committed_evidence_passes_focused_validator() -> None:
    result = validator.validate()
    assert result["ok"] is True, result
    assert result["gate"] == "PASS_WITH_LIMITATIONS"
