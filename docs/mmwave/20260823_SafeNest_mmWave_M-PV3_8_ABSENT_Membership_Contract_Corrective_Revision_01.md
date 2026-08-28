# SafeNest mmWave V2 — M-PV3.8 ABSENT Membership Contract Corrective Revision

**Date:** 2026-08-23
**Contract version:** `M-PV3.8.3_CORRECTIVE`
**Scope:** Contract correction only; membership construction remains blocked pending independent re-audit

## 1. Correct ABSENT class

`ABSENT` is an intended negative class, not a breathing non-detection. An accepted window has immutable `subject_id=NO_HUMAN_TARGET` and the reason code `NO_HUMAN_TARGET_NO_TARGET_PHYSIOLOGICAL_SOURCE_VALID_SENSOR_OBSERVATION_INTENDED_NEGATIVE_CLASS`.

For the full 30-second context and five-second target, all four conditions are required: no human target present; no target physiological source; valid sensor observation; and predeclared intended-negative-class membership. Human-present breath holds, apnea-like intervals, no respiration detected, low SNR, radar failure, dropout, missing input, `INPUT_UNAVAILABLE`, and ambiguous presence are explicitly forbidden as ABSENT. Any uncertainty remains `AMBIGUOUS`, with original evidence retained and excluded from pure-class membership and metrics.

`acquisition_lineage_group_id` is separate from `subject_id`: it preserves D1 split lineage without asserting that a named person is present in a negative window.

## 2. Deterministic one-shot construction

Before acquisition, `campaign_predeclaration.json` must freeze every recording ID/checksum, slot, lineage group, quota, recording order, scan range, tool version, repository SHA, and selection-rule version. The predeclared rule is `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1`: scan every candidate 30-second context in ascending time order, record every rejection, and accept only the first fixed number of qualifying windows. Operators cannot choose easier negatives.

The one campaign has three fixed lineage groups and three fixed recording slots per group, with quotas 7/6/6 and 19 ABSENT contexts per group (57 total). From predeclaration lock onward, replacement, top-up, reallocation, quota change, alternate recording, and second attempt are forbidden. A failed slot remains failed and terminates the construction.

## 3. Final lock schema

Every accepted window requires immutable `window_id`, `recording_id`, `subject_id`, `start_time`, `end_time`, `class`, and `class_assignment_reason`, plus source and recording checksums, presence/target-source evidence, label mapping/version/checksum, quality provenance, deterministic selection order, and review evidence.

The membership requires `membership_id`, contract ID/version, creation timestamp, generator/tool version, repository commit SHA, membership checksum, and identifiers/checksums of the authorized training preprocessing artifacts. The campaign predeclaration, manifest, ambiguity registry, and checksum files must reproduce the lock without undocumented operator decisions.

## 4. Leakage prevention

Before the final lock, it is forbidden to fit preprocessing statistics, refresh normalization parameters, regenerate caches, create feature or other derived artifacts using final-membership data, or modify feature extraction using final-evaluation data. Only previously authorized training artifacts may provide preprocessing parameters.

## 5. Audit findings resolved

| Finding | Resolution |
|---|---|
| ABSENT semantics | Hard no-human/no-target/valid-observation requirement and forbidden-state list. |
| Missing immutable fields | Adds window ID, class reason, membership timestamp, tool version, repository SHA, and checksum. |
| Cherry-picking | Adds predeclared chronological exhaustive first-N selection. |
| Replacement loophole | Forbids replacement, top-up, reallocation, alternate recording, and a second attempt throughout. |
| Preprocessing leakage | Final-membership data remains unseen by preprocessing fitting, cache generation, and feature changes. |

## 6. Status

This correction creates no samples, no membership, no derived evaluation artifact, and no candidate output. It does not change thresholds, candidates, model contracts, M-PV4 authorization, D2 access, or MR60 supervised physiology. The corrected contract is ready only for independent re-audit.
