# SafeNest Thermal V2 — TV2-A0 Candidate Architecture Hypothesis Deep Review

- Document ID: `THERMAL_V2_TV2_A0_ARCHITECTURE_HYPOTHESIS_REVIEW_01`
- Date: `2026-08-30`
- Worker: Architecture Grok (Grok 4.5 High)
- Repository: `sheepmeat/test`
- Base: `origin/main` at `925eec664ace68bb2d4b50557b7cbf809314833d`
- Branch: `thermal-v2/tv2-a0-architecture-hypothesis-review`
- Scope: architecture / experiment-design review only
- Training: `FORBIDDEN`
- Model artifacts: `NOT_CREATED`
- Master execution map: `NOT_MODIFIED`
- Gate recommendation: `PASS_WITH_LIMITATIONS`

---

## 1. Executive Conclusion

Enough merged-main architecture evidence exists for the Thermal Control Tower to
freeze a **Candidate A direction** after G1 contract review, and to treat a
scientifically distinct **Candidate B** as justified rather than optional
fashion.

**Current model to beat / complement** is the B6R-P1/P2 public-SDT pooled MLP,
not the historical T-B SMALL_CNN:

```text
PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1
thermal_public_sdt_pooled_mlp_fp32_tflite_v1
62×80×1 → adaptive mean pool 8×10 (80 features) → Dense(32, ReLU) → Dense(3)
parameters = 2691
DEVELOPMENT accuracy ≈ 0.907
DEVELOPMENT macro F1 ≈ 0.901
NORMAL → FALL_PROXY = 174 / 4000 ≈ 4.35%
LOCKED_PUBLIC_TEST access = 0
```

These DEVELOPMENT numbers are **diagnostics**, not scientific final performance.

**Historical architecture findings (reconstructed, not invented):**

| ID | Regime | Params | Role |
|---|---|---:|---|
| `SMALL_CNN_BASELINE_V1` | T-B1/T-B2 (T-A6 + P1 z-score) | 312,131 | Controlled spatial-CNN winner vs depthwise |
| `DEPTHWISE_SEPARABLE_CNN_V1` | T-B2 (same protocol as SMALL_CNN) | 347 | Lost; extreme under-capacity + GAP-only head |
| `PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1` | B6R-P0–P4 public SDT | 2,691 | Current Team baseline identity for V2 comparison |

**Comparability finding:** T-B metrics and B6R-P metrics are
`NOT_DIRECTLY_COMPARABLE`. Do not argue that SMALL_CNN “beat” the pooled MLP
because VALIDATION F1 was ~0.995 versus DEVELOPMENT F1 ~0.901.

**Primary architecture problem under investigation (hypothesis, not fact):**
aggressive adaptive mean pooling to 8×10 may discard local/contour structure
needed to separate low-body normal postures from lying/fall-proxy, leaving only
coarse regional averages for an MLP.

**Candidate A recommendation:** `A_RECOMMEND_REVISED_SMALL_CNN`

Keep the historically evidenced two-stage conventional Conv→Pool stack that won
T-B2, but **do not freeze the exact 312,131-parameter Flatten head**. Replace
Flatten with a compact spatial-summary head (GAP or light adaptive spatial
retain) so Candidate A tests spatial inductive bias on the **current public-SDT
regime** without inheriting an oversized absolute-layout head.

**Candidate B recommendation:** `B_JUSTIFIED`

Most scientifically distinct family: **capacity-matched depthwise-separable CNN**.
Do **not** rerun the historical 347-parameter depthwise model. That loss is best
read as under-capacity / representation-bottleneck evidence, not a closed
negative result against the depthwise family.

**TV2-A0 gate:** `PASS_WITH_LIMITATIONS`

Pass substance: architecture shortlist, A/B recommendations, and fair-comparison
rules are Control-Tower-reviewable. Limitations: no Candidate has been retrained
on the public-SDT contract; G1/GEO/PRE/SPLIT/LABEL and TV2-D0/H0 are parallel and
not Control-Tower-approved truth in this review; float prototype quality remains
first — no training is authorized by this document.

---

## 2. Evidence Reviewed

### 2.1 Merged-main primary evidence

| Area | Paths |
|---|---|
| Control-Tower map | `docs/thermal/20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md` |
| B6R index | `docs/thermal/B6R_DEVELOPMENT_INDEX.md` |
| SMALL_CNN executable | `datasets/thermal/t_b1_model.py` |
| Depthwise executable | `datasets/thermal/t_b2_model.py` |
| T-B0 protocol | `datasets/thermal/manifests/T-B0_offline_model_protocol/` |
| T-B1 winner | `datasets/thermal/manifests/T-B1_full_experiment/` |
| T-B2 comparison | `datasets/thermal/manifests/T-B2_architecture_comparison/validation_architecture_comparison.json` |
| T-B2 report | `docs/reports/20260814_Codex_T-B2_Architecture_Comparison_01.md` |
| T-B1 report | `docs/reports/20260814_Codex_T-B1_Full_Experiment_01.md` |
| B6R-P1 contract | `config/thermal/b6r_p1_public_sdt_training_contract.json` |
| B6R-P1 metadata | `models/thermal/public_sdt/public_sdt_pooled_mlp_v1.json` |
| B6R-P4 clean CM | `datasets/thermal/manifests/B6R-P4_public_sdt_software_robustness_failure_mode/clean_baseline_metrics.json` |
| B6R-P2 / P4 reports | `docs/reports/20260826_Codex_Thermal_B6R_P2_*`, `docs/reports/20260828_Codex_Thermal_B6R_B6R-P4_*` |

### 2.2 Baseline claim verification

From `models/thermal/public_sdt/public_sdt_pooled_mlp_v1.json` and
`datasets/thermal/manifests/B6R-P4_public_sdt_software_robustness_failure_mode/clean_baseline_metrics.json`:

| Claim | Verified value | Status |
|---|---|---|
| Architecture | adaptive mean pool 8×10 → Dense 32 → Dense 3 | CONFIRMED |
| Parameters | 2691 | CONFIRMED |
| Classes | NOT_HUMAN / HUMAN_NORMAL / HUMAN_FALL_PROXY | CONFIRMED |
| DEVELOPMENT accuracy | 0.907 | CONFIRMED |
| DEVELOPMENT macro F1 | 0.901326741104394 | CONFIRMED |
| Confusion row NORMAL | `[129, 3697, 174]` | CONFIRMED |
| NORMAL→FALL_PROXY | 174/4000 = 4.35% | CONFIRMED |
| Locked-test metrics | not computed; access 0 | CONFIRMED |

### 2.3 Parallel work inspected as `UNVERIFIED_PARALLEL_WORK`

Local branches present at review time (not Control-Tower truth):

| Branch | Tip file | Status for this review |
|---|---|---|
| `thermal-v2/g1-contract-foundation` | G1 GEO/PRE/SPLIT/LABEL proposal | `PARALLEL_UNVERIFIED` |
| `thermal-v2/tv2-h0-sdt-hard-negative-audit` | SDT hard-negative audit | `PARALLEL_UNVERIFIED` |
| `thermal-v2/tv2-d0-dataset-discovery` | dataset discovery | `PARALLEL_UNVERIFIED` |

These were inspected only to avoid duplicating their scopes. Architecture
conclusions below are grounded in **merged main** evidence.

### 2.4 Explicit non-evidence

- No new training, TFLite export, quantization, or inference benchmark.
- No LOCKED_PUBLIC_TEST access.
- No Team / Integration / Pi runtime changes.
- Default runtime entry in `models/model_manifest.json` remains legacy
  `thermal_fall_int8` and is **not** reinterpreted as the V2 comparison baseline.
  V2 comparison baseline identity follows the Master Execution Map §4.2
  (B6R-P2 public SDT pooled MLP).

---

## 3. Historical Architecture Reconstruction

### 3.1 `SMALL_CNN_BASELINE_V1`

**Executable structure** (`datasets/thermal/t_b1_model.py`):

```text
Input 62×80×1
→ Conv2D 16, 3×3, ReLU, same
→ MaxPool 2×2                 → ~31×40×16
→ Conv2D 32, 3×3, ReLU, same
→ MaxPool 2×2                 → ~15×20×32
→ Flatten                     → 9600
→ Dense 32, ReLU
→ Dense 3, softmax
```

| Field | Evidence |
|---|---|
| Parameter count | **312,131** (contract `EXPECTED_PARAMETER_COUNT`) |
| Fingerprint | `937fceb88900a779d67a8e407cebc3362cc21346721f92cea5ae8de1413aba2a` |
| Input geometry | `[1,62,80,1]` float32 |
| Preprocessing (winner) | `P1_TRAIN_FITTED_GLOBAL_ZSCORE` (TRAIN-fit mean/std only) |
| Dataset | T-A6 canonical roles: TRAIN 32k / VAL 8k / REAL_EVAL_DEV 8k |
| Labels | NOT_HUMAN / HUMAN_NORMAL / HUMAN_FALL (lying posture proxy) |
| Optimizer / loss | Adam lr 0.001; unweighted sparse categorical CE |
| Class weight / aug / focal | DISABLED |
| Seeds | primary 20260813; T-B3 also 20260814, 20260815 |
| VAL metrics | acc 0.995125; macro F1 **0.99513**; NORMAL→FALL **22/4000 (0.55%)** |
| REAL_EVAL_DEV | macro F1 **0.5939**; acc 0.67825; FALL recall 0.446 (diagnostic) |
| Locked test | none in T-B lineage |
| TFLite / INT8 | T-B4/T-B5 FULL_INT8 selected historically (~318 KB external); not re-validated here |
| Known failures | near-duplicates TRAIN↔VAL; large synthetic→real gap; subject generalization `NOT_VERIFIABLE` |

**Spatial behavior relevant to posture:** local 3×3 filters before aggressive
pooling can respond to limb/contour fragments; two-stage pooling still retains a
15×20×32 map before Flatten — much richer than an 8×10 mean grid. The Flatten
head, however, allocates the vast majority of parameters to absolute spatial
positions, which can memorize layout rather than posture geometry.

### 3.2 `DEPTHWISE_SEPARABLE_CNN_V1`

**Executable structure** (`datasets/thermal/t_b2_model.py`):

```text
Input 62×80×1
→ Conv2D 8, 3×3, ReLU, same
→ MaxPool 2×2
→ SeparableConv2D 16, 3×3, ReLU, same, depth_multiplier=1
→ MaxPool 2×2
→ GlobalAveragePooling2D      → 16 features
→ Dense 3, softmax
```

| Field | Evidence |
|---|---|
| Parameter count | **347** (bound ≤ 30,000) |
| Fingerprint | `3057cc8ba5272315d5bc6a0716f756e54767685d5cb3f4a7935e8862f31478d3` |
| Protocol | Identical to SMALL_CNN T-B budget (architecture factor only) |
| VAL metrics | acc 0.922375; macro F1 **0.92123**; FALL recall **0.842** |
| NORMAL→FALL | **181/4000 ≈ 4.53%** |
| Confusion | `[[1893,105,2],[17,3802,181],[2,314,1684]]` |
| REAL / INT8 | not evaluated for loser |
| Outcome | lost to SMALL_CNN under `THERMAL_T_B0_WINNER_RULE_001` |

**Why it likely failed (evidence-tied, not generic):**

1. **Extreme under-capacity:** 347 vs 312,131 parameters (~99.9% reduction).
2. **Representation bottleneck:** GAP collapses to **16** scalars before the
   classifier — far less than SMALL_CNN’s 9600 flattened units or even the
   pooled MLP’s 80 regional means.
3. **No intermediate Dense capacity** after GAP.
4. **Not a fair test of “depthwise as a family”** — only of this tiny instance.
5. Protocol/dataset/preprocess were matched to SMALL_CNN, so the loss is
   architectural/capacity within T-B, not a preprocessing confound.

### 3.3 `PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1` (B6R-P1/P2)

```text
(62,80,1) float32
→ adaptive mean pool → (8,10) = 80 features
→ Dense(80→32) + ReLU
→ Dense(32→3) + softmax
```

| Field | Evidence |
|---|---|
| Parameters | **2691** |
| Dataset | `PUBLIC_SDT_48000_THERMAL_ONLY_V1` |
| Preprocess | bilinear 480×640→62×80 + per-frame min-max |
| Labels | NOT_HUMAN / HUMAN_NORMAL / HUMAN_FALL_PROXY |
| Split | TRAIN 32k / DEVELOPMENT 8k / LOCKED_PUBLIC_TEST 8k (access 0) |
| Optimizer | deterministic minibatch SGD lr 0.05, L2 1e-4, batch 512, seed 42 |
| DEVELOPMENT | acc 0.907; macro F1 0.90133 |
| CM | `[[1907,93,0],[129,3697,174],[115,233,1652]]` |
| FALL_PROXY recall | 0.826 |
| TFLite FP32 | 70,592 B (`thermal_public_sdt_pooled_mlp_fp32_tflite_v1`) |
| INT8 | not produced for this architecture |
| Pi | B6R-P3 `BLOCKED_HARDWARE` |
| Failure pattern (P4 software) | sensitive to ~10% rectangle occlusion and spatial shifts |

### 3.4 Additional meaningful Thermal model evidence (non-candidates)

| ID | Role | Architecture note |
|---|---|---|
| Legacy `thermal_fall_int8` | Default runtime manifest entry | Ops family resembles SMALL_CNN; training provenance unverified for V2 scientific comparison |
| Historical `thermal_train.py` CNN | Script lineage | Same conv skeleton + Dropout(0.3); **not** frozen T-B architecture |
| T-B4/T-B5 FULL_INT8 of SMALL_CNN | Offline lock lineage | External artifact; Pi latency not validated |

No other trained Thermal architecture with an executable layer contract was found
on main beyond the three primary reconstructions above.

---

## 4. Comparability Matrix

| Pair | Classification | Reason |
|---|---|---|
| SMALL_CNN vs DEPTHWISE (T-B2) | **DIRECTLY_COMPARABLE** | Same T-A6 data, P1 preprocess, labels, Adam/CE budget, seed, VAL selection rule; architecture alone varied |
| SMALL_CNN P1 vs P0/P2 preprocess (T-B1) | **DIRECTLY_COMPARABLE** within T-B1 | Architecture fixed; preprocess factor varied |
| SMALL_CNN multiseed (T-B3) | **DIRECTLY_COMPARABLE** within T-B3 | Architecture/preprocess fixed; seed varied |
| SMALL_CNN VAL vs SMALL_CNN REAL_EVAL_DEV | **PARTIALLY_COMPARABLE** | Same model/preprocess; REAL role is diagnostic, near-duplicates differ, not locked test |
| SMALL_CNN vs PUBLIC_SDT pooled MLP | **NOT_DIRECTLY_COMPARABLE** | Different dataset packaging, preprocess (z-score vs bilinear+minmax), label name (`HUMAN_FALL` vs `HUMAN_FALL_PROXY`), trainer (Adam/TF vs NumPy SGD), selection split naming, and selection metric |
| DEPTHWISE vs pooled MLP | **NOT_DIRECTLY_COMPARABLE** | Same reasons as above |
| Pooled MLP P1 NumPy vs P2 FP32 TFLite | **DIRECTLY_COMPARABLE** (parity lineage) | Same weights/preprocess/split; export parity was the P2 question |
| Pooled MLP clean vs P4 synthetic stresses | **PARTIALLY_COMPARABLE** | Same model/DEVELOPMENT set; stresses are software diagnostics, not new architectures |
| Legacy INT8 vs any above | **NOT_DIRECTLY_COMPARABLE** | Unverified training provenance / different claim boundary |

**Rule for future prose:** never write “Model X F1 0.90 therefore better than
Model Y F1 0.59” across `NOT_DIRECTLY_COMPARABLE` cells.

---

## 5. Current Pooled-MLP Representation Analysis

### 5.1 What the 8×10 adaptive mean pool preserves

Adaptive mean pooling with integer linspace boundaries partitions the 62×80
frame into an 8×10 grid of rectangular bins and replaces each bin by its mean.
Approximate bin size is on the order of ~7–8 rows by 8 columns (edges vary by
linspace). This retains:

- **Coarse vertical mass distribution** (upper vs lower thirds as groups of
  rows of bins)
- **Coarse horizontal laterality** (left/center/right groups of columns)
- **Multi-region presence** (which bins are warm relative to others after
  per-frame min-max)
- **Very low-frequency posture silhouette energy**

Relative thermal gradients survive only as **differences between bin means**,
not as within-bin structure.

### 5.2 What is likely discarded (hypothesis)

Within each ~8×8-ish bin, the following are destroyed by averaging:

- **Local limb structure** (arms, legs as thin warm ridges)
- **Body contour / edge geometry**
- **Localized head vs torso peaks** inside a bin
- **Small body structures** and partial-occupancy patterns
- **High-frequency thermal gradients** (boundary sharpness between body and
  floor/background)
- **Fine multi-part geometry** that distinguishes kneeling/crouching/bending
  from fully reclined lying when both occupy similar lower-frame mass

### 5.3 Implication for NORMAL→FALL_PROXY

The practical error is HUMAN_NORMAL → HUMAN_FALL_PROXY at 174/4000 on
DEVELOPMENT. Public SDT maps SITTING+STANDING→NORMAL and LYING→FALL_PROXY.
Sitting and lying can share **lower-frame thermal mass** after coarse pooling,
especially under per-frame min-max that equalizes contrast. An MLP on 80 bin
means can still separate many standing vs lying cases via vertical distribution,
but is structurally weak when:

- the person is low in the frame (crouch/kneel/sit-low),
- the silhouette is elongated horizontally,
- occlusion or shift moves mass across bin boundaries (P4 stress sensitivity).

This does **not** prove the pool is the cause of the 174 errors. It establishes
a **testable representation hypothesis** for Candidate A/B: preserve learnable
local spatial filters before any global summary.

---

## 6. Failure-Mode Architecture Requirements

Candidate architectures should be assessed primarily for features that may
separate:

```text
standing / sitting / walking / bending / crouching / kneeling /
reclining-but-normal / near-floor normal
    vs
lying / fall-proxy posture
```

Required representational properties:

1. **Vertical structure sensitivity** without requiring hand-crafted features.
2. **Local contour / part cues** before global collapse.
3. **Robustness to absolute position shifts** (avoid Flatten memorization).
4. **Enough channel capacity** to avoid the 347-param collapse failure mode.
5. **Stable FALL_PROXY recall** while reducing NORMAL→FALL_PROXY — not accuracy
   alone.
6. **TFLite-simple ops** for eventual edge use (float quality first).

Non-goals for architecture selection:

- Minimizing parameters toward 2,691 by default.
- Maximizing VALIDATION accuracy on near-duplicate-heavy historical T-B VAL.
- Exotic operators, transformers, or large pretrained backbones without a
  SafeNest-specific justification.

---

## 7. Architecture Family Review

### Family 1 — Historical / revised compact conventional CNN

| Axis | Assessment |
|---|---|
| Spatial behavior | Local 3×3 filters + staged pooling preserve posture-relevant structure the pooled MLP never computes |
| Capacity | Historical 312k is Flatten-dominated; revised GAP form ~5–25k is a more honest capacity for this task |
| TFLite / INT8 | Conv2D, MaxPool, Dense, ReLU are `LIKELY_SAFE`; historical INT8 lineage exists for the Flatten form |
| Overfitting risk | Flatten form high (absolute layout); GAP form lower |
| Dataset-size suitability | Good for ~32k TRAIN; GAP preferred if hard-negatives remain scarce |
| Hard-negative suitability | Strong — local filters can use hard low-posture normals if TV2-H0/D0 supply them |
| Implementation complexity | Low |
| Scientific distinctness vs baseline | High (spatial CNN vs pooled MLP) |
| Historical overlap | Direct SafeNest evidence in T-B1/T-B2 |

**Verdict:** strongest empirical SafeNest anchor. Prefer **revised** form for V2.

### Family 2 — Capacity-matched depthwise-separable CNN

| Axis | Assessment |
|---|---|
| Spatial behavior | Depthwise spatial filtering + pointwise channel mixing; can retain local structure if channels and head are adequate |
| Capacity | Target ~5–50k, **not** 347 |
| TFLite / INT8 | DepthwiseConv / SeparableConv generally `LIKELY_SAFE_WITH_VERIFICATION` |
| Overfitting risk | Moderate if capacity-matched; lower than Flatten CNN |
| Dataset-size suitability | Good |
| Hard-negative suitability | Good if capacity adequate |
| Implementation complexity | Low–moderate |
| Scientific distinctness | High vs both pooled MLP and revised conventional CNN |
| Historical overlap | Tiny depthwise already tested and lost; **capacity-matched** variant not tested |

**Verdict:** best Candidate B family — answers a concrete SafeNest open question.

### Family 3 — Small residual CNN

| Axis | Assessment |
|---|---|
| Spatial behavior | Residual paths help train slightly deeper local filters; may help multi-scale posture cues |
| Capacity | ~20–50k for a tiny ResNet-style stem |
| TFLite / INT8 | Add + Conv usually `LIKELY_SAFE_WITH_VERIFICATION` |
| Overfitting risk | Moderate; depth helps only if data diversity exists |
| Hard-negative suitability | Plausible but not uniquely motivated by SafeNest false-fall evidence |
| Scientific distinctness | Moderate |
| Historical overlap | **Not tested** in SafeNest Thermal |

**Verdict:** `PLAUSIBLE` reserve; weaker priority than Families 1–2 for first A/B.

### Family 4 — Multi-scale compact spatial CNN

| Axis | Assessment |
|---|---|
| Spatial behavior | Explicit short/long receptive fields may help standing height vs lying extent |
| Capacity | ~5–30k |
| TFLite | Usually safe if built from Conv/Pool/Concat/Dense |
| Overfitting / complexity | Higher design surface; harder to attribute gains |
| Scientific distinctness | High, but more speculative for this proxy task |
| Historical overlap | Not tested |

**Verdict:** interesting optional third experiment after A/B, not required for
TV2-A0 freeze.

### Optional families (architecture vs training)

| Idea | Type | TV2-A0 stance |
|---|---|---|
| Global average pooling CNN | Architecture (part of revised A) | Include as head choice inside A |
| Spatial pyramid | Architecture | Optional later; increases complexity |
| Coordinate channels | Architecture/features | Defer; interacts with GEO contract |
| Dual-branch | Architecture | Overlap with multi-scale; defer |
| Ordinal posture auxiliary | Loss/task | **Training hypothesis** — separate from A/B architecture factor |
| Metric-learning head | Loss/task | Separate |
| Focal loss / class weights | Loss | Separate; do not bundle into first A/B architecture comparison |
| Hard-negative oversampling | Data/training | Separate factor (TV2-H0/D0 → later corrective stage) |

---

## 8. Edge / TFLite / INT8 Assessment

Philosophy: **float prototype quality first**. Parameter counts in the 10k–100k
regime can be reasonable if spatial information is preserved. Exact Raspberry Pi
latency: `UNKNOWN_UNTIL_MEASURED` (B6R-P3 blocked).

| Candidate concept | Approx params | Major ops | TFLite float | INT8 outlook |
|---|---:|---|---|---|
| Current pooled MLP | 2,691 | MeanPool, Dense, ReLU, Softmax | Proven FP32 export | Not yet produced; Dense-only should be tractable |
| Revised SMALL_CNN (GAP) | ~5–25k | Conv, MaxPool, GAP, Dense | `LIKELY_SAFE` | `LIKELY_SAFE_WITH_VERIFICATION` |
| Exact historical SMALL_CNN (Flatten) | 312,131 | Conv, MaxPool, Flatten, Dense | Historically converted | Historical FULL_INT8 exists externally; large activation/Flatten cost |
| Capacity-matched depthwise | ~5–50k | Conv, SeparableConv, Pool, GAP, Dense | `LIKELY_SAFE_WITH_VERIFICATION` | Usually friendly if ReLU kept |
| Tiny residual | ~20–50k | Conv, Add, Pool, GAP | `LIKELY_SAFE_WITH_VERIFICATION` | Verify Add fusion |
| Multi-scale concat | ~5–30k | Conv, Concat, Pool | `LIKELY_SAFE_WITH_VERIFICATION` | Avoid exotic reductions |

Avoid for first candidates: transformers, large pretrained RGB backbones,
custom attention ops without TFLite proof, GPU-only kernels.

---

## 9. Experimental Identifiability Rules

A good Thermal V2 experiment changes **one meaningful factor at a time**.

### 9.1 Required factor isolation

```text
Stage ARCH (this review’s concern):
  same TRAIN / DEVELOPMENT contracts
  same preprocessing contract (G1 freeze)
  same label map
  same augmentation policy (initially none, unless separately frozen)
  same optimizer / stop policy / seed set
  → architecture differs (A vs baseline; B vs A)

Stage DATA-CORRECTIVE (later, after TV2-D0/H0 + G1):
  freeze winning or nominated architecture
  → vary hard-negative / data membership only

Stage LOSS (optional later):
  freeze architecture + data
  → vary class weight / focal / sampling
```

### 9.2 Forbidden first comparison

```text
Candidate B =
  new dataset + new preprocess + new architecture + new loss + new aug
```

Any win from that bundle is scientifically uninterpretable.

### 9.3 Architecture-data interactions (advisory only)

| Family | Likely interaction with hard-negatives | Scene-texture overfitting risk |
|---|---|---|
| Pooled MLP | Limited benefit if errors are spatial-structure failures | Lower (features already coarse) |
| Revised CNN (GAP) | High benefit if hard-negatives expose low-posture normals | Moderate |
| Flatten CNN | Can memorize layout of hard-negatives | High |
| Capacity-matched depthwise | High if capacity adequate | Moderate |
| Residual / multi-scale | Benefit depends on diversity; easier to overfit limited scenes | Moderate–high |

---

## 10. Serious Architecture Shortlist

Limited to four options.

### S1 — Revised compact conventional CNN (Candidate A direction)

- Rating: **STRONG**
- Why: inherits T-B2 spatial-CNN win; removes Flatten capacity trap; directly
  tests the pooled-MLP representation hypothesis on local filters; TFLite-simple.

### S2 — Capacity-matched depthwise-separable CNN (Candidate B direction)

- Rating: **STRONG** (as distinct second hypothesis)
- Why: SafeNest already has a failed tiny depthwise; capacity-matched retest is
  uniquely identifiable and edge-friendly.

### S3 — Exact historical `SMALL_CNN_BASELINE_V1` (312k Flatten)

- Rating: **PLAUSIBLE** as ablation / continuity check; **WEAK** as frozen A
- Why: historically strong on T-B VAL, but not run on public-SDT minmax regime;
  Flatten head is edge-heavy and leak-prone; REAL_EVAL gap warns against treating
  VAL saturation as posture competence.

### S4 — Tiny residual or multi-scale CNN

- Rating: **WEAK** for immediate A/B freeze; **PLAUSIBLE** reserve
- Why: scientifically interesting but no SafeNest Thermal history; higher design
  degrees of freedom; can wait until A/B float results exist.

### Rejected for first freeze

| Option | Rating | Why |
|---|---|---|
| Rerun exact 347-param depthwise | **REJECT** | Already lost; under-capacity confound unresolved if repeated |
| Transformer / large backbone | **REJECT** | No SafeNest evidence; edge/TFLite mismatch |
| “MLP but 2× wider” as Candidate B | **REJECT** | Not a distinct spatial hypothesis |
| Architecture+loss+data mega-bundle | **REJECT** | Non-identifiable |

---

## 11. Candidate A Recommendation

### Recommendation code

```text
A_RECOMMEND_REVISED_SMALL_CNN
```

### Why not exact reuse (`A_RECOMMEND_REUSE_SMALL_CNN`)

1. Exact SMALL_CNN has never been trained under
   `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1`.
2. 312k Flatten parameters are mostly absolute-layout Dense weights — poorly
   matched to shift-sensitive false-fall errors and edge constraints.
3. T-B VAL near-saturation + REAL gap means historical F1 is not a portable
   proof of posture competence on the current public regime.

### Why not fully new (`A_RECOMMEND_NEW_COMPACT_CNN`)

A clean-sheet network would discard the only SafeNest-controlled evidence that
conventional spatial CNN beats an alternative under matched protocol (T-B2).
Revision preserves that inductive-bias lineage while correcting the head.

### Why not `A_UNRESOLVED_PENDING_G1`

Architecture direction can be recommended now. Final freeze of exact tensors /
preprocess still waits on G1, but TV2-A0 can nominate the family.

### Provisional Candidate A specification (design proposal only)

```text
TV2_CANDIDATE_A_REVISED_SMALL_CNN_GAP_V1  (provisional name)

Input 62×80×1
→ Conv2D 16, 3×3, ReLU, same
→ MaxPool 2×2
→ Conv2D 32, 3×3, ReLU, same
→ MaxPool 2×2
→ GlobalAveragePooling2D          → 32
→ Dense 32, ReLU                  → 32
→ Dense 3, softmax

Approx trainable parameters: ~5,955
Major activations: 62×80×16, 31×40×16, 31×40×32, 15×20×32, then vectors
Approx MAC regime: low 10^6–10^7 per frame order (coarse); exact UNKNOWN_UNTIL_MEASURED
Ops: Conv2D, MaxPool, GAP, Dense, ReLU, Softmax
TFLite: LIKELY_SAFE
INT8: LIKELY_SAFE_WITH_VERIFICATION
```

**Optional A ablation (same family, still architecture-identifiable):** replace GAP
with adaptive average pool to 4×5 then Dense(32) (~25k params) if G1 review wants
more retained spatial layout than GAP. Treat as A-ablation, not Candidate B.

**Rationale tied to this task:** the Conv stack supplies the local structure the
8×10 mean pool erases; GAP prevents Flatten from turning Candidate A into a
layout memorizer while keeping parameters in a compact edge-plausible band.

---

## 12. Candidate B Recommendation

### Recommendation code

```text
B_JUSTIFIED
```

### Distinct family

```text
CAPACITY_MATCHED_DEPTHWISE_SEPARABLE_CNN
```

### Why justified

1. Tests a **different inductive bias** from revised conventional CNN
   (factorized spatial/channel mixing).
2. Directly resolves the SafeNest-specific ambiguity left by T-B2: was depthwise
   weak, or was **347 params + 16-D GAP** weak?
3. Remains compact and TFLite-oriented.
4. Is not “Candidate A + extra Dense” or “Candidate A + seed 43”.

### Why not the historical depthwise

Repeating `DEPTHWISE_SEPARABLE_CNN_V1` would reconfirm under-capacity, not the
family hypothesis.

### Provisional Candidate B specification (design proposal only)

```text
TV2_CANDIDATE_B_CAP_DEPTHWISE_V1  (provisional name)

Input 62×80×1
→ Conv2D 16, 3×3, ReLU, same
→ MaxPool 2×2
→ SeparableConv2D 32, 3×3, ReLU, same, depth_multiplier=1
→ MaxPool 2×2
→ SeparableConv2D 48, 3×3, ReLU, same, depth_multiplier=1
→ GlobalAveragePooling2D          → 48
→ Dense 32, ReLU
→ Dense 3, softmax

Approx trainable parameters: ~4,435
Ops: Conv2D, SeparableConv2D, MaxPool, GAP, Dense, ReLU, Softmax
TFLite: LIKELY_SAFE_WITH_VERIFICATION
INT8: LIKELY_SAFE_WITH_VERIFICATION
```

Capacity is intentionally near Candidate A’s revised scale (same order of
magnitude), not near 347.

---

## 13. Proposed Future Architecture Specs

### 13.1 Baseline (reference, already trained — do not retrain for A0)

```text
PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1
62×80×1 → AdaptiveAvgPool 8×10 → Flatten 80 → Dense32 ReLU → Dense3
params ≈ 2691
```

### 13.2 Candidate A provisional

See §11 (`TV2_CANDIDATE_A_REVISED_SMALL_CNN_GAP_V1`, ~5955 params).

### 13.3 Candidate B provisional

See §12 (`TV2_CANDIDATE_B_CAP_DEPTHWISE_V1`, ~4435 params).

### 13.4 Continuity ablation (optional, not B)

```text
SMALL_CNN_BASELINE_V1 exact Flatten form
params = 312131
Use only if Control Tower wants a continuity bridge to T-B5 INT8 lineage.
Not recommended as primary A.
```

### 13.5 Reserve (not required for G2/G3)

Tiny residual (~24k) or dual-branch multi-scale (~7k) only after A/B float
results fail to explain NORMAL→FALL_PROXY.

---

## 14. Future Fair-Comparison Protocol

Draft policy for post-G1 offline comparison (not executed here):

1. **Shared data:** same canonical TRAIN and DEVELOPMENT membership after G1/D3.
2. **Shared preprocess:** one frozen PRE contract for A and B unless a pre-registered
   preprocess factor experiment says otherwise.
3. **Shared labels:** same 3-class proxy map and class order.
4. **Shared augmentation:** default none for architecture bake-off.
5. **Shared optimization policy:** one optimizer/schedule/early-stop rule for A and B
   (do not reuse T-B Adam vs B6R SGD casually without freezing one).
6. **Shared seeds:** fixed seed set (recommend ≥3 for confirmation after first float).
7. **Single factor:** architecture ID differs.
8. **Baseline compare:** evaluate the frozen B6R-P2 FP32 TFLite or equivalent
   pooled-MLP under the same DEVELOPMENT protocol as a reference comparator,
   documenting any unavoidable trainer mismatch as a limitation.
9. **Data-corrective stage later:** freeze architecture, vary hard-negatives.
10. **LOCKED_PUBLIC_TEST:** remains closed through architecture selection.

### Metrics that must be preserved

- macro F1
- per-class precision / recall / F1
- full confusion matrix
- **NORMAL → FALL_PROXY count and rate**
- FALL_PROXY → NORMAL
- NOT_HUMAN → FALL_PROXY

### Selection rule recommendation (threshold not frozen)

Architecture experiments should include an **explicit NORMAL→FALL_PROXY term** in
the development selection / reporting rule (for example: primary macro F1 with a
reported constraint or secondary rank on NORMAL→FALL_PROXY), so a model cannot
“win” solely by boosting overall accuracy while inflating false falls. Exact
numeric threshold: **not chosen here**.

### Loss / training strategy (separate from architecture)

| Strategy | Evidence basis | TV2 stance |
|---|---|---|
| Categorical / sparse CE | Used in T-B and B6R-P | Default for architecture bake-off |
| Class weighting | Not shown to fix false-fall in SafeNest Thermal | Optional later factor; not part of A definition |
| Focal loss | No SafeNest Thermal evidence it fixes NORMAL→FALL | Speculation only; do not bundle into A/B |
| Hard-negative oversampling / balanced batches | Motivated by false-fall problem + pending H0/D0 | **Data/training** stage after architecture factor |

Primary problem is not simple class imbalance (DEVELOPMENT supports are balanced
at 2000/4000/2000 in public SDT). Do not assume focal loss solves false fall.

### Preprocessing interaction (defer authority to PRE/G1)

| Preprocess | CNN interaction note |
|---|---|
| Per-frame min-max (current B6R) | Equalizes contrast; may amplify background clutter for local filters |
| Global TRAIN z-score (historical P1) | Preserves absolute temperature scale; won T-B1 historically |
| Aspect-preserving resize vs direct stretch | Affects body geometry; GEO/PRE own this — architectures should consume the frozen tensor contract |

Architectures above assume final input remains `[1,62,80,1]`.

---

## 15. Unknowns / Limitations

1. No Candidate A/B has been trained on public SDT under matched protocol.
2. T-B and B6R-P regimes remain `NOT_DIRECTLY_COMPARABLE`.
3. Subject/session isolation is not claimed for public SDT; leakage risk exists.
4. TV2-D0 / TV2-H0 / G1 outputs were parallel and `PARALLEL_UNVERIFIED` here.
5. Exact Pi latency / INT8 accuracy for revised A or capacity-matched B:
   `UNKNOWN_UNTIL_MEASURED`.
6. HARD_NEGATIVE membership for NORMAL→FALL_PROXY rows is not reconstructed in
   this architecture document (owned by TV2-H0).
7. Legacy runtime INT8 is not used as a scientific comparator.
8. This review does not authorize training, export, Team import, or final model
   selection.

---

## 16. TV2-A0 Gate Recommendation

```text
TV2-A0 = PASS_WITH_LIMITATIONS
```

### Pass substance

- Historical architectures reconstructed from executable contracts and manifests.
- Baseline pooled-MLP claims verified from P1/P4 artifacts.
- Comparability matrix explicit.
- Representation hypothesis for 8×10 pooling stated as hypothesis, not fact.
- Serious shortlist reduced to actionable options.
- Candidate A: `A_RECOMMEND_REVISED_SMALL_CNN` with provisional spec.
- Candidate B: `B_JUSTIFIED` as capacity-matched depthwise-separable CNN.
- Fair-comparison and false-fall metric rules drafted.
- Enough for Control Tower to freeze Candidate A direction and decide B after
  G1 evidence review.

### Limitations (why not unconditional PASS)

- Architecture freeze still depends on G1 data/model contracts.
- No float training evidence yet on the public-SDT comparison regime.
- Parallel D0/H0 conclusions are not absorbed as approved truth.
- Exact A/B tensor specs remain provisional until Control Tower freeze (G2/G3).

### Explicit exclusions

```text
NO TRAINING
NO DATASET MODIFICATION
NO LOCKED TEST ACCESS
NO TEAM REPO CHANGE
NO INTEGRATION CHANGE
NO MODEL ARTIFACT
NO EXECUTION MAP UPDATE
NO FINAL MODEL SELECTION
NO PRODUCTION READINESS CLAIM
```

---

## Appendix A — Branch isolation record

```text
Branch: thermal-v2/tv2-a0-architecture-hypothesis-review
Base:   origin/main = 925eec664ace68bb2d4b50557b7cbf809314833d
Master map on base: PRESENT
UNRELATED_COMMITS (pre-change): 0
UNRELATED_FILES (pre-change): 0
Changed intended path: docs/thermal/20260830_SafeNest_Thermal_V2_TV2-A0_Architecture_Hypothesis_Review_01.md
```

## Appendix B — Key numeric anchors

| Source | Anchor |
|---|---|
| P4 clean CM | `[[1907,93,0],[129,3697,174],[115,233,1652]]` |
| P1/P4 macro F1 | 0.901326741104394 |
| T-B2 SMALL_CNN VAL F1 | 0.9951295332536425 |
| T-B2 DEPTHWISE VAL F1 | 0.9212330380736017 |
| T-B1 REAL_EVAL_DEV F1 | 0.593926523563344 |
| SMALL_CNN params | 312131 |
| DEPTHWISE params | 347 |
| Pooled MLP params | 2691 |
