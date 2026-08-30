#!/usr/bin/env python3
"""Acquire the official Thermal-IM archives used by the Thermal V2 Candidate A prototype.

The archive set is frozen in ``config/thermal/tv2_candidate_a_thermal_im_source_registry.json``
and resolves only against the official public Drive release recorded by TV2-D1. Payloads are
written outside the repository; nothing here copies raw media into Git.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "thermal" / "tv2_candidate_a_thermal_im_source_registry.json"


class AcquisitionError(RuntimeError):
    """Raised when the official source cannot be acquired or verified."""


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def download_archive(entry: dict, archive_root: Path, attempts: int = 4) -> dict:
    import gdown

    target = archive_root / entry["archive_name"]
    expected_sha = entry.get("d1_verified_sha256")
    if target.exists():
        actual = sha256_file(target)
        if expected_sha is None or actual == expected_sha:
            return {
                "archive_name": entry["archive_name"],
                "status": "ALREADY_PRESENT",
                "sha256": actual,
                "size_bytes": target.stat().st_size,
            }
        target.unlink()

    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            gdown.download(id=entry["drive_file_id"], output=str(target), quiet=True)
        except Exception as exc:  # noqa: BLE001 - surfaced through the receipt
            last_error = f"{type(exc).__name__}: {exc}"
        if target.exists() and target.stat().st_size > 0:
            actual = sha256_file(target)
            if expected_sha is not None and actual != expected_sha:
                target.unlink()
                last_error = "D1_SHA256_MISMATCH"
                continue
            return {
                "archive_name": entry["archive_name"],
                "status": "DOWNLOADED",
                "sha256": actual,
                "size_bytes": target.stat().st_size,
                "attempts": attempt,
            }
        time.sleep(2 * attempt)

    return {
        "archive_name": entry["archive_name"],
        "status": "FAILED",
        "error": last_error or "UNKNOWN_DOWNLOAD_FAILURE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch official Thermal-IM archives for TV2 Candidate A")
    parser.add_argument("--work-root", required=True, help="Non-Git working root for raw payloads")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    archive_root = Path(args.work_root) / "thermal_im" / "archives"
    archive_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download_archive, entry, archive_root) for entry in registry["archives"]]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            results.append(record)
            print(f"{record['status']:>15}  {record['archive_name']}", flush=True)

    results.sort(key=lambda item: item["archive_name"])
    failed = [item for item in results if item["status"] == "FAILED"]
    anchors = registry["d1_identity_anchors"]
    anchor_status = {}
    for name, expected in anchors.items():
        match = next((item for item in results if item["archive_name"] == name), None)
        anchor_status[name] = {
            "expected_sha256": expected["sha256"],
            "observed_sha256": (match or {}).get("sha256"),
            "expected_size_bytes": expected["size_bytes"],
            "observed_size_bytes": (match or {}).get("size_bytes"),
            "identity_match": bool(match and match.get("sha256") == expected["sha256"]
                                  and match.get("size_bytes") == expected["size_bytes"]),
        }

    receipt = {
        "schema_version": "safenest.thermal.tv2_candidate_a.thermal_im_acquisition_receipt.v1",
        "source_id": registry["source_id"],
        "official_release_folder": registry["official_release_folder"],
        "requested_archives": len(registry["archives"]),
        "acquired_archives": len(results) - len(failed),
        "failed_archives": [item["archive_name"] for item in failed],
        "d1_identity_anchor_status": anchor_status,
        "identity_status": (
            "VERIFIED_AGAINST_D1_ANCHORS"
            if all(item["identity_match"] for item in anchor_status.values())
            else "IDENTITY_NOT_VERIFIED"
        ),
        "archives": results,
    }
    receipt_path = Path(args.work_root) / "thermal_im" / "acquisition_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": os.fspath(receipt_path),
        "acquired": receipt["acquired_archives"],
        "failed": receipt["failed_archives"],
        "identity_status": receipt["identity_status"],
    }, indent=2))
    return 0 if not failed and receipt["identity_status"] == "VERIFIED_AGAINST_D1_ANCHORS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AcquisitionError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        raise SystemExit(2) from exc
