# SafeNest mmWave V2 — PUBABS-A4 C1 Availability / Domain / Leakage Stress Audit

- Phase: **PUBABS-A4**
- Date: 2026-08-26
- Base SHA (post-PR #162): `b020f22ab40ca1b888ce72f11a96688f8627a47e`
- Branch: `research/mmwave-pubabs-a4-availability-domain-leakage`
- Frozen proposal SHA-256: `cfce866f659658e772e833f64e881549a4244b8c9daaa85423b343f34c424446`
- Primary population: **ALL 77** C1 sessions (VALID-34 secondary only)
- A4 gate: **`A4_CLEAR_WITH_LIMITATIONS_FOR_A5`**
- A5 recommendation: **`RECOMMEND_A5`**
- Manifest: `datasets/mmwave/manifests/PUBABS_A4_c1_availability_domain_leakage/`

Frozen R1T / RG-S1 / historical R1 **unchanged**. No model inference. No membership. A5 not executed.

---

## Verdict

The frozen adapter does not consume class labels, yet **adapter availability is strongly class-correlated** (PRESENT fail 41/66 vs ABSENT fail 2/11). Failures concentrate in **subjects N1/N2/N6**, not solely in robot position or pure startup.  
A5 membership-governance design may proceed **only with explicit hard limits** on availability leakage, VALID-subset non-representativeness, scale mismatch, and cross-sensor domain risk. The frozen adapter is **not** retuned here.

---

## All-77 integrity

| | Count |
|---|---:|
| TOTAL | 77 |
| ABSENT (Empty_space) | 11 |
| PRESENT (N1–N6) | 66 |
| VALID | 34 |
| FAIL_CLOSED | 43 |
| `UNRESOLVABLE_TIME_GAP` | 42 |
| `TOO_SHORT_FOR_30S` | 1 |

Statuses match A3R session results 1:1. Data.zip MD5 `99067ac569e419fc122eef49635d72d0`.

---

## Class × availability

| Class | VALID | FAIL | Valid rate | Fail rate |
|---|---:|---:|---:|---:|
| ABSENT | 9 | 2 | 81.8% | 18.2% |
| PRESENT | 25 | 41 | 37.9% | 62.1% |

- Absolute fail-rate difference (PRESENT − ABSENT): **0.439**
- Fail risk ratio (PRESENT / ABSENT): **3.417**
- Fisher exact OR: **7.38** (two-sided p≈0.0088; ABSENT n=11 — **not causal**)

**AVAILABILITY_CLASS_NEUTRALITY = NOT_SUPPORTED**

---

## Subject × availability (PRESENT)

| Subject | Fail / Total | Fail rate |
|---|---:|---:|
| N1 | 10/11 | 90.9% |
| N2 | 10/11 | 90.9% |
| N3 | 2/11 | 18.2% |
| N4 | 3/11 | 27.3% |
| N5 | 5/11 | 45.5% |
| N6 | 11/11 | 100% |

All subjects have ≥1 failure; concentration is **subset-heavy (N1/N2/N6)**, not uniform. Treated as acquisition/timing clustering — **not** physiology attribution.

---

## Position × availability

Failures occur across positions −5…+5 for PRESENT. Empty_space is mostly VALID at the same position labels. Matched-position pairs do **not** show identical timing integrity across classes → position alone does not explain the class gap.

---

## Timing failure mechanism (42 gap fails)

A-priori severity bins on `excess = max_gap / (2.5·median_dt)`:

| Bin | Count |
|---|---:|
| barely_over_limit (1.0, 1.2] | 19 |
| moderately_over_limit (1.2, 2.0] | 20 |
| large_gap (>2.0) | 3 |

Max-gap offset from t0: median ≈ **13.94 s**; fraction ≤5 s ≈ **16.7%**; ≤10 s ≈ **42.9%**.

→ Not a pure first-sample startup spike; gaps occur throughout the first 30 s.

---

## First-30s / startup (diagnostic later windows)

- Later non-overlapping 30 s windows marked **`DIAGNOSTIC_ONLY` / `NOT_ADAPTER_ELIGIBILITY`**.
- Among 42 gap failures, **17** have ≥1 later diagnostic window that would pass the *same* frozen gap/rate rules.
- This does **not** authorize skip-first / second-window / threshold changes.

---

## Temporal acquisition comparability

- **SCHEMA_COMPARABILITY = SUPPORTED** (shared CSV schema; A2).
- **TEMPORAL_ACQUISITION_COMPARABILITY = NOT_SUPPORTED** (similar median Hz, very different gap/fail behavior by class/subject).

---

## VALID-subset representativeness (secondary)

**VALID_SUBSET_REPRESENTATIVENESS = NOT_SUPPORTED**

VALID-34 over-represents ABSENT (9/34 ≈ 26.5% vs 11/77 ≈ 14.3%) and under-represents high-gap PRESENT subjects (esp. N1/N2/N6).

---

## Leakage

| Axis | Result |
|---|---|
| Adapter-availability leakage | **HIGH_RISK** — VALID vs UNAVAILABLE is class-correlated; must never map UNAVAILABLE→ABSENT |
| Path/metadata leakage | **LOW_RISK** — `adapt_c1_raw` has no class parameter; paths are audit/provenance only |

Hard safety: `UNAVAILABLE ≠ ABSENT ≠ NORMAL ≠ physiological-negative`.

---

## Secondary VALID-34 structural risks

| Axis | Result |
|---|---|
| Selected-bin confound | **MEDIUM_RISK** (near-field edge bins dominate; descriptive class differences only) |
| TRAIN z-score scale | **HIGH** (`SCALE_RISK_REMAINS`; |z|≪1 vs TRAIN std≈10.98) |
| Cross-sensor domain | **HIGH_RISK** (UWB through-wall robot vs MR60 ROLE_L; no equivalence claim) |

---

## Decision axes (machine)

```text
AVAILABILITY_CLASS_NEUTRALITY     = NOT_SUPPORTED
VALID_SUBSET_REPRESENTATIVENESS   = NOT_SUPPORTED
TEMPORAL_ACQUISITION_COMPARABILITY= NOT_SUPPORTED
PATH_METADATA_LEAKAGE             = LOW_RISK
ADAPTER_AVAILABILITY_LEAKAGE      = HIGH_RISK
SELECTED_BIN_CONFOUND_RISK        = MEDIUM_RISK
TRAIN_ZSCORE_SCALE_RISK           = HIGH
CROSS_SENSOR_DOMAIN_RISK          = HIGH_RISK
```

---

## A4 gate

```text
A4_CLEAR_WITH_LIMITATIONS_FOR_A5
```

Rationale: frozen adapter remains scientifically usable as a **governed** structural transform for a limited valid subset, but membership design must treat availability bias, domain mismatch, and scale risk as first-class constraints. Not a reject of the entire C1 path; not a clean pass.

A5 recommendation:

```text
RECOMMEND_A5
```

A5 = public both-class **membership governance design only** — not membership construction, not model eval, not M-PV3.8 reopen.

---

## Explicit non-actions

- MODEL_INFERENCE = NOT_EXECUTED
- MEMBERSHIP = NOT_CREATED
- ADAPTER_RULES = UNCHANGED
- HISTORICAL_R1 = UNCHANGED
- M-PV3.8 = UNCHANGED (`RESOURCE_BLOCKED_CLOSED`)
- M-PV4 = UNAUTHORIZED
- D2 = LOCKED
- A5 = NOT_EXECUTED
