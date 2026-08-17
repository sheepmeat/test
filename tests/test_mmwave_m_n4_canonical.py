#!/usr/bin/env python3
"""Focused M-N4 canonical contract tests. No training. No heldout inspection."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from scripts.mmwave_m_n4_canonical import (
    CLASS_TO_ID,
    CONTRACT_ID,
    MAD_EPSILON,
    SAMPLE_COUNT,
    SPLIT_SEED,
    accept_phase_events,
    apply_s1,
    assign_subject_splits,
    canonical_from_public_native,
    canonical_grid,
    contract_self_check,
    CanonicalContractError,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"
SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"
INDEX = ROOT / "datasets/mmwave/manifests/m_n4_canonical/window_index.jsonl"


class TestMmwaveMN4Canonical(unittest.TestCase):
    def test_self_check_clean(self) -> None:
        self.assertEqual(contract_self_check(), [])

    def test_contract_json_agrees_with_code(self) -> None:
        doc = json.loads(CONTRACT.read_text())
        self.assertEqual(doc["contract_id"], CONTRACT_ID)
        self.assertEqual(doc["resampling"]["sample_count"], SAMPLE_COUNT)
        self.assertEqual(doc["resampling"]["target_rate_hz"], 8.0)
        self.assertEqual(doc["resampling"]["input_shape"], [1, 240, 1])
        self.assertEqual(doc["scale"]["mad_epsilon"], MAD_EPSILON)
        self.assertEqual(doc["scale"]["normalization_formula"], "r / MAD")
        self.assertEqual(doc["timing"]["update_advancement_tolerance_ms"], 8.0)
        self.assertFalse(doc["timing"]["eight_ms_is_sensor_period"])
        self.assertEqual(doc["public_split"]["seed"], SPLIT_SEED)
        self.assertEqual(doc["target"]["class_mapping"], {"0": "NORMAL", "1": "RAPID_OR_ABNORMAL", "2": "APNEA"})
        self.assertEqual(doc["team_mr60"]["supervised_training"], "DISALLOWED")
        self.assertEqual(doc["active_canonical_shape_count"], 1)
        self.assertFalse(doc["historical_b_input_inherited"])

    def test_grid_240_not_241(self) -> None:
        grid = canonical_grid(10.0)
        self.assertEqual(grid.size, 240)
        self.assertAlmostEqual(grid[0], 10.0)
        self.assertAlmostEqual(grid[-1], 10.0 + 29.875)
        self.assertLess(grid[-1], 10.0 + 30.0)

    def test_mad_zero_tensor(self) -> None:
        out, mad, collapsed = apply_s1(np.zeros(240))
        self.assertTrue(collapsed)
        self.assertEqual(mad, 0.0)
        self.assertTrue(np.all(out == 0))
        self.assertEqual(out.dtype, np.float32)

    def test_mad_divides_without_centering(self) -> None:
        y = np.linspace(-2.0, 2.0, 240)
        out, mad, collapsed = apply_s1(y)
        self.assertFalse(collapsed)
        expected = (y / mad).astype(np.float32)
        np.testing.assert_allclose(out, expected, rtol=0, atol=1e-6)

    def test_split_isolation(self) -> None:
        doc = json.loads(SPLIT.read_text())
        train = set(doc["subject_ids"]["TRAIN"])
        val = set(doc["subject_ids"]["VAL"])
        held = set(doc["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        self.assertEqual(len(train), 77)
        self.assertEqual(len(val), 17)
        self.assertEqual(len(held), 16)
        self.assertEqual(len(train | val | held), 110)
        self.assertEqual(len(train & val), 0)
        self.assertEqual(len(train & held), 0)
        self.assertEqual(len(val & held), 0)
        self.assertFalse(doc["heldout_is_project_wide_pristine"])
        self.assertFalse(doc["historical_a5_split_copied"])

    def test_index_matches_split_and_excludes_ambiguous_from_supervised(self) -> None:
        split = json.loads(SPLIT.read_text())
        assignment = {sid: sp for sp, ids in split["subject_ids"].items() for sid in ids}
        counts = {"TRAIN": 0, "VAL": 0, "NEW_MODEL_HELDOUT_TEST": 0}
        eligible = {"TRAIN": set(), "VAL": set(), "NEW_MODEL_HELDOUT_TEST": set()}
        with INDEX.open() as handle:
            for line in handle:
                row = json.loads(line)
                self.assertEqual(row["split"], assignment[row["subject_id"]])
                self.assertFalse(row["heldout_performance_inspected"])
                self.assertFalse(row["team_mr60_supervised"])
                if row["supervised_eligible"]:
                    counts[row["split"]] += 1
                    eligible[row["split"]].add(row["safenest_label"])
                    self.assertIn(row["safenest_label"], CLASS_TO_ID)
                elif row["assignment_status"] == "AMBIGUOUS":
                    self.assertFalse(row["supervised_eligible"])
        self.assertEqual(counts["TRAIN"], 337)
        self.assertEqual(counts["VAL"], 70)
        self.assertEqual(counts["NEW_MODEL_HELDOUT_TEST"], 74)
        for split_name in ("TRAIN", "VAL"):
            self.assertEqual(eligible[split_name], set(CLASS_TO_ID))

    def test_assign_is_deterministic(self) -> None:
        frozen = json.loads(SPLIT.read_text())["subject_ids"]
        all_ids = sorted(frozen["TRAIN"] + frozen["VAL"] + frozen["NEW_MODEL_HELDOUT_TEST"])
        again = assign_subject_splits(all_ids)
        rebuilt = {sp: sorted(sid for sid, s in again.items() if s == sp) for sp in frozen}
        self.assertEqual(rebuilt, {k: frozen[k] for k in frozen})

    def test_public_native_window_dtype_shape(self) -> None:
        t = np.arange(0, 30.0, 0.1)
        x = np.sin(2 * np.pi * 0.2 * t)
        win = canonical_from_public_native(t, x, 0.0)
        self.assertEqual(win.values.shape, (240,))
        tensor = win.values.reshape(1, 240, 1)
        self.assertEqual(tensor.shape, (1, 240, 1))
        self.assertTrue(np.all(np.isfinite(tensor)))

    def test_one_train_public_window_if_archive_present(self) -> None:
        archive = ROOT / "datasets/raw_archives/external_datasets/db_records.zip"
        if not archive.is_file():
            self.skipTest("public archive not present")
        from scripts.mmwave_m_n2_common_representation import load_public_series

        split = json.loads(SPLIT.read_text())
        train = set(split["subject_ids"]["TRAIN"])
        held = set(split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        prow = None
        with (ROOT / "datasets/mmwave/manifests/a6_full_conversion/full_provenance_manifest.jsonl").open() as handle:
            for line in handle:
                row = json.loads(line)
                if row["window_id"].endswith("__W0000") and row["subject_id"] in train:
                    prow = row
                    break
        self.assertIsNotNone(prow)
        self.assertNotIn(prow["subject_id"], held)
        series = load_public_series(prow["recording_id"], prow)
        t_start = float(prow["source_start_index"]) * float(series.median_dt)
        win = canonical_from_public_native(series.elapsed_s, series.values, t_start)
        self.assertEqual(win.values.shape, (240,))
        self.assertTrue(np.all(np.isfinite(win.values)))
        self.assertFalse(win.collapsed)
        t_ms = np.arange(0, 30000, 100, dtype=np.float64)
        x = np.ones_like(t_ms)
        with self.assertRaises(CanonicalContractError) as ctx:
            accept_phase_events(t_ms, x, None, production=True, timestamps_are_seconds=False)
        self.assertEqual(str(ctx.exception), "PRODUCTION_FRESHNESS_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
