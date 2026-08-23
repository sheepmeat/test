#!/usr/bin/env python3
"""Fail-closed validator for the M-PV3 30-second candidate selection gate."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "config/mmwave/m_pv3_selection_contract.json"
M_PV2_REGISTRY = ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training/candidate_registry.json"
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_candidate_selection"
REQUIRED = (
    "selection_contract.json",
    "candidate_selection_inventory.json",
    "candidate_metrics_audit.json",
    "candidate_ranking.json",
    "selection_decision.json",
    "determinism_audit.json",
    "exception_registry.json",
    "validation_result.json",
    "checksums.sha256",
)
FAMILIES = ("family_a", "family_b", "family_c")
SEEDS = (11, 23, 47)
Q2_MODES = ("SOURCE_FREEZE", "LARGE_GAP", "STALE_SOURCE", "FLAT_EXACT", "REPUBLICATION_TO_FREEZE")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _candidate_map(metrics: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("candidate_key")): row for row in metrics.get("candidates", [])}


def _verify_checksums(checks: list[dict[str, Any]]) -> None:
    path = OUT / "checksums.sha256"
    if not path.is_file():
        check(checks, "checksums_sha256_present", False, str(path))
        return
    failures: list[str] = []
    listed: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            failures.append(f"malformed:{line}")
            continue
        listed.append(rel)
        target = ROOT / rel
        if not target.is_file() or sha(target) != digest:
            failures.append(rel)
    check(checks, "checksums_sha256_present", True, {"line_count": len(listed)})
    check(checks, "checksums_cover_existing_files", not failures, failures)
    check(checks, "checksums_include_required_evidence", all(str(OUT.relative_to(ROOT) / name) in listed for name in REQUIRED if name != "checksums.sha256"), listed)


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    check(checks, "required_evidence_present", not missing, missing)
    if missing:
        return {"schema_version": "M-PV3.1", "phase": "M-PV3", "gate": "BLOCKED", "ok": False, "failed_checks": ["required_evidence_present"], "checks": checks}
    contract = read(CONTRACT)
    frozen = read(OUT / "selection_contract.json")
    inventory = read(OUT / "candidate_selection_inventory.json")
    metrics = read(OUT / "candidate_metrics_audit.json")
    ranking = read(OUT / "candidate_ranking.json")
    decision = read(OUT / "selection_decision.json")
    determinism = read(OUT / "determinism_audit.json")
    exceptions = read(OUT / "exception_registry.json")
    generated_validation = read(OUT / "validation_result.json")
    registry = read(M_PV2_REGISTRY)

    check(checks, "contract_frozen_before_evaluation", contract.get("status") == "FROZEN_BEFORE_EVALUATION", contract.get("status"))
    check(checks, "selection_contract_copy_matches", frozen == contract, {"source_sha256": sha(CONTRACT), "copy_sha256": sha(OUT / "selection_contract.json")})
    check(checks, "contract_30s_only", contract.get("lane") == "30S_CANDIDATE_ONLY" and contract.get("upstream", {}).get("parallel_15s_lane") == "EXCLUDED_FROM_THIS_GATE", contract.get("lane"))
    check(checks, "m_pv2_registry_candidate_only", registry.get("phase") == "M-PV2" and registry.get("final_selection") is False and registry.get("selected_float_model") is False, {"phase": registry.get("phase"), "final_selection": registry.get("final_selection")})
    check(checks, "candidate_count_nine", inventory.get("authorized_candidate_count") == 9 and inventory.get("observed_candidate_count") == 9 and metrics.get("candidate_count", 9) == 9, {"inventory": inventory.get("observed_candidate_count"), "metrics": len(metrics.get("candidates", []))})
    expected_keys = {f"{family}/seed_{seed}" for family in FAMILIES for seed in SEEDS}
    actual_keys = {str(row.get("candidate_key")) for row in metrics.get("candidates", [])}
    check(checks, "all_family_seed_variants_reported", actual_keys == expected_keys and len(actual_keys) == 9, sorted(actual_keys))
    check(checks, "inventory_integrity_pass", inventory.get("all_inventory_checks_pass") is True, inventory.get("all_inventory_checks_pass"))
    check(checks, "inventory_no_d2_or_mr60", inventory.get("d2_access") is False and inventory.get("mr60_supervised_physiology") is False and inventory.get("training_invocations") == 0, {key: inventory.get(key) for key in ("d2_access", "mr60_supervised_physiology", "training_invocations")})

    provenance = inventory.get("provenance_audit", {})
    check(checks, "provenance_intact", provenance.get("provenance_intact") is True and provenance.get("status") == "PASS" and provenance.get("duplicate_model_input_count") == 0, provenance)
    check(checks, "d2_lock_respected", provenance.get("d2_forbidden_access_absent") is True and provenance.get("d2_rows") == 0, provenance)

    candidate_rows = list(metrics.get("candidates", []))
    safety_failures: dict[str, Any] = {}
    utility_rows: dict[str, Any] = {}
    for row in candidate_rows:
        key = str(row.get("candidate_key"))
        safety = row.get("safety", {})
        if safety.get("pass") is not True:
            safety_failures[key] = safety
        quality = row.get("validation", {}).get("D1_DEV_VAL_PLUS_Q2", {}).get("quality", {})
        gate = row.get("validation", {}).get("D1_DEV_VAL_PLUS_Q2", {}).get("consumer_quality_gate", {})
        modes = sorted(quality.get("per_corruption_mode", {}).keys())
        check(checks, f"q2_modes_{key}", modes == sorted(Q2_MODES), modes)
        check(checks, f"q2_invalid_false_acceptance_{key}", quality.get("hard_Q2_invalid_false_acceptance") == 0.0 and gate.get("invalid_input_physiology_exposed_count") == 0, {"quality": quality.get("hard_Q2_invalid_false_acceptance"), "exposed": gate.get("invalid_input_physiology_exposed_count")})
        check(checks, f"clean_false_rejection_{key}", quality.get("clean_false_rejection") is not None and float(quality.get("clean_false_rejection")) <= 0.10, quality.get("clean_false_rejection"))
        rr = row.get("validation", {}).get("D1_DEV_VAL", {}).get("rr", {})
        check(checks, f"rr_metrics_{key}", rr.get("status") == "DEFINED" and all(metric in rr for metric in ("MAE_bpm", "median_absolute_error_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm")), {metric: rr.get(metric) for metric in ("MAE_bpm", "median_absolute_error_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm")})
        if row.get("architecture") in ("family_b", "family_c"):
            breathing = row.get("validation", {}).get("D1_DEV_VAL", {}).get("breathing", {})
            check(checks, f"breathing_metrics_{key}", breathing.get("status") == "DEFINED" and breathing.get("recall") is not None and breathing.get("Brier") is not None and "calibration_ece" in breathing, breathing)
        else:
            check(checks, f"family_a_breathing_limitation_{key}", row.get("validation", {}).get("D1_DEV_VAL", {}).get("breathing", {}).get("status") == "NOT_SUPPORTED_F2_BREATHING_LOCATION_SUPPORT_NO", row.get("validation", {}).get("D1_DEV_VAL", {}).get("breathing"))
        utility_rows[key] = row.get("utility", {})
    check(checks, "all_candidate_safety_gates_pass", not safety_failures, safety_failures)
    check(checks, "all_candidates_evaluation_only", all(row.get("reproducibility", {}).get("checkpoint_sha256_match") is True for row in candidate_rows) and metrics.get("training_invocations") == 0 and metrics.get("retraining") is False, {"training_invocations": metrics.get("training_invocations"), "retraining": metrics.get("retraining")})

    check(checks, "deterministic_fresh_process_replay", determinism.get("fresh_process") is True and determinism.get("deterministic") is True and all(bool(value) for value in determinism.get("equalities", {}).values()), {"deterministic": determinism.get("deterministic"), "equalities": determinism.get("equalities")})
    check(checks, "ranking_not_validation_loss_only", ranking.get("combined_score") is None and ranking.get("selection_use") == "PARETO_AND_FROZEN_GATES_ONLY" and isinstance(ranking.get("policy"), Mapping), {"combined_score": ranking.get("combined_score"), "selection_use": ranking.get("selection_use")})
    allowed_results = {"SELECTED_FLOAT_MODEL", "MULTIPLE_ACCEPTABLE_CANDIDATES", "NO_SELECTION_READY"}
    result = decision.get("selection_result")
    check(checks, "selection_result_allowed", result in allowed_results, result)
    pareto = set(ranking.get("pareto_front_candidates", []))
    shortlist = set(decision.get("shortlist", []))
    check(checks, "decision_shortlist_matches_ranking", pareto == shortlist, {"ranking": sorted(pareto), "decision": sorted(shortlist)})
    if result == "SELECTED_FLOAT_MODEL":
        decision_consistent = len(shortlist) == 1 and decision.get("selected_candidate") in shortlist and decision.get("ready_for_m_pv4") is True
    elif result == "MULTIPLE_ACCEPTABLE_CANDIDATES":
        decision_consistent = len(shortlist) > 1 and decision.get("selected_candidate") is None and decision.get("ready_for_m_pv4") is False
    else:
        decision_consistent = decision.get("selected_candidate") is None and decision.get("ready_for_m_pv4") is False
    check(checks, "selection_decision_consistent", decision_consistent, {"result": result, "shortlist": sorted(shortlist), "selected": decision.get("selected_candidate"), "ready_for_m_pv4": decision.get("ready_for_m_pv4")})
    check(checks, "15s_lane_not_mixed", decision.get("15s_lane_status") == "EXCLUDED_NOT_WAITED_NOT_MERGED" and "15s" not in json.dumps(metrics, ensure_ascii=False).lower(), decision.get("15s_lane_status"))

    forbidden_hits: list[str] = []
    for path in OUT.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if lowered.endswith((".tflite", ".int8", ".pt", ".pth")) or "optimizer" in lowered or "epoch_checkpoint" in lowered:
            forbidden_hits.append(str(path.relative_to(ROOT)))
    check(checks, "no_forbidden_model_artifacts", not forbidden_hits, forbidden_hits)
    check(checks, "generated_validation_matches_gate", generated_validation.get("gate") == decision.get("gate") and generated_validation.get("selection_result") == result and generated_validation.get("training_invocations") == 0, {"generated": generated_validation.get("gate"), "decision": decision.get("gate")})
    check(checks, "exception_registry_invariants", exceptions.get("d2_access") is False and exceptions.get("mr60_supervised_physiology") is False and exceptions.get("training_invocations") == 0, exceptions)
    _verify_checksums(checks)

    # The M-PV3 source must not invoke the upstream training function.
    source = (ROOT / "scripts/mmwave_m_pv3_candidate_selection.py").read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
        training_calls = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"_train_one", "_save_checkpoint"}]
    except SyntaxError as exc:
        training_calls = [f"syntax:{exc}"]
    check(checks, "selection_script_has_no_training_or_checkpoint_write_call", not training_calls, training_calls)

    for item in checks:
        if not item["ok"]:
            failures.append(item["name"])
    gate = "PASS_WITH_LIMITATIONS" if not failures and decision.get("gate") != "BLOCKED" else "BLOCKED"
    return {
        "schema_version": "M-PV3.1",
        "phase": "M-PV3",
        "gate": gate,
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
        "selection_result": result,
        "candidate_count": len(candidate_rows),
        "selected_candidate": decision.get("selected_candidate"),
        "shortlist": decision.get("shortlist", []),
        "ready_for_m_pv4": decision.get("ready_for_m_pv4"),
        "d2_semantic_use": False,
        "mr60_supervised_use": False,
        "training_invocations": 0,
        "limitations": decision.get("limitations", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation_result_validator.json")
    args = parser.parse_args()
    try:
        result = validate()
        if args.write:
            (OUT / "validation_result_validator.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"gate": result["gate"], "ok": result["ok"], "failed_checks": result["failed_checks"], "selection_result": result["selection_result"]}, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 2
    except Exception as exc:
        print(json.dumps({"gate": "BLOCKED", "ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
