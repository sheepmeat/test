# SafeNest Thermal V2 — TV2-H0 SDT Hard-Negative / False-Fall Audit

**Date:** 2026-08-30
**Worker:** Luna 2
**Repository:** `sheepmeat/test`
**Base:** `origin/main` at `925eec664ace68bb2d4b50557b7cbf809314833d`
**Branch:** `thermal-v2/tv2-h0-sdt-hard-negative-audit`
**Training:** `FORBIDDEN`
**Gate:** `PASS_WITH_LIMITATIONS`

## Scope and protection boundary

This is an evidence audit of the current public SDT development evidence. It
does not retrain, fine-tune, export, select, or modify a model. It does not
modify any dataset, split, runtime, manifest, Team repository, Integration
repository, or the master execution map.

`LOCKED_PUBLIC_TEST` was not opened, sampled, visualized, predicted, or used
for metrics, selection, tuning, or hard-negative slicing. The current P1
model metadata records `test_access_count: 0` and
`test_metrics_computed: false`; the P1 access audit records zero array opens,
zero sample reads, and no selection/tuning use. The P4 audit independently
records the same zero-access boundary. No locked-test evidence is used below.

## 1. Verified Dataset Semantics

The active public baseline is `PUBLIC_SDT_48000_THERMAL_ONLY_V1`, not MI48 and
not a device-domain dataset. Its preserved roles are TRAIN 32,000,
DEVELOPMENT 8,000, and `LOCKED_PUBLIC_TEST` 8,000. The current public
baseline evidence is the B6R-P1/P2 pooled-MLP line. The P1 NumPy artifact
below is the recorded source of the exact P2 FP32 TFLite parameters; the
confusion evidence is the P1 DEVELOPMENT evaluation:

```text
480×640 image
  → PIL bilinear resize to 62×80
  → per-frame min-max normalization to [0,1]
  → adaptive mean pool to 8×10 = 80 features
  → Dense(32, ReLU) → Dense(3, softmax)
```

The source-to-target mapping is explicit and is a posture/presence proxy:

| SDT source token | Source semantic | SafeNest target | Development support |
|---:|---|---|---:|
| `0` | `LYING` | `HUMAN_FALL_PROXY` | 2,000 |
| `1` | `SITTING` | `HUMAN_NORMAL` | 2,000 |
| `2` | `STANDING` | `HUMAN_NORMAL` | 2,000 |
| `3` | `EMPTY_ROOM` | `NOT_HUMAN` | 2,000 |

`HUMAN_FALL_PROXY` means a lying/fallen posture proxy. It is not a temporal
fall event, clinical apnea/fall label, safety ground truth, or real-fall
measurement.

The tracked P0 contract and source materializer preserve source token,
source archive/member, source image geometry/mode, label-record index, and
derived tensor identity. They do not provide trusted subject, session,
recording, sequence, scene, orientation, or human-geometry annotations for
the error rows. The source semantic policy also explicitly forbids using
temporal fields as if they were present. The bulk P0 payload and row-level
prediction arrays are not Git-tracked in the current checkout; the P1 model
metadata retains prediction hashes, not row memberships.

Evidence reviewed includes:

- `docs/thermal/20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md`
- `config/thermal/b6r_p0_public_sdt_contract.json`
- `datasets/thermal/label_semantics.py`
- `scripts/materialize_thermal_b6r_p0_public_sdt.py`
- `datasets/thermal/manifests/B6R-P0_public_sdt_materialization/`
- `datasets/thermal/manifests/B6R-P1_public_sdt_controlled_training/`
- `models/thermal/public_sdt/public_sdt_pooled_mlp_v1.json`
- `datasets/thermal/manifests/B6R-P4_public_sdt_software_robustness_failure_mode/`
- historical T-B1/T-B2 reports and compact manifests for the two CNN
  references.

## 2. Existing Confusion Evidence

The current pooled-MLP evidence is the P1 DEVELOPMENT diagnostic, which was
also used for P1 best-epoch selection. It is not an independent final test.
The class order is rows = true class and columns = predicted class:

```text
                         predicted
                       NOT   NORMAL  FALL_PROXY
true NOT_HUMAN         1907      93       0
true HUMAN_NORMAL       129    3697     174
true HUMAN_FALL_PROXY   115     233    1652
```

The tracked P1/P4 evidence reports:

| Item | Value |
|---|---:|
| DEVELOPMENT samples | 8,000 |
| Accuracy | 0.907000 |
| Macro F1 | 0.901327 |
| `HUMAN_NORMAL` support | 4,000 |
| `HUMAN_FALL_PROXY` support | 2,000 |
| Current pooled-MLP prediction SHA | `65efe9df3da592c9c01a4da0d1ab2709815009fe803a8b1f319d97fc1c3d7223` |

The direct failure signal is therefore real within this public DEVELOPMENT
experiment: normal frames are sometimes emitted as the fall proxy. The
signal establishes a failure mode, not its cause and not real-fall
performance.

### Historical model evidence, kept non-comparable

The existing CNN records are useful context only. They are not used to crown
a model or to combine metrics with the current public-SDT baseline.

| Evidence | Dataset / role | Preprocessing and label caveat | `NORMAL → FALL` count |
|---|---|---|---:|
| `SMALL_CNN_BASELINE_V1`, T-B1 P1 | canonical T-B development `VALIDATION`, 8,000 | TRAIN-fitted global z-score; target is `HUMAN_FALL`, not current `HUMAN_FALL_PROXY` | 22 |
| `SMALL_CNN_BASELINE_V1`, T-B1 P1 | canonical T-B `REAL_EVAL_DEVELOPMENT`, 8,000 | separate real-development characterization; not locked test | 141 |
| `DEPTHWISE_SEPARABLE_CNN_V1`, T-B2 | canonical T-B `VALIDATION`, 8,000 | different dataset/protocol; one architecture trial | 181 |
| current pooled MLP, B6R-P1 | public SDT `DEVELOPMENT`, 8,000 | per-frame min-max + 8×10 pooling; target is `HUMAN_FALL_PROXY` | 174 |

The historical rows differ in source dataset, thermal units/preprocessing,
split and role semantics, architecture, training protocol, and evaluation
purpose. The T-B real-development result is especially not a replacement for
the protected public test. These records can motivate failure analysis, but
they cannot support a cross-experiment ranking or causal conclusion.

## 3. NORMAL → FALL_PROXY Breakdown

For the current public pooled MLP:

| True target | Predicted `NOT_HUMAN` | Predicted `HUMAN_NORMAL` | Predicted `HUMAN_FALL_PROXY` | Total |
|---|---:|---:|---:|---:|
| `HUMAN_NORMAL` | 129 | 3,697 | **174** | 4,000 |

Thus:

```text
NORMAL → FALL_PROXY = 174 / 4,000 = 4.35%
```

The 174 rows cannot be reconstructed as `SITTING → FALL_PROXY` versus
`STANDING → FALL_PROXY` from current tracked evidence. The source token names
and aggregate 2,000/2,000 DEVELOPMENT supports are known, but the error
matrix is only available after the two normal source tokens have been
collapsed into target class `HUMAN_NORMAL`. Row-level predictions and the
source-token-to-prediction join are not retained in Git. No 87/87 or other
allocation is inferred.

### Concentration by available dimensions

| Dimension | Current evidence | Audit status |
|---|---|---|
| Source token (`SITTING` vs `STANDING`) | Source semantics exist; error counts do not | `NOT_VERIFIABLE` |
| Sequence / temporal order | No trusted sequence-level error table; temporal fields are not part of the SDT semantic contract | `NOT_VERIFIABLE` |
| Scene | No scene field or scene-level confusion table | `NOT_VERIFIABLE` |
| Orientation | No orientation field or orientation-level confusion table | `NOT_VERIFIABLE` |
| Subject | No subject/session/recording identity is claimed for public SDT | `NOT_VERIFIABLE` |
| Frame group | No frame-group definition or row-level prediction membership is available | `NOT_VERIFIABLE` |

## 4. Error / Geometry Slices

No current DEVELOPMENT evidence joins the 174 error rows to low centroid,
silhouette width/aspect, body footprint, bottom-frame proximity, partial
visibility, contrast, or orientation features. The source image size
`480×640` and model tensor size `62×80` are preprocessing geometry, not
human-geometry annotations.

The existing P4 audit provides one bounded software-only clue. It applies
synthetic transformations to the fixed 8,000-sample DEVELOPMENT role; it does
not label physical geometry or add real hard negatives. The resulting
`HUMAN_NORMAL → HUMAN_FALL_PROXY` counts were:

| Synthetic condition | Normal-to-fall count | Interpretation allowed here |
|---|---:|---|
| Clean baseline | 174 | Current aggregate failure |
| Bounded noise, σ=0.05 | 194 | Output changes under synthetic intensity noise |
| Row/column dropout, 4 lines | 177 | Output changes under synthetic line loss |
| Rectangle occlusion, 10×10 | 182 | Output changes under small synthetic masking |
| Rectangle occlusion, 16×16 | 240 | Larger synthetic masking changes errors |
| Rectangle occlusion, 22×23 | 242 | Approx. 10% synthetic masking changes errors |
| Four small spatial shifts | 105–251 | Direction/severity-dependent spatial sensitivity |

These results support only a **weak engineering hypothesis** that spatial or
visibility perturbations can affect the current model's outputs. They do not
show that the original false-fall rows are low, horizontal, near the bottom,
partially visible, weak-contrast, or unusually oriented humans. Synthetic
rectangle masking is not a semantic partial-human label; synthetic shift is
not camera/sensor orientation evidence.

| Requested slice | Status | Reason |
|---|---|---|
| Low centroid | `NOT_VERIFIABLE` | No row-level human centroid and no error-row membership |
| Wide / horizontal silhouette | `NOT_VERIFIABLE` | No silhouette or posture-shape feature |
| Body footprint | `NOT_VERIFIABLE` | No foreground/body segmentation or footprint feature |
| Bottom-frame proximity | `NOT_VERIFIABLE` | No row-level error geometry or frame-location feature |
| Partial visibility | `NOT_VERIFIABLE` for original data; `WEAK_HYPOTHESIS` for synthetic masking sensitivity | P4 has masking stress only, not partial-human labels |
| Weak contrast | `NOT_VERIFIABLE` | No contrast slice; per-frame min-max is preprocessing, not an error annotation |
| Orientation | `NOT_VERIFIABLE` | No orientation provenance; synthetic shifts are not orientation |

## 5. Missing Hard-Negative Coverage

The four public source tokens do not constitute a hard-negative taxonomy. In
particular, `LYING` is mapped to the fall-posture proxy, while `SITTING` and
`STANDING` are broad normal classes. The current evidence has no explicit,
reviewable coverage contract for the following normal-but-fall-like cases:

| Requested hard-negative family | Current status |
|---|---|
| Crouching | No explicit source label or coverage count |
| Bending | No explicit source label or coverage count |
| Kneeling | No explicit source label or coverage count |
| Reclining | Not separated from broad posture tokens; coverage not verifiable |
| Near-floor normal | No semantic label or geometry slice |
| Partial human | No semantic label; P4 masking is synthetic stress only |
| Occlusion | No source annotation; P4 masking is synthetic stress only |
| Walking transition | No temporal/transition annotation |
| Unusual orientation | No orientation provenance or slice |

This should be read as **missing explicit evidence**, not as a claim that no
such visual examples can exist inside raw public images. The current evidence
cannot identify, count, or validate them. The absence is material for
Candidate A/G1 design because a broad `SITTING` or `STANDING` target cannot
demonstrate coverage of these subcases.

## 6. DEVELOPMENT Hard-Negative Subset Feasibility

**Decision:**

```text
CURRENT_SDT_HARD_NEGATIVE_SUBSET_NOT_DEFENSIBLE
```

A semantic hard-negative subset cannot be defined from the current tracked
DEVELOPMENT evidence without inventing labels. The aggregate confusion matrix
does not identify the 174 rows, the P0 materialized payload is intentionally
not Git-tracked, and the P1 prediction artifact is represented by a hash
rather than row-level predictions. Even if the row IDs were recovered, a
false prediction is an observed error slice, not proof that the source image
is crouching, bending, kneeling, near-floor normal, occluded, or otherwise a
hard negative.

For a future DEVELOPMENT-only diagnostic rerun, the defensible deterministic
error predicate would be:

```text
split == DEVELOPMENT
AND target_label == HUMAN_NORMAL
AND exact_current_model_prediction == HUMAN_FALL_PROXY
```

That predicate must remain an **error slice**, preserve the original split,
retain the original source token, and avoid relabeling. It would not become a
semantic hard-negative label until a separate, reviewed annotation contract
provided evidence for the visual condition. No such rerun, materialization,
resplit, or label mutation was performed in TV2-H0.

## 7. Candidate-A Implications

TV2-H0 supplies enough failure evidence to inform G1/Candidate A design, but
not enough evidence to freeze an architecture or declare a cause.

Candidate A should therefore:

1. Treat `NORMAL → FALL_PROXY` as a primary failure metric and report the
   source-token breakdown for `SITTING` and `STANDING` separately whenever
   row-level provenance and predictions are available.
2. Add an explicit hard-negative annotation/capture taxonomy for crouching,
   bending, kneeling, reclining, near-floor normal, partial human, occlusion,
   walking transitions, and unusual orientations. Do not synthesize these
   semantics from the existing four tokens.
3. Preserve subject/session/recording/sequence/frame provenance and freeze
   subject-level splits before any model comparison. Define geometry slices
   before looking at comparative results, and keep `LOCKED_PUBLIC_TEST`
   unavailable to development selection.
4. Use a spatially explicit, compact representation as a testable Candidate A
   hypothesis because the pooled MLP and P4 stress evidence show a plausible
   spatial-detail failure mode. This is a design hypothesis, not evidence
   that a CNN will win.
5. Keep the `HUMAN_FALL_PROXY` name and claim boundary. Candidate A must not
   convert lying-posture evidence into real-fall or safety ground truth.

No Candidate A training, model export, architecture freeze, or model ranking
was performed by this audit.

## 8. Root-Cause Hypothesis Classification

The following classifications use only the allowed root-cause vocabulary.

| Hypothesis / claim | Classification | Evidence boundary |
|---|---|---|
| The current pooled MLP has a measurable public-DEVELOPMENT normal-to-fall-proxy failure mode | `SUPPORTED_HYPOTHESIS` | 174/4,000 in the tracked P1 DEVELOPMENT confusion matrix |
| Synthetic spatial/visibility perturbations can change the model's error pattern | `WEAK_HYPOTHESIS` | P4 masking/shift stress changes counts, but is not physical or semantic geometry evidence |
| Adaptive pooling or loss of fine spatial detail is the cause of the 174 errors | `WEAK_HYPOTHESIS` | Plausible design explanation; no ablation or row-level geometry join |
| Low centroid causes the false falls | `UNRESOLVED` | No centroid/error slice |
| Wide or horizontal human geometry causes the false falls | `UNRESOLVED` | No silhouette/error slice; `LYING` is a source posture proxy, not an error-cause label |
| Body footprint or bottom-frame proximity causes the false falls | `UNRESOLVED` | No footprint/location features |
| Partial visibility, weak contrast, or orientation explains the false falls | `UNRESOLVED` | No original-data slice; synthetic stress does not identify the cause |
| Errors concentrate in SITTING rather than STANDING, or in a sequence/scene/subject/frame group | `UNRESOLVED` | Required row-level joins are unavailable |
| `HUMAN_FALL_PROXY` errors are evidence of real fall events or safety failures | `CONTRADICTED` | The immutable semantic contract defines a lying/fallen posture proxy, not real-fall or safety ground truth |

No requested physical-geometry cause is promoted to `SUPPORTED_HYPOTHESIS`.
The classifications are failure-understanding guidance, not model-selection
authority.

## 9. TV2-H0 Gate

**Gate: `PASS_WITH_LIMITATIONS`**

The gate passes with limitations because current public DEVELOPMENT evidence
is sufficient to inform G1/Candidate A design:

- the aggregate `NORMAL → FALL_PROXY` failure is verified at 174/4,000
  (4.35%);
- P4 supplies a deterministic, DEVELOPMENT-only software stress indication
  that spatial masking and shifts can alter the failure pattern; and
- the audit identifies the exact missing hard-negative and provenance fields
  required for the next contract.

The limitations are binding:

- SITTING-versus-STANDING false-fall counts are not verifiable;
- concentration by sequence, scene, orientation, subject, or frame group is
  not verifiable;
- the requested low/horizontal/centroid/footprint/bottom/contrast slices are
  not verifiable;
- a semantic current-Dataset hard-negative subset is not defensible; and
- no claim about MI48, Thermal-90, real falls, safety, device performance, or
  production readiness follows from this gate.

TV2-H0 does not authorize training, dataset mutation, locked-test access,
Candidate A execution, Candidate B execution, runtime changes, manifest
changes, Team-repository changes, Integration work, or an update to the
master execution map.

## Validation record

The audit branch was created from the current `origin/main` after verifying
that the master execution map from PR #184 is present. Before commit, the
following checks are required and are reported with the delivery:

```text
git status --short
git diff --check
git log origin/main..HEAD --oneline
git diff origin/main...HEAD --name-only
```

The intended change set is one file only:

```text
docs/thermal/20260830_SafeNest_Thermal_V2_TV2-H0_SDT_Hard_Negative_Audit_01.md
```

Explicit exclusions: no training, no dataset mutation, no model export, no
locked-test access, no Team repository change, no Integration change, and no
master-map update.
