# SafeNest mmWave V2 — 15s vs 30s Context Comparison Independent Review

- Phase: **Independent Review — 15s short-context ablation vs 30s M-PV3 full-task pool**
- Base: `origin/main` `dc25952` (after `#130` 15s candidate merge; includes `#129` M-PV3)
- Branch: `docs/mmwave-v2-15s-30s-independent-review`
- Gate: **review only. no selection. no retraining.**
- 15s lane: `PASS_WITH_LIMITATIONS`, not a production candidate
- 30s lane: `PASS_WITH_LIMITATIONS`, `NO_SELECTION_READY`
- Selected float model: **none**
- Ready for M-PV4 production selection: **NO**

This document is not an implementation. It reads already-frozen 15s and 30s evidence and answers only whether the lanes are interchangeable candidates or different engineering roles, and what the next validation phase should be. It does not modify files used as evidence, retrain models, change labels, thresholds, or contracts, select a production model, access D2 payload semantics, or use MR60 supervised physiology.

---

## 1. Decision

The two lanes are **intentionally separated** and must not be merged into one utility pool.

1. 15s and 30s already encode different contracts. The 30s lane is a breathing + RR + quality full-task pool. The 15s lane is a breathing-only ablation.
2. The D1 PRESENT recall comparison `0.991` vs `0.386` must not be read as a context-length causal result. The 15s mean is dominated by seed collapse.
3. Extending the frozen M-PV3 selection contract by dropping the 15s candidate into the same RR utility vector is a category error. The 15s contract does not train or evaluate RR, so a naive merge would auto-fail 15s and pretend the role question was settled.
4. The next step is not production selection. It is a **successor multi-context comparison gate**. Cascade and adaptive implementations are premature.

---

## 2. Scope and non-actions

### Evidence read

- 30s selection: `datasets/mmwave/manifests/M-PV3_candidate_selection/`
- 30s training contract: `config/mmwave/m_pv2_candidate_training_contract.json`
- 15s candidate: `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/`
- Prior reports: `docs/mmwave/20260823_SafeNest_mmWave_M-PV3_Candidate_Selection_Gate_01.md`, `docs/mmwave/20260823_SafeNest_mmWave_M-PV2_Candidate_Training_01.md`, `docs/mmwave/20260823_Luna_Max_Fast_2_M-PV2_SHORT_15S_CANDIDATE_RESULT_SUMMARY.md`

### Not performed

- Retraining, architecture change, label regeneration, threshold search
- M-PV1 / M-PV2 / M-PV3 contract edits
- D2 payload semantic access, MR60 supervised physiology
- Calibration fitting, INT8/TFLite, Raspberry Pi measurement
- Production model selection, PR merge of either candidate lane

---

## 3. Lane status

### 3.1 Lane A — 30s full-task (M-PV3)

| Item | Value |
|---|---|
| Contract | `MMWV_V2_M_PV3_SELECTION_CONTRACT_V1` |
| Input | `[t-30s, t]`, 10 Hz, 300 samples |
| Target | final 5 s `[t-5s, t]` |
| Candidates | Families A/B/C × seeds 11/23/47, 9 total |
| Family A | F2 MLP, 5,986 params, RR + quality only |
| Family B | trace TCN, 17,915 params, breathing + RR + quality |
| Family C | hybrid TCN + F2, 21,115 params, breathing + RR + quality |
| Gate | `PASS_WITH_LIMITATIONS` |
| Selection | `NO_SELECTION_READY` |
| 15s lane | excluded from this gate; not mixed into the registry |

Frozen utility guards: `PRESENT recall >= 0.95`, `Brier <= 0.05`, `RR MAE <= 5 bpm`, `within ±2 >= 0.40`, `within ±4 >= 0.60`, `within ±6 >= 0.75`. These values were not changed after seeing results.

D1_DEV_VAL full-task results:

| Candidate | PRESENT recall | Brier | RR MAE | ±2 | ±4 | ±6 | Utility |
|---|---:|---:|---:|---:|---:|---:|---|
| B/11 | 100.0% | 0.0985 | 4.565 | 33.3% | 63.2% | 77.2% | Brier / ±2 miss |
| B/23 | 100.0% | 0.0065 | 4.194 | 49.1% | 66.7% | 70.2% | ±6 miss |
| B/47 | 98.2% | 0.0251 | 4.900 | 45.6% | 64.9% | 73.7% | ±6 miss |
| C/11 | 98.2% | 0.0212 | 4.540 | 33.3% | 63.2% | 78.9% | ±2 miss |
| C/23 | 98.2% | 0.0179 | 4.541 | 36.8% | 63.2% | 80.7% | ±2 miss |
| C/47 | 100.0% | 0.0013 | 4.461 | 45.6% | 64.9% | 73.7% | ±6 miss |

Safety and reproducibility passed 9/9. Q2 invalid false acceptance was 0.0 and clean false rejection was 0.0. No full-task candidate satisfied every frozen utility guard. The closest case is C/47: PRESENT 100%, Brier 0.0013, but within ±6 bpm is 73.7% against a 75% floor. Lowering that floor after seeing the table would turn the selection gate into post-hoc tuning. Keeping `NO_SELECTION_READY` was correct.

Family A remains RR/quality-only and cannot enter full-task selection. Q2 modes `SOURCE_FREEZE`, `LARGE_GAP`, `STALE_SOURCE`, `FLAT_EXACT`, and `REPUBLICATION_TO_FREEZE` were evaluated as synthetic unavailable-input profiles, not live MR60 captures.

### 3.2 Lane B — 15s breathing ablation (PR #130)

| Item | Value |
|---|---|
| Identity | `MMWAVE_V2_M_PV2_SHORT_CONTEXT_15S_BREATHING_CANDIDATE_V1` |
| Input | `[t-15s, t]`, 10 Hz, 150 samples, `[B,150,1]` |
| Target | same `[t-5s, t]`; samples 100:150 inside the short context |
| Derivation | last 150 samples of the accepted 300-sample R1 trace |
| Architecture | Conv1D(1→8,k5,s2) → Conv1D(8→16,k5,s2) → Conv1D(16→24,k3,s2) → newest-5 pool → Linear |
| Parameters | 2,297 / 45,304 MACs / 90,608 FLOPs |
| Trained head | breathing logit only |
| Excluded | RR, temporal hold, quality head, INT8, Pi |
| Gate | `PASS_WITH_LIMITATIONS` |
| Selection | not performed |

Causal rules: context end equals target end; future samples forbidden; internal event position forbidden; random alignment forbidden. The 15s contract does not replace the 30s contract, and it does not modify D0/D1 governance, Q2 availability semantics, or I1/I2/I3 runtime contracts.

`PASS_WITH_LIMITATIONS` means the ablation was produced with intact lineage. It does not mean 15s is ready for selection.

---

## 4. Signal-processing analysis

Respiratory information must be counted in **cycles**, not samples. Period is `T = 60 / RR` seconds. Observed RR ranges are 6–42 bpm on D0 TRAIN and 7.03–37.5 bpm on D1_DEV_VAL.

| RR | Period | Cycles in 15s | Cycles in 30s |
|---:|---:|---:|---:|
| 6 bpm | 10.0 s | 1.5 | 3.0 |
| 8 bpm | 7.5 s | 2.0 | 4.0 |
| 12 bpm | 5.0 s | 3.0 | 6.0 |
| 16 bpm | 3.75 s | 4.0 | 8.0 |
| 20 bpm | 3.0 s | 5.0 | 10.0 |

Autocorrelation peaks and DFT/periodogram estimators usually need at least two to three periods before a true period can be separated from a single motion transient. At slow rates (6–8 bpm), 15s holds 1.5–2 cycles and is borderline; 30s holds 3–4 cycles and is closer to a stable estimate. That is why the 15s contract left RR as metadata-only.

Frequency resolution is `Δf = 1 / window`.

| Context | DFT bin | Frozen ±6 bpm band |
|---|---:|---|
| 15 s | 4.0 bpm | about 1.5 bins |
| 30 s | 2.0 bpm | about 3 bins |

The 30s full-task pool still missed the ±6 floor. Applying the same RR utility to 15s would put a tighter ruler on a window with half the frequency resolution.

Transient artifacts also scale with window length. A 2–3 s motion burst occupies 13–20% of a 15s window and 7–10% of a 30s window. One irregular breath moves a short-window period estimate more. A longer window leaves more clean cycles after an artifact and averages phase wander over more periods.

The short-context advantage is **contract refill time**, not a learned physiological gain. The Q2 hard pre-gate blocks the model until the causal buffer is full. On the synthetic 120 s stream with a 1 s interruption, recovery and first valid decision are 15 s versus 30 s. Usable-slot ratios are 0.858 versus 0.670. These numbers are not live MR60 or Raspberry Pi measurements. Gap, freeze, and stale source share the same recovery time because the Q2 invalidation window is the causal context length.

Compute also favors the shorter window. The 15s Conv1D is 2,297 parameters / 45k MACs. 30s B/C is 17,915–21,115 parameters on a 300-sample trace plus F2/F3 descriptors. That footprint gap is confounded with architecture, so it cannot by itself promote 15s as a role winner.

---

## 5. D1 performance gap

### 5.1 Observed values

D0 TRAIN is observe-only. It is not held-out. D1_DEV_VAL has no supervised ABSENT class, so ABSENT recall and macro F1 are undefined for both lanes.

| Evaluation group | 15s macro F1 | 15s PRESENT | 15s ABSENT | 30s B/C macro F1 | 30s B/C PRESENT | 30s B/C ABSENT |
|---|---:|---:|---:|---:|---:|---:|
| D0 TRAIN observe-only | 0.783 | 0.805 | 0.764 | 0.885 | 0.995 | 0.772 |
| D1_DEV_VAL | undefined | 0.386 | undefined | undefined | 0.991 | undefined |

D0 ABSENT means are similar (0.764 vs 0.772). Most of the D0 gap is PRESENT (0.805 vs 0.995). Thirty-second D0 ABSENT is itself seed-unstable: family B/11 is 0.302 on D0 TRAIN observe-only.

### 5.2 The 15s mean 0.386 is seed collapse

D1_DEV_VAL has 57 PRESENT rows, 0 ABSENT, and 3 subjects.

| 15s seed | D1 PRESENT recall | TP / FN | Best epoch | Best val loss | Last val loss |
|---:|---:|---|---:|---:|---:|
| 11 | 0.193 | 11 / 46 | 4 | 0.710 | 0.832 |
| 23 | 0.877 | 50 / 7 | 90 | 0.310 | 0.479 |
| 47 | 0.088 | 5 / 52 | 5 | 0.718 | 0.878 |

Fifteen-second D1 PRESENT standard deviation is 0.350. Thirty-second B/C six-candidate PRESENT stays in 0.982–1.000 with standard deviation 0.009. Seed 23 reached 0.877, near the 0.95 floor. Seeds 11 and 47 stopped at epochs 4–5 and collapsed toward ABSENT. **Do not publish 0.386 as the 15s lane score.**

The 15s early-stop monitor is `D1_DEV_VAL_masked_breathing_bce`. That split is PRESENT-only. Stopping on a one-class validation loss can terminate training before the model has learned. The 30s pool uses the same D1 split but a multi-task composite loss, F2/F3 descriptors, and a quality head.

### 5.3 Factors that must be separated

| Factor | 15s | 30s | Can it explain the gap? |
|---|---|---|---|
| Context length | 150-sample tail crop | 300-sample full window | Possible, not isolated |
| Architecture | 3-layer Conv1D + pool | TCN + F3; C adds F2 | Yes. unmatched families |
| Capacity | 2,297 params | 17,915 / 21,115 | Yes. 8–9× |
| Objective | breathing BCE only | breathing + RR Huber + quality | Yes. no multi-task regularizer |
| Seed / training | D1 std 0.350; 2/3 early-stop | D1 std 0.009 | Yes. 15s mean is unstable |
| D1 domain | same 3 subjects, 57 PRESENT | same split, plus F2/F3 | Shared limitation, different features |
| Target alignment | same `[t-5s, t]`, no rewrite | same final-anchor target | Unlikely. alignment audit passed |

A causal claim requires a controlled isolation run that holds architecture, capacity, objective, scaler policy, and seeds fixed and varies only context length (15s crop vs 30s). That experiment does not exist yet. Report per-seed and per-subject D1 numbers. Do not average a collapsed seed into a lane score.

---

## 6. Engineering-role analysis

No architecture is selected. Options C and D remain hypotheses. Do not implement them yet.

### Option A — 30s only, then final decision

Advantages: only full-task pool. Safety/Q2 already pass. RR and quality heads exist. Closest to current I1/I2/I3 contracts.

Risks: no candidate passed every utility guard. 30s recovery tax. D1 has no ABSENT class. Family A cannot do breathing.

Missing evidence: locked test, ABSENT discrimination, calibration, INT8/Pi, real MR60, and the still-open RR ±6 tightness.

### Option B — 15s only, then final decision

Advantages: faster synthetic recovery, smaller tensor, 2.3k parameters. Useful as a screening hypothesis.

Risks: no RR by contract. No quality head. D1 mean 0.386 with seed collapse. Cannot satisfy the current M-PV3 utility vector.

Missing evidence: matched-architecture 30s control, seed-stable D1, ABSENT class, RR eligibility study, deployment measurement.

**Current evidence cannot support 15s as a full-task replacement.**

### Option C — 15s screen, then 30s confirm

Advantages: 30s compute could be spent only when 15s is uncertain or positive. Screen-path recovery could stay at 15s.

Risks: 15s screening is not stable. Mean recall 0.386 would miss PRESENT often. Error correlation is unknown. Fail-closed composition is undefined. Confirm path is double compute.

Missing evidence: joint confusion matrix, latency composition, threshold/hysteresis contract.

**Hypothesis only. Do not implement yet.**

### Option D — 15s when confident, 30s when uncertain

Advantages: short context as default, long context as fallback.

Risks: requires calibrated uncertainty. 15s D1 Brier is 0.209 versus 30s 0.028. Calibration fitting was forbidden and not performed. Confidence from a collapsed seed is not a switch signal.

Missing evidence: ECE by context, switch policy, fail-closed when both are uncertain.

**Hypothesis only. Do not implement yet.**

Interpretation: 15s and 30s are **different role candidates**. 15s is a recovery / responsiveness / lightweight screening hypothesis. 30s is a multi-cycle RR / stability / full-task confirmation path. Different roles do not authorize 15s promotion or cascade implementation.

---

## 7. Selection-contract review

The current M-PV3 gate assumes one context length, one candidate pool, and one utility vector. That was correct for the 30s registry it was frozen to evaluate. Combined score is `NOT_USED`. Validation-loss selection is forbidden. Unique selection requires every gate to pass and strict dominance on every secondary metric. Those rules should stay.

The 15s candidate must not be dropped into the same RR MAE / ±2 / ±4 / ±6 vector. RR is undefined on 15s by contract, so a naive merge auto-fails 15s.

Future selection should become multi-objective in the **reporting** sense, not via a combined score.

| Dimension | Current M-PV3 | Later comparison gate |
|---|---|---|
| Accuracy — breathing, RR, Brier/ECE | full-task secondary utility | role-specific; 15s cannot be scored on RR |
| Safety — Q2 FA=0, fail-closed, clean FR ≤ 0.10 | primary; 9/9 passed | remain first and non-compensable |
| Responsiveness — recovery, first valid decision | invisible to selection; 15s diagnostic only | explicit reported constraint; cannot buy accuracy |
| Deployment — params, MACs, tensor, memory | tertiary param count only; no Pi/INT8 | a card after a real device measurement |
| Evidence availability — usable cycles | hidden assumption of the 30s contract | report cycle-count eligibility by RR bin before any RR claim |

---

## 8. Recommended next validation phase

**A. Successor multi-context comparison gate.**

Do not mutate the frozen M-PV3 contract. Do not dump 15s into the existing utility vector. Do not implement a cascade. Do not promote 15s. Do not relax the 30s ±6 bpm floor after the fact.

| Option | Verdict | Reason |
|---|---|---|
| A. Multi-context comparison gate | **Select this phase** | Only this answers whether the lanes have different roles, and only if isolation runs first |
| B. Continue 30s only | Necessary but incomplete | Still the only full-task path, but it does not close the role question |
| C. Dedicated cascade experiment | Premature | 15s screening is seed-unstable; no joint error or fail-closed composition exists |
| D. Investigate 15s further, alone | A work package inside A, not the phase | Seed collapse must be explained, but 15s alone cannot enter production selection |

The successor gate should keep the lanes separate and freeze a comparison contract **before** evaluation. The first work package is controlled isolation: same architecture, same objective, same seeds, only context length varies (15s crop versus 30s). Report per-seed and per-subject cards. Do not publish a collapsed-seed mean as the 15s score. Keep the 30s full-task utility frozen. Score 15s only on breathing, recovery, and footprint cards.

---

## 9. Required evidence before production selection

1. **E1 Controlled isolation.** Hold architecture, objective, and seeds fixed. Vary only context length. Without this, `0.991` vs `0.386` remains confounded.
2. **E2 Per-seed and per-subject D1 cards.** 15s D1 standard deviation is 0.35 on 57 rows / 3 subjects. Do not use 0.386 as the 15s lane score.
3. **E3 Cycle-count / RR-bin eligibility table** for both contexts. 15s RR was excluded for this reason and never measured.
4. **E4 ABSENT-class discrimination** on a governed split that actually contains ABSENT. D1_DEV_VAL has zero ABSENT. D0 TRAIN is not held-out.
5. **E5 Keep the 30s utility vector frozen.** Changing ±6 needs a separate approval. C/47 missed 75% by 1.3 points. Relaxing the floor after seeing the table would invalidate M-PV3.
6. **E6 Role-specific comparison cards** for accuracy, safety, recovery, footprint, and evidence availability. No combined score. No unique-winner rule across incomparable tasks.
7. **E7 Later gates remain later.** Calibration, locked test, INT8/TFLite, Raspberry Pi, and real MR60 do not exist in the audited evidence. None may be claimed from this review.

---

## 10. Independent Review Result

### 1. Current interpretation

15s and 30s already encode different contracts. 30s M-PV3 confirmed a safely reproducible full-task candidate set, but no single production candidate passed every frozen utility guard. 15s is a causally aligned breathing ablation and does not replace the 30s contract. The two pools must not be merged to pick a winner now.

### 2. 15s vs 30s technical tradeoff

30s has more respiratory cycles and finer DFT resolution (2 bpm vs 4 bpm) at slow rates, which favors RR stability and transient resistance. 15s has a 15 s Q2 refill, so recovery, first decision, and input size are smaller. That recovery delta is a causal-context contract consequence, not a learned physiological advantage. 15s does not have enough information for the current RR utility.

### 3. Main uncertainties

The D1 PRESENT gap mixes context length, architecture, capacity, training objective, seed collapse, and a 3-subject PRESENT-only split. D1 has no ABSENT class. Q2 recovery is synthetic. Calibration, locked test, INT8, Pi, and real MR60 are absent. The 30s ±6 guard is still open.

### 4. Recommended next validation phase

**A — successor multi-context comparison gate.** Do not mutate frozen M-PV3. First work package: same-model context-length isolation. Do not implement C or D.

### 5. Required evidence before production selection

E1 isolation, E2 seed/subject cards, E3 cycle-count eligibility, E4 ABSENT split, E5 frozen 30s utility, E6 role-specific cards with no combined score, E7 later deployment and real-sensor gates.

---

## 11. Evidence paths

- `datasets/mmwave/manifests/M-PV3_candidate_selection/selection_decision.json`
- `datasets/mmwave/manifests/M-PV3_candidate_selection/selection_contract.json`
- `datasets/mmwave/manifests/M-PV3_candidate_selection/candidate_ranking.json`
- `datasets/mmwave/manifests/M-PV3_candidate_selection/validation_result.json`
- `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/evaluation_result.json`
- `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/limitations.json`
- `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/model_card.json`
- `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/input_contract.json`
- `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/target_alignment.json`
- `datasets/mmwave/manifests/M-PV2_short_context_15s_candidate/training_config.json`
- `datasets/mmwave/manifests/M-PV2_candidate_training/footprint_audit.json`
- `config/mmwave/m_pv2_candidate_training_contract.json`
- `docs/mmwave/20260823_SafeNest_mmWave_M-PV3_Candidate_Selection_Gate_01.md`
- `docs/mmwave/20260823_Luna_Max_Fast_2_M-PV2_SHORT_15S_CANDIDATE_RESULT_SUMMARY.md`

Upstream PRs: 30s selection `#129`, 15s candidate `#130`. Both were already on `main` when this review was written.

---

## 12. Limitations

- D0 metrics are observe-only.
- D1_DEV_VAL has no supervised ABSENT class.
- Q2 recovery is a synthetic timing diagnostic, not live MR60.
- 15s did not train RR or temporal hold.
- INT8, Raspberry Pi, calibration, and locked test were not performed.
- Inherited A4 reference semantics are SafeNest breathing proxies, not clinical apnea.
- This document does not select a production model.
