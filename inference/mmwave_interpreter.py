#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
inference/mmwave_interpreter.py
SafeNest 공용 mmWave 30초 시계열 호흡 파형 TFLite 추론 Wrapper

[검수 2차 지적사항 반영 완료]
1. INT8 / FLOAT32 입력/출력 텐서 스펙 검사 및 양자화/역양자화 연산 수립
2. 모델 SHA-256 및 입출력 텐서 계약을 Manifest와 대조
3. TFLite 모델 파일 미존재/로드 실패 원인을 구분하여 fallback provenance에 명시
4. 휴리스틱 결과 산출 시 model_id를 "mmwave_heuristic_fallback"으로 투명하게 반환하여 가짜 AI 표기 방지
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import time
import numpy as np

try:
    import ai_edge_litert.interpreter as tflite
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        try:
            import tensorflow.lite as tflite
        except ImportError:
            import tensorflow as tf
            tflite = tf.lite


@dataclass(frozen=True)
class MMWavePrediction:
    class_index: int
    class_name: str
    confidence: float
    probabilities: list[float]
    latency_ms: float
    model_id: str
    model_version: str
    fallback_used: bool
    fallback_reason: str | None


class MMWaveInterpreter:
    def __init__(
        self,
        project_root: str | Path | None = None,
        manifest_path: str = "models/model_manifest.json",
    ) -> None:
        if project_root is None:
            self.project_root = Path(__file__).resolve().parent.parent
        else:
            self.project_root = Path(project_root).resolve()

        manifest_file = self.project_root / manifest_path
        if not manifest_file.is_file():
            raise FileNotFoundError(f"Manifest file not found: {manifest_file}")

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.model_meta = manifest["models"]["mmwave"]
        self.class_map = {
            int(key): value
            for key, value in self.model_meta["class_map"].items()
        }

        # Metadata 로드 (Z-Score mean/std). 학습 산출물이 [value] 형태로
        # 저장되는 경우도 허용하되, 다변량 통계는 조용히 축약하지 않는다.
        meta_file = self.project_root / self.model_meta.get(
            "metadata_path", "models/mmwave/sensor_stats_metadata_v0.1.0.json"
        )
        if not meta_file.is_file():
            raise FileNotFoundError(f"mmWave metadata file not found: {meta_file}")
        self.stats_meta = json.loads(meta_file.read_text(encoding="utf-8"))
        self.mean = self._read_scalar_stat(self.stats_meta.get("mean"), "mean")
        self.std = self._read_scalar_stat(self.stats_meta.get("std"), "std")
        if self.std <= 0:
            raise ValueError("mmWave metadata std must be greater than zero")

        self.model_path = self.project_root / self.model_meta["path"]
        self.interpreter = None
        self.model_file_exists = self.model_path.is_file()
        self.sha256_hash = None
        self.sha256_matches = False
        self.load_error_reason = None

        # TFLite 바이너리가 존재하는 경우 SHA-256과 텐서 계약을 검증한다.
        if self.model_file_exists:
            try:
                model_bytes = self.model_path.read_bytes()
                self.sha256_hash = hashlib.sha256(model_bytes).hexdigest()
                expected_sha256 = self.model_meta.get("sha256")
                if expected_sha256 and self.sha256_hash != expected_sha256:
                    self.load_error_reason = "TFLITE_MODEL_SHA256_MISMATCH"
                    raise ValueError(
                        f"mmWave model SHA-256 mismatch: expected={expected_sha256}, "
                        f"actual={self.sha256_hash}"
                    )
                self.sha256_matches = True
                self.interpreter = tflite.Interpreter(model_path=str(self.model_path))
                self.interpreter.allocate_tensors()
                self.input_info = self.interpreter.get_input_details()[0]
                self.output_info = self.interpreter.get_output_details()[0]
                self._validate_tensor_contract()
            except Exception as e:
                print(f"⚠️ [MMWaveInterpreter] TFLite 로드 경고: {e}")
                self.interpreter = None
                if self.load_error_reason is None:
                    self.load_error_reason = "TFLITE_MODEL_LOAD_ERROR"
        else:
            self.load_error_reason = "TFLITE_MODEL_FILE_MISSING"

    @staticmethod
    def _read_scalar_stat(value: object, field_name: str) -> float:
        array = np.asarray(value, dtype=np.float32).reshape(-1)
        if array.size != 1 or not np.all(np.isfinite(array)):
            raise ValueError(f"mmWave metadata {field_name} must contain one finite value")
        return float(array[0])

    @staticmethod
    def _dtype_name(dtype: object) -> str:
        return np.dtype(dtype).name

    def _validate_tensor_contract(self) -> None:
        for label, actual, expected in (
            ("input", self.input_info, self.model_meta["input"]),
            ("output", self.output_info, self.model_meta["output"]),
        ):
            actual_shape = [int(value) for value in actual["shape"]]
            if actual_shape != expected["shape"]:
                raise ValueError(
                    f"mmWave {label} shape mismatch: expected={expected['shape']}, "
                    f"actual={actual_shape}"
                )
            actual_dtype = self._dtype_name(actual["dtype"])
            if actual_dtype != expected["dtype"]:
                raise ValueError(
                    f"mmWave {label} dtype mismatch: expected={expected['dtype']}, "
                    f"actual={actual_dtype}"
                )

            expected_scale = expected.get("scale")
            expected_zero_point = expected.get("zero_point")
            if expected_scale is not None:
                actual_scale, actual_zero_point = actual["quantization"]
                if not np.isclose(float(actual_scale), float(expected_scale), rtol=0, atol=1e-12):
                    raise ValueError(
                        f"mmWave {label} scale mismatch: expected={expected_scale}, "
                        f"actual={actual_scale}"
                    )
                if int(actual_zero_point) != int(expected_zero_point):
                    raise ValueError(
                        f"mmWave {label} zero_point mismatch: expected={expected_zero_point}, "
                        f"actual={actual_zero_point}"
                    )

    def prepare_window(self, window: np.ndarray) -> np.ndarray:
        """300샘플 10Hz resp_phase 파형 검증 및 Z-Score 정규화 및 INT8/FLOAT32 양자화"""
        array = np.asarray(window, dtype=np.float32)

        if array.shape == (300,):
            array = array[None, ..., None]
        elif array.shape == (300, 1):
            array = array[None, ...]
        elif array.shape != (1, 300, 1):
            raise ValueError(f"mmWave window shape must be (300,), (300,1), or (1,300,1), got {array.shape}")

        if not np.all(np.isfinite(array)):
            raise ValueError("mmWave window contains NaN or infinity")

        # Z-Score 정규화
        normalized = (array - self.mean) / self.std

        # INT8 양자화 처리 (Interpreter 존재 시)
        if self.interpreter is not None:
            dtype = self.input_info["dtype"]
            if np.issubdtype(dtype, np.integer):
                scale, zero_point = self.input_info["quantization"]
                if scale > 0:
                    quantized = np.rint(normalized / scale + zero_point)
                    limits = np.iinfo(dtype)
                    quantized = np.clip(quantized, limits.min, limits.max)
                    return quantized.astype(dtype)

        return normalized.astype(np.float32)

    def decode_output(self, raw_output: np.ndarray) -> np.ndarray:
        """INT8 / FLOAT32 역양자화 처리"""
        if self.interpreter is not None:
            dtype = self.output_info["dtype"]
            if np.issubdtype(dtype, np.integer):
                scale, zero_point = self.output_info["quantization"]
                if scale > 0:
                    probs = (raw_output.astype(np.float32) - zero_point) * scale
                    return probs[0]

        return raw_output[0].astype(np.float32)

    def predict(self, window: np.ndarray) -> MMWavePrediction:
        input_tensor = self.prepare_window(window)
        started = time.perf_counter()

        if self.interpreter is not None:
            self.interpreter.set_tensor(self.input_info["index"], input_tensor)
            self.interpreter.invoke()
            raw_output = self.interpreter.get_tensor(self.output_info["index"])
            probabilities = self.decode_output(raw_output)
            probabilities = np.clip(probabilities, 0.0, None)
            total = float(np.sum(probabilities))
            if total > 0:
                probabilities = probabilities / total
            else:
                probabilities = np.array([0.333, 0.333, 0.334], dtype=np.float32)
            fallback_used = False
            fallback_reason = None
            model_id_str = self.model_meta["model_id"]
        else:
            # Fallback heuristic calculation for 300-sample window
            std_val = float(np.std(window))
            if std_val < 0.05:  # Flat line -> Apnea
                probabilities = np.array([0.02, 0.03, 0.95], dtype=np.float32)
            elif std_val > 0.5:  # Rapid/Abnormal
                probabilities = np.array([0.10, 0.85, 0.05], dtype=np.float32)
            else:  # Normal
                probabilities = np.array([0.92, 0.05, 0.03], dtype=np.float32)
            fallback_used = True
            fallback_reason = self.load_error_reason or "TFLITE_MODEL_LOAD_ERROR"
            model_id_str = "mmwave_heuristic_fallback"

        latency_ms = (time.perf_counter() - started) * 1000.0
        class_index = int(np.argmax(probabilities))

        return MMWavePrediction(
            class_index=class_index,
            class_name=self.class_map.get(class_index, f"CLASS_{class_index}"),
            confidence=float(probabilities[class_index]),
            probabilities=[float(p) for p in probabilities],
            latency_ms=float(latency_ms),
            model_id=model_id_str,
            model_version=self.model_meta["version"],
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
