# SafeNest I1 — V2 Runtime Semantic I/O Contract Skeleton

- Semantic contract: `MMWAVE_V2_I1_RUNTIME_SEMANTIC_CONTRACT_V1`
- Input contract: `MMWAVE_V2_I1_RUNTIME_INPUT_CONTRACT_V1`
- Output contract: `MMWAVE_V2_I1_RUNTIME_OUTPUT_CONTRACT_V1`
- Provenance contract: `MMWAVE_V2_I1_PROVENANCE_CONTRACT_V1`
- Replay interface: `MMWAVE_V2_I1_REPLAY_INTERFACE_SKELETON_V1`
- Date: 2026-08-22
- Phase: **I1 only**. No training, no R1/R2/R3 feature choice, no Q2 detector, no I2 full replay, no D2.
- Gate: **PASS_WITH_LIMITATIONS**
- Base: `origin/main` `03b0f4c3b5bcff3f066eaf3f29a43d4889ad24b9`

This artifact answers:

> What exact information must cross the V2 runtime boundary so that future R1/R2/R3/M-PV1 implementations can change internally without changing the meaning of presence suppression, input availability, respiration evidence, RR, temporal-hold evidence, provenance, or application-facing output?

---

## 1. Scope and isolation

I1 is an independent peer lane from `origin/main`. It does not stack on unmerged D1/R1/Q1/Q2/D2/D3 branches. Merged Q2 on `main` is referenced only as an external quality policy identity.

I1 freezes a **semantic runtime contract**, not a model tensor specification. V1 identity `MMWAVE_M_N9_FULL_INT8_V1` is `OBSERVE_ONLY` and is not reused.

---

## 2. Runtime boundary

```text
sensor / native adapter output
    → V2 runtime input envelope
        → presence gate
        → quality / availability gate (Q2 policy, not executed here)
        → model-input boundary (deferred representation)
        → mock / future inference boundary
    → V2 runtime output envelope
        → application state
```

Invalid availability cannot carry a clinically/physiologically meaningful NORMAL or APNEA-proxy result.

---

## 3. Presence and quality precedence

| Presence | Quality | State | Physiology executed |
|---|---|---|---|
| `human_detected_raw` false (field in scope) | any | `PRESENCE_SUPPRESSED` | false |
| null / unknown (field in scope) | any | `PRESENCE_SUPPRESSED` | false |
| true | invalid | `INPUT_UNAVAILABLE` | false |
| true | eligible | `PHYSIOLOGY_ELIGIBLE` | false in I1 (boundary may be entered) |
| public offline, field `NOT_APPLICABLE` | eligible | `PHYSIOLOGY_ELIGIBLE` | false in I1 |

Presence is never inferred from amplitude, model output, breathing evidence, or RR. No-person is not APNEA. Class confidence cannot override invalid availability.

Q2 (`MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1`) remains the external detector policy. I1 carries `INPUT_UNAVAILABLE` and Q2 reason codes but does not copy 400 ms gap/freeze/stale/flat rules.

---

## 4. Input envelope

The input schema can represent production MR60 telemetry (`breath_phase`, `ts_monotonic_ms`, `phase_age_ms`, `seq`, `human_detected_raw`, `session_id`, firmware/config/schema) and public D0/D1-style adapted traces (native or index/`Fs` time, phase-like or relative displacement, reference/condition metadata).

Applicability is explicit:

- `REQUIRED_FOR_PRODUCTION_MR60`
- `NOT_APPLICABLE_TO_PUBLIC_OFFLINE_DOMAIN`

Public inputs are not rejected merely because `phase_age_ms` / `seq` / ESP time are absent. Production MR60 missing required freshness cannot be declared `PHYSIOLOGY_ELIGIBLE`; it can be represented as fail-closed `INPUT_UNAVAILABLE` / `SOURCE_STALE` under the external Q2 policy.

`breath_rate_raw` may be carried only as auxiliary telemetry. It is not V2 supervised RR truth.

Time fields are not collapsed. Each timestamp declares clock/domain, unit, monotonic vs wall vs reconstructed, and whether it is authoritative. ESP `ts_monotonic_ms` is not physical radar acquisition time.

---

## 5. Output envelope

Separate optional component slots:

- breathing evidence (`available` / `unavailable` / `not_evaluated`)
- RR (`rr_bpm`-capable value + validity/confidence + unavailable reason)
- quality / availability
- temporal-hold / APNEA-proxy evidence
- resolved application state

Application states: `PRESENCE_SUPPRESSED`, `INPUT_UNAVAILABLE`, `RESPIRATION_PRESENT`, `ABNORMAL_RR`, `APNEA_PROXY_CANDIDATE`, `NOT_EVALUATED`.

These slots are not neural heads. I1 emits only `MockInferenceResult` / `NOT_IMPLEMENTED_MODEL_BOUNDARY`.

Mandatory fail-closed fields: availability state, reason codes, whether physiology was executed, whether the result is actionable. Invalid input is not actionable and does not execute physiology.

Reason codes are not physiological labels. Carryable codes include Q2 names (`PRESENCE_NOT_CONFIRMED`, `LARGE_GAP`, `SOURCE_FREEZE`, `SOURCE_STALE`, `SIGNAL_FLAT_EXACT`, `TIMESTAMP_INVALID`, `RECOVERY_WARMUP`) without I1 thresholds.

Confidence, if present, is component-scoped. There is no ambiguous top-level `confidence`. Quality availability is not class confidence.

---

## 6. Provenance and window identity

`runtime_window_id` is `runtime_window:` plus SHA-256 of canonical JSON over contract, source, session, recording, event, and window start/end. Random UUID may exist as `transport_record_id` and is not evidence identity.

Lineage includes source/device, session/recording/event, adapter and representation profile ids, software git SHA, optional synthetic corruption profile, and firmware/config identity. Absolute paths and archive/version-snapshot fallbacks are forbidden.

---

## 7. Replay readiness

I2 may later feed historical JSONL, public adapted traces, and synthetic fixtures through `serialize_runtime_record` / `deserialize_runtime_record` / schema validators / `resolve_precedence`. I1 includes a tiny deterministic fixture only. No multi-session replay, metrics, or MR60 application scoring.

---

## 8. Deferred bindings

| Topic | Status |
|---|---|
| R1 representation / common rate | `DEFERRED_TO_R1_R2_R3` / `DEFERRED_TO_R1_M_PV1` |
| R2 spectral/autocorrelation features | `DEFERRED_TO_R1_R2_R3` |
| R3 breathing, RR, temporal-hold algorithm | `DEFERRED_TO_R3` / `DEFERRED_TO_R3_M_PV1` |
| Q2 detector implementation | `OUTSIDE_I1` (policy bound) |
| FLOAT family, heads, tensor shape, history duration | `DEFERRED_TO_M_PV1` |
| INT8 quantization | `DEFERRED_TO_M_PV2` |
| near-flat threshold | `DEFERRED_TO_R2_R3_M_PV1` |

---

## 9. Validation

`tests/test_mmwave_i1_runtime_io_contract.py` and `scripts/validate_mmwave_i1_runtime_io_contract.py`.

Gate: **PASS_WITH_LIMITATIONS**. D2 unused. No model training or V1/V2 inference. V1 artifact unmodified.
