# SafeNest I3 — Presence / Gap / Freeze / Stale Fail-Closed Regression

- Regression contract: `MMWAVE_V2_I3_FAIL_CLOSED_REGRESSION_CONTRACT_V1`
- Regression matrix: `MMWAVE_V2_I3_REGRESSION_MATRIX_V1`
- Runtime safety gate: `MMWAVE_V2_I3_RUNTIME_SAFETY_GATE_V1`
- Date: 2026-08-23
- Phase: **I3 only**. No training, no V1/V2 physiology, no Q3, no M-PV1, no D2, no Q2 threshold fork.
- Gate: **PASS_WITH_LIMITATIONS**
- Base: `origin/main` `e84d802e5b9aa28e6729a02b304f1f70043f89c3` (I2 squash merge `#122`)

This artifact answers:

> When historical or synthetic MR60 runtime input indicates no confirmed person, a large gap, source freeze, stale source, exact flat signal, invalid timestamp, malformed freshness, or recovery warmup, does the frozen runtime boundary deterministically fail closed before physiology and prevent a valid respiratory/APNEA/NORMAL result from being emitted?

---

## 1. Scope and isolation

I3 is created from updated `origin/main` after I2 merged. It does not stack on unmerged R2/R3/D2/D3 or model lanes.

I3 reuses:

- I1 `resolve_precedence` / output envelope
- I2 replay harness and representative session inventory
- canonical Q2 `evaluate_availability` / `apply_quality_corruption`

Numeric Q2 thresholds are not copied into an I3-local detector.

---

## 2. Precedence

presence → input availability / quality → physiology → application state

| Presence | Quality | Resolved state | Physiology |
|---|---|---|---|
| false | clean | `PRESENCE_SUPPRESSED` | false |
| unknown/null (production) | clean | `PRESENCE_SUPPRESSED` | false |
| true | clean | `PHYSIOLOGY_ELIGIBLE` | mock / not evaluated |
| true | invalid | `INPUT_UNAVAILABLE` | false |
| false | invalid | `PRESENCE_SUPPRESSED` | false |

A synthetic high-confidence NORMAL/APNEA object cannot override invalid availability.

---

## 3. Synthetic Q2 coverage

All frozen Q2 modes are evaluated through the canonical evaluator, then wrapped in an I1 envelope:

`CLEAN_VALID`, `LARGE_GAP`, `SOURCE_FREEZE`, `STALE_SOURCE`, `FLAT_EXACT`, `JITTER_PLUS_LARGE_GAP`, `REPUBLICATION_TO_FREEZE`

`CLEAN_VALID` remains `PHYSIOLOGY_ELIGIBLE` with `physiology_executed=false`. Invalid modes remain `INPUT_UNAVAILABLE` with no interpolation and no physiology class.

Controls:

- typical Q1 cadence jitter stays eligible
- one isolated republication is not a freeze
- a tiny dynamic sinusoid is not rejected for amplitude
- production missing `phase_age_ms` is `SOURCE_STALE`
- public-offline missing MR60 freshness is not automatically invalid

---

## 4. Historical I2 replay

I2 replays the seven representative sessions. I3 then applies Q2 to the preserved event series without mutating lineage (`replay_event_id`, seq, timestamps, git blob SHA).

| Role | Quality-only window | Notes |
|---|---|---|
| modern 1.2 | `PHYSIOLOGY_ELIGIBLE` | 150 eligible events |
| legacy 1.0 | `PHYSIOLOGY_ELIGIBLE` | 99 eligible events |
| source republication | `INPUT_UNAVAILABLE` / exact-flat | empty-desk presence suppressed; isolated republication is not treated as freeze in the synthetic control |
| 95-run freeze-like | `INPUT_UNAVAILABLE` / `SOURCE_FREEZE` | runtime interval fail-closed; not a physiology label |
| 3598-run prefix | `INPUT_UNAVAILABLE` / `SOURCE_FREEZE` | 64-row committed prefix |
| timestamp collision | `INPUT_UNAVAILABLE` / `TIMESTAMP_UNRESOLVED` | I2 also typed-rejects one truncated row |
| phase-age absent | `INPUT_UNAVAILABLE` / `SOURCE_STALE` | production freshness missing |

Totals: 7/7 sessions evaluated, 1719 replayed, 1 I2 reject, 1262 presence-suppressed, 162 input-unavailable, 295 eligible. Eligible events still do not execute a model.

Do not read these counts as NORMAL/APNEA accuracy.

---

## 5. Ownership of timestamp defects

- I2 owns parser/replay rejection: `TRUNCATED_ROW`, `NON_NUMERIC_TIMESTAMP`, unsupported schema
- Q2 owns runtime availability rejection: `TIMESTAMP_NON_MONOTONIC`, `TIMESTAMP_UNRESOLVED`

Neither path repairs timestamps into a clean physiology window.

---

## 6. Session and sequence

I2 session state resets on session boundary, `device_id` change, and firmware change. Q2 is evaluated per session; a freeze in session A does not make an independent clean session B unavailable. Seq gaps are audited and not interpolated. Seq increment does not refresh a stale `phase_age_ms`.

---

## 7. Determinism

The compact regression payload (states, reasons, matrix, session counts) hashes identically across two in-process evaluations. Wall-clock runtime is excluded.

---

## 8. Completion meaning

`I3_INTEGRATION_LANE_COMPLETE = YES` means the I1 → I2 → I3 integration-preparation lane is closed: the runtime boundary, deterministic replay, and fail-closed availability regression are ready for later V2 model integration.

It does **not** mean the V2 model is accurate, APNEA false-positive performance passed, or Pi deployment passed.
