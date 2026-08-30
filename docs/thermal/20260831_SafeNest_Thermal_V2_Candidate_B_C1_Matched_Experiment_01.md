# SafeNest Thermal V2 — Candidate B and C1 Matched Experiment

- Date: 2026-08-31
- Repository: `sheepmeat/test`
- Base: `625b4a6e4e0e0eef01afa24b3245ecf6416dae5a` (`#195` Candidate A Phase 2)
- Branch: `thermal-v2/candidate-b-c1-matched-experiment`
- `LOCKED_PUBLIC_TEST_ACCESS`: 0

## 1. Environment

| Item | Value |
|---|---|
| Python | 3.12.3 |
| NumPy | 2.5.2 |
| TensorFlow | 2.21.0 |
| GPU | NVIDIA GeForce RTX 2060 SUPER |
| Batch size | 256 |

Candidate A was **not** retrained. Family comparison uses merged `config/thermal/tv2_candidate_a_phase2_result.json`, not the A0 re-export artifact score.

## 2. Fair comparison contract

Same for C1 and Candidate B (and matched to merged Candidate A A0):

- PUBLIC_SDT only (Thermal-IM not used)
- TRAIN 32000 (8k / 16k / 8k), DEVELOPMENT 8000 (2k / 4k / 2k)
- `RELATIVE_THERMAL_APPEARANCE_V1` + `FRAME_ROBUST_P2_P98_V1`
- input `[62,80,1]`; classes `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL_PROXY`
- Adam `1e-3`, sparse CE, batch 256, max 30 epochs, ES val_loss patience 5, restore best, no class weights, no augmentation
- seeds 42, 7, 1337

Only architecture differs.

## 3. Architectures

**C1** `MATCHED_POOLED_MLP_CONTROL` (B6R pooled-MLP family, retrained here):

`[62,80,1]` → integer-linspace adaptive mean pool `[8,10]` flatten 80 → Dense(32, ReLU) → Dense(3, Softmax)

Parameters: **2691**

**Candidate B** `CAPACITY_MATCHED_DEPTHWISE_SEPARABLE_CNN` (not the historical 347-param instance):

Conv2D(16,3,same,ReLU) → MaxPool2 → SeparableConv2D(32) → MaxPool2 → SeparableConv2D(48) → GAP → Dense(32, ReLU) → Dense(3, Softmax)

Parameters: **4387**

**Candidate A A0** (merged reference): `COARSE_SPATIAL_RETAIN_FLATTEN_V1`, **64387** params.

## 4. C1 DEVELOPMENT results

Confusion matrices `rows=true, cols=pred`, order `(NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY)`.

| Seed | N→F | rate | FALL rec | macro F1 | F→N | NH→F | epochs | CM |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 42 | 103 | 2.57% | 0.9475 | 0.9696 | 105 | 0 | 30 | `[[2000,0,0],[35,3862,103],[0,105,1895]]` |
| 7 | 111 | 2.77% | 0.9450 | 0.9676 | 109 | 0 | 30 | `[[2000,0,0],[38,3851,111],[1,109,1890]]` |
| 1337 | 109 | 2.73% | 0.9490 | 0.9689 | 100 | 0 | 30 | `[[2000,0,0],[37,3854,109],[2,100,1898]]` |

Mean / population SD: N→F **107.67 / 3.40** (103–111). FALL rec **0.9472 / 0.0016**. macro F1 **0.9687 / 0.0008**.

C1 status: **CONTROL_COMPLETE**

## 5. Candidate B DEVELOPMENT results

| Seed | N→F | rate | FALL rec | macro F1 | F→N | NH→F | epochs | CM |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 42 | 145 | 3.62% | 0.9505 | 0.9655 | 99 | 0 | 30 | `[[1994,6,0],[27,3828,145],[0,99,1901]]` |
| 7 | 102 | 2.55% | 0.9090 | 0.9585 | 182 | 0 | 30 | `[[1972,28,0],[17,3881,102],[0,182,1818]]` |
| 1337 | 114 | 2.85% | 0.9165 | 0.9538 | 164 | 0 | 30 | `[[1953,47,0],[39,3847,114],[3,164,1833]]` |

Mean / population SD: N→F **120.33 / 18.12** (102–145). FALL rec **0.9253 / 0.0181**. macro F1 **0.9593 / 0.0048**.

## 6. A vs B vs C1

| Model | Params | N→F mean | N→F spread | FALL recall mean | Macro F1 mean |
|---|---:|---:|---|---:|---:|
| C1 matched pooled MLP | 2691 | 107.67 | 103–111, SD 3.40 | 0.9472 | 0.9687 |
| Candidate A A0 | 64387 | 17.00 | 14–21, SD 2.94 | 0.9920 | 0.9949 |
| Candidate B depthwise | 4387 | 120.33 | 102–145, SD 18.12 | 0.9253 | 0.9593 |

## 7. Interpretation

A vs C1: C1 is dramatically worse on the primary false-FALL metric and FALL recall. The spatial CNN architecture provides useful benefit beyond the matched relative-appearance representation in this offline experiment.

A vs B: B is much smaller but materially worse and less seed-stable (FALL recall 0.909 on seed 7). No extra search was run.

B status: **B_NOT_COMPETITIVE**

Offline provisional preference: **A_PREFERRED**

C1 is a control, not a prototype winner.

## 8. Artifacts

Primary seed is 42 (predefined; not cherry-picked).

| Path | bytes | SHA-256 |
|---|---:|---|
| `models/thermal/controls/tv2_c1/C1_MATCHED_POOLED_MLP_seed42.keras` | 58150 | `5091a52d74432cc529d1d1c1ebf22ab3a279ef454a30f20bcbf3a0503663e040` |
| `models/thermal/controls/tv2_c1/C1_MATCHED_POOLED_MLP_seed42_fp32.tflite` | 70460 | `b7380a52813b80e6f0892d5135a0f1b687976a350ed2bb715e638a8965f609e8` |
| `models/thermal/candidates/tv2_candidate_b/B_DEPTHWISE_SEPARABLE_seed42.keras` | 98408 | `42563c3316e9e8511ab897aaa4dfd9a154887f3a0270d5dfb77a7a344cd3ff35` |

C1 Keras is the serialized seed-42 family run (JSONL instance). C1 TFLite is converted from that Keras file. Invoke smoke on DEVELOPMENT index 0: load/allocate/invoke PASS, finite, shape `[1,3]` float32, max abs diff vs Keras `2.79e-08`.

Candidate B FP32 TFLite: **SKIPPED** (`B_NOT_COMPETITIVE`). INT8 not performed. Production selector not changed.

## 9. Limitations

- PUBLIC_SDT DEVELOPMENT offline prototype only
- No device, Pi, MI48, or clinical claim
- `LOCKED_PUBLIC_TEST` unused
- Thermal-IM not used
- No post-result architecture expansion

Compact metrics: `config/thermal/tv2_b_c1_matched_result.json`.
