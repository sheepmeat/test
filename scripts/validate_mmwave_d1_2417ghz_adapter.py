#!/usr/bin/env python3
"""Focused validator for the D1 native adapter evidence.

The raw payload is intentionally not required to be tracked.  If it is
present locally, its size/MD5/SHA-256 are rechecked; otherwise the validator
checks the compact recorded acquisition evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "datasets/mmwave/manifests/M-PV0_D1_2417ghz_adapter"
PAYLOAD = ROOT / "datasets/raw_archives/external_datasets/d1_2417ghz/datasets_scidata_vsmdb.zip"
REQUIRED_FILES = (
    "source_acquisition.json",
    "payload_inventory.json",
    "schema_audit.json",
    "adapter_contract.json",
    "recording_inventory.json",
    "exception_registry.json",
    "validation_result.json",
    "checksums.json",
)
ABSOLUTE_PATH_RE = re.compile(r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)")


def load(name: str) -> Any:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contains_absolute_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_absolute_path(key) or contains_absolute_path(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_absolute_path(item) for item in value)
    if isinstance(value, str):
        return bool(ABSOLUTE_PATH_RE.search(value))
    return False


def validate() -> dict[str, Any]:
    errors: list[str] = []
    for name in REQUIRED_FILES:
        if not (EVIDENCE / name).is_file():
            errors.append(f"MISSING_EVIDENCE:{name}")
    if errors:
        return {"ok": False, "gate": "BLOCKED", "errors": errors}

    docs = {name: load(name) for name in REQUIRED_FILES}
    for name, document in docs.items():
        if contains_absolute_path(document):
            errors.append(f"ABSOLUTE_PATH:{name}")

    source = docs["source_acquisition.json"]
    archive = docs["payload_inventory.json"]
    schema = docs["schema_audit.json"]
    contract = docs["adapter_contract.json"]
    inventory = docs["recording_inventory.json"]
    exceptions = docs["exception_registry.json"]
    recorded_validation = docs["validation_result.json"]
    checksums = docs["checksums.json"]

    if source["source_id"] != "D1":
        errors.append("SOURCE_ID")
    if source["verification"]["status"] != "PASS":
        errors.append("PAYLOAD_VERIFICATION")
    if source["observed"]["byte_size"] != source["expected"]["byte_size"]:
        errors.append("PAYLOAD_SIZE")
    if source["observed"]["md5"] != source["expected"]["md5"]:
        errors.append("PAYLOAD_MD5")
    if source["local_payload"]["git_tracked"]:
        errors.append("RAW_PAYLOAD_TRACKED")
    if archive["mat_recording_member_count"] != inventory["recording_count"]:
        errors.append("ARCHIVE_RECORDING_COUNT")
    if archive["mat_recording_member_count"] != 265:
        errors.append("EXPECTED_RECORDING_COUNT")
    if archive["subject_count"] != 11 or schema["subject_inventory"]["subject_count"] != 11:
        errors.append("SUBJECT_COUNT")
    if schema["observed_field_presence"].get("radar_I") != 265:
        errors.append("RADAR_I_PRESENCE")
    if schema["observed_field_presence"].get("radar_Q") != 265:
        errors.append("RADAR_Q_PRESENCE")
    if schema["observed_field_presence"].get("respiration") != 265:
        errors.append("RESPIRATION_PRESENCE")
    if schema["required_channel_length_consistency"]["mismatched_recordings"]:
        errors.append("REQUIRED_LENGTH_MISMATCH")
    if schema["observed_sample_rates_hz"] != {"500.0": 36, "2000.0": 229}:
        errors.append("SAMPLE_RATE_DISTRIBUTION")
    if schema["payload_inventory_summary"]["observed_reference_csv_files"] != 265:
        errors.append("REFERENCE_CSV_COUNT")
    if contract["source_sampling_rate"]["observed_values_hz"] != [500.0, 2000.0]:
        errors.append("CONTRACT_SAMPLE_RATES")
    if contract["baseband_channel_decoding"]["array_order_inference"] != "FORBIDDEN":
        errors.append("ARRAY_ORDER_INFERENCE")
    if contract["reference_channel"]["name"] != "respiration":
        errors.append("REFERENCE_CHANNEL")
    if "window-local MAD normalization" not in contract["forbidden_processing"]:
        errors.append("NORMALIZATION_FORBIDDEN_POLICY")

    recordings = inventory["recordings"]
    if len(recordings) != 265:
        errors.append("INVENTORY_ROW_COUNT")
    statuses = {row["adaptation_status"] for row in recordings}
    if statuses != {"SUCCESS"}:
        errors.append("ADAPTER_STATUS")
    if any(not row["required_channel_lengths_equal"] for row in recordings):
        errors.append("RECORD_REQUIRED_LENGTH_FLAG")
    for row in recordings:
        metadata = row["adapter_output"]
        if metadata.get("adapter_id") != contract["adapter_id"]:
            errors.append(f"RECORD_ADAPTER_ID:{row['recording_id']}")
        if metadata.get("quality_flags", {}).get("large_missing_region_interpolated") is not False:
            errors.append(f"INTERPOLATION_FLAG:{row['recording_id']}")
        if metadata.get("quality_flags", {}).get("native_amplitude_preserved") is not True:
            errors.append(f"AMPLITUDE_FLAG:{row['recording_id']}")
        output_names = set(metadata.get("output_signal_names", []))
        if not {"native_unwrapped_phase_rad", "relative_displacement_m", "respiration"}.issubset(output_names):
            errors.append(f"OUTPUT_CONTRACT:{row['recording_id']}")

    if exceptions["total_blockers"] != 0:
        errors.append("EXCEPTION_BLOCKERS")
    if not recorded_validation["ok"] or recorded_validation["gate"] != "PASS_WITH_LIMITATIONS":
        errors.append("RECORDED_VALIDATION_RESULT")
    if recorded_validation["native_adapter_behavior"]["model_training_performed"]:
        errors.append("MODEL_TRAINING_PERFORMED")
    if recorded_validation["native_adapter_behavior"]["D0_or_MR60_normalization_used"]:
        errors.append("D0_MR60_NORMALIZATION_USED")
    if recorded_validation["native_adapter_behavior"]["D2_semantics_touched"]:
        errors.append("D2_SEMANTICS_TOUCHED")

    for name, recorded_hash in checksums["files"].items():
        path = EVIDENCE / name
        if not path.is_file() or sha256_file(path) != recorded_hash:
            errors.append(f"EVIDENCE_CHECKSUM:{name}")
    for relative_path, recorded_hash in checksums.get("code", {}).get("files", {}).items():
        path = ROOT / relative_path
        if not path.is_file() or sha256_file(path) != recorded_hash:
            errors.append(f"CODE_CHECKSUM:{relative_path}")

    tracked_raw = subprocess.run(
        ["git", "ls-files", "--", "*.zip", "*.mat", "datasets/raw_archives"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if tracked_raw:
        errors.append("RAW_FILE_TRACKED")

    local_payload_recheck: dict[str, Any]
    if PAYLOAD.is_file():
        observed_sha = sha256_file(PAYLOAD)
        observed_md5 = md5_file(PAYLOAD)
        local_payload_recheck = {
            "performed": True,
            "size_matches": PAYLOAD.stat().st_size == source["expected"]["byte_size"],
            "md5_matches": observed_md5 == source["expected"]["md5"],
            "sha256_matches_recorded": observed_sha == checksums["payload"]["sha256"],
        }
        if not all(local_payload_recheck.values()):
            errors.append("LOCAL_PAYLOAD_RECHECK")
    else:
        local_payload_recheck = {"performed": False, "reason": "raw payload intentionally not tracked"}

    return {
        "phase": "M-PV0_D1_2417GHZ_ADAPTER",
        "schema_version": "D1.1",
        "ok": not errors,
        "gate": "PASS_WITH_LIMITATIONS" if not errors else "BLOCKED",
        "errors": errors,
        "recording_count": len(recordings),
        "optional_reference_length_mismatch_count": schema["required_channel_length_consistency"]["optional_reference_length_mismatch_count"],
        "local_payload_recheck": local_payload_recheck,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
