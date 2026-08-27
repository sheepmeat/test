"""M-PROT-4 system-level offline / replay / synthetic smoke tests.

Exercises the real MProt3IntegrationRuntime public API via MProt4SystemSmokeHarness.
Not M-PROT-5 hardware. Not final evaluation.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adapters.mmwave_m_prot_2_b23_runtime import (
    SOURCE_ARTIFACT_REL,
    SOURCE_ARTIFACT_SHA256,
    TRACE_SAMPLES,
    PrototypeFailClosed,
    verify_artifact,
)
from adapters.mmwave_m_prot_3_integration_runtime import MProt3FailClosed
from adapters.mmwave_m_prot_4_system_smoke import (
    LINEAGE_CLASS,
    MProt4SystemSmokeHarness,
    assert_no_mn9_or_direct_b23_bypass,
    make_bundle,
    phase_samples,
    samples_covering_span,
)
from adapters.mmwave_r1_sensor_independent_trace import CommonTraceOutput
from adapters.mmwave_sw01_interface_checker import Sample

ROOT = Path(__file__).resolve().parents[1]
PHYSIOLOGY_OK = {
    "PHYSIOLOGY_ELIGIBLE",
    "ABSENT",
    "QUALITY_SUPPRESSED",
    "RR_UNAVAILABLE",
}


class MProt4SystemSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = MProt4SystemSmokeHarness(root=ROOT)

    def test_a_valid_10hz(self) -> None:
        smoke = self.harness.run_case(
            case_id="A_VALID_10HZ",
            fixture_id="phase_10hz_span_29p9",
            bundles=[make_bundle(samples_covering_span(10.0))],
            expected_system_state="PHYSIOLOGY_ELIGIBLE",
            accept_observed=list(PHYSIOLOGY_OK),
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())
        self.assertEqual(smoke.r1_sample_count, TRACE_SAMPLES)
        self.assertEqual(smoke.assembled_dim, 621)
        self.assertEqual(smoke.artifact_sha256, SOURCE_ARTIFACT_SHA256)
        self.assertEqual(smoke.lineage_class, LINEAGE_CLASS)
        self.assertTrue(smoke.not_final_evaluation)
        self.assertFalse(smoke.live_hardware)
        self.assertFalse(smoke.direct_b23_bypass)
        self.assertFalse(smoke.m_n9_fallback)

    def test_b_valid_20hz(self) -> None:
        samples = samples_covering_span(20.0)
        self.assertGreater(len(samples), 300)
        smoke = self.harness.run_case(
            case_id="B_VALID_20HZ",
            fixture_id="phase_20hz_span_29p9",
            bundles=[make_bundle(samples)],
            expected_system_state="PHYSIOLOGY_ELIGIBLE",
            accept_observed=list(PHYSIOLOGY_OK),
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())
        self.assertEqual(smoke.r1_sample_count, 300)

    def test_c_multi_bundle_continuous(self) -> None:
        bundles = [
            make_bundle(phase_samples(100, t0=0.0, seq0=0)),
            make_bundle(phase_samples(120, t0=10.0, seq0=100)),
            make_bundle(phase_samples(80, t0=22.0, seq0=220)),
        ]
        smoke = self.harness.run_case(
            case_id="C_MULTI_BUNDLE",
            fixture_id="phase_10hz_three_chunks",
            bundles=bundles,
            expected_system_state="PHYSIOLOGY_ELIGIBLE",
            accept_observed=list(PHYSIOLOGY_OK),
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())
        self.assertEqual(smoke.r1_sample_count, 300)
        self.assertGreaterEqual(len(smoke.sw01_receipt_sha256_chain), 2)

    def test_d_deterministic_repeat(self) -> None:
        bundles = [make_bundle(samples_covering_span(10.0))]
        a = self.harness.run_case(
            case_id="D_REPEAT_1",
            fixture_id="phase_10hz_repeat",
            bundles=bundles,
            expected_system_state="PHYSIOLOGY_ELIGIBLE",
            accept_observed=list(PHYSIOLOGY_OK),
        )
        b = self.harness.run_case(
            case_id="D_REPEAT_2",
            fixture_id="phase_10hz_repeat",
            bundles=bundles,
            expected_system_state="PHYSIOLOGY_ELIGIBLE",
            accept_observed=list(PHYSIOLOGY_OK),
        )
        self.assertTrue(a.deterministic_pass and b.deterministic_pass)
        self.assertEqual(a.observed_system_state, b.observed_system_state)
        self.assertEqual(a.r1_sample_count, b.r1_sample_count)
        self.assertEqual(a.assembled_dim, b.assembled_dim)
        self.assertEqual(a.artifact_sha256, b.artifact_sha256)
        self.assertEqual(a.sw01_receipt_sha256_chain, b.sw01_receipt_sha256_chain)

    def test_e_sw01_fail_after_ready(self) -> None:
        self.harness.reset()
        ready = self.harness.runtime.ingest_bundle(make_bundle(samples_covering_span(10.0)))
        self.assertIn("PASS", ready["overall_status"])
        first = self.harness.runtime.try_infer(presence_gate_satisfied=True)
        self.assertIsNotNone(first.prototype_receipt)
        bad = make_bundle(
            [
                Sample(t=0.0, phase=0.1, seq=0, health_ok=True, session_id="A"),
                Sample(t=-1.0, phase=0.2, seq=1, health_ok=True, session_id="A"),
            ]
        )
        with self.assertRaises(MProt3FailClosed) as ctx:
            self.harness.runtime.ingest_bundle(bad)
        self.assertEqual(ctx.exception.code, "SOURCE_VALIDATION_FAILED")

        def _boom(*_a, **_k):
            raise AssertionError("B23 must not run after subsequent SW-01 fail")

        with mock.patch(
            "adapters.mmwave_m_prot_3_integration_runtime.run_prototype_inference",
            side_effect=_boom,
        ):
            after = self.harness.runtime.try_infer(presence_gate_satisfied=True)
        self.assertEqual(after.fail_closed_code, "SW01_ADMISSION_REQUIRED")
        self.assertIsNone(after.prototype_receipt)

    def test_f_scalar_rr_missing_phase(self) -> None:
        smoke = self.harness.run_case(
            case_id="F_SCALAR_RR",
            fixture_id="scalar_vendor_rr",
            bundles=[
                make_bundle(
                    [
                        Sample(t=0.0, phase=None, scalar_rr=16.0, seq=0, health_ok=True, session_id="A"),
                        Sample(t=0.1, phase=None, scalar_rr=16.1, seq=1, health_ok=True, session_id="A"),
                    ],
                    observation_kind="scalar_vendor_rr",
                )
            ],
            expected_system_state="SCALAR_RR_NOT_MODEL_INPUT",
            expect_ingest_fail_code="SCALAR_RR_NOT_MODEL_INPUT",
            accept_observed=["SCALAR_RR_NOT_MODEL_INPUT", "SOURCE_VALIDATION_FAILED"],
        )
        # Prefer SCALAR code; SOURCE_VALIDATION_FAILED also fail-closed OK if raised first.
        self.assertIn(
            smoke.observed_system_state,
            {"SCALAR_RR_NOT_MODEL_INPUT", "SOURCE_VALIDATION_FAILED"},
        )
        self.assertTrue(
            smoke.observed_system_state
            in {"SCALAR_RR_NOT_MODEL_INPUT", "SOURCE_VALIDATION_FAILED"}
        )

    def test_g_sequence_gap(self) -> None:
        smoke = self.harness.run_case(
            case_id="G_SEQ_GAP",
            fixture_id="seq_gap_boundary",
            bundles=[
                make_bundle(phase_samples(150, t0=0.0, seq0=0)),
                make_bundle(phase_samples(150, t0=15.0, seq0=152)),
            ],
            expected_system_state="WINDOW_NOT_READY",
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())

    def test_h_sequence_regression(self) -> None:
        smoke = self.harness.run_case(
            case_id="H_SEQ_REGRESSION",
            fixture_id="seq_regression_boundary",
            bundles=[
                make_bundle(phase_samples(150, t0=0.0, seq0=0)),
                make_bundle(phase_samples(150, t0=15.0, seq0=10)),
            ],
            expected_system_state="WINDOW_NOT_READY",
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())

    def test_i_timestamp_regression(self) -> None:
        smoke = self.harness.run_case(
            case_id="I_TS_REGRESSION",
            fixture_id="timestamp_regression_boundary",
            bundles=[
                make_bundle(phase_samples(150, t0=10.0, seq0=0)),
                make_bundle(phase_samples(150, t0=5.0, seq0=150)),
            ],
            expected_system_state="WINDOW_NOT_READY",
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())

    def test_j_large_gap(self) -> None:
        smoke = self.harness.run_case(
            case_id="J_LARGE_GAP",
            fixture_id="large_gap_boundary",
            bundles=[
                make_bundle(phase_samples(150, t0=0.0, seq0=0)),
                make_bundle(phase_samples(150, t0=20.0, seq0=150)),
            ],
            expected_system_state="WINDOW_NOT_READY",
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())

    def test_k_session_change(self) -> None:
        smoke = self.harness.run_case(
            case_id="K_SESSION_CHANGE",
            fixture_id="session_boundary",
            bundles=[
                make_bundle(phase_samples(150, t0=0.0, seq0=0, session="A")),
                make_bundle(phase_samples(150, t0=15.0, seq0=150, session="B")),
            ],
            expected_system_state="WINDOW_NOT_READY",
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())

    def test_l_reset_boundary(self) -> None:
        self.harness.reset()
        self.harness.runtime.ingest_bundle(make_bundle(samples_covering_span(10.0)))
        self.assertTrue(self.harness.runtime.composer.ready())
        self.harness.runtime.ingest_bundle(
            make_bundle(
                [
                    Sample(
                        t=40.0,
                        phase=0.1,
                        seq=0,
                        health_ok=True,
                        session_id="A",
                        reset_flag=True,
                    )
                ]
            )
        )
        receipt = self.harness.runtime.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.fail_closed_code, "WINDOW_NOT_READY")

    def test_m_window_not_ready(self) -> None:
        smoke = self.harness.run_case(
            case_id="M_WINDOW_NOT_READY",
            fixture_id="short_10hz",
            bundles=[make_bundle(phase_samples(50, rate=10.0))],
            expected_system_state="WINDOW_NOT_READY",
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())

    def test_n_below_10hz_r1_fail(self) -> None:
        smoke = self.harness.run_case(
            case_id="N_BELOW_10HZ",
            fixture_id="phase_5hz_span",
            bundles=[make_bundle(samples_covering_span(5.0))],
            expected_system_state="R1_SOURCE_RATE_BELOW_TARGET",
            accept_observed=["R1_SOURCE_RATE_BELOW_TARGET"],
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())
        self.assertTrue(str(smoke.observed_system_state).startswith("R1_"))

    def test_o_presence_unavailable(self) -> None:
        smoke = self.harness.run_case(
            case_id="O_PRESENCE_UNAVAILABLE",
            fixture_id="phase_10hz_no_presence",
            bundles=[make_bundle(samples_covering_span(10.0))],
            expected_system_state="PRESENCE_UNAVAILABLE",
            presence_gate_satisfied=False,
        )
        self.assertTrue(smoke.deterministic_pass, smoke.to_json())
        self.assertIn("LIVE_PRESENCE_SOURCE_NOT_PROVEN", smoke.presence_limitation)

    def test_p_r1_count_mismatch_injection(self) -> None:
        self.harness.reset()
        self.harness.runtime.ingest_bundle(make_bundle(samples_covering_span(10.0)))

        def _fake_adapt(_native):
            import numpy as np

            return CommonTraceOutput(
                trace=np.zeros(301, dtype=np.float64),
                time_s=np.arange(301, dtype=np.float64) / 10.0,
                validity_mask=np.ones(301, dtype=bool),
                metadata={"profile_id": "FAKE"},
            )

        with mock.patch(
            "adapters.mmwave_m_prot_3_integration_runtime.adapt_native_trace",
            side_effect=_fake_adapt,
        ):
            receipt = self.harness.runtime.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.fail_closed_code, "R1_SAMPLE_COUNT_MISMATCH")

    def test_q_artifact_identity_failure_injection(self) -> None:
        verify_artifact(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "candidate_seed_23.pt"
            shutil.copyfile(ROOT / SOURCE_ARTIFACT_REL, bad)
            data = bytearray(bad.read_bytes())
            data[0] ^= 0xFF
            bad.write_bytes(bytes(data))
            with self.assertRaises(PrototypeFailClosed) as ctx:
                verify_artifact(ROOT, artifact_path=bad)
            self.assertEqual(ctx.exception.code, "ARTIFACT_SHA_MISMATCH")

    def test_r_no_mn9_no_direct_b23(self) -> None:
        assert_no_mn9_or_direct_b23_bypass()
        tree = ast.parse((ROOT / "adapters/mmwave_m_prot_4_system_smoke.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = {a.name for a in node.names}
                self.assertNotIn("run_prototype_inference", names)
                self.assertNotIn("MMWaveInterpreter", names)


if __name__ == "__main__":
    unittest.main()
