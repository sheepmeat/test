#!/usr/bin/env python3
"""D2 locked acquisition and cryptographic seal.

Byte-level custody only. Does not unzip, list archive members, parse .mat,
extract signals, compute features, or run models.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_ID = "D2"
SCHEMA_VERSION = "D2.1"
AUDIT_DATE = "2026-08-22"
BASE_SHA = "e74e54736d5cde1773d530b8398a630486270785"
MPV0_COMMIT = "18e4a4e86d6bf95795d6749a91ce303ad3f1c417"

MANIFEST_DIR = ROOT / "datasets/mmwave/manifests/M-PV0_D2_locked_acquisition"
MPV0_POLICY = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/role_lock_policy.json"
MPV0_SOURCE = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/source_registry.json"
MPV0_LICENSE = ROOT / "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/license_access_audit.json"
V2_ROADMAP = ROOT / "docs/20260822_SafeNest_mmWave_Public_Multidomain_V2_Development_Roadmap_01.md"

PAYLOAD_FILENAME = "VITALSENSE_120_DATASET.zip"
PAYLOAD_LOGICAL_PATH = "datasets/raw_archives/external_datasets/VITALSENSE_120_DATASET.zip"
PAYLOAD_STORAGE_ROLE = "GITIGNORED_RAW_ARCHIVE_OPAQUE_BLOB"

DATASET_DOI = "10.21227/wq68-sv85"
PUBLICATION_DOI = "10.1038/s41597-026-07016-6"
IEEE_LANDING = (
    "https://ieee-dataport.org/open-access/new-dataset-millimeter-wave-radar-vital-sensing-reference-signals"
)
DATASET_DOI_URL = "https://doi.org/10.21227/wq68-sv85"
PUBLICATION_URL = "https://www.nature.com/articles/s41597-026-07016-6"
ANNOUNCED_IEEE_SIZE = "28.69 MB"
ANNOUNCED_GITHUB_SIZE = "about 31 MB"

MANIFEST_JSON_FILES = (
    "source_identity.json",
    "acquisition_record.json",
    "payload_digest_lock.json",
    "access_state.json",
    "exception_registry.json",
)

FORBIDDEN_SELECTION = (
    "representation_selection",
    "feature_selection",
    "model_family_selection",
    "seed_selection",
    "threshold_selection",
    "calibration_selection",
    "augmentation_selection",
    "candidate_inference",
)

D2_CONTAMINATION_NEEDLES = (
    "wq68-sv85",
    "VITALSENSE_120",
    "s41597-026-07016",
    "VS01_Resting",
    "VS01_Apnea",
)

ALLOWED_HIT_PREFIXES = (
    "docs/20260822_SafeNest_mmWave_Public_Multidomain_V2_Development_Roadmap_01.md",
    "docs/mmwave/20260822_SafeNest_mmWave_M-PV0",
    "docs/mmwave/20260822_SafeNest_mmWave_D2",
    "datasets/mmwave/manifests/M-PV0_public_multidomain_registry/",
    "datasets/mmwave/manifests/M-PV0_D2_locked_acquisition/",
    "scripts/mmwave_m_pv0",
    "scripts/mmwave_d2_locked_acquisition.py",
    "scripts/validate_mmwave_d2_locked_acquisition.py",
    "tests/test_mmwave_m_pv0.py",
    "tests/test_mmwave_d2_locked_acquisition.py",
)

FORBIDDEN_LOADER_TOKEN_PARTS = (
    ("scipy.io.", "loadmat"),
    ("numpy.", "load("),
    ("h5py.", "File"),
    ("zipfile.", "ZipFile"),
    (".name", "list()"),
    ("tarfile.", "open"),
    ("pandas.", "read_"),
)


def forbidden_loader_tokens() -> tuple[str, ...]:
    return tuple("".join(parts) for parts in FORBIDDEN_LOADER_TOKEN_PARTS)

ABSOLUTE_PATH_RE = re.compile(
    r"(?:/Users/|file://|~(?:/|$)|[A-Za-z]:\\|/home/|/private/tmp/)"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def dump_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def payload_path() -> Path:
    return ROOT / PAYLOAD_LOGICAL_PATH


def hash_file(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_file_twice(path: Path, algorithm: str) -> tuple[str, str]:
    first = hash_file(path, algorithm)
    second = hash_file(path, algorithm)
    return first, second


def git_ls_files(rel_path: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "--", rel_path],
        cwd=ROOT,
        text=True,
    ).strip()
    return [line for line in output.splitlines() if line]


def git_check_ignore(rel_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel_path],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def allowed_hit(rel: str) -> bool:
    return any(rel == prefix or rel.startswith(prefix) for prefix in ALLOWED_HIT_PREFIXES)


def scan_d2_development_dependency() -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    skip_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".npy", ".npz", ".tflite", ".keras"}
    search_roots = (
        ROOT / "docs",
        ROOT / "datasets",
        ROOT / "config",
        ROOT / "models",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / "preprocessing",
    )
    for needle in D2_CONTAMINATION_NEEDLES:
        for search_root in search_roots:
            if not search_root.exists():
                continue
            for path in search_root.rglob("*"):
                if not path.is_file() or path.suffix.lower() in skip_suffixes:
                    continue
                rel = repo_rel(path)
                if "/archive/" in f"/{rel}":
                    continue
                if allowed_hit(rel):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if needle in text:
                    hits.append({"path": rel, "needle": needle})
    return {
        "D2_DEVELOPMENT_DEPENDENCY_FOUND": "YES" if hits else "NO",
        "disallowed_hits": hits,
    }


def scan_d2_scripts_for_forbidden_loaders() -> list[str]:
    violations: list[str] = []
    for rel in (
        "scripts/mmwave_d2_locked_acquisition.py",
        "scripts/validate_mmwave_d2_locked_acquisition.py",
    ):
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_loader_tokens():
            if token in text:
                violations.append(f"{rel}:{token}")
    return violations


def opaque_payload_present_elsewhere() -> list[str]:
    found: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name == PAYLOAD_FILENAME or ("VITALSENSE_120" in name and path.suffix.lower() in {".zip", ".mat"}):
            found.append(repo_rel(path))
        if name.startswith("VS") and name.endswith(".mat"):
            found.append(repo_rel(path))
    return sorted(set(found))


def build() -> dict[str, Any]:
    policy = load_json(MPV0_POLICY)
    source = load_json(MPV0_SOURCE)
    license_audit = load_json(MPV0_LICENSE)
    d2_source = source["sources"]["D2"]
    d2_lock = policy["d2_lock"]

    if d2_source.get("intended_role") != "LOCKED_PUBLIC_CROSS_DEVICE_TEST":
        raise RuntimeError("M-PV0 D2 role is not LOCKED_PUBLIC_CROSS_DEVICE_TEST")
    if d2_source.get("dataset_doi_or_record_id") != DATASET_DOI:
        raise RuntimeError("M-PV0 D2 dataset DOI mismatch")
    if d2_source.get("publication_doi") != PUBLICATION_DOI:
        raise RuntimeError("M-PV0 D2 publication DOI mismatch")

    payload = payload_path()
    payload_exists = payload.is_file()
    tracked = git_ls_files(PAYLOAD_LOGICAL_PATH)
    ignore_ok = git_check_ignore(PAYLOAD_LOGICAL_PATH)
    stray_payloads = opaque_payload_present_elsewhere()
    dependency = scan_d2_development_dependency()
    loader_violations = scan_d2_scripts_for_forbidden_loaders()

    local_sha256 = None
    local_sha512 = None
    local_md5 = None
    byte_size = None
    hash_stable = None
    hash_read_count = 0
    if payload_exists:
        byte_size = payload.stat().st_size
        sha_a, sha_b = hash_file_twice(payload, "sha256")
        sha512_a, sha512_b = hash_file_twice(payload, "sha512")
        md5_a, md5_b = hash_file_twice(payload, "md5")
        hash_read_count = 2
        hash_stable = sha_a == sha_b and sha512_a == sha512_b and md5_a == md5_b
        local_sha256 = sha_a
        local_sha512 = sha512_a
        local_md5 = md5_a
        if not hash_stable:
            raise RuntimeError("HASH_STABLE=NO; D2 payload identity is not established")

    semantic_inspection = "NO"
    archive_listing = "NO"
    feature_extraction = "NO"
    model_inference = "NO"
    model_inference_count = 0
    if loader_violations:
        semantic_inspection = "D2_LOCK_VIOLATION"

    if payload_exists and not tracked and hash_stable:
        acquisition_state = "YES"
        lock_state = "ACQUIRED_AND_CRYPTOGRAPHICALLY_SEALED"
        payload_acquired = True
    else:
        acquisition_state = "BLOCKED_AUTH_REQUIRED"
        lock_state = "LOCKED_BEFORE_SEMANTIC_USE"
        payload_acquired = False

    identity = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "source_id": "D2",
        "role": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
        "canonical_name": d2_source.get("canonical_name"),
        "dataset_doi": DATASET_DOI,
        "publication_doi": PUBLICATION_DOI,
        "publisher": "IEEE DataPort",
        "publication_venue": "Scientific Data",
        "canonical_landing_page": IEEE_LANDING,
        "canonical_download_identity": PAYLOAD_FILENAME,
        "sensor": "120 GHz mmWave radar",
        "subjects": 24,
        "reference": "synchronized respiration reference (Mindray ePM10)",
        "protocol": [
            "resting",
            "normal to instructed breath-hold to normal",
        ],
        "parent_m_pv0_lock": {
            "commit": MPV0_COMMIT,
            "role_lock_policy": repo_rel(MPV0_POLICY),
            "source_registry": repo_rel(MPV0_SOURCE),
            "prior_lock_state": d2_lock.get("lock_state"),
            "prior_payload_acquisition": d2_lock.get("PAYLOAD_ACQUISITION"),
        },
        "do_not_substitute": True,
        "github_companion_not_used_as_payload_source": True,
        "clinical_apnea_claimed": False,
        "safenest_apnea_meaning": "instructed inhale-and-hold is a source protocol term; SafeNest maps it to APNEA-proxy, not clinical apnea",
    }

    acquisition = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "source_id": "D2",
        "role": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
        "audit_date": AUDIT_DATE,
        "retrieval_date": AUDIT_DATE,
        "access_mode": "IEEE_DATAPORT_OPEN_ACCESS_LOGIN_REQUIRED",
        "authentication_required": True,
        "ieee_account_session_present_in_environment": False,
        "payload_acquired": payload_acquired,
        "D2_PAYLOAD_ACQUISITION": acquisition_state,
        "acquisition_source": IEEE_LANDING if payload_acquired else None,
        "canonical_download_identity": PAYLOAD_FILENAME,
        "payload_filename": PAYLOAD_FILENAME if payload_acquired else None,
        "announced_payload_filename": PAYLOAD_FILENAME,
        "payload_byte_size": byte_size,
        "observed_size": byte_size,
        "published_size_claims": {
            "ieee_dataport": ANNOUNCED_IEEE_SIZE,
            "github_readme_inherited_from_m_pv0": ANNOUNCED_GITHUB_SIZE,
            "authoritative_exact_byte_source": None,
        },
        "landing_page_probe": {
            "url": IEEE_LANDING,
            "http_status": 200,
            "login_to_access_dataset_files": True,
            "announced_filename": PAYLOAD_FILENAME,
            "announced_size": ANNOUNCED_IEEE_SIZE,
            "sha256_mentions": 0,
            "md5_mentions": 0,
        },
        "dataset_doi_probe": {
            "url": DATASET_DOI_URL,
            "http_status": 302,
            "redirect_location": IEEE_LANDING,
            "final_http_status": 200,
        },
        "publication_data_availability": {
            "url": PUBLICATION_URL,
            "dataset_host": "IEEE DataPort",
            "dataset_doi": DATASET_DOI,
            "nature_hosted_payload_used": False,
        },
        "alternative_sources": {
            "github_companion": "https://github.com/Rc-W024/VS_DATASET",
            "used": False,
            "reason": "DO_NOT_SUBSTITUTE; binary equivalence with the IEEE DataPort object is not established without the canonical download",
        },
        "payload_storage_role": PAYLOAD_STORAGE_ROLE,
        "payload_logical_path": PAYLOAD_LOGICAL_PATH,
        "payload_git_tracked": bool(tracked),
        "payload_git_ignore_covers_logical_path": ignore_ok,
        "absolute_path_persisted": False,
        "semantic_inspection_performed": semantic_inspection,
        "archive_member_listing_performed": archive_listing,
        "feature_extraction_performed": feature_extraction,
        "model_inference_performed": model_inference,
        "model_inference_count": model_inference_count,
        "lock_state": lock_state,
        "parent_m_pv0_lock": MPV0_COMMIT,
        "base_sha": BASE_SHA,
        "known_limitations": [
            "IEEE DataPort open-access zip requires a logged-in IEEE account.",
            "This environment had no IEEE DataPort session, cookies, or tokens.",
            "No payload SHA-256 is published on the audited IEEE DataPort landing page.",
            "Public size claims remain 28.69 MB vs about 31 MB until an exact local byte count exists.",
        ],
    }

    digest = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "source_id": "D2",
        "audit_date": AUDIT_DATE,
        "payload_acquired": payload_acquired,
        "payload_filename": PAYLOAD_FILENAME if payload_acquired else None,
        "payload_logical_path": PAYLOAD_LOGICAL_PATH,
        "payload_byte_size": byte_size,
        "LOCAL_COMPUTED_SHA256": local_sha256,
        "LOCAL_COMPUTED_SHA512": local_sha512,
        "LOCAL_COMPUTED_MD5": local_md5,
        "hash_read_count": hash_read_count,
        "hash_stable": hash_stable,
        "published_checksum_available": False,
        "published_checksum_value": None,
        "published_checksum_source": license_audit["sources"]["D2"]["checksum_source"],
        "canonical_digest_algorithm": "SHA-256",
        "repackaged": False,
        "unzipped": False,
        "internal_content_rewritten": False,
        "semantic_inspection_performed": semantic_inspection,
        "archive_member_listing_performed": archive_listing,
    }

    access = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "source_id": "D2",
        "role": "LOCKED_PUBLIC_CROSS_DEVICE_TEST",
        "audit_date": AUDIT_DATE,
        "lock_state": lock_state,
        "PUBLIC_METADATA_ACCESS": "YES",
        "PAYLOAD_ACQUISITION": acquisition_state,
        "PAYLOAD_SEMANTIC_INSPECTION": semantic_inspection,
        "ARCHIVE_MEMBER_LISTING": archive_listing,
        "FEATURE_EXTRACTION": feature_extraction,
        "MODEL_INFERENCE": model_inference,
        "MODEL_INFERENCE_COUNT": model_inference_count,
        "selection_policy": {name: "FORBIDDEN" for name in FORBIDDEN_SELECTION},
        "candidate_inference_count": 0,
        "downloading_does_not_unlock": True,
        "final_evaluation_authorized": False,
        "final_evaluation_requires": [
            "M-PV3 selected FLOAT identity frozen",
            "model SHA frozen",
            "feature contract frozen",
            "preprocessing frozen",
            "thresholds frozen",
            "calibration frozen",
            "D2 access authorization explicitly opened",
        ],
        "D2_DEVELOPMENT_DEPENDENCY_FOUND": dependency["D2_DEVELOPMENT_DEPENDENCY_FOUND"],
        "disallowed_development_hits": dependency["disallowed_hits"],
        "forbidden_loader_tokens_in_d2_scripts": loader_violations,
        "stray_payload_paths_in_worktree": stray_payloads,
        "payload_git_tracked": bool(tracked),
        "PARALLEL_TRACK_BRANCH_CONTAMINATION": "NO",
        "d2_derived_data": {
            "physiological_arrays": 0,
            "extracted_samples": 0,
            "windows": 0,
            "features": 0,
            "plots": 0,
            "labels_derived_from_payload": 0,
            "model_outputs": 0,
        },
    }

    exceptions = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_ID,
        "audit_date": AUDIT_DATE,
        "total_blockers": 0 if payload_acquired else 1,
        "exceptions": [
            {
                "blocking": not payload_acquired,
                "code": "D2_PAYLOAD_ACQUISITION_BLOCKED_AUTH_REQUIRED",
                "severity": "BLOCKING" if not payload_acquired else "RESOLVED",
                "summary": (
                    "IEEE DataPort presents VITALSENSE_120_DATASET.zip behind LOGIN TO ACCESS DATASET FILES. "
                    "This environment had no authorized IEEE session. No mirror was substituted."
                    if not payload_acquired
                    else "Canonical IEEE DataPort payload was acquired and hashed as an opaque blob."
                ),
            },
            {
                "blocking": False,
                "code": "D2_PAYLOAD_CHECKSUM_NOT_PUBLISHED",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "IEEE DataPort landing page still publishes no SHA-256 or MD5. SafeNest local SHA-256 is the custody digest if/when acquired.",
            },
            {
                "blocking": False,
                "code": "D2_ANNOUNCED_SIZE_DISCREPANCY",
                "severity": "NON_BLOCKING_WARNING",
                "summary": "IEEE DataPort lists 28.69 MB; M-PV0 recorded GitHub README about 31 MB. No exact-byte publisher claim exists. Local exact bytes remain null until acquisition.",
            },
            {
                "blocking": False,
                "code": "D2_LOCK_REMAINS_AFTER_THIS_LANE",
                "severity": "POLICY_REQUIREMENT",
                "summary": "Acquisition, even if later successful, does not authorize representation, family, threshold, calibration, augmentation, or candidate inference from D2.",
            },
        ],
    }

    if tracked:
        exceptions["exceptions"].append(
            {
                "blocking": True,
                "code": "D2_PAYLOAD_GIT_TRACKED",
                "severity": "BLOCKING",
                "summary": "D2 payload path is Git-tracked. This is a custody failure.",
            }
        )
        exceptions["total_blockers"] += 1
    if dependency["disallowed_hits"]:
        exceptions["exceptions"].append(
            {
                "blocking": True,
                "code": "D2_DEVELOPMENT_DEPENDENCY_FOUND",
                "severity": "BLOCKING",
                "summary": "D2 identity appears outside allowed lock/roadmap/custody paths.",
            }
        )
        exceptions["total_blockers"] += 1
    if loader_violations:
        exceptions["exceptions"].append(
            {
                "blocking": True,
                "code": "D2_LOCK_VIOLATION",
                "severity": "BLOCKING",
                "summary": "D2 scripts contain forbidden payload parsers or archive listers.",
            }
        )
        exceptions["total_blockers"] += 1

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "source_identity.json": identity,
        "acquisition_record.json": acquisition,
        "payload_digest_lock.json": digest,
        "access_state.json": access,
        "exception_registry.json": exceptions,
    }
    checksum_files = {name: dump_json(MANIFEST_DIR / name, doc) for name, doc in artifacts.items()}
    checksums = {
        "algorithm": "SHA-256",
        "encoding": "utf-8 JSON indent=2 sort_keys=True trailing newline",
        "phase": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "files": checksum_files,
    }
    dump_json(MANIFEST_DIR / "checksums.json", checksums)
    return {
        "payload_acquired": payload_acquired,
        "acquisition_state": acquisition_state,
        "lock_state": lock_state,
        "byte_size": byte_size,
        "sha256": local_sha256,
    }


def main() -> int:
    result = build()
    print(json.dumps({"ok": True, "phase": PHASE_ID, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
