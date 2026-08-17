# SafeNest M-N1 — Training Eligibility and Label Provenance Classification

- Classification ID: `M-N1_TEAM_MR60_TRAINING_ELIGIBILITY_001`
- Date: 2026-08-17
- Phase: **M-N1 only**. No training. No M-N2 representation work.
- Linked inventory: [`20260817_SafeNest_mmWave_M-N0_Team_MR60_Physical_Inventory_01.md`](20260817_SafeNest_mmWave_M-N0_Team_MR60_Physical_Inventory_01.md)
- Standalone base: `origin/main` `2574fbc4abba7988565dd1fd013b1698fe4ecf49`
- Gate: **PASS_WITH_LIMITATIONS**
- M-N2 authorized: **YES** (development-reference use only)

The question this artifact answers:

> Given that all currently known Team MR60 physical recordings were collected from the same single physical participant, what legitimate machine-learning role can each recording support based on its condition, label/reference provenance, signal quality, and timing/freshness evidence?

---

## 1. Owner-confirmed physical-subject correction

All currently inventoried **Team** MR60 physical measurements were collected from **one physical participant**.

```text
UNIQUE_TEAM_MR60_PHYSICAL_SUBJECTS = 1
physical_subject = OWNER_CONFIRMED_SINGLE_SUBJECT
S001 == SUBJ-001  (physical participant)
equality_source = PROJECT_OWNER / EXPERIMENT_OPERATION CONFIRMATION
equality_proven_from_file_internal_metadata_alone = NO
historical_hardcoded_subject_id_design_generally_valid = NO
```

The ~74 physical source recordings are **74 repeated recordings / sessions / trials from 1 person**. They are not 74 subjects.

Machine-readable `subject_id` quality remains separate:

| Identifier / field | Physical person | File-schema quality |
|---|---|---|
| JSONL without `subject_id` | `OWNER_CONFIRMED_SINGLE_SUBJECT` | ABSENT |
| Delivery exporter `S001` | same person | HARDCODED |
| PR18 `SUBJ-001` | same person | PRESENT in session metadata |
| Historical `S001` hardcode | happened to match because only one participant was measured | still WEAK as a capture design |

Do not generalize the old hardcode to future multi-subject capture.

Recent Pi runtime files are **not** covered by this owner confirmation. Their participant is not inferred here.

---

## 2. Two distinct limitations

These are different problems. Do not collapse them.

**Limitation A — target supervision.**  
Independent respiratory ground truth is **ABSENT**. Paced cue is an experimental instruction, not physiology. Vendor `breath_rate_raw` is the same sensor/algorithm family, not an independent label. Apple Watch files are heart-rate comparison only.

**Limitation B — subject generalization.**  
Only one Team MR60 physical subject exists. Team-only subject-wise TRAIN / VAL / TEST is **IMPOSSIBLE**. Unseen-person Team validation is **IMPOSSIBLE**. Session-wise splits may later measure same-person cross-session behavior; they are not unseen-person generalization.

Recording diversity is **not** subject diversity. Dates, distances, conditions, capture versions, and device states provide session / condition / device diversity only.

---

## 3. Label provenance hierarchy

Strongest actual evidence on this Team set, from strongest to weakest:

1. independent physiological reference — **none found**
2. independently observed / reference-derived condition — **none for respiration**
3. operator observation / documented protocol failure — used for QA (failed 12 rpm, D12, D15, stale 31 min)
4. participant instruction / paced cue — present on paced sessions; **not** physiology GT
5. MR60 vendor-derived BPM — diagnostic metadata only
6. filename / export label — condition intent only
7. no target evidence — empty-room, healthcheck, many occupied sessions

Occupied / empty / desk-work / entry-exit describe experimental setup. They are not a frozen respiration-class target. Do not map paced 12 / 15 / 20 rpm onto `NORMAL` / `RAPID_OR_ABNORMAL` / APNEA proxy. The new model target is not frozen.

Derived CSVs, replay windows, and entry/exit trial splits retain lineage to their physical source. They do not create new people or independent sessions.

---

## 4. Classification rules used here

Primary role is the most defensible **one** role per physical recording.

| Role | When used |
|---|---|
| `SUPERVISED_TRAINING_ELIGIBLE` | Trustworthy target evidence **and** usable signal/timing. Known subject identity is not enough. |
| `WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE` | Real MR60 signal plus paced/condition cue, but no independent physiology GT. |
| `DEVICE_DOMAIN_REFERENCE` | Actual MR60 scale, waveform, cadence, session variation, preprocessing / common-representation design. |
| `FAILURE_OR_QA_EVIDENCE` | Freeze, stale phase, presence/lock loss, low amplitude, capture/parser, documented protocol failure. |
| `NOT_RECOMMENDED_FOR_MODEL_USE` | Too damaged even for domain/QA interpretation. None assigned. |

Pi files are a separate class: `RECENT_PI_RUNTIME_REFERENCE` (runtime input / device-domain), not Team supervised evidence. Do not cross a `boot_id` boundary as one continuous physiological recording.

---

## 5. Counts

Team physical source recordings classified: **74**. Unique physical subjects: **1**.

| Primary ML role | Count | Sessions |
|---|---:|---|
| SUPERVISED_TRAINING_ELIGIBLE | **0** | — |
| WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | **7** | valid paced 15 / deep-20 / valid-12 / later 15 and 20 explicit sessions |
| DEVICE_DOMAIN_REFERENCE | **57** | empty, preferred occupied, diagnostics, entry/exit, Apple Watch HR, PR18 Desk-work, 07-13 occupied/transitions |
| FAILURE_OR_QA_EVIDENCE | **10** | failed/incomplete paced, shallow 20, D12, D15, stale 31 min attempt02, PR18 Stationary, both Aug-08 raw files |
| NOT_RECOMMENDED_FOR_MODEL_USE | **0** | — |

Recent Pi runtime files (not in the 74): **7**, all `RECENT_PI_RUNTIME_REFERENCE`.

Existing Team MR60 supervised-training eligibility: **NONE**.

Reason: subject identity is now known, but no recording has an independent respiratory target. Occupied is not a respiration class. Paced cue is not physiology. Vendor BPM is not independent GT.

---

## 6. Classification table

Physical subject provenance for every Team row below is `OWNER_CONFIRMED_SINGLE_SUBJECT`. Machine-readable ID quality is noted only where it matters.

Equivalent sessions are grouped. Groups are **disjoint** and sum to 74. Session IDs match M-N0 Appendix A. Preferred M-N2 waveforms are named in §10; they are a subset of DEVICE_DOMAIN_REFERENCE, not extra recordings.

| Recording / session (n) | Machine-readable ID | Condition / target evidence | Timing / freshness | Primary ML role | Main limitation |
|---|---|---|---|---|---|
| `LEGACY_2026-07-26_breath_paced_15rpm` (1) | HARDCODED `S001` in delivery CSV | paced cue 15 rpm; phase-derived ~15 rpm; vendor median ~19 | JSONL `phase_age_ms` sampled present; delivery CSV drops it | WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | cue ≠ physiology; vendor offset |
| `LEGACY_2026-07-26_breath_paced_20rpm_deep` (1) | HARDCODED `S001` | paced cue 20 rpm deep; phase ~20; vendor median ~23 | same campaign freshness | WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | cue ≠ physiology |
| `LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt03` (1) | ABSENT on JSONL; delivery `S001_BREATH_PACED_12_02` | only delivery-valid 12 rpm attempt; phase ~12.34 vs cue 12 | JSONL freshness present | WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | cue ≠ physiology; earlier 12 rpm attempts invalid |
| `LEGACY_2026-07-28_breath_paced_15rpm_explicit_full_v3` (1) | ABSENT | paced cue 15; phase ~15.01; vendor ±2 vs cue hit rate 0.112 | JSONL freshness present | WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | cue ≠ physiology |
| `LEGACY_2026-07-28_breath_paced_15rpm_retry_v2`; `..._15rpm_v2` (2) | ABSENT | paced cue 15; extra same-campaign trials | JSONL freshness present | WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | cue ≠ physiology; weaker campaign notes than explicit_full_v3 |
| `LEGACY_2026-07-28_breath_paced_20rpm_explicit_full_v2` (1) | ABSENT | paced cue 20; phase ~20.01; vendor median 22 / std 6.39 | JSONL freshness present | WEAKLY_LABELED_OR_ADAPTATION_CANDIDATE | cue ≠ physiology; vendor not a label |
| Empty-room (13): four 2026-07-13 empty logs; 07-25/07-28 empty gates; `empty_v2_360s`; `empty_preflight_20s`; `empty_v120_30min`; `empty_v120_preflight_60s` | ABSENT | empty-room intent / filename | 07-13: `phase_age_ms` ABSENT; later: present | DEVICE_DOMAIN_REFERENCE | 07-13 timing provenance weak; empty ≠ respiration class |
| Occupied ~0.9 m without documented failure (10): D09 360 s v1/v2; D09 60 s; three D09 preflights; 08-01 31 min **attempt01**; three position-check files | HARDCODED `S001` on D09 delivery CSV; others ABSENT | occupied distance setup; **no** independent respiration reference | JSONL freshness sampled present; 08-01 `phase_age_ms` PRESENT; CSV drops it | DEVICE_DOMAIN_REFERENCE | setup ≠ respiration GT; do not merge attempt01 with stale attempt02 |
| Occupied ~0.6 m (2): `LEGACY_2026-07-25_occupied_d06_v1_360s`; `..._occupied_front_d06_60s` | HARDCODED `S001` on D06 delivery CSV | occupied 0.6 m setup | JSONL freshness sampled present | DEVICE_DOMAIN_REFERENCE | setup ≠ respiration GT |
| 2026-07-13 occupied / transitions (3): `occupied_front_p0_5min`; `d06_m0_trial01`; `trial02` | ABSENT | occupied / presence-transition intent | `phase_age_ms` ABSENT | DEVICE_DOMAIN_REFERENCE | early schema; no freshness field |
| Entry/exit physical sources (3): `LEGACY_2026-07-25_entry_exit_10`; `..._entry_exit_20_v2`; `..._entry_exit_preflight_10s` | ABSENT | presence change trials; 10 derived CSVs from one JSONL are **not** 10 people | JSONL freshness sampled present | DEVICE_DOMAIN_REFERENCE | derived splits are not new sessions |
| Apple Watch HR comparison (5) | ABSENT | heart-rate comparison only | later files have `phase_age_ms` | DEVICE_DOMAIN_REFERENCE | Watch ≠ respiration belt |
| Healthcheck (6) | ABSENT | capture/health intent | campaign freshness where sampled | DEVICE_DOMAIN_REFERENCE | too short; no respiration target |
| Preflight (10) | ABSENT | short capture checks, including paced-session preflights | campaign freshness where sampled | DEVICE_DOMAIN_REFERENCE | too short; filename cue is not a paced trial |
| Short diagnostic / quickcheck / tones (4) | ABSENT | 30 s checks around 15 rpm campaign | campaign freshness where sampled | DEVICE_DOMAIN_REFERENCE | too short for a respiration target |
| `M-C0-PILOT-DESKWORK-001` (1) | PRESENT `SUBJ-001` | seated desk-work ~55 cm; spontaneous breathing claimed; 961/1799 low-amplitude | `phase_age` p95 15 ms — good freshness | DEVICE_DOMAIN_REFERENCE | good timing ≠ supervised label; partial low amplitude; other person ~2 m behind target |
| `LEGACY_2026-07-25_breath_paced_12rpm` (1) | HARDCODED `S001_BREATH_PACED_12_01` | cue 12 rpm; **performed ~6.06 rpm** | JSONL freshness present | FAILURE_OR_QA_EVIDENCE | documented protocol failure; cue ≠ performed rate |
| Incomplete 12 rpm (2): `LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2`; `..._attempt02` | ABSENT | campaign treated only attempt03 as valid | JSONL freshness present | FAILURE_OR_QA_EVIDENCE | incomplete / superseded attempts |
| `LEGACY_2026-07-26_breath_paced_20rpm` (1) | HARDCODED `S001_BREATH_PACED_20_04` | shallow 20 rpm cue; phase std 0.113 | JSONL freshness present | FAILURE_OR_QA_EVIDENCE | low-amplitude shallow trial |
| `LEGACY_2026-07-25_occupied_d12_v1_360s` (1) | HARDCODED `S001_NORMAL_D12` | occupied 1.2 m; presence drop / range-limit | JSONL freshness present | FAILURE_OR_QA_EVIDENCE | presence loss |
| `LEGACY_2026-07-25_occupied_d15_v1_360s` (1) | HARDCODED `S001_NORMAL_D15` | occupied 1.5 m; lock-loss / vitals freeze; distance still hops (~2.94 cm std) | JSONL freshness present | FAILURE_OR_QA_EVIDENCE | freeze; do not treat as normal occupied |
| `LEGACY_2026-08-01_occupied_d09_v120_31min_attempt02` (1) | ABSENT | long occupied; telemetry ~10 Hz with stale `breath_phase`; `phase_age_ms` max 288530 ms | PRESENT_BUT_STALE_WINDOWS | FAILURE_OR_QA_EVIDENCE | stale phase; not continuous physiology |
| `M-C0-PILOT-STATIONARY-001` (1) | PRESENT `SUBJ-001` | stationary Pilot; 1568/1799 low-amplitude | p95 15 ms | FAILURE_OR_QA_EVIDENCE | majority degraded; **no** `session_manifest.json` |
| `AUG08_IDENTITY_RAW_20S` (1) | ABSENT | identity raw; sampled LOCK_LOSS_FREEZE / DEGRADED | `phase_age_ms` PRESENT | FAILURE_OR_QA_EVIDENCE | freeze in sampled records; still real schema 1.2 telemetry for QA |
| `AUG08_NO_PERSON_RAW_10S` (1) | ABSENT | filename `no_person`; sampled presence + freeze | `phase_age_ms` PRESENT | FAILURE_OR_QA_EVIDENCE | filename vs sampled mismatch |

Row counts: 7 weak + 57 device-domain + 10 QA = 74.

### Recent Pi runtime (not in the 74)

Owner confirmation of the Team participant **does not** cover these files. Do not infer the Pi participant.

| File | Primary role | Main limitation |
|---|---|---|
| `PI_20260816_13` … `PI_20260817_06` | RECENT_PI_RUNTIME_REFERENCE | no nested `breath_phase`; host cadence ≠ ESP 10 Hz |
| `PI_20260817_07` | RECENT_PI_RUNTIME_REFERENCE | mixed schema; partial `breath_phase` |
| `PI_20260817_08` | RECENT_PI_RUNTIME_REFERENCE | **two `boot_id`s** (743 + 20321 records); 1 bad JSON line; never window across the boot boundary |
| `PI_20260817_09` | RECENT_PI_RUNTIME_REFERENCE | usable runtime timing snapshot only |

---

## 7. Evidence-family summary

**PRE_PR18_LEGACY_ESP_JSONL (70).**  
Subject: `OWNER_CONFIRMED_SINGLE_SUBJECT`. Machine-readable ID often ABSENT or HARDCODED. Mix of device-domain occupied/empty, weakly labeled paced, and documented QA failures. 2026-07-13 lacks `phase_age_ms`.

**PR18_PILOT_CAPTURE (2).**  
Same physical participant (`SUBJ-001` alias). Desk-work is device-domain with good freshness and partial low amplitude. Stationary is QA (majority low-amplitude + missing manifest). Good freshness does not imply supervised-label quality.

**AUG08_LIVE_RAW_JSONL (2).**  
Same physical participant. Real schema 1.2 ESP telemetry, but sampled freeze / condition mismatch. Primary role is QA, not clean development-reference waveforms.

**RECENT_PI_RUNTIME_REFERENCE (7).**  
Runtime input / device-domain only. Participant not owner-confirmed. Preserve `boot_id` boundaries.

---

## 8. What this does **not** support

- Team-only unseen-person generalization
- Artificial subject splits from filenames, dates, `S001` vs `SUBJ-001`, session IDs, or `boot_id`
- Treating paced 12/15/20 as verified respiration classes
- Training a model from MR60 `breath_phase` using MR60 `breath_rate_raw` as if that were independent physiology
- Using delivery CSV windows or replay outputs as extra people

Public 110-subject data remains necessary for subject diversity:

```text
110-subject public dataset  →  subject-diverse supervised backbone
single-subject Team MR60    →  device-domain representation,
                               condition/session evidence,
                               possible limited adaptation,
                               QA / failure evidence
```

This is an interpretation, not the frozen M-N4 training strategy.

---

## 9. Strategy feasibility (assess only; not selected)

| Strategy | Meaning | Feasibility |
|---|---|---|
| A | Public 110-subject supervised training only; Team MR60 for representation / domain evidence | **PLAUSIBLE** |
| B | Public supervised training plus truly eligible Team MR60 supervised windows | **NOT_CURRENTLY_SUPPORTED** (eligible count = 0) |
| C | Public supervised / pretraining, then limited single-subject MR60 adaptation | **LIMITED** — weakly labeled paced sessions exist, but `SINGLE_SUBJECT_ADAPTATION_OVERFIT_RISK` |
| D | Public supervised training plus Team MR60 domain / reference analysis; future multi-subject MR60 for independent validation | **PLAUSIBLE** |

---

## 10. Recommended Team MR60 role for M-N2

Use as **`MR60_DEVELOPMENT_REFERENCE`**, not as a supervised set and not as unseen-person validation.

Preferred development-reference waveforms (device-domain, same person):

- occupied D06 / D09 360 s and 07-28 occupied v2
- 08-01 occupied 31 min **attempt01** and empty 30 min (schema 1.2, `phase_age_ms` present)
- PR18 Desk-work (freshness; keep the low-amplitude caveat)
- empty-room counterparts with freshness, for occupied-vs-empty scale / presence contrast

Also useful, with explicit caveats:

- the 7 weakly labeled paced sessions — periodicity / common-representation comparison only; **not** GT
- FAILURE_OR_QA sessions — freeze, stale phase, presence/lock loss, protocol failure; do not promote them to normal training examples

Unseen-person `MR60_HELDOUT_REFERENCE`: **empty**. A later same-person session holdout would still be same-person cross-session behavior.

Do not window across Pi `boot_id` boundaries.

---

## 11. Gate

```text
M-N1 gate = PASS_WITH_LIMITATIONS
M-N2 authorized = YES
Training performed = NO
Historical A/B modified = NO
Team raw evidence modified = NO
EXISTING_MMWAVE_B_LIVE_GATE = CLOSED  (unchanged)
```

PASS_WITH_LIMITATIONS because every meaningful recording has a defensible ML role and M-N2 has a clear development-reference set, while Team supervised eligibility remains **NONE** and subject diversity remains **NONE**. FAIL is not appropriate: the evidence supports honest role classification.
