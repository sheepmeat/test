#!/usr/bin/env python3
"""
Unit tests for Phase A0 mmWave Raw Dataset Inventory Audit.
Tests checksum computation, zip integrity checks, deterministic ID generation,
role classification, recording linkage, and error handling.
"""

import os
import sys
import json
import tempfile
import zipfile
import unittest

# Add scripts directory to path to import audit functions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
import audit_mmwave_raw_inventory as audit


class TestMMWaveRawInventoryAudit(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_streaming_checksums(self):
        """Verify streaming SHA-256 and MD5 computation against known data."""
        tmp_file = os.path.join(self.test_dir.name, "sample.bin")
        content = b"SafeNest Phase A0 Audit Test Content"
        with open(tmp_file, "wb") as f:
            f.write(content)

        sha256, md5 = audit.compute_streaming_checksums(tmp_file)
        self.assertEqual(len(sha256), 64)
        self.assertEqual(len(md5), 32)

    def test_derive_ids(self):
        """Verify deterministic ID generation algorithm."""
        d_id, a_id, subj_id, sess_id, rec_id, src_id = audit.derive_ids(
            "10.5281/zenodo.18599983", "f0bcfdac94f88b43bb34d3da8e8f071a787291f86c97798059b8dbf4d4be08b0",
            "P001", "Sitting", "Rest", "db_records/P001/Sitting/Rest/radar_rFFTs.zlib"
        )

        self.assertTrue(d_id.startswith("dataset-"))
        self.assertTrue(a_id.startswith("archive-sha256-"))
        self.assertEqual(subj_id, "dataset-10_5281_zenodo_18599983-p001")
        self.assertEqual(sess_id, "dataset-10_5281_zenodo_18599983-p001-session-01")
        self.assertEqual(rec_id, "dataset-10_5281_zenodo_18599983-p001-sitting-rest")
        self.assertTrue(src_id.startswith("file-"))

    def test_classify_member_role(self):
        """Verify classification of dataset file roles."""
        role, ev = audit.classify_member_role("db_records/P001/Sitting/Rest/radar_rFFTs.zlib")
        self.assertEqual(role, "RADAR_DATA")
        self.assertEqual(ev, "DIRECT_FILE_METADATA")

        role, ev = audit.classify_member_role("db_records/P001/Sitting/Rest/radar_timestamps.csv")
        self.assertEqual(role, "RADAR_TIMESTAMP")

        role, ev = audit.classify_member_role("db_records/P001/Sitting/Rest/radar_chirpConfig.json")
        self.assertEqual(role, "CHIRP_CONFIG")

        role, ev = audit.classify_member_role("db_records/P001/Sitting/Rest/movesense_ecg.csv")
        self.assertEqual(role, "REFERENCE_SIGNAL")

        role, ev = audit.classify_member_role("db_records/P001/Sitting/Rest/non_breathing_ts.csv")
        self.assertEqual(role, "ANNOTATION")

        role, ev = audit.classify_member_role("__MACOSX/._db_records")
        self.assertEqual(role, "AUXILIARY")

        role, ev = audit.classify_member_role("db_records/P001/Sitting/Rest/unknown_data.bin")
        self.assertEqual(role, "UNKNOWN")

    def test_zip_integrity_clean(self):
        """Test zip integrity audit on a clean mock archive."""
        zip_path = os.path.join(self.test_dir.name, "clean.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test_dir/", "")
            zf.writestr("test_dir/file1.txt", "hello")
            zf.writestr("test_dir/file2.json", "{}")

        res = audit.audit_zip_integrity(zip_path, verify_crc=True)
        self.assertTrue(res["zip_openable"])
        self.assertEqual(res["member_count"], 3)
        self.assertEqual(res["crc_failure_count"], 0)
        self.assertEqual(res["path_traversal_risk_count"], 0)
        self.assertEqual(res["zip_integrity_status"], "PASS")

    def test_zip_integrity_traversal_detection(self):
        """Test detection of path traversal risks in zip archive."""
        zip_path = os.path.join(self.test_dir.name, "traversal.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../dangerous.txt", "bad content")

        res = audit.audit_zip_integrity(zip_path, verify_crc=False)
        self.assertEqual(res["path_traversal_risk_count"], 1)
        self.assertEqual(res["zip_integrity_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
