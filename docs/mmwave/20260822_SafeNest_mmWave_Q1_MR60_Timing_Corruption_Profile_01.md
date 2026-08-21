# SafeNest Q1 — MR60-like Cadence, Jitter, and Duplicate Synthetic Corruption Profile

- Profile ID: `MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1`
- Date: 2026-08-22
- Phase: **Q1 only**. No training, no R1, no Q2 thresholds, no D1/D2/D3.
- Gate: **PASS_WITH_LIMITATIONS**
- Base: `origin/main` `e74e54736d5cde1773d530b8398a630486270785`

This artifact answers:

> What cadence, source-update timing, arrival jitter, packet duplication/republication, and repeated-source-sample behavior does the existing SafeNest MR60 runtime evidence actually exhibit, and how can those transport/timing effects be reproduced deterministically on a generic public radar trace without importing MR60 physiology or labels?

---

## 1. MR60 runtime evidence used

Q1 re-parsed Git blobs already catalogued by M-N0. Raw JSONL was not copied into the Q1 tree.

| Class | Count | Q1 use |
|---|---:|---|
| M-N0 physical Team sessions | 74 | discovered |
| PRE_PR18 ESP JSONL blobs present in this repo | 70 | timing analysis |
| Eligible core (pooled for TYPICAL/STRESSED parameters) | 62 | empirical profile |
| Observed but held out of TYPICAL pooling (`Q2_HANDOFF_EVIDENCE`) | 7 | cadence/repeat observation only |
| Receive-cadence only (`phase_age_ms` absent) | 1 | receive intervals only |
| PR18 Pilot + Aug-08 live raw (no blob in this repo) | 4 | excluded |
| Recent Pi runtime-reference (not in this repo) | 7 | excluded; not re-parsed |

Runtime identities in the analyzed ESP set:

- schema `1.0` / `firmware_version` null
- schema `1.1` / `safenest-mr60-esp/1.1.0`
- schema `1.2` / `safenest-mr60-esp/1.2.0`

Receive cadence is compatible across those strata (median 100 ms). Source-update medians are not: schema 1.0 session medians cluster near 117 ms, while 1.1.0/1.2.0 cluster near 100–101 ms. The frozen profile records those strata and uses pooled-core quantiles for the default inverse-CDF.

M-N7 republication counts were cross-checked as already-published device-domain evidence. They were not used to retune parameters.

---

## 2. Source vs receive timing

ESP JSONL in this repository has **no Pi capture timestamp**.

| Domain | Field | Authority in Q1 |
|---|---|---|
| ESP row / publish time | `ts_monotonic_ms` | receive/publish cadence |
| Source-update estimate | `ts_monotonic_ms - phase_age_ms` | source cadence and source jitter |
| Transport identity | `seq` | exact packet duplicate vs new packet |
| Freshness | `phase_age_ms` | whether the vendor sample advanced |

`ts_monotonic_ms` is not physical radar acquisition time. The source estimate is the M-N4 firmware dequeue/update estimate.

---

## 3. Nominal cadence

On 62 core sessions:

- ESP publish/receive median interval = **100 ms** (10 Hz). p95 = 100 ms, p99 = 101 ms, max = 300 ms.
- Source-update median interval = **101 ms**. Session-median source interval = **116.5 ms** because schema 1.0 sessions update slower than the 10 Hz row clock even when most rows are still accepted events.

All-session receive statistics that still include Q2-handoff files show min 0 ms (one broken 2026-07-13 collector) and p99 = 102 ms. Those extremes are not used as TYPICAL synthesis parameters.

---

## 4. Observed jitter

Definitions:

```text
receive_jitter_i = receive_interval_i - 100 ms
source_jitter_i  = source_update_interval_i - 100 ms
```

Core receive jitter is essentially zero (median 0, MAD 0, p99 = 1 ms).

Core source jitter is the MR60-like non-uniform cadence: median +1 ms, MAD 14 ms, p95 = 28 ms, p99 = 97 ms. Synthetic `CADENCE_JITTER` uses that source-jitter inverse-CDF, not the near-zero receive residual.

---

## 5. Exact duplicate vs source republication

Three repeat classes were kept separate.

**A. Exact transport duplicate** (`same seq` and `same ts_monotonic_ms`): **0** events in 160,589 parsed rows. `TRANSPORT_DUPLICATE` is therefore **not** a supported Q1 mode.

**B. Confirmed source republication** (new `seq`, source-update estimate does not advance by more than the M-N4 8 ms last-accepted guard): 5,098 core events in 24/62 core sessions; every such core run length is **1**. All 19,032 republications across core+handoff increment `seq` by 1. This is a new telemetry row republishing an unrefreshed source sample, not a duplicated packet identity.

**C. Numeric plateau only** (accepted source event with equal `breath_phase` versus the previous accepted event): common, and **not** treated as a duplicate or a freeze. Plateau fractions are recorded in the repeat audit and are **not** copied into the synthetic profile.

---

## 6. Frozen synthetic profile

Identity: `MMWAVE_V2_Q1_MR60_TIMING_CORRUPTION_PROFILE_V1`

Supported modes, all empirically justified:

- `CLEAN`
- `CADENCE_JITTER`
- `SOURCE_REPUBLICATION`
- `JITTER_PLUS_SOURCE_REPUBLICATION`

Severity:

- `NOMINAL` — occupied-like: 10 Hz, republication probability 0, no added jitter
- `TYPICAL` — pooled-core source jitter (p05–p95) and core session republication-fraction p75 = 0.012764
- `STRESSED` — p01–p99 source jitter and core empty-room median republication fraction = 0.139046

The engine delays or holds existing samples. It does not interpolate, amplitude-normalize, or emit class labels. Republication provenance points at the original kept sample index.

---

## 7. Why MR60 physiology is absent

Q1 inspected `breath_phase` only as a supporting identity field for numeric-plateau accounting. The profile stores timing quantiles, republication probabilities, and mode contracts. It does not store MR60 amplitudes, RR targets, APNEA/NORMAL labels, or model outputs. Parameters were not selected by asking which corruption makes V1 fail or V2 look better.

---

## 8. Limitations

- Recent Pi host JSONL is not in this standalone repository, so Q1 did not re-parse the M-N3 Pi 7–10 Hz / 16–22% republication observation into frozen numbers.
- PR18 and 2026-08-08 raw files have no Git blob here.
- Most schema 1.0 sessions lack `firmware_version`.
- There is no separate Pi receive clock in the ESP JSONL.
- Exact transport duplicates were not observed; a networking-style duplicate injector was not invented.

Gate is therefore `PASS_WITH_LIMITATIONS`, not `BLOCKED`: source vs receive fields are distinguishable, republication identity is `seq`-defensible, and the core profile is versioned.

---

## 9. Explicitly deferred to Q2

Q1 records, but does not convert into rejection policy:

- longest observed source-republication run = 3598 (`LEGACY_2026-07-25_occupied_d15_v1_360s`)
- other long runs: 2884, 1582, 683, 598, 425, 95
- source-interval maxima of 158380 ms and 42637 ms
- one session whose receive timestamps collide at 0 ms median
- freeze / flat / stale / large-gap / `INPUT_UNAVAILABLE` thresholds

Those are `Q2_HANDOFF_EVIDENCE`. Q1 does not decide `if run > N → reject`.

---

## Validation

Focused generator, validator, and `tests/test_mmwave_q1_mr60_timing_corruption.py` check profile parse, determinism, lineage, CLEAN identity, jitter 1:1 ordering, republication provenance, no synthetic class labels, no D2 access, and no Q2 threshold freeze.
