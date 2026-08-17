#!/usr/bin/env python3
"""Focused M-N5 candidate-training checks. No heldout inference. No final selection."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from scripts.mmwave_m_n4_canonical import CONTRACT_ID, SAMPLE_COUNT
from scripts.mmwave_m_n5_train_candidates import (
    ALLOWED_SPLITS,
    DIAGNOSTIC_CANDIDATE,
    FORBIDDEN_SPLIT,
    NEW_MODEL_HELDOUT_TEST_INFERENCE,
    PARAM_BUDGET,
    PRIMARY_CANDIDATES,
    SEEDS,
    RECIPE_PATH,
    build_candidate,
    load_supervised_index,
    trainable_parameter_count,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/mmwave/m_n4_canonical_input_dataset_contract.json"
SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"
TRAIN_SCRIPT = ROOT / "scripts/mmwave_m_n5_train_candidates.py"
INDEX = ROOT / "datasets/mmwave/manifests/m_n4_canonical/window_index.jsonl"


class TestMmwaveMN5Candidates(unittest.TestCase):
    def test_frozen_m_n4_contract_untouched(self) -> None:
        doc = json.loads(CONTRACT.read_text())
        self.assertEqual(doc["contract_id"], CONTRACT_ID)
        self.assertEqual(doc["resampling"]["input_shape"], [1, 240, 1])
        self.assertEqual(doc["resampling"]["sample_count"], SAMPLE_COUNT)
        self.assertEqual(doc["resampling"]["target_rate_hz"], 8.0)
        self.assertEqual(doc["scale"]["method"], "WINDOW_LOCAL_MAD")
        self.assertEqual(doc["derivative"]["representation"], "TIME_AWARE_FIRST_DERIVATIVE")
        self.assertEqual(doc["public_split"]["counts"]["TRAIN"], 77)
        self.assertEqual(doc["public_split"]["counts"]["VAL"], 17)
        self.assertEqual(doc["public_split"]["counts"]["NEW_MODEL_HELDOUT_TEST"], 16)
        self.assertFalse(doc["public_split"]["m_n5_may_use_heldout_for_selection"])

    def test_split_identity_unchanged(self) -> None:
        split = json.loads(SPLIT.read_text())
        self.assertEqual(len(split["subject_ids"]["TRAIN"]), 77)
        self.assertEqual(len(split["subject_ids"]["VAL"]), 17)
        self.assertEqual(len(split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"]), 16)
        train = set(split["subject_ids"]["TRAIN"])
        val = set(split["subject_ids"]["VAL"])
        held = set(split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        self.assertEqual(len(train & val), 0)
        self.assertEqual(len(train & held), 0)
        self.assertEqual(len(val & held), 0)

    def test_recipe_matches_fixed_contract(self) -> None:
        recipe = json.loads(RECIPE_PATH.read_text())
        self.assertEqual(recipe["input_contract_id"], CONTRACT_ID)
        self.assertEqual(recipe["seeds"], [42, 2026])
        self.assertEqual(recipe["class_weighting"], "UNWEIGHTED")
        self.assertEqual(recipe["learning_rate"], 0.001)
        self.assertEqual(recipe["batch_size"], 32)
        self.assertEqual(recipe["maximum_epochs"], 120)
        self.assertEqual(recipe["early_stopping"]["patience"], 15)
        self.assertEqual(recipe["new_model_heldout_test_inference"], 0)
        self.assertFalse(recipe["final_model_selection"])
        self.assertEqual(tuple(recipe["primary_candidates"]), PRIMARY_CANDIDATES)
        self.assertEqual(tuple(SEEDS), (42, 2026))

    def test_supervised_index_excludes_heldout_and_ambiguous(self) -> None:
        train_rows, val_rows, meta = load_supervised_index()
        self.assertEqual(len(train_rows), 337)
        self.assertEqual(len(val_rows), 70)
        self.assertEqual(meta["heldout_tensors_materialized"], 0)
        self.assertEqual(meta["heldout_inference_runs"], 0)
        self.assertEqual(NEW_MODEL_HELDOUT_TEST_INFERENCE, 0)
        self.assertFalse(meta["team_mr60_supervised"])
        for row in train_rows + val_rows:
            self.assertIn(row["split"], ALLOWED_SPLITS)
            self.assertNotEqual(row["split"], FORBIDDEN_SPLIT)
            self.assertTrue(row["supervised_eligible"])
            self.assertNotEqual(row["safenest_label"], "AMBIGUOUS")

    def test_script_source_does_not_materialize_heldout(self) -> None:
        text = TRAIN_SCRIPT.read_text()
        self.assertIn("NEW_MODEL_HELDOUT_TEST_INFERENCE = 0", text)
        self.assertIn("FORBIDDEN_SPLIT", text)
        self.assertIn("HELDOUT_MATERIALIZATION_ATTEMPTED", text)
        self.assertNotIn("LOCKED_TEST", text)
        self.assertIn("UNWEIGHTED", text)
        self.assertNotIn("compute_train_class_weights", text)
        self.assertNotIn("class_weight=", text)
        self.assertNotIn("Optuna", text)
        self.assertNotIn("LSTM", text)

    def test_primary_architectures_io_and_budget(self) -> None:
        dummy = np.zeros((2, 240, 1), dtype=np.float32)
        for candidate_id in PRIMARY_CANDIDATES:
            model = build_candidate(candidate_id)
            self.assertEqual(tuple(model.inputs[0].shape), (None, 240, 1))
            self.assertEqual(tuple(model.outputs[0].shape), (None, 3))
            n_params = trainable_parameter_count(model)
            self.assertLessEqual(n_params, PARAM_BUDGET)
            self.assertGreater(n_params, 0)
            out = model(dummy, training=False).numpy()
            self.assertEqual(out.shape, (2, 3))
            self.assertTrue(np.all(np.isfinite(out)))
            np.testing.assert_allclose(out.sum(axis=1), np.ones(2), atol=1e-5)

    def test_diagnostic_linear_is_not_a_primary_candidate(self) -> None:
        self.assertNotIn(DIAGNOSTIC_CANDIDATE, PRIMARY_CANDIDATES)
        model = build_candidate(DIAGNOSTIC_CANDIDATE)
        self.assertEqual(tuple(model.outputs[0].shape), (None, 3))
        self.assertLess(trainable_parameter_count(model), 1000)

    def test_manifest_excludes_heldout_metrics_if_present(self) -> None:
        path = ROOT / "datasets/mmwave/manifests/m_n5_candidate_runs.json"
        if not path.is_file():
            self.skipTest("candidate manifest not generated")
        doc = json.loads(path.read_text())
        self.assertEqual(doc["contract_id"], CONTRACT_ID)
        self.assertEqual(doc["heldout"]["NEW_MODEL_HELDOUT_TEST_INFERENCE"], 0)
        self.assertFalse(doc["heldout"]["heldout_performance_inspected"])
        self.assertIsNone(doc["candidate_viability"]["FINAL_SELECTED_MODEL"])
        self.assertFalse(doc["m_n4_contract_modified"])
        self.assertNotIn("heldout_macro_f1", json.dumps(doc))
        self.assertNotIn("NEW_MODEL_HELDOUT_TEST", json.dumps(doc.get("runs", [])))

    def test_index_file_not_rewritten_by_m_n5_module(self) -> None:
        before = INDEX.read_bytes()
        load_supervised_index()
        self.assertEqual(INDEX.read_bytes(), before)
        self.assertEqual(json.loads(CONTRACT.read_text())["contract_id"], "MMWAVE_MR60_COMPAT_INPUT_DATASET_V1")


if __name__ == "__main__":
    unittest.main()
