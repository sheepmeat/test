from __future__ import annotations

import unittest

import numpy as np

from adapters.mmwave_r1_sensor_independent_trace import (
    NativeTraceInput,
    R1TraceError,
    adapt_native_trace,
)


def _native(
    trace: np.ndarray,
    fs: float,
    *,
    time_s: np.ndarray | None = None,
    validity_mask: np.ndarray | None = None,
) -> NativeTraceInput:
    trace = np.asarray(trace, dtype=np.float64)
    if time_s is None:
        time_s = np.arange(trace.size, dtype=np.float64) / fs
    return NativeTraceInput(
        source_id="TEST",
        dataset_id="dataset-test",
        subject_id="subject-1",
        recording_id="recording-1",
        condition="default",
        trace=trace,
        time_s=np.asarray(time_s, dtype=np.float64),
        sampling_rate_hz=fs,
        native_trace_semantics="TEST_NATIVE_PHASE",
        native_trace_unit="test_unit",
        source_scale_metadata={"source_marker": "fixture"},
        provenance={"adapter_identity": "TEST_ADAPTER"},
        validity_mask=validity_mask,
        source_quality_flags=("TEST_SOURCE",),
    )


class R1SensorIndependentTraceTests(unittest.TestCase):
    def test_source_rate_is_preserved_at_existing_10_hz(self):
        values = 4.0 + 2.0 * np.sin(2.0 * np.pi * 0.2 * np.arange(300) / 10.0)
        result = adapt_native_trace(_native(values, 10.0))
        self.assertEqual(result.trace.size, 300)
        self.assertFalse(result.metadata["resampling_metadata"]["resampling_performed"])
        self.assertFalse(result.metadata["native_scale_metadata"]["scale_normalization_applied"])
        self.assertTrue(result.metadata["native_scale_metadata"]["native_scale_preserved"])
        self.assertAlmostEqual(float(np.median(result.trace)), 0.0, places=12)

    def test_high_rate_source_is_anti_alias_resampled_deterministically(self):
        t = np.arange(5000, dtype=np.float64) / 500.0
        values = 15.0 + 3.0 * np.sin(2.0 * np.pi * 0.25 * t)
        first = adapt_native_trace(_native(values, 500.0))
        second = adapt_native_trace(_native(values, 500.0))
        metadata = first.metadata["resampling_metadata"]
        self.assertTrue(metadata["resampling_performed"])
        self.assertEqual(metadata["resampling_up"], 1)
        self.assertEqual(metadata["resampling_down"], 50)
        self.assertTrue(np.array_equal(first.trace, second.trace))
        self.assertTrue(np.array_equal(first.time_s, second.time_s))
        self.assertTrue(np.all(np.diff(first.time_s) > 0.0))
        self.assertEqual(first.trace.size, 100)

    def test_sign_is_preserved_and_no_gain_matching_is_applied(self):
        values = 2.0 * np.sin(2.0 * np.pi * 0.2 * np.arange(300) / 10.0)
        positive = adapt_native_trace(_native(values, 10.0))
        negative = adapt_native_trace(_native(-values, 10.0))
        self.assertTrue(np.allclose(positive.trace, -negative.trace))
        self.assertFalse(positive.metadata["native_scale_metadata"]["sensor_gain_matching_applied"])
        self.assertFalse(positive.metadata["native_scale_metadata"]["sign_inversion_applied"])

    def test_nonfinite_input_fails_closed(self):
        values = np.ones(100, dtype=np.float64)
        values[10] = np.nan
        with self.assertRaisesRegex(R1TraceError, "NONFINITE_INPUT"):
            adapt_native_trace(_native(values, 10.0))

    def test_large_gap_fails_closed_without_zero_fill(self):
        values = np.ones(100, dtype=np.float64)
        time_s = np.arange(100, dtype=np.float64) / 10.0
        time_s[50:] += 1.0
        with self.assertRaisesRegex(R1TraceError, "UNRESOLVABLE_TIME_GAP"):
            adapt_native_trace(_native(values, 10.0, time_s=time_s))

    def test_invalid_mask_fails_closed(self):
        values = np.ones(100, dtype=np.float64)
        mask = np.ones(100, dtype=bool)
        mask[25] = False
        with self.assertRaisesRegex(R1TraceError, "INVALID_SOURCE_REGION"):
            adapt_native_trace(_native(values, 10.0, validity_mask=mask))


if __name__ == "__main__":
    unittest.main()
