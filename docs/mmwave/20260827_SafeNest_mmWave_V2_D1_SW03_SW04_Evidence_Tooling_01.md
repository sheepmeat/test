# SafeNest mmWave V2 — D1 SW-03/SW-04 Evidence Tooling Report

Date: 2026-08-27
Executing agent: Luna Max Fast
Phase: MMWAVE-V2-D1-SWPREP-03-04
Base: post-PR #170 `origin/main` at `13a56b7e41e9519ad61238a74861ef4ad6ea16ab`
Branch: `feature/mmwave-d1-sw03-sw04-evidence-tooling`
PR: [#174](https://github.com/sheepmeat/test/pull/174)

## Scope and outcome

This change implements software-only evidence plumbing for SW-03 Time Synchronization / Evidence Hashing and SW-04 Evidence Registries. No live campaign, sensor collection, D1 membership construction, model training, model evaluation, D2 access, or MR60 supervised physiology was performed.

The result is a deterministic, non-campaign fixture bundle with versioned schemas, validators, and focused automated tests. The four evidence registries remain logically distinct:

- recording provenance;
- occupancy evidence;
- sensor health; and
- rejection retention.

### Required return fields

```text
PHASE: MMWAVE-V2-D1-SWPREP-03-04
BASE: 13a56b7e41e9519ad61238a74861ef4ad6ea16ab
BRANCH: feature/mmwave-d1-sw03-sw04-evidence-tooling
COMMIT: 77edc4ba (implementation commit)
PR: #174 (open; not merged)

SW03_IMPLEMENTED: YES
SW04_IMPLEMENTED: YES

SYNC_METHODS_SUPPORTED: SHARED_CLOCK, EXPLICIT_SYNC_MARKER
HASH_RECEIPT_IMPLEMENTED: YES
REGISTRIES_IMPLEMENTED: recording provenance, occupancy evidence, sensor health, rejection
REJECTION_RETENTION_TESTED: YES

FIXTURE_ONLY: YES
LIVE_OCCUPANCY_EVIDENCE: NOT_PRODUCED
LIVE_SENSOR_HEALTH_EVIDENCE: NOT_PRODUCED

D1_MEMBERSHIP_CREATED: NO
CAPTURE_EXECUTED: NO

TESTS: 13 focused tests passed; CLI validators passed; Python compile check passed
TERMINAL_VERDICT: SW03_SW04_IMPLEMENTED_FIXTURE_VALIDATED
```

The report was updated after PR creation. PR #174 is open for review and was not merged.

## SW-03 implementation

`m_pv38_evidence_sync_hash.py` supports the canonical synchronization alternatives:

1. `SHARED_CLOCK`, recording the source and host timestamps, common clock identity, measured offset/delta, uncertainty when available, and fixture-only validation status.
2. `EXPLICIT_SYNC_MARKER`, requiring a marker identity and explicit observation on both timelines.

The validator emits `ALIGNMENT_MEASURABLE` and `THRESHOLD_NOT_GOVERNED`. No maximum clock error, timing tolerance, or pass threshold was introduced. Fixture values are never promoted to live synchronization evidence.

Hash receipts use lowercase SHA-256 and preserve an immutable evidence ID, evidence type, source identity, reference identity, optional portable file reference, optional size, and optional time coverage. Receipt creation and verification accept sensitive payload bytes only in memory for synthetic tests; payloads are not stored in the manifest. Malformed hashes, duplicate immutable IDs, and mismatches are rejected.

## SW-04 implementation

`m_pv38_evidence_registry.py` provides versioned schemas and validation for:

- recording provenance: planned recording → actual recording/reference → sensor/configuration → placement/zone → separate evidence channels → health → acceptance/rejection state;
- occupancy evidence: authoritative occupancy identity, target-zone coverage, no-human reference, sealed/access reference, interval, synchronization references, hash receipts, and review state;
- sensor health: connection, stream validity, timestamp validity, continuity, device-reported health, restart/reset, fault code, and health review state;
- rejection: immutable candidate/recording reference, reason code/detail, evidence references, time coverage, decision source, and mandatory retention.

An occupancy reference gap remains `UNKNOWN_REFERENCE_MISSING` / `INCOMPLETE_REVIEW_REQUIRED` and `NOT_ELIGIBLE`; it is not converted to `ABSENT`. A sensor freeze is retained as `FAULT_RETAINED` with `physiology_interpretation: NOT_PROVIDED`. A rejected observation remains `REJECTED`, retained, and `eligible_for_absent: false`.

The registries preserve separate sensor observation, occupancy reference, sealed/access evidence, sensor health, timing alignment, recording identity, and rejection-reason channels. They do not infer `ABSENT` from non-detection, weak periodicity, no respiration, low SNR, sensor failure, or an operator statement.

## Fixture evidence

Manifest: `datasets/mmwave/manifests/MMWAVE_V2_D1_sw03_sw04_evidence_tooling_01/`

The bundle includes positive fixtures for shared-clock synchronization, explicit sync markers, and deterministic hash verification. It also includes negative/retention fixtures for sensor-health fault, missing occupancy evidence, retained rejection, duplicate immutable evidence ID, and hash mismatch. Every fixture states:

```text
FIXTURE_ONLY
NON_CAMPAIGN
NOT_D1_MEMBERSHIP
NOT_DATASET_ADMISSIBLE
```

`checksums.json` and `checksums.sha256` cover all bundle artifacts except the checksum files themselves. The bundle was generated twice in isolated temporary directories and compared byte-for-byte; both generations validated successfully.

## Governance checks

The validator reads the canonical D1 state and the resource-recovery snapshot without modifying either. It observed:

- expected D1: 57 PRESENT and 57 governed ABSENT;
- current governed D1: 57 PRESENT and 0 governed ABSENT;
- absent sessions created in this phase: 0;
- D1 campaign directory: absent;
- membership construction: not performed;
- M-PV3.8: `RESOURCE_BLOCKED_CLOSED`;
- D2: `LOCKED`; M-PV4: `UNAUTHORIZED`.

The D1 counts and upstream source bytes were unchanged after fixture generation. SW-01 and SW-02 were not implemented or modified. `AGENTS.md` and `docs/README.md` were not modified.

## Verification

Commands and results:

- `python3 -m py_compile scripts/mmwave/m_pv38_evidence_sync_hash.py scripts/mmwave/m_pv38_evidence_registry.py` — passed.
- `python3 scripts/mmwave/m_pv38_evidence_sync_hash.py validate` — passed; 2 sync records and 7 hash receipts.
- `python3 scripts/mmwave/m_pv38_evidence_registry.py validate` — passed.
- `python3 -m unittest tests/test_mmwave_d1_sw03_sw04_evidence_tooling.py -v` — 13 passed.

## Limitations and non-claims

This is software readiness evidence only. It does not establish live occupancy readiness, live sensor-health readiness, physical clock performance, D1 admissibility, dataset membership, physiological accuracy, clinical validity, Raspberry Pi latency, or campaign authorization. No real payloads, live timestamps, MR60 supervised physiology, D2 data, or hardware measurements were used.

## Final verdict

`SW03_SW04_IMPLEMENTED_FIXTURE_VALIDATED`

This verdict means the SW-03/SW-04 schemas, validators, deterministic hashing, registry separation, and fixture demonstrations are implemented and validated. It does not authorize a live campaign, create D1 membership, or claim live evidence readiness.
