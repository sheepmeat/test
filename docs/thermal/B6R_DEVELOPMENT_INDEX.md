# Thermal B6-R Development Index

이 문서는 Thermal / MI48 B6-R 작업의 단일 탐색 지점이다. 과학적 판정은 각 stage 보고서를 우선하며, 이 인덱스는 보고서를 대체하지 않는다.

## Current Active Branch

`feature/thermal-b6r-development`

모든 B6-R 단계 작업은 사용자가 승인한 한 stage 또는 한 wave만 이 브랜치에서 수행한다. stage별 브랜치를 새로 만들지 않는다.

## Authoritative Roadmap

`docs/20260822_Codex_Thermal_B6R_Robust_Relative_FP32_Parallel_Roadmap_KO_01.md`

## Repository Main Documentation

`docs/README.md`

## Stage Status

| Stage | Status | Report | Artifact | Commit | Notes |
|---|---|---|---|---|---|
| B6R-0 | `FAIL` | `docs/reports/20260822_LunaMax_Agent2_Thermal_B6R0_Asset_Baseline_Verification_01.md` | `datasets/thermal/manifests/B6R-0_asset_baseline_verification/` | source `ee966f9186915a2364e81f944f45aabf22b7b71c`; merge `c70d994ecd4be666dd46e0b7b06872ee8f97f0f2` | B5 checkpoint와 B5 candidate binary가 materialize되지 않았고 TensorFlow/LiteRT 및 Pi 증거가 없다. |
| B6R-1 | `INCONCLUSIVE` | `docs/reports/20260822_LunaMax_Agent1_Thermal_B6R1_MI48_Inventory_01.md` | `datasets/thermal/manifests/B6R-1_mi48_inventory/` | source `d87d452372cc890e85ec6c4d5ec117052be865df`; merge `d0c0c911eb2e27cf91d8f057d1cc9f9360c7fb6a` | authoritative MI48 snapshot을 찾지 못했고 MI48 eligible frame은 0이다. profiler와 focused test는 보존했다. |
| B6R-2 | `BLOCKED` | `docs/reports/20260826_Codex_Thermal_B6R_B6R-2_Retry_Execution_Report_KO_02.md` (이전: `docs/reports/20260826_Codex_Thermal_B6R_B6R-2_Execution_Report_KO_01.md`) | `datasets/thermal/manifests/B6R-2_dataset_contract_retry_02/` (이전: `datasets/thermal/manifests/B6R-2_dataset_contract/`) | 이전 `ab77885`; retry delivery commit은 `git log` 참조 | archive 6/6 SHA 동일, checksum 실패는 CRLF 원인으로 진단. MI48/group/label/holdout evidence 부재는 해소되지 않아 안전 중단했다. |
| B6R-3 | `NOT_STARTED` | - | - | - | - |
| B6R-4 | `NOT_STARTED` | - | - | - | - |
| B6R-5 | `NOT_STARTED` | - | - | - | - |
| B6R-6 | `NOT_STARTED` | - | - | - | - |
| B6R-7 | `NOT_STARTED` | - | - | - | - |
| B6R-8 | `NOT_STARTED` | - | - | - | - |
| B6R-9 | `NOT_STARTED` | - | - | - | - |
| B6R-10 | `NOT_STARTED` | - | - | - | - |
| B6R-11 | `NOT_STARTED` | - | - | - | - |
| B6R-12 | `NOT_STARTED` | - | - | - | - |
| B6R-13 | `NOT_STARTED` | - | - | - | - |
| B6R-14 | `NOT_STARTED` | - | - | - | - |

## External Real-Capture Pilot Evidence (Non-Gating)

| Package | Status | Report | Source | Notes |
|---|---|---|---|---|
| `B6R-RC0` Desktop `sessions` pilot evidence review | `INCONCLUSIVE / NON-GATING` | `docs/reports/20260826_Codex_Thermal_B6R_Desktop_Sessions_Real_Capture_Pilot_Gate_Assessment_Report_KO_01.md` | external `Desktop/sessions/` (not copied into Git) | 5 Thermal-90 sessions, all subject `S000`; raw/native/checksum evidence exists, but 3 sessions are `CAPTURE_INVALID`, unit/orientation are unverified, no locked holdout, and validator model-use eligibility is not authorized. This package does not open B6R-1/2 or training. |

## Current PC Thermal Data Paths

아래 절대 경로는 현재 작업 PC에서 다음 agent가 파일을 찾기 위한 사람용 참고다. portable contract·manifest에는 절대 경로를 저장하지 않는다.

| 역할 | 현재 PC 위치 | 상태·경계 |
|---|---|---|
| 실제 센서 capture | `C:\Users\KIMTAEGYUN\Desktop\sessions` | `Thermal-90` 5세션, B6R-RC0 non-gating pilot; 학습·holdout 금지 |
| public SDT source archive | `C:\Users\KIMTAEGYUN\Documents\ChatGPT\Thermal_AI\열화상_dataset` | 6개 archive, P0 contract size/SHA `6/6` 일치; MI48 아님 |
| active checkout | `C:\Users\KIM TAEGYUN\Documents\ChatGPT\Thermal_AI\test` | 현재 feature branch root |
| P0 derived local payload | `<active checkout>\datasets\thermal\materialized\B6R-P0_public_sdt_v1` | 48,000개 float32, `.gitignore` local-only |
| P0 tracked evidence | `<active checkout>\datasets\thermal\manifests\B6R-P0_public_sdt_materialization` | split/provenance/source immutability/validation |
| P0 contract | `<active checkout>\config\thermal\b6r_p0_public_sdt_contract.json` | `WORKSPACE_THERMAL_DATASET_ARCHIVES`, public-only claim boundary |

현재 Codex 환경에서는 사용자 profile 표기가 `KIMTAEGYUN`과 `KIM TAEGYUN` 두 형태로 노출된다. 두 표기의 source/capture 경로가 모두 보이므로, 다음 agent는 `Test-Path`와 checksum으로 현재 process의 실제 위치를 확인한다.

`열화상_dataset`은 P0/P1/P2 public-data source이고 `sessions`는 실제 `Thermal-90` capture pilot이다. 두 폴더는 서로 다른 evidence 계보이며 합치거나 MI48로 재명명하지 않는다. 경로가 보이지 않는 환경에서는 추측하지 말고 `Test-Path`와 P0 source hash를 먼저 확인한다.

## Public-data Auxiliary Stage Status

이 보조 흐름은 사용자의 2026-08-26 model-first 승인으로 추가되었으며, 기존 B6R-0~14의 판정과 선행 gate를 변경하지 않는다.

| Stage | Status | Report | Artifact | Commit | Notes |
|---|---|---|---|---|---|
| B6R-P0 | `PASS_WITH_LIMITATIONS` | `docs/reports/20260826_Codex_Thermal_B6R_B6R-P0_Public_SDT_Materialization_Report_KO_01.md` | `datasets/thermal/manifests/B6R-P0_public_sdt_materialization/`; local payload `datasets/thermal/materialized/B6R-P0_public_sdt_v1/` | delivery commit은 `git log` 참조 | public SDT 48,000개를 원본 split 그대로 materialize하고 전수 provenance·결정론·원본 불변 검증을 통과했다. MI48/physical/safety 근거는 아니다. |
| B6R-P1 | `PASS_WITH_LIMITATIONS` | `docs/reports/20260826_Codex_Thermal_B6R_B6R-P1_Public_SDT_Training_Report_KO_01.md` | `models/thermal/public_sdt/`; `datasets/thermal/manifests/B6R-P1_public_sdt_controlled_training/` | delivery commit은 `git log` 참조 | P0 exact identity의 TRAIN/DEVELOPMENT만 사용해 NumPy pooled-MLP 실험 모델을 생성했다. test read 0, legacy manifest 불변. TFLite/Pi/safety 권한은 별도 단계다. |
| B6R-P2 | `PASS` | `docs/reports/20260826_Codex_Thermal_B6R_P2_FP32_TFLite_Export_Offline_Parity_Report_KO_01.md` | `models/thermal/public_sdt/public_sdt_pooled_mlp_fp32_tflite_v1.tflite`; `datasets/thermal/manifests/B6R-P2_public_sdt_fp32_tflite_export/` | delivery commit은 `git log` 참조 | P1 parameter를 그대로 TensorFlow graph와 70,592-byte FP32 TFLite로 옮겼다. 48 DEVELOPMENT fixture 3단계 parity·2회 export byte determinism 통과, mismatch 0, locked test read 0, default/runtime 불변. |

## Historical Source Branches

| Branch | Original tip SHA | Related PR | Unified branch preservation | Deletion status |
|---|---|---|---|---|
| `codex/thermal-b6r0-asset-baseline-audit` | `ee966f9186915a2364e81f944f45aabf22b7b71c` | #125, `OPEN` at audit time | full `--no-ff` merge; report and manifest directory preserved | local `NOT_DELETED_WORKTREE_IN_USE`; remote `NOT_DELETED_APPROVAL_REJECTED` |
| `codex/thermal-b6r1-mi48-inventory-v2` | `d87d452372cc890e85ec6c4d5ec117052be865df` | #124, `OPEN` at audit time | full `--no-ff` merge; report, manifest directory, profiler, and test preserved | local `DELETED`; remote `NOT_DELETED_APPROVAL_REJECTED` |
| `docs/thermal-b6r-robust-relative-roadmap` | `37f5b2dd914654a12539149317b0895cdf47c00b` | #117, `MERGED` | already an ancestor of `origin/main`; authoritative main copy retained | local `DELETED`; remote `NOT_DELETED_APPROVAL_REJECTED` |
| `codex/thermal-b6r1-mi48-inventory` | `bb5d7fd1518b50297e46858365540cf60ce9e740` | 확인된 전용 PR 없음 | already an ancestor of `origin/main`; unique work 없음 | local `DELETED` |
| `thermal/b6r-1-mi48-inventory` | `bb5d7fd1518b50297e46858365540cf60ce9e740` | 확인된 전용 PR 없음 | already an ancestor of `origin/main`; unique work 없음 | local `DELETED` |

PR #124와 #125는 통합 브랜치로 대체되는 기존 개발 경로다. 감사 시 GitHub CLI 인증 토큰이 유효하지 않아 PR 댓글 또는 종료 작업은 수행하지 않았다. 원격 구브랜치 삭제 요청도 열린 PR의 협업·복구 위험에 대한 별도 명시 승인이 필요하다는 안전 검토로 거부되어 재시도하지 않았다.

## Current Blockers

- B6R-0: B5 FLOAT checkpoint와 B5 FP32/FULL INT8 binary가 현재 환경에 materialize되지 않았다.
- B6R-0: TensorFlow/LiteRT runtime과 Raspberry Pi 하드웨어 증거가 없어 load, parity, latency, memory, stability를 검증할 수 없다.
- B6R-1: authoritative MI48 raw snapshot이 접근 가능한 경로에 없고 외부 `SafeNestssd`가 mount되지 않았다.
- B6R-1: 후보 archive의 MI48 identity가 해소되지 않았으며 식별된 eligible MI48 frame은 0이다.
- B6R-1: 외부 `Desktop/sessions` 실제 capture 파일럿은 존재하지만 metadata sensor model이 `Thermal-90`이고 권위 MI48 identity mapping이 없다. `B6R-RC0`는 non-gating assessment로만 기록했다.
- B6R-1: sessions 5개 모두 subject `S000`; `S000_011`, `S000_012`, `S000_014`는 packet/counter gap으로 `CAPTURE_INVALID`, unit/orientation/FPS도 완전히 검증되지 않았다.
- B6R-1: 현재 checkout에서 standalone validator가 generated evidence 10개의 checksum mismatch로 실패한다. CRLF→LF 정규화 시 10/10 registry와 일치하여 cross-platform line-ending 원인으로 진단됐다.
- B6R-2: session/label/split/holdout 계약을 만들 data gate가 충족되지 않았고 independent holdout이 없다. Desktop sessions도 `NOT_LOCKED_TEST`, `split_frozen_at=null`, `model_use_eligibility=NOT_AUTHORIZED_BY_CAPTURE_VALIDATOR`다.
- B6R-P0의 성공은 public-data 경로만 개방하며 위 MI48 blocker를 해소하지 않는다.

## Next Authorized Stage

`DATA_EVIDENCE_TRIAGE_WAITING_FOR_USER_INSTRUCTION`

- MI48 본선: B6R-3 또는 이후 stage는 승인되지 않는다. 권위 MI48 payload와 provenance를 복구하고 B6R-1을 새 revision으로 재검증한 뒤 B6R-2를 다시 실행해야 한다.
- External capture: `B6R-RC0` read-only assessment는 완료되었지만 비게이팅이다. 현재 `Desktop/sessions`만으로는 학습·holdout을 시작하지 않는다. 다음 행동은 Thermal-90/MI48 identity 승인, unit/orientation/quality 보완, 다인 재수집을 위한 acquisition/contract plan이며 새 사용자 승인이 필요하다.
- Public 보조: `B6R-P2`는 2026-08-26 사용자 승인으로 완료됐다. P0/P1의 split 역할, preprocessing, label mapping, architecture, trained parameter를 그대로 상속했다.
- B6R-P2 결과도 legacy 기본 모델·manifest를 덮어쓰거나 safety authority를 부여하지 않는다. locked public test read count는 `0`이다.
- 다음 public 작업 후보는 Raspberry Pi FP32 replay/shadow benchmark 성격이지만 아직 stage로 정의·승인·실행하지 않았다.

## Required Reading Order for Future Agents

1. `docs/README.md`
2. `docs/20260822_Codex_Thermal_B6R_Robust_Relative_FP32_Parallel_Roadmap_KO_01.md`
3. `docs/thermal/B6R_DEVELOPMENT_INDEX.md`
4. 실행하려는 stage의 직접 선행 stage 보고서
5. 직접 선행 stage의 manifest와 artifact
6. roadmap이 요구하는 stage-specific source, test, runtime 파일

실제 센서 파일럿을 검토하는 agent는 위 순서에 더해 `docs/reports/20260826_Codex_Thermal_B6R_Desktop_Sessions_Real_Capture_Pilot_Gate_Assessment_Report_KO_01.md`를 읽고, 외부 `Desktop/sessions/`를 raw/native/checksum/validation evidence로만 취급한다.

Public 보조 흐름을 수행하는 agent는 위 순서에 더해 `B6R-P0` 보고서, contract, validation result를 읽고 `PUBLIC_SDT_ONLY_NOT_MI48` 경계를 상속한다.

## Working Rules

1. `git fetch origin` 후 `feature/thermal-b6r-development`로 진입하고 `git pull --ff-only origin feature/thermal-b6r-development`를 수행한다.
2. 작업 트리가 깨끗한지 확인하고 사용자가 승인한 한 stage 또는 한 wave만 실행한다.
3. 역사적 `FAIL` 또는 `INCONCLUSIVE` 보고서를 덮어쓰거나 `PASS`로 바꾸지 않는다. 재실행은 새 revision 보고서로 남긴다.
4. stage별 전용 보고서를 `docs/reports/`에 생성하고 명시적 경로만 stage한다.
5. stage 결과와 정확한 commit SHA를 이 인덱스에 반영한 뒤 같은 활성 브랜치에 push하고 멈춘다.
6. `main` 통합 PR은 사용자가 milestone 범위를 명시적으로 승인할 때만 준비한다.
7. `B6R-P*`는 기존 B6R-0~14와 별도 identity를 사용한다. public dataset/model을 MI48로 재명명하지 않고 legacy model/default manifest를 수정하지 않는다.
8. `B6R-P1` 이후 학습은 TRAIN만 fit하고 DEVELOPMENT만 선택에 사용하며 `LOCKED_PUBLIC_TEST`는 명시적으로 승인된 최종 public 평가 전까지 metric·선택·튜닝 경로에서 열지 않는다.
9. `B6R-P2` artifact는 shadow-only deployment-format 후보다. Raspberry Pi·MI48·physical·latency·runtime integration 또는 safety 검증으로 승격하지 않는다.
10. `B6R-RC0` Desktop sessions evidence는 non-gating capture pilot이다. `Thermal-90`을 MI48로 재명명하지 않고, 단일 subject·invalid capture·미검증 unit/orientation·정적 posture proxy를 final training/holdout/낙상 성능 근거로 사용하지 않는다.
