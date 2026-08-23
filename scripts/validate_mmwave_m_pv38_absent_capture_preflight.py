#!/usr/bin/env python3
"""Validate the fail-closed M-PV3.8 ABSENT capture-preflight record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_capture_preflight"
PREFLIGHT = OUT / "preflight_readiness.json"
RESULT = OUT / "validation_result.json"
CHECKSUMS = OUT / "checksums.json"
CHECKSUM_LIST = OUT / "checksums.sha256"
REPORT = ROOT / "docs/mmwave/20260823_SafeNest_mmWave_M-PV3_8_ABSENT_Capture_Preflight_Result_01.md"
PLAN = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_acquisition_planning/acquisition_plan.json"
CONTRACT = ROOT / "config/mmwave/m_pv38_absent_membership_acquisition_gate.json"
SCHEMA = "M-PV3.8.4_CAPTURE_PREFLIGHT_V1"
PREFLIGHT_ID = "MMWAVE_V2_M_PV38_ABSENT_CAPTURE_PREFLIGHT_V1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def absolute_paths(value: Any, location: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(absolute_paths(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(absolute_paths(child, f"{location}[{index}]"))
    elif isinstance(value, str) and (value.startswith("/Users/") or value.startswith("/private/") or value.startswith("file://")):
        found.append(location)
    return found


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required = (PREFLIGHT, RESULT, CHECKSUMS, CHECKSUM_LIST, REPORT, PLAN, CONTRACT)
    missing = [rel(path) for path in required if not path.is_file()]
    add("required_artifacts_present", not missing, missing)
    if missing:
        return {"status": "CAPTURE_BLOCKED", "ok": False, "failed_checks": ["required_artifacts_present"], "checks": checks}

    preflight = read(PREFLIGHT)
    result = read(RESULT)
    plan = read(PLAN)
    contract = read(CONTRACT)
    checksum_map = read(CHECKSUMS)

    add("preflight_identity", preflight.get("schema_version") == SCHEMA and preflight.get("preflight_id") == PREFLIGHT_ID and preflight.get("mode") == "PREFLIGHT_ONLY_NO_CAPTURE_NO_MEMBERSHIP_NO_EVALUATION", preflight.get("mode"))
    add("status_is_fail_closed", preflight.get("result", {}).get("status") == "CAPTURE_BLOCKED" and result.get("status") == "CAPTURE_BLOCKED" and result.get("capture_authorized") is False, preflight.get("result"))
    observed = preflight.get("preflight_observation", {})
    add("unverified_live_requirements_block_capture", observed.get("target_mmwave_serial_interface_detected") is False and observed.get("raw_data_stream_verified") is False and observed.get("timestamp_stream_verified") is False and observed.get("sensor_health_telemetry_verified") is False and observed.get("authoritative_occupancy_reference_verified") is False, observed)
    structure = preflight.get("campaign_structure", {})
    add("fixed_structure_not_prematurely_locked", structure.get("required_lineage_group_count") == 3 and structure.get("required_slots_per_group") == 3 and structure.get("required_total_slots") == 9 and structure.get("predeclared_slots_created") == 0 and structure.get("slot_lock_created") is False and structure.get("selection_rule_version") == "CHRONOLOGICAL_FIRST_N_QUALIFYING_V1", structure)
    artifacts = preflight.get("artifact_state", {})
    add("no_campaign_or_membership_artifacts_created", all(artifacts.get(key) is False for key in ("campaign_predeclaration_created", "post_capture_checksum_receipts_created", "recording_manifest_created", "occupancy_evidence_registry_created", "sensor_health_registry_created", "rejection_registry_created", "final_membership_created")), artifacts)
    preserved = preflight.get("prohibitions_preserved", {})
    add("prohibitions_preserved", all(preserved.get(key) is False for key in ("capture_performed", "absent_samples_created", "existing_d1_relabelled", "membership_constructed", "model_evaluation_performed", "candidate_outputs_inspected", "thresholds_changed", "candidate_roster_modified", "d2_accessed", "mr60_supervised_physiology_used", "m_pv4_authorized")), preserved)
    add("plan_and_contract_still_require_lifecycle", plan.get("capture_protocol", {}).get("recording_duration_seconds") == 300 and plan.get("capture_protocol", {}).get("selection_rule") == "CHRONOLOGICAL_FIRST_N_QUALIFYING_V1" and contract.get("recording_identity_lifecycle", {}).get("stage_2_post_capture_immutable_checksum_receipt", {}).get("eligibility_scan") == "FORBIDDEN_UNTIL_RECEIPT_IS_LOCKED", {"plan_duration": plan.get("capture_protocol", {}).get("recording_duration_seconds"), "selection_rule": plan.get("capture_protocol", {}).get("selection_rule")})
    add("machine_readable_artifacts_are_portable", not absolute_paths(preflight) and not absolute_paths(result) and not absolute_paths(checksum_map), absolute_paths(preflight) + absolute_paths(result) + absolute_paths(checksum_map))

    listed: dict[str, str] = {}
    malformed: list[str] = []
    for line in CHECKSUM_LIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, path = line.split("  ", 1)
            listed[path] = digest
        except ValueError:
            malformed.append(line)
    expected_paths = {rel(PREFLIGHT), rel(RESULT), rel(REPORT)}
    mismatch = [path for path, digest in listed.items() if not (ROOT / path).is_file() or sha256(ROOT / path) != digest]
    add("checksum_receipt_complete", not malformed and expected_paths == set(listed) and not mismatch, {"missing": sorted(expected_paths - set(listed)), "unexpected": sorted(set(listed) - expected_paths), "mismatch": mismatch, "malformed": malformed})
    declared = checksum_map.get("artifacts", {})
    add("checksum_json_matches_receipt", declared == listed, {"declared": declared, "listed": listed})

    failures = [check["name"] for check in checks if not check["ok"]]
    return {"schema_version": SCHEMA, "preflight_id": PREFLIGHT_ID, "status": "CAPTURE_BLOCKED", "capture_authorized": False, "capture_performed": False, "ok": not failures, "failed_checks": failures, "checks": checks}


def main() -> int:
    result = validate()
    print(json.dumps({key: result[key] for key in ("status", "capture_authorized", "capture_performed", "ok", "failed_checks")}, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
