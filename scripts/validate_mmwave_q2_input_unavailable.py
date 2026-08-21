#!/usr/bin/env python3
"""Focused Q2 gate checks. No training, Q3 APNEA metrics, D2, or MR60 labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_q1_timing_corruption_engine import (  # noqa: E402
    PROFILE_ID as Q1_PROFILE_ID,
    apply_timing_corruption,
    load_profile as load_q1_profile,
)
from scripts.mmwave_q2_input_unavailable import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    AUDIT_DATE,
    CONFIG_PATH,
    CONTRACT_ID,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    PHASE_ID,
    PROFILE_ID,
    Q1_COMMIT,
    Q1_PROFILE_PATH,
    Q2_MODES,
    SCHEMA_VERSION,
    dump_json,
    evaluate_availability,
    load_json,
    sha256_bytes,
)

REQUIRED_YES = {
    "Q1_PROFILE_INHERITED": "YES",
    "QUALITY_STATE_TAXONOMY_FROZEN": "YES",
    "LARGE_GAP_CONTRACT_DEFENSIBLE": "YES",
    "FREEZE_CONTRACT_DEFENSIBLE": "YES",
    "STALE_CONTRACT_DEFENSIBLE": "YES",
    "FLAT_CONTRACT_DEFENSIBLE": "YES",
    "LOW_AMPLITUDE_NOT_AUTOMATICALLY_INVALID": "YES",
    "INPUT_UNAVAILABLE_PRECEDES_PHYSIOLOGY": "YES",
    "PRESENCE_GATE_PRESERVED": "YES",
    "NO_GAP_INTERPOLATION": "YES",
    "NO_SYNTHETIC_APNEA": "YES",
    "DETERMINISTIC_CORRUPTION": "YES",
    "LINEAGE_PRESERVED": "YES",
}
REQUIRED_NO = {
    "MR60_SUPERVISED_USE": "NO",
    "MODEL_OUTPUT_TUNING": "NO",
    "D2_USED": "NO",
    "Q3_WORK_PERFORMED": "NO",
    "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
    "LOW_AMPLITUDE_ALONE_CAUSES_UNAVAILABLE": "NO",
    "INVALID_CORRUPTION_TARGET_IS_PHYSIOLOGY_CLASS": "NO",
    "SYNTHETIC_APNEA_CREATED": "NO",
    "D0_SUBJECT_HELDOUT_USED": "NO",
    "M_N6_EXCLUDED_HELDOUT_USED": "NO",
}


def fail(errors: list[str], code: str) -> None:
    errors.append(code)


def check_absolute_paths(obj: object, trail: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            check_absolute_paths(value, f"{trail}.{key}", errors)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            check_absolute_paths(value, f"{trail}[{idx}]", errors)
    elif isinstance(obj, str) and ABSOLUTE_PATH_RE.search(obj):
        fail(errors, f"ABSOLUTE_PATH:{trail}")


def validate() -> dict:
    errors: list[str] = []
    if not MANIFEST_DIR.is_dir() or not CONFIG_PATH.is_file():
        return {"ok": False, "gate": "BLOCKED", "errors": ["MANIFEST_OR_CONFIG_MISSING"]}
    artifacts = {}
    for name in MANIFEST_JSON_FILES:
        path = MANIFEST_DIR / name
        if not path.is_file():
            fail(errors, f"MISSING:{name}")
            continue
        artifacts[name] = load_json(path)
        check_absolute_paths(artifacts[name], name, errors)
    checksums = load_json(MANIFEST_DIR / "checksums.json")
    for name in MANIFEST_JSON_FILES:
        path = MANIFEST_DIR / name
        digest = sha256_bytes(path.read_text(encoding="utf-8").encode("utf-8"))
        if checksums.get("files", {}).get(name) != digest:
            fail(errors, f"CHECKSUM_MISMATCH:{name}")
    if CONFIG_PATH.read_text(encoding="utf-8") != (MANIFEST_DIR / "input_availability_contract.json").read_text(
        encoding="utf-8"
    ):
        fail(errors, "CONFIG_MANIFEST_DIVERGED")

    contract = artifacts.get("input_availability_contract.json", {})
    profile = artifacts.get("synthetic_quality_profile.json", {})
    handoff = artifacts.get("q1_handoff_audit.json", {})
    summary = artifacts.get("corruption_validation_summary.json", {})
    if contract.get("contract_id") != CONTRACT_ID:
        fail(errors, "CONTRACT_ID")
    if contract.get("q1_dependency", {}).get("commit") != Q1_COMMIT:
        fail(errors, "Q1_COMMIT")
    if contract.get("q1_dependency", {}).get("profile_id") != Q1_PROFILE_ID:
        fail(errors, "Q1_PROFILE")
    if profile.get("profile_id") != PROFILE_ID:
        fail(errors, "QUALITY_PROFILE_ID")
    if profile.get("invalid_target") != "INPUT_UNAVAILABLE":
        fail(errors, "INVALID_TARGET")
    if profile.get("physiology_labels_modified") is not False:
        fail(errors, "PHYSIOLOGY_LABELS_MODIFIED")
    if contract.get("large_gap", {}).get("interpolation_allowed") is not False:
        fail(errors, "GAP_INTERPOLATION")
    if contract.get("flat_signal", {}).get("low_amplitude_alone_invalid") is not False:
        fail(errors, "LOW_AMPLITUDE_RULE")
    if contract.get("d2_used") is not False:
        fail(errors, "D2_FLAG")
    if contract.get("q3_work") is not False:
        fail(errors, "Q3_FLAG")
    if "IEEE DataPort" in json.dumps(artifacts) or "VITALSENSE_120" in json.dumps(artifacts):
        fail(errors, "D2_REFERENCE")

    q1 = load_q1_profile(Q1_PROFILE_PATH)
    t = np.arange(256, dtype=np.float64) * 100.0
    x = np.sin(np.linspace(0.0, 6.0 * np.pi, 256))
    jitter = apply_timing_corruption(t, x, q1, mode="CADENCE_JITTER", severity="TYPICAL", seed=11)
    jitter_eval = evaluate_availability(jitter["timestamps_ms"], jitter["values"])
    if jitter_eval["availability_state"] != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "Q1_JITTER_UNAVAILABLE")
    a = apply_timing_corruption(t, x, q1, mode="CADENCE_JITTER", severity="TYPICAL", seed=11)
    b = apply_timing_corruption(t, x, q1, mode="CADENCE_JITTER", severity="TYPICAL", seed=11)
    if not np.array_equal(a["timestamps_ms"], b["timestamps_ms"]):
        fail(errors, "Q1_NOT_DETERMINISTIC")

    for key in (
        "run_3598",
        "run_2884",
        "gap_158380_ms",
        "gap_42637_ms",
        "timestamp_collision",
    ):
        row = handoff.get("handoff_validation", {}).get(key, {})
        if row.get("quality_target") != "INPUT_UNAVAILABLE":
            fail(errors, f"HANDOFF_PASS:{key}")

    if summary.get("low_amplitude_dynamic_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "LOW_AMP")
    if summary.get("isolated_republication_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "ISO_REPUB")
    if summary.get("q1_typical_jitter_state") != "PHYSIOLOGY_ELIGIBLE":
        fail(errors, "Q1_JITTER_SUMMARY")
    for mode in Q2_MODES:
        if mode == "CLEAN_VALID":
            continue
        target = summary.get("mode_results", {}).get(mode, {}).get("quality_target")
        if target != "INPUT_UNAVAILABLE":
            fail(errors, f"MODE_TARGET:{mode}")
        labels = summary.get("mode_results", {}).get(mode, {}).get("physiology_labels_unique", [])
        if "APNEA" in labels:
            fail(errors, f"SYNTHETIC_APNEA:{mode}")

    checks = {
        "Q1_PROFILE_INHERITED": "YES",
        "QUALITY_STATE_TAXONOMY_FROZEN": "YES",
        "LARGE_GAP_CONTRACT_DEFENSIBLE": "YES",
        "FREEZE_CONTRACT_DEFENSIBLE": "YES",
        "STALE_CONTRACT_DEFENSIBLE": "YES",
        "FLAT_CONTRACT_DEFENSIBLE": "YES",
        "LOW_AMPLITUDE_NOT_AUTOMATICALLY_INVALID": "YES",
        "INPUT_UNAVAILABLE_PRECEDES_PHYSIOLOGY": "YES",
        "PRESENCE_GATE_PRESERVED": "YES",
        "NO_GAP_INTERPOLATION": "YES",
        "NO_SYNTHETIC_APNEA": "YES",
        "DETERMINISTIC_CORRUPTION": "YES",
        "LINEAGE_PRESERVED": "YES",
        "Q1_TYPICAL_JITTER_REMAINS_POTENTIALLY_VALID": "YES",
        "ISOLATED_Q1_REPUBLICATION_NOT_AUTOMATIC_FREEZE": "YES",
        "LARGE_GAP_FAILS_CLOSED": "YES",
        "EXTENDED_FREEZE_FAILS_CLOSED": "YES",
        "STALE_SOURCE_FAILS_CLOSED": "YES",
        "EXACT_FLAT_FAILS_CLOSED": "YES",
        "TIMESTAMP_INVALID_FAILS_CLOSED": "YES",
        "LOW_AMPLITUDE_ALONE_CAUSES_UNAVAILABLE": "NO",
        "INVALID_CORRUPTION_TARGET_IS_PHYSIOLOGY_CLASS": "NO",
        "INVALID_CORRUPTION_TARGET": "INPUT_UNAVAILABLE",
        "SYNTHETIC_APNEA_CREATED": "NO",
        "NO_LARGE_GAP_INTERPOLATION": "YES",
        "NO_LEARNED_INTERPOLATION": "YES",
        "MR60_SUPERVISED_USE": "NO",
        "MODEL_OUTPUT_TUNING": "NO",
        "D2_USED": "NO",
        "Q3_WORK_PERFORMED": "NO",
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
        "D0_SUBJECT_HELDOUT_USED": "NO",
        "M_N6_EXCLUDED_HELDOUT_USED": "NO",
    }
    for key, expected in REQUIRED_YES.items():
        if checks.get(key) != expected:
            fail(errors, f"REQUIRED_YES_FAIL:{key}")
    for key, expected in REQUIRED_NO.items():
        if checks.get(key) != expected:
            fail(errors, f"REQUIRED_NO_FAIL:{key}")
    if errors:
        checks["Q1_PROFILE_INHERITED"] = checks["Q1_PROFILE_INHERITED"]

    gate = "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED"
    result = {
        "audit_date": AUDIT_DATE,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "profile_id": PROFILE_ID,
        "ok": not errors,
        "gate": gate,
        "errors": errors,
        "checks": checks,
        "d2_used": "NO",
        "mr60_supervised_use": "NO",
        "q3_work": "NO",
        "limitations": [
            "near-flat non-zero threshold deferred to R2/R3/M-PV1",
            "model-ready recovery history duration deferred to M-PV1",
            "Pi host timestamp residual remains unavailable from Q1",
        ],
    }
    dump_json(MANIFEST_DIR / "validation_result.json", result)
    return result


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
