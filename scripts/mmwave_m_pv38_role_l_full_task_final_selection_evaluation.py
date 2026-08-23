#!/usr/bin/env python3
"""Fail-closed M-PV3.8 ROLE_L_FULL_TASK final-selection gate.

The M-PV3.8 contract requires a separately locked
``D1_FINAL_SELECTION_BOTH_CLASS_V1`` membership before any candidate output is
opened.  This runner audits that prerequisite from the governed M-PV1
membership and writes a terminal blocker when the lock is absent or invalid.
It deliberately does not import model-evaluation code or open checkpoints.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_REL = Path("config/mmwave/m_pv38_minimal_selection_readiness_gate.json")
GATE_REL = Path("datasets/mmwave/manifests/M-PV3_8_minimal_selection_readiness_gate/minimal_selection_gate.json")
REQUIREMENTS_REL = Path("datasets/mmwave/manifests/M-PV3_8_minimal_selection_readiness_gate/evidence_requirements.json")
M_PV1_REL = Path("datasets/mmwave/manifests/M-PV1_public_multidomain_contract/m_pv2_example_manifest.json")
REGISTRY_REL = Path("datasets/mmwave/manifests/M-PV2_candidate_training/candidate_registry.json")
OUTPUT_REL = Path("datasets/mmwave/manifests/M-PV3_8_role_L_full_task_final_selection_evaluation")
REPORT_REL = Path("docs/mmwave/20260823_M-PV3_8_ROLE_L_FULL_TASK_FINAL_SELECTION_EVALUATION.md")

EXPECTED_CONTRACT = "MMWAVE_V2_M_PV38_MINIMAL_SELECTION_READINESS_GATE_V1"
EXPECTED_SCHEMA = "M-PV3.8.1"
EXPECTED_ROLE = "ROLE_L_FULL_TASK"
MEMBERSHIP_ID = "D1_FINAL_SELECTION_BOTH_CLASS_V1"
HELD_OUT_SUBJECTS = ("D1_PERSON_03", "D1_PERSON_09", "D1_PERSON_11")
FAMILIES = ("Family_B", "Family_C")
SEEDS = (11, 23, 47)
EXPECTED_CANDIDATES = tuple(f"{family}_seed_{seed}" for family in FAMILIES for seed in SEEDS)

EXPECTED_MEMBERSHIP_PATHS = (
    Path("datasets/mmwave/manifests/D1_FINAL_SELECTION_BOTH_CLASS_V1/membership_manifest.json"),
    Path("datasets/mmwave/manifests/D1_FINAL_SELECTION_BOTH_CLASS_V1/manifest.json"),
    Path("datasets/mmwave/manifests/M-PV3_8_minimal_selection_readiness_gate/D1_FINAL_SELECTION_BOTH_CLASS_V1_membership_manifest.json"),
    Path("datasets/mmwave/manifests/M-PV3_8_minimal_selection_readiness_gate/d1_final_selection_membership_manifest.json"),
)


class PV38Error(RuntimeError):
    """Fail-closed M-PV3.8 execution error."""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PV38Error(f"failed to read {path}: {exc}") from exc


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _candidate_key(family: str, seed: int) -> str:
    return f"{family}_seed_{seed}"


def _source_provenance(row: Mapping[str, Any]) -> dict[str, Any]:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    return {
        "source_dataset": provenance.get("source_dataset"),
        "subject": row.get("subject_id"),
        "recording_or_session": row.get("recording_id") or provenance.get("recording_id"),
        "time_or_window": {
            "context_start_s": row.get("context_start_s"),
            "context_end_s": row.get("context_end_s"),
            "target_start_s": row.get("target_start_s"),
            "target_end_s": row.get("target_end_s"),
            "context_time_range_s": provenance.get("context_time_range_s"),
        },
        "label_mapping": provenance.get("label_mapping"),
        "split": row.get("split"),
        "quality_provenance": provenance.get("quality_provenance"),
        "quality_status": row.get("quality_status"),
        "source_file": provenance.get("source_file"),
        "reference_method": provenance.get("reference_method"),
    }


def _summary_row(row: Mapping[str, Any]) -> dict[str, Any]:
    provenance = _source_provenance(row)
    return {
        "model_input_id": row.get("model_input_id"),
        "subject_id": row.get("subject_id"),
        "recording_id": row.get("recording_id"),
        "split": row.get("split"),
        "breathing_reference_state": row.get("breathing_reference_state"),
        "breathing_supervision_eligible": row.get("breathing_supervision_eligible"),
        "quality_status": row.get("quality_status"),
        "provenance": provenance,
    }


def _audit_source_membership(manifest: Mapping[str, Any]) -> dict[str, Any]:
    examples = manifest.get("examples")
    if not isinstance(examples, list):
        raise PV38Error("M-PV1 manifest has no examples list")
    model_rows = [row for row in examples if isinstance(row, Mapping) and row.get("model_ready") is True]
    final_rows = [row for row in model_rows if row.get("source_id") == "D1" and row.get("split") == "D1_DEV_VAL"]

    def present(row: Mapping[str, Any]) -> bool:
        return row.get("breathing_reference_state") == "BREATHING_REFERENCE_PRESENT" and row.get("breathing_supervision_eligible") is True

    def absent(row: Mapping[str, Any]) -> bool:
        return row.get("breathing_reference_state") == "BREATHING_REFERENCE_ABSENT" and row.get("breathing_supervision_eligible") is True

    present_rows = [row for row in final_rows if present(row)]
    absent_rows = [row for row in final_rows if absent(row)]
    ambiguous_rows = [row for row in final_rows if not present(row) and not absent(row)]
    by_subject: dict[str, dict[str, Any]] = {}
    for subject in HELD_OUT_SUBJECTS:
        subject_rows = [row for row in final_rows if row.get("subject_id") == subject]
        subject_present = [row for row in subject_rows if present(row)]
        subject_absent = [row for row in subject_rows if absent(row)]
        subject_ambiguous = [row for row in subject_rows if not present(row) and not absent(row)]
        by_subject[subject] = {
            "observed_total_model_ready_contexts": len(subject_rows),
            "observed_eligible_present": len(subject_present),
            "observed_eligible_absent": len(subject_absent),
            "observed_ambiguous": len(subject_ambiguous),
            "required_eligible_present": 19,
            "required_eligible_absent": 19,
            "absent_deficit": 19 - len(subject_absent),
            "ambiguous_records": [_summary_row(row) for row in subject_ambiguous],
        }

    training_rows = [row for row in model_rows if row.get("split") in {"TRAIN", "D1_DEV_TRAIN"}]
    training_subjects = {str(row.get("subject_id")) for row in training_rows}
    heldout_overlap = sorted(training_subjects.intersection(HELD_OUT_SUBJECTS))
    source_required = ("source_dataset", "subject", "recording_or_session", "time_or_window", "label_mapping", "split", "quality_provenance")
    missing_provenance_fields = Counter()
    for row in final_rows:
        provenance = _source_provenance(row)
        for field in source_required:
            value = provenance.get(field)
            if value is None or value == {}:
                missing_provenance_fields[field] += 1

    manifest_candidates = [{"path": _rel(ROOT / path), "present": (ROOT / path).is_file()} for path in EXPECTED_MEMBERSHIP_PATHS]
    lock_present = any(item["present"] for item in manifest_candidates)
    observed_by_subject = {
        subject: {
            "present": details["observed_eligible_present"],
            "absent": details["observed_eligible_absent"],
            "ambiguous": details["observed_ambiguous"],
        }
        for subject, details in by_subject.items()
    }
    blocking_reasons = [
        "D1_FINAL_SELECTION_BOTH_CLASS_V1 membership manifest is not present in the repository.",
        f"Required eligible ABSENT contexts: 57; observed governed eligible ABSENT contexts: {len(absent_rows)}.",
        "Each held-out subject is missing the required 19 eligible ABSENT contexts.",
        "The one-time membership lock, membership checksum coverage, and ambiguous exception registry cannot be verified.",
    ]
    if missing_provenance_fields:
        blocking_reasons.append("The available D1 source rows do not carry all final-lock provenance fields as explicit fields: " + ", ".join(sorted(missing_provenance_fields)) + ".")
    return {
        "membership_id": MEMBERSHIP_ID,
        "source_boundary": "D1_GOVERNED_NON_D2_ONLY",
        "expected_membership_manifest_candidates": manifest_candidates,
        "membership_manifest_present": lock_present,
        "membership_lock_valid": False,
        "membership_checksum_coverage": False,
        "ambiguous_exception_registry_present": False,
        "source_manifest": _rel(ROOT / M_PV1_REL),
        "source_manifest_sha256": _sha(ROOT / M_PV1_REL),
        "observed_source_rows": {
            "model_ready_total": len(model_rows),
            "d1_final_split_model_ready": len(final_rows),
            "eligible_present": len(present_rows),
            "eligible_absent": len(absent_rows),
            "ambiguous": len(ambiguous_rows),
            "required_present": 57,
            "required_absent": 57,
            "required_ambiguous_handling": "RETAIN_PROVENANCE_EXCLUDE_FROM_PURE_CLASS_METRICS_NO_RELABEL",
        },
        "held_out_subjects": list(HELD_OUT_SUBJECTS),
        "per_subject": by_subject,
        "observed_class_counts_by_subject": observed_by_subject,
        "ambiguous_records": [_summary_row(row) for row in ambiguous_rows],
        "candidate_training_subject_disjointness": {
            "training_split_scope": ["TRAIN", "D1_DEV_TRAIN"],
            "training_subject_count": len(training_subjects),
            "held_out_subject_count": len(HELD_OUT_SUBJECTS),
            "overlap": heldout_overlap,
            "pass": not heldout_overlap,
        },
        "provenance_required_fields": list(source_required),
        "source_row_explicit_provenance_missing_counts": dict(sorted(missing_provenance_fields.items())),
        "blocking_reasons": blocking_reasons,
    }


def _registry_audit(registry: Mapping[str, Any]) -> dict[str, Any]:
    candidates = registry.get("candidates")
    if not isinstance(candidates, list):
        raise PV38Error("candidate registry has no candidates list")
    observed = sorted(
        _candidate_key(str(row.get("family")).replace("family_", "Family_").title().replace("Family_B", "Family_B").replace("Family_C", "Family_C"), int(row.get("seed")))
        for row in candidates
        if isinstance(row, Mapping) and row.get("family") in {"family_b", "family_c"} and row.get("seed") in SEEDS
    )
    # The roster comparison uses the contract spelling, while the registry
    # stores lower-case family identifiers.
    observed = sorted(f"Family_{str(row.get('family'))[-1].upper()}_seed_{int(row.get('seed'))}" for row in candidates if isinstance(row, Mapping) and row.get("family") in {"family_b", "family_c"} and row.get("seed") in SEEDS)
    return {
        "registry": _rel(ROOT / REGISTRY_REL),
        "registry_sha256": _sha(ROOT / REGISTRY_REL),
        "authorized_roster_matches_contract": observed == sorted(EXPECTED_CANDIDATES),
        "observed_authorized_roster": observed,
        "expected_authorized_roster": list(EXPECTED_CANDIDATES),
        "checkpoint_files_opened": False,
    }


def _blocked_card(card_id: str, title: str, candidates: Sequence[str], extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION",
        "card_id": card_id,
        "title": title,
        "role_id": EXPECTED_ROLE,
        "evaluation_status": "BLOCKED_INVALID_FINAL_MEMBERSHIP",
        "candidate_output_accessed": False,
        "metrics": None,
        "candidates": [
            {
                "candidate_key": candidate,
                "status": "NOT_EVALUATED",
                "metrics": None,
                "guard_result": None,
                "reason": "D1_FINAL_SELECTION_BOTH_CLASS_V1 membership lock invalid or absent",
            }
            for candidate in candidates
        ],
    }
    if extra:
        card.update(extra)
    return card


def _write_checksums(output: Path, input_paths: Sequence[Path]) -> None:
    files: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"checksums.json", "checksums.sha256"}:
            files[_rel(path)] = _sha(path)
    all_inputs = list(input_paths)
    report = ROOT / REPORT_REL
    if report.is_file():
        all_inputs.append(report)
    inputs = {_rel(path): _sha(path) for path in all_inputs}
    _write(output / "checksums.json", {"schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION", "files": files, "inputs": inputs, "decision": "BLOCKED_INVALID_FINAL_MEMBERSHIP"})
    lines = dict(files)
    lines[_rel(output / "checksums.json")] = _sha(output / "checksums.json")
    (output / "checksums.sha256").write_text("\n".join(f"{digest}  {path}" for path, digest in sorted(lines.items())) + "\n", encoding="utf-8")


def run_phase() -> dict[str, Any]:
    contract = _read(ROOT / CONTRACT_REL)
    gate = _read(ROOT / GATE_REL)
    requirements = _read(ROOT / REQUIREMENTS_REL)
    source_manifest = _read(ROOT / M_PV1_REL)
    registry = _read(ROOT / REGISTRY_REL)
    if contract.get("contract_id") != EXPECTED_CONTRACT or contract.get("schema_version") != EXPECTED_SCHEMA or contract.get("mode") != "CONTRACT_DESIGN_ONLY":
        raise PV38Error("M-PV3.8 contract identity/schema/mode changed")
    required_before_access = requirements.get("required_before_any_candidate_output_access", [])
    if gate.get("minimum_final_membership", {}).get("membership_id") != MEMBERSHIP_ID or f"{MEMBERSHIP_ID}_membership_manifest" not in required_before_access:
        raise PV38Error("M-PV3.8 membership identity changed")
    if tuple(contract.get("authorized_candidate_roster", {}).get("families", [])) != FAMILIES or tuple(contract.get("authorized_candidate_roster", {}).get("seeds", [])) != SEEDS:
        raise PV38Error("M-PV3.8 authorized roster changed")

    membership = _audit_source_membership(source_manifest)
    roster = _registry_audit(registry)
    if roster["authorized_roster_matches_contract"] is not True:
        raise PV38Error("candidate registry does not match the frozen six-candidate roster")
    # The contract requires a valid one-time lock before candidate outputs are
    # opened.  The current repository has no such lock, so stop here.
    decision = "BLOCKED_INVALID_FINAL_MEMBERSHIP"
    candidate_table = [
        {
            "candidate_key": candidate,
            "family": candidate.split("_seed_")[0],
            "seed": int(candidate.rsplit("_", 1)[-1]),
            "decision": decision,
            "evaluation_status": "NOT_EVALUATED",
            "candidate_output_accessed": False,
            "safety": None,
            "breathing": None,
            "rr": None,
            "stability": None,
        }
        for candidate in EXPECTED_CANDIDATES
    ]
    output = ROOT / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION",
        "contract_id": contract["contract_id"],
        "contract_schema_version": contract["schema_version"],
        "contract_mode": contract["mode"],
        "contract_sha256": _sha(ROOT / CONTRACT_REL),
        "phase": "M-PV3.8",
        "role_id": EXPECTED_ROLE,
        "evaluation_mode": "FINAL_SELECTION_MEMBERSHIP_GATE",
        "authorized_candidates": list(EXPECTED_CANDIDATES),
        "candidate_count": len(EXPECTED_CANDIDATES),
        "excluded_candidates": ["Family_A", "ROLE_S_SHORT_CONTEXT_15s", "M-PV3.5_isolation_CNN"],
        "membership_id": MEMBERSHIP_ID,
        "membership_audit": membership,
        "candidate_roster_audit": roster,
        "candidate_output_accessed": False,
        "candidate_evaluation_performed": False,
        "training_performed": False,
        "threshold_modified": False,
        "combined_score_created": False,
        "ranking_created": False,
        "post_hoc_seed_selection": False,
        "d2_access": False,
        "mr60_supervised_physiology": False,
        "m_pv4_approved": False,
        "decision": decision,
        "selection_result": decision,
        "selected_candidate": None,
        "blocking_reason": "D1_FINAL_SELECTION_BOTH_CLASS_V1 is not locked and does not contain the required 57 eligible ABSENT contexts (19 per held-out subject).",
        "cards": {
            "safety": "card_a_safety.json",
            "breathing": "card_b_breathing.json",
            "rr": "card_c_rr.json",
            "stability": "card_d_stability.json",
            "candidate_decision_table": "candidate_decision_table.json",
            "membership_audit": "membership_audit.json",
        },
    }
    _write(output / "membership_audit.json", membership)
    _write(output / "card_a_safety.json", _blocked_card("CARD_A_SAFETY", "Class A safety", EXPECTED_CANDIDATES, {"runtime_precedence": ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"], "input_unavailable_must_not_emit": ["PRESENT", "ABSENT", "NORMAL", "APNEA"], "q2_scope": "NOT_EVALUATED_DUE_INVALID_FINAL_MEMBERSHIP"}))
    _write(output / "card_b_breathing.json", _blocked_card("CARD_B_BREATHING", "Both-class breathing", EXPECTED_CANDIDATES, {"frozen_guards": contract["frozen_rules"]["breathing"], "required_class_counts": {"PRESENT": 57, "ABSENT": 57}, "ambiguous_policy": "RETAIN_PROVENANCE_EXCLUDE_NO_RELABEL"}))
    _write(output / "card_c_rr.json", _blocked_card("CARD_C_RR", "RR", EXPECTED_CANDIDATES, {"frozen_guards": contract["frozen_rules"]["rr"], "metrics_required": ["MAE_bpm", "median_absolute_error_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm"]}))
    _write(output / "card_d_stability.json", _blocked_card("CARD_D_STABILITY", "Every-seed stability", EXPECTED_CANDIDATES, {"seeds_required": list(SEEDS), "held_out_subjects": list(HELD_OUT_SUBJECTS), "summary_metrics": ["mean", "population_std", "min", "max", "per_subject_results"]}))
    _write(output / "candidate_decision_table.json", {"schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION", "role_id": EXPECTED_ROLE, "decision": decision, "selection_result": decision, "selected_candidate": None, "candidate_count": len(candidate_table), "candidate_output_accessed": False, "rows": candidate_table})
    _write(output / "evaluation_manifest.json", manifest)
    validation = {
        "schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION",
        "contract_id": EXPECTED_CONTRACT,
        "phase": "M-PV3.8",
        "role_id": EXPECTED_ROLE,
        "decision": decision,
        "selection_result": decision,
        "selected_candidate": None,
        "gate": decision,
        "ok": True,
        "artifact_valid": True,
        "terminal_membership_block": True,
        "evaluated_candidate_count": 0,
        "authorized_candidate_count": len(EXPECTED_CANDIDATES),
        "candidate_output_accessed": False,
        "candidate_evaluation_performed": False,
        "no_training": True,
        "no_threshold_change": True,
        "no_combined_score": True,
        "no_ranking": True,
        "no_post_hoc_seed_selection": True,
        "no_d2": True,
        "no_mr60_supervised_physiology": True,
        "no_m_pv4_approval": True,
        "blocking_reasons": membership["blocking_reasons"],
        "failed_membership_requirements": [
            "membership_manifest_present",
            "membership_checksum_coverage",
            "eligible_absent_count_57",
            "eligible_absent_count_19_per_held_out_subject",
            "ambiguous_exception_registry_present",
        ],
        "selection_candidate_decisions": {candidate: decision for candidate in EXPECTED_CANDIDATES},
    }
    _write(output / "validation_result.json", validation)
    _write_checksums(output, [ROOT / CONTRACT_REL, ROOT / GATE_REL, ROOT / REQUIREMENTS_REL, ROOT / M_PV1_REL, ROOT / REGISTRY_REL])
    return {"decision": decision, "role": EXPECTED_ROLE, "candidate_count": len(EXPECTED_CANDIDATES), "evaluated_candidate_count": 0, "candidate_output_accessed": False, "output": OUTPUT_REL.as_posix()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="run the fail-closed membership gate")
    del parser
    try:
        print(json.dumps(run_phase(), ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"M-PV3.8 ROLE_L_FULL_TASK FAILED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
