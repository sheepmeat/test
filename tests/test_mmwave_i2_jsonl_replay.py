#!/usr/bin/env python3
"""I2 historical JSONL replay tests. No training, I3 regression, or physiology scoring."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV0_I2_jsonl_replay"
GENERATOR = ROOT / "scripts/mmwave_i2_jsonl_replay.py"
VALIDATOR = ROOT / "scripts/validate_mmwave_i2_jsonl_replay.py"

from adapters.mmwave_i2_replay_adapter import (  # noqa: E402
    I2_CONTRACT_ID,
    map_mr60_row_to_i1,
    replay_event_id,
)
from scripts.mmwave_i1_runtime_io_contract import INPUT_CONTRACT_ID, OUTPUT_CONTRACT_ID  # noqa: E402
from scripts.mmwave_i2_jsonl_replay import (  # noqa: E402
    SessionReplayState,
    BASE_SHA,
    VirtualReplayClock,
    parse_jsonl_bytes,
    public_offline_replay,
    replay_parsed_rows,
    synthetic_fixture_rows,
)


def load(name: str) -> dict:
    return json.loads((MANIFEST / name).read_text(encoding="utf-8"))


def mr60_row(**overrides: object) -> dict:
    row = {
        "breath_phase": 0.2,
        "firmware_version": "safenest-mr60-esp/1.2.0",
        "human_detected_raw": True,
        "phase_age_ms": 12,
        "schema_version": "1.2",
        "seq": 1,
        "ts_monotonic_ms": 1000,
    }
    row.update(overrides)
    return row


class TestMmwaveI2JsonlReplay(unittest.TestCase):
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

    def test_validator_pass_with_limitations(self) -> None:
        self.assertEqual(self.validator.returncode, 0, self.validator.stdout + self.validator.stderr)
        result = load("validation_result.json")
        self.assertTrue(result["ok"])
        self.assertEqual(result["gate"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(result["contract_id"], I2_CONTRACT_ID)
        self.assertEqual(result["checks"]["I3_REGRESSION_GATE_PERFORMED"], "NO")
        self.assertEqual(result["checks"]["MR60_SUPERVISED_USE"], "NO")
        self.assertEqual(result["i2_ready_for_i3"], "YES")

    def test_basic_replay_original_order(self) -> None:
        parsed = [
            {"_i2_row": mr60_row(seq=10, ts_monotonic_ms=1000), "_row_index": 0},
            {"_i2_row": mr60_row(seq=11, ts_monotonic_ms=1100, breath_phase=0.4), "_row_index": 1},
        ]
        result = replay_parsed_rows(
            parsed,
            session_id="unit-modern",
            source_id="unit",
            git_blob_sha="abc",
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        self.assertEqual(result["replayed_count"], 2)
        self.assertEqual([item["row_index"] for item in result["replayed"]], [0, 1])
        self.assertEqual(result["replayed"][0]["i1_input"]["schema_id"], INPUT_CONTRACT_ID)
        self.assertEqual(
            [item["evidence_timestamp_ms"] for item in result["replayed"]],
            [1000, 1100],
        )

    def test_legacy_optionality(self) -> None:
        row = {"seq": 3, "ts_monotonic_ms": 50, "breath_phase": 0.0, "human_detected_raw": False}
        envelope = map_mr60_row_to_i1(
            row,
            session_id="legacy",
            row_index=0,
            git_blob_sha="def",
            source_id="unit",
            replay_harness_sha=BASE_SHA,
        )
        self.assertEqual(envelope["freshness"]["phase_age_ms"]["status"], "FIELD_ABSENT_LEGACY")
        self.assertIsNone(envelope["freshness"]["phase_age_ms"]["value"])
        self.assertEqual(envelope["mr60_telemetry"]["firmware_version"], None)
        self.assertIs(envelope["presence"]["value"], False)

    def test_deterministic_ids(self) -> None:
        parsed = [{"_i2_row": mr60_row(), "_row_index": 4}]
        kwargs = dict(
            session_id="unit-id",
            source_id="unit",
            git_blob_sha="sha",
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        first = replay_parsed_rows(parsed, **kwargs)
        second = replay_parsed_rows(parsed, **kwargs)
        self.assertEqual(first["event_ids"], second["event_ids"])
        self.assertEqual(first["compact_result_sha256"], second["compact_result_sha256"])
        self.assertTrue(first["event_ids"][0].startswith("replay_event:"))

    def test_fast_mode_preserves_evidence_time(self) -> None:
        parsed = synthetic_fixture_rows()
        fast = replay_parsed_rows(
            parsed,
            session_id="synth",
            source_id="synthetic-q1-fixture",
            git_blob_sha=None,
            mode="FAST",
            source_class="SYNTHETIC_Q1_Q2_FIXTURE",
            synthetic={"profile_id": "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1", "seed": 7, "mode": "CADENCE_JITTER"},
        )
        recorded = replay_parsed_rows(
            parsed,
            session_id="synth",
            source_id="synthetic-q1-fixture",
            git_blob_sha=None,
            mode="AS_RECORDED",
            source_class="SYNTHETIC_Q1_Q2_FIXTURE",
            synthetic={"profile_id": "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1", "seed": 7, "mode": "CADENCE_JITTER"},
        )
        self.assertEqual(fast["evidence_timestamps_ms"], recorded["evidence_timestamps_ms"])
        self.assertNotEqual(
            [item["virtual_replay_time_ms"] for item in fast["replayed"]],
            [item["virtual_replay_time_ms"] for item in recorded["replayed"]],
        )

    def test_virtual_clock_scaled_does_not_mutate_evidence(self) -> None:
        clock = VirtualReplayClock("SCALED", scale=0.5)
        self.assertEqual(clock.observe(1000), 0.0)
        self.assertEqual(clock.observe(1200), 100.0)
        parsed = [{"_i2_row": mr60_row(ts_monotonic_ms=5000), "_row_index": 0}]
        result = replay_parsed_rows(
            parsed,
            session_id="scaled",
            source_id="unit",
            git_blob_sha=None,
            mode="SCALED",
            source_class="PHYSICAL_MR60_JSONL",
        )
        self.assertEqual(result["replayed"][0]["evidence_timestamp_ms"], 5000)

    def test_session_reset_does_not_leak_seq_state(self) -> None:
        state = SessionReplayState()
        self.assertEqual(state.observe(10, "dev-a", "fw1"), "INCREMENT")
        state.reset("new_file")
        self.assertIsNone(state.last_seq)
        self.assertEqual(state.observe(99, "dev-b", "fw1"), "INCREMENT")
        first = replay_parsed_rows(
            [{"_i2_row": mr60_row(seq=50), "_row_index": 0}],
            session_id="s1",
            source_id="unit",
            git_blob_sha="a",
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        second = replay_parsed_rows(
            [{"_i2_row": mr60_row(seq=1), "_row_index": 0}],
            session_id="s2",
            source_id="unit",
            git_blob_sha="b",
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        self.assertEqual(first["seq_audit_counts"]["RESET"], 0)
        self.assertEqual(second["seq_audit_counts"]["RESET"], 0)

    def test_seq_gap_audited_not_interpolated(self) -> None:
        parsed = [
            {"_i2_row": mr60_row(seq=1, ts_monotonic_ms=1), "_row_index": 0},
            {"_i2_row": mr60_row(seq=2, ts_monotonic_ms=2), "_row_index": 1},
            {"_i2_row": mr60_row(seq=5, ts_monotonic_ms=3), "_row_index": 2},
        ]
        result = replay_parsed_rows(
            parsed,
            session_id="gap",
            source_id="unit",
            git_blob_sha=None,
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        self.assertEqual(result["replayed_count"], 3)
        self.assertEqual(result["seq_audit_counts"]["GAP"], 1)
        self.assertEqual(len(result["replayed"]), 3)

    def test_timestamp_defect_preserved(self) -> None:
        parsed = [
            {"_i2_row": mr60_row(seq=1, ts_monotonic_ms=200), "_row_index": 0},
            {"_i2_row": mr60_row(seq=2, ts_monotonic_ms=100), "_row_index": 1},
        ]
        result = replay_parsed_rows(
            parsed,
            session_id="defect",
            source_id="unit",
            git_blob_sha=None,
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        self.assertEqual(result["evidence_timestamps_ms"], [200, 100])
        self.assertEqual([item["row_index"] for item in result["replayed"]], [0, 1])

    def test_malformed_json_explicit(self) -> None:
        parsed = parse_jsonl_bytes(b'{not-json\n{"seq":1,"ts_monotonic_ms":10,"schema_version":"1.2","phase_age_ms":1}\n')
        result = replay_parsed_rows(
            parsed,
            session_id="malformed",
            source_id="unit",
            git_blob_sha=None,
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["rejected"][0]["reason"], "INVALID_JSON")
        self.assertEqual(result["replayed_count"], 1)

    def test_presence_not_coerced_true(self) -> None:
        missing = map_mr60_row_to_i1(
            {"seq": 1, "ts_monotonic_ms": 1, "schema_version": "1.0", "phase_age_ms": 4},
            session_id="nopres",
            row_index=0,
            git_blob_sha=None,
            source_id="unit",
            replay_harness_sha=BASE_SHA,
        )
        self.assertIsNone(missing["presence"]["value"])
        self.assertNotEqual(missing["presence"]["value"], True)
        self.assertFalse(missing["presence"]["inferred_from_amplitude"])
        false_row = map_mr60_row_to_i1(
            mr60_row(human_detected_raw=False),
            session_id="falsep",
            row_index=0,
            git_blob_sha=None,
            source_id="unit",
            replay_harness_sha=BASE_SHA,
        )
        self.assertIs(false_row["presence"]["value"], False)

    def test_freshness_and_seq_not_rewritten(self) -> None:
        parsed = [
            {"_i2_row": mr60_row(seq=1, phase_age_ms=400, ts_monotonic_ms=1000), "_row_index": 0},
            {"_i2_row": mr60_row(seq=2, phase_age_ms=400, ts_monotonic_ms=1100), "_row_index": 1},
        ]
        result = replay_parsed_rows(
            parsed,
            session_id="fresh",
            source_id="unit",
            git_blob_sha=None,
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        ages = [item["i1_input"]["freshness"]["phase_age_ms"]["value"] for item in result["replayed"]]
        self.assertEqual(ages, [400, 400])
        self.assertEqual(result["replayed"][1]["i1_input"]["freshness"]["seq"]["value"], 2)

    def test_mock_physiology_not_emitted(self) -> None:
        result = replay_parsed_rows(
            [{"_i2_row": mr60_row(), "_row_index": 0}],
            session_id="mock",
            source_id="unit",
            git_blob_sha=None,
            mode="FAST",
            source_class="PHYSICAL_MR60_JSONL",
        )
        output = result["replayed"][0]["i1_output"]
        self.assertEqual(output["schema_id"], OUTPUT_CONTRACT_ID)
        self.assertFalse(output["physiology_executed"])
        self.assertEqual(output["application_state"], "NOT_EVALUATED")
        blob = json.dumps(output)
        self.assertNotIn('"NORMAL"', blob)
        self.assertNotIn("RAPID_OR_ABNORMAL", blob)
        self.assertNotIn('"APNEA"', blob)

    def test_public_offline_fixture(self) -> None:
        public = public_offline_replay("FAST")
        self.assertEqual(public["replayed_count"], 1)
        self.assertEqual(public["i1_input"]["source"]["domain_class"], "PUBLIC_OFFLINE")
        self.assertEqual(
            public["i1_input"]["freshness"]["phase_age_ms"]["applicability"],
            "NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN",
        )

    def test_synthetic_lineage_preserved(self) -> None:
        result = replay_parsed_rows(
            synthetic_fixture_rows(),
            session_id="SYNTHETIC_Q1_CADENCE_JITTER_TINY",
            source_id="synthetic-q1-fixture",
            git_blob_sha=None,
            mode="FAST",
            source_class="SYNTHETIC_Q1_Q2_FIXTURE",
            synthetic={
                "mode": "CADENCE_JITTER",
                "original_sample_index": 0,
                "profile_id": "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1",
                "seed": 7,
                "severity": "TYPICAL",
            },
        )
        prov = result["replayed"][0]["i1_input"]["provenance"]
        self.assertEqual(prov["synthetic_corruption_profile_id"], "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1")
        self.assertEqual(prov["synthetic_corruption_seed"], 7)
        self.assertEqual(prov["synthetic_corruption_mode"], "CADENCE_JITTER")
        self.assertEqual(prov["original_sample_index"], 0)

    def test_replay_event_id_stable_formula(self) -> None:
        first = replay_event_id(
            source_id="unit",
            session_id="s",
            row_index=3,
            seq=9,
            timestamp_ms=11,
            git_blob_sha="blob",
        )
        second = replay_event_id(
            source_id="unit",
            session_id="s",
            row_index=3,
            seq=9,
            timestamp_ms=11,
            git_blob_sha="blob",
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
