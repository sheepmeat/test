#!/usr/bin/env python3
"""I2 historical JSONL replay harness through the frozen I1 semantic boundary.

Replays existing MR60 telemetry evidence deterministically. Does not train, does
not run V1/V2 physiology, does not redefine Q2 thresholds, and does not perform
the I3 fail-closed regression gate.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mmwave_i2_replay_adapter import (  # noqa: E402
    I2_CONTRACT_ID,
    I2_HARNESS_ID,
    I2_RESULT_SCHEMA_ID,
    classify_schema,
    i1_output_for_replay,
    map_mr60_row_to_i1,
    parse_status_for_row,
    replay_event_id,
)
from scripts.mmwave_i1_runtime_io_contract import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    INPUT_CONTRACT_ID,
    OUTPUT_CONTRACT_ID,
    PROVENANCE_CONTRACT_ID,
    Q2_CONTRACT_ID,
    REPLAY_INTERFACE_ID,
    SEMANTIC_CONTRACT_ID,
    canonical_dumps,
    check_absolute_paths,
    dump_json,
    load_json,
    serialize_runtime_record,
    sha256_bytes,
    validate_runtime_input,
    validate_runtime_output,
)

PHASE_ID = "I2"
SCHEMA_VERSION = "I2.1"
AUDIT_DATE = "2026-08-23"
BASE_SHA = "38ff2466280125bb7cdd073e163348fe4a9e9ec8"
I1_HANDOFF_COMMIT = "83c8045755f37bcb7bb72ab87aa56506f8603bb8"
I2_SCHEMA_REGISTRY_ID = "MMWAVE_V2_I2_SCHEMA_COMPATIBILITY_REGISTRY_V1"
Q1_PROFILE_ID = "MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1"

CONFIG_PATH = ROOT / "config/mmwave/i2_jsonl_replay_contract.json"
MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_I2_jsonl_replay"
Q1_INVENTORY = ROOT / "datasets/mmwave/manifests/M-PV0_Q1_mr60_timing_corruption/evidence_inventory.json"
I1_CONFIG = ROOT / "config/mmwave/i1_runtime_semantic_contract.json"
I1_REPLAY_SKELETON = (
    ROOT / "datasets/mmwave/manifests/M-PV0_I1_runtime_io_contract/replay_interface_skeleton.json"
)

REPLAY_MODES = ("AS_RECORDED", "FAST", "SCALED")
SOURCE_CLASSES = ("PHYSICAL_MR60_JSONL", "SYNTHETIC_Q1_Q2_FIXTURE", "PUBLIC_OFFLINE_FIXTURE")

REPRESENTATIVE_SESSIONS = (
    {
        "role": "modern_schema_1_2",
        "session_id": "LEGACY_2026-08-01_heartrate_watch_s1_preflight_v120_15s",
    },
    {
        "role": "legacy_schema_1_0",
        "session_id": "LEGACY_2026-07-28_breath15_full_preflight_10s",
    },
    {
        "role": "source_republication",
        "session_id": "LEGACY_2026-07-13_empty_desk_collector_v2_30s",
    },
    {
        "role": "q2_handoff_freeze_like_95_run",
        "session_id": "LEGACY_2026-07-25_empty_gate_attempt03_15s",
    },
    {
        "role": "q2_handoff_freeze_like_3598_run",
        "session_id": "LEGACY_2026-07-25_occupied_d15_v1_360s",
        "max_rows": 64,
        "full_session_replayed": False,
        "note": "3598-run evidence is replayable; committed summary uses a 64-row prefix",
    },
    {
        "role": "timestamp_collision",
        "session_id": "LEGACY_2026-07-13_empty_desk_collector_v1_30s",
    },
    {
        "role": "phase_age_absent",
        "session_id": "LEGACY_2026-07-13_empty_desk_prechange_30s",
    },
)

MANIFEST_JSON_FILES = (
    "replay_contract.json",
    "schema_compatibility_registry.json",
    "replay_source_inventory.json",
    "representative_session_results.json",
    "determinism_audit.json",
    "lineage_audit.json",
    "exception_registry.json",
)


class I2ReplayError(RuntimeError):
    pass


class SessionReplayState:
    def __init__(self) -> None:
        self.last_seq: int | None = None
        self.last_device_id: Any = None
        self.last_firmware: Any = None
        self.seq_events: list[str] = []

    def reset(self, reason: str) -> None:
        self.last_seq = None
        self.last_device_id = None
        self.last_firmware = None
        self.seq_events.append(f"RESET:{reason}")

    def observe(self, seq: Any, device_id: Any, firmware: Any) -> str | None:
        if self.last_device_id is not None and device_id != self.last_device_id:
            self.reset("device_id_change")
        if self.last_firmware is not None and firmware != self.last_firmware:
            self.reset("firmware_change")
        self.last_device_id = device_id
        self.last_firmware = firmware
        if seq is None or not isinstance(seq, (int, float)) or isinstance(seq, bool):
            return None
        seq_int = int(seq)
        audit = None
        if self.last_seq is None:
            audit = "INCREMENT"
        elif seq_int == self.last_seq:
            audit = "REPEAT"
        elif seq_int == self.last_seq + 1:
            audit = "INCREMENT"
        elif seq_int < self.last_seq:
            audit = "RESET"
            self.seq_events.append("RESET:seq_decrease")
        else:
            audit = "GAP"
        self.last_seq = seq_int
        if audit:
            self.seq_events.append(audit)
        return audit


class VirtualReplayClock:
    def __init__(self, mode: str = "FAST", scale: float = 1.0) -> None:
        if mode not in REPLAY_MODES:
            raise I2ReplayError("UNKNOWN_REPLAY_MODE")
        self.mode = mode
        self.scale = float(scale)
        self._t0: float | None = None
        self._prev: float | None = None
        self._virtual = 0.0
        self._index = 0

    def observe(self, evidence_ts: float | None) -> float:
        if evidence_ts is None or not math.isfinite(evidence_ts):
            virtual = self._virtual
            self._index += 1
            if self.mode == "FAST":
                self._virtual = float(self._index)
            return virtual
        if self._t0 is None:
            self._t0 = evidence_ts
        if self.mode == "FAST":
            virtual = float(self._index)
        elif self.mode == "AS_RECORDED":
            virtual = evidence_ts - self._t0
        else:
            delta = 0.0 if self._prev is None else max(0.0, evidence_ts - self._prev) * self.scale
            self._virtual += delta
            virtual = self._virtual
        self._prev = evidence_ts
        self._index += 1
        return virtual


def git_cat_blob(sha: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "-p", sha], cwd=ROOT)


def blob_exists(sha: str) -> bool:
    try:
        subprocess.check_output(["git", "cat-file", "-t", sha], cwd=ROOT, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def parse_jsonl_bytes(raw: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines()):
        if not line.strip():
            continue
        text = line.decode("utf-8", errors="replace")
        try:
            row = json.loads(text)
            if not isinstance(row, dict):
                records.append({"_i2_reject": "INVALID_JSON", "_raw": text, "_row_index": index})
                continue
            status = parse_status_for_row(row, text)
            if status:
                records.append({"_i2_reject": status, "_raw": text, "_row_index": index, "_row": row})
            else:
                records.append({"_i2_row": row, "_row_index": index})
        except json.JSONDecodeError:
            status = parse_status_for_row(None, text)
            records.append({"_i2_reject": status or "INVALID_JSON", "_raw": text, "_row_index": index})
    return records


def apply_external_quality_policy(timestamps_ms: list[float], values: list[float]) -> dict[str, Any]:
    """Optional Q2 reuse. Not invoked by default replay. Does not fork thresholds."""
    from scripts.mmwave_q2_input_unavailable import evaluate_availability

    return evaluate_availability(timestamps_ms, values)


def load_inventory_index() -> dict[str, dict[str, Any]]:
    inventory = load_json(Q1_INVENTORY)
    return {item["session_id"]: item for item in inventory["sessions"]}


def replay_parsed_rows(
    parsed: list[dict[str, Any]],
    *,
    session_id: str,
    source_id: str,
    git_blob_sha: str | None,
    mode: str,
    source_class: str,
    synthetic: dict[str, Any] | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    clock = VirtualReplayClock(mode=mode)
    state = SessionReplayState()
    replayed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[str] = []
    evidence_timestamps: list[Any] = []
    event_ids: list[str] = []
    seq_audits: list[str] = []
    used = parsed if max_rows is None else parsed[:max_rows]
    for item in used:
        row_index = int(item["_row_index"])
        if "_i2_reject" in item:
            rejected.append(
                {
                    "reason": item["_i2_reject"],
                    "row_index": row_index,
                    "session_id": session_id,
                }
            )
            continue
        row = item["_i2_row"]
        seq_audit = state.observe(row.get("seq"), row.get("device_id"), row.get("firmware_version"))
        if seq_audit:
            seq_audits.append(seq_audit)
        i1_input = map_mr60_row_to_i1(
            row,
            session_id=session_id,
            row_index=row_index,
            git_blob_sha=git_blob_sha,
            source_id=source_id,
            replay_harness_sha=BASE_SHA,
            synthetic=synthetic,
        )
        input_errors = validate_runtime_input(i1_input)
        if input_errors:
            rejected.append(
                {
                    "reason": "I1_INPUT_VALIDATION",
                    "details": input_errors,
                    "row_index": row_index,
                    "session_id": session_id,
                }
            )
            continue
        ts = i1_input["timestamps"]["transport_publish_time"]["value"]
        evidence_ts = float(ts) if ts is not None else None
        virtual = clock.observe(evidence_ts)
        evidence_timestamps.append(ts)
        event_id = replay_event_id(
            source_id=source_id,
            session_id=session_id,
            row_index=row_index,
            seq=row.get("seq"),
            timestamp_ms=ts,
            git_blob_sha=git_blob_sha,
        )
        event_ids.append(event_id)
        i1_output = i1_output_for_replay(i1_input)
        output_errors = validate_runtime_output(i1_output, i1_input)
        if output_errors:
            rejected.append(
                {
                    "reason": "I1_OUTPUT_VALIDATION",
                    "details": output_errors,
                    "row_index": row_index,
                    "session_id": session_id,
                }
            )
            continue
        if i1_input["freshness"]["phase_age_ms"]["status"] != "FIELD_PRESENT":
            warnings.append("PHASE_AGE_NOT_PRESENT")
        if i1_input["presence"]["status"] != "FIELD_PRESENT":
            warnings.append("PRESENCE_FIELD_NOT_PRESENT")
        replayed.append(
            {
                "evidence_timestamp_ms": ts,
                "i1_input": i1_input,
                "i1_output": i1_output,
                "parser_status": "OK",
                "replay_event_id": event_id,
                "runtime_window_id": i1_input["provenance"]["runtime_window_id"],
                "row_index": row_index,
                "seq_audit": seq_audit,
                "source_class": source_class,
                "virtual_replay_time_ms": virtual,
            }
        )
    warning_counts: dict[str, int] = {}
    for warning in warnings:
        warning_counts[warning] = warning_counts.get(warning, 0) + 1
    compact_hash = sha256_bytes(
        canonical_dumps(
            {
                "event_ids": event_ids,
                "inputs": [serialize_runtime_record(item["i1_input"]) for item in replayed],
                "outputs": [serialize_runtime_record(item["i1_output"]) for item in replayed],
                "rejected": rejected,
                "seq_audits": seq_audits,
                "virtual": [item["virtual_replay_time_ms"] for item in replayed],
            }
        ).encode("utf-8")
    )
    return {
        "compact_result_sha256": compact_hash,
        "evidence_timestamps_ms": evidence_timestamps,
        "event_ids": event_ids,
        "mode": mode,
        "parsed": len(used),
        "rejected": rejected,
        "rejected_count": len(rejected),
        "replayed": replayed,
        "replayed_count": len(replayed),
        "seq_audit_counts": {
            name: seq_audits.count(name) for name in ("INCREMENT", "GAP", "REPEAT", "RESET")
        },
        "session_id": session_id,
        "source_class": source_class,
        "warning_counts": warning_counts,
        "warnings": len(warnings),
    }


def replay_blob_session(spec: dict[str, Any], inventory_row: dict[str, Any], mode: str = "FAST") -> dict[str, Any]:
    sha = inventory_row.get("git_blob_sha")
    session_id = spec["session_id"]
    summary = {
        "evidence_family": inventory_row.get("evidence_family"),
        "firmware_version": inventory_row.get("firmware_version"),
        "full_session_replayed": spec.get("full_session_replayed", True),
        "git_blob_sha": sha,
        "inventory_current_path": inventory_row.get("inventory_current_path"),
        "max_republication_run": inventory_row.get("max_republication_run"),
        "note": spec.get("note"),
        "packet_count_inventory": inventory_row.get("packet_count"),
        "phase_age_available": inventory_row.get("phase_age_available"),
        "q1_status": inventory_row.get("q1_status"),
        "q2_handoff_reason": inventory_row.get("q2_handoff_reason"),
        "role": spec["role"],
        "schema_version": inventory_row.get("schema_version"),
        "session_id": session_id,
        "source_class": "PHYSICAL_MR60_JSONL",
    }
    if not sha:
        return {**summary, "status": "UNAVAILABLE", "unavailable_reason": "NO_GIT_BLOB"}
    if not blob_exists(str(sha)):
        return {**summary, "status": "UNAVAILABLE", "unavailable_reason": "GIT_BLOB_NOT_IN_REPO"}
    parsed = parse_jsonl_bytes(git_cat_blob(str(sha)))
    result = replay_parsed_rows(
        parsed,
        session_id=session_id,
        source_id="device-mr60-historical-jsonl",
        git_blob_sha=str(sha),
        mode=mode,
        source_class="PHYSICAL_MR60_JSONL",
        max_rows=spec.get("max_rows"),
    )
    compact = {
        **summary,
        "compact_result_sha256": result["compact_result_sha256"],
        "first_replay_event_id": result["event_ids"][0] if result["event_ids"] else None,
        "last_replay_event_id": result["event_ids"][-1] if result["event_ids"] else None,
        "mode": mode,
        "parsed": result["parsed"],
        "rejected_count": result["rejected_count"],
        "rejected_reasons": sorted({item["reason"] for item in result["rejected"]}),
        "replayed_count": result["replayed_count"],
        "seq_audit_counts": result["seq_audit_counts"],
        "status": "REPLAYED",
        "warning_counts": result["warning_counts"],
        "warnings": result["warnings"],
    }
    compact["_result"] = result
    return compact


def synthetic_fixture_rows() -> list[dict[str, Any]]:
    rows = []
    for index in range(4):
        rows.append(
            {
                "_i2_row": {
                    "breath_phase": 0.1 * (index + 1),
                    "firmware_version": "synthetic",
                    "human_detected_raw": True,
                    "phase_age_ms": 8,
                    "schema_version": "1.2",
                    "seq": 10 + index,
                    "ts_monotonic_ms": 1000 + (index * 100),
                },
                "_row_index": index,
            }
        )
    return rows


def public_offline_replay(mode: str = "FAST") -> dict[str, Any]:
    fixture = load_json(I1_REPLAY_SKELETON)["tiny_deterministic_fixture"]["public_d0_without_phase_age_eligible"]
    record = fixture["input"]
    clock = VirtualReplayClock(mode=mode)
    virtual = clock.observe(record["timestamps"]["window_start"]["value"])
    event_id = replay_event_id(
        source_id=record["source"]["source_id"],
        session_id=record["session"]["session_id"],
        row_index=0,
        seq=None,
        timestamp_ms=record["timestamps"]["window_start"]["value"],
        git_blob_sha=None,
    )
    output = i1_output_for_replay(record)
    compact = sha256_bytes(
        canonical_dumps({"event_id": event_id, "input": serialize_runtime_record(record)}).encode("utf-8")
    )
    return {
        "compact_result_sha256": compact,
        "event_ids": [event_id],
        "i1_input": record,
        "i1_output": output,
        "mode": mode,
        "parsed": 1,
        "rejected_count": 0,
        "replayed_count": 1,
        "session_id": record["session"]["session_id"],
        "source_class": "PUBLIC_OFFLINE_FIXTURE",
        "status": "REPLAYED",
        "virtual_replay_time_ms": virtual,
        "warnings": 0,
    }


def build_schema_registry() -> dict[str, Any]:
    return {
        "audit_date": AUDIT_DATE,
        "contract_id": I2_SCHEMA_REGISTRY_ID,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "versions": {
            "1.0": {
                "absent_legacy_fields": ["config_hash", "firmware_version often null"],
                "known_limitation": "firmware identity may be null",
                "normalization": "map present fields only; do not fabricate firmware/config",
                "optional_fields": ["firmware_version", "config_hash", "session_id"],
                "required_replay_identity_fields": ["ts_monotonic_ms", "seq"],
            },
            "1.1": {
                "absent_legacy_fields": ["some 1.2 freeze/filter flags"],
                "known_limitation": "firmware present as safenest-mr60-esp/1.1.0",
                "normalization": "preserve firmware_version; do not upgrade schema",
                "optional_fields": ["config_hash", "session_id"],
                "required_replay_identity_fields": ["ts_monotonic_ms", "seq", "phase_age_ms"],
            },
            "1.2": {
                "absent_legacy_fields": [],
                "known_limitation": "Pi host receive timestamp still absent from ESP JSONL",
                "normalization": "preserve config_hash and auxiliary 1.2 fields under mr60_telemetry",
                "optional_fields": ["session_id", "freeze_detected", "human_detected_stable"],
                "required_replay_identity_fields": ["ts_monotonic_ms", "seq", "phase_age_ms"],
            },
            "legacy_unversioned": {
                "absent_legacy_fields": ["schema_version", "phase_age_ms", "firmware_version", "config_hash"],
                "known_limitation": "source-update estimate cannot be formed; presence may exist",
                "normalization": "FIELD_ABSENT_LEGACY; never fill phase_age_ms",
                "optional_fields": ["human_detected_raw", "breath_phase"],
                "required_replay_identity_fields": ["ts_monotonic_ms", "seq"],
            },
        },
    }


def build_contract() -> dict[str, Any]:
    return {
        "audit_date": AUDIT_DATE,
        "base_sha": BASE_SHA,
        "contract_id": I2_CONTRACT_ID,
        "d2_used": False,
        "harness_id": I2_HARNESS_ID,
        "i1_dependency": {
            "handoff_commit": I1_HANDOFF_COMMIT,
            "input": INPUT_CONTRACT_ID,
            "merged_on_main_squash": BASE_SHA,
            "output": OUTPUT_CONTRACT_ID,
            "provenance": PROVENANCE_CONTRACT_ID,
            "replay_skeleton": REPLAY_INTERFACE_ID,
            "semantic": SEMANTIC_CONTRACT_ID,
        },
        "i3_regression_gate_performed": False,
        "model_inference": False,
        "model_training": False,
        "mr60_supervised_use": False,
        "phase": PHASE_ID,
        "q1_profile_retuned": False,
        "q2_thresholds_redefined": False,
        "q3_false_positive_gate_performed": False,
        "replay_modes": list(REPLAY_MODES),
        "result_schema_id": I2_RESULT_SCHEMA_ID,
        "schema_compatibility_registry_id": I2_SCHEMA_REGISTRY_ID,
        "schema_version": SCHEMA_VERSION,
        "session_unit": "one physical/logical JSONL session; no concatenation",
        "source_classes": list(SOURCE_CLASSES),
        "virtual_clock": {
            "as_recorded": "virtual_time = evidence_ts - session_t0",
            "evidence_timestamps_modified": False,
            "fast": "schedule by event index; evidence timestamps unchanged",
            "realtime_sleep_required_for_validation": False,
            "scaled": "scale affects scheduling deltas only",
        },
    }


def generate() -> dict[str, Any]:
    if not I1_CONFIG.is_file():
        raise I2ReplayError("I1_CONTRACT_MISSING")
    semantic = load_json(I1_CONFIG)
    if semantic.get("contract_id") != SEMANTIC_CONTRACT_ID:
        raise I2ReplayError("I1_CONTRACT_ID")
    inventory = load_inventory_index()
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    physical: list[dict[str, Any]] = []
    full_results: list[dict[str, Any]] = []
    for spec in REPRESENTATIVE_SESSIONS:
        row = inventory.get(spec["session_id"])
        if not row:
            physical.append({"session_id": spec["session_id"], "status": "UNAVAILABLE", "unavailable_reason": "NOT_IN_Q1_INVENTORY"})
            continue
        compact = replay_blob_session(spec, row, mode="FAST")
        stored = dict(compact)
        stored.pop("_result", None)
        physical.append(stored)
        full_results.append(compact)
    synthetic_meta = {
        "mode": "CADENCE_JITTER",
        "original_sample_index": 0,
        "profile_id": Q1_PROFILE_ID,
        "seed": 7,
        "severity": "TYPICAL",
    }
    synthetic = replay_parsed_rows(
        synthetic_fixture_rows(),
        session_id="SYNTHETIC_Q1_CADENCE_JITTER_TINY",
        source_id="synthetic-q1-fixture",
        git_blob_sha=None,
        mode="FAST",
        source_class="SYNTHETIC_Q1_Q2_FIXTURE",
        synthetic=synthetic_meta,
    )
    public = public_offline_replay("FAST")
    second = []
    for spec, first in zip(REPRESENTATIVE_SESSIONS, full_results):
        if first.get("status") != "REPLAYED":
            continue
        again = replay_blob_session(spec, inventory[spec["session_id"]], mode="FAST")
        second.append(again["compact_result_sha256"] == first["compact_result_sha256"])
    synth2 = replay_parsed_rows(
        synthetic_fixture_rows(),
        session_id="SYNTHETIC_Q1_CADENCE_JITTER_TINY",
        source_id="synthetic-q1-fixture",
        git_blob_sha=None,
        mode="FAST",
        source_class="SYNTHETIC_Q1_Q2_FIXTURE",
        synthetic=synthetic_meta,
    )
    as_recorded = replay_parsed_rows(
        synthetic_fixture_rows(),
        session_id="SYNTHETIC_Q1_CADENCE_JITTER_TINY",
        source_id="synthetic-q1-fixture",
        git_blob_sha=None,
        mode="AS_RECORDED",
        source_class="SYNTHETIC_Q1_Q2_FIXTURE",
        synthetic=synthetic_meta,
    )
    evidence_unchanged = (
        synthetic["evidence_timestamps_ms"] == as_recorded["evidence_timestamps_ms"]
    )
    scheduling_changed = [row["virtual_replay_time_ms"] for row in synthetic["replayed"]] != [
        row["virtual_replay_time_ms"] for row in as_recorded["replayed"]
    ]
    unavailable_pi = [
        {
            "evidence_family": item.get("evidence_family"),
            "session_id": item["session_id"],
            "status": "UNAVAILABLE",
            "unavailable_reason": "NO_GIT_BLOB_IN_Q1_INVENTORY",
        }
        for item in load_json(Q1_INVENTORY)["sessions"]
        if not item.get("git_blob_sha")
    ]
    contract = build_contract()
    registry = build_schema_registry()
    source_inventory = {
        "audit_date": AUDIT_DATE,
        "phase": PHASE_ID,
        "physical_representative": physical,
        "public_offline_fixture": {
            "replayed_count": public["replayed_count"],
            "session_id": public["session_id"],
            "source_class": public["source_class"],
            "status": public["status"],
        },
        "schema_version": SCHEMA_VERSION,
        "synthetic_q1_q2_fixture": {
            "compact_result_sha256": synthetic["compact_result_sha256"],
            "profile_id": Q1_PROFILE_ID,
            "replayed_count": synthetic["replayed_count"],
            "seed": 7,
            "session_id": synthetic["session_id"],
            "source_class": synthetic["source_class"],
            "status": "REPLAYED",
        },
        "unavailable_inventoried_without_blob": unavailable_pi,
    }
    representative = {
        "audit_date": AUDIT_DATE,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "sessions": physical,
        "totals": {
            "parsed": sum(item.get("parsed", 0) for item in physical if item.get("status") == "REPLAYED"),
            "rejected": sum(item.get("rejected_count", 0) for item in physical if item.get("status") == "REPLAYED"),
            "replayed": sum(item.get("replayed_count", 0) for item in physical if item.get("status") == "REPLAYED"),
            "sessions_attempted": len(REPRESENTATIVE_SESSIONS),
            "sessions_successful": sum(1 for item in physical if item.get("status") == "REPLAYED"),
            "warnings": sum(item.get("warnings", 0) for item in physical if item.get("status") == "REPLAYED"),
        },
    }
    determinism = {
        "as_recorded_vs_fast_evidence_timestamps_identical": evidence_unchanged,
        "as_recorded_vs_fast_virtual_schedule_differs": scheduling_changed,
        "audit_date": AUDIT_DATE,
        "physical_repeat_identical": all(second) and bool(second),
        "schema_version": SCHEMA_VERSION,
        "synthetic_repeat_identical": synthetic["compact_result_sha256"] == synth2["compact_result_sha256"],
        "wall_clock_excluded_from_evidence_hash": True,
    }
    lineage = {
        "absolute_path_policy": "forbidden",
        "audit_date": AUDIT_DATE,
        "i1_contracts": [SEMANTIC_CONTRACT_ID, INPUT_CONTRACT_ID, OUTPUT_CONTRACT_ID, PROVENANCE_CONTRACT_ID],
        "i2_contract": I2_CONTRACT_ID,
        "physical_blob_shas": [item.get("git_blob_sha") for item in physical],
        "schema_version": SCHEMA_VERSION,
        "synthetic_lineage": synthetic_meta,
    }
    exceptions = {
        "entries": [
            {
                "code": "PI_HOST_RECEIVE_TIMESTAMP_UNAVAILABLE",
                "detail": "Inventoried ESP JSONL does not carry Pi host receive time",
            },
            {
                "code": "PR18_AND_RECENT_PI_BLOBS_ABSENT",
                "detail": "Q1 already recorded these families as unavailable git blobs",
            },
            {
                "code": "3598_RUN_PREFIX_ONLY_IN_COMMITTED_SUMMARY",
                "detail": "Full blob remains replayable via git object identity",
            },
        ],
        "firmware_identities_may_be_null": True,
        "i3_not_performed": True,
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
    }
    artifacts = {
        "replay_contract.json": contract,
        "schema_compatibility_registry.json": registry,
        "replay_source_inventory.json": source_inventory,
        "representative_session_results.json": representative,
        "determinism_audit.json": determinism,
        "lineage_audit.json": lineage,
        "exception_registry.json": exceptions,
    }
    checksums: dict[str, str] = {}
    for name, payload in artifacts.items():
        check_absolute_paths(payload, name, [])
        checksums[name] = dump_json(MANIFEST_DIR / name, payload)
    dump_json(CONFIG_PATH, contract)
    dump_json(
        MANIFEST_DIR / "checksums.json",
        {
            "algorithm": "SHA-256",
            "config_file": {
                "path": "config/mmwave/i2_jsonl_replay_contract.json",
                "sha256": sha256_bytes(CONFIG_PATH.read_text(encoding="utf-8").encode("utf-8")),
            },
            "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
            "files": checksums,
            "phase": PHASE_ID,
            "schema_version": SCHEMA_VERSION,
        },
    )
    return {"determinism": determinism, "representative": representative, "synthetic": synthetic, "public": public}


def main() -> int:
    generate()
    print(json.dumps({"ok": True, "phase": PHASE_ID, "manifest": str(MANIFEST_DIR.relative_to(ROOT))}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
