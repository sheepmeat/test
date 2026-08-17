# SafeNest M-N9 — FULL_INT8 artifact lock + Raspberry Pi inference readiness

- Date: 2026-08-18
- Phase: **M-N9 only**. M-N8 skipped. No M-N10 capture work.
- Artifact ID: `MMWAVE_M_N9_FULL_INT8_V1`
- Lock: `config/mmwave/m_n9_full_int8_artifact_lock.json`
- Result: `datasets/mmwave/manifests/m_n9_full_int8_result.json`

`PI_INFERENCE_READY` is not `DEVICE_VALIDATED`. Formal multi-subject MR60
validation with independent respiratory reference remains later.

---

## 1. Exact FLOAT model converted

```text
selection_id:  MMWAVE_M_N6_SELECTED_FLOAT_V1
architecture:  M-N5_DILATED_CONV1D_GAP_TINY
seed:          2026
params:        5019
path:          models/mmwave/m_n6/MMWAVE_M_N6_SELECTED_FLOAT_V1.keras
```

M-N8 was not reopened. No retrain, fine-tune, architecture change, or
TRAIN+VAL final retrain.

---

## 2. FLOAT SHA matches M-N6

```text
expected: 9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab
actual:   9de3818c0f4854f8512c9d390d290938b6e562d590e0775cb1dab885cc72e2ab
FLOAT_ARTIFACT_SHA_MATCH = YES
```

---

## 3. Representative calibration source

```text
INT8_CALIBRATION_SOURCE = PUBLIC_TRAIN_ONLY
subjects: 77
windows:  337 (all frozen canonical TRAIN tensors)
```

VAL, `NEW_MODEL_HELDOUT_TEST`, Team MR60, M-N7 reserved recordings, and Pi
runtime samples were not used for calibration.

---

## 4. FULL_INT8 conversion settings

```text
optimizations:            DEFAULT
supported_ops:            TFLITE_BUILTINS_INT8 only
inference_input_type:     int8
inference_output_type:    int8
weights / activations:    INT8 / INT8
FULL_INT8_ONLY:           YES
float fallback ops:       NO
opcodes:                  RESHAPE, CONV_2D, MEAN, FULLY_CONNECTED, SOFTMAX
tensor dtypes:            int8, int32
TensorFlow / TFLite:      2.20.0
```

Unsupported-op fallback was not used. Architecture was not changed to make
conversion pass.

---

## 5. Input / output INT8 contract

Input:

```text
shape [1,240,1]  dtype int8
scale 0.5623255372047424
zero_point 4
q = clip(round(x / scale + zero_point), -128, 127)
```

Output:

```text
shape [1,3]  dtype int8
scale 0.00390625
zero_point -128
x_float = (q - zero_point) * scale
```

These values are interpreter-reported, not assumed.

Locked binary:

```text
models/mmwave/m_n9/MMWAVE_M_N9_FULL_INT8_V1.tflite
SHA-256  3b008af4be0facc4037c2afd3fe39292fb794208eb4370dbe6916b2d15aa38a4
size     11816 bytes
```

Provenance (no reconversion):

```text
conversion_base_sha:          bee5fd6f1611036d1a5cade29712586bdca4b6bf
  meaning: HEAD at conversion time (canonical main / M-N7 merge)
artifact_introducing_commit:  a475d06623dd91298a8563924fafaa5fc6d3532b
  meaning: first M-N9 commit that added the locked TFLite binary
```

---

## 6. VAL FLOAT → INT8 parity

Public VAL only: 17 subjects, 70 supervised windows. Not a new model-selection
phase. Heldout was not rerun.

| Metric | FLOAT | INT8 | delta |
|---|---:|---:|---:|
| Accuracy | 0.771429 | 0.785714 | +0.014285 |
| Macro F1 | 0.723358 | 0.739087 | +0.015729 |
| Balanced accuracy | 0.742130 | 0.760648 | +0.018518 |
| Top-1 agreement | — | **0.985714** | — |
| NORMAL recall | 0.888889 | 0.944444 | +0.055555 |
| RAPID recall | 0.400000 | 0.400000 | 0.000000 |
| APNEA-proxy recall | 0.937500 | 0.937500 | 0.000000 |

Quantization-parity gate:

```text
no numerical/invoke failure
top-1 agreement 0.985714 >= 0.95
Macro-F1 degradation -0.015729 (<= 0.03; INT8 did not degrade)
no class recall degradation > 0.10
PARITY = PASS
```

INT8 dequantized softmax bins need not sum exactly to 1.0; class decisions
use argmax.

---

## 7. RAPID parity

```text
FLOAT VAL RAPID recall: 0.400
INT8  VAL RAPID recall: 0.400
delta: 0.000
```

INT8 did not materially worsen the known FLOAT RAPID weakness. M-N9 did not
attempt to improve RAPID.

---

## 8. Zero / no-person behavior

Canonical all-zero input:

| | FLOAT | INT8 |
|---|---|---|
| predicted class | APNEA-proxy | APNEA-proxy |
| confidence | 0.997562 | 0.996094 |

This is expected inherited M-N7 behavior, not an INT8 failure.

Optional reuse of the 13 already-consumed M-N7 windows for technical parity
only: FLOAT↔INT8 top-1 agreement **1.000**. No MR60 accuracy was computed.

---

## 9. Mandatory external presence gate

```text
PRESENCE_GATE_REQUIRED = YES
```

If `valid_person_presence == false`, respiratory classification is
`SUPPRESSED` (`NO_VALID_PERSON` / `RESPIRATORY_INFERENCE_SUPPRESSED`).
NORMAL / RAPID_OR_ABNORMAL / APNEA must not be exposed as physiology when
there is no valid person.

This is **not** a fourth neural-network class and not threshold tuning.
Existing MR60 telemetry already carries `human_detected_raw`; M-N9 does not
invent a new presence threshold. Exact runtime wiring is integration work.

---

## 10. Actual Pi smoke status

```text
PI_ARTIFACT_READY = YES
PI_DEVICE_SMOKE = NOT_PERFORMED_ENVIRONMENT_UNAVAILABLE
PI_ISOLATED_LOAD / INVOKE = NOT_PERFORMED
PI_ISOLATED_EXECUTION_VERIFIED = NO
```

No authorized Raspberry Pi target was configured. The locked TFLite file is
ready for a later isolated load/invoke. No live MR60 feed and no new capture
were required or performed.

---

## 11. Why `PI_INFERENCE_READY != DEVICE_VALIDATED`

The artifact can be loaded by a TFLite/LiteRT interpreter under the frozen
`[1,240,1]` int8 contract. That is inference readiness.

It does **not** prove that the model is physiologically correct on real MR60
people. M-N7 was one subject with no independent respiratory GT. Therefore:

```text
DEVICE_VALIDATED = NO
```

even after a future Pi isolated smoke.

---

## 12. Next validation gap

```text
M_N8_STATUS = SKIPPED_NOT_JUSTIFIED
FULL_INT8_ARTIFACT_LOCKED = YES
NEXT_RECOMMENDED_PHASE = M-N10
```

Remaining evidence gap:

```text
real MR60
+ multiple physical subjects
+ independent respiratory reference
+ development-unseen formal validation
```

M-N10 is not started here.

---

## Gate

**PASS_WITH_LIMITATIONS** — FULL_INT8 conversion and VAL parity pass; Pi
isolated execution was not available; RAPID FLOAT weakness is inherited.

## Files

- `scripts/mmwave_m_n9_full_int8.py`
- `models/mmwave/m_n9/MMWAVE_M_N9_FULL_INT8_V1.tflite`
- `config/mmwave/m_n9_full_int8_artifact_lock.json`
- `datasets/mmwave/manifests/m_n9_full_int8_result.json`
- `tests/test_mmwave_m_n9_full_int8.py`
