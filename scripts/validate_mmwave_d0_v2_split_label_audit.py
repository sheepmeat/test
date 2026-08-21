#!/usr/bin/env python3
"""Focused D0 gate checks. No training, R1, D2 payload, or MR60 labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mmwave_d0_v2_split_label_audit import (  # noqa: E402
    ABSOLUTE_PATH_RE,
    A0_IDENTITY,
    A0_RECORDINGS,
    A6_WINDOWS,
    AUDIT_DATE,
    CANONICAL_DOI,
    ELIGIBILITY_TAXONOMY,
    FORBIDDEN_SPLIT_NAMES,
    MANIFEST_DIR,
    MANIFEST_JSON_FILES,
    MN4_SPLIT,
    MPV0_POLICY,
    PHASE_ID,
    SCHEMA_VERSION,
    SPLIT_IDENTITY,
    SPLIT_NAMES,
    SPLIT_NAMESPACE,
    SPLIT_PATH,
    SPLIT_SEED,
    assign_subject_splits,
    dump_json,
    load_json,
    load_jsonl,
    sha256_bytes,
)

REQUIRED_YES = (
    "D0_CANONICAL_IDENTITY_VERIFIED",
    "M_N6_HELDOUT_EXCLUDED",
    "ELIGIBLE_D0_SUBJECT_ACCOUNTING_COMPLETE",
    "SUBJECT_SPLIT_DISJOINT",
    "SPLIT_DETERMINISTIC",
    "LABEL_PROVENANCE_AUDITED",
    "D0_SUBJECT_HELDOUT_HAS_USABLE_TARGET_COVERAGE",
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


def any_clinical_apnea_true(obj: object) -> bool:
    if isinstance(obj, dict):
        if obj.get("clinical_apnea_claimed") is True:
            return True
        return any(any_clinical_apnea_true(value) for value in obj.values())
    if isinstance(obj, list):
        return any(any_clinical_apnea_true(value) for value in obj)
    return False


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
    split_doc = load_json(SPLIT_PATH)
    for name, doc in files.items():
        check_absolute_paths(doc, name, errors)
    check_absolute_paths(split_doc, "split_file", errors)

    population = files["source_population_audit.json"]
    balance = files["split_balance_summary.json"]
    eligibility = files["eligibility_summary.json"]
    label_audit = files["label_reference_audit.json"]
    exceptions = files["exception_registry.json"]
    checksums = files["checksums.json"]
    v2_split = files["v2_subject_split.json"]
    policy = load_json(MPV0_POLICY)
    a0 = load_json(A0_IDENTITY)
    mn4 = load_json(MN4_SPLIT)
    recordings = load_jsonl(A0_RECORDINGS)
    windows = load_jsonl(A6_WINDOWS)

    if v2_split != split_doc:
        fail(errors, "SPLIT_FILE_MANIFEST_MISMATCH")
    if v2_split.get("split_identity") != SPLIT_IDENTITY:
        fail(errors, "SPLIT_IDENTITY")
    if v2_split.get("namespace") != SPLIT_NAMESPACE or v2_split.get("seed") != SPLIT_SEED:
        fail(errors, "SPLIT_ALGORITHM_IDENTITY")
    if v2_split.get("historical_m_n6_train_val_copied") is not False:
        fail(errors, "M_N6_TRAIN_VAL_COPIED")
    for forbidden in FORBIDDEN_SPLIT_NAMES:
        if forbidden in v2_split.get("subject_ids", {}):
            fail(errors, f"FORBIDDEN_SPLIT_NAME:{forbidden}")

    doi_ok = (
        population["canonical_d0_identity"]["doi"] == CANONICAL_DOI
        and a0["dataset_identity"]["doi"] == CANONICAL_DOI
        and v2_split["source_identity"]["doi"] == CANONICAL_DOI
        and population["canonical_d0_identity"]["canonical_safenest_version"] == "Zenodo v1.1"
    )
    if not doi_ok:
        fail(errors, "D0_CANONICAL_IDENTITY")

    a0_subjects = sorted({row["subject_id"] for row in recordings})
    if len(a0_subjects) != 110 or population["source_population"]["total_subjects"] != 110:
        fail(errors, "SUBJECT_COUNT_110")
    if len(recordings) != 440 or population["source_population"]["total_recordings"] != 440:
        fail(errors, "RECORDING_COUNT_440")

    frozen = list(policy["heldout_exclusion"]["excluded_subject_ids"])
    mn4_heldout = list(mn4["subject_ids"]["NEW_MODEL_HELDOUT_TEST"])
    excluded = list(v2_split["excluded_subject_ids"])
    if excluded != frozen or excluded != mn4_heldout or len(excluded) != 16:
        fail(errors, "EXCLUDED_SET_MISMATCH")

    ids = v2_split["subject_ids"]
    train, val, heldout = set(ids["TRAIN"]), set(ids["VAL"]), set(ids["D0_SUBJECT_HELDOUT"])
    excluded_set = set(excluded)
    if train & val or train & heldout or val & heldout:
        fail(errors, "SUBJECT_LEAKAGE")
    if (train | val | heldout) & excluded_set:
        fail(errors, "EXCLUDED_IN_V2_SPLITS")
    eligible = sorted(sid for sid in a0_subjects if sid not in excluded_set)
    assigned = sorted(train | val | heldout)
    if assigned != eligible:
        fail(errors, "ELIGIBLE_POOL_MISMATCH")
    if len(eligible) != 110 - 16:
        fail(errors, "ELIGIBLE_COUNT")
    if population["source_population"]["v2_eligible_subjects"] != len(eligible):
        fail(errors, "POPULATION_ELIGIBLE_COUNT")
    if len(train) + len(val) + len(heldout) != len(eligible):
        fail(errors, "SPLIT_COUNT_SUM")
    if any(len(ids[name]) != len(set(ids[name])) for name in SPLIT_NAMES):
        fail(errors, "DUPLICATE_SUBJECT_IN_SPLIT")

    regenerated = assign_subject_splits(eligible)
    expected = {name: sorted(sid for sid, split in regenerated.items() if split == name) for name in SPLIT_NAMES}
    if expected != {name: ids[name] for name in SPLIT_NAMES}:
        fail(errors, "SPLIT_NOT_DETERMINISTIC")

    rec_splits: dict[str, set[str]] = {}
    for rec in recordings:
        sid = rec["subject_id"]
        if sid in excluded_set:
            continue
        split_name = regenerated[sid]
        rec_id = rec["recording_id"]
        rec_splits.setdefault(rec_id, set()).add(split_name)
    if any(len(splits) > 1 for splits in rec_splits.values()):
        fail(errors, "RECORDING_CROSS_SPLIT")

    if eligibility.get("taxonomy") != list(ELIGIBILITY_TAXONOMY):
        fail(errors, "TAXONOMY")
    for rec in label_audit["recordings"]:
        for key in rec.get("window_primary_eligibility", {}):
            if key not in ELIGIBILITY_TAXONOMY:
                fail(errors, f"UNKNOWN_ELIGIBILITY:{key}")
        if rec.get("clinical_apnea_claimed") is True:
            fail(errors, "CLINICAL_APNEA_CLAIM")

    if any_clinical_apnea_true(v2_split) or any_clinical_apnea_true(label_audit):
        fail(errors, "CLINICAL_APNEA_CLAIM")
    if label_audit["apnea_policy"].get("clinical_apnea_claimed") is not False:
        fail(errors, "CLINICAL_APNEA_POLICY")
    if not label_audit["apnea_policy"].get("unlabeled_quiet_region_is_not_apnea"):
        fail(errors, "QUIET_AS_APNEA")

    coverage = balance["heldout_coverage"]
    if not coverage.get("usable"):
        fail(errors, "HELDOUT_COVERAGE")
    if coverage.get("assigned_apnea_proxy_windows", 0) < 1:
        fail(errors, "HELDOUT_NO_APNEA")

    if v2_split.get("d2_accessed") != "NO" or population.get("d2_accessed") != "NO":
        fail(errors, "D2_ACCESSED")
    if v2_split.get("mr60_supervised_use") != "NO":
        fail(errors, "MR60_SUPERVISED")

    for name in MANIFEST_JSON_FILES:
        text = (MANIFEST_DIR / name).read_text(encoding="utf-8")
        digest = sha256_bytes(text.encode("utf-8"))
        if checksums["files"].get(name) != digest:
            fail(errors, f"CHECKSUM_MISMATCH:{name}")
    split_text = SPLIT_PATH.read_text(encoding="utf-8")
    if checksums["split_file"]["sha256"] != sha256_bytes(split_text.encode("utf-8")):
        fail(errors, "CHECKSUM_MISMATCH:split_file")

    rerun = json.dumps(v2_split, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if sha256_bytes(rerun.encode("utf-8")) != checksums["files"]["v2_subject_split.json"]:
        fail(errors, "JSON_NOT_DETERMINISTIC")

    window_count = len(windows)
    if window_count != 530:
        fail(errors, f"WINDOW_COUNT:{window_count}")
    if label_audit.get("annotation_parse_failures") != 0:
        fail(errors, "ANNOTATION_PARSE_FAILURES")
    if exceptions.get("total_blockers") != 0:
        fail(errors, "UNEXPECTED_BLOCKERS")

    flags = {
        "D0_CANONICAL_IDENTITY_VERIFIED": "YES" if doi_ok and "D0_CANONICAL_IDENTITY" not in errors else "NO",
        "M_N6_HELDOUT_EXCLUDED": "YES" if "EXCLUDED_IN_V2_SPLITS" not in errors and "EXCLUDED_SET_MISMATCH" not in errors else "NO",
        "ELIGIBLE_D0_SUBJECT_ACCOUNTING_COMPLETE": "YES" if "ELIGIBLE_POOL_MISMATCH" not in errors and "ELIGIBLE_COUNT" not in errors else "NO",
        "SUBJECT_SPLIT_DISJOINT": "YES" if "SUBJECT_LEAKAGE" not in errors else "NO",
        "SPLIT_DETERMINISTIC": "YES" if "SPLIT_NOT_DETERMINISTIC" not in errors else "NO",
        "LABEL_PROVENANCE_AUDITED": "YES" if "CLINICAL_APNEA_POLICY" not in errors else "NO",
        "D0_SUBJECT_HELDOUT_HAS_USABLE_TARGET_COVERAGE": "YES" if coverage.get("usable") else "NO",
        "D2_ACCESSED": "NO",
        "MR60_SUPERVISED_USE": "NO",
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
    }
    for key in REQUIRED_YES:
        if flags.get(key) != "YES":
            fail(errors, f"GATE_FLAG:{key}")

    if errors:
        gate = "BLOCKED"
    else:
        gate = "PASS_WITH_LIMITATIONS"

    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "ok": not errors,
        "gate": gate,
        "errors": errors,
        "checks": flags,
        "split_identity": SPLIT_IDENTITY,
        "eligible_subject_count": len(eligible),
        "excluded_subject_count": len(excluded),
        "counts": {name: len(ids[name]) for name in SPLIT_NAMES},
        "heldout_coverage": {
            "assigned_apnea_proxy_windows": coverage.get("assigned_apnea_proxy_windows"),
            "rr_supervised_windows": coverage.get("rr_supervised_windows"),
            "usable": coverage.get("usable"),
        },
        "d2_accessed": "NO",
        "mr60_supervised_use": "NO",
    }
    dump_json(MANIFEST_DIR / "validation_result.json", result)
    return result


def main() -> int:
    result = validate()
    print(json.dumps({"ok": result["ok"], "gate": result["gate"], "errors": result["errors"]}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
