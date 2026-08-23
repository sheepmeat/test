#!/usr/bin/env python3
"""Validate the M-PV3.8 ABSENT acquisition feasibility decision audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_acquisition_feasibility_audit"
AUDIT = OUT / "feasibility_audit.json"
RESULT = OUT / "validation_result.json"
CHECKSUMS = OUT / "checksums.json"
CHECKSUM_LIST = OUT / "checksums.sha256"
REPORT = ROOT / "docs/mmwave/20260824_SafeNest_mmWave_M-PV3_8_ABSENT_Acquisition_Feasibility_Decision_Audit_01.md"
SCHEMA = "M-PV3.8.4_FEASIBILITY_AUDIT_V1"
AUDIT_ID = "MMWAVE_V2_M_PV38_ABSENT_ACQUISITION_FEASIBILITY_AUDIT_V1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def absolute_strings(value: Any, location: str = "root") -> list[str]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            matches.extend(absolute_strings(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(absolute_strings(child, f"{location}[{index}]"))
    elif isinstance(value, str) and (value.startswith("/Users/") or value.startswith("/private/") or value.startswith("file://")):
        matches.append(location)
    return matches


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required = (AUDIT, RESULT, CHECKSUMS, CHECKSUM_LIST, REPORT)
    missing = [rel(path) for path in required if not path.is_file()]
    add("required_artifacts_present", not missing, missing)
    if missing:
        return {"status": "ACQUISITION_REQUIRES_RESOURCE_ACCESS", "ok": False, "failed_checks": ["required_artifacts_present"], "checks": checks}

    audit = read(AUDIT)
    result = read(RESULT)
    checksums = read(CHECKSUMS)
    add("identity", audit.get("schema_version") == SCHEMA and audit.get("audit_id") == AUDIT_ID and audit.get("mode") == "EVIDENCE_AVAILABILITY_AUDIT_ONLY_NO_CAPTURE_NO_MEMBERSHIP_NO_EVALUATION", audit.get("mode"))
    decision = audit.get("decision", {})
    add("decision_is_resource_access_not_authorization", decision.get("status") == "ACQUISITION_REQUIRES_RESOURCE_ACCESS" and decision.get("current_setup_feasible") is False and decision.get("feasible_after_resources_are_authoritatively_available") is True and result.get("status") == "ACQUISITION_REQUIRES_RESOURCE_ACCESS", decision)
    hardware = audit.get("hardware_feasibility", {})
    evidence = audit.get("evidence_feasibility", {})
    add("hardware_and_evidence_gaps_are_explicit", hardware.get("status") == "RESOURCE_ACCESS_REQUIRED" and len(hardware.get("findings", [])) == 4 and evidence.get("status") == "RESOURCE_AND_GOVERNANCE_ACCESS_REQUIRED" and len(evidence.get("findings", [])) == 4 and "SUPPORTING_ONLY" in evidence.get("operator_statement", ""), {"hardware": hardware.get("status"), "evidence": evidence.get("status")})
    package = audit.get("minimum_resource_package", {})
    add("minimum_resources_cover_all_domains", all(len(package.get(key, [])) >= 3 for key in ("hardware", "personnel", "environment", "software_and_evidence_tooling")), {key: len(package.get(key, [])) for key in ("hardware", "personnel", "environment", "software_and_evidence_tooling")})
    preserved = audit.get("prohibitions_preserved", {})
    add("no_prohibited_work", all(value is False for value in preserved.values()) and result.get("campaign_predeclaration_created") is False and result.get("capture_performed") is False and result.get("membership_constructed") is False and result.get("model_evaluation_performed") is False and result.get("m_pv4_authorized") is False, preserved)
    preserved_rules = audit.get("authorization_boundary", {}).get("preserved_rules", [])
    add("frozen_rules_remain_preserved", len(preserved_rules) == 3 and any("no-replacement" in rule for rule in preserved_rules) and any("CHRONOLOGICAL_FIRST_N_QUALIFYING_V1" in rule for rule in preserved_rules), preserved_rules)
    add("portable_machine_readable_artifacts", not absolute_strings(audit) and not absolute_strings(result) and not absolute_strings(checksums), absolute_strings(audit) + absolute_strings(result) + absolute_strings(checksums))

    listed: dict[str, str] = {}
    malformed: list[str] = []
    for line in CHECKSUM_LIST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value, name = line.split("  ", 1)
            listed[name] = value
        except ValueError:
            malformed.append(line)
    expected = {rel(AUDIT), rel(RESULT), rel(REPORT)}
    mismatches = [name for name, value in listed.items() if not (ROOT / name).is_file() or digest(ROOT / name) != value]
    add("checksums_complete", not malformed and set(listed) == expected and not mismatches and checksums.get("artifacts") == listed, {"malformed": malformed, "missing": sorted(expected - set(listed)), "unexpected": sorted(set(listed) - expected), "mismatches": mismatches})

    failed = [check["name"] for check in checks if not check["ok"]]
    return {"schema_version": SCHEMA, "audit_id": AUDIT_ID, "status": "ACQUISITION_REQUIRES_RESOURCE_ACCESS", "capture_authorized": False, "capture_performed": False, "ok": not failed, "failed_checks": failed, "checks": checks}


def main() -> int:
    result = validate()
    print(json.dumps({key: result[key] for key in ("status", "capture_authorized", "capture_performed", "ok", "failed_checks")}, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
