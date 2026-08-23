#!/usr/bin/env python3
"""Focused fail-closed validator for the M-PV2 bounded candidate phase."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "config/mmwave/m_pv2_candidate_training_contract.json"
M_PV1_MANIFEST = ROOT / "datasets/mmwave/manifests/M-PV1_public_multidomain_contract/m_pv2_example_manifest.json"
M_PV1_VALIDATION = ROOT / "datasets/mmwave/manifests/M-PV1_public_multidomain_contract/validation_result.json"
M_PV1_D2 = ROOT / "datasets/mmwave/manifests/M-PV1_public_multidomain_contract/d2_lock_audit.json"
OUT = ROOT / "datasets/mmwave/manifests/M-PV2_candidate_training"


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


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    contract = read(CONTRACT)
    m_pv1 = read(M_PV1_MANIFEST)
    m_pv1_validation = read(M_PV1_VALIDATION)
    d2 = read(M_PV1_D2)
    prerequisite = read(OUT / "prerequisite_audit.json")
    membership = read(OUT / "membership_audit.json")
    tensor = read(OUT / "tensor_materialization_audit.json")
    registry = read(OUT / "candidate_registry.json")
    metrics = read(OUT / "metrics_by_source.json")
    breathing = read(OUT / "breathing_metrics.json")
    rr = read(OUT / "rr_metrics.json")
    quality = read(OUT / "quality_metrics.json")
    degeneracy = read(OUT / "degeneracy_audit.json")
    determinism = read(OUT / "determinism_audit.json")
    contract_snapshot = read(OUT / "contract_snapshot.json")

    check(checks, "contract_frozen_before_training", contract.get("status") == "FROZEN_BEFORE_TRAINING", contract.get("status"))
    check(checks, "contract_snapshot_matches_contract_id", contract_snapshot.get("contract_id") == contract.get("contract_id"), {"contract": contract.get("contract_id"), "snapshot": contract_snapshot.get("contract_id")})
    check(checks, "m_pv1_corrective_schema", m_pv1_validation.get("schema_version") == "M-PV1.2_CORRECTIVE_ALIGNMENT", m_pv1_validation.get("schema_version"))
    check(checks, "m_pv1_gate_ready", m_pv1_validation.get("ok") is True and m_pv1_validation.get("m_pv1_ready_for_m_pv2") is True, {"ok": m_pv1_validation.get("ok"), "ready": m_pv1_validation.get("m_pv1_ready_for_m_pv2")})
    check(checks, "m_pv1_model_ready_count", m_pv1.get("model_ready_example_count") == 562 and m_pv1.get("unique_model_input_contexts") == 562, {"model_ready": m_pv1.get("model_ready_example_count"), "unique": m_pv1.get("unique_model_input_contexts")})
    check(checks, "m_pv1_duplicate_overlays_zero", m_pv1.get("duplicate_target_overlay_count") == 0, m_pv1.get("duplicate_target_overlay_count"))

    rows = m_pv1.get("examples", [])
    ready = [row for row in rows if row.get("model_ready") is True]
    source_counts = {source: sum(row.get("source_id") == source for row in ready) for source in ("D0", "D1")}
    check(checks, "membership_source_counts", source_counts == {"D0": 318, "D1": 244}, source_counts)
    check(checks, "membership_model_input_ids_unique", len({row.get("model_input_id") for row in ready}) == len(ready), len(ready))
    check(checks, "d0_train_only", all(row.get("source_id") != "D0" or row.get("split") == "TRAIN" for row in ready), sorted({row.get("split") for row in ready if row.get("source_id") == "D0"}))
    check(checks, "d1_split_subject_disjoint", len({row.get("subject_id") for row in ready if row.get("source_id") == "D1" and row.get("split") == "D1_DEV_TRAIN"} & {row.get("subject_id") for row in ready if row.get("source_id") == "D1" and row.get("split") == "D1_DEV_VAL"}) == 0, "subject intersection")
    check(checks, "d2_m_pv1_locked", d2.get("semantic_access") in ("NO", False) and d2.get("model_inference_count") == 0 and d2.get("selection_use") == "NO", {"semantic_access": d2.get("semantic_access"), "model_inference_count": d2.get("model_inference_count"), "selection_use": d2.get("selection_use")})

    counts = tensor.get("counts", {})
    check(checks, "tensor_lineage_count", counts.get("model_ready_unique") == 562 and counts.get("by_source") == {"D0": 318, "D1": 244}, {"model_ready_unique": counts.get("model_ready_unique"), "by_source": counts.get("by_source")})
    check(checks, "tensor_lineage_duplicate_zero", counts.get("duplicate_target_overlays") == 0 and membership.get("duplicate_model_input_count") == 0, {"tensor": counts.get("duplicate_target_overlays"), "membership": membership.get("duplicate_model_input_count")})
    check(checks, "tensor_cache_not_committed", tensor.get("tensor_cache_committed") is False and tensor.get("raw_waveform_payloads_committed") is False, {"tensor_cache": tensor.get("tensor_cache_committed"), "raw": tensor.get("raw_waveform_payloads_committed")})
    check(checks, "d0_val_not_used", prerequisite.get("role_contract", {}).get("d0_val_m_pv2_use") == "NOT_AUTHORIZED", prerequisite.get("role_contract", {}).get("d0_val_m_pv2_use"))

    candidates = registry.get("candidates", [])
    expected_keys = {(family, seed) for family in ("family_a", "family_b", "family_c") for seed in (11, 23, 47)}
    actual_keys = {(entry.get("family"), entry.get("seed")) for entry in candidates}
    check(checks, "all_authorized_family_seed_runs_present", actual_keys == expected_keys and len(candidates) == 9, sorted(actual_keys))
    check(checks, "no_final_selection", registry.get("final_selection") is False and registry.get("selected_float_model") is False and all(entry.get("selection_status") == "NOT_SELECTED" for entry in candidates), {"final_selection": registry.get("final_selection"), "selected_float_model": registry.get("selected_float_model")})
    checkpoint_ok = True
    checkpoint_details: list[str] = []
    for entry in candidates:
        path = ROOT / str(entry.get("checkpoint", {}).get("path", ""))
        valid_path = path.is_file() and path.is_relative_to(ROOT / "models/mmwave/m_pv2")
        if not valid_path:
            checkpoint_ok = False
            checkpoint_details.append(str(path))
    check(checks, "compact_checkpoint_paths", checkpoint_ok, checkpoint_details or "all present under models/mmwave/m_pv2")
    check(checks, "no_optimizer_or_all_epoch_artifacts", not any("optimizer" in str(path).lower() or "epoch" in str(path).lower() for path in (ROOT / "models/mmwave/m_pv2").rglob("*")), "model directory scan")

    for key, group_values in metrics.items():
        check(checks, f"metrics_present_{key}", isinstance(group_values, Mapping) and bool(group_values), sorted(group_values) if isinstance(group_values, Mapping) else group_values)
    breathing_candidates = [value for key, value in breathing.items() if key.startswith("family_b/") or key.startswith("family_c/")]
    breathing_defined = [value for candidate in breathing_candidates for name, value in candidate.items() if name in ("D0_TRAIN_OBSERVE", "D1_DEV_VAL") and value.get("status") == "DEFINED"]
    check(checks, "trace_breathing_metric_defined", len(breathing_defined) >= 6, len(breathing_defined))
    d1_absent = [value.get("D1_DEV_VAL", {}).get("absent_count") for value in breathing_candidates]
    check(checks, "d1_absent_class_reported_zero", all(value == 0 for value in d1_absent), d1_absent)
    rr_defined = [value for key, value in rr.items() if value.get("D1_DEV_VAL", {}).get("status") == "DEFINED"]
    check(checks, "rr_metrics_meaningful", len(rr_defined) == 9 and all(value.get("D1_DEV_VAL", {}).get("eligible_count", 0) > 0 for value in rr_defined), len(rr_defined))
    quality_fa = [value.get("D1_DEV_VAL", {}).get("hard_Q2_invalid_false_acceptance") for value in quality.values()]
    check(checks, "q2_fail_closed_evaluated", all(value is not None and value <= 0.5 for value in quality_fa), quality_fa)
    check(checks, "degeneracy_pass", all(value.get("fail_closed") is True for value in degeneracy.values()), {key: value.get("fail_closed") for key, value in degeneracy.items()})
    check(checks, "deterministic_replay", determinism.get("fresh_process") is True and determinism.get("canonical_parameter_sha256_equal") is True and determinism.get("deterministic") is True, {key: determinism.get(key) for key in ("fresh_process", "canonical_parameter_sha256_equal", "deterministic")})

    artifact_hits: list[str] = []
    for path in [*(ROOT / "models/mmwave/m_pv2").rglob("*"), *OUT.rglob("*")]:
        lowered = path.name.lower()
        if any(token in lowered for token in ("selected_float_model", "optimizer", "epoch_")) or lowered.endswith((".tflite", ".int8")):
            artifact_hits.append(path.relative_to(ROOT).as_posix())
    check(checks, "forbidden_artifact_scan", not artifact_hits, artifact_hits)

    for item in checks:
        if not item["ok"]:
            failures.append(item["name"])
    result = {
        "schema_version": "M-PV2.1",
        "phase": "M-PV2",
        "gate": "PASS_WITH_LIMITATIONS" if not failures else "BLOCKED",
        "ok": not failures,
        "failed_checks": failures,
        "checks": checks,
        "candidate_count": len(candidates),
        "final_selection": False,
        "selected_float_model": False,
        "d2_semantic_use": False,
        "mr60_supervised_use": False,
        "m_pv2_ready_for_m_pv3": not failures,
        "limitations": ["D0 VAL was not used because frozen M-PV1 model-ready membership is TRAIN-only.", "D1 model-ready membership has no ABSENT examples.", "Event F1 remains deferred to M-PV3 or later."],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation_result_validator.json")
    args = parser.parse_args()
    try:
        result = validate()
        if args.write:
            (OUT / "validation_result_validator.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"gate": result["gate"], "ok": result["ok"], "failed_checks": result["failed_checks"]}, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 2
    except Exception as exc:
        print(json.dumps({"gate": "BLOCKED", "ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
