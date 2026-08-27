#!/usr/bin/env python3
"""Validate portable, non-final M-PROT-4 SmokeReceipt evidence.

This validator owns evidence shape and provenance checks only.  It does not
run M-PROT-3, invoke B23, replay data, load a model, or authorize a governed
evaluation.  Cross-field checks intentionally fail closed when a smoke card
claims that the prototype was reached without the M-PROT-3 V3 prerequisites.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas/mmwave/m_prot_4_smoke_receipt.schema.json"
SCHEMA_ID = "MMWAVE_V2_M_PROT_4_SMOKE_RECEIPT_V1"
SCHEMA_VERSION = "M-PROT-4-SMOKE-RECEIPT-V1"
PHASE = "M-PROT-4"
WIRING_RECEIPT_VERSION = "M-PROT-3-WIRING-RECEIPT-V3"

# Frozen identities inherited from the M-PROT-3-WIRING-RECEIPT-V3 seam and
# the M-PROT-2 B23 deployable artifact contract.  These are expected values,
# not values discovered from a smoke case.
B23_PANEL_ID = "B23"
B23_ARTIFACT_PATH = "models/mmwave/m_pv2/family_b/candidate_seed_23.pt"
B23_ARTIFACT_SHA256 = "8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c"
B23_PARAMETER_SHA256 = "6db949c242e25888dd20c3fc8e2305af03448aa229e3ca73e4159216a266d78e"
B23_SCALER_PATH = "datasets/mmwave/manifests/M-PV2_candidate_training/scaler_statistics.json"
B23_SCALER_SHA256 = "5a2583b5b5064be5480b0cf56f2a2c12d40a4a2d005eb087dc8e12106881159c"
B23_REPRESENTATION = "PYTORCH_FLOAT32_STATE_DICT"
R1_PROFILE = "R1-A_NATIVE_CENTERED_RELATIVE_MOTION_10HZ_V1"
WINDOW_CONTRACT = "M_PROT_3_CAUSAL_30S_10HZ_300_V1"
R1_SAMPLE_COUNT = 300

ALLOWED_CASE_CLASSES = frozenset({"FIXTURE_SMOKE", "OFFLINE_REPLAY_SMOKE", "SYNTHETIC_SMOKE"})
CASE_LINEAGE = {
    "FIXTURE_SMOKE": "FIXTURE_NON_CAMPAIGN",
    "OFFLINE_REPLAY_SMOKE": "OFFLINE_REPLAY_NON_CAMPAIGN",
    "SYNTHETIC_SMOKE": "SYNTHETIC_SMOKE_NON_CAMPAIGN",
}
ALLOWED_LINEAGE_CLASSES = frozenset(CASE_LINEAGE.values())
ALLOWED_OUTCOMES = frozenset(
    {
        "PROTOTYPE_REACHED",
        "PROTOTYPE_NOT_REACHED",
        "PHYSIOLOGY_SUCCESS",
        "PHYSIOLOGY_ELIGIBLE",
        "FAIL_CLOSED",
        "UNAVAILABLE",
    }
)
SUCCESS_OUTCOMES = frozenset({"PHYSIOLOGY_SUCCESS", "PHYSIOLOGY_ELIGIBLE"})
R1_STATUSES = frozenset({"PASS", "READY", "NOT_REACHED", "UNAVAILABLE", "FAIL"})
PROTOTYPE_STATUSES = frozenset(
    {"PHYSIOLOGY_ELIGIBLE", "PHYSIOLOGY_SUCCESS", "NOT_REACHED", "UNAVAILABLE", "FAIL_CLOSED"}
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SW01_PASS_STATUS = "PASS_NON_CAMPAIGN_INTERFACE_CHECK"
SW01_FAILURE_RE = re.compile(r"^(FAIL_|LIVE_TARGET_UNAVAILABLE$|BACKEND_UNAVAILABLE$)")

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "phase",
        "wiring_receipt_version",
        "case_id",
        "case_class",
        "input_fixture_id",
        "input_fixture_reference",
        "input_fixture_sha256",
        "expected_outcome",
        "observed_outcome",
        "source",
        "sw01",
        "window",
        "r1",
        "presence",
        "prototype",
        "lineage_class",
        "flags",
        "track_f",
    }
)
SOURCE_FIELDS = frozenset(
    {"device_identity", "interface_identity", "configuration_identity", "observation_kind"}
)
SW01_FIELDS = frozenset(
    {
        "overall_status",
        "source_validation_status",
        "sw01_receipt_sha256",
        "contributing_receipt_sha256_chain",
        "sw01_receipt_sha256_chain",
        "latest_receipt_semantics",
        "chain_semantics",
        "noncontributing_receipt_sha256",
        "session_id",
    }
)
WINDOW_FIELDS = frozenset(
    {
        "contract",
        "causal_past_only",
        "ready",
        "start",
        "end",
        "window_start_s",
        "window_end_s",
        "source_sample_count",
    }
)
R1_FIELDS = frozenset({"profile", "sample_count", "r1_sample_count", "status"})
PRESENCE_FIELDS = frozenset({"status", "gate_satisfied"})
PROTOTYPE_FIELDS = frozenset(
    {
        "reached",
        "panel_id",
        "artifact_path",
        "artifact_sha256",
        "parameter_sha256",
        "scaler_path",
        "scaler_sha256",
        "representation",
        "result_status",
        "fail_closed_code",
    }
)
FLAG_FIELDS = frozenset(
    {
        "PROTOTYPE_INTEGRATION_ONLY",
        "NOT_FINAL_SELECTED_MODEL",
        "NOT_DEPLOYMENT_VALIDATED",
        "NOT_SAFETY_VALIDATED",
        "NOT_CLINICAL_VALIDATION",
        "FINAL_GOVERNED_EVALUATION",
        "D1_ADMISSIBLE",
        "LIVE_HARDWARE",
    }
)
TRACK_F_FIELDS = frozenset(
    {
        "d1_present",
        "d1_absent",
        "d1_membership",
        "m_pv38",
        "m_pv38_evaluation",
        "m_pv4",
        "d2",
    }
)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _valid_sw01_status(value: Any) -> bool:
    return value == SW01_PASS_STATUS or (isinstance(value, str) and SW01_FAILURE_RE.match(value) is not None)


def _portable_reference(value: Any) -> bool:
    """Require a repository-relative reference, not a workstation path."""

    if not _non_empty_string(value) or "\x00" in value:
        return False
    normalized = value.replace("\\", "/")
    if normalized.startswith(("/", "~/", "./", "../", "file://", "$HOME/", "%USERPROFILE%/")):
        return False
    if re.match(r"^[A-Za-z]:/", normalized):
        return False
    return ".." not in normalized.split("/") and not normalized.startswith(".")


def _forbidden_path_string(value: str) -> bool:
    """Detect absolute/home-relative/local path leakage anywhere in a card."""

    normalized = value.replace("\\", "/")
    lowered = normalized.lower()
    if normalized.startswith(("/", "~/", "./", "../", "file://", "$HOME/", "%USERPROFILE%/")):
        return True
    if re.match(r"^[A-Za-z]:/", normalized):
        return True
    for marker in ("/users/", "/private/", "/tmp/", "/var/folders/", "/var/tmp/"):
        if marker in lowered:
            return True
    return False


def _find_path_leaks(value: Any, location: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_find_path_leaks(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_path_leaks(child, f"{location}[{index}]"))
    elif isinstance(value, str) and _forbidden_path_string(value):
        found.append(location)
    return found


def _unexpected_fields(value: Mapping[str, Any], allowed: set[str] | frozenset[str], label: str) -> list[str]:
    unexpected = sorted(set(value) - set(allowed))
    return [f"{label}: unexpected fields {unexpected}"] if unexpected else []


def _required_fields(value: Mapping[str, Any], required: Sequence[str], label: str) -> list[str]:
    return [f"{label}: missing {field}" for field in required if field not in value]


def _validate_sha(value: Any, label: str, errors: list[str]) -> None:
    if not _sha256(value):
        errors.append(f"{label}: must be lowercase 64-character SHA-256")


def _validate_string_fields(value: Mapping[str, Any], fields: Sequence[str], label: str, errors: list[str]) -> None:
    for field in fields:
        if not _non_empty_string(value.get(field)):
            errors.append(f"{label}.{field}: must be a non-empty string")


def _validate_sw01(sw01: Any, errors: list[str]) -> None:
    label = "sw01"
    if not isinstance(sw01, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(sw01, sorted(SW01_FIELDS), label))
    errors.extend(_unexpected_fields(sw01, SW01_FIELDS, label))

    overall = sw01.get("overall_status")
    source_status = sw01.get("source_validation_status")
    if not _valid_sw01_status(overall):
        errors.append(f"{label}.overall_status: unsupported status")
    if not _valid_sw01_status(source_status):
        errors.append(f"{label}.source_validation_status: unsupported status")
    if _valid_sw01_status(overall) and _valid_sw01_status(source_status) and overall != source_status:
        errors.append(f"{label}: source_validation_status must equal overall_status")

    latest = sw01.get("sw01_receipt_sha256")
    if latest is not None:
        _validate_sha(latest, f"{label}.sw01_receipt_sha256", errors)
    for chain_name in ("contributing_receipt_sha256_chain", "sw01_receipt_sha256_chain"):
        chain = sw01.get(chain_name)
        if not isinstance(chain, list):
            errors.append(f"{label}.{chain_name}: must be an array")
            continue
        for index, receipt_sha in enumerate(chain):
            _validate_sha(receipt_sha, f"{label}.{chain_name}[{index}]", errors)
        if len(chain) != len(set(chain)):
            errors.append(f"{label}.{chain_name}: malformed duplicate receipt chain")

    contributing = sw01.get("contributing_receipt_sha256_chain")
    v3_chain = sw01.get("sw01_receipt_sha256_chain")
    if isinstance(contributing, list) and isinstance(v3_chain, list) and contributing != v3_chain:
        errors.append(f"{label}: contributing chain must preserve sw01_receipt_sha256_chain exactly")
    if isinstance(contributing, list):
        if contributing:
            if overall != SW01_PASS_STATUS or source_status != SW01_PASS_STATUS:
                errors.append(f"{label}: contributing receipt chain requires SW-01 PASS")
            if latest != contributing[-1]:
                errors.append(f"{label}: latest sw01 receipt must be the final contributing receipt")
        elif latest is not None:
            errors.append(f"{label}: empty selected-window chain must not claim a latest receipt")

    if sw01.get("latest_receipt_semantics") != "LATEST_CONTRIBUTING_PASS_RECEIPT":
        errors.append(f"{label}.latest_receipt_semantics: must state latest contributing PASS semantics")
    if sw01.get("chain_semantics") != "ORDERED_UNIQUE_ADJACENT_COLLAPSED_CONTRIBUTING_PASS_RECEIPTS_FOR_SELECTED_WINDOW_ONLY":
        errors.append(f"{label}.chain_semantics: selected-window ordered chain semantics are required")
    noncontributing = sw01.get("noncontributing_receipt_sha256")
    if not isinstance(noncontributing, list):
        errors.append(f"{label}.noncontributing_receipt_sha256: must be an array")
    else:
        for index, receipt_sha in enumerate(noncontributing):
            _validate_sha(receipt_sha, f"{label}.noncontributing_receipt_sha256[{index}]", errors)
        if isinstance(contributing, list) and set(noncontributing) & set(contributing):
            errors.append(f"{label}: noncontributing receipts must not be claimed in the contributing chain")
    if sw01.get("session_id") is not None and not _non_empty_string(sw01.get("session_id")):
        errors.append(f"{label}.session_id: must be a non-empty string or null")


def _validate_window(window: Any, errors: list[str]) -> None:
    label = "window"
    if not isinstance(window, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(window, sorted(WINDOW_FIELDS), label))
    errors.extend(_unexpected_fields(window, WINDOW_FIELDS, label))
    if window.get("contract") != WINDOW_CONTRACT:
        errors.append(f"{label}.contract: must preserve M-PROT-3 causal window contract")
    if window.get("causal_past_only") is not True:
        errors.append(f"{label}.causal_past_only: must be true")
    if not isinstance(window.get("ready"), bool):
        errors.append(f"{label}.ready: must be boolean")
    for field in ("start", "end", "window_start_s", "window_end_s"):
        value = window.get(field)
        if value is not None and not _finite_number(value):
            errors.append(f"{label}.{field}: must be finite number or null")
    if window.get("start") != window.get("window_start_s"):
        errors.append(f"{label}: start and window_start_s must match")
    if window.get("end") != window.get("window_end_s"):
        errors.append(f"{label}: end and window_end_s must match")
    count = window.get("source_sample_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        errors.append(f"{label}.source_sample_count: must be a non-negative integer")
    if window.get("ready") is True:
        if not _finite_number(window.get("start")) or not _finite_number(window.get("end")):
            errors.append(f"{label}: ready window requires start and end timestamps")
        elif float(window["end"]) < float(window["start"]):
            errors.append(f"{label}: end must not precede start")
        if isinstance(count, int) and count <= 0:
            errors.append(f"{label}: ready window requires source samples")
    elif window.get("ready") is False:
        if any(window.get(field) is not None for field in ("start", "end", "window_start_s", "window_end_s")):
            errors.append(f"{label}: unavailable window must not claim timestamps")
        if count != 0:
            errors.append(f"{label}: unavailable window must use source_sample_count=0")


def _validate_r1(r1: Any, errors: list[str]) -> None:
    label = "r1"
    if not isinstance(r1, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(r1, sorted(R1_FIELDS), label))
    errors.extend(_unexpected_fields(r1, R1_FIELDS, label))
    if r1.get("profile") != R1_PROFILE:
        errors.append(f"{label}.profile: unexpected R1 profile")
    for field in ("sample_count", "r1_sample_count"):
        value = r1.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{label}.{field}: must be a non-negative integer")
    if r1.get("sample_count") != r1.get("r1_sample_count"):
        errors.append(f"{label}: sample_count must equal r1_sample_count")
    if r1.get("status") not in R1_STATUSES:
        errors.append(f"{label}.status: unsupported status")
    if r1.get("status") in {"PASS", "READY"} and r1.get("sample_count") != R1_SAMPLE_COUNT:
        errors.append(f"{label}: ready R1 must contain exactly {R1_SAMPLE_COUNT} samples")


def _validate_presence(presence: Any, errors: list[str]) -> None:
    label = "presence"
    if not isinstance(presence, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(presence, sorted(PRESENCE_FIELDS), label))
    errors.extend(_unexpected_fields(presence, PRESENCE_FIELDS, label))
    status = presence.get("status")
    gate = presence.get("gate_satisfied")
    if status not in {"PRESENCE_GATE_SATISFIED", "PRESENCE_UNAVAILABLE", "PRESENCE_UNKNOWN"}:
        errors.append(f"{label}.status: unsupported status")
    if not isinstance(gate, bool):
        errors.append(f"{label}.gate_satisfied: must be boolean")
    elif gate is True and status != "PRESENCE_GATE_SATISFIED":
        errors.append(f"{label}: satisfied gate requires PRESENCE_GATE_SATISFIED")
    elif gate is False and status == "PRESENCE_GATE_SATISFIED":
        errors.append(f"{label}: unavailable gate must not use PRESENCE_GATE_SATISFIED")


def _validate_prototype(prototype: Any, errors: list[str]) -> None:
    label = "prototype"
    if not isinstance(prototype, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(prototype, sorted(PROTOTYPE_FIELDS), label))
    errors.extend(_unexpected_fields(prototype, PROTOTYPE_FIELDS, label))
    if not isinstance(prototype.get("reached"), bool):
        errors.append(f"{label}.reached: must be boolean")
    if prototype.get("panel_id") != B23_PANEL_ID:
        errors.append(f"{label}.panel_id: must be B23")
    if prototype.get("artifact_path") != B23_ARTIFACT_PATH or not _portable_reference(prototype.get("artifact_path")):
        errors.append(f"{label}.artifact_path: must be the portable frozen B23 artifact path")
    if prototype.get("scaler_path") != B23_SCALER_PATH or not _portable_reference(prototype.get("scaler_path")):
        errors.append(f"{label}.scaler_path: must be the portable frozen scaler path")
    if prototype.get("artifact_sha256") != B23_ARTIFACT_SHA256:
        errors.append(f"{label}.artifact_sha256: wrong or missing frozen B23 artifact SHA-256")
    if prototype.get("parameter_sha256") != B23_PARAMETER_SHA256:
        errors.append(f"{label}.parameter_sha256: wrong or missing frozen B23 parameter SHA-256")
    if prototype.get("scaler_sha256") != B23_SCALER_SHA256:
        errors.append(f"{label}.scaler_sha256: wrong or missing frozen scaler SHA-256")
    if prototype.get("representation") != B23_REPRESENTATION:
        errors.append(f"{label}.representation: unexpected B23 representation")
    result_status = prototype.get("result_status")
    if result_status not in PROTOTYPE_STATUSES:
        errors.append(f"{label}.result_status: unsupported status")
    fail_code = prototype.get("fail_closed_code")
    if fail_code is not None and not _non_empty_string(fail_code):
        errors.append(f"{label}.fail_closed_code: must be a non-empty string or null")
    if prototype.get("reached") is True:
        if result_status not in SUCCESS_OUTCOMES:
            errors.append(f"{label}: reached=true requires a physiology success/eligible result")
        if fail_code is not None:
            errors.append(f"{label}: reached=true must not carry a fail-closed code")
    elif prototype.get("reached") is False:
        if result_status in SUCCESS_OUTCOMES:
            errors.append(f"{label}: reached=false must not claim physiology success")
        if not _non_empty_string(fail_code):
            errors.append(f"{label}: not-reached prototype requires fail_closed_code")


def _validate_flags(flags: Any, errors: list[str]) -> None:
    label = "flags"
    if not isinstance(flags, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(flags, sorted(FLAG_FIELDS), label))
    errors.extend(_unexpected_fields(flags, FLAG_FIELDS, label))
    expected_true = {
        "PROTOTYPE_INTEGRATION_ONLY",
        "NOT_FINAL_SELECTED_MODEL",
        "NOT_DEPLOYMENT_VALIDATED",
        "NOT_SAFETY_VALIDATED",
        "NOT_CLINICAL_VALIDATION",
    }
    expected_false = {"FINAL_GOVERNED_EVALUATION", "D1_ADMISSIBLE", "LIVE_HARDWARE"}
    for field in sorted(expected_true):
        if flags.get(field) is not True:
            errors.append(f"{label}.{field}: must be true")
    for field in sorted(expected_false):
        if flags.get(field) is not False:
            errors.append(f"{label}.{field}: must be false")


def _validate_track_f(track_f: Any, errors: list[str]) -> None:
    label = "track_f"
    if not isinstance(track_f, Mapping):
        errors.append(f"{label}: must be an object")
        return
    errors.extend(_required_fields(track_f, sorted(TRACK_F_FIELDS), label))
    errors.extend(_unexpected_fields(track_f, TRACK_F_FIELDS, label))
    expected = {
        "d1_present": 57,
        "d1_absent": 0,
        "d1_membership": "BLOCKED_INVALID_FINAL_MEMBERSHIP",
        "m_pv38": "RESOURCE_BLOCKED_CLOSED",
        "m_pv38_evaluation": "NOT_EXECUTED",
        "m_pv4": "UNAUTHORIZED",
        "d2": "LOCKED",
    }
    for field, value in expected.items():
        if track_f.get(field) != value:
            errors.append(f"{label}.{field}: must preserve Track F value {value}")


def _validate_forbidden_semantics(value: Any, location: str = "root") -> list[str]:
    errors: list[str] = []
    forbidden = {
        "FINAL_GOVERNED_EVALUATION",
        "LOCKED_TEST",
        "D1_MEMBERSHIP",
        "M-PV3.8_SCIENTIFIC_EVIDENCE",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            errors.extend(_validate_forbidden_semantics(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_validate_forbidden_semantics(child, f"{location}[{index}]"))
    elif isinstance(value, str) and value in forbidden:
        errors.append(f"{location}: forbidden final/scientific promotion value {value}")
    return errors


def _validate_provenance_and_prerequisites(receipt: Mapping[str, Any], errors: list[str]) -> None:
    sw01 = receipt.get("sw01")
    window = receipt.get("window")
    r1 = receipt.get("r1")
    presence = receipt.get("presence")
    prototype = receipt.get("prototype")
    observed = receipt.get("observed_outcome")
    if not all(isinstance(value, Mapping) for value in (sw01, window, r1, presence, prototype)):
        return

    source_pass = sw01.get("overall_status") == SW01_PASS_STATUS and sw01.get("source_validation_status") == SW01_PASS_STATUS
    window_ready = window.get("ready") is True
    presence_ready = presence.get("gate_satisfied") is True and presence.get("status") == "PRESENCE_GATE_SATISFIED"
    r1_ready = r1.get("status") in {"PASS", "READY"} and r1.get("sample_count") == R1_SAMPLE_COUNT and r1.get("r1_sample_count") == R1_SAMPLE_COUNT
    chain = sw01.get("contributing_receipt_sha256_chain")
    chain_ready = isinstance(chain, list) and bool(chain)
    prerequisites = {
        "sw01_pass": source_pass,
        "window_ready": window_ready,
        "presence_gate_satisfied": presence_ready,
        "r1_ready": r1_ready,
        "receipt_chain_present": chain_ready,
    }
    success_claimed = observed in SUCCESS_OUTCOMES or prototype.get("result_status") in SUCCESS_OUTCOMES
    if success_claimed and not all(prerequisites.values()):
        missing = [name for name, ready in prerequisites.items() if not ready]
        errors.append(f"prototype: physiology success is invalid while prerequisites are unavailable: {missing}")

    if prototype.get("reached") is True:
        if not all(prerequisites.values()):
            missing = [name for name, ready in prerequisites.items() if not ready]
            errors.append(f"prototype: reached=true is inconsistent with M-PROT-3 V3 prerequisites: {missing}")
        if observed not in SUCCESS_OUTCOMES:
            errors.append("prototype: reached=true requires observed_outcome physiology success/eligible")
    else:
        if observed in SUCCESS_OUTCOMES:
            errors.append("prototype: reached=false cannot have a physiology success/eligible observed outcome")

    if not window_ready and (r1.get("sample_count") != 0 or r1.get("status") in {"PASS", "READY"}):
        errors.append("r1: R1 cannot be ready when the M-PROT-3 window is unavailable")


def validate_smoke_receipt(receipt: Mapping[str, Any], label: str = "receipt") -> list[str]:
    """Return deterministic validation errors for one M-PROT-4 SmokeReceipt."""

    if not isinstance(receipt, Mapping):
        return [f"{label}: must be an object"]
    errors: list[str] = []
    errors.extend(_find_path_leaks(receipt, label))
    errors.extend(_validate_forbidden_semantics(receipt, label))
    errors.extend(_required_fields(receipt, sorted(TOP_LEVEL_FIELDS), label))
    errors.extend(_unexpected_fields(receipt, TOP_LEVEL_FIELDS, label))

    if receipt.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}.schema_version: unsupported schema version")
    if receipt.get("phase") != PHASE:
        errors.append(f"{label}.phase: must be M-PROT-4")
    if receipt.get("wiring_receipt_version") != WIRING_RECEIPT_VERSION:
        errors.append(f"{label}.wiring_receipt_version: M-PROT-3 V3 provenance is required")
    if not isinstance(receipt.get("case_id"), str) or CASE_ID_RE.fullmatch(receipt.get("case_id", "")) is None:
        errors.append(f"{label}.case_id: malformed or missing case id")
    case_class = receipt.get("case_class")
    if case_class not in ALLOWED_CASE_CLASSES:
        errors.append(f"{label}.case_class: unsupported smoke class")
    if not _non_empty_string(receipt.get("input_fixture_id")):
        errors.append(f"{label}.input_fixture_id: missing fixture identity")
    if not _portable_reference(receipt.get("input_fixture_reference")):
        errors.append(f"{label}.input_fixture_reference: must be repository-relative and portable")
    _validate_sha(receipt.get("input_fixture_sha256"), f"{label}.input_fixture_sha256", errors)
    if receipt.get("expected_outcome") not in ALLOWED_OUTCOMES:
        errors.append(f"{label}.expected_outcome: unsupported outcome")
    if receipt.get("observed_outcome") not in ALLOWED_OUTCOMES:
        errors.append(f"{label}.observed_outcome: unsupported outcome")

    source = receipt.get("source")
    if not isinstance(source, Mapping):
        errors.append(f"{label}.source: must be an object")
    else:
        errors.extend(_required_fields(source, sorted(SOURCE_FIELDS), f"{label}.source"))
        errors.extend(_unexpected_fields(source, SOURCE_FIELDS, f"{label}.source"))
        _validate_string_fields(source, sorted(SOURCE_FIELDS), f"{label}.source", errors)

    _validate_sw01(receipt.get("sw01"), errors)
    _validate_window(receipt.get("window"), errors)
    _validate_r1(receipt.get("r1"), errors)
    _validate_presence(receipt.get("presence"), errors)
    _validate_prototype(receipt.get("prototype"), errors)
    _validate_flags(receipt.get("flags"), errors)
    _validate_track_f(receipt.get("track_f"), errors)

    lineage = receipt.get("lineage_class")
    if lineage not in ALLOWED_LINEAGE_CLASSES:
        errors.append(f"{label}.lineage_class: only explicit non-final smoke lineage is allowed")
    elif case_class in CASE_LINEAGE and lineage != CASE_LINEAGE[case_class]:
        errors.append(f"{label}: case_class and lineage_class do not match")
    _validate_provenance_and_prerequisites(receipt, errors)
    return errors


def validate_schema_document(schema_path: Path = SCHEMA_PATH) -> list[str]:
    """Validate the frozen schema identity and safety constants."""

    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"schema: {exc}"]
    errors: list[str] = []
    if schema.get("$id") != SCHEMA_ID:
        errors.append("schema: unexpected $id")
    if schema.get("properties", {}).get("schema_version", {}).get("const") != SCHEMA_VERSION:
        errors.append("schema: schema_version const is not frozen")
    if schema.get("properties", {}).get("phase", {}).get("const") != PHASE:
        errors.append("schema: phase const is not M-PROT-4")
    if schema.get("properties", {}).get("wiring_receipt_version", {}).get("const") != WIRING_RECEIPT_VERSION:
        errors.append("schema: wiring_receipt_version must preserve M-PROT-3-WIRING-RECEIPT-V3")
    prototype = schema.get("$defs", {}).get("prototype", {}).get("properties", {})
    expected = {
        "panel_id": B23_PANEL_ID,
        "artifact_path": B23_ARTIFACT_PATH,
        "artifact_sha256": B23_ARTIFACT_SHA256,
        "parameter_sha256": B23_PARAMETER_SHA256,
        "scaler_path": B23_SCALER_PATH,
        "scaler_sha256": B23_SCALER_SHA256,
        "representation": B23_REPRESENTATION,
    }
    for field, value in expected.items():
        if prototype.get(field, {}).get("const") != value:
            errors.append(f"schema: prototype.{field} const is not frozen")
    flags = schema.get("$defs", {}).get("flags", {}).get("properties", {})
    for field in ("FINAL_GOVERNED_EVALUATION", "D1_ADMISSIBLE", "LIVE_HARDWARE"):
        if flags.get(field, {}).get("const") is not False:
            errors.append(f"schema: flags.{field} must be const false")
    return errors


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "validate-schema"), nargs="?", default="validate")
    parser.add_argument("--case-file", type=Path, default=None)
    parser.add_argument("--schema-file", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args(argv)
    if args.command == "validate-schema":
        errors = validate_schema_document(args.schema_file)
        result = {"ok": not errors, "errors": errors, "schema_id": SCHEMA_ID}
    else:
        if args.case_file is None:
            result = {"ok": False, "errors": ["--case-file is required"], "schema_id": SCHEMA_ID}
        else:
            try:
                case = _read_json(args.case_file)
                errors = validate_smoke_receipt(case)
                result = {"ok": not errors, "errors": errors, "case_id": case.get("case_id"), "schema_id": SCHEMA_ID}
            except (OSError, json.JSONDecodeError, AttributeError) as exc:
                result = {"ok": False, "errors": [str(exc)], "schema_id": SCHEMA_ID}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(_main())
