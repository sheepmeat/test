"""Focused tests for the M-PROT-4 SmokeReceipt evidence contract."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mmwave.validate_m_prot_4_smoke_evidence import (
    B23_ARTIFACT_SHA256,
    B23_ARTIFACT_PATH,
    B23_PARAMETER_SHA256,
    B23_SCALER_PATH,
    B23_SCALER_SHA256,
    R1_PROFILE,
    SCHEMA_ID,
    SCHEMA_PATH,
    SCHEMA_VERSION,
    SW01_PASS_STATUS,
    WIRING_RECEIPT_VERSION,
    WINDOW_CONTRACT,
    _main,
    validate_schema_document,
    validate_smoke_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_A = "a" * 64
RECEIPT_B = "b" * 64
RECEIPT_NONCONTRIBUTING = "c" * 64
FIXTURE_SHA = "d" * 64


def valid_receipt() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "M-PROT-4",
        "wiring_receipt_version": WIRING_RECEIPT_VERSION,
        "case_id": "SMOKE-FIXTURE-B23-001",
        "case_class": "FIXTURE_SMOKE",
        "input_fixture_id": "M_PROT_4_FIXTURE_001",
        "input_fixture_reference": "fixtures/mmwave/m_prot_4/smoke_case_001.json",
        "input_fixture_sha256": FIXTURE_SHA,
        "expected_outcome": "PROTOTYPE_REACHED",
        "observed_outcome": "PHYSIOLOGY_ELIGIBLE",
        "source": {
            "device_identity": "M_PROT_4_FIXTURE_DEVICE",
            "interface_identity": "fixture:json",
            "configuration_identity": "M_PROT_4_CFG_V1",
            "observation_kind": "near_raw_phase",
        },
        "sw01": {
            "overall_status": SW01_PASS_STATUS,
            "source_validation_status": SW01_PASS_STATUS,
            "sw01_receipt_sha256": RECEIPT_B,
            "contributing_receipt_sha256_chain": [RECEIPT_A, RECEIPT_B],
            "sw01_receipt_sha256_chain": [RECEIPT_A, RECEIPT_B],
            "latest_receipt_semantics": "LATEST_CONTRIBUTING_PASS_RECEIPT",
            "chain_semantics": "ORDERED_UNIQUE_ADJACENT_COLLAPSED_CONTRIBUTING_PASS_RECEIPTS_FOR_SELECTED_WINDOW_ONLY",
            "noncontributing_receipt_sha256": [RECEIPT_NONCONTRIBUTING],
            "session_id": "M_PROT_4_FIXTURE_SESSION_001",
        },
        "window": {
            "contract": WINDOW_CONTRACT,
            "causal_past_only": True,
            "ready": True,
            "start": 0.0,
            "end": 29.9,
            "window_start_s": 0.0,
            "window_end_s": 29.9,
            "source_sample_count": 300,
        },
        "r1": {
            "profile": R1_PROFILE,
            "sample_count": 300,
            "r1_sample_count": 300,
            "status": "PASS",
        },
        "presence": {
            "status": "PRESENCE_GATE_SATISFIED",
            "gate_satisfied": True,
        },
        "prototype": {
            "reached": True,
            "panel_id": "B23",
            "artifact_path": B23_ARTIFACT_PATH,
            "artifact_sha256": B23_ARTIFACT_SHA256,
            "parameter_sha256": B23_PARAMETER_SHA256,
            "scaler_path": B23_SCALER_PATH,
            "scaler_sha256": B23_SCALER_SHA256,
            "representation": "PYTORCH_FLOAT32_STATE_DICT",
            "result_status": "PHYSIOLOGY_ELIGIBLE",
            "fail_closed_code": None,
        },
        "lineage_class": "FIXTURE_NON_CAMPAIGN",
        "flags": {
            "PROTOTYPE_INTEGRATION_ONLY": True,
            "NOT_FINAL_SELECTED_MODEL": True,
            "NOT_DEPLOYMENT_VALIDATED": True,
            "NOT_SAFETY_VALIDATED": True,
            "NOT_CLINICAL_VALIDATION": True,
            "FINAL_GOVERNED_EVALUATION": False,
            "D1_ADMISSIBLE": False,
            "LIVE_HARDWARE": False,
        },
        "track_f": {
            "d1_present": 57,
            "d1_absent": 0,
            "d1_membership": "BLOCKED_INVALID_FINAL_MEMBERSHIP",
            "m_pv38": "RESOURCE_BLOCKED_CLOSED",
            "m_pv38_evaluation": "NOT_EXECUTED",
            "m_pv4": "UNAUTHORIZED",
            "d2": "LOCKED",
        },
    }


def unavailable_receipt() -> dict:
    receipt = valid_receipt()
    receipt["expected_outcome"] = "PROTOTYPE_REACHED"
    receipt["observed_outcome"] = "FAIL_CLOSED"
    receipt["sw01"] = {
        "overall_status": SW01_PASS_STATUS,
        "source_validation_status": SW01_PASS_STATUS,
        "sw01_receipt_sha256": None,
        "contributing_receipt_sha256_chain": [],
        "sw01_receipt_sha256_chain": [],
        "latest_receipt_semantics": "LATEST_CONTRIBUTING_PASS_RECEIPT",
        "chain_semantics": "ORDERED_UNIQUE_ADJACENT_COLLAPSED_CONTRIBUTING_PASS_RECEIPTS_FOR_SELECTED_WINDOW_ONLY",
        "noncontributing_receipt_sha256": [],
        "session_id": None,
    }
    receipt["window"] = {
        "contract": WINDOW_CONTRACT,
        "causal_past_only": True,
        "ready": False,
        "start": None,
        "end": None,
        "window_start_s": None,
        "window_end_s": None,
        "source_sample_count": 0,
    }
    receipt["r1"] = {
        "profile": R1_PROFILE,
        "sample_count": 0,
        "r1_sample_count": 0,
        "status": "NOT_REACHED",
    }
    receipt["presence"] = {
        "status": "PRESENCE_UNAVAILABLE",
        "gate_satisfied": False,
    }
    receipt["prototype"] = {
        **receipt["prototype"],
        "reached": False,
        "result_status": "NOT_REACHED",
        "fail_closed_code": "WINDOW_NOT_READY",
    }
    return receipt


class MProt4SmokeEvidenceTest(unittest.TestCase):
    def assert_invalid(self, receipt: dict, text: str) -> None:
        errors = validate_smoke_receipt(receipt)
        self.assertTrue(errors, receipt)
        self.assertTrue(any(text in error for error in errors), errors)

    def test_schema_document_is_frozen_and_portable(self) -> None:
        self.assertEqual(validate_schema_document(), [])
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], SCHEMA_ID)
        self.assertFalse(schema["$defs"]["flags"]["properties"]["D1_ADMISSIBLE"]["const"])

    def test_valid_reached_receipt_is_accepted(self) -> None:
        self.assertEqual(validate_smoke_receipt(valid_receipt()), [])

    def test_valid_fail_closed_receipt_is_accepted(self) -> None:
        self.assertEqual(validate_smoke_receipt(unavailable_receipt()), [])

    def test_v3_status_and_version_cannot_be_downgraded(self) -> None:
        downgraded_status = valid_receipt()
        downgraded_status["sw01"]["overall_status"] = "PASS"
        downgraded_status["sw01"]["source_validation_status"] = "PASS"
        self.assert_invalid(downgraded_status, "sw01.overall_status: unsupported status")

        downgraded_version = valid_receipt()
        downgraded_version["wiring_receipt_version"] = "M-PROT-3-WIRING-RECEIPT-V2"
        self.assert_invalid(downgraded_version, "M-PROT-3 V3 provenance is required")

    def test_wrong_or_missing_frozen_b23_identity_is_rejected(self) -> None:
        wrong_artifact = valid_receipt()
        wrong_artifact["prototype"]["artifact_sha256"] = "0" * 64
        self.assert_invalid(wrong_artifact, "wrong or missing frozen B23 artifact SHA-256")

        missing_artifact = valid_receipt()
        del missing_artifact["prototype"]["artifact_sha256"]
        self.assert_invalid(missing_artifact, "prototype.artifact_sha256: wrong or missing")

        wrong_scaler = valid_receipt()
        wrong_scaler["prototype"]["scaler_sha256"] = "0" * 64
        self.assert_invalid(wrong_scaler, "wrong or missing frozen scaler SHA-256")

        missing_scaler = valid_receipt()
        del missing_scaler["prototype"]["scaler_sha256"]
        self.assert_invalid(missing_scaler, "prototype.scaler_sha256: wrong or missing")

    def test_final_d1_and_live_hardware_promotions_are_rejected(self) -> None:
        for field in ("FINAL_GOVERNED_EVALUATION", "D1_ADMISSIBLE", "LIVE_HARDWARE"):
            receipt = valid_receipt()
            receipt["flags"][field] = True
            self.assert_invalid(receipt, f"flags.{field}: must be false")

        final_lineage = valid_receipt()
        final_lineage["lineage_class"] = "FINAL_GOVERNED_EVALUATION"
        self.assert_invalid(final_lineage, "forbidden final/scientific promotion value")

    def test_malformed_receipt_chain_and_noncontributor_claim_are_rejected(self) -> None:
        duplicate = valid_receipt()
        duplicate["sw01"]["contributing_receipt_sha256_chain"] = [RECEIPT_A, RECEIPT_A]
        duplicate["sw01"]["sw01_receipt_sha256_chain"] = [RECEIPT_A, RECEIPT_A]
        self.assert_invalid(duplicate, "malformed duplicate receipt chain")

        mismatched_alias = valid_receipt()
        mismatched_alias["sw01"]["sw01_receipt_sha256_chain"] = [RECEIPT_A]
        self.assert_invalid(mismatched_alias, "must preserve sw01_receipt_sha256_chain exactly")

        wrong_latest = valid_receipt()
        wrong_latest["sw01"]["sw01_receipt_sha256"] = RECEIPT_A
        self.assert_invalid(wrong_latest, "latest sw01 receipt must be the final contributing receipt")

        claimed_noncontributor = valid_receipt()
        claimed_noncontributor["sw01"]["noncontributing_receipt_sha256"] = [RECEIPT_A]
        self.assert_invalid(claimed_noncontributor, "must not be claimed in the contributing chain")

    def test_missing_fixture_sha_and_absolute_local_paths_are_rejected(self) -> None:
        missing_fixture_sha = valid_receipt()
        del missing_fixture_sha["input_fixture_sha256"]
        self.assert_invalid(missing_fixture_sha, "input_fixture_sha256: must be lowercase")

        absolute_fixture = valid_receipt()
        absolute_fixture["input_fixture_reference"] = "/Users/example/smoke.json"
        self.assert_invalid(absolute_fixture, "input_fixture_reference: must be repository-relative")

        home_relative = valid_receipt()
        home_relative["prototype"]["artifact_path"] = "~/models/candidate_seed_23.pt"
        self.assert_invalid(home_relative, "receipt.prototype.artifact_path")

        drive_path = valid_receipt()
        drive_path["input_fixture_reference"] = "C:\\captures\\smoke.json"
        self.assert_invalid(drive_path, "input_fixture_reference: must be repository-relative")

    def test_reached_state_requires_all_m_prot_3_prerequisites(self) -> None:
        source_fail = valid_receipt()
        source_fail["sw01"]["overall_status"] = "FAIL_REQUIRED_FIELD_MISSING"
        source_fail["sw01"]["source_validation_status"] = "FAIL_REQUIRED_FIELD_MISSING"
        self.assert_invalid(source_fail, "M-PROT-3 V3 prerequisites")

        window_unavailable = valid_receipt()
        window_unavailable["window"] = unavailable_receipt()["window"]
        self.assert_invalid(window_unavailable, "M-PROT-3 V3 prerequisites")

        presence_unavailable = valid_receipt()
        presence_unavailable["presence"] = {
            "status": "PRESENCE_UNAVAILABLE",
            "gate_satisfied": False,
        }
        self.assert_invalid(presence_unavailable, "prerequisites are unavailable")

        r1_short = valid_receipt()
        r1_short["r1"]["sample_count"] = 299
        r1_short["r1"]["r1_sample_count"] = 299
        self.assert_invalid(r1_short, "prerequisites are unavailable")

    def test_physiology_success_cannot_be_claimed_when_unavailable(self) -> None:
        for field, value in (
            ("sw01", {**unavailable_receipt()["sw01"], "overall_status": "LIVE_TARGET_UNAVAILABLE", "source_validation_status": "LIVE_TARGET_UNAVAILABLE"}),
            ("window", unavailable_receipt()["window"]),
            ("presence", unavailable_receipt()["presence"]),
        ):
            receipt = unavailable_receipt()
            receipt["observed_outcome"] = "PHYSIOLOGY_SUCCESS"
            receipt["prototype"]["result_status"] = "PHYSIOLOGY_SUCCESS"
            receipt["prototype"]["reached"] = True
            receipt[field] = value
            receipt["prototype"]["fail_closed_code"] = None
            self.assert_invalid(receipt, "physiology success")

    def test_non_final_lineage_variants_are_explicit(self) -> None:
        for case_class, lineage in (
            ("FIXTURE_SMOKE", "FIXTURE_NON_CAMPAIGN"),
            ("OFFLINE_REPLAY_SMOKE", "OFFLINE_REPLAY_NON_CAMPAIGN"),
            ("SYNTHETIC_SMOKE", "SYNTHETIC_SMOKE_NON_CAMPAIGN"),
        ):
            receipt = valid_receipt()
            receipt["case_class"] = case_class
            receipt["lineage_class"] = lineage
            self.assertEqual(validate_smoke_receipt(receipt), [])

        track_f_promotion = valid_receipt()
        track_f_promotion["track_f"]["d1_absent"] = 57
        self.assert_invalid(track_f_promotion, "track_f.d1_absent: must preserve Track F value")

    def test_cli_validates_case_and_schema_without_runtime_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_path = Path(temp_dir) / "smoke_receipt.json"
            case_path.write_text(json.dumps(valid_receipt()), encoding="utf-8")
            self.assertEqual(_main(["validate", "--case-file", str(case_path)]), 0)
            self.assertEqual(_main(["validate-schema", "--schema-file", str(SCHEMA_PATH)]), 0)

            invalid = copy.deepcopy(valid_receipt())
            invalid["flags"]["D1_ADMISSIBLE"] = True
            case_path.write_text(json.dumps(invalid), encoding="utf-8")
            self.assertEqual(_main(["validate", "--case-file", str(case_path)]), 2)


if __name__ == "__main__":
    unittest.main()
