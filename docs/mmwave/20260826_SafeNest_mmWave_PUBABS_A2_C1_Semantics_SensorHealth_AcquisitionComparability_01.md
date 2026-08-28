# SafeNest mmWave V2 — PUBABS-A2 C1 Semantics, Sensor-Health & Acquisition Comparability

- Phase: **PUBABS-A2 — C1 ABSENT semantics / sensor-health / acquisition comparability**
- Date: 2026-08-26
- Base SHA: `e2b50aa93bd3b37e91e6e3d455acfc65ed925464` (post-PR #158 `origin/main`)
- Branch: `research/mmwave-pubabs-a2-c1-validation`
- Status: **COMPLETE**
- A2 gate: **`A2_STRONG_INTERNAL_BOTH_CLASS_SOURCE`**
- A3 recommendation: **`RECOMMEND_A3`** (recommendation only; not authorized)
- Manifests: `datasets/mmwave/manifests/PUBABS_A2_c1_validation/`
- Raw payload: `/tmp/pubabs-a2-c1-raw/Data.zip` (**not committed**)

---

## Freeze boundaries (unchanged)

| Item | Status |
|---|---|
| M-PV3.8 | `RESOURCE_BLOCKED_CLOSED` |
| Membership | unchanged / not constructed |
| Evaluation | `NOT_EXECUTED` |
| M-PV4 / D2 | `UNAUTHORIZED` / locked |
| PUBABS-A3 | recommended only |

---

## C1 payload receipt

| Field | Value |
|---|---|
| DOI | `10.5281/zenodo.15032859` |
| File | `Data.zip` |
| Official size | `3372690765` |
| Official MD5 | `99067ac569e419fc122eef49635d72d0` |
| Local MD5 | **match** |
| Local SHA-256 | `bc120db7fb7ba8143dfd6499f7d80788d1d965e6a6ebf3e402fc34cb2870aa85` |
| Download window (UTC) | `2026-08-26T10:24:48Z` → `2026-08-26T11:55:44Z` |
| License | CC BY 4.0 |

Reference-only lineage (metadata only, not mixed): Zenodo `16533267` / SciData `10.1038/s41597-026-07314-z`.

---

## Empty-session inventory (all 11)

Positions **`-5..+5`** (inclusive). Every `Data/Empty_space/{pos}/plot_data.csv` opened.

| position | rows | bins | duration_s | Hz | finite | zero | frozen_max | nonzero_nonconst |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| -5 | 16889 | 180 | 899.936 | 18.7740 | 1.0 | 0.0 | 1 | True |
| -4 | 16948 | 180 | 899.902 | 18.8303 | 1.0 | 0.0 | 1 | True |
| -3 | 16950 | 180 | 899.917 | 18.8327 | 1.0 | 0.0 | 1 | True |
| -2 | 16950 | 180 | 899.885 | 18.8353 | 1.0 | 0.0 | 1 | True |
| -1 | 16957 | 180 | 899.917 | 18.8407 | 1.0 | 0.0 | 1 | True |
| 0 | 16962 | 180 | 900.006 | 18.8483 | 1.0 | 0.0 | 1 | True |
| 1 | 16954 | 180 | 899.878 | 18.8420 | 1.0 | 0.0 | 1 | True |
| 2 | 16960 | 180 | 899.996 | 18.8432 | 1.0 | 0.0 | 1 | True |
| 3 | 16958 | 180 | 899.897 | 18.8426 | 1.0 | 0.0 | 1 | True |
| 4 | 16954 | 180 | 899.925 | 18.8384 | 1.0 | 0.0 | 1 | True |
| 5 | 16957 | 180 | 899.958 | 18.8401 | 1.0 | 0.0 | 1 | True |

**Totals (inventory only, not membership):**
- total empty duration ≈ **165.0 min** (9899.2 s)
- non-overlapping 30 s contexts: **320**
- conservative stride-60 s contexts: **155**

Timing source: **`MEASURED_TIMESTAMP_NS`** (not metadata-nominal).

---

## Human-present structural inventory

Inspected **all 66** PRESENT `plot_data.csv` members in this archive:

- Subjects N1–N6 × 11 positions = 66
- Path pattern: `Data/Ni/Scenario_A/1_Meter/Face_toward_wall/{position}/plot_data.csv`
- Schema: identical to Empty (`2` columns; `180` complex bins; same encoding)
- Duration ≈ **179.7–180.8 s**; Hz ≈ **18.778–22.956**

---

## No-human semantics

| Field | Result |
|---|---|
| `NO_HUMAN_TARGET` | **VERIFIED** (official metadata + `Empty_space` + SciData Absence/N0 definition) |
| physiological source absence | **VERIFIED** as class semantics (not inferred from flat signal) |
| `VALID_RADAR_OBSERVATION` | **VERIFIED_FROM_SIGNAL_STRUCTURE** |

Rejected as ABSENT interpretations: breath-hold / apnea / motionless human / low-SNR-as-absence / algorithm-predicted absence.

---

## Sensor health

| Field | Result |
|---|---|
| Device-health telemetry | **`NOT_AVAILABLE`** |
| Signal-structure validity (all 11 empty) | **VERIFIED** (finite=1.0, zero=0, bins=180, non-constant, temporal range-bin variation) |

---

## Position / acquisition comparability

Same 11 positions `-5..+5` for Empty and each of N1–N6 (Scenario_A / 1 m / face-toward-wall).

| Check | Result |
|---|---|
| Same schema / bins / encoding / cadence | **YES** |
| Same position framework | **YES** |
| Duration asymmetry | Empty ~900 s vs Present ~180 s → acquisition difference **MEDIUM**, not blocking if windowed |

---

## Acquisition / domain confounds

| Class | Assessment |
|---|---|
| `ACQUISITION_CONFOUND_RISK` | **MEDIUM** |
| Blocking? | **No** |
| Environment vs SafeNest MR60 | Through-wall robot UWB classroom — A3 domain issue, not A2 internal invalidity |

---

## A3 structural plausibility (not implemented)

| Question | Answer |
|---|---|
| Stable complex range-bin frames? | **YES** (180 bins/frame) |
| Temporal sequence coherent? | **YES** (monotonic ns timestamps, ~18.8 Hz) |
| Deterministic target/range representation plausible? | **YES** (pre-register rule in A3; no class-fitted bin choice here) |
| Requires label-driven fitting? | **NO** for structural conversion feasibility |

---

## A2 gate

```text
A2_STRONG_INTERNAL_BOTH_CLASS_SOURCE
```

A3 recommendation (not authorization):

```text
RECOMMEND_A3
```

---

## Explicit non-actions

- No membership construction / no silent add to `D1_FINAL_SELECTION_BOTH_CLASS_V1`
- No PUBABS-A3 execution, no `[300,1]` canonicalization in this phase
- No model inference / range-bin optimization by class score
- No M-PV3.8 reopen / M-PV4 / D2
- No git commit of `Data.zip`
