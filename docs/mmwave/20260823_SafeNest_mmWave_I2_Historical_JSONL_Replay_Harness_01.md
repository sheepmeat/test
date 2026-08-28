# SafeNest I2 — Historical JSONL Deterministic Replay Harness

- Replay contract: `MMWAVE_V2_I2_HISTORICAL_JSONL_REPLAY_CONTRACT_V1`
- Harness: `MMWAVE_V2_I2_REPLAY_HARNESS_V1`
- Schema registry: `MMWAVE_V2_I2_SCHEMA_COMPATIBILITY_REGISTRY_V1`
- Result schema: `MMWAVE_V2_I2_REPLAY_RESULT_SCHEMA_V1`
- Date: 2026-08-23
- Phase: **I2 only**. No training, no V1/V2 physiology, no Q2 threshold fork, no I3 regression gate, no D2.
- Gate: **PASS_WITH_LIMITATIONS**
- Base: `origin/main` `38ff2466280125bb7cdd073e163348fe4a9e9ec8` (I1 squash merge `#120`)
- I1 handoff commit: `83c8045755f37bcb7bb72ab87aa56506f8603bb8`

This artifact answers:

> Can existing SafeNest MR60 telemetry JSONL evidence be deterministically replayed through the frozen I1 runtime semantic boundary while preserving source-event timing, transport identity, presence, freshness, session/reset behavior, and provenance without fabricating physiological inference?

---

## 1. Scope and isolation

I2 is created from updated `origin/main` after I1 merged. It does not stack on unmerged R1/R2/D1/D2/D3 branches. Raw JSONL is read through Q1's git blob inventory (`git cat-file`) and is not copied into Git.

A backward-compatible I1 Python extension accepts declared quality `NOT_EVALUATED` so replay can map envelopes without claiming Q2 availability. Frozen I1 JSON identities are unchanged.

---

## 2. I1 mapping

Each replayed row becomes an I1 input envelope. Quality is `NOT_EVALUATED` unless a later I3/Q2 adapter is invoked. `apply_external_quality_policy(...)` can reuse canonical `evaluate_availability` and is not used by default replay.

I1 outputs are `MockInferenceResult` / `NOT_IMPLEMENTED_MODEL_BOUNDARY` with `physiology_executed=false` and application state `NOT_EVALUATED` (or `PRESENCE_SUPPRESSED` when the I1 presence gate fires). No NORMAL / RAPID / APNEA class is emitted.

---

## 3. Sources and schemas

| Class | Role |
|---|---|
| `PHYSICAL_MR60_JSONL` | Q1-inventoried ESP blobs |
| `SYNTHETIC_Q1_Q2_FIXTURE` | tiny lineage-preserving fixture |
| `PUBLIC_OFFLINE_FIXTURE` | I1 public D0-shaped envelope |

Schema registry: `legacy_unversioned`, `1.0`, `1.1`, `1.2`. Missing fields stay `FIELD_ABSENT_LEGACY` or `FIELD_REQUIRED_BUT_MISSING_FOR_PRODUCTION`. They are not fake-filled.

Unknown telemetry keys are stored under `mr60_telemetry.auxiliary`.

---

## 4. Virtual clock and identity

Modes: `AS_RECORDED`, `FAST`, `SCALED`. Scaling and FAST change scheduling only. Evidence timestamps are never rewritten. Tests do not sleep.

`replay_event_id` is `replay_event:` plus SHA-256 of I2 contract, source, session, row index, seq, timestamp, and git blob SHA. `runtime_window_id` remains the I1 function. Row replay does not invent a physiological model window.

Session unit is one JSONL session. State resets on new session/file, device_id change, or firmware change. Seq gaps are audited; missing packets are not interpolated. Timestamp collisions/non-monotonic values are preserved. Truncated/invalid JSON is rejected with a typed reason.

---

## 5. Representative replay

| Role | Session | Result |
|---|---|---|
| modern 1.2 | heartrate watch preflight 15s | 150/150 |
| legacy 1.0 | breath15 preflight 10s | 99/99 |
| source republication | empty desk collector v2 | 299/299 |
| freeze-like 95-run | empty gate attempt03 15s | 149/149 |
| freeze-like 3598-run | occupied d15 v1 360s | 64-row prefix; blob replayable |
| timestamp collision | empty desk collector v1 | 684 replayed, 1 `TRUNCATED_ROW` |
| phase_age absent | empty desk prechange | 274 replayed, freshness explicitly absent |

Totals: 7/7 sessions successful, 1720 parsed, 1719 replayed, 1 rejected.

PR18/Pi blobs without git SHA are recorded unavailable. Pi host receive time is unavailable.

This does **not** mean presence/gap/freeze safety passed. I3 owns those gates.

---

## 6. Determinism

The same representative FAST replay twice yields identical event ids, I1 serializations, reject reasons, and compact checksums. Wall-clock execution time is excluded from evidence hashes.

---

## 7. Validation

`tests/test_mmwave_i2_jsonl_replay.py` 16 passed. `scripts/validate_mmwave_i2_jsonl_replay.py` gate **PASS_WITH_LIMITATIONS**.

I2_READY_FOR_I3 = YES
