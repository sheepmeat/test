from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.materialize_thermal_b6r_p0_public_sdt import (
    MultiFileStream,
    map_source_label,
    normalize_image,
    stable_json_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "config/thermal/b6r_p0_public_sdt_contract.json").read_text(encoding="utf-8")
)


class B6RP0PublicSdtTest(unittest.TestCase):
    def test_label_mapping_is_explicit_and_proxy_scoped(self) -> None:
        self.assertEqual([map_source_label(i, CONTRACT) for i in range(4)], [2, 1, 1, 0])
        self.assertIn("proxy", CONTRACT["label_mapping"]["semantic_limit"].lower())

    def test_normalization_is_deterministic_62x80_float32(self) -> None:
        source = np.arange(480 * 640, dtype=np.uint16).reshape(480, 640)
        image = Image.fromarray(source)
        first = normalize_image(image, CONTRACT)
        second = normalize_image(image, CONTRACT)
        self.assertEqual(first.shape, (62, 80))
        self.assertEqual(first.dtype, np.dtype("float32"))
        self.assertTrue(np.array_equal(first, second))
        self.assertGreaterEqual(float(first.min()), 0.0)
        self.assertLessEqual(float(first.max()), 1.0)

    def test_constant_frame_becomes_zero_tensor(self) -> None:
        image = Image.fromarray(np.full((480, 640), 30000, dtype=np.uint16))
        output = normalize_image(image, CONTRACT)
        self.assertEqual(int(np.count_nonzero(output)), 0)

    def test_multifile_stream_opens_split_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("train/labels.txt", "0,a,b,c,d\n")
            payload = buffer.getvalue()
            cut = len(payload) // 2
            paths = [root / "part.001", root / "part.002"]
            paths[0].write_bytes(payload[:cut])
            paths[1].write_bytes(payload[cut:])
            stream = MultiFileStream(paths)
            try:
                with zipfile.ZipFile(stream, "r") as archive:
                    self.assertEqual(archive.read("train/labels.txt"), b"0,a,b,c,d\n")
            finally:
                stream.close()

    def test_stable_json_is_key_sorted_lf(self) -> None:
        self.assertEqual(stable_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}\n')


if __name__ == "__main__":
    unittest.main()
