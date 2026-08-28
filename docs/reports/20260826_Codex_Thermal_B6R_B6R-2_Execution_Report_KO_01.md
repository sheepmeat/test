# SafeNest Thermal B6-R Stage 수행 보고서

## 1. 작업 개요

- 날짜: `2026-08-26`
- Stage: `B6R-2 — Session / Label / Split / Holdout Contract`
- 작업 브랜치: `feature/thermal-b6r-development`
- 시작 HEAD: `8acf7dac6a353fc9830e220747c8cdb88748c323`
- 작업 목적: 권위 있는 MI48 근거에서 누수 없는 group split과 독립 holdout 계약을 동결할 수 있는지 판정
- 결과 상태: `BLOCKED`
- 작업 전 dirty worktree: `NO`

## 2. 이번 Stage의 목표

로드맵의 핵심 질문은 subject/session/recording identity와 label provenance를 신뢰할 수 있는지, 그리고 adjacent-frame/random split 없이 group-isolated TRAIN/DEVELOPMENT/independent holdout 역할을 만들 수 있는지다.

### 실행 계약

- 선행 조건: B6R-1의 전체 accounting, 식별된 MI48 schema family, frame 및 metadata evidence.
- 허용 입력: B6R-1 machine-readable evidence, 읽기 전용 T-A5 역사 증거, 현재 source availability/file-stat 확인.
- 금지 입력: 미확인 archive의 MI48 승격, synthetic 예제의 물리 데이터 대체, `REAL_EVAL_DEVELOPMENT`의 독립 holdout 재명명, independent holdout 접근.
- 필요한 구현: dataset contract, provenance map, group split, contamination report, holdout seal. 단, entry gate 통과 후에만 허용한다.
- 필요한 분석: group identity와 label 신뢰도, exact/near-duplicate contamination 가능성, 모든 sample 역할 accounting.
- 필요한 artifact: B6R-2 계약 package 또는, 선행 조건 불충족 시 blocker evidence package와 보고서.
- 필요한 테스트: JSON/schema/checksum 검증, predecessor validator, group isolation, contamination, holdout seal audit. 후자의 세 항목은 입력 부재 시 `NOT TESTED`로 기록한다.
- 완료 gate: 한 group이 정확히 한 role에 속하고, contamination audit와 holdout seal이 PASS해야 한다.
- 다음 Stage 진입 조건: B6R-2 gate PASS 후에만 B6R-3 수행 가능.

## 3. 작업 전 상태

### 기존 B1~B5 역사 결과

| 역사 단계 | 현재 evidence | B6-R에서의 의미 |
|---|---|---|
| T-B1 | P1 TRAIN-global z-score winner 기록, checkpoint bytes는 외부 | read-only lineage; 현재 checkpoint 사용 불가 |
| T-B2 | `SMALL_CNN_BASELINE_V1` 계열 선택 기록 | architecture identity 근거만 사용 |
| T-B3 | multi-seed 완료 제한사항 기록 | historical reproducibility evidence |
| T-B4 | FLOAT Keras→FP32→FULL INT8 identity와 hash 기록, binary는 외부 | binary materialization을 보증하지 않음 |
| T-B5 | offline INT8 candidate lock with limitations | Pi/MI48/독립 holdout 검증이 아님 |

B6R-0은 B5 FLOAT/FP32/INT8 bytes가 현재 worktree에 materialize되지 않았고 TensorFlow/LiteRT 및 Raspberry Pi evidence가 없어 `FAIL`이다. 현재 runtime은 `models/model_manifest.json`이 가리키는 legacy `thermal_fall_int8 v0.1.0`이며 B5 계보와 model hash/preprocessing이 다르다. B6-R selector나 robust-relative preprocessing은 활성 상태가 아니다.

### B6R-1과 dataset 상태

- B6R-1 판정: `INCONCLUSIVE`.
- 권위 source `RP-X0_O2.6_MI48_FIELD_SNAPSHOT`: 현재 mount되지 않음.
- workspace 후보 `열화상_dataset`: 파일 6개이며 MI48 identity가 unresolved.
- B6R-1 accounting: `total 6 = readable MI48 0 + corrupt 0 + explicitly excluded 6`.
- 식별된 MI48 frame: `0`.
- `subject_id`, `session_id`, `recording_id`: `ABSENT`.
- label: label-like field name만 관찰되었고 값 의미/provenance는 미확정.
- split role: `AMBIGUOUS`.
- 역사적 T-A5의 pristine locked test: `NO`; `REAL_EVAL_DEVELOPMENT`는 개발 접근 이력이 있어 독립 holdout으로 사용할 수 없음.

### 환경과 dependency

- OS: Windows 11 AMD64.
- Python: 앱 번들 CPython `3.12.13`.
- NumPy: `2.3.5`.
- pytest: 설치되지 않음.
- file-system drive: `C`, `Temp`; `SafeNestssd` 없음.
- 현재 모델 binary: legacy thermal INT8 1개만 tracked.

## 4. 수행한 작업

1. 저장소·원격·브랜치·dirty 상태를 확인하고 `origin/feature/thermal-b6r-development`와 fast-forward 동기화했다.
2. `docs/README.md`와 B6-R 로드맵을 처음부터 끝까지 읽고 B6R-0/B6R-1 보고서, manifest, B1~B5, runtime, model, preprocessing, split/holdout evidence를 조사했다.
3. 현재 파일시스템에 새 B5 artifact나 권위 MI48 snapshot이 생겼는지 확인했다.
4. workspace 후보 6개의 파일명, size, mtime이 B6R-1 registry와 모두 일치하며 새 파일이 없음을 확인했다. 원본 내용은 수정하지 않았다.
5. B6R-1 profiler focused synthetic harness 4개를 실행하고 source/test compile을 확인했다.
6. B6R-1 standalone validator를 재실행했다. dataset 판정은 여전히 `INCONCLUSIVE`이고 현재 checkout의 generated evidence 10개에 `CHECKSUM_MISMATCH`가 발생했다. 이 B6R-2 stage에서 역사적 B6R-1 파일을 수정하지 않았다.
7. B6R-2 entry gate 실패를 machine-readable하게 기록했다. 실제 dataset contract, split, contamination metric, holdout은 생성하거나 열지 않았다.

## 5. 변경된 파일

- `datasets/thermal/manifests/B6R-2_dataset_contract/input_evidence_registry.json` — 사용한 선행 evidence path·size·worktree SHA-256과 접근 경계 기록.
- `datasets/thermal/manifests/B6R-2_dataset_contract/prerequisite_assessment.json` — 실행 계약, current evidence, entry gate, blocker, unblock 조건 기록.
- `datasets/thermal/manifests/B6R-2_dataset_contract/validation_result.json` — 실제 검증 결과와 허용/금지 주장을 기록.
- `datasets/thermal/manifests/B6R-2_dataset_contract/checksums.sha256` — 신규 machine-readable artifact checksum registry.
- `.gitattributes` — B6R-2 artifact 디렉터리만 LF checkout으로 고정하여 SHA-256 재현성을 보호.
- `docs/reports/20260826_Codex_Thermal_B6R_B6R-2_Execution_Report_KO_01.md` — 본 보고서.
- `docs/thermal/B6R_DEVELOPMENT_INDEX.md` — B6R-2 상태와 blocker 탐색 경로 갱신.

## 6. 실행한 명령

민감정보를 제외한 핵심 command는 다음과 같다.

1. `git rev-parse --show-toplevel`, `git remote -v`, `git status --short --branch`, `git branch --show-current`, `git log -5 --oneline --decorate` — 저장소/브랜치 확인, exit `0`.
2. `git fetch origin --prune` — 원격 갱신, exit `0`.
3. `git pull --ff-only origin feature/thermal-b6r-development` — `Already up to date`, exit `0`.
4. 앱 번들 Python `--version` 및 `-c "import numpy, platform; ..."` — Python/NumPy/platform 확인, exit `0`.
5. 앱 번들 Python `-m pytest tests/test_thermal_b6r1_mi48_inventory.py -q` — pytest 부재, exit `1`.
6. 앱 번들 Python `-m py_compile scripts/profile_thermal_b6r1_mi48.py tests/test_thermal_b6r1_mi48_inventory.py` — exit `0`.
7. 앱 번들 Python direct synthetic harness — `4 PASS`, exit `0`.
8. 앱 번들 Python `scripts/profile_thermal_b6r1_mi48.py validate datasets/thermal/manifests/B6R-1_mi48_inventory` — 10 checksum mismatch, exit `1`.
9. PowerShell read-only source stat comparison — 6/6 size·mtime match, exit `0`.

## 7. 검증 및 테스트

| Test | Expected | Actual | Result |
|---|---|---|---|
| Git branch/worktree | 지정 브랜치, clean | 지정 브랜치, clean | PASS |
| B6R-1 accounting invariant | 6 = 0 + 0 + 6 | 일치 | PASS |
| Candidate source stat comparison | 6개 size/mtime 유지 | 6/6 일치, 신규 파일 0 | PASS |
| Python compile | syntax valid | exit 0 | PASS |
| B6R-1 synthetic focused harness | 4 tests pass | 4 PASS | PASS |
| pytest runner | focused suite 실행 | `No module named pytest` | NOT TESTED |
| B6R-1 standalone artifact validator | checksum/accounting PASS | checksum mismatch 10개 | FAIL |
| B6R-2 group isolation | 실제 group evidence 필요 | group identity 없음 | NOT TESTED / BLOCKED |
| B6R-2 contamination audit | split 및 sample ledger 필요 | eligible MI48 sample 0 | NOT TESTED / BLOCKED |
| B6R-2 holdout seal | 독립 holdout 필요 | 독립 holdout 없음, 접근 0 | NOT TESTED / BLOCKED |

## 8. 주요 결과

- 선행 B6R-1 data gate가 충족되지 않았다.
- 식별 가능한 MI48 frame과 group metadata가 없으므로 subject-level 또는 session-level split을 정당화할 수 없다.
- 역사적 `REAL_EVAL_DEVELOPMENT`는 이미 개발에 사용되어 independent holdout이 아니다.
- B6R-1 profiler 코드의 synthetic wiring은 4개 test에서 동작하지만 physical MI48 evidence를 제공하지 않는다.
- 현재 checkout에서 B6R-1 checksum validator가 FAIL이므로 선행 evidence package의 standalone 재현 gate도 복구가 필요하다.
- holdout은 열지 않았고, dataset/split/label을 추측하지 않았다.

## 9. 생성 Artifact

| Artifact | SHA-256 | Size | Identity / Source |
|---|---|---:|---|
| `input_evidence_registry.json` | `eb9fe5d4c636667c23eb9ab472161e18596a9bdff75d6f3f9292c54da3c6747e` | 2,184 bytes | B6R-2 prerequisite blocker / read-only repo evidence |
| `prerequisite_assessment.json` | `74086a46db2f42ac673b6ca96edb04cc47c6919f030022efbe5386753c172bae` | 4,116 bytes | B6R-2 entry gate decision |
| `validation_result.json` | `910e71d221f5fd6c9d986214d2909fc2474b30dba17611303161a33adc579a0e` | 1,514 bytes | B6R-2 validation result |
| `checksums.sha256` | 별도 self-hash 미기록 | 3-entry registry | 위 3개 artifact checksum |

원시 snapshot, checkpoint, model binary, split manifest, holdout payload는 생성·수정·추가하지 않았다.

## 10. 문제점 / 제한 사항

- 권위 MI48 snapshot과 B5 binary/checkpoint가 현재 환경에 없다.
- subject/session/recording identity와 label provenance가 없다.
- 독립 holdout이 없다.
- B6R-1 standalone validator가 현재 checkout에서 checksum mismatch 10개로 실패한다. 원인 수정은 B6R-2 범위를 벗어나므로 수행하지 않았다.
- pytest가 없어 pytest runner는 사용하지 못했고, 동일 test 함수를 임시 디렉터리에서 direct harness로 실행했다.
- physical MI48, Raspberry Pi, latency, accuracy, recall, F1, 실제 낙상 성능에 관한 주장은 할 수 없다.

## 11. Stage Gate 판정

최종 판정: `BLOCKED`

| Gate 기준 | Evidence | 판정 |
|---|---|---|
| B6R-1 full accounting 및 usable schema | file accounting은 있으나 MI48 readable 0, frame 0 | FAIL |
| subject/session 또는 정당화된 session grouping | 필드 모두 ABSENT | FAIL |
| label provenance | field name clue만 존재 | FAIL |
| group isolation | split 미생성 | BLOCKED |
| contamination audit | sample ledger 없음 | BLOCKED |
| independent holdout seal | pristine holdout 없음, 접근하지 않음 | FAIL / SAFE STOP |
| predecessor standalone validation | checksum mismatch 10개 | FAIL |

B6R-3 진입은 허용되지 않는다.

## 12. 전체 B6-R 진행 상황

| Stage | 상태 | 핵심 결과 |
|---|---|---|
| B6R-0 | DONE_FAIL | B5 bytes/runtime/Pi capability 부재를 확인 |
| B6R-1 | DONE_INCONCLUSIVE | 권위 MI48 없음, eligible frame 0; validator checksum 복구 필요 |
| B6R-2 | BLOCKED | group/label/holdout evidence 부재로 계약 생성 중단 |
| B6R-3 | NOT_STARTED | B6R-2 gate 필요 |
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

다음 대상: `B6R-2 재실행` (B6R-3가 아님)

필요 작업:

1. owner-authorized `RP-X0_O2.6_MI48_FIELD_SNAPSHOT` 또는 승인된 대체 snapshot을 read-only로 materialize한다.
2. B6R-1을 새 revision으로 재실행하여 schema/frame/pixel/metadata 전체 accounting을 만들고 checksum validator를 PASS시킨다.
3. subject/session/recording·label provenance를 확보하거나 신규 acquisition plan을 승인한다.
4. tuning에 사용되지 않은 independent holdout을 확보한 후에만 B6R-2 group split·contamination·seal을 수행한다.

선행 조건:

- B6R-1 usable 또는 정당화된 partially usable 판정.
- 선행 artifact standalone validation PASS.
- trustworthy group 및 label provenance.
- 독립 holdout availability와 접근 정책.

필요 리소스:

- read-only MI48 payload.
- source/session/label manifest.
- 새 독립 holdout 또는 승인된 acquisition 결과.

다음 Stage는 실행하지 않았다.

## 14. Rollback / 안전성

이번 변경은 신규 B6R-2 blocker manifest 디렉터리, 해당 디렉터리 전용 LF 규칙, 본 보고서, 개발 인덱스 갱신뿐이다. runtime, model manifest, preprocessing, sensor subsystem, 원시 데이터, B1~B5 artifact를 변경하지 않았다. 되돌릴 때는 이번 commit만 일반적인 revert로 되돌릴 수 있으며 model/runtime 동작에는 영향이 없다.

`DO NOT PROCEED WITHOUT NEW USER INSTRUCTION`
