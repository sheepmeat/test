# SafeNest mmWave V2 — M-PV3.8 ABSENT Membership Acquisition Gate

**Date:** 2026-08-23
**Phase mode:** Contract design only
**Current selection state:** `BLOCKED_INVALID_FINAL_MEMBERSHIP`

## 1. Purpose and boundary

M-PV3.8 final selection is blocked because the required final D1 membership has 57 eligible PRESENT contexts and zero eligible ABSENT contexts. This contract defines the smallest governed process to acquire and lock valid ABSENT evidence. It does not evaluate models, open candidate outputs, select a candidate, change a model contract or threshold, access D2, or use MR60 supervised physiology.

The only permitted source boundary is a governed non-D2 D1 ABSENT extension. No ABSENT label may be generated from radar, model output, missing data, quality failure, or an AMBIGUOUS/TARGET_UNAVAILABLE row.

## 2. Eligible ABSENT evidence

An eligible ABSENT row has the canonical label `BREATHING_REFERENCE_ABSENT`. It is a SafeNest non-clinical breathing-reference state, not clinical apnea.

It requires all of the following:

- A pre-authorized, non-MR60 D1 reference source and immutable source recording.
- A synchronized reference interval that reports ABSENT throughout the entire five-second physiology target interval.
- A protocol or operator record that confirms the same intentional non-breathing interval.
- An immutable recording ID and verifiable time alignment evidence.

If a target touches onset/offset, has incomplete coverage, has reference/protocol disagreement, or has uncertain alignment, it is `AMBIGUOUS`. It is retained in the registry and never becomes ABSENT.

## 3. Bounded acquisition campaign

The campaign is one attempt only, using the three held-out D1 subjects: `D1_PERSON_03`, `D1_PERSON_09`, and `D1_PERSON_11`. They must remain subject-disjoint from candidate training.

For each subject, acquire exactly 19 eligible ABSENT contexts from three distinct qualified ABSENT recordings, allocated 7, 6, and 6 contexts. This produces exactly 57 eligible ABSENT contexts. Every selected 30-second input context must be non-overlapping, every target interval must be unique, and ABSENT recordings must be distinct from both candidate-training recordings and final-membership PRESENT recordings.

The campaign closes as soon as all quotas are met, or once the three predeclared recordings for any subject are exhausted. A failed recording is rejected, not replaced. The contract authorizes no additional recording, subject, source, or collection round.

## 4. Quality and provenance requirements

Each accepted row needs an immutable raw sensor recording and reference recording; monotonic timestamps and resolvable clock alignment; complete reference coverage for the 30-second input and five-second target; a valid governed quality state; no missing, stale, freeze, large-gap, or `INPUT_UNAVAILABLE` condition; and an independent review that the reference and protocol agree.

The lock manifest must include source and recording checksums, subject/session/recording identity, input and target times, reference source and interval times, alignment evidence, raw reference label, label-mapping ID/version/checksum, protocol/operator record, split, quality provenance, reviewer decision, and reviewer evidence ID.

The ambiguity registry records every uncertain, transition, incomplete, or rejected row with its original evidence and reason code. It preserves `AMBIGUOUS` without relabeling.

## 5. Final membership lock

`D1_FINAL_SELECTION_BOTH_CLASS_V1` is locked only when it contains all 57 existing eligible PRESENT contexts and all 57 new governed eligible ABSENT contexts, with 19 ABSENT contexts per held-out subject. The manifest, label mapping, ambiguity registry, class/subject counts, and SHA-256 checksum files are frozen before any candidate output is opened.

The membership is invalid if any count, subject, recording-separation, provenance, label-mapping, ambiguity, checksum, or quality rule fails. Invalid membership keeps selection blocked.

## 6. Stop condition

When the complete lock exists, the already-defined M-PV3.8 final selection evaluation may proceed once; this contract does not perform it.

If the one bounded campaign closes without a valid 57/57 membership, or no authoritative non-D2/non-MR60 ABSENT reference can be established, stop collection. Mark the `ROLE_L_FULL_TASK` selection direction `RECONSIDERATION_REQUIRED`; no further collection loop is authorized by this gate.
