#!/usr/bin/env python3
"""Focused Q2 availability-contract tests. No training, Q3 metrics, D2, or MR60 labels."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_Q2_input_unavailable_contract"
GENERATOR = ROOT / "scripts/mmwave_q2_input_unavailable.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_q2_input_unavailable.py"

from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    apply_timing_corruption,
    load_profile as load_q1_profile,
)
from scripts.mmwave_q2_input_unavailable import (  # noqa: E402
    CONTRACT_ID,
    PROFILE_ID,
    Q1_COMMIT,
    Q1_PROFILE_PATH,
    apply_quality_corruption,
    evaluate_availability,
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


class TestMmwaveQ2InputUnavailable(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.check_call(["python3", str(GENERATOR)], cwd=ROOT)
        cls.validator = subprocess.run(
            ["python3", str(VALIDATOR)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        cls.q1 = load_q1_profile(Q1_PROFILE_PATH)
        cls.t = np.arange(256, dtype=np.float64) * 100.0
        cls.x = np.sin(np.linspace(0.0, 6.0 * np.pi, 256))
        cls.labels = np.array(["NORMAL"] * 256)

    def test_validator_pass_with_limitations(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["checks"]["Q1_PROFILE_INHERITED"], "YES")
        self.assertEqual(result["checks"]["D2_USED"], "NO")
        self.assertEqual(result["checks"]["Q3_WORK_PERFORMED"], "NO")
        self.assertEqual(result["checks"]["PARALLEL_TRACK_BRANCH_CONTAMINATION"], "NO")

    def test_q1_typical_jitter_remains_valid(self) -> None:
        jittered = apply_timing_corruption(
            self.t, self.x, self.q1, mode="CADENCE_JITTER", severity="TYPICAL", seed=5
        )
        evaluation = evaluate_availability(jittered["timestamps_ms"], jittered["values"])
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertEqual(evaluation["window_state"], "VALID_WINDOW")

    def test_isolated_republication_is_not_freeze(self) -> None:
        src = self.t[:32].copy()
        values = self.x[:32].copy()
        src[10] = src[9]
        values[10] = values[9]
        evaluation = evaluate_availability(self.t[:32], values, source_update_ms=src)
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertNotIn("SOURCE_FREEZE", evaluation["reasons"])

    def test_large_gap_freeze_stale_flat_timestamp_fail_closed(self) -> None:
        labels = self.labels
        gap = apply_quality_corruption(
            self.t, self.x, mode="LARGE_GAP", seed=1, labels=labels, q1_profile=self.q1
        )
        freeze = apply_quality_corruption(
            self.t, self.x, mode="SOURCE_FREEZE", seed=1, labels=labels, q1_profile=self.q1
        )
        stale = apply_quality_corruption(
            self.t, self.x, mode="STALE_SOURCE", seed=1, labels=labels, q1_profile=self.q1
        )
        flat = apply_quality_corruption(
            self.t, self.x, mode="FLAT_EXACT", seed=1, labels=labels, q1_profile=self.q1
        )
        self.assertEqual(gap["evaluation"]["quality_target"], "INPUT_UNAVAILABLE")
        self.assertIn("LARGE_GAP", gap["evaluation"]["reasons"])
        self.assertEqual(freeze["evaluation"]["quality_target"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_FREEZE", freeze["evaluation"]["reasons"])
        self.assertEqual(stale["evaluation"]["quality_target"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_STALE", stale["evaluation"]["reasons"])
        self.assertEqual(flat["evaluation"]["quality_target"], "INPUT_UNAVAILABLE")
        self.assertIn("SIGNAL_FLAT_EXACT", flat["evaluation"]["reasons"])
        collided = np.concatenate([np.zeros(8), np.arange(1, 25, dtype=np.float64) * 100.0])
        ts_eval = evaluate_availability(collided, np.sin(np.linspace(0.0, np.pi, collided.size)))
        self.assertEqual(ts_eval["quality_target"], "INPUT_UNAVAILABLE")
        self.assertTrue(
            "TIMESTAMP_UNRESOLVED" in ts_eval["reasons"] or "TIMESTAMP_NON_MONOTONIC" in ts_eval["reasons"]
        )

    def test_low_amplitude_dynamic_not_rejected(self) -> None:
        tiny = 1e-5 * np.sin(np.linspace(0.0, 10.0 * np.pi, 256))
        evaluation = evaluate_availability(self.t, tiny)
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertNotIn("SIGNAL_FLAT_EXACT", evaluation["reasons"])

    def test_invalid_target_is_not_physiology(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="SOURCE_FREEZE", seed=2, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["quality_target"], "INPUT_UNAVAILABLE")
        self.assertIsNone(result["evaluation"]["physiology_class_assigned"])
        self.assertTrue(all(label == "NORMAL" for label in result["labels"]))
        self.assertNotIn("APNEA", list(result["labels"]))

    def test_presence_gate(self) -> None:
        absent = evaluate_availability(self.t, self.x, presence=False)
        unknown = evaluate_availability(self.t, self.x, presence=None)
        present_valid = evaluate_availability(self.t, self.x, presence=True)
        present_invalid = apply_quality_corruption(
            self.t, self.x, mode="LARGE_GAP", seed=1, labels=self.labels, q1_profile=self.q1, presence=True
        )
        self.assertEqual(absent["availability_state"], "PRESENCE_SUPPRESSED")
        self.assertEqual(unknown["availability_state"], "PRESENCE_SUPPRESSED")
        self.assertEqual(present_valid["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertEqual(present_invalid["evaluation"]["availability_state"], "INPUT_UNAVAILABLE")

    def test_no_gap_interpolation_and_lineage(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="LARGE_GAP", seed=3, labels=self.labels, q1_profile=self.q1
        )
        self.assertFalse(result["evaluation"]["interpolation_applied"])
        dts = np.diff(result["timestamps_ms"])
        self.assertGreaterEqual(float(np.max(dts)), 500.0 - 1e-9)
        self.assertTrue(all(row["original_sample_index"] is not None for row in result["provenance"]))
        self.assertEqual(set(result["values"].tolist()), set(self.x.tolist()))

    def test_determinism(self) -> None:
        a = apply_quality_corruption(
            self.t, self.x, mode="JITTER_PLUS_LARGE_GAP", seed=9, labels=self.labels, q1_profile=self.q1
        )
        b = apply_quality_corruption(
            self.t, self.x, mode="JITTER_PLUS_LARGE_GAP", seed=9, labels=self.labels, q1_profile=self.q1
        )
        np.testing.assert_array_equal(a["timestamps_ms"], b["timestamps_ms"])
        self.assertEqual(a["evaluation"]["reasons"], b["evaluation"]["reasons"])

    def test_handoff_and_contract_identity(self) -> None:
        contract = load("input_availability_contract.json")
        self.assertEqual(contract["contract_id"], CONTRACT_ID)
        self.assertEqual(contract["q1_dependency"]["commit"], Q1_COMMIT)
        profile = load("synthetic_quality_profile.json")
        self.assertEqual(profile["profile_id"], PROFILE_ID)
        handoff = load("q1_handoff_audit.json")["handoff_validation"]
        for key in ("run_3598", "run_2884", "gap_158380_ms", "gap_42637_ms", "timestamp_collision"):
            self.assertEqual(handoff[key]["quality_target"], "INPUT_UNAVAILABLE", key)

    def test_recovery_marks_window_invalid(self) -> None:
        freeze = apply_quality_corruption(
            self.t, self.x, mode="SOURCE_FREEZE", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(freeze["evaluation"]["window_state"], "INVALID_WINDOW_INPUT_UNAVAILABLE")
        self.assertNotEqual(freeze["evaluation"]["availability_state"], "PHYSIOLOGY_ELIGIBLE")


if __name__ == "__main__":
    unittest.main()
