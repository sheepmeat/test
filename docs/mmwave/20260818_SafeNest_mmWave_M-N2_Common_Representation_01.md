# SafeNest M-N2 — Public ↔ MR60 Common Respiratory Representation

- Study ID: `M-N2_COMMON_REPRESENTATION_001`
- Date: 2026-08-18
- Phase: **M-N2 only**. No training. No M-N3 timing freeze.
- Script: `scripts/mmwave_m_n2_common_representation.py`
- Experimental cache (gitignored): `tmp/mmwave_m_n2/`

```text
PREDECESSOR_PUBLICATION_STATE:
LOCAL_COMMITTED_PENDING_GITHUB_PUBLICATION
```

GitHub fetch of `origin/main` succeeded, but canonical `main` still does **not** contain M-N0, M-N1, or PUBLIC-P0. This study used a provisional local integration branch. That does not invalidate the experiment. Publication must be normalized later (see §10).

The question this artifact answers:

> What simple representation preserves useful respiration information in the 110-subject public radar domain while also producing coherent, usable respiratory structure from real MR60BHA2 `0x0A13 breath_phase`?

---

## 1. Inputs

### Public (development only)

| Field | Value |
|---|---|
| Dataset | Zenodo `10.5281/zenodo.18599983` |
| Local archive | `datasets/raw_archives/external_datasets/db_records.zip` |
| Entry point | A1 `SafeRFFTReader` → A2 native unwrap on **reused A6 bin/channel** |
| Historical BPF_ZSCORE | **not used** |
| Historical B scaler | **not used** |
| Split | historical TRAIN subjects only |
| LOCKED_TEST / NEW_MODEL_HELDOUT_TEST | **not accessed** |
| Recordings | 12 Post-exercise recordings from 8 TRAIN subjects (sitting + lying) |

30-second slices used for public RR comparison are **`EXPLORATORY_ONLY`**. They match A6 `W0000` duration for a like-for-like ACC RR check. They are not the M-N3 window.

Reference: Movesense chest ACC `rr_bpm` stored on A6 `W0000` (search band 0.1–0.7 Hz).

### Team MR60 (development reference)

| Field | Value |
|---|---|
| Physical subjects | **1** (`OWNER_CONFIRMED_SINGLE_SUBJECT`) |
| Independent respiratory GT | **ABSENT** |
| Supervised metrics | **not computed** |
| QA/failure sessions in primary score | **NO** |
| Pi files | **not used** (no `boot_id` crossing) |

Primary occupied/empty/desk-work sessions:

- `LEGACY_2026-07-25_occupied_d06_v1_360s`
- `LEGACY_2026-07-25_occupied_d09_v1_360s`
- `LEGACY_2026-07-28_occupied_d09_v2_360s`
- `LEGACY_2026-08-01_occupied_d09_v120_31min` (attempt01)
- `M-C0-PILOT-DESKWORK-001`
- empty contrast: `LEGACY_2026-07-25_empty_gate_v1_360s`, `LEGACY_2026-08-01_empty_v120_30min`

Paced sessions used **only** as periodicity diagnostics, not labels:

- `LEGACY_2026-07-26_breath_paced_15rpm` (cue 15)
- `LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt03` (cue 12)
- `LEGACY_2026-07-26_breath_paced_20rpm_deep` (cue 20)

Stale samples (`phase_age_ms > 2000`) were dropped. Occupied/empty/desk-work dropped **0** stale rows. Timing used `ts_monotonic_ms` (not a pretended uniform grid). Empirical median dt was ~0.100 s on every loaded Team file; that is an observation, not a frozen contract.

---

## 2. Candidates

No candidate multiplies MR60 by a public/MR60 std ratio. No old B scaler. Per-recording MAD, where used, is a local scale-free transform, not a global statistic fitted on held-out or MR60-as-TRAIN data.

| ID | Definition | Scale handling | Complexity |
|---|---|---|---|
| **R1** | Linear detrend vs elapsed time: `x(t) − (at+b)` | Keeps native units | Trivial |
| **R2** | Time-aware first derivative: `(x[i]−x[i−1]) / Δt` | Offset and absolute unit drop out | Trivial |
| **R3** | New 0.10–0.70 Hz order-2 bandpass, then per-recording MAD | Local MAD only | Filter + MAD |

R3 band is the **A4 ACC search band** (public RR 6–42 bpm). It is **not** historical B `0.1–0.5 Hz / order 4 / BPF_ZSCORE`.

R3 filter on non-uniform samples is marked `R3_EXPLORATORY_FILTER_ON_NATIVE_SAMPLES` when dt irregularity is large. It is not an M-N3 resampler.

**R4** was not added. R1–R3 already separated information retention from scale/unit behavior.

Per-window z-score was **not** used. It would make domains look similar by erasing amplitude and could hide empty-vs-occupied collapse.

---

## 3. Public respiratory information

In-band spectral peak (0.10–0.70 Hz) on the exploratory 30 s slice vs Movesense ACC RR.

| Representation | n | Median \|Δbpm\| | Within 2 bpm | Within 4 bpm | Median band fraction |
|---|---:|---:|---:|---:|---:|
| R1 | 12 | 15.0 | 0.33 | 0.33 | 0.66 |
| **R2** | 12 | **2.0** | 0.33 | **0.58** | 0.58 |
| R3 | 12 | 13.0 | 0.42 | 0.42 | 0.95* |

\*R3 band fraction is inflated because R3 *is* a respiration-band filter. It is not an independent information score.

NORMAL-range ACC RR (10–25 bpm) is where the public domain is most informative:

| Recording | ACC RR | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| p001 sitting post-ex | 16 | 15.9 | **16.0** | 15.9 |
| p007 sitting post-ex | 16 | 15.9 | **16.0** | 15.9 |
| p008 sitting post-ex | 20 | 21.9 | **22.0** | 21.9 |
| p011 sitting post-ex | 16 | 17.9 | **18.0** | 17.9 |
| p004 sitting post-ex | 24 | 8.0 | **26.0** | 8.0 |
| p004 lying post-ex | 22 | 12.0 | **24.0** | 12.0 |
| p008 lying post-ex | 22 | 8.0 | **24.0** | 23.9 |

RAPID ACC RR (≥25 bpm) is **under-estimated by all three** (often ~14–16 bpm). 42 bpm sits on the 0.70 Hz band edge. M-N2 does not claim a high-rate public match.

A1 alignment for these recordings: `EXACT_ALIGNMENT`. Finite fraction: 1.0.

---

## 4. MR60 domain behavior

No Accuracy / Macro-F1 / recall was computed. Filename, paced cue, and `breath_rate_raw` are not independent GT.

| Session | Raw max \|phase\| | R1 bpm | R2 bpm | R3 bpm | Band frac R1/R2/R3 |
|---|---:|---:|---:|---:|---|
| occupied D06 | 1.08 | 14.0 | 18.1 | 14.0 | 0.93 / 0.99 / 0.95 |
| occupied D09 | 1.01 | 18.0 | 18.1 | 18.0 | 0.89 / 0.99 / 0.95 |
| occupied D09 v2 | 1.24 | 24.0 | 24.1 | 24.0 | 1.00 / 0.99 / 1.00 |
| occupied 31 min attempt01 | 0.91 | 18.0 | 26.1 | 18.0 | 0.66 / 0.96 / 0.89 |
| PR18 Desk-work | 0.75 | 20.0 | 22.1 | 20.0 | 1.00 / 0.99 / 1.00 |
| empty 360 s | **0.00** | — | — | — | 0 / 0 / 0 |
| empty 30 min | **0.00** | — | — | — | 0 / 0 / 0 |

Occupied/desk-work values stay finite. No explosion. Native `|breath_phase|` is O(1), unlike public unwrapped radians. Derivative (R2) and MAD (R3) both remove that unit mismatch without a hand-tuned gain.

Empty-room `breath_phase` is a constant 0 on these files. That is **device/no-person collapse**, not an APNEA label.

Paced cue diagnostic only (not GT): valid 12 rpm → 12 bpm on R1/R2/R3. 15 rpm cue → 10 bpm on the 30 s slice. 20 rpm deep → R2 18.1 vs R1/R3 10. Cue mismatch is expected; M-N0 already documented that paced instruction is not physiology.

Cross-session occupied structure is visible on one person across dates/distances. That is **device-domain compatibility**, not unseen-person generalization.

---

## 5. Comparison and decision

| Representation | Public respiratory information | MR60 stability/periodicity | Scale/unit robustness | Runtime complexity | Main weakness | Decision |
|---|---|---|---|---|---|---|
| R1 centered/detrended | Weak outside a few NORMAL files; often harmonic-halves | Occupied periodic; empty collapses | Poor (keeps native units) | Lowest | Public RR poorly retained | **REJECT** |
| **R2 Δx/Δt** | Best NORMAL-range ACC agreement (median \|Δbpm\| = 2.0) | Occupied 18–26 bpm, high band fraction; empty collapses | Strong (offset/unit removed) | Lowest | Amplifies high-frequency noise; RAPID public RR still weak | **SELECT_PRIMARY** |
| R3 band + MAD | Similar to R1 on several files; tautological band fraction | Occupied 14–24 bpm; empty collapses | Strong (local MAD) | Filter + MAD; exploratory on irregular dt | More moving parts; not better than R2 on public NORMAL | **RETAIN_FALLBACK** |

**Primary: R2 — time-aware first derivative of native unwrapped phase (public) / `breath_phase` (MR60).**

Why: simplest representation that actually keeps public NORMAL-range respiratory rate information **and** yields stable occupied-vs-empty structure on real MR60 without arbitrary domain scaling.

**Fallback: R3.** Keep if M-N3 finds derivative noise unacceptable. Do not silently revert to historical BPF_ZSCORE.

**Rejected: R1.** Useful as a plotting overlay, not as the common contract.

---

## 6. Limitations (must stay visible)

**Limitation A — target supervision.** Team MR60 still has no independent respiratory GT. Paced cue and vendor BPM were not used as labels.

**Limitation B — subject generalization.** All Team MR60 files are one person. Beautiful cross-session MR60 plots are not multi-person evidence.

**Public RAPID RR.** High ACC rates are not recovered well in this 30 s in-band peak test. Do not freeze a class map here.

**Empty ≠ APNEA.** Constant-zero empty-room phase is a device contrast only.

**Timing not frozen.** Both domains happened to sit near 10 Hz here. M-N3 still owns window, sample count, and resampling.

---

## 7. M-N3 handoff

Carry forward:

1. Public source = A2 native unwrap with existing A6 bin/channel (do not reopen range-bin search unless R2/R3 both fail later).
2. MR60 source = `breath_phase` with `ts_monotonic_ms`, drop stale `phase_age_ms`.
3. Primary representation = R2 time-aware derivative.
4. Fallback = R3 0.10–0.70 Hz + per-recording MAD.
5. Compare a few window/timing options on public TRAIN + this same MR60 development subset only.
6. Do not inherit 30 s / 300 / 10 Hz / BPF_ZSCORE as the new contract.

---

## 8. Focused validation

- Public A1 decode: `EXACT_ALIGNMENT` on the 12 development recordings.
- Representation outputs finite on occupied/desk-work/paced files.
- Empty files finite but collapsed (max abs 0).
- Timestamp order: MR60 sorted by `ts_monotonic_ms`; longest contiguous run used if gaps exist.
- No LOCKED_TEST subject IDs in the public list.
- No Pi `boot_id` files.
- Historical A1/A2/A6 arrays were not overwritten.
- No global public↔MR60 gain.

---

## 9. Gate

```text
M-N2 = PASS_WITH_LIMITATIONS
M-N3 authorized = YES (after review; timing still unfrozen)
Production model trained = NO
MR60 adaptation = NO
```

PASS_WITH_LIMITATIONS because R2 is a credible cross-domain bridge on public NORMAL-range RR and on single-subject MR60 occupied/empty structure, while RAPID public RR and unseen-person MR60 claims remain out of reach.

---

## 10. GitHub recovery publication plan

Do **not** open one PR from `work/mmwave-m-n2-premerge`.

1. Merge M-N0 (`feature/mmwave-m-n0-team-mr60-inventory`, PR #96 if still open).
2. Merge PUBLIC-P0 (`docs/mmwave-public-p0-dataset-readiness` / commit `d944e10`).
3. Refit M-N1 from then-current main (PR #97 currently stacked on M-N0).
4. `git switch -c feature/mmwave-m-n2-common-representation origin/main`
5. Cherry-pick **only** the M-N2 commit from this provisional branch.
6. Confirm `git diff origin/main...HEAD --name-only` is M-N2-specific.

This study must not be re-run unless that transplant changes the code or numbers.
