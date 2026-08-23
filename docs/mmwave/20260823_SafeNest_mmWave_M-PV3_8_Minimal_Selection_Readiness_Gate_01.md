# SafeNest mmWave V2 — M-PV3.8 Minimal Selection Readiness Gate

**Date:** 2026-08-23
**Phase mode:** Contract design only
**Primary direction:** `ROLE_L_FULL_TASK` (30 seconds)
**Secondary direction:** `ROLE_S_SHORT_CONTEXT` (15 seconds)

## 1. Decision purpose

M-PV3.8 defines the smallest final validation gate required to determine whether one of the six existing 30-second `ROLE_L_FULL_TASK` candidates can be selected for a later M-PV4 gate. It does not train, infer, select, tune, calibrate, access D2, or use MR60 supervised physiology.

The authorized candidate roster is fixed:

- Family B: seeds 11, 23, and 47
- Family C: seeds 11, 23, and 47

`ROLE_S_SHORT_CONTEXT` is a secondary engineering direction. It is not a substitute candidate and cannot compensate for a `ROLE_L_FULL_TASK` failure in this gate.

## 2. One bounded final membership

The final membership is `D1_FINAL_SELECTION_BOTH_CLASS_V1`. Before any candidate output is inspected, it must be locked with all provenance and checksums.

| Requirement | Fixed minimum |
|---|---:|
| Eligible PRESENT contexts | 57 existing D1 contexts |
| Eligible ABSENT contexts | Exactly 57 newly governed D1 contexts |
| Held-out subjects | `D1_PERSON_03`, `D1_PERSON_09`, `D1_PERSON_11` |
| ABSENT contexts per held-out subject | 19 |
| Training overlap | None |

Every held-out subject must contribute both eligible PRESENT and eligible ABSENT contexts. The membership is subject-disjoint from candidate training; no recording or window can belong to both. AMBIGUOUS windows remain in provenance and the exception registry, but are excluded from both pure-class metrics and class counts. They must never be relabeled as PRESENT or ABSENT.

This is deliberately one finite complement to the current 57 PRESENT contexts. There is no top-up, replacement, resampling, or second final membership after the lock.

## 3. Evaluation and frozen gates

Every one of the six existing candidates is evaluated once on the same locked membership, with its fixed checkpoint and preprocessing. The contract retains the frozen requirements:

- Breathing: PRESENT recall >= 0.95 and Brier <= 0.05.
- RR: MAE <= 5 bpm, within ±2 >= 0.40, within ±4 >= 0.60, and within ±6 >= 0.75.
- Safety: Q2 fail-closed and `presence → quality / availability → physiology`; `INPUT_UNAVAILABLE` cannot emit `PRESENT`, `ABSENT`, `NORMAL`, or `APNEA`.

ABSENT recall, specificity, precision, and F1 must be reported because the final membership is both-class. M-PV3.8 adds no new numerical ABSENT threshold; these results cannot relax, offset, or compensate for any frozen guard failure.

## 4. Decision rule

A candidate passes only if it passes every Class A safety requirement and every frozen breathing and RR guard. No score, ranking, Pareto rule, or post-hoc seed choice is permitted.

| Condition | Terminal result |
|---|---|
| Membership violates class, subject, provenance, or AMBIGUOUS rules | `BLOCKED_INVALID_FINAL_MEMBERSHIP` |
| Exactly one candidate passes all gates | `SINGLE_SELECTION_READY` |
| Two or more candidates pass all gates | `MULTIPLE_CANDIDATES_PASS_NO_SELECTION` |
| No candidate passes all gates | `NO_SELECTION_READY` |

Only `SINGLE_SELECTION_READY` can authorize a separately governed M-PV4 gate. It is not deployment approval and does not change threshold, D2, or MR60 authorization.

## 5. Single bounded RR remediation

`M-PV3.8-RR-ONE` is the only remediation path. It is triggered only if the ABSENT membership is complete, all six candidates pass Class A safety and frozen breathing guards, and every candidate fails exclusively on one or more frozen RR guards.

The future phase is limited to one pre-registered RR-only hypothesis, applied once to the fixed Family B/C × seed 11/23/47 roster. It cannot alter breathing, safety, labels, thresholds, D2 access, MR60 supervised physiology, or the final-membership definition. If fitting is needed, it may use only authorized non-final training data. It receives one final evaluation on the locked membership, with no interim inspection or rerun.

If that one remediation is unsuccessful, `NO_SELECTION_READY` is terminal for this candidate direction. M-PV3.8 authorizes no further RR loop and no additional data-collection loop.

## 6. Stopping condition

Stop after the single final membership is invalidated or its one evaluation yields a terminal result. If and only if the RR-only trigger is met, stop after the one `M-PV3.8-RR-ONE` evaluation yields its terminal result.

**M-PV3.8 is a readiness contract, not an execution result. Model selection and M-PV4 remain unauthorized until the contract produces `SINGLE_SELECTION_READY`.**
