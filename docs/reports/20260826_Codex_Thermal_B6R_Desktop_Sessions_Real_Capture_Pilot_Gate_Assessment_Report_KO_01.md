# SafeNest Thermal B6-R Desktop `sessions` 실제 센서 파일럿 감사 및 본선 gate 영향 보고서

## 1. 작업 개요

- 날짜: `2026-08-26`
- 비게이팅 evidence package: `B6R-RC0 — Real-Capture Pilot Evidence Review`
- 브랜치: `feature/thermal-b6r-development`
- 외부 원본: `Desktop/sessions/` (원본은 저장소에 복사하지 않음)
- 목적: 실제 센서 수집 폴더가 B6R 본선과 B6R-P public 보조 흐름의 어떤 조건을 충족하는지 read-only로 판단
- 최종 상태: `INCONCLUSIVE / NON-GATING`
- 이번 보완: 현재 작업 PC의 `sessions`·`열화상_dataset`·P0 materialized payload 실제 위치와 source identity를 문서화
- 변경 범위: 원본 센서 파일과 runtime/model을 수정하지 않았고, 저장소에는 이 보고서와 roadmap/index 문서만 반영

이 package는 새로운 B6R 본선 stage를 통과시키는 실행이 아니다. 외부에서 전달된 실제 수집 기록을 다음 에이전트가 잘못 학습·holdout·physical 증거로 승격하지 않도록 현재 gate와 재개 조건을 기록하는 목적이다.

## 2. 결론 요약

`Desktop/sessions`는 실제 센서 통신과 데이터 보존이 이루어졌다는 유용한 파일럿 증거다. 그러나 이 폴더가 존재한다는 사실만으로 B6R 본선이 열리지는 않는다.

현재 판정은 다음과 같다.

| 구분 | 판정 | 의미 |
|---|---|---|
| 실제 capture 파일 존재 | `PARTIAL PASS` | raw UDP 조각, 재조립 frame, native decode, annotation, checksum이 보존됨 |
| capture 품질 | `INCONCLUSIVE` | 5개 세션 중 3개가 packet/counter gap 때문에 `CAPTURE_INVALID`; 나머지도 제한사항 있음 |
| B6R MI48 identity | `NOT ESTABLISHED` | metadata의 sensor model은 `Thermal-90`; 권위 MI48 snapshot과 동일하다는 provenance가 없음 |
| B6R-1 | `INCONCLUSIVE` 유지 | 이 자료로 real-capture pilot inventory는 가능하지만 MI48 gate를 통과시키지 않음 |
| B6R-2 | `BLOCKED` 유지 | 모든 세션이 subject `S000`이고 locked independent holdout이 없음 |
| B6R-3~14 | `NOT_STARTED` 유지 | 위 선행 gate가 열리지 않음 |
| B6R-P0~P2 | 기존 상태 유지 | public SDT 보조 흐름이며 이 실제 capture 폴더와 별도임 |

따라서 “실제 데이터가 전혀 없다”는 blocker는 “실제 파일럿 데이터는 있으나 B6R 권위 데이터로 승인할 증거가 부족하다”로 정교화된다. 이 자료를 곧바로 학습 데이터나 final holdout으로 사용하는 것은 허용하지 않는다.

## 3. 원본 inventory

### 3.1 보존된 파일 구조

- 세션 디렉터리: `session_S000_004`, `session_S000_011`, `session_S000_012`, `session_S000_013`, `session_S000_014`
- 각 세션: `raw/`, `raw_chunks/`, `decoded_native/`, `session.json`, `frames.jsonl`, `annotations.jsonl`, `checksums.sha256`
- 외부 root의 validation JSON 5개와 `pilot_review_session_S000_004_KO.md`도 확인
- 전체 파일 수: `7,428`
- `frames.jsonl` 합계: `3,784` records
- raw binary: `7,402`개, 약 `24.7 MB`
- validation 기준 유효 frame: 약 `820`개

### 3.2 센서·transport metadata

| 항목 | 확인값 |
|---|---|
| schema | `safenest.thermal.real_capture.session.v1` |
| sensor model | `Thermal-90` |
| native geometry | `62×80` |
| native dtype | `uint16` |
| raw encoding | `LITTLE_ENDIAN_UINT16_WORDS_5040` |
| transport | `XIAO_ESP32C6_TO_RASPBERRY_PI_UDP` |
| protocol | `THERMAL_TEST_UDP_RAW_V1` |
| raw preservation | full-frame raw 및 raw UDP chunks 보존 |
| checksum | 세션별 checksum 파일 존재; validation 결과 checksum `PASS` |
| collection | `collection_20260816_pilot01` |
| subject | 모든 세션 `S000` |

### 3.3 아직 검증되지 않은 metadata

`session.json`은 다음을 아직 확정하지 않는다.

- `raw_unit_claim`: `UNKNOWN_NOT_VERIFIED`
- `unit_verification_status`: `NOT_VERIFIED`
- `orientation`: `UNKNOWN_NOT_VERIFIED`
- `verified_fps_status`: `CONFIGURED_ONLY` (설정값은 7 FPS)
- 센서 vendor/hardware revision, mount angle/height/distance
- ambient temperature, background variation, occlusion
- device timestamp 및 device monotonic timestamp

따라서 `(62,80)`이라는 숫자가 같다는 사실만으로 MI48과 같은 센서 입력 의미라고 해석할 수 없다.

## 4. 세션별 validation 결과

| Session | 캡처 라벨 | frame records | valid | invalid | capture status | 핵심 문제 |
|---|---|---:|---:|---:|---|---|
| `S000_004` | `EMPTY` | 130 | 129 | 1 | `CAPTURE_STRUCTURE_VALID_WITH_LIMITATIONS` | partial 1개, effective FPS 약 4.3173, 2초 이상 timing gap 4회, unit/orientation 미검증 |
| `S000_011` | `EMPTY` | 810 | 171 | 639 | `CAPTURE_INVALID` | packet/counter gap 및 duplicate/reversal, 대부분 제외 |
| `S000_012` | `STANDING` | 1,882 | 173 | 1,709 | `CAPTURE_INVALID` | packet/counter gap, 대부분 제외 |
| `S000_013` | `SITTING` | 175 | 174 | 1 | `CAPTURE_STRUCTURE_VALID_WITH_LIMITATIONS` | partial 1개, effective FPS 약 5.7792, unit/orientation 미검증 |
| `S000_014` | `LYING` | 787 | 173 | 614 | `CAPTURE_INVALID` | packet/counter gap, 대부분 제외 |

모든 validation JSON의 공통 결과는 다음과 같다.

- `raw_integrity_status`: `PASS_WITH_LIMITATIONS`
- `temporal_provenance_status`: `TEMPORAL_ORDER_ONLY`
- `model_use_eligibility`: `NOT_AUTHORIZED_BY_CAPTURE_VALIDATOR`
- `role_governance.role`: `DEVICE_CONTRACT_PILOT`
- `locked_test_status`: `NOT_LOCKED_TEST`
- `split_frozen_at`: `null`

주석은 운영자가 정적으로 선언한 `EMPTY`, `STANDING`, `SITTING`, `LYING` 자세 proxy다. 독립적인 ground truth review가 아니며, fall event ID나 temporal phase range가 없다. `fall_like_capture_authorized`도 `false`이고 `NO_FREE_FALL_CAPTURE`로 기록되어 있다.

## 5. B6R gate와의 대조

| B6R 요구사항 | `sessions`가 제공하는 것 | 현재 판단 |
|---|---|---|
| 권위 있는 `RP-X0_O2.6_MI48_FIELD_SNAPSHOT` | `Thermal-90` 파일럿 capture | MI48 identity 불충분 |
| read-only raw inventory | raw/chunks/native/checksum/metadata | pilot inventory 근거로 유용 |
| schema·dtype·shape | `uint16`, `62×80`, little-endian raw encoding | 구조는 확인되지만 unit/orientation은 미검증 |
| 품질 분포 | valid/invalid와 packet gap이 계수됨 | 3/5 세션 invalid, 재수집 필요 |
| subject-level split | 모든 데이터가 `S000` | subject generalization 불가 |
| 독립 holdout | locked test 없음, split 미동결 | B6R-2 진입 불가 |
| 학습용 label | 정적 operator-declared posture | 최종 평가·낙상 사건 근거 아님 |
| temporal stabilization 근거 | host receive 순서만 존재 | verified device time/event range 없음 |
| physical MI48 E2E | UDP capture 기록만 있음 | Pi/runtime/risk E2E 증거 아님 |

이 표의 의미는 “파일이 나쁘다”가 아니라 “파일의 역할이 파일럿 증거로 제한된다”는 것이다. 특히 validation이 성공한 `S000_004`와 `S000_013`도 모델 학습 또는 locked test 사용 승인을 받은 것이 아니다.

## 6. P단계와의 관계

| 흐름 | 데이터 | 현재 역할 |
|---|---|---|
| B6R-P0~P2 | public SDT 48,000 frames 및 그 파생 model/TFLite | public-only offline/shadow 후보; MI48/physical 대체 불가 |
| Desktop `sessions` | Thermal-90 실제 UDP capture pilot | capture contract·decoder·품질 감사 근거; 학습·holdout 승격 전 상태 |
| B6R 본선 | 권위 MI48 + group split + Pi/physical evidence | 최종 classifier 및 candidate lock 경로 |

P2의 FP32 TFLite parity 성공은 export 기술 위험을 줄였지만, `sessions`의 센서 identity나 B6R 본선 gate를 바꾸지 않는다. 반대로 `sessions`가 생겼다고 public P2 model을 MI48 model로 재명명할 수도 없다.

## 7. 다음 에이전트의 stage 결정 규칙

### 7.1 현재 즉시 실행할 수 있는 것

이 보고서의 `B6R-RC0` read-only assessment는 완료되었다. 다음 에이전트가 같은 폴더를 보더라도 우선 다음 사실을 상속해야 한다.

1. `B6R-2` split/holdout 계약이나 학습을 시작하지 않는다.
2. `sessions`의 frame을 P1/P2 model metric, final holdout, 실제 낙상 성능에 사용하지 않는다.
3. 필요하면 별도의 **capture-contract remediation/acquisition plan**만 작성한다. 그 plan은 stage 실행이 아니라 부족한 센서·subject·label·holdout을 채우기 위한 승인 요청이다.

### 7.2 본선으로 재개하는 조건

다음 중 하나가 먼저 충족되어야 한다.

- **MI48 경로:** 권위 MI48 snapshot의 read-only 경로, schema, provenance가 확보되면 `B6R-1 — MI48 Snapshot Inventory & Abnormal-Pixel Profiler`를 새 revision으로 실행한다.
- **실제 capture 경로:** Thermal-90을 B6R 센서로 사용할 수 있다는 owner 승인과 sensor identity mapping이 먼저 확보되고, 단위·방향·FPS·장착·환경·packet quality를 보완한 다인 세션을 새로 수집한다. 그 뒤 B6R-1 inventory와 B6R-2 contract를 다시 판정한다.

어느 경로든 `B6R-2`로 넘어가려면 여러 subject 또는 정당화된 session-level isolation, 독립 holdout, label provenance, near-duplicate/adjacent-frame contamination 검사가 모두 필요하다.

### 7.3 이후의 정식 순서

```text
권위 MI48 또는 승인된 real-capture dataset
→ B6R-1 inventory/profile
→ B6R-2 session/label/split/holdout
→ B6R-3~B6R-6 preprocessing·training·development freeze
→ B6R-7~B6R-10 FP32/Pi/temporal/runtime
→ B6R-11~B6R-14 independent holdout·safety·physical E2E·candidate lock
```

데이터가 보완되기 전에는 B6R-3 이후 stage나 B6R-P3를 자동 실행하지 않는다.

## 8. 주장 가능한 범위와 금지 범위

### 주장 가능한 범위

- 실제 Thermal-90 UDP capture가 존재한다.
- raw packet/chunk와 native frame 보존 구조, checksum, session/annotation schema를 점검할 수 있다.
- 일부 세션의 packet loss와 timing limitation을 재현·분류할 수 있다.
- 향후 capture-contract 보완과 재수집의 구체적인 blocker가 드러났다.

### 주장할 수 없는 범위

- MI48과 동일한 센서 domain 또는 실제 MI48 성능
- 여러 사람에 대한 일반화 성능
- 실제 낙상 검출 또는 safety decision
- 독립 holdout 성능, locked test 성능
- Raspberry Pi latency/memory/장시간 안정성
- B6R 본선 candidate lock 또는 production default 전환

## 9. Evidence와 재현 경로

- 외부 원본 logical root: `Desktop/sessions/`
- 대표 validation: `Desktop/sessions/validation_session_S000_004.json`
- pilot review: `Desktop/sessions/pilot_review_session_S000_004_KO.md`
- 세션별 validation JSON에는 checksum, frame validity, raw integrity, temporal provenance, model-use eligibility가 기록되어 있다.
- 이 보고서 작성에서는 외부 원본을 저장소로 복사하거나 변경하지 않았다.

## 10. 현재 작업 PC 경로 registry

아래 절대 경로는 다음 에이전트가 현재 작업 PC에서 파일을 찾기 위한 **사람용 참고 정보**다. portable contract·manifest에는 절대 경로를 저장하지 않고, 아래의 저장소 상대 경로와 logical source ID를 계속 사용한다.

| 역할 | 현재 PC에서 확인한 위치 | 상태·용도 |
|---|---|---|
| 실제 센서 capture | `C:\Users\KIMTAEGYUN\Desktop\sessions` | 5개 `Thermal-90` pilot session, raw/native/annotation/checksum/validation. 학습·final holdout용 아님 |
| public SDT 원본 archive | `C:\Users\KIMTAEGYUN\Documents\ChatGPT\Thermal_AI\열화상_dataset` | `test.zip`, `train.zip.001~.004`, `validation.zip` 6개. P0 contract의 size·SHA-256과 `6/6` 일치 |
| 현재 B6R 저장소 root | `C:\Users\KIM TAEGYUN\Documents\ChatGPT\Thermal_AI\test` | active Git checkout, `feature/thermal-b6r-development` |
| P0 파생 local payload | `<B6R 저장소 root>\datasets\thermal\materialized\B6R-P0_public_sdt_v1` | 48,000개 `(62,80,1)` float32 배열. `.gitignore` 대상 local-only |
| P0 tracked evidence | `<B6R 저장소 root>\datasets\thermal\manifests\B6R-P0_public_sdt_materialization` | contract snapshot, source immutability, split/provenance/checksum/validation evidence |
| P0 contract | `<B6R 저장소 root>\config\thermal\b6r_p0_public_sdt_contract.json` | source logical ID `WORKSPACE_THERMAL_DATASET_ARCHIVES`, archive names·hash·split·claim boundary |

현재 Codex 환경에서는 사용자 profile 표기가 `KIMTAEGYUN`과 `KIM TAEGYUN` 두 형태로 노출된다. 위 source/capture 경로의 space 표기 variant도 `Test-Path`로 확인되므로, 다음 agent는 문자열을 추측해 바꾸지 말고 현재 process에서 존재하는 경로를 사용한다.

### 10.1 `열화상_dataset` source 상세

실제 source directory에는 다음 6개 파일이 있고 총 크기는 `19,223,751,874 bytes`다.

| 파일 | 크기(bytes) | P0 source registry SHA-256 일치 |
|---|---:|---|
| `test.zip` | 1,740,348,425 | `PASS` |
| `train.zip.001` | 4,194,304,000 | `PASS` |
| `train.zip.002` | 4,194,304,000 | `PASS` |
| `train.zip.003` | 4,194,304,000 | `PASS` |
| `train.zip.004` | 1,408,015,891 | `PASS` |
| `validation.zip` | 3,492,473,558 | `PASS` |

이 폴더는 **public SDT source**이지 MI48 field snapshot이나 실제 Thermal-90 capture가 아니다. P0는 이를 read-only stream으로 처리해 TRAIN `32,000`, DEVELOPMENT `8,000`, LOCKED_PUBLIC_TEST `8,000`을 만들었고, P1/P2는 그중 TRAIN/DEVELOPMENT와 derived artifact를 사용했다. `LOCKED_PUBLIC_TEST`는 P2에서 열지 않았다.

다음 에이전트는 `열화상_dataset`을 MI48로 재명명하거나 `sessions`와 합치지 않는다. source path가 보이지 않는 환경에서는 경로를 추측하지 말고 `B6R-P0` contract의 archive identity와 `Test-Path`/checksum을 먼저 확인한다.

## 11. Exit Criteria와 STOP

- 최종 판정: `INCONCLUSIVE / NON-GATING`
- `B6R-1`: `INCONCLUSIVE` 유지
- `B6R-2`: `BLOCKED` 유지
- `B6R-3~14`: `NOT_STARTED` 유지
- P0/P1/P2: 기존 status와 claim boundary 유지

`MI48 identity`, sensor unit/orientation, clean multi-subject capture, label provenance, split/holdout seal이 새 evidence로 확인되기 전에는 B6R 본선 학습·holdout·physical E2E로 진행하지 않는다.

`STOP — 다음 stage는 새 사용자 지시와 위 재개 조건 확인 후에만 실행한다.`
