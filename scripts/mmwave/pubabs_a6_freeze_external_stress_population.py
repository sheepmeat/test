#!/usr/bin/env python3
"""PUBABS-A6: freeze PUBABS_C1_EXTERNAL_STRESS_V1 Layer1/Layer2 populations.

Eligibility for Layer 2 is derived ONLY from canonical A3R adapter_status == VALID.
No class/subject/position quality selection. No model inference. No D1 mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN_ADAPTER_SHA256 = (
    "cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446"
)
A3R_SESSION_RESULTS = (
    ROOT
    / "datasets/mmwave/manifests/PUBABS_A3R_c1_frozen_adapter_revalidation/session_results.json"
)
CONTRACT_ID = "PUBABS_C1_EXTERNAL_STRESS_V1"
LAYER1_ID = "PUBABS_C1_EXTERNAL_STRESS_V1__L1_AVAILABILITY_ALL77"
LAYER2_ID = "PUBABS_C1_EXTERNAL_STRESS_V1__L2_CONDITIONAL_VALID34"
SOURCE_DOI = "10.5281/zenodo.15032859"
SOURCE_DATASET = "zenodo_15032859_c1_data_zip"
EXPECTED_MD5 = "99067ac569e419fc122eef49635d72d0"

EXPECTED_PRESENT_VALID = {"N1": 1, "N2": 1, "N3": 9, "N4": 8, "N5": 6, "N6": 0}

TERMINAL_GUARDS = [
    "UNAVAILABLE_NEVER_CLASS_LABEL",
    "NO_SILENT_DROP_OF_FAIL_CLOSED",
    "ALL77_IS_LAYER1_DENOMINATOR",
    "LAYER2_CONDITIONAL_ON_ADAPTER_VALID_ONLY",
    "VALID_SUBSET_NOT_CORPUS_REPRESENTATIVE",
    "NO_D1_SUBSTITUTION",
    "NO_M_PV38_FINAL_SELECTION_USE",
    "NO_MODEL_SELECTION_CLAIM_FROM_EXTERNAL_STRESS",
    "NO_THRESHOLD_TUNING_ON_C1",
    "NO_CALIBRATION_TUNING_ON_C1",
    "NO_SCALER_REFIT_ON_C1",
    "NO_ADAPTER_RETUNING",
    "NO_LATER_WINDOW_RESCUE",
    "NO_CLASS_REBALANCING_IN_A6",
    "NO_POSTHOC_SUBJECT_SELECTION",
    "NO_POSTHOC_POSITION_SELECTION",
    "FUTURE_MODEL_INFERENCE_REQUIRES_SOL",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def make_session_id(subject: str, position: str) -> str:
    # Deterministic stable ID (not a mutable absolute path).
    return f"PUBABS_C1::{subject}::{position}"


def build_populations(a3r_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    layer1 = []
    for r in a3r_rows:
        subject = r["subject"]
        position = str(r["position"])
        status = r["status"]
        sid = make_session_id(subject, position)
        row = {
            "external_stress_session_id": sid,
            "canonical_source_path": r["zip_member"],
            "reporting_class": r["reporting_class"],
            "subject_or_empty_identity": subject,
            "position": position,
            "source_dataset": SOURCE_DATASET,
            "source_doi": SOURCE_DOI,
            "source_record_identity": r["zip_member"],
            "adapter_status": status,
            "fail_closed_code": r.get("fail_closed_code"),
            "layer1_member": True,
            "layer2_member": status == "VALID",
            "frozen_adapter_contract_hash": FROZEN_ADAPTER_SHA256,
            "layer2_semantics": (
                "CONDITIONAL_ON_ADAPTER_VALID" if status == "VALID" else None
            ),
            "selected_bin": int(r["selected_bin"]) if status == "VALID" and r.get("selected_bin") is not None else None,
            "selected_range_m_equiv": r.get("selected_range_m_equiv") if status == "VALID" else None,
            "r1t_10hz_sha256": r.get("r1t_10hz_sha256") if status == "VALID" else None,
            "r1_centered_sha256": r.get("r1_centered_sha256") if status == "VALID" else None,
            "train_zscore_trace_sha256": r.get("train_zscore_trace_sha256") if status == "VALID" else None,
            "median_dt": r.get("median_dt"),
            "median_source_hz": r.get("median_source_hz"),
            "max_gap": r.get("max_gap"),
        }
        layer1.append(row)

    layer1.sort(key=lambda x: x["external_stress_session_id"])
    layer2 = [dict(x) for x in layer1 if x["layer2_member"]]
    # Already sorted as subset of sorted layer1
    return layer1, layer2


def reconcile(layer1: list[dict], layer2: list[dict]) -> None:
    if len(layer1) != 77:
        raise SystemExit(f"A6_UPSTREAM_POPULATION_MISMATCH: layer1={len(layer1)}")
    if len(layer2) != 34:
        raise SystemExit(f"A6_UPSTREAM_POPULATION_MISMATCH: layer2={len(layer2)}")
    if any(not r["layer1_member"] for r in layer1):
        raise SystemExit("A6_UPSTREAM_POPULATION_MISMATCH: layer1 flag")
    if any(r["adapter_status"] != "VALID" for r in layer2):
        raise SystemExit("A6_UPSTREAM_POPULATION_MISMATCH: non-VALID in layer2")
    if any(r["fail_closed_code"] for r in layer2):
        raise SystemExit("A6_UPSTREAM_POPULATION_MISMATCH: fail code in layer2")
    fail = [r for r in layer1 if r["adapter_status"] != "VALID"]
    if len(fail) != 43:
        raise SystemExit(f"A6_UPSTREAM_POPULATION_MISMATCH: fail={len(fail)}")
    if any(r["layer2_member"] for r in fail):
        raise SystemExit("A6_UPSTREAM_POPULATION_MISMATCH: fail in layer2")
    absent_l2 = sum(1 for r in layer2 if r["reporting_class"] == "ABSENT")
    present_l2 = sum(1 for r in layer2 if r["reporting_class"] == "PRESENT")
    if absent_l2 != 9 or present_l2 != 25:
        raise SystemExit(
            f"A6_UPSTREAM_POPULATION_MISMATCH: L2 class {absent_l2}/{present_l2}"
        )
    present_valid = Counter(
        r["subject_or_empty_identity"]
        for r in layer2
        if r["reporting_class"] == "PRESENT"
    )
    for k, v in EXPECTED_PRESENT_VALID.items():
        got = present_valid.get(k, 0)
        if got != v:
            raise SystemExit(
                f"A6_UPSTREAM_POPULATION_MISMATCH: subject {k} expected {v} got {got}"
            )
    # Layer2 subset of Layer1 by ID
    l1_ids = {r["external_stress_session_id"] for r in layer1}
    for r in layer2:
        if r["external_stress_session_id"] not in l1_ids:
            raise SystemExit("A6_UPSTREAM_POPULATION_MISMATCH: L2 not subset")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--a3r-session-results", type=Path, default=A3R_SESSION_RESULTS)
    args = parser.parse_args()

    prop = ROOT / (
        "datasets/mmwave/manifests/PUBABS_A3C_corrective_contract_proposal/"
        "proposed_adapter_contract.json"
    )
    prop_sha = sha256_file(prop)
    if prop_sha != FROZEN_ADAPTER_SHA256:
        raise SystemExit("A6_ABORT_CONTRACT_HASH_DRIFT")

    a3r = json.loads(args.a3r_session_results.read_text())
    if len(a3r) != 77:
        raise SystemExit(f"A6_UPSTREAM_POPULATION_MISMATCH: a3r={len(a3r)}")

    # Build twice for determinism
    l1_a, l2_a = build_populations(a3r)
    l1_b, l2_b = build_populations(a3r)
    reconcile(l1_a, l2_a)
    if l1_a != l1_b or l2_a != l2_b:
        raise SystemExit("A6_DETERMINISM_FAILURE")

    layer1_doc = {
        "schema_version": "PUBABS-A6-LAYER1-POPULATION-V1",
        "layer_identity": LAYER1_ID,
        "contract_id": CONTRACT_ID,
        "semantics": "AVAILABILITY_INGRESS_SAFETY_ALL77",
        "denominator": 77,
        "sessions": l1_a,
    }
    layer2_doc = {
        "schema_version": "PUBABS-A6-LAYER2-POPULATION-V1",
        "layer_identity": LAYER2_ID,
        "contract_id": CONTRACT_ID,
        "semantics": "CONDITIONAL_ON_ADAPTER_VALID",
        "denominator": 34,
        "source_population_denominator": 77,
        "generalization_to_all77": "FORBIDDEN",
        "sessions": l2_a,
    }

    l1_bytes = canonical_json(layer1_doc)
    l2_bytes = canonical_json(layer2_doc)
    l1_sha = sha256_bytes(l1_bytes)
    l2_sha = sha256_bytes(l2_bytes)

    # Composition
    def class_counts(rows):
        return dict(Counter(r["reporting_class"] for r in rows))

    def subject_counts(rows):
        return dict(
            Counter(
                r["subject_or_empty_identity"]
                for r in rows
                if r["reporting_class"] == "PRESENT"
            )
        )

    def position_counts(rows):
        return {
            str(p): sum(1 for r in rows if r["position"] == str(p))
            for p in [str(i) for i in range(-5, 6)]
        }

    composition = {
        "schema_version": "PUBABS-A6-POPULATION-COMPOSITION-V1",
        "layer1": {
            "total": len(l1_a),
            "by_class": class_counts(l1_a),
            "by_adapter_status": dict(Counter(r["adapter_status"] for r in l1_a)),
            "fail_closed_codes": dict(
                Counter(
                    r["fail_closed_code"]
                    for r in l1_a
                    if r["fail_closed_code"]
                )
            ),
            "present_subjects_all_source": dict(
                Counter(
                    r["subject_or_empty_identity"]
                    for r in l1_a
                    if r["reporting_class"] == "PRESENT"
                )
            ),
            "positions": position_counts(l1_a),
        },
        "layer2": {
            "total": len(l2_a),
            "by_class": class_counts(l2_a),
            "present_subjects_valid": {
                **{k: 0 for k in EXPECTED_PRESENT_VALID},
                **subject_counts(l2_a),
            },
            "positions": position_counts(l2_a),
            "semantics": "CONDITIONAL_ON_ADAPTER_VALID",
        },
    }

    availability = {
        "schema_version": "PUBABS-A6-AVAILABILITY-SEMANTICS-V1",
        "layer1_denominator": 77,
        "layer2_denominator": 34,
        "layer2_metric_label_required": "CONDITIONAL_ON_ADAPTER_VALID",
        "fail_closed_count": 43,
        "adapter_status_as_model_feature": "FORBIDDEN",
        "UNAVAILABLE_NE_ABSENT": True,
        "UNAVAILABLE_NE_NORMAL": True,
        "UNAVAILABLE_NE_PHYSIOLOGICAL_NEGATIVE": True,
        "silent_drop_of_fail_closed": "FORBIDDEN",
        "later_window_rescue": "FORBIDDEN",
    }

    future = {
        "schema_version": "PUBABS-A6-FUTURE-AUTHORITY-V1",
        "future_external_model_inference": "REQUIRES_SEPARATE_SOL_AUTHORIZATION",
        "eligible_for_D1": False,
        "eligible_for_M_PV3_8_final_selection": False,
        "eligible_for_model_selection": False,
        "eligible_for_threshold_selection": False,
        "eligible_for_calibration_selection": False,
        "domain_role": "EXTERNAL_SAFETY_DOMAIN_STRESS_ONLY",
        "scale_risk": "HIGH",
        "TRAIN_zscore_refit_on_c1": "FORBIDDEN",
    }

    guards = {
        "schema_version": "PUBABS-A6-TERMINAL-GUARDS-V1",
        "guards": TERMINAL_GUARDS,
    }

    contract = {
        "schema_version": "PUBABS-A6-EXTERNAL-STRESS-CONTRACT-V1",
        "contract_id": CONTRACT_ID,
        "source_identity": {
            "doi": SOURCE_DOI,
            "dataset_id": SOURCE_DATASET,
            "official_data_zip_md5": EXPECTED_MD5,
            "payload_committed": False,
        },
        "source_population_count": 77,
        "layer1_identity": LAYER1_ID,
        "layer1_count": 77,
        "layer1_semantics": "AVAILABILITY_INGRESS_SAFETY_ALL77",
        "layer2_identity": LAYER2_ID,
        "layer2_count": 34,
        "layer2_semantics": "CONDITIONAL_ON_ADAPTER_VALID",
        "frozen_adapter_hash": FROZEN_ADAPTER_SHA256,
        "timestamp_contract": "R1T_MEASURED_TIMESTAMP_10HZ_V1",
        "range_contract": "C1_ROI_EXCLUDE_NEARFIELD28_DYNENERGY_UNWRAP_V1",
        "range_policy": "RG-S1",
        "historical_r1": "UNCHANGED",
        "eligibility_rule": "layer2_member_iff_canonical_A3R_adapter_status_eq_VALID",
        "denominator_rules": {
            "layer1": 77,
            "layer2": 34,
            "layer2_must_reference_source_population_77": True,
        },
        "fail_closed_semantics": availability,
        "subject_composition": composition["layer2"]["present_subjects_valid"],
        "position_composition": {
            "layer1": composition["layer1"]["positions"],
            "layer2": composition["layer2"]["positions"],
        },
        "class_composition": {
            "layer1": composition["layer1"]["by_class"],
            "layer2": composition["layer2"]["by_class"],
        },
        "domain_role": "EXTERNAL_SAFETY_DOMAIN_STRESS_ONLY",
        "scale_risk": "HIGH",
        "future_authority": future,
        "forbidden_uses": [
            "D1_FINAL_SELECTION_BOTH_CLASS_V1_population",
            "M_PV3_8_final_selection_evidence",
            "model_selection_winner_determination",
            "threshold_or_calibration_selection",
            "corpus_wide_metrics_from_VALID34_alone",
        ],
        "terminal_guards": TERMINAL_GUARDS,
        "layer1_manifest_sha256": l1_sha,
        "layer2_manifest_sha256": l2_sha,
        "a5_route": "A5_ROUTE_EXTERNAL_SAFETY_STRESS_ONLY",
        "post_a5_base_sha": args.base_sha,
    }
    contract_bytes = canonical_json(contract)
    contract_sha = sha256_bytes(contract_bytes)

    contract_receipt = {
        "schema_version": "PUBABS-A6-EXTERNAL-STRESS-CONTRACT-RECEIPT-V1",
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract_sha,
        "population_manifest_sha256": {
            "layer1_all77_population.json": l1_sha,
            "layer2_valid34_population.json": l2_sha,
        },
        "layer1_count": 77,
        "layer2_count": 34,
        "source_data_receipt": {
            "doi": SOURCE_DOI,
            "official_data_zip_md5": EXPECTED_MD5,
            "payload_committed": False,
        },
        "frozen_adapter_sha256": FROZEN_ADAPTER_SHA256,
        "post_A5_base": args.base_sha,
    }

    population_receipt = {
        "schema_version": "PUBABS-A6-POPULATION-FREEZE-RECEIPT-V1",
        "contract_id": CONTRACT_ID,
        "layer1_identity": LAYER1_ID,
        "layer2_identity": LAYER2_ID,
        "layer1_manifest_sha256": l1_sha,
        "layer2_manifest_sha256": l2_sha,
        "layer1_count": 77,
        "layer2_count": 34,
        "ordering_key": "external_stress_session_id",
    }

    repro = {
        "schema_version": "PUBABS-A6-REPRODUCIBILITY-RECEIPT-V1",
        "builds": 2,
        "identical_session_ordering": True,
        "identical_session_ids": True,
        "identical_membership_flags": True,
        "identical_fail_codes": True,
        "identical_tensor_hashes": True,
        "identical_manifest_sha256": True,
        "layer1_manifest_sha256": l1_sha,
        "layer2_manifest_sha256": l2_sha,
        "contract_sha256": contract_sha,
    }

    a6_gate = "A6_EXTERNAL_STRESS_CONTRACT_FROZEN_WITH_LIMITATIONS"
    next_rec = "RECOMMEND_EXTERNAL_STRESS_INFERENCE_DESIGN"

    validation = {
        "schema_version": "PUBABS-A6-VALIDATION-RESULT-V1",
        "phase": "PUBABS-A6",
        "date": "2026-08-26",
        "base_sha": args.base_sha,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract_sha,
        "frozen_adapter_sha256": FROZEN_ADAPTER_SHA256,
        "layer1_count": 77,
        "layer2_count": 34,
        "upstream_reconciliation": "EXACT",
        "determinism": True,
        "model_inference": "NOT_EXECUTED",
        "d1_unchanged": True,
        "final_membership_created": False,
        "m_pv38_status": "RESOURCE_BLOCKED_CLOSED",
        "m_pv4": "UNAUTHORIZED",
        "d2": "LOCKED",
        "adapter_rules_unchanged": True,
        "historical_r1_unchanged": True,
        "scale_risk_limitation": "HIGH",
        "domain_role": "EXTERNAL_SAFETY_DOMAIN_STRESS_ONLY",
        "a6_gate": a6_gate,
        "next_phase_recommendation": next_rec,
        "report": "docs/mmwave/20260826_SafeNest_mmWave_PUBABS_A6_C1_External_Stress_Contract_Population_Freeze_01.md",
        "manifest_dir": "datasets/mmwave/manifests/PUBABS_A6_c1_external_stress_freeze/",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "layer1_all77_population.json").write_bytes(l1_bytes)
    (args.out_dir / "layer2_valid34_population.json").write_bytes(l2_bytes)
    (args.out_dir / "external_stress_contract.json").write_bytes(contract_bytes)
    for name, obj in [
        ("population_composition.json", composition),
        ("availability_semantics.json", availability),
        ("future_authority.json", future),
        ("terminal_guards.json", guards),
        ("external_stress_contract_receipt.json", contract_receipt),
        ("population_freeze_receipt.json", population_receipt),
        ("reproducibility_receipt.json", repro),
        ("validation_result.json", validation),
    ]:
        (args.out_dir / name).write_text(json.dumps(obj, indent=2) + "\n")

    print(
        json.dumps(
            {
                "a6_gate": a6_gate,
                "next_phase_recommendation": next_rec,
                "contract_sha256": contract_sha,
                "layer1_sha256": l1_sha,
                "layer2_sha256": l2_sha,
                "present_valid_subjects": composition["layer2"]["present_subjects_valid"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
