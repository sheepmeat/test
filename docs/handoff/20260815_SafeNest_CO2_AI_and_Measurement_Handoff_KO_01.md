# SafeNest CO₂ AI 및 실측 인수인계 안내서

- 문서 버전: `01`
- 작성일: `2026-08-15`
- 단계: `C-C1T — Human Handoff and Two-Stage SCD40 Measurement`
- 작성 에이전트: `Codex (CO2 Human Handoff and Two-Stage Measurement Documentation Agent)`
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
최종 미래 모델 입력: CO2 + CO2_slope
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

Temperature과 Humidity는 최종 후보의 필수 AI 입력이 아닙니다. 그렇다고
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

## 5. 남아 있는 기술 의존성

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

## 6. 두 가지 evidence class

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

## 7. 팀원이 지금 할 수 있는 일

### 7.1 지금 시작 가능한 1차 exploratory 실측

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

### 7.2 #19 배포 이후 정식 실측

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

## 8. 전체 흐름

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

## 9. 팀원이 하면 안 되는 것

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

## 10. 인수인계 결과물

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
