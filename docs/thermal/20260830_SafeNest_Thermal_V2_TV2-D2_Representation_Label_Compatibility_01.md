# SafeNest Thermal V2 — TV2-D2 Representation, Label, and Canonical Compatibility

- Worker: `제1그록4.5`
- Date: 2026-08-30
- Repository: `sheepmeat/test`
- Phase: `TV2-D2`
- Branch: `thermal-v2/tv2-d2-representation-label-compatibility`
- Startup base: `origin/main` at `5fd4b0d42160198ce48c86cdc2b9d89a10d24a0d` (TV2-D1 merge, PR `#191`)
- Training authorization: `NONE`
- Dataset merge authorization: `NONE`
- `LOCKED_PUBLIC_TEST_ACCESS`: `0`
- G1 freeze: `NOT_CLAIMED`
- D2 recommendation: `PASS_WITH_LIMITATIONS`

This report answers which D1-admitted sources can defensibly move toward D3, under what representation lane, geometry adapter, label semantics, grouping contract, frame-supervision rule, and preprocessing boundary. It does not train, merge datasets, freeze G1, or select a model.

Companion machine-readable contract: `config/thermal/tv2_d2_source_compatibility.json`. The JSON restates lane, geometry, label, frame-supervision, grouping, quality, and D3 recommendation fields so a later verification worker can check them without re-parsing this prose. No raw payload is stored in Git.

## 1. Executive Conclusion

TV2-D2 is **`PASS_WITH_LIMITATIONS`**.

The D1 representation split is real and must remain a hard pipeline boundary:

```text
P — PHYSICAL_TEMP_LANE
  QUIDA calibrated MLX90640 Celsius rows
  eHomeSeniors calibrated MLX90640 IR 1..768 [C] fields
  IPHD base K×100 thermal  (REFERENCE_ONLY; different sensor family)

I — INTENSITY_LANE
  Thermal-IM decoded RGBT_T.mp4 uint8 visual intensity
```

Concatenating Celsius matrices with rendered intensity video, or treating eHomeSeniors raw MLX words as a second temperature image, is scientifically invalid. No common representation that would justify that merge was found.

Serious D3 work is limited to QUIDA, calibrated eHomeSeniors MLX90640, and Thermal-IM. Their D3 roles are not interchangeable:

| Source | D3 recommendation | Why this is not training membership |
|---|---|---|
| QUIDA | `ADVANCE_TO_D3_WITH_UNRESOLVED_LABEL_LIMIT` | Native 32×24 Celsius-compatible frames and subject IDs exist; frame-level FALL_PROXY labels do not. |
| eHomeSeniors calibrated MLX90640 | `ADVANCE_TO_D3_WITH_UNRESOLVED_LABEL_LIMIT` | Calibrated 768-field extraction is contractable; file-level staged-fall protocol is not frame supervision. |
| Thermal-IM | `ADVANCE_TO_D3_SUPPLEMENTAL` | Separate intensity lane; action intervals are frame-derivable; no fall labels; grouping only partial. |
| eHomeSeniors raw MLX | `REFERENCE_ONLY` / `EXCLUDED_FROM_FRAME_MODEL_INPUT` | Raw words are not Celsius. |
| eHomeSeniors Omron | `REFERENCE_ONLY` / `EXCLUDED` | 32 linear-array values cannot feed a 62×80 spatial posture model without fabricating geometry. |
| IPHD base | `REFERENCE_ONLY` | Different sensor, boxes not posture/fall labels, asset terms unverified. |
| TF-66, IPHPDT | `HOLD_FOR_ADDITIONAL_METADATA` | Still access-gated; not promoted from paper descriptions. |

Candidate A/B remain frame classifiers. QUIDA and eHomeSeniors are event/file temporal sources. That mismatch is not solved by inventing `fall timestamp ± N seconds`. The QUIDA paper’s “e.g., 2 s” window is an author analysis parameter, not an authoritative dataset interval.

`P1_TRAIN_FITTED_GLOBAL_ZSCORE` remains a G1 hypothesis. D2 classifies it as `P1_NOT_READY`. This document does not close G1.

## 2. D1 Inputs and D2 Boundary

Verified on this branch: `docs/thermal/20260830_SafeNest_Thermal_V2_TV2-D1_Source_Access_License_Payload_Verification_01.md` is present on `origin/main` at `5fd4b0d42160198ce48c86cdc2b9d89a10d24a0d`.

Authoritative D1 decisions consumed:

```text
TF-66        = HOLD_PENDING_ACCESS
IPHD base    = REFERENCE_ONLY
IPHPDT       = HOLD_PENDING_ACCESS
Thermal-IM   = ADMIT_TO_D2_WITH_LIMITATIONS
QUIDA        = ADMIT_TO_D2_WITH_LIMITATIONS
eHomeSeniors = ADMIT_TO_D2_WITH_LIMITATIONS
```

D2 therefore restricts serious source analysis to QUIDA, eHomeSeniors, and Thermal-IM. IPHD is reference-only. TF-66 and IPHPDT are not promoted.

Additional evidence read: TV2-D0, G1 contract foundation, TV2-H0, TV2-A0, the master execution map, T-A2 geometry report, T-A0 eHomeSeniors identity notes, `datasets/thermal/label_semantics.py`, QUIDA PeerJ methods text, and the eHomeSeniors Sensors methods text. Where prose and executable/payload evidence conflict, payload evidence wins and the conflict is named.

D1 leftover official archives were re-inspected outside Git (`/tmp` D1 download tree). No payload was copied into this repository.

D2 does not: train; merge datasets; freeze PRE/G1; reuse the SDT crop as a QUIDA/eHome/Thermal-IM adapter; access `LOCKED_PUBLIC_TEST`; edit the execution map; change Team/Integration/Pi artifacts; or treat SafeNest captures as training evidence.

## 3. Representation-Lane Decision

### P — PHYSICAL_TEMP_LANE

This lane is scientifically coherent as a **physical-temperature family**, not as a claim of identical distribution.

Members:

- QUIDA: paper-stated Celsius, 768 decimal values per Unix-timestamped row, MLX90640 32×24.
- eHomeSeniors calibrated MLX90640: labeled `IR 1 [C]` … `IR 768 [C]`, paper-stated 32×24 heat image.

Reference only:

- IPHD base: documented K×100 16-bit PNG, FLIR Lepton v3, 160×120 original. Different sensor, different invalid encoding (zeros from depth registration). It may inform physical-unit discussion; it must not be concatenated into an MLX90640 TRAIN tensor.

Excluded from P-lane model input:

- eHomeSeniors raw MLX words.
- eHomeSeniors Omron 32-value arrays.
- Thermal-IM intensity video.

Same sensor family does **not** imply identical distribution. QUIDA subject-level bulk ranges are typically about 20–30 °C with rare extremes; sampled eHomeSeniors calibrated files were about 13–32 °C. Mount height, FOV, room, and protocol differ. A later shared P1 statistic, if ever authorized, would have to be TRAIN-fitted after D3 membership and would still be a calibration to that TRAIN mix, not a proof of domain match.

Candidate conceptual pipeline, not an implementation:

```text
verified physical temperature
→ source-specific invalid-value handling   (policy NOT FROZEN)
→ source-specific geometry adapter         (adapter NOT FROZEN)
→ [62,80,1] Celsius float32
→ future TRAIN-fitted preprocessing        (P1 NOT READY)
```

### I — INTENSITY_LANE

Thermal-IM is the only D1-admitted intensity member. Decoded frames are `uint8` 3-channel visual samples at 288×384, not a radiometric matrix. Role:

```text
separate future training lane
and/or hard-negative-only supplemental lane
NOT diagnostic/reference-only
NOT rejected from D3
NEVER fabricated Celsius
```

It must not enter the P-lane raw tensor, P1 fit, or any concatenated “thermal” array.

## 4. QUIDA Compatibility

Official payload re-inspected from the D1 OSF archive (`dataset.zip`, SHA-256 `c312975bb91d436dcf5bec1c57dc1a857de0cef3c1a04c70d5267f50e662b47b`).

### 4.1 Payload contract

Each `subject_N/ir_camera.csv` is headerless comma-separated text. Every thermal row is width 769: Unix timestamp plus 768 decimal values. All 10 subject files parse with uniform width; `parse_fail = 0`; `nonfinite = 0`. Total frames = **11,877**. The paper states columns 2–769 are Celsius for a 32×24 matrix. The CSV itself has no unit metadata.

The archive’s top-level `ir_camera.csv` is **not** a thermal frame file (small 10-column count table). D2 uses only `subject_*/ir_camera.csv`.

`falls.csv` is 10×10: rows = fall instances, columns = subjects 1–10. All 100 timestamps fall inside the corresponding subject thermal range. Nearest-frame absolute offset is sub-sampling-interval (subject-1 median 0.069 s, max 0.196 s).

### 4.2 Orientation

```text
ORIENTATION_NOT_VERIFIABLE
```

Checked:

- Row-major vs column-major: **not documented** in the CSV, OSF archive, or paper beyond “32 × 24 matrix”.
- Width/height ordering: sensor is MLX90640 32×24; stored vector order is not labeled.
- Transpose: not specified.
- Physical mount: desktop, 1 m above ground, 1.5 m from the fall area. No flip/rotation metadata in the files.

A spatial-neighbor diagnostic was computed and is **not** treated as orientation proof. `reshape(24, 32)` has high horizontal and vertical autocorrelation (mean ≈ 0.919 / 0.925). `reshape(32, 24)` preserves horizontal correlation (≈ 0.900) but collapses vertical correlation (≈ 0.302). That pattern is consistent with a 24×32 row-major packing candidate and with common MLX90640 RAM dumps. It does not verify which edge is physically “up”, whether the capture software transposed the frame, or whether a later adapter must flip/rotate.

D2 therefore records a **packing-order candidate** `H=24, W=32` and keeps orientation `ORIENTATION_NOT_VERIFIABLE`. Do not guess a freeze.

### 4.3 Quality

```text
QUALITY_POLICY_NOT_FROZEN
```

Quantified over all 11,877 × 768 = 9,121,536 thermal values:

| Quantity | Value |
|---|---:|
| Non-finite | 0 |
| Duplicate timestamps | 0 |
| Non-monotonic timestamps | 0 |
| Gaps > 2 s | 0 |
| Median Δt | 0.3845 s |
| Δt 5th–95th percentile | 0.218–0.478 s |
| Δt min / max | 0.183 / 0.603 s |
| Global min / max | −3.46 / 928.26 |
| Values < 0 | 2 |
| Values < 10 | 17 |
| Values > 50 | 4 |
| Values > 80 | 2 |
| Values > 100 | 1 |
| Values > 300 | 1 |

Extremes are rare and concentrated (subject 10 holds the 928.26 value; subject 3 holds the two negatives). Subject-level 1st–99th percentiles remain in a plausible indoor band even when extrema do not. No clipping threshold is invented. A later quality contract may fail-close non-finite values (none observed) and **flag** physically implausible pixels without treating a numeric cutoff as frozen here.

Sampling is variable, not a clean video FPS. Temporal spikes of the kind that would show as large Δt gaps were not observed; the variability is sub-second jitter around the paper’s ~2.6 Hz setting.

### 4.4 Geometry

Target remains `[1,62,80,1]` (`H=62, W=80`, aspect 80/62 ≈ 1.2903). Using the packing candidate 24×32 (aspect 32/24 ≈ 1.3333):

| Adapter | Scale | Aspect distortion | Interpolation | Known loss |
|---|---|---|---|---|
| Direct 24×32 → 62×80 | sx=2.500, sy=2.583 | ≈ 3.33% extra vertical stretch | required upsample | native 768 pixels expanded to 4,960; low-resolution structure is amplified, not recovered |
| Aspect-preserving resize to 60×80, pad to 62×80 | sx=sy=2.500 | 0% | required upsample | 2 padded rows (about 3.2% of canonical height); no SDT-style crop of native content |
| SDT `G1_FIXED_ASPECT_CROP_BILINEAR` `[10,0,630,480)` | n/a | n/a | n/a | **forbidden reuse** — that crop is SDT 480×640 evidence |

No source-specific crop is justified. Status: `GEOMETRY_NOT_FROZEN`.

### 4.5 Frame labels

```text
FRAME_SUPERVISION_UNRESOLVED
```

QUIDA supplies temporal fall **instants**, not frame classes. The paper describes a researcher-chosen window “determined by user-defined parameters, e.g., 2 s” before and after each annotated instant. That is an example analysis parameter, not a dataset-authoritative event interval. Falls.csv has no duration field.

D2 therefore does **not** adopt `timestamp ± 2 s` or any other N. A diagnostic count only: a ±2 s example would mark about 6–11% of each subject’s frames. That fraction is not a label.

Also forbidden: labeling every frame of a fall-containing recording as `HUMAN_FALL_PROXY`. Each subject file is a long contiguous walk-plus-fall protocol.

Walking-without-falling context exists in the protocol but is not independently frame-labeled.

### 4.6 Grouping

Subject identity is explicit (`subject_1` … `subject_10`). The minimum later split unit is subject. Random frames or windows across the same subject are forbidden. Session/scene fields are absent (`GROUPING_PARTIAL` at D1; subject-disjoint split later = `YES`).

## 5. eHomeSeniors Compatibility

Official MDPI supplementary archive re-inspected (SHA-256 `e0b158800478b4e6f979bbc650c2fb51b171b6f872d537f0ad9de8d682a1773a`). 90 Melexis CSVs, 90 Omron CSVs, 180 `.mat` files. These are **not** one image representation.

### 5.1 Calibrated MLX90640 extraction contract

Candidate contract from the representative file `eHomeSeniors dataset/melexis sensor/melexis-G1-1-f01.csv` and paper text:

```text
delimiter              = |
row 0                  = metadata (timestamp, sensor model, emissivity, config regs, …)
row 1                  = field labels
data rows              = start at row index 2
col 0                  = timestamp HH:MM:SS
col 1                  = sensor model (example: 90640-D87 4E57-2.65-0x33)
cols [2, 770)          = IR 1 [C] … IR 768 [C]   (768 calibrated temperatures)
remaining columns      = mixed Private*/Ta [C]/Raw N  — NOT the spatial temperature image
dtype                  = decimal text → float
physical unit          = Celsius (field suffix [C] + paper)
```

Representative file: 880 data rows, all width 1668, `parse_fail = 0`, calibrated finite, range 14.09–27.31 °C. Sampled additional Melexis CSVs stayed in about 12.9–32.0 °C with zero non-finite calibrated values.

Headers do **not** freeze 2-D order: labels are `IR n [C]`, not `(row, col)`. Spatial autocorrelation again favors `reshape(24, 32)` over `reshape(32, 24)` (vertical correlation ≈ 0.85 vs ≈ −0.02). Physical mount is wall, 1.2 m, 37.5° H / 55° V FOV. Flip/rotation of the stored vector is still `ORIENTATION_NOT_VERIFIABLE`.

Timestamps are second-resolution. The representative file has 57 unique `HH:MM:SS` values across 880 data rows. Sub-second order is file-row order, not a distinct timestamp. Metadata row 0 must not be used as a data index.

Header/data width mismatch is explicit: label row has 1604 fields; data rows have 1668. An empty label sits at index 770 before `Private 1`. D2 uses the paper + `IR 1..768 [C]` span for calibrated extraction and does not invent names for the extra unlabeled data fields.

`.mat` files are a parallel MATLAB container of the same release, not a second geometry. They are not required for the calibrated-CSV contract.

### 5.2 Raw MLX fields

```text
EXCLUDED_FROM_FRAME_MODEL_INPUT
```

also `REFERENCE_ONLY` for datasheet/debug provenance.

The tail includes `Raw 1` … `Raw 768` labels plus Private/Ta fields. First-row numeric tail values include magnitudes such as −12748 and 32767. The paper says temperatures are obtained from raw data “through formulas documented for the sensor.” This repository has no executable, source-verified decoder that maps those words onto Celsius for these files. Raw words must never be assumed Celsius and must never be concatenated with the `IR n [C]` image.

`SEPARATE_FUTURE_DECODING_LANE` is not opened: there is no verified decoding evidence here.

### 5.3 Omron

```text
EXCLUDED
```

also `REFERENCE_ONLY` / `SEPARATE_MODALITY` as a non-image thermal array.

Paper + payload: 33 semicolon-separated fields (timestamp + 32 temperatures) from four 8-pixel D6T-8L-06 arrays (upper pair ≈ 1 m, lower pair ≈ 0.1 m). Representative range 18.2–24.9 °C. This is two stacked 1×16 (or four 1×8) linear measurements of a standing/fallen body, not a 2-D posture image. Interpolating 32 values into 62×80 would fabricate spatial structure. It cannot meaningfully feed a 62×80 spatial human-posture frame classifier.

### 5.4 Labels

```text
FRAME_SUPERVISION_UNRESOLVED
```

Original evidence is file-name fall-type IDs `f01`–`f15` plus a protocol of five staged falls per file (three in `omron-G2-3-f15`). The paper states ordinary activity immediately before a fall may include standing, walking, sitting, or lying down, and that this context is **not** independently labeled. Paper fall-duration histograms (group-1 mean 2.62 s, group-2 mean 2.20 s) are analysis results from barycenter rules, not per-frame labels in the files.

Forbidden: marking all frames in a fall file as `HUMAN_FALL_PROXY`.

### 5.5 Grouping

Volunteer identity is explicit (`G1-1` … `G2-3`; six volunteers). Minimum split unit is volunteer. No frame/file random splitting across one volunteer. Group 1 = performing artists coached to emulate older-adult falls; group 2 = healthy young volunteers. That grouping must remain provenance, not a clinical age label.

## 6. Thermal-IM Compatibility

Official clip archives from D1 were decoded (not re-downloaded into Git).

### 6.1 Decoded representation

OpenCV decode of the leftover D1 members:

| Clip (D1 identity) | Decoded shape | dtype | range | FPS |
|---|---|---|---|---|
| `20220613_7_split6` `RGBT_T.mp4` | 63 × 288 × 384 × 3 | `uint8` | 35–255 | 15 |
| `20220613_9_split7` `RGBT_T.mp4` | 53 × 288 × 384 × 3 | `uint8` | 0–255 | 15 |

README geometry 288×384 (H×W) matches decoded height×width. D1’s MP4 sample-entry 384×288 is the same pair in W×H. FourCC from OpenCV: `FMP4` / MPEG-4 visual (`mp4v` in D1).

Channels are **not** byte-identical. Unique RGB colors per sample frame (≈ 155–174) approximately equal unique grayscale values, with small BGR mean offsets. That is consistent with a compressed grayscale or limited false-color visualization, **not** with a radiometric Celsius matrix and not with full natural-color photography. Compression posterization is present. No physical-unit metadata.

This is `NON_RADIOMETRIC_THERMAL_INTENSITY`. Do not call it physical temperature. Do not invert a colormap into fabricated Celsius.

`annotation.json`: one inspected clip is `[]`; the other has `{start: 0.63, end: 1.35, action: "touch", object: "book"}`. Empty `[]` is not `NOT_HUMAN`.

### 6.2 Geometry

Native 288×384, aspect 384/288 = 1.3333, same ratio as 32×24.

| Adapter | Aspect distortion | Interpolation | Known loss |
|---|---|---|---|
| Direct 288×384 → 62×80 | ≈ 3.33% extra vertical stretch | required **downsample** | most native spatial detail discarded (110,592 → 4,960 pixels) |
| Aspect-preserving to 60×80, pad to 62×80 | 0% | downsample | 2 padded rows; still large information loss |
| Source-specific crop | none justified from inspected clips | n/a | pose/extrinsic arrays exist in `info.npz` but were not used to invent a body crop |

SDT crop coordinates are irrelevant. Status: `GEOMETRY_COMPATIBLE_WITH_LIMITATIONS` (native geometry known; adapter not frozen; downsampling loss is material).

### 6.3 Semantics

Source tokens are preserved. Recommended mapping is advisory and does **not** amend the LABEL contract:

| Original evidence | Candidate class | Subtype | D2 use |
|---|---|---|---|
| `sit sofa` / `sit chair` / `sit stool` / `sit desk` | `HUMAN_NORMAL` | `NON_FALL_ACTIVITY_OR_POSTURE` | `MAP_WITH_LIMITATION` |
| `lie sofa` | none for pure-class training | `STATIC_LYING_POSTURE` | `EXCLUDE` (G1 reclining/intentional-lying rule); **not** `HUMAN_NORMAL`; **not** automatically `HUMAN_FALL_PROXY` |
| `touch …` object interactions | none or `HUMAN_NORMAL` only with low confidence | `NON_FALL_ACTIVITY_OR_POSTURE` | conservative: prefer `EXCLUDE` from FALL_PROXY tests that need a clean posture class |
| `push-ups` / `sit-ups` / `leg-stretching` / `take-off clothes/shoes` | none | `NON_FALL_ACTIVITY_OR_POSTURE` | `EXCLUDE` (floor exercise / garment; G1 ambiguous-activity rule) |
| empty `annotation.json` | none | `UNKNOWN` | `UNRESOLVED`; not `NOT_HUMAN` |
| no source token for fall | none | n/a | not a positive fall source |

D0 prose that provisionally listed walking/kneeling is **overridden** by D1’s verified action-object vocabulary. Those tokens were not present in the official chart/selected annotations.

### 6.4 Grouping

```text
GROUPING_COMPATIBILITY = PARTIAL
```

README documents `meta.csv` fields: actor, room, scene, train/validation/test, plus clip-level `annotation.json`. Clip archives inspected in D1/D2 do not contain `meta.csv`. Actor overlap between official splits is therefore not independently audited here. Minimum grouping keys if/when `meta.csv` is obtained: actor, then room, scene, clip. Do not randomly split frames inside a clip.

## 7. Geometry Compatibility Matrix

Target: `[1,62,80,1]`. The accepted SDT adapter `G1_FIXED_ASPECT_CROP_BILINEAR` is source-specific SDT evidence and is **not** the adapter for these sources.

| Source | Native Geometry | Orientation | Candidate Adapter | Aspect Distortion | Interpolation | Known Loss | Status |
|---|---|---|---|---|---|---|---|
| QUIDA | 32×24 / 768-vector; packing candidate 24×32 | `ORIENTATION_NOT_VERIFIABLE` | aspect-preserving 60×80 + pad, or direct 62×80; **not** SDT crop | direct ≈ 3.33% vertical; pad path 0% | bilinear upsample (not frozen) | native detail amplified; pad ≈ 2 rows | `GEOMETRY_NOT_FROZEN` |
| eHomeSeniors calibrated MLX | 32×24 / 768 `IR n [C]` | `ORIENTATION_NOT_VERIFIABLE` | same family as QUIDA, source-specific, not SDT crop | same as QUIDA if 24×32 | bilinear upsample (not frozen) | same upsample amplification | `GEOMETRY_NOT_FROZEN` |
| eHomeSeniors raw MLX | not a temperature image | n/a | none | n/a | n/a | using raw as image is a unit error | `GEOMETRY_INCOMPATIBLE` |
| eHomeSeniors Omron | 32 linear values (4×8) | not a 2-D posture image | none for 62×80 spatial CNN/MLP | n/a | interpolation would fabricate 2-D structure | all spatial-posture information not present | `GEOMETRY_INCOMPATIBLE` |
| Thermal-IM | 288×384×3 `uint8` | decoded top-left origin; no flip metadata | aspect-preserving 60×80 + pad, or direct 62×80; optional single-channel luminance | direct ≈ 3.33% vertical; pad path 0% | downsample | large native-detail loss | `GEOMETRY_COMPATIBLE_WITH_LIMITATIONS` |
| IPHD base (reference) | 160×120 or registered 213×120 | not re-verified in D2 | would need its own adapter | not computed as a D3 member | n/a | zeros from registration | `GEOMETRY_NOT_FROZEN` |

## 8. Label / Semantic Compatibility Matrix

SafeNest class order remains `0 NOT_HUMAN`, `1 HUMAN_NORMAL`, `2 HUMAN_FALL_PROXY`. Static lying is not an actual fall. Staged events are not clinical/natural falls.

| Source | Original Evidence | Evidence Type | Candidate SafeNest Class | Subtype | Confidence | D2 Use |
|---|---|---|---|---|---|---|
| QUIDA | `falls.csv` Unix instants (100) | `TEMPORAL_FALL_EVIDENCE` | `HUMAN_FALL_PROXY` only if a later verified interval exists | staged laboratory fall | low until interval exists | do not frame-label yet |
| QUIDA | walking-without-falling protocol | `NON_FALL_ACTIVITY_OR_POSTURE` | `HUMAN_NORMAL` only if a later verified complement rule exists | walking | low | not independently frame-labeled |
| eHomeSeniors | file `f01`–`f15` | `TEMPORAL_FALL_EVIDENCE` | `HUMAN_FALL_PROXY` only with future onset/end | staged volunteer fall | low at frame scope | file/event provenance only |
| eHomeSeniors | unlabeled pre-fall standing/walking/sitting/lying | `NON_FALL_ACTIVITY_OR_POSTURE` / `UNKNOWN` | none | unlabeled context | none | do not treat as hard-negative labels |
| Thermal-IM | `sit sofa/chair/stool/desk` | `NON_FALL_ACTIVITY_OR_POSTURE` | `HUMAN_NORMAL` | seated activity | medium | `MAP_WITH_LIMITATION` |
| Thermal-IM | `lie sofa` | `STATIC_LYING_POSTURE` | none (G1 reclining exclude) | furniture recline | medium that it is not a fall | `EXCLUDE`; not `HUMAN_NORMAL` |
| Thermal-IM | `touch *` | `NON_FALL_ACTIVITY_OR_POSTURE` | none preferred | object interaction | low as posture class | conservative exclude from pure-class |
| Thermal-IM | exercise / garment actions | `NON_FALL_ACTIVITY_OR_POSTURE` | none | G1 ambiguous activity | medium | `EXCLUDE` |
| Thermal-IM | empty `annotation.json` | `UNKNOWN` | none | missing action list | high that it is not empty-room | `UNRESOLVED`; not `NOT_HUMAN` |
| IPHD base | human box class 0 | presence only | none for 3-class posture | box | n/a | `REFERENCE_ONLY` |
| IPHD `lying` (paper, not payload) | static posture name | `STATIC_LYING_POSTURE` | not used | not a fall | n/a | derivative still `HOLD_PENDING_ACCESS` |

## 9. Frame-Supervision Compatibility

This is a mandatory D2 output. Candidate A/B are frame classifiers.

| Source | Status | Why |
|---|---|---|
| QUIDA | `FRAME_SUPERVISION_UNRESOLVED` | Fall instants exist; no authoritative duration/interval; paper ±2 s is an example parameter; cannot label whole recordings FALL_PROXY. |
| eHomeSeniors calibrated MLX | `FRAME_SUPERVISION_UNRESOLVED` | File-level staged-fall protocol; five falls per file without framewise onset/end; preceding ADL unlabeled. |
| eHomeSeniors Omron | `FRAME_SUPERVISION_UNRESOLVED` | Same protocol, and geometry already incompatible. |
| Thermal-IM | `FRAME_SUPERVISION_DERIVABLE_WITH_VERIFIED_RULE` | `annotation.json` `start`/`end` seconds at documented 15 FPS define action-interval frames. Outside-interval frames stay unlabeled. Empty list ≠ `NOT_HUMAN`. No fall class. |
| IPHD base | `FRAME_SUPERVISION_NOT_DEFENSIBLE` | Frame order was removed; boxes are not 3-class posture/fall labels. |

Do not close the QUIDA/eHome gap by inventing event windows in D2. D3 may design an annotation or exclusion policy; it may not silently adopt ±N seconds.

## 10. Grouping / Leakage Compatibility

| Source | Minimum split unit | Additional keys | Leakage if ignored | Later subject-disjoint |
|---|---|---|---|---|
| QUIDA | subject (`subject_1`–`subject_10`) | recording = per-subject `ir_camera.csv`; time = Unix | high: long contiguous recordings | `YES` |
| eHomeSeniors | volunteer (`GX-Y`) | group, fall-type file, row order | high: adjacent frames and repeated falls in one file | `YES` |
| Thermal-IM | actor if `meta.csv` obtained; else clip as temporary weaker key with `LIMITATION_EXPLICIT` | room, scene, official split, clip | high inside a clip; actor overlap across official splits **not** audited | `POSSIBLY` / `GROUPING_COMPATIBILITY=PARTIAL` |
| IPHD | not verified | video ID + frame ID | correlated frames likely | `NOT_VERIFIABLE` |

G1 isolation order (subject → session → sequence/video → scene) applies. Namespace groups by `source_id`. Do not fabricate identity.

## 11. Quality / Invalid-Value Handling

No clipping threshold is frozen.

| Source | Observed quality | Handling implication |
|---|---|---|
| QUIDA | All finite; no duplicate/non-monotonic timestamps; rare extrema (4 pixels > 50 °C of 9.12e6; one 928 °C; two negatives) | Fail-closed on non-finite (none seen). Flag extrema in provenance. Do not clip to an invented band. |
| eHomeSeniors calibrated | Sampled files finite and indoor-plausible; second-level timestamps collide | Preserve row order as sub-second sequence. Do not drop metadata rows into the image. |
| eHomeSeniors raw | Integer-like words, including 32767-scale values | Exclude from frame-model input. |
| Thermal-IM | `uint8` compressed visual; limited unique colors | Record compression/palette limitation; no invalid-temperature mask exists. |
| IPHD (reference) | Documented zero registration errors | Preserve masks; zeros are not ambient Celsius. |

```text
QUALITY_POLICY_NOT_FROZEN
```

for all serious D3 candidates.

## 12. PRE Compatibility Decision

### A. Can QUIDA + calibrated eHomeSeniors share a physical-temperature pre-PRE lane?

```text
YES_WITH_LIMITATIONS
```

Both are MLX90640 calibrated Celsius 32×24-class arrays. Limitations: orientation not frozen; distributions are not demonstrated identical; quality policy not frozen; frame labels unresolved; QUIDA asset terms unverified. Sharing a **lane** is not sharing a fitted P1 statistic.

### B. Can Thermal-IM join the same raw physical-temperature lane?

```text
NO
```

Intensity ≠ Celsius. No contrary evidence.

### C. P1 status

```text
P1_NOT_READY
```

`P1_TRAIN_FITTED_GLOBAL_ZSCORE` remains the G1 hypothesis (`y = (x − mean_TRAIN) / max(std_TRAIN, 1e-6)` on finite TRAIN pixels after canonicalization). It cannot freeze here: D3 membership is unset, two representation lanes exist, QUIDA/eHome distributions are unpooled, orientation/geometry adapters are unfrozen, and Control Tower owns G1. Historical T-B1 P1 results are SDT-regime evidence, not permission to fit P1 on new sources.

### D. Thermal-IM representation boundary if it remains useful

Required explicit boundary:

```text
lane_id            = I_INTENSITY_LANE
decoded_dtype      = uint8
native_hw          = [288, 384]
channel_policy     = declare luminance or keep 3-channel visual; do not call either Celsius
value_range        = [0, 255] as stored
physical_units     = NONE
conversion_to_C    = FORBIDDEN
PRE statistics     = must not share P-lane mean/std
concatenation      = FORBIDDEN with QUIDA/eHome/IPHD tensors
```

A later I-lane model, if ever authorized, needs its own geometry adapter, its own TRAIN-fitted statistics, and source-token provenance.

## 13. Hard-Negative Relevance

Primary Thermal V2 failure remains `HUMAN_NORMAL → HUMAN_FALL_PROXY` at the B6R DEVELOPMENT anchor **174 / 4000 = 4.35%** (TV2-H0 / B6R-P1). That number is a current-model diagnostic, not a target these sources are claimed to move.

| Source | Verified relevant semantics | Allowed language |
|---|---|---|
| Thermal-IM | seated actions; object-touch motion; furniture recline (`lie sofa`) as a **non-fall** confound | contains relevant hard-negative semantics; can test a false-FALL hypothesis for sitting/recline-like postures versus `HUMAN_FALL_PROXY`; does not prove false-FALL reduction |
| QUIDA | protocol walking outside fall instants; not a labeled ADL taxonomy | limited non-fall context exists; does not prove false-FALL reduction; not a bending/crouching/kneeling source |
| eHomeSeniors | unlabeled pre-fall ADL only | does not currently contain verified hard-negative **labels**; using unlabeled context as HUMAN_NORMAL would invent supervision |
| IPHD/IPHPDT | paper posture names including bending/lying | not D2-admitted; derivative still request-gated |

No source is ranked by imagined model performance. Missing H0 coverage (crouch, bend, kneel, near-floor normal, partial human) is **not** filled by QUIDA/eHome frame labels. Thermal-IM sitting/recline is the only admitted source with explicit normal-posture-like tokens.

## 14. D3 Source Recommendations

This is not final training membership.

### QUIDA — `ADVANCE_TO_D3_WITH_UNRESOLVED_LABEL_LIMIT`

- Representation: P-lane member; Celsius-compatible 768-vectors.
- Labels: temporal instants only.
- Frame supervision: unresolved.
- Grouping: subject-level possible.
- Hard-negative value: weak/limited walking context.
- License / terms: `DATASET_LICENSE_NOT_VERIFIABLE`; confirm before any training release.

### eHomeSeniors calibrated MLX90640 — `ADVANCE_TO_D3_WITH_UNRESOLVED_LABEL_LIMIT`

- Representation: P-lane member with an explicit 768-field extraction contract.
- Labels: file-level staged fall types.
- Frame supervision: unresolved.
- Grouping: volunteer-level possible.
- Hard-negative value: not currently labeled.
- License / terms: CC BY 4.0 from linked asset metadata; confirm raw-field scope even though raw is excluded from model input.

### Thermal-IM — `ADVANCE_TO_D3_SUPPLEMENTAL`

- Representation: I-lane only.
- Labels: preserve action-object tokens; conservative G1 mapping; empty annotation ≠ `NOT_HUMAN`.
- Frame supervision: derivable for action intervals.
- Grouping: partial until `meta.csv` audit.
- Hard-negative value: relevant sitting/interaction/recline semantics; no performance claim.
- License / terms: BSD-3-Clause dataset notice.

### eHomeSeniors raw MLX — `REFERENCE_ONLY`

Excluded from frame-model input.

### eHomeSeniors Omron — `REFERENCE_ONLY`

Excluded as 62×80 spatial input (`EXCLUDED`).

### IPHD base — `REFERENCE_ONLY`

### TF-66, IPHPDT — `HOLD_FOR_ADDITIONAL_METADATA`

Not admitted on paper descriptions.

No source is `ADVANCE_TO_D3_PRIMARY` because no admitted source currently supplies both a frozen geometry adapter and defensible frame supervision for a 3-class frame classifier. No source is `REJECT_FROM_V2_EXPANSION`: the three D1-admitted payloads remain useful for D3 membership **design**.

## 15. Unresolved Issues

1. QUIDA and eHomeSeniors physical orientation (flip/rotation/true-up) and stored 2-D order.
2. Authoritative fall intervals for QUIDA; framewise onset/end for eHomeSeniors.
3. QUIDA asset-level license/terms.
4. Thermal-IM release-level `meta.csv` actor/room/scene/split overlap.
5. Quality exclusion bounds for QUIDA extrema.
6. Whether a later D3 annotation campaign can create `FRAME_SUPERVISION_DERIVABLE_WITH_VERIFIED_RULE` for QUIDA/eHome without inventing ±N seconds in this phase.
7. IPHD/IPHPDT access, terms, and subject grouping — still outside serious D2 membership.
8. TF-66 video payload.
9. Whether any I-lane intensity statistic should exist at all; not designed here.
10. G1 PRE/GEO freeze — owned by Control Tower after D3.

Prose vs payload discrepancies recorded:

- D0 provisionally mentioned Thermal-IM walking/kneeling; D1/D2 verified vocabulary does not include those exact tokens.
- D1 described Thermal-IM as 384×288 in the MP4 sample entry; decode is 288×384 H×W, which agrees with the README and is the same dimensions.
- eHomeSeniors label-row width 1604 vs data-row width 1668 is a real file inconsistency, not resolved by assuming a uniform table.
- QUIDA top-level `ir_camera.csv` is not a thermal recording.

## 16. TV2-D2 Gate Recommendation

**`PASS_WITH_LIMITATIONS`**

D3 may proceed to membership / expansion **design** with these contracts on the table. Material limitations remain explicit: two representation lanes; unresolved frame supervision for both physical sources; unfrozen geometry adapters; `P1_NOT_READY`; QUIDA terms unverified; Thermal-IM grouping only partial; Omron/raw excluded; no training.

The gate is not `PASS` because those limitations are material to Candidate A/B frame classification. It is not `BLOCKED` because three serious sources have defensible D3 roles without merging Celsius and intensity.

Authorized next step:

```text
D2
 ↓
D3 membership / expansion design
 ↓
G1 final contract freeze   (Control Tower)
```

Not authorized: Candidate A training; Candidate B training; C1 matched pooled-MLP training; dataset merge; TFLite/INT8; model ranking; locked-test access; Team/Integration/Pi work; SafeNest-capture training use; raw-data commit; final PRE freeze; G1 PASS claim; execution-map edit.

SafeNest captures remain `REFERENCE_ONLY`.
