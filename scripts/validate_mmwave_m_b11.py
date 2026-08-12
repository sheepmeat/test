#!/usr/bin/env python3
"""Fail-closed M-B11 artifact-lock validator.

Validates stored evidence and current immutable files only.
Never calls LOCKED_TEST or recovery accessors, never invokes TFLite,
never fits preprocessing, and never reads raw sensor payloads for evaluation.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.mmwave_m_b10r1_metrics import metric_bundle, saturation_audit_from_rows, subject_metrics  # noqa: E402
from scripts.mmwave_m_b10r1_result_writer import (  # noqa: E402
    SELECTED_MODEL_ID,
    V01_MODEL_ID,
    V02_MODEL_ID,
    sha256_file as _sha256_file,
)
from scripts.mmwave_m_b11_artifact_lock import (  # noqa: E402
    A5_SPLIT_REL,
    A6_MANIFEST_REL,
    ARCHITECTURE_ID,
    ARTIFACT_STATUS,
    B_DIR_REL,
    CALIBRATION_ID,
    CANONICAL_NPY_REL,
    CLASS_MAP,
    EXECUTION_PREPROCESSING_CONTRACT_ID,
    EXPECTED_ELIGIBLE,
    EXPECTED_MODELS,
    EXPECTED_PAIRS,
    LOCK_DIR_REL,
    LOCK_JSON_FILES,
    PREPROCESSING_PROFILE_ID,
    RAW_ARCHIVE_REL,
    RESULT_LIMITATION,
    RUNTIME_MODEL_ID,
    SELECTED_CANDIDATE_ID,
    SELECTED_TFLITE_REL,
    SENSOR_LOCK_REL,
    TRAINING_STRATEGY_ID,
    V01_TFLITE_REL,
    V02_TFLITE_REL,
    analyze_recovery_ledger,
    inspect_tflite_identity,
    load_json,
    load_jsonl,
    require_repo_relative,
)

FORBIDDEN_CLAIMS = (
    "PRISTINE_LOCKED_TEST",
    "FIRST_LOCKED_TEST_EVALUATION",
)
FORBIDDEN_TRUE_FLAGS = (
    "deployment_ready",
    "production_ready",
    "clinical_apnea_validated",
    "MR60_device_validation_complete",
    "Raspberry_Pi_validation_complete",
    "Phase_B_release_ready",
    "locked_test_reopen_allowed",
    "recovery_reopen_allowed",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class MB11ValidationError(Exception):
    """Fail-closed M-B11 validation failure."""


@lru_cache(maxsize=None)
def sha256_file(path: str, mtime_ns: int, size: int) -> str:
    return _sha256_file(Path(path))


def sha256_file_path(path: Path) -> str:
    stat = path.stat()
    return sha256_file(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _raise(code: str) -> None:
    raise MB11ValidationError(code)


def _inspect_no_accessor_or_invoke() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "get_locked_test_recovery_evaluation_dataset",
        "get_locked_test_final_evaluation_dataset",
        "invoke",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in forbidden:
                _raise(f"M_B11_VALIDATOR_FORBIDDEN_CALL:{name}")


def _validate_checksums(out: Path) -> None:
    checksum_path = out / "checksums.sha256"
    if not checksum_path.is_file():
        _raise("CHECKSUMS_MISSING")
    mapped: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or not HEX64.fullmatch(parts[0]):
            _raise(f"CHECKSUM_LINE_INVALID:{line}")
        rel = parts[1]
        if ".." in rel or rel.startswith("/") or "\\" in rel:
            _raise(f"CHECKSUM_UNSAFE_PATH:{rel}")
        if rel in mapped and mapped[rel] != parts[0]:
            _raise(f"CHECKSUM_DUPLICATE_INCONSISTENT:{rel}")
        mapped[rel] = parts[0]
        target = out / rel
        if not target.is_file():
            _raise(f"CHECKSUM_TARGET_MISSING:{rel}")
        if sha256_file_path(target) != parts[0]:
            _raise(f"CHECKSUM_MISMATCH:{rel}")
    expected = set(LOCK_JSON_FILES)
    if set(mapped) != expected:
        missing = sorted(expected - set(mapped))
        extra = sorted(set(mapped) - expected)
        _raise(f"CHECKSUM_ENTRY_SET_MISMATCH:missing={missing}:extra={extra}")
    if "checksums.sha256" in mapped:
        _raise("CHECKSUM_SELF_HASH")


def _walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item))
    return found


def _reject_unsafe_paths(payload: Any, *, context: str) -> None:
    for text in _walk_strings(payload):
        if text.startswith("/") or text.startswith("file:") or "\\" in text:
            _raise(f"UNSAFE_PATH:{context}:{text}")
        if ".." in Path(text).parts:
            _raise(f"UNSAFE_PATH:{context}:{text}")


def _require_equal(actual: Any, expected: Any, code: str) -> None:
    if actual != expected:
        _raise(f"{code}:{actual}!={expected}")


def validate_m_b11(
    root: Path | None = None,
    *,
    lock_dir: Path | None = None,
    b_dir: Path | None = None,
    sensor_lock_path: Path | None = None,
) -> dict[str, Any]:
    _inspect_no_accessor_or_invoke()
    root = Path(root) if root is not None else ROOT_DIR
    lock_dir = Path(lock_dir) if lock_dir is not None else root / LOCK_DIR_REL
    b_dir = Path(b_dir) if b_dir is not None else root / B_DIR_REL
    sensor_lock_path = Path(sensor_lock_path) if sensor_lock_path is not None else root / SENSOR_LOCK_REL
    if not lock_dir.is_dir():
        _raise("LOCK_DIR_MISSING")
    _validate_checksums(lock_dir)

    locks = {name: load_json(lock_dir / name) for name in LOCK_JSON_FILES}
    for name, payload in locks.items():
        _reject_unsafe_paths(payload, context=name)

    identity = locks["artifact_lock_identity.json"]
    source = locks["source_lineage_lock.json"]
    canonical = locks["canonical_dataset_lock.json"]
    split = locks["subject_split_lock.json"]
    window = locks["window_population_lock.json"]
    prep = locks["preprocessing_lock.json"]
    train = locks["training_lock.json"]
    model = locks["model_artifact_lock.json"]
    quant = locks["quantization_lock.json"]
    runtime = locks["runtime_contract_lock.json"]
    lineage = locks["phase_b_lineage_registry.json"]
    final_eval = locks["final_evaluation_lock.json"]
    history = locks["recovery_access_history_lock.json"]
    registry_lock = locks["final_sample_registry_lock.json"]
    metrics_lock = locks["final_metric_lock.json"]
    subject_lock = locks["final_subject_metric_lock.json"]
    baselines = locks["baseline_comparison_lock.json"]
    claims = locks["claim_boundary_lock.json"]
    limitations = locks["scientific_limitations.json"]
    immutable = locks["immutable_artifact_registry.json"]
    summary = locks["artifact_lock_summary.json"]

    _require_equal(identity.get("artifact_status"), ARTIFACT_STATUS, "ARTIFACT_STATUS")
    _require_equal(identity.get("result_limitation"), RESULT_LIMITATION, "RESULT_LIMITATION")
    if identity.get("result_not_pristine") is not True:
        _raise("RESULT_NOT_PRISTINE_FALSE")
    if identity.get("m_b11_creates_new_model") is not False:
        _raise("CREATES_NEW_MODEL_NOT_FALSE")
    _require_equal(identity.get("candidate_id"), SELECTED_CANDIDATE_ID, "CANDIDATE_ID")
    _require_equal(identity.get("runtime_model_id"), RUNTIME_MODEL_ID, "RUNTIME_MODEL_ID")
    _require_equal(identity.get("class_map"), CLASS_MAP, "CLASS_MAP")

    blob = json.dumps(locks, sort_keys=True)
    for claim in FORBIDDEN_CLAIMS:
        if f'"{claim}": true' in blob.lower() or f'"{claim}":true' in blob.replace(" ", "").lower():
            _raise(f"FORBIDDEN_PRISTINE_CLAIM:{claim}")
        if claims.get(claim) is True:
            _raise(f"FORBIDDEN_PRISTINE_CLAIM:{claim}")
    if "PRISTINE_LOCKED_TEST" in blob and claims.get("PRISTINE_LOCKED_TEST") is not False:
        _raise("PRISTINE_CLAIM_INSERTED")
    if claims.get("result_not_pristine") is not True:
        _raise("CLAIM_RESULT_NOT_PRISTINE_FALSE")
    if claims.get("result_limitation") != RESULT_LIMITATION:
        _raise("CLAIM_RESULT_LIMITATION_MISMATCH")
    for flag in FORBIDDEN_TRUE_FLAGS:
        if claims.get(flag) is True:
            _raise(f"FORBIDDEN_TRUE_CLAIM:{flag}")
    if claims.get("M-B12_required") is not True:
        _raise("M_B12_REQUIRED_MISSING")
    if "seed43" in json.dumps(model).lower() or "seed44" in json.dumps(model).lower():
        _raise("SELECTED_MODEL_RESELECTION")
    if model.get("candidate_id") != SELECTED_CANDIDATE_ID or model.get("seed") != 42:
        _raise("SELECTED_CANDIDATE_NOT_SEED42")
    if model.get("runtime_model_id") in {V01_MODEL_ID, V02_MODEL_ID}:
        _raise("BASELINE_PROMOTED_TO_SELECTED")
    if baselines["v0_1"].get("promoted_to_candidate") or baselines["v0_2"].get("promoted_to_candidate"):
        _raise("BASELINE_PROMOTED")

    raw_path = root / require_repo_relative(source["raw_archive_repo_relative_path"], context="raw")
    if not raw_path.is_file():
        _raise("RAW_ARCHIVE_MISSING")
    live_raw_sha = sha256_file_path(raw_path)
    _require_equal(live_raw_sha, source["raw_archive_sha256"], "RAW_SHA")
    _require_equal(int(raw_path.stat().st_size), source["raw_archive_bytes"], "RAW_BYTES")
    a0 = load_json(root / "datasets/mmwave/manifests/a0_raw_inventory/source_identity.json")
    _require_equal(a0["local_archive"]["sha256"], live_raw_sha, "A0_RAW_SHA")

    npy_path = root / require_repo_relative(canonical["canonical_npy_repo_relative_path"], context="npy")
    import numpy as np

    array = np.load(npy_path, mmap_mode="r")
    _require_equal(sha256_file_path(npy_path), canonical["canonical_npy_sha256"], "CANONICAL_SHA")
    _require_equal([int(item) for item in array.shape], canonical["shape"], "CANONICAL_SHAPE")
    _require_equal(str(array.dtype), canonical["dtype"], "CANONICAL_DTYPE")
    _require_equal(canonical["shape"], [530, 300], "CANONICAL_SHAPE_EXPECTED")

    split_path = root / require_repo_relative(split["split_artifact_repo_relative_path"], context="a5")
    _require_equal(sha256_file_path(split_path), split["split_sha256"], "A5_SPLIT_SHA")
    a5_profile = load_json(root / "datasets/mmwave/manifests/a5_subject_split/split_profile.json")
    _require_equal(split["split_seed"], a5_profile["split_seed"], "A5_SPLIT_SEED")
    _require_equal(split["subject_counts"], {"TRAIN": 77, "VALIDATION": 17, "LOCKED_TEST": 16}, "A5_COUNTS")

    a6_manifest = root / require_repo_relative(window["a6_manifest_repo_relative_path"], context="a6")
    _require_equal(sha256_file_path(a6_manifest), window["a6_manifest_sha256"], "A6_MANIFEST_SHA")
    a6_split = load_json(root / "datasets/mmwave/manifests/a6_full_conversion/full_split_distribution.json")
    _require_equal(window["structural"]["TRAIN"], a6_split["window_counts"]["TRAIN"], "A6_TRAIN_STRUCT")
    _require_equal(
        window["pure_supervised_eligible"]["LOCKED_TEST"],
        a6_split["eligibility_counts"]["locked_test_evaluation_eligible"],
        "A6_LOCKED_ELIGIBLE",
    )
    _require_equal(window["total_canonical_windows"], 530, "A6_TOTAL")
    _require_equal(window["locked_test"]["excluded_ambiguous_or_non_eligible"], 13, "A6_LOCKED_EXCLUDED")

    _require_equal(prep["selected_profile_id"], PREPROCESSING_PROFILE_ID, "PREPROCESSING_ID")
    _require_equal(prep["execution_preprocessing_contract_id"], EXECUTION_PREPROCESSING_CONTRACT_ID, "PREPROCESSING_CONTRACT")
    _require_equal(train["selected_strategy_id"], TRAINING_STRATEGY_ID, "TRAINING_STRATEGY")
    _require_equal(model["calibration_profile"], CALIBRATION_ID, "CALIBRATION_ID")
    _require_equal(model["architecture_id"], ARCHITECTURE_ID, "ARCHITECTURE")
    b1_selected = load_json(root / "datasets/mmwave/manifests/M-B1_preprocessing_ablation/selected_preprocessing_profile.json")
    b2_selected = load_json(root / "datasets/mmwave/manifests/M-B2_class_imbalance/selected_imbalance_strategy.json")
    b5_summary = load_json(root / "datasets/mmwave/manifests/M-B5_representative_calibration/m_b5_summary.json")
    b10a = load_json(root / "datasets/mmwave/manifests/M-B10A_candidate_selection_setup/m_b10a_summary.json")
    _require_equal(b1_selected["selected_profile_id"], prep["selected_profile_id"], "B1_PROFILE")
    _require_equal(b2_selected["selected_strategy_id"], train["selected_strategy_id"], "B2_STRATEGY")
    _require_equal(b5_summary["selected_calibration_profile"], model["calibration_profile"], "B5_CAL")
    _require_equal(b10a["selected_candidate_id"], SELECTED_CANDIDATE_ID, "B10A_CANDIDATE")

    live_model = inspect_tflite_identity(root, SELECTED_TFLITE_REL)
    _require_equal(live_model["sha256"], model["sha256"], "MODEL_SHA")
    _require_equal(live_model["bytes"], model["bytes"], "MODEL_BYTES")
    _require_equal(live_model["input_shape"], model["input_tensor"]["shape"], "INPUT_SHAPE")
    _require_equal(live_model["input_dtype"], model["input_tensor"]["dtype"], "INPUT_DTYPE")
    _require_equal(live_model["input_scale"], model["input_tensor"]["scale"], "INPUT_SCALE")
    _require_equal(live_model["input_zero_point"], model["input_tensor"]["zero_point"], "INPUT_ZP")
    _require_equal(live_model["output_shape"], model["output_tensor"]["shape"], "OUTPUT_SHAPE")
    _require_equal(live_model["output_dtype"], model["output_tensor"]["dtype"], "OUTPUT_DTYPE")
    _require_equal(live_model["output_scale"], model["output_tensor"]["scale"], "OUTPUT_SCALE")
    _require_equal(live_model["output_zero_point"], model["output_tensor"]["zero_point"], "OUTPUT_ZP")
    if not live_model["strict_int8"] or not model.get("strict_int8"):
        _raise("STRICT_INT8_FALSE")
    if live_model["flex_ops_present"] or live_model["select_tf_ops_present"]:
        _raise("FLEX_OR_SELECT_PRESENT")
    _require_equal(runtime["input_contract"]["scale"], live_model["input_scale"], "RUNTIME_INPUT_SCALE")
    _require_equal(runtime["output_contract"]["zero_point"], live_model["output_zero_point"], "RUNTIME_OUTPUT_ZP")

    b_registry = load_json(b_dir / "recovery_registry.json")
    b_ledger = load_jsonl(b_dir / "recovery_sample_predictions.jsonl")
    analysis = analyze_recovery_ledger(b_registry, b_ledger)
    _require_equal(analysis["unique_eligible_window_ids"], EXPECTED_ELIGIBLE, "UNIQUE_IDS")
    _require_equal(analysis["actual_pairs"], EXPECTED_PAIRS, "PAIRS")
    _require_equal(analysis["model_ids"], list(EXPECTED_MODELS), "MODEL_SET")
    _require_equal(registry_lock["unique_eligible_window_ids"], EXPECTED_ELIGIBLE, "LOCK_UNIQUE_IDS")
    _require_equal(registry_lock["actual_pairs"], EXPECTED_PAIRS, "LOCK_PAIRS")
    _require_equal(registry_lock["duplicates"], 0, "LOCK_DUP")
    _require_equal(registry_lock["missing"], 0, "LOCK_MISSING")
    _require_equal(registry_lock["unexpected"], 0, "LOCK_UNEXPECTED")
    _require_equal(registry_lock["ordered_window_ids"], analysis["ordered_window_ids"], "LOCK_WINDOW_ORDER")
    if len(registry_lock.get("samples") or []) != EXPECTED_ELIGIBLE:
        _raise("LOCK_SAMPLE_COUNT")
    lock_pairs = set()
    lock_models = set()
    for sample in registry_lock["samples"]:
        models = sample.get("models") or {}
        if set(models) != set(EXPECTED_MODELS):
            _raise(f"LOCK_SAMPLE_MODEL_SET:{sample.get('window_id')}")
        truths = {str(models[mid].get("true_class")) for mid in EXPECTED_MODELS}
        subjects = {str(models[mid].get("subject_id")) for mid in EXPECTED_MODELS}
        if len(truths) != 1:
            _raise(f"LOCK_CROSS_MODEL_LABEL:{sample.get('window_id')}")
        if len(subjects) != 1:
            _raise(f"LOCK_CROSS_MODEL_SUBJECT:{sample.get('window_id')}")
        live_sample = next(item for item in analysis["samples"] if item["window_id"] == sample["window_id"])
        if sample["true_class"] != live_sample["true_class"] or sample["subject_id"] != live_sample["subject_id"]:
            _raise(f"LOCK_SAMPLE_IDENTITY_MISMATCH:{sample['window_id']}")
        for mid in EXPECTED_MODELS:
            lock_pairs.add((sample["window_id"], mid))
            lock_models.add(mid)
            if models[mid]["predicted_class_index"] != live_sample["models"][mid]["predicted_class_index"]:
                _raise(f"LOCK_PREDICTION_MISMATCH:{sample['window_id']}:{mid}")
    if len(lock_pairs) != EXPECTED_PAIRS:
        _raise(f"LOCK_PAIR_CARDINALITY:{len(lock_pairs)}")
    if lock_models != set(EXPECTED_MODELS):
        _raise(f"LOCK_MODEL_SET:{sorted(lock_models)}")

    seed42_rows = analysis["per_model_rows"][SELECTED_MODEL_ID]
    v01_rows = analysis["per_model_rows"][V01_MODEL_ID]
    v02_rows = analysis["per_model_rows"][V02_MODEL_ID]
    seed42 = metric_bundle(
        [int(row["true_class_index"]) for row in seed42_rows],
        [int(row["predicted_class_index"]) for row in seed42_rows],
        evaluated_sample_count=75,
    )
    v01 = metric_bundle(
        [int(row["true_class_index"]) for row in v01_rows],
        [int(row["predicted_class_index"]) for row in v01_rows],
        evaluated_sample_count=75,
    )
    v02 = metric_bundle(
        [int(row["true_class_index"]) for row in v02_rows],
        [int(row["predicted_class_index"]) for row in v02_rows],
        evaluated_sample_count=75,
    )
    subjects = subject_metrics(seed42_rows)
    saturation = saturation_audit_from_rows(seed42_rows)
    b_selected = load_json(b_dir / "selected_candidate_recovery_result.json")
    b_baselines = load_json(b_dir / "historical_baseline_recovery_results.json")
    b_subjects = load_json(b_dir / "subject_level_metrics.json")
    b_quant = load_json(b_dir / "selected_candidate_quantization_audit.json")
    stored = b_selected["metrics"]
    for key in ("accuracy", "macro_f1", "macro_precision", "macro_recall", "confusion_matrix", "prediction_distribution"):
        _require_equal(seed42[key], stored[key], f"B_METRIC_{key}")
        _require_equal(metrics_lock[key], seed42[key], f"LOCK_METRIC_{key}")
    _require_equal(seed42["apnea_proxy"]["misses"], stored["apnea_proxy"]["misses"], "B_APNEA_MISSES")
    _require_equal(metrics_lock["apnea_proxy"]["misses"], seed42["apnea_proxy"]["misses"], "LOCK_APNEA_MISSES")
    _require_equal(seed42["apnea_proxy"]["fpr"], stored["apnea_proxy"]["fpr"], "B_APNEA_FPR")
    _require_equal(metrics_lock["apnea_proxy"]["fpr"], seed42["apnea_proxy"]["fpr"], "LOCK_APNEA_FPR")
    _require_equal(seed42["class_collapse"]["collapsed"], False, "SEED42_COLLAPSE")
    _require_equal(subjects["subject_count"], 16, "SUBJECT_COUNT")
    _require_equal(subjects["median_subject_macro_f1"], subject_lock["median_subject_macro_f1"], "LOCK_MEDIAN")
    _require_equal(subjects["worst_subject_macro_f1"], subject_lock["worst_subject_macro_f1"], "LOCK_WORST")
    _require_equal(subjects["worst_subject_id"], subject_lock["worst_subject_id"], "LOCK_WORST_ID")
    _require_equal(subjects["median_subject_macro_f1"], b_subjects[SELECTED_MODEL_ID]["median_subject_macro_f1"], "B_MEDIAN")
    _require_equal(subjects["worst_subject_id"], b_subjects[SELECTED_MODEL_ID]["worst_subject_id"], "B_WORST_ID")
    _require_equal(v01["macro_f1"], baselines["v0_1"]["macro_f1"], "V01_LOCK_F1")
    _require_equal(v02["macro_f1"], baselines["v0_2"]["macro_f1"], "V02_LOCK_F1")
    _require_equal(v01["macro_f1"], b_baselines[V01_MODEL_ID]["metrics"]["macro_f1"], "V01_B_F1")
    _require_equal(v02["macro_f1"], b_baselines[V02_MODEL_ID]["metrics"]["macro_f1"], "V02_B_F1")
    if not v01["class_collapse"]["collapsed"] or v01["prediction_distribution"]["NORMAL"] != 75:
        _raise("V01_COLLAPSE_MISMATCH")
    if not v02["class_collapse"]["collapsed"] or v02["prediction_distribution"]["RAPID_OR_ABNORMAL"] != 0:
        _raise("V02_COLLAPSE_MISMATCH")
    _require_equal(saturation["input_saturation_ratio"], quant["input_saturation_ratio"], "SAT_RATIO")
    _require_equal(saturation["total_quantized_elements"], 22500, "SAT_ELEMENTS")
    _require_equal(b_quant["input_saturation_ratio"], saturation["input_saturation_ratio"], "B_SAT")

    b_audit = load_json(b_dir / "one_time_recovery_access_audit.json")
    b_summary = load_json(b_dir / "m_b10r1b_summary.json")
    b10b = load_json(root / "datasets/mmwave/manifests/M-B10B_locked_test_final_evaluation/m_b10b_summary.json")
    _require_equal(history["original_m_b10b_accessor_invocations"], 1, "ORIG_ACCESS")
    _require_equal(history["original_m_b10b_payload_releases"], 1, "ORIG_RELEASE")
    _require_equal(history["original_m_b10b_model_inference"], 0, "ORIG_INFER")
    _require_equal(history["m_b10r1b_recovery_accessor_invocations"], 1, "REC_ACCESS")
    _require_equal(history["m_b10r1b_recovery_payload_releases"], 1, "REC_RELEASE")
    _require_equal(history["historical_total_payload_releases"], 2, "HIST_TOTAL")
    _require_equal(history["recovery_model_inference"], 225, "REC_INFER")
    if history.get("second_recovery") is not False:
        _raise("SECOND_RECOVERY_TRUE")
    if history.get("rerun") is not False:
        _raise("RERUN_TRUE")
    _require_equal(b_audit["historical_total_payload_release_events"], 2, "B_HIST_TOTAL")
    _require_equal(b_audit["recovery_payload_release_events"], 1, "B_REC_RELEASE")
    _require_equal(b10b["model_inference_invocations"], 0, "B10B_INFER")
    _require_equal(b_summary["actual_total_tflite_invocations"], 225, "B_TFLITE")
    _require_equal(final_eval["result_designation"], RESULT_LIMITATION, "FINAL_DESIGNATION")
    if final_eval.get("result_not_pristine") is not True:
        _raise("FINAL_EVAL_PRISTINE")

    selected_path = lineage.get("selected_path") or {}
    for phase in (
        "M-B1", "M-B2", "M-B3", "M-B4", "M-B5", "M-B6", "M-B7", "M-B8", "M-B9",
        "M-B10A", "M-B10B", "M-B10R0", "M-B10R1-A", "M-B10R1-B",
    ):
        if phase not in selected_path:
            _raise(f"LINEAGE_MISSING:{phase}")
    _require_equal(selected_path["M-B1"]["selected_preprocessing"], PREPROCESSING_PROFILE_ID, "LINEAGE_B1")
    _require_equal(selected_path["M-B2"]["selected_strategy"], TRAINING_STRATEGY_ID, "LINEAGE_B2")
    _require_equal(selected_path["M-B5"]["selected_calibration"], CALIBRATION_ID, "LINEAGE_B5")
    if not selected_path["M-B4"].get("seed42_materially_better_than_seed44"):
        _raise("B4_SENSITIVITY_HIDDEN")
    if selected_path["M-B8"].get("not_raspberry_pi_latency") is not True:
        _raise("B8_CLAIMED_AS_RPI")
    if selected_path["M-B9"].get("not_physical_sensor_integration") is not True:
        _raise("B9_CLAIMED_AS_PHYSICAL")

    artifacts = immutable.get("artifacts") or []
    if not artifacts:
        _raise("IMMUTABLE_REGISTRY_EMPTY")
    seen_roles = set()
    for item in artifacts:
        role = str(item.get("artifact_role"))
        seen_roles.add(role)
        rel = require_repo_relative(str(item.get("repo_relative_path")), context=role)
        target = root / rel
        if not target.is_file():
            _raise(f"REGISTRY_MISSING_FILE:{rel}")
        live = sha256_file_path(target)
        if live != item.get("sha256"):
            _raise(f"REGISTRY_SHA_MISMATCH:{rel}")
        if int(target.stat().st_size) != int(item.get("bytes")):
            _raise(f"REGISTRY_BYTES_MISMATCH:{rel}")
        if item.get("immutable") is not True:
            _raise(f"REGISTRY_NOT_IMMUTABLE:{rel}")
    required_roles = {
        "raw_source_archive",
        "a5_subject_split",
        "a6_window_manifest",
        "canonical_npy",
        "selected_tflite",
        "b10r1b_ledger",
        "v0_1_tflite",
        "v0_2_tflite",
        "sensor_local_candidate_lock",
    }
    missing_roles = sorted(required_roles - seen_roles)
    if missing_roles:
        _raise(f"REGISTRY_ROLE_MISSING:{missing_roles}")

    if not sensor_lock_path.is_file():
        _raise("SENSOR_LOCK_MISSING")
    sensor = load_json(sensor_lock_path)
    _reject_unsafe_paths(sensor, context="sensor_lock")
    _require_equal(sensor.get("status"), ARTIFACT_STATUS, "SENSOR_STATUS")
    _require_equal(sensor.get("sha256"), live_model["sha256"], "SENSOR_SHA")
    _require_equal(sensor.get("candidate_id"), SELECTED_CANDIDATE_ID, "SENSOR_CANDIDATE")
    if sensor.get("models_model_manifest_json_modified") is not False:
        _raise("SENSOR_TOUCHED_MODEL_MANIFEST")
    if limitations.get("locked_limitations_not_immediate_b_series_retuning_defects") is not True:
        _raise("LIMITATIONS_REFRAMED_AS_DEFECTS")
    _require_equal(summary.get("new_locked_test_access"), 0, "SUMMARY_LOCKED_ACCESS")
    _require_equal(summary.get("new_recovery_access"), 0, "SUMMARY_RECOVERY_ACCESS")
    _require_equal(summary.get("new_model_inference"), 0, "SUMMARY_INFERENCE")
    return {
        "status": "PASS",
        "candidate_id": SELECTED_CANDIDATE_ID,
        "model_sha256": live_model["sha256"],
        "macro_f1": seed42["macro_f1"],
    }


def main() -> int:
    try:
        result = validate_m_b11()
    except MB11ValidationError as exc:
        print(f"M-B11 VALIDATION FAIL: {exc}", file=sys.stderr)
        return 1
    print("M-B11 VALIDATION PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
