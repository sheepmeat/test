# SafeNest Thermal V2 — G1 Contract Foundation Audit

- Worker: `Luna 3`
- Date: `2026-08-30`
- Repository: `sheepmeat/test`
- Branch: `thermal-v2/g1-contract-foundation`
- Scope: `GEO + PRE + SPLIT + LABEL`
- Status: `CONTROL_TOWER_REVIEWABLE_CONTRACT_PROPOSAL_ONLY`
- Training: `FORBIDDEN`
- Final recommendation: `G1_READY_PENDING_D0_D3`

This document prepares a contract foundation for Control-Tower review. It does
not mark G1 PASS, select a production model, change the execution map, or
authorize downstream training.

## 1. Evidence Reviewed

The audit uses repository evidence already present on the local
`origin/main` reference. The required master map is present at
`docs/thermal/20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md`.

| Evidence | Contract-relevant finding |
|---|---|
| `docs/thermal/20260830_SafeNest_Thermal_V2_Master_Execution_Map_01.md` | G0 is PASS; GEO, PRE, SPLIT, LABEL, TV2-D0, and TV2-H0 are the active frontier. G1 remains planned and must not be closed by this worker. |
| `docs/reports/20260810_Codex_T-A0_Thermal_Dataset_Selection_Source_Identity_01.md` through `docs/reports/20260811_Codex_T-A6_Stage1_Thermal_Real_Conversion_Colab_01.md` | SDT source identity, raw-unit handling, canonical geometry, frame/event limits, proxy-label policy, immutable source partitions, and conversion provenance. |
| `datasets/thermal/manifests/T-A2_geometry_calibration_canonical_frame/` | Model-independent geometry candidate comparison selected `G1_FIXED_ASPECT_CROP_BILINEAR` with source orientation and deterministic coordinate semantics. |
| `datasets/thermal/manifests/T-A4_label_semantics_ambiguity/` | Source labels remain immutable; the three-class compatibility layer is explicitly derived and posture-limited. |
| `datasets/thermal/manifests/T-A5_grouping_immutable_split/` and `datasets/thermal/manifests/T-A6_full_conversion_integrity/` | Source partition preservation, absent identity fields, access history, duplicate screening, and real-evaluation-development limitations. |
| `datasets/thermal/manifests/T-B0_offline_model_protocol/` | P0 physical reference, P1 TRAIN-fitted global z-score, and P2 legacy per-frame min-max are separate profiles; learned statistics are TRAIN-only. |
| `datasets/thermal/manifests/T-B1_full_experiment/` and `docs/reports/20260814_Codex_T-B1_Full_Experiment_01.md` | Historical controlled P0/P1/P2 comparison and the observed synthetic-to-real development gap. This is evidence for contract design, not new selection authority. |
| `datasets/thermal/manifests/B6R-P0_public_sdt_materialization/`, `B6R-P1_public_sdt_controlled_training/`, and `B6R-P2_public_sdt_fp32_tflite_export/` | Current public SDT auxiliary lineage, active baseline preprocessing identity, and locked-test non-access boundaries. |
| `scripts/materialize_thermal_b6r_p0_public_sdt.py`, `datasets/thermal/t_b1_preprocessing.py`, and `inference/thermal_interpreter.py` | Direct implementation reconstruction for B6R per-frame min-max, historical P1, and the runtime/canonical representation boundary. |
| `docs/reports/20260828_Codex_Thermal_B6R_B6R-P4_Public_SDT_Software_Only_Robustness_Failure_Mode_Audit_Report_KO_01.md` | Synthetic software-only stress evidence; it does not establish physical-domain robustness or authorize a preprocessing winner. |

The locked public test payload was not opened or used in this audit. Existing
SafeNest/Thermal-90 capture packages were treated as reference-only status and
provenance documentation, not as new model evidence.

### Scope and non-authority

This change is documentation-only. It does not:

- train, tune, quantize, or export a model;
- mutate raw, canonical, or split data;
- inspect or score the locked public test;
- change selectors, runtime code, model manifests, or deployment defaults;
- modify the Team or Integration repository; or
- claim clinical, real-fall, hardware, Raspberry Pi, or production readiness.

## 2. GEO Recommendation

### Recommendation

`TV2_GEOMETRY_CONTRACT = READY_WITH_LIMITATIONS`

Future Candidate A/B data should retain SafeNest-compatible output geometry
`[1, 62, 80, 1]`, using the already-evidenced T-A2 software canonical profile
`G1_FIXED_ASPECT_CROP_BILINEAR`. This proposal does not rewrite the existing
B6R baseline or its artifacts. Any baseline replacement or cross-profile model
comparison requires its own explicit input contract.

### Geometry facts and shape ordering

| Boundary | Contract |
|---|---|
| Distributed SDT source | `image_t`, one thermal channel, source array shape `[H,W] = [480,640]`, encoded `uint16` values. |
| Physical canonical frame | Celsius `float32`, row-major shape `[62,80]`, with a separate validity mask where required. |
| Model input boundary | NHWC shape `[1,62,80,1]`; channel `0` is the single thermal channel. SDT depth members are not part of this contract. |
| Orientation | Source as stored: row `0` is top and increasing rows move down; column `0` is left and increasing columns move right. No rotation or horizontal/vertical flip. |
| Unit boundary | `K = raw / 100`; `°C = (raw - 27315) / 100`. No unverified Thermal-44 compensation is introduced. |

The distributed `480×640` frame already reflects the SDT authors' documented
bilinear enlargement from the native FLIR Lepton 3.5 `120×160` grid. The
canonicalizer must not claim to restore the native grid by resizing the
distributed image again.

### Direct stretch versus aspect-preserving crop

The target aspect ratio is slightly narrower than the distributed source:

```text
source: 640 / 480 = 1.3333333333
target:  80 /  62 = 1.2903225806
```

A direct `480×640 → 62×80` resize therefore uses unequal scale factors:

```text
horizontal: 80 / 640 = 0.1250000000
vertical:   62 / 480 = 0.1291666667
scale-ratio excess ≈ 3.3333%
```

That path slightly compresses horizontal geometry. T-A2 evaluated direct
stretch, fixed-aspect crop, and masked-aspect pad candidates with area,
bilinear, and nearest interpolation. Its selected profile is:

```text
profile:             G1_FIXED_ASPECT_CROP_BILINEAR
crop:                [x0,y0,x1,y1) = [10,0,630,480]
crop size:           620×480
resize output:       H×W = 62×80
horizontal scale:    80 / 620 = 0.1290322581
vertical scale:      62 / 480 = 0.1291666667
scale-ratio excess:  ≈ 0.1042%
source area retained: 96.875%
padding:             none
```

The crop removes only the ten outermost source columns on each side. In the
T-A2 pilot, its minimum transformed person-bbox retention was `0.9977064`,
additional crop loss was `0.0001515` of source-clipped bbox area, and all
mandatory geometry gates passed. These are geometry diagnostics, not model
performance results.

### Proposed deterministic geometry contract

For Candidate A/B canonical input, retain the following exact semantics:

1. Require source shape `[480,640]`, one thermal channel, finite decoded
   values, and the verified source orientation.
2. Convert encoded SDT values to Celsius `float32` before the physical
   canonical frame is emitted.
3. Apply the fixed half-open crop `[10,0,630,480)` in source `x,y` order.
4. Resize the cropped `[480,620]` frame to `[62,80]` using bilinear
   interpolation with `HALF_PIXEL_CENTER` mapping and `EDGE_CLAMPING`.
5. Use `NO_EXPLICIT_ANTIALIAS_PREFILTER`; do not describe coordinate mapping
   as antialiasing.
6. Keep `rotation=0`, `horizontal_flip=false`, and `vertical_flip=false`.
7. Emit finite little-endian `float32` Celsius `[62,80]` plus the required
   provenance and validity information; add the channel dimension only at the
   model input boundary.
8. Fail closed for unsupported shape, channel, unit, orientation, invalid
   pixel, or non-finite input. Do not substitute zeros, ambient values, or a
   data-dependent crop for a failed physical frame.

The existing B6R materializer historically performs a direct PIL bilinear
resize to `62×80` and then per-frame min-max normalization. That implementation
is retained as historical baseline evidence. It is not silently reinterpreted
as the T-A2 physical geometry contract, and this document does not edit it.

### GEO limitations

- Thermal-44 packet ordering, physical orientation, native geometry, and
  hardware calibration remain unverified and deferred to the device-domain
  track.
- `G1_FIXED_ASPECT_CROP_BILINEAR` is a software canonical convention for the
  verified SDT source; it does not prove Thermal-44 optical or packet
  equivalence.
- A future source with a different native shape must not be forced through
  this profile. It needs a separately reviewed source-to-canonical geometry
  mapping or a fail-closed exclusion.

## 3. PRE Recommendation

### Recommendation

`TV2_PREPROCESSING_CONTRACT = READY_WITH_LIMITATIONS`

Use one shared, model-specific preprocessing contract for Candidate A and
Candidate B. The proposed primary is:

```text
P1_TRAIN_FITTED_GLOBAL_ZSCORE
y = (x - mean_TRAIN) / max(std_TRAIN, 1e-6)
```

`mean_TRAIN` and `std_TRAIN` are one scalar mean and standard deviation over
all finite TRAIN pixels after split assignment and physical canonicalization.
They are fit once, serialized, checksummed, and applied unchanged to
DEVELOPMENT, later authorized evaluation roles, and both candidates. No
validation, real-development, or locked-test values may influence the fit.

This is a proposal pending Control-Tower review, not a frozen candidate or
runtime change.

### Reconstructed preprocessing lineage

| Profile | Operation | Fit and semantic boundary | Evidence status |
|---|---|---|---|
| `P0_CANONICAL_CELSIUS_DIRECT` | `y=x` on T-A6 canonical Celsius, then add channel | No fit; preserves physical Celsius exactly. | Scientific physical reference; not calibrated for the legacy normalized model. |
| `P1_TRAIN_FITTED_GLOBAL_ZSCORE` | `(x-mean_TRAIN)/max(std_TRAIN,1e-6)` | One scalar fit on TRAIN only; same statistics everywhere else. | Historical reproducible comparison profile and proposed shared Candidate A/B contract. |
| `P2_LEGACY_PER_FRAME_MINMAX` | `(x-min_frame)/(max_frame-min_frame)` when range is positive | No learned fit; removes frame-level absolute offset and scale. | Compatibility-only reconstruction of the current normalized path. |
| B6R-P0 materialization | Direct PIL bilinear resize, then P2-like per-frame min-max to `[0,1]`; constant frame becomes zeros. | Applied while materializing the public SDT auxiliary arrays. | `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1`; not T-A6 physical canonical data. |
| Legacy runtime | Accepts `[62,80]`, `[62,80,1]`, or `[1,62,80,1]`; finite-checks, then conditionally applies per-frame min-max when the range is outside `[0,1]`; quantizes afterward. | No train-fitted statistics. Constant out-of-range input is clipped; in-range values can pass unchanged. | `inference/thermal_interpreter.py`; compatibility behavior, not a physical-unit contract. |

The historical runtime mismatch is material: T-A6 canonical frames are
physically meaningful Celsius values generally outside `[0,1]`, while the
legacy runtime converts each such frame to a relative min-max image before
inference. The legacy model manifest declares a normalized thermal frame, but
its original reproducible training lineage is not established as T-A6
canonical training.

### Profile assessment

#### P2 per-frame min-max

- Retains within-frame ordering and relative spatial contrast, which can be
  useful when sensor offset or gain is unknown.
- Removes absolute temperature and therefore cannot distinguish a globally
  hotter or colder scene when spatial shape is similar.
- Couples every pixel to the frame extrema. A hot/cold outlier or scene
  artifact can rescale the whole image and change contrast elsewhere.
- Has no learned calibration and is simple to reproduce, but its apparent
  domain robustness is only a relative-image property. The B6R-P4 evidence is
  synthetic software stress, not cross-sensor or physical-domain validation.
- Requires an explicit constant-frame rule. The B6R materializer's zero output
  and the runtime's conditional/clip behavior must not be conflated.

#### P1 TRAIN-fitted global z-score

- Preserves spatial thermal structure while retaining frame-level temperature
  offsets relative to the TRAIN calibration.
- Does not preserve raw Celsius units after transformation; “absolute
  temperature retention” means retention relative to a serialized TRAIN mean
  and scale, not a direct thermometer reading.
- Avoids per-frame extrema coupling and is deterministic when the split,
  canonical tensor, statistics, epsilon, and checksum are fixed.
- Depends on calibration compatibility. A source or device with a shifted
  temperature distribution can move away from the TRAIN scale, as observed in
  the historical real-development characterization.
- Requires strict TRAIN-only fitting and immutable statistics provenance.

#### P0 direct Celsius

- Keeps the physical quantity and absolute temperature information intact,
  with no fit or adaptive scene transform.
- Gives a new model the clearest physical input contract, but the legacy
  normalized model cannot consume it as an equivalent input without a new
  model/input contract.
- Remains a useful physical reference profile; no new evidence justifies
  expanding Candidate A/B preprocessing into an unbounded profile search.

### Historical comparison evidence

In the controlled T-B1 full experiment, the same registered
`SMALL_CNN_BASELINE_V1`, data roles, initialization, and training budget were
used while only preprocessing varied:

| Profile | Synthetic VALIDATION Macro F1 | Synthetic VALIDATION balanced accuracy | HUMAN_FALL proxy recall |
|---|---:|---:|---:|
| P0 direct Celsius | `0.9724235030` | `0.9690833333` | `0.9270` |
| P1 TRAIN-fitted global z-score | **`0.9951295333`** | **`0.9957500000`** | **`0.9940`** |
| P2 legacy per-frame min-max | `0.9916275375` | `0.9920000000` | `0.9855` |

P1 was the historical validation winner under the declared T-B0 rule. A later
multi-seed confirmation reported P1 synthetic validation Macro F1 mean
`0.9950440601`, population standard deviation `0.0005140802`, and range
`0.0012505014`. These results are historical evidence only.

The same selected P1 checkpoint scored Macro F1 `0.5939265236` and
HUMAN_FALL posture-proxy recall `0.446` on `REAL_EVAL_DEVELOPMENT`. That role
is not a pristine locked test, but the contrast with synthetic validation is
large and must prevent any claim that P1 is domain-robust or production-ready.

### Proposed shared Candidate A/B preprocessing contract

1. Input is the T-A2 canonical finite Celsius `float32` frame with shape
   `[N,62,80]` before channel expansion.
2. Fit P1 once from TRAIN only, after immutable group/role assignment. Record
   `mean`, `std`, `effective_std`, epsilon, fit row/pixel counts, TRAIN
   artifact checksum, profile ID, and statistics checksum.
3. Apply the exact stored values to both Candidate A and Candidate B. Do not
   refit per candidate, source, session, frame, DEVELOPMENT partition, or
   real-development role.
4. Do not add implicit clipping, percentile normalization, temperature
   centering, or per-frame fallback to this profile. Any such operation is a
   distinct preregistered profile.
5. Reject non-finite input and record the preprocessing profile ID in every
   model-ready artifact and prediction/evaluation manifest.
6. Compare candidates with the same geometry, labels, split roles, P1
   statistics, and preprocessing implementation. Architecture is the intended
   experimental factor unless a later contract says otherwise.

If Control Tower does not accept P1 as the shared primary because of the
observed domain-gap limitation, the bounded fallback is a preregistered
P1-versus-P2 ablation with the same candidate, seed, split, and evaluation
protocol. It must not become an open-ended preprocessing search, and the
locked public test cannot decide between profiles.

## 4. SPLIT Governance

### Existing SDT roles are immutable

Preserve the official SDT partition membership and the established role names:

| SDT partition / role | Count | Permitted use in the contract |
|---|---:|---|
| `TRAIN` | `32,000` | Model fitting and TRAIN-only P1 statistics. |
| `DEVELOPMENT` | `8,000` | Early stopping, development comparison, and preregistered selection. |
| `LOCKED_PUBLIC_TEST` | `8,000` | No access in this audit; no preprocessing fit, tuning, selection, or metrics here. |

No random frame resplit, hash resplit, deletion, role reassignment, or
retroactive clean-subset invention is permitted.

There is an important lineage qualification. T-A0 through T-A4 used the
materialized official real `test` partition for source/reader, geometry,
temporal-capability, and semantic development evidence; T-A5 therefore records
that no pristine locked test is available for the complete A-stage lineage.
T-A6 and T-B1 call the corresponding development characterization
`REAL_EVAL_DEVELOPMENT`. This access history does not authorize a resplit or a
new locked-test claim. The source membership remains immutable, while any
future final unbiased evaluation requires a separately obtained independent
holdout.

### Mandatory lineage for a new dataset

Every new source must have an auditable chain:

```text
RAW
  → inventory
  → provenance
  → canonicalization
  → label mapping
  → split assignment
  → preprocessing
  → training
```

Split assignment is a first-class artifact and occurs before learned
preprocessing statistics or model-ready materialization. Every descendant
window/frame/sample inherits its source, group, split, label decision, and
quality status.

### Group isolation priority

When metadata exists, choose the strongest complete grouping key in this order:

1. subject;
2. session;
3. sequence/video;
4. scene.

All frames and windows from one group stay in exactly one role. Group IDs are
namespaced by source so that `source_a:subject_01` cannot collide silently with
`source_b:subject_01`. A weaker key may be used only when the stronger key is
absent or demonstrably incomplete, and the downgrade must be recorded.

If subject/session identity is unavailable, record
`LIMITATION_EXPLICIT`. Do not fabricate identity from frame index, filename
order, hash, timestamp absence, or a random surrogate. A frame-only source
cannot support a subject-generalization claim merely because rows were
shuffled.

### Leakage and duplicate policy

- Never randomly split highly correlated video frames, neighboring frames, or
  sequence windows across roles.
- Run exact duplicate checks on source members, decoded arrays, canonical
  frames, and model-ready tensors where applicable.
- Run the declared deterministic near-duplicate diagnostic before comparative
  evaluation and report the scope and non-exhaustiveness of the diagnostic.
- Keep duplicate/near-duplicate witnesses in provenance. Do not move or delete
  rows to conceal leakage; report a diagnostic sensitivity view separately.
- The current T-A6 evidence reports `14,514` TRAIN↔VALIDATION near-duplicate
  pairs and keeps the official roles unchanged.

### Locked-test access policy

The locked public test is unavailable to this worker. For any later authorized
evaluation, its access must be logged with path/configuration, read count,
sample count, metric status, and selection/tuning status. It may be used only
after the model and preprocessing contract are sealed, and its results cannot
feed back into fitting, ranking, threshold choice, architecture choice, or
hyperparameter tuning.

### Existing SafeNest captures

Existing SafeNest/Thermal-90 captures remain `REFERENCE_ONLY`. They may be used
only for:

- orientation sanity;
- geometry sanity; and
- qualitative domain-gap inspection.

They may not be used for model validation, scientific ranking, hyperparameter
tuning, or as a locked-test substitute. Their unverified hardware identity,
unit, orientation, invalid-capture records, and subject limitations remain
explicit rather than being converted into split authority.

## 5. LABEL Contract

### Target classes

The compatibility target is exactly:

| Index | Target | Contract meaning |
|---:|---|---|
| `0` | `NOT_HUMAN` | Frame-scoped absence-of-annotated-human proxy; not a claim that the room is universally empty. |
| `1` | `HUMAN_NORMAL` | Non-fall activity/posture proxy; “normal” is not clinical normality or a safety determination. |
| `2` | `HUMAN_FALL_PROXY` | Fall-compatible posture/event proxy; never a clinically verified fall label. |

`HUMAN_FALL_PROXY ≠ clinically verified fall`. The source annotation and the
derived compatibility target are stored as separate fields. Source labels are
never overwritten.

### Conservative mapping policy

`ACCEPT` means that the evidence is admitted into the target contract; it does
not upgrade a proxy into ground truth. `MAP_WITH_LIMITATION` admits a bounded
derived mapping while preserving its limitation. `EXCLUDE` removes a row from
pure-class training but retains its provenance. `UNRESOLVED` fails closed until
the missing or conflicting evidence is resolved.

| Evidence pattern | Decision | Target | Required interpretation |
|---|---|---|---|
| Explicit, source-verified no-human/empty frame with no conflicting evidence | `ACCEPT` | `NOT_HUMAN` | Frame-level presence equivalence only. |
| Explicit human plus clearly non-fall activity or posture: standing, sitting, walking, crouching, bending, or kneeling | `MAP_WITH_LIMITATION` | `HUMAN_NORMAL` | Keep the activity subtype as a hard-negative slice; this is a non-fall activity proxy, not clinical normality. |
| Authoritative temporal fall-like transition with sequence/event evidence such as onset, impact, or post-event context | `MAP_WITH_LIMITATION` | `HUMAN_FALL_PROXY` | A bounded fall-compatible proxy; not clinical verification and not a safety label. |
| Source-verified static lying posture without temporal transition or impact evidence | `MAP_WITH_LIMITATION` | `HUMAN_FALL_PROXY` | Static posture proxy only; do not describe it as an observed fall event. |
| Reclining, floor exercise, intentional lying, crawling, or other activity that can be either non-fall or fall-compatible | `EXCLUDE` | none | Retain for provenance and transition/ambiguity analysis; do not force into FALL_PROXY to increase count. |
| Partial body, unknown label, missing annotation, conflicting annotation, or insufficient evidence to establish presence/activity | `UNRESOLVED` | none | Fail closed; resolve with new evidence or exclude from pure-class training. |

### SDT mapping under this contract

The existing SDT source label remains in every record:

| SDT source label | Compatibility target | Decision | Boundary |
|---|---|---|---|
| `EMPTY_ROOM` | `NOT_HUMAN` | `ACCEPT` | Frame-scoped presence proxy. |
| `SITTING` | `HUMAN_NORMAL` | `MAP_WITH_LIMITATION` | Non-lying posture proxy; no temporal safety claim. |
| `STANDING` | `HUMAN_NORMAL` | `MAP_WITH_LIMITATION` | Non-lying posture proxy; no temporal safety claim. |
| `LYING` | `HUMAN_FALL_PROXY` | `MAP_WITH_LIMITATION` | Static lying posture proxy; no fall onset, impact, or event evidence. |

SDT does not establish walking, crouching, bending, kneeling, reclining,
floor exercise, crawling, partial-body, transition, impact, or recovery
semantics. Their absence is not a negative example. `AMBIGUOUS` records are
retained for provenance and transition analysis but excluded from pure-class
training.

### Temporal versus static evidence

Future provenance must carry an explicit `event_evidence_type`, at minimum:

```text
TEMPORAL_FALL_EVIDENCE
STATIC_LYING_POSTURE
NON_FALL_ACTIVITY_OR_POSTURE
NO_ANNOTATED_HUMAN
AMBIGUOUS
UNKNOWN
```

Temporal fall evidence and static lying posture must remain separate slices in
counts, confusion matrices, and failure analysis. A temporal label still maps
to the proxy class under limitation; it does not become clinical fall truth.

## 6. Cross-Dataset Rules

Datasets are not merged by this worker. A future merge requires the D0–D3
evidence path, Control-Tower review, and a new auditable manifest.

| Rule | Mandatory contract |
|---|---|
| Source identity | Namespace each source with stable `source_id`, dataset/version, DOI or authoritative URI, license evidence, retrieval/access date, archive/member identity, and source checksum. |
| Source provenance | Preserve subject, session, recording, sequence/video, scene, timestamp or window bounds, source member/row/frame, source geometry, unit, channel semantics, extraction profile, and quality status. Missing values remain explicit. |
| Dataset-specific metadata | Keep source-native metadata in a namespaced record. Do not flatten fields with different meanings or silently coerce absent values into defaults. |
| Label provenance | Store original label/token, annotation source/version, mapping policy ID, mapping decision, target class if any, limitation reason, event-evidence type, and reviewer/quality status. |
| Sequence IDs | Use authoritative sequence/video/recording IDs where present. Never derive a fake sequence from neighboring frame numbers or archive order. |
| Duplicate detection | Check exact source/member, decoded, canonical, and model-ready identities; perform deterministic near-duplicate screening across and within sources before evaluation. Preserve witnesses and disclose non-exhaustive scope. |
| Group/split inheritance | Namespace group IDs by source and assign complete groups to one role. Derived windows, augmentations, and representations inherit the parent role. |
| Source balancing | Split and leakage-audit first. Only then apply a preregistered training sampler, cap, or weight. Do not duplicate or rebalance validation/locked-test membership. Report raw and effective per-source counts. |
| Per-source metrics | Report aggregate metrics alongside per-source, per-domain, per-label-decision, temporal/static, and hard-negative slices. A strong aggregate must not hide a failed source. |
| Hard negatives | Preserve explicit slices for standing, sitting, walking, crouching, bending, kneeling, partial-body, no-human, and ambiguity where available. Do not infer unrepresented activities. |
| Representation compatibility | Confirm geometry, unit, orientation, channel semantics, invalid-pixel policy, and preprocessing compatibility per source before concatenation. A common target shape alone is insufficient. |
| License and release | Retain source-specific use/release restrictions. The strictest applicable restriction governs a merged artifact until separately reviewed. |

The first future merge decision must state which sources are included, which are
kept reference-only, which labels are excluded/unresolved, how groups are
isolated, how sources are balanced, and how every source receives its own
metrics. No source balancing or label harmonization may erase provenance.

## 7. G1 Readiness Matrix

| Node | Status | Blocking issue / limitation |
|---|---|---|
| GEO | `READY_WITH_LIMITATIONS` | The SDT software profile is deterministic and aspect-preserving, but Thermal-44 native geometry, packet ordering, physical orientation, and device equivalence remain unverified. |
| PRE | `READY_WITH_LIMITATIONS` | P1 is a bounded shared proposal supported by historical controlled evidence; P2 remains a legacy compatibility reference, and the synthetic-to-real development gap prevents a robustness or production claim. |
| SPLIT | `READY_WITH_LIMITATIONS` | SDT identity is absent below source partition level; `14,514` TRAIN↔VALIDATION near-duplicate pairs remain disclosed; no pristine independent locked holdout exists for the full A-stage lineage. |
| LABEL | `READY_WITH_LIMITATIONS` | Three classes are proxy semantics; static lying is not a temporal fall event; ambiguous activities are excluded/unresolved; no clinical or safety label is established. |

The contract foundation is reviewable, but G1 also depends on the active data
path: TV2-D0 discovery, TV2-D1 license/provenance/access, TV2-D2
representation/label compatibility, TV2-D3 expansion decision, and TV2-H0
hard-negative evidence. Those items remain outside this documentation-only
worker scope and were not marked complete here.

## 8. G1 Recommendation

```text
G1_READY_PENDING_D0_D3
```

Meaning:

- GEO, PRE, SPLIT, and LABEL have bounded, reviewable proposals with explicit
  limitations.
- Control Tower must review and accept or revise these contracts.
- D0–D3 and the hard-negative path remain pending; this worker does not close
  G1 and does not claim `G1 PASS`.
- Candidate A remains **DATA-CORRECTIVE COMPACT SPATIAL CNN**.
- `SMALL_CNN_BASELINE_V1` remains a strong reference candidate only; it is not
  frozen as Candidate A.
- Candidate B remains conditional and is not frozen.

The next authorized work is evidence completion and Control-Tower review, not
training by implication. Any later candidate experiment must inherit the
accepted geometry, shared preprocessing, immutable split/access policy, and
conservative proxy-label contract, then report source and hard-negative slices
without upgrading proxy results into clinical or production claims.
