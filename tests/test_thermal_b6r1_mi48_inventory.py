"""Focused synthetic tests for the B6R-1 read-only profiler."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from scripts.profile_thermal_b6r1_mi48 import profile_snapshot, validate_evidence


SHAPE = (62, 80)


def _write_png_header(path: Path, width: int = 128, height: int = 224) -> None:
    # Header-only content is enough to exercise the archive/image schema path.
    import struct

    signature = b"\x89PNG\r\n\x1a\n"
    body = struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0)
    path.write_bytes(signature + struct.pack(">I", 13) + b"IHDR" + body)


def _write_fixture(root: Path) -> None:
    root.mkdir(parents=True)
    native = np.full((3, *SHAPE), 1000, dtype=np.uint16)
    native[:, 0, 0] = 0
    native[:2, 1, 1] = 65535
    native[2, 2, 2] = 999
    floating = np.full((2, *SHAPE), 20.5, dtype=np.float32)
    floating[0, 3, 3] = np.nan
    floating[1, 4, 4] = np.inf
    np.savez(
        root / "readable.npz",
        thermal_uint16=native,
        thermal_float=floating,
        unexpected=np.zeros((2, 10, 10), dtype=np.int16),
    )
    (root / "corrupt.npz").write_bytes(b"not-an-npz")
    (root / "opaque.bin").write_bytes(b"\x00" * 32)
    (root / "metadata.json").write_text(
        json.dumps({"session_id": "SYNTHETIC_ONLY", "scenario": "TEST_ONLY"}),
        encoding="utf-8",
    )
    archive_root = root / "archive"
    archive_root.mkdir()
    png = archive_root / "image_d_0.png"
    _write_png_header(png)
    with zipfile.ZipFile(root / "images.zip", "w") as archive:
        archive.write(png, "validation/image_d_0.png")
        archive.writestr("validation/labels.txt", "0,1,2,3,4\n")
    png.unlink()


def test_inventory_profiles_arrays_and_accounts_every_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    _write_fixture(source)

    summary = profile_snapshot(
        source,
        output,
        logical_source_id="TEST_SYNTHETIC_B6R1",
        identity_status="RESOLVED",
    )

    assert summary["accounting"]["total_discovered"] == 5
    assert summary["accounting"]["readable"] == 2
    assert summary["accounting"]["corrupt"] == 1
    assert summary["accounting"]["excluded_with_explicit_reason"] == 2
    assert summary["accounting"]["invariant_total_equals_readable_plus_corrupt_plus_excluded"] is True
    assert summary["thermal_frames"]["identified_without_guessing"] == 5
    assert summary["decision"]["B6R_1_MI48_DATASET_STATUS"] == "PARTIALLY_USABLE"
    assert validate_evidence(output)["status"] == "PASS"

    with (output / "file_ledger.csv").open(newline="", encoding="utf-8") as handle:
        ledger = list(csv.DictReader(handle))
    assert [row["relative_path"] for row in ledger] == sorted(row["relative_path"] for row in ledger)
    corrupt = next(row for row in ledger if row["relative_path"] == "corrupt.npz")
    assert corrupt["accounting_class"] == "CORRUPT"
    assert corrupt["readability_status"] == "UNREADABLE"
    archive = next(row for row in ledger if row["relative_path"] == "images.zip")
    assert archive["accounting_class"] == "EXCLUDED_WITH_EXPLICIT_REASON"
    assert archive["readability_status"] == "READABLE"
    assert "128" in archive["archive_summary"]

    with (output / "frame_statistics.csv").open(newline="", encoding="utf-8") as handle:
        frames = list(csv.DictReader(handle))
    assert any(int(row["exact_zero_count"]) > 0 for row in frames)
    assert any(int(row["exact_65535_count"]) > 0 for row in frames)
    assert any(int(row["nonfinite_count"]) > 0 for row in frames)
    coordinate_text = (output / "coordinate_frequency_profile.csv").read_text(encoding="utf-8")
    assert "ANOMALY_CANDIDATE" in coordinate_text


def test_inventory_is_deterministic_and_does_not_mutate_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_fixture(source)
    before = {
        path.relative_to(source).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in source.rglob("*")
        if path.is_file()
    }

    profile_snapshot(source, first, logical_source_id="TEST_SYNTHETIC_B6R1", identity_status="RESOLVED")
    profile_snapshot(source, second, logical_source_id="TEST_SYNTHETIC_B6R1", identity_status="RESOLVED")

    after = {
        path.relative_to(source).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in source.rglob("*")
        if path.is_file()
    }
    assert before == after
    first_files = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file())
    assert first_files == second_files
    for relative in first_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_unresolved_identity_is_inconclusive_even_when_candidate_frames_exist(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    np.save(source.with_suffix(".npy"), np.zeros(SHAPE, dtype=np.uint16))
    # Use a directory with an intentionally unknown schema candidate as input.
    source.mkdir()
    (source / "candidate.npy").write_bytes((tmp_path / "source.npy").read_bytes())

    summary = profile_snapshot(
        source,
        output,
        logical_source_id="UNRESOLVED_CANDIDATE",
        identity_status="UNRESOLVED",
    )
    assert summary["thermal_frames"]["identified_without_guessing"] == 1
    assert summary["decision"]["B6R_1_MI48_DATASET_STATUS"] == "INCONCLUSIVE"
    assert validate_evidence(output)["status"] == "PASS"


def test_empty_snapshot_is_inconclusive_and_has_zero_frame_statistics(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir()
    output = tmp_path / "output"

    summary = profile_snapshot(
        source,
        output,
        logical_source_id="EMPTY_CANDIDATE",
        identity_status="UNRESOLVED",
    )
    assert summary["accounting"]["total_discovered"] == 0
    assert summary["thermal_frames"]["identified_without_guessing"] == 0
    assert summary["decision"]["B6R_1_MI48_DATASET_STATUS"] == "INCONCLUSIVE"
    assert (output / "frame_statistics.csv").read_text(encoding="utf-8").count("\n") == 1
    assert validate_evidence(output)["status"] == "PASS"
