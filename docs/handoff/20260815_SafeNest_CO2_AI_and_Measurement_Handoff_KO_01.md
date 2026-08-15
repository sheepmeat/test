# SafeNest CO₂ AI 및 실측 인수인계 안내서

- 문서 버전: `02`
- 작성일: `2026-08-15`
- 단계: `C-C1T — Final Human Handoff and Two-Stage SCD40 Measurement`
- 작성 에이전트: `Codex (Final CO2 Human Handoff Documentation Agent)`
- 문서 상태: `CO2_HANDOFF_PACKAGE_READY`

## 먼저 읽을 현재 상태

이 문서는 CO₂ 담당자가 지금 바로 업무를 이어받기 위한 요약입니다.

```text
[지금 가능]
1차 exploratory real-device collection
= READY_FOR_HANDOFF

[#19 배포 전에는 아직 불가]
정식 protocol-controlled collection
= HOLD

C-C2 formal device-domain validation
= NOT_STARTED
```

즉 현재 모든 CO₂ 측정이 막힌 것은 아닙니다. 다만 지금 수집하는
exploratory evidence와, 나중에 C-C2에서 formal validation에 사용하는
protocol-controlled evidence는 반드시 구분해야 합니다.

## 1. 지금까지 무엇을 만들었는가

SafeNest CO₂ occupancy 방향의 offline model development는 reduced-feature
candidate lock까지 완료됐습니다.

```text
현재 C-B6 후보 입력 계약: CO2 + CO2_slope
모델 실행 위치: Raspberry Pi / later processing
ESP32 역할: 센서 측정과 telemetry transport
운영자 역할: slope 계산이나 AI 실행을 하지 않음
```

현재 고정된 C-B6 후보는 다음과 같습니다.

```text
candidate: C_B6_REDUCED_CO2_SLOPE_CANDIDATE_001
feature order: CO2, CO2_slope
threshold: 0.43
threshold source: TRAIN_INTERNAL_ONLY
```

주요 산출물은 다음 경로에 보존되어 있습니다. 이 파일들은 현재 후보의
오프라인 계보를 설명하며, 실제 장치 성능 검증이나 live deployment를 뜻하지
않습니다.

```text
candidate lock: datasets/co2/manifests/c_b6_reduced_feature_candidate/candidate_lock.json
input contract: models/co2/candidates/c_b6/input_contract.json
float reference: models/co2/candidates/c_b6/float_reference.tflite
INT8 candidate: models/co2/candidates/c_b6/full_integer_int8.tflite
```

기존 B5 four-feature 후보와 그 산출물은 역사적 기준으로 보존되어 있으며,
이번 reduced candidate가 B5를 덮어쓰지 않았습니다.

Temperature와 Humidity는 최종 후보의 필수 AI 입력이 아닙니다. 그렇다고
정보가 전혀 없거나 무가치하다고 결론 낸 것은 아닙니다. 기존 four-feature
실험에서 일부 방향성 이점은 있었지만, 새 SafeNest device contract의
mandatory field로 만들 정도의 결정적 근거는 부족했기 때문에 현재 방향은
`CO2 + CO2_slope`로 고정됐습니다.

## 2. 왜 CO₂ slope를 사용하는가

CO₂ 절대값 하나만 보는 대신, 최근 시간 동안 CO₂가 얼마나 증가하거나
감소했는지를 함께 보기 위해 `CO2_slope`를 사용합니다.

```text
SCD40 / ESP32
    ↓ CO₂ measurement events
Raspberry Pi / later processing
    ↓ past-only ENDPOINT_H150 history
CO2_slope
    ↓
CO2 + CO2_slope model input
```

운영자가 slope를 직접 계산하거나 수기로 입력하지 않습니다. 모델용 slope는
Pi 또는 이후의 고정된 processing path에서 계산합니다.

## 3. 현재 모델 계약

```text
required model fields: CO2, CO2_slope
nominal effective model-input/export cadence: 약 60초
slope history: 최근 150초
chronology: PAST_ONLY
valid-event gap > 90초: H150 history reset
```

명칭은 산출물마다 다르게 보일 수 있습니다. C-B6 오프라인 input contract의
method 표기는 `ENDPOINT_DIFFERENCE`이고, C-C1R/C-C1T 측정 protocol의 선택
profile 표기는 `ENDPOINT_H150`입니다. 현재 두 표기는 모두
`CO2_SLOPE_FEATURE_PROFILE_001`의 **과거 150초 endpoint difference**를
가리킵니다. 이 계산 의미를 바꾸거나 다른 slope 방법으로 교체할 때는
새 candidate와 새 protocol decision이 필요합니다.

60초는 SCD40 native measurement cadence가 60초라는 뜻이 아닙니다. 모델 입력
기회/export 계약과 센서 native cadence는 분리합니다. 새 유효 측정이 없을
때는 이전 값을 60초 위치에 복사하지 않고 missing/failure로 남깁니다.

## 4. 온도와 습도

Temperature/Humidity는 다음처럼 이해하면 됩니다.

```text
기존 four-feature 방향: CO2 + Temperature + Humidity + CO2_slope
현재 reduced candidate: CO2 + CO2_slope
Temperature/Humidity: optional diagnostic evidence, not mandatory model fields
```

따라서 장치가 T/RH를 제공하면 원본 evidence로 보존할 수 있지만, 없다고
CO₂ exploratory session 자체를 무효화하거나 값을 만들어 넣지 않습니다.

## 5. 모델이 하는 일

현재 C-B6에서 고정한 것은 **실제 장치에 배포되어 성능이 입증된 최종 제품
모델**이 아니라, 다음 검증 단계에서 사용할 수 있도록 계약을 고정한 reduced
feature 후보입니다. 이 후보가 의도하는 역할은 방 안의 점유 상태를 추정하는
것입니다.

정상적인 입력 계약이 충족되면 모델은 다음을 수행합니다.

```text
1. 유효한 SCD40 CO₂ 측정값을 받는다.
2. 과거 150초의 검증된 측정 chronology로 CO2_slope를 만든다.
3. [CO2, CO2_slope]를 고정된 순서와 preprocessing으로 모델에 넣는다.
4. 점유 상태 후보와 P(OCCUPIED)를 출력한다.
```

여기서 `P(OCCUPIED)`는 모델이 본 데이터에 대한 **점유 상태의 확률적
출력**입니다. 위험도, 질식 가능성, 의료적 상태, CO₂ 안전판정의 확률이
아닙니다. 현재 문서와 계약은 C-C2 formal device-domain validation 전까지
이 후보의 실측 성능을 확정했다고 말하지 않습니다.

모델 실행과 slope 계산은 Raspberry Pi 또는 이후 승인된 processing path의
책임입니다. ESP32와 현장 운영자는 센서 측정·전달·관찰을 담당하며 slope나
AI를 임의로 계산하거나 입력을 만들어 넣지 않습니다.

## 6. 모델이 하지 않는 일

다음 항목은 현재 CO₂ occupancy 후보의 책임이 아닙니다.

```text
CO₂ 농도만으로 환기·안전 임계값을 판정하지 않는다.
임상적 apnea, 질병, 의료 상태를 판정하지 않는다.
CO₂ 상승이나 모델 출력을 ground truth로 만들지 않는다.
새 SCD40 측정인지 cached telemetry인지 스스로 증명하지 않는다.
누락·오류·stale 값을 정상값이나 이전값으로 자동 대체하지 않는다.
60초 cadence를 맞추기 위해 같은 값을 복제하거나 시각을 조작하지 않는다.
불완전한 H150 chronology에서 신뢰할 수 있는 slope를 만들어내지 않는다.
탐색적 실측만으로 accuracy, F1, recall 또는 formal device validation을 주장하지 않는다.
```

따라서 `connected=true` 또는 CO₂ 숫자가 화면에 보인다는 사실만으로 모델
입력이 완성된 것은 아닙니다. 센서 freshness, event chronology, missing/error
상태가 계약에 맞아야 하며, 그렇지 않으면 해당 시점의 formal inference는
차단하거나 관찰용 상태로 남겨야 합니다.

## 7. 모델 사용 방법

후속 담당자가 모델을 사용할 때는 다음 고정값을 하나의 묶음으로 취급합니다.

| 항목 | 현재 계약 |
|---|---|
| 후보 ID | `C_B6_REDUCED_CO2_SLOPE_CANDIDATE_001` |
| 입력 순서 | `CO2`, `CO2_slope` |
| slope 창 | 과거 150초, `PAST_ONLY` |
| 유효 event gap | 90초 초과 시 H150 reset |
| nominal effective cadence | 약 60초 |
| threshold | `0.43`, `TRAIN_INTERNAL_ONLY` |
| T/RH | 현재 mandatory input 아님 |

실제 사용 순서는 다음과 같습니다.

1. raw payload와 상태를 먼저 보존하고, 새 SCD40 measurement event인지 확인합니다.
2. 현재 event와 과거 150초의 유효 event만으로 slope를 계산합니다.
3. gap, stale, error, missing이 있으면 H150을 reset하거나 해당 inference를
   차단합니다. 이전 값을 새 측정처럼 재사용하지 않습니다.
4. 후보 ID, feature order, scaler, threshold가 모두 일치하는지 확인한 뒤에만
   모델 결과를 점유 상태 관찰값으로 기록합니다.
5. 결과를 ground truth나 안전·의료 판단으로 재해석하지 않습니다.

현재 실측이 exploratory class라면 이 사용 결과는 장치 동작·입력 계약·운영
절차를 확인하는 관찰 evidence로만 기록합니다. formal 성능 주장을 하려면
별도의 C-C2 authorization과 compliance 검사가 먼저 필요합니다.

## 8. 실측과 모델의 관계

실측은 모델을 바로 “정답 확인기”로 만드는 단계가 아닙니다. 두 evidence
class의 역할은 다음처럼 나뉩니다.

```text
exploratory real-device evidence
  → 실제 CO₂ range, 상승/회복 패턴, 통신·stale·error, 운영 절차 확인
  → protocol rehearsal 및 다음 수집의 문제 발견
  → formal 성능 dataset으로 자동 승격하지 않음

protocol-controlled evidence
  → frozen protocol, candidate, event chronology, independent GT 확인
  → 먼저 protocol compliance audit
  → 승인된 경우에만 C-C2 formal device-domain validation 검토
```

수집 중 모델 출력을 보고 라벨, protocol, threshold, scaler, feature를 바꾸지
않습니다. `VACANT`/`OCCUPIED` ground truth는 통제된 장면과 독립적인 운영
기록으로 정하고, CO₂가 오르거나 모델이 `OCCUPIED`를 출력했다는 이유만으로
라벨을 바꾸지 않습니다. 이렇게 해야 실제 측정이 모델을 검증하는 자료인지,
단순히 모델에 맞춰진 자료인지 구분할 수 있습니다.

## 9. 향후 모델을 개선하거나 교체할 때

현재 후보를 개선하거나 새 모델로 교체할 때는 기존 후보를 조용히 덮어쓰지
않습니다. 다음 순서를 새 decision/phase로 기록합니다.

```text
개선 사유와 변경 범위 명시
  ↓
새 candidate ID와 새 model/input contract 생성
  ↓
기존 subject-level split을 상속하여 TRAIN에서만 fit
  ↓
model selection 중 LOCKED_TEST를 열지 않음
  ↓
새 feature, scaler, threshold, window, missing policy 검증
  ↓
후보 lock 후 기존 후보와 offline 비교
  ↓
명시적 승인 뒤에만 runtime/팀 계약과 C-C2 계획 갱신
```

새 후보가 T/RH를 다시 포함하거나 cadence, slope window, freshness semantics를
바꾸면 단순한 weight 교체가 아닙니다. 입력 계약, preprocessing, 수집
protocol, runtime compatibility, evidence manifest를 함께 갱신해야 합니다.
기존 `C_B6_REDUCED_CO2_SLOPE_CANDIDATE_001`의 산출물·체크섬·평가 결과는
역사적 기준으로 보존하고, 새 후보는 별도 ID와 별도 보고서로 추적합니다.

새 모델이 더 좋아 보인다는 이유만으로 탐색적 실측을 소급하여 formal evidence로
바꾸지 않습니다. 새 후보의 비교 결과, 독립 GT, protocol compliance, C-C2
승인 여부가 모두 별도로 기록되어야 합니다.

## 10. 남아 있는 기술 의존성

현재 Pi가 받은 CO₂ 값이 새 SCD40 측정인지, 이전 값의 재전송인지 구분하려면
producer event identity가 필요합니다.

필요한 의미는 다음과 같습니다.

```text
새로운 SCD40 readMeasurement() 성공
    → event ID 증가

cached telemetry retransmission
    → 같은 event ID 유지
```

현재 팀 producer observability 변경은 별도 팀 PR에서 검토 중입니다. PR 번호나
브랜치는 변경될 수 있으므로 담당자는 번호보다 위의 event semantics를
기준으로 확인해야 합니다. 현재 문서 작성 시점에는 팀 PR #19가 `OPEN`이고
team `main` 배포·live verification은 아직 확인되지 않았습니다.

이 의존성은 정식 protocol-controlled collection을 막습니다. 하지만 아래의
exploratory collection까지 막지는 않습니다.

별도로 C-B6 INT8 진단에서 `CO2_slope` 입력 saturation이 낮은 빈도로 관찰된
제한도 남아 있습니다. 이 제한은 문서 작성으로 해결되지 않았으며, C-C2에서
protocol-compliant session의 실제 saturation rate와 prediction effect를
관찰해야 합니다. 따라서 현재 후보는 `C_B6_PASS_WITH_LIMITATIONS`이고,
이 문서는 saturation을 이유로 모델을 임의 교체하지 않습니다.

## 11. 두 가지 evidence class

| 구분 | 지금 가능한 exploratory | 정식 protocol-controlled |
|---|---|---|
| 분류 | `PRE_DEPLOYMENT_EXPLORATORY_REAL_DEVICE_EVIDENCE` | `PROTOCOL_CONTROLLED_REAL_DEVICE_EVIDENCE` |
| 시작 조건 | 현재 가능 | producer 배포 + live C-C1T PASS |
| fresh sensor event identity | `UNVERIFIED`를 limitation으로 보존 | 필수 |
| 실제 CO₂ range/변화 관찰 | 가능 | 가능 |
| qualitative VACANT/OCCUPIED 관찰 | 가능 | 가능 |
| transport/stale/error 진단 | 가능 | 가능 |
| formal H150 chronology claim | 불가 unless separately verified | 가능 조건 |
| C-C2 formal performance dataset | 자동 인정 안 됨 | compliance 통과 후 가능 |
| 모델 accuracy/F1 claim | 불가 | C-C2 이후에만 검토 |

Exploratory data는 버리는 데이터가 아닙니다. 실제 장치 range, 상승·회복
패턴, 통신 안정성, stale/error, 운영 절차와 future formal collection을
이해하는 데 사용할 수 있습니다. 다만 fresh physical event가 검증되지 않은
경우 C-C2 formal performance evidence로 자동 승격하지 않습니다.

## 12. 팀원이 지금 할 수 있는 일

### 12.1 지금 시작 가능한 1차 exploratory 실측

팀 repository의 현재 capture utility를 사용합니다.

```bash
cd <team-repository-root>
python3 devices/co2/firmware/capture_scd40.py \
  --url http://<pi-host>:8080/health \
  --duration-sec 300 \
  --interval-sec 1 \
  --scenario VACANT_STABLE \
  --output <output-root>/20260815_1200_VACANT_<session-id>.csv
```

처음에는 stable VACANT 또는 stable OCCUPIED session을 권장합니다. 한 세션은
기존 150초 H150 history와 warm-up을 관찰할 수 있도록 **최소 300초(5분)**를
권장합니다. 이는 통계적 sample-size 주장이 아니며, 여러 session을 반복할
수록 실제 장치 변동을 더 잘 볼 수 있다는 운영 권고입니다.

Exploratory CSV에는 현재 가능한 범위의 다음 evidence가 남습니다.

```text
raw /health response
host wall-clock timestamp
host monotonic timestamp
CO2 ppm
telemetry seq / uptime
valid.co2
connected / fresh / age / status
error / missing / stale state
device ID and scenario
```

기존 경로에서 producer event marker를 아직 받지 못하면 다음 limitation을
명시합니다.

```text
fresh_sensor_event_identity = UNVERIFIED
formal_h150_eligibility = NOT_ESTABLISHED
evidence_class = PRE_DEPLOYMENT_EXPLORATORY_REAL_DEVICE_EVIDENCE
```

### 12.2 #19 배포 이후 정식 실측

다음 조건이 모두 확인된 후에만 formal mode를 사용합니다.

```text
team producer fresh-event semantics deployed
live producer payload verified
C-C1T live readiness validator PASS
protocol/session/candidate identity available
independent GT and raw checksum workflow available
```

그때 standalone capture tool을 사용합니다.

```bash
python3 scripts/capture_co2_c_c1t_session.py \
  --output-root <session-output-root> \
  --operator-id <operator-id> \
  --location-id <location-id> \
  --scenario-id VACANT_STABLE \
  --ground-truth VACANT \
  --ground-truth-source CONTROLLED_EMPTY_ROOM \
  --source-url http://<pi-host>:8080/health \
  --duration-sec 300 \
  --interval-sec 1
```

정식 bundle은 protocol ID/version, C-B6 candidate identity, producer event
ID/chronology, GT, raw payload, failure/deviation, checksum을 모두 보존해야
합니다. 같은 event ID가 여러 packet에서 반복되면 한 physical measurement로
계수합니다.

## 13. 전체 흐름

```text
현재
  ↓
1차 exploratory real-device collection 가능
  ↓                         ↘
실제 CO₂/통신/운영 evidence       producer fresh-event review/deploy
                                ↓
                         live C-C1T verification
                                ↓
                         formal acquisition release
                                ↓
                  protocol-controlled data accumulation
                                ↓
                 explicit authorization for C-C2
                                ↓
                    C-C2 compliance + validation
```

Exploratory data는 C-C2에서 context, device range, failure mode, capture
diagnostic으로 검토할 수 있지만, 자동으로 formal dataset이 되지는 않습니다.

## 14. 팀원이 하면 안 되는 것

```text
모델 결과를 보고 ground truth를 변경하지 않기
CO₂가 높다는 이유만으로 OCCUPIED라고 라벨링하지 않기
CO2_slope가 올라간 시각을 입장 시각으로 사용하지 않기
raw CSV/JSONL을 수동 수정하거나 삭제하지 않기
missing/error/stale row를 삭제하지 않기
stale CO₂를 새 측정처럼 복제하지 않기
60초에 맞추려고 timestamp나 값을 인위적으로 만들지 않기
ESP32에서 slope/AI 계산을 임의로 추가하지 않기
수집 중 threshold/scaler/model/feature를 조정하지 않기
```

## 15. 인수인계 결과물

```text
human handoff document:
docs/handoff/20260815_SafeNest_CO2_AI_and_Measurement_Handoff_KO_01.md

two-stage measurement guide:
docs/prompts/20260815_SafeNest_CO2_SCD40_Physical_Measurement_Guide_KO_01.md

machine-readable handoff status:
datasets/co2/manifests/c_c1t_acquisition_tooling/human_handoff_status.json
```

현재 상태는 다음과 같습니다.

```text
EXPLORATORY_OPERATOR_HANDOFF: READY_FOR_HANDOFF
EXPLORATORY_PHYSICAL_COLLECTION: ALLOWED
FORMAL_PROTOCOL_OPERATOR_HANDOFF: HOLD
FORMAL_PHYSICAL_COLLECTION: HOLD
C-C2: NOT_STARTED
C-D: NOT_AUTHORIZED
```
