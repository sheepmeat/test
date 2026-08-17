#!/usr/bin/env python3
"""Focused M-N6 Stage B checks. Does not evaluate a second candidate."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.mmwave_m_n4_canonical import CONTRACT_ID
from scripts.mmwave_m_n6_select_lock import SELECTION_ID

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/mmwave/m_n6_selected_candidate_lock.json"
RESULT = ROOT / "datasets/mmwave/manifests/m_n6_heldout_result.json"
PRED = ROOT / "datasets/mmwave/manifests/m_n6_heldout_predictions.jsonl"
EVAL_SCRIPT = ROOT / "scripts/mmwave_m_n6_heldout_eval.py"
SPLIT = ROOT / "datasets/mmwave/splits/mmwave_mr60_compat_subject_split_v1.json"


class TestMmwaveMN6Heldout(unittest.TestCase):
    def test_eval_script_is_single_identity(self) -> None:
        text = EVAL_SCRIPT.read_text()
        self.assertIn("Does not evaluate any", text)
        self.assertIn("require_lock", text)
        self.assertNotIn("M-N5_CONV1D_GAP_TINY", text)
        self.assertNotIn("M-N5_SMALL_MLP_BASELINE", text)
        self.assertNotIn("class_weight", text)

    def test_lock_and_result_share_identity(self) -> None:
        if not RESULT.is_file():
            self.skipTest("heldout result not generated")
        lock = json.loads(LOCK.read_text())
        result = json.loads(RESULT.read_text())
        self.assertEqual(lock["selection_id"], SELECTION_ID)
        self.assertEqual(result["selection_id"], SELECTION_ID)
        self.assertEqual(lock["artifact_sha256"], result["artifact_sha256"])
        self.assertEqual(lock["candidate_id"], result["candidate_id"])
        self.assertEqual(lock["seed"], result["seed"])
        self.assertEqual(result["candidate_identities_evaluated"], 1)
        self.assertFalse(result["runner_up_evaluated"])
        self.assertFalse(result["alternative_seed_evaluated"])
        self.assertFalse(result["threshold_tuned"])
        self.assertEqual(lock["heldout_inference_before_lock"], 0)
        self.assertEqual(result["heldout_access_state"], "CONSUMED_ONCE_FOR_M_N6_FINAL_EVALUATION")
        self.assertEqual(result["contract_id"], CONTRACT_ID)
        self.assertTrue(result["artifact_sha_unchanged"])

    def test_heldout_split_identity(self) -> None:
        if not RESULT.is_file():
            self.skipTest("heldout result not generated")
        split = json.loads(SPLIT.read_text())
        result = json.loads(RESULT.read_text())
        held = set(split["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
        train = set(split["subject_ids"]["TRAIN"])
        val = set(split["subject_ids"]["VAL"])
        self.assertEqual(len(held), 16)
        self.assertEqual(len(held & train), 0)
        self.assertEqual(len(held & val), 0)
        self.assertEqual(result["heldout_subject_count"], 16)
        self.assertEqual(result["heldout_window_count"], 74)

    def test_prediction_rows_match_windows(self) -> None:
        if not PRED.is_file():
            self.skipTest("heldout predictions not generated")
        rows = [json.loads(line) for line in PRED.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 74)
        lock = json.loads(LOCK.read_text())
        subjects = set()
        for row in rows:
            self.assertEqual(row["selected_artifact_sha256"], lock["artifact_sha256"])
            self.assertEqual(row["contract_id"], CONTRACT_ID)
            self.assertIn("probabilities", row)
            self.assertNotIn("values", row)
            subjects.add(row["subject_id"])
        self.assertEqual(len(subjects), 16)


if __name__ == "__main__":
    unittest.main()
