from __future__ import annotations

import unittest

import numpy as np

from adapters.mmwave_r1_sensor_independent_trace import NativeTraceInput, adapt_native_trace
from adapters.mmwave_r2_representation_features import (
    R2FeatureError,
    extract_feature_candidates,
)


def _common(values: np.ndarray, recording_id: str = "fixture"):
    values = np.asarray(values, dtype=np.float64)
    fs = 10.0
    native = NativeTraceInput(
        source_id="R2_TEST",
        dataset_id="r2-test-dataset",
        subject_id="subject-1",
        recording_id=recording_id,
        condition="synthetic",
        trace=values,
        time_s=np.arange(values.size, dtype=np.float64) / fs,
        sampling_rate_hz=fs,
        native_trace_semantics="TEST_NATIVE_PHASE",
        native_trace_unit="phase_like_radian",
        source_scale_metadata={"test": True},
        provenance={"adapter_identity": "R2_TEST_ADAPTER"},
    )
    return adapt_native_trace(native)


class R2SpectralAutocorrFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.time_s = np.arange(300, dtype=np.float64) / 10.0
        self.trace = 0.8 * np.sin(2.0 * np.pi * 0.20 * self.time_s)
        self.trace += 0.12 * np.sin(2.0 * np.pi * 0.35 * self.time_s)

    def test_normalized_shape_is_scale_stable_but_absolute_scale_is_not(self):
        large = extract_feature_candidates(_common(self.trace, "large"))
        small = extract_feature_candidates(_common(self.trace / 100.0, "small"))
        self.assertEqual(large.f1.status, "AVAILABLE")
        self.assertEqual(small.f1.status, "AVAILABLE")
        shape_names = (
            "spectral_shape_fraction_0p10_0p25_hz",
            "spectral_shape_fraction_0p25_0p40_hz",
            "spectral_shape_fraction_0p40_0p55_hz",
            "spectral_shape_fraction_0p55_0p70_hz",
            "spectral_shape_centroid_hz",
            "spectral_shape_peak_frequency_hz",
            "spectral_shape_peak_fraction",
            "spectral_shape_entropy_normalized",
        )
        for name in shape_names:
            self.assertAlmostEqual(large.f1.features[name], small.f1.features[name], places=10)
        self.assertAlmostEqual(
            large.f1.features["native_mad_about_median"]
            / small.f1.features["native_mad_about_median"],
            100.0,
            places=8,
        )
        self.assertAlmostEqual(
            large.f1.features["total_signal_energy"]
            / small.f1.features["total_signal_energy"],
            10000.0,
            places=6,
        )
        self.assertAlmostEqual(
            large.f1.features["respiratory_band_energy"]
            / small.f1.features["respiratory_band_energy"],
            10000.0,
            places=6,
        )

    def test_low_amplitude_periodic_trace_is_not_treated_as_flat_or_apnea(self):
        result = extract_feature_candidates(_common(self.trace / 100.0, "low-amplitude"))
        self.assertEqual(result.f1.status, "AVAILABLE")
        self.assertEqual(result.f2.status, "AVAILABLE")
        self.assertEqual(result.f3.features["trace_is_exact_flat"], 0.0)
        self.assertGreater(result.f1.features["respiratory_band_energy"], 0.0)
        self.assertNotIn("apnea", result.f1.features)

    def test_exact_flat_trace_is_typed_unavailable_without_fake_shape(self):
        result = extract_feature_candidates(_common(np.full(300, 2.0), "flat"))
        self.assertEqual(result.f1.status, "FEATURE_UNAVAILABLE_FLAT_TRACE")
        self.assertEqual(result.f2.status, "FEATURE_UNAVAILABLE_FLAT_TRACE")
        self.assertEqual(result.f3.status, "FEATURE_UNAVAILABLE_FLAT_TRACE")
        self.assertEqual(result.f1.unavailable_reasons, ("EXACT_FLAT_TRACE",))
        self.assertFalse(any(name.startswith("spectral_shape_") for name in result.f1.features))
        self.assertTrue(all(np.isfinite(value) for value in result.f1.features.values()))
        self.assertTrue(all(np.isfinite(value) for value in result.f2.features.values()))
        self.assertEqual(result.f3.features["trace_is_exact_flat"], 1.0)

    def test_sign_is_not_flipped_and_sign_invariant_descriptors_match(self):
        positive = extract_feature_candidates(_common(self.trace, "positive"))
        negative = extract_feature_candidates(_common(-self.trace, "negative"))
        for name in (
            "spectral_shape_centroid_hz",
            "spectral_shape_peak_frequency_hz",
            "spectral_shape_entropy_normalized",
            "autocorr_periodicity_peak_strength",
            "autocorr_periodicity_peak_lag_s",
        ):
            self.assertAlmostEqual(positive.f2.features[name], negative.f2.features[name], places=10)
        self.assertFalse(positive.provenance["source_sign_flipped"])

    def test_short_trace_is_unavailable_without_zero_padding(self):
        result = extract_feature_candidates(_common(self.trace[:30], "short"))
        self.assertEqual(result.f1.status, "FEATURE_UNAVAILABLE_SHORT_TRACE")
        self.assertEqual(result.f2.status, "FEATURE_UNAVAILABLE_SHORT_TRACE")
        self.assertEqual(result.f3.status, "AVAILABLE")
        self.assertFalse(result.f1.diagnostics["welch"]["zero_padding"])

    def test_r1_scale_contract_violation_fails_closed(self):
        common = _common(self.trace)
        common.metadata["native_scale_metadata"]["scale_normalization_applied"] = True
        with self.assertRaisesRegex(R2FeatureError, "R1_SCALE_NORMALIZATION_PRESENT"):
            extract_feature_candidates(common)

    def test_extraction_is_deterministic(self):
        first = extract_feature_candidates(_common(self.trace, "deterministic"))
        second = extract_feature_candidates(_common(self.trace, "deterministic"))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertTrue(np.array_equal(first.trace, second.trace))


if __name__ == "__main__":
    unittest.main()
