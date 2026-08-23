"""Focused regression tests for the M-PV3.6 contract-design phase."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_mmwave_m_pv36_role_based_evaluation as validator


def test_contract_prohibits_selection_and_combined_winner_score() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    assert contract["decision_boundary"]["production_model_selection"] is False
    assert contract["decision_boundary"]["m_pv4_approval"] is False
    assert contract["global_rules"]["combined_winner_score"] == "PROHIBITED"
    assert contract["global_rules"]["safety_is_non_compensable"] is True


def test_short_role_does_not_receive_rr_penalty() -> None:
    contract = json.loads((ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json").read_text(encoding="utf-8"))
    role = contract["roles"]["ROLE_S_SHORT_CONTEXT"]
    assert role["rr_metric_status"] == "NOT_APPLICABLE"
    assert role["temporal_hold_metric_status"] == "NOT_APPLICABLE"


def test_focused_contract_validator_passes() -> None:
    result = validator.validate()
    assert result["ok"] is True, result
    assert result["gate"] == "PASS_WITH_LIMITATIONS"
