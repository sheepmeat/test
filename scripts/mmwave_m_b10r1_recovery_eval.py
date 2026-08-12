#!/usr/bin/env python3
"""M-B10R1 recovery evaluation runner (pre-freeze + future authorized path).

Default / pre-access modes never release recovery payload.
``execute_authorized_recovery`` is irreversible and MUST NOT be invoked during
M-B10R1-A.
"""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.mmwave_m_b10r1_metrics import (  # noqa: E402
    CLASS_MAP,
    metric_bundle,
    saturation_audit_from_rows,
    subject_metrics,
)
from scripts.mmwave_m_b10r1_recovery_access import (  # noqa: E402
    EXPECTED_AMBIGUOUS,
    EXPECTED_ELIGIBLE,
    EXPECTED_INFERENCES,
    EXPECTED_STRUCTURAL,
    EXPECTED_SUBJECTS,
    ORIGINAL_FINAL_TOKEN,
    RECOVERY_AUTHORIZATION_TOKEN,
    RESULT_LIMITATION,
    LimitedReuseRecoveryAccessController,
    RecoveryAccessError,
    RecoveryReadiness,
)

OUT_DIR_REL = Path("datasets/mmwave/manifests/M-B10R1A_recovery_prefreeze")
M_B10R0_DIR_REL = Path("datasets/mmwave/manifests/M-B10R0_holdout_policy_review")
M_B10A_DIR_REL = Path("datasets/mmwave/manifests/M-B10A_candidate_selection_setup")
M_B10B_DIR_REL = Path("datasets/mmwave/manifests/M-B10B_locked_test_final_evaluation")

SELECTED_CANDIDATE_ID = "M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120"
SELECTED_MODEL_ID = "M-B3_CONV1D_GAP_BASELINE_seed42_M-B6_STRICT_INT8"
SELECTED_PATH = (
    "models/mmwave/experiments/M-B6_stage_equivalence/"
    "M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite"
)
SELECTED_SHA = "6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5"
V01_PATH = "models/mmwave/mmwave_resp_int8_v0.1.0.tflite"
V01_SHA = "43cdd6f321c2b645232162233e098c2b65549388cbc9e680a17a0eccdc8f0158"
V02_PATH = "models/mmwave/mmwave_resp_int8_v0.2.0_candidate.tflite"
V02_SHA = "85c023d3eefca13ecbb72a841974e53a56d5f4173920645d46df49a9088452ff"
EXECUTOR_PATH = "scripts/mmwave_m_b10b_baseline_preprocessing.py"
EXECUTOR_SHA = "8ca87f457d0a151cffa2da23ae9ab9d87764b144fa826b91444776f3dc58ec4f"
META_V01_PATH = "models/mmwave/sensor_stats_metadata_v0.1.0.json"
META_V01_SHA = "a875a8369ff7adf5477cec009b99c0c6d0fbb8b0e60e5b0b07a551f3780d2e37"
META_V02_PATH = "models/mmwave/mmwave_resp_int8_v0.2.0_candidate_metadata.json"
META_V02_SHA = "36039a6cffbc57162dbb4c720034da6dcfa49ef2f2d33238bee65a62aa133127"
M_B10A_CONTRACT_SHA = "ba6429ecfe685de1807ec85b55e697ee12e24138e6b96e94715b0a1a6b19e0f7"

FORBIDDEN_MODEL_IDS = {
    "M-B3_CONV1D_GAP_BASELINE_seed43_M-B6_STRICT_INT8",
    "M-B3_CONV1D_GAP_BASELINE_seed44_M-B6_STRICT_INT8",
}

LEDGER_ROW_FIELDS = (
    "window_id",
    "subject_id",
    "recording_id",
    "true_class",
    "true_class_index",
    "model_role",
    "model_id",
    "model_sha256",
    "preprocessing_contract_id",
    "model_input_tensor_sha256",
    "raw_output_int8",
    "dequantized_output",
    "predicted_class_index",
    "predicted_class",
    "confidence",
    "input_saturation_count",
    "input_saturation_ratio",
    "fallback_used",
    "invalid",
    "error",
    "result_limitation",
    "result_not_pristine",
)

LEDGER_SCHEMA_STATUS = "NOT_EXECUTED"
RESULT_SCHEMA_STATUS = "NOT_POPULATED"


class MB10R1EvalError(Exception):
    """Recovery evaluation harness error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def frozen_model_specs() -> list[dict[str, Any]]:
    return [
        {
            "role": "SELECTED_NEW_REAL_DATA_CANDIDATE",
            "candidate_id": SELECTED_CANDIDATE_ID,
            "model_id": SELECTED_MODEL_ID,
            "path": SELECTED_PATH,
            "sha256": SELECTED_SHA,
            "seed": 42,
            "bytes": 22080,
            "preprocessing": "BPF_ZSCORE",
            "preprocessing_profile": "M-B1_D0_B1_Z1",
            "calibration": "M-B5_CAL_CLASS_BALANCED_120",
            "baseline_id": None,
            "class_map": dict(CLASS_MAP),
        },
        {
            "role": "HISTORICAL_MODEL_COMPATIBILITY_BASELINE",
            "model_id": "mmwave_resp_int8",
            "path": V01_PATH,
            "sha256": V01_SHA,
            "bytes": 466616,
            "baseline_id": "mmwave_resp_int8",
            "executor_path": EXECUTOR_PATH,
            "executor_sha256": EXECUTOR_SHA,
            "metadata_path": META_V01_PATH,
            "metadata_sha256": META_V01_SHA,
            "interpretation": "HISTORICAL_MODEL_COMPATIBILITY_BENCHMARK",
            "class_map": dict(CLASS_MAP),
        },
        {
            "role": "SYNTHETIC_TRAINED_EXTERNAL_COMPATIBILITY_BASELINE",
            "model_id": "mmwave_resp_int8_v0.2.0_candidate",
            "path": V02_PATH,
            "sha256": V02_SHA,
            "bytes": 22472,
            "baseline_id": "mmwave_resp_int8_v0.2.0_candidate",
            "executor_path": EXECUTOR_PATH,
            "executor_sha256": EXECUTOR_SHA,
            "metadata_path": META_V02_PATH,
            "metadata_sha256": META_V02_SHA,
            "interpretation": "SYNTHETIC_TRAINED_EXTERNAL_COMPATIBILITY_BENCHMARK",
            "class_map": dict(CLASS_MAP),
        },
    ]


def validate_frozen_recovery_models(root: Path) -> list[dict[str, Any]]:
    """Exact 3 models; reject seed43/44/fourth."""
    specs = frozen_model_specs()
    if len(specs) != 3:
        raise MB10R1EvalError("MODEL_COUNT_MUST_BE_THREE")
    ids = [s["model_id"] for s in specs]
    if len(set(ids)) != 3:
        raise MB10R1EvalError("DUPLICATE_MODEL_IDS")
    for forbidden in FORBIDDEN_MODEL_IDS:
        if forbidden in ids:
            raise MB10R1EvalError(f"FORBIDDEN_MODEL:{forbidden}")
    serialized = json.dumps(specs, sort_keys=True).lower()
    if "seed43" in serialized or "seed44" in serialized:
        raise MB10R1EvalError("FORBIDDEN_SEED_IN_MODEL_SET")
    for spec in specs:
        path = root / spec["path"]
        if not path.is_file():
            raise MB10R1EvalError(f"MODEL_MISSING:{spec['path']}")
        live = sha256_file(path)
        if live != spec["sha256"]:
            raise MB10R1EvalError(f"MODEL_SHA_MISMATCH:{spec['model_id']}")
        if path.stat().st_size != int(spec["bytes"]):
            raise MB10R1EvalError(f"MODEL_BYTES_MISMATCH:{spec['model_id']}")
        if spec.get("executor_path"):
            executor = root / spec["executor_path"]
            if sha256_file(executor) != spec["executor_sha256"]:
                raise MB10R1EvalError(f"EXECUTOR_SHA_MISMATCH:{spec['model_id']}")
        if spec.get("metadata_path"):
            meta = root / spec["metadata_path"]
            if sha256_file(meta) != spec["metadata_sha256"]:
                raise MB10R1EvalError(f"METADATA_SHA_MISMATCH:{spec['model_id']}")
    return specs


def build_bound_contract_identity(root: Path) -> dict[str, Any]:
    """SHA-bind M-B10R0 + M-B10A + model/baseline identities for future access."""
    validate_frozen_recovery_models(root)
    r0 = root / M_B10R0_DIR_REL
    return {
        "schema_version": "M-B10R1_BOUND_CONTRACT_IDENTITY_V1",
        "include_ambiguous": False,
        "positional_truncation": False,
        "eligibility_rule": (
            "split==LOCKED_TEST AND assignment_status!=AMBIGUOUS "
            "(A6 locked_test_evaluation_eligible semantics via PhaseBAccessGuard._get_split_dataset)"
        ),
        "expected_eligible_windows": EXPECTED_ELIGIBLE,
        "expected_subjects": EXPECTED_SUBJECTS,
        "expected_structural_windows": EXPECTED_STRUCTURAL,
        "expected_ambiguous_windows": EXPECTED_AMBIGUOUS,
        "expected_model_inference_count": EXPECTED_INFERENCES,
        "result_limitation": RESULT_LIMITATION,
        "result_not_pristine": True,
        "policy_decision_sha256": sha256_file(r0 / "policy_decision.json"),
        "reuse_exception_gate_results_sha256": sha256_file(r0 / "reuse_exception_gate_results.json"),
        "proposed_recovery_evaluation_contract_sha256": sha256_file(
            r0 / "proposed_recovery_evaluation_contract.json"
        ),
        "future_recovery_access_requirements_sha256": sha256_file(
            r0 / "future_recovery_access_requirements.json"
        ),
        "m_b10r0_summary_sha256": sha256_file(r0 / "m_b10r0_summary.json"),
        "m_b10a_metric_contract_sha256": sha256_file(
            root / M_B10A_DIR_REL / "locked_test_evaluation_contract.json"
        ),
        "selected_model_sha256": SELECTED_SHA,
        "baseline_v01_sha256": V01_SHA,
        "baseline_v02_sha256": V02_SHA,
        "executor_sha256": EXECUTOR_SHA,
        "metadata_v01_sha256": META_V01_SHA,
        "metadata_v02_sha256": META_V02_SHA,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selected_model_id": SELECTED_MODEL_ID,
        "model_count": 3,
        "recovery_authorization_token_id": "M_B10R1_LIMITED_REUSE_RECOVERY_AUTHORIZATION_V1",
        "original_final_token_rejected": ORIGINAL_FINAL_TOKEN,
    }


def build_preaccess_readiness(root: Path, *, validator_pass: bool = False) -> dict[str, Any]:
    """All authorization flags FALSE during M-B10R1-A."""
    del root  # identity is global; root reserved for future path checks
    return {
        "schema_version": "M-B10R1A_RECOVERY_ACCESS_READINESS_V1",
        "phase_id": "M-B10R1-A",
        "mechanism_implemented": True,
        "runner_implemented": True,
        "pre_access_validator_pass": bool(validator_pass),
        "independent_review_required": True,
        "recovery_execution_authorized": False,
        "recovery_payload_release_authorized": False,
        "M-B10R1B_started": False,
        "new_recovery_accessor_invocations": 0,
        "new_payload_release_events": 0,
        "authorization_token_supplied_during_m_b10r1a": False,
        "notes": (
            "Mechanism and runner are implemented for future M-B10R1-B. "
            "No recovery execution authorization is granted by M-B10R1-A."
        ),
    }


def future_ledger_schema() -> dict[str, Any]:
    return {
        "schema_version": "M-B10R1_FUTURE_LEDGER_SCHEMA_V1",
        "status": LEDGER_SCHEMA_STATUS,
        "row_unit": "eligible_sample_x_model",
        "expected_rows": EXPECTED_INFERENCES,
        "expected_eligible_windows": EXPECTED_ELIGIBLE,
        "expected_models": 3,
        "required_fields": list(LEDGER_ROW_FIELDS),
        "stores_raw_phase_tensors": False,
        "result_limitation": RESULT_LIMITATION,
        "result_not_pristine": True,
        "populated": False,
        "population_note": "NOT_EXECUTED — ledger rows are not populated during M-B10R1-A",
    }


def future_result_schema() -> dict[str, Any]:
    return {
        "schema_version": "M-B10R1_FUTURE_RESULT_SCHEMA_V1",
        "status": RESULT_SCHEMA_STATUS,
        "required_result_designation": RESULT_LIMITATION,
        "result_not_pristine": True,
        "original_pristine_final_access_consumed": True,
        "original_model_inferences": 0,
        "reuse_exception_reviewed": True,
        "forbidden_scientific_wording": [
            "PRISTINE_REAL_SUBJECT_FINAL_TEST",
            "PRISTINE_ONE_TIME_LOCKED_TEST",
            "PRISTINE_LOCKED_TEST",
            "FIRST_LOCKED_TEST_EVALUATION",
            "LOCKED_TEST_NOT_CONSUMED",
            "NO_INFORMATION_EXPOSURE",
            "ORIGINAL_ACCESS_UNUSED",
        ],
        "allowed_scientific_wording": "OFFLINE_REAL_DATA_RECOVERY_EVALUATION_WITH_HOLDOUT_REUSE_LIMITATION",
        "acceptance_threshold": "FINAL_LOCKED_TEST_NUMERICAL_ACCEPTANCE_THRESHOLD_NOT_PREDEFINED",
        "metrics_populated": False,
        "predictions_populated": False,
        "note": "NOT_POPULATED — no recovery metrics or predictions during M-B10R1-A",
    }


def run_validation_smoke(root: Path, *, attempt_tflite: bool = False) -> dict[str, Any]:
    """VALIDATION-only smoke; never LOCKED_TEST. Labeled mock/VALIDATION inference."""
    from scripts.mmwave_phase_b_access import PhaseBAccessGuard

    specs = validate_frozen_recovery_models(root)
    guard = PhaseBAccessGuard(root_dir=root)
    validation = guard.get_validation_data(include_ambiguous=False)
    selection = guard.get_model_selection_dataset("VALIDATION", include_ambiguous=False)
    if selection["total_count"] != validation["total_count"]:
        raise MB10R1EvalError("VALIDATION_ACCESSOR_COUNT_MISMATCH")

    probes: list[dict[str, Any]] = [
        {
            "split": "VALIDATION",
            "label": "VALIDATION_ACCESSOR_PROBE",
            "status": "OK",
            "sample_count": int(validation["total_count"]),
            "model_count_frozen": len(specs),
            "locked_test_accessed": False,
        }
    ]
    inference_count = 0
    if attempt_tflite:
        try:
            from scripts.mmwave_m_b10b_final_eval import TFLiteRunner
            import numpy as np

            # Synthetic int8 probe — VALIDATION wiring only; not recovery.
            dummy = np.zeros((1, 300, 1), dtype=np.int8)
            for spec in specs:
                mb10b_spec = {
                    "role": "SELECTED_NEW_REAL_DATA_CANDIDATE",
                    "model_id": spec["model_id"],
                    "path": spec["path"],
                    "baseline_id": spec.get("baseline_id"),
                }
                runner = TFLiteRunner(root, mb10b_spec)
                out = runner.invoke(dummy)
                inference_count += 1
                probes.append(
                    {
                        "split": "VALIDATION_WIRING",
                        "label": "MOCK_SYNTHETIC_INT8_PROBE",
                        "model_id": spec["model_id"],
                        "predicted_class": out["predicted_class"],
                        "locked_test_accessed": False,
                        "status": "OK",
                    }
                )
        except Exception as exc:
            probes.append(
                {
                    "split": "VALIDATION",
                    "label": "TFLITE_SMOKE_SKIPPED",
                    "status": f"SKIPPED:{exc}",
                    "locked_test_accessed": False,
                }
            )
    return {
        "status": "VALIDATION_SMOKE_COMPLETE",
        "split": "VALIDATION",
        "locked_test_accessed": False,
        "recovery_accessor_invoked": False,
        "validation_sample_count": int(validation["total_count"]),
        "validation_inferences_attempted_or_completed": inference_count,
        "probes": probes,
        "note": "MOCK/VALIDATION only — not recovery LOCKED_TEST inference",
    }


def execute_authorized_recovery(root: Path, authorization_token: str) -> dict[str, Any]:
    """Irreversible recovery path. MUST NOT be called during M-B10R1-A."""
    readiness_path = root / OUT_DIR_REL / "recovery_access_readiness.json"
    if not readiness_path.is_file():
        raise MB10R1EvalError("READINESS_MANIFEST_MISSING")
    readiness_doc = load_json(readiness_path)
    if readiness_doc.get("recovery_execution_authorized") is not True:
        raise MB10R1EvalError("READINESS_EXECUTION_NOT_AUTHORIZED")
    if readiness_doc.get("recovery_payload_release_authorized") is not True:
        raise MB10R1EvalError("READINESS_PAYLOAD_NOT_AUTHORIZED")
    if readiness_doc.get("pre_access_validator_pass") is not True:
        raise MB10R1EvalError("READINESS_VALIDATOR_NOT_PASS")

    bound = build_bound_contract_identity(root)
    specs = validate_frozen_recovery_models(root)
    readiness = RecoveryReadiness(
        recovery_execution_authorized=True,
        recovery_payload_release_authorized=True,
        independent_review_required=True,
        mechanism_implemented=True,
        runner_implemented=True,
        pre_access_validator_pass=True,
        M_B10R1B_started=True,
    )
    controller = LimitedReuseRecoveryAccessController(root)
    # Single payload transaction for all three models.
    payload = controller.get_locked_test_recovery_evaluation_dataset(
        authorization_token=authorization_token,
        bound_contract_identity=bound,
        readiness=readiness,
    )
    if int(payload["total_count"]) != EXPECTED_ELIGIBLE:
        raise MB10R1EvalError("POST_RELEASE_COUNT_MISMATCH")

    # Import inference helpers only on authorized path.
    from scripts.mmwave_m_b10b_final_eval import TFLiteRunner, preprocess_for_spec

    ledger: list[dict[str, Any]] = []
    for spec in specs:
        mb10b_spec = {
            "role": (
                "SELECTED_NEW_REAL_DATA_CANDIDATE"
                if spec["role"] == "SELECTED_NEW_REAL_DATA_CANDIDATE"
                else "HISTORICAL_MODEL_COMPATIBILITY_BASELINE"
            ),
            "model_id": spec["model_id"],
            "path": spec["path"],
            "baseline_id": spec.get("baseline_id"),
            "preprocessing_contract_id": (
                "M-B1_D0_B1_Z1" if spec.get("baseline_id") is None else spec["model_id"]
            ),
        }
        runner = TFLiteRunner(root, mb10b_spec)
        for window, signal in zip(payload["windows"], payload["signals"]):
            row: dict[str, Any] = {
                "window_id": window.get("window_id"),
                "subject_id": window.get("subject_id"),
                "recording_id": window.get("recording_id"),
                "true_class": window.get("safenest_label"),
                "true_class_index": int(window.get("safenest_label_id", -1)),
                "model_role": spec["role"],
                "model_id": spec["model_id"],
                "model_sha256": spec["sha256"],
                "preprocessing_contract_id": mb10b_spec["preprocessing_contract_id"],
                "fallback_used": False,
                "invalid": False,
                "error": None,
                "result_limitation": RESULT_LIMITATION,
                "result_not_pristine": True,
            }
            try:
                # Prefer window object; M-B10B selected path uses window arrays.
                prepared = preprocess_for_spec(window, mb10b_spec)
                out = runner.invoke(prepared["input_int8"])
                row.update(
                    {
                        "model_input_tensor_sha256": hashlib.sha256(
                            prepared["input_int8"].tobytes()
                        ).hexdigest(),
                        "raw_output_int8": out["raw_output_int8"],
                        "dequantized_output": out["dequantized_output"],
                        "predicted_class_index": out["predicted_class_index"],
                        "predicted_class": out["predicted_class"],
                        "confidence": out["confidence"],
                        "input_saturation_count": prepared.get("input_saturation_count", 0),
                        "input_saturation_ratio": prepared.get("input_saturation_ratio", 0.0),
                    }
                )
            except Exception as exc:
                row["invalid"] = True
                row["error"] = str(exc)
                row["predicted_class_index"] = -1
                row["predicted_class"] = None
                row["confidence"] = None
                row["input_saturation_count"] = 0
                row["input_saturation_ratio"] = 0.0
            ledger.append(row)

    if len(ledger) != EXPECTED_INFERENCES:
        # No retry — payload already consumed.
        raise MB10R1EvalError(f"INFERENCE_COUNT_MISMATCH:{len(ledger)}")

    # No post-result branching / no performance thresholds.
    metrics_by_model: dict[str, Any] = {}
    subject_by_model: dict[str, Any] = {}
    for spec in specs:
        model_rows = [r for r in ledger if r["model_id"] == spec["model_id"] and not r.get("invalid")]
        labels = [int(r["true_class_index"]) for r in model_rows]
        preds = [int(r["predicted_class_index"]) for r in model_rows]
        metrics_by_model[spec["model_id"]] = metric_bundle(
            labels, preds, evaluated_sample_count=EXPECTED_ELIGIBLE
        )
        subject_by_model[spec["model_id"]] = subject_metrics(model_rows)

    seed42_rows = [r for r in ledger if r["model_id"] == SELECTED_MODEL_ID and not r.get("invalid")]
    return {
        "status": "RECOVERY_EXECUTED",
        "result_limitation": RESULT_LIMITATION,
        "result_not_pristine": True,
        "ledger_row_count": len(ledger),
        "expected_inferences": EXPECTED_INFERENCES,
        "metrics_by_model": metrics_by_model,
        "subject_metrics_by_model": subject_by_model,
        "saturation_audit_seed42": saturation_audit_from_rows(seed42_rows),
        "ledger": ledger,
        "acceptance_threshold": "FINAL_LOCKED_TEST_NUMERICAL_ACCEPTANCE_THRESHOLD_NOT_PREDEFINED",
        "note": "No performance threshold gating; no retry; no post-result model branching.",
    }


def readiness_summary(root: Path) -> dict[str, Any]:
    """Default CLI payload — never accesses recovery."""
    out = root / OUT_DIR_REL
    readiness_path = out / "recovery_access_readiness.json"
    audit_path = out / "recovery_access_audit.json"
    summary = {
        "phase_id": "M-B10R1-A",
        "mode": "PRE_ACCESS_READINESS_SUMMARY",
        "recovery_accessor_invoked": False,
        "recovery_payload_released": False,
        "locked_test_reopened": False,
        "recovery_execution_authorized": False,
        "recovery_authorization_token_constant_present": RECOVERY_AUTHORIZATION_TOKEN,
        "original_final_token_rejected_for_recovery": ORIGINAL_FINAL_TOKEN,
        "result_limitation": RESULT_LIMITATION,
        "expected_eligible": EXPECTED_ELIGIBLE,
        "expected_inferences": EXPECTED_INFERENCES,
        "generated_at": _utc_now(),
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
    }
    if readiness_path.is_file():
        summary["readiness"] = load_json(readiness_path)
    else:
        summary["readiness"] = build_preaccess_readiness(root, validator_pass=False)
    if audit_path.is_file():
        summary["audit"] = load_json(audit_path)
    return summary
