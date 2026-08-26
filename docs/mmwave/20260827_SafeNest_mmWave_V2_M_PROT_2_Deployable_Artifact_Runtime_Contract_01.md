# SafeNest mmWave V2 — Deployable Artifact / Runtime Contract (M-PROT-2)

- Phase: **M-PROT-2**
- Date: 2026-08-27
- Base (`origin/main`): `0def5c7cb22cc6a15866ac5737fc5865bb016974`
- Branch: `research/mmwave-m-prot-2-deployable-contract`
- Terminal verdict: **`M_PROT_2_DEPLOYABLE_CONTRACT_FROZEN`**
- Manifest: `datasets/mmwave/manifests/M_PROT_2_deployable_artifact_runtime_contract/`

This freezes a **prototype packaging/runtime contract** for M-PROT-1 nominated **B23**. It is not final model selection, not M-PV3.8 evaluation, not deployment validation, and not safety/clinical validation.

```text
PROTOTYPE_INTEGRATION_ONLY
NOT_FINAL_SELECTED_MODEL
NOT_DEPLOYMENT_VALIDATED
NOT_SAFETY_VALIDATED
NOT_CLINICAL_VALIDATION
SUBJECT_TO_REPLACEMENT
```

---

## Representation selected

```text
PRIMARY_PROTOTYPE_DEPLOYABLE_REPRESENTATION = PYTORCH_FLOAT32_STATE_DICT
SOURCE_OF_TRUTH = models/mmwave/m_pv2/family_b/candidate_seed_23.pt
SHA256 = 8f7de6f50d6ff62ff9b0ebfaed0b1fccd8d194c7e33781bc5b93366fae251a2c
```

The existing B23 checkpoint is frozen **by identity + SHA**. It is not copied under a new filename.

PyTorch-first is the current source format. It is **not** a claim that Raspberry Pi must run torch forever. It is the only representation that currently preserves B23 semantics without an unproven conversion.

---

## Why this representation

Decision order: semantic preservation, reproducibility, artifact integrity, actual runtime compatibility, simplicity, dependency burden, integration practicality.

B23 is a compact float32 `state_dict` for `TraceModel` (`family_b`, seed 23). Strict load and canonical parameter SHA `6db949c2…` match M-PROT-1.

This repository’s Pi file `requirements-pi.txt` declares **LiteRT**, not torch. The existing `inference/mmwave_interpreter.py` is a **V1 3-class TFLite** wrapper with heuristic fallback and must not be reused for B23.

Read-only inspection of `https://github.com/yuname121/integration.git` at commit `c759205bfae0adbbd3a33235718801a8e476b28c` (`main`): live mmWave loads `MN9Interpreter` / `MMWAVE_M_N9_FULL_INT8_V1.tflite`. That is **ROLE_INCOMPATIBLE** with breathing / RR / quality. Backend requirements there do not include torch. That evidence is recorded; the integration repository was not modified.

So:

- Pi/LiteRT compatibility is proven for **M-N9**, not for B23.
- Torch-on-Pi is `TARGET_RUNTIME_DEPENDENCY_NOT_LIVE_VERIFIED`.
- Hardware latency is `NOT_MEASURED`.
- Choosing M-N9 because it is already TFLite would silently replace ROLE_L. Forbidden.

---

## Alternatives inspected

| Option | Result |
|---|---|
| Existing B23 PyTorch float32 state_dict | **Selected** |
| TFLite float32 conversion of B23 | `NOT_YET_PROVEN` — no governed conversion or equivalence criterion |
| INT8 | `NOT_AUTHORIZED_IN_M_PROT_2` — needs calibration data; D1/D2/C1/live calibration forbidden |
| TorchScript | Not selected; not in Pi or integration mmWave adapters |
| ONNX Runtime | Not introduced |
| M-N9 / M-B11 TFLite | ROLE_INCOMPATIBLE; not a B23 package |

No conversion binary was created. Source vs deployed parity is **not applicable** because the source **is** the deployable artifact.

---

## What was proven

- B23 path, SHA, bytes, family/seed payload, strict `TraceModel` load
- TRAIN scaler file SHA `9555c8c9…` and content SHA `5a2583b5…`
- Executable 30 s / 10 Hz / 300-sample / 621-d float32 layout
- Feature order: `concat(trace[300], trace_mask[300], scale[12], quality[9])`
- Double z-score rejected
- Wrong artifact SHA / missing artifact / wrong scaler SHA fail closed
- Malformed dimensions, missing mask, NaN/Inf, short window fail closed
- Breathing threshold remains **0.5** (`PROTOTYPE_THRESHOLD`)
- Quality threshold remains **0.5** (`PROTOTYPE_QUALITY_THRESHOLD`)
- ABSENT is never APNEA; no fallback model
- Decoded RR `<= 0` or non-finite → `UNAVAILABLE_INVALID_DECODE` (not clamped to 0/1)
- Presence / availability failure suppresses physiology
- Isolated harness: `adapters/mmwave_m_prot_2_b23_runtime.py` + `scripts/mmwave/run_m_prot_2_reference_harness.py`
- Focused tests: `tests/test_mmwave_m_prot_2_deployable_contract.py`

---

## What was not proven

- TFLite/TorchScript conversion of B23
- Raspberry Pi package install of torch
- Pi latency
- Live MR60 windowing at 10 Hz
- Live R2 F3 scale/quality computation (harness consumes named 12+9 descriptors)
- Device-domain or safety performance
- Both-class ABSENT discrimination

Training applied `nan_to_num` before inference. The prototype harness **fails closed** on non-finite values instead of filling zeros and emitting physiology.

---

## Frozen I/O

| Item | Value |
|---|---|
| Window | 30 s causal, 10 Hz, 300 samples |
| Assembled input | 621 float32 |
| Scaler | TRAIN-only, apply once; refit forbidden |
| F2 | `NOT_REQUIRED` |
| Breathing | sigmoid; PRESENT if `>= 0.5` else ABSENT |
| RR | `rr_bpm = rr_raw * 8.948729232744911 + 17.12899193548387` |
| Quality | sigmoid; `< 0.5` suppresses RR |
| Precedence | PRESENCE → QUALITY/AVAILABILITY → PHYSIOLOGY |

SW-01..04 were not modified. SW-02 is not required for prototype inference.

---

## Handoff to M-PROT-3

M-PROT-3 should wire:

sensor/transport → SW-01 validated source → 30 s / 10 Hz window → this assembler/model/decode → prototype output → LIVE_DEBUG_NON_CAMPAIGN evidence → SW-03/SW-04.

Do not call `MMWaveInterpreter` or M-N9. Do not start M-PROT-3 in this PR.

---

## Governance unchanged

```text
D1 PRESENT = 57
D1 ABSENT  = 0
D1 MEMBERSHIP = BLOCKED_INVALID_FINAL_MEMBERSHIP
M-PV3.8 = RESOURCE_BLOCKED_CLOSED
M-PV3.8 evaluation = NOT_EXECUTED
M-PV4 = UNAUTHORIZED
D2 = LOCKED
M_PV38_PANEL_CHANGED = false
```

```text
TERMINAL_VERDICT = M_PROT_2_DEPLOYABLE_CONTRACT_FROZEN
NEXT_PHASE       = M-PROT-3
```
