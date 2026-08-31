#!/usr/bin/env python3
"""Evaluate the committed Thermal V2 Candidate A A0 standalone TFLite artifact.

Loads canonical PUBLIC_SDT DEVELOPMENT only. LOCKED_PUBLIC_TEST is never referenced.
Does not train. Does not select a model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datasets.thermal import tv2_ca_metrics as metrics  # noqa: E402
from datasets.thermal import tv2_ca_sdt_source as sdt  # noqa: E402
from inference import thermal_tv2_a0 as a0  # noqa: E402


def _predict_tflite(interpreter, inp, out, batch: np.ndarray) -> tuple[np.ndarray, np.ndarray, int, int]:
    n = batch.shape[0]
    probs = np.empty((n, 3), dtype=np.float32)
    failures = 0
    nonfinite = 0
    for i in range(n):
        try:
            interpreter.set_tensor(inp["index"], batch[i:i + 1])
            interpreter.invoke()
            row = np.asarray(interpreter.get_tensor(out["index"]), dtype=np.float32)[0]
            if not np.isfinite(row).all():
                nonfinite += 1
                failures += 1
                probs[i] = np.nan
            else:
                probs[i] = row
        except Exception:
            failures += 1
            nonfinite += 1
            probs[i] = np.nan
    pred = np.full(n, -1, dtype=np.int64)
    ok = np.isfinite(probs).all(axis=1)
    pred[ok] = np.argmax(probs[ok], axis=1)
    return probs, pred, nonfinite, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Thermal V2 A0 standalone DEVELOPMENT evaluation")
    parser.add_argument("--canonical-root", required=True)
    parser.add_argument("--evaluate-development", action="store_true")
    parser.add_argument("--parity-with-keras", action="store_true")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--project-root", default=str(ROOT))
    args = parser.parse_args()
    if not args.evaluate_development:
        parser.error("--evaluate-development is required")

    project_root = Path(args.project_root)
    canonical_root = Path(args.canonical_root)
    manifest = a0.load_manifest(project_root / "config/thermal/tv2_a0_standalone_prototype_manifest.json")

    identity = sdt.verify_role(canonical_root, "DEVELOPMENT", verify_checksums=False)
    spec = sdt.CANONICAL_ARTIFACTS["DEVELOPMENT"]
    frames = np.load(canonical_root / spec["tensor_relpath"], mmap_mode="r")
    if frames.shape != (spec["rows"], 62, 80):
        raise SystemExit(f"unexpected DEVELOPMENT shape {frames.shape}")
    loaded = sdt.load_role(canonical_root, "DEVELOPMENT", verify_checksums=False)
    labels = loaded["labels"]

    interpreter, inp, out, tflite_sha = a0.load_tflite_interpreter(project_root, manifest)
    preprocessed = a0.preprocess_canonical_batch(np.asarray(frames, dtype=np.float32))
    tflite_probs, tflite_pred, tflite_nonfinite, tflite_failures = _predict_tflite(
        interpreter, inp, out, preprocessed,
    )
    scored = tflite_pred >= 0
    tflite_metrics = metrics.evaluate(labels[scored], tflite_pred[scored]) if scored.any() else {}

    payload: dict = {
        "role": "PUBLIC_SDT_DEVELOPMENT",
        "sample_count": int(labels.size),
        "scored_count": int(scored.sum()),
        "tflite_sha256": tflite_sha,
        "sdt_identity": identity,
        "tflite_metrics": tflite_metrics,
        "tflite_nonfinite_output_count": int(tflite_nonfinite),
        "tflite_inference_failure_count": int(tflite_failures),
        "LOCKED_PUBLIC_TEST_ACCESS": 0,
    }

    if args.parity_with_keras:
        import tensorflow as tf

        keras_rel = manifest["keras"]["repository_relative_path"]
        keras_path = project_root / keras_rel
        keras_sha = a0.sha256_file(keras_path)
        if keras_sha != manifest["keras"]["sha256"]:
            raise SystemExit(f"Keras SHA-256 mismatch: {keras_sha}")
        model = tf.keras.models.load_model(keras_path, compile=False)
        keras_probs = model.predict(preprocessed, batch_size=256, verbose=0).astype(np.float32)
        keras_nonfinite = int((~np.isfinite(keras_probs)).any(axis=1).sum())
        keras_pred = np.argmax(keras_probs, axis=1)
        keras_metrics = metrics.evaluate(labels, keras_pred)
        abs_diff = np.abs(keras_probs - tflite_probs)
        finite_both = np.isfinite(keras_probs).all(axis=1) & np.isfinite(tflite_probs).all(axis=1)
        agree = int((keras_pred[finite_both] == tflite_pred[finite_both]).sum())
        n_both = int(finite_both.sum())
        payload["keras_sha256"] = keras_sha
        payload["keras_metrics"] = keras_metrics
        payload["keras_nonfinite_output_count"] = keras_nonfinite
        payload["parity"] = {
            "samples": n_both,
            "argmax_agreement_count": agree,
            "argmax_agreement_rate": (agree / n_both) if n_both else 0.0,
            "max_abs_diff": float(np.max(abs_diff[finite_both])) if n_both else None,
            "mean_abs_diff": float(np.mean(abs_diff[finite_both])) if n_both else None,
            "keras_nonfinite": keras_nonfinite,
            "tflite_nonfinite": int(tflite_nonfinite),
            "status": "PASS" if n_both == labels.size and agree == n_both else "MISMATCH",
        }

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        Path(args.output_json).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
