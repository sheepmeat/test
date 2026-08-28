"""Focused tests for the B6R-RC1 Thermal-90 remediation contract."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_thermal_b6r_rc1 import DEFAULT_CONTRACT, validate_contract


class ThermalB6RRC1ContractTests(unittest.TestCase):
    def _mutated_contract(self, mutate) -> Path:
        value = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        mutate(value)
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        directory = Path(temporary_directory.name)
        path = directory / "contract.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_frozen_contract_passes(self) -> None:
        result = validate_contract()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["identity_approval_status"], "EVIDENCE_PENDING_OWNER_ACCEPTANCE")

    def test_mi48_equivalence_self_promotion_fails(self) -> None:
        path = self._mutated_contract(lambda value: value["identity_decision"].update({"equivalent_to_mi48_claimed": True}))
        self.assertEqual(validate_contract(path)["status"], "FAIL")

    def test_existing_s000_holdout_promotion_fails(self) -> None:
        path = self._mutated_contract(lambda value: value["holdout_contract"].update({"existing_s000_eligible_for_locked_holdout": True}))
        self.assertEqual(validate_contract(path)["status"], "FAIL")

    def test_frame_random_split_fails(self) -> None:
        def mutate(value) -> None:
            value["capture_waves"]["wave_b_role_separated_acquisition"]["frame_random_split_allowed"] = True

        self.assertEqual(validate_contract(self._mutated_contract(mutate))["status"], "FAIL")

    def test_absolute_path_leak_fails(self) -> None:
        path = self._mutated_contract(lambda value: value.update({"debug_path": "C:\\Users\\example\\sessions"}))
        codes = {item["code"] for item in validate_contract(path)["errors"]}
        self.assertIn("NONPORTABLE_PATH", codes)

    def test_contract_hash_is_stable_across_crlf_checkout(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        path = Path(temporary_directory.name) / "contract.json"
        path.write_bytes(DEFAULT_CONTRACT.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(
            validate_contract(path)["contract_sha256"],
            validate_contract(DEFAULT_CONTRACT)["contract_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
