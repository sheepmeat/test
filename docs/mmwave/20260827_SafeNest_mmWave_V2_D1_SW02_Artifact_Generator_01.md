# SafeNest mmWave V2 — D1 SW-02 Governed Artifact Generator

- Phase: `MMWAVE-V2-D1-SWPREP-02`
- Base: `origin/main` after PR #170 — `13a56b7e41e9519ad61238a74861ef4ad6ea16ab`
- Scope: fixture/tooling only; no real campaign predeclaration and no capture
- Tool version: `SW-02_ARTIFACT_GENERATOR_V1`
- Terminal verdict: **`SW02_IMPLEMENTED_FIXTURE_VALIDATED`**

## Authority and preserved governance

The implementation reads the canonical M-PV3.8 acquisition gate and plan; it
does not modify either file. The recovered Stage-1 identity lock requires the
canonical campaign, contract, repository, timestamp, lineage, slot, planned
recording, recording order, quota, scan interval, context/target lengths,
sensor, placement, target zone, selection-rule, and pre-capture checksum
fields. Stage-2 receipts require the canonical planned ID, actual recording
identifier, SHA-256, file metadata, capture timestamp, source provenance, and
tool-version fields.

The fixed governance remains three lineage groups × three slots (nine total),
`CHRONOLOGICAL_FIRST_N_QUALIFYING_V1`, and the immutable 7/6/6 per-recording
quota allocation (57 contexts total). No replacement, top-up, reallocation,
alternate recording, second attempt, or manual selection path is implemented.

## Implemented tooling

`scripts/mmwave/m_pv38_absent_artifact_generator.py` provides a deterministic
stdlib-only API and CLI for:

1. canonicalizing and validating a future Stage-1 predeclaration;
2. generating and validating complete Stage-2 receipts;
3. verifying unique planned IDs, unique actual identifiers, valid SHA-256
   values, exact nine-slot coverage, canonical order, and binding evidence;
4. generating the checked-in fixture bundle without a runtime timestamp.

Receipt validation fails closed when the Stage-1 identity lock is incomplete,
when a planned slot is missing or extra, when an actual identifier is
duplicated, when a SHA-256 value is malformed, or when optional immutable
binding evidence disagrees with the claimed planned/actual pair.

`scripts/validate_mmwave_d1_sw02_artifact_generator.py` validates the complete
fixture bundle, checksum list, deterministic byte output, and non-campaign
semantics.

## Fixture evidence

Only the following non-campaign evidence was generated:

- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/fixtures/fixture_predeclaration.json`
- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/fixtures/fixture_post_capture_checksum_receipts.json`
- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/fixture_execution_receipt.json`
- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/validation_result.json`
- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/evidence_manifest.json`
- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/checksums.json`
- `datasets/mmwave/manifests/MMWAVE_V2_D1_sw02_artifact_generator_01/checksums.sha256`

The fixture proves:

| Evidence | Result |
|---|---|
| Lineage groups | 3 |
| Slots per group | 3 |
| Total slots | 9 |
| Total governed context quota | 57 |
| Planned → actual receipt binding | PASS, 9/9 |
| Real campaign predeclaration | `NO` |
| Real slot consumed | `NO` |
| D1 membership entries | `0` |
| Semantics | `FIXTURE_ONLY`, `NON_CAMPAIGN`, `NOT_D1_MEMBERSHIP`, `NOT_DATASET_ADMISSIBLE` |

## Validation evidence

- Focused test suite: 14 tests passed (`unittest`)
- Standalone fixture validator: passed
- Python compile check: passed
- `git diff --check`: passed
- No model, threshold, contract, membership, capture, evaluation, or
  lifecycle artifact was changed.

## Checksums

- Generator: `8115f823a415158d23e0c31f83059b15248be85fc79752043b62636eabe02063`
- Validator: `ea39363b982b1e1e94b6d96f15fd7be1db1956c16e404a7894db4bbf22b0c4aa`
- Fixture predeclaration: `a2b48e741b7a6466a987d4a7b7b7a431f2332f65b34dc84583c10d0bb29cba3e`
- Fixture receipts: `466f2d955305d80e050b712e2814c34fa77977e3318f5ed7f337c225e0bdccba`

## Boundary

`SW02_IMPLEMENTED_FIXTURE_VALIDATED` means the deterministic tooling and
non-campaign fixture pass. It does not authorize a real campaign lock,
capture, D1 membership construction, M-PV3.8 evaluation, M-PV4, or D2
semantic access.
