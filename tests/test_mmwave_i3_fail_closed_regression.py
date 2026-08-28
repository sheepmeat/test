#!/usr/bin/env python3
"""I3 fail-closed regression tests. No training, Q3 metrics, D2, or model inference."""

from __future__ import annotations

import json
import math
import subprocess
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_I3_fail_closed_regression"
GENERATOR = ROOT / "scripts/mmwave_i3_fail_closed_regression.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_i3_fail_closed_regression.py"

from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    make_output_from_input,
    resolve_precedence,
)
from scripts.mmwave_i2_jsonl_replay import (  # noqa: E402
    I1_REPLAY_SKELETON,
    SessionReplayState,
    replay_parsed_rows,
)
from scripts.mmwave_i3_fail_closed_regression import (  # noqa: E402
    I3_CONTRACT_ID,
    I3_GATE_ID,
    I3_MATRIX_ID,
    declared_quality_from_q2,
    envelope_for_case,
    resolve_i3_envelope,
)
from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    apply_timing_corruption,
    load_profile as load_q1_profile,
)
from scripts.mmwave_q2_input_unavailable import (  # noqa: E402
    Q1_PROFILE_PATH,
    apply_quality_corruption,
    evaluate_availability,
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


class TestMmwaveI3FailClosedRegression(unittest.TestCase):
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
        cls.q1 = load_q1_profile(Q1_PROFILE_PATH)
        cls.t = np.arange(256, dtype=np.float64) * 100.0
        cls.x = np.sin(np.linspace(0.0, 6.0 * math.pi, 256))
        cls.labels = np.array(["NORMAL"] * 256)

    def test_validator_pass_with_limitations(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["contract_id"], I3_CONTRACT_ID)
        self.assertEqual(result["i3_integration_lane_complete"], "YES")
        self.assertEqual(result["checks"]["Q2_THRESHOLD_FORK"], "NO")
        self.assertEqual(result["checks"]["MODEL_INFERENCE"], "NO")
        self.assertEqual(result["checks"]["D2_USED"], "NO")
        self.assertEqual(result["checks"]["Q3_PERFORMED"], "NO")

    def test_identities(self) -> None:
        contract = load("i3_regression_contract.json")
        self.assertEqual(contract["contract_id"], I3_CONTRACT_ID)
        self.assertEqual(contract["matrix_id"], I3_MATRIX_ID)
        self.assertEqual(contract["gate_id"], I3_GATE_ID)
        self.assertFalse(contract["q2_threshold_fork"])
        self.assertEqual(
            contract["dependencies"]["q2_evaluator"],
            "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1",
        )

    def test_a_presence_false(self) -> None:
        evaluation = evaluate_availability(self.t, self.x, presence=False)
        resolved = resolve_i3_envelope(evaluation, presence=False, domain_class="PRODUCTION_MR60")
        self.assertEqual(resolved["availability_state"], "PRESENCE_SUPPRESSED")
        self.assertFalse(resolved["physiology_executed"])

    def test_b_production_presence_unknown(self) -> None:
        evaluation = evaluate_availability(self.t, self.x, presence=None)
        resolved = resolve_i3_envelope(evaluation, presence=None, domain_class="PRODUCTION_MR60")
        self.assertEqual(resolved["availability_state"], "PRESENCE_SUPPRESSED")

    def test_c_true_large_gap(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="LARGE_GAP", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("LARGE_GAP", result["evaluation"]["reasons"])
        self.assertFalse(result["evaluation"]["interpolation_applied"])

    def test_d_true_source_freeze(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="SOURCE_FREEZE", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_FREEZE", result["evaluation"]["reasons"])

    def test_e_true_stale(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="STALE_SOURCE", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_STALE", result["evaluation"]["reasons"])

    def test_f_true_exact_flat(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="FLAT_EXACT", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SIGNAL_FLAT_EXACT", result["evaluation"]["reasons"])

    def test_g_tiny_dynamic_signal(self) -> None:
        tiny = 1e-5 * np.sin(np.linspace(0.0, 10.0 * math.pi, 256))
        evaluation = evaluate_availability(self.t, tiny, presence=True)
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertNotIn("SIGNAL_FLAT_EXACT", evaluation["reasons"])

    def test_h_invalid_non_monotonic_timestamp(self) -> None:
        broken = self.t.copy()
        broken[20] = broken[18]
        evaluation = evaluate_availability(broken, self.x, presence=True)
        self.assertEqual(evaluation["availability_state"], "INPUT_UNAVAILABLE")
        self.assertTrue(
            "TIMESTAMP_NON_MONOTONIC" in evaluation["reasons"]
            or "TIMESTAMP_UNRESOLVED" in evaluation["reasons"]
        )
        self.assertFalse(evaluation["interpolation_applied"])

    def test_i_missing_production_freshness(self) -> None:
        evaluation = evaluate_availability(
            self.t, self.x, presence=True, timing_context="PRODUCTION_MR60"
        )
        self.assertEqual(evaluation["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_STALE", evaluation["reasons"])

    def test_j_public_offline_freshness_not_required(self) -> None:
        evaluation = evaluate_availability(
            self.t, self.x, presence=True, timing_context="PUBLIC_NATIVE"
        )
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        fixture = json.loads(I1_REPLAY_SKELETON.read_text(encoding="utf-8"))
        public = fixture["tiny_deterministic_fixture"]["public_d0_without_phase_age_eligible"]["input"]
        output = make_output_from_input(public)
        self.assertEqual(output["availability_state"], "PHYSIOLOGY_ELIGIBLE")

    def test_k_seq_increment_while_stale(self) -> None:
        age = np.full(32, 500.0)
        t = np.arange(32, dtype=np.float64) * 100.0
        x = np.sin(np.linspace(0.0, math.pi, 32))
        first = evaluate_availability(t, x, source_update_ms=t, phase_age_ms=age, presence=True)
        second = evaluate_availability(t, x, source_update_ms=t, phase_age_ms=age, presence=True)
        self.assertEqual(first["availability_state"], "INPUT_UNAVAILABLE")
        self.assertEqual(second["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_STALE", second["reasons"])

    def test_l_isolated_republication(self) -> None:
        src = self.t[:32].copy()
        values = self.x[:32].copy()
        src[10] = src[9]
        values[10] = values[9]
        evaluation = evaluate_availability(self.t[:32], values, source_update_ms=src, presence=True)
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertNotIn("SOURCE_FREEZE", evaluation["reasons"])

    def test_m_persistent_freeze(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="REPUBLICATION_TO_FREEZE", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_FREEZE", result["evaluation"]["reasons"])

    def test_n_presence_false_plus_bad_quality(self) -> None:
        result = apply_quality_corruption(
            self.t,
            self.x,
            mode="LARGE_GAP",
            seed=1,
            labels=self.labels,
            q1_profile=self.q1,
            presence=False,
        )
        resolved = resolve_i3_envelope(
            result["evaluation"], presence=False, domain_class="PRODUCTION_MR60"
        )
        self.assertEqual(resolved["availability_state"], "PRESENCE_SUPPRESSED")
        self.assertNotEqual(resolved["availability_state"], "INPUT_UNAVAILABLE")

    def test_o_unavailable_plus_fake_confidence(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="LARGE_GAP", seed=1, labels=self.labels, q1_profile=self.q1
        )
        resolved = resolve_i3_envelope(
            result["evaluation"],
            presence=True,
            domain_class="SYNTHETIC_CORRUPTION",
            class_confidence=0.99,
            proposed_physiology="NORMAL",
        )
        self.assertEqual(resolved["availability_state"], "INPUT_UNAVAILABLE")
        self.assertFalse(resolved["physiology_executed"])
        self.assertTrue(resolved["class_confidence_override_rejected"])

    def test_p_invalid_to_normal_impossible(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="STALE_SOURCE", seed=1, labels=self.labels, q1_profile=self.q1
        )
        resolved = resolve_i3_envelope(
            result["evaluation"],
            presence=True,
            proposed_physiology="NORMAL",
            class_confidence=0.9,
        )
        self.assertNotEqual(resolved["application_state"], "RESPIRATION_PRESENT")
        self.assertIn("INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY", resolved["schema_errors"])

    def test_q_invalid_to_apnea_impossible(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="FLAT_EXACT", seed=1, labels=self.labels, q1_profile=self.q1
        )
        resolved = resolve_i3_envelope(
            result["evaluation"],
            presence=True,
            proposed_physiology="APNEA",
            class_confidence=0.95,
        )
        self.assertNotIn(resolved["application_state"], ("APNEA_PROXY_CANDIDATE", "APNEA"))
        self.assertIn("INVALID_INPUT_CANNOT_EMIT_VALID_PHYSIOLOGY", resolved["schema_errors"])

    def test_r_no_person_not_apnea_or_rr0(self) -> None:
        resolved = resolve_precedence(
            presence=False,
            declared_quality="PHYSIOLOGY_ELIGIBLE",
            domain_class="PRODUCTION_MR60",
            proposed_physiology="APNEA",
        )
        self.assertEqual(resolved["availability_state"], "PRESENCE_SUPPRESSED")
        output = envelope_for_case(
            "no-person-rr",
            evaluate_availability(self.t, self.x, presence=False),
            presence=False,
            domain_class="PRODUCTION_MR60",
            freshness_value=20.0,
        )
        self.assertEqual(output["i1_output"]["application_state"], "PRESENCE_SUPPRESSED")
        self.assertFalse(output["i1_output"]["physiology_executed"])
        self.assertNotIn(output["i1_output"]["application_state"], ("APNEA_PROXY_CANDIDATE", "RESPIRATION_PRESENT"))

    def test_s_recovery_warmup(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="SOURCE_FREEZE", seed=1, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(result["evaluation"]["window_state"], "INVALID_WINDOW_INPUT_UNAVAILABLE")
        self.assertNotEqual(result["evaluation"]["availability_state"], "PHYSIOLOGY_ELIGIBLE")

    def test_t_session_reset(self) -> None:
        audit = load("session_reset_audit.json")
        self.assertFalse(audit["session_state_leak"])
        self.assertEqual(audit["session_b_independent_state"], "PHYSIOLOGY_ELIGIBLE")
        state = SessionReplayState()
        state.observe(3, "dev-a", "fw-a")
        state.reset("session_boundary")
        self.assertIsNone(state.last_seq)

    def test_u_identical_replay_twice(self) -> None:
        audit = load("determinism_audit.json")
        self.assertTrue(audit["identical_repeat"])
        self.assertTrue(audit["wall_clock_excluded"])
        a = apply_quality_corruption(
            self.t, self.x, mode="JITTER_PLUS_LARGE_GAP", seed=9, labels=self.labels, q1_profile=self.q1
        )
        b = apply_quality_corruption(
            self.t, self.x, mode="JITTER_PLUS_LARGE_GAP", seed=9, labels=self.labels, q1_profile=self.q1
        )
        self.assertEqual(a["evaluation"]["reasons"], b["evaluation"]["reasons"])
        self.assertEqual(a["evaluation"]["availability_state"], b["evaluation"]["availability_state"])

    def test_v_clean_valid_eligible_but_not_executed(self) -> None:
        result = apply_quality_corruption(
            self.t, self.x, mode="CLEAN_VALID", seed=1, labels=self.labels, q1_profile=self.q1
        )
        resolved = resolve_i3_envelope(result["evaluation"], presence=True)
        self.assertEqual(resolved["availability_state"], "PHYSIOLOGY_ELIGIBLE")
        self.assertFalse(resolved["physiology_executed"])
        self.assertEqual(resolved["application_state"], "NOT_EVALUATED")

    def test_q2_declared_quality_mapping(self) -> None:
        suppressed = evaluate_availability(self.t, self.x, presence=False)
        self.assertEqual(declared_quality_from_q2(suppressed), "PHYSIOLOGY_ELIGIBLE")
        gap = apply_quality_corruption(
            self.t, self.x, mode="LARGE_GAP", seed=1, labels=self.labels, q1_profile=self.q1, presence=False
        )["evaluation"]
        self.assertEqual(declared_quality_from_q2(gap), "INPUT_UNAVAILABLE")

    def test_seq_gap_not_interpolated(self) -> None:
        parsed = [
            {
                "_i2_row": {
                    "breath_phase": 0.1,
                    "firmware_version": "synthetic",
                    "human_detected_raw": True,
                    "phase_age_ms": 8,
                    "schema_version": "1.2",
                    "seq": 10,
                    "ts_monotonic_ms": 1000,
                },
                "_row_index": 0,
            },
            {
                "_i2_row": {
                    "breath_phase": 0.2,
                    "firmware_version": "synthetic",
                    "human_detected_raw": True,
                    "phase_age_ms": 8,
                    "schema_version": "1.2",
                    "seq": 13,
                    "ts_monotonic_ms": 1300,
                },
                "_row_index": 1,
            },
        ]
        result = replay_parsed_rows(
            parsed,
            session_id="unit-seq-gap",
            source_id="unit-seq-gap",
            git_blob_sha=None,
            mode="FAST",
            source_class="SYNTHETIC_Q1_Q2_FIXTURE",
        )
        self.assertEqual(result["replayed_count"], 2)
        self.assertEqual(result["seq_audit_counts"]["GAP"], 1)

    def test_typical_jitter_control(self) -> None:
        jittered = apply_timing_corruption(
            self.t, self.x, self.q1, mode="CADENCE_JITTER", severity="TYPICAL", seed=5
        )
        evaluation = evaluate_availability(jittered["timestamps_ms"], jittered["values"], presence=True)
        self.assertEqual(evaluation["availability_state"], "PHYSIOLOGY_ELIGIBLE")

    def test_historical_freeze_sessions(self) -> None:
        historical = load("historical_replay_regression.json")
        roles = {item["role"]: item for item in historical["sessions"]}
        freeze_95 = roles["q2_handoff_freeze_like_95_run"]["quality_only_window"]
        freeze_3598 = roles["q2_handoff_freeze_like_3598_run"]["quality_only_window"]
        self.assertEqual(freeze_95["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_FREEZE", freeze_95["reasons"])
        self.assertEqual(freeze_3598["availability_state"], "INPUT_UNAVAILABLE")
        self.assertIn("SOURCE_FREEZE", freeze_3598["reasons"])
        self.assertFalse(historical["physiology_interpreted"])
