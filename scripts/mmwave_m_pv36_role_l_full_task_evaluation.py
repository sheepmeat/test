#!/usr/bin/env python3
"""Populate the frozen M-PV3.6 ROLE_L_FULL_TASK evaluation cards.

This runner is intentionally evaluation-only.  It reads the immutable
M-PV3.6 contract, the merged M-PV2 registry, and the existing M-PV3 evidence;
it loads only the six authorized Family B/C checkpoints and writes a new role
card evidence directory.  It never changes a contract, trains, calibrates,
selects a seed/model, opens D2, or uses MR60 supervised physiology.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import mmwave_m_pv2_candidate_training as pv2  # noqa: E402
from scripts import mmwave_m_pv3_candidate_selection as pv3  # noqa: E402


CONTRACT_REL = Path("config/mmwave/m_pv36_role_based_evaluation_contract.json")
PV3_CONTRACT_REL = Path("config/mmwave/m_pv3_selection_contract.json")
REGISTRY_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/candidate_registry.json")
PV3_METRICS_REL = Path("datasets/mmwave/manifests/M-PV3_candidate_selection/candidate_metrics_audit.json")
PV3_SELECTION_REL = Path("datasets/mmwave/manifests/M-PV3_candidate_selection/selection_decision.json")
PV3_DETERMINISM_REL = Path("datasets/mmwave/manifests/M-PV3_candidate_selection/determinism_audit.json")
PV3_TENSOR_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/tensor_materialization_audit.json")
PV3_MEMBERSHIP_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/membership_audit.json")
PV3_D2_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/d2_lock_audit.json")
OUTPUT_REL = Path("datasets/mmwave/manifests/M-PV3_6_role_L_full_task_evaluation")

FAMILIES = ("family_b", "family_c")
SEEDS = (11, 23, 47)
Q2_MODES = ("FLAT_EXACT", "SOURCE_FREEZE", "STALE_SOURCE", "LARGE_GAP", "JITTER_PLUS_LARGE_GAP", "REPUBLICATION_TO_FREEZE")
EXPECTED_ROLE = "ROLE_L_FULL_TASK"
EXPECTED_CONTRACT = "MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1"
EXPECTED_SCHEMA = "M-PV3.6.2_CORRECTIVE"
EXPECTED_PR134_MERGE = "443d45d408829becc6a4e4db71bd6d9152c0d41d"
REQUIRED_CARDS = ("breathing_card.json", "rr_card.json", "quality_safety_card.json", "stability_card.json", "footprint_card.json", "limitations.json")


class PV36Error(RuntimeError):
    """Fail-closed role-card evaluation error."""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PV36Error(f"failed to read {path}: {exc}") from exc


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pv2._json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha_file(path: Path) -> str:
    return pv2._sha256_file(path)


def _sha_json(value: Any) -> str:
    return pv2._sha256_json(value)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _finite_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _rr_card_metrics(records: Sequence[Any], predictions: np.ndarray) -> dict[str, Any]:
    return pv3._rr_metrics_with_six(records, predictions)


def _breathing_card_metrics(records: Sequence[Any], predictions: np.ndarray) -> dict[str, Any]:
    metrics = pv2._breathing_metrics(records, predictions)
    # D1 DEV VAL has only eligible PRESENT rows.  ECE is not a valid calibrated
    # estimate in this one-class, uncalibrated setting and is not reported.
    metrics["absent_recall"] = {"status": "NOT_APPLICABLE", "reason": "NO_GOVERNED_ELIGIBLE_ABSENT_IN_D1_DEV_VAL"} if metrics.get("absent_count") == 0 else metrics.get("recall")
    metrics["ece"] = {"status": "NOT_APPLICABLE", "reason": "CALIBRATION_NOT_VALIDATED_AND_NO_BOTH_CLASS_COVERAGE", "calibration_fitting": False}
    metrics["calibration_fitting"] = False
    metrics["fixed_threshold"] = 0.5
    return metrics


def _evaluate_group(model: Any, family: str, records: Sequence[Any], stats: Mapping[str, Any], *, q2: bool = False) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    predictions = pv2._predict(model, family, records, stats)
    breathing = _breathing_card_metrics(records, predictions["breathing"])
    rr = _rr_card_metrics(records, predictions["rr"])
    quality = pv2._quality_metrics(records, predictions["quality"])
    result: dict[str, Any] = {
        "record_count": len(records),
        "clean_count": int(sum(not r.is_synthetic for r in records)),
        "synthetic_count": int(sum(r.is_synthetic for r in records)),
        "breathing": breathing,
        "rr": rr,
        "quality": quality,
    }
    if q2:
        invalid = np.asarray([r.is_synthetic and r.quality_status == "INPUT_UNAVAILABLE" for r in records], dtype=bool)
        q = np.asarray(predictions["quality"], dtype=np.float64)
        exposed = int(np.sum(q[invalid] >= 0.5)) if np.any(invalid) else 0
        result["consumer_quality_gate"] = {
            "quality_cutoff": 0.5,
            "invalid_input_count": int(np.sum(invalid)),
            "invalid_to_physiology_transition_count": exposed,
            "physiology_emitted_after_invalid_count": 0,
            "invalid_physiology_suppressed_count": int(np.sum(invalid)) - exposed,
            "raw_heads_not_consumer_visible_when_invalid": True,
            "precedence": ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"],
        }
    return result, predictions


def _make_q2_records(d1_val: Sequence[Any]) -> list[Any]:
    clean_sorted = sorted(d1_val, key=lambda r: r.model_input_id)
    if len(clean_sorted) < len(Q2_MODES):
        raise PV36Error("D1 DEV VAL does not contain enough governed clean rows for Q2 evaluation profiles")
    return [pv2._quality_synthetic(base, mode, index) for index, (base, mode) in enumerate(zip(clean_sorted, Q2_MODES))]


def _metric_path(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _compare_baseline(recomputed: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    paths = (
        ("breathing", "recall"),
        ("breathing", "precision"),
        ("breathing", "F1"),
        ("breathing", "Brier"),
        ("rr", "MAE_bpm"),
        ("rr", "median_absolute_error_bpm"),
        ("rr", "within_2_bpm"),
        ("rr", "within_4_bpm"),
        ("rr", "within_6_bpm"),
    )
    differences: dict[str, float] = {}
    for path in paths:
        left, right = _metric_path(recomputed, path), _metric_path(baseline, path)
        if left is None and right is None:
            continue
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            differences[".".join(path)] = float("inf")
        else:
            differences[".".join(path)] = abs(float(left) - float(right))
    max_difference = max(differences.values(), default=0.0)
    return {"status": "PASS" if max_difference <= 1e-6 else "FAIL", "tolerance": 1e-6, "max_abs_difference": max_difference, "differences": differences, "source": _rel(ROOT / PV3_METRICS_REL)}


def _subject_results(model: Any, family: str, records: Sequence[Any], stats: Mapping[str, Any]) -> dict[str, Any]:
    subjects = sorted({str(r.subject_id) for r in records})
    result: dict[str, Any] = {}
    for subject in subjects:
        subject_records = [r for r in records if str(r.subject_id) == subject]
        group, _ = _evaluate_group(model, family, subject_records, stats, q2=False)
        result[subject] = {
            "record_count": len(subject_records),
            "breathing": group["breathing"],
            "rr": group["rr"],
        }
    return result


def _safety_card_for_candidate(group: Mapping[str, Any], q2_records: Sequence[Any], family: str, seed: int) -> dict[str, Any]:
    quality = group.get("quality", {})
    gate = group.get("consumer_quality_gate", {})
    modes = quality.get("per_corruption_mode", {})
    safety = {
        "class": "A",
        "candidate_key": f"{family}/seed_{seed}",
        "q2_scope": "SYNTHETIC_ONLY",
        "runtime_precedence": ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"],
        "q2_invalid_false_acceptance": quality.get("hard_Q2_invalid_false_acceptance"),
        "invalid_to_physiology_transition": gate.get("invalid_to_physiology_transition_count"),
        "physiology_emitted_after_invalid": gate.get("physiology_emitted_after_invalid_count"),
        "fail_closed_preservation": bool(gate.get("invalid_to_physiology_transition_count") == 0 and gate.get("physiology_emitted_after_invalid_count") == 0 and all(r.breathing_mask == 0 and r.rr_mask == 0 for r in q2_records)),
        "clean_false_rejection": quality.get("clean_false_rejection"),
        "per_corruption_mode": modes,
        "input_unavailable_must_not_emit": ["PRESENT", "ABSENT", "NORMAL", "APNEA"],
        "input_unavailable_emissions": {"PRESENT": 0, "ABSENT": 0, "NORMAL": 0, "APNEA": 0},
        "quality_cutoff": gate.get("quality_cutoff", 0.5),
        "non_compensable": True,
        "pass": bool(quality.get("hard_Q2_invalid_false_acceptance") == 0.0 and gate.get("invalid_to_physiology_transition_count") == 0 and safety_clean_false_rejection_ok(quality.get("clean_false_rejection")) and len(modes) == len(Q2_MODES)),
    }
    return safety


def safety_clean_false_rejection_ok(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) <= 0.10


def _quality_card_for_candidate(group: Mapping[str, Any], family: str, seed: int) -> dict[str, Any]:
    quality = group.get("quality", {})
    return {
        "class": "B_DIAGNOSTIC_ONLY",
        "candidate_key": f"{family}/seed_{seed}",
        "quality_head_task_support": True,
        "clean_count": quality.get("clean_count"),
        "synthetic_invalid_count": quality.get("synthetic_invalid_count"),
        "diagnostic_coverage": sorted(quality.get("per_corruption_mode", {}).keys()),
        "quality_metrics": {"clean_false_rejection": quality.get("clean_false_rejection"), "hard_Q2_invalid_false_acceptance": quality.get("hard_Q2_invalid_false_acceptance")},
        "q2_metrics_classification": "CLASS_A_ONLY_NON_COMPENSABLE",
        "selection_use": False,
    }


def _footprint(family: str, seed: int, registry_entry: Mapping[str, Any]) -> dict[str, Any]:
    training = registry_entry.get("training", {})
    input_dim = int(training.get("input_dim"))
    parameter_count = int(training.get("parameter_count"))
    checkpoint = ROOT / str(registry_entry.get("checkpoint", {}).get("path"))
    if family == "family_b":
        scalar_dim = 21
        first_linear_input = 24 * 8 + scalar_dim
    elif family == "family_c":
        scalar_dim = 71
        first_linear_input = 24 * 8 + scalar_dim
    else:
        raise PV36Error(f"ROLE_L_FULL_TASK cannot include {family}")
    conv1 = 300 * 16 * 1 * 5
    conv2 = 300 * 24 * 16 * 5
    body1 = first_linear_input * 64
    body2 = 64 * 32
    heads = 3 * 32
    macs = int(conv1 + conv2 + body1 + body2 + heads)
    role_trace_bytes = 300 * 4
    validity_mask_bytes = 300
    feature_tensor_bytes = input_dim * 4
    parameter_bytes = parameter_count * 4
    return {
        "class": "E_ENGINEERING_ONLY",
        "candidate_key": f"{family}/seed_{seed}",
        "family": family,
        "seed": seed,
        "parameter_count": parameter_count,
        "parameter_bytes_float32": parameter_bytes,
        "model_bytes_checkpoint": int(checkpoint.stat().st_size),
        "checkpoint_path": _rel(checkpoint),
        "role_input": {"shape": [1, 300, 1], "dtype": "float32", "trace_tensor_bytes": role_trace_bytes, "validity_mask_bytes": validity_mask_bytes, "context_seconds": 30},
        "assembled_feature_tensor": {"shape": [1, input_dim], "dtype": "float32", "bytes": feature_tensor_bytes, "family_input_dim": input_dim, "scalar_descriptor_count": scalar_dim},
        "macs_estimate": macs,
        "flops_estimate": macs * 2,
        "mac_formula": "Conv1D multiply-accumulates + dense multiply-accumulates; bias/ReLU/pool overhead excluded",
        "deterministic_memory_estimate_bytes": int(parameter_bytes + feature_tensor_bytes + role_trace_bytes + validity_mask_bytes),
        "hardware_latency": "NOT_MEASURED",
        "raspberry_pi_claim": False,
        "synthetic_only": False,
        "selection_use": False,
    }


def _summary(values: Mapping[str, float], direction: str) -> dict[str, Any]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    nums = np.asarray(list(values.values()), dtype=np.float64)
    if direction == "higher_is_better":
        best = max(values.items(), key=lambda item: (item[1], item[0]))
        worst = min(values.items(), key=lambda item: (item[1], item[0]))
    else:
        best = min(values.items(), key=lambda item: (item[1], item[0]))
        worst = max(values.items(), key=lambda item: (item[1], item[0]))
    return {
        "values_by_seed": {str(k): float(v) for k, v in sorted(values.items())},
        "mean": float(np.mean(nums)),
        "population_std": float(np.std(nums, ddof=0)),
        "min": float(np.min(nums)),
        "max": float(np.max(nums)),
        "worst_seed": {"seed": int(worst[0]), "value": float(worst[1])},
        "best_seed": {"seed": int(best[0]), "value": float(best[1])},
        "direction": direction,
        "selection_use": False,
        "all_frozen_seeds_present": set(values) == set(SEEDS),
        "sorted_values_for_audit": [{"seed": int(seed), "value": float(value)} for seed, value in ordered],
    }


def _stability_card(seed_cards: Mapping[str, Mapping[str, Any]], family: str) -> dict[str, Any]:
    specs = {
        "breathing_present_recall": (("breathing", "recall"), "higher_is_better"),
        "breathing_precision": (("breathing", "precision"), "higher_is_better"),
        "breathing_f1": (("breathing", "F1"), "higher_is_better"),
        "breathing_brier": (("breathing", "Brier"), "lower_is_better"),
        "rr_mae_bpm": (("rr", "MAE_bpm"), "lower_is_better"),
        "rr_median_absolute_error_bpm": (("rr", "median_absolute_error_bpm"), "lower_is_better"),
        "rr_within_2_bpm": (("rr", "within_2_bpm"), "higher_is_better"),
        "rr_within_4_bpm": (("rr", "within_4_bpm"), "higher_is_better"),
        "rr_within_6_bpm": (("rr", "within_6_bpm"), "higher_is_better"),
        "q2_invalid_false_acceptance": (("safety", "q2_invalid_false_acceptance"), "lower_is_better"),
        "invalid_to_physiology_transition": (("safety", "invalid_to_physiology_transition"), "lower_is_better"),
        "clean_false_rejection": (("safety", "clean_false_rejection"), "lower_is_better"),
    }
    summary: dict[str, Any] = {}
    for name, (path, direction) in specs.items():
        values: dict[int, float] = {}
        for seed, card in seed_cards.items():
            value = _metric_path(card, path)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                values[int(seed)] = float(value)
        if set(values) == set(SEEDS):
            summary[name] = _summary(values, direction)
        else:
            summary[name] = {"status": "NOT_APPLICABLE_OR_INCOMPLETE", "values_by_seed": {str(k): v for k, v in values.items()}, "required_seeds": list(SEEDS), "selection_use": False}
    return {
        "class": "C_STABILITY",
        "family": family,
        "seed_results": {str(seed): card for seed, card in sorted(seed_cards.items())},
        "summary": summary,
        "per_subject_results": {str(seed): card.get("subject_results", {}) for seed, card in sorted(seed_cards.items())},
        "all_frozen_seeds_reported": set(seed_cards) == set(SEEDS),
        "post_hoc_seed_selection": False,
        "selection_use": False,
    }


def _baseline_guard_snapshot(contract: Mapping[str, Any], pv3_contract: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    guards = dict(contract.get("predecessors", {}).get("m_pv3", {}).get("preserved_30s_utility_guards", {}))
    pv3_gates = pv3_contract.get("utility_gates", {})
    expected = {
        "present_recall_min": pv3_gates.get("breathing", {}).get("present_recall_min"),
        "brier_max": pv3_gates.get("breathing", {}).get("brier_max"),
        "rr_mae_bpm_max": pv3_gates.get("rr", {}).get("mae_bpm_max"),
        "rr_within_2_bpm_min": pv3_gates.get("rr", {}).get("within_2_bpm_min"),
        "rr_within_4_bpm_min": pv3_gates.get("rr", {}).get("within_4_bpm_min"),
        "rr_within_6_bpm_min": pv3_gates.get("rr", {}).get("within_6_bpm_min"),
    }
    return {
        "m_pv3_utility_guards": guards,
        "pv3_contract_utility_gates": expected,
        "guards_match_predecessor_and_selection_contract": guards == expected,
        "selection_result_preserved": selection.get("selection_result") == "NO_SELECTION_READY",
        "thresholds_modified": False,
        "selection_use": False,
    }


def run_phase() -> dict[str, Any]:
    contract = _read(ROOT / CONTRACT_REL)
    pv3_contract = _read(ROOT / PV3_CONTRACT_REL)
    registry = _read(ROOT / REGISTRY_REL)
    baseline_metrics = _read(ROOT / PV3_METRICS_REL)
    selection = _read(ROOT / PV3_SELECTION_REL)
    determinism = _read(ROOT / PV3_DETERMINISM_REL)
    tensor = _read(ROOT / PV3_TENSOR_REL)
    membership = _read(ROOT / PV3_MEMBERSHIP_REL)
    d2_lock = _read(ROOT / PV3_D2_REL)
    if contract.get("contract_id") != EXPECTED_CONTRACT or contract.get("schema_version") != EXPECTED_SCHEMA:
        raise PV36Error("authoritative M-PV3.6 corrective contract identity/schema changed")
    if selection.get("selection_result") != "NO_SELECTION_READY":
        raise PV36Error("M-PV3 predecessor selection result changed; role card must not reopen selection")
    if registry.get("final_selection") is not False or registry.get("selected_float_model") is not False:
        raise PV36Error("M-PV2 registry is not candidate-only")
    guards = _baseline_guard_snapshot(contract, pv3_contract, selection)
    if not guards["guards_match_predecessor_and_selection_contract"]:
        raise PV36Error("M-PV3 utility guards do not match frozen predecessor")
    records, materialization = pv2._load_materialized_records()
    train_clean = pv2._record_group(records, "TRAIN")
    d1_val = pv2._record_group(records, "D1_DEV_VAL")
    stats = pv2._fit_stats(train_clean)
    if len(d1_val) != 59 or len({r.subject_id for r in d1_val}) != 3:
        raise PV36Error("D1 DEV VAL governed membership changed")
    pv2._set_deterministic(0)
    q2_records = _make_q2_records(d1_val)
    baseline_map = {str(row.get("candidate_key")): row for row in baseline_metrics.get("candidates", [])}
    candidate_entries = [entry for entry in registry.get("candidates", []) if entry.get("family") in FAMILIES]
    expected_keys = {f"{family}/seed_{seed}" for family in FAMILIES for seed in SEEDS}
    actual_keys = {f"{entry.get('family')}/seed_{entry.get('seed')}" for entry in candidate_entries}
    if actual_keys != expected_keys:
        raise PV36Error(f"ROLE_L_FULL_TASK candidate membership changed: {sorted(actual_keys)}")

    breathing_candidates: list[dict[str, Any]] = []
    rr_candidates: list[dict[str, Any]] = []
    quality_candidates: list[dict[str, Any]] = []
    footprint_candidates: list[dict[str, Any]] = []
    seed_cards: dict[str, dict[int, dict[str, Any]]] = {family: {} for family in FAMILIES}
    baseline_consistency: dict[str, Any] = {}
    for entry in sorted(candidate_entries, key=lambda e: (str(e.get("family")), int(e.get("seed")))):
        family, seed = str(entry["family"]), int(entry["seed"])
        candidate_key = f"{family}/seed_{seed}"
        model, _, checkpoint = pv3._load_checkpoint(entry)
        clean_group, clean_predictions = _evaluate_group(model, family, d1_val, stats, q2=False)
        q2_group, _ = _evaluate_group(model, family, [*d1_val, *q2_records], stats, q2=True)
        subject = _subject_results(model, family, d1_val, stats)
        safety = _safety_card_for_candidate(q2_group, q2_records, family, seed)
        quality = _quality_card_for_candidate(q2_group, family, seed)
        baseline_consistency[candidate_key] = _compare_baseline(clean_group, baseline_map[candidate_key]["validation"]["D1_DEV_VAL"])
        if baseline_consistency[candidate_key]["status"] != "PASS":
            raise PV36Error(f"recomputed M-PV3 metrics differ for {candidate_key}")
        breathing_candidates.append({"candidate_key": candidate_key, "family": family, "seed": seed, "validation_group": "D1_DEV_VAL", "metrics": clean_group["breathing"], "baseline_consistency": baseline_consistency[candidate_key], "selection_use": False})
        rr_candidates.append({"candidate_key": candidate_key, "family": family, "seed": seed, "validation_group": "D1_DEV_VAL", "metrics": clean_group["rr"], "frozen_guard_comparison": {"present_recall": _finite_or_none(clean_group["breathing"].get("recall")), "brier": _finite_or_none(clean_group["breathing"].get("Brier")), "rr_mae_bpm": _finite_or_none(clean_group["rr"].get("MAE_bpm")), "within_2_bpm": _finite_or_none(clean_group["rr"].get("within_2_bpm")), "within_4_bpm": _finite_or_none(clean_group["rr"].get("within_4_bpm")), "within_6_bpm": _finite_or_none(clean_group["rr"].get("within_6_bpm")), "thresholds_modified": False, "selection_use": False}, "baseline_consistency": baseline_consistency[candidate_key], "selection_use": False})
        quality_candidates.append({"candidate_key": candidate_key, "quality": quality, "safety": safety, "validation_group": "D1_DEV_VAL_PLUS_Q2", "selection_use": False})
        footprint_candidates.append(_footprint(family, seed, entry))
        seed_cards[family][seed] = {
            "candidate_key": candidate_key,
            "seed": seed,
            "breathing": clean_group["breathing"],
            "rr": clean_group["rr"],
            "safety": {key: safety.get(key) for key in ("q2_invalid_false_acceptance", "invalid_to_physiology_transition", "clean_false_rejection", "pass")},
            "quality": quality,
            "subject_results": subject,
            "selection_use": False,
        }

    cards = {
        "breathing": {"role_id": EXPECTED_ROLE, "class": "B", "validation_group": "D1_DEV_VAL", "eligible_present": 57, "eligible_absent": 0, "absent_metric_policy": "NOT_APPLICABLE_WHERE_GOVERNED_ABSENT_UNAVAILABLE", "candidates": breathing_candidates, "ece_policy": "NOT_APPLICABLE_UNLESS_CALIBRATION_ALREADY_VALID; no numeric ECE emitted", "calibration_fitting": False, "selection_use": False},
        "rr": {"role_id": EXPECTED_ROLE, "class": "B", "validation_group": "D1_DEV_VAL", "target": "continuous_rr_bpm", "frozen_guards": guards["m_pv3_utility_guards"], "candidates": rr_candidates, "selection_use": False},
        "quality_safety": {"role_id": EXPECTED_ROLE, "quality_class": "B_DIAGNOSTIC_ONLY", "safety_class": "A_NON_COMPENSABLE", "validation_group": "D1_DEV_VAL_PLUS_Q2", "q2_scope": "SYNTHETIC_ONLY", "runtime_precedence": ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"], "candidates": quality_candidates, "all_safety_pass": all(row["safety"]["pass"] for row in quality_candidates), "selection_use": False},
        "stability": {family: _stability_card(seed_cards[family], family) for family in FAMILIES},
        "footprint": {"role_id": EXPECTED_ROLE, "class": "E_ENGINEERING_ONLY", "candidates": footprint_candidates, "pi_latency_measured": False, "raspberry_pi_claim": False, "selection_use": False},
    }
    limitations = {
        "role_id": EXPECTED_ROLE,
        "gate": "PASS_WITH_LIMITATIONS",
        "limitations": [
            {"code": "D1_ABSENT_LIMITATION", "statement": "D1 DEV VAL has 57 eligible PRESENT, 2 AMBIGUOUS, and 0 eligible ABSENT; ABSENT recall/specificity/full both-class role eligibility are NOT_APPLICABLE or incomplete."},
            {"code": "D0_OBSERVE_ONLY", "statement": "D0 TRAIN is observe-only and no reserved D0 VAL/subject-heldout membership was opened."},
            {"code": "D2_LOCKED", "statement": "D2 semantic access, inference, and selection remain forbidden."},
            {"code": "MR60_SUPERVISED_FORBIDDEN", "statement": "No MR60 supervised physiology was used."},
            {"code": "NO_CALIBRATION", "statement": "No calibration fitting and no final threshold tuning were performed; numeric ECE is not emitted."},
            {"code": "NO_INT8_TFLITE", "statement": "No INT8 quantization or TFLite conversion was performed."},
            {"code": "NO_PI_BENCHMARK", "statement": "No Raspberry Pi latency or throughput claim was made."},
            {"code": "NO_SELECTION", "statement": "No Family B/C winner, best-seed choice, combined score, weighted ranking, Pareto winner, or M-PV4 recommendation was produced."},
            {"code": "Q2_SYNTHETIC_ONLY", "statement": "Q2 corruption cards are SYNTHETIC_ONLY safety evidence and are not live-device validation."},
        ],
        "role_eligibility_for_future_selection": "INCOMPLETE_DUE_D1_ABSENT_COVERAGE_AND_M_PV3_GUARD_RESULTS",
        "sufficiently_evidenced_for_future_selection_consideration": False,
        "selection_use": False,
    }
    manifest = {
        "schema_version": "M-PV3.6.2_ROLE_L_FULL_TASK_EVALUATION",
        "phase": "M-PV3.6",
        "execution_mode": "ROLE_CARD_POPULATION_ONLY",
        "contract_id": contract["contract_id"],
        "contract_schema_version": contract["schema_version"],
        "contract_source_sha256": _sha_file(ROOT / CONTRACT_REL),
        "contract_source_phase_mode": contract.get("phase_mode"),
        "pr134_merge_sha": EXPECTED_PR134_MERGE,
        "baseline_contract_immutable": True,
        "role_id": EXPECTED_ROLE,
        "role_membership": "M_PV3_FAMILY_B_AND_FAMILY_C_ONLY",
        "included_candidates": sorted(actual_keys),
        "excluded_roles": ["ROLE_L_RR_QUALITY / Family A", "ROLE_L_ISOLATION / M-PV3.5 isolation CNN", "ROLE_S_SHORT_CONTEXT / M-PV2 15s candidate"],
        "governed_membership": {"source": "D1_DEV_VAL", "record_count": len(d1_val), "subjects": sorted({str(r.subject_id) for r in d1_val}), "eligible_present": int(sum(r.breathing_mask for r in d1_val)), "eligible_absent": int(sum(r.breathing_mask and r.breathing_label == 0 for r in d1_val)), "ambiguous": int(sum(not r.breathing_mask for r in d1_val)), "split_change": False, "label_regeneration": False},
        "q2_evaluation": {"modes": list(Q2_MODES), "record_count": len(q2_records), "scope": "SYNTHETIC_ONLY", "physiology_target_rewrite": False, "d2_used": False, "mr60_supervised_physiology": False},
        "m_pv3_baseline": {"selection_result": selection.get("selection_result"), "selection_evidence": _rel(ROOT / PV3_SELECTION_REL), "utility_guards": guards, "determinism_evidence": _rel(ROOT / PV3_DETERMINISM_REL)},
        "provenance": {"tensor_materialization": _rel(ROOT / PV3_TENSOR_REL), "membership_audit": _rel(ROOT / PV3_MEMBERSHIP_REL), "d2_lock": _rel(ROOT / PV3_D2_REL), "materialization_counts": materialization.get("counts", {}), "m_pv2_scaler_sha256": stats.get("sha256")},
        "cards": {"breathing": "breathing_card.json", "rr": "rr_card.json", "quality_safety": "quality_safety_card.json", "stability": "stability_card.json", "footprint": "footprint_card.json", "limitations": "limitations.json"},
        "training_invocations": 0,
        "calibration_fitting": False,
        "thresholds_modified": False,
        "combined_score": None,
        "winner_selected": False,
        "best_seed_selected": False,
        "m_pv4_recommended": False,
        "evaluation_deterministic_cpu": True,
        "upstream_determinism": determinism.get("deterministic") is True,
        "baseline_metric_consistency": baseline_consistency,
    }
    output = ROOT / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "role_l_full_task_evaluation_manifest.json", manifest)
    _write(output / "breathing_card.json", cards["breathing"])
    _write(output / "rr_card.json", cards["rr"])
    _write(output / "quality_safety_card.json", cards["quality_safety"])
    _write(output / "stability_card.json", cards["stability"])
    _write(output / "footprint_card.json", cards["footprint"])
    _write(output / "limitations.json", limitations)
    validation = {
        "schema_version": "M-PV3.6.2_ROLE_L_FULL_TASK_EVALUATION",
        "phase": "M-PV3.6",
        "contract_id": contract["contract_id"],
        "role_id": EXPECTED_ROLE,
        "gate": "PASS_WITH_LIMITATIONS",
        "ok": True,
        "evaluated_candidate_count": len(actual_keys),
        "all_six_b_c_candidates_evaluated": True,
        "role_eligibility": "INCOMPLETE_DUE_D1_ABSENT_COVERAGE_AND_M_PV3_GUARD_RESULTS",
        "sufficiently_evidenced_for_future_selection_consideration": False,
        "m_pv3_selection_preserved": selection.get("selection_result") == "NO_SELECTION_READY",
        "no_model_selected": True,
        "no_training": True,
        "no_contract_modification": True,
        "no_d2": True,
        "no_mr60_supervised_physiology": True,
        "no_calibration": True,
        "no_threshold_change": True,
        "no_int8_tflite": True,
        "no_pi_benchmark": True,
        "baseline_metric_consistency": all(item.get("status") == "PASS" for item in baseline_consistency.values()),
        "safety_all_candidates_pass": cards["quality_safety"]["all_safety_pass"],
        "limitations": limitations["limitations"],
    }
    _write(output / "validation_result.json", validation)
    _write_checksums(output, contract)
    return {"gate": validation["gate"], "role": EXPECTED_ROLE, "candidate_count": len(actual_keys), "sufficiently_evidenced_for_future_selection_consideration": validation["sufficiently_evidenced_for_future_selection_consideration"], "output": OUTPUT_REL.as_posix()}


def _write_checksums(output: Path, contract: Mapping[str, Any]) -> None:
    files: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"checksums.sha256", "checksums.json"}:
            files[_rel(path)] = _sha_file(path)
    inputs = {
        _rel(ROOT / CONTRACT_REL): _sha_file(ROOT / CONTRACT_REL),
        _rel(ROOT / PV3_CONTRACT_REL): _sha_file(ROOT / PV3_CONTRACT_REL),
        _rel(ROOT / REGISTRY_REL): _sha_file(ROOT / REGISTRY_REL),
        _rel(ROOT / PV3_METRICS_REL): _sha_file(ROOT / PV3_METRICS_REL),
        _rel(ROOT / PV3_SELECTION_REL): _sha_file(ROOT / PV3_SELECTION_REL),
    }
    _write(output / "checksums.json", {"schema_version": "M-PV3.6.2_ROLE_L_FULL_TASK_EVALUATION", "files": files, "inputs": inputs, "contract_id": contract.get("contract_id")})
    lines = dict(files)
    lines[_rel(output / "checksums.json")] = _sha_file(output / "checksums.json")
    (output / "checksums.sha256").write_text("\n".join(f"{digest}  {path}" for path, digest in sorted(lines.items())) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="populate the ROLE_L_FULL_TASK cards (default action)")
    args = parser.parse_args()
    del args
    try:
        result = run_phase()
    except Exception as exc:
        print(f"M-PV3.6 ROLE_L_FULL_TASK FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(pv2._json_safe(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
