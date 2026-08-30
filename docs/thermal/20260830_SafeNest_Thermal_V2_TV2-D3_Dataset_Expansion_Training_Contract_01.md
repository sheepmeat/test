# SafeNest Thermal V2 — TV2-D3 Dataset Expansion Membership and Prototype Training Contract

- Worker: `제2그록4.5`
- Date: 2026-08-30
- Repository: `sheepmeat/test`
- Phase: `TV2-D3`
- Branch: `thermal-v2/tv2-d3-expansion-training-contract`
- Startup base: `origin/main` at `3d6170c6c96abe7b7a75127d70c17876eee39a75` (TV2-D2 merge, PR `#192`)
- Training authorization: `NONE`
- Dataset merge authorization: `NONE`
- Dataset materialization: `NONE`
- `LOCKED_PUBLIC_TEST_ACCESS`: `0`
- G1 freeze: `NOT_CLAIMED`
- D3 gate: `PASS_WITH_LIMITATIONS`

This report answers which exact dataset membership, source role, label eligibility, split unit, geometry policy, quality policy, and representation boundary may be frozen for the future controlled Candidate A / C1 / Candidate B DEVELOPMENT experiment. It does not train, rank models, freeze G1, or materialize raw data.

Companion machine-readable contract: `config/thermal/tv2_d3_dataset_membership.json`. The JSON restates membership roles, lane boundaries, lineage fields, and hard-negative coverage so a later verification worker can check them without re-parsing this prose. No raw payload is stored in Git.

## 1. Executive Conclusion

TV2-D3 is **`PASS_WITH_LIMITATIONS`**.

The data side of the future matched A / C1 / (B) architecture comparison can be defined as a **bounded SDT-core contract**. Advancing from D2 does **not** place QUIDA, eHomeSeniors, or Thermal-IM into supervised TRAIN.

```text
PROPOSED_CORE_TRAIN_MEMBERSHIP
  PUBLIC_SDT official TRAIN (32,000) only
  lane = P_PHYSICAL_TEMP_LANE
  geometry = G1_FIXED_ASPECT_CROP_BILINEAR → [62,80,1]
  labels = SDT_POSTURE_TO_SAFENEST_3CLASS_PROXY_V1

PROPOSED_CORE_DEV_MEMBERSHIP
  PUBLIC_SDT official DEVELOPMENT (8,000) only
  LOCKED_PUBLIC_TEST remains closed
```

New public sources improve **evidence and evaluation design**. They are **not** yet defensible supervised TRAIN additions. That is an intended conservative result, not a failure to expand sample count.

| Source / subset | Representation lane | TRAIN | DEV | HN eval | Reference | Reason |
|---|---|---|---|---|---|---|
| PUBLIC_SDT official TRAIN 32,000 | P | **YES** | no | source-token slices later | no | Only admitted source with frame-level 3-class labels **and** frozen geometry |
| PUBLIC_SDT official DEVELOPMENT 8,000 | P | no | **YES** | H0 error-slice predicate | no | Official DEVELOPMENT role; architecture selection only |
| PUBLIC_SDT `LOCKED_PUBLIC_TEST` 8,000 | P | no | no | no | integrity-only | No access through architecture selection |
| QUIDA `subject_*/ir_camera.csv` | P | **NO** | **NO** | **NO** | temporal diagnostic | `FRAME_SUPERVISION_UNRESOLVED` + `NOT_TRAIN_ELIGIBLE_UNTIL_GEOMETRY_RESOLVED` + unverified asset terms |
| eHomeSeniors calibrated MLX90640 | P | **NO** | **NO** | **NO** | temporal diagnostic | File-level staged falls; no framewise onset/end; orientation unfrozen |
| Thermal-IM action intervals | I | **NO** | **NO** | **YES, I-lane only** | no | Intensity ≠ Celsius; would confound matched A/C1/B; sitting/recline tokens are HN diagnostics |
| eHomeSeniors raw MLX | none | no | no | no | **YES** | Raw words are not Celsius |
| eHomeSeniors Omron | none | no | no | no | **YES** | 32 linear values cannot feed 62×80 spatial posture |
| IPHD base | P (ref) | no | no | no | **YES** | Different sensor; boxes not 3-class posture; asset terms unverified |
| TF-66 | n/a | no | no | no | HOLD | Payload still request-gated |
| IPHPDT | n/a | no | no | no | HOLD | Labeled posture derivative still request-gated |
| SafeNest / Thermal-90 captures | n/a | no | no | no | **YES** | Existing G1 policy: orientation/geometry sanity only |

Thermal-IM and temporal fall data **do not** enter core supervised training.

PRE advisory (D3 does not fit statistics): `PRE_READY_FOR_G1_FREEZE_WITH_LIMITATIONS`. Newly TRAIN-fitted SDT P1 after G1 geometry is the matched-experiment hypothesis. Historical T-B1 P1 statistics and B6R per-frame min-max are **not** C1 PRE. Thermal-IM intensity must never contribute to P-lane P1.

Control Tower, not D3, closes G1. D3 does not declare `G1 PASS`.

## 2. Evidence Consumed and D3 Boundary

Verified on this branch: TV2-D2 report and `config/thermal/tv2_d2_source_compatibility.json` exist on `origin/main` at `3d6170c6c96abe7b7a75127d70c17876eee39a75`.

Authoritative D2 inputs consumed:

```text
d2_gate = PASS_WITH_LIMITATIONS
P_PHYSICAL_TEMP_LANE = QUIDA + eHomeSeniors calibrated MLX90640
I_INTENSITY_LANE     = Thermal-IM
Celsius + intensity + raw MLX words MUST NOT be concatenated
P1_NOT_READY (membership was unset)

QUIDA                              = ADVANCE_TO_D3_WITH_UNRESOLVED_LABEL_LIMIT
eHomeSeniors calibrated MLX90640   = ADVANCE_TO_D3_WITH_UNRESOLVED_LABEL_LIMIT
Thermal-IM                         = ADVANCE_TO_D3_SUPPLEMENTAL
eHome raw MLX                      = REFERENCE_ONLY / EXCLUDED
eHome Omron                        = REFERENCE_ONLY / EXCLUDED
IPHD                               = REFERENCE_ONLY
TF-66 / IPHPDT                     = HOLD
```

`ADVANCE_TO_D3_*` is **not** TRAIN membership. D3 distinguishes, for every source:

```text
TRAIN_ELIGIBLE
DEV_SLICE_ONLY
HARD_NEGATIVE_EVAL_ONLY
REFERENCE_ONLY
HOLD
EXCLUDE
EXCLUDED_FROM_FRAME_TRAIN
TEMPORAL_DIAGNOSTIC_ONLY
FUTURE_ANNOTATION_CANDIDATE
```

Additional evidence read: TV2-D0, TV2-D1, TV2-H0, TV2-A0, G1 Model Contract Foundation, Thermal V2 Master Execution Map, `config/thermal/b6r_p0_public_sdt_contract.json`, `config/thermal/b6r_p1_public_sdt_training_contract.json`, `datasets/thermal/label_semantics.py`, and T-A0 source-identity limits. Historical B6R-P0/P1/P2 contracts remain **SDT-specific**. They are not silently reused as a multi-source training contract.

D3 does not: train Candidate A, Candidate B, or C1; invent `fall_timestamp ± N seconds`; label whole eHome files `FALL_PROXY`; concatenate Celsius with intensity; reuse the SDT crop as a QUIDA/eHome/Thermal-IM adapter; fit P1 statistics; access `LOCKED_PUBLIC_TEST`; edit the execution map; change Team/Integration/Pi artifacts; or treat SafeNest captures as training evidence.

## 3. Primary Question and Conservative Rule

The primary D3 question is membership, not model ranking:

```text
What exact dataset membership, source role, label eligibility, split unit,
geometry policy, quality policy, and representation boundary may be frozen
for the future controlled A / C1 / (B) comparison?
```

D3 does **not** answer which model performs best.

Conservative rule: **do not force data into training**. A source with unresolved frame supervision must not receive invented labels so that it can be used for training. It is valid for new sources to improve diagnostics while remaining outside supervised TRAIN. D3 optimizes for defensible comparison, not sample count.

## 4. Core Fair-Comparison Contract (Data Side)

Future architecture comparison requires C1 `MATCHED_POOLED_MLP_CONTROL`, Candidate A, and Candidate B if G3 approves, to use the **same** data-side contract except architecture itself.

### 4.1 C0 is not C1

| ID | Role | Data/PRE identity | Comparability |
|---|---|---|---|
| **C0** | Frozen operational baseline B6R-P2 pooled MLP | Native historical contract: direct PIL bilinear 480×640→62×80, per-frame min-max, official SDT splits | Historical / operational reference. **Not** architecture-factor-only comparable if GEO/PRE differ |
| **C1** | `MATCHED_POOLED_MLP_CONTROL` | **This D3 membership** + G1 GEO + newly TRAIN-fitted P1 | Clean architecture-factor control versus A/(B) |
| **A / (B)** | Candidate architectures | Same membership, GEO, PRE, LABEL, splits, augmentation, optimizer/LR, early stopping, seeds, evaluation as C1 | Architecture is the intended experimental factor |

C0 remains a frozen historical operational reference. Retraining C0 under a new contract would destroy that reference. C1 is a future retrain of the pooled-MLP **architecture** under the matched contract. D3 does not train C1.

### 4.2 Data-side matched fields frozen here

```text
dataset membership     = PUBLIC_SDT TRAIN 32,000 / DEVELOPMENT 8,000
TRAIN / DEV roles      = official SDT partitions, no resplit
label mapping          = SDT_POSTURE_TO_SAFENEST_3CLASS_PROXY_V1
                         0 LYING → 2 HUMAN_FALL_PROXY
                         1 SITTING → 1 HUMAN_NORMAL
                         2 STANDING → 1 HUMAN_NORMAL
                         3 EMPTY_ROOM → 0 NOT_HUMAN
geometry               = G1_FIXED_ASPECT_CROP_BILINEAR on SDT only
                         crop [10,0,630,480) → bilinear 62×80, 1 channel
preprocessing          = P1_TRAIN_FITTED_GLOBAL_ZSCORE newly fit on that TRAIN
                         after G1 canonicalization; not fitted in D3
quality policy         = fail-closed non-finite / unsupported shape; no invented clip
augmentation           = NONE for the architecture bake-off
LOCKED_PUBLIC_TEST     = closed through architecture selection
```

Optimizer, learning-rate policy, early stopping, and seed set are **required to be shared** among A/C1/(B) (TV2-A0). D3 does not freeze their numeric values; that remains G1/G2. The data contract requires they be identical once chosen.

A later data-corrective stage may vary hard-negative evaluation **after** architecture is frozen. That stage is not the matched A/C1/B bake-off.

## 5. SDT Core Dataset Role

The existing public SDT 48,000-sample dataset (`PUBLIC_SDT_48000_THERMAL_ONLY_V1`, Zenodo `doi:10.5281/zenodo.4124309`) remains the current strongest **frame-labeled** source. D3 therefore keeps future core training as:

```text
SDT_CORE
new public sources = supplemental / evaluation / reference / HOLD
no additional source joins supervised TRAIN under current evidence
```

A new model does **not** require merging new datasets. The main objective is reducing `HUMAN_NORMAL → HUMAN_FALL_PROXY` without destroying useful `FALL_PROXY` sensitivity. Data correction can include better hard-negative evaluation, more conservative label inclusion, and separate diagnostic sources. It does not require forced multi-source training.

SDT limitations remain binding and are inherited, not hidden:

- Source labels are posture/presence proxies, not temporal fall events.
- Subject/session/recording identity is absent; subject-generalization is `NOT_VERIFIABLE`.
- T-A6 disclosed 14,514 TRAIN↔VALIDATION near-duplicate pairs; official roles stay unchanged.
- T-A0 records a non-commercial research restriction with citation/attribution.
- Distributed geometry is 480×640, already bilinear-enlarged from native Lepton 3.5 120×160. Canonicalization must not claim to restore the native grid.
- SDT is FLIR Lepton, not MLX90640. Sharing a physical-temperature **family** with QUIDA/eHome does not authorize pooling TRAIN tensors.

B6R-P0/P1 remain the historical SDT auxiliary lineage. The new D3 contract is a **new membership object** that happens to still be SDT-only for TRAIN. It is not a silent promotion of B6R min-max into the C1 matched experiment.

## 6. QUIDA Membership Decision

D2 established: P-lane Celsius-compatible; subject grouping available; orientation not frozen; fall instants only; `FRAME_SUPERVISION_UNRESOLVED`; quality policy not frozen; asset terms `DATASET_LICENSE_NOT_VERIFIABLE`.

D3 role:

```text
EXCLUDED_FROM_FRAME_TRAIN
TEMPORAL_DIAGNOSTIC_ONLY
FUTURE_ANNOTATION_CANDIDATE
NOT_TRAIN_ELIGIBLE_UNTIL_GEOMETRY_RESOLVED
```

Not `TRAIN_ELIGIBLE`. Not core `DEV_SLICE_ONLY`. Not `HARD_NEGATIVE_EVAL_ONLY` (walking context is unlabeled). Not `EXCLUDE` from the V2 evidence set.

### Why TRAIN is refused

1. **Frame supervision.** `falls.csv` supplies 100 Unix instants. There is no authoritative duration or interval field. The paper’s “e.g., 2 s” window is an author analysis parameter, not a dataset contract. D3 does **not** invent `fall_timestamp ± N seconds`. Labeling every frame of a walk-plus-fall recording as `HUMAN_FALL_PROXY` is forbidden.
2. **Geometry.** Packing-order candidate `H=24, W=32` is a diagnostic, not a freeze. Physical up-edge, capture transpose, and flip/rotation remain `ORIENTATION_NOT_VERIFIABLE`. `NOT_TRAIN_ELIGIBLE_UNTIL_GEOMETRY_RESOLVED` is accepted rather than guessing orientation to enlarge TRAIN.
3. **License.** Asset terms remain unverified (OSF `node_license=null`, no archive terms file). Unverified terms independently block a training release.
4. **Quality.** Rare extrema (including 928 °C) are flagged in D2; no clipping bound is frozen. Unfrozen quality is another TRAIN blocker.
5. **Hard negatives.** Protocol walking exists but is not independently frame-labeled. Using complement-of-instant as `HUMAN_NORMAL` would invent supervision.

### What QUIDA may be used for

- Subject-preserving temporal diagnostic plots (instant markers on Celsius sequences).
- Future **authorized** annotation campaign to create `FRAME_SUPERVISION_DERIVABLE_WITH_VERIFIED_RULE` without D3 fabricating ±N seconds.
- Provenance-preserving reference for MLX90640 physical-lane discussion.

Subject identity (`subject_1`–`subject_10`) is preserved. If a later annotation campaign is authorized, the minimum split unit remains **subject**. Derived frames inherit `source_id=QUIDA` and must not cross subject boundaries.

## 7. eHomeSeniors Membership Decision

Use **calibrated MLX90640** `IR 1 [C]` … `IR 768 [C]` fields only. Raw MLX words and Omron remain excluded from the 62×80 frame model.

D2 established: file-level staged falls; no framewise onset/end; preceding ADL unlabeled; `FRAME_SUPERVISION_UNRESOLVED`; orientation not verifiable.

D3 role for calibrated MLX90640:

```text
EXCLUDED_FROM_FRAME_TRAIN
TEMPORAL_DIAGNOSTIC_ONLY
FUTURE_ANNOTATION_CANDIDATE
NOT_TRAIN_ELIGIBLE_UNTIL_GEOMETRY_RESOLVED
```

Whole files must **not** be labeled `FALL_PROXY`. Each volunteer file is a staged-fall protocol with ordinary activity immediately before a fall. Paper fall-duration histograms (group-1 mean 2.62 s, group-2 mean 2.20 s) are barycenter analysis results, not per-frame labels.

Volunteer (`G1-1` … `G2-3`) is the minimum split unit. Group 1 (performing artists coached to emulate older-adult falls) versus group 2 (healthy young volunteers) remains provenance, not a clinical age label.

Geometry adapter is unfrozen. SDT crop reuse is forbidden. Quality policy is unfrozen. License is CC BY 4.0 from linked asset metadata, with raw-field scope still limited — but license alone does not create frame supervision.

Calibrated MLX data are therefore **not** `TRAIN_ELIGIBLE`, **not** core `DEV_SLICE_ONLY`, and **not** labeled hard-negative evaluation. They are a temporal diagnostic and a future annotation candidate.

Raw MLX: `EXCLUDE` / `EXCLUDED_FROM_FRAME_MODEL_INPUT` / `REFERENCE_ONLY`.
Omron: `EXCLUDE` / `REFERENCE_ONLY`. Interpolating 32 linear pixels into 62×80 would fabricate spatial structure.

## 8. Thermal-IM Membership Decision

Hard boundary:

```text
Thermal-IM != Celsius
MUST NOT enter:
  P-lane raw tensors
  P-lane mean/std fit (P1)
  P-lane A / C1 / B TRAIN
```

`ADVANCE_TO_D3_SUPPLEMENTAL` from D2 does **not** mean merge into P-lane training.

Chosen role:

```text
HARD_NEGATIVE_EVAL_ONLY
lane = I_INTENSITY_LANE
NOT part of core matched A/C1/B TRAIN or DEVELOPMENT selection
I_LANE_SEPARATE_EXPERIMENT = DEFERRED_NOT_CORE_WOULD_CONFOUND_A_C1_B
```

An I-lane experiment would change representation, PRE statistics, geometry adapter, and positive-class availability (no fall labels). Mixing it into the matched architecture comparison would confound the spatial-CNN hypothesis with a domain/representation change. D3 therefore keeps Thermal-IM **outside** the core matched comparison.

### Why not the other roles

| Rejected role | Why |
|---|---|
| `I_LANE_SEPARATE_EXPERIMENT` as a G1-core track | Would split A/C1/B into incomparable representation regimes |
| `DEV_SLICE_ONLY` in the matched DEV set | Intensity DEV metrics cannot fairly select a P-lane architecture |
| `REFERENCE_ONLY` | Understates verified sitting/recline/exercise tokens useful as HN diagnostics |
| `EXCLUDE` | Would discard the only admitted source with explicit seated/recline vocabulary |
| `TRAIN_ELIGIBLE` | Not Celsius; no `HUMAN_FALL_PROXY` positives; grouping only partial |

### HN-eval mapping (advisory; does not amend the LABEL contract)

| Original evidence | HN-eval use | Subtype | Decision |
|---|---|---|---|
| `sit sofa/chair/stool/desk` | `HUMAN_NORMAL` diagnostic | `NON_FALL_ACTIVITY_OR_POSTURE` | `MAP_WITH_LIMITATION` for I-lane HN eval only |
| `lie sofa` | recline confound vs `HUMAN_FALL_PROXY` | `STATIC_LYING_POSTURE` | `EXCLUDE` from TRAIN and from automatic `FALL_PROXY`; **not** `HUMAN_NORMAL` |
| `touch …` | object-interaction motion | `NON_FALL_ACTIVITY_OR_POSTURE` | conservative `EXCLUDE` from pure-class; optional OTHER HN slice |
| `push-ups` / `sit-ups` / `leg-stretching` / garment actions | floor exercise / ambiguous activity | `NON_FALL_ACTIVITY_OR_POSTURE` | `EXCLUDE` (G1 rule) |
| empty `annotation.json` | none | `UNKNOWN` | `UNRESOLVED`; **not** `NOT_HUMAN` |
| no fall token | none | n/a | not a positive fall source |

Frame supervision is derivable for annotated `start`/`end` intervals at documented 15 FPS. Outside-interval frames stay unlabeled.

Grouping: actor if/when `meta.csv` is obtained and audited; otherwise clip as a weaker key with `LIMITATION_EXPLICIT`. Do not claim subject-level generalization. Do not randomly split frames inside a clip.

I-lane HN eval must **not** feed matched A/C1/B early stopping, architecture selection, or P1 fit. It is a supplemental diagnostic after, or beside, the core comparison — never a silent fourth class or a concatenated tensor.

## 9. Hard-Negative Policy

H0 established current SDT hard-negative coverage is weak. Primary failure remains `HUMAN_NORMAL → HUMAN_FALL_PROXY` at the B6R DEVELOPMENT anchor **174 / 4000 = 4.35%**. That number is a current-model diagnostic, not a target D3 claims these sources will move.

A semantic SDT hard-negative subset remains `CURRENT_SDT_HARD_NEGATIVE_SUBSET_NOT_DEFENSIBLE`. The allowed DEVELOPMENT error predicate stays an **error slice**, not a new label:

```text
split == DEVELOPMENT
AND target_label == HUMAN_NORMAL
AND exact_current_model_prediction == HUMAN_FALL_PROXY
```

### Taxonomy

Statuses mean: `verified` = payload-verified source token; `unverified` = paper/D0 claim not payload-verified here; `absent` = no evidence the category exists as a label or verified token; `unlabeled` = protocol/context may contain it without independent labels. Unavailable categories are not pretended to exist.

| Family | PUBLIC_SDT | QUIDA | eHome calibrated MLX | Thermal-IM |
|---|---|---|---|---|
| `NORMAL_SEATED` | verified (`SITTING`) | absent | unlabeled | verified (`sit *`) |
| `NORMAL_UPRIGHT` | verified (`STANDING`) | unlabeled | unlabeled | absent |
| `WALKING` | absent | unlabeled (protocol) | unlabeled | absent (D0 walking/kneeling overridden by D1/D2 vocabulary) |
| `BENDING` | absent | absent | absent | absent |
| `CROUCHING` | absent | absent | absent | absent |
| `KNEELING` | absent | absent | absent | absent |
| `RECLINING` | unlabeled | absent | unlabeled (pre-fall lying possible) | verified (`lie sofa`) — `EXCLUDE` from TRAIN |
| `NEAR_FLOOR_NORMAL` | unlabeled | unlabeled | unlabeled | unlabeled |
| `PARTIAL_HUMAN` | unlabeled | unlabeled | unlabeled | unlabeled |
| `OCCLUSION` | unlabeled (P4 synthetic only) | unlabeled | unlabeled | unlabeled |
| `EXERCISE` | absent | absent | absent | verified — `EXCLUDE` |
| `TRANSITION` | absent | unlabeled (instants only) | unlabeled (no onset/end) | unlabeled |
| `OTHER` | unlabeled | unlabeled | unlabeled | verified (`touch`, garment) |

TF-66 metadata and IPHPDT paper posture names (including bending) remain `HOLD` / unverified as payload and are **not** entered as coverage.

Future DEVELOPMENT analysis should report these slices where `verified`, and must not infer `absent` categories from collapsed `HUMAN_NORMAL`. SDT `SITTING` versus `STANDING` source-token breakdown is required whenever row-level predictions exist (H0).

## 10. Label Membership Policy

Class contract remains:

| Index | Target | Meaning |
|---:|---|---|
| `0` | `NOT_HUMAN` | Frame-scoped absence-of-annotated-human proxy |
| `1` | `HUMAN_NORMAL` | Non-fall activity/posture proxy |
| `2` | `HUMAN_FALL_PROXY` | Fall-compatible posture/event proxy; never clinically verified fall |

Provenance distinctions that must be stored and never flattened:

```text
STATIC_LYING_POSTURE
TEMPORAL_FALL_EVIDENCE
NON_FALL_ACTIVITY_OR_POSTURE
NO_ANNOTATED_HUMAN
AMBIGUOUS
UNKNOWN
```

Static lying ≠ actual fall. Staged fall ≠ clinical/natural fall. Ambiguous samples are not forced into one of three classes. Use `EXCLUDE` or `UNRESOLVED`.

### Training-candidate inclusion (core SDT)

| SDT source | Target | Decision | `event_provenance` | Core TRAIN |
|---|---|---|---|---|
| `EMPTY_ROOM` | `NOT_HUMAN` | `ACCEPT` | `NO_ANNOTATED_HUMAN` | include |
| `SITTING` | `HUMAN_NORMAL` | `MAP_WITH_LIMITATION` | `NON_FALL_ACTIVITY_OR_POSTURE` | include |
| `STANDING` | `HUMAN_NORMAL` | `MAP_WITH_LIMITATION` | `NON_FALL_ACTIVITY_OR_POSTURE` | include |
| `LYING` | `HUMAN_FALL_PROXY` | `MAP_WITH_LIMITATION` | `STATIC_LYING_POSTURE` | include |

No SDT `AMBIGUOUS` invent-to-fill. Historical T-A4 `AMBIGUOUS` records stay provenance-only and out of pure-class training.

### Explicit non-inclusion

| Evidence | Decision | Why |
|---|---|---|
| QUIDA fall instants | `UNRESOLVED` at frame scope | No authoritative interval |
| QUIDA walking complement | `UNRESOLVED` | Not independently labeled |
| eHome file `f01`–`f15` | `UNRESOLVED` at frame scope | File/event provenance only |
| eHome unlabeled pre-fall ADL | `UNRESOLVED` | Do not treat as `HUMAN_NORMAL` |
| Thermal-IM `lie sofa` | `EXCLUDE` | G1 reclining/intentional-lying rule |
| Thermal-IM exercise/garment | `EXCLUDE` | G1 ambiguous-activity rule |
| Thermal-IM empty annotation | `UNRESOLVED` | Not `NOT_HUMAN` |
| IPHD human box | `EXCLUDE` from 3-class TRAIN | Presence only |

QUIDA/eHome temporal evidence may later map to `HUMAN_FALL_PROXY` **with limitation** only after a verified interval/onset-end rule exists. D3 does not create that rule.

## 11. Geometry Contract for G1 Input

Target remains `[1, 62, 80, 1]`. D2 did not freeze QUIDA/eHome orientation. D3 does not invent physical orientation.

For the core matched A/C1/B experiment, **only PUBLIC_SDT** has sufficiently frozen geometry to enter training.

### Core (PUBLIC_SDT)

```text
native geometry        = 480×640, 1 thermal channel, uint16 K×100 encoding
orientation            = source as stored; row 0 top, col 0 left;
                         rotation=0; horizontal_flip=false; vertical_flip=false
unit conversion        = °C = (raw - 27315) / 100   (G1)
adapter                = G1_FIXED_ASPECT_CROP_BILINEAR
crop [x0,y0,x1,y1)     = [10, 0, 630, 480)
interpolation          = bilinear, HALF_PIXEL_CENTER, EDGE_CLAMPING
channel count          = 1
output                 = [62, 80, 1] float32 Celsius before P1
fail-closed            = unsupported shape/channel/unit/orientation/non-finite
SDT crop reuse on others = FORBIDDEN
```

Historical B6R direct stretch without crop remains **C0-native** and is not silently reinterpreted as this profile.

### Non-core sources

| Source | Native | Adapter | Orientation | Output | Status |
|---|---|---|---|---|---|
| QUIDA | 768-vector; packing candidate 24×32 | not frozen; aspect-preserving 60×80+pad or direct 62×80 are candidates only | `ORIENTATION_NOT_VERIFIABLE` | n/a for TRAIN | `NOT_TRAIN_ELIGIBLE_UNTIL_GEOMETRY_RESOLVED` |
| eHome calibrated MLX | 768 `IR n [C]`; packing candidate 24×32 | same family candidates, source-specific, not SDT crop | `ORIENTATION_NOT_VERIFIABLE` | n/a for TRAIN | `NOT_TRAIN_ELIGIBLE_UNTIL_GEOMETRY_RESOLVED` |
| eHome raw / Omron | not a 62×80 posture image | none | n/a | n/a | `GEOMETRY_INCOMPATIBLE` |
| Thermal-IM | 288×384×3 uint8 | downsample candidates only; large detail loss | decoded top-left; no flip metadata | I-lane only, not core | `GEOMETRY_COMPATIBLE_WITH_LIMITATIONS` |
| IPHD | 160×120 or 213×120 registered | not frozen | not re-verified in D2 | reference | `GEOMETRY_NOT_FROZEN` |

Scientific standards are not weakened to enlarge the dataset.

## 12. PRE / P1 Decision Input

D2: `P1_NOT_READY` because membership was unset and two representation lanes existed.

D3 TRAIN membership is now **SDT-only**. That removes the membership blocker for a P-lane P1 fit. D3 does **not** fit P1.

Appropriate matched-experiment hypothesis:

```text
P1_TRAIN_FITTED_GLOBAL_ZSCORE
y = (x − mean_TRAIN) / max(std_TRAIN, 1e-6)
mean_TRAIN, std_TRAIN = one scalar each over all finite TRAIN pixels
after G1 GEO canonicalization of PUBLIC_SDT official TRAIN only
fit once, serialize, checksum; apply unchanged to DEVELOPMENT and both/all candidates
Thermal-IM intensity NEVER contributes to P-lane P1
QUIDA / eHome calibrated frames are not in TRAIN, so they do not affect the fit
```

Do **not** reuse:

- Historical T-B1 P1 statistics (T-A6 materialization / different experiment).
- B6R-P0 per-frame min-max as C1 PRE (that is C0).
- Any I-lane intensity statistic as a P-lane scale.

If Control Tower rejects P1 because of the documented synthetic-to-real gap, G1’s bounded fallback remains a preregistered P1-versus-P2 ablation with the **same** SDT membership. That is not an open preprocessing search and is not executed here.

```text
PRE advisory = PRE_READY_FOR_G1_FREEZE_WITH_LIMITATIONS
```

Ready: membership no longer blocks a TRAIN-only SDT P1 freeze after G1 GEO. Limitations: D3 does not freeze optimizer/seeds; GEO still requires Control-Tower acceptance of the SDT crop profile versus C0 stretch; P1 is not claimed domain-robust; quality policy for non-SDT sources remains unfrozen (they are not in TRAIN). Control Tower closes G1.

## 13. Split / Leakage Contract

No random correlated-frame splitting.

| Source | Minimum grouping | Additional keys | If ignored |
|---|---|---|---|
| PUBLIC_SDT | official source partition (`TRAIN` / `DEVELOPMENT` / `LOCKED_PUBLIC_TEST`) | archive member, label index, `image_t` identity | high: near-duplicates already disclosed; resplit forbidden |
| QUIDA | **subject** | per-subject `ir_camera.csv`, Unix time | high: long contiguous recordings |
| eHomeSeniors | **volunteer** `GX-Y` | group, fall-type file, row order | high: adjacent frames and repeated staged falls |
| Thermal-IM | **actor** if `meta.csv` verified; else **clip** with `LIMITATION_EXPLICIT` | room, scene, official split, clip | high inside a clip; actor overlap **not** audited |

Derived frames/windows inherit:

```text
source_id
subject / group
recording / clip
split
original label
mapped class
event provenance
extraction profile
```

Derived descendants must not cross split boundaries. Group IDs are namespaced by `source_id`. Do not fabricate identity from frame index, filename order, or hash.

`LOCKED_PUBLIC_TEST`: no preprocessing fit, tuning, selection, or metrics in D3 or in subsequent architecture selection. Access count remains 0 here.

SafeNest captures remain `REFERENCE_ONLY` (orientation/geometry sanity, qualitative domain-gap inspection). They are not a split authority and not a locked-test substitute.

## 14. Quality Policy

Core matched experiment (SDT):

- Require finite decoded values and verified source shape/channel.
- Fail closed on unsupported geometry, unit, orientation, or non-finite input. Do not substitute zeros, ambient, or a data-dependent crop.
- Do not invent a Celsius clip band for SDT TRAIN.
- Preserve validity-mask provenance where the T-A6 physical path requires it.

Supplemental sources keep `QUALITY_POLICY_NOT_FROZEN` (QUIDA extrema flag-not-clip; eHome second-resolution timestamp collisions preserve row order; Thermal-IM compression/palette limitation). Unfrozen quality is a reason they stay out of TRAIN, not a reason to invent thresholds so they can enter.

## 15. Dataset Lineage Manifest Design

D3 defines a machine-readable **future** lineage contract. It does **not** materialize or commit raw datasets.

Required fields for every future sample row (schema only; see JSON `lineage_record_schema`):

```text
sample_id
source_id
source_asset_id
subject_or_group_id
session_or_recording_id
frame_or_timestamp
representation_lane
native_geometry
canonical_geometry
geometry_profile
quality_flags
source_label
mapped_class
semantic_subtype
event_provenance
split_role
training_eligible
exclusion_reason
```

Missing values stay explicit (`ABSENT`, `UNRESOLVED`, `NOT_APPLICABLE`). Source-native metadata remains namespaced. Augmentations inherit the parent split and must record `augmentation=NONE` for the core bake-off.

No sample table is emitted in this phase.

## 16. Proposed Membership Lists

```text
PROPOSED_CORE_TRAIN_MEMBERSHIP
  PUBLIC_SDT official TRAIN 32,000
  representation_lane = P_PHYSICAL_TEMP_LANE
  training_eligible = true

PROPOSED_CORE_DEV_MEMBERSHIP
  PUBLIC_SDT official DEVELOPMENT 8,000
  representation_lane = P_PHYSICAL_TEMP_LANE
  training_eligible = false
  role = early stopping / development comparison / preregistered selection

SUPPLEMENTAL_DIAGNOSTICS
  QUIDA temporal diagnostic (subject-preserving; no frame TRAIN labels)
  eHomeSeniors calibrated MLX90640 temporal diagnostic (volunteer-preserving)
  Thermal-IM I-lane HARD_NEGATIVE_EVAL_ONLY (not matched DEV selection)
  IPHD base REFERENCE_ONLY
  SafeNest / Thermal-90 captures REFERENCE_ONLY
  H0 DEVELOPMENT error-slice predicate (not a semantic HN label)

EXCLUDED_OR_HELD
  QUIDA from supervised frame TRAIN
  eHomeSeniors calibrated MLX from supervised frame TRAIN
  Thermal-IM from P-lane A/C1/B TRAIN and P1
  eHomeSeniors raw MLX from frame-model input
  eHomeSeniors Omron from 62×80 spatial input
  PUBLIC_SDT LOCKED_PUBLIC_TEST from all development use
  TF-66 HOLD_PENDING_ACCESS
  IPHPDT HOLD_PENDING_ACCESS
```

## 17. Unresolved Issues (Explicit, Non-Blocking for Bounded Core)

1. QUIDA and eHome physical orientation and stored 2-D order.
2. Authoritative QUIDA fall intervals; eHome framewise onset/end.
3. QUIDA asset-level license/terms.
4. Thermal-IM `meta.csv` actor/room/scene/split overlap.
5. QUIDA quality exclusion bounds.
6. Whether a later authorized annotation campaign can create defensible frame supervision for QUIDA/eHome **without** inventing ±N seconds.
7. IPHD/IPHPDT access, terms, subject grouping, and bending-posture labels.
8. TF-66 video payload.
9. Whether any I-lane intensity statistic should ever exist; not designed as a G1-core track.
10. G1 GEO/PRE numeric freeze, optimizer/seed freeze, and G1 PASS — owned by Control Tower.
11. SDT subject identity remains absent; near-duplicates remain disclosed.
12. Crouch/bend/kneel/near-floor/partial-human coverage remains absent from core TRAIN.

These limitations keep supplemental sources out of TRAIN. They do not prevent defining a bounded SDT-core A/C1/B data contract.

## 18. TV2-D3 Gate Recommendation

**`PASS_WITH_LIMITATIONS`**

`PASS` is not chosen because supplemental sources remain scientifically limited (unresolved frame supervision, unfrozen geometry, I-lane confound, access holds). `BLOCKED` is not chosen because the core matched A/C1/(B) **data** contract can be defined without those sources: SDT TRAIN/DEV, frozen SDT geometry profile, conservative 3-class proxy map, no invented labels, no Celsius/intensity merge.

G1 may potentially freeze this bounded core contract while supplemental sources stay diagnostic/HOLD. D3 does **not** itself declare `G1 PASS`.

Authorized next step:

```text
D3 membership / training-data contract
 ↓
G1 final contract freeze   (Control Tower)
 ↓
Candidate A spec (G2) / Candidate B decision (G3)
```

Not authorized: Candidate A training; Candidate B training; C1 matched pooled-MLP training; dataset merge or materialization into Git; TFLite/INT8; model ranking; locked-test access; Team/Integration/Pi work; SafeNest-capture training use; P1 statistic fit; G1 PASS claim; execution-map edit.

SafeNest captures remain `REFERENCE_ONLY`.
