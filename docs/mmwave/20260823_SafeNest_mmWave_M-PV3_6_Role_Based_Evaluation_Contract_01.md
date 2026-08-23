# SafeNest mmWave V2 — M-PV3.6 Role-Based Evaluation Contract

**Date:** 2026-08-23
**Branch:** `docs/mmwave-m-pv36-role-evaluation-contract`
**Base:** `origin/main` at `dc25952ca12a323477f77b9c30c7b1921323491e`
**Gate:** `PASS_WITH_LIMITATIONS`
**Phase mode:** Contract design only; no evaluation run and no model selection

## 1. Executive decision

M-PV3.6 freezes a role-based evaluation framework for future independent execution. It separates a 15-second breathing-screening candidate role from a 30-second full-task candidate role, without forcing incomparable tasks into one utility score.

No 15-second or 30-second model is selected. M-PV3 remains `NO_SELECTION_READY`, M-PV4 is not authorized, and this phase does not train a checkpoint, tune a threshold, fit calibration, open a reserved split, access D2 semantics, use MR60 supervised physiology, or measure device performance.

## 2. Why M-PV3.6 is required

The prior 15-second and 30-second candidates do not have the same task scope. The short lane is breathing-evidence only; it has no authorized RR or temporal-hold task. The long lane may support breathing, RR, and quality. Treating a missing short-lane RR metric as zero or failure would be unfair, while letting latency compensate for an unsafe invalid-input result would be unsafe.

M-PV3.5 also showed that its controlled context-length comparison did not establish a stable performance advantage attributable to duration. Its seed variation was larger than any stable duration effect. M-PV3.6 therefore freezes how future evidence is reported, rather than declaring 15 seconds or 30 seconds better.

## 3. Authoritative predecessor state

| Predecessor | Authoritative state retained by this contract |
|---|---|
| M-PV3 | `PASS_WITH_LIMITATIONS`; 30-second full-task selection remains `NO_SELECTION_READY`. |
| M-PV2-SHORT | `PASS_WITH_LIMITATIONS`; 15-second breathing-only candidate, with no RR/temporal-hold selection utility. |
| M-PV3.5 | `PASS_WITH_LIMITATIONS`; no stable context-duration performance advantage was isolated. |

M-PV3's frozen 30-second utility guards remain unchanged: PRESENT recall ≥ 0.95, Brier ≤ 0.05, RR MAE ≤ 5 bpm, and RR within ±2/±4/±6 bpm ≥ 0.40/0.60/0.75. M-PV3.6 neither relaxes these guards nor retroactively changes the M-PV3 result.

## 4. Role S — 15-second short-context role

Role S is a candidate engineering role for fast breathing-evidence screening, faster causal-buffer recovery, and a smaller inference footprint. It is not automatically a production role.

Its applicable metric cards are:

- Breathing: PRESENT recall, ABSENT recall only where a governed split contains eligible ABSENT examples, precision, F1, Brier, and optional already-valid ECE.
- Safety: Q2 invalid false acceptance, invalid-to-physiology transition, fail-closed preservation, stale/freeze/gap handling, and clean false rejection where defined.
- Stability: every frozen seed, mean, population standard deviation, min/max, worst/best seed, and per-subject results.
- Responsiveness: context refill, first valid inference, and usable-slot ratio under frozen Q2 scenarios, marked `SYNTHETIC_ONLY` until a live device is measured.
- Footprint: parameters, model/input bytes, MACs/FLOPs, and deterministic memory estimates.

RR and temporal-hold metrics for Role S are explicitly `NOT_APPLICABLE`, not zero, failure, or missing-as-error. They may enter a future short role only after separately authorized training and evaluation.

## 5. Role L — 30-second long-context role

Role L is a candidate role for breathing evidence, RR, quality, multi-cycle physiology evidence, and a possible stable-confirmation path. It is not automatically a production role.

Its cards include breathing, RR, quality, safety, stability, responsiveness, and footprint. The RR card preserves the historical M-PV3 metrics and frozen utility guards unchanged. Later hardware timing is `REQUIRES_FUTURE_GATE`; deterministic footprint estimates must not be presented as Raspberry Pi measurements.

## 6. Safety hierarchy

Class A safety gates are non-compensable. A failure in invalid false acceptance, invalid-to-physiology transition, fail-closed preservation, or frozen stale/freeze/gap handling blocks role eligibility. Better latency, smaller footprint, or stronger average accuracy cannot compensate for a Class A failure.

Every invalid input must remain `INPUT_UNAVAILABLE` and must not emit PRESENT, ABSENT, NORMAL, or APNEA. Synthetic Q2 evidence is useful only for the declared synthetic condition; it is not live MR60 or hardware validation.

## 7. Physiological metric rules

Class B metrics are role-specific. Breathing metrics can be reported for both roles where governed labels support them. RR/quality metrics belong only to Role L unless a future phase explicitly authorizes and validates equivalent short-lane tasks.

The contract prohibits a weighted aggregate, normalized utility score, accuracy-latency scalar, AHP-style ranking, or Pareto rule that silently produces one winner. It also prohibits cross-role comparisons that penalize Role S for an inapplicable RR task.

## 8. Seed-stability rules

Future reports must retain every frozen candidate-training seed and report its evaluation result on the same governed membership. They must include mean, population standard deviation, minimum, maximum, worst seed, best seed, and per-subject results. Collapsed seeds cannot be dropped, and the favorable seed cannot be selected after seeing results.

M-PV3.6 distinguishes candidate-training seed from evaluation seed result and from a seed-selection policy. Any policy to select a seed, a maximum allowed variance, or a minimum worst-seed threshold is `THRESHOLD_REQUIRES_PRE_REGISTRATION`. It needs an up-front use case, seed count, class coverage, subject-disjoint membership, failure cost, and justification before results are examined.

## 9. Evaluation-data sufficiency

Current D1 DEV VAL has 57 eligible PRESENT contexts, two AMBIGUOUS contexts, zero eligible ABSENT contexts, and three validation subjects. It therefore cannot establish ABSENT recall, specificity, balanced macro F1, or full breathing-state discrimination.

Future full breathing-state evaluation is recorded as `BREATHING_BOTH_CLASS_EVALUATION_REQUIRED`. It requires subject-disjoint eligible PRESENT and ABSENT examples, preserved AMBIGUOUS handling, no target regeneration, and no leakage. M-PV3.6 does not open D0 VAL or D0 subject-heldout data; it requires explicit governed authorization before any reserved membership is accessed. D0 TRAIN remains observe-only.

## 10. Responsiveness metrics

Context refill time, first valid inference time, and usable-slot ratio under frozen Q2 scenarios are Class D engineering dimensions. They are reported separately from physiological utility and safety. Synthetic Q2 timing must be labeled `SYNTHETIC_ONLY`; it cannot support real-device latency claims.

## 11. Footprint metrics

Class E reports parameter count, model bytes, input tensor bytes, MACs/FLOPs, and deterministic memory estimates. It is useful engineering evidence but does not produce a winner or prove Raspberry Pi speed. A real hardware benchmark needs a separately authorized measured phase.

## 12. `NOT_APPLICABLE` semantics

`NOT_APPLICABLE` is an explicit valid state for a task that the role does not train or evaluate. It must never be rendered as zero, failure, or an implicit error. For this contract, 15-second RR and temporal hold are `NOT_APPLICABLE`; D2 and MR60 supervised physiology are `NOT_AUTHORIZED`; D1 ABSENT evaluation is `INCOMPLETE`; real Pi latency and both-class evaluation are `REQUIRES_FUTURE_GATE`.

## 13. Prohibited comparisons

Future reports must not claim that 15 seconds is more accurate, 30 seconds is more accurate, 30 seconds is inherently more stable, or context duration does not matter unless a controlled experiment isolates duration and shows stable supporting evidence. Current evidence does not meet that bar.

## 14. Cascade and adaptive-context deferral

M-PV3.6 does not implement a 15-second screening → 30-second confirmation cascade, confidence switching, adaptive context, dual-model composition, buffer-state behavior, or latency composition. These remain hypotheses only. Before any implementation proposal, evidence must include stable 15-second screening, a joint confusion/error matrix, error correlation, threshold/persistence policy, fail-closed composition, buffer-state semantics, and latency composition.

## 15. Requirements for the next execution phase

A future independently authorized evaluation must:

- use the frozen role cards and safety hierarchy;
- obtain governed, subject-disjoint both-class breathing evaluation membership before making full discrimination claims;
- report every frozen seed and per-subject result without post-hoc seed selection;
- preserve M-PV3's long-role utility guards unchanged;
- keep D2 locked and MR60 supervised physiology prohibited unless a later explicit gate changes authorization;
- keep synthetic responsiveness and deterministic footprint distinct from live-device evidence.

## 16. Limitations

- This is a framework, not a new performance run.
- D1 DEV VAL lacks eligible ABSENT contexts.
- No defensible numerical seed-stability threshold is set yet; a future rule must be pre-registered.
- No real MR60, Raspberry Pi, calibration, quantization, or production selection evidence was generated.

## 17. Gate decision and evidence

The machine-readable contract, evaluation matrix, evidence requirements, and focused validator are located at:

- `config/mmwave/m_pv36_role_based_evaluation_contract.json`
- `datasets/mmwave/manifests/M-PV3_6_role_based_evaluation/`
- `scripts/validate_mmwave_m_pv36_role_based_evaluation.py`
- `tests/test_mmwave_m_pv36_role_based_evaluation.py`

Focused validation passed with zero failed checks. The contract preserves non-compensable safety, forbids a combined score, makes 15-second RR `NOT_APPLICABLE`, retains the M-PV3 guards, governs seed instability, records the D1 ABSENT deficiency, leaves D2 locked, and makes no production selection.

**PASS_WITH_LIMITATIONS: M-PV3.6 freezes the role-based evaluation framework only. No 15s or 30s model is selected, M-PV3 remains NO_SELECTION_READY, and M-PV4 remains unauthorized.**
