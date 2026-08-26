# SafeNest mmWave V2 — D1 SW-03/SW-04 Evidence Tooling Corrective Report

Date: 2026-08-27
Executing agent: Luna Max Fast 2
Phase: `MMWAVE-V2-D1-SWPREP-03-04C`
Branch: `feature/mmwave-d1-sw03-sw04-evidence-tooling`
PR: [#174](https://github.com/sheepmeat/test/pull/174)
Manifest: `datasets/mmwave/manifests/MMWAVE_V2_D1_sw03_sw04_evidence_tooling_01/`

## Purpose and scope

This report records the corrective completion of SW-03 Time Sync/Hash and SW-04 Evidence Registries. The original fixture-only implementation in PR #174 was generalized into explicit, versioned non-campaign scopes without authorizing a campaign or changing any frozen contract.

The supported scopes are:

- `FIXTURE_NON_CAMPAIGN`: the existing deterministic fixture lane, retained for regression coverage.
- `LIVE_DEBUG_NON_CAMPAIGN`: an operational record shape for local debug evidence. It is not D1 membership, not final evaluation, and not dataset-admissible by default.

No governed campaign scope was enabled or used. No live hardware evidence was collected. The corrective work does not modify SW-02, D0/D1 governance, D2, M-PV3/M-PV4 authority, or any sensor runtime contract.

The original PR #174 source base was post-PR #170 commit `13a56b7e41e9519ad61238a74861ef4ad6ea16ab`. The reviewed pre-corrective head was `0b7c5babd70e8da37fb227b923a3142b13b7cf42`. `origin/main` subsequently advanced to `7659a988fad7ab92f6a2a09f42da74544cbe0f52` through the unrelated merged M-PROT-0 work; that advancement was not treated as corrective scope or contamination. Corrective commits were appended to PR #174; no new PR was created and PR #174 was not merged.

## Required return

```text
PHASE: MMWAVE-V2-D1-SWPREP-03-04C
CORRECTIVE: GENERALIZE_FIXTURE_TO_OPERATIONAL_NON_CAMPAIGN
ORIGINAL_PR_BASE: 13a56b7e41e9519ad61238a74861ef4ad6ea16ab
OLD_REVIEWED_HEAD: 0b7c5babd70e8da37fb227b923a3142b13b7cf42
CORRECTIVE_HEAD: 43f0aa82 (implementation commit)
BRANCH: feature/mmwave-d1-sw03-sw04-evidence-tooling
PR: #174 (open; not merged)

FIXTURE_PIPELINE: COMPLETE
OPERATIONAL_NON_CAMPAIGN_PIPELINE: COMPLETE
SYNC_GENERATOR: COMPLETE
HASH_FILE_PIPELINE: COMPLETE
HASH_RECEIPT_PIPELINE: COMPLETE
PROVENANCE_REGISTRY: COMPLETE
OCCUPANCY_REGISTRY: COMPLETE
HEALTH_REGISTRY: COMPLETE
REJECTION_REGISTRY: COMPLETE
CROSS_REGISTRY_INTEGRITY: COMPLETE

LIVE_HARDWARE_USED: NO
LIVE_HARDWARE_EVIDENCE_STATUS: NOT_EXECUTED
LIVE_OCCUPANCY_EVIDENCE: NOT_PRODUCED
LIVE_SENSOR_HEALTH_EVIDENCE: NOT_PRODUCED
D1_MEMBERSHIP_CREATED: NO
CAPTURE_EXECUTED: NO
D2_ACCESSED: NO
MR60_SUPERVISED_PHYSIOLOGY_USED: NO
SW02_MODIFIED: NO

TESTS: 20 focused tests passed; compile and focused CLI validators passed
TERMINAL_VERDICT: SW03_SW04_SOFTWARE_COMPLETE_LIVE_EVIDENCE_PENDING
REMAINING_HARDWARE_DEPENDENCY: live evidence collection/debug only
```

## Corrective implementation

### Versioned scope semantics

The new `evidence_scope_schema.json` defines the explicit scope model:

- `FIXTURE_NON_CAMPAIGN` retains the exact legacy fixture semantics: `FIXTURE_ONLY`, `NON_CAMPAIGN`, `NOT_D1_MEMBERSHIP`, and `NOT_DATASET_ADMISSIBLE`.
- `LIVE_DEBUG_NON_CAMPAIGN` requires `NON_CAMPAIGN`, `NOT_D1_MEMBERSHIP`, `NOT_FINAL_EVALUATION`, and `NOT_DATASET_ADMISSIBLE_BY_DEFAULT`.

Operational records no longer require fixture-only fields or fixture-only status strings. The default live-debug status is `LIVE_DEBUG_NON_CAMPAIGN_OBSERVED`; it does not imply live hardware execution, D1 admissibility, or campaign approval.

### SW-03 synchronization and hashing

`scripts/mmwave/m_pv38_evidence_sync_hash.py` now supports caller-supplied synchronization records for both supported scopes. Records preserve source identity, clock identity, source timestamp, optional host timestamp, marker identity and observed states, measured offset/delta, uncertainty when supplied, and the locked non-governed statuses:

- `alignment_status: ALIGNMENT_MEASURABLE`
- `threshold_status: THRESHOLD_NOT_GOVERNED`

Explicit-marker records require the marker to be observed on both timelines. Shared-clock and explicit-marker methods remain distinguishable. No tolerance, maximum clock-error limit, pass threshold, or governed synchronization PASS was introduced.

The actual local-file path is implemented by `hash-file` and `create-hash-receipt`. It hashes the supplied file with SHA-256 without copying the payload into the manifest. Only a portable reference, digest, size, and caller-supplied metadata are persisted; absolute workstation paths are rejected. `verify-hash-receipt` validates the receipt and recomputes the digest against the supplied local file.

### SW-04 registries

The four registries accept both scopes while retaining their logical separation:

- recording provenance;
- occupancy evidence;
- sensor health; and
- rejection retention.

Operational examples use statuses such as `UNREVIEWED`, `REFERENCE_PRESENT_UNREVIEWED`, `REFERENCE_MISSING`, `OBSERVED_UNREVIEWED`, and `FAULT_RETAINED`. They are synthetic caller-supplied record shapes only and are marked `live_hardware_evidence_status: NOT_EXECUTED`.

The validators enforce the following fail-closed behavior:

- missing occupancy remains `NOT_ELIGIBLE` and never becomes `ABSENT`;
- stale, freeze, gap, flat-signal, sensor-fault, and other quality conditions remain quality/availability evidence;
- a health fault is retained with `physiology_interpretation: NOT_PROVIDED`;
- a rejected record remains retained as `REJECTED`, with `eligible_for_absent: false` and no physiology label;
- no non-detection, weak periodicity, low SNR, sensor fault, missing occupancy, or operator statement is converted into a physiological label.

Cross-registry references are checked against known IDs and classes. Provenance health links must resolve to the health registry; optional provenance rejection links must resolve to the rejection registry; hash receipt and synchronization references must resolve to the correct evidence class; dangling, unknown, and class-mismatched references are rejected.

## CLI and validator surface

The required CLI paths are available:

- `validate-sync-record`
- `create-sync-record`
- `create-hash-receipt` / `hash-file`
- `verify-hash-receipt`
- `validate-provenance`
- `validate-occupancy`
- `validate-health`
- `validate-rejection`
- `validate-evidence-bundle`

The bundle validator reports the required pipeline fields:

```text
fixture_pipeline_status = COMPLETE
operational_non_campaign_pipeline_status = COMPLETE
actual_file_hash_pipeline_status = COMPLETE
cross_registry_integrity_status = COMPLETE
live_hardware_evidence_status = NOT_EXECUTED
```

The manifest is regenerated deterministically. Its checksum files cover all bundle artifacts other than the checksum files themselves. The operational examples remain synthetic and do not constitute collected live evidence.

## Governance and immutability checks

The corrective validator confirms:

- D2 was not accessed;
- MR60 supervised physiology was not used;
- SW-02 was not modified;
- no D1 membership was created;
- no capture was executed;
- M-PV3.8 remains `RESOURCE_BLOCKED_CLOSED`;
- M-PV4 remains `UNAUTHORIZED`;
- fixture records retain their prior semantics and validation behavior;
- no absolute or machine-specific path is present in active machine-readable artifacts;
- no new synchronization threshold or physiological interpretation was added.

The intended handoff remains: an actual recording/evidence file is hashed by SW-03, the immutable receipt is verified and referenced by SW-04, and any future SW-02 stage-2 planned-to-actual binding remains a separate governed step. This phase does not perform that future binding.

## Verification evidence

Executed checks:

- `python3 -m py_compile scripts/mmwave/m_pv38_evidence_sync_hash.py scripts/mmwave/m_pv38_evidence_registry.py tests/test_mmwave_d1_sw03_sw04_evidence_tooling.py` — passed.
- `python3 -m unittest tests/test_mmwave_d1_sw03_sw04_evidence_tooling.py -v` — 20 passed.
- `python3 scripts/mmwave/m_pv38_evidence_sync_hash.py validate` — passed.
- `python3 scripts/mmwave/m_pv38_evidence_registry.py validate-evidence-bundle` — passed.
- Individual provenance, occupancy, health, and rejection validators — passed on the generated fixture registry inputs.
- Operational CLI test — actual temporary-file hash, receipt verification, and explicit-marker sync record creation/validation passed.
- `git diff --check` — passed before final staging.

Focused tests retain the original fixture coverage and add operational coverage for live-debug scope semantics, actual temporary-file hashing, shared-clock and explicit-marker records, non-fixture operational registry states, missing occupancy, retained health faults/rejections, dangling cross-registry references, unknown hash/sync references, and unchanged D1/no-threshold/no-SW-02 behavior.

## Limitations and non-claims

This is software evidence tooling readiness, not live evidence readiness. It does not claim:

- live hardware synchronization or sensor performance;
- live occupancy evidence or live sensor-health evidence;
- D1 dataset admissibility or campaign membership;
- final evaluation or threshold validity;
- physiological accuracy or clinical validity;
- MR60 supervised physiology validation;
- D2 access;
- Raspberry Pi performance;
- hardware latency or throughput;
- any benefit over another implementation.

No live hardware evidence was available in this phase. Future live-debug collection must remain explicitly `LIVE_DEBUG_NON_CAMPAIGN` unless separately governed, and must not be silently promoted to D1 or final evaluation evidence.

## Final verdict

`SW03_SW04_SOFTWARE_COMPLETE_LIVE_EVIDENCE_PENDING`

This verdict means that SW-03/SW-04 software plumbing is complete for the retained fixture lane and the explicitly versioned operational non-campaign lane, including actual local-file hashing, caller-supplied synchronization records, registry validation, and cross-registry integrity checks. Live evidence collection remains pending. It does not authorize a campaign, create D1 membership, modify SW-02, or establish live hardware readiness.
