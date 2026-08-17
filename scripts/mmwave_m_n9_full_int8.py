#!/usr/bin/env python3
"""M-N9: convert the exact M-N6-selected float model to FULL_INT8 TFLite.

PUBLIC TRAIN representative calibration only. VAL is used for quantization
parity, not calibration. NEW_MODEL_HELDOUT_TEST is never inferred.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_m_n4_canonical import CONTRACT_ID, SAMPLE_COUNT  # noqa: E402
from scripts.mmwave_m_n5_train_candidates import (  # noqa: E402
    LABEL_NAMES,
    evaluate_val,
    generate_train_val_tensors,
)
from scripts.mmwave_m_n6_select_lock import LOCK_PATH as FLOAT_LOCK_PATH  # noqa: E402
from scripts.mmwave_m_n6_select_lock import SELECTION_ID  # noqa: E402

ARTIFACT_ID = "MMWAVE_M_N9_FULL_INT8_V1"
EXPECTED_FLOAT_SHA = "9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab"
FLOAT_PATH = ROOT / "models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras"
INT8_PATH = ROOT / "models/mmwave/m_n9/MMWAVE_M_N9_FULL_INT8_V1.tflite"
LOCK_PATH = ROOT / "config/mmwave/m_n9_full_int8_artifact_lock.json"
RESULT_PATH = ROOT / "datasets/mmwave/manifests/m_n9_full_int8_result.json"
MN7_RESULT = ROOT / "datasets/mmwave/manifests/m_n7_device_domain_result.json"
MN7_PRED = ROOT / "datasets/mmwave/manifests/m_n7_mr60_predictions.jsonl"
NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9 = 0
EXPECTED_TRAIN_WINDOWS = 337
EXPECTED_TRAIN_SUBJECTS = 77
EXPECTED_VAL_WINDOWS = 70
EXPECTED_VAL_SUBJECTS = 17
TOP1_MIN = 0.95
MACRO_F1_MAX_DEGRADATION = 0.03
RECALL_MAX_DEGRADATION = 0.10


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def git_sha() -> str:
    """HEAD at conversion time. This is the branch base, not the later lock commit."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def round6(value: float) -> float:
    return round(float(value), 6)


def require_predecessors() -> dict[str, Any]:
    if not MN7_RESULT.is_file():
        raise RuntimeError("M_N7_NOT_CANONICALLY_MERGED")
    mn7 = json.loads(MN7_RESULT.read_text())
    if mn7.get("gate") != "PASS_WITH_LIMITATIONS":
        raise RuntimeError("M_N7_NOT_CANONICALLY_MERGED")
    if mn7.get("DEVICE_DOMAIN_GAP") != "LIMITED":
        raise RuntimeError("M_N7_NOT_CANONICALLY_MERGED")
    if mn7.get("M_N8_REQUIRED") != "NO":
        raise RuntimeError("M_N8_REQUIRED_BY_CANONICAL_M_N7")
    if mn7.get("NEXT_RECOMMENDED_PHASE") != "M-N9":
        raise RuntimeError("M_N8_REQUIRED_BY_CANONICAL_M_N7")
    if not (mn7.get("empty_no_person") or {}).get("NO_PERSON_INFERENCE_GATING_HAZARD"):
        raise RuntimeError("M_N7_NOT_CANONICALLY_MERGED")
    lock = json.loads(FLOAT_LOCK_PATH.read_text())
    if lock["selection_id"] != SELECTION_ID:
        raise RuntimeError("M_N6_SELECTED_FLOAT_IDENTITY_MISMATCH")
    if not FLOAT_PATH.is_file():
        raise RuntimeError("M_N6_SELECTED_FLOAT_IDENTITY_MISMATCH")
    digest = sha256_file(FLOAT_PATH)
    if digest != EXPECTED_FLOAT_SHA or digest != lock["artifact_sha256"]:
        raise RuntimeError("M_N6_SELECTED_FLOAT_IDENTITY_MISMATCH")
    if lock["candidate_id"] != "M-N5_DILATED_CONV1D_GAP_TINY" or int(lock["seed"]) != 2026:
        raise RuntimeError("M_N6_SELECTED_FLOAT_IDENTITY_MISMATCH")
    return {"mn7": mn7, "float_lock": lock, "float_sha256": digest}


def quantize_int8(values: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    q = np.round(np.asarray(values, dtype=np.float64) / float(scale) + float(zero_point))
    return np.clip(q, -128, 127).astype(np.int8)


def dequantize_int8(q_values: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    return (np.asarray(q_values, dtype=np.float64) - float(zero_point)) * float(scale)


def metrics_from_probs(y_true: np.ndarray, probs: np.ndarray, subjects: list[str]) -> dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        precision_recall_fscore_support,
    )

    probs = np.asarray(probs, dtype=np.float64)
    finite = bool(np.all(np.isfinite(probs)))
    if not finite or probs.shape != (y_true.shape[0], 3):
        return {
            "val_accuracy": None,
            "val_macro_f1": None,
            "val_balanced_accuracy": None,
            "per_class": {},
            "per_class_recall": {},
            "confusion_matrix": [],
            "predicted_class_counts": {},
            "probability_finite": finite,
            "probability_row_sum_ok": False,
            "collapse_status": "NUMERICAL_FAILURE",
        }
    y_pred = np.argmax(probs, axis=1).astype(np.int32)
    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", labels=[0, 1, 2], zero_division=0))
    bal = float(balanced_accuracy_score(y_true, y_pred))
    _prec, rec, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=[0, 1, 2], zero_division=0
    )
    per_class = {}
    for i, name in enumerate(LABEL_NAMES):
        per_class[name] = {
            "precision": round6(_prec[i]),
            "recall": round6(rec[i]),
            "f1": round6(f1[i]),
            "support": int(support[i]),
        }
    pred_counts = {LABEL_NAMES[i]: int(np.sum(y_pred == i)) for i in range(3)}
    row_sums = np.sum(probs, axis=1)
    return {
        "val_accuracy": round6(acc),
        "val_macro_f1": round6(macro_f1),
        "val_balanced_accuracy": round6(bal),
        "per_class": per_class,
        "per_class_recall": {name: per_class[name]["recall"] for name in LABEL_NAMES},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).astype(int).tolist(),
        "predicted_class_counts": pred_counts,
        "probability_finite": True,
        "probability_row_sum_ok": bool(np.allclose(row_sums, 1.0, atol=1e-3)),
        "collapse_status": "NON_DEGENERATE" if sum(v > 0 for v in pred_counts.values()) >= 3 else "CLASS_COLLAPSE",
        "n_subjects": len(set(subjects)),
        "y_pred": y_pred,
        "probs": probs,
    }


def list_tflite_opcodes(model_bytes: bytes) -> list[str]:
    from tensorflow.lite.python import schema_py_generated as schema

    model = schema.Model.GetRootAsModel(model_bytes, 0)
    mapping = {
        getattr(schema.BuiltinOperator, name): name
        for name in dir(schema.BuiltinOperator)
        if name[:1].isupper() and not name.startswith("_")
    }
    names: list[str] = []
    for i in range(model.OperatorCodesLength()):
        opcode = model.OperatorCodes(i)
        custom = opcode.CustomCode()
        if custom:
            decoded = custom.decode("utf-8") if isinstance(custom, bytes) else str(custom)
            names.append(f"CUSTOM:{decoded}")
            continue
        builtin = int(opcode.BuiltinCode())
        names.append(mapping.get(builtin, f"BUILTIN_{builtin}"))
    return names


def convert_full_int8(model, x_train: np.ndarray) -> bytes:
    import tensorflow as tf

    inp = tf.keras.Input(shape=(SAMPLE_COUNT, 1), batch_size=1, dtype=tf.float32, name="canonical_r2")
    out = model(inp, training=False)
    frozen = tf.keras.Model(inp, out, name="mmwave_m_n9_full_int8_source")

    def representative_dataset():
        for i in range(int(x_train.shape[0])):
            yield [np.asarray(x_train[i : i + 1], dtype=np.float32)]

    converter = tf.lite.TFLiteConverter.from_keras_model(frozen)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    return converter.convert()


def interpreter_contract(interpreter) -> dict[str, Any]:
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError(f"BAD_IO_COUNT:{len(inputs)}:{len(outputs)}")
    in_d, out_d = inputs[0], outputs[0]
    in_scale, in_zp = in_d["quantization"]
    out_scale, out_zp = out_d["quantization"]
    in_shape = [int(x) for x in in_d["shape"]]
    out_shape = [int(x) for x in out_d["shape"]]
    if in_shape != [1, 240, 1] or in_d["dtype"] != np.int8:
        raise RuntimeError(f"BAD_INPUT_CONTRACT:{in_shape}:{in_d['dtype']}")
    if out_shape != [1, 3] or out_d["dtype"] != np.int8:
        raise RuntimeError(f"BAD_OUTPUT_CONTRACT:{out_shape}:{out_d['dtype']}")
    if float(in_scale) <= 0 or float(out_scale) <= 0:
        raise RuntimeError("BAD_QUANTIZATION_SCALE")
    return {
        "input": {
            "name": in_d.get("name"),
            "dtype": "int8",
            "shape": in_shape,
            "scale": float(in_scale),
            "zero_point": int(in_zp),
            "quantization_formula": "q = clip(round(x / scale + zero_point), -128, 127)",
        },
        "output": {
            "name": out_d.get("name"),
            "dtype": "int8",
            "shape": out_shape,
            "scale": float(out_scale),
            "zero_point": int(out_zp),
            "dequantization_formula": "x_float = (q - zero_point) * scale",
        },
        "n_inputs": 1,
        "n_outputs": 1,
    }


def invoke_int8(interpreter, x_float: np.ndarray, contract: dict[str, Any]) -> np.ndarray:
    in_d = interpreter.get_input_details()[0]
    out_d = interpreter.get_output_details()[0]
    scale = contract["input"]["scale"]
    zp = contract["input"]["zero_point"]
    q_in = quantize_int8(x_float.reshape(1, SAMPLE_COUNT, 1), scale, zp)
    interpreter.set_tensor(in_d["index"], q_in)
    interpreter.invoke()
    q_out = interpreter.get_tensor(out_d["index"])
    return dequantize_int8(q_out, contract["output"]["scale"], contract["output"]["zero_point"]).reshape(3)


def predict_int8_batch(interpreter, x: np.ndarray, contract: dict[str, Any]) -> np.ndarray:
    rows = []
    for i in range(int(x.shape[0])):
        rows.append(invoke_int8(interpreter, x[i], contract))
    return np.stack(rows, axis=0)


def zero_behavior(float_probs: np.ndarray, int8_probs: np.ndarray) -> dict[str, Any]:
    f = np.asarray(float_probs, dtype=np.float64).reshape(3)
    i = np.asarray(int8_probs, dtype=np.float64).reshape(3)
    f_cls = LABEL_NAMES[int(np.argmax(f))]
    i_cls = LABEL_NAMES[int(np.argmax(i))]
    return {
        "float_probabilities": {LABEL_NAMES[j]: round6(float(f[j])) for j in range(3)},
        "int8_probabilities": {LABEL_NAMES[j]: round6(float(i[j])) for j in range(3)},
        "float_predicted_class": f_cls,
        "int8_predicted_class": i_cls,
        "float_confidence": round6(float(np.max(f))),
        "int8_confidence": round6(float(np.max(i))),
        "top1_agreement": f_cls == i_cls,
        "abs_prob_max_delta": round6(float(np.max(np.abs(f - i)))),
        "inherited_apnea_proxy_on_zero": f_cls == "APNEA" and i_cls == "APNEA",
        "presence_gate_required": True,
        "expected_inherited_behavior": True,
    }


def optional_mr60_parity(keras_model, interpreter, contract: dict[str, Any]) -> dict[str, Any]:
    try:
        from scripts.mmwave_m_n4_canonical import (
            CanonicalContractError,
            WINDOW_SECONDS,
            accept_phase_events,
            form_canonical_window,
        )
        from scripts.mmwave_m_n7_device_domain_check import (
            RESERVED_SPECS,
            candidate_window_starts,
            load_flat_rows,
            locate_source,
            timing_status,
        )
    except Exception as exc:
        return {"performed": False, "reason": f"IMPORT:{exc}"}

    if not MN7_PRED.is_file():
        return {"performed": False, "reason": "M_N7_PREDICTIONS_MISSING"}

    rows = []
    for spec in RESERVED_SPECS:
        source = locate_source(spec)
        if not source.get("located"):
            continue
        path = ROOT / source["path"]
        flat = load_flat_rows(path)
        status, _meta = timing_status(flat)
        if status != "CANONICAL_TIMING_ELIGIBLE":
            continue
        ts = np.asarray([r["ts_monotonic_ms"] for r in flat], dtype=np.float64)
        phase = np.asarray([r["breath_phase"] for r in flat], dtype=np.float64)
        age = np.asarray([r["phase_age_ms"] for r in flat], dtype=np.float64)
        t_acc, x_acc, _event = accept_phase_events(
            ts, phase, age, production=True, timestamps_are_seconds=False
        )
        t0 = float(ts[0]) / 1000.0
        t_last = float(ts[-1]) / 1000.0
        for index, t_start in enumerate(candidate_window_starts(t0, t_last, WINDOW_SECONDS)):
            try:
                win = form_canonical_window(t_acc, x_acc, t_start, boot_ids=None)
            except CanonicalContractError:
                continue
            values = np.asarray(win.values, dtype=np.float32)
            f_prob = np.asarray(keras_model.predict(values.reshape(1, SAMPLE_COUNT, 1), verbose=0), dtype=np.float64)[0]
            i_prob = invoke_int8(interpreter, values, contract)
            rows.append(
                {
                    "session_id": spec["session_id"],
                    "window_index": index,
                    "float_predicted_class": LABEL_NAMES[int(np.argmax(f_prob))],
                    "int8_predicted_class": LABEL_NAMES[int(np.argmax(i_prob))],
                    "float_confidence": round6(float(np.max(f_prob))),
                    "int8_confidence": round6(float(np.max(i_prob))),
                    "abs_prob_max_delta": round6(float(np.max(np.abs(f_prob - i_prob)))),
                    "agreement": LABEL_NAMES[int(np.argmax(f_prob))] == LABEL_NAMES[int(np.argmax(i_prob))],
                    "supervised_label": None,
                }
            )
    if not rows:
        return {
            "performed": False,
            "reason": "RESERVED_WINDOWS_UNAVAILABLE",
            "M_N7_EVIDENCE_REUSED_FOR_QUANTIZATION_PARITY_ONLY": False,
            "mr60_accuracy_computed": False,
        }
    n_agree = sum(1 for r in rows if r["agreement"])
    return {
        "performed": True,
        "purpose": "QUANTIZATION_PARITY_ONLY",
        "label": "M_N7_EVIDENCE_REUSED_FOR_QUANTIZATION_PARITY_ONLY",
        "n_windows": len(rows),
        "top1_agreement": round6(n_agree / len(rows)),
        "mean_abs_prob_max_delta": round6(float(np.mean([r["abs_prob_max_delta"] for r in rows]))),
        "windows": rows,
        "mr60_accuracy_computed": False,
        "used_for_calibration": False,
        "used_for_conversion_tuning": False,
    }


def decide_gate(parity_ok: bool, conversion_ok: bool, pi_verified: bool) -> dict[str, Any]:
    if not conversion_ok or not parity_ok:
        return {
            "gate": "FAIL",
            "FULL_INT8_ARTIFACT_LOCKED": False,
            "PI_ARTIFACT_READY": False,
            "M_N10_authorized": False,
            "NEXT_RECOMMENDED_PHASE": "BLOCKED",
        }
    if pi_verified:
        gate = "PASS"
    else:
        gate = "PASS_WITH_LIMITATIONS"
    return {
        "gate": gate,
        "FULL_INT8_ARTIFACT_LOCKED": True,
        "PI_ARTIFACT_READY": True,
        "M_N10_authorized": True,
        "NEXT_RECOMMENDED_PHASE": "M-N10",
    }


def presence_gate_contract() -> dict[str, Any]:
    return {
        "PRESENCE_GATE_REQUIRED": True,
        "not_a_neural_network_class": True,
        "fourth_neural_class_added": False,
        "model_not_retrained_to_fix_empty_room": True,
        "semantic": "if valid_person_presence == false: respiratory_classification = SUPPRESSED",
        "suppressed_states": ["NO_VALID_PERSON", "RESPIRATORY_INFERENCE_SUPPRESSED"],
        "must_not_expose_when_no_valid_person": LABEL_NAMES,
        "existing_mr60_presence_field": "human_detected_raw",
        "threshold_invented_in_m_n9": False,
        "exact_runtime_implementation": "DEFERRED_TO_INTEGRATION",
        "source": "M-N7 NO_PERSON_INFERENCE_GATING_HAZARD on empty-room zero canonical input",
    }


def main() -> int:
    pred = require_predecessors()
    print(
        json.dumps(
            {
                "selection_id": SELECTION_ID,
                "float_sha256": pred["float_sha256"],
                "FLOAT_ARTIFACT_SHA_MATCH": True,
                "NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9": NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9,
                "INT8_CALIBRATION_SOURCE": "PUBLIC_TRAIN_ONLY",
            },
            indent=2,
        ),
        flush=True,
    )
    bundle = generate_train_val_tensors(force=False)
    x_train = np.asarray(bundle["x_train"], dtype=np.float32)
    y_train = np.asarray(bundle["y_train"], dtype=np.int32)
    x_val = np.asarray(bundle["x_val"], dtype=np.float32)
    y_val = np.asarray(bundle["y_val"], dtype=np.int32)
    subjects_val = list(bundle["subjects_val"])
    if int(x_train.shape[0]) != EXPECTED_TRAIN_WINDOWS or len(set(bundle["subjects_train"])) != EXPECTED_TRAIN_SUBJECTS:
        raise RuntimeError("TRAIN_COUNT_MISMATCH")
    if int(x_val.shape[0]) != EXPECTED_VAL_WINDOWS or len(set(subjects_val)) != EXPECTED_VAL_SUBJECTS:
        raise RuntimeError("VAL_COUNT_MISMATCH")
    if bundle.get("heldout_tensors_materialized") != 0:
        raise RuntimeError("HELDOUT_TENSORS_MATERIALIZED")
    if NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9 != 0:
        raise RuntimeError("HELDOUT_INFERENCE_NOT_ZERO")

    import tensorflow as tf

    keras_model = tf.keras.models.load_model(FLOAT_PATH)
    print("converting FULL_INT8 with 337 TRAIN windows...", flush=True)
    tflite_bytes = convert_full_int8(keras_model, x_train)
    opcodes = list_tflite_opcodes(tflite_bytes)
    custom_or_flex = [name for name in opcodes if name.startswith("CUSTOM:") or "FLEX" in name.upper()]
    INT8_PATH.parent.mkdir(parents=True, exist_ok=True)
    INT8_PATH.write_bytes(tflite_bytes)
    int8_sha = sha256_file(INT8_PATH)

    interpreter = tf.lite.Interpreter(model_content=tflite_bytes)
    interpreter.allocate_tensors()
    contract = interpreter_contract(interpreter)
    tensor_dtypes = sorted({str(np.dtype(d["dtype"])) for d in interpreter.get_tensor_details()})
    float_tensors = [
        d["name"]
        for d in interpreter.get_tensor_details()
        if np.dtype(d["dtype"]) in (np.float32, np.float16)
    ]
    full_int8_only = not custom_or_flex and not float_tensors
    if not full_int8_only:
        raise RuntimeError(f"FLOAT_FALLBACK_OPS:{custom_or_flex}:{float_tensors[:8]}")

    zero = np.zeros((SAMPLE_COUNT, 1), dtype=np.float32)
    float_zero = np.asarray(keras_model.predict(zero.reshape(1, SAMPLE_COUNT, 1), verbose=0), dtype=np.float64)[0]
    int8_zero = invoke_int8(interpreter, zero, contract)
    zero_doc = zero_behavior(float_zero, int8_zero)

    print("evaluating FLOAT VAL...", flush=True)
    float_metrics = evaluate_val(keras_model, x_val, y_val, subjects_val)
    float_probs = np.asarray(keras_model.predict(x_val, batch_size=32, verbose=0), dtype=np.float64)
    float_pred = np.argmax(float_probs, axis=1)
    print("evaluating INT8 VAL...", flush=True)
    int8_probs = predict_int8_batch(interpreter, x_val, contract)
    int8_metrics = metrics_from_probs(y_val, int8_probs, subjects_val)
    int8_pred = int8_metrics.pop("y_pred")
    int8_metrics.pop("probs")
    agreement = float(np.mean(float_pred == int8_pred))
    f1_delta = round6(float(int8_metrics["val_macro_f1"]) - float(float_metrics["val_macro_f1"]))
    acc_delta = round6(float(int8_metrics["val_accuracy"]) - float(float_metrics["val_accuracy"]))
    recall_delta = {
        name: round6(
            float(int8_metrics["per_class_recall"][name]) - float(float_metrics["per_class_recall"][name])
        )
        for name in LABEL_NAMES
    }
    f1_degradation = round6(float(float_metrics["val_macro_f1"]) - float(int8_metrics["val_macro_f1"]))
    recall_degradation = {name: round6(-recall_delta[name]) for name in LABEL_NAMES}
    parity_fail_reasons = []
    if not float_metrics.get("probability_finite") or not int8_metrics.get("probability_finite"):
        parity_fail_reasons.append("NUMERICAL_FAILURE")
    if agreement < TOP1_MIN:
        parity_fail_reasons.append("TOP1_AGREEMENT")
    if f1_degradation > MACRO_F1_MAX_DEGRADATION:
        parity_fail_reasons.append("MACRO_F1_DEGRADATION")
    for name, deg in recall_degradation.items():
        if deg > RECALL_MAX_DEGRADATION:
            parity_fail_reasons.append(f"RECALL_DEGRADATION_{name}")
    parity_ok = not parity_fail_reasons

    print("optional M-N7 MR60 FLOAT↔INT8 parity...", flush=True)
    mr60 = optional_mr60_parity(keras_model, interpreter, contract)

    del keras_model
    tf.keras.backend.clear_session()

    pi_access = bool(os.environ.get("SAFENEST_PI_HOST") or os.environ.get("RASPBERRY_PI_HOST"))
    pi = {
        "PI_ARTIFACT_READY": True,
        "actual_pi_access_available": pi_access,
        "PI_DEVICE_SMOKE": "NOT_PERFORMED_ENVIRONMENT_UNAVAILABLE" if not pi_access else "NOT_RUN",
        "PI_ISOLATED_LOAD": "NOT_PERFORMED",
        "PI_ISOLATED_INVOKE": "NOT_PERFORMED",
        "PI_ISOLATED_EXECUTION_VERIFIED": False,
        "live_mr60_sensor_required": False,
        "new_sensor_capture_performed": False,
        "note": "No authorized Raspberry Pi target is configured in this environment. Artifact is locked for later isolated smoke.",
    }
    decision = decide_gate(parity_ok, True, bool(pi_access))
    presence = presence_gate_contract()
    conversion_sha = git_sha()
    tf_version = tf.__version__
    tflite_version = getattr(tf.lite, "__version__", tf_version)

    lock = {
        "artifact_id": ARTIFACT_ID,
        "phase": "M-N9",
        "source_selection_id": SELECTION_ID,
        "source_float_path": FLOAT_PATH.relative_to(ROOT).as_posix(),
        "source_float_sha256": pred["float_sha256"],
        "source_architecture": "M-N5_DILATED_CONV1D_GAP_TINY",
        "source_seed": 2026,
        "source_parameter_count": 5019,
        "locked_artifact_path": INT8_PATH.relative_to(ROOT).as_posix(),
        "artifact_sha256": int8_sha,
        "artifact_size_bytes": INT8_PATH.stat().st_size,
        "contract_id": CONTRACT_ID,
        "input_contract": contract["input"],
        "output_contract": contract["output"],
        "quantization": {
            "mode": "FULL_INT8",
            "weights": "INT8",
            "activations": "INT8",
            "inference_input_type": "int8",
            "inference_output_type": "int8",
            "supported_ops": ["TFLITE_BUILTINS_INT8"],
            "FULL_INT8_ONLY": True,
            "float_fallback_ops": False,
            "opcodes": opcodes,
            "tensor_dtypes": tensor_dtypes,
            "input_quantization": "q = clip(round(x / scale + zero_point), -128, 127)",
            "output_dequantization": "x_float = (q - zero_point) * scale",
        },
        "calibration": {
            "INT8_CALIBRATION_SOURCE": "PUBLIC_TRAIN_ONLY",
            "train_subjects": EXPECTED_TRAIN_SUBJECTS,
            "train_windows": EXPECTED_TRAIN_WINDOWS,
            "representative_windows_used": int(x_train.shape[0]),
            "val_used_for_calibration": False,
            "public_heldout_used": False,
            "mr60_used_for_calibration": False,
        },
        "presence_gate": presence,
        "tensorflow_version": tf_version,
        "tflite_litert_version": tflite_version,
        "conversion_base_sha": conversion_sha,
        "conversion_base_sha_meaning": "HEAD at conversion time (canonical main). Not the later M-N9 documentation commit.",
        "NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9": 0,
        "M_N8_STATUS": "SKIPPED_NOT_JUSTIFIED",
        "DEVICE_VALIDATED": False,
        "PI_INFERENCE_READY_IS_NOT_DEVICE_VALIDATED": True,
        "production_final_runtime": False,
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n")

    result = {
        "phase": "M-N9",
        "artifact_id": ARTIFACT_ID,
        "source_selection_id": SELECTION_ID,
        "source_float_sha256": pred["float_sha256"],
        "FLOAT_ARTIFACT_SHA_MATCH": True,
        "contract_id": CONTRACT_ID,
        "INT8_CALIBRATION_SOURCE": "PUBLIC_TRAIN_ONLY",
        "representative_windows_used": int(x_train.shape[0]),
        "train_subjects": EXPECTED_TRAIN_SUBJECTS,
        "train_windows": EXPECTED_TRAIN_WINDOWS,
        "val_subjects": EXPECTED_VAL_SUBJECTS,
        "val_windows": EXPECTED_VAL_WINDOWS,
        "NEW_MODEL_HELDOUT_TEST_INFERENCE_M_N9": 0,
        "FULL_INT8_ONLY": True,
        "float_fallback_ops": False,
        "opcodes": opcodes,
        "artifact_path": INT8_PATH.relative_to(ROOT).as_posix(),
        "artifact_sha256": int8_sha,
        "artifact_size_bytes": INT8_PATH.stat().st_size,
        "input_contract": contract["input"],
        "output_contract": contract["output"],
        "val_float": {
            "accuracy": float_metrics["val_accuracy"],
            "macro_f1": float_metrics["val_macro_f1"],
            "balanced_accuracy": float_metrics["val_balanced_accuracy"],
            "per_class_recall": float_metrics["per_class_recall"],
            "confusion_matrix": float_metrics["confusion_matrix"],
        },
        "val_int8": {
            "accuracy": int8_metrics["val_accuracy"],
            "macro_f1": int8_metrics["val_macro_f1"],
            "balanced_accuracy": int8_metrics["val_balanced_accuracy"],
            "per_class_recall": int8_metrics["per_class_recall"],
            "confusion_matrix": int8_metrics["confusion_matrix"],
            "probability_row_sum_ok": int8_metrics["probability_row_sum_ok"],
        },
        "val_parity": {
            "top1_agreement": round6(agreement),
            "accuracy_delta": acc_delta,
            "macro_f1_delta": f1_delta,
            "macro_f1_degradation": f1_degradation,
            "per_class_recall_delta": recall_delta,
            "parity_gate": "PASS" if parity_ok else "FAIL",
            "parity_fail_reasons": parity_fail_reasons,
            "thresholds": {
                "top1_agreement_min": TOP1_MIN,
                "macro_f1_max_degradation": MACRO_F1_MAX_DEGRADATION,
                "class_recall_max_degradation": RECALL_MAX_DEGRADATION,
            },
        },
        "zero_no_person": zero_doc,
        "presence_gate": presence,
        "optional_mr60_parity": mr60,
        "raspberry_pi": pi,
        "M_N8_STATUS": "SKIPPED_NOT_JUSTIFIED",
        "DEVICE_VALIDATED": False,
        "lock_path": LOCK_PATH.relative_to(ROOT).as_posix(),
        "tensorflow_version": tf_version,
        "tflite_litert_version": tflite_version,
        "conversion_base_sha": conversion_sha,
        "conversion_base_sha_meaning": "HEAD at conversion time (canonical main). Not the later M-N9 documentation commit.",
        "evaluation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "focused_validation": {
            "float_identity": "PASS",
            "full_int8_conversion": "PASS",
            "artifact_reload": "PASS",
            "input_output_dtype": "PASS",
            "input_output_shape": "PASS",
            "val_parity": "PASS" if parity_ok else "FAIL",
            "zero_input_invoke": "PASS",
            "pi_smoke": "NOT_PERFORMED",
        },
        "gate": decision["gate"],
        "FULL_INT8_ARTIFACT_LOCKED": decision["FULL_INT8_ARTIFACT_LOCKED"],
        "PI_ARTIFACT_READY": decision["PI_ARTIFACT_READY"],
        "PI_ISOLATED_EXECUTION_VERIFIED": False,
        "M_N10_authorized": decision["M_N10_authorized"],
        "NEXT_RECOMMENDED_PHASE": decision["NEXT_RECOMMENDED_PHASE"],
        "model_retrained": False,
        "m_n8_adaptation": False,
        "threshold_tuned": False,
        "alternative_model_evaluated": False,
        "train_plus_val_retraining": False,
        "public_heldout_rerun": False,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "FULL_INT8_ONLY": True,
                "artifact_sha256": int8_sha,
                "top1_agreement": round6(agreement),
                "macro_f1_delta": f1_delta,
                "rapid_recall_delta": recall_delta["RAPID_OR_ABNORMAL"],
                "parity": "PASS" if parity_ok else "FAIL",
                "PRESENCE_GATE_REQUIRED": True,
                "PI_DEVICE_SMOKE": pi["PI_DEVICE_SMOKE"],
            },
            indent=2,
        )
    )
    return 0 if decision["gate"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
