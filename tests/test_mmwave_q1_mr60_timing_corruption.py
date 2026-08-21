#!/usr/bin/env python3
"""Focused Q1 timing-corruption tests. No training, D2, or MR60 labels."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption"
GENERATOR = ROOT / "scripts/mmwave_q1_mr60_timing_corruption.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_q1_mr60_timing_corruption.py"

from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    PROFILE_ID,
    SUPPORTED_MODES,
    TRANSPORT_DUPLICATE_MODE,
    apply_timing_corruption,
    load_profile,
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


class TestMmwaveQ1TimingCorruption(unittest.TestCase):
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
        cls.profile = load_profile(MANIFEST / "synthetic_corruption_profile.json")
        cls.t = np.arange(256, dtype=np.float64) * 100.0
        cls.x = np.sin(np.linspace(0.0, 4.0 * np.pi, 256))

    def test_validator_pass_with_limitations(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["checks"]["D2_USED"], "NO")
        self.assertEqual(result["checks"]["MR60_LABELS_USED"], "NO")
        self.assertEqual(result["checks"]["Q2_THRESHOLD_DECISIONS_MADE"], "NO")
        self.assertEqual(result["checks"]["PARALLEL_TRACK_BRANCH_CONTAMINATION"], "NO")

    def test_profile_parseable_and_safety_flags(self) -> None:
        profile = load("synthetic_corruption_profile.json")
        self.assertEqual(profile["profile_id"], PROFILE_ID)
        self.assertEqual(profile["supported_corruption_modes"], list(SUPPORTED_MODES))
        self.assertFalse(profile["physiological_values_imported_from_mr60"])
        self.assertFalse(profile["mr60_labels_used"])
        self.assertFalse(profile["model_outputs_used"])
        self.assertFalse(profile["d2_used"])
        blob = json.dumps(profile)
        self.assertNotIn("breath_phase_values", blob)
        self.assertNotIn("apnea_labels", blob)
        self.assertNotIn("VITALSENSE_120", blob)

    def test_clean_identity(self) -> None:
        result = apply_timing_corruption(
            self.t, self.x, self.profile, mode="CLEAN", severity="NOMINAL", seed=99
        )
        np.testing.assert_array_equal(result["timestamps_ms"], self.t)
        np.testing.assert_array_equal(result["values"], self.x)
        self.assertTrue(all(row["operation"] == "UNCHANGED" for row in result["provenance"]))

    def test_determinism_and_seed(self) -> None:
        a = apply_timing_corruption(
            self.t, self.x, self.profile, mode="CADENCE_JITTER", severity="TYPICAL", seed=3
        )
        b = apply_timing_corruption(
            self.t, self.x, self.profile, mode="CADENCE_JITTER", severity="TYPICAL", seed=3
        )
        c = apply_timing_corruption(
            self.t, self.x, self.profile, mode="CADENCE_JITTER", severity="TYPICAL", seed=4
        )
        np.testing.assert_array_equal(a["timestamps_ms"], b["timestamps_ms"])
        self.assertFalse(np.array_equal(a["timestamps_ms"], c["timestamps_ms"]))

    def test_cadence_jitter_lineage_and_order(self) -> None:
        result = apply_timing_corruption(
            self.t, self.x, self.profile, mode="CADENCE_JITTER", severity="STRESSED", seed=5
        )
        self.assertEqual(result["output_count"], 256)
        self.assertEqual(
            [row["original_sample_index"] for row in result["provenance"]],
            list(range(256)),
        )
        self.assertTrue(np.all(np.diff(result["timestamps_ms"]) > 0))
        np.testing.assert_array_equal(result["values"], self.x)
        self.assertTrue(any(row["operation"] == "TIMING_JITTERED" for row in result["provenance"]))

    def test_source_republication_lineage(self) -> None:
        labels = np.array(["NORMAL"] * 256)
        result = apply_timing_corruption(
            self.t,
            self.x,
            self.profile,
            mode="SOURCE_REPUBLICATION",
            severity="STRESSED",
            seed=13,
            labels=labels,
        )
        published = [row for row in result["provenance"] if row["operation"] == "SOURCE_REPUBLISHED"]
        self.assertGreater(len(published), 0)
        for row in published:
            self.assertIsNotNone(row["duplicate_or_republication_source_index"])
            origin = row["original_sample_index"]
            self.assertEqual(result["values"][row["output_index"]], self.x[origin])
        self.assertTrue(all(label == "NORMAL" for label in result["labels"]))
        self.assertNotIn("APNEA", list(result["labels"]))

    def test_no_amplitude_normalization_or_interpolation(self) -> None:
        values = np.array([10.0, 20.0, 40.0, 80.0, 160.0] + [160.0] * 123)
        t = np.arange(values.size, dtype=np.float64) * 100.0
        result = apply_timing_corruption(
            t, values, self.profile, mode="JITTER_PLUS_SOURCE_REPUBLICATION", severity="TYPICAL", seed=2
        )
        self.assertTrue(np.all(np.isin(result["values"], values)))
        self.assertGreaterEqual(float(np.max(np.abs(result["values"]))), 160.0 - 1e-12)

    def test_transport_duplicate_rejected(self) -> None:
        with self.assertRaises(ValueError):
            apply_timing_corruption(
                self.t, self.x, self.profile, mode=TRANSPORT_DUPLICATE_MODE, severity="TYPICAL", seed=1
            )

    def test_session_accounting(self) -> None:
        inventory = load("evidence_inventory.json")
        self.assertEqual(inventory["discovered_sessions"]["physical_m_n0"], 74)
        self.assertGreaterEqual(inventory["eligible_core_sessions"], 50)
        self.assertGreater(inventory["excluded_sessions"], 0)
        self.assertGreater(inventory["q2_handoff_sessions"], 0)

    def test_no_q2_thresholds(self) -> None:
        profile = load("synthetic_corruption_profile.json")
        self.assertEqual(profile["unsupported_corruption_modes"]["LARGE_GAP"], "DEFERRED_TO_Q2")
        self.assertEqual(profile["unsupported_corruption_modes"]["FREEZE"], "DEFERRED_TO_Q2")
        exceptions = load("exception_registry.json")
        self.assertTrue(
            all(row["q1_does_not_set_rejection_threshold"] for row in exceptions["q2_handoff_observations"])
        )


if __name__ == "__main__":
    unittest.main()
