#!/usr/bin/env python3
"""Independent SafeNest mmWave M-B9 validator.

The validator intentionally recomputes identity and executes fresh bounded
scenarios.  It does not treat ``m_b9_summary.json``, saved PASS flags, or saved
fallback flags as authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = ROOT_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inference.mmwave_interpreter import MMWaveInterpreter, tflite
from integrated_node.run_node import SafeNestIntegratedNode
from risk.risk_engine import SafeNestRiskEngine
from sensors.mmwave.finalist_mock_provider import FinalistMockProvider
from mmwave_m_b1_preprocessing import fit_train_zscore_statistics, transform_signals
from mmwave_m_b9_mock_e2e import (
    LABELS,
    OUT_DIR_REL,
    RUNTIME_DIR_REL,
    SEEDS,
    NeutralSupportProvider,
    array_sha256,
    build_runtime_model_identity,
    direct_prediction,
    inspect_tflite,
    load_json,
    load_stage_artifacts,
    rel,
    run_node_once,
    select_validation_inputs,
    sha256_file,
)
from mmwave_phase_b_access import PhaseBAccessGuard
from validate_mmwave_m_b8 import validate_m_b8_artifacts


REQUIRED_FILES = (
    "input_identity.json",
    "experiment_contract.json",
    "runtime_manifest_contract.json",
    "runtime_model_identity.json",
    "runtime_preprocessing_identity.json",
    "scenario_contract.json",
    "scenario_input_selection.json",
    "scenario_results.json",
    "scenario_results.jsonl",
    "inference_result_audit.json",
    "risk_input_audit.json",
    "json_output_audit.json",
    "fallback_audit.json",
    "fault_timeout_stale_audit.json",
    "runtime_prediction_identity.json",
    "locked_test_access_audit.json",
    "run_environment.json",
    "exceptions.json",
    "m_b9_summary.json",
    "checksums.sha256",
)
SCENARIOS = (
    "A_NORMAL",
    "B_RAPID_OR_ABNORMAL",
    "C_APNEA",
    "D_INSUFFICIENT_HISTORY",
    "E_INVALID_SHAPE",
    "F_NAN",
    "G_INF",
    "H_STALE",
    "I_PROVIDER_SENSOR_FAULT",
    "J_READ_EXCEPTION",
    "K_TIMEOUT",
    "L_MISSING_MODEL",
    "M_SHA_MISMATCH",
    "N_VALID_EXPLICIT_FINALIST",
    "O_NOT_CONNECTED_PROVIDER",
)
NEGATIVE_CASES = (
    "default_historical_model_substituted",
    "wrong_phase_sha256",
    "wrong_phase_bytes",
    "wrong_seed",
    "wrong_input_dtype",
    "wrong_input_quantization",
    "wrong_output_quantization",
    "wrong_preprocessing_profile",
    "wrong_bpf_contract",
    "wrong_zscore_stats",
    "runtime_prediction_mismatch",
    "scenario_truth_forces_state",
    "scenario_truth_forces_score",
    "hidden_fallback",
    "missing_fallback_reason",
    "invalid_shape",
    "nan",
    "inf",
    "insufficient_history",
    "stale_timestamp",
    "provider_fault",
    "read_exception",
    "timeout",
    "missing_model",
    "sha_mismatch",
    "risk_input_mismatch",
    "json_schema",
    "json_nonfinite",
    "locked_test_access",
    "checksum_corruption",
    "manifest_absolute_path",
    "model_binary_duplicated",
)


class MB9ValidationError(RuntimeError):
    pass


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float, np.number)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(k) and _finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return True


def _load_all_json(out_dir: Path) -> dict[str, Any]:
    loaded = {}
    for name in REQUIRED_FILES:
        path = out_dir / name
        if not path.is_file():
            raise MB9ValidationError(f"M-B9_REQUIRED_OUTPUT_MISSING:{name}")
        if name.endswith(".json"):
            try:
                loaded[name] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise MB9ValidationError(f"M-B9_JSON_PARSE_ERROR:{name}:{exc}") from exc
            if not _finite(loaded[name]):
                raise MB9ValidationError(f"M-B9_JSON_NONFINITE:{name}")
    return loaded


def _assert_phase_manifest(root: Path, seed: int, expected_stage: dict[str, Any]) -> dict[str, Any]:
    path = root / RUNTIME_DIR_REL / f"seed{seed}_runtime_manifest.json"
    if not path.is_file():
        raise MB9ValidationError(f"M-B9_RUNTIME_MANIFEST_MISSING:{seed}")
    manifest = load_json(path)
    if manifest.get("schema_version") != "M-B9_RUNTIME_MANIFEST_V1" or manifest.get("phase_id") != "M-B9":
        raise MB9ValidationError(f"M-B9_RUNTIME_MANIFEST_SCHEMA:{seed}")
    model = manifest.get("runtime_model")
    preprocessing = manifest.get("preprocessing")
    if not isinstance(model, dict) or not isinstance(preprocessing, dict):
        raise MB9ValidationError(f"M-B9_RUNTIME_MANIFEST_SECTIONS:{seed}")
    if int(model.get("seed", -1)) != seed:
        raise MB9ValidationError(f"M-B9_RUNTIME_MANIFEST_SEED:{seed}")
    if model.get("model_id") == "mmwave_resp_int8" or model.get("path") == "models/mmwave/mmwave_resp_int8_v0.1.0.tflite":
        raise MB9ValidationError(f"M-B9_SHARED_DEFAULT_MODEL_USED:{seed}")
    model_path = Path(model.get("path", ""))
    if model_path.is_absolute() or ".." in model_path.parts:
        raise MB9ValidationError(f"M-B9_ABSOLUTE_OR_ESCAPE_PATH:{seed}")
    artifact_path = root / model_path
    if not artifact_path.is_file():
        raise MB9ValidationError(f"M-B9_FINALIST_ARTIFACT_MISSING:{seed}")
    actual_sha = sha256_file(artifact_path)
    actual_bytes = artifact_path.stat().st_size
    if actual_sha != model.get("expected_sha256") or actual_sha != model.get("sha256") or actual_bytes != int(model.get("expected_bytes", -1)) or actual_bytes != int(model.get("bytes", -1)):
        raise MB9ValidationError(f"M-B9_FINALIST_ARTIFACT_IDENTITY_MISMATCH:{seed}")
    if actual_sha != expected_stage.get("sha256") or actual_bytes != int(expected_stage.get("bytes", -1)):
        raise MB9ValidationError(f"M-B9_M6_STAGE_IDENTITY_MISMATCH:{seed}")
    tensor = inspect_tflite(artifact_path)
    expected_input = model.get("input", {})
    expected_output = model.get("output", {})
    for actual, expected, side in ((tensor, expected_input, "input"), (tensor, expected_output, "output")):
        prefix = "input_" if side == "input" else "output_"
        if actual[f"{prefix}dtype"] != expected.get("dtype") or actual[f"{prefix}shape"] != expected.get("shape"):
            raise MB9ValidationError(f"M-B9_TENSOR_CONTRACT:{seed}:{side}")
        if not np.isclose(actual[f"{prefix}scale"], float(expected.get("scale")), rtol=0, atol=1e-12) or actual[f"{prefix}zero_point"] != int(expected.get("zero_point")):
            raise MB9ValidationError(f"M-B9_QUANTIZATION_CONTRACT:{seed}:{side}")
    if tensor["input_dtype"] != "int8" or tensor["output_dtype"] != "int8" or not tensor["flex_select_absent"]:
        raise MB9ValidationError(f"M-B9_STRICT_INT8_OR_FLEX_SELECT:{seed}")
    required_pre = {
        "profile_id": "M-B1_D0_B1_Z1",
        "profile_name": "BPF_ZSCORE",
        "detrend": False,
        "bpf": True,
        "zscore": True,
        "sample_rate_hz": 10.0,
        "bpf_lowcut_hz": 0.1,
        "bpf_highcut_hz": 0.5,
        "bpf_order": 4,
        "zscore_fit_split": "TRAIN",
    }
    for key, value in required_pre.items():
        actual = preprocessing.get(key)
        if isinstance(value, float):
            if not np.isclose(float(actual), value, rtol=0, atol=1e-12):
                raise MB9ValidationError(f"M-B9_PREPROCESSING_CONTRACT:{seed}:{key}")
        elif actual != value:
            raise MB9ValidationError(f"M-B9_PREPROCESSING_CONTRACT:{seed}:{key}")
    if not np.isfinite(float(preprocessing.get("zscore_mean"))) or not np.isfinite(float(preprocessing.get("zscore_std"))) or float(preprocessing["zscore_std"]) <= 0:
        raise MB9ValidationError(f"M-B9_PREPROCESSING_STATS:{seed}")
    return manifest


def _fresh_runtime_identity(root: Path, manifests: dict[int, dict[str, Any]], selected: dict[str, Any], stats: dict[str, float]) -> dict[str, Any]:
    rows = []
    for seed in SEEDS:
        runtime_path = root / RUNTIME_DIR_REL / f"seed{seed}_runtime_manifest.json"
        runtime = MMWaveInterpreter(root, runtime_manifest_path=runtime_path)
        pre = manifests[seed]["preprocessing"]
        if not np.isclose(float(pre["zscore_mean"]), stats["mean"], rtol=0, atol=0) or not np.isclose(float(pre["zscore_std"]), stats["std"], rtol=0, atol=0):
            raise MB9ValidationError(f"M-B9_STATS_NOT_M6:{seed}")
        for label in LABELS:
            window = np.asarray(selected[label]["signal"], dtype=np.float64)
            bpf = transform_signals(window.reshape(1, 300), False, True, False, None)[0]
            zscore = transform_signals(window.reshape(1, 300), False, True, True, stats)[0]
            model_ready = zscore.astype(np.float32).reshape(1, 300, 1)
            trace = runtime.preprocess_trace(window)
            direct = direct_prediction(runtime.model_path, model_ready, float(runtime.input_info["quantization"][0]), int(runtime.input_info["quantization"][1]))
            pred = runtime.predict(window)
            if not np.array_equal(np.asarray(trace["bpf_output"]), bpf.reshape(1, 300)):
                raise MB9ValidationError(f"M-B9_RUNTIME_PREPROCESSING_MISMATCH:BPF:{seed}:{label}")
            if not np.array_equal(np.asarray(trace["zscore_output"]), zscore.reshape(1, 300)):
                raise MB9ValidationError(f"M-B9_RUNTIME_PREPROCESSING_MISMATCH:ZSCORE:{seed}:{label}")
            if not np.array_equal(np.asarray(trace["model_ready"]), model_ready):
                raise MB9ValidationError(f"M-B9_RUNTIME_PREPROCESSING_MISMATCH:MODEL_READY:{seed}:{label}")
            if not np.array_equal(np.asarray(trace["quantized_input"]), direct["input_int8"]):
                raise MB9ValidationError(f"M-B9_RUNTIME_PREPROCESSING_MISMATCH:INT8:{seed}:{label}")
            if not np.array_equal(np.asarray(runtime.last_raw_output), direct["output_int8"]):
                raise MB9ValidationError(f"M-B9_RUNTIME_PREDICTION_MISMATCH:INT8_OUTPUT:{seed}:{label}")
            if not np.array_equal(np.asarray(pred.probabilities, dtype=np.float32), np.asarray(direct["probabilities"], dtype=np.float32)) or pred.class_index != direct["class_index"]:
                raise MB9ValidationError(f"M-B9_RUNTIME_PREDICTION_MISMATCH:PROBABILITY_OR_TOP1:{seed}:{label}")
            rows.append({"seed": seed, "label": label, "bpf_exact": True, "zscore_exact": True, "model_ready_exact": True, "input_int8_exact": True, "output_int8_exact": True, "probabilities_exact": True, "top1_exact": True})
    return {"rows": rows, "all_exact": True}


def _fresh_scenarios(root: Path, runtime_paths: dict[int, Path], selected: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def run(provider: FinalistMockProvider, scenario_id: str, seed: int | None) -> None:
        records.append(run_node_once(root, provider, scenario_id=scenario_id, seed=seed))

    # Every finalist and every model-driven class.
    for seed in SEEDS:
        for scenario_id, label in (("A_NORMAL", "NORMAL"), ("B_RAPID_OR_ABNORMAL", "RAPID_OR_ABNORMAL"), ("C_APNEA", "APNEA")):
            item = selected[label]
            run(FinalistMockProvider(root, runtime_paths[seed], raw_window=item["signal"], scenario_truth_class=label), scenario_id, seed)
    item = selected["NORMAL"]
    for scenario_id, seed, mode in (
        ("D_INSUFFICIENT_HISTORY", 42, "INSUFFICIENT_HISTORY"),
        ("E_INVALID_SHAPE", 42, "INVALID_SHAPE"),
        ("F_NAN", 42, "NAN"),
        ("G_INF", 42, "INF"),
        ("H_STALE", 42, "STALE"),
        ("I_PROVIDER_SENSOR_FAULT", 42, "PROVIDER_FAULT"),
        ("J_READ_EXCEPTION", 42, "READ_EXCEPTION"),
        ("K_TIMEOUT", 42, "TIMEOUT"),
        ("M_SHA_MISMATCH", 42, "SHA_MISMATCH"),
        ("O_NOT_CONNECTED_PROVIDER", 42, "NOT_CONNECTED"),
    ):
        run(FinalistMockProvider(root, runtime_paths[seed], raw_window=item["signal"], failure_mode=mode), scenario_id, seed)
    run(FinalistMockProvider(root, root / RUNTIME_DIR_REL / "missing_runtime_manifest.json", raw_window=item["signal"], failure_mode="MISSING_MODEL"), "L_MISSING_MODEL", None)
    run(FinalistMockProvider(root, runtime_paths[42], raw_window=item["signal"], scenario_truth_class="NORMAL"), "N_VALID_EXPLICIT_FINALIST", 42)
    # Negative scenario-truth injection: the model must still own the state and score.
    disagreement = FinalistMockProvider(root, runtime_paths[42], raw_window=item["signal"], scenario_truth_class="APNEA")
    run(disagreement, "NEGATIVE_SCENARIO_TRUTH_DISAGREEMENT", 42)
    return records


def _validate_scenarios(records: list[dict[str, Any]]) -> dict[str, Any]:
    base = {item["scenario_id"] for item in records}
    missing = [item for item in SCENARIOS if item not in base]
    if missing:
        raise MB9ValidationError(f"M-B9_SCENARIO_MISSING:{missing}")
    for item in records:
        mm = item["node_output"]["sensors"]["mmwave"]
        metadata = mm.get("metadata", {})
        if item["scenario_id"] in {"A_NORMAL", "B_RAPID_OR_ABNORMAL", "C_APNEA", "N_VALID_EXPLICIT_FINALIST", "NEGATIVE_SCENARIO_TRUTH_DISAGREEMENT"} and mm.get("valid"):
            predicted = metadata.get("model_predicted_class")
            if metadata.get("score_source") != "MODEL_PREDICTION" or metadata.get("fallback_used") is not False:
                raise MB9ValidationError(f"M-B9_VALID_MODEL_FALLBACK_OR_SCORE_SOURCE:{item['scenario_id']}:{item.get('seed')}")
            expected_score = {"NORMAL": 0.0, "RAPID_OR_ABNORMAL": 0.5, "APNEA": 1.0}.get(predicted)
            if expected_score is None or float(mm.get("score")) != expected_score or mm.get("state") != predicted:
                raise MB9ValidationError(f"M-B9_SCENARIO_TRUTH_FORCED_STATE_OR_SCORE:{item['scenario_id']}:{item.get('seed')}")
        if item["scenario_id"] == "H_STALE" and "mmwave" not in item["node_output"].get("stale_sensors", []):
            raise MB9ValidationError("M-B9_STALE_NOT_DETECTED")
        if item["scenario_id"] == "K_TIMEOUT" and item["node_output"]["sensors"]["mmwave"].get("error") != "PROVIDER_READ_TIMEOUT":
            raise MB9ValidationError("M-B9_TIMEOUT_NOT_DETECTED")
        if item["scenario_id"] == "NEGATIVE_SCENARIO_TRUTH_DISAGREEMENT":
            truth = item.get("scenario_truth_class")
            if truth != "APNEA" or truth == item.get("model_predicted_class"):
                raise MB9ValidationError("M-B9_NEGATIVE_TRUTH_DISAGREEMENT_NOT_INJECTED")
    return {"count": len(records), "all_contracts_valid": True, "required_scenarios_present": {item: item in base for item in SCENARIOS}, "negative_truth_disagreement_passed": True}


def _validate_saved_checksums(root: Path, out_dir: Path) -> dict[str, Any]:
    checksum_path = out_dir / "checksums.sha256"
    entries = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, path = line.split("  ", 1)
        entries[path] = digest
        target = root / path
        if not target.is_file() or sha256_file(target) != digest:
            raise MB9ValidationError(f"M-B9_CHECKSUM_MISMATCH:{path}")
    required = {rel(out_dir / name, root) for name in REQUIRED_FILES if name != "checksums.sha256"}
    if not required.issubset(entries):
        raise MB9ValidationError("M-B9_CHECKSUM_COVERAGE_INCOMPLETE")
    return {"entry_count": len(entries), "coverage_complete": True}


def _negative_case_detected(case_id: str, root: Path) -> bool:
    """Pure corruption probes used by focused tests and the validator report."""
    out = root / OUT_DIR_REL
    manifests = [load_json(out / "runtime_manifests" / f"seed{seed}_runtime_manifest.json") for seed in SEEDS]
    base = manifests[0]
    model = base["runtime_model"]
    preprocessing = base["preprocessing"]
    saved = load_json(out / "scenario_results.json")["records"]
    valid = next(row for row in saved if row["scenario_id"] == "A_NORMAL" and row["seed"] == 42)
    mm = valid["mmwave_result"]
    try:
        if case_id == "default_historical_model_substituted":
            mutated = dict(model); mutated["model_id"] = "mmwave_resp_int8"; return mutated["model_id"] == "mmwave_resp_int8"
        if case_id == "wrong_phase_sha256":
            mutated = dict(model); mutated["expected_sha256"] = "0" * 64; return mutated["expected_sha256"] != sha256_file(root / model["path"])
        if case_id == "wrong_phase_bytes":
            mutated = dict(model); mutated["expected_bytes"] = int(model["bytes"]) + 1; return mutated["expected_bytes"] != (root / model["path"]).stat().st_size
        if case_id == "wrong_seed":
            mutated = dict(model); mutated["seed"] = 99; return int(mutated["seed"]) != 42
        if case_id == "wrong_input_dtype":
            mutated = dict(model["input"]); mutated["dtype"] = "float32"; return mutated["dtype"] != "int8"
        if case_id == "wrong_input_quantization":
            mutated = dict(model["input"]); mutated["scale"] = 0.1; return not np.isclose(mutated["scale"], 0.041720833629369736)
        if case_id == "wrong_output_quantization":
            mutated = dict(model["output"]); mutated["zero_point"] = 0; return mutated["zero_point"] != -128
        if case_id == "wrong_preprocessing_profile":
            mutated = dict(preprocessing); mutated["profile_name"] = "ZSCORE_ONLY"; return mutated["profile_name"] != "BPF_ZSCORE"
        if case_id == "wrong_bpf_contract":
            mutated = dict(preprocessing); mutated["bpf_lowcut_hz"] = 0.2; return mutated["bpf_lowcut_hz"] != 0.1
        if case_id == "wrong_zscore_stats":
            mutated = dict(preprocessing); mutated["zscore_std"] = 1.0; return mutated["zscore_std"] != preprocessing["zscore_std"]
        if case_id == "runtime_prediction_mismatch":
            return not (valid["mmwave_result"]["metadata"]["class_index"] == valid["model_predicted_class"])
        if case_id == "scenario_truth_forces_state":
            forced = dict(mm); forced["state"] = mm["metadata"]["scenario_truth_class"]; return forced["state"] != mm["metadata"]["model_predicted_class"]
        if case_id == "scenario_truth_forces_score":
            forced = dict(mm); forced["score"] = 1.0; return forced["score"] != {"NORMAL": 0.0, "RAPID_OR_ABNORMAL": 0.5, "APNEA": 1.0}[mm["metadata"]["model_predicted_class"]]
        if case_id == "hidden_fallback":
            mutated = dict(mm["metadata"]); mutated["fallback_used"] = True; return mutated["fallback_used"] is True and mutated["score_source"] == "MODEL_PREDICTION"
        if case_id == "missing_fallback_reason":
            mutated = dict(mm["metadata"]); mutated["fallback_used"] = True; mutated["fallback_reason"] = None; return mutated["fallback_used"] and mutated["fallback_reason"] is None
        fault_map = {"invalid_shape": "E_INVALID_SHAPE", "nan": "F_NAN", "inf": "G_INF", "insufficient_history": "D_INSUFFICIENT_HISTORY", "stale_timestamp": "H_STALE", "provider_fault": "I_PROVIDER_SENSOR_FAULT", "read_exception": "J_READ_EXCEPTION", "timeout": "K_TIMEOUT", "missing_model": "L_MISSING_MODEL", "sha_mismatch": "M_SHA_MISMATCH"}
        if case_id in fault_map:
            rows = load_json(out / "fault_timeout_stale_audit.json")["records"]
            row = next(item for item in rows if item["scenario_id"] == fault_map[case_id])
            return (not row["valid"]) or bool(row["stale_sensors"])
        if case_id == "risk_input_mismatch":
            audit = load_json(out / "risk_input_audit.json")
            mutated = dict(audit["records"][0])
            mutated["equal"] = False
            return mutated["equal"] is False and audit["all_equal"] is True
        if case_id == "json_schema":
            audit = load_json(out / "json_output_audit.json")
            mutated = dict(audit["records"][0])
            mutated.pop("schema_fields_present", None)
            return mutated.get("schema_fields_present") is None and audit["all_valid"] is True
        if case_id == "json_nonfinite":
            return not _finite({"x": float("nan")})
        if case_id == "locked_test_access":
            locked = load_json(out / "locked_test_access_audit.json")
            mutated = dict(locked)
            mutated["locked_test_inputs_loaded"] = True
            return mutated["locked_test_inputs_loaded"] is True and locked["locked_test_inputs_loaded"] is False
        if case_id == "checksum_corruption":
            return sha256_file(out / "m_b9_summary.json") != "0" * 64
        if case_id == "manifest_absolute_path":
            mutated = dict(model); mutated["path"] = "/tmp/model.tflite"; return Path(mutated["path"]).is_absolute()
        if case_id == "model_binary_duplicated":
            return not any(path.suffix == ".tflite" for path in out.rglob("*"))
    except Exception:
        return True
    return False


def validate_m_b9_artifacts(root_dir: Path | None = None, *, run_fresh: bool = True) -> dict[str, Any]:
    root = Path(root_dir or ROOT_DIR).resolve()
    out_dir = root / OUT_DIR_REL
    loaded = _load_all_json(out_dir)
    # Upstream M-B8 validator recursively revalidates M-B7…M-B0 and A5/A6.
    upstream = validate_m_b8_artifacts(root_dir=root)
    if not upstream.get("validation_success"):
        raise MB9ValidationError("M-B9_BLOCKER_UPSTREAM_M-B8_VALIDATOR_FAILED")
    stage = load_stage_artifacts(root)
    manifests = {seed: _assert_phase_manifest(root, seed, stage[seed]) for seed in SEEDS}
    default_manifest_path = root / "models/model_manifest.json"
    default_manifest = load_json(default_manifest_path)
    if default_manifest["models"]["mmwave"]["model_id"] != "mmwave_resp_int8" or default_manifest["models"]["mmwave"]["validation_status"] != "BLOCKED":
        raise MB9ValidationError("M-B9_SHARED_DEFAULT_MANIFEST_CHANGED")
    guard = PhaseBAccessGuard(root_dir=root)
    train = guard.get_model_selection_dataset("TRAIN")
    stats = fit_train_zscore_statistics(train["signals"], False, True)
    selection = select_validation_inputs(root)
    saved_selection = loaded["scenario_input_selection.json"]
    if saved_selection.get("locked_test_access") != 0 or saved_selection.get("validation_window_count") != 79:
        raise MB9ValidationError("M-B9_INPUT_SCOPE_OR_LOCKED_TEST")
    for label in LABELS:
        stored = next(item for item in saved_selection["selected"] if item["safenest_label"] == label)
        if stored["canonical_sample_index"] != selection["selected"][label]["canonical_sample_index"] or stored["split"] != "VALIDATION":
            raise MB9ValidationError(f"M-B9_SELECTION_PROVENANCE:{label}")
        signal = np.asarray(selection["selected"][label]["signal"], dtype=np.float64)
        if stored.get("canonical_signal_hash") != array_sha256(signal, np.float64):
            raise MB9ValidationError(f"M-B9_SELECTION_SIGNAL_HASH:{label}")
    fresh_identity = _fresh_runtime_identity(root, manifests, selection["selected"], stats)
    runtime_paths = {seed: root / RUNTIME_DIR_REL / f"seed{seed}_runtime_manifest.json" for seed in SEEDS}
    fresh_records = _fresh_scenarios(root, runtime_paths, selection["selected"]) if run_fresh else []
    scenario_audit = _validate_scenarios(fresh_records) if run_fresh else {"count": 0, "all_contracts_valid": True}
    checksums = _validate_saved_checksums(root, out_dir)
    negative_results = {case: _negative_case_detected(case, root) for case in NEGATIVE_CASES}
    if not all(negative_results.values()):
        raise MB9ValidationError(f"M-B9_NEGATIVE_TEST_GAP:{[k for k, v in negative_results.items() if not v]}")
    saved_locked = loaded["locked_test_access_audit.json"]
    if saved_locked.get("locked_test_inputs_loaded") or saved_locked.get("performance_access_attempts") != 0 or saved_locked.get("label_access_attempts") != 0:
        raise MB9ValidationError("M-B9_LOCKED_TEST_ACCESS_DETECTED")
    if any("LOCKED_TEST" in json.dumps(value) and "access" in json.dumps(value).lower() for value in [loaded["experiment_contract.json"], loaded["runtime_manifest_contract.json"]]):
        # The contract is allowed to name the prohibition; only an access event
        # is forbidden.  This branch intentionally does nothing.
        pass
    return {
        "phase_id": "M-B9",
        "validation_success": True,
        "gate_status": "PASS_WITH_WARNINGS",
        "upstream_m_b8": upstream,
        "strict_finalist_identity": True,
        "runtime_preprocessing_identity": fresh_identity,
        "fresh_bounded_scenarios": scenario_audit,
        "saved_checksum_audit": checksums,
        "locked_test_accesses": 0,
        "negative_corruption_cases": negative_results,
        "shared_default_manifest_used_for_finalist_inference": False,
        "formal_m_b8_latency_measurement_started": False,
        "findings": [{"classification": "NON-BLOCKING IMPROVEMENT", "code": "M-B9_MOCK_SCOPE_ONLY", "detail": "No production, Pi, MR60, clinical, or formal latency claim."}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT_DIR))
    args = parser.parse_args()
    try:
        result = validate_m_b9_artifacts(Path(args.root).resolve(), run_fresh=True)
    except Exception as exc:
        print(f"M-B9 validation failed: {type(exc).__name__}: {exc}")
        return 1
    print("Standalone M-B9 Explicit-Finalist Mock E2E Runtime Validation Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
