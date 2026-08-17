# SafeNest Thermal — T-B5 Real-MI48 INT8 Quantization Corrective Review

## Decision

This bounded audit is **PASS_WITH_LIMITATIONS** and **INCONCLUSIVE** for root
cause.  It reconstructs the historical T-B5 FULL_INT8 calibration lineage and
records the frozen RP-X0 O2.6 field-equivalence evidence, but it does not
generate a replacement artifact.  The canonical TRAIN tensor payload and the
frozen Float checkpoint are not materialized in the current AI worktree, so a
same-weight TRAIN-only correction cannot be converted or validated without
guessing.  No real MI48 frame was used for calibration or selection.

The historical artifact remains locked and untouched.  Production selection,
Pi adapter work, T-C, and retraining remain unauthorized by this review.

## Scope and evidence boundary

| Item | Result |
| --- | --- |
| AI repository base | `origin/main` at `2574fbc4abba7988565dd1fd013b1698fe4ecf49` |
| Review branch | `fix/thermal-tb5-mi48-int8-calibration` |
| Historical artifact modified | **NO** |
| New INT8 candidate | **NO** |
| Real MI48 used for calibration | **NO** |
| LOCKED_TEST used | **NO** |
| Field ground truth | **NO** |
| Integration repository modified | **NO** |
| Pi snapshot modified | **NO** |
| Real field payload committed | **NO** |
| External SSD | `NOT_MOUNTED`; no hydration or download requested |

The RP-X0 O2.6 summary was consumed as read-only local evidence from source
commit `4879fbb`.  Its compact report SHA-256 is
`d70e5aa5e1f4e9e6d66ecc45187ea4f787a9198d9fbea309c6a546052fe4bd7b`.

## Historical quantization lineage

The repository code and T-B4 compact manifests establish the following chain:

```text
T-B1 frozen Float checkpoint
  → P1_TRAIN_FITTED_GLOBAL_ZSCORE
  → TRAIN-only 512-row representative set
  → TFLite DEFAULT + representative dataset + strict INT8 converter
  → T-B5 FULL_INT8 (locked)
```

- Representative source/split: `TRAIN` only; validation, REAL_EVAL_DEVELOPMENT,
  and LOCKED_TEST were not used.
- Selector: four source labels × eight TRAIN frame-mean quantile bands, up to
  16 evenly spaced canonical indices per stratum, then 20 deterministic global
  index backfills.  The set has 512 unique rows, no random seed, and policy
  checksum `c5ce8a54898a19d0b9dad156aee89feeafbf85f79a64a6e424d7912b24a95179`.
- P1: mean `22.769290618485442`, standard deviation
  `2.8684523405441222`, with the frozen Celsius conversion
  `physical_C = raw_uint16 / 10.0 - 273.15`.
- Converter: `Optimize.DEFAULT`, representative dataset attached,
  `TFLITE_BUILTINS_INT8` only, int8 input/output, no float16 path, and strict
  FULL_INT8 semantics.
- Locked FULL_INT8: 318,280 bytes,
  `fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be`.
- Input quantizer: scale `0.31791284680366516`, zero point `-125`; the
  lower representable P1 value is `(-128 - (-125)) * scale = -0.9537385404109955`.

The compact representative manifest preserves frame means but not the 512 ×
62 × 80 pixel tensors.  Its frame-mean P1 range is approximately
`[-0.2675, 0.9914]`; this is **not** a pixel-level calibration distribution and
must not be used to claim that TRAIN covered or failed to cover the real cold
tail.

## TRAIN-versus-real range decision

The required pixel-level TRAIN and historical representative quantiles
(P1/Celsius min, p1, p5, median, p95, p99, max) are **not measurable from the
current compact evidence**.  The expected canonical files are recorded in
`access_status.json` with their known shape, dtype, and checksums, but are not
materialized in this worktree.  The frozen Float checkpoint is likewise absent
from this worktree.  Therefore:

```text
TRAIN_DOMAIN_RANGE_GAP = NOT_VERIFIABLE
HISTORICAL_CALIBRATION_COVERAGE_DEFECT = NOT_VERIFIABLE
CONVERTER_CONFIGURATION_DEFECT = NOT_VERIFIABLE
ROOT_CAUSE = INCONCLUSIVE
```

No synthetic cold values, field frames, reverse-engineered weights, or TFLite-
to-Keras guesses were used to fill this evidence gap.  Consequently, no
corrective candidate was generated and no candidate was eligible for
integration review.

## Frozen RP-X0 O2.6 real-field evidence

The fixed O2.6 selection contains 154 deterministic frames from 23,788
readable frames (1,964 readable NPZ files; 15 `FIELD_CAPTURE_ARTIFACT` files).
The raw input is uint16 `(62, 80)` and the frozen physical conversion and P1
contract were reproduced exactly.

Across all pixels in the 154 selected frames, the measured P1 distribution was:

| statistic | P1 | Celsius |
| --- | ---: | ---: |
| min | -30.4412555106 | -64.55 |
| p1 | -8.7919503706 | -2.45 |
| p5 | -5.0617158296 | 8.25 |
| median | -0.8782752228 | 20.25 |
| p95 | 3.1308553587 | 31.75 |
| p99 | 5.3271616772 | 38.05 |
| max | 13.5545948705 | 61.65 |

About `48.1664%` of these selected pixels are below the historical INT8 lower
representable P1 range (`-0.9537385404`).  This is a measured field-domain
observation, not evidence that the Float model is correct or incorrect.

The already-frozen Float↔historical INT8 replay remains:

| metric | historical FULL_INT8 |
| --- | ---: |
| top-1 agreement | 139/154 = 90.2597% |
| disagreements | 15 |
| ranking agreement | 90.2597% |
| output MAE median | 0.0013021 |
| output MAE p95 | 0.6628250 |
| output MAE max | 0.6653646 |
| low-side saturation median | 43.4476% |
| low-side saturation p95 | 83.1452% |
| high-side saturation max | 0% |
| association | `STRONG_ASSOCIATION_OBSERVED` |

No accuracy, fall-detection, temporal-event, Thermal-44, or T-C claim is made.
The fixed field frames remain evaluation-only and were not iterated against.

## Corrective candidate and next gate

```text
Created: NO
Identity/path/SHA: NONE
Strict FULL_INT8: NOT APPLICABLE
Float weights unchanged: NOT APPLICABLE (conversion not run)
P1 unchanged: YES (no conversion attempted)
Calibration source: NONE
Canonical parity: NOT RUN FOR A NEW CANDIDATE
RP-X0 corrective replay: NOT RUN FOR A NEW CANDIDATE
FLOAT_RETRAINING_REQUIRED: UNRESOLVED
NEW_INT8_CANDIDATE_ELIGIBLE_FOR_INTEGRATION_REVIEW: NO
```

The smallest next step is owner-authorized, read-only materialization of the
canonical TRAIN arrays and frozen Float checkpoint in a dedicated experiment
worktree.  Then run exactly one TRAIN-derived calibration correction, verify
strict INT8 internals and canonical parity first, and perform the one frozen
154-frame O2.6 replay once.  Do not use O2.6 frames as calibration or tune a
candidate against field agreement.

## Validation and delivery

The standalone validator is
`scripts/validate_thermal_t_b5_mi48_quantization_review.py`.  It checks the
historical identity, converter policy, P1 identity, real-evaluation boundary,
pixel-statistic blocker, portability, deterministic ordering, and compact
checksums without opening large payloads.  Its machine-readable result is
`datasets/thermal/manifests/T-B5_MI48_quantization_corrective_review/validation_result.json`.

This audit does not authorize T-C, Pi O3, production activation, or a merge.
