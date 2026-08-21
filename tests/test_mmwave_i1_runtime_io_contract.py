#!/usr/bin/env python3
"""I1 runtime semantic I/O contract tests. No training, Q2 detectors, or I2 replay."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_I1_runtime_io_contract"
GENERATOR = ROOT / "scripts/mmwave_i1_runtime_io_contract.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_i1_runtime_io_contract.py"

from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    INPUT_CONTRACT_ID,
    OUTPUT_CONTRACT_ID,
    PROVENANCE_CONTRACT_ID,
    Q2_CONTRACT_ID,
    REPLAY_INTERFACE_ID,
    SEMANTIC_CONTRACT_ID,
    V1_FORBIDDEN_IDENTITY,
    deserialize_runtime_record,
    deterministic_runtime_window_id,
    make_output_from_input,
    resolve_precedence,
    serialize_runtime_record,
    validate_runtime_input,
    validate_runtime_output,
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


class TestMmwaveI1RuntimeIoContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.check_call(["python3", str(GENERATOR)], cwd=ROOT)
        cls.validator = subprocess.run(
            ["python3", str(VALIDATOR)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        cls.replay = load("replay_interface_skeleton.json")
        cls.public_in = cls.replay["tiny_deterministic_fixture"]["public_d0_without_phase_age_eligible"]["input"]
        cls.mr60_in = cls.replay["tiny_deterministic_fixture"]["mr60_missing_freshness_fail_closed"]["input"]

    def test_validator_pass_with_limitations(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["checks"]["PARALLEL_TRACK_BRANCH_CONTAMINATION"], "NO")
        self.assertEqual(result["checks"]["D2_USED"], "NO")
        self.assertEqual(result["checks"]["MODEL_TRAINING"], "NO")
        self.assertEqual(result["checks"]["V1_V2_MODEL_INFERENCE"], "NO")
        self.assertEqual(result["checks"]["I2_FULL_REPLAY_IMPLEMENTED"], "NO")
        self.assertEqual(result["contract_id"], SEMANTIC_CONTRACT_ID)

    def test_identities_are_v2_only(self) -> None:
        semantic = load("runtime_semantic_contract.json")
        self.assertEqual(semantic["identities"]["input"], INPUT_CONTRACT_ID)
        self.assertEqual(semantic["identities"]["output"], OUTPUT_CONTRACT_ID)
        self.assertEqual(semantic["identities"]["provenance"], PROVENANCE_CONTRACT_ID)
        self.assertEqual(semantic["identities"]["replay_interface"], REPLAY_INTERFACE_ID)
        self.assertEqual(semantic["identities"]["v1_identity_forbidden"], V1_FORBIDDEN_IDENTITY)
        self.assertNotEqual(semantic["contract_id"], V1_FORBIDDEN_IDENTITY)
        self.assertEqual(semantic["q2_relationship"]["contract_id"], Q2_CONTRACT_ID)
        self.assertFalse(semantic["q2_relationship"]["numerical_thresholds_copied_into_i1"])
        self.assertFalse(semantic["q2_relationship"]["detection_implemented_in_i1"])

    def test_presence_false_and_null_suppress_physiology(self) -> None:
        false_p = resolve_precedence(
            presence=False,
            declared_quality="PHYSIOLOGY_ELIGIBLE",
            domain_class="PRODUCTION_MR60",
            presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
        )
        null_p = resolve_precedence(
            presence=None,
            declared_quality="PHYSIOLOGY_ELIGIBLE",
            domain_class="PRODUCTION_MR60",
            presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
        )
        self.assertEqual(false_p["availability_state"], "PRESENCE_SUPPRESSED")
        self.assertFalse(false_p["physiology_executed"])
        self.assertFalse(false_p["actionable"])
        self.assertEqual(null_p["availability_state"], "PRESENCE_SUPPRESSED")
        self.assertFalse(null_p["physiology_executed"])
        self.assertIn("PRESENCE_NOT_CONFIRMED", false_p["reason_codes"])

    def test_quality_unavailable_and_eligible_boundary(self) -> None:
        unavailable = resolve_precedence(
            presence=True,
            declared_quality="INPUT_UNAVAILABLE",
            reason_codes=["LARGE_GAP"],
            domain_class="PRODUCTION_MR60",
            production_freshness_present=True,
            presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
        )
        eligible = resolve_precedence(
            presence=True,
            declared_quality="PHYSIOLOGY_ELIGIBLE",
            domain_class="PRODUCTION_MR60",
            production_freshness_present=True,
            presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
        )
        self.assertEqual(unavailable["availability_state"], "INPUT_UNAVAILABLE")
        self.assertFalse(unavailable["physiology_executed"])
        self.assertFalse(unavailable["physiology_boundary_entered"])
        self.assertEqual(eligible["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertTrue(eligible["physiology_boundary_entered"])
        self.assertFalse(eligible["physiology_executed"])
        self.assertEqual(eligible["inference_boundary"], "NOT_IMPLEMENTED_MODEL_BOUNDARY")

    def test_class_confidence_cannot_override_invalid_availability(self) -> None:
        result = resolve_precedence(
            presence=True,
            declared_quality="INPUT_UNAVAILABLE",
            reason_codes=["SOURCE_STALE"],
            class_confidence=0.99,
            proposed_physiology="APNEA",
            domain_class="PRODUCTION_MR60",
            production_freshness_present=True,
            presence_applicability="REQUIRED_FOR_PRODUCTION_MR60",
        )
        self.assertTrue(result["class_confidence_override_rejected"])
        self.assertFalse(result["physiology_executed"])
        self.assertIn("INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY", result["schema_errors"])
        self.assertNotEqual(result["application_state"], "APNEA_PROXY_CANDIDATE")

    def test_public_without_phase_age_is_not_rejected(self) -> None:
        errors = validate_runtime_input(self.public_in)
        self.assertEqual(errors, [])
        output = make_output_from_input(self.public_in)
        self.assertEqual(output["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertEqual(self.public_in["freshness"]["phase_age_ms"]["value"], None)
        self.assertEqual(
            self.public_in["freshness"]["phase_age_ms"]["applicability"],
            "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
        )
        self.assertEqual(validate_runtime_output(output, self.public_in), [])

    def test_production_mr60_missing_freshness_fail_closed_representation(self) -> None:
        errors = validate_runtime_input(self.mr60_in)
        self.assertEqual(errors, [])
        output = make_output_from_input(self.mr60_in)
        self.assertEqual(output["availability_state"], "INPUT_UNAVAILABLE")
        self.assertFalse(output["physiology_executed"])
        self.assertIn("SOURCE_STALE", output["reason_codes"])
        claimed_eligible = json.loads(json.dumps(self.mr60_in))
        claimed_eligible["quality"]["declared_availability_state"] = "PHYSIOLOGY_ELIGIBLE"
        claimed_eligible["quality"]["reason_codes"] = []
        claimed_eligible["model_input_boundary"]["eligible_for_physiological_inference"] = True
        claimed_eligible["model_input_boundary"]["not_for_physiological_inference"] = False
        self.assertIn(
            "PRODUCTION_MR60_MISSING_FRESHNESS_CANNOT_BE_ELIGIBLE",
            validate_runtime_input(claimed_eligible),
        )

    def test_provenance_and_deterministic_window_id(self) -> None:
        public_id = self.public_in["provenance"]["runtime_window_id"]
        expected = deterministic_runtime_window_id(
            {
                "event_id": self.public_in["event"]["event_id"],
                "recording_id": self.public_in["session"]["recording_id"],
                "session_id": self.public_in["session"]["session_id"],
                "source_id": self.public_in["source"]["source_id"],
                "window_end": self.public_in["timestamps"]["window_end"]["value"],
                "window_start": self.public_in["timestamps"]["window_start"]["value"],
            }
        )
        self.assertEqual(public_id, expected)
        self.assertTrue(public_id.startswith("runtime_window:"))
        self.assertEqual(self.public_in["provenance"]["software_git_sha"], load("runtime_semantic_contract.json")["base_sha"])
        self.assertIsNone(self.public_in["provenance"]["synthetic_corruption_profile_id"])
        self.assertNotEqual(
            self.mr60_in["provenance"]["transport_record_id"],
            self.mr60_in["provenance"]["runtime_window_id"],
        )
        blob = json.dumps(self.public_in) + json.dumps(self.mr60_in)
        self.assertNotRegex(blob, r"/Users/|file://|/private/tmp/")

    def test_serialize_roundtrip_and_mock_boundary(self) -> None:
        text = serialize_runtime_record(self.public_in)
        restored = deserialize_runtime_record(text)
        self.assertEqual(restored, self.public_in)
        output = make_output_from_input(self.public_in)
        self.assertEqual(output["schema_id"], OUTPUT_CONTRACT_ID)
        self.assertEqual(output["inference_kind"], "MockInferenceResult")
        self.assertEqual(output["breathing_evidence"]["status"], "not_evaluated")
        self.assertIsNone(output["rr"]["value"])
        self.assertEqual(output["rr"]["confidence"]["component"], "rr")
        self.assertNotIn("confidence", [key for key, value in output.items() if key == "confidence"])


if __name__ == "__main__":
    unittest.main()
