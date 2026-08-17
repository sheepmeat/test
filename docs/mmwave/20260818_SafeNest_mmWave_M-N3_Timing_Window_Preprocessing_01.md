# SafeNest M-N3 — Timing, Window, and Preprocessing Selection

- Study ID: `M-N3_TIMING_WINDOW_PREPROCESSING_001`
- Date: 2026-08-18
- Phase: **M-N3 only**. No training. Canonical freeze is M-N4.
- Script: `scripts/mmwave_m_n3_timing_preprocessing.py`
- Experimental cache (gitignored): `tmp/mmwave_m_n3/`
- Representation inherited from M-N2: **R2** (time-aware first derivative). R1 not reopened.

```text
PREDECESSOR_PUBLICATION_STATE:
LOCAL_COMMITTED_PENDING_GITHUB_PUBLICATION
```

Canonical `origin/main` still does not contain M-N0 / PUBLIC-P0 / M-N1 / M-N2. This study ran on `work/mmwave-m-n3-premerge` branched from corrected M-N2 (`a32dce2`). Do not publish that combined predecessor history as one PR.

The question this artifact answers:

> Given R2, what timing basis, derivative construction, gap/duplicate rule, noise handling, amplitude-scale rule, window, and fixed-grid rate should M-N4 freeze?

---

## 1. Timing problem

A received telemetry row is not automatically a new `breath_phase` sample. Pi publication can republish an older phase while `seq` / host time still advance. Differentiating those rows invents false R2 spikes.

`ts_monotonic_ms - phase_age_ms` is used as a **firmware dequeue/update estimate**. It is **not** physical radar acquisition time.

Compared (small set, not a sweep):

| ID | Rule |
|---|---|
| T1 | R2 on every telemetry row timestamp |
| T2 | R2 only when the update estimate advances by > 8 ms |
| T3 | T2 event sequence, then R2, then resample to a fixed model grid |

Equal consecutive `breath_phase` values are **not** treated as duplicates. PR18 Desk-work has 229 new updates with unchanged numeric phase; D06 occupied has 249. Value equality alone is insufficient.

---

## 2. Observed timing

| Domain | Observation |
|---|---|
| Public native | 28/28 TRAIN development recordings: median frame Δt = **0.100 s** (10 Hz). Each frame is a new radar sample. |
| Historical Team occupied / PR18 | Row median Δt ≈ **100 ms**. T2 republications ≈ 0 on clean occupied D06/D09; PR18 Desk-work **1 / 1799**. T2 update median ≈ 100–116 ms. |
| Empty gate / 30 min empty | Constant `breath_phase = 0`. T2 drops republications of a frozen update (empty gate **492 / 3598**). Remaining events stay at 0. |
| Recent Pi `20260817_08` | **RECENT_PI_RUNTIME_REFERENCE** only. Two `boot_id`s; windows never cross boots. Host publication median ≈ **100.1 ms** (~10 Hz). Nested `ts_monotonic_ms` median Δt ≈ **121 ms**. T2 update median ≈ **140 ms** (~7.1 Hz). Republication fraction **16–22%**. 300 T2 events span **37–43 s**, not a 30 s × 10 Hz tensor. |

Publication row == new phase update: **NOT_ALWAYS**.

Selected timing: **T3** (T2 events → R2 → fixed grid).

Why: respects genuine updates on Pi, does not invent derivatives on republications, and still matches PR18/legacy occupied files where almost every row already is a new update. Legacy files without `phase_age_ms` would fall back to row time with an explicit provenance flag; the M-N2 development files used here all have `phase_age_ms`.

M-N2 `phase_age_ms > 2000` was **not** inherited. Gap rule is relative:

```text
invalidate / start a new segment if Δt_update > max(0.40 s, 4 × median_update_dt)
```

No derivative across that gap. No interpolation across the gap. No boot crossing.

---

## 3. R2 construction and noise

Derivative (causal):

```text
R2[i] = (phase[i] − phase[i−1]) / Δt_update[i]
```

only on accepted T2 events. First sample exists after the first interval; at most two model bins of edge hold are allowed when resampling.

Noise candidates on a fixed 30 s / 10 Hz exploratory grid (TRAIN-only, same 28 recordings):

| ID | Rule | Continuous RR &lt; 25 within 4 bpm | High-RR fundamental retained |
|---|---|---:|---:|
| N0 | raw R2 | 0.89 (8/9) | **0.47** |
| N1 | causal EMA τ=0.15 s on phase, then R2 | 0.89 | 0.40 |
| N2 | R2, then causal EMA τ=0.15 s | 0.89 | 0.40 |

N1/N2 did not improve low-RR retention and slightly reduced high-RR fundamental energy. Historical B `0.1–0.5 Hz / order 4 / BPF_ZSCORE` was not used. `filtfilt` was not used as a runtime candidate.

**Selected noise: N0.** Extra smoothing is not required to keep R2 usable and would be the wrong way to “fix” high-RR peaks.

---

## 4. Amplitude scale

M-N2 left `R2_AMPLITUDE_SCALE_CONTRACT = UNRESOLVED` because `d(ax+b)/dt = a dx/dt`.

| ID | Rule | Cross-domain | Empty/near-zero |
|---|---|---|---|
| S0 | raw R2 amplitude | Public non-breathing-window unscaled std ≈ 4.4 vs occupied MR60 unscaled std ≈ 0.30–1.08 | Empty stays 0, but occupied public/MR60 scales remain incompatible |
| S1 | **current-window MAD**; if MAD &lt; 1e-6 emit zeros | Occupied MR60 std after S1 ≈ 1.2–2.6, comparable order to scaled public | Empty **collapses** (std 0, no fake unit-amplitude waveform) |
| S2 | TRAIN-only median MAD from the 28-file N0 30 s/10 Hz windows (= 4.39) | Occupied MR60 after S2 std ≈ 0.07–0.25 — public/MR60 mismatch **remains** | Empty stays 0 |

No public/MR60 std matching. No MR60-specific gain. No historical B scaler.

**Selected: S1 window-local MAD**, applied to the completed model window (runtime-causal once the window exists). Near-zero / empty: **output zeros**, do not divide.

S1 can erase absolute amplitude. If M-N4 needs a compact amplitude/quality sidecar, use the **unscaled window MAD** as a candidate scalar — not extra waveform channels in M-N3.

```text
R2_AMPLITUDE_SCALE_CONTRACT = RESOLVED_S1_WINDOW_MAD
```

---

## 5. High-RR: representation vs peak picker

Diagnostic band **0.08–1.00 Hz** is **DIAGNOSTIC_ONLY**. It is not the new model filter. The old 0.10–0.70 Hz edge is not frozen (42 bpm = 0.70 Hz).

On N0+S1, 30 s, 10 Hz, 15 windows with ACC RR ≥ 25 bpm:

| Class | n | Meaning |
|---|---:|---|
| PEAK_MATCH | 1 | wide-band peak within 4 bpm of ACC |
| FUNDAMENTAL_ENERGY_RETAINED_PEAK_MISMATCH | 6 | energy near f_ref ≥ 0.75 × energy near f_ref/2, but the largest peak is elsewhere |
| SUBHARMONIC_PEAK | 5 | largest peak ≈ f_ref/2 and weak fundamental |
| other under-estimate / 0.70 Hz-adjacent | 3 | mixed, several Rest + non-breathing |

Examples that keep fundamental energy while the M-N2-style peak is wrong: p002 sitting post-ex 42 bpm (ratio 0.91, peak 14); p005 sitting post-ex 38 bpm (ratio 1.03, peak 12); p003 sitting post-ex 32 bpm (ratio 1.30, peak 12). p021 sitting post-ex 28 bpm matches.

N0 does **not** systematically destroy high-RR fundamentals. Residual errors are largely peak-selection / 30 s slice / subharmonic weighting — not a reason to reopen R2. No RR estimator was trained.

---

## 6. Non-breathing overlap

Interpreted separately from continuous breathing. All 12 TRAIN Rest `W0000` windows overlap a source non-breathing interval. Single-number RR agreement is not the criterion.

Those 12 windows do **not** collapse under S1 (they are not empty-room zeros). Median wide-band fraction ≈ 0.72. Preprocessing does not manufacture a clean empty-like constant, and it does not invent a high-confidence single RR. Not APNEA GT.

Continuous-breathing RR &lt; 25 bpm (9 recordings): median \|Δbpm\| = **2.0**, within 4 bpm = **8/9** at 30 s × 10 Hz and **7/9** at 30 s × 8 Hz.

---

## 7. Window and rate

Compared 20 / 30 / 40 s × 8 / 10 Hz on the selected T3+N0+S1 path (and N2 as a noise check). Not a Cartesian sweep of every earlier choice.

| Window × rate | Samples | RR &lt; 25 within 4 bpm | High-RR fundamental retained | Notes |
|---|---:|---:|---:|---|
| 20 s × 8/10 Hz | 160 / 200 | 0.78 | 0.33–0.40 | less low-frequency observation |
| **30 s × 8 Hz** | **240** | 0.78 | **0.47** | near Pi update cadence |
| 30 s × 10 Hz | 300 | **0.89** | **0.47** | public-native rate; more Pi interpolation |
| 40 s × 8/10 Hz | 320 / 400 | 0.78 | 0.27–0.33 | extra latency; ACC reference is still 30 s W0000 |

30 s is the duration that keeps high-RR fundamental energy without 40 s latency. 8 Hz is selected over 10 Hz because genuine Pi phase updates are ~7.1 Hz; resampling Pi rows to 10 Hz would interpolate extra samples. Public 10 Hz → 8 Hz is a mild downsample of content well below 4 Hz Nyquist. Linear interpolation of R2 onto the grid is allowed only inside a gap-free segment (edge hold ≤ 2 bins). **Long-gap interpolation is forbidden.**

`[1, 300, 1]` was **not** inherited. 30 s × 10 Hz = 300 remains the fallback because public radar is natively 10 Hz, not because historical B used 300.

Empty files collapse at every compared window/rate. Occupied D06 / Desk-work stay finite and periodic (≈ 18–22 bpm on the diagnostic peak, not GT).

---

## 8. Comparison

| Contract | Timing | Noise | Scale | Window | Rate | Samples | Public evidence | MR60 / runtime | Decision |
|---|---|---|---|---:|---:|---:|---|---|---|
| **T3 N0 S1 30 s 8 Hz** | update estimate → R2 → grid | none | window MAD | 30 | 8 | 240 | continuous RR&lt;25 median \|Δbpm\|=2.0; high-RR energy often present | occupied periodic; empty → zeros; Pi cadence fit | **SELECT_PRIMARY** |
| T3 N0 S1 30 s 10 Hz | same | none | window MAD | 30 | 10 | 300 | +1/9 within 4 bpm vs 8 Hz | occupied/empty OK; interpolates Pi updates | **RETAIN_FALLBACK** |
| T1 raw rows | row time | — | — | — | — | — | public identical (no republication) | Pi 16–22% false new samples | **REJECT** |
| N1 or N2 | T3 | EMA 0.15 s | S1 | 30 | 10 | 300 | no low-RR gain; worse high-RR energy | occupied OK | **REJECT** |
| S0 raw amplitude | T3 | N0 | none | 30 | 10 | 300 | RR unchanged | public vs MR60 scale mismatch | **REJECT** |
| S2 TRAIN MAD | T3 | N0 | global TRAIN | 30 | 10 | 300 | RR unchanged | MR60 still ~10× smaller | **REJECT** |
| 20 s or 40 s | T3 | N0 | S1 | 20/40 | 8/10 | 160–400 | no high-RR gain; 20 s weaker | OK but 40 s slower | **REJECT** |

---

## 9. Selected contract (for M-N4 freeze)

```text
representation:            R2 derivative
phase-event timing basis:  ts_monotonic_ms - phase_age_ms  (update estimate, not physical t)
duplicate/republication:   drop rows whose update estimate does not advance by > 8 ms
gap handling:              segment / invalidate window if Δt_update > max(0.40 s, 4×median_update_dt)
derivative definition:     (x[i]-x[i-1]) / Δt_update on accepted events only
noise handling:            N0 (none)
amplitude scaling:         S1 current-window MAD; MAD < 1e-6 → zeros
window duration:           30 s
target sampling rate:      8 Hz
resulting sample count:    240
resampling method:         linear interpolation of R2 onto a uniform grid after the derivative
interpolation/gap boundary: edge hold ≤ 2 bins; no long-gap interpolation
runtime causality:         YES (window-local MAD uses the completed window only)
known limitations:         single-subject MR60; no Team respiratory GT; high-RR peak picker still imperfect;
                           Pi 300-event span ≠ 30 s; some Rest windows mix non-breathing with ACC RR
```

Fallback (one): same contract at **10 Hz / 300 samples** if M-N4 prefers the public-native grid.

M-N4 should freeze this contract with the new dataset/split strategy. Do not redo the timing study unless inputs change.

---

## 10. Focused validation

- Clean occupied/empty/desk-work: finite R2; empty S1 collapsed to zeros.
- Pi: two boots handled separately; no window across `boot_id`.
- Large-gap derivative: forbidden by segment rule (Pi T2 gaps counted, not crossed).
- Fixed-grid length deterministic: `n = round(window_s × hz)`.
- S1 near-zero path emits zeros.
- Transforms are causal given a completed window; no `filtfilt` in the contract.
- LOCKED_TEST not accessed. `NEW_MODEL_HELDOUT_TEST` is absent from the historical split file and was not created.

---

## 11. Gate

```text
M-N3 = PASS_WITH_LIMITATIONS
M-N4 authorized = YES (after review; this file is a recommendation, not the freeze)
Production model trained = NO
MR60 adaptation = NO
```

PASS_WITH_LIMITATIONS because the contract is specific enough to freeze, while Team MR60 remains one person with no independent respiratory GT, high-RR hand-coded peaks remain imperfect, and some live files still need the update-estimate (not physical) timing interpretation.

---

## 12. GitHub recovery publication plan

Do **not** open one PR from `work/mmwave-m-n3-premerge`.

1. Merge M-N0, PUBLIC-P0, M-N1, then transplant M-N2-only commits.
2. `git switch -c feature/mmwave-m-n3-timing-preprocessing origin/main`
3. Cherry-pick **only** the M-N3-specific commit(s).
4. Confirm `git diff origin/main...HEAD --name-only` is M-N3-specific.

Do not rerun M-N3 on transplant unless the analysis code or input files change.
