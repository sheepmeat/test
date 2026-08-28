# SafeNest Thermal B6-R RC1 — Thermal-90 identity·다인 capture·label·holdout 보완 계획

문서 상태: **FROZEN PLAN / EXECUTION NOT STARTED**

비게이팅 package: `B6R-RC1`

작성일: `2026-08-27`

machine-readable contract: `config/thermal/b6r_rc1_thermal90_capture_remediation_contract.json`

## 1. 목적과 현재 판정

이 계획은 외부 `Desktop/sessions`의 `Thermal-90` 파일럿을 곧바로 `B6R-1` MI48 evidence나 `B6R-2` 학습/holdout으로 승격하지 않고, 그 전에 필요한 sensor identity, unit, orientation, FPS·packet quality, 다인 수집, label provenance, 독립 holdout 통제를 고정한다.

`B6R-RC1` 자체 판정은 **계획 동결 완료(`PASS_WITH_LIMITATIONS`)**다. 실제 identity 승인은 아직 `EVIDENCE_PENDING_OWNER_ACCEPTANCE`, capture 실행은 `NOT_STARTED`다. `Thermal-90`은 현재부터 MI48의 별칭이 아니라 **별도 target sensor 후보**로 관리한다.

## 2. 이번 단위의 경계

| 항목 | 이번 실행 |
|---|---|
| RC0 사실·수치 상속 | 수행 |
| identity 승인 절차·증거 목록 동결 | 수행 |
| 다인 capture·unit/orientation/FPS·label·holdout 계획 동결 | 수행 |
| 실제 장치 촬영·참가자 모집 | 미수행 |
| Thermal-90 identity 최종 승인 | 미수행 — 장치 증거와 owner decision 필요 |
| B6R-1/B6R-2 재실행 | 미수행 |
| model 학습·평가·runtime 변경 | 금지 |

기존 `S000` 5세션은 반복 열람된 `DEVICE_CONTRACT_PILOT`다. 이 자료는 decoder·packet failure·metadata gap 확인에는 사용할 수 있지만 `REAL_LOCKED_TEST`로 재분류하지 않는다.

## 3. Thermal-90 identity 승인 절차

### 3.1 기본 원칙

- 표시명 `Thermal-90`, `(62,80)`, `uint16`이 같다는 사실만으로 MI48 동등성을 주장하지 않는다.
- 우선 `DISTINCT_TARGET_SENSOR_CANDIDATE`로 등록한다.
- 최종 decision은 다음 셋 중 하나만 허용한다.
  - `APPROVED_AS_DISTINCT_B6R_TARGET`
  - `APPROVED_AS_DOCUMENTED_MI48_VARIANT`
  - `REJECTED_AS_B6R_TARGET`
- MI48 variant 승인은 제조사 문서의 part mapping, raw encoding/unit, hardware revision mapping과 owner의 명시적 동등성 승인이 모두 있어야 한다.

### 3.2 제출해야 할 identity evidence

1. 제조사·공급사, 상용 model/module part number, hardware revision
2. pseudonymous device ID, firmware version, collector version·Git commit
3. transport와 protocol, native width/height/dtype/byte order
4. 장치·모듈 표기 기록과 SHA-256, 제조사 또는 공급사 문서 reference
5. 대표 raw packet과 native decode 한 프레임의 byte-count·endianness 교차검증
6. owner decision record: 날짜, 승인 범위, 제한, 서명자 역할

위 evidence가 없으면 승인 상태는 계속 `EVIDENCE_PENDING_OWNER_ACCEPTANCE`다. 이 상태에서도 수집기 개선용 pilot은 가능하지만 모델 학습·locked holdout·MI48 claim은 불가하다.

## 4. unit 검증

현재 `raw_unit_claim=UNKNOWN_NOT_VERIFIED`를 유지한다. public SDT, 과거 MI48 계약, legacy code의 나눗셈 상수를 Thermal-90에 복사하지 않는다.

검증 record에는 reference device ID·교정 상태, reference 값과 단위, 같은 시각의 raw 분포, ambient context, 측정 시각, 불확도를 기록한다. 제조사 encoding 문서와 예상 사용 범위를 가로지르는 둘 이상의 reference condition을 교차 확인한다. 허용 오차는 측정 전에 owner가 별도 addendum으로 승인하며, 검증 전에는 Celsius 변환이나 calibrated temperature claim을 만들지 않는다.

실패하거나 문서와 실측이 충돌하면 raw uint16을 보존한 채 `UNIT_NOT_VERIFIED`로 중단한다. 모델 입력 변환을 추측하지 않는다.

## 5. orientation·mount 검증

좌·우·상·하의 알려진 위치에 안전한 thermal marker 또는 사람이 차례로 위치한 reference session을 원본 native frame으로 남긴다. 다음을 함께 고정한다.

- native row/column 축의 물리 의미
- 필요한 rotation degrees, horizontal/vertical flip
- mount height, pitch, yaw, sensor-to-scene distance
- 설치 reference record의 SHA-256

변환은 role-separated 다인 capture 전에 하나의 contract revision으로 동결한다. 화면을 보고 추정하거나 수집 후 세션마다 다른 rotate/flip을 적용하면 해당 세션을 승인하지 않는다.

## 6. FPS·packet quality 검증

설정 FPS와 실측 FPS를 분리한다. 모든 session은 가능한 device frame counter, device monotonic clock, host receive monotonic clock, timezone 포함 wall time을 보존한다. validator는 received/valid/invalid frame 수, effective FPS, inter-frame p50/p95/p99, counter gap·duplicate·reversal, partial/decode failure를 보고해야 한다.

초기 contract acceptance는 다음을 만족해야 한다.

- counter reversal `0`, duplicate `0`
- effective FPS의 configured FPS 대비 상대 오차 `≤ 10%`
- 설명되지 않은 counter gap, partial, decode failure `0`
- 실패 frame도 ledger에서 삭제하거나 번호를 다시 붙이지 않음

이 값은 safety 성능 기준이 아니라 깨끗한 acquisition session을 인정하기 위한 engineering gate다. 미달 session은 원본과 기록을 보존한 채 `CAPTURE_INVALID`로 제외한다.

## 7. 다인 capture wave

### Wave A — contract verification

기존 T-C0 operational floor를 상속해 독립 subject 최소 3명, subject당 최소 2 session, empty-room 최소 2 session을 수집한다. 이는 통계적 일반화 충분성을 뜻하지 않는다. 각 subject는 거리·시야 위치·방향·session·자연 배경 변화를 포함한다.

필수 scenario는 empty, standing, sitting, crouching, lying posture proxy, normal entry/exit, partial occlusion, warm object/background hard negative다. 위험한 자유 낙상은 하지 않는다. 모든 Wave A session 역할은 `DEVICE_CONTRACT_PILOT`이며 locked test가 아니다.

### Wave B — role-separated acquisition

Wave A validator PASS와 identity owner acceptance 후에만 시작한다. TRAIN 후보와 DEVELOPMENT의 정확한 subject 수는 Wave A의 결손·변동을 보고 owner가 addendum으로 승인한다. 최소 수를 성능 충분성으로 포장하지 않는다.

locked holdout은 protocol freeze 뒤 모집·촬영한 **새 subject 최소 2명**을 operational floor로 둔다. 이 수만으로 일반화나 좁은 confidence interval을 주장하지 않으며, support가 부족하면 최종 결과는 `INCONCLUSIVE`다. 같은 subject/session/event의 cross-role 배치는 금지하고 frame-random split은 사용하지 않는다.

## 8. label 계약

라벨은 모델 출력에서 만들지 않는다. 촬영 operator의 scenario 선언과 독립 reviewer의 확인을 모두 남기고 revision 이력을 보존한다.

- source posture: `EMPTY`, `STANDING`, `SITTING`, `CROUCHING`, `LYING`, `OTHER_CONTROLLED`, `UNKNOWN`
- `LYING`: `POSTURE_PROXY_NOT_TEMPORAL_FALL_GROUND_TRUTH`
- temporal event: 별도 안전 승인 후 `event_id`와 비중첩 range로 `PRE_EVENT → FALL_TRANSITION → POST_FALL_LYING → RECOVERY`
- 모호한 구간: 삭제하지 않고 provenance를 남기되 pure-class 평가에서 제외

실제 자유 낙상, 임상 낙상, 안전 판정 label은 이 계획의 범위가 아니다.

## 9. 독립 holdout 봉인

holdout roster와 protocol은 holdout 촬영 전에 preregister한다. holdout custodian은 model developer와 분리하고, 새 subject만 `REAL_LOCKED_TEST`로 배정한다. 기존 `S000`과 Wave A 참가자는 holdout이 될 수 없다.

manifest·raw checksum seal과 access log를 만들고 상태를 `UNTOUCHED`로 유지한다. train, preprocessing 선택, architecture 선택, threshold/calibration, INT8 representative data, debugging에는 접근하지 않는다. classifier와 temporal pipeline이 동결된 뒤 `B6R-11`에서 한 번만 연다. 결과를 보고 tuning하면 같은 holdout을 final로 재사용하지 않는다.

## 10. 필수 전달물

수집 책임자는 collection/session/frame/annotation manifests, native raw, decoded native, checksum, capture validator 결과 외에 다음 네 증거를 전달해야 한다.

1. `identity_evidence_registry.json`
2. `unit_verification_record.json`
3. `orientation_verification_record.json`
4. `holdout_preregistration_and_access_log`

portable artifact에는 절대 Windows 경로를 기록하지 않고 logical source ID와 collection-relative 또는 repository-relative path를 사용한다. raw payload는 이 저장소에 자동 commit하지 않는다.

## 11. exit criteria와 다음 단계

다음이 모두 증거로 확인되어야 `B6R-RC1` 보완 실행이 종료된다.

- identity owner decision 기록
- unit 검증 또는 명시적 target rejection
- orientation/mount 동결
- FPS·packet quality gate PASS
- Wave A 다인 accounting 완료
- label dual review·revision provenance PASS
- role-separated holdout preregistration·seal
- standalone capture validator PASS

그 뒤에도 바로 `B6R-2`나 training으로 가지 않는다. 승인된 새 capture를 대상으로 `B6R-1` 새 revision이 file/frame/schema/quality accounting을 수행하고, 그 결과가 usable일 때만 `B6R-2`를 재검토한다.

## 12. STOP 조건

Thermal-90의 근거 없는 MI48 재명명, unit/orientation 추측, frame-random split, subject role leakage, 기존 `S000`의 holdout 승격, `LYING`의 실제 낙상 승격, holdout tuning 접근, invalid session의 조용한 수리·삭제, 이 package에서의 model/runtime 변경 중 하나라도 발생하면 중단한다.

`STOP — 현재는 계획과 validator만 동결되었으며, 실제 identity 승인·수집·B6R-1은 새 evidence와 사용자 지시 후 실행한다.`
