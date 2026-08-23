# SafeNest mmWave V2 — M-PV2-SHORT-15S Candidate Result Summary

## 1. Review metadata

- Date: **2026-08-23**
- Executing agent: **Luna Max Fast 2**
- Phase: **M-PV2-SHORT-15S**
- Candidate identity: MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1
- Result identity: SHORT_CONTEXT_CANDIDATE_RESULT
- Gate: **PASS_WITH_LIMITATIONS**
- Review purpose: independent agent review of a bounded 15-second breathing-evidence ablation

### Delivery and review routing

- Pull request: [#130](https://github.com/sheepmeat/test/pull/130)
- Source branch: `codex/mmwave-v2-m-pv2-short-context-15s`
- Target branch: `main`
- This PR is independent of the existing M-PV3 selection PR and contains no M-PV3 artifacts.

## 2. Executive result

A separate 15-second causal breathing-evidence candidate was produced for comparison with the existing 30-second M-PV2 lane.

This result does **not** select a model, replace the 30-second contract, modify D0/D1 governance, modify Q2 availability semantics, or modify I1/I2/I3 runtime contracts.

No claim is made that 15 seconds is better than 30 seconds, or that 15 seconds replaces 30 seconds.

## 3. Implemented scope

The candidate uses the following frozen input profile:

| Item | Candidate contract |
|---|---|
| Context | [t-15s, t] |
| Sampling | 10 Hz |
| Samples | 150 |
| Tensor shape | [B,150,1] |
| Ordering | oldest to newest |
| Breathing target | [t-5s, t] |
| Target samples in short context | 100:150 |
| Future samples | forbidden |
| Internal event position | not used |
| Random target alignment | not used |

The short input is derived from the final 150 samples of the accepted M-PV1/R1 30-second trace. The inherited final five-second reference interval remains the target; no target is re-aligned or regenerated.

Primary learning target:

- PRESENT
- ABSENT

AMBIGUOUS and TARGET_UNAVAILABLE remain explicit supervision/status states. AMBIGUOUS rows are retained for provenance and excluded from pure-class training and metrics. Invalid input is blocked by the Q2 hard pre-gate and maps to INPUT_UNAVAILABLE; it cannot become PRESENT, ABSENT, or APNEA.

RR was not trained or evaluated. RR-related fields remain metadata only. Temporal hold was not trained.

## 4. Data governance and provenance

The candidate uses only the governed M-PV1 model-ready membership:

| Source | Use | Subjects | Contexts |
|---|---|---:|---:|
| D0 | frozen TRAIN only | 66 | 318 |
| D1 | D1_DEV_TRAIN / D1_DEV_VAL | 8 / 3 | 185 / 59 |
| Total | governed model-ready membership | 77 | 562 |

D1 train/validation subject intersection is 0 and recording intersection is 0.

The following were not used:

- D0 VAL
- D0_SUBJECT_HELDOUT
- M-N6 excluded subjects
- D2 semantic payloads, features, inference, or selection
- MR60 supervised physiology
- apnea protocol strings or breath-hold names as labels
- radar amplitude as a label
- model output as a label

Inherited breathing-reference state counts:

| Source | PRESENT | ABSENT | AMBIGUOUS |
|---|---:|---:|---:|
| D0 TRAIN | 162 | 116 | 40 |
| D1 total | 236 | 0 | 8 |
| Total | 398 | 116 | 48 |

Every recorded short-context lineage row retains source dataset, source file, subject, recording, model input, split, short context interval, target interval, reference method, and inherited target state.

## 5. Candidate architecture and artifacts

The candidate is a lightweight valid-convolution 1D CNN:

Conv1D(1→8,k5,s2) → Conv1D(8→16,k5,s2) → Conv1D(16→24,k3,s2) → newest-5-position pooling → Linear(24→16) → breathing logit

- Parameters: **2,297**
- Float32 parameter bytes: **9,188**
- Estimated operations: **45,304 MACs / 90,608 FLOPs**
- Input: [B,150,1]
- Fixed seeds: **11, 23, 47**
- Quantization/TFLite: not generated
- Final selection: not performed

The model card contains three compact candidate checkpoints. No optimizer state or epoch checkpoint series is committed.

## 6. Evaluation evidence

The existing 30-second M-PV2 breathing-capable candidate lane is used as a descriptive baseline only. It contains no selected final model; its family B/C candidate evidence is aggregated without selection.

### 6.1 Breathing evidence

| Evaluation group | 15-second macro F1 | 15-second PRESENT recall | 15-second ABSENT recall | 30-second baseline macro F1 | 30-second baseline PRESENT recall | 30-second baseline ABSENT recall |
|---|---:|---:|---:|---:|---:|---:|
| D0 TRAIN observe-only | 0.783 | 0.805 | 0.764 | 0.885 | 0.995 | 0.772 |
| D1 DEV_VAL | undefined | 0.386 | undefined | undefined | 0.991 | undefined |

D1 DEV_VAL has no supervised ABSENT rows, so D1 ABSENT recall and macro F1 are undefined for both lanes. D0 is a training/observe-only diagnostic and is not held-out evidence.

The short candidate shows seed variation on D1 PRESENT recall. This is retained as evidence and is not used to select a seed or declare superiority.

### 6.2 Availability and recovery

The following is a synthetic Q2 quality-only timing diagnostic using a one-second interruption in a 120-second stream. It is not real MR60 or Raspberry Pi measurement.

| Context | Usable prediction ratio | INPUT_UNAVAILABLE ratio | Recovery after gap/freeze/stale source | First valid decision |
|---|---:|---:|---:|---:|
| 15 seconds | 0.858 | 0.142 | 15 s | 15 s |
| 30 seconds | 0.670 | 0.330 | 30 s | 30 s |

The observed context requirement difference is **15 seconds**. The diagnostic records the same recovery result for gap, source freeze, and stale source because the Q2 invalidation window is governed by the causal context length.

Invalid synthetic inputs block model invocation and emit INPUT_UNAVAILABLE; they do not create physiology labels and do not emit PRESENT or ABSENT.

### 6.3 Latency estimate

The model card records a deterministic operation-count estimate of **0.090608 ms at a declared 1 GFLOP/s reference rate**. This is not a hardware benchmark and is not a Raspberry Pi claim.

## 7. Validation and safety evidence

Passed checks:

- short-candidate focused validator: PASS_WITH_LIMITATIONS, 0 failed checks
- short-candidate artifact tests: **4 passed**
- existing 30-second M-PV2 validator: PASS_WITH_LIMITATIONS
- existing 30-second M-PV2 artifact tests: **4 passed**
- combined inherited M-PV2/M-PV1/D0/Q2/I3 regression suite: **60 passed**
- generated-file checksums: passed
- protected existing 30-second artifacts: unchanged
- repository-relative active artifact paths: passed
- D2 semantic access: false
- MR60 supervised physiology: false
- future leakage: false

Primary evidence paths:

- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/input_contract.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/target_alignment.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/dataset_audit.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/training_config.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/model_card.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/evaluation_result.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/limitations.json
- datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/checksums.json

Implementation and review tools:

- scripts/mmwave_m_pv2_short_context_15s_candidate.py
- scripts/validate_mmwave_m_pv2_short_context_15s_candidate.py
- tests/test_mmwave_m_pv2_short_context_15s_candidate.py

## 8. Limitations and review boundary

- D0 metrics are observe-only because D0 VAL and D0_SUBJECT_HELDOUT were not authorized for this lane.
- D1 validation has no supervised ABSENT class.
- AMBIGUOUS rows are not converted to PRESENT or ABSENT.
- Availability and recovery results are synthetic Q2 diagnostics only.
- No real MR60 validation, Raspberry Pi benchmark, INT8/TFLite conversion, calibration, or deployment was performed.
- Inherited A4 reference semantics are SafeNest breathing proxies and are not clinical apnea.
- RR and temporal hold remain outside this candidate.
- Later M-PV3 evaluation must decide whether this candidate has sufficient accuracy, availability, stability, and deployment evidence.

## 9. Final review decision

**PASS_WITH_LIMITATIONS**

The success condition is met: a bounded 15-second breathing-evidence candidate was produced with auditable data lineage, causal alignment, comparative evidence, availability/recovery diagnostics, and explicit limitations.

The success condition does not imply replacement or selection of the existing 30-second M-PV2 model contract.
