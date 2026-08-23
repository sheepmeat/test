#!/usr/bin/env python3
"""Focused fail-closed validator for the M-PV2 15-second candidate lane."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "datasets/mmwave/manifests/M-PV2_short_context_15s_candidate"
MODEL_ROOT = ROOT / "models/mmwave/m_pv2_short_context_15s_candidate"
BASELINE_ROOT = ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training"
BASELINE_MODEL_ROOT = ROOT / "models/mmwave/m_pv2"

REQUIRED = (
    "input_contract.json",
    "target_alignment.json",
    "dataset_audit.json",
    "training_config.json",
    "model_card.json",
    "evaluation_result.json",
    "limitations.json",
    "checksums.json",
)

IDENTITY = "MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(checks: List[Dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _walk_strings(value: Any) -> List[str]:
    found: List[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item))
    return found


def _protected_current_hashes() -> Dict[str, str]:
    paths: List[Path] = [
        BASELINE_ROOT / "breathing_metrics.json",
        BASELINE_ROOT / "candidate_registry.json",
        BASELINE_ROOT / "tensor_materialization_audit.json",
        BASELINE_ROOT / "scaler_statistics.json",
        BASELINE_ROOT / "validation_result.json",
    ]
    paths.extend(
        path for path in BASELINE_MODEL_ROOT.rglob("*") if path.is_file()
    )
    return {
        path.relative_to(ROOT).as_posix(): sha(path)
        for path in sorted(paths)
        if path.is_file()
    }


def validate() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    failures: List[str] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    check(checks, "required_outputs_present", not missing, missing)
    if missing:
        return {
            "schema_version": "M-PV2-SHORT-15S.1",
            "identity": IDENTITY,
            "gate": "BLOCKED",
            "ok": False,
            "failed_checks": ["required_outputs_present"],
            "checks": checks,
        }

    input_contract = read(OUT / "input_contract.json")
    target_alignment = read(OUT / "target_alignment.json")
    dataset = read(OUT / "dataset_audit.json")
    training = read(OUT / "training_config.json")
    card = read(OUT / "model_card.json")
    evaluation = read(OUT / "evaluation_result.json")
    limitations = read(OUT / "limitations.json")
    checksums = read(OUT / "checksums.json")

    check(checks, "identity_consistent", all(
        payload.get("identity") == IDENTITY
        for payload in (input_contract, dataset, training, card)
    ) and evaluation.get("candidate_identity") == IDENTITY, {
        "input": input_contract.get("identity"),
        "dataset": dataset.get("identity"),
        "training": training.get("identity"),
        "model_card": card.get("identity"),
        "evaluation": evaluation.get("candidate_identity"),
    })
    check(checks, "short_input_shape", input_contract.get("context") == {
        "duration_s": 15,
        "interval": "[t-15s,t]",
        "ordering": "OLDEST_TO_NEWEST",
        "samples": 150,
        "sampling_rate_hz": 10,
        "shape": "[B,150,1]",
        "target_end_sample_exclusive_in_short_context": 150,
        "target_interval": "[t-5s,t]",
        "target_start_sample_in_short_context": 100,
    }, input_contract.get("context"))
    check(checks, "causal_rules", input_contract.get("causal_rules") == {
        "context_end_equals_target_end": True,
        "future_samples_forbidden": True,
        "internal_event_position_forbidden": True,
        "random_target_alignment_forbidden": True,
    }, input_contract.get("causal_rules"))
    task = input_contract.get("task_contract", {})
    check(checks, "target_state_contract", task.get("target_states") == [
        "PRESENT", "ABSENT", "AMBIGUOUS", "TARGET_UNAVAILABLE"
    ] and task.get("rr_primary_target") is False
    and task.get("temporal_hold_training") is False, {
        "target_states": task.get("target_states"),
        "rr_primary_target": task.get("rr_primary_target"),
        "temporal_hold_training": task.get("temporal_hold_training"),
    })
    check(checks, "quality_order_and_fail_closed", input_contract.get("quality_order") == [
        "presence", "input_availability", "breathing_evidence"
    ] and input_contract.get("invalid_input_must_not_become") == [
        "PRESENT", "ABSENT", "APNEA"
    ], {
        "quality_order": input_contract.get("quality_order"),
        "invalid_input_must_not_become": input_contract.get("invalid_input_must_not_become"),
    })
    check(checks, "target_alignment_is_fixed_and_causal", target_alignment.get(
        "alignment_validation"
    ) == {
        "context_end_equals_target_end": True,
        "fixed_target_start_sample": True,
        "future_samples": False,
        "internal_event_position": False,
        "random_alignment": False,
        "row_count": 562,
    }, target_alignment.get("alignment_validation"))
    label_semantics = target_alignment.get("label_semantics", {})
    check(checks, "label_semantics_not_rewritten", all(
        label_semantics.get(key) is False
        for key in (
            "apnea_protocol_to_label",
            "breath_hold_name_to_label",
            "radar_amplitude_to_label",
        )
    ) and label_semantics.get("ambiguous_learning_mask") == 0, label_semantics)
    excluded = target_alignment.get("excluded_task_alignment", {})
    check(checks, "rr_and_temporal_hold_excluded", excluded.get("rr", {}).get(
        "trained"
    ) is False and excluded.get("rr", {}).get("evaluated") is False
    and excluded.get("temporal_hold", {}).get("status") == "NOT_TRAINED", excluded)

    membership = dataset.get("source_membership", {})
    check(checks, "governed_membership_counts", membership.get("D0", {}).get(
        "context_count"
    ) == 318 and membership.get("D0", {}).get("subject_count") == 66
    and membership.get("D0", {}).get("selected_split") == "TRAIN"
    and membership.get("D1", {}).get("context_count") == 244
    and membership.get("D1", {}).get("train_context_count") == 185
    and membership.get("D1", {}).get("val_context_count") == 59
    and membership.get("D1", {}).get("train_subject_count") == 8
    and membership.get("D1", {}).get("val_subject_count") == 3
    and membership.get("D1", {}).get("subject_intersection_count") == 0
    and membership.get("D1", {}).get("recording_intersection_count") == 0
    and membership.get("total_model_ready_unique") == 562
    and membership.get("duplicate_model_input_count") == 0, membership)
    d0 = membership.get("D0", {})
    check(checks, "d0_val_heldout_mn6_excluded", d0.get("VAL_rows_selected") == 0
    and d0.get("D0_SUBJECT_HELDOUT_rows_selected") == 0
    and d0.get("M_N6_excluded_subjects_selected") == 0
    and d0.get("selected_subjects_outside_frozen_train") == 0, d0)
    supervision = dataset.get("supervision", {})
    check(checks, "ambiguous_provenance_only", supervision.get(
        "ambiguous_rows_retained_for_provenance"
    ) == 48 and supervision.get("ambiguous_rows_used_for_learning") == 0
    and supervision.get("target_unavailable_rows_used_for_learning") == 0, supervision)
    provenance = dataset.get("provenance_requirements", {})
    check(checks, "complete_row_provenance", provenance.get(
        "row_lineage_count"
    ) == 562 and provenance.get("required_fields_present") is True
    and len(dataset.get("records", [])) == 562, {
        "row_lineage_count": provenance.get("row_lineage_count"),
        "required_fields_present": provenance.get("required_fields_present"),
        "records": len(dataset.get("records", [])),
    })
    labels = dataset.get("label_lineage_audit", {})
    check(checks, "reference_label_lineage", labels.get(
        "label_source"
    ) == "M-PV1.breathing_reference_state"
    and labels.get("reference_semantics_preserved") is True
    and labels.get("apnea_protocol_strings_used") is False
    and labels.get("breath_hold_names_used") is False
    and labels.get("low_amplitude_as_label_used") is False
    and labels.get("radar_amplitude_as_label_used") is False
    and labels.get("model_output_as_label_used") is False, labels)
    leakage = dataset.get("leakage_audit", {})
    check(checks, "leakage_and_forbidden_sources", leakage.get(
        "future_samples_used"
    ) is False and leakage.get("random_target_alignment") is False
    and leakage.get("internal_event_position_used") is False
    and leakage.get("d0_val_or_heldout_used") is False
    and leakage.get("d1_dev_val_used_for_training") is False
    and leakage.get("d2_accessed") is False
    and leakage.get("mr60_supervised_physiology_used") is False
    and leakage.get("d2_rows") == 0 and leakage.get("mr60_rows") == 0, leakage)

    check(checks, "training_is_train_only_and_bounded", training.get(
        "frozen_before_training"
    ) is True and training.get("seeds") == [11, 23, 47]
    and training.get("primary_run_count") == 3
    and training.get("preprocessing", {}).get("fit_scope") == [
        "D0:TRAIN", "D1:D1_DEV_TRAIN"
    ] and training.get("preprocessing", {}).get("validation_statistics_used") is False
    and training.get("preprocessing", {}).get("d0_val_used") is False
    and training.get("preprocessing", {}).get("d2_used") is False
    and training.get("preprocessing", {}).get("mr60_supervised_labels_used") is False
    and training.get("quality", {}).get("synthetic_corruption", {}).get(
        "used_for_physiology_labels"
    ) is False
    and training.get("quality", {}).get("synthetic_corruption", {}).get(
        "used_for_threshold_tuning"
    ) is False, training.get("preprocessing"))

    model = card.get("architecture", {})
    checkpoints = card.get("checkpoints", [])
    checkpoint_paths = [str(item.get("path")) for item in checkpoints]
    check(checks, "edge_model_footprint_recorded", model.get(
        "input_shape"
    ) == "[B,150,1]" and model.get("parameter_count") == 2297
    and model.get("flops_estimate", {}).get("estimated_flops") == 90608
    and len(checkpoints) == 3, {
        "architecture": model,
        "checkpoint_count": len(checkpoints),
    })
    checkpoint_ok = True
    checkpoint_details: List[str] = []
    for item in checkpoints:
        path_text = str(item.get("path", ""))
        path = ROOT / path_text
        if not path.is_file() or not path_text.startswith(
            "models/mmwave/m_pv2_short_context_15s_candidate/"
        ):
            checkpoint_ok = False
            checkpoint_details.append(path_text)
        elif sha(path) != item.get("sha256"):
            checkpoint_ok = False
            checkpoint_details.append(f"checksum:{path_text}")
    check(checks, "candidate_checkpoints_present_and_hashed", checkpoint_ok, checkpoint_details)
    check(checks, "model_not_selected_or_quantized", card.get("status") == (
        "CANDIDATE_ONLY_NOT_SELECTED"
    ) and card.get("selection", {}).get("final_selection") is False
    and card.get("selection", {}).get("selected_float_model") is False
    and card.get("quantization") == "NOT_GENERATED"
    and card.get("tflite") == "NOT_GENERATED", {
        "status": card.get("status"),
        "selection": card.get("selection"),
        "quantization": card.get("quantization"),
        "tflite": card.get("tflite"),
    })

    short = evaluation.get("breathing_evidence", {}).get(
        "short_context_metrics", {}
    )
    per_seed = short.get("per_seed", {})
    required_seed_keys = {"11", "23", "47"}
    check(checks, "three_seed_metrics_present", set(per_seed) == required_seed_keys, sorted(per_seed))
    metric_shape_ok = True
    metric_details: List[str] = []
    for seed in sorted(required_seed_keys):
        groups = per_seed.get(seed, {}).get("groups", {})
        d0_metrics = groups.get("D0_TRAIN_OBSERVE", {})
        d1_metrics = groups.get("D1_DEV_VAL", {})
        if (
            d0_metrics.get("supervision_eligible_count") != 278
            or d0_metrics.get("present_count") != 162
            or d0_metrics.get("absent_count") != 116
            or d1_metrics.get("supervision_eligible_count") != 57
            or d1_metrics.get("present_count") != 57
            or d1_metrics.get("absent_count") != 0
            or d1_metrics.get("absent_recall") is not None
            or d1_metrics.get("macro_f1") is not None
            or d0_metrics.get("macro_f1") is None
        ):
            metric_shape_ok = False
            metric_details.append(seed)
    check(checks, "required_breathing_metrics_and_absent_limit", metric_shape_ok, metric_details)
    check(checks, "no_selection_result", evaluation.get("gate") == "PASS_WITH_LIMITATIONS"
    and evaluation.get("status") == "EVIDENCE_PRODUCED_NO_SELECTION"
    and evaluation.get("selection", {}).get("performed") is False
    and evaluation.get("selection", {}).get("final_selection") is False
    and evaluation.get("selection", {}).get("selected_model") is None, evaluation.get("selection"))

    availability = evaluation.get("availability", {})
    availability_ok = True
    availability_details: List[str] = []
    for side, expected_context, expected_recovery in (
        ("short_context", 15, 15.0),
        ("baseline_30s_context", 30, 30.0),
    ):
        for mode in ("gap", "freeze", "stale_source"):
            item = availability.get(side, {}).get(mode, {})
            if (
                item.get("context_requirement_s") != expected_context
                or item.get("first_valid_decision_time_s") != float(expected_context)
                or item.get("recovery_time_after_event_s") != expected_recovery
                or item.get("synthetic_quality_only") is not True
                or item.get("physiology_targets_created_or_rewritten") is not False
                or item.get("invalid_mapping", {}).get("model_invocation") != "BLOCKED"
                or item.get("invalid_mapping", {}).get("PRESENT_or_ABSENT_emitted") is not False
            ):
                availability_ok = False
                availability_details.append(f"{side}:{mode}")
    check(checks, "availability_and_recovery_evidence", availability_ok, availability_details)
    check(checks, "rr_and_hold_not_evaluated", evaluation.get("excluded_tasks", {}).get(
        "rr", {}
    ).get("trained") is False and evaluation.get("excluded_tasks", {}).get(
        "rr", {}
    ).get("evaluated") is False and evaluation.get("excluded_tasks", {}).get(
        "temporal_hold", {}
    ).get("trained") is False, evaluation.get("excluded_tasks"))
    safety = evaluation.get("safety_checks", {})
    check(checks, "evaluation_safety_flags", all(
        safety.get(key) is False
        for key in (
            "d2_accessed",
            "mr60_supervised_physiology_used",
            "future_leakage",
            "radar_amplitude_label_generation",
            "existing_30s_artifacts_modified",
            "q2_invalid_can_emit_physiology",
        )
    ), safety)
    check(checks, "limitations_explicit", limitations.get("gate") == "PASS_WITH_LIMITATIONS"
    and bool(limitations.get("limitations"))
    and "15 seconds replaces the existing 30-second M-PV2 contract"
    in limitations.get("claims_not_permitted", []), limitations)

    checksum_failures: List[str] = []
    for relative, expected in checksums.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha(path) != expected:
            checksum_failures.append(relative)
    check(checks, "checksums_cover_generated_files", not checksum_failures, checksum_failures)
    protected_before = dataset.get("protected_30s_artifact_hashes_before_run", {})
    protected_now = _protected_current_hashes()
    check(checks, "protected_30s_artifacts_unchanged", protected_now == protected_before, {
        "before_count": len(protected_before),
        "current_count": len(protected_now),
        "equal": protected_now == protected_before,
    })

    forbidden_strings: List[str] = []
    for name in REQUIRED[:-1]:
        payload = read(OUT / name)
        for value in _walk_strings(payload):
            if (
                value.startswith("/")
                or value.startswith("file://")
                or value.startswith("~/")
                or "/Users/" in value
                or "SafeNest_V4_" in value
                or "SafeNest_V5_" in value
                or "SafeNest_V6" in value
                or value.startswith("archive/")
            ):
                forbidden_strings.append(f"{name}:{value}")
    check(checks, "repository_relative_active_paths", not forbidden_strings, forbidden_strings[:10])

    for item in checks:
        if not item["ok"]:
            failures.append(item["name"])
    result = {
        "schema_version": "M-PV2-SHORT-15S.1",
        "identity": IDENTITY,
        "phase": "M-PV2_SHORT_CONTEXT_15S",
        "gate": "PASS_WITH_LIMITATIONS" if not failures else "BLOCKED",
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
        "selection": False,
        "d2_accessed": False,
        "mr60_supervised_physiology_used": False,
        "expected_result": "SHORT_CONTEXT_CANDIDATE_RESULT",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation_result.json")
    args = parser.parse_args()
    try:
        result = validate()
        if args.write:
            (OUT / "validation_result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps({
            "gate": result["gate"],
            "ok": result["ok"],
            "failed_checks": result["failed_checks"],
        }, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 2
    except Exception as exc:
        print(json.dumps({"gate": "BLOCKED", "ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
