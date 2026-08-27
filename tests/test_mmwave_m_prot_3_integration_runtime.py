"""Focused M-PROT-3 wiring tests (not M-PROT-4 system smoke).

Corrective round: no production SW-01 bypass; time-coverage windows; lazy model load.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from adapters.mmwave_m_prot_2_b23_runtime import (
    CANONICAL_PARAMETER_SHA256,
    INPUT_DIM,
    SOURCE_ARTIFACT_REL,
    SOURCE_ARTIFACT_SHA256,
    TRACE_SAMPLES,
    PrototypeFailClosed,
    verify_artifact,
)
from adapters.mmwave_m_prot_3_integration_runtime import (
    TARGET_SPAN_S,
    CausalTemporalComposer,
    MProt3FailClosed,
    MProt3IntegrationRuntime,
    assert_no_mn9_imports,
)
from adapters.mmwave_r1_sensor_independent_trace import CommonTraceOutput, R1TraceError
from adapters.mmwave_sw01_interface_checker import Sample, StreamBundle

ROOT = Path(__file__).resolve().parents[1]


def _header_meta(**kw):
    meta = {
        "device_identity": "M_PROT_3_FIXTURE_DEVICE",
        "interface_identity": "fixture:json",
        "configuration_identity": "M_PROT_3_CFG",
        "observation_kind": "near_raw_phase",
    }
    meta.update(kw)
    return meta


def _phase_samples(
    n: int,
    rate: float = 10.0,
    session: str = "A",
    t0: float = 0.0,
    *,
    seq0: int = 0,
    reset_at: int | None = None,
):
    samples = []
    for i in range(n):
        t = t0 + i / rate
        samples.append(
            Sample(
                t=t,
                phase=float(np.sin(2 * np.pi * 0.25 * t)),
                seq=seq0 + i,
                health_ok=True,
                session_id=session,
                reset_flag=(reset_at is not None and i == reset_at),
            )
        )
    return samples


def _bundle(samples, **meta_kw) -> StreamBundle:
    meta = _header_meta(**meta_kw)
    return StreamBundle(
        device_identity=meta["device_identity"],
        interface_identity=meta["interface_identity"],
        configuration_identity=meta["configuration_identity"],
        observation_kind=meta["observation_kind"],
        samples=list(samples),
    )


def _samples_covering_span(rate: float, span_s: float = TARGET_SPAN_S, session: str = "A", t0: float = 0.0):
    """Build a contiguous phase stream whose first→last span is exactly span_s."""
    n = int(round(span_s * rate)) + 1
    return _phase_samples(n, rate=rate, session=session, t0=t0)


class MProt3WiringCorrectiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rt = MProt3IntegrationRuntime(root=ROOT)
        # Intentionally do NOT ensure_runtime() here — lazy-load tests rely on that.

    def test_a_10hz_happy_path(self) -> None:
        samples = _samples_covering_span(10.0)
        self.assertEqual(len(samples), 300)
        src = self.rt.ingest_bundle(_bundle(samples))
        self.assertEqual(src["overall_status"], "PASS_NON_CAMPAIGN_INTERFACE_CHECK")
        receipt = self.rt.try_infer(presence_gate_satisfied=True, lineage_class="FIXTURE_NON_CAMPAIGN")
        self.assertTrue(receipt.window_ready)
        self.assertEqual(receipt.r1_sample_count, TRACE_SAMPLES)
        self.assertEqual(receipt.assembled_dim, INPUT_DIM)
        self.assertEqual(receipt.artifact_sha256, SOURCE_ARTIFACT_SHA256)
        self.assertEqual(receipt.parameter_sha256, CANONICAL_PARAMETER_SHA256)
        self.assertIsNotNone(receipt.prototype_receipt)
        self.assertEqual(receipt.prototype_receipt["panel_id"], "B23")
        self.assertFalse(receipt.prototype_receipt.get("apnea_emitted", True))
        self.assertTrue(receipt.provisional_integration_freeze)
        self.assertIn(receipt.status, {"PHYSIOLOGY_ELIGIBLE", "ABSENT", "QUALITY_SUPPRESSED", "RR_UNAVAILABLE"})

    def test_b_20hz_happy_path_r1_downsamples(self) -> None:
        samples = _samples_covering_span(20.0)
        # ~30 s at 20 Hz is far more than 300 source samples.
        self.assertGreater(len(samples), 300)
        self.assertAlmostEqual(samples[-1].t - samples[0].t, TARGET_SPAN_S, places=9)
        src = self.rt.ingest_bundle(_bundle(samples))
        self.assertEqual(src["overall_status"], "PASS_NON_CAMPAIGN_INTERFACE_CHECK")
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertTrue(receipt.window_ready)
        self.assertGreater(receipt.source_sample_count or 0, 300)
        self.assertEqual(receipt.r1_sample_count, 300)
        self.assertEqual(receipt.assembled_dim, 621)
        self.assertIsNotNone(receipt.prototype_receipt)

    def test_c_insufficient_duration_not_count(self) -> None:
        # 300 samples @ 20 Hz ≈ 14.95 s — lots of samples, insufficient time coverage.
        self.rt.ingest_bundle(_bundle(_phase_samples(300, rate=20.0)))
        self.assertFalse(self.rt.composer.ready())
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.status, "WINDOW_NOT_READY")
        self.assertEqual(receipt.fail_closed_code, "WINDOW_NOT_READY")
        self.assertIsNone(receipt.prototype_receipt)

    def test_d_unvalidated_cannot_infer(self) -> None:
        # No ingest / no binding — production path cannot reach B23.
        self.assertIsNone(getattr(self.rt, "push_sample", None))
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.fail_closed_code, "SW01_ADMISSION_REQUIRED")
        self.assertIsNone(receipt.prototype_receipt)
        # Composer used in isolation does not create a production inference route.
        composer = CausalTemporalComposer()
        for s in _samples_covering_span(10.0):
            composer.push(s, admission_id=99, receipt_sha256="fixture-sha")
        self.assertTrue(composer.ready())
        self.rt.composer = composer
        receipt2 = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt2.fail_closed_code, "SW01_ADMISSION_REQUIRED")

    def test_e_failed_sw01_does_not_populate(self) -> None:
        samples = [
            Sample(t=0.0, phase=0.1, seq=0, health_ok=True, session_id="A"),
            Sample(t=-1.0, phase=0.2, seq=1, health_ok=True, session_id="A"),
        ]
        with self.assertRaises(MProt3FailClosed) as ctx:
            self.rt.ingest_bundle(_bundle(samples))
        self.assertEqual(ctx.exception.code, "SOURCE_VALIDATION_FAILED")
        self.assertEqual(self.rt.composer.buffered_count, 0)
        self.assertIsNone(self.rt._validated_binding)
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.fail_closed_code, "SW01_ADMISSION_REQUIRED")

    def test_f_session_change_flush(self) -> None:
        self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0, session="A")))
        self.assertTrue(self.rt.composer.ready())
        self.rt.ingest_bundle(_bundle(_phase_samples(50, session="B", t0=100.0)))
        self.assertFalse(self.rt.composer.ready())
        self.assertLess(self.rt.composer.buffered_count, 300)

    def test_g_reset_flush(self) -> None:
        self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0, session="A")))
        self.assertTrue(self.rt.composer.ready())
        reset_bundle = _bundle(
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
        self.rt.ingest_bundle(reset_bundle)
        self.assertFalse(self.rt.composer.ready())

    def test_h_large_gap_no_bridge(self) -> None:
        samples = _phase_samples(100, session="A")
        samples.append(Sample(t=50.0, phase=0.2, seq=100, health_ok=True, session_id="A"))
        for i in range(1, 50):
            samples.append(
                Sample(t=50.0 + i * 0.1, phase=0.2, seq=100 + i, health_ok=True, session_id="A")
            )
        # May fail SW-01 due to large gap — either way must not bridge into a ready window.
        try:
            self.rt.ingest_bundle(_bundle(samples))
        except MProt3FailClosed as exc:
            self.assertEqual(exc.code, "SOURCE_VALIDATION_FAILED")
            self.assertEqual(self.rt.composer.buffered_count, 0)
            return
        self.assertFalse(self.rt.composer.ready())
        self.assertLess(self.rt.composer.buffered_count, 300)

    def test_i_scalar_rr_rejected(self) -> None:
        samples = [
            Sample(t=0.0, phase=None, scalar_rr=16.0, seq=0, health_ok=True, session_id="A"),
            Sample(t=0.1, phase=None, scalar_rr=16.1, seq=1, health_ok=True, session_id="A"),
        ]
        with self.assertRaises(MProt3FailClosed) as ctx:
            self.rt.ingest_bundle(_bundle(samples, observation_kind="scalar_vendor_rr"))
        self.assertIn(ctx.exception.code, {"SCALAR_RR_NOT_MODEL_INPUT", "SOURCE_VALIDATION_FAILED"})
        self.assertEqual(self.rt.composer.buffered_count, 0)

    def test_j_below_10hz_r1_failure(self) -> None:
        # Sufficient duration at 5 Hz; SW-01 may PASS, R1 must fail closed (no upsample).
        samples = _samples_covering_span(5.0)
        self.rt.ingest_bundle(_bundle(samples))
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.status, "UNAVAILABLE")
        self.assertTrue(str(receipt.fail_closed_code).startswith("R1_"))
        self.assertIsNone(receipt.prototype_receipt)

    def test_k_r1_count_mismatch_no_trim(self) -> None:
        self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0)))

        def _fake_adapt(native):
            trace = np.zeros(301, dtype=np.float64)
            time_s = np.arange(301, dtype=np.float64) / 10.0
            return CommonTraceOutput(
                trace=trace,
                time_s=time_s,
                validity_mask=np.ones(301, dtype=bool),
                metadata={"profile_id": "FAKE"},
            )

        with mock.patch(
            "adapters.mmwave_m_prot_3_integration_runtime.adapt_native_trace",
            side_effect=_fake_adapt,
        ):
            receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.fail_closed_code, "R1_SAMPLE_COUNT_MISMATCH")
        self.assertEqual(receipt.r1_sample_count, 301)
        self.assertIsNone(receipt.prototype_receipt)

    def test_l_presence_unavailable(self) -> None:
        self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0)))
        receipt = self.rt.try_infer(presence_gate_satisfied=None)
        self.assertEqual(receipt.fail_closed_code, "PRESENCE_UNAVAILABLE")
        self.assertIsNone(receipt.prototype_receipt)

    def test_m_lazy_load_window_not_ready(self) -> None:
        self.rt.ingest_bundle(_bundle(_phase_samples(50, rate=10.0)))

        def _boom():
            raise AssertionError("ensure_runtime must not be called for WINDOW_NOT_READY")

        with mock.patch.object(self.rt, "ensure_runtime", side_effect=_boom):
            receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.fail_closed_code, "WINDOW_NOT_READY")

    def test_n_lazy_load_presence_unavailable(self) -> None:
        self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0)))

        def _boom():
            raise AssertionError("ensure_runtime must not be called for PRESENCE_UNAVAILABLE")

        with mock.patch.object(self.rt, "ensure_runtime", side_effect=_boom):
            receipt = self.rt.try_infer(presence_gate_satisfied=False)
        self.assertEqual(receipt.fail_closed_code, "PRESENCE_UNAVAILABLE")

    def test_o_wrong_artifact_rejected(self) -> None:
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

    def test_p_no_mn9_fallback(self) -> None:
        assert_no_mn9_imports()
        tree = ast.parse((ROOT / "adapters/mmwave_m_prot_3_integration_runtime.py").read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported.append(ast.dump(node))
        blob = "\n".join(imported)
        self.assertNotIn("mmwave_interpreter", blob)
        self.assertNotIn("MMWaveInterpreter", blob)
        src = (ROOT / "adapters/mmwave_m_prot_3_integration_runtime.py").read_text()
        self.assertNotIn("require_sw01_pass", src)
        self.assertNotIn("def push_sample", src)

    def test_q_portable_source_provenance(self) -> None:
        src = self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0)))
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.device_identity, "M_PROT_3_FIXTURE_DEVICE")
        self.assertEqual(receipt.interface_identity, "fixture:json")
        self.assertEqual(receipt.configuration_identity, "M_PROT_3_CFG")
        self.assertEqual(receipt.observation_kind, "near_raw_phase")
        self.assertEqual(receipt.source_validation_status, src["overall_status"])
        self.assertEqual(receipt.sw01_receipt_sha256, src["receipt_sha256"])
        self.assertEqual(list(receipt.sw01_receipt_sha256_chain), [src["receipt_sha256"]])
        self.assertIsNotNone(receipt.window_start_s)
        self.assertIsNotNone(receipt.window_end_s)
        self.assertEqual(receipt.session_id, "A")
        self.assertNotIn("/Users/", str(receipt.to_json()))

    def test_composer_unit_time_coverage(self) -> None:
        composer = CausalTemporalComposer()
        for s in _phase_samples(300, rate=20.0):
            composer.push(s, admission_id=1, receipt_sha256="a")
        self.assertFalse(composer.ready())
        composer2 = CausalTemporalComposer()
        for s in _samples_covering_span(20.0):
            composer2.push(s, admission_id=1, receipt_sha256="b")
        self.assertTrue(composer2.ready())
        window = composer2.select_causal_source_suffix()
        self.assertGreaterEqual(window[-1].t - window[0].t, TARGET_SPAN_S * 0.98)

    # --- Corrective Round 2 ---

    def test_r2_a_pass_ready_then_sw01_fail_invalidates(self) -> None:
        self.rt.ingest_bundle(_bundle(_samples_covering_span(10.0)))
        ready = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertIsNotNone(ready.prototype_receipt)
        bad = [
            Sample(t=0.0, phase=0.1, seq=0, health_ok=True, session_id="A"),
            Sample(t=-1.0, phase=0.2, seq=1, health_ok=True, session_id="A"),
        ]
        with self.assertRaises(MProt3FailClosed) as ctx:
            self.rt.ingest_bundle(_bundle(bad))
        self.assertEqual(ctx.exception.code, "SOURCE_VALIDATION_FAILED")
        self.assertEqual(self.rt.composer.buffered_count, 0)
        self.assertIsNone(self.rt._validated_binding)
        self.assertIsNone(self.rt._boundary)

        def _boom(*_a, **_k):
            raise AssertionError("B23 must not run after subsequent SW-01 fail")

        with mock.patch(
            "adapters.mmwave_m_prot_3_integration_runtime.run_prototype_inference",
            side_effect=_boom,
        ):
            after = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(after.fail_closed_code, "SW01_ADMISSION_REQUIRED")
        self.assertIsNone(after.prototype_receipt)

    def test_r2_b_cross_bundle_valid_continuation(self) -> None:
        # Unequal chunk sizes so SW-01 receipt SHAs differ (receipt hashes metadata).
        a = self.rt.ingest_bundle(_bundle(_phase_samples(100, t0=0.0, seq0=0)))
        b = self.rt.ingest_bundle(_bundle(_phase_samples(120, t0=10.0, seq0=100)))
        c = self.rt.ingest_bundle(_bundle(_phase_samples(80, t0=22.0, seq0=220)))
        self.assertNotEqual(a["receipt_sha256"], b["receipt_sha256"])
        self.assertNotEqual(b["receipt_sha256"], c["receipt_sha256"])
        self.assertTrue(self.rt.composer.ready())
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.r1_sample_count, 300)
        self.assertEqual(
            list(receipt.sw01_receipt_sha256_chain),
            [a["receipt_sha256"], b["receipt_sha256"], c["receipt_sha256"]],
        )
        self.assertEqual(receipt.sw01_receipt_sha256, c["receipt_sha256"])

    def test_r2_c_seq_gap_no_bridge(self) -> None:
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=0.0, seq0=0)))
        self.assertGreater(self.rt.composer.buffered_count, 100)
        # Internally continuous B, but boundary skips seq 150,151
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=15.0, seq0=152)))
        self.assertEqual(self.rt.composer.buffered_count, 150)
        self.assertFalse(self.rt.composer.ready())

    def test_r2_d_seq_regression_no_bridge(self) -> None:
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=0.0, seq0=0)))
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=15.0, seq0=10)))
        self.assertEqual(self.rt.composer.buffered_count, 150)
        self.assertFalse(self.rt.composer.ready())

    def test_r2_e_timestamp_regression_no_bridge(self) -> None:
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=10.0, seq0=0)))
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=5.0, seq0=150)))
        self.assertEqual(self.rt.composer.buffered_count, 150)
        self.assertFalse(self.rt.composer.ready())

    def test_r2_f_large_gap_no_bridge(self) -> None:
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=0.0, seq0=0)))
        # dt from last (14.9) to first of B (20.0) = 5.1 > 0.5
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=20.0, seq0=150)))
        self.assertEqual(self.rt.composer.buffered_count, 150)
        self.assertFalse(self.rt.composer.ready())

    def test_r2_g_session_change_no_bridge(self) -> None:
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=0.0, seq0=0, session="A")))
        self.rt.ingest_bundle(_bundle(_phase_samples(150, t0=15.0, seq0=150, session="B")))
        self.assertEqual(self.rt.composer.buffered_count, 150)
        self.assertFalse(self.rt.composer.ready())

    def test_r2_h_noncontributing_receipt_excluded(self) -> None:
        early = self.rt.ingest_bundle(_bundle(_phase_samples(100, t0=0.0, seq0=0)))
        # Continue to span well beyond 29.9 s so early samples fall outside causal suffix.
        mid = self.rt.ingest_bundle(_bundle(_phase_samples(200, t0=10.0, seq0=100)))
        late = self.rt.ingest_bundle(_bundle(_phase_samples(201, t0=30.0, seq0=300)))
        receipt = self.rt.try_infer(presence_gate_satisfied=True)
        self.assertEqual(receipt.r1_sample_count, 300)
        chain = list(receipt.sw01_receipt_sha256_chain)
        self.assertNotIn(early["receipt_sha256"], chain)
        self.assertIn(late["receipt_sha256"], chain)
        # Mid may or may not contribute depending on exact suffix start; late must.
        self.assertTrue(len(chain) >= 1)
        self.assertEqual(receipt.sw01_receipt_sha256, chain[-1])
        # Absolute paths forbidden
        self.assertNotIn("/Users/", str(receipt.to_json()))
        # Ensure early truly outside window
        self.assertGreater(receipt.window_start_s or 0.0, 9.9)


if __name__ == "__main__":
    unittest.main()
