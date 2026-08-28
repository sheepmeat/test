# SafeNest mmWave V2 — M-PV2 Bounded Candidate Training Report

**Date:** 2026-08-23
**Branch:** `feature/mmwave-v2-m-pv2-candidate-training`
**Base:** `origin/main` at `71475aa37b37ae5e643461d804f2ecdcbaea34cd`
**Gate:** `PASS_WITH_LIMITATIONS`
**M-PV2 ready for M-PV3:** `YES` (bounded candidate registry only)

## 1. Scope and decision boundary

This run implements only the M-PV2 bounded candidate-training phase. It does not choose a final model. No `SELECTED_FLOAT_MODEL` was produced, and no threshold, calibration, INT8/TFLite artifact, Raspberry Pi deployment, or event-level F1 was performed.

The frozen prerequisite was the merged M-PV1 corrective contract (`M-PV1.2_CORRECTIVE_ALIGNMENT`). Its validation gate was `PASS_WITH_LIMITATIONS`, `ok=true`, and `m_pv1_ready_for_m_pv2=true`.

The following data boundaries were enforced:

- D0: 318 unique `TRAIN` contexts only. D0 VAL and `D0_SUBJECT_HELDOUT` were not reconstructed because the frozen M-PV1 model-ready membership is TRAIN-only; adding them would change the 562-input contract.
- D1: 244 model-ready contexts. Training used `D1_DEV_TRAIN`; validation used subject-disjoint `D1_DEV_VAL` (eight versus three subjects, no recording leakage).
- D2: custody state only. Semantic access, feature extraction, inference, and selection count remain zero.
- MR60: QA/reference only; no physiology labels or supervised training.

## 2. Frozen input accounting

| Item | Count |
|---|---:|
| D0 unique model-ready inputs | 318 |
| D1 unique model-ready inputs | 244 |
| Total unique clean inputs | 562 |
| Duplicate target overlays | 0 |
| D0 breathing PRESENT / ABSENT / AMBIGUOUS | 162 / 116 / 40 |
| D1 breathing PRESENT / ABSENT / AMBIGUOUS | 236 / 0 / 8 |
| RR-eligible inputs | 398 |
| D1 short audit-only recordings excluded from tensors | 21 |

Every tensor audit row retains source, subject, recording, context/target interval, fixed final-anchor identity, supervision masks, R1/R2 profile IDs, and source provenance. Waveform arrays and tensor caches were not committed.

The model input is the accepted R1 output, the first fixed 300 samples (30 seconds at 10 Hz), and R2-derived descriptors. The breathing target is always the final five seconds (`indices 250:300`); target metadata is not placed in the tensor.

## 3. Authorized candidate pool

| Family | Inputs | Heads | Parameters |
|---|---|---|---:|
| A — F2 MLP | F2 25 + validity mask + quality descriptors | RR, quality | 5,986 |
| B — trace TCN | trace 300 + mask + scale/quality descriptors | breathing evidence, RR, quality | 17,915 |
| C — hybrid | Family B plus F2 25 + validity mask | breathing evidence, RR, quality | 21,115 |

The optimizer and schedule were frozen before training: Adam, learning rate `1e-3`, weight decay `1e-4`, batch size 32, maximum 150 epochs, minimum 30 epochs, patience 20, gradient clip 1.0. Seeds were exactly `11`, `23`, and `47`, for nine primary runs.

Preprocessing statistics were fitted on clean TRAIN membership only. RR mean/std used RR-eligible TRAIN rows only. Source weights were D0 `0.75` and D1 `0.25`, with inverse eligible-count subject weighting within source. No source-specific gain matching or window-local MAD division was used.

For Q2 quality supervision, 50 deterministic training corruptions (9.95% of the 503 clean training inputs) and five validation corruptions were derived from the Q2 contract. Physiology targets were not rewritten; corrupted examples were quality-only negatives.

## 4. Development results (not a selection)

The table reports D1 DEV_VAL diagnostics. Family A has no breathing head by contract. The fixed breathing threshold is 0.50 and was not tuned.

| Family/seed | Best val loss | Breathing PRESENT recall | Breathing Brier | RR MAE (bpm) | RR within 4 bpm | Q2 invalid false acceptance |
|---|---:|---:|---:|---:|---:|---:|
| A/11 | 0.205647 | n/a | n/a | 4.208 | 0.684 | 0.000 |
| A/23 | 0.198289 | n/a | n/a | 3.958 | 0.737 | 0.000 |
| A/47 | 0.204044 | n/a | n/a | 4.039 | 0.754 | 0.000 |
| B/11 | 0.469786 | 1.000 | 0.0985 | 4.565 | 0.632 | 0.000 |
| B/23 | 0.163349 | 1.000 | 0.0065 | 4.194 | 0.667 | 0.000 |
| B/47 | 0.246967 | 0.982 | 0.0251 | 4.900 | 0.649 | 0.000 |
| C/11 | 0.176146 | 0.982 | 0.0212 | 4.540 | 0.632 | 0.000 |
| C/23 | 0.192251 | 0.982 | 0.0179 | 4.541 | 0.632 | 0.000 |
| C/47 | 0.119416 | 1.000 | 0.0013 | 4.461 | 0.649 | 0.000 |

D1 DEV_VAL contains 57 PRESENT and two AMBIGUOUS eligible breathing contexts, with zero ABSENT examples. Therefore PR-AUC/ROC-AUC and false-present-on-ABSENT are explicitly undefined on that split; this is a data limitation, not an imputed negative class.

D0 TRAIN is reported as an observe-only development diagnostic, not a held-out claim. For example, Family B/11 gives PRESENT recall `0.981`, false absent on PRESENT `0.019`, and RR MAE `6.51 bpm` on the D0 TRAIN observation pool; the high false-present-on-ABSENT rate (`0.698`) is retained as evidence rather than hidden.

Seed sensitivity is descriptive only. Best-validation-loss mean/std were A `0.2027/0.0032`, B `0.2934/0.1293`, and C `0.1626/0.0312`; these values do not select a family or seed.

The quality head rejected every synthetic invalid example in the recorded validation set (hard-Q2 invalid false acceptance `0.000`) and did not reject the clean validation rows (clean false rejection `0.000`). Per-corruption results are recorded for `FLAT_EXACT`, `SOURCE_FREEZE`, `STALE_SOURCE`, `LARGE_GAP`, `JITTER_PLUS_LARGE_GAP`, and `REPUBLICATION_TO_FREEZE`.

## 5. Reproducibility and safety evidence

- Family B seed 11 was retrained in a fresh process. The canonical parameter SHA matched exactly: `84bb325bb2fa8054b39ac7c30f3aadf6acc1ed5886b79f93352d77b1fb5d4aba`.
- Split identity, scaler SHA, optimizer schedule, and deterministic CPU settings are recorded in `determinism_audit.json`.
- D2 lock audit records semantic access `false`, feature extraction `false`, inference count `0`, and selection `false`.
- The prior V1 NPZ is observe-only. It was not retrained, compared apples-to-apples, or used for selection.
- Temporal output is a context diagnostic only. Event-level F1 and sequence thresholding are deferred to M-PV3 or later.

## 6. Evidence and validator outputs

- [M-PV2 contract](../../config/mmwave/m_pv2_candidate_training_contract.json)
- [Candidate registry](../../datasets/mmwave/manifests/M-PV2_candidate_training/candidate_registry.json)
- [Tensor/materialization lineage](../../datasets/mmwave/manifests/M-PV2_candidate_training/tensor_materialization_audit.json)
- [Metrics by source](../../datasets/mmwave/manifests/M-PV2_candidate_training/metrics_by_source.json)
- [Determinism audit](../../datasets/mmwave/manifests/M-PV2_candidate_training/determinism_audit.json)
- [M-PV2 validator result](../../datasets/mmwave/manifests/M-PV2_candidate_training/validation_result_validator.json)
- [Checksums](../../datasets/mmwave/manifests/M-PV2_candidate_training/checksums.sha256)

Executed checks:

```text
validate_mmwave_m_pv2_candidate_training.py       PASS_WITH_LIMITATIONS
test_mmwave_m_pv2_candidate_training.py           4 tests passed
validate_mmwave_m_pv1_public_multidomain_contract  PASS_WITH_LIMITATIONS
validate_mmwave_r1_sensor_independent_trace       PASS_WITH_LIMITATIONS
validate_mmwave_r2_spectral_autocorr_features     PASS_WITH_LIMITATIONS
validate_mmwave_i3_fail_closed_regression         PASS_WITH_LIMITATIONS
git diff --check                                  PASS
```

## 7. Exit interpretation

M-PV2 is complete as a bounded candidate-generation phase. All authorized families and seeds have compact float32 checkpoints and aggregate evidence, no candidate is marked as final, and the registry is ready for a later M-PV3 selection gate. The next decision must be made in M-PV3 with a separately frozen selection contract; it must not be inferred from this report's diagnostic table.
