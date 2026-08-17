#!/usr/bin/env python3
"""Focused M-N6 Stage A tests. No heldout inference."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.mmwave_m_n4_canonical import CONTRACT_ID
from scripts.mmwave_m_n6_select_lock import (
    HELDOUT_INFERENCE_BEFORE_SELECTION_LOCK,
    PRIMARY_FAMILIES,
    SELECTION_ID,
    family_summary,
    load_primary_runs,
    select_exact_run,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/m_n5_candidate_runs.json"
LOCK_SCRIPT = ROOT / "scripts/mmwave_m_n6_select_lock.py"


class TestMmwaveMN6SelectLock(unittest.TestCase):
    def test_stage_a_script_does_not_open_heldout(self) -> None:
        text = LOCK_SCRIPT.read_text()
        self.assertIn("Heldout tensors are never loaded here", text)
        self.assertIn("HELDOUT_INFERENCE_BEFORE_SELECTION_LOCK = 0", text)
        self.assertNotIn("canonical_from_public_native", text)
        self.assertNotIn("load_public_series", text)
        self.assertNotIn("window_index.jsonl", text)
        self.assertNotIn("generate_train_val_tensors", text)

    def test_family_rule_selects_dilated_on_canonical_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        self.assertEqual(manifest["contract_id"], CONTRACT_ID)
        self.assertEqual(manifest["heldout"]["NEW_MODEL_HELDOUT_TEST_INFERENCE"], 0)
        runs = load_primary_runs(manifest)
        families = family_summary(runs)
        self.assertEqual(
            [row["candidate_id"] for row in families],
            [
                "M-N5_DILATED_CONV1D_GAP_TINY",
                "M-N5_CONV1D_GAP_TINY",
                "M-N5_SMALL_MLP_BASELINE",
            ],
        )
        self.assertEqual(families[0]["candidate_id"], "M-N5_DILATED_CONV1D_GAP_TINY")
        self.assertGreater(families[0]["mean_val_macro_f1"], families[1]["mean_val_macro_f1"])

    def test_exact_run_is_dilated_seed_2026(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        runs = load_primary_runs(manifest)
        selected = select_exact_run(runs, "M-N5_DILATED_CONV1D_GAP_TINY")
        self.assertEqual(selected["seed"], 2026)
        self.assertEqual(selected["artifact_sha256"], "9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab")
        self.assertEqual(HELDOUT_INFERENCE_BEFORE_SELECTION_LOCK, 0)
        self.assertEqual(SELECTION_ID, "MMWAVE_M_N6_SELECTED_FLOAT_V1")


if __name__ == "__main__":
    unittest.main()
