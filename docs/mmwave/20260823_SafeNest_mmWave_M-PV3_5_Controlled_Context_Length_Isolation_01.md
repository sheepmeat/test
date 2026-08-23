# SafeNest mmWave V2 — M-PV3.5 Controlled Context Length Isolation Study

**Date:** 2026-08-23
**Branch:** `experiment/mmwave-m-pv35-context-isolation`
**Base:** `origin/main` at `dc25952ca12a323477f77b9c30c7b1921323491e`
**Gate:** `PASS_WITH_LIMITATIONS`
**Decision boundary:** controlled comparison only; no model selection

## 1. Scope

M-PV3.5 answers one limited question: with the same governed data, model, preprocessing, training objective, and seed set, does changing the causal trace context from 15 seconds to 30 seconds produce a stable difference in breathing-evidence performance?

This is independent comparison evidence. It does not select a production model, approve M-PV4, tune a threshold, fit calibration, generate an INT8/TFLite artifact, claim Raspberry Pi performance, or make a clinical claim. The existing M-PV3 selection contract and the separate M-PV2 short-context candidate were not modified or merged into this registry.

## 2. Exact experimental controls

The frozen contract is `MMWAVE_V2_M_PV35_CONTROLLED_CONTEXT_ISOLATION_V1`. Context duration and its resulting tensor length are the only variables.

| Control | Both lanes |
|---|---|
| Target | Fixed final five seconds, `[t-5s,t]` |
| Sampling | 10 Hz |
| Model | `PARITY_TRACE_CNN_V1`: Conv1D 1→8→16→24, adaptive global pooling, Linear 24→16→1 |
| Parameters | 2,297 exactly in every run |
| Optimizer | Adam, learning rate 0.001, weight decay 0.0001, batch size 32 |
| Loss | TRAIN-only source/subject/class-weighted masked binary cross-entropy with logits |
| Seeds | 11, 23, 47 |
| Schedule | Maximum 150 epochs; D1 DEV masked BCE early stopping, minimum 30 epochs, patience 20 |
| Threshold | 0.50, frozen before training; not tuned after evaluation |
| Preprocessing | One global z-score fit once on the full 30-second clean TRAIN traces and applied unchanged to both lanes |

The 15-second lane consumes the tail 150 samples of each accepted 300-sample causal trace. The 30-second lane consumes all 300 accepted samples. Both remain oldest-to-newest causal inputs and preserve the same final target anchor.

## 3. Dataset accounting

| Membership | Contexts | Role |
|---|---:|---|
| D0 TRAIN | 318 | Training only |
| D1 DEV TRAIN | 185 | Training |
| D1 DEV VAL | 59 | Subject-disjoint development evaluation |
| Total governed inputs | 562 | Unique, with no duplicate model-input IDs |

D1 TRAIN contains eight subjects and D1 DEV VAL contains three subjects; their subject intersection is zero. D0 VAL, D0 subject-heldout contexts, D2 payload semantics, MR60 supervised physiology, regenerated targets, and new labels were excluded. The D1 DEV VAL set has 57 eligible PRESENT contexts and two AMBIGUOUS contexts, with no eligible ABSENT context. AMBIGUOUS was retained in provenance and excluded from loss and pure-class metrics.

## 4. Architecture parity explanation

The convolutional layers, hidden widths, kernel sizes, strides, pooling operation, output head, initialization procedure, and parameter count are exactly the same. Adaptive global pooling permits the one model definition to accept `[B,150,1]` and `[B,300,1]` without padding, truncating the 30-second lane, or introducing input-length-dependent learned parameters. The two lanes also share one fitted scaler rather than independently fitting length-specific statistics.

Their operation counts differ only because the same convolutional layers process a different number of samples. This is the intended computational consequence of context length, not an architecture/capacity change.

## 5. 15-second results

The table reports D1 DEV VAL. ABSENT recall is unavailable because that split contains no eligible ABSENT context. Precision is consequently not evidence of ABSENT specificity and must not be interpreted as such.

| Seed | Best epoch | PRESENT recall | Precision | F1 | Brier |
|---:|---:|---:|---:|---:|---:|
| 11 | 4 | 0.1053 | 1.0000 | 0.1905 | 0.2531 |
| 23 | 4 | 0.9298 | 1.0000 | 0.9636 | 0.2299 |
| 47 | 6 | 0.1228 | 1.0000 | 0.2188 | 0.2551 |

Across seeds, PRESENT recall was `0.3860 ± 0.3846` (population standard deviation), F1 was `0.4576 ± 0.3580`, and Brier was `0.2460 ± 0.0114`. Seeds 11 and 47 did not attain useful PRESENT recall under the frozen setup; they are retained as failed/unstable seed evidence rather than excluded.

## 6. 30-second results

| Seed | Best epoch | PRESENT recall | Precision | F1 | Brier |
|---:|---:|---:|---:|---:|
| 11 | 4 | 0.1930 | 1.0000 | 0.3235 | 0.2379 |
| 23 | 4 | 0.6667 | 1.0000 | 0.8000 | 0.2224 |
| 47 | 5 | 0.1754 | 1.0000 | 0.2985 | 0.2569 |

Across seeds, PRESENT recall was `0.3450 ± 0.2275`, F1 was `0.4740 ± 0.2307`, and Brier was `0.2391 ± 0.0141`.

## 7. Seed stability comparison

No combined score was created. The individual metrics show a mixed pattern: seed 23 favors 15 seconds on PRESENT recall and F1, whereas seeds 11 and 47 favor 30 seconds on those metrics. The mean F1 differs by only 0.0164 in favor of 30 seconds, while the 15-second lane has markedly larger recall/F1 variation because its seed 23 run differs sharply from its other two runs.

Therefore, this controlled study does not support the conclusion that 30 seconds is inherently more accurate, nor that 15 seconds is inherently more accurate. With only three seeds and a DEV set without an eligible ABSENT class, the observed differences are dominated by seed instability and limited evaluation coverage rather than a stable duration effect.

## 8. Subject-level comparison

All D1 DEV VAL subjects were PRESENT-only among eligible examples. The following per-seed PRESENT recalls make the cross-subject pattern visible; per-subject precision, F1, Brier, recording IDs, and unavailable-class fields are retained in `subject_metrics.json`.

| Seed | 15 s: P03 / P09 / P11 | 30 s: P03 / P09 / P11 |
|---:|---|---|
| 11 | 0.1579 / 0.1250 / 0.0714 | 0.1579 / 0.1667 / 0.2857 |
| 23 | 0.9474 / 0.9167 / 0.9286 | 0.7368 / 0.5833 / 0.7143 |
| 47 | 0.1579 / 0.1250 / 0.0714 | 0.2105 / 0.1667 / 0.1429 |

The same seed-dependent pattern appears across all three held-out subjects. This reinforces the non-selection conclusion; it is not a subject-specific production claim.

## 9. Cycle-count and frequency-resolution analysis

| RR (bpm) | Cycles in 15 s | Cycles in 30 s |
|---:|---:|---:|
| 6 | 1.5 | 3.0 |
| 8 | 2.0 | 4.0 |
| 12 | 3.0 | 6.0 |
| 20 | 5.0 | 10.0 |

The nominal frequency resolutions are `1/15 = 0.0667 Hz` (4 bpm equivalent) and `1/30 = 0.0333 Hz` (2 bpm equivalent). These values only explain the engineering information available to a longer window; they do not prove breathing or RR accuracy, and RR was not trained or evaluated in this phase.

## 10. Recovery comparison

This is a synthetic Q2 timing/accounting diagnostic only. Both lanes retain hard fail-closed behavior: `INPUT_UNAVAILABLE` blocks model invocation and is never emitted as PRESENT, ABSENT, NORMAL, or APNEA.

| Measure | 15 s | 30 s |
|---|---:|---:|
| Context refill time | 15 s | 30 s |
| First valid inference time | 15 s | 30 s |
| Difference, 30 s minus 15 s | — | 15 s |

The result does not measure real MR60 recovery or latency.

## 11. Footprint comparison

| Measure | 15 s | 30 s |
|---|---:|---:|
| Parameters | 2,297 | 2,297 |
| Float32 parameter bytes | 9,188 | 9,188 |
| Input tensor bytes | 600 | 1,200 |
| Estimated MACs/inference | 45,304 | 92,720 |

These are deterministic operation and memory estimates. They are not Raspberry Pi timing measurements.

## 12. Limitations

- D1 DEV VAL has no eligible ABSENT context, so ABSENT recall and discrimination are not established.
- D0 TRAIN results are retained as observe-only diagnostics in the evidence, not as held-out performance.
- The controlled model is deliberately small and seed-sensitive; this isolates duration from the prior architecture/objective confounds but does not establish a production-ready architecture.
- Q2 recovery evidence is synthetic and does not validate a live device.
- No calibration, post-hoc threshold tuning, quantization, deployment benchmark, clinical apnea claim, D2 semantic use, or MR60 supervised physiology was performed.

## 13. Recommendation for the next gate

Keep both lanes unselected. Do not use this evidence to reopen M-PV3 selection or approve M-PV4. A later, separately authorized and pre-registered evaluation would need adequate subject-disjoint coverage of both breathing classes and a stability plan that addresses the observed seed sensitivity, while preserving the frozen target and fail-closed Q2 semantics.

## Reproducibility and evidence

- A complete regeneration produced an identical `checksums.json` digest, including all six checkpoints and compact evidence artifacts.
- Focused M-PV3.5 validation: `PASS_WITH_LIMITATIONS`, 0 failed checks.
- Upstream M-PV1, M-PV2, M-PV3, and M-PV2 short-context validators: `PASS_WITH_LIMITATIONS`, 0 failed checks each.
- Related regression tests: 25 passed.

Evidence paths:

- `config/mmwave/m_pv35_context_isolation_contract.json`
- `datasets/mmwave/manifests/M-PV3_5_controlled_context_isolation/`
- `models/mmwave/m_pv35_context_isolation/`
- `scripts/mmwave_m_pv35_context_isolation.py`
- `scripts/validate_mmwave_m_pv35_context_isolation.py`

**PASS_WITH_LIMITATIONS: controlled comparison completed.**
