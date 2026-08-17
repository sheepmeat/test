# SafeNest Thermal — T-B5Q1 TRAIN-Domain INT8 Calibration Corrective

## Final decision

`TRAIN_DOMAIN_RANGE_GAP` is established.  The complete legitimate TRAIN
contains a very small lower-tail population that the historical 512-row
representative selector missed, but it does not cover the cold/background
domain observed on the real MI48 device.  A new calibration-only INT8 would
therefore be a field-domain workaround rather than a principled TRAIN-derived
correction.

```text
THERMAL_T_B5Q1_TRAIN_CALIBRATION_CORRECTIVE = PASS_WITH_LIMITATIONS
Corrective candidate = NOT CREATED
NEW_INT8_CANDIDATE_ELIGIBLE_FOR_INTEGRATION_REVIEW = NO
FLOAT_RETRAINING_REQUIRED = UNRESOLVED
DEVICE_DOMAIN_DATA_GAP = YES
```

No retraining, TFLite conversion, Pi O3, integration change, production change,
or historical-artifact replacement was performed.

## Evidence recovery and identity

The external SSD was used as read-only evidence storage.  Its filesystem is
exFAT over USB; no SSD file was edited.  Compact repository evidence records
logical paths only and does not include the mount path or raw payload.

| Evidence | Identity |
| --- | --- |
| TRAIN canonical | `canonical/TRAIN/train_canonical.npy`, 32,000 × 62 × 80, little-endian float32 Celsius, 634,880,128 bytes |
| TRAIN SHA-256 | `749c847fc9ab50ea5eee8827f0d47b5ebaa48165732a382c59f8b96c565b9d93` |
| TRAIN provenance | 77,767,837 bytes, SHA `b4ec8228e35703bac3319ca218a69fdef43013ea44b23376da4929b274d24888` |
| Frozen P1 checkpoint | `experiments/T-B1/T-B1_execution_result/checkpoints/P1_TRAIN_FITTED_GLOBAL_ZSCORE.weights.h5` |
| Checkpoint SHA-256 | `7aba32fe8d0e241546429bdc3e8cd059b10d4d8f548e9e12c4085abeba308a75` |
| Architecture | `SMALL_CNN_BASELINE_V1`, fingerprint `937fceb88900a779d67a8e407cebc3362cc21346721f92cea5ae8de1413aba2a`, 312,131 parameters |
| Seed | `20260813` |
| FLOAT TFLite reference | SHA `fbe891520f07e0534b1a7074dc819d8ed44bca58b27e35c78916c3ddae73a779`, 1,252,048 bytes |
| Historical FULL_INT8 | SHA `fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be`, 318,280 bytes |

The checkpoint, architecture fingerprint, selected profile, class map, and
winner registry match the frozen T-B1/T-B4 lineage.  P1 remained exactly
`(Celsius - 22.769290618485442) / 2.8684523405441222`.

The checkpoint was loaded into the frozen 312,131-parameter architecture as a
read-only identity check.  The resulting ordered weight-tensor aggregate SHA
was `19eec68045e801acd7d33d0ad10776b8cb0eb1f8514a268b9cd4bb3159ada170`, and
the architecture fingerprint remained unchanged.

## Historical 512-row calibration reproduction

The repository `_freeze_calibration` implementation was executed against the
SSD TRAIN payload.  The result exactly matched the committed T-B4 policy and
manifest checksums:

- policy: `T-B4_TRAIN_ONLY_STRATIFIED_CALIBRATION_512`
- policy checksum: `c5ce8a54898a19d0b9dad156aee89feeafbf85f79a64a6e424d7912b24a95179`
- manifest checksum: `51bbced6b40ab14d547e3c80afd99b92a24c016c1853e66c634b69d1dc4b30a4`
- selection: four labels × eight TRAIN frame-mean bands, up to 16 evenly
  spaced indices per stratum, then 20 deterministic global backfills
- rows: 512 unique, no random seed, validation/REAL/LOCKED_TEST usage: zero
- selected source-label counts: EMPTY_ROOM 133, SITTING 133, STANDING 120,
  LYING 126
- selected-index JSON SHA: `7a5de14aede74418c50104b5d543aeefe60764767b444ac02dca576de7f2bd5b`

### Pixel-level distribution

All values below use float64 P1 arithmetic over the float32 Celsius source.

| statistic | historical 512 P1 | historical 512 Celsius |
| --- | ---: | ---: |
| min | -0.827001 | 20.397078 |
| p0.1 | -0.390995 | 21.647741 |
| p1 | -0.341204 | 21.790564 |
| p5 | -0.309153 | 21.882500 |
| median | -0.261218 | 22.020000 |
| p95 | 1.512633 | 27.108207 |
| p99 | 5.328659 | 38.054295 |
| p99.9 | 9.517575 | 50.070000 |
| max | 80.240774 | 252.936127 |

Historical input quantization was scale `0.31791284680366516`, zero point
`-125`, giving a lower representable P1 value of `-0.9537385404109955`.
None of the 2,539,520 historical calibration pixels fell below that value.

## Full TRAIN distribution

| statistic | full TRAIN P1 | full TRAIN Celsius |
| --- | ---: | ---: |
| min | -1.367601 | 18.846392 |
| p0.1 | -0.390383 | 21.649496 |
| p1 | -0.340972 | 21.791229 |
| p5 | -0.308914 | 21.883186 |
| median | -0.261218 | 22.020000 |
| p95 | 1.520041 | 27.129456 |
| p99 | 5.324780 | 38.043167 |
| p99.9 | 9.517575 | 50.069999 |
| max | 80.517644 | 253.730316 |

TRAIN does contain a rare lower tail: 32 of 158,720,000 pixels
(`2.0161290322580645e-7`) are below the historical INT8 lower range, across 32
frames.  The historical 512 selector missed all 32.  This proves a small
historical subset coverage defect, but not a sufficient correction: the full
TRAIN minimum is still far warmer than the real MI48 cold pixels.

## Fixed real MI48 O2.6 comparison

The exact frozen O2.6 154-frame identities were reused from the read-only
`RP-X0_O2.6_MI48_FIELD_SNAPSHOT` evidence (source commit `4879fbb`).  No new
frames were selected, and no field frame entered calibration or selector
design.  There is no independent ground truth.

| statistic | real MI48 O2.6 P1 | real MI48 Celsius |
| --- | ---: | ---: |
| min | -30.441251 | -64.549988 |
| p0.1 | -18.727621 | -30.949997 |
| p1 | -8.791944 | -2.449982 |
| p5 | -5.061715 | 8.250000 |
| median | -0.878275 | 20.250000 |
| p95 | 3.130855 | 31.750000 |
| p99 | 5.327168 | 38.050018 |
| p99.9 | 8.011536 | 45.750000 |
| max | 13.554593 | 61.649994 |

Range comparison:

- `48.16636992040218%` of real pixels (367,914/763,840) are below the
  historical INT8 lower representable P1 range.
- `40.5579702555509%` of real pixels (309,798/763,840) are below the full
  TRAIN minimum P1 value.
- `0%` of real pixels are above the full TRAIN maximum.
- Therefore `40.5579702555509%` of real pixels are outside the legitimate full
  TRAIN P1 range.

The prior historical FLOAT↔INT8 O2.6 replay remains unchanged: 139/154
(90.26%) top-1 agreement, 15 disagreements, low-side saturation median
43.45%, p95 83.15%, high-side saturation 0%, MAE p95 0.6628.  This phase does
not claim accuracy or causality from that association.

The canonical 512-row VALIDATION three-stage equivalence is inherited from the
immutable T-B5 parity evidence (SHA
`18246ee6f34a64bfaefdacf5ee6429853dcf80887da476ebaa984acf12bc5261`):
Float Keras↔true FP32 TFLite has 1.0 argmax agreement, 0 disagreements,
probability MAE `5.011796603787694e-09`, and maximum absolute error
`7.152557373046875e-07`; true FP32↔historical FULL_INT8 has `0.99609375`
agreement, 2 disagreements, MAE `0.0033456996413038435`, and maximum error
`0.5893600583076477`; Float Keras↔historical FULL_INT8 has the same 2
disagreements, MAE `0.0033457006260881245`, and maximum error
`0.5893602967262268`.  The inherited evidence is VALIDATION-only, does not
use LOCKED_TEST, and no new corrective candidate was compared because the
TRAIN_DOMAIN_RANGE_GAP gate forbids candidate generation.

## Root-cause gate

The evidence supports `TRAIN_DOMAIN_RANGE_GAP`, not merely a bad 512-row
selector.  A TRAIN-only selector could recover the 32 rare lower-tail TRAIN
pixels, but it cannot legitimately produce representative values for the
40.56% of real MI48 pixels below the entire TRAIN minimum.  Using RP-X0 frames
to force a lower quantizer would violate the evaluation-only boundary.

Accordingly:

```text
Candidate authorization: NO
Corrective TFLite: NOT CREATED
Canonical FLOAT↔corrective INT8: NOT RUN
One-shot O2.6 corrective replay: NOT RUN
FLOAT_RETRAINING_REQUIRED: UNRESOLVED
DEVICE_DOMAIN_DATA_GAP: YES
```

The smallest principled next step is a separate device-domain data phase with
authorized, consented MI48 captures (or an equivalent documented source).  Do
not silently calibrate on unlabeled field data and do not start retraining in
T-B5Q1.

## Validation and delivery scope

The compact evidence is under
`datasets/thermal/manifests/T-B5Q1_train_calibration_corrective/` and is
validated by `scripts/validate_thermal_t_b5q1.py`.  It contains identities,
checksums, selector reproducibility, aggregate distributions, the fixed O2.6
boundary, and the no-candidate decision; it contains no TRAIN tensors, model
weights, raw field frames, or TFLite payloads.

Historical FULL_INT8 SHA before/after remains
`fa9730c29535477a3994c11e664474a0ca0116afaaa172889f47446ab2ac46be`.
The integration repository and Pi snapshot were not modified.  This work is a
stacked follow-up to PR #98 and is not a production or Pi O3 authorization.
