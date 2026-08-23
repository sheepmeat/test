#!/usr/bin/env python3
"""Validate the M-PV3.8 ABSENT acquisition resource-readiness checklist."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/mmwave/manifests/M-PV3_8_absent_resource_readiness_checklist"
CHECKLIST = OUT / "readiness_requirements.json"
RESULT = OUT / "validation_result.json"
CHECKSUMS = OUT / "checksums.json"
CHECKSUM_LIST = OUT / "checksums.sha256"
REPORT = ROOT / "docs/mmwave/20260824_SafeNest_mmWave_M-PV3_8_ABSENT_Acquisition_Resource_Readiness_Checklist_01.md"
SCHEMA = "M-PV3.8.4_RESOURCE_READINESS_CHECKLIST_V1"
CHECKLIST_ID = "MMWAVE_V2_M_PV38_ABSENT_RESOURCE_READINESS_CHECKLIST_V1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def relative(path: Path) -> str:
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

    required = (CHECKLIST, RESULT, CHECKSUMS, CHECKSUM_LIST, REPORT)
    missing = [relative(path) for path in required if not path.is_file()]
    add("required_artifacts_present", not missing, missing)
    if missing:
        return {"ok": False, "failed_checks": ["required_artifacts_present"], "checks": checks}

    checklist = read(CHECKLIST)
    result = read(RESULT)
    checksum_map = read(CHECKSUMS)
    add("identity_and_mode", checklist.get("schema_version") == SCHEMA and checklist.get("checklist_id") == CHECKLIST_ID and checklist.get("mode") == "READINESS_REQUIREMENTS_ONLY_NO_CAPTURE_NO_MEMBERSHIP_NO_EVALUATION", checklist.get("mode"))
    add("four_resource_domains_complete", all(len(checklist.get(key, [])) >= 4 for key in ("required_hardware", "required_software_and_tooling", "required_evidence_and_proof", "required_personnel_and_process")), {key: len(checklist.get(key, [])) for key in ("required_hardware", "required_software_and_tooling", "required_evidence_and_proof", "required_personnel_and_process")})
    setup = checklist.get("minimum_setup_for_future_preflight_pass", [])
    add("minimum_setup_is_complete", len(setup) == 6 and any("300-second" in item for item in setup) and any("nine slot" in item for item in setup), setup)
    blockers = checklist.get("estimated_blockers", [])
    add("blockers_are_bounded_and_fail_closed", len(blockers) == 4 and sum(item.get("severity") == "HARD_BLOCKER" for item in blockers) == 3 and any(item.get("severity") == "CAMPAIGN_STOP_CONDITION" and "No recovery" in item.get("estimate", "") for item in blockers), blockers)
    governance = checklist.get("preserved_governance", [])
    add("governance_is_preserved", len(governance) == 5 and any("no replacement" in item for item in governance) and any("checksum" in item for item in governance) and any("CHRONOLOGICAL_FIRST_N_QUALIFYING_V1" in item for item in governance), governance)
    prohibited = checklist.get("prohibitions_preserved", {})
    add("no_capture_or_authorization", all(value is False for value in prohibited.values()) and result.get("capture_authorized") is False and result.get("capture_started") is False and result.get("membership_constructed") is False and result.get("model_evaluation_performed") is False and result.get("m_pv4_authorized") is False, prohibited)
    add("machine_readable_artifacts_are_portable", not absolute_paths(checklist) and not absolute_paths(result) and not absolute_paths(checksum_map), absolute_paths(checklist) + absolute_paths(result) + absolute_paths(checksum_map))

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
    expected = {relative(CHECKLIST), relative(RESULT), relative(REPORT)}
    mismatch = [name for name, digest in listed.items() if not (ROOT / name).is_file() or sha256(ROOT / name) != digest]
    add("checksums_complete", not malformed and set(listed) == expected and not mismatch and checksum_map.get("artifacts") == listed, {"malformed": malformed, "missing": sorted(expected - set(listed)), "unexpected": sorted(set(listed) - expected), "mismatch": mismatch})

    failures = [item["name"] for item in checks if not item["ok"]]
    return {"schema_version": SCHEMA, "checklist_id": CHECKLIST_ID, "capture_authorized": False, "capture_started": False, "ok": not failures, "failed_checks": failures, "checks": checks}


def main() -> int:
    result = validate()
    print(json.dumps({key: result[key] for key in ("capture_authorized", "capture_started", "ok", "failed_checks")}, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
