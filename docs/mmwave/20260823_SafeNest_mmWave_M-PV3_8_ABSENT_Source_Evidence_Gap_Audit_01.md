# SafeNest mmWave V2 — M-PV3.8 ABSENT Source Evidence Gap Audit

**Date:** 2026-08-23
**Scope:** Evidence availability audit only
**Final status:** `ABSENT_ACQUISITION_REQUIRED`

## 1. Evidence availability summary

The approved M-PV3.8.3 corrective contract requires an ABSENT window to prove an intended negative observation: no human target, no target physiological source, valid sensor observation, and immutable evidence for that assignment. No current D1 artifact provides that proof.

No ABSENT sample, final membership, model result, candidate output, threshold change, or M-PV4 authorization was produced in this audit.

## 2. Current D1 classification

| Evidence layer | Valid PRESENT | Valid ABSENT | AMBIGUOUS | Invalid / unavailable | Interpretation |
|---|---:|---:|---:|---:|---|
| M-PV1 materialized D1 manifest, 265 contexts | 236 | 0 | 8 | 21 | The governed materialization has usable PRESENT evidence but no verified no-human ABSENT class. |
| M-PV1 `D1_DEV_VAL`, 62 contexts | 57 | 0 | 2 | 3 | This is the final-selection-relevant shortage. |
| M-PV0 R3 compact D1 target-row audit, 265 contexts | 0 | 0 | 35 transition / ambiguous | 265 target unavailable | The compact source audit cannot supply final target labels. |

Weak periodicity remains `AMBIGUOUS`; it is not an ABSENT candidate. Human-present non-detection, breath hold, apnea proxy, poor quality, missing input, and `INPUT_UNAVAILABLE` are likewise not ABSENT.

## 3. Root cause

Current D1 recordings were collected and materialized around human-target respiration evidence. They contain no immutable proof that the target zone was empty, no no-target physiological-source confirmation, and no predeclared negative-class recording slots. The compact source audit also records target-reference unavailability. These missing facts cannot be recovered by relabeling, feature regeneration, cache creation, or interpreting weak periodicity.

Therefore existing D1 data is sufficient for its governed PRESENT use but insufficient for the M-PV3.8 ABSENT contract. A new governed non-D2 negative-class acquisition is required.

## 4. Minimum future ABSENT evidence specification

Future acquisition must provide, for every candidate window:

- A target zone with no human target throughout the complete 30-second context and five-second target.
- An immutable, time-aligned presence/target-source evidence record confirming no human and no physiological source; an operator assertion alone is insufficient unless it is the pre-authorized authoritative presence record.
- A valid sensor-health observation covering the same interval, with no low-SNR classification, radar failure, dropout, missing input, stale/frozen/gapped data, or `INPUT_UNAVAILABLE` condition.
- Monotonic source timestamps and resolvable alignment among sensor, presence evidence, and acquisition record.
- Immutable source/recording identifiers and SHA-256 checksums.
- The fixed ABSENT reason code and no manual label assignment.

This is intended-negative-class evidence only. It must never be inferred from no respiration detected or a failed signal.

## 5. Required pre-lock acquisition artifacts

Before any future membership construction, the following must exist and be frozen:

- `campaign_predeclaration.json` with contract version, creation timestamp, generator/tool version, repository SHA, selection-rule version, and predeclared recording IDs/checksums.
- Nine fixed recording slots: three immutable lineage groups with three fixed slots each; the subsequent contract allocation is 7/6/6 per group.
- Recording order, scan start/end bounds, 30-second context / five-second target durations, and `CHRONOLOGICAL_FIRST_N_QUALIFYING_V1`.
- Presence-evidence identifiers, sensor-health evidence, source timestamps, and checksum coverage for each recording.
- A future ambiguity/rejection registry schema that records every scanned non-qualifying window in deterministic order.
- Authorized training preprocessing artifact identifiers/checksums, proving final-membership data remains unseen by preprocessing.

The predeclaration is not a membership and must not be retrofitted after availability is observed.

## 6. Stop conditions and next decision

- If all predeclared slots later provide valid, immutable no-human/no-target evidence, the evidence-acquisition prerequisite is complete and a separately authorized membership-construction phase may begin.
- If a candidate window is ambiguous, human-present, invalid, or unavailable, exclude it and retain its evidence; do not convert it to ABSENT.
- If any predeclared recording slot cannot establish the required evidence, the one bounded construction cannot proceed. Do not replace or top up it; determine whether a separate future recording campaign is authorized.
- If no source can provide immutable no-human/no-target evidence, the source is `DATA_SOURCE_INVALID_FOR_M_PV3_8` and the ROLE_L_FULL_TASK direction requires reconsideration.

**Recommended next phase decision: `ABSENT_ACQUISITION_REQUIRED`. Do not start M-PV3.8 evaluation.**
