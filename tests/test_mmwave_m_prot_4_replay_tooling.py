"""Focused tests for the standalone M-PROT-4 deterministic replay lane."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from adapters.mmwave_m_prot_3_integration_runtime import (
    MProt3FailClosed,
    MProt3IntegrationRuntime,
)
from adapters.mmwave_sw01_interface_checker import (
    MODE_FIXTURE,
    STATUS_PASS,
    evaluate_stream,
)
from tests.helpers.mmwave_m_prot_4_replay import (
    FixtureSpec,
    ReplayFixture,
    Sample,
    StreamBundle,
    fixture_spec_sha256,
    generate_fixture,
    load_fixture_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tests" / "fixtures" / "mmwave" / "m_prot_4" / "fixture_catalog.json"


class _RecordingRuntime:
    """Small caller-owned runtime double for replay ordering only."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def ingest_bundle(self, bundle: StreamBundle, *, mode: str) -> dict[str, object]:
        self.calls.append(("ingest_bundle", bundle))
        return {"overall_status": STATUS_PASS, "mode": mode}

    def try_infer(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("try_infer", kwargs))
        return {"status": "RECORDED", "kwargs": kwargs}


class MProt4ReplayToolingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.specs = load_fixture_catalog(CATALOG)
        cls.fixtures = {spec.fixture_id: generate_fixture(spec) for spec in cls.specs}

    def test_catalog_covers_all_required_cases(self) -> None:
        self.assertEqual(
            {spec.case for spec in self.specs},
            {
                "VALID_10HZ_30S",
                "VALID_20HZ_30S_MULTIBUNDLE",
                "VALID_LONGER_THAN_WINDOW",
                "INSUFFICIENT_DURATION",
                "SEQ_GAP",
                "SEQ_REGRESSION",
                "TIMESTAMP_REGRESSION",
                "LARGE_TIMESTAMP_GAP",
                "SESSION_TRANSITION",
                "RESET",
                "HEALTH_FAILURE",
                "MISSING_PHASE",
                "SCALAR_RR_ONLY",
                "IDENTITY_CHANGE",
                "CONFIGURATION_CHANGE",
                "BELOW_10HZ",
            },
        )

    def test_materialization_is_deterministic_and_path_free(self) -> None:
        for spec in self.specs:
            first = generate_fixture(spec)
            second = generate_fixture(spec)
            self.assertEqual(first.canonical_bytes, second.canonical_bytes, spec.fixture_id)
            self.assertEqual(first.fixture_sha256, second.fixture_sha256, spec.fixture_id)
            self.assertEqual(fixture_spec_sha256(spec), fixture_spec_sha256(spec))
            self.assertNotIn(b"/Users/", first.canonical_bytes)
            self.assertNotIn(b"file://", first.canonical_bytes)
            self.assertEqual(len(first.samples), first.sample_count)
            self.assertTrue(all(isinstance(sample, Sample) for sample in first.samples))
            self.assertTrue(all(isinstance(bundle, StreamBundle) for bundle in first.bundles))

    def test_semantic_spec_change_changes_fixture_sha(self) -> None:
        source = next(spec for spec in self.specs if spec.fixture_id == "valid_10hz_30s")
        changed = replace(source, seed=source.seed + 1)
        self.assertNotEqual(generate_fixture(source).fixture_sha256, generate_fixture(changed).fixture_sha256)
        # Mapping insertion order is not semantic and must not change the spec hash.
        raw = source.to_mapping()
        reordered = {key: raw[key] for key in reversed(list(raw))}
        from_mapping = FixtureSpec.from_mapping(reordered)
        self.assertEqual(fixture_spec_sha256(source), fixture_spec_sha256(from_mapping))

    def test_timing_and_bundle_partition_are_explicit(self) -> None:
        for fixture in self.fixtures.values():
            self.assertEqual(sum(fixture.bundle_partition), fixture.sample_count)
            self.assertEqual(fixture.samples[0].t, fixture.spec.start_timestamp_s)
            self.assertEqual(fixture.samples[0].seq, fixture.spec.start_seq)
        ten = self.fixtures["valid_10hz_30s"]
        self.assertEqual(ten.sample_count, 301)
        self.assertAlmostEqual(ten.samples[1].t - ten.samples[0].t, 0.1, places=12)
        self.assertAlmostEqual(ten.samples[-1].t - ten.samples[0].t, 30.0, places=12)
        twenty = self.fixtures["valid_20hz_30s_multibundle"]
        self.assertEqual(twenty.bundle_partition, (201, 200, 200))
        self.assertAlmostEqual(twenty.samples[1].t - twenty.samples[0].t, 0.05, places=12)
        self.assertAlmostEqual(twenty.samples[-1].t - twenty.samples[0].t, 30.0, places=12)
        short = self.fixtures["insufficient_duration"]
        self.assertEqual(short.sample_count, 21)
        self.assertAlmostEqual(short.duration_s, 2.0, places=12)
        low = self.fixtures["below_10hz_5hz"]
        self.assertEqual(low.sample_count, 151)
        self.assertEqual(low.sample_rate_hz, 5.0)

    def test_declared_mutations_survive_materialization(self) -> None:
        seq_gap = self.fixtures["seq_gap_multibundle"]
        self.assertEqual(seq_gap.samples[150].seq - seq_gap.samples[149].seq, 3)
        seq_reg = self.fixtures["seq_regression_multibundle"]
        self.assertEqual(seq_reg.samples[150].seq - seq_reg.samples[149].seq, -1)
        ts_reg = self.fixtures["timestamp_regression_multibundle"]
        self.assertLess(ts_reg.samples[150].t, ts_reg.samples[149].t)
        large_gap = self.fixtures["large_timestamp_gap_multibundle"]
        self.assertGreater(large_gap.samples[150].t - large_gap.samples[149].t, 0.5)
        session = self.fixtures["session_transition_multibundle"]
        self.assertNotEqual(session.samples[149].session_id, session.samples[150].session_id)
        reset = self.fixtures["reset_multibundle"]
        self.assertTrue(reset.samples[150].reset_flag)
        health = self.fixtures["health_failure_10hz"]
        self.assertFalse(health.samples[150].health_ok)
        self.assertEqual(health.samples[150].fault_code, "FIXTURE_HEALTH_DOWN")
        missing = self.fixtures["missing_phase_10hz"]
        self.assertIsNone(missing.samples[150].phase)
        scalar = self.fixtures["scalar_rr_only_10hz"]
        self.assertEqual(scalar.bundles[0].observation_kind, "scalar_vendor_rr")
        self.assertTrue(all(sample.phase is None for sample in scalar.samples))
        self.assertTrue(all(sample.scalar_rr == 16.0 for sample in scalar.samples))
        identity = self.fixtures["identity_change_multibundle"]
        self.assertNotEqual(identity.bundles[0].device_identity, identity.bundles[1].device_identity)
        configuration = self.fixtures["configuration_change_multibundle"]
        self.assertNotEqual(
            configuration.bundles[0].configuration_identity,
            configuration.bundles[1].configuration_identity,
        )

    def test_each_bundle_can_be_checked_by_sw01_without_normalization(self) -> None:
        for fixture in self.fixtures.values():
            receipts = [evaluate_stream(bundle, mode=MODE_FIXTURE) for bundle in fixture.bundles]
            if fixture.spec.case == "HEALTH_FAILURE":
                self.assertTrue(any(receipt["overall_status"] != STATUS_PASS for receipt in receipts))
            elif fixture.spec.case == "SCALAR_RR_ONLY":
                self.assertTrue(any(receipt["overall_status"] != STATUS_PASS for receipt in receipts))
            else:
                self.assertTrue(all(receipt["overall_status"] == STATUS_PASS for receipt in receipts))

    def test_replay_calls_ingest_for_every_bundle_then_try_infer(self) -> None:
        fixture = self.fixtures["valid_20hz_30s_multibundle"]
        runtime = _RecordingRuntime()
        result = fixture.replay_into(
            runtime,
            infer_kwargs={"presence_gate_satisfied": False, "lineage_class": "FIXTURE_NON_CAMPAIGN"},
        )
        self.assertIsInstance(result, object)
        self.assertEqual([name for name, _ in runtime.calls], ["ingest_bundle", "ingest_bundle", "ingest_bundle", "try_infer"])
        self.assertEqual(len(result.sw01_receipts), 3)
        self.assertEqual(result.inference_receipt["status"], "RECORDED")
        self.assertFalse(result.inference_receipt["kwargs"]["presence_gate_satisfied"])

    def test_valid_fixtures_replay_through_real_mprot3_path(self) -> None:
        for fixture_id in ("valid_10hz_30s", "valid_20hz_30s_multibundle"):
            runtime = MProt3IntegrationRuntime(root=ROOT)
            fixture = self.fixtures[fixture_id]
            result = fixture.replay_into(
                runtime,
                infer_kwargs={"presence_gate_satisfied": False, "lineage_class": "FIXTURE_NON_CAMPAIGN"},
            )
            self.assertTrue(all(receipt["overall_status"] == STATUS_PASS for receipt in result.sw01_receipts))
            self.assertTrue(result.inference_receipt.window_ready)
            self.assertEqual(result.inference_receipt.fail_closed_code, "PRESENCE_UNAVAILABLE")

    def test_boundary_mutations_do_not_bridge_temporal_history(self) -> None:
        for fixture_id in (
            "seq_gap_multibundle",
            "seq_regression_multibundle",
            "timestamp_regression_multibundle",
            "large_timestamp_gap_multibundle",
            "session_transition_multibundle",
            "reset_multibundle",
            "identity_change_multibundle",
            "configuration_change_multibundle",
        ):
            runtime = MProt3IntegrationRuntime(root=ROOT)
            fixture = self.fixtures[fixture_id]
            result = fixture.replay_into(
                runtime,
                infer_kwargs={"presence_gate_satisfied": False},
            )
            self.assertEqual(len(result.sw01_receipts), 2, fixture_id)
            self.assertFalse(runtime.composer.ready(), fixture_id)
            self.assertEqual(result.inference_receipt.fail_closed_code, "WINDOW_NOT_READY", fixture_id)

    def test_invalid_payloads_fail_closed_at_the_real_boundary(self) -> None:
        health = self.fixtures["health_failure_10hz"]
        with self.assertRaises(MProt3FailClosed) as health_error:
            health.replay_into(MProt3IntegrationRuntime(root=ROOT), infer=False)
        self.assertEqual(health_error.exception.code, "SOURCE_VALIDATION_FAILED")

        missing = self.fixtures["missing_phase_10hz"]
        with self.assertRaises(MProt3FailClosed) as missing_error:
            missing.replay_into(MProt3IntegrationRuntime(root=ROOT), infer=False)
        self.assertEqual(missing_error.exception.code, "SOURCE_ADMISSION_REJECTED")

        scalar = self.fixtures["scalar_rr_only_10hz"]
        with self.assertRaises(MProt3FailClosed) as scalar_error:
            scalar.replay_into(MProt3IntegrationRuntime(root=ROOT), infer=False)
        self.assertIn(scalar_error.exception.code, {"SOURCE_VALIDATION_FAILED", "SCALAR_RR_NOT_MODEL_INPUT"})

    def test_longer_than_window_ages_out_early_receipt(self) -> None:
        fixture = self.fixtures["valid_longer_than_window_40s"]
        runtime = MProt3IntegrationRuntime(root=ROOT)
        result = fixture.replay_into(
            runtime,
            infer_kwargs={"presence_gate_satisfied": False},
        )
        self.assertTrue(result.inference_receipt.window_ready)
        self.assertGreater(result.inference_receipt.window_start_s, 1009.9)
        self.assertNotIn(
            result.sw01_receipts[0]["receipt_sha256"],
            result.inference_receipt.sw01_receipt_sha256_chain,
        )

    def test_catalog_is_machine_readable_and_compact(self) -> None:
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(raw["schema_version"], "M_PROT_4_DETERMINISTIC_REPLAY_FIXTURE_SPEC_V1")
        self.assertLess(CATALOG.stat().st_size, 30_000)
        self.assertNotIn("samples", raw)


if __name__ == "__main__":
    unittest.main()
