from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import savemat

from adapters.mmwave_d1_2417ghz_adapter import (
    ADAPTER_ID,
    D1AdapterError,
    RELATIVE_DISTANCE_PER_RAD_M,
    adapt_mat_file,
)


class TestMmwaveD1Adapter(unittest.TestCase):
    def _write_mat(self, directory: Path, *, named_iq: bool = True, **overrides: object) -> Path:
        samples = 240
        theta = np.linspace(-3.0, 7.0, samples)
        unit = np.column_stack((np.cos(theta), np.sin(theta)))
        affine = np.array([[3.0, 0.7], [-0.4, 1.8]])
        raw = 100.0 + unit @ affine.T
        payload: dict[str, object] = {
            "radar_I": raw[:, 0],
            "radar_Q": raw[:, 1],
            "respiration": np.sin(theta / 4.0),
            "Fs": 2000.0,
            "measurement_info": np.array(["2016-12-20_11-25-55", "1"], dtype=object),
        }
        if not named_iq:
            payload.pop("radar_I")
            payload.pop("radar_Q")
            payload.update(
                {
                    "B3": raw[:, 1],
                    "B4": np.zeros(samples),
                    "B5": raw[:, 0],
                    "B6": np.zeros(samples),
                }
            )
        payload.update(overrides)
        if payload.get("radar_I", object()) is None:
            payload.pop("radar_I", None)
        path = directory / "recording.mat"
        savemat(path, payload)
        return path

    def test_named_differential_iq_is_adapted_without_window_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_mat(Path(temp_dir))
            result = adapt_mat_file(path, condition="DEFAULT", condition_source="TEST")
        self.assertEqual(result.metadata["adapter_id"], ADAPTER_ID)
        self.assertEqual(result.metadata["subject_id"], "1")
        self.assertEqual(result.metadata["measurement_timestamp_label"], "2016-12-20_11-25-55")
        self.assertEqual(result.metadata["channel_metadata"]["channel_source"], "PUBLISHED_NAMED_DIFFERENTIAL_IQ")
        self.assertEqual(result.metadata["sample_count"], 240)
        self.assertEqual(result.metadata["output_sampling_rate_hz"], 2000.0)
        self.assertEqual(result.time_s[0], 0.0)
        self.assertAlmostEqual(result.time_s[-1], 239.0 / 2000.0)
        self.assertEqual(result.native_phase_rad.shape, (240,))
        self.assertEqual(result.respiration_reference_native.shape, (240,))
        self.assertTrue(np.all(np.isfinite(result.native_phase_rad)))
        self.assertTrue(np.allclose(result.relative_displacement_m, result.native_phase_rad * RELATIVE_DISTANCE_PER_RAD_M))
        self.assertTrue(result.metadata["quality_flags"]["native_amplitude_preserved"])
        self.assertFalse(result.metadata["quality_flags"]["large_missing_region_interpolated"])
        self.assertIn("window_local_MAD_normalization", result.metadata["forbidden_processing_not_applied"])

    def test_explicit_b3_b6_mapping_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_mat(Path(temp_dir), named_iq=False)
            result = adapt_mat_file(path)
        self.assertEqual(
            result.metadata["channel_metadata"]["channel_source"],
            "PUBLISHED_SIX_PORT_B3_B6_DIFFERENTIAL_RECONSTRUCTION",
        )
        self.assertEqual(result.metadata["channel_metadata"]["six_port_combination"], {"I": "B5 - B6", "Q": "B3 - B4"})

    def test_required_channels_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_mat(Path(temp_dir), radar_I=None)
            with self.assertRaises(D1AdapterError) as error:
                adapt_mat_file(path)
        self.assertEqual(error.exception.code, "REQUIRED_RADAR_CHANNELS_ABSENT")

    def test_length_mismatch_does_not_interpolate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_mat(Path(temp_dir), respiration=np.zeros(12))
            with self.assertRaises(D1AdapterError) as error:
                adapt_mat_file(path)
        self.assertEqual(error.exception.code, "REQUIRED_CHANNEL_LENGTH_MISMATCH")

    def test_nonfinite_and_wrong_source_rate_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_mat(Path(temp_dir), radar_Q=np.full(240, np.nan))
            with self.assertRaises(D1AdapterError) as error:
                adapt_mat_file(path)
            self.assertEqual(error.exception.code, "NONFINITE_REQUIRED_CHANNEL")

            path = self._write_mat(Path(temp_dir), Fs=1000.0)
            with self.assertRaises(D1AdapterError) as error:
                adapt_mat_file(path)
        self.assertEqual(error.exception.code, "SOURCE_SAMPLING_RATE_UNSUPPORTED")

    def test_partial_six_port_set_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_mat(Path(temp_dir), named_iq=False)
            # Remove one detector output after the fixture is written.
            from scipy.io import loadmat

            payload = loadmat(path)
            payload.pop("B4")
            savemat(path, payload)
            with self.assertRaises(D1AdapterError) as error:
                adapt_mat_file(path)
        self.assertEqual(error.exception.code, "PARTIAL_SIX_PORT_CHANNEL_SET")


if __name__ == "__main__":
    unittest.main()
