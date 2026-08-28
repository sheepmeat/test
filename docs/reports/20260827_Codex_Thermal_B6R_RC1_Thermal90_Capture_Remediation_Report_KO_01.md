# SafeNest Thermal B6-R RC1 — Thermal-90 capture remediation 실행 보고서

## 1. 수행 단계

- 날짜: `2026-08-27`
- 브랜치: `feature/thermal-b6r-development`
- 실행 단위: `B6R-RC1 — Thermal-90 Identity and Capture Remediation Plan`
- 유형: 정식 B6R-0~14를 열지 않는 비게이팅 gate-remediation package
- 시작 HEAD: `7925ff2fcf4c11a354774a5f999a6085284aa924`
- 원격 동기화: `git fetch --prune`, `git pull --ff-only` 후 시작 branch와 origin이 동일함을 확인
- 사용자 승인 범위: Thermal-90 identity 승인 절차와 다인 capture·unit/orientation/FPS·label·holdout 보완 계획 작성·검증

이번 실행은 실제 촬영, 참가자 모집, sensor identity 최종 승인, B6R-1/2, model 학습, holdout 개방, runtime 또는 safety 변경을 수행하지 않았다.

## 2. 최종 판정

`PASS_WITH_LIMITATIONS`

- `PASS`: RC1 machine-readable contract, Korean field plan, fail-closed validator와 focused tests를 만들고 최종 검증을 통과했다.
- `LIMITATIONS`: identity approval은 `EVIDENCE_PENDING_OWNER_ACCEPTANCE`, capture는 `NOT_STARTED`다. 따라서 B6R-1은 `INCONCLUSIVE`, B6R-2는 `BLOCKED`, B6R-3~14는 `NOT_STARTED`를 유지한다.

## 3. 상속한 실제 evidence

RC0와 외부 `Desktop/sessions`를 read-only로 재대조했다.

| 항목 | 확인 상태 |
|---|---|
| sensor metadata | 5세션 모두 `Thermal-90`, vendor/revision `UNKNOWN` |
| native representation | `(62,80)`, `uint16`, raw/native/checksum 보존 |
| subject | 모두 `S000` |
| capture quality | 5세션 중 3세션 `CAPTURE_INVALID` |
| raw unit | `UNKNOWN_NOT_VERIFIED` / `NOT_VERIFIED` |
| orientation | `UNKNOWN_NOT_VERIFIED` |
| FPS | configured `7.0`, status `CONFIGURED_ONLY` |
| role | `DEVICE_CONTRACT_PILOT`, model-use promotion 근거 없음 |
| holdout | `NOT_LOCKED_TEST`; 기존 `S000`은 새 locked holdout으로 승격 금지 |

이 확인으로 “현재 실제 파일럿 capture는 있다”는 RC0 사실은 유지되지만, MI48 identity나 학습/holdout eligibility는 추가되지 않았다.

## 4. 핵심 결정

### 4.1 identity

`Thermal-90`을 `DISTINCT_TARGET_SENSOR_CANDIDATE`로 고정했다. 표시명과 frame geometry만으로 MI48 동등성을 주장하지 않는다. 제조사/part number/revision, 장치 표기 hash, raw packet↔native decode, firmware/collector provenance와 owner decision이 필요하다.

허용되는 최종 decision은 distinct B6R target 승인, 문서화된 MI48 variant 승인, target rejection 세 가지다. 현재는 절차만 승인·동결되었고 사실 승인은 대기 상태다.

### 4.2 unit/orientation/FPS

- unit: 제조사 encoding과 reference measurement를 교차검증하고 측정 전 owner tolerance addendum을 요구한다. SDT나 legacy 상수 복사는 금지한다.
- orientation: 알려진 좌·우·상·하 marker와 mount record로 row/column, rotate/flip, height/pitch/yaw/distance를 고정한다.
- FPS/packet: device/host clocks와 frame counter를 보존하고 effective FPS, inter-frame percentile, gap/duplicate/reversal/partial을 계수한다. acceptance session은 reversal/duplicate/unexplained gap `0`, configured 대비 FPS 상대오차 `≤10%`로 고정했다.

### 4.3 다인 capture

Wave A는 T-C0 operational floor를 상속해 독립 subject 최소 3명, subject당 최소 2 session, empty-room 최소 2 session을 요구한다. 이는 통계적 충분성 주장이 아니다. empty, static postures, entry/exit, occlusion, warm-object/background hard negative를 포함한다.

Wave B는 Wave A validation과 identity 승인 후에만 진행한다. train/development exact subject 수는 Wave A 결과 뒤 owner addendum으로 동결한다. locked holdout은 protocol freeze 후의 새 subject 최소 2명을 operational floor로 두되, 이 최소 수만으로 일반화 성능을 주장하지 않는다.

### 4.4 label/holdout

operator 선언과 독립 reviewer를 모두 요구하고 model output을 label source로 금지했다. `LYING`은 posture proxy일 뿐 temporal fall ground truth가 아니다. temporal transition은 별도 safety 승인, event ID와 PRE/TRANSITION/POST/RECOVERY range가 있어야 한다.

holdout은 subject 단위, 새 참가자, custodian 분리, preregistration, checksum seal, access log, `UNTOUCHED`, B6R-11 one-time access로 고정했다. tuning 뒤 같은 holdout 재사용은 금지한다.

## 5. 변경 파일

- `config/thermal/b6r_rc1_thermal90_capture_remediation_contract.json`
- `scripts/validate_thermal_b6r_rc1.py`
- `tests/test_validate_thermal_b6r_rc1.py`
- `datasets/thermal/manifests/B6R-RC1_thermal90_capture_remediation/README.md`
- `datasets/thermal/manifests/B6R-RC1_thermal90_capture_remediation/validation_result.json`
- `datasets/thermal/manifests/B6R-RC1_thermal90_capture_remediation/checksums.sha256`
- `docs/thermal/20260827_SafeNest_Thermal_B6R_RC1_Thermal90_Capture_Remediation_Plan_KO_01.md`
- 이 보고서, B6R roadmap/index, `docs/README.md`

raw capture, public SDT payload, model, runtime selector, legacy manifest, locked public test는 수정하지 않았다.

## 6. 검증

### 최종 검증 결과

- Python compile: `scripts/validate_thermal_b6r_rc1.py`, `tests/test_validate_thermal_b6r_rc1.py` 통과
- focused unittest: `6/6 PASS`
  - frozen contract PASS
  - MI48 self-promotion 차단
  - 기존 `S000` holdout 승격 차단
  - frame-random split 차단
  - absolute path leak 차단
  - CRLF/LF checkout 간 contract identity 동일성
- standalone validator: `PASS`, error `0`
- contract SHA-256: `ec7d58ca6615be535cdd98b49ccf627310d7d0c4c7689da93b7b792b1770a6fe`
- RC1 핵심 contract/validator/test/plan/evidence 6개 checksum registry 생성. text hash는 checkout CRLF 차이로 identity가 깨지지 않도록 UTF-8 CRLF→LF 정규화 규칙을 명시했다. raw sensor bytes에는 이 정규화를 적용하지 않는다.

첫 테스트 실행에서는 Windows 임시 디렉터리 cleanup 순서 때문에 변조 테스트 4개가 teardown error를 냈다. fixture cleanup을 수정하고 cross-platform line-ending 회귀를 추가한 뒤 최종 6개를 재실행해 모두 통과했다. 계약 validator는 최초와 최종 실행 모두 error `0`이었다.

## 7. Roadmap / state changes

- `B6R-RC1`을 비게이팅 remediation package로 추가했다.
- 이전 상태 `DATA_EVIDENCE_TRIAGE_WAITING_FOR_USER_INSTRUCTION`은 사용자 승인으로 종료했다.
- 새 현재 상태는 `B6R_RC1_PLAN_COMPLETE_IDENTITY_EVIDENCE_AND_CAPTURE_EXECUTION_PENDING`이다.
- mainline 판정은 변경하지 않았다: B6R-0 `FAIL`, B6R-1 `INCONCLUSIVE`, B6R-2 `BLOCKED`, B6R-3~14 `NOT_STARTED`.
- RC0/P0/P1/P2 판정과 claim boundary도 변경하지 않았다.

## 8. 남은 blocker

1. vendor/model/module part number, revision, device marking, firmware/collector provenance가 없다.
2. Thermal-90 raw unit과 native byte-order의 장치 근거가 없다.
3. orientation/mount reference가 없다.
4. configured 7 FPS를 만족하는 clean counter/timing evidence가 없다.
5. independent subject와 dual-reviewed labels가 없다.
6. role-separated new-subject holdout preregistration·seal이 없다.
7. B5 exact assets, LiteRT/Pi evidence, authoritative MI48 lineage 등 기존 B6R-0/1 blocker도 남아 있다.

## 9. 다음 실행 단위

현재 바로 수행할 다음 정식 B6R stage는 없다. 현장 측에서는 RC1의 **identity evidence packet + Wave A capture**를 준비해야 한다. 해당 evidence가 전달되고 사용자 실행 지시가 오면 다음 저장소 단위는 `B6R-RC1 CAPTURE EVIDENCE REVIEW`다.

RC1 exit criteria가 모두 충족된 뒤의 첫 정식 본선 stage는 `B6R-1` 새 revision이다. `B6R-2`, training, locked holdout 평가로 건너뛰지 않는다.

## 10. STOP

`DO NOT PROCEED WITHOUT NEW USER INSTRUCTION AND NEW DEVICE/CAPTURE EVIDENCE`

이번 실행은 RC1 계획·검증 단위에서 종료한다.
