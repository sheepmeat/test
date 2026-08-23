# SafeNest mmWave V2 — M-PV3.6 Corrective Role-Based Evaluation Contract

**Date:** 2026-08-23
**Branch:** `docs/mmwave-m-pv36-corrective-role-contract`
**Parent contract:** `MMWAVE_V2_M_PV36_ROLE_BASED_EVALUATION_CONTRACT_V1`
**Gate:** `PASS_WITH_LIMITATIONS`
**Scope:** Contract correction only; no model training, inference, selection, threshold change, D2 access, or MR60 supervised physiology

## 1. Corrective decision

This corrective update resolves the role-membership and safety-classification ambiguities identified by the independent audit. It refines the M-PV3.6 evaluation contract without changing any predecessor result, frozen utility guard, model, threshold, dataset membership, or authorization boundary.

## 2. Corrected Role L membership

Role L is now three distinct, non-interchangeable sub-roles. A metric that is not trained or evaluated by a sub-role is represented as `NOT_APPLICABLE`; it is never converted to zero, failure, or a compensable utility penalty.

| Sub-role | Eligible family | Input shape | Tasks | Applicable metric cards | `NOT_APPLICABLE` |
|---|---|---|---|---|---|
| `ROLE_L_FULL_TASK` | M-PV3 Family B and Family C only | `[B,300,1]` | Breathing evidence, RR, quality | Breathing, RR, quality diagnostic, Class A safety, stability, responsiveness, footprint | None for its declared tasks |
| `ROLE_L_RR_QUALITY` | M-PV3 Family A only | `[B,59]` | RR, quality | RR, quality diagnostic, Class A safety, stability, responsiveness, footprint | Breathing metrics |
| `ROLE_L_ISOLATION` | M-PV3.5 30-second parity CNN only | `[B,300,1]` | Breathing evidence | Breathing, Class A safety, stability, responsiveness, footprint | RR and quality metrics |

The historical 15-second `ROLE_S_SHORT_CONTEXT` remains a breathing-only candidate role. Its RR and temporal-hold metrics remain `NOT_APPLICABLE`.

## 3. I1/Q2 Class A safety precedence

The following is a Class A runtime invariant and is non-compensable:

`presence → quality / availability → physiology`

- `presence=false` cannot produce a physiology card.
- `presence=unknown` cannot produce a physiology card.
- `INPUT_UNAVAILABLE` cannot emit `PRESENT`, `ABSENT`, `NORMAL`, or `APNEA`.
- Q2 synthetic evidence is safety evidence only. It does not become a Role L utility metric, live-device evidence, MR60 validation, or a basis for a threshold change.

Q2 invalid false acceptance and fail-closed preservation remain Class A safety metrics for every role. They are excluded from Class B role-specific utility cards, so accuracy, latency, footprint, or other utility evidence cannot compensate for a safety failure. This update does not modify Q2 thresholds.

## 4. D1 PRESENT limitation

D1 DEV VAL contains 57 eligible PRESENT contexts across three validation subjects, two AMBIGUOUS contexts, and no eligible ABSENT context. Therefore D1 PRESENT evaluation is `AVAILABLE_WITH_LIMITATION`, and stable role eligibility is `INCOMPLETE`.

This evidence cannot establish stable role eligibility, ABSENT recall, specificity, balanced macro F1, or full breathing-state discrimination. Subject-disjoint governed both-class membership remains a future gate; D2 remains locked.

## 5. Rules preserved without change

- M-PV3 remains `NO_SELECTION_READY`; no model is selected.
- Frozen M-PV3 utility guards remain unchanged.
- Combined scores, weighted rankings, normalized utility rankings, Pareto winner selection, and post-hoc seed selection remain prohibited.
- D2 access and MR60 supervised physiology remain unauthorized.
- M-PV4 approval, new checkpoints, threshold tuning, calibration fitting, quantization, and production implementation remain out of scope.

## 6. Validation and execution boundary

The focused validator confirms explicit sub-role membership, task applicability, Class A I1/Q2 precedence, non-compensable Q2 safety treatment, D1 limitation status, immutable predecessor guards, and the continuing authorization locks.

**PASS_WITH_LIMITATIONS: Contract corrected. Role-card evaluation may proceed, but model selection remains unauthorized.**

Any future role-card evaluation must use the corrected sub-role cards, preserve Class A fail-closed behavior, obtain any required governed membership authorization, and report all frozen seeds without post-hoc selection. It cannot be used to claim a selected model, a winning context duration, D2 validation, MR60 supervised physiology, or production readiness.
