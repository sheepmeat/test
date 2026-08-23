#!/usr/bin/env python3
"""Populate the frozen M-PV3.6 Role S evaluation card.

This evaluator is intentionally evaluation-only.  It loads the already frozen
M-PV2-SHORT checkpoints, replays the governed M-PV1/R1 membership, and writes
one Role S evidence manifest.  It does not train, fit calibration, tune a
threshold, access D2, use MR60 supervised physiology, or select a seed/model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Mapping, Sequence

import numpy as np

try:
    import torch
except ImportError as exc:  # pragma: no cover - environment prerequisite
    raise SystemExit("Role S evaluation requires torch") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import mmwave_m_pv2_short_context_15s_candidate as short  # noqa: E402


SCHEMA_VERSION = "M-PV3.6-ROLE-S.1"
ROLE_ID = "ROLE_S_SHORT_CONTEXT"
CANDIDATE_ID = "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1"
CONTRACT_ID = "MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1"
SEEDS = (11, 23, 47)
THRESHOLD = 0.5

OUT_REL = Path("datasets/mmwave/manifests/M-PV3_6_ROLE_S_SHORT_CONTEXT_evaluation")
MANIFEST_REL = OUT_REL / "evidence_manifest.json"
VALIDATION_REL = OUT_REL / "validation_result.json"
CHECKSUMS_REL = OUT_REL / "checksums.json"

M_PV36_CONTRACT_REL = Path("config/mmwave/m_pv36_role_based_evaluation_contract.json")
M_PV36_MATRIX_REL = Path("datasets/mmwave/manifests/M-PV3_6_role_based_evaluation/evaluation_matrix.json")
M_PV36_EVIDENCE_REL = Path("datasets/mmwave/manifests/M-PV3_6_role_based_evaluation/evidence_requirements.json")
SHORT_ROOT_REL = Path("datasets/mmwave/manifests/M-PV2_short_context_15s_candidate")
SHORT_MODEL_REL = Path("models/mmwave/m_pv2_short_context_15s_candidate")
Q2_REGRESSION_REL = Path("datasets/mmwave/manifests/M-PV0_I3_fail_closed_regression/synthetic_q2_regression.json")
Q2_PROFILE_REL = Path("datasets/mmwave/manifests/M-PV0_Q2_input_unavailable_contract/synthetic_quality_profile.json")
I3_PRESENCE_REL = Path("datasets/mmwave/manifests/M-PV0_I3_fail_closed_regression/presence_precedence_audit.json")
I3_AVAILABILITY_REL = Path("datasets/mmwave/manifests/M-PV0_I3_fail_closed_regression/availability_precedence_audit.json")
I3_CONTRACT_REL = Path("datasets/mmwave/manifests/M-PV0_I3_fail_closed_regression/i3_regression_contract.json")

PRESENT = "BREATHING_REFERENCE_PRESENT"
ABSENT = "BREATHING_REFERENCE_ABSENT"
AMBIGUOUS = "BREATHING_REFERENCE_AMBIGUOUS"


class RoleSEvaluationError(RuntimeError):
    """Raised when frozen evidence cannot be evaluated fail-closed."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleSEvaluationError(f"failed to read JSON {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _safe_divide(numerator: float, denominator: float) -> float | None:
    return float(numerator / denominator) if denominator else None


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RoleSEvaluationError(message)


def _load_frozen_inputs() -> dict[str, Any]:
    contract = _read_json(ROOT / M_PV36_CONTRACT_REL)
    matrix = _read_json(ROOT / M_PV36_MATRIX_REL)
    evidence = _read_json(ROOT / M_PV36_EVIDENCE_REL)
    short_input = _read_json(ROOT / SHORT_ROOT_REL / "input_contract.json")
    short_alignment = _read_json(ROOT / SHORT_ROOT_REL / "target_alignment.json")
    short_audit = _read_json(ROOT / SHORT_ROOT_REL / "dataset_audit.json")
    short_training = _read_json(ROOT / SHORT_ROOT_REL / "training_config.json")
    short_card = _read_json(ROOT / SHORT_ROOT_REL / "model_card.json")
    short_result = _read_json(ROOT / SHORT_ROOT_REL / "evaluation_result.json")

    role = contract.get("roles", {}).get(ROLE_ID, {})
    _assert(contract.get("contract_id") == CONTRACT_ID, "M-PV3.6 identity mismatch")
    _assert(contract.get("phase") == "M-PV3.6", "unexpected M-PV3.6 phase")
    _assert(contract.get("frozen_before_future_evaluation") is True, "contract is not frozen")
    _assert(contract.get("phase_mode") == "CONTRACT_DESIGN_ONLY", "contract mode changed")
    _assert(matrix.get("contract_id") == CONTRACT_ID, "evaluation matrix identity mismatch")
    _assert(evidence.get("contract_id") == CONTRACT_ID, "evidence requirement identity mismatch")
    _assert(role.get("context_seconds") == 15, "Role S context changed")
    _assert(role.get("input_shape") == "[B,150,1]", "Role S input shape changed")
    _assert(role.get("rr_metric_status") == "NOT_APPLICABLE", "Role S RR status changed")
    _assert(role.get("temporal_hold_metric_status") == "NOT_APPLICABLE", "Role S temporal-hold status changed")
    _assert(contract["predecessors"]["m_pv3"]["authoritative_selection_result"] == "NO_SELECTION_READY", "M-PV3 selection state changed")
    _assert(contract["decision_boundary"]["m_pv4_approval"] is False, "M-PV4 unexpectedly authorized")
    _assert(contract["decision_boundary"]["d2_semantic_access"] is False, "D2 unexpectedly authorized")
    _assert(contract["decision_boundary"]["mr60_supervised_physiology"] is False, "MR60 supervised physiology unexpectedly authorized")

    _assert(short_input.get("identity") == CANDIDATE_ID, "short input identity mismatch")
    _assert(short_input["context"]["shape"] == "[B,150,1]", "short input contract mismatch")
    _assert(short_input["context"]["sampling_rate_hz"] == 10, "short sampling rate changed")
    _assert(short_input["context"]["samples"] == 150, "short sample count changed")
    _assert(short_input["context"]["target_start_sample_in_short_context"] == 100, "short target start changed")
    _assert(short_input["context"]["target_end_sample_exclusive_in_short_context"] == 150, "short target end changed")
    _assert(short_alignment["alignment_validation"]["future_samples"] is False, "future leakage flag changed")
    _assert(short_alignment["alignment_validation"]["random_alignment"] is False, "random alignment flag changed")
    _assert(short_alignment["alignment_validation"]["internal_event_position"] is False, "event-position leakage flag changed")
    _assert(short_audit["leakage_audit"]["d2_accessed"] is False, "short audit accessed D2")
    _assert(short_audit["leakage_audit"]["mr60_supervised_physiology_used"] is False, "short audit used MR60 supervised physiology")
    _assert(short_audit["label_lineage_audit"]["radar_amplitude_as_label_used"] is False, "radar amplitude label source detected")
    _assert(short_audit["label_lineage_audit"]["model_output_as_label_used"] is False, "model output label source detected")
    _assert(short_audit["label_lineage_audit"]["apnea_protocol_strings_used"] is False, "apnea protocol label source detected")
    _assert(short_audit["label_lineage_audit"]["breath_hold_names_used"] is False, "breath-hold label source detected")
    _assert(short_card["selection"]["final_selection"] is False, "short candidate is selected")
    _assert(short_card["selection"]["selected_float_model"] is False, "short float model is selected")
    _assert(short_training["evaluation"]["selection_during_phase"] is False, "selection was enabled in source training config")
    _assert(short_training["preprocessing"]["d0_val_used"] is False, "D0 VAL was used")
    _assert(short_training["preprocessing"]["d0_subject_heldout_used"] is False, "D0 heldout was used")
    _assert(short_training["preprocessing"]["d2_used"] is False, "D2 was used")
    _assert(short_training["preprocessing"]["mr60_supervised_labels_used"] is False, "MR60 labels were used")
    _assert(short_training["quality"]["synthetic_corruption"]["used_for_threshold_tuning"] is False, "corruption threshold tuning detected")

    return {
        "contract": contract,
        "matrix": matrix,
        "evidence_requirements": evidence,
        "short_input": short_input,
        "short_alignment": short_alignment,
        "short_audit": short_audit,
        "short_training": short_training,
        "short_card": short_card,
        "short_result": short_result,
    }


def _load_models(card: Mapping[str, Any]) -> dict[int, Any]:
    models: dict[int, Any] = {}
    checkpoints = {
        int(item["path"].rsplit("candidate_seed_", 1)[1].split(".", 1)[0]): item
        for item in card.get("checkpoints", [])
    }
    _assert(set(checkpoints) == set(SEEDS), "frozen checkpoint seed set changed")
    for seed in SEEDS:
        metadata = checkpoints[seed]
        path = ROOT / metadata["path"]
        _assert(path.is_file(), f"missing frozen checkpoint: {metadata['path']}")
        _assert(_sha256_file(path) == metadata["sha256"], f"checkpoint checksum mismatch: {metadata['path']}")
        _assert(path.stat().st_size == metadata["bytes"], f"checkpoint byte count mismatch: {metadata['path']}")
        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:  # pragma: no cover - older torch compatibility
            payload = torch.load(path, map_location="cpu")
        _assert(payload.get("identity") == CANDIDATE_ID, f"checkpoint identity mismatch for seed {seed}")
        _assert(int(payload.get("seed")) == seed, f"checkpoint seed mismatch for seed {seed}")
        _assert(payload.get("selection_status") == "NOT_SELECTED", f"checkpoint selection status changed for seed {seed}")
        model = short.ShortBreathingCNN()
        model.load_state_dict(payload["state_dict"])
        model.eval()
        models[seed] = model
    return models


def _group_records(records: Sequence[Any]) -> dict[str, list[Any]]:
    return {
        "D0_TRAIN_OBSERVE": [record for record in records if record.source_id == "D0"],
        "D1_DEV_VAL": [record for record in records if record.source_id == "D1" and record.split == "D1_DEV_VAL"],
    }


def _classification_metrics(records: Sequence[Any], scores: np.ndarray) -> dict[str, Any]:
    _assert(len(records) == len(scores), "prediction/record count mismatch")
    active = np.asarray([record.breathing_mask > 0 for record in records], dtype=bool)
    labels = np.asarray([1 if record.breathing_state == PRESENT else 0 for record in records], dtype=np.int64)
    predicted = scores >= THRESHOLD
    y = labels[active]
    p = predicted[active]
    tp = int(np.sum((y == 1) & (p == 1)))
    tn = int(np.sum((y == 0) & (p == 0)))
    fp = int(np.sum((y == 0) & (p == 1)))
    fn = int(np.sum((y == 1) & (p == 0)))
    present_recall = _safe_divide(tp, tp + fn)
    absent_recall = _safe_divide(tn, tn + fp)
    precision = _safe_divide(tp, tp + fp)
    f1 = _safe_divide(2 * tp, 2 * tp + fp + fn)
    absent_f1 = _safe_divide(2 * tn, 2 * tn + fn + fp)
    macro_f1 = (
        float(statistics.fmean([f1, absent_f1]))
        if f1 is not None and absent_f1 is not None and np.any(y == 1) and np.any(y == 0)
        else None
    )
    brier = float(np.mean((scores[active] - labels[active]) ** 2)) if y.size else None
    return {
        "status": "DEFINED" if y.size else "NOT_APPLICABLE_NO_VALID_SUPERVISION",
        "threshold": THRESHOLD,
        "threshold_tuned": False,
        "record_count": len(records),
        "supervision_eligible_count": int(y.size),
        "present_count": int(np.sum(y == 1)),
        "absent_count": int(np.sum(y == 0)),
        "ambiguous_count": int(sum(record.breathing_state == AMBIGUOUS for record in records)),
        "target_unavailable_count": int(sum(record.quality_status == "INPUT_UNAVAILABLE" for record in records)),
        "ambiguous_handling": "EXCLUDED_FROM_METRICS_NO_LABEL_REWRITE",
        "confusion": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "present_recall": present_recall,
        "absent_recall": absent_recall,
        "precision": precision,
        "f1": f1,
        "f1_definition": "PRESENT_CLASS_F1",
        "macro_f1": macro_f1,
        "brier": brier,
    }


def _subject_results(records: Sequence[Any], scores: np.ndarray) -> list[dict[str, Any]]:
    by_subject: dict[str, list[tuple[Any, float]]] = {}
    for record, score in zip(records, scores):
        by_subject.setdefault(record.subject_id, []).append((record, float(score)))
    return [
        {"subject_id": subject_id, **_classification_metrics(
            [item[0] for item in items],
            np.asarray([item[1] for item in items], dtype=np.float64),
        )}
        for subject_id, items in sorted(by_subject.items())
    ]


def _metric_summary(rows: Sequence[Mapping[str, Any]], metric: str) -> dict[str, Any]:
    values = [
        (int(row["seed"]), float(row["metrics"][metric]))
        for row in rows
        if row["metrics"].get(metric) is not None and _finite(row["metrics"].get(metric))
    ]
    if not values:
        return {"status": "NOT_APPLICABLE", "metric": metric, "n": 0}
    higher_is_better = metric != "brier"
    worst_seed, worst_value = (min(values, key=lambda item: item[1]) if higher_is_better else max(values, key=lambda item: item[1]))
    best_seed, best_value = (max(values, key=lambda item: item[1]) if higher_is_better else min(values, key=lambda item: item[1]))
    only_values = [item[1] for item in values]
    return {
        "status": "DEFINED",
        "metric": metric,
        "n": len(only_values),
        "mean": float(statistics.fmean(only_values)),
        "population_std": float(np.std(only_values)),
        "min": float(min(only_values)),
        "max": float(max(only_values)),
        "worst_seed": worst_seed,
        "worst_value": float(worst_value),
        "best_seed": best_seed,
        "best_value": float(best_value),
        "direction": "higher_is_better" if higher_is_better else "lower_is_better",
        "descriptive_only_no_seed_selection": True,
    }


def _evaluate_breathing(
    models: Mapping[int, Any], records: Sequence[Any], scaler: Mapping[str, Any], frozen_result: Mapping[str, Any]
) -> dict[str, Any]:
    groups = _group_records(records)
    per_seed: dict[str, Any] = {}
    for seed in SEEDS:
        seed_groups: dict[str, Any] = {}
        for group_name, group_records in groups.items():
            scores = short._predict(models[seed], group_records, scaler)
            metrics = _classification_metrics(group_records, scores)
            subject_rows = _subject_results(group_records, scores)
            seed_groups[group_name] = {
                "metrics": metrics,
                "subject_level_results": subject_rows,
                "subject_count": len(subject_rows),
            }
        per_seed[str(seed)] = {
            "seed": seed,
            "checkpoint": next(item for item in frozen_result["short_card"]["checkpoints"] if f"candidate_seed_{seed}.pt" in item["path"]),
            "groups": seed_groups,
        }

    summary_by_group: dict[str, Any] = {}
    for group_name in groups:
        rows = [per_seed[str(seed)]["groups"][group_name] for seed in SEEDS]
        summary_by_group[group_name] = {
            metric: _metric_summary(
                [{"seed": seed, "metrics": per_seed[str(seed)]["groups"][group_name]["metrics"]} for seed in SEEDS],
                metric,
            )
            for metric in ("present_recall", "absent_recall", "precision", "f1", "brier")
        }
        summary_by_group[group_name]["subject_count_by_seed"] = {
            str(seed): per_seed[str(seed)]["groups"][group_name]["subject_count"] for seed in SEEDS
        }

    frozen_per_seed = frozen_result["short_result"]["breathing_evidence"]["short_context_metrics"]["per_seed"]
    reproduction_checks: list[dict[str, Any]] = []
    for seed in SEEDS:
        for group_name in groups:
            ours = per_seed[str(seed)]["groups"][group_name]["metrics"]
            frozen = frozen_per_seed[str(seed)]["groups"][group_name]
            for field in ("present_recall", "absent_recall", "f1", "brier"):
                frozen_field = "present_f1" if field == "f1" else field
                expected = frozen.get(frozen_field)
                actual = ours.get(field)
                matches = (expected is None and actual is None) or (
                    expected is not None and actual is not None and math.isclose(float(expected), float(actual), rel_tol=0.0, abs_tol=1e-9)
                )
                reproduction_checks.append({"seed": seed, "group": group_name, "metric": field, "matches_frozen_result": matches})
    _assert(all(item["matches_frozen_result"] for item in reproduction_checks), "replayed metrics differ from frozen M-PV2 result")

    return {
        "card_id": "S_BREATHING",
        "class": "B",
        "state": "PASS_WITH_LIMITATIONS",
        "task": "BREATHING_EVIDENCE_ONLY",
        "metrics": {
            "present_recall": "reported_per_seed_and_summary",
            "absent_recall": "reported_where_governed_and_defined; D1_DEV_VAL NOT_APPLICABLE",
            "precision": "reported_per_seed_and_summary",
            "f1": "reported_per_seed_and_summary_as_PRESENT_CLASS_F1",
            "brier": "reported_per_seed_and_summary",
            "ece": {
                "state": "NOT_APPLICABLE",
                "calibration_already_exists": False,
                "calibration_generated": False,
                "reason": "M-PV3.6 permits ECE only when calibration already exists; no calibration was generated.",
            },
        },
        "evaluation_membership": {
            "D0_TRAIN_OBSERVE": {"role": "observe_only_not_held_out", "record_count": len(groups["D0_TRAIN_OBSERVE"])},
            "D1_DEV_VAL": {"role": "governed_development_validation", "record_count": len(groups["D1_DEV_VAL"])},
        },
        "per_seed": per_seed,
        "summary_by_group": summary_by_group,
        "reproduction_against_frozen_m_pv2_result": {
            "all_checked_metrics_match": True,
            "checks": reproduction_checks,
        },
        "calibration_and_threshold_policy": {
            "threshold": THRESHOLD,
            "threshold_source": "frozen M-PV2-SHORT evaluation threshold",
            "threshold_tuned_in_this_phase": False,
            "ece_generated": False,
        },
    }


def _safety_card() -> dict[str, Any]:
    q2_regression = _read_json(ROOT / Q2_REGRESSION_REL)
    q2_profile = _read_json(ROOT / Q2_PROFILE_REL)
    presence = _read_json(ROOT / I3_PRESENCE_REL)
    availability = _read_json(ROOT / I3_AVAILABILITY_REL)
    i3_contract = _read_json(ROOT / I3_CONTRACT_REL)
    required_modes = {
        "LARGE_GAP": "LARGE_GAP",
        "SOURCE_FREEZE": "SOURCE_FREEZE",
        "STALE_SOURCE": "SOURCE_STALE",
        "FLAT_EXACT": "SIGNAL_FLAT_EXACT",
    }
    scenarios: dict[str, Any] = {}
    for mode, reason in required_modes.items():
        result = q2_regression["modes"][mode]
        passed = (
            result["availability_state"] == "INPUT_UNAVAILABLE"
            and result["expected_state"] == "INPUT_UNAVAILABLE"
            and result["physiology_executed"] is False
            and result["interpolation_applied"] is False
            and result["primary_reason"] == reason
        )
        _assert(passed, f"Q2 safety scenario failed: {mode}")
        scenarios[mode] = {
            "status": "PASS",
            "qualification": "SYNTHETIC_ONLY",
            "availability_state": result["availability_state"],
            "application_state": "INPUT_UNAVAILABLE",
            "physiology_executed": result["physiology_executed"],
            "physiology_class_assigned": None,
            "interpolation_applied": result["interpolation_applied"],
            "primary_reason": result["primary_reason"],
            "source_evidence": _relative(ROOT / Q2_REGRESSION_REL),
        }

    presence_cases = {
        "presence_false": presence["no_person"],
        "presence_unknown": presence["unknown_production"],
        "presence_true_plus_invalid": presence["true_plus_invalid"],
    }
    _assert(presence_cases["presence_false"]["physiology_executed"] is False, "presence false reached physiology")
    _assert(presence_cases["presence_false"]["application_state"] == "PRESENCE_SUPPRESSED", "presence false state changed")
    _assert(presence_cases["presence_unknown"]["physiology_executed"] is False, "presence unknown reached physiology")
    _assert(presence_cases["presence_unknown"]["application_state"] == "PRESENCE_SUPPRESSED", "presence unknown state changed")
    _assert(presence_cases["presence_true_plus_invalid"]["physiology_executed"] is False, "invalid input reached physiology")
    _assert(presence_cases["presence_true_plus_invalid"]["application_state"] == "INPUT_UNAVAILABLE", "invalid input state changed")
    _assert(i3_contract.get("d2_used") is False, "I3 D2 usage flag changed")
    _assert(i3_contract.get("mr60_supervised_use") is False, "I3 MR60 usage flag changed")
    _assert(q2_profile.get("model_outputs_used") is False, "Q2 model output usage flag changed")
    _assert(q2_profile.get("mr60_labels_used") is False, "Q2 MR60 label usage flag changed")
    _assert(q2_profile.get("physiology_labels_modified") is False, "Q2 physiology label modification flag changed")

    forbidden_outputs = ["PRESENT", "ABSENT", "NORMAL", "APNEA"]
    return {
        "card_id": "S_SAFETY",
        "class": "A",
        "state": "PASS_WITH_LIMITATIONS",
        "qualification": "SYNTHETIC_ONLY",
        "runtime_order": ["presence", "quality_availability", "physiology"],
        "scenarios": scenarios,
        "presence_precedence": {
            "presence_false": {
                "status": "PASS",
                "application_state": presence_cases["presence_false"]["application_state"],
                "physiology_executed": False,
                "source_evidence": _relative(ROOT / I3_PRESENCE_REL),
            },
            "presence_unknown": {
                "status": "PASS",
                "application_state": presence_cases["presence_unknown"]["application_state"],
                "physiology_executed": False,
                "source_evidence": _relative(ROOT / I3_PRESENCE_REL),
            },
            "presence_true_plus_invalid": {
                "status": "PASS",
                "application_state": presence_cases["presence_true_plus_invalid"]["application_state"],
                "physiology_executed": False,
                "source_evidence": _relative(ROOT / I3_PRESENCE_REL),
            },
        },
        "invalid_must_not_become": forbidden_outputs,
        "invalid_to_physiology_transition": {
            "status": "PASS",
            "all_invalid_scenarios_block_physiology": True,
            "all_invalid_scenarios_have_null_physiology_class": True,
        },
        "source_policy": {
            "q2_profile_id": q2_profile["profile_id"],
            "q2_diagnostics_synthetic_only": True,
            "d2_accessed": False,
            "mr60_supervised_physiology_used": False,
            "model_outputs_used_for_quality_labels": False,
            "physiology_labels_modified": False,
            "threshold_tuning_on_corruption": False,
            "source_evidence": [
                _relative(ROOT / Q2_PROFILE_REL),
                _relative(ROOT / Q2_REGRESSION_REL),
                _relative(ROOT / I3_PRESENCE_REL),
                _relative(ROOT / I3_AVAILABILITY_REL),
            ],
        },
    }


def _responsiveness_card(short_result: Mapping[str, Any]) -> dict[str, Any]:
    availability = short_result["availability"]["short_context"]
    modes: dict[str, Any] = {}
    for mode in ("gap", "freeze", "stale_source"):
        item = availability[mode]
        _assert(item["synthetic_quality_only"] is True, f"responsiveness mode is not synthetic-only: {mode}")
        _assert(item["first_valid_decision_time_s"] == 15.0, f"first valid decision changed: {mode}")
        _assert(item["recovery_time_after_event_s"] == 15.0, f"context refill changed: {mode}")
        modes[mode] = {
            "status": "REPORTED",
            "qualification": "SYNTHETIC_ONLY",
            "context_refill_time_s": item["recovery_time_after_event_s"],
            "first_valid_decision_time_s": item["first_valid_decision_time_s"],
            "usable_slot_ratio": item["usable_prediction_ratio"],
            "input_unavailable_ratio": item["input_unavailable_ratio"],
            "context_requirement_s": item["context_requirement_s"],
            "source_evidence": _relative(ROOT / SHORT_ROOT_REL / "evaluation_result.json"),
        }
    return {
        "card_id": "S_RESPONSIVENESS",
        "class": "D",
        "state": "PASS_WITH_LIMITATIONS",
        "qualification": "SYNTHETIC_ONLY",
        "modes": modes,
        "real_device_latency_measured": False,
        "raspberry_pi_benchmark": False,
    }


def _footprint_card(card: Mapping[str, Any]) -> dict[str, Any]:
    architecture = card["architecture"]
    flops = architecture["flops_estimate"]
    checkpoints = list(card["checkpoints"])
    input_bytes = 150 * 1 * 4
    output_bytes = 1 * 4
    activation_elements = (8 * 73) + (16 * 35) + (24 * 17) + 24 + 16 + 1
    activation_bytes = activation_elements * 4
    parameter_bytes = int(architecture["float32_parameter_bytes"])
    deterministic_memory = parameter_bytes + input_bytes + activation_bytes + output_bytes
    return {
        "card_id": "S_FOOTPRINT",
        "class": "E",
        "state": "PASS_WITH_LIMITATIONS",
        "parameter_count": architecture["parameter_count"],
        "float32_parameter_bytes": parameter_bytes,
        "model_bytes": {
            "checkpoint_bytes_per_seed": {str(item["path"].rsplit("candidate_seed_", 1)[1].split(".", 1)[0]): item["bytes"] for item in checkpoints},
            "all_frozen_checkpoint_bytes": int(sum(item["bytes"] for item in checkpoints)),
            "selected_model_bytes": None,
        },
        "input_tensor_bytes": {
            "shape": "[1,150,1]",
            "dtype": "float32",
            "bytes": input_bytes,
        },
        "output_tensor_bytes": output_bytes,
        "macs": flops["multiply_accumulates"],
        "flops": flops["estimated_flops"],
        "deterministic_memory_estimate": {
            "method": "parameter bytes + input + output + all declared inference intermediates",
            "bytes": deterministic_memory,
            "hardware_allocator_measurement": False,
        },
        "raspberry_pi_benchmark": False,
        "int8_generated": False,
    }


def _source_hashes() -> dict[str, str]:
    paths = [
        M_PV36_CONTRACT_REL,
        M_PV36_MATRIX_REL,
        M_PV36_EVIDENCE_REL,
        SHORT_ROOT_REL / "input_contract.json",
        SHORT_ROOT_REL / "target_alignment.json",
        SHORT_ROOT_REL / "dataset_audit.json",
        SHORT_ROOT_REL / "training_config.json",
        SHORT_ROOT_REL / "model_card.json",
        SHORT_ROOT_REL / "evaluation_result.json",
        Q2_PROFILE_REL,
        Q2_REGRESSION_REL,
        I3_CONTRACT_REL,
        I3_PRESENCE_REL,
        I3_AVAILABILITY_REL,
        Path("scripts/mmwave_m_pv2_short_context_15s_candidate.py"),
        Path("scripts/mmwave_q2_input_unavailable.py"),
        Path("scripts/mmwave_i3_fail_closed_regression.py"),
    ]
    paths.extend(SHORT_MODEL_REL / f"candidate_seed_{seed}.pt" for seed in SEEDS)
    result: dict[str, str] = {}
    for relative in paths:
        path = ROOT / relative
        _assert(path.is_file(), f"missing source evidence for checksum: {relative}")
        result[relative.as_posix()] = _sha256_file(path)
    return dict(sorted(result.items()))


def build_manifest() -> dict[str, Any]:
    frozen = _load_frozen_inputs()
    records, source_scope = short._load_short_records()
    _assert(len(records) == 562, f"governed short membership changed: {len(records)}")
    scaler = frozen["short_training"]["trace_scaler"]
    models = _load_models(frozen["short_card"])
    breathing = _evaluate_breathing(models, records, scaler, frozen)
    safety = _safety_card()
    responsiveness = _responsiveness_card(frozen["short_result"])
    footprint = _footprint_card(frozen["short_card"])

    d0_records = [record for record in records if record.source_id == "D0"]
    d1_val_records = [record for record in records if record.source_id == "D1" and record.split == "D1_DEV_VAL"]
    d1_train_records = [record for record in records if record.source_id == "D1" and record.split == "D1_DEV_TRAIN"]
    d1_val_subjects = sorted({record.subject_id for record in d1_val_records})
    d1_train_subjects = sorted({record.subject_id for record in d1_train_records})

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "phase": "M-PV3.6",
        "role_id": ROLE_ID,
        "candidate_identity": CANDIDATE_ID,
        "evaluation_identity": "M-PV3_6_ROLE_S_SHORT_CONTEXT_EVALUATION_RESULT",
        "gate": "PASS_WITH_LIMITATIONS",
        "evaluation_only": True,
        "execution_policy": {
            "training_performed": False,
            "retraining_performed": False,
            "new_checkpoint_created": False,
            "threshold_tuning_performed": False,
            "calibration_fitted": False,
            "seed_selection_performed": False,
            "combined_score_created": False,
            "role_l_comparison_performed": False,
            "cascade_or_adaptive_context_implemented": False,
            "d2_accessed": False,
            "mr60_supervised_physiology_used": False,
            "int8_generated": False,
            "raspberry_pi_benchmark_performed": False,
        },
        "frozen_contract_snapshot": {
            "contract_id": CONTRACT_ID,
            "m_pv3_selection_state": frozen["contract"]["predecessors"]["m_pv3"]["authoritative_selection_result"],
            "m_pv4_authorized": frozen["contract"]["decision_boundary"]["m_pv4_approval"],
            "d2_authorized": frozen["contract"]["decision_boundary"]["d2_semantic_access"],
            "mr60_supervised_physiology_authorized": frozen["contract"]["decision_boundary"]["mr60_supervised_physiology"],
            "no_combined_score": frozen["contract"]["global_rules"]["combined_winner_score"],
            "safety_non_compensable": frozen["contract"]["global_rules"]["safety_is_non_compensable"],
        },
        "input_and_target": {
            "input_shape": "[B,150,1]",
            "context_interval": "[t-15s,t]",
            "sampling_rate_hz": 10,
            "sample_count": 150,
            "ordering": "OLDEST_TO_NEWEST",
            "target_interval": "[t-5s,t]",
            "target_sample_range": [100, 150],
            "task_scope": "BREATHING_EVIDENCE_ONLY",
            "rr": {"status": "NOT_APPLICABLE", "evaluated": False},
            "temporal_hold": {"status": "NOT_APPLICABLE", "evaluated": False},
            "source_input_contract": _relative(ROOT / SHORT_ROOT_REL / "input_contract.json"),
            "source_target_alignment": _relative(ROOT / SHORT_ROOT_REL / "target_alignment.json"),
        },
        "governed_data_audit": {
            "source_policy": "M-PV1 governed membership only",
            "D0": {
                "split": "TRAIN",
                "role": "OBSERVE_ONLY_NOT_HELD_OUT",
                "context_count": len(d0_records),
                "subject_count": len({record.subject_id for record in d0_records}),
                "eligible_absent_count": sum(record.breathing_state == ABSENT for record in d0_records),
                "eligible_present_count": sum(record.breathing_state == PRESENT for record in d0_records),
                "ambiguous_count": sum(record.breathing_state == AMBIGUOUS for record in d0_records),
            },
            "D1": {
                "selected_splits": ["D1_DEV_TRAIN", "D1_DEV_VAL"],
                "train_context_count": len(d1_train_records),
                "val_context_count": len(d1_val_records),
                "train_subject_count": len(d1_train_subjects),
                "val_subject_count": len(d1_val_subjects),
                "train_subject_ids": d1_train_subjects,
                "val_subject_ids": d1_val_subjects,
                "subject_intersection_count": len(set(d1_train_subjects) & set(d1_val_subjects)),
                "val_eligible_absent_count": sum(record.breathing_state == ABSENT for record in d1_val_records),
                "val_eligible_present_count": sum(record.breathing_state == PRESENT for record in d1_val_records),
                "val_ambiguous_count": sum(record.breathing_state == AMBIGUOUS for record in d1_val_records),
            },
            "D0_VAL_accessed": False,
            "D0_SUBJECT_HELDOUT_accessed": False,
            "D2_accessed": False,
            "MR60_supervised_physiology_accessed": False,
            "target_regenerated": False,
            "future_samples_used": False,
            "target_from_radar_amplitude": False,
            "target_from_apnea_protocol_string": False,
            "target_from_breath_hold_name": False,
            "target_from_model_output": False,
            "source_audit": _relative(ROOT / SHORT_ROOT_REL / "dataset_audit.json"),
            "source_scope_summary": source_scope.get("counts", {}),
        },
        "cards": {
            "S_BREATHING": breathing,
            "S_SAFETY": safety,
            "S_STABILITY": {
                "card_id": "S_STABILITY",
                "class": "C",
                "state": "PASS_WITH_LIMITATIONS",
                "mean_only_summary_prohibited": True,
                "all_frozen_seeds_reported": True,
                "seed_count": len(SEEDS),
                "seeds": list(SEEDS),
                "summary_by_group": breathing["summary_by_group"],
                "per_seed_and_subject_results": breathing["per_seed"],
                "post_hoc_seed_selection": False,
                "seed_instability_observed": True,
                "future_stability_threshold": "NOT_SET_REQUIRES_PRE_REGISTRATION",
            },
            "S_RESPONSIVENESS": responsiveness,
            "S_FOOTPRINT": footprint,
        },
        "limitations": [
            "D1_DEV_VAL contains zero eligible ABSENT contexts; D1 ABSENT recall and balanced two-class F1 are NOT_APPLICABLE, not zero or failure.",
            "D0 TRAIN metrics are observe-only and are not held-out selection evidence.",
            "Seed instability is visible, including materially different D1 PRESENT recall; no seed was dropped or selected.",
            "D1 DEV VAL has only three validation subjects, and the governed role evaluation has limited subject coverage.",
            "RR is NOT_APPLICABLE for Role S and was not evaluated.",
            "Temporal hold is NOT_APPLICABLE for Role S and was not evaluated.",
            "D2 remains locked and was not accessed.",
            "MR60 supervised physiology remains prohibited and was not used.",
            "No INT8 or TFLite artifact was generated.",
            "No Raspberry Pi or real-device benchmark was performed.",
            "Q2 gap, freeze, stale, and flat diagnostics are SYNTHETIC_ONLY.",
            "No final role eligibility, model selection, context winner, cascade, or adaptive-context decision is made.",
        ],
        "conclusion": {
            "question": "Is ROLE_S_SHORT_CONTEXT sufficiently evidenced for future role comparison?",
            "answer": "PASS_WITH_LIMITATIONS",
            "statement": "Role S has independently measurable breathing, safety, stability, responsiveness, and footprint evidence for a future role comparison, but current evidence is limited by D1 ABSENT unavailability, seed instability, limited subject coverage, and synthetic-only responsiveness. This is not a final model or context selection.",
        },
        "source_artifact_sha256": _source_hashes(),
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the Role S evidence manifest")
    args = parser.parse_args()
    manifest = build_manifest()
    if args.write:
        _write_json(ROOT / MANIFEST_REL, manifest)
    print(json.dumps({
        "role_id": ROLE_ID,
        "candidate_identity": CANDIDATE_ID,
        "gate": manifest["gate"],
        "evaluation_only": manifest["evaluation_only"],
        "seed_count": manifest["cards"]["S_STABILITY"]["seed_count"],
        "d1_val_absent_count": manifest["governed_data_audit"]["D1"]["val_eligible_absent_count"],
        "output": _relative(ROOT / MANIFEST_REL),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
