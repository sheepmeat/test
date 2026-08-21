from __future__ import annotations

import unittest

from scripts.validate_mmwave_d1_2417ghz_adapter import validate


class TestMmwaveD1Evidence(unittest.TestCase):
    def test_d1_evidence_gate_passes(self) -> None:
        result = validate()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["recording_count"], 265)
        self.assertEqual(result["optional_reference_length_mismatch_count"], 16)


if __name__ == "__main__":
    unittest.main()
