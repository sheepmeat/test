from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from scripts.benchmark_thermal_b6r_p3_rpi import (
    DEFAULT_CONTRACT,
    build_replay_manifest,
    compare_outputs,
    load_contract,
    load_fixture,
    not_measured_target_evidence,
    prepare_replay_input,
    statistics,
)


ROOT = Path(__file__).resolve().parents[1]


class B6RP3ReplayBenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract(DEFAULT_CONTRACT)

    def test_contract_freezes_identity_boundary_and_tolerance(self) -> None:
        self.assertEqual(self.contract["stage_id"], "B6R-P3")
        self.assertEqual(
            self.contract["p2_artifact"]["sha256"],
            "f88d65d76dbb21862e1f3cdff17cefb038a432047ded6ac8d5563bc8bc8c52ff",
        )
        self.assertEqual(self.contract["p2_artifact"]["input_shape"], [1, 62, 80, 1])
        self.assertEqual(self.contract["p2_artifact"]["output_shape"], [1, 3])
        self.assertEqual(self.contract["p2_artifact"]["quantization"], "NONE")
        self.assertEqual(
            self.contract["determinism"]["predefined_tolerances"]["definition_timing"],
            "defined_before_B6R-P3_target_measurement",
        )
        self.assertFalse(self.contract["deployment_boundary"]["default_activation"])
        self.assertFalse(self.contract["deployment_boundary"]["safety_authority"])
        self.assertFalse(self.contract["locked_test_policy"]["path_configured"])

    def test_prepare_replay_input_preserves_canonical_tensor_contract(self) -> None:
        frame = np.zeros((62, 80, 1), dtype=np.float32)
        prepared = prepare_replay_input(frame)
        self.assertEqual(prepared.shape, (1, 62, 80, 1))
        self.assertEqual(prepared.dtype, np.float32)
        self.assertTrue(prepared.flags.c_contiguous)
        with self.assertRaises(ValueError):
            prepare_replay_input(np.full((62, 80), np.nan, dtype=np.float32))
        with self.assertRaises(ValueError):
            prepare_replay_input(np.full((62, 80), 2.0, dtype=np.float32))

    def test_statistics_reports_required_percentiles(self) -> None:
        result = statistics([float(value) for value in range(1, 101)])
        self.assertEqual(result["count"], 100)
        self.assertEqual(result["median"], result["p50"])
        self.assertAlmostEqual(result["p95"], 95.05)
        self.assertAlmostEqual(result["p99"], 99.01)
        self.assertEqual(result["min"], 1.0)
        self.assertEqual(result["max"], 100.0)

    def test_determinism_comparison_uses_predefined_strict_tolerance(self) -> None:
        tolerance = self.contract["determinism"]["predefined_tolerances"]
        reference = np.array([[0.1, 0.8, 0.1], [0.7, 0.2, 0.1]], dtype=np.float32)
        self.assertTrue(compare_outputs(reference, reference.copy(), tolerance)["passed"])
        changed = reference.copy()
        changed[0, 1] += 2e-6
        self.assertFalse(compare_outputs(reference, changed, tolerance)["passed"])

    def test_replay_fixture_is_exactly_inherited_from_p2_development(self) -> None:
        fixture = load_fixture(self.contract)
        replay = build_replay_manifest(self.contract, fixture)
        p2 = json.loads(
            (ROOT / "datasets/thermal/manifests/B6R-P2_public_sdt_fp32_tflite_export/parity_manifest.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(replay["role"], "DEVELOPMENT")
        self.assertEqual(replay["sample_count"], 48)
        self.assertEqual(replay["locked_public_test_access_count"], 0)
        self.assertEqual(
            [sample["sample_id"] for sample in replay["samples"]],
            [sample["sample_id"] for sample in p2["samples"]],
        )
        self.assertEqual(replay["canonical_fixture_sha256"], fixture.canonical_fixture_sha256)

    def test_blocked_evidence_never_invents_target_numbers(self) -> None:
        evidence = not_measured_target_evidence(self.contract)
        self.assertEqual(evidence["target_status"], "BLOCKED_HARDWARE")
        self.assertEqual(evidence["target_measurement_status"], "NOT_MEASURED_ON_TARGET")
        for stage in ("preprocessing_ingress_ms", "inference_ms", "total_ms"):
            self.assertTrue(
                all(
                    value == "NOT_MEASURED_ON_TARGET"
                    for value in evidence["statistics"][stage].values()
                )
            )


if __name__ == "__main__":
    unittest.main()
