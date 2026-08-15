# SafeNest CO₂ SCD40 실측 안내서 — Exploratory / Formal 두 단계

- 문서 버전: `01`
- 작성일: `2026-08-15`
- 단계: `C-C1T — Two-Stage SCD40 Physical Measurement Handoff`
- 작성 에이전트: `Codex (CO2 Human Handoff and Two-Stage Measurement Documentation Agent)`
- 문서 상태: `EXPLORATORY_READY_FORMAL_HOLD`

> 이 문서는 두 가지 측정 모드를 지원합니다.
>
> **[1차 실측] Exploratory Mode — 지금 수행 가능**
> 실제 장치 evidence를 모으되, fresh physical measurement event identity가
> 확인되지 않으면 formal C-C2 evidence로 자동 인정하지 않습니다.
>
> **[정식 실측] Protocol-Controlled Mode — 현재 HOLD**
> producer fresh-event 배포, live verification, C-C1T readiness PASS 이후에만
> 시작합니다.

## 1. 모든 모드에 공통인 모델 계약

```text
AI 필수 입력: CO2
AI 필수 파생 입력: CO2_slope
Temperature/Humidity: 현재 모델의 필수 입력 아님
CO2_slope 계산: Pi 또는 later processing
nominal effective model-input/export cadence: 약 60초
H150 history: 150초
chronology: 과거값만 사용
valid-event gap >90초: history reset
threshold: 0.43 (TRAIN_INTERNAL_ONLY)
```

운영자는 slope, model output, threshold를 계산하거나 수정하지 않습니다.
60초에 새 측정이 없으면 이전 CO₂를 복사하지 않고 missing/failure로 남깁니다.
60초는 SCD40 native cadence를 뜻하지 않습니다.

## 2. MODE 1 — Pre-deployment Exploratory Real-Device Collection

### 상태와 목적

```text
상태: READY_FOR_HANDOFF
실제 collection: ALLOWED
분류: PRE_DEPLOYMENT_EXPLORATORY_REAL_DEVICE_EVIDENCE
자동 C-C2 eligible: NO
```

이 데이터는 버리는 데이터가 아닙니다. 다음을 확인하는 데 사용합니다.

```text
실제 CO₂ range와 변화
VACANT/OCCUPIED 조건의 qualitative behavior
rise/recovery 관찰
ESP32–Pi transport 안정성
stale/missing/error 동작
운영자의 capture workflow
future formal collection 준비
```

다만 기존 producer 경로에서 새 SCD40 measurement event를 증명할 수 없으면
다음 limitation을 함께 보존합니다.

```text
fresh_sensor_event_identity = UNVERIFIED
formal_measurement_chronology = NOT_ESTABLISHED
formal_ENDPOINT_H150_claim = BLOCKED
formal_C-C2_performance_eligibility = NO
```

### 시작 전 체크

```text
□ 실제 사용할 SCD40–ESP32–Pi 장치 확인
□ Pi /health URL 확인
□ capture software/firmware/library identity 기록
□ 새 session용 출력 경로 준비
□ VACANT 또는 OCCUPIED 상태를 실제로 확인
□ 모델 출력은 보지 않기로 확인
```

### 권장 session 절차

첫 exploratory session은 stable label로 진행합니다.

```text
VACANT_STABLE: 측정 시작부터 종료까지 실제로 사람이 없음
OCCUPIED_STABLE: 측정 시작부터 종료까지 실제로 사람이 있음
권장 duration: 최소 300초(5분)
권장 capture interval: 1초
```

300초는 150초 H150 history와 warm-up 이후의 실제 변화를 관찰하기 위한
실무적 최소 권고입니다. 통계적 검정력이나 C-C2 sample-size 보장은 아닙니다.
가능하면 VACANT/OCCUPIED 각각 여러 session을 반복합니다.

### Exploratory capture 명령

팀 repository root에서 현재 사용 가능한 legacy capture utility를 실행합니다.

```bash
python3 devices/co2/firmware/capture_scd40.py \
  --url http://<pi-host>:8080/health \
  --duration-sec 300 \
  --interval-sec 1 \
  --scenario VACANT_STABLE \
  --output <output-root>/20260815_1200_VACANT_<session-id>.csv
```

`OCCUPIED_STABLE` session은 `--scenario` 값을 바꾸고 실제 사람의 존재를
기록합니다. capture utility는 기존 `/health` raw response, host timestamp,
host monotonic timestamp, CO₂, packet seq, `valid`, `connected`, `fresh`,
transport status, age, error를 저장합니다.

### Exploratory ground truth

Ground truth는 사람이 실제로 있는지에 대한 운영자 관찰에서만 만듭니다.

```text
VACANT: 시작부터 종료까지 사람이 없음
OCCUPIED: 시작부터 종료까지 사람이 있음
```

세션 메모에 최소한 다음을 기록합니다.

```text
session ID / 파일명
operator ID
실제 시작·종료 시각
VACANT 또는 OCCUPIED
장치 ID와 위치
사람 입장·퇴장 시각(transition session인 경우)
센서 끊김, stale, error, missing 관찰
```

CO₂ 값이 높거나 slope가 올라간 것을 근거로 OCCUPIED를 만들지 않습니다.
모델 결과나 threshold crossing도 ground truth가 아닙니다.

### Exploratory transition

전환 session은 stable session 다음에 선택적으로 진행합니다.

```text
사람이 실제로 들어온 시각을 기록
사람이 실제로 나간 시각을 기록
시각이 불확실하면 transition/ambiguous로 표시
CO₂ 상승 시각을 입장 시각으로 사용하지 않음
```

### Exploratory 오류 처리

다음 상태가 생겨도 raw 데이터를 지우지 않습니다.

```text
sensor disconnected
transport error
missing response
CO₂ missing/invalid
stale telemetry
logger failure
```

이전 valid 값을 복사하거나 정상값으로 대체하지 않습니다. exploratory
파일은 현재 가능한 evidence와 limitation을 함께 보존하는 것이 목적입니다.

### Exploratory 제출물

```text
<session-directory>/
  capture.csv
  ground_truth.md
  operator_notes.md
  checksums.sha256
```

raw CSV는 수정하지 않습니다. checksum을 만들 수 있으면 파일을 닫은 뒤
생성합니다.

```bash
cd <session-directory>
shasum -a 256 capture.csv ground_truth.md operator_notes.md > checksums.sha256
```

파일명에는 모델 결과나 threshold를 넣지 않습니다. 권장 형식은 다음과 같습니다.

```text
YYYYMMDD_HHMM_<VACANT|OCCUPIED>_<session-id>.csv
```

## 3. MODE 2 — Protocol-Controlled Formal-Eligible Collection

### 현재 상태

```text
상태: HOLD_PENDING_PRODUCER_DEPLOYMENT_AND_LIVE_C_C1T_VERIFICATION
실제 collection: 현재 시작 금지
분류: PROTOCOL_CONTROLLED_REAL_DEVICE_EVIDENCE (release 이후)
```

Mode 2를 열려면 다음을 모두 확인해야 합니다.

```text
□ producer fresh-event change가 team main에 반영됨
□ 실제 배포된 ESP32/Pi payload에서 event semantics 확인
□ C-C1T live readiness validator PASS
□ protocol ID/version 기록 가능
□ C-B6 candidate identity 기록 가능
□ producer event ID와 measurement chronology 보존 가능
□ independent VACANT/OCCUPIED GT 기록 가능
□ raw session bundle과 checksum finalization 가능
```

현재 팀 producer PR #19는 문서 작성 시점에 `OPEN`이며, formal mode는
그 배포와 live verification 전까지 `HOLD`입니다.

### Formal capture 명령

release 후 standalone repository에서 실행합니다.

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

이 도구는 raw payload를 전처리 전에 보존하고 session manifest,
ground_truth_events, failure/deviation log, checksums를 생성합니다.

### Formal 필수 fresh-event semantics

```text
co2_measurement_event_id
co2_measurement_monotonic_ms
co2_measurement_event_valid
```

같은 event ID가 packet seq 변화와 함께 반복되면 cached retransmission입니다.
새 physical measurement가 아니므로 새 event로 세지 않습니다. `fresh`,
`age_seconds`, Pi receipt time, packet seq만으로 fresh sensor event를 선언하지
않습니다.

## 4. H150과 warm-up을 운영자 관점에서 이해하기

AI는 최근 약 150초의 CO₂ 변화 history로 slope를 계산합니다. 따라서 측정
시작 직후에는 과거 history가 부족해 slope가 없을 수 있습니다. 초기 row를
삭제하지 않습니다.

유효한 fresh-event gap이 90초를 넘으면 history를 reset합니다. 중간 값을
만들거나 이전 값을 복사해 gap을 숨기지 않습니다.

## 5. C-C2 연결 규칙

```text
Exploratory evidence
    != automatically C-C2 eligible
```

Exploratory evidence는 C-C2에서 실제 장치 range, failure mode, capture
diagnostic, context로 검토할 수 있습니다. 그러나 formal accuracy,
precision, recall, F1, confusion matrix를 자동으로 주장할 수 없습니다.

Protocol-controlled evidence도 C-C2 compliance audit를 먼저 통과하고,
사용자의 별도 C-C2 승인이 있어야 formal validation으로 진행됩니다.

## 6. 제출 전 quick checklist

### Exploratory Mode

```text
□ 실제 VACANT/OCCUPIED 상태 확인
□ capture 시작·종료 시각 기록
□ raw CSV 보존
□ packet/transport/stale/error 정보 보존
□ GT를 CO₂나 모델 결과에서 유도하지 않음
□ missing/error row 삭제하지 않음
□ operator note 작성
□ checksum 생성 가능하면 생성
□ PRE_DEPLOYMENT_EXPLORATORY_REAL_DEVICE_EVIDENCE로 표시
□ 자동 C-C2 eligible이라고 표시하지 않음
```

### Formal Mode

```text
□ producer fresh-event fields 확인
□ event ID와 measurement chronology 확인
□ protocol/version 확인
□ C-B6 candidate identity 확인
□ independent GT 확인
□ raw/session/failure/deviation bundle 확인
□ checksum PASS 확인
□ C-C1T live readiness PASS 확인
□ 별도 승인 없이 C-C2 시작하지 않음
```

## 7. 금지 사항

```text
모델 결과를 보고 GT 변경 금지
CO₂가 높다는 이유로 OCCUPIED 라벨 생성 금지
CO₂ 상승으로 transition 시각 추정 금지
raw 데이터 수동 수정·삭제 금지
missing/error/stale 삭제 금지
stale 값을 새 측정처럼 복제 금지
60초 cadence를 맞추기 위한 인위적 timestamp 생성 금지
ESP32에서 slope/AI 계산 임의 추가 금지
수집 중 feature/scaler/threshold/model 변경 금지
```
