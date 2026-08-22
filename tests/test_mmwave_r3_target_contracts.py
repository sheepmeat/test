from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.mmwave_r3_target_contracts import build_d0_target_row, build_d1_target_row
from scripts.run_mmwave_r3_target_contracts import OUTPUT_FILES, run


def _window(
    *,
    rr: float | None = 16.0,
    event: tuple[float, float] | None = None,
    exact_flat: bool = False,
    has_nan: bool = False,
    start_s: float = 0.0,
    end_s: float = 30.0,
    source_label: str = "NORMAL",
) -> dict:
    events = []
    overlap = 0.0
    if event is not None:
        event_start, event_end = event
        overlap = max(0.0, min(end_s, event_end) - max(start_s, event_start))
        events = [
            {
                "event_id": "EVT_0001",
                "event_start_seconds": event_start,
                "event_end_seconds": event_end,
                "overlap_seconds": overlap,
                "overlap_start_seconds": max(start_s, event_start),
                "overlap_end_seconds": min(end_s, event_end),
            }
        ]
    info = None if rr is None else {
        "rr_bpm": rr,
        "peak_freq_hz": rr / 60.0,
        "sample_count": 798,
        "reference_sensor": "MOVESENSE_CHEST_ACC",
        "search_band_hz": [0.1, 0.7],
    }
    return {
        "subject_id": "dataset-10_5281_zenodo_18599983-p001",
        "recording_id": "dataset-10_5281_zenodo_18599983-p001-lying-rest",
        "window_id": f"window-{start_s}",
        "window_index": int(start_s / 30),
        "source_start_index": int(start_s * 10),
        "source_end_index_exclusive": int(end_s * 10),
        "duration_seconds": end_s - start_s,
        "assignment_status": "ASSIGNED",
        "timeline_valid": True,
        "large_gap_count": 0,
        "interpolated_sample_count": 0,
        "signal_quality_metrics": {
            "has_nan": has_nan,
            "has_inf": False,
            "is_exact_constant": exact_flat,
            "std_dev": 0.00001 if exact_flat is False else 0.0,
        },
        "annotation_events_overlapping": events,
        "annotation_overlap_seconds": overlap,
        "movesense_reference_rr": info,
        "safenest_label": source_label,
        "mapping_rule_id": "A4_RULE_APNEA_VOLUNTARY_PROXY" if event else "A4_RULE_NORMAL_MOVESENSE_ACC_REF",
        "mapping_type": "DERIVED",
        "original_annotation_type": "VOLUNTARY_NON_BREATHING" if event else "NONE",
        "source_test_condition": "Rest",
        "posture": "Lying",
        "phase_profile": "MMWAVE_PHASE_EXTRACTION_PROFILE_001",
        "quality_flags": ["TIMELINE_EXACT_NATIVE_10HZ"],
    }


def _recording_meta() -> dict:
    return {"source_recording_path": "db_records/P001/Lying/Rest"}


class R3TargetSemanticsTests(unittest.TestCase):
    def test_breathing_and_rr_are_separate_for_high_rr(self) -> None:
        row = build_d0_target_row(_window(rr=36.0), _recording_meta(), "TRAIN")
        self.assertEqual(row["breathing_evidence"]["breathing_reference_state"], "BREATHING_REFERENCE_PRESENT")
        self.assertEqual(row["rr_target"]["rr_bpm"], 36.0)
        self.assertEqual(row["temporal_hold"]["event_state"], "NO_HOLD_EVENT_IN_WINDOW")
        self.assertTrue(row["supervision_eligibility"]["rr_supervision_eligible"])

    def test_low_amplitude_does_not_change_reference_target(self) -> None:
        row = _window(rr=16.0)
        row["signal_quality_metrics"]["std_dev"] = 0.0000001
        built = build_d0_target_row(row, _recording_meta(), "TRAIN")
        self.assertEqual(built["breathing_evidence"]["breathing_reference_state"], "BREATHING_REFERENCE_PRESENT")

    def test_exact_flat_or_nan_input_is_not_physiology_eligible(self) -> None:
        flat = build_d0_target_row(_window(exact_flat=True), _recording_meta(), "TRAIN")
        self.assertEqual(flat["breathing_evidence"]["target_status"], "TARGET_UNAVAILABLE")
        self.assertFalse(flat["supervision_eligibility"]["model_supervision_eligible"])
        nan_row = build_d0_target_row(_window(has_nan=True), _recording_meta(), "TRAIN")
        self.assertEqual(nan_row["rr_target"]["rr_bpm"], None)
        self.assertFalse(nan_row["supervision_eligibility"]["model_supervision_eligible"])

    def test_partial_hold_is_event_relative_not_whole_window_absence(self) -> None:
        row = build_d0_target_row(_window(rr=14.0, event=(21.0, 31.0), source_label="APNEA"), _recording_meta(), "TRAIN")
        self.assertEqual(row["breathing_evidence"]["breathing_reference_state"], "BREATHING_REFERENCE_AMBIGUOUS")
        self.assertNotEqual(row["breathing_evidence"]["breathing_reference_state"], "BREATHING_REFERENCE_ABSENT")
        self.assertIsNone(row["rr_target"]["rr_bpm"])
        self.assertEqual(row["temporal_hold"]["event_state"], "HOLD_ONSET_WITHOUT_RECOVERY_IN_WINDOW")
        self.assertTrue(row["temporal_hold"]["has_previous_valid_breathing"])
        self.assertFalse(row["temporal_hold"]["recovery_detected"])

    def test_hold_candidate_requires_previous_baseline(self) -> None:
        row = build_d0_target_row(_window(rr=14.0, event=(0.0, 10.0), source_label="APNEA"), _recording_meta(), "TRAIN")
        self.assertEqual(row["temporal_hold"]["baseline_state"], "BASELINE_NOT_ESTABLISHED")
        self.assertFalse(row["supervision_eligibility"]["temporal_hold_supervision_eligible"])
        self.assertFalse(row["supervision_eligibility"]["model_supervision_eligible"])

    def test_recovery_terminates_event_and_next_window_resets(self) -> None:
        hold = build_d0_target_row(_window(rr=14.0, event=(5.0, 15.0), source_label="APNEA"), _recording_meta(), "TRAIN")
        self.assertTrue(hold["temporal_hold"]["recovery_detected"])
        next_window = _window(rr=16.0, start_s=30.0, end_s=60.0)
        next_window["window_id"] = "window-after-recovery"
        resumed = build_d0_target_row(next_window, _recording_meta(), "TRAIN")
        self.assertEqual(resumed["temporal_hold"]["event_state"], "NO_HOLD_EVENT_IN_WINDOW")
        self.assertTrue(resumed["temporal_hold"]["has_previous_valid_breathing"])

    def test_unavailable_rr_is_not_zero_and_vendor_value_is_ignored(self) -> None:
        row = _window(rr=None)
        row["breath_rate_raw"] = 0.0
        built = build_d0_target_row(row, _recording_meta(), "TRAIN")
        self.assertIsNone(built["rr_target"]["rr_bpm"])
        self.assertNotEqual(built["rr_target"]["rr_bpm"], 0)
        self.assertEqual(built["rr_target"]["target_status"], "TARGET_UNAVAILABLE")
        source = _window(rr=15.0)
        source["breath_rate_raw"] = 999.0
        with_vendor = build_d0_target_row(source, _recording_meta(), "TRAIN")
        self.assertEqual(with_vendor["rr_target"]["rr_bpm"], 15.0)

    def test_d1_apnea_protocol_is_provenance_only(self) -> None:
        recording = {
            "adaptation_status": "SUCCESS",
            "required_channel_lengths_equal": True,
            "required_channel_presence": {"radar_I": True, "radar_Q": True},
            "adapter_output": {
                "sample_count": 1000,
                "time_s_start": 0.0,
                "time_s_end": 9.99,
                "quality_flags": {"required_channels_finite": True, "timestamps_valid": True},
                "respiration_reference": {"native_stats": {"mean": 1.0}},
            },
            "observed_signal_fields": {"required": ["radar_I", "radar_Q", "respiration"]},
            "condition_metadata": {
                "source_scenario_normalized": "apnea",
                "breath_hold_protocol_present": True,
                "source_protocol_labels": ["BREATH_HOLD"],
            },
            "source_quality_ratings": {"breathing_reference": "A"},
            "subject_id": "D1_PERSON_01",
            "recording_id": "D1_PERSON_01-0001",
        }
        row = build_d1_target_row(recording)
        self.assertEqual(row["temporal_hold"]["target_status"], "TARGET_UNAVAILABLE")
        self.assertIsNone(row["temporal_hold"]["event_id"])
        self.assertFalse(row["source_label_provenance"]["source_apnea_string_auto_mapped_to_safenest_apnea"])

    def test_runner_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            first = run(output)
            first_bytes = {name: (output / name).read_bytes() for name in OUTPUT_FILES}
            second = run(output)
            second_bytes = {name: (output / name).read_bytes() for name in OUTPUT_FILES}
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["gate"], "PASS_WITH_LIMITATIONS")


if __name__ == "__main__":
    unittest.main()
