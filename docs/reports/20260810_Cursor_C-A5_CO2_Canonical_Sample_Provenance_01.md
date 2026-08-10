# SafeNest CO₂ Phase C-A5 — Canonical Sample Provenance and Group-Wise Split Materialization

- Document Version: `01`
- Author: `Cursor` (CO₂ Track Implementation Agent)
- Execution Date: `2026-08-10`
- Phase: `C-A5 — CO₂ Canonical Sample Provenance and Group-Wise Split Materialization`
- Status: `PASS_WITH_WARNINGS`
- C-A6 Authorization (post-merge gate readiness): `YES` (do not start C-A6 on this branch)
- A-series release: `DEFERRED_UNTIL_C-A6`

---

## 1. Executive Summary

Phase **C-A5** materializes a deterministic canonical sample contract joining C-A1 source-row provenance, C-A2 temporal-block/split membership, C-A3 `CO2_slope` lineage/status, and C-A4 occupancy targets for all **20,560** real UCI source rows. Warm-up rows remain represented. Model-eligible samples (**20,551**) are an explicit derived view. No scaler fitting, model training, split redesign, or synthetic-fixture mixing was performed.

---

## 2. Predecessor Gate

| Gate | Result |
|---|---|
| Canonical base | `origin/main` @ `812061e` |
| C-A4 merge | Present on `main` (PR #24 lineage) |
| C-A0..C-A4 validators | all `PASS_WITH_WARNINGS` |
| Fresh branch | `feature/C-A5-co2-canonical-samples` from updated `main` |

---

## 3. Canonical Sample Profile

- **Profile ID:** `CO2_CANONICAL_SAMPLE_PROFILE_001`
- **Grain:** one C-A1 source row → one canonical source sample
- **Canonical sample ID:** `co2cs_` + `sha256(archive_sha256\|member\|source_row_identifier\|physical_line)[:32]`
- **Ordering:** `CHRONOLOGICAL_C_A2_MEMBER_ORDER` — `datatest.txt` → `datatraining.txt` → `datatest2.txt`
- **Total canonical source samples:** `20560`

---

## 4. Provenance Chain

```text
raw UCI archive
→ C-A1 source observation
→ C-A2 temporal block + future_split_role
→ C-A3 CO2_slope value/status + history lineage
→ C-A4 occupancy source value + canonical class
→ C-A5 canonical sample record
```

Each JSONL record retains archive/member/row identifiers, timestamps, block ID, split role, measured fields, slope status/value, and occupancy target fields.

---

## 5. Immutable Inherited Contracts

| Contract | Inheritance |
|---|---|
| Split | `BLOCK_02→TRAIN`, `BLOCK_01→VALIDATION`, `BLOCK_03→LOCKED_TEST` |
| Target | `Occupancy` `0→VACANT`, `1→OCCUPIED`; derivation `NONE` |
| Slope | `CO2_SLOPE_FEATURE_PROFILE_001` / `ENDPOINT_DIFFERENCE` / warm-up preserved |

---

## 6. Counts

| Metric | Count |
|---|---:|
| Canonical source samples | 20560 |
| CO2_slope eligible | 20551 |
| Warm-up / unavailable | 9 |
| Missing source mappings | 0 |
| Duplicate source mappings | 0 |
| Duplicate canonical IDs | 0 |

### Per split

| Role | Canonical | Slope-eligible | Warm-up | VACANT | OCCUPIED |
|---|---:|---:|---:|---:|---:|
| TRAIN | 8143 | 8140 | 3 | 6414 | 1729 |
| VALIDATION | 2665 | 2662 | 3 | 1693 | 972 |
| LOCKED_TEST | 9752 | 9749 | 3 | 7703 | 2049 |

---

## 7. Canonical vs Model-Eligible

- **CANONICAL_SOURCE_SAMPLE:** all 20,560 rows (including warm-up).
- **MODEL_ELIGIBLE_SAMPLE:** 20,551 rows with `co2_slope_status == FEATURE_AVAILABLE`.
- Exclusions use reason `FEATURE_UNAVAILABLE_WARMUP` (not malformed data).

---

## 8. LOCKED_TEST / Scaler Boundary

- LOCKED_TEST membership and provenance are materialized.
- LOCKED_TEST is **not** authorized for fit, tuning, feature-contract tuning, or threshold calibration.
- Future scaler-fit population is **TRAIN only**.
- C-A5 does **not** compute scaler statistics.

---

## 9. Predecessor Fingerprint Lock

`predecessor_fingerprint_registry.json` locks SHA-256 identities of consumed C-A1..C-A4 machine-readable artifacts plus the raw archive path/hash. Validator fails if upstream evidence changes without regeneration.

---

## 10. Synthetic Isolation

`datasets/co2/processed/co2_occupancy_v1.npz` remains `SYNTHETIC_SMOKE_FIXTURE` and is not part of real canonical lineage.

---

## 11. Determinism

Audit generation was run repeatedly; `checksums.sha256` was identical across successive runs (`DETERMINISM_CHECKSUMS:IDENTICAL`).

---

## 12. Artifacts

Directory: `datasets/co2/manifests/c_a5_canonical_samples/`

- `canonical_sample_profile.json`
- `predecessor_fingerprint_registry.json`
- `split_membership_manifest.json`
- `feature_availability_manifest.json`
- `materialization_integrity_summary.json`
- `exceptions_and_limitations.json`
- `generation_metadata.json`
- `canonical_source_samples.jsonl`
- `model_eligible_sample_ids.jsonl`
- `artifact_identity.json`
- `checksums.sha256`

Code / validation:

- `datasets/co2/canonical_samples.py`
- `scripts/audit_co2_canonical_samples.py`
- `scripts/validate_co2_canonical_samples.py`
- `tests/test_co2_canonical_samples.py`

---

## 13. Validation Evidence

| Check | Result |
|---|---|
| C-A5 standalone validator | `PASS_WITH_WARNINGS` (0 errors, 8 warnings) |
| Focused tests | 8 passed |
| Determinism | identical checksums across regenerations |

Inherited non-blocking warnings retained (timezone, single-room group independence, model/scaler lineage unverified, slope history lineage, SCD40 cadence gap, deferred shared update, A-series release deferred).

---

## 14. Parallel Isolation

C-A5 was implemented on `feature/C-A5-co2-canonical-samples` (isolated worktree) while other tracks (mmWave M-B3, Thermal) occupied the primary working tree. Branch history and PR diff must contain only CO₂ C-A5 paths.

---

## 15. Deferred Work

| Item | Status |
|---|---|
| C-A6 final conversion integrity audit / artifact lock | DEFERRED |
| C-B model selection / scaler fit | DEFERRED |
| C-C SCD40 domain | DEFERRED |
| CO₂ A-series release/tag | `DEFERRED_UNTIL_C-A6` |
| Shared inventory/contract refresh | `DEFERRED_SHARED_INTEGRATION_UPDATE` |

---

## 16. C-A6 Authorization Gate (readiness only)

C-A6 may proceed only after this C-A5 contract is merged and isolation gates remain clean. This branch must not begin C-A6 implementation.
