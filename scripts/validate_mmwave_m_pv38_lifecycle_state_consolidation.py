#!/usr/bin/env python3
"""Validate the authoritative M-PV3.8 lifecycle closure state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/mmwave/m_pv38_absent_membership_acquisition_gate.json"
GATE = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_membership_acquisition_gate/acquisition_gate.json"
LOCK = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_membership_acquisition_gate/final_lock_requirements.json"
PLAN = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_acquisition_planning/planning_result.json"
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_lifecycle_closure"
CLOSURE = OUT / "lifecycle_closure_state.json"
RESULT = OUT / "validation_result.json"
CHECKSUMS = OUT / "checksums.json"
CHECKSUM_LIST = OUT / "checksums.sha256"
REPORT = ROOT / "docs/mmwave/20260824_SafeNest_mmWave_M-PV3_8_Lifecycle_State_Consolidation_01.md"
VERSION = "M-PV3.8.4_CHECKSUM_LIFECYCLE_CLARIFICATION"
CLOSURE_STATUS = "RESOURCE_BLOCKED_CLOSED"


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


def absolute_strings(value: Any, location: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(absolute_strings(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(absolute_strings(child, f"{location}[{index}]"))
    elif isinstance(value, str) and (value.startswith("/Users/") or value.startswith("/private/") or value.startswith("file://")):
        found.append(location)
    return found


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required = (CONTRACT, GATE, LOCK, PLAN, CLOSURE, RESULT, CHECKSUMS, CHECKSUM_LIST, REPORT)
    missing = [rel(path) for path in required if not path.is_file()]
    add("required_artifacts_present", not missing, missing)
    if missing:
        return {"closure_status": CLOSURE_STATUS, "ok": False, "failed_checks": ["required_artifacts_present"], "checks": checks}

    contract, gate, lock, plan, closure, result, checksums = map(read, (CONTRACT, GATE, LOCK, PLAN, CLOSURE, RESULT, CHECKSUMS))
    add("contract_and_gate_audit_are_approved", contract.get("schema_version") == VERSION and contract.get("current_state", {}).get("independent_audit_result") == "APPROVED" and gate.get("schema_version") == VERSION and gate.get("audit_state") == "APPROVED" and lock.get("schema_version") == VERSION and lock.get("audit_state") == "APPROVED", {"contract": contract.get("schema_version"), "gate": gate.get("schema_version"), "lock": lock.get("schema_version")})
    add("closure_is_authoritative", closure.get("phase_id") == "M-PV3.8" and closure.get("closure_status") == CLOSURE_STATUS and closure.get("reason") == "ACQUISITION_REQUIRES_RESOURCE_ACCESS" and closure.get("contract_version") == VERSION and closure.get("audit_state") == "APPROVED", closure)
    add("lifecycle_statuses_are_consistent", contract.get("current_state", {}).get("lifecycle_closure_status") == CLOSURE_STATUS and contract.get("current_state", {}).get("membership_construction") == "BLOCKED_INVALID_FINAL_MEMBERSHIP" and gate.get("lifecycle_closure_status") == CLOSURE_STATUS and gate.get("membership_construction") == "BLOCKED_INVALID_FINAL_MEMBERSHIP" and gate.get("candidate_evaluation") == "NOT_EXECUTED" and lock.get("lifecycle_closure_status") == CLOSURE_STATUS and lock.get("construction_status") == "BLOCKED_INVALID_FINAL_MEMBERSHIP" and plan.get("status") == "SUPERSEDED_BY_RESOURCE_BLOCKED_CLOSED" and plan.get("lifecycle_closure_status") == CLOSURE_STATUS, {"contract": contract.get("current_state"), "gate": gate.get("membership_construction"), "lock": lock.get("construction_status"), "plan": plan.get("status")})
    non_execution = closure.get("non_execution_confirmation", {})
    add("no_execution_or_mpv4_authorization", all(value is False for value in non_execution.values()) and closure.get("mpv4_authorization") == "UNAUTHORIZED" and result.get("capture_performed") is False and result.get("membership_constructed") is False and result.get("evaluation_performed") is False and result.get("candidate_outputs_inspected") is False and result.get("mpv4_authorized") is False, non_execution)
    frozen = " ".join(closure.get("preserved_restrictions", []))
    add("frozen_restrictions_present", "ABSENT semantics" in frozen and "No-replacement" in frozen and "checksum lifecycle" in frozen and "CHRONOLOGICAL_FIRST_N_QUALIFYING_V1" in frozen and "M-PV4" in frozen, closure.get("preserved_restrictions"))
    stale_values = ("M-PV3.8.3_CORRECTIVE", "NEEDS_CORRECTION_RESOLVED_PENDING_INDEPENDENT_REAUDIT", "NOT_AUTHORIZED_PENDING_INDEPENDENT_REAUDIT", "READY_FOR_CAPTURE_AUTHORIZATION")
    inspected = (CONTRACT, GATE, LOCK, PLAN)
    found_stale = {rel(path): [value for value in stale_values if value in path.read_text(encoding="utf-8")] for path in inspected}
    found_stale = {path: values for path, values in found_stale.items() if values}
    add("no_stale_lifecycle_values_in_authoritative_sources", not found_stale, found_stale)
    add("machine_readable_artifacts_are_portable", not absolute_strings(closure) and not absolute_strings(result) and not absolute_strings(checksums), absolute_strings(closure) + absolute_strings(result) + absolute_strings(checksums))

    listed: dict[str, str] = {}
    malformed: list[str] = []
    for line in CHECKSUM_LIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split("  ", 1)
            listed[name] = digest
        except ValueError:
            malformed.append(line)
    expected = {rel(CONTRACT), rel(GATE), rel(LOCK), rel(PLAN), rel(CLOSURE), rel(RESULT), rel(REPORT)}
    mismatch = [name for name, digest in listed.items() if not (ROOT / name).is_file() or sha256(ROOT / name) != digest]
    add("lifecycle_checksums_complete", not malformed and set(listed) == expected and not mismatch and checksums.get("files") == listed, {"malformed": malformed, "missing": sorted(expected - set(listed)), "unexpected": sorted(set(listed) - expected), "mismatch": mismatch})

    failed = [check["name"] for check in checks if not check["ok"]]
    return {"schema_version": "M-PV3.8_LIFECYCLE_CLOSURE_V1", "phase_id": "M-PV3.8", "closure_status": CLOSURE_STATUS, "ok": not failed, "failed_checks": failed, "checks": checks}


def main() -> int:
    result = validate()
    print(json.dumps({key: result[key] for key in ("closure_status", "ok", "failed_checks")}, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
