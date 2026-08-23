# SafeNest mmWave V2 — M-PV3.6 Role S Short Context Evaluation Report

## 1. Review metadata

- Date: **2026-08-23**
- Evaluator: **Independent evaluation engineer**
- Phase: **M-PV3.6 Role-Based Evaluation**
- Role: `ROLE_S_SHORT_CONTEXT`
- Candidate: `MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1`
- Frozen base: **PR #134 merged state**, merge commit `443d45d408829becc6a4e4db71bd6d9152c0d41d`
- Contract schema: `M-PV3.6.2_CORRECTIVE`
- Gate: **PASS_WITH_LIMITATIONS**

## 2. Executive conclusion

Role S has independently measurable breathing, Class A safety, stability, responsiveness, and footprint evidence that can be carried into a future role comparison.

The evidence is limited. D1 DEV VAL contains no eligible ABSENT contexts, seed instability is material, subject coverage is limited, and responsiveness evidence is synthetic only. Therefore this report does not establish final role eligibility, production suitability, a winning context length, or model selection.

M-PV3 remains `NO_SELECTION_READY`. M-PV4 remains unauthorized. No combined score, latency-accuracy scalar, threshold relaxation, cascade, or adaptive-context implementation was used.

## 3. Evaluation boundary

This phase replayed the existing frozen short-context candidate checkpoints. It did not retrain, create a checkpoint, select a seed, tune a threshold, fit calibration, or generate ECE.

The evaluation did not access D2 or MR60 supervised physiology. It did not modify the M-PV3.6 contract, the M-PV1 contract, the M-PV2 30-second contract, Q2, or I1/I2/I3. It did not evaluate Role L and did not compare Role S as a winner or loser against Role L.

## 4. Frozen Role S contract

| Item | Frozen value |
|---|---|
| Input | `[B,150,1]` |
| Context | `[t-15s,t]` |
| Sampling | 10 Hz |
| Samples | 150 |
| Ordering | oldest to newest |
| Target | `[t-5s,t]` |
| Target samples | `100:150` in the short context |
| Task | breathing evidence only |
| RR | `NOT_APPLICABLE` |
| Temporal hold | `NOT_APPLICABLE` |
| ECE | `NOT_APPLICABLE`; no pre-existing valid calibration was available |

`PRESENT` and `ABSENT` remain inherited breathing-reference states. `AMBIGUOUS` rows remain provenance and are excluded from pure-class metrics without label rewriting. Invalid runtime input remains an abstention/availability state, not a physiological label.

## 5. Governed evaluation membership

| Membership | Contexts | Subjects | Eligible PRESENT | Eligible ABSENT | AMBIGUOUS | Use |
|---|---:|---:|---:|---:|---:|---|
| D0 TRAIN | 318 | 66 | 162 | 116 | 40 | observe-only; not held-out evidence |
| D1 DEV TRAIN | 185 | 8 | not scored here | not scored here | not scored here | inherited training membership, not refit |
| D1 DEV VAL | 59 | 3 | 57 | 0 | 2 | governed development validation |

D1 train/validation subject intersection is zero. D0 VAL and D0 subject-heldout membership were not opened. D2 and MR60 supervised physiology were not accessed.

The target lineage remains `M-PV1.breathing_reference_state`. No label was created from an apnea string, breath-hold name, radar amplitude, low amplitude, corruption, or model output.

## 6. Card B — Breathing evidence

F1 below is PRESENT-class F1. D0 is explicitly observe-only. D1 ABSENT recall is `NOT_APPLICABLE` because the governed D1 DEV VAL membership has zero eligible ABSENT contexts; it is not zero or failure.

| Group | Seed | PRESENT recall | ABSENT recall | Precision | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|
| D0 TRAIN observe-only | 11 | 0.685185 | 0.775862 | 0.810219 | 0.742475 | 0.213409 |
| D0 TRAIN observe-only | 23 | 0.962963 | 0.836207 | 0.891429 | 0.925816 | 0.067893 |
| D0 TRAIN observe-only | 47 | 0.765432 | 0.681034 | 0.770186 | 0.767802 | 0.212932 |
| D1 DEV VAL | 11 | 0.192982 | `NOT_APPLICABLE` | 1.000000 | 0.323529 | 0.260167 |
| D1 DEV VAL | 23 | 0.877193 | `NOT_APPLICABLE` | 1.000000 | 0.934579 | 0.102880 |
| D1 DEV VAL | 47 | 0.087719 | `NOT_APPLICABLE` | 1.000000 | 0.161290 | 0.263664 |

ECE was not generated. The frozen M-PV3.6 rule allows ECE only when calibration already exists without fitting a new calibration model.

## 7. Card C — Stability

All three frozen candidate-training seeds were evaluated on the same governed memberships. The best/worst labels below are descriptive summaries only; no seed was selected after observing results.

| Group | Metric | Mean | Population std | Min | Max | Worst seed | Best seed |
|---|---|---:|---:|---:|---:|---:|---:|
| D0 TRAIN observe-only | PRESENT recall | 0.804527 | 0.116723 | 0.685185 | 0.962963 | 11 | 23 |
| D0 TRAIN observe-only | ABSENT recall | 0.764368 | 0.063868 | 0.681034 | 0.836207 | 47 | 23 |
| D0 TRAIN observe-only | Precision | 0.823945 | 0.050440 | 0.770186 | 0.891429 | 47 | 23 |
| D0 TRAIN observe-only | F1 | 0.812031 | 0.081120 | 0.742475 | 0.925816 | 11 | 23 |
| D0 TRAIN observe-only | Brier | 0.164745 | 0.068485 | 0.067893 | 0.213409 | 11 | 23 |
| D1 DEV VAL | PRESENT recall | 0.385965 | 0.349999 | 0.087719 | 0.877193 | 47 | 23 |
| D1 DEV VAL | ABSENT recall | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| D1 DEV VAL | Precision | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 11 | 11 |
| D1 DEV VAL | F1 | 0.473133 | 0.332946 | 0.161290 | 0.934579 | 47 | 23 |
| D1 DEV VAL | Brier | 0.208904 | 0.074984 | 0.102880 | 0.263664 | 47 | 23 |

Per-subject results are retained for every seed: 66 D0 subjects per seed and 3 D1 DEV VAL subjects per seed. They are not collapsed, dropped, or used for post-hoc seed selection. The complete subject-level card is in the evidence manifest.

## 8. Card A — Safety

The safety card is `SYNTHETIC_ONLY`. It reuses the frozen Q2/I3 fail-closed evidence and does not claim live-device behavior.

| Synthetic Q2 scenario | Availability/application state | Physiology executed | Physiology class |
|---|---|---:|---|
| Large gap | `INPUT_UNAVAILABLE` | false | null |
| Source freeze | `INPUT_UNAVAILABLE` | false | null |
| Stale source | `INPUT_UNAVAILABLE` | false | null |
| Exact flat signal | `INPUT_UNAVAILABLE` | false | null |

Presence precedence checks also pass:

- presence false → `PRESENCE_SUPPRESSED`; physiology does not execute;
- presence unknown → `PRESENCE_SUPPRESSED`; physiology does not execute;
- presence true plus invalid quality → `INPUT_UNAVAILABLE`; physiology does not execute.

`INPUT_UNAVAILABLE` is not allowed to become `PRESENT`, `ABSENT`, `NORMAL`, or `APNEA`. No interpolation, synthetic physiology labeling, or corruption-based threshold tuning was performed.

## 9. Card D — Responsiveness

Responsiveness is reported separately and marked `SYNTHETIC_ONLY`.

| Scenario | Context refill time | First valid decision | Usable-slot ratio | INPUT_UNAVAILABLE ratio |
|---|---:|---:|---:|---:|
| Gap | 15.0 s | 15.0 s | 0.858491 | 0.141509 |
| Freeze | 15.0 s | 15.0 s | 0.858491 | 0.141509 |
| Stale source | 15.0 s | 15.0 s | 0.858491 | 0.141509 |

These are frozen synthetic Q2 timing diagnostics. No real sensor latency or device recovery claim is made.

## 10. Card E — Footprint

| Metric | Result |
|---|---:|
| Parameters | 2,297 |
| Float32 parameter bytes | 9,188 |
| Checkpoint bytes per seed | 13,125 |
| All three frozen checkpoint bytes | 39,375 |
| Input tensor | 600 bytes, `[1,150,1]`, float32 |
| Output tensor | 4 bytes |
| MACs | 45,304 |
| FLOPs estimate | 90,608 |
| Deterministic memory estimate | 16,164 bytes |

The footprint is a deterministic artifact estimate. No INT8/TFLite artifact and no Raspberry Pi benchmark were produced.

## 11. Required limitations

- D1 ABSENT is unavailable: zero eligible ABSENT contexts means D1 ABSENT recall and balanced two-class F1 are `NOT_APPLICABLE`.
- D0 TRAIN metrics are observe-only and are not held-out selection evidence.
- Seed instability is material, especially on D1 PRESENT recall; no failed or unfavorable seed was dropped.
- Subject coverage is limited: D1 DEV VAL contains only three validation subjects.
- RR is `NOT_APPLICABLE` and was not evaluated.
- Temporal hold is `NOT_APPLICABLE` and was not evaluated.
- D2 remains locked and was not accessed.
- MR60 supervised physiology remains prohibited and was not used.
- No INT8/TFLite artifact was generated.
- No Raspberry Pi or real-device benchmark was performed.
- Q2 gap, freeze, stale, and flat diagnostics are synthetic only.
- No final role eligibility, model selection, context winner, cascade, or adaptive-context decision is made.

## 12. Evidence and verification

Evidence manifest:

`datasets/mmwave/manifests/M-PV3_6_ROLE_S_SHORT_CONTEXT_evaluation/evidence_manifest.json`

Validation and checksums:

- `datasets/mmwave/manifests/M-PV3_6_ROLE_S_SHORT_CONTEXT_evaluation/validation_result.json`
- `datasets/mmwave/manifests/M-PV3_6_ROLE_S_SHORT_CONTEXT_evaluation/checksums.json`

Evaluation and validation tools:

- `scripts/evaluate_mmwave_m_pv36_role_s_short_context.py`
- `scripts/validate_mmwave_m_pv36_role_s_short_context.py`
- `tests/test_mmwave_m_pv36_role_s_short_context.py`

The focused validator reports zero failed checks and the focused test suite reports four passed tests.

## 13. Final gate

**PASS_WITH_LIMITATIONS**

Answer to the phase question — **Is `ROLE_S_SHORT_CONTEXT` sufficiently evidenced for future role comparison?** — **Yes, with explicit limitations.** Role S has independently auditable cards for future comparison, but the current evidence is not a final model decision and does not establish that 15 seconds is better than 30 seconds.
