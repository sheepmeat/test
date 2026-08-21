#!/usr/bin/env python3
"""Focused D2 acquisition-lock validator. Fail closed. No payload parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_d2_locked_acquisition import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    AUDIT_DATE,
    DATASET_DOI,
    FORBIDDEN_SELECTION,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    MPV0_POLICY,
    PAYLOAD_FILENAME,
    PAYLOAD_LOGICAL_PATH,
    PHASE_ID,
    PUBLICATION_DOI,
    SCHEMA_VERSION,
    dump_json,
    git_ls_files,
    load_json,
    payload_path,
    sha256_bytes,
)

REQUIRED_NO = (
    "PAYLOAD_SEMANTIC_INSPECTION",
    "ARCHIVE_MEMBER_LISTING",
    "FEATURE_EXTRACTION",
    "MODEL_INFERENCE",
)


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
    if not MANIFEST_DIR.is_dir():
        return {
            "phase": PHASE_ID,
            "gate": "BLOCKED",
            "ok": False,
            "errors": ["MANIFEST_DIR_MISSING"],
        }

    files = {name: load_json(MANIFEST_DIR / name) for name in (*MANIFEST_JSON_FILES, "checksums.json")}
    for name, doc in files.items():
        check_absolute_paths(doc, name, errors)

    identity = files["source_identity.json"]
    acquisition = files["acquisition_record.json"]
    digest = files["payload_digest_lock.json"]
    access = files["access_state.json"]
    exceptions = files["exception_registry.json"]
    checksums = files["checksums.json"]
    policy = load_json(MPV0_POLICY)

    if identity.get("role") != "LOCKED_PUBLIC_CROSS_DEVICE_TEST":
        fail(errors, "D2_ROLE")
    if identity.get("dataset_doi") != DATASET_DOI or identity.get("publication_doi") != PUBLICATION_DOI:
        fail(errors, "D2_DOI")
    if identity.get("parent_m_pv0_lock", {}).get("commit") is None:
        fail(errors, "M_PV0_PARENT_LOCK_MISSING")
    if policy.get("roles", {}).get("D2") != "LOCKED_PUBLIC_CROSS_DEVICE_TEST":
        fail(errors, "M_PV0_ROLE_DRIFT")

    payload_acquired = bool(acquisition.get("payload_acquired"))
    tracked = git_ls_files(PAYLOAD_LOGICAL_PATH)
    if tracked:
        fail(errors, "PAYLOAD_GIT_TRACKED")
    if acquisition.get("payload_git_tracked") is True:
        fail(errors, "MANIFEST_CLAIMS_TRACKED_PAYLOAD")

    if payload_path().is_file() != payload_acquired:
        fail(errors, "PAYLOAD_PRESENCE_MISMATCH")

    if payload_acquired:
        if not digest.get("LOCAL_COMPUTED_SHA256"):
            fail(errors, "SHA256_MISSING")
        if digest.get("payload_byte_size") in (None, 0):
            fail(errors, "BYTE_SIZE_MISSING")
        if digest.get("hash_stable") is not True:
            fail(errors, "HASH_NOT_STABLE")
        if acquisition.get("D2_PAYLOAD_ACQUISITION") != "YES":
            fail(errors, "ACQUISITION_FLAG")
        if access.get("lock_state") != "ACQUIRED_AND_CRYPTOGRAPHICALLY_SEALED":
            fail(errors, "LOCK_STATE")
    else:
        if acquisition.get("D2_PAYLOAD_ACQUISITION") != "BLOCKED_AUTH_REQUIRED":
            fail(errors, "AUTH_BLOCK_NOT_RECORDED")
        if digest.get("LOCAL_COMPUTED_SHA256") is not None:
            fail(errors, "SHA256_WITHOUT_PAYLOAD")
        if access.get("lock_state") != "LOCKED_BEFORE_SEMANTIC_USE":
            fail(errors, "LOCK_STATE")

    for field in REQUIRED_NO:
        value = access.get(field)
        if value not in ("NO", False):
            fail(errors, f"{field}_NOT_NO")
    if access.get("MODEL_INFERENCE_COUNT") != 0:
        fail(errors, "MODEL_INFERENCE_COUNT")
    if access.get("candidate_inference_count") != 0:
        fail(errors, "CANDIDATE_INFERENCE_COUNT")
    for name in FORBIDDEN_SELECTION:
        if access.get("selection_policy", {}).get(name) != "FORBIDDEN":
            fail(errors, f"SELECTION_NOT_FORBIDDEN:{name}")
    if access.get("final_evaluation_authorized") is not False:
        fail(errors, "FINAL_EVAL_AUTHORIZED")
    if access.get("D2_DEVELOPMENT_DEPENDENCY_FOUND") != "NO":
        fail(errors, "D2_DEVELOPMENT_DEPENDENCY_FOUND")
    if access.get("PARALLEL_TRACK_BRANCH_CONTAMINATION") != "NO":
        fail(errors, "PARALLEL_TRACK_BRANCH_CONTAMINATION")
    if access.get("forbidden_loader_tokens_in_d2_scripts"):
        fail(errors, "FORBIDDEN_LOADERS")
    derived = access.get("d2_derived_data") or {}
    if any(derived.get(key) not in (0, None) for key in derived):
        fail(errors, "D2_DERIVED_DATA")

    if acquisition.get("alternative_sources", {}).get("used") is True:
        fail(errors, "MIRROR_SUBSTITUTED")
    if acquisition.get("absolute_path_persisted") is not False:
        fail(errors, "ABSOLUTE_PATH_FLAG")

    for name in MANIFEST_JSON_FILES:
        text = (MANIFEST_DIR / name).read_text(encoding="utf-8")
        digest_text = sha256_bytes(text.encode("utf-8"))
        if checksums["files"].get(name) != digest_text:
            fail(errors, f"CHECKSUM_MISMATCH:{name}")
    rerun = json.dumps(identity, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if sha256_bytes(rerun.encode("utf-8")) != checksums["files"]["source_identity.json"]:
        fail(errors, "JSON_NOT_DETERMINISTIC")

    if PAYLOAD_FILENAME in tracked:
        fail(errors, "FILENAME_TRACKED")

    flags = {
        "D2_ROLE": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
        "M_PV0_PARENT_LOCK_PRESENT": "YES" if "M_PV0_PARENT_LOCK_MISSING" not in errors else "NO",
        "SHA256_PRESENT": "YES" if payload_acquired and digest.get("LOCAL_COMPUTED_SHA256") else "NO",
        "BYTE_SIZE_PRESENT": "YES" if payload_acquired and digest.get("payload_byte_size") else "NO",
        "HASH_STABLE": "YES" if digest.get("hash_stable") is True else ("NO" if payload_acquired else "NA"),
        "PAYLOAD_GIT_TRACKED": "NO" if not tracked else "YES",
        "PAYLOAD_SEMANTIC_INSPECTION": "NO",
        "ARCHIVE_MEMBER_LISTING": "NO",
        "FEATURE_EXTRACTION": "NO",
        "MODEL_INFERENCE": "NO",
        "MODEL_INFERENCE_COUNT": 0,
        "REPRESENTATION_SELECTION_FROM_D2": "FORBIDDEN",
        "MODEL_SELECTION_FROM_D2": "FORBIDDEN",
        "THRESHOLD_SELECTION_FROM_D2": "FORBIDDEN",
        "D2_DEVELOPMENT_DEPENDENCY_FOUND": access.get("D2_DEVELOPMENT_DEPENDENCY_FOUND"),
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
        "D2_PAYLOAD_ACQUISITION": acquisition.get("D2_PAYLOAD_ACQUISITION"),
    }

    if errors:
        gate = "BLOCKED"
        ok = False
    elif payload_acquired:
        gate = "PASS_WITH_LIMITATIONS"
        ok = True
    else:
        gate = "BLOCKED"
        ok = True

    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "ok": ok,
        "gate": gate,
        "errors": errors,
        "checks": flags,
        "payload_acquired": payload_acquired,
        "payload_byte_size": digest.get("payload_byte_size"),
        "LOCAL_COMPUTED_SHA256": digest.get("LOCAL_COMPUTED_SHA256"),
        "published_checksum_available": digest.get("published_checksum_available"),
        "lock_state": access.get("lock_state"),
        "d2_remains_locked": True,
    }
    dump_json(MANIFEST_DIR / "validation_result.json", result)
    return result


def main() -> int:
    result = validate()
    print(json.dumps({"ok": result["ok"], "gate": result["gate"], "errors": result["errors"]}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
