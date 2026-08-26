# SafeNest Thermal B6-R B6R-2 재실행 보고서

## 1. 작업 개요

- 날짜: `2026-08-26`
- Stage: `B6R-2 — Session / Label / Split / Holdout Contract` 재실행 revision 2
- 작업 브랜치: `feature/thermal-b6r-development`
- 시작 HEAD: `ab7788546c8f1c9fa143d997e3081737d08d7dab`
- 작업 목적: 새 MI48·group·label·holdout 근거가 생겼는지 재검증하고 누수 없는 dataset contract를 동결할 수 있는지 판정
- 결과 상태: `BLOCKED`
- 작업 전 dirty worktree: `NO`

## 2. 이번 Stage의 목표와 실행 계약

핵심 질문은 subject/session/recording identity와 label provenance를 신뢰할 수 있고, adjacent-frame/random split 없이 group-isolated TRAIN/DEVELOPMENT/independent holdout 역할을 만들 수 있는가이다.

| 항목 | 계약 |
|---|---|
| 선행 조건 | 권위 있거나 승인된 MI48 identity, B6R-1 전체 accounting·schema·metadata evidence |
| 허용 입력 | B6R-1 machine-readable evidence, T-A5 역사 증거, workspace archive read-only 검사 |
| 금지 입력 | 폴더명·resize target만으로 MI48 승격, synthetic의 physical 대체, random frame split, `REAL_EVAL_DEVELOPMENT`의 holdout 재명명 |
| 필요한 구현 | entry gate 통과 시 dataset contract, provenance map, group split, contamination report, holdout seal |
| 필요한 테스트 | JSON/checksum, group isolation, exact/near-duplicate cross-role audit, 전체 sample accounting, holdout seal |
| 완료 gate | 한 group은 한 role에만 존재하고 contamination 및 holdout seal audit가 PASS |
| 다음 Stage 조건 | 위 B6R-2 gate PASS 후에만 B6R-3 허용 |

## 3. 작업 전 상태

### B1~B5와 runtime

- T-B1은 P1 TRAIN-global z-score를 선택했고, T-B2는 `SMALL_CNN_BASELINE_V1` 312,131 parameters를 유지했다.
- T-B3 multi-seed 결과와 T-B4 Keras→FP32→FULL INT8 결과는 역사적 read-only evidence다.
- B5 checkpoint/FP32/INT8 bytes는 현재 worktree에 없으며 B6R-0 판정은 `FAIL`이다.
- 현재 runtime은 `models/model_manifest.json`의 legacy `thermal_fall_int8_v0.1.0.tflite`와 frame-wise min-max 또는 `[0,1]` 입력 경로다. B5 P1 및 B6-R robust-relative 계보와 같지 않다.
- `REAL_EVAL_DEVELOPMENT`는 이미 개발에 사용되었으므로 pristine independent holdout이 아니다.

### B6R-1과 dataset

- B6R-1 상태는 `INCONCLUSIVE`, candidate identity는 `UNRESOLVED`다.
- 기존 accounting은 `6 = MI48 readable 0 + corrupt 0 + explicitly excluded 6`, identified MI48 frame은 `0`이다.
- `subject_id`, `session_id`, `recording_id`는 없으며 source class field만 관찰되었다.
- 프로젝트 루트의 `열화상_dataset`에는 `test.zip`, `validation.zip`, `train.zip.001`~`.004`가 있다.

## 4. 수행한 작업

1. 올바른 `sheepmeat/test` clone, 지정 branch, clean worktree, 원격 fast-forward 상태를 확인했다.
2. `docs/README.md`, B6-R roadmap, `AGENTS.md`, B6R-0~2 보고서·manifest, Thermal B1~B5, runtime/model/preprocessing 코드를 조사했다.
3. `열화상_dataset`의 6개 파일 SHA-256을 모두 다시 계산하여 B6R-1 registry와 `6/6` byte identity가 일치함을 확인했다. 원본에는 쓰지 않았다.
4. `test.zip`과 `validation.zip` central directory, label member, 첫 PNG header를 직접 읽었다.
5. source PNG와 model input의 축 관계를 확인했다. source는 H×W `480×640`; 역사적 `thermal_prep.py`의 PIL `resize((80, 62))`가 NumPy H×W `(62,80)`을 만들고 channel을 추가한다. 이는 raw MI48 `(80,62)` 또는 `(62,80)`의 증거가 아니다.
6. B6R-1 profiler compile, synthetic focused harness 4개, standalone validator를 재실행했다.
7. B6R-1 checksum mismatch를 진단했다. raw checkout은 `0/10`, CRLF→LF 정규화 후 `10/10`이 registry와 일치해 line-ending 변환이 원인임을 확인했다. 역사적 B6R-1 artifact와 validator는 수정하지 않았다.
8. MI48 identity·group provenance·independent holdout이 여전히 없으므로 split, contamination result, holdout을 만들거나 열지 않고 새 retry evidence를 기록했다.

## 5. 변경된 파일

- `.gitattributes` — retry artifact의 LF checkout을 고정.
- `datasets/thermal/manifests/B6R-2_dataset_contract_retry_02/prerequisite_reassessment.json` — 실행 계약, 실제 dataset 재검사, entry gate와 unblock 조건.
- `datasets/thermal/manifests/B6R-2_dataset_contract_retry_02/source_checksum_recheck.json` — 원본 archive 6개의 size·SHA-256 재검증.
- `datasets/thermal/manifests/B6R-2_dataset_contract_retry_02/validation_result.json` — 실행한 검증과 금지되는 주장.
- `datasets/thermal/manifests/B6R-2_dataset_contract_retry_02/checksums.sha256` — 신규 artifact checksum registry.
- `docs/reports/20260826_Codex_Thermal_B6R_B6R-2_Retry_Execution_Report_KO_02.md` — 본 보고서.
- `docs/thermal/B6R_DEVELOPMENT_INDEX.md` — B6R-2 retry 상태와 blocker 진단 갱신.

원시 dataset, historical B1~B5/B6R-1 artifact, model, runtime, sensor subsystem은 변경하지 않았다.

## 6. 실행한 주요 명령

1. `git rev-parse --show-toplevel`, `git remote -v`, `git status --short --branch`, `git branch --show-current`, `git log -5 --oneline --decorate` — repository/branch 확인, exit `0`.
2. `git fetch origin --prune` 및 `git pull --ff-only origin feature/thermal-b6r-development` — 원격 동기화, exit `0`, already up to date.
3. bundled Python `--version`, NumPy/platform 확인 — Python `3.12.13`, NumPy `2.3.5`, Windows 11 AMD64.
4. bundled Python `-m py_compile ...` — profiler/test syntax 확인, exit `0`.
5. bundled Python direct synthetic harness — `4 PASS`, exit `0`.
6. bundled Python `scripts/profile_thermal_b6r1_mi48.py validate ...` — checksum mismatch 10개, exit `1`.
7. bundled Python read-only ZIP inspection — 두 archive의 member/label/PNG header 확인, exit `0`.
8. `Get-FileHash -Algorithm SHA256` — 원본 archive 6개 hash 재계산, exit `0`.

## 7. 검증 및 테스트

| Test | Expected | Actual | Result |
|---|---|---|---|
| Branch/worktree | 지정 branch, clean | 지정 branch, clean | PASS |
| Source checksum recheck | B6R-1 registry와 동일 | 6/6 일치 | PASS |
| Archive metadata read | central directory/label/PNG header readable | 두 ZIP 모두 readable | PASS |
| Python compile | syntax valid | exit 0 | PASS |
| Focused synthetic harness | 4 tests pass | 4 PASS | PASS |
| pytest runner | suite 실행 | `No module named pytest` | NOT TESTED |
| B6R-1 standalone validator | checksum PASS | raw byte mismatch 10 | FAIL |
| Line-ending diagnosis | LF registry와 일치 여부 | CRLF→LF 후 10/10 일치 | PASS / ROOT CAUSE FOUND |
| B6R-2 group isolation | trustworthy groups 필요 | group identity 없음 | NOT TESTED / BLOCKED |
| Cross-role contamination | split/sample ledger 필요 | 생성 불가 | NOT TESTED / BLOCKED |
| Independent holdout seal | pristine holdout 필요 | 없음, 접근 0 | NOT TESTED / BLOCKED |

## 8. 주요 결과

- 원본 6개 archive는 B6R-1 당시와 SHA-256이 모두 같다.
- `test.zip`과 `validation.zip`은 각각 member 16,002개, PNG 16,000개, label record 8,000개를 가진다. 각 class token `0`~`3`은 2,000개씩 관찰됐다.
- 표본 PNG는 16-bit grayscale H×W `480×640`이다. 모델 입력 `(62,80,1)`은 역사적 resize 결과이지 native MI48 geometry 증거가 아니다.
- class token은 관찰할 수 있지만 MI48 provenance, subject/session/recording group, 독립 holdout 근거는 없다.
- B6R-1 validator 실패는 CRLF checkout 변환으로 진단됐지만 raw-byte standalone gate는 현재도 FAIL이다.
- holdout 접근 수와 원본 수정 수는 모두 `0`이다.

## 9. 생성 Artifact

| Artifact | SHA-256 | Size | Identity / Source |
|---|---|---:|---|
| `prerequisite_reassessment.json` | `d4dcb535d91bebca946d75877f4b8fc88b14f81fa9c0962131acd2169b58cc92` | 5,361 bytes | B6R-2 retry entry gate |
| `source_checksum_recheck.json` | `4cecfa345e3d1ff1c6aa1e482e2697f671cecf5d799cc898a15ad4c3883bab3d` | 1,569 bytes | workspace candidate source recheck |
| `validation_result.json` | `f9975c60c92d623be6898a2edfe4cffe3d5d177b185de70836490c2a63977695` | 1,613 bytes | B6R-2 retry validation result |
| `checksums.sha256` | self-hash 미기록 | 3-entry registry | 위 3개 artifact coverage |

## 10. 문제점 / 제한 사항

- owner-authorized MI48 snapshot 또는 승인된 대체 payload가 없다.
- subject/session/recording identity와 권위 label provenance가 없다.
- tuning에 쓰이지 않은 independent holdout이 없다.
- B6R-1 raw-byte validator의 cross-platform line-ending 재현 문제는 진단했지만 이번 B6R-2에서 역사적 artifact/code를 수정하지 않았다.
- pytest가 없어 pytest runner는 실행하지 못했다.
- physical MI48, Raspberry Pi, accuracy/recall/F1/latency 또는 실제 낙상 성능은 주장할 수 없다.

## 11. Stage Gate 판정

최종 판정: `BLOCKED`

| Gate 기준 | Evidence | 판정 |
|---|---|---|
| 권위 MI48 identity 및 usable schema | identified MI48 frame 0 | FAIL |
| subject/session 또는 정당화된 group | 필드 없음 | FAIL |
| label provenance | token만 관찰, MI48/group provenance 없음 | FAIL |
| group isolation | split 미생성 | BLOCKED |
| contamination audit | sample ledger 없음 | BLOCKED |
| independent holdout seal | pristine holdout 없음, 접근 0 | FAIL / SAFE STOP |
| predecessor standalone validation | raw checkout FAIL; CRLF root cause 확인 | FAIL_WITH_DIAGNOSIS |

B6R-3 진입은 허용되지 않는다.

## 12. 전체 B6-R 진행 상황

| Stage | 상태 | 핵심 결과 |
|---|---|---|
| B6R-0 | DONE_FAIL | B5 bytes/runtime/Pi capability 부재 |
| B6R-1 | DONE_INCONCLUSIVE | 권위 MI48 없음, eligible frame 0 |
| B6R-2 | BLOCKED | retry에서도 group/label/holdout gate 미충족 |
| B6R-3 | NOT_STARTED | B6R-2 PASS 필요 |
| B6R-4 | NOT_STARTED | - |
| B6R-5 | NOT_STARTED | - |
| B6R-6 | NOT_STARTED | - |
| B6R-7 | NOT_STARTED | - |
| B6R-8 | NOT_STARTED | - |
| B6R-9 | NOT_STARTED | - |
| B6R-10 | NOT_STARTED | - |
| B6R-11 | NOT_STARTED | - |
| B6R-12 | NOT_STARTED | - |
| B6R-13 | NOT_STARTED | - |
| B6R-14 | NOT_STARTED | - |

## 13. 다음에 해야 할 작업

다음 대상: `B6R-2 재실행`이며 B6R-3가 아니다.

필요 작업:

1. owner-authorized MI48 snapshot 또는 승인된 대체 snapshot을 read-only로 materialize한다.
2. B6R-1 새 revision에서 schema/frame/pixel/metadata accounting과 target checkout validator를 PASS시킨다.
3. subject/session/recording·label provenance를 확보한다.
4. tuning-naive independent holdout을 확보하거나 신규 acquisition plan을 승인한다.
5. 그 후에만 B6R-2 group split·contamination·seal을 재실행한다.

## 14. Rollback / 안전성

변경은 신규 retry evidence, 보고서, 인덱스, 해당 artifact용 LF 규칙뿐이다. runtime/model/raw dataset에는 영향이 없다. 필요하면 delivery commit 하나를 일반 `git revert`로 되돌릴 수 있다.

## 15. STOP

`DO NOT PROCEED WITHOUT NEW USER INSTRUCTION`

다음 Stage는 실행하지 않았다.
