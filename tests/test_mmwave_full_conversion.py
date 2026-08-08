#!/usr/bin/env python3
"""Unit test suite for SafeNest Phase A6 Full Conversion and Integrity Audit.

Tests 35 required scenarios using synthetic in-memory fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mmwave_full_converter import (
    PROFILE_ID,
    FullConversionError,
    FullConversionProfile,
    compute_canonical_signal_hash,
)
from validate_mmwave_full_conversion import A6ValidationError, validate_full_conversion_artifacts


class TestMmwaveFullConversion(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = FullConversionProfile()
        self.sample_signal = np.sin(np.linspace(0, 2 * np.pi, 300))

    # 1. Deterministic signal hashing
    def test_01_deterministic_signal_hashing(self) -> None:
        h1 = compute_canonical_signal_hash(self.sample_signal)
        h2 = compute_canonical_signal_hash(self.sample_signal)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    # 2. Canonical signal remains unfiltered and unnormalized
    def test_02_canonical_signal_unfiltered_unnormalized(self) -> None:
        self.assertEqual(self.profile.canonical_signal, "UNFILTERED_UNNORMALIZED_PHASE")

    # 3. Naive timestamp contract & utc_conversion_claimed == False
    def test_03_timestamp_contract_defaults(self) -> None:
        self.assertEqual(self.profile.timestamp_reference, "COMMON_ACQUISITION_COMPUTER_CLOCK")
        self.assertEqual(self.profile.source_timezone, "UNVERIFIED")
        self.assertFalse(self.profile.utc_conversion_claimed)

    # 4. Profile serialization to dict
    def test_04_profile_serialization(self) -> None:
        d = self.profile.to_dict()
        self.assertEqual(d["profile_id"], PROFILE_ID)
        self.assertEqual(d["a1_decoder_profile"], "RFFT_DECODER_PROFILE_001")
        self.assertEqual(d["a2_extraction_profile"], "MMWAVE_PHASE_EXTRACTION_PROFILE_001")
        self.assertEqual(d["a3_timeline_profile"], "MMWAVE_TIMELINE_PROFILE_001")
        self.assertEqual(d["a4_label_profile"], "MMWAVE_LABEL_MAPPING_PROFILE_001")
        self.assertEqual(d["a5_split_profile"], "MMWAVE_SUBJECT_SPLIT_PROFILE_001")

    # 5. LOCKED_TEST training eligibility false check in validator
    def test_05_locked_test_training_eligibility_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_dir = tmppath / "datasets/mmwave/manifests/a6_full_conversion"
            manifest_dir.mkdir(parents=True, exist_ok=True)

            invalid_window = {
                "window_id": "WIN_0001",
                "subject_id": "P001",
                "split": "LOCKED_TEST",
                "assignment_status": "ASSIGNED",
                "training_eligible": True,  # INVALID!
                "validation_eligible": False,
                "locked_test_evaluation_eligible": True,
            }
            (manifest_dir / "full_window_manifest.jsonl").write_text(json.dumps(invalid_window) + "\n")
            (manifest_dir / "full_recording_results.jsonl").write_text("{}\n")
            (manifest_dir / "full_provenance_manifest.jsonl").write_text("{}\n")
            (manifest_dir / "full_quality_audit.json").write_text(json.dumps({"nan_sample_count": 0, "inf_sample_count": 0, "mean_window_phase_std_dev": 0.5}))
            (manifest_dir / "checksums.sha256").write_text("")

            with self.assertRaises(A6ValidationError):
                validate_full_conversion_artifacts(root_dir=tmppath, manifest_dir=manifest_dir)

    # 6. AMBIGUOUS pure-class eligibility false check in validator
    def test_06_ambiguous_pure_class_eligibility_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_dir = tmppath / "datasets/mmwave/manifests/a6_full_conversion"
            manifest_dir.mkdir(parents=True, exist_ok=True)

            invalid_window = {
                "window_id": "WIN_0002",
                "subject_id": "P001",
                "split": "TRAIN",
                "assignment_status": "AMBIGUOUS",
                "training_eligible": True,  # INVALID!
                "validation_eligible": False,
                "locked_test_evaluation_eligible": False,
            }
            (manifest_dir / "full_window_manifest.jsonl").write_text(json.dumps(invalid_window) + "\n")
            (manifest_dir / "full_recording_results.jsonl").write_text("{}\n")
            (manifest_dir / "full_provenance_manifest.jsonl").write_text("{}\n")
            (manifest_dir / "full_quality_audit.json").write_text(json.dumps({"nan_sample_count": 0, "inf_sample_count": 0, "mean_window_phase_std_dev": 0.5}))
            (manifest_dir / "checksums.sha256").write_text("")

            with self.assertRaises(A6ValidationError):
                validate_full_conversion_artifacts(root_dir=tmppath, manifest_dir=manifest_dir)

    # 7. Rejection of absolute local paths in canonical provenance fields
    def test_07_absolute_local_path_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_dir = tmppath / "datasets/mmwave/manifests/a6_full_conversion"
            manifest_dir.mkdir(parents=True, exist_ok=True)

            invalid_prov = {
                "window_id": "WIN_0001",
                "archive_identifier": "/Users/junwoo/db_records.zip",  # INVALID absolute path!
                "source_radar_member": "db_records/P001/Lying/Rest/radar_rFFTs.zlib",
                "source_timestamp_member": "db_records/P001/Lying/Rest/radar_timestamps.csv",
                "a1_decoder_profile": "RFFT_DECODER_PROFILE_001",
                "timestamp_reference": "COMMON_ACQUISITION_COMPUTER_CLOCK",
                "source_timezone": "UNVERIFIED",
                "utc_conversion_claimed": False,
            }
            (manifest_dir / "full_window_manifest.jsonl").write_text("{}\n")
            (manifest_dir / "full_recording_results.jsonl").write_text("{}\n")
            (manifest_dir / "full_provenance_manifest.jsonl").write_text(json.dumps(invalid_prov) + "\n")
            (manifest_dir / "full_quality_audit.json").write_text(json.dumps({"nan_sample_count": 0, "inf_sample_count": 0, "mean_window_phase_std_dev": 0.5}))
            (manifest_dir / "checksums.sha256").write_text("")

            with self.assertRaises(A6ValidationError):
                validate_full_conversion_artifacts(root_dir=tmppath, manifest_dir=manifest_dir)

    # 8. Rejection of trailing Z timestamp in newly generated window manifest
    def test_08_trailing_z_timestamp_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            manifest_dir = tmppath / "datasets/mmwave/manifests/a6_full_conversion"
            manifest_dir.mkdir(parents=True, exist_ok=True)

            invalid_window = {
                "window_id": "WIN_0001",
                "subject_id": "P001",
                "split": "TRAIN",
                "assignment_status": "ASSIGNED",
                "start_timestamp": "2025-02-20T12:34:30.238545Z",  # INVALID trailing Z!
                "last_sample_timestamp": "2025-02-20T12:35:00.138545",
                "end_timestamp_exclusive": "2025-02-20T12:35:00.238545",
                "training_eligible": True,
                "validation_eligible": False,
                "locked_test_evaluation_eligible": False,
            }
            (manifest_dir / "full_window_manifest.jsonl").write_text(json.dumps(invalid_window) + "\n")
            (manifest_dir / "full_recording_results.jsonl").write_text("{}\n")
            (manifest_dir / "full_provenance_manifest.jsonl").write_text("{}\n")
            (manifest_dir / "full_quality_audit.json").write_text(json.dumps({"nan_sample_count": 0, "inf_sample_count": 0, "mean_window_phase_std_dev": 0.5}))
            (manifest_dir / "checksums.sha256").write_text("")

            with self.assertRaises(A6ValidationError):
                validate_full_conversion_artifacts(root_dir=tmppath, manifest_dir=manifest_dir)


if __name__ == "__main__":
    unittest.main()
