# SafeNest Q2 — Gap / Freeze / Flat / Stale Input-Unavailability Contract

- Contract ID: `MMWAVE_V2_Q2_INPUT_AVAILABILITY_CONTRACT_V1`
- Quality profile: `MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1`
- Date: 2026-08-22
- Phase: **Q2 only**. No training, no R1, no Q3 APNEA false-positive evaluation, no D1/D2/D3.
- Gate: **PASS_WITH_LIMITATIONS**
- Q1 dependency: `MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1` at `b643bbfa48c07897406fa168f959b2037ad9adae`

This artifact answers:

> Which timing/signal-integrity failures are severe enough that SafeNest must refuse physiological inference entirely, and how can those failures be represented as deterministic synthetic quality targets without turning them into NORMAL or APNEA-proxy examples?

---

## 1. Scope and isolation

Q2 is stacked on the unmerged Q1 commit. It does not rewrite Q1 history. Unmerged D1/D2/R1 ancestry is absent.

Q2 freezes an **input availability contract**. It does not choose neural-vs-rule quality-head architecture (M-PV1) and does not measure NORMAL→APNEA false positives (Q3).

---

## 2. Q1 inheritance

Consumed as frozen facts:

- receive/publish nominal 100 ms
- source-update estimate `ts_monotonic_ms - phase_age_ms`
- core source interval median 101 / p95 128 / p99 197 ms
- exact transport duplicates 0
- source republication = new `seq` and source estimate advances ≤ 8 ms
- numeric plateau ≠ duplicate or freeze
- Q1 modes `CLEAN`, `CADENCE_JITTER`, isolated `SOURCE_REPUBLICATION`, `JITTER_PLUS_SOURCE_REPUBLICATION` remain **potentially valid**
- Q1 handoff long runs and huge source intervals are validation evidence, not threshold values

---

## 3. Availability states and precedence

```text
presence gate
    ↓
input quality / availability gate
    ↓
breathing evidence / RR / temporal-hold reasoning
```

| Presence | Quality | State |
|---|---|---|
| `human_detected_raw` false | any | `PRESENCE_SUPPRESSED` |
| null / unknown | any | `PRESENCE_SUPPRESSED` |
| true | invalid | `INPUT_UNAVAILABLE` |
| true | valid | `PHYSIOLOGY_ELIGIBLE` |

Presence is never inferred from waveform amplitude. No-person is not APNEA. Invalid quality is not a fourth physiological class.

Reason precedence is deterministic: `PRESENCE_NOT_CONFIRMED` → timestamp faults → `LARGE_GAP` → `SOURCE_FREEZE` → `SOURCE_STALE` → `SIGNAL_FLAT_EXACT` → `RECOVERY_WARMUP`. All applicable reasons are retained.

A candidate window containing any severe quality fault is `INVALID_WINDOW_INPUT_UNAVAILABLE`. There is no 29 s valid + 1 s broken majority vote.

---

## 4. Gap

Any accepted source-update interval in the candidate window that exceeds `max(400 ms, 4 × window median source-update interval)` is a large gap.

- Time domain: source-update estimate, else native sample time
- Floor 400 ms and multiplier 4 are **inherited** from M-N4 (`REJECT_ENTIRE_WINDOW`, no long-gap interpolation)
- Fewer than 8 intervals: fail closed as `INSUFFICIENT_INTERVAL_HISTORY` (M-N4 initialization)
- Interpolation across a Q2 large gap is forbidden
- Synthetic example duration is 500 ms (roadmap explicit policy), strictly above the 400 ms detector

Q1 core p99 source interval is 197 ms, so ordinary Q1 jitter stays below this bound.

---

## 5. Freeze

Transport/receive time continues while the source-update estimate does not advance by more than 8 ms for **at least 400 ms**.

This is not `breath_phase[i] == breath_phase[i-1]`. Isolated Q1 republication (core max run 1, ~100 ms) is not freeze. Q1 handoff runs 95–3598 validate that obvious freezes are caught; the threshold is not 3598.

---

## 6. Stale

`phase_age_ms >= 400` means the published source sample is older than the permitted gap. A new `seq` does not refresh a stale source.

- Production MR60 with missing freshness: `INPUT_UNAVAILABLE` (M-N4 `WINDOW_UNAVAILABLE`)
- Public native frames without `phase_age_ms`: staleness not applicable
- M-N3 `phase_age_ms > 2000` is **not** inherited
- Staleness is not inferred from amplitude

---

## 7. Flat vs low amplitude

Frozen exact-flat rule:

- any non-finite value, or
- unique finite values in the window == 1, or
- contiguous exact-equal span lasting ≥ 400 ms **while source events continue to advance**

Near-flat / MAD cutoffs are **not** frozen. A low-amplitude but dynamically varying trace remains `PHYSIOLOGY_ELIGIBLE`. Two-sample numeric plateaus are not flat.

---

## 8. Timestamp invalid

Non-monotonic time, non-positive intervals, or unresolvable collisions (`dt == 0`) are `TIMESTAMP_NON_MONOTONIC` / `TIMESTAMP_UNRESOLVED`. The Q1 receive-median 0 ms collision shape fails closed.

---

## 9. Recovery

After a fault, samples are `RECOVERY_WARMUP` until the next advancing source event. The current candidate window stays invalid. The final model-ready history duration (including 30 s) is deferred to M-PV1.

---

## 10. Synthetic quality profile

`MMWAVE_V2_Q2_INPUT_UNAVAILABLE_CORRUPTION_PROFILE_V1` builds on Q1 rather than copying it.

Modes: `CLEAN_VALID`, `LARGE_GAP`, `SOURCE_FREEZE`, `STALE_SOURCE`, `FLAT_EXACT`, `JITTER_PLUS_LARGE_GAP`, `REPUBLICATION_TO_FREEZE`.

Invalid target is `INPUT_UNAVAILABLE`. Physiology labels are not rewritten. No synthetic APNEA. No learned interpolation.

---

## 11. Q1 handoff validation (quality only)

| Case | Result |
|---|---|
| run 3598 / 2884 / 1582 / 683 / 598 / 425 / 95 | `INPUT_UNAVAILABLE` / `SOURCE_FREEZE` |
| 158380 ms and 42637 ms source interval | `INPUT_UNAVAILABLE` / `LARGE_GAP` |
| receive timestamp collision | `INPUT_UNAVAILABLE` / `TIMESTAMP_UNRESOLVED` |

Physiology of those sessions was not interpreted.

---

## 12. Limitations (why not PASS)

- Near-flat non-zero threshold deferred to R2/R3/M-PV1
- Model-ready recovery history duration deferred to M-PV1
- Pi host timestamp residual still unavailable from Q1

These limitations do not allow corrupted input to become APNEA.

---

## 13. Handoff to Q3 / M-PV1

Frozen for later phases: availability states, reason taxonomy, gap/freeze/stale/exact-flat rules, synthetic invalid-target profile, presence precedence, recovery fail-closed window mapping.

Unfrozen: model architecture, feature schema, quality-head design, breathing evidence, RR, temporal hold, APNEA false-positive gate, final runtime tensor contract.
