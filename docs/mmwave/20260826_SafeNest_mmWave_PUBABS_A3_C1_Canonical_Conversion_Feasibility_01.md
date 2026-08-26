# SafeNest mmWave V2 — PUBABS-A3 C1 Canonical ROLE_L Conversion Feasibility

- Phase: **PUBABS-A3**
- Date: 2026-08-26
- Base SHA: `eae5948f3359079dc4dc0135e6ffd11793e88910` (post-PR #159)
- Branch: `research/mmwave-pubabs-a3-c1-canonical-feasibility`
- A3 gate: **`A3_CORRECTIVE_REQUIRED`**
- A4 recommendation: **`CORRECTIVE_BEFORE_A4`**
- Manifests: `datasets/mmwave/manifests/PUBABS_A3_c1_canonical_feasibility/`

M-PV3.8 remains `RESOURCE_BLOCKED_CLOSED`. No membership. No model inference. No A4.

---

## Answers to required questions

### 1. What exact quantity do the six ROLE_L candidates expect?
**R1** `OFFSET_CENTERED_NATIVE_PHASE_LIKE_RELATIVE_MOTION` / `respiratory_motion_trace` in **phase-like radians**, 10 Hz, then **first 300 samples** (30 s). Not derivative, not magnitude, not BPF_ZSCORE. Family B/C then apply **TRAIN-fitted global z-score** (+ scale/quality[/F2] sidecars) — never refit on C1.

### 2. What exact C1 quantity is available?
Measured-ns timestamped frames of **180 complex range bins** (~18.8 Hz irregular). Near-raw complex envelope (not classifier output).

### 3. What deterministic rule maps 180 bins → one trace?
**None uniquely frozen for C1.** D0 `PROFILE_001` dynamic-energy search is label-independent but **not registered** for C1 geometry. Probe transferring that method selected bins often near ~0.5 m (wall/near-field), not a unique human-range solution.

### 4. Why not chosen via labels/models?
Class/model-driven bin search was **forbidden and not used**. Remaining options are multiple non-label adapters → `MULTIPLE_NONLABEL_ADAPTERS_REMAIN`.

### 5. How are ~18.8 Hz timestamps converted to 10 Hz under frozen R1?
**They are not.** Declaring the measured median rate (or rounded 19 Hz) into R1 fails with **`UNRESOLVABLE_TIME_GAP`** because C1 timing is not a regular grid within R1’s 2.5-sample gap rule, and the rate is not an integer multiple of 10 for `resample_poly`.

A **non-canonical** probe (linear timestamp interpolation → claim 10 Hz → R1) structurally accepted and yielded finite length≥300 traces — but this **bypasses** frozen Kaiser anti-alias integer-ratio resampling and is **not** authorized as the conversion.

### 6. How are 30 s / 300 windows defined?
Frozen rule: R1 output then **`trace[:300]`** without re-centering. Upstream R1 failure blocks canonical window emission. No feasibility windows were promoted; **no membership**.

### 7. What frozen preprocessing is reused?
Intended reuse: R1 median centering + frozen TRAIN z-score. **Not applied** because canonical R1 ingress failed.

### 8. Does C1 require a fitted parameter?
For a future corrective adapter: **must not** fit on C1 labels. TRAIN z-score constants already exist but applying them is premature until ingress exists. Range search region for C1 **requires Sol registration**, not C1-label fitting.

### 9. Is the final trace physically/semantically compatible?
**Not established via frozen path.** Conceptual phase-like target is only a **PARTIAL_MATCH**; sampling/preprocessing **INCOMPATIBLE** today; cross-sensor domain risk **HIGH** (UWB through-wall vs MR60/V2 D0/D1 stack).

### 10. What remains unproven?
- Unique C1 range-bin rule
- Sol-frozen irregular-timestamp → 10 Hz rule compatible with R1
- Scale/polarity alignment vs TRAIN z-score domain
- Any ROLE_L evaluation utility (explicitly not run)

---

## Structural probe summary

| Check | Result |
|---|---|
| Data.zip MD5 | match `99067ac569e419fc122eef49635d72d0` |
| Sessions probed | 7 (Empty + N1/N2/N3/N6) |
| Complex 180 parse / phase finite | YES |
| R1 measured-rate | `UNRESOLVABLE_TIME_GAP` |
| R1 integer 19 Hz | `UNRESOLVABLE_TIME_GAP` |
| Noncanonical linear→10Hz→R1 | structural ACCEPT (not canonical) |
| Model inference | NOT_EXECUTED |

Probe script: `scripts/mmwave/pubabs_a3_c1_r1_compatibility_probe.py`

---

## A3 gate

```text
A3_CORRECTIVE_REQUIRED
```

### Corrective before retry
1. Freeze C1 timestamp→10 Hz / grid policy under R1 fail-closed semantics (or authorize an R1 extension).
2. Freeze a **unique** label-independent C1 range extraction registration.
3. Re-run A3; only then consider A4.

A4 recommendation:

```text
CORRECTIVE_BEFORE_A4
```

---

## Explicit non-actions

- No Family B/C seed inference
- No membership / M-PV3.8 reopen / M-PV4 / D2
- No class-driven bin/filter optimization
- No commit of Data.zip
- No A4 execution
