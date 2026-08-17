# SafeNest M-N0 — Existing Team MR60 Physical-Data Inventory

- Inventory ID: `M-N0_TEAM_MR60_PHYSICAL_INVENTORY_001`
- Date: 2026-08-17
- Phase: **M-N0 only**. This is an inventory, not a forensic re-audit and not an M-N1 label/eligibility table.
- Standalone base: `https://github.com/sheepmeat/test.git` `origin/main` `2574fbc4abba7988565dd1fd013b1698fe4ecf49`
- Team evidence SHA: `jinsu1011/safenest-embedded-competition` `main` `c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16`
- Gate: **PASS_WITH_LIMITATIONS**
- M-N1 authorized: **YES**

The question this artifact answers:

> What real MR60BHA2 physical measurements already exist, where are they, what does each recording actually represent, and what evidence accompanies each recording?

TRAIN / VAL / TEST membership is **not assigned** here. ML-role classification is in [`20260817_SafeNest_mmWave_M-N1_Training_Eligibility_01.md`](20260817_SafeNest_mmWave_M-N1_Training_Eligibility_01.md).

The complete machine-readable catalog is the JSON document in [Appendix A](#appendix-a-canonical-json).

---

## Project-owner correction, 2026-08-17

All currently inventoried **Team** MR60 physical measurements were collected from **one physical participant**. Historical identifiers `S001` and `SUBJ-001` are therefore aliases for that same participant in the current evidence set.

```text
UNIQUE_TEAM_MR60_PHYSICAL_SUBJECTS = 1
physical_subject = OWNER_CONFIRMED_SINGLE_SUBJECT
S001 == SUBJ-001  (physical participant)
equality_source = PROJECT_OWNER / EXPERIMENT_OPERATION CONFIRMATION
equality_proven_from_file_internal_metadata_alone = NO
```

This supersedes earlier M-N0 wording that treated `S001` / `SUBJ-001` as an unconfirmed relationship, and that described most Team recordings as unknown-subject at the physical-person level.

It does **not**:

- reconstruct missing machine-readable `subject_id` fields;
- make historical exporter hardcoding a valid general capture design;
- create independent respiration ground truth;
- repair `phase_age_ms` / freshness gaps;
- cover Recent Pi runtime files, which were **not** included in this owner confirmation.

Future multi-subject capture must use explicit stable subject/session identity. Do not generalize the old `S001` hardcode.

---

## 1. Where the evidence lives now

On current Team `main`, the live `devices/mmwave/` tree is empty. Physical MR60 logs were relocated during the 2026-08-17 canonical-repo refactor:

| Era | Path |
|---|---|
| Historical report paths (2026-08-14 / handoff / M-C0) | `devices/mmwave/firmware/logs/...` |
| Current Team `main` | `archive/legacy_main_repo/devices/mmwave/firmware/logs/...` |
| PR18 Pilot (merged 2026-08-16, then archived) | `archive/legacy_main_repo/devices/mmwave/device_measurements/pilot/` |
| Historical M-C0 correspondence outputs | `research/mmwave_ai/datasets/mmwave/manifests/M-C0_correspondence_audit/` |
| Recent Pi runtime JSONL | `yuname121/integration` `data/mmwave/` — **not** Team `devices/mmwave/` |

Raspberry Pi `Runtime/data/mmwave/` in the Team repo contains only `.gitkeep`.

Team PR #18 is **MERGED** (2026-08-16, merge `0fc2fd5be40f3a5714e738258183676f4adb1109`). The 2026-08-15 handoff still described it as an open draft; this inventory uses the merged/archived tree.

---

## 2. Method

Existing trustworthy evidence was used first:

- `docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md`
- `docs/20260815_SafeNest_mmWave_Technical_Handoff_01.md`
- Team `raw_file_index.json` (78 firmware JSONL files at historical SHA `fdf34b80`)
- Delivery v2 `manifest.json` / `DELIVERY_NOTES.md`
- PR18 session manifest + QA JSON
- Team `existing_measurement_inventory.json` (M-C0 12-file subset — **not treated as complete**)

Raw files were opened only to identify source/session identity, fields, condition, duration, timing/freshness, and label/reference provenance. M-C0 correspondence statistics were not recomputed. Historical A/B artifacts were not modified. Team raw measurements were not modified.

Sampled physical schemas:

- 2026-07-13 empty-desk JSONL: `breath_phase` present, **no** `phase_age_ms`, no `schema_version`
- 2026-07-25 / 2026-07-28 healthcheck JSONL: schema `1.0`, `phase_age_ms` present
- 2026-08-01 long occupied: schema `1.2`, `phase_age_ms` present (from 2026-08-14 report)
- PR18 Pilot: schema `1.2`, `phase_age_ms` present
- 2026-08-08 `identity_raw_20s.jsonl` / `no_person_raw_10s.jsonl`: schema `1.2` physical telemetry
- Most other 2026-08-08 `live_*.jsonl`: inference logs with `raw_sensor_data_stored: false`

---

## 3. Counts

| Quantity | Count |
|---|---:|
| Physical measurement bundles / families | 5 |
| Team physical source recordings | **74** |
| — PRE_PR18 legacy ESP JSONL | 70 |
| — PR18 Pilot | 2 |
| — 2026-08-08 live raw JSONL | 2 |
| Companion non-waveform files in the firmware log index | 8 |
| Recent Pi runtime files (separate class) | 7 |
| Unique physical subjects (owner-confirmed) | **1** |
| File identifiers | `S001` and `SUBJ-001` are aliases for that same participant |
| Machine-readable subject field | often ABSENT or HARDCODED; physical subject is still known |

CSV exports, analysis summaries, quality-policy windows, replay windows, and 2026-08-08 inference logs are **not** extra physical sessions.

Entry/exit: one physical JSONL (`2026-07-25_entry_exit_10.jsonl`) produced 10 derived trial CSVs. A later `2026-07-28_entry_exit_20_v2.jsonl` is a second physical recording, not 20 independent people.

---

## 4. Evidence families

1. **PRE_PR18_LEGACY_ESP_JSONL** — Team firmware logs (physical source).
2. **PR18_PILOT_CAPTURE** — Desk-work and Stationary Pilots from merged PR #18.
3. **AUG08_LIVE_RAW_JSONL** — The two 2026-08-08 files that actually keep ESP telemetry.
4. **DERIVED_CSV_AND_ANALYSIS** — delivery CSVs, copied JSONL, analysis JSON, quality-policy/replay windows, M-C0 audit JSON, public Phase A/B manifests.
5. **RECENT_PI_RUNTIME_REFERENCE** — Pi host JSONL in `yuname121/integration`. Not supervised training evidence.

Do not merge `PRE_PR18_LEGACY_LOGS` and `PR18_PILOT_CAPTURE` silently. Capture tool and session metadata differ even when ESP app firmware is `safenest-mr60-esp/1.2.0`.

Public 110-subject Zenodo / Phase A–B datasets are **not** Team MR60 physical measurements.

---

## 5. Known historical examples

All roadmap examples were found or explicitly classified.

| Example | Status | Physical source (current Team path prefix `archive/legacy_main_repo/`) | What it actually is |
|---|---|---|---|
| D06 | FOUND | `.../logs/matrix/2026-07-25_occupied_d06_v1_360s.jsonl` | Occupied ~0.6 m; delivery `S001_NORMAL_D06`; preferred |
| D09 | FOUND | `.../logs/baseline/2026-07-25_occupied_d09_v1_360s.jsonl` | Occupied ~0.9 m; delivery `S001_NORMAL_D09`; preferred |
| D12 | FOUND | `.../logs/matrix/2026-07-25_occupied_d12_v1_360s.jsonl` | Occupied ~1.2 m; presence drop / range-limit |
| D15 | FOUND | `.../logs/matrix/2026-07-25_occupied_d15_v1_360s.jsonl` | Lock-loss / vitals freeze. Distance std is ~2.94 cm, not 0 |
| paced 12 rpm | FOUND | failed `.../breath/2026-07-25_breath_paced_12rpm.jsonl` (~6.06 rpm performed); valid `.../breath/2026-07-28_breath_paced_12rpm_explicit_v2_attempt03.jsonl`; extra attempts 01/02 also exist | Cue ≠ performed rate |
| paced 15 rpm | FOUND | delivery `2026-07-26_breath_paced_15rpm.jsonl` plus 07-28 explicit/retry/v2 | Phase tracks ~15 rpm; vendor clusters ~19 |
| paced 20 rpm | FOUND | shallow `..._20rpm.jsonl`; deep `..._20rpm_deep.jsonl`; later explicit full v2 | Shallow is low-amplitude QA |
| long-duration | FOUND | `.../final/2026-08-01_occupied_d09_v120_31min_attempt02.jsonl` (and attempt01, plus 30 min empty) | ~10 Hz rows with stale `breath_phase`; `phase_age_ms` max 288530 ms |
| PR18 Desk-work | FOUND | `.../device_measurements/pilot/M-C0-PILOT-DESKWORK-001.raw.jsonl` | 1799 records / ~180 s; `SUBJ-001`; seated desk-work |
| PR18 Stationary | FOUND | `.../pilot/M-C0-PILOT-STATIONARY-001.raw.jsonl` | Same counts; **no** session_manifest.json |
| Pi `20260817_08_mmwave.jsonl` | FOUND | `yuname121/integration` `data/mmwave/20260817_08_mmwave.jsonl` | **RECENT_PI_RUNTIME_REFERENCE** only |

Additional physical recordings exist beyond that list: empty-room, diagnostics/preflight/healthcheck, entry/exit, Apple Watch HR comparison, 07-13 transitions, 08-01 position checks, extra paced attempts, and two Aug-08 raw JSONL files.

---

## 6. Delivery / PR18 detail

Subject `S001` in delivery CSVs is hardcoded by the exporter. Multiple files are not multiple people. PR18 uses `SUBJ-001`. Per the 2026-08-17 project-owner correction, `S001` and `SUBJ-001` are aliases for the **same physical participant**. That equality is `OWNER_CONFIRMED_SINGLE_SUBJECT`, not file-internal identity proof. The exporter hardcode happened to match because only one participant was involved; it is **not** a valid general provenance design for future capture.

| Session | Intended | Observed / notes | `breath_phase` | `phase_age_ms` | Vendor BPM | Independent resp. ref. |
|---|---|---|---|---|---|---|
| `S001_NORMAL_D06` | occupied 0.6 m | preferred occupied | CSV `resp_phase`; JSONL source has campaign schema 1.0 | JSONL likely present; CSV absent | yes | none |
| `S001_NORMAL_D09` | occupied 0.9 m | preferred occupied | same | same | yes | none |
| `S001_NORMAL_D12` | occupied 1.2 m | presence drop | same | same | yes | none |
| `S001_NORMAL_D15` | occupied 1.5 m | vitals freeze; distance hops 172.20/177.94/183.68 cm | frozen `-0.01` | CSV absent | frozen 15.0 | none |
| `S001_BREATH_PACED_12_01` | 12 rpm cue | performed ~6.06 rpm | yes | CSV absent | ~6 rpm | paced cue only |
| `S001_BREATH_PACED_12_02` | 12 rpm cue | phase ~12.34; vendor median 14 | yes | CSV absent | yes | paced cue only |
| `S001_BREATH_PACED_15_03` | 15 rpm cue | phase ~15.00; vendor median 19 | yes | CSV absent | yes | paced cue only |
| `S001_BREATH_PACED_20_04` | 20 rpm shallow | phase ~20, std 0.113 | yes | CSV absent | yes | paced cue only |
| `S001_BREATH_PACED_20_05` | 20 rpm deep | phase ~20, std 0.501; vendor median 23 | yes | CSV absent | yes | paced cue only |
| 31 min D09 attempt02 | occupied long | stale phase windows | yes | PRESENT, max 288530 ms | yes | none |
| `M-C0-PILOT-DESKWORK-001` | desk-work ~55 cm | 1799 rows; 961 low-amplitude | yes | p95 15 ms | yes | none |
| `M-C0-PILOT-STATIONARY-001` | stationary | 1799 rows; 1568 low-amplitude; no session manifest | yes | p95 15 ms | yes | none |

Exact `0x0A13` frame-arrival identity is **not** logged. `phase_age_ms` is staleness relative to telemetry emit time.

---

## 7. Compact index of other Team physical JSONL

Folder counts inside `firmware/logs/` (physical waveform JSONL only):

| Folder | Physical JSONL files | Typical meaning |
|---|---:|---|
| `baseline` | 9 | empty-room and occupied baselines (2026-07-13 through 07-28) |
| `breath` | 11 | paced 12/15/20 rpm, including failed and extra attempts |
| `diagnostics` | 29 | short healthcheck / preflight / quickcheck |
| `final` | 9 | schema 1.2 long occupied/empty, position-check, healthcheck |
| `kpi` | 7 | entry/exit plus Apple Watch HR comparison (not respiration GT) |
| `matrix` | 3 | occupied D06 / D12 / D15 |
| `transitions` | 2 | 2026-07-13 presence-transition trials |

Companion files kept beside those logs (not counted as physical sessions): 2 transition timing JSONL, 3 watch-prompt JSONL, 3 telemetry-receipt JSONL.

---

## 8. Recent Pi runtime reference

Status: **FOUND**

These files are committed in `https://github.com/yuname121/integration` at `a966b164e99b01f7a3e80a596d30d388b3a567d6` (`data/mmwave/`). They are **not** in the Team MR60 firmware log tree. Duplicate local working copies exist in other sibling checkouts; those are not additional sessions.

Classification: `RECENT_PI_RUNTIME_REFERENCE`. They may support actual MR60 numeric range, runtime timing, source behavior, and pipeline sanity. They are **not** supervised training evidence and **not** formal validation.

| File | Records | Nested `mmwave` | `breath_phase` | `phase_age_ms` | Notes |
|---|---:|---|---|---|---|
| `20260816_13_mmwave.jsonl` | 2737 | no | no | no | ~0.89 Hz host rows |
| `20260816_14_mmwave.jsonl` | 1518 | no | no | no | ~0.42 Hz |
| `20260816_15_mmwave.jsonl` | 478 | no | no | no | ~0.82 Hz |
| `20260817_06_mmwave.jsonl` | 276 | no | no | no | ~1.00 Hz |
| `20260817_07_mmwave.jsonl` | 10466 | 9736 | partial | when nested | mixed file; unified node FW |
| `20260817_08_mmwave.jsonl` | 21064 | 21064 | yes | yes | roadmap example; 1 bad line; **two boot_ids** |
| `20260817_09_mmwave.jsonl` | 7436 | 7436 | yes | yes | p95 age 72 ms |

Nested firmware string is `safenest-esp32-sensor-node/1.2.0`, not `safenest-mr60-esp/1.2.0`. Host row cadence is not ESP 10 Hz telemetry.

---

## 9. Physical vs derived

Separated: **YES**

| Class | Examples | Counted as independent physical sessions? |
|---|---|---|
| PHYSICAL_SOURCE_EVIDENCE | firmware JSONL, PR18 `.raw.jsonl`, Aug-08 identity/no-person raw | yes |
| DERIVED_DATA | delivery CSV windows, `original_jsonl/` copies, entry/exit trial CSVs | no |
| ANALYSIS_OUTPUT | `firmware/analysis/*`, quality-policy windows, replay windows, M-C0 audit JSON | no |
| MODEL_OUTPUT | 2026-08-08 live window inference logs; public Phase A/B prediction indexes | no |
| REPORT | 2026-08-14 evaluation, handoff, PR18 reports | no |
| RECENT_PI_RUNTIME_REFERENCE | integration `data/mmwave/*.jsonl` | separate class, not Team supervised evidence |

`raw_preflight_15s.jsonl` under 2026-08-08 current-production is thermal/health console text, not MR60 JSONL.

---

## 10. Major provenance gaps

1. Physical subject identity for the Team set is now `OWNER_CONFIRMED_SINGLE_SUBJECT` (one person). Machine-readable subject fields remain ABSENT or HARDCODED on many files; that is a schema-quality issue, not an unknown person.
2. No independent respiration reference exists. Paced cue ≠ physiology. Apple Watch ≠ respiration belt. Vendor `breath_rate_raw` ≠ independent label.
3. PR18 Stationary has no committed `session_manifest.json`.
4. Most 2026-08-08 live USB runs did not store raw waveforms.
5. 2026-07-13 logs lack `phase_age_ms`; delivery CSVs drop it even when 2026-07-25+ JSONL has it.
6. Exact `0x0A13` update identity is unavailable.
7. Team physical tree now lives only under `archive/legacy_main_repo/`.
8. Pi `20260817_08` concatenates two `boot_id`s; several Pi files lack `breath_phase`. Pi participant identity is **not** covered by the Team owner confirmation.

M-N0 did not byte-inspect every large JSONL. Completeness of the **file set** is from the Team tree + `raw_file_index.json`. Per-file condition for unnamed diagnostics is filename-derived.

---

## 11. Gate

```text
M-N0 gate = PASS_WITH_LIMITATIONS
M-N1 authorized = YES
EXISTING_MMWAVE_B_LIVE_GATE = CLOSED  (unchanged; SIGNAL_CONTRACT_MISMATCH)
Historical A/B modified = NO
Team raw evidence modified = NO
```

PASS_WITH_LIMITATIONS because a useful inventory exists, but some historical condition, freshness, and machine-readable metadata cannot be recovered. The 2026-08-17 owner correction resolved physical-subject identity for the Team set; it did not repair independent respiration labels or timing provenance. FAIL is not appropriate: the project can determine what its real MR60 evidence is, with explicit remaining gaps.

---

## Appendix A. Canonical JSON

```json
{
  "inventory_id": "M-N0_TEAM_MR60_PHYSICAL_INVENTORY_001",
  "phase": "M-N0",
  "schema_version": "M-N0_TEAM_MR60_PHYSICAL_INVENTORY_V1",
  "created_utc_date": "2026-08-17",
  "owner_confirmed_single_subject_correction": {
    "date": "2026-08-17",
    "source": "PROJECT_OWNER / EXPERIMENT_OPERATION CONFIRMATION",
    "unique_team_mr60_physical_subjects": 1,
    "physical_subject": "OWNER_CONFIRMED_SINGLE_SUBJECT",
    "s001_equals_subj_001_physical_participant": true,
    "equality_proven_from_file_internal_metadata_alone": false,
    "historical_hardcoded_subject_id_design_generally_valid": false,
    "applies_to": [
      "PRE_PR18_LEGACY_ESP_JSONL",
      "delivery-derived recordings of those sources",
      "PR18_PILOT_CAPTURE",
      "AUG08_LIVE_RAW_JSONL",
      "related Team physical MR60 measurements in this inventory"
    ],
    "does_not_apply_to": [
      "RECENT_PI_RUNTIME_REFERENCE unless separately confirmed"
    ],
    "supersedes_human_wording": [
      "S001 / SUBJ-001 relationship unknown",
      "most Team physical measurements are unknown-subject at the physical-person level"
    ],
    "does_not_repair": [
      "independent respiration ground truth",
      "phase_age_ms / freshness gaps",
      "missing session manifests",
      "historical exporter hardcode as a future capture design"
    ],
    "per_session_subject_id_fields": "Per-session subject_id values such as UNKNOWN or S001_DELIVERY_EXPORTER_HARDCODE remain as machine-readable file-schema quality. They are superseded for physical-person identity by this owner confirmation. Do not treat those historical fields as current physical-subject truth."
  },
  "standalone_repository": "https://github.com/sheepmeat/test.git",
  "standalone_base_sha": "2574fbc4abba7988565dd1fd013b1698fe4ecf49",
  "team_repository": "https://github.com/jinsu1011/safenest-embedded-competition",
  "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
  "question": "What real MR60BHA2 physical measurements already exist, where are they, what does each recording actually represent, and what evidence accompanies each recording?",
  "not_this_phase": [
    "TRAIN/VAL/TEST assignment",
    "SUPERVISED_TRAINING_ELIGIBLE classification",
    "new model training",
    "reopening EXISTING_MMWAVE_B_LIVE_GATE",
    "checksum regeneration of historical A/B"
  ],
  "method": {
    "primary_reports": [
      "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
      "docs/20260815_SafeNest_mmWave_Technical_Handoff_01.md",
      "research/mmwave_ai/datasets/mmwave/manifests/M-C0_correspondence_audit/existing_measurement_inventory.json",
      "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json",
      "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/manifest.json"
    ],
    "raw_inspection": "Focused source checks only: Team tree listing on current main; sampled first records for 2026-07-13, 2026-07-25, 2026-07-28, 2026-08-08 identity/no-person raw, PR18 QA/manifests; Pi JSONL field/cadence/boot_id stats. Did not recompute all historical checksums or re-run M-C0.",
    "location_note": "On team main SHA c6979cd2 the live devices/mmwave/ tree is gone. Physical logs now live under archive/legacy_main_repo/devices/mmwave/ after the 2026-08-17 canonical-repo refactor (commit a4158e640c06) plus M-C0 correspondence import (f4bc5492a8cb). Historical report paths remain valid if prefixed."
  },
  "counts": {
    "physical_measurement_bundles": 5,
    "team_physical_source_recordings": 74,
    "team_companion_non_waveform_files_indexed": 8,
    "recent_pi_runtime_files": 7,
    "known_subject_ids": [
      "S001",
      "SUBJ-001"
    ],
    "unique_physical_subjects_owner_confirmed": 1,
    "subject_id_alias_note": "S001 and SUBJ-001 are aliases for one owner-confirmed physical participant"
  },
  "evidence_families": [
    "PRE_PR18_LEGACY_ESP_JSONL",
    "PR18_PILOT_CAPTURE",
    "AUG08_LIVE_RAW_JSONL",
    "DERIVED_CSV_AND_ANALYSIS",
    "RECENT_PI_RUNTIME_REFERENCE"
  ],
  "known_examples_accounted": {
    "D06": "FOUND",
    "D09": "FOUND",
    "D12": "FOUND",
    "D15": "FOUND",
    "paced_12_rpm": "FOUND including failed 07-25 and valid 07-28 attempt03 plus extra attempts",
    "paced_15_rpm": "FOUND delivery 07-26 plus 07-28 explicit/retry variants",
    "paced_20_rpm": "FOUND shallow and deep 07-26 plus 07-28 explicit",
    "shallow_deep_breathing_variants": "FOUND",
    "long_duration_recording": "FOUND 31min occupied attempt01 and attempt02 plus 30min empty",
    "PR18_Pilot_Desk_work": "FOUND",
    "PR18_Pilot_Stationary": "FOUND raw+QA; session_manifest missing",
    "recent_pi_20260817_08": "FOUND as RECENT_PI_RUNTIME_REFERENCE in yuname121/integration, not in Team devices/mmwave"
  },
  "physical_sessions": [
    {
      "session_id": "LEGACY_2026-07-13_empty_desk_collector_v1_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-13_empty_desk_collector_v1_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-13_empty_desk_collector_v1_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 347956,
      "git_blob_sha_at_raw_index": "f444c4c8c8d4e5b93e700cf57dcc255c8fa52c47"
    },
    {
      "session_id": "LEGACY_2026-07-13_empty_desk_collector_v2_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-13_empty_desk_collector_v2_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-13_empty_desk_collector_v2_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 146487,
      "git_blob_sha_at_raw_index": "12ea6a08337edd9a152a4942f969f8daecd04db7"
    },
    {
      "session_id": "LEGACY_2026-07-13_empty_desk_prechange_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-13_empty_desk_prechange_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-13_empty_desk_prechange_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 64428,
      "git_blob_sha_at_raw_index": "57a3b895700d1fb848ddfa7414e1a41d2318ce16"
    },
    {
      "session_id": "LEGACY_2026-07-13_empty_fixed_d06_e0_5min",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-13_empty_fixed_d06_e0_5min.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-13_empty_fixed_d06_e0_5min.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": {
        "seconds_approx": 300,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1488048,
      "git_blob_sha_at_raw_index": "9a2305c9896163b6d729db2318243563cca0f1b5"
    },
    {
      "session_id": "LEGACY_2026-07-13_occupied_front_p0_5min",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-13_occupied_front_p0_5min.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-13_occupied_front_p0_5min.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": {
        "seconds_approx": 300,
        "source": "filename"
      },
      "intended_condition": "occupied",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1494787,
      "git_blob_sha_at_raw_index": "27de6b05e314809b00e4db6899d99fb14432b898"
    },
    {
      "session_id": "LEGACY_2026-07-25_empty_gate_v1_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-25_empty_gate_v1_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-25_empty_gate_v1_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 360,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1785223,
      "git_blob_sha_at_raw_index": "14b21752ac2dcdb3886b2a5c87b67d316680f500"
    },
    {
      "session_id": "LEGACY_2026-07-25_occupied_d09_v1_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-25_occupied_d09_v1_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-25_occupied_d09_v1_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/2026-07-25_occupied_d09_v1_360s__S001_NORMAL_D09.csv",
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/original_jsonl/2026-07-25_occupied_d09_v1_360s.jsonl"
      ],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "Same hardcoded S001 as other delivery_v2 sessions.",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 360,
        "csv_window_records": 2998,
        "csv_window_seconds": 299.816,
        "telemetry_row_hz": 9.996131,
        "source": "20260814_report"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "Occupied preferred distance session",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1793029,
      "git_blob_sha_at_raw_index": "b48075a1b58d9b6002c6975c867926b1350db401",
      "delivery_session_id": "S001_NORMAL_D09"
    },
    {
      "session_id": "LEGACY_2026-07-28_empty_v2_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-28_empty_v2_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-28_empty_v2_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 360,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1785798,
      "git_blob_sha_at_raw_index": "2d0eaf105bba3545fb5f29dbb6e6bc812b19481e"
    },
    {
      "session_id": "LEGACY_2026-07-28_occupied_d09_v2_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/baseline/2026-07-28_occupied_d09_v2_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/baseline/2026-07-28_occupied_d09_v2_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 360,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1794148,
      "git_blob_sha_at_raw_index": "2a05c4af928521efe2d39896b31bd3c9fc9d44ba"
    },
    {
      "session_id": "LEGACY_2026-07-25_breath_paced_12rpm",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-25_breath_paced_12rpm.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-25_breath_paced_12rpm.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/2026-07-25_breath_paced_12rpm__S001_BREATH_PACED_12_01.csv"
      ],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "csv_window_records": 2087,
        "source": "delivery_v2"
      },
      "intended_condition": "paced_12_rpm_cue",
      "actually_observed_or_reference_condition": "Cue metronome ~12 rpm; performed chest motion ~6.06 rpm (half-breath instruction accident). NOT a valid 12 rpm reference.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": "protocol_failure_performed_rate_ne_cue",
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1432772,
      "git_blob_sha_at_raw_index": "d8c9543aebac1c7de5bda1573343b72fc179a354",
      "delivery_session_id": "S001_BREATH_PACED_12_01"
    },
    {
      "session_id": "LEGACY_2026-07-26_breath_paced_15rpm",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-26_breath_paced_15rpm.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-26_breath_paced_15rpm.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-26",
      "duration": {
        "csv_window_records": 1779,
        "csv_window_seconds": 177.905,
        "telemetry_row_hz": 9.994098,
        "source": "20260814_report"
      },
      "intended_condition": "paced_15_rpm_cue",
      "actually_observed_or_reference_condition": "Phase-dominant ~15.00 rpm; vendor mean 18.04 / median 19.0 rpm",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 2362295,
      "git_blob_sha_at_raw_index": "0e5233c10a1a3f406144e2fdbc685ebb02e49f9a",
      "delivery_session_id": "S001_BREATH_PACED_15_03"
    },
    {
      "session_id": "LEGACY_2026-07-26_breath_paced_20rpm",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-26_breath_paced_20rpm.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-26_breath_paced_20rpm.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-26",
      "duration": {
        "csv_window_records": 1784,
        "csv_window_seconds": 178.403,
        "telemetry_row_hz": 9.994227,
        "source": "20260814_report"
      },
      "intended_condition": "paced_20_rpm_shallow_cue",
      "actually_observed_or_reference_condition": "Phase-dominant ~20.00 rpm but low amplitude (phase std 0.113); presence 97.3% CSV. Weak/shallow trial.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": "low_amplitude_shallow_breathing",
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 2345238,
      "git_blob_sha_at_raw_index": "4cb124ba0b85e7a8a58492db0d0f0a60fa4744e7",
      "delivery_session_id": "S001_BREATH_PACED_20_04"
    },
    {
      "session_id": "LEGACY_2026-07-26_breath_paced_20rpm_deep",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-26_breath_paced_20rpm_deep.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-26_breath_paced_20rpm_deep.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-26",
      "duration": {
        "csv_window_records": 1784,
        "csv_window_seconds": 178.425,
        "telemetry_row_hz": 9.992994,
        "source": "20260814_report"
      },
      "intended_condition": "paced_20_rpm_deep_cue",
      "actually_observed_or_reference_condition": "Phase-dominant ~20.00 rpm; vendor mean 23.31 / median 23.0; phase std 0.501; presence 1.00",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 2338452,
      "git_blob_sha_at_raw_index": "c50fddf8701adc686c9d02b7c2aa47c3940e496d",
      "delivery_session_id": "S001_BREATH_PACED_20_05"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_12rpm_explicit_v2.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_12rpm_explicit_v2.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "paced_12_rpm_cue",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 537047,
      "git_blob_sha_at_raw_index": "f1ee4d9134785133ea565fffe5753680f3b881af"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt02",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_12rpm_explicit_v2_attempt02.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_12rpm_explicit_v2_attempt02.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "paced_12_rpm_cue",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 471240,
      "git_blob_sha_at_raw_index": "637ca7ab05c03312a3d2dc02cbc93038c4679ac6"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_12rpm_explicit_v2_attempt03",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_12rpm_explicit_v2_attempt03.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_12rpm_explicit_v2_attempt03.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "csv_window_records": 1774,
        "csv_window_seconds": 177.381,
        "telemetry_row_hz": 9.995434,
        "source": "20260814_report"
      },
      "intended_condition": "paced_12_rpm_cue",
      "actually_observed_or_reference_condition": "Phase-dominant ~12.34 rpm vs cue 12; vendor median 14.0 rpm. Paced cue is not independent physiology.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1476615,
      "git_blob_sha_at_raw_index": "29ca83025b55ec22f32e4af068e962172ca411b2",
      "delivery_session_id": "S001_BREATH_PACED_12_02"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_15rpm_explicit_full_v3",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_15rpm_explicit_full_v3.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_15rpm_explicit_full_v3.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "paced_15_rpm_cue",
      "actually_observed_or_reference_condition": "Phase-dominant ~15.01 rpm; vendor mean 18.80 / median 19.0; vendor ±2 rpm hit rate vs 15 rpm cue 0.112",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/firmware/analysis/breath/2026-07-28_breath_paced_15rpm_explicit_full_v3_summary.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1477753,
      "git_blob_sha_at_raw_index": "07915a2eddfb38469198f2df961144cd9180f806"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_15rpm_retry_v2",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_15rpm_retry_v2.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_15rpm_retry_v2.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "paced_15_rpm_cue",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1606454,
      "git_blob_sha_at_raw_index": "a8925aff84732dea2dd93457edf809203d3b0527"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_15rpm_v2",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_15rpm_v2.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_15rpm_v2.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "paced_15_rpm_cue",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1442064,
      "git_blob_sha_at_raw_index": "5490b8e3b4c534f438381d4f3a01e6eb22f19249"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath_paced_20rpm_explicit_full_v2",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_20rpm_explicit_full_v2.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/breath/2026-07-28_breath_paced_20rpm_explicit_full_v2.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "paced_20_rpm_cue",
      "actually_observed_or_reference_condition": "Phase-dominant ~20.01 rpm; vendor mean 19.40 / median 22.0 / std 6.39. Vendor offset is not universal.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1483051,
      "git_blob_sha_at_raw_index": "23a427c28f26610b5aebbf09d50233d6a82d1429"
    },
    {
      "session_id": "LEGACY_2026-07-25_empty_gate_120s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_120s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_120s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 120,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 593974,
      "git_blob_sha_at_raw_index": "6c0fe38298e7c4adb7204395cbf44dcd60c75c5f"
    },
    {
      "session_id": "LEGACY_2026-07-25_empty_gate_attempt02_60s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_attempt02_60s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_attempt02_60s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 60,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 298330,
      "git_blob_sha_at_raw_index": "22f433e7814c9113e4996faae3eb39d2e1295a36"
    },
    {
      "session_id": "LEGACY_2026-07-25_empty_gate_attempt03_15s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_attempt03_15s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_attempt03_15s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 74569,
      "git_blob_sha_at_raw_index": "2ed043543b745f431136aa3d88718085c2dddbc6"
    },
    {
      "session_id": "LEGACY_2026-07-25_empty_gate_attempt03_60s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_attempt03_60s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_empty_gate_attempt03_60s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 60,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 303801,
      "git_blob_sha_at_raw_index": "b6cf7ae2f514651d1b5d9c0e40de7c98106df889"
    },
    {
      "session_id": "LEGACY_2026-07-25_healthcheck_15s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_healthcheck_15s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_healthcheck_15s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "healthcheck",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 74268,
      "git_blob_sha_at_raw_index": "b3dd99f5e18285366f52b4f1d0e8c7cdc4817936"
    },
    {
      "session_id": "LEGACY_2026-07-25_occupied_d09_60s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_d09_60s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_d09_60s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 60,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 299056,
      "git_blob_sha_at_raw_index": "959817ffec8884f89cdd3e0f09cf899e8cf48bee"
    },
    {
      "session_id": "LEGACY_2026-07-25_occupied_front_d06_60s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_front_d06_60s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-25_occupied_front_d06_60s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 60,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.6m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 296178,
      "git_blob_sha_at_raw_index": "eaac565dff8258d000f56341bf1618d684b58cad"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath12_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath12_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath12_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49935,
      "git_blob_sha_at_raw_index": "0f44be0686f3e827a773a0ecfa6822e488d7cf7b"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_explicit_audible_retry_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_audible_retry_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_audible_retry_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "diagnostic_or_short_check",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 392006,
      "git_blob_sha_at_raw_index": "1928df997cde56a8634d74c3e862b6403149fc18"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_explicit_preflight02_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_preflight02_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_preflight02_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49815,
      "git_blob_sha_at_raw_index": "2ed2b2e701898bcaf02074ba3754b0164b74a53d"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_explicit_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49848,
      "git_blob_sha_at_raw_index": "9388dea2e70d7ec1fad876ae094f17ec6b37f1e1"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_explicit_quickcheck_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_quickcheck_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_explicit_quickcheck_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "diagnostic_or_short_check",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 391435,
      "git_blob_sha_at_raw_index": "5592f7f741945252b6d34e76d66162bcd9707993"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_full_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_full_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_full_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49537,
      "git_blob_sha_at_raw_index": "156c1433db7dc97ce2eb3540bcafa83ad01cd783"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49853,
      "git_blob_sha_at_raw_index": "5d7bf2a0321fcda1c7547d9dcfa620ca206bde64"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_quickcheck_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_quickcheck_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_quickcheck_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "diagnostic_or_short_check",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 343777,
      "git_blob_sha_at_raw_index": "edb4b985f6097bfc722dab4b782731cd5fff671c"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_retry_preflight02_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_retry_preflight02_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_retry_preflight02_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49926,
      "git_blob_sha_at_raw_index": "044963f436e27aa8eb7d69a4fdd30e71b0ce9791"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_retry_preflight03_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_retry_preflight03_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_retry_preflight03_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49849,
      "git_blob_sha_at_raw_index": "647fd9ae6850b2aa3f5fc112036b5fc750d31745"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_retry_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_retry_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_retry_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49745,
      "git_blob_sha_at_raw_index": "d4b3f00eb7da2bad98e5e8f91c63457965a88bba"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath15_tones_retry_30s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_tones_retry_30s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath15_tones_retry_30s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 30,
        "source": "filename"
      },
      "intended_condition": "diagnostic_or_short_check",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 420044,
      "git_blob_sha_at_raw_index": "7898bf14007ba2ab0cf0e3f2f78135c1463f219a"
    },
    {
      "session_id": "LEGACY_2026-07-28_breath20_full_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath20_full_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_breath20_full_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 50072,
      "git_blob_sha_at_raw_index": "fe752534b7794834528b76f09457f666ff888aee"
    },
    {
      "session_id": "LEGACY_2026-07-28_empty_preflight_20s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_empty_preflight_20s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_empty_preflight_20s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 20,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 99232,
      "git_blob_sha_at_raw_index": "1d11e3b5d39c87ca205211c1aa965df65511f249"
    },
    {
      "session_id": "LEGACY_2026-07-28_entry_exit_preflight_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_entry_exit_preflight_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_entry_exit_preflight_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "entry_exit",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49628,
      "git_blob_sha_at_raw_index": "65a9bcca491d0e57cd14bdc137ed56d40c1970e7"
    },
    {
      "session_id": "LEGACY_2026-07-28_healthcheck_15s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_healthcheck_15s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_healthcheck_15s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "healthcheck",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 74305,
      "git_blob_sha_at_raw_index": "f6d869134cb064d9b3629d1234b50fcc9e365d10"
    },
    {
      "session_id": "LEGACY_2026-07-28_healthcheck_15s_v2",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_healthcheck_15s_v2.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_healthcheck_15s_v2.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "healthcheck",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 74181,
      "git_blob_sha_at_raw_index": "9c269762450209084d8e4050706d1d124d02dd7d"
    },
    {
      "session_id": "LEGACY_2026-07-28_occupied_d09_preflight02_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_occupied_d09_preflight02_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_occupied_d09_preflight02_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49928,
      "git_blob_sha_at_raw_index": "c15dc6d76933509a9965b82342916580893a6525"
    },
    {
      "session_id": "LEGACY_2026-07-28_occupied_d09_preflight03_10s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_occupied_d09_preflight03_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_occupied_d09_preflight03_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 49852,
      "git_blob_sha_at_raw_index": "8847169e4eb923696eefa5a52337e699f553ca06"
    },
    {
      "session_id": "LEGACY_2026-07-28_occupied_d09_preflight_20s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-07-28_occupied_d09_preflight_20s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-07-28_occupied_d09_preflight_20s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": {
        "seconds_approx": 20,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 99895,
      "git_blob_sha_at_raw_index": "06cbd39e046a02285d90a2aa32a404171a879bdf"
    },
    {
      "session_id": "LEGACY_2026-08-01_healthcheck_resume_15s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-08-01_healthcheck_resume_15s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-08-01_healthcheck_resume_15s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "healthcheck",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 123416,
      "git_blob_sha_at_raw_index": "6741cbde6a312d86da9eb8ff75ace0ef40952147"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s1_preflight_v120_15s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/diagnostics/2026-08-01_heartrate_watch_s1_preflight_v120_15s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/diagnostics/2026-08-01_heartrate_watch_s1_preflight_v120_15s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "preflight",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 150205,
      "git_blob_sha_at_raw_index": "42e34d783f8f45379964770d46c8b9b13b5ccf26"
    },
    {
      "session_id": "LEGACY_2026-08-01_empty_v120_30min",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_empty_v120_30min.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_empty_v120_30min.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 1800,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 18358335,
      "git_blob_sha_at_raw_index": "1ce0aa03398f9d53ea1c63d817fdad4cbbe1e12c"
    },
    {
      "session_id": "LEGACY_2026-08-01_empty_v120_preflight_60s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_empty_v120_preflight_60s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_empty_v120_preflight_60s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 60,
        "source": "filename"
      },
      "intended_condition": "empty_room",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 612115,
      "git_blob_sha_at_raw_index": "ed0084a6929e9faf78d9d6d3f6068502e94c8d5b"
    },
    {
      "session_id": "LEGACY_2026-08-01_healthcheck_v110_15s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_healthcheck_v110_15s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_healthcheck_v110_15s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 15,
        "source": "filename"
      },
      "intended_condition": "healthcheck",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 121746,
      "git_blob_sha_at_raw_index": "df6ff511cde20ebb70568ce448e87506a1902753"
    },
    {
      "session_id": "LEGACY_2026-08-01_healthcheck_v120_75s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_healthcheck_v120_75s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_healthcheck_v120_75s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 75,
        "source": "filename"
      },
      "intended_condition": "healthcheck",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 751229,
      "git_blob_sha_at_raw_index": "d756c03b80a1a1905bb63e4c071f2c63d7cb6e0d"
    },
    {
      "session_id": "LEGACY_2026-08-01_occupied_d09_v120_31min",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_31min.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_31min.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 1860,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 18886470,
      "git_blob_sha_at_raw_index": "53e1d662d68b1bbfed9577cc4fcbcc3311936802"
    },
    {
      "session_id": "LEGACY_2026-08-01_occupied_d09_v120_31min_attempt02",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_31min_attempt02.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_31min_attempt02.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 1859.84,
        "records": 18574,
        "telemetry_row_hz": 9.986,
        "source": "20260814_report"
      },
      "intended_condition": "occupied_distance_0.9m_long_duration",
      "actually_observed_or_reference_condition": "Schema 1.2; duration 1859.84 s; telemetry 9.986 Hz; phase_age_ms max 288530 ms; 2585 packets phase_age_ms>30s; firmware safenest-mr60-esp/1.2.0; final-validation PRESENCE_PASS_BREATH_CONTINUITY_FAIL",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_BUT_STALE_WINDOWS",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": "stale_phase_despite_10hz_rows",
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/firmware/analysis/final/2026-08-01_mr60_final_validation_manifest.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 18956494,
      "git_blob_sha_at_raw_index": "ffdaa0cbb3bd6bc32f5fd1ca91130a69f4075426"
    },
    {
      "session_id": "LEGACY_2026-08-01_occupied_d09_v120_positioncheck_180s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_positioncheck_180s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_positioncheck_180s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 180,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1826216,
      "git_blob_sha_at_raw_index": "3af1d73d5e1136b6ab38f503085551ab1b443c74"
    },
    {
      "session_id": "LEGACY_2026-08-01_occupied_d09_v120_positioncheck_attempt02_180s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_positioncheck_attempt02_180s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_positioncheck_attempt02_180s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 180,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1837273,
      "git_blob_sha_at_raw_index": "aeddffbc57a95e81144d8df5b87a7f5537d6d71d"
    },
    {
      "session_id": "LEGACY_2026-08-01_occupied_d09_v120_positioncheck_attempt03_60s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_positioncheck_attempt03_60s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_positioncheck_attempt03_60s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 60,
        "source": "filename"
      },
      "intended_condition": "occupied_distance_0.9m",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 597739,
      "git_blob_sha_at_raw_index": "9c26c7172087e10a0d894d9c80e941bc05250f30"
    },
    {
      "session_id": "LEGACY_2026-07-25_entry_exit_10",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-07-25_entry_exit_10.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-07-25_entry_exit_10.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": null,
      "intended_condition": "entry_exit",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 2500367,
      "git_blob_sha_at_raw_index": "f445f87ef308e7bee13708d263973425c3d0ea88"
    },
    {
      "session_id": "LEGACY_2026-07-26_heartrate_ref_applewatch_300s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-07-26_heartrate_ref_applewatch_300s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-07-26_heartrate_ref_applewatch_300s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-26",
      "duration": {
        "seconds_approx": 300,
        "source": "filename"
      },
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 2471433,
      "git_blob_sha_at_raw_index": "ea9ef1688cbae7b07a3bc5a1abdd8d3eaeb86a5a"
    },
    {
      "session_id": "LEGACY_2026-07-26_heartrate_ref_applewatch_run2_300s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-07-26_heartrate_ref_applewatch_run2_300s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-07-26_heartrate_ref_applewatch_run2_300s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-26",
      "duration": {
        "seconds_approx": 300,
        "source": "filename"
      },
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 2434885,
      "git_blob_sha_at_raw_index": "7c4ebdcbbdf821d713d32fe352e8937da58fbdd8"
    },
    {
      "session_id": "LEGACY_2026-07-28_entry_exit_20_v2",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-07-28_entry_exit_20_v2.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-07-28_entry_exit_20_v2.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-28",
      "duration": null,
      "intended_condition": "entry_exit",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 6795941,
      "git_blob_sha_at_raw_index": "6d1b82dac5126f4a5441fe434c291e6dfefa0471"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s1_v120_300s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s1_v120_300s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s1_v120_300s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 300,
        "source": "filename"
      },
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 3057039,
      "git_blob_sha_at_raw_index": "81277d1f2306a659b22acbd0cb8a2c3701d94ec8"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 360,
        "source": "filename"
      },
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1084032,
      "git_blob_sha_at_raw_index": "c9df1884397d1adacf56c269337069589c591fb0"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s2_recovery_v120_480s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_v120_480s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_v120_480s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": {
        "seconds_approx": 480,
        "source": "filename"
      },
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 4854744,
      "git_blob_sha_at_raw_index": "9a4b667940f2d4ce9ab30c647745c6c7174b3189"
    },
    {
      "session_id": "LEGACY_2026-07-25_occupied_d06_v1_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/matrix/2026-07-25_occupied_d06_v1_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/matrix/2026-07-25_occupied_d06_v1_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/2026-07-25_occupied_d06_v1_360s__S001_NORMAL_D06.csv",
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/original_jsonl/2026-07-25_occupied_d06_v1_360s.jsonl"
      ],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "Same hardcoded S001 as other delivery_v2 sessions. Not proven to be a distinct person from PR18 SUBJ-001.",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 360,
        "csv_window_records": 2998,
        "csv_window_seconds": 299.851,
        "telemetry_row_hz": 9.994964,
        "source": "delivery_v2_and_20260814_report"
      },
      "intended_condition": "occupied_distance_0.6m",
      "actually_observed_or_reference_condition": "Occupied preferred distance session after 60s warmup in CSV window; no independent respiration reference",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1800829,
      "git_blob_sha_at_raw_index": "253343fdf1b29841dee1edc33d0aa077b8e86e12",
      "delivery_session_id": "S001_NORMAL_D06"
    },
    {
      "session_id": "LEGACY_2026-07-25_occupied_d12_v1_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/matrix/2026-07-25_occupied_d12_v1_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/matrix/2026-07-25_occupied_d12_v1_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/2026-07-25_occupied_d12_v1_360s__S001_NORMAL_D12.csv"
      ],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 360,
        "csv_window_records": 2998,
        "csv_window_seconds": 299.826,
        "telemetry_row_hz": 9.995798,
        "source": "20260814_report"
      },
      "intended_condition": "occupied_distance_1.2m",
      "actually_observed_or_reference_condition": "Occupied; presence drop / range-limit documented",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": "presence_drop_or_range_limit",
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1802621,
      "git_blob_sha_at_raw_index": "7299c7b0d6188b71bb507dac3e9e05530aed79bd",
      "delivery_session_id": "S001_NORMAL_D12"
    },
    {
      "session_id": "LEGACY_2026-07-25_occupied_d15_v1_360s",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/matrix/2026-07-25_occupied_d15_v1_360s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/matrix/2026-07-25_occupied_d15_v1_360s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/2026-07-25_occupied_d15_v1_360s__S001_NORMAL_D15.csv"
      ],
      "subject_id": "S001_DELIVERY_EXPORTER_HARDCODE",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-25",
      "duration": {
        "seconds_approx": 360,
        "csv_window_records": 2999,
        "csv_window_seconds": 299.849,
        "telemetry_row_hz": 9.998366,
        "source": "20260814_report"
      },
      "intended_condition": "occupied_distance_1.5m",
      "actually_observed_or_reference_condition": "Lock-loss / vitals freeze: unique breath_phase=-0.01, unique breath_rate_raw=15.0; distance still hops among 172.20/177.94/183.68 cm (sample std ~2.94 cm). Do not repeat 'distance std=0'.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT_IN_JSONL_SAMPLED_SAME_CAMPAIGN",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": "lock_loss_vitals_freeze",
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1853318,
      "git_blob_sha_at_raw_index": "ea274bd183fa676da6c355eb2949b11b3963b9fd",
      "delivery_session_id": "S001_NORMAL_D15"
    },
    {
      "session_id": "LEGACY_2026-07-13_d06_m0_trial01",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial01.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial01.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": null,
      "intended_condition": "presence_transition",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 647324,
      "git_blob_sha_at_raw_index": "bd511c1f107f94b0ea3c802206f0a04394a63fd3"
    },
    {
      "session_id": "LEGACY_2026-07-13_d06_m0_trial02",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial02.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial02.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": null,
      "intended_condition": "presence_transition",
      "actually_observed_or_reference_condition": "NOT_INDEPENDENTLY_VERIFIED_IN_M-N0",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "ABSENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 779879,
      "git_blob_sha_at_raw_index": "b95299eba936dff0002dabe6c738bfead9709c36"
    },
    {
      "session_id": "M-C0-PILOT-DESKWORK-001",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PR18_PILOT_CAPTURE",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/device_measurements/pilot/M-C0-PILOT-DESKWORK-001.raw.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/device_measurements/pilot/M-C0-PILOT-DESKWORK-001.raw.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY_SCHEMA_1.2",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/device_measurements/manifests/M-C0-PILOT-DESKWORK-001.session_manifest.json",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/manifests/M-C0-PILOT-DESKWORK-001.environment_metadata.json",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/qa/M-C0-PILOT-DESKWORK-001.qa.json"
      ],
      "subject_id": "SUBJ-001",
      "subject_relationship_to_other_sessions": "UNCONFIRMED vs delivery S001. Different capture tool/session meta; do not silently merge with PRE_PR18_LEGACY_LOGS.",
      "date": "2026-08-14",
      "duration": {
        "seconds_approx": 179.908,
        "records": 1799,
        "telemetry_row_hz": 9.993997,
        "source": "PR18_QA"
      },
      "intended_condition": "desk_work_small_arm_movements_seated_~55cm",
      "actually_observed_or_reference_condition": "Technical acquisition/movement Pilot; breathing_mode normal_spontaneous; no independent respiration reference; other person ~2m behind target",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "phase_age_ms p95=15ms max=111ms; M-C0 later estimated fresh cadence ~9.988 Hz vs row ~9.994 Hz",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "BREATH_PHASE_LOW_AMPLITUDE on 961/1799 records; sensor_state DEGRADED 961 / VALID 838; sensor_firmware_version UNKNOWN_NOT_REPORTED",
      "existing_qa_or_report_reference": [
        "archive/legacy_main_repo/devices/mmwave/device_measurements/qa/M-C0-PILOT-DESKWORK-001.qa.json",
        "docs/20260815_SafeNest_mmWave_Technical_Handoff_01.md"
      ],
      "unresolved_ambiguity": "ESP firmware_version safenest-mr60-esp/1.2.0 vs sensor.sensor_firmware_version UNKNOWN_NOT_REPORTED (MR60 vendor FW string not in ESP JSON).",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "sha256": "368e6a16e897b9231ff5fcdecd3edcc5b725a0a4dc6b20dee1e3162405bc2876",
      "firmware_version": "safenest-mr60-esp/1.2.0",
      "config_hash": "b817e8bfd5e52b18275626f7b6a9bd60098ea4b108428a5aaf63600dbc987834"
    },
    {
      "session_id": "M-C0-PILOT-STATIONARY-001",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "PR18_PILOT_CAPTURE",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/device_measurements/pilot/M-C0-PILOT-STATIONARY-001.raw.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/device_measurements/pilot/M-C0-PILOT-STATIONARY-001.raw.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY_SCHEMA_1.2",
      "derived_artifacts": [
        "archive/legacy_main_repo/devices/mmwave/device_measurements/qa/M-C0-PILOT-STATIONARY-001.qa.json"
      ],
      "subject_id": "SUBJ-001",
      "subject_relationship_to_other_sessions": "Same PR18 subject_id string SUBJ-001 as desk-work Pilot. Session manifest JSON is missing (only QA present).",
      "date": "2026-08-14",
      "duration": {
        "seconds_approx": 179.92,
        "records": 1799,
        "telemetry_row_hz": 9.99333,
        "source": "PR18_QA"
      },
      "intended_condition": "stationary",
      "actually_observed_or_reference_condition": "Stationary Pilot; no independent respiration reference. Low-amplitude / DEGRADED majority.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "phase_age_ms p95=15ms max=17ms; M-C0 later estimated fresh cadence ~9.993 Hz",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "BREATH_PHASE_LOW_AMPLITUDE on 1568/1799; DEGRADED 1568 / VALID 231; no session_manifest.json in manifests/",
      "existing_qa_or_report_reference": [
        "archive/legacy_main_repo/devices/mmwave/device_measurements/qa/M-C0-PILOT-STATIONARY-001.qa.json"
      ],
      "unresolved_ambiguity": "No committed session_manifest.json for this Pilot; condition/geometry less documented than desk-work.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "sha256": "e2b832fd3a72f18b4c3a370738c10e58c0269283dac218ae2d7d4dad48036f6f",
      "firmware_version": "safenest-mr60-esp/1.2.0",
      "config_hash": "b817e8bfd5e52b18275626f7b6a9bd60098ea4b108428a5aaf63600dbc987834"
    },
    {
      "session_id": "AUG08_IDENTITY_RAW_20S",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "AUG08_LIVE_RAW_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/identity_raw_20s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/identity_raw_20s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY_SCHEMA_1.2",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN",
      "date": "2026-08-08",
      "duration": {
        "seconds_approx": 20,
        "records": 199,
        "source": "filename_and_line_count"
      },
      "intended_condition": "identity_raw_capture",
      "actually_observed_or_reference_condition": "Sampled first records show LOCK_LOSS_FREEZE / DEGRADED, breath_phase near 0, freeze_detected true",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "lock_loss_freeze_in_sampled_records",
      "existing_qa_or_report_reference": [
        "archive/legacy_main_repo/devices/mmwave/validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/FINAL_REPORT_KO.md"
      ],
      "unresolved_ambiguity": "Short identity capture; not a labeled respiration trial.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "firmware_version": "safenest-mr60-esp/1.2.0"
    },
    {
      "session_id": "AUG08_NO_PERSON_RAW_10S",
      "artifact_class": "PHYSICAL_SOURCE_EVIDENCE",
      "evidence_family": "AUG08_LIVE_RAW_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/no_person_raw_10s.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/no_person_raw_10s.jsonl",
      "physical_source_format": "ESP_JSONL_TELEMETRY_SCHEMA_1.2",
      "derived_artifacts": [],
      "subject_id": "NONE_INTENDED_EMPTY",
      "subject_relationship_to_other_sessions": "N/A",
      "date": "2026-08-08",
      "duration": {
        "seconds_approx": 10,
        "source": "filename"
      },
      "intended_condition": "no_person",
      "actually_observed_or_reference_condition": "Sampled records: human_detected_raw true with LOCK_LOSS_FREEZE / DEGRADED; filename says no-person but sampled freeze lock may not match empty-room intent. Ambiguous.",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": true,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "filename_no_person_vs_sampled_presence_and_freeze",
      "existing_qa_or_report_reference": [
        "archive/legacy_main_repo/devices/mmwave/validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/FINAL_REPORT_KO.md"
      ],
      "unresolved_ambiguity": "Need full-file presence statistics before treating as a clean empty-room recording.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "firmware_version": "safenest-mr60-esp/1.2.0"
    }
  ],
  "companion_files": [
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s1_v120_telemetry_receipts",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s1_v120_telemetry_receipts.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s1_v120_telemetry_receipts.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": null,
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 325404,
      "git_blob_sha_at_raw_index": "043a9816caad496fc97e31b9e853d46d2d04e990"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s1_v120_watch_prompts",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s1_v120_watch_prompts.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s1_v120_watch_prompts.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": null,
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1048,
      "git_blob_sha_at_raw_index": "273d19395ce1e39d50d5eff5e55793ea62bd16d5"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_telemetry_receipts",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_telemetry_receipts.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_telemetry_receipts.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": null,
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 115668,
      "git_blob_sha_at_raw_index": "45dd5a148ac01f41e7d7d57d7fd2d68d97df0320"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_watch_prompts",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_watch_prompts.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_attempt02_v120_watch_prompts.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": null,
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 312,
      "git_blob_sha_at_raw_index": "e26085a93222bf31597850a13ca856f9b21b6e56"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s2_recovery_v120_telemetry_receipts",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_v120_telemetry_receipts.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_v120_telemetry_receipts.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": null,
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 520014,
      "git_blob_sha_at_raw_index": "7ab6310e271674912a3a1e085cfd3d9427298c75"
    },
    {
      "session_id": "LEGACY_2026-08-01_heartrate_watch_s2_recovery_v120_watch_prompts",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_v120_watch_prompts.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/kpi/2026-08-01_heartrate_watch_s2_recovery_v120_watch_prompts.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-08-01",
      "duration": null,
      "intended_condition": "occupied_apple_watch_hr_comparison",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "PRESENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 1684,
      "git_blob_sha_at_raw_index": "843f450e463ee3284607c5992894637b56df3fc6"
    },
    {
      "session_id": "LEGACY_2026-07-13_d06_m0_trial01_timing",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial01_timing.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial01_timing.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": null,
      "intended_condition": "presence_transition",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 139226,
      "git_blob_sha_at_raw_index": "413f91fde6f71f6016ddaff77717302174b6849e"
    },
    {
      "session_id": "LEGACY_2026-07-13_d06_m0_trial02_timing",
      "artifact_class": "COMPANION_NOT_MR60_WAVEFORM",
      "evidence_family": "PRE_PR18_LEGACY_ESP_JSONL",
      "repository": "https://github.com/jinsu1011/safenest-embedded-competition",
      "team_main_sha": "c6979cd2bc5383e6aeca94a2e4a7c6e2b0d75c16",
      "historical_path": "devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial02_timing.jsonl",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/logs/transitions/2026-07-13_d06_m0_trial02_timing.jsonl",
      "physical_source_format": "COMPANION_LOG",
      "derived_artifacts": [],
      "subject_id": "UNKNOWN",
      "subject_relationship_to_other_sessions": "UNKNOWN; delivery exporter later hardcodes S001 but these logs do not carry a verified subject field",
      "date": "2026-07-13",
      "duration": null,
      "intended_condition": "presence_transition",
      "actually_observed_or_reference_condition": "not_applicable",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "NOT_APPLICABLE",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": false,
      "presence_distance_motion_metadata": false,
      "freshness_timing_quality": "ABSENT",
      "independent_reference_availability": "NONE_FOR_RESPIRATION; Apple Watch HR files are heart-rate comparison only",
      "known_anomaly_or_failure": null,
      "existing_qa_or_report_reference": [
        "docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md",
        "archive/legacy_main_repo/devices/mmwave/device_measurements/reports/raw_file_index.json"
      ],
      "unresolved_ambiguity": "Filename/path is the primary condition label; subject identity is not in the JSONL.",
      "split_membership": "NOT_ASSIGNED_DEFERRED_TO_M-N1",
      "size_bytes": 167898,
      "git_blob_sha_at_raw_index": "10b0e62f5983fe59ba1d23f526e75bc5b6b6dc2a"
    }
  ],
  "recent_pi_runtime_reference": [
    {
      "session_id": "PI_20260816_13",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260816_13_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_NO_NESTED_MMWAVE",
      "subject_id": "UNKNOWN",
      "date": "2026-08-16",
      "duration": {
        "seconds_approx": 3080.7,
        "records": 2737,
        "host_row_hz_approx": 0.888
      },
      "intended_condition": "unlabeled_pi_runtime",
      "actually_observed_or_reference_condition": "UNKNOWN",
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "ABSENT",
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": "pir_motion_only",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "No nested mmwave.breath_phase; ~0.9 Hz host rows",
      "unresolved_ambiguity": "Useful as runtime plumbing evidence only.",
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false
    },
    {
      "session_id": "PI_20260816_14",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260816_14_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_NO_NESTED_MMWAVE",
      "subject_id": "UNKNOWN",
      "date": "2026-08-16",
      "duration": {
        "seconds_approx": 3597.9,
        "records": 1518,
        "host_row_hz_approx": 0.422
      },
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "ABSENT",
      "vendor_respiration_bpm_available": true,
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false,
      "known_anomaly_or_failure": "No nested mmwave.breath_phase"
    },
    {
      "session_id": "PI_20260816_15",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260816_15_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_NO_NESTED_MMWAVE",
      "subject_id": "UNKNOWN",
      "date": "2026-08-16",
      "duration": {
        "seconds_approx": 580.7,
        "records": 478,
        "host_row_hz_approx": 0.821
      },
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "ABSENT",
      "vendor_respiration_bpm_available": true,
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false
    },
    {
      "session_id": "PI_20260817_06",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260817_06_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_NO_NESTED_MMWAVE",
      "subject_id": "UNKNOWN",
      "date": "2026-08-17",
      "duration": {
        "seconds_approx": 274.2,
        "records": 276,
        "host_row_hz_approx": 1.003
      },
      "breath_phase_or_resp_phase_available": false,
      "phase_age_ms_available": "ABSENT",
      "vendor_respiration_bpm_available": true,
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false
    },
    {
      "session_id": "PI_20260817_07",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260817_07_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_MIXED_THEN_NESTED_MMWAVE",
      "subject_id": "UNKNOWN",
      "date": "2026-08-17",
      "duration": {
        "seconds_approx": 3347.6,
        "records": 10466,
        "nested_mmwave_records": 9736,
        "host_row_hz_approx": 3.126
      },
      "intended_condition": "unlabeled_pi_runtime",
      "actually_observed_or_reference_condition": "UNKNOWN; file starts without nested mmwave then includes schema 1.2 breath_phase",
      "breath_phase_or_resp_phase_available": "PARTIAL_9736_of_10466",
      "phase_age_ms_available": "PRESENT_WHEN_NESTED",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": "pir_motion plus nested mmwave when present",
      "freshness_timing_quality": "phase_age_ms min 0 median 40 p95 174 max 5342 on nested rows; host cadence ~3.1 Hz not ESP 10 Hz",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "Mixed schema in one file; firmware_version safenest-esp32-sensor-node/1.2.0 (unified node, not safenest-mr60-esp/1.2.0)",
      "unresolved_ambiguity": "Condition/subject unlabeled. Not supervised evidence.",
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false,
      "firmware_version": "safenest-esp32-sensor-node/1.2.0"
    },
    {
      "session_id": "PI_20260817_08",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260817_08_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_NESTED_MMWAVE_SCHEMA_1.2",
      "subject_id": "UNKNOWN",
      "date": "2026-08-17",
      "duration": {
        "seconds_approx": 2815.7,
        "records": 21064,
        "bad_lines": 1,
        "host_row_hz_approx": 7.48
      },
      "intended_condition": "unlabeled_pi_runtime",
      "actually_observed_or_reference_condition": "UNKNOWN; two boot_id values in one file (743 + 20321 records) so this is likely concatenated runtime segments",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "phase_update_identity_available": false,
      "vendor_respiration_bpm_available": true,
      "presence_distance_motion_metadata": "pir_motion plus nested mmwave",
      "freshness_timing_quality": "phase_age_ms min 0 median 33 p95 76 max 5779; host cadence ~7.48 Hz",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": "One malformed JSON line; concatenated boot_ids; firmware safenest-esp32-sensor-node/1.2.0",
      "existing_qa_or_report_reference": [
        "docs/20260817_SafeNest_mmWave_MR60_Compatible_Model_Development_Roadmap_01.md"
      ],
      "unresolved_ambiguity": "Roadmap example file. Numeric range/timing/source-behavior reference only. Do not promote to supervised training or formal validation.",
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false,
      "firmware_version": "safenest-esp32-sensor-node/1.2.0",
      "breath_phase_range_sampled": {
        "n": 21016,
        "min": -0.848227,
        "max": 0.929102
      }
    },
    {
      "session_id": "PI_20260817_09",
      "artifact_class": "RECENT_PI_RUNTIME_REFERENCE",
      "evidence_family": "RECENT_PI_RUNTIME_REFERENCE",
      "repository": "https://github.com/yuname121/integration",
      "commit_sha": "a966b164e99b01f7a3e80a596d30d388b3a567d6",
      "current_path": "data/mmwave/20260817_09_mmwave.jsonl",
      "physical_source_format": "PI_HOST_JSONL_NESTED_MMWAVE_SCHEMA_1.2",
      "subject_id": "UNKNOWN",
      "date": "2026-08-17",
      "duration": {
        "seconds_approx": 1007.7,
        "records": 7436,
        "host_row_hz_approx": 7.378
      },
      "intended_condition": "unlabeled_pi_runtime",
      "actually_observed_or_reference_condition": "UNKNOWN",
      "breath_phase_or_resp_phase_available": true,
      "phase_age_ms_available": "PRESENT",
      "vendor_respiration_bpm_available": true,
      "freshness_timing_quality": "phase_age_ms min 0 median 32 p95 72 max 162",
      "independent_reference_availability": "NONE",
      "known_anomaly_or_failure": null,
      "unresolved_ambiguity": "Unlabeled. Same unified ESP node firmware as 08.",
      "split_membership": "NOT_SUPERVISED_TRAINING_EVIDENCE",
      "supervised_training_eligible": false,
      "firmware_version": "safenest-esp32-sensor-node/1.2.0"
    }
  ],
  "derived_and_analysis_groups": [
    {
      "group_id": "DELIVERY_V2_CSV_WINDOWS",
      "artifact_class": "DERIVED_DATA",
      "note": "Warmup-skipped CSV windows plus copied original_jsonl. Not independent physical sessions. resp_phase is unmodified breath_phase. phase_age_ms is not in the CSV.",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/",
      "source_physical_sessions": [
        "S001_NORMAL_D06",
        "S001_NORMAL_D09",
        "S001_NORMAL_D12",
        "S001_NORMAL_D15",
        "S001_BREATH_PACED_12_01",
        "S001_BREATH_PACED_12_02",
        "S001_BREATH_PACED_15_03",
        "S001_BREATH_PACED_20_04",
        "S001_BREATH_PACED_20_05"
      ]
    },
    {
      "group_id": "DELIVERY_V1_ENTRY_EXIT_CSV_TRIALS",
      "artifact_class": "DERIVED_DATA",
      "note": "Ten ENTRY_EXIT CSV trials split from one physical JSONL. Counting 10 CSVs as 10 independent physical sessions would be double-counting.",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/csv/2026-07-25_han_junwoo_delivery/",
      "source_physical_sessions": [
        "LEGACY_2026-07-25_entry_exit_10"
      ],
      "derived_trial_count": 10
    },
    {
      "group_id": "FIRMWARE_ANALYSIS_SUMMARIES",
      "artifact_class": "ANALYSIS_OUTPUT",
      "current_path": "archive/legacy_main_repo/devices/mmwave/firmware/analysis/",
      "note": "JSON summaries and plots derived from firmware logs."
    },
    {
      "group_id": "QUALITY_POLICY_AND_REPLAY_WINDOWS",
      "artifact_class": "ANALYSIS_OUTPUT",
      "current_path": "archive/legacy_main_repo/devices/mmwave/validation_results/",
      "note": "quality_policy candidate windows and replay_v5 windows are derived from existing physical logs, not new captures."
    },
    {
      "group_id": "AUG08_LIVE_INFERENCE_LOGS",
      "artifact_class": "MODEL_OUTPUT",
      "note": "Most 2026-08-08 live jsonl files are window/session inference logs with raw_sensor_data_stored=false. They prove a live USB session happened but do not retain the breath_phase waveform. Do not count as additional physical sessions.",
      "examples": [
        "validation_results/2026-08-08_live_baseline_3windows.jsonl",
        "validation_results/2026-08-08_no_person_30s.jsonl",
        "validation_results/2026-08-08_normal_70cm_seated_3windows.jsonl",
        "validation_results/final_live/2026-08-08_standalone_mmwave_attempt01/live_performance_3windows.jsonl"
      ],
      "not_physical": [
        "validation_results/2026-08-08_preflight_10s.jsonl (connection_failure)",
        "validation_results/final_live/2026-08-08_current_production_attempt01/raw_preflight_15s.jsonl (thermal/health console text, not MR60 JSONL)"
      ]
    },
    {
      "group_id": "M_C0_CORRESPONDENCE_AUDIT",
      "artifact_class": "ANALYSIS_OUTPUT",
      "current_path": "research/mmwave_ai/datasets/mmwave/manifests/M-C0_correspondence_audit/",
      "note": "Historical correspondence audit of 12 expected files. Useful secondary evidence. Not a complete physical inventory and not M-N0. Historical B live gate remains CLOSED."
    },
    {
      "group_id": "PUBLIC_PHASE_AB_MANIFESTS",
      "artifact_class": "MODEL_OUTPUT",
      "note": "RaspberryPi/Ondevice_AI/datasets/mmwave/manifests/* are public 110-subject Phase A/B artifacts, not Team MR60 physical measurements."
    },
    {
      "group_id": "PR18_PILOT_FIXTURE",
      "artifact_class": "DERIVED_DATA",
      "current_path": "archive/legacy_main_repo/devices/mmwave/device_measurements/fixtures/example.raw.jsonl",
      "note": "Example fixture, not a physical session."
    }
  ],
  "ml_split_policy": "NOT_ASSIGNED. Team-only subject-wise TRAIN/VAL/TEST is IMPOSSIBLE because unique physical subjects = 1. M-N1 owns ML-role classification.",
  "recent_pi_status": "FOUND",
  "major_provenance_gaps": [
    "Physical-person identity for the Team set is OWNER_CONFIRMED_SINGLE_SUBJECT (one participant). Machine-readable subject fields remain ABSENT or HARDCODED on many files; S001 and SUBJ-001 are aliases, not file-internal identity proof. Historical exporter hardcoding is not a valid future capture design.",
    "No independent respiration reference in any inventoried Team or Pi session. Apple Watch files are heart-rate comparison only. Paced cue is not physiology ground truth.",
    "Stationary PR18 Pilot has no committed session_manifest.json.",
    "Most 2026-08-08 live USB runs stored inference logs only (raw_sensor_data_stored=false).",
    "Early 2026-07-13 JSONL lacks phase_age_ms; delivery CSV windows also lack it even when source JSONL from 2026-07-25+ has it.",
    "Exact 0x0A13 frame-arrival identity is not logged; phase_age_ms is staleness evidence only.",
    "Team physical tree relocated to archive/legacy_main_repo/; live devices/mmwave/ is empty on current team main.",
    "Pi 20260817_08 concatenates two boot_ids; Pi 16th/early-17th files lack breath_phase."
  ],
  "gate": {
    "result": "PASS_WITH_LIMITATIONS",
    "m_n1_authorized": true,
    "reason": "Known Team MR60 physical evidence is located or explicitly accounted for, physical vs derived is distinguished, and remaining condition/freshness/raw-source gaps are explicit. Physical-subject identity for the Team set was later corrected to OWNER_CONFIRMED_SINGLE_SUBJECT; independent respiration labels and timing provenance were not repaired."
  }
}
```

