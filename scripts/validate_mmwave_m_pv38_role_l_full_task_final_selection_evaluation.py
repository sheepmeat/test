#!/usr/bin/env python3
"""Validate the fail-closed M-PV3.8 ROLE_L final-selection blocker."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_role_L_full_task_final_selection_evaluation"
CONTRACT = ROOT / "config/mmwave/m_pv38_minimal_selection_readiness_gate.json"
REPORT = ROOT / "docs/mmwave/20260823_M-PV3_8_ROLE_L_FULL_TASK_FINAL_SELECTION_EVALUATION.md"
ROLE = "ROLE_L_FULL_TASK"
IDENTITY = "MMWAVE_V2_M_PV38_MINIMAL_SELECTION_READINESS_GATE_V1"
SCHEMA = "M-PV3.8.1"
DECISION = "BLOCKED_INVALID_FINAL_MEMBERSHIP"
EXPECTED = {f"Family_{family}_seed_{seed}" for family in ("B", "C") for seed in (11, 23, 47)}
SUBJECTS = {"D1_PERSON_03", "D1_PERSON_09", "D1_PERSON_11"}
REQUIRED = (
    "evaluation_manifest.json",
    "membership_audit.json",
    "candidate_decision_table.json",
    "card_a_safety.json",
    "card_b_breathing.json",
    "card_c_rr.json",
    "card_d_stability.json",
    "validation_result.json",
    "checksums.json",
    "checksums.sha256",
)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def add(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _verify_checksums(checks: list[dict[str, Any]]) -> None:
    checksum_path = OUT / "checksums.sha256"
    listed: list[str] = []
    failures: list[str] = []
    if checksum_path.is_file():
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                digest, path = line.split("  ", 1)
            except ValueError:
                failures.append(f"malformed:{line}")
                continue
            listed.append(path)
            target = ROOT / path
            if not target.is_file() or sha(target) != digest:
                failures.append(path)
    add(checks, "checksums_cover_listed_files", checksum_path.is_file() and not failures, {"listed": listed, "failures": failures})
    required = {rel(OUT / name) for name in REQUIRED if name not in {"checksums.json", "checksums.sha256"}}
    add(checks, "checksums_cover_required_artifacts", required.issubset(set(listed)), sorted(required - set(listed)))


def _absolute_strings(value: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_absolute_strings(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_absolute_strings(child, f"{path}[{index}]"))
    elif isinstance(value, str) and (value.startswith("/Users/") or value.startswith("/private/") or value.startswith("file://")):
        found.append(path)
    return found


def _runner_has_candidate_output_access() -> list[str]:
    source = (ROOT / "scripts/mmwave_m_pv38_role_l_full_task_final_selection_evaluation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_names = {"_load_checkpoint", "_predict", "_evaluate_group", "load_state_dict"}
    calls = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_names]
    forbidden_text = [token for token in ("torch.load", "mmwave_m_pv3_candidate_selection", "mmwave_m_pv2_candidate_training") if token in source]
    return [f"call:{line}" for line in calls] + [f"text:{token}" for token in forbidden_text]


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    add(checks, "required_artifacts_present", not missing, missing)
    if missing:
        return {"schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION", "role_id": ROLE, "decision": DECISION, "gate": DECISION, "ok": False, "artifact_valid": False, "failed_checks": ["required_artifacts_present"], "checks": checks}

    contract = read(CONTRACT)
    manifest = read(OUT / "evaluation_manifest.json")
    membership = read(OUT / "membership_audit.json")
    table = read(OUT / "candidate_decision_table.json")
    cards = [read(OUT / name) for name in ("card_a_safety.json", "card_b_breathing.json", "card_c_rr.json", "card_d_stability.json")]
    validation = read(OUT / "validation_result.json")
    checksums = read(OUT / "checksums.json")

    add(checks, "contract_identity_and_design_mode", contract.get("contract_id") == IDENTITY and contract.get("schema_version") == SCHEMA and contract.get("mode") == "CONTRACT_DESIGN_ONLY", {"contract_id": contract.get("contract_id"), "schema_version": contract.get("schema_version"), "mode": contract.get("mode")})
    add(checks, "contract_hash_matches_manifest", manifest.get("contract_sha256") == sha(CONTRACT) and checksums.get("inputs", {}).get(rel(CONTRACT)) == sha(CONTRACT), {"manifest": manifest.get("contract_sha256"), "actual": sha(CONTRACT)})
    add(checks, "report_checksum_covered", REPORT.is_file() and checksums.get("inputs", {}).get(rel(REPORT)) == sha(REPORT), {"report_present": REPORT.is_file(), "recorded": checksums.get("inputs", {}).get(rel(REPORT))})
    add(checks, "role_and_decision_identity", manifest.get("role_id") == ROLE and manifest.get("decision") == DECISION and manifest.get("selection_result") == DECISION and manifest.get("selected_candidate") is None and validation.get("decision") == DECISION and validation.get("selection_result") == DECISION and validation.get("selected_candidate") is None and validation.get("gate") == DECISION, {"role": manifest.get("role_id"), "manifest_decision": manifest.get("decision"), "validation_decision": validation.get("decision"), "selected_candidate": validation.get("selected_candidate")})
    add(checks, "authorized_roster_exactly_six", set(manifest.get("authorized_candidates", [])) == EXPECTED and manifest.get("candidate_count") == 6, manifest.get("authorized_candidates"))
    add(checks, "candidate_registry_verified_without_checkpoint_open", manifest.get("candidate_roster_audit", {}).get("authorized_roster_matches_contract") is True and manifest.get("candidate_roster_audit", {}).get("checkpoint_files_opened") is False, manifest.get("candidate_roster_audit"))
    add(checks, "membership_manifest_lock_is_invalid_as_expected", membership.get("membership_manifest_present") is False and membership.get("membership_lock_valid") is False and membership.get("membership_checksum_coverage") is False, {key: membership.get(key) for key in ("membership_manifest_present", "membership_lock_valid", "membership_checksum_coverage")})
    observed = membership.get("observed_source_rows", {})
    add(checks, "observed_membership_counts_are_recorded", observed.get("eligible_present") == 57 and observed.get("eligible_absent") == 0 and observed.get("ambiguous") == 2 and observed.get("required_absent") == 57, observed)
    per_subject = membership.get("per_subject", {})
    add(checks, "per_subject_absent_requirement_is_missing", set(per_subject) == SUBJECTS and all(row.get("observed_eligible_absent") == 0 and row.get("absent_deficit") == 19 and row.get("required_eligible_absent") == 19 for row in per_subject.values()), per_subject)
    add(checks, "ambiguous_rows_retained_without_relabel", len(membership.get("ambiguous_records", [])) == 2 and all(row.get("breathing_reference_state") == "BREATHING_REFERENCE_AMBIGUOUS" for row in membership.get("ambiguous_records", [])), membership.get("ambiguous_records"))
    add(checks, "training_subject_disjointness_audit", membership.get("candidate_training_subject_disjointness", {}).get("pass") is True and membership.get("candidate_training_subject_disjointness", {}).get("overlap") == [], membership.get("candidate_training_subject_disjointness"))
    rows = table.get("rows", [])
    add(checks, "candidate_decision_table_has_all_six_blocked_rows", table.get("selection_result") == DECISION and table.get("selected_candidate") is None and len(rows) == 6 and {row.get("candidate_key") for row in rows} == EXPECTED and all(row.get("decision") == DECISION and row.get("evaluation_status") == "NOT_EVALUATED" and row.get("candidate_output_accessed") is False and row.get("safety") is None and row.get("breathing") is None and row.get("rr") is None and row.get("stability") is None for row in rows), rows)
    for card in cards:
        card_rows = card.get("candidates", [])
        add(checks, f"{card.get('card_id')}_blocked_without_metrics", card.get("evaluation_status") == DECISION and card.get("candidate_output_accessed") is False and len(card_rows) == 6 and all(row.get("status") == "NOT_EVALUATED" and row.get("metrics") is None and row.get("guard_result") is None for row in card_rows), {"status": card.get("evaluation_status"), "candidate_count": len(card_rows)})
    safety_locks_ok = validation.get("candidate_output_accessed") is False and validation.get("candidate_evaluation_performed") is False and validation.get("no_training") is True and validation.get("no_threshold_change") is True and validation.get("no_combined_score") is True and validation.get("no_ranking") is True and validation.get("no_post_hoc_seed_selection") is True and validation.get("no_d2") is True and validation.get("no_mr60_supervised_physiology") is True and validation.get("no_m_pv4_approval") is True
    add(checks, "execution_safety_locks", safety_locks_ok, validation)
    runner_access = _runner_has_candidate_output_access()
    add(checks, "runner_does_not_open_candidate_outputs", not runner_access, runner_access)
    forbidden_artifacts = [str(path.relative_to(ROOT)) for path in OUT.rglob("*") if path.is_file() and path.suffix.lower() in {".pt", ".pth", ".tflite", ".int8"}]
    add(checks, "no_model_artifacts_in_evidence", not forbidden_artifacts, forbidden_artifacts)
    absolute = []
    for name in REQUIRED:
        if name.endswith(".json"):
            absolute.extend(_absolute_strings(read(OUT / name), name))
    add(checks, "machine_readable_evidence_has_no_machine_absolute_paths", not absolute, absolute)
    _verify_checksums(checks)

    failures = [item["name"] for item in checks if not item["ok"]]
    return {
        "schema_version": "M-PV3.8.1_ROLE_L_FULL_TASK_FINAL_SELECTION",
        "contract_id": IDENTITY,
        "phase": "M-PV3.8",
        "role_id": ROLE,
        "decision": DECISION,
        "gate": DECISION,
        "ok": not failures,
        "artifact_valid": not failures,
        "terminal_membership_block": True,
        "failed_checks": failures,
        "checks": checks,
        "evaluated_candidate_count": 0,
        "authorized_candidate_count": 6,
        "candidate_output_accessed": False,
        "no_model_selected": True,
    }


def main() -> int:
    result = validate()
    print(json.dumps({"decision": result["decision"], "gate": result["gate"], "ok": result["ok"], "failed_checks": result["failed_checks"]}, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
