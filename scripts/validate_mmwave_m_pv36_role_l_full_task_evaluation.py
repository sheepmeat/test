#!/usr/bin/env python3
"""Fail-closed validator for the M-PV3.6 ROLE_L_FULL_TASK cards."""

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

CONTRACT = ROOT / "config/mmwave/m_pv36_role_based_evaluation_contract.json"
PV3_CONTRACT = ROOT / "config/mmwave/m_pv3_selection_contract.json"
PV3_SELECTION = ROOT / "datasets/mmwave/manifests/M-PV3_candidate_selection/selection_decision.json"
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_6_role_L_full_task_evaluation"
IDENTITY = "MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1"
SCHEMA = "M-PV3.6.2_CORRECTIVE"
ROLE = "ROLE_L_FULL_TASK"
FAMILIES = ("family_b", "family_c")
SEEDS = (11, 23, 47)
Q2_MODES = ("FLAT_EXACT", "SOURCE_FREEZE", "STALE_SOURCE", "LARGE_GAP", "JITTER_PLUS_LARGE_GAP", "REPUBLICATION_TO_FREEZE")
REQUIRED = ("role_l_full_task_evaluation_manifest.json", "breathing_card.json", "rr_card.json", "quality_safety_card.json", "stability_card.json", "footprint_card.json", "limitations.json", "validation_result.json", "checksums.sha256")


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


def _keys(rows: list[Mapping[str, Any]]) -> set[str]:
    return {str(row.get("candidate_key")) for row in rows}


def _verify_checksums(checks: list[dict[str, Any]]) -> None:
    checksum_path = OUT / "checksums.sha256"
    failures: list[str] = []
    listed: list[str] = []
    if checksum_path.is_file():
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                digest, relative = line.split("  ", 1)
            except ValueError:
                failures.append(f"malformed:{line}")
                continue
            listed.append(relative)
            target = ROOT / relative
            if not target.is_file() or sha(target) != digest:
                failures.append(relative)
    check(checks, "checksums_cover_listed_files", checksum_path.is_file() and not failures, {"listed": listed, "failures": failures})
    required_rel = {_rel(OUT / name) for name in REQUIRED if name != "checksums.sha256"}
    check(checks, "checksums_cover_required_cards", required_rel.issubset(set(listed)), sorted(required_rel - set(listed)))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _metric(row: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = row
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    missing = [name for name in REQUIRED if not (OUT / name).is_file()]
    check(checks, "required_role_card_artifacts_present", not missing, missing)
    if missing:
        return {"schema_version": "M-PV3.6.2_ROLE_L_FULL_TASK_EVALUATION", "phase": "M-PV3.6", "role_id": ROLE, "gate": "BLOCKED", "ok": False, "failed_checks": ["required_role_card_artifacts_present"], "checks": checks}
    contract = read(CONTRACT)
    pv3_contract = read(PV3_CONTRACT)
    pv3_selection = read(PV3_SELECTION)
    manifest = read(OUT / "role_l_full_task_evaluation_manifest.json")
    breathing = read(OUT / "breathing_card.json")
    rr = read(OUT / "rr_card.json")
    quality_safety = read(OUT / "quality_safety_card.json")
    stability = read(OUT / "stability_card.json")
    footprint = read(OUT / "footprint_card.json")
    limitations = read(OUT / "limitations.json")
    validation = read(OUT / "validation_result.json")
    checksums = read(OUT / "checksums.json")

    check(checks, "authoritative_contract_identity_unchanged", contract.get("contract_id") == IDENTITY and contract.get("schema_version") == SCHEMA and contract.get("phase_mode") == "CONTRACT_DESIGN_ONLY", {"contract_id": contract.get("contract_id"), "schema_version": contract.get("schema_version"), "phase_mode": contract.get("phase_mode")})
    check(checks, "role_manifest_identity", manifest.get("contract_id") == IDENTITY and manifest.get("role_id") == ROLE and manifest.get("contract_schema_version") == SCHEMA, {key: manifest.get(key) for key in ("contract_id", "role_id", "contract_schema_version")})
    check(checks, "contract_source_hash_unchanged", manifest.get("contract_source_sha256") == sha(CONTRACT) and checksums.get("inputs", {}).get(_rel(CONTRACT)) == sha(CONTRACT), {"manifest": manifest.get("contract_source_sha256"), "actual": sha(CONTRACT)})
    check(checks, "pr134_merge_baseline_recorded", manifest.get("pr134_merge_sha") == "443d45d408829becc6a4e4db71bd6d9152c0d41d", manifest.get("pr134_merge_sha"))
    check(checks, "execution_is_role_card_only", manifest.get("execution_mode") == "ROLE_CARD_POPULATION_ONLY" and manifest.get("baseline_contract_immutable") is True, {"mode": manifest.get("execution_mode"), "immutable": manifest.get("baseline_contract_immutable")})

    expected_keys = {f"{family}/seed_{seed}" for family in FAMILIES for seed in SEEDS}
    included = set(manifest.get("included_candidates", []))
    check(checks, "role_membership_only_family_b_c", included == expected_keys and manifest.get("role_membership") == "M_PV3_FAMILY_B_AND_FAMILY_C_ONLY", sorted(included))
    check(checks, "excluded_roles_explicit", all(token in " ".join(manifest.get("excluded_roles", [])) for token in ("Family A", "M-PV3.5", "15s")), manifest.get("excluded_roles"))
    check(checks, "governed_membership_unchanged", manifest.get("governed_membership", {}).get("record_count") == 59 and manifest.get("governed_membership", {}).get("eligible_present") == 57 and manifest.get("governed_membership", {}).get("eligible_absent") == 0 and manifest.get("governed_membership", {}).get("ambiguous") == 2 and manifest.get("governed_membership", {}).get("split_change") is False and manifest.get("governed_membership", {}).get("label_regeneration") is False, manifest.get("governed_membership"))
    check(checks, "m_pv3_selection_unchanged", manifest.get("m_pv3_baseline", {}).get("selection_result") == "NO_SELECTION_READY" and pv3_selection.get("selection_result") == "NO_SELECTION_READY" and manifest.get("winner_selected") is False and manifest.get("best_seed_selected") is False, {"manifest": manifest.get("m_pv3_baseline"), "selection": pv3_selection.get("selection_result")})

    expected_guards = {"present_recall_min": 0.95, "brier_max": 0.05, "rr_mae_bpm_max": 5.0, "rr_within_2_bpm_min": 0.4, "rr_within_4_bpm_min": 0.6, "rr_within_6_bpm_min": 0.75}
    check(checks, "m_pv3_utility_guards_unchanged", contract.get("predecessors", {}).get("m_pv3", {}).get("preserved_30s_utility_guards") == expected_guards and manifest.get("m_pv3_baseline", {}).get("utility_guards", {}).get("m_pv3_utility_guards") == expected_guards and manifest.get("m_pv3_baseline", {}).get("utility_guards", {}).get("thresholds_modified") is False and pv3_contract.get("utility_gates", {}).get("rr", {}).get("mae_bpm_max") == expected_guards["rr_mae_bpm_max"], manifest.get("m_pv3_baseline", {}).get("utility_guards"))

    candidate_breathing = breathing.get("candidates", [])
    candidate_rr = rr.get("candidates", [])
    candidate_q = quality_safety.get("candidates", [])
    candidate_f = footprint.get("candidates", [])
    check(checks, "all_six_b_c_candidates_in_cards", all(_keys(rows) == expected_keys for rows in (candidate_breathing, candidate_rr, candidate_q, candidate_f)), {"breathing": sorted(_keys(candidate_breathing)), "rr": sorted(_keys(candidate_rr)), "quality": sorted(_keys(candidate_q)), "footprint": sorted(_keys(candidate_f))})

    for row in candidate_breathing:
        key = str(row.get("candidate_key"))
        metrics = row.get("metrics", {})
        check(checks, f"breathing_metrics_{key}", metrics.get("eligible_count") == 57 and metrics.get("present_count") == 57 and metrics.get("absent_count") == 0 and metrics.get("absent_recall", {}).get("status") == "NOT_APPLICABLE" and metrics.get("ece", {}).get("status") == "NOT_APPLICABLE" and metrics.get("calibration_fitting") is False, {key: {field: metrics.get(field) for field in ("eligible_count", "present_count", "absent_count", "recall", "precision", "F1", "Brier", "absent_recall", "ece")}})
        check(checks, f"breathing_baseline_consistency_{key}", row.get("baseline_consistency", {}).get("status") == "PASS", row.get("baseline_consistency"))
    for row in candidate_rr:
        key = str(row.get("candidate_key"))
        metrics = row.get("metrics", {})
        guard = row.get("frozen_guard_comparison", {})
        check(checks, f"rr_metrics_{key}", metrics.get("status") == "DEFINED" and all(metrics.get(name) is not None for name in ("MAE_bpm", "median_absolute_error_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm")) and guard.get("thresholds_modified") is False and guard.get("selection_use") is False, {key: {field: metrics.get(field) for field in ("MAE_bpm", "median_absolute_error_bpm", "within_2_bpm", "within_4_bpm", "within_6_bpm")}})
        check(checks, f"rr_baseline_consistency_{key}", row.get("baseline_consistency", {}).get("status") == "PASS", row.get("baseline_consistency"))

    check(checks, "quality_safety_classification", quality_safety.get("q2_scope") == "SYNTHETIC_ONLY" and quality_safety.get("runtime_precedence") == ["PRESENCE", "QUALITY_OR_AVAILABILITY", "PHYSIOLOGY"] and quality_safety.get("safety_class") == "A_NON_COMPENSABLE" and quality_safety.get("all_safety_pass") is True, {key: quality_safety.get(key) for key in ("q2_scope", "runtime_precedence", "safety_class", "all_safety_pass")})
    for row in candidate_q:
        key = str(row.get("candidate_key"))
        safety = row.get("safety", {})
        quality = row.get("quality", {})
        check(checks, f"safety_fail_closed_{key}", safety.get("q2_invalid_false_acceptance") == 0.0 and safety.get("invalid_to_physiology_transition") == 0 and safety.get("physiology_emitted_after_invalid") == 0 and safety.get("fail_closed_preservation") is True and safety.get("input_unavailable_emissions") == {"PRESENT": 0, "ABSENT": 0, "NORMAL": 0, "APNEA": 0} and safety.get("pass") is True, {key: safety})
        check(checks, f"quality_q2_modes_{key}", sorted(quality.get("diagnostic_coverage", [])) == sorted(Q2_MODES) and quality.get("q2_metrics_classification") == "CLASS_A_ONLY_NON_COMPENSABLE" and quality.get("selection_use") is False, {key: quality})

    for family in FAMILIES:
        card = stability.get(family, {})
        seed_results = card.get("seed_results", {})
        check(checks, f"stability_all_seeds_{family}", set(int(seed) for seed in seed_results) == set(SEEDS) and card.get("all_frozen_seeds_reported") is True and card.get("post_hoc_seed_selection") is False and card.get("selection_use") is False, {"seed_results": sorted(seed_results), "all": card.get("all_frozen_seeds_reported")})
        check(checks, f"stability_subject_results_{family}", all(set(card.get("per_subject_results", {}).get(str(seed), {})) == {"D1_PERSON_03", "D1_PERSON_09", "D1_PERSON_11"} for seed in SEEDS), card.get("per_subject_results"))
        summaries = card.get("summary", {})
        required_summary = ("mean", "population_std", "min", "max", "worst_seed", "best_seed")
        check(checks, f"stability_summary_{family}", bool(summaries) and all(all(field in summary for field in required_summary) and summary.get("selection_use") is False and summary.get("all_frozen_seeds_present") is True for summary in summaries.values() if isinstance(summary, Mapping) and "status" not in summary), sorted(summaries))

    check(checks, "footprint_engineering_only", footprint.get("pi_latency_measured") is False and footprint.get("raspberry_pi_claim") is False and footprint.get("selection_use") is False, {key: footprint.get(key) for key in ("pi_latency_measured", "raspberry_pi_claim", "selection_use")})
    for row in candidate_f:
        key = str(row.get("candidate_key"))
        check(checks, f"footprint_fields_{key}", all(isinstance(row.get(field), int) and row.get(field) > 0 for field in ("parameter_count", "model_bytes_checkpoint", "macs_estimate", "flops_estimate", "deterministic_memory_estimate_bytes")) and row.get("hardware_latency") == "NOT_MEASURED" and row.get("raspberry_pi_claim") is False and row.get("selection_use") is False, {key: row})

    limitation_codes = {item.get("code") for item in limitations.get("limitations", []) if isinstance(item, Mapping)}
    required_codes = {"D1_ABSENT_LIMITATION", "D2_LOCKED", "MR60_SUPERVISED_FORBIDDEN", "NO_CALIBRATION", "NO_INT8_TFLITE", "NO_PI_BENCHMARK", "NO_SELECTION", "Q2_SYNTHETIC_ONLY"}
    check(checks, "limitations_explicit", required_codes.issubset(limitation_codes) and limitations.get("sufficiently_evidenced_for_future_selection_consideration") is False, sorted(limitation_codes))
    check(checks, "no_combined_score_or_winner", manifest.get("combined_score") is None and manifest.get("winner_selected") is False and manifest.get("best_seed_selected") is False and manifest.get("m_pv4_recommended") is False, {key: manifest.get(key) for key in ("combined_score", "winner_selected", "best_seed_selected", "m_pv4_recommended")})
    check(checks, "execution_safety_locks", validation.get("gate") == "PASS_WITH_LIMITATIONS" and validation.get("ok") is True and validation.get("no_training") is True and validation.get("no_contract_modification") is True and validation.get("no_d2") is True and validation.get("no_mr60_supervised_physiology") is True and validation.get("no_calibration") is True and validation.get("no_threshold_change") is True and validation.get("no_int8_tflite") is True and validation.get("no_pi_benchmark") is True, validation)

    forbidden_artifacts = [str(path.relative_to(ROOT)) for path in OUT.rglob("*") if path.is_file() and path.suffix.lower() in {".pt", ".pth", ".tflite", ".int8"}]
    check(checks, "no_model_or_conversion_artifacts_in_role_evidence", not forbidden_artifacts, forbidden_artifacts)
    try:
        source = (ROOT / "scripts/mmwave_m_pv36_role_l_full_task_evaluation.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        training_calls = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"_train_one", "_save_checkpoint"}]
    except (OSError, SyntaxError) as exc:
        training_calls = [str(exc)]
    check(checks, "role_runner_has_no_training_or_checkpoint_write_call", not training_calls, training_calls)
    _verify_checksums(checks)

    failures = [item["name"] for item in checks if not item["ok"]]
    return {
        "schema_version": "M-PV3.6.2_ROLE_L_FULL_TASK_EVALUATION",
        "phase": "M-PV3.6",
        "contract_id": IDENTITY,
        "role_id": ROLE,
        "gate": "PASS_WITH_LIMITATIONS" if not failures else "BLOCKED",
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
        "evaluated_candidate_count": len(candidate_breathing),
        "sufficiently_evidenced_for_future_selection_consideration": limitations.get("sufficiently_evidenced_for_future_selection_consideration"),
        "no_model_selected": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation_result_validator.json")
    args = parser.parse_args()
    try:
        result = validate()
        if args.write:
            (OUT / "validation_result_validator.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"gate": result["gate"], "ok": result["ok"], "failed_checks": result["failed_checks"], "role": result["role_id"]}, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 2
    except Exception as exc:
        print(json.dumps({"gate": "BLOCKED", "ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
