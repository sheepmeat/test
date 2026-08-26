"""Focused fail-closed tests for the SW-02 nine-slot artifact tooling."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from scripts.mmwave import m_pv38_absent_artifact_generator as generator


ROOT = Path(__file__).resolve().parents[1]


class SW02ArtifactGeneratorTests(unittest.TestCase):
    def fixture(self):
        predeclaration = generator.generate_fixture_predeclaration(ROOT)
        receipts = generator.generate_fixture_receipts(predeclaration, ROOT)
        return predeclaration, receipts

    def assert_error(self, code, function):
        with self.assertRaises(generator.ArtifactValidationError) as context:
            function()
        self.assertIn(code, str(context.exception))

    def test_exact_nine_slot_fixture_and_three_by_three_order(self):
        predeclaration, receipts = self.fixture()
        result = generator.validate_predeclaration(predeclaration, ROOT, require_fixture=True)
        self.assertEqual(result["slot_count"], 9)
        self.assertEqual(result["lineage_group_count"], 3)
        self.assertEqual(
            result["orders_by_group"],
            {
                "D1_PERSON_03": [1, 2, 3],
                "D1_PERSON_09": [1, 2, 3],
                "D1_PERSON_11": [1, 2, 3],
            },
        )
        receipt_result = generator.validate_receipts(predeclaration, receipts, ROOT)
        self.assertTrue(receipt_result["complete_binding"])
        self.assertEqual(receipt_result["receipt_count"], 9)

    def test_fixture_semantics_and_non_campaign_state_are_preserved(self):
        predeclaration, receipts = self.fixture()
        self.assertEqual(predeclaration["semantics"], generator.FIXTURE_SEMANTICS)
        self.assertEqual(receipts["semantics"], generator.FIXTURE_SEMANTICS)
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temporary:
            result = generator.build_fixture_bundle(Path(temporary) / "bundle", ROOT)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["real_campaign_predeclaration_created"])
            self.assertFalse(result["real_slot_consumed"])
            self.assertEqual(result["d1_membership_entries_created"], 0)

    def test_duplicate_slot_rejected(self):
        predeclaration, _ = self.fixture()
        mutated = copy.deepcopy(predeclaration)
        mutated["slots"][1]["recording_slot_id"] = mutated["slots"][0]["recording_slot_id"]
        self.assert_error(
            "DUPLICATE_RECORDING_SLOT_ID",
            lambda: generator.validate_predeclaration(mutated, ROOT, require_fixture=True),
        )

    def test_missing_slot_rejected(self):
        predeclaration, _ = self.fixture()
        mutated = copy.deepcopy(predeclaration)
        mutated["slots"].pop()
        self.assert_error(
            "SLOT_COUNT_MISMATCH",
            lambda: generator.validate_predeclaration(mutated, ROOT, require_fixture=True),
        )

    def test_wrong_lineage_or_order_rejected(self):
        predeclaration, _ = self.fixture()
        wrong_lineage = copy.deepcopy(predeclaration)
        wrong_lineage["slots"][0]["acquisition_lineage_group_id"] = "D1_PERSON_09"
        self.assert_error(
            "LINEAGE_SLOT_COUNT_MISMATCH",
            lambda: generator.validate_predeclaration(wrong_lineage, ROOT, require_fixture=True),
        )

        wrong_order = copy.deepcopy(predeclaration)
        wrong_order["slots"][0]["recording_order"] = 2
        wrong_order["slots"][0]["context_quota"] = 6
        self.assert_error(
            "LINEAGE_ORDER_MISMATCH",
            lambda: generator.validate_predeclaration(wrong_order, ROOT, require_fixture=True),
        )

    def test_duplicate_planned_id_rejected(self):
        predeclaration, _ = self.fixture()
        mutated = copy.deepcopy(predeclaration)
        mutated["slots"][1]["planned_recording_id"] = mutated["slots"][0]["planned_recording_id"]
        self.assert_error(
            "DUPLICATE_PLANNED_RECORDING_ID",
            lambda: generator.validate_predeclaration(mutated, ROOT, require_fixture=True),
        )

    def test_duplicate_actual_id_rejected(self):
        predeclaration, receipts = self.fixture()
        mutated = copy.deepcopy(receipts)
        first = mutated["receipts"][0]
        second = mutated["receipts"][1]
        second["actual_recording_identifier"] = first["actual_recording_identifier"]
        second["file_metadata"]["actual_recording_identifier"] = first["actual_recording_identifier"]
        second["source_provenance"]["actual_recording_identifier"] = first["actual_recording_identifier"]
        self.assert_error(
            "DUPLICATE_ACTUAL_RECORDING_ID",
            lambda: generator.validate_receipts(predeclaration, mutated, ROOT),
        )

    def test_bad_hash_rejected(self):
        predeclaration, receipts = self.fixture()
        mutated = copy.deepcopy(receipts)
        mutated["receipts"][0]["sha256"] = "g" * 64
        self.assert_error(
            "INVALID_SHA256",
            lambda: generator.validate_receipts(predeclaration, mutated, ROOT),
        )

    def test_missing_and_extra_receipts_rejected(self):
        predeclaration, receipts = self.fixture()
        missing = copy.deepcopy(receipts)
        missing["receipts"].pop()
        self.assert_error(
            "MISSING_PLANNED_RECEIPT",
            lambda: generator.validate_receipts(predeclaration, missing, ROOT),
        )

        extra = copy.deepcopy(receipts)
        extra_receipt = copy.deepcopy(extra["receipts"][0])
        extra_receipt["planned_recording_id"] = "FIXTURE_PLANNED_UNPLANNED"
        extra_receipt["source_provenance"]["planned_recording_id"] = "FIXTURE_PLANNED_UNPLANNED"
        extra["receipts"].append(extra_receipt)
        self.assert_error(
            "EXTRA_UNPLANNED_ACTUAL_RECORDING",
            lambda: generator.validate_receipts(predeclaration, extra, ROOT),
        )

    def test_wrong_planned_actual_binding_rejected(self):
        predeclaration, receipts = self.fixture()
        mutated = copy.deepcopy(receipts)
        mutated["receipts"][0]["source_provenance"]["planned_recording_id"] = "FIXTURE_PLANNED_09"
        self.assert_error(
            "WRONG_PLANNED_ACTUAL_BINDING",
            lambda: generator.validate_receipts(predeclaration, mutated, ROOT),
        )

    def test_receipt_before_identity_lock_rejected(self):
        predeclaration, receipts = self.fixture()
        mutated = copy.deepcopy(predeclaration)
        del mutated["creation_timestamp"]
        self.assert_error(
            "PREDECLARATION_IDENTITY_LOCK_REQUIRED",
            lambda: generator.validate_receipts(mutated, receipts, ROOT),
        )

    def test_identical_fixture_inputs_are_byte_stable(self):
        first_pre, first_rec = self.fixture()
        second_pre, second_rec = self.fixture()
        self.assertEqual(generator.canonical_json_bytes(first_pre), generator.canonical_json_bytes(second_pre))
        self.assertEqual(generator.canonical_json_bytes(first_rec), generator.canonical_json_bytes(second_rec))

    def test_generator_does_not_add_a_runtime_timestamp(self):
        predeclaration, _ = self.fixture()
        self.assertEqual(predeclaration["creation_timestamp"], "2026-08-27T00:00:00Z")
        self.assertTrue(all(slot["creation_timestamp"] == predeclaration["creation_timestamp"] for slot in predeclaration["slots"]))

    def test_fixture_bundle_validator_accepts_generated_bundle(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temporary:
            manifest_dir = Path(temporary) / "bundle"
            generator.build_fixture_bundle(manifest_dir, ROOT)
            result = generator.validate_fixture_bundle(ROOT, manifest_dir)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["terminal_verdict"], "SW02_IMPLEMENTED_FIXTURE_VALIDATED")


if __name__ == "__main__":
    unittest.main()
