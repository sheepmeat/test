# SafeNest mmWave V2 — PUBABS-A0A1 Public ABSENT Source Validation

- Phase: **PUBABS-A0A1 — public ABSENT / both-class source validation**
- Date: 2026-08-26
- Base SHA: `d89a0c598eebce488d98cfadfac00f9aa68e0348` (`origin/main`)
- Gate: **source validation only**. M-PV3.8 remains `RESOURCE_BLOCKED_CLOSED`. No membership. No evaluation. No M-PV4.
- Manifests: `datasets/mmwave/manifests/PUBABS_A0A1_public_source_validation/`
- Payload inspection workdir: `/tmp/pubabs-a0a1-payload` (**not committed**)

This package screens public radar datasets as candidate ABSENT / both-class sources. It does not reopen M-PV3.8, construct membership, authorize capture, or start PUBABS-A2/A3.

---

## Overall verdict

`PASS_STRONG_PUBLIC_SOURCE_FOUND`

At least one strong same-dataset both-class public source (C1) was located with verified no-human semantics and valid radar CSV observations. Downstream PUBABS-A2/A3 are **recommended, not authorized**.

---

## Scope and freeze boundaries

| Item | Status |
|---|---|
| M-PV3.8 lifecycle | Unchanged — `RESOURCE_BLOCKED_CLOSED` |
| M-PV3.8 membership / evaluation | Not executed; not authorized |
| M-PV4 | Unauthorized |
| PUBABS-A2 / A3 | Recommended only; **authorizations all false** |
| Payload binaries under `/tmp/pubabs-a0a1-payload` | Inspected locally; **not** added to git |

---

## Candidate gates

| ID | Source | License | Gate |
|---|---|---|---|
| C1 | UniWA robot-mounted UWB — Zenodo [15032859](https://doi.org/10.5281/zenodo.15032859) | CC-BY-4.0 | `A_STRONG_SAME_DATASET_BOTH_CLASS` |
| C2 | UniWA X4M200 Signs-of-life — Zenodo [7679165](https://doi.org/10.5281/zenodo.7679165) | CC-BY-NC-SA-4.0 | `B_USABLE_WITH_LIMITATIONS` |
| C3 | UniWA foliage — Zenodo [10815247](https://doi.org/10.5281/zenodo.10815247) | CC-BY-NC-SA-4.0 | `C_RESEARCH_ONLY` |
| C4 | Gambi walking mmWave — Zenodo [3824534](https://doi.org/10.5281/zenodo.3824534) Background.zip | CC-BY-4.0 | `D_REJECT` |

### C1 — `A_STRONG_SAME_DATASET_BOTH_CLASS`

- Same `Data.zip`: `Empty_space` + `N1`–`N6` (CD: 77 entries; no folder named `N0` in this record; absence is `Empty_space`).
- License: CC-BY-4.0 → `LICENSE_OK_FOR_RESEARCH`.
- Complex 180-bin range-bin CSV; native ≈ **18.85 Hz** from timestamp deltas; sessions ≫ 30 s (Empty_space ≈ 15 min est.; presence ≈ 3 min est.).
- Structural downsample to 10 Hz: **YES**.
- Domain conflict vs SafeNest: **MEDIUM** (robot through-wall UWB).
- `sensor_independent_trace`: **UNVERIFIED**.
- Repo leakage: **UNSEEN**.

### C2 — `B_USABLE_WITH_LIMITATIONS`

- Same archive: `Human Presence` + `No human Presence`.
- License: CC-BY-NC-SA-4.0 → `LICENSE_NONCOMMERCIAL_SHAREALIKE`.
- No-human semantics: path + full amplitude CSV opened → **VERIFIED** (was PARTIALLY_VERIFIED by path alone).
- Metadata sampling rate **17 Hz**; opened file shape **8818×109** floats (`clean amplitude_NoPresence Out 15mins4.csv`).
- Domain: **MEDIUM**. Repo leakage: **UNSEEN**.

### C3 — `C_RESEARCH_ONLY`

- Explicit `Absence.zip` / `Presence.zip`; metadata **141 present / 127 absence × 150 s**.
- Domain conflict: **HIGH** (foliage + wind confound).
- License: NC-SA.
- Internal structure: **FULL_PAYLOAD_REQUIRED** (no deep payload open this phase).
- Repo leakage: **UNSEEN**.

### C4 — `D_REJECT` (ABSENT membership source)

- `Background.zip` → sole member `Background/adc_Data.mat`.
- Companion paper supports “absence of subjects” for background analysis: **PARTIAL** only.
- Not sealed empty-zone contract evidence for SafeNest ABSENT membership → **REJECT**.
- `no_human_semantics`: **UNVERIFIED** for membership use.
- Repo leakage: **UNSEEN**.

---

## Payload actually inspected (bytes / methods)

| Artifact | Bytes (approx.) | Method |
|---|---:|---|
| C1–C4 Zenodo API JSON | ~6–9 KB each | HTTPS API |
| C1 `CNN_Model.zip` | 86048 | Full download; unzip list (docs/png only) |
| C1 `Data.zip` HEAD / range head / EOCD / CD | 0 + 65536 + 262144 + 7823 | HTTP range; no full 3.37 GB download |
| C1 Empty_space + N1 CSV prefixes | 524288 × 2 | Range extract of STORE members |
| C2 Signs.zip range head / EOCD / CD | 65536 + 262144 + 172655 | HTTP range; no full ~910 MB download |
| C2 no-human amplitude CSV | 10047573 | Full single member inflate |
| C3 Presence/Absence zips | 0 body | API metadata only (~2 GB each not downloaded) |
| C4 `Background.zip` CD | 69 | Range CD (1 entry) |
| C4 companion OA PDF | 2691249 | Text extract for Background semantics |

Full multi-GB archives were **not** committed and are **not** part of this repository change.

---

## Leakage

Repository search for DOIs / Zenodo IDs / characteristic paths: all four candidates **UNSEEN** in the active SafeNest tree (excluding unrelated archive noise). No prior checkout of these payloads into tracked datasets.

---

## Compatibility checklist (machine-readable mirrors)

See manifests:

- `source_registry.json`
- `access_license_audit.json`
- `payload_structure_audit.json`
- `absent_semantics_audit.json`
- `same_dataset_both_class_audit.json`
- `domain_conflict_audit.json`
- `compatibility_summary.json`
- `validation_result.json` (`m_pv38_unchanged: true`, all authorizations `false`)

---

## Downstream recommendation (not authorization)

1. **Recommend** PUBABS-A2 then PUBABS-A3 focused on **C1**.
2. **Optional parallel** PUBABS-A2 on **C2** (NC-SA limitations apply).
3. Hold **C3** as research-only; do not treat as membership path without separate domain justification.
4. Do **not** pursue **C4** as ABSENT membership source.

This PUBABS-A0A1 package does **not** authorize A2/A3, membership, evaluation, or M-PV4.

---

## Explicit non-actions

- Did not modify M-PV3.8 lifecycle, acquisition gate, or membership artifacts.
- Did not create ABSENT windows, splits, or evaluation runs.
- Did not commit `/tmp/pubabs-a0a1-payload` binaries.
- Did not merge any PR as part of this phase.
- Did not claim MR60 / Raspberry Pi / clinical validation from these public sources.
