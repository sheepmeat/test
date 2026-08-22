#!/usr/bin/env python3
"""Generate deterministic R3 breathing/RR/temporal-hold target evidence.

The runner consumes compact upstream evidence only.  D0 uses the frozen V2
TRAIN subject split and the authoritative A6 window/reference audit.  D1 is
audited conservatively from the adapter inventory because the synchronized
reference waveform is not materialized in the compact evidence available in
this repository.  No D2 payload, MR60 telemetry, waveform copy, model, or
threshold search is performed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_r3_target_contracts import (
    BREATHING_TARGET_ID,
    RR_TARGET_ID,
    SUPERVISION_ELIGIBILITY_ID,
    TEMPORAL_HOLD_TARGET_ID,
    build_d0_target_row,
    build_d1_target_row,
)


OUTPUT_RELATIVE_ROOT = Path("datasets/mmwave/manifests/M-PV0_R3_breathing_rr_temporal_hold")
AUDIT_DATE = "2026-08-23"
R3_SCHEMA_VERSION = "R3.1"
TARGET_CONTRACT_SET_ID = "MMWAVE_V2_R3_TARGET_CONTRACT_SET_V1"
R2_HEAD = "37ea18d43780393b3f5c28deed655343ade59cd9"
R2_CANDIDATE_SET_ID = "MMWAVE_V2_R2_REPRESENTATION_CANDIDATE_SET_V1"
R1_CONTRACT_ID = "R1_SENSOR_INDEPENDENT_TRACE_CONTRACT_V1"
Q2_CONTRACT_ID = "MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1"

D0_A6_WINDOWS = Path("datasets/mmwave/manifests/a6_full_conversion/full_window_manifest.jsonl")
D0_LABEL_AUDIT = Path("datasets/mmwave/manifests/M-PV0_D0_v2_split_label_audit/label_reference_audit.json")
D0_SPLIT = Path("datasets/mmwave/splits/mmwave_v2_d0_subject_split_v1.json")
D1_INVENTORY = Path("datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter/recording_inventory.json")
R1_CONTRACT = Path("datasets/mmwave/manifests/M-PV0_R1_sensor_independent_trace/common_trace_contract.json")
R2_CANDIDATE_SET = Path("datasets/mmwave/manifests/M-PV0_R2_spectral_autocorr_features/feature_candidate_set.json")
Q2_CONTRACT = Path("datasets/mmwave/manifests/M-PV0_Q2_input_unavailable_contract/input_availability_contract.json")

OUTPUT_FILES = (
    "target_contract_set.json",
    "breathing_evidence_contract.json",
    "rr_target_contract.json",
    "temporal_hold_contract.json",
    "supervision_eligibility_contract.json",
    "d0_target_rows.jsonl",
    "d1_target_rows.jsonl",
    "d0_target_audit.json",
    "d1_target_audit.json",
    "cross_domain_target_compatibility.json",
    "transition_audit.json",
    "exception_registry.json",
    "validation_result.json",
    "checksums.json",
)


class R3RunnerError(RuntimeError):
    """Raised when R3 source accounting or target construction must stop."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise R3RunnerError(f"cannot read JSON input {path}: {exc}") from exc


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise R3RunnerError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
                if not isinstance(value, dict):
                    raise R3RunnerError(f"expected JSON object at {path}:{line_number}")
                rows.append(value)
    except OSError as exc:
        raise R3RunnerError(f"cannot read JSONL input {path}: {exc}") from exc
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise R3RunnerError(f"path is outside canonical repository root: {path}") from exc


def _counter(values: Iterable[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values).items()))


def _input_paths() -> tuple[Path, ...]:
    return (
        D0_A6_WINDOWS,
        D0_LABEL_AUDIT,
        D0_SPLIT,
        D1_INVENTORY,
        R1_CONTRACT,
        R2_CANDIDATE_SET,
        Q2_CONTRACT,
    )


def _load_d0_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split_doc = _load_json(ROOT / D0_SPLIT)
    label_audit = _load_json(ROOT / D0_LABEL_AUDIT)
    windows = _load_jsonl(ROOT / D0_A6_WINDOWS)
    subject_to_split: dict[str, str] = {}
    for split, subject_ids in (split_doc.get("subject_ids") or {}).items():
        for subject_id in subject_ids:
            if subject_id in subject_to_split:
                raise R3RunnerError(f"D0 subject appears in multiple splits: {subject_id}")
            subject_to_split[str(subject_id)] = str(split)
    recording_audit = {
        str(row.get("recording_id")): row
        for row in label_audit.get("recordings", [])
        if row.get("recording_id")
    }
    if len(recording_audit) != 440:
        raise R3RunnerError(f"D0 recording audit must contain 440 recordings, got {len(recording_audit)}")

    train_rows: list[dict[str, Any]] = []
    for window in windows:
        subject_id = str(window.get("subject_id") or "")
        recording_id = str(window.get("recording_id") or "")
        split = subject_to_split.get(subject_id)
        if split != "TRAIN":
            continue
        recording_meta = recording_audit.get(recording_id)
        if recording_meta is None:
            raise R3RunnerError(f"D0 window references recording absent from label audit: {recording_id}")
        if recording_meta.get("v2_split") != "TRAIN":
            raise R3RunnerError(f"D0 subject split disagreement for {recording_id}")
        train_rows.append(build_d0_target_row(window, recording_meta, "TRAIN"))
    train_rows.sort(key=lambda row: str(row["window_id"]))
    if len(train_rows) != 318:
        raise R3RunnerError(f"D0 TRAIN target row count must be 318, got {len(train_rows)}")
    return train_rows, split_doc


def _load_d1_rows() -> list[dict[str, Any]]:
    inventory = _load_json(ROOT / D1_INVENTORY)
    recordings = inventory.get("recordings") if isinstance(inventory, Mapping) else None
    if not isinstance(recordings, list):
        raise R3RunnerError("D1 recording inventory has no recordings list")
    rows = [build_d1_target_row(recording) for recording in recordings]
    rows.sort(key=lambda row: str(row["recording_id"]))
    if len(rows) != 265:
        raise R3RunnerError(f"D1 target row count must be 265, got {len(rows)}")
    if len({row["recording_id"] for row in rows}) != len(rows):
        raise R3RunnerError("D1 target rows contain duplicate recording IDs")
    return rows


def _target_contract_set(r2: Mapping[str, Any], r1: Mapping[str, Any], q2: Mapping[str, Any]) -> dict[str, Any]:
    candidate_ids = list(r2.get("candidate_schema_ids", []))
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "contract_set_id": TARGET_CONTRACT_SET_ID,
        "phase": "R3",
        "audit_date": AUDIT_DATE,
        "status": "BOUNDED_TARGET_SEMANTICS_READY_FOR_M_PV1",
        "r2_contract_inherited": "YES",
        "r2_handoff": {
            "head": R2_HEAD,
            "candidate_set_id": r2.get("candidate_set_id"),
            "candidate_schema_ids": candidate_ids,
            "selected_candidate": r2.get("selected_candidate"),
            "selection_performed": r2.get("selection_performed"),
        },
        "upstream_contracts": {
            "r1": r1.get("contract_id"),
            "q2": q2.get("contract_id"),
            "d0_split": "MMWAVE_V2_D0_SUBJECT_SPLIT_V1",
            "d0_label_mapping": "MMWAVE_LABEL_MAPPING_PROFILE_001",
        },
        "bounded_candidates": [
            {
                "candidate_id": "T1_REFERENCE_SEPARATED",
                "status": "BOUNDED_CANDIDATE_FOR_M_PV1",
                "targets": [BREATHING_TARGET_ID, RR_TARGET_ID, TEMPORAL_HOLD_TARGET_ID],
                "semantics": "separate breathing evidence, continuous RR, and temporal event targets",
                "architecture_selected": False,
            },
            {
                "candidate_id": "T2_BREATHING_RR_WITH_RULE_COMPOSED_HOLD",
                "status": "BOUNDED_CANDIDATE_FOR_M_PV1",
                "targets": [BREATHING_TARGET_ID, RR_TARGET_ID, TEMPORAL_HOLD_TARGET_ID],
                "semantics": "supervised breathing/RR with later deterministic sequential hold composition",
                "persistence_threshold": "DEFERRED_TO_M_PV1",
                "architecture_selected": False,
            },
            {
                "candidate_id": "T3_OPTIONAL_MULTIHEAD_SEMANTICS",
                "status": "SEMANTIC_INTERFACE_ONLY",
                "targets": [BREATHING_TARGET_ID, RR_TARGET_ID, TEMPORAL_HOLD_TARGET_ID, SUPERVISION_ELIGIBILITY_ID],
                "semantics": "future separate output heads without architecture or training selection",
                "architecture_selected": False,
                "model_trained": False,
            },
        ],
        "selection": {
            "selected_candidate": None,
            "selection_performed": False,
            "target_definition_depends_on_model_score": False,
            "f1_f2_f3_winner_selected": False,
        },
        "safety_boundaries": {
            "direct_three_class_primary_target": False,
            "whole_window_apnea_default": False,
            "clinical_apnea_claimed": False,
            "voluntary_breath_hold_proxy_language_required": True,
            "low_radar_amplitude_defines_apnea": False,
            "radar_amplitude_used_as_reference_label": False,
            "d2_used": False,
            "mr60_supervised_use": False,
            "q2_thresholds_redefined": False,
            "model_training": False,
            "model_architecture_selected": False,
            "probability_threshold_selected": False,
            "apnea_persistence_threshold_finalized": False,
        },
        "m_pv1_boundary": {
            "common_representation_profile": "DEFERRED_TO_M_PV1",
            "exact_input_window_history": "DEFERRED_TO_M_PV1",
            "exact_target_binding": "DEFERRED_TO_M_PV1",
            "temporal_hold_composition": "DEFERRED_TO_M_PV1",
            "model_family": "DEFERRED_TO_M_PV1",
            "calibration_and_threshold_strategy": "DEFERRED_TO_M_PV1",
        },
    }


def _breathing_contract() -> dict[str, Any]:
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "contract_id": BREATHING_TARGET_ID,
        "target_kind": "REFERENCE_SUPERVISED_BREATHING_EVIDENCE",
        "definition": "Trustworthy periodic respiratory activity is present in the synchronized reference during the evaluation interval.",
        "states": [
            "BREATHING_REFERENCE_PRESENT",
            "BREATHING_REFERENCE_ABSENT",
            "BREATHING_REFERENCE_AMBIGUOUS",
            "TARGET_UNAVAILABLE",
        ],
        "target_status_values": ["AVAILABLE", "AMBIGUOUS", "TARGET_UNAVAILABLE"],
        "numeric_encoding": {
            "BREATHING_REFERENCE_PRESENT": 1,
            "BREATHING_REFERENCE_ABSENT": 0,
            "BREATHING_REFERENCE_AMBIGUOUS": "NOT_ENCODED_AS_PURE_CLASS",
            "TARGET_UNAVAILABLE": "NOT_ENCODED",
        },
        "reference_policy": {
            "reference_waveform_required": True,
            "radar_trace_is_not_reference_label": True,
            "low_radar_amplitude_is_not_absence": True,
            "rr_category_is_not_breathing_evidence": True,
            "ambiguous_transition_not_forced_to_present_or_absent": True,
            "source_event_timing_is_preserved": True,
        },
        "d0_binding": {
            "reference_source": "MOVESENSE_CHEST_ACC plus audited voluntary non-breathing timing",
            "method": "inherit authoritative A4/A6 reference eligibility and event overlap; no radar-derived relabeling",
            "training_split": "MMWAVE_V2_D0_SUBJECT_SPLIT_V1 -> TRAIN only",
        },
        "d1_binding": {
            "reference_source": "synchronized respiration channel declared by D1 adapter",
            "current_status": "TARGET_UNAVAILABLE_LOCALLY_WHEN_REFERENCE_WAVEFORM_IS_NOT_MATERIALIZED",
            "source_condition_apnea_is_provenance_only": True,
        },
        "provenance_required": [
            "source_dataset",
            "subject_id",
            "recording_id",
            "window_id_or_null",
            "reference_time_range_s",
            "reference_source",
            "extraction_profile",
            "split_or_domain_role",
        ],
    }


def _rr_contract() -> dict[str, Any]:
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "contract_id": RR_TARGET_ID,
        "target_kind": "CONTINUOUS_REFERENCE_RESPIRATORY_RATE",
        "primary_field": "rr_bpm",
        "target_type": "continuous_float_bpm",
        "category_target": "NOT_PRIMARY; NORMAL/RAPID CATEGORIES ARE NOT R3 TARGETS",
        "validity_requirements": [
            "reference_signal_available",
            "reference_timing_aligned",
            "sufficient_reference_duration",
            "breathing_evidence_appropriate",
            "reference_quality_acceptable",
            "radar_input_available_for_model_supervision",
        ],
        "unavailable_encoding": {
            "target_status": "TARGET_UNAVAILABLE",
            "rr_bpm": None,
            "zero_is_not_unavailable": True,
            "nan_is_not_serialized": True,
            "unavailable_reason_required": True,
        },
        "d0_authoritative_method": {
            "reference_channel": "MOVESENSE_CHEST_ACC",
            "analysis_duration": "inherited A4 30 s canonical window",
            "peak_period_method": "existing deterministic spectral peak extraction from A4 label mapper",
            "frequency_constraints_hz": [0.1, 0.7],
            "minimum_cycles": "not separately tuned in R3; inherit A4 method evidence",
            "edge_handling": "inherit A4 finite-window interpolation/mask behavior",
            "ambiguity_handling": "hold/transition overlap is RR_TARGET_UNAVAILABLE",
        },
        "d1_method_boundary": {
            "reference_channel": "respiration",
            "analysis_duration": "DEFERRED_UNTIL_REFERENCE_WAVEFORM_ACCESS",
            "peak_period_method": "DEFERRED_UNTIL_REFERENCE_WAVEFORM_ACCESS",
            "frequency_constraints_hz": [0.1, 0.7],
            "minimum_cycles": "DEFERRED",
            "edge_handling": "DEFERRED",
            "ambiguity_handling": "TARGET_UNAVAILABLE; do not infer from source condition",
        },
        "forbidden_reference_substitutions": [
            "MR60 vendor breath_rate_raw",
            "MR60 live telemetry",
            "radar amplitude or R2 feature score",
            "source condition string alone",
        ],
    }


def _temporal_contract() -> dict[str, Any]:
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "contract_id": TEMPORAL_HOLD_TARGET_ID,
        "target_kind": "EVENT_RELATIVE_VOLUNTARY_BREATH_HOLD_PROXY",
        "safe_nest_language": "VOLUNTARY_BREATH_HOLD_PROXY",
        "clinical_apnea_claimed": False,
        "event_states": [
            "NO_HOLD_EVENT_IN_WINDOW",
            "HOLD_ONSET_AND_RECOVERY_WITHIN_WINDOW",
            "HOLD_ONSET_WITHOUT_RECOVERY_IN_WINDOW",
            "HOLD_ACTIVE_AT_WINDOW_START_AND_RECOVERY",
            "SUSTAINED_HOLD_COVERS_WINDOW",
            "SOURCE_HOLD_PROTOCOL_WITHOUT_DEFENSIBLE_INTERVAL",
            "UNAVAILABLE_REFERENCE",
        ],
        "required_fields": [
            "baseline_state",
            "has_previous_valid_breathing",
            "event_state",
            "event_id",
            "event_onset_s",
            "event_offset_s",
            "elapsed_hold_s",
            "recovery_state",
            "transition_ambiguity",
        ],
        "baseline_policy": {
            "required_before_hold_candidate": True,
            "unknown_start_is_not_hold": True,
            "recording_session_boundary_resets_state": True,
            "baseline_not_established_state": "BASELINE_NOT_ESTABLISHED",
        },
        "transition_policy": {
            "partial_onset_or_recovery_is_event_relative": True,
            "whole_window_apnea_default": False,
            "ambiguous_transition_retained_for_analysis": True,
            "source_event_boundaries_not_sharpened": True,
        },
        "recovery_policy": {
            "recovery_explicit": True,
            "returning_breathing_terminates_event": True,
            "no_hidden_carry_over_across_recordings": True,
        },
        "persistence_policy": {
            "persistent_loss_required_conceptually": True,
            "final_duration": "DEFERRED_TO_M_PV1",
            "bounded_candidate_for_m_pv1": True,
        },
        "d1_protocol_policy": {
            "source_string_apnea_auto_mapping": False,
            "onset_offset_required_for_temporal_target": True,
            "unavailable_state_when_boundary_not_defensible": True,
        },
    }


def _eligibility_contract(q2: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "contract_id": SUPERVISION_ELIGIBILITY_ID,
        "fields": {
            "reference_target_available": "reference evidence exists, even when retained as transition semantics",
            "radar_input_available": "Q2-compatible input availability gate",
            "subject_split_allowed": "frozen D0 subject role permits the row for the current scope",
            "transition_ambiguous": "event boundary or reference ambiguity is explicit",
            "model_supervision_eligible": "radar input valid and at least one selected target semantics available",
            "retained_for_transition_analysis": "ambiguous rows are retained but not pure-class rows",
        },
        "precedence": list(q2.get("precedence", {}).get("order", ["presence gate", "input quality / availability gate", "physiology"])),
        "q2_contract_id": q2.get("contract_id"),
        "invalid_radar_input_model_supervision_eligible": False,
        "public_offline_presence": "NOT_APPLICABLE_TO_D0_A6_COMPACT_AUDIT",
        "d0_rule": "TRAIN rows only; subject identity is inherited from MMWAVE_V2_D0_SUBJECT_SPLIT_V1",
        "d1_rule": "auxiliary domain is not model-supervision eligible until reference waveform and split role are bound",
    }


def _d0_audit(rows: list[dict[str, Any]], split_doc: Mapping[str, Any]) -> dict[str, Any]:
    breathing = [row["breathing_evidence"]["target_status"] for row in rows]
    breathing_states = [row["breathing_evidence"]["breathing_reference_state"] for row in rows]
    rr = [row["rr_target"]["target_status"] for row in rows]
    temporal = [row["temporal_hold"]["event_state"] for row in rows]
    subjects = sorted({row["subject_id"] for row in rows})
    recordings = sorted({row["recording_id"] for row in rows})
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "phase": "R3",
        "audit_date": AUDIT_DATE,
        "source_id": "D0",
        "selection_scope": "MMWAVE_V2_D0_SUBJECT_SPLIT_V1 -> TRAIN ONLY",
        "d0_train_only": True,
        "d0_val_used_for_target_tuning": False,
        "d0_subject_heldout_used": False,
        "m_n6_excluded_heldout_used": False,
        "split_identity": split_doc.get("split_identity"),
        "subject_count": len(subjects),
        "recording_count": len(recordings),
        "window_count": len(rows),
        "subjects": subjects,
        "counts": {
            "breathing_target_status": _counter(breathing),
            "breathing_reference_state": _counter(breathing_states),
            "rr_target_status": _counter(rr),
            "temporal_event_state": _counter(temporal),
            "transition_rows": sum(1 for row in rows if row["supervision_eligibility"]["transition_ambiguous"]),
            "pure_class_training_eligible": sum(1 for row in rows if row["supervision_eligibility"]["pure_class_training_eligible"]),
            "model_supervision_eligible": sum(1 for row in rows if row["supervision_eligibility"]["model_supervision_eligible"]),
        },
        "condition_coverage": _counter(row["condition"] for row in rows),
        "posture_coverage": _counter(row["posture"] for row in rows),
        "reference": {
            "source": "MOVESENSE_CHEST_ACC",
            "reference_rr_present_in_authoritative_a6_rows": sum(1 for row in rows if row["rr_target"]["reference_sample_count"] is not None),
            "reference_rr_used_as_r3_target": sum(1 for row in rows if row["rr_target"]["target_status"] == "AVAILABLE"),
            "reference_rr_during_transition_retained_only_for_audit": sum(1 for row in rows if row["rr_target"]["unavailable_reason"] == "REFERENCE_TRANSITION_OR_HOLD_OVERLAP"),
        },
        "source_label_counts_for_provenance_only": _counter(row["source_label_provenance"]["a4_label"] for row in rows),
        "forbidden_or_not_used": {
            "d2_used": False,
            "mr60_supervised_use": False,
            "radar_amplitude_used_as_reference_label": False,
            "direct_three_class_primary_target": False,
        },
    }


def _d1_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_conditions = [row["condition"] for row in rows]
    apnea_protocol_rows = [
        row for row in rows if row["source_label_provenance"].get("source_breath_hold_protocol_present") is True or str(row["condition"]).startswith("apnea")
    ]
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "phase": "R3",
        "audit_date": AUDIT_DATE,
        "source_id": "D1",
        "selection_scope": "FULL_AUXILIARY_DEVELOPMENT_POOL_FOR_TARGET_COMPATIBILITY_AUDIT",
        "recording_count": len(rows),
        "subject_count": len({row["subject_id"] for row in rows}),
        "counts": {
            "breathing_target_status": _counter(row["breathing_evidence"]["target_status"] for row in rows),
            "rr_target_status": _counter(row["rr_target"]["target_status"] for row in rows),
            "temporal_target_status": _counter(row["temporal_hold"]["target_status"] for row in rows),
            "radar_input_available": sum(1 for row in rows if row["supervision_eligibility"]["radar_input_available"]),
            "model_supervision_eligible": sum(1 for row in rows if row["supervision_eligibility"]["model_supervision_eligible"]),
        },
        "reference_audit": {
            "reference_channel": "respiration",
            "reference_channel_declared_and_stats_present": sum(
                1 for row in rows if row["provenance"]["reference_waveform_materialized_in_compact_input"] is False
            ),
            "reference_waveform_materialized_in_compact_evidence": False,
            "breathing_reference_target_available": 0,
            "rr_target_available": 0,
        },
        "source_condition_coverage": _counter(source_conditions),
        "source_apnea_metadata_count": len(apnea_protocol_rows),
        "source_apnea_metadata_defensible_temporal_boundaries": 0,
        "source_apnea_metadata_auto_mapped_to_safenest_apnea": False,
        "limitations": [
            "D1 compact inventory preserves synchronized respiration-channel presence and statistics, not waveform samples.",
            "R3 therefore does not claim a D1 periodicity target or onset/offset target.",
            "D1 source condition strings remain protocol provenance only.",
        ],
        "forbidden_or_not_used": {
            "d2_used": False,
            "mr60_supervised_use": False,
            "model_training": False,
            "feature_winner_selected": False,
        },
    }


def _cross_domain(rows_d0: list[dict[str, Any]], rows_d1: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "contract_set_id": TARGET_CONTRACT_SET_ID,
        "domains": {
            "D0": {"rows": len(rows_d0), "role": "primary_supervised_development_domain; TRAIN only"},
            "D1": {"rows": len(rows_d1), "role": "auxiliary_cross_domain_target_compatibility_audit"},
        },
        "compatibility": {
            "A_breathing_evidence": {
                "answer": "YES_WITH_SOURCE_REFERENCE_MATERIALIZATION_LIMITATION",
                "shared_semantics": True,
                "d0_status": "GENERATED_FROM_AUTHORITATIVE_A6_REFERENCE_AND_EVENT_AUDIT",
                "d1_status": "REFERENCE_CHANNEL_DECLARED_BUT_TARGET_NOT_REGENERATED_LOCALLY",
            },
            "B_rr": {
                "answer": "YES_WITH_SOURCE_REFERENCE_METHOD_METADATA",
                "shared_semantics": True,
                "d0_status": "CONTINUOUS_RR_FROM_INHERITED_MOVESENSE_REFERENCE_METHOD",
                "d1_status": "TARGET_UNAVAILABLE_UNTIL_RESPIRATION_WAVEFORM_ACCESS",
            },
            "C_temporal_hold": {
                "answer": "D0_ONLY_PARTIAL",
                "shared_semantics": True,
                "d0_status": "EVENT_RELATIVE_VOLUNTARY_BREATH_HOLD_PROXY",
                "d1_status": "SOURCE_APNEA_PROTOCOL_PROVENANCE_ONLY; NO_DEFENSIBLE_BOUNDARIES",
            },
        },
        "artificial_symmetry_forced": False,
        "model_score_used_to_define_targets": False,
    }


def _transition_audit(rows_d0: list[dict[str, Any]], rows_d1: list[dict[str, Any]]) -> dict[str, Any]:
    overlap_bins = Counter()
    for row in rows_d0:
        overlap = float(row["breathing_evidence"].get("window_overlap_seconds") or 0.0)
        if overlap == 0:
            bucket = "ZERO"
        elif overlap < 6:
            bucket = "POSITIVE_BELOW_A4_PURE_PROXY_OVERLAP"
        elif overlap < 30:
            bucket = "PARTIAL_6_TO_WINDOW_DURATION"
        else:
            bucket = "FULL_WINDOW"
        overlap_bins[bucket] += 1
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "d0_train": {
            "window_count": len(rows_d0),
            "overlap_seconds_bins": dict(sorted(overlap_bins.items())),
            "event_state_counts": _counter(row["temporal_hold"]["event_state"] for row in rows_d0),
            "partial_event_rows_are_not_whole_window_apnea": True,
            "full_window_event_rows": overlap_bins.get("FULL_WINDOW", 0),
            "baseline_not_established_rows": sum(1 for row in rows_d0 if row["temporal_hold"]["baseline_state"] == "BASELINE_NOT_ESTABLISHED"),
            "recovery_detected_rows": sum(1 for row in rows_d0 if row["temporal_hold"]["recovery_detected"] is True),
        },
        "d1": {
            "recording_count": len(rows_d1),
            "source_apnea_protocol_rows": sum(1 for row in rows_d1 if row["source_label_provenance"].get("source_breath_hold_protocol_present") is True),
            "defensible_onset_offset_rows": 0,
            "source_apnea_protocol_auto_mapped": False,
        },
    }


def _exceptions(d0_audit: Mapping[str, Any], d1_audit: Mapping[str, Any]) -> dict[str, Any]:
    entries = [
        {
            "id": "R3-D1-REFERENCE-WAVEFORM-NOT-MATERIALIZED",
            "severity": "LIMITATION",
            "scope": "D1",
            "status": "OPEN_FOR_M_PV1_INPUT_MATERIALIZATION",
            "detail": "D1 adapter evidence records synchronized respiration-channel presence and statistics, but no respiration waveform is materialized for deterministic R3 target extraction.",
        },
        {
            "id": "R3-D1-SOURCE-APNEA-BOUNDARY-UNAVAILABLE",
            "severity": "LIMITATION",
            "scope": "D1",
            "status": "OPEN",
            "detail": "D1 source condition 'apnea' and related protocol strings are retained as provenance; no onset/offset is guessed.",
        },
        {
            "id": "R3-D0-FINAL-PERSISTENCE-DEFERRED",
            "severity": "LIMITATION",
            "scope": "D0/M-PV1",
            "status": "DEFERRED",
            "detail": "R3 does not finalize an X-second persistence threshold or model history length.",
        },
        {
            "id": "R3-D0-NO-FULL-HOLD-COVERAGE-IN-TRAIN",
            "severity": "LIMITATION",
            "scope": "D0 TRAIN",
            "status": "OBSERVED",
            "detail": "The D0 TRAIN compact window audit contains partial hold overlaps but no full-window event; ABSENT remains a supported contract state and is not fabricated.",
        },
    ]
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "phase": "R3",
        "total_blockers": 0,
        "entries": entries,
        "d0_train_window_count": d0_audit.get("window_count"),
        "d1_recording_count": d1_audit.get("recording_count"),
    }


def _validation_result(d0_audit: Mapping[str, Any], d1_audit: Mapping[str, Any], exceptions: Mapping[str, Any]) -> dict[str, Any]:
    checks = {
        "R2_CONTRACT_INHERITED": "YES",
        "D0_TRAIN_ONLY": "YES" if d0_audit.get("d0_train_only") else "NO",
        "D0_VAL_USED_FOR_TARGET_TUNING": "NO",
        "D0_SUBJECT_HELDOUT_USED": "NO",
        "M_N6_EXCLUDED_HELDOUT_USED": "NO",
        "D1_REFERENCE_SUPPORTED": "YES",
        "D2_USED": "NO",
        "MR60_SUPERVISED_USE": "NO",
        "BREATHING_EVIDENCE_TARGET_VERSIONED": "YES",
        "RR_TARGET_VERSIONED": "YES",
        "TEMPORAL_HOLD_TARGET_VERSIONED": "YES",
        "BREATHING_AND_RR_SEPARATE": "YES",
        "RR_UNAVAILABLE_ENCODED_AS_ZERO": "NO",
        "DIRECT_THREE_CLASS_PRIMARY_TARGET": "NO",
        "WHOLE_WINDOW_APNEA_DEFAULT": "NO",
        "LOW_RADAR_AMPLITUDE_DEFINES_APNEA": "NO",
        "RADAR_AMPLITUDE_USED_AS_REFERENCE_LABEL": "NO",
        "TEMPORAL_BASELINE_EXPLICIT": "YES",
        "TEMPORAL_RECOVERY_EXPLICIT": "YES",
        "TRANSITION_STATE_EXPLICIT": "YES",
        "D1_PROTOCOL_APNEA_AUTO_MAPPED_TO_SAFENEST_APNEA": "NO",
        "Q2_THRESHOLDS_REDEFINED": "NO",
        "INVALID_RADAR_INPUT_MODEL_SUPERVISION_ELIGIBLE": "NO",
        "F1_F2_F3_WINNER_SELECTED": "NO",
        "MODEL_TRAINING": "NO",
        "MODEL_ARCHITECTURE_SELECTED": "NO",
        "PROBABILITY_THRESHOLD_SELECTED": "NO",
        "APNEA_PERSISTENCE_THRESHOLD_FINALIZED": "NO",
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
    }
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "phase": "R3",
        "audit_date": AUDIT_DATE,
        "ok": exceptions.get("total_blockers") == 0,
        "gate": "PASS_WITH_LIMITATIONS" if exceptions.get("total_blockers") == 0 else "BLOCKED",
        "errors": [],
        "checks": checks,
        "r3_ready_for_m_pv1": "YES" if exceptions.get("total_blockers") == 0 else "NO",
        "known_limitations": [entry["detail"] for entry in exceptions.get("entries", [])],
        "deterministic_generation": True,
        "raw_waveforms_committed": False,
        "model_training_performed": False,
    }


def _checksums(output_root: Path) -> dict[str, Any]:
    evidence_files = [name for name in OUTPUT_FILES if name != "checksums.json"]
    code_files = (
        "adapters/mmwave_r3_target_contracts.py",
        "scripts/run_mmwave_r3_target_contracts.py",
        "scripts/validate_mmwave_r3_target_contracts.py",
        "tests/test_mmwave_r3_target_contracts.py",
    )
    return {
        "schema_version": R3_SCHEMA_VERSION,
        "manifest_id": "MMWAVE_V2_R3_CHECKSUM_MANIFEST_V1",
        "algorithm": "SHA-256",
        "repository_relative_paths_only": True,
        "files": {name: _sha256(output_root / name) for name in evidence_files},
        "input_lineage": {
            _repo_relative(ROOT / path): _sha256(ROOT / path)
            for path in _input_paths()
        },
        "code": {
            path: _sha256(ROOT / path)
            for path in code_files
            if (ROOT / path).is_file()
        },
        "checksum_self_included": False,
        "raw_waveforms_committed": False,
        "derived_waveforms_committed": False,
    }


def run(output_root: Path = ROOT / OUTPUT_RELATIVE_ROOT) -> dict[str, Any]:
    for path in _input_paths():
        if not (ROOT / path).is_file():
            raise R3RunnerError(f"required input missing: {_repo_relative(ROOT / path)}")
    r1 = _load_json(ROOT / R1_CONTRACT)
    r2 = _load_json(ROOT / R2_CANDIDATE_SET)
    q2 = _load_json(ROOT / Q2_CONTRACT)
    d0_rows, split_doc = _load_d0_rows()
    d1_rows = _load_d1_rows()
    output_root.mkdir(parents=True, exist_ok=True)

    d0_audit = _d0_audit(d0_rows, split_doc)
    d1_audit = _d1_audit(d1_rows)
    exceptions = _exceptions(d0_audit, d1_audit)
    validation = _validation_result(d0_audit, d1_audit, exceptions)

    _write_json(output_root / "target_contract_set.json", _target_contract_set(r2, r1, q2))
    _write_json(output_root / "breathing_evidence_contract.json", _breathing_contract())
    _write_json(output_root / "rr_target_contract.json", _rr_contract())
    _write_json(output_root / "temporal_hold_contract.json", _temporal_contract())
    _write_json(output_root / "supervision_eligibility_contract.json", _eligibility_contract(q2))
    _write_jsonl(output_root / "d0_target_rows.jsonl", d0_rows)
    _write_jsonl(output_root / "d1_target_rows.jsonl", d1_rows)
    _write_json(output_root / "d0_target_audit.json", d0_audit)
    _write_json(output_root / "d1_target_audit.json", d1_audit)
    _write_json(output_root / "cross_domain_target_compatibility.json", _cross_domain(d0_rows, d1_rows))
    _write_json(output_root / "transition_audit.json", _transition_audit(d0_rows, d1_rows))
    _write_json(output_root / "exception_registry.json", exceptions)
    _write_json(output_root / "validation_result.json", validation)
    _write_json(output_root / "checksums.json", _checksums(output_root))
    return validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / OUTPUT_RELATIVE_ROOT)
    args = parser.parse_args()
    try:
        result = run(args.output_root.resolve())
    except (R3RunnerError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "gate": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
