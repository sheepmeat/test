# SafeNest Thermal V2 Candidate A — Phase 2 Execution Report

- Date: 2026-08-31
- Repository: `sheepmeat/test`
- Execution worktree: `/tmp/safenest-tv2-d3-expansion-training-contract`
- GPU work root: `/home/junwoo/tv2ca-work-gpu` (work-root-relative below: `WORK_GPU`)
- CPU predecessor work root (preserved, not mixed into GPU selection): `/home/junwoo/tv2ca-work`
- Training authorization: owner-authorized prototype Phase 2 only
- `LOCKED_PUBLIC_TEST`: not opened, not materialized, not scored
- Nominated prototype: A0 (seed 42 artifact)
- Delivery branch: `thermal-v2/candidate-a-phase2-results`

## 1. Repository Base SHA

```text
HEAD / origin/main = 80b70d564677d3e36939b89b00fa2ef5bfd59497
80b70d5 feat(thermal): implement Thermal V2 Candidate A data-corrective prototype (#194)
```

## 2. Repository Freshness

```text
branch: main...origin/main
git status --short: empty at execution start
working tree used for training: clean at 80b70d5
```

Training completed against a clean `80b70d5` worktree. This report, the compact result JSON, the nominated A0 Keras/TFLite pair, and a small runner skip/export fix are the intended Git delivery.

## 3. Environment

| Item | Value |
|---|---|
| Python | 3.12.3 |
| NumPy | 2.5.2 |
| TensorFlow | 2.21.0 |
| GPU visible | yes (`/physical_device:GPU:0`) |
| GPU name | NVIDIA GeForce RTX 2060 SUPER |
| Compute | GPU (CUDA 12.9 pip wheels via `tensorflow[and-cuda]`, plus `LD_LIBRARY_PATH` in `WORK_GPU/gpu_env.sh`) |
| Platform | Linux 6.6.87.2-microsoft-standard-WSL2 x86_64 |
| Native work root | `/home/junwoo/tv2ca-work-gpu` |
| Native venv | `/home/junwoo/tv2ca-work/venv` |
| Native canonical | `/home/junwoo/tv2ca-data/canonical` |
| Native Thermal-IM | `/home/junwoo/tv2ca-work/thermal_im` (symlinked from GPU work root) |

CPU-only A0 (and a partial A1 10% run) exists under `/home/junwoo/tv2ca-work` and was **not** used for GPU selection, ratio choice, or nomination. After CUDA libraries were installed, A0/A1/A0R were re-run on GPU so all reported stages share one device.

Fixed training policy (unchanged): Adam `1e-3`, sparse categorical crossentropy, batch 256, max 30 epochs, early stopping `val_loss` patience 5, restore best weights, no class weighting, no augmentation, seeded shuffle, compute float32, cache float16.

## 4. SDT Source Identity

```text
PUBLIC_SDT T-A6 canonical
TRAIN/train_canonical.npy
  size 634880128
  sha256 749c847fc9ab50ea5eee8827f0d47b5ebaa48165732a382c59f8b96c565b9d93
TRAIN/train_provenance.jsonl
  size 77767837
  sha256 b4ec8228e35703bac3319ca218a69fdef43013ea44b23376da4929b274d24888
VALIDATION/validation_canonical.npy
  size 158720128
  sha256 5d16451702c1bccfa945d9188d9b29a26ce11c8b33bf7a0dfbb25bfa86d74610
VALIDATION/validation_provenance.jsonl
  size 19648546
  sha256 48ebd03ca6f8d738ad7048aa72d4c454fd821140aa887971c27c5b49c1d7ec63

TRAIN 32000: NOT_HUMAN 8000 / HUMAN_NORMAL 16000 / HUMAN_FALL_PROXY 8000
DEVELOPMENT 8000: NOT_HUMAN 2000 / HUMAN_NORMAL 4000 / HUMAN_FALL_PROXY 2000
LOCKED_PUBLIC_TEST: loader absent; not used
```

## 5. Thermal-IM Source Identity

```text
identity_status = VERIFIED_AGAINST_D1_ANCHORS
archives acquired = 50 / 50
total archive bytes on disk = 5536999794

D1 anchors (byte-exact):
20220613_7_split6.zip  15167944
  9f3a941629f6ec92c03e5434ca34a6562b17e55d87aebb0bed4660ac5ab735c4
20220613_9_split7.zip  13613265
  56cde94b5db00c1b95ad7db3fe42be213f77b769333b9e9145c14728442bce5b

Phase 1 pool (shared via symlink):
hard_negative_pool.npz
  sha256 4a4cec2df89a22f738061e382f487171b2b9e91b0a6e9e515a1491211d404650
admitted_frame_total 20994
hn_train_pool_frames 17322
hn_holdout_eval_frames 3672
4,000-frame gate: PASS
```

TRAIN groups: `20220613_10, 20220613_2, 20220613_6, 20220613_7, 20220613_8, 20220620_1`
HOLDOUT groups: `20220613_1, 20220613_4, 20220613_9`
Recording-group disjoint. Actor-disjointness not verifiable (`meta.csv` absent).

## 6. Common Representation

```text
RELATIVE_THERMAL_APPEARANCE_V1
unit: RELATIVE_DIMENSIONLESS_NOT_CELSIUS
input: [62, 80, 1]
output range: [0, 1]
lane: R_RELATIVE_APPEARANCE_PROTOTYPE_LANE
```

PUBLIC_SDT: T-A6 Celsius canonical (G1 crop already applied) → per-frame relative operator.
Thermal-IM: intensity → TIM crop profile → same per-frame relative operator.
Not used: P1 global z-score, Celsius fabrication, raw concatenation.

## 7. Selected Normalization / Head / Parameters

Selection role: **PUBLIC_SDT DEVELOPMENT only**. Thermal-IM holdout was recorded and not used for selection.

| Run | N→F | rate | FALL recall | macro F1 | F→N | NH→F | params | epochs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MINMAX + GAP | 85 | 2.12% | 0.9840 | 0.9839 | 31 | 0 | 27651 | 30 |
| MINMAX + SPATIAL | 20 | 0.50% | 0.9925 | 0.9951 | 15 | 0 | 64387 | 30 |
| ROBUST + GAP | 95 | 2.38% | 0.9650 | 0.9761 | 70 | 0 | 27651 | 27 |
| **ROBUST + SPATIAL** | **8** | **0.20%** | **0.9890** | **0.9957** | 22 | 0 | **64387** | 24 |

```text
selected_normalization = FRAME_ROBUST_P2_P98_V1
selected_head          = COARSE_SPATIAL_RETAIN_FLATTEN_V1
parameter_count        = 64387
```

Loser variants are listed above; none were hidden.

## 8. Membership

```text
A0:
  32000 total
  NOT_HUMAN 8000 / HUMAN_NORMAL 16000 / HUMAN_FALL_PROXY 8000
  Thermal-IM HN = 0

A1 10%:
  33600 total
  NOT_HUMAN 8000 / HUMAN_NORMAL 17600 / HUMAN_FALL_PROXY 8000
  Thermal-IM HN = 1600 from HN_TRAIN_POOL only

A1 25% (ratio stage only; not selected):
  36000 total
  HUMAN_NORMAL 20000
  Thermal-IM HN = 4000

A0R 10% (final only; control):
  33600 total
  same class counts as A1 10%
  duplicated SDT HUMAN_NORMAL = 1600
  Thermal-IM frames = 0
```

## 9. Selected Ratio

Ratio-stage seed 42, PUBLIC_SDT DEVELOPMENT only, vs the selected A0:

| Arm | N→F | FALL recall | macro F1 |
|---|---:|---:|---:|
| A0 (repr seed 42) | 8 | 0.9890 | 0.9957 |
| A1 10% | 11 | 0.9900 | 0.9956 |
| A1 25% | 22 | 0.9975 | 0.9956 |

Neither A1 beat A0 on the primary metric. **10%** is the better A1 and is the extra-row count used in the planned final 9-run. No extra ratios were searched.

```text
selected_ratio = 0.10
seeds = 42, 7, 1337
```

## 10. Representation Results

Confusion matrices are `rows=true, cols=pred`, order `(NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY)`, DEVELOPMENT n=8000, support 2000/4000/2000.

```text
MINMAX+GAP     [[1999,1,0],[11,3904,85],[1,31,1968]]
MINMAX+SPATIAL [[2000,0,0],[4,3976,20],[0,15,1985]]
ROBUST+GAP     [[1995,5,0],[22,3883,95],[0,70,1930]]
ROBUST+SPATIAL [[2000,0,0],[4,3988,8],[0,22,1978]]
```

## 11. Ratio Results

```text
A1 10% N->F 11/4000 (0.27%) FALL recall 0.9900 macro F1 0.9956
A1 25% N->F 22/4000 (0.55%) FALL recall 0.9975 macro F1 0.9956
TIM-HN holdout (not used for selection): both A1 runs predicted HUMAN_NORMAL on all 3672 holdout frames
```

## 12. Final Results (9 runs)

Confusion matrices, DEVELOPMENT n=8000:

| Arm | Seed | N→F | F→N | NH→F | FALL rec | macro F1 | epochs | val_loss | CM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A0 | 42 | 16 | 19 | 0 | 0.9905 | 0.9950 | 19 | 0.01500 | `[[2000,0,0],[5,3979,16],[0,19,1981]]` |
| A0 | 7 | 14 | 17 | 0 | 0.9915 | 0.9947 | 30 | 0.01552 | `[[1995,5,0],[6,3980,14],[0,17,1983]]` |
| A0 | 1337 | 21 | 12 | 0 | 0.9940 | 0.9950 | 22 | 0.01304 | `[[1999,1,0],[6,3973,21],[0,12,1988]]` |
| A1 | 42 | 15 | 8 | 0 | 0.9960 | 0.9965 | 27 | 0.01208 | `[[2000,0,0],[5,3980,15],[0,8,1992]]` |
| A1 | 7 | 15 | 19 | 0 | 0.9905 | 0.9952 | 23 | 0.01479 | `[[2000,0,0],[4,3981,15],[0,19,1981]]` |
| A1 | 1337 | 23 | 13 | 0 | 0.9935 | 0.9945 | 19 | 0.01938 | `[[2000,0,0],[8,3969,23],[0,13,1987]]` |
| A0R | 42 | 5 | 33 | 0 | 0.9835 | 0.9949 | 25 | 0.01571 | `[[2000,0,0],[3,3992,5],[0,33,1967]]` |
| A0R | 7 | 13 | 13 | 0 | 0.9935 | 0.9961 | 29 | 0.01378 | `[[2000,0,0],[5,3982,13],[0,13,1987]]` |
| A0R | 1337 | 8 | 12 | 0 | 0.9940 | 0.9969 | 30 | 0.01148 | `[[2000,0,0],[5,3987,8],[0,12,1988]]` |

### Mean and spread (population SD)

| Arm | N→F mean | N→F SD | min–max | FALL rec mean | FALL rec SD | macro F1 mean |
|---|---:|---:|---|---:|---:|---:|
| A0 | 17.000 | 2.944 | 14–21 | 0.9920 | 0.0015 | 0.9949 |
| A1 | 17.667 | 3.771 | 15–23 | 0.9933 | 0.0022 | 0.9954 |
| A0R | 8.667 | 3.300 | 5–13 | 0.9903 | 0.0048 | 0.9960 |

C0 historical diagnostic anchor 174/4000 = 4.35% is a different representation/architecture. It is **not** a like-for-like baseline for these runs.

## 13. Thermal-IM Held-out HN (separate; not mixed into SDT macro F1)

Ground truth of this block is all `HUMAN_NORMAL`. Macro F1 is not computed.

| Arm | Seed | n | pred NORMAL | pred FALL | pred NOT_HUMAN | accept NORMAL | false FALL | NOT_HUMAN rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | 42 | 3672 | 1418 | 11 | 2243 | 38.6% | 0.3% | 61.1% |
| A0 | 7 | 3672 | 2143 | 0 | 1529 | 58.4% | 0.0% | 41.6% |
| A0 | 1337 | 3672 | 2142 | 0 | 1530 | 58.3% | 0.0% | 41.7% |
| A1 | 42/7/1337 | 3672 | 3672 | 0 | 0 | 100.0% | 0.0% | 0.0% |
| A0R | 42 | 3672 | 1415 | 266 | 1991 | 38.5% | 7.2% | 54.2% |
| A0R | 7 | 3672 | 1699 | 0 | 1973 | 46.3% | 0.0% | 53.7% |
| A0R | 1337 | 3672 | 1517 | 0 | 2155 | 41.3% | 0.0% | 58.7% |

A1 100% NORMAL acceptance on TIM holdout is expected after training on TIM seated frames. It is not SDT DEVELOPMENT evidence.

## 14. Interpretation

```text
A1 vs A0:
  A1 did not beat A0 on mean DEVELOPMENT HUMAN_NORMAL->HUMAN_FALL_PROXY
  (17.67 vs 17.00). Valid result. No extra ratio/seed/label search.

A1 vs A0R:
  A0R had lower mean N->F (8.67 vs 17.67). That pattern is consistent with
  class-prior shift rather than Thermal-IM content.
  A0R is a control arm and is not a nominated prototype.

FALL_PROXY recall did not collapse on A0 or A1 (means 0.992 / 0.993).
A0R seed 42 recall 0.9835 is a control-arm observation only.
```

## 15. Nominated Prototype

```text
Nominated Prototype: A0
artifact seed: 42 (predefined primary seed; not cherry-picked)
```

A0 is the SDT-only selected CNN under the frozen representation. Across three seeds A1 did not beat A0 on mean DEVELOPMENT NORMAL→FALL (17.67 vs 17.00), and A1 did not beat the A0R prior-shift control. FALL recall stayed healthy on A0 (mean 0.9920) and A1 (mean 0.9933). A0R is a control arm and is not nominable.

Under the relative thermal appearance prototype lane, the revised compact spatial CNN produced a strong offline SDT DEVELOPMENT result, while the tested Thermal-IM seated hard-negative addition did not demonstrate additional benefit.

## 16. Artifact Paths and SHA-256

Nominated FLOAT prototype (repository-relative):

| Path | bytes | SHA-256 |
|---|---:|---|
| `models/thermal/candidates/tv2_candidate_a/A0_hn000_FRAME_ROBUST_P2_P98_V1_COARSE_SPATIAL_RETAIN_FLATTEN_V1_seed42.keras` | 820623 | `6a8fd53c815bb29ac42b25fd45c0fe5e0cdad86e4caf359ae37a752d2e2e20ee` |
| `models/thermal/candidates/tv2_candidate_a/A0_hn000_FRAME_ROBUST_P2_P98_V1_COARSE_SPATIAL_RETAIN_FLATTEN_V1_seed42_fp32.tflite` | 264704 | `a158a70c4735e28eec70b5a996f82c91f452b94bcc24c040838143f4a55b1985` |

Input `[1,62,80,1]` float32. Output `[1,3]` float32. Classes `(NOT_HUMAN, HUMAN_NORMAL, HUMAN_FALL_PROXY)`. Parameters 64387.

The original 9-run A0 weights were not serialized (`--export-arm A1` only). The Keras file is a same-policy A0 seed-42 re-export; the runner skipped JSONL append so `candidate_a_results_final.jsonl` remains 9 rows. Re-export DEVELOPMENT: N→F 14/4000, FALL recall 0.9915, macro F1 0.9956. Nomination evidence remains the 3-seed JSONL family, not this re-export.

FP32 TFLite: EXPORTED. Invoke smoke on DEVELOPMENT index 0: finite output, shape `[1,3]`, max abs diff vs Keras `4.94e-15`. INT8: not performed. `models/model_manifest.json` was not changed.

Work-root result files (outside Git; filenames + SHA only):

| Path | SHA-256 |
|---|---|
| `candidate_a_results_representation.jsonl` | `0581136e12ccb37cf6357fc5cededf9d0bdbd35d27533f4abb7f5b541b19f196` |
| `candidate_a_results_ratio.jsonl` | `fe85507b5562624150549ec006559b2561e3a47fb348a9882186f4549a828500` |
| `candidate_a_results_final.jsonl` | `606c0d5e851600b72713d6199dc67208dbbd35c7b639275ecc44537fc4661382` |

A1 `.keras` files remain in the GPU work root only and are **not** nominated.

## 17. Limitations

- Prototype / public-SDT DEVELOPMENT only. No device-domain, Pi, or clinical claim.
- Thermal-IM is non-radiometric intensity; relative appearance is not Celsius.
- Actor-disjointness of Thermal-IM is not verifiable.
- Drive HTML listing freeze is 50 archives, not the full release.
- GPU vs a preserved CPU A0 predecessor: numbers differ; GPU path is the same-device contract after CUDA install.
- Nominated Keras is a seed-42 re-export; original 9-run in-memory weights were not saved.
- C0 4.35% is not like-for-like.
- `LOCKED_PUBLIC_TEST` unused.
- INT8 / Pi / team integration not performed.

## 18. Changed Files / Commit / PR

```text
Changed files (intended Git delivery):
  docs/thermal/20260830_SafeNest_Thermal_V2_Candidate_A_Phase2_Execution_Report_KO_01.md
  config/thermal/tv2_candidate_a_phase2_result.json
  models/thermal/candidates/tv2_candidate_a/artifact_identity.json
  models/thermal/candidates/tv2_candidate_a/A0_hn000_FRAME_ROBUST_P2_P98_V1_COARSE_SPATIAL_RETAIN_FLATTEN_V1_seed42.keras
  models/thermal/candidates/tv2_candidate_a/A0_hn000_FRAME_ROBUST_P2_P98_V1_COARSE_SPATIAL_RETAIN_FLATTEN_V1_seed42_fp32.tflite
  scripts/run_thermal_tv2_candidate_a.py
```

Compact metrics: `config/thermal/tv2_candidate_a_phase2_result.json`.
Runner change: skip already-recorded JSONL run IDs; allow missing-checkpoint export without duplicating rows.
