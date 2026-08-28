# SafeNest Thermal standing 오탐 원인분리 Fast-Track 로드맵

문서 상태: **EXECUTION MANUAL / DIAGNOSTIC ONLY**

- 작성일: 2026-08-29
- 작업 브랜치: `docs/thermal-false-positive-fast-track-manual`
- 기준 `origin/main`: `ccdb2b16ddbbec82d1a4d53cef6b23314ebf366b`
- 목표: 화면상 서 있는 사람이 `HUMAN_FALL_PROXY`로 분류되는 원인을 가능한 한 한 번의 통제 실험과 2시간 이내의 분석으로 좁힌다.
- 변경 경계: 이 단계에서는 모델 재학습, production 모델 교체, 임계값 튜닝, 센서 펌웨어 변경, emergency 권한 부여를 하지 않는다.

## 1. 결론부터 실행 순서

```text
배포 identity·안전 경계 확인
        ↓
오탐 한 sequence의 네 경계 보존
        ↓
물리 marker로 orientation 확정
        ↓
동일 standing frame 변환별 재추론
        ↓
TRANSPORT / ORIENTATION / LINEAGE / DOMAIN 중 하나로 분류
```

빠른 완료 기준은 모델 성능을 개선하는 것이 아니다. 다음 네 원인 범주 중 하나를 증거로 선택하거나, 선택을 막는 누락 증거를 정확히 특정하면 이번 fast-track은 완료다.

1. `TRANSPORT_OR_DECODE_DEFECT`
2. `ORIENTATION_OR_DISPLAY_MODEL_DIVERGENCE`
3. `MODEL_OR_PREPROCESSING_LINEAGE_MISMATCH`
4. `REAL_SENSOR_DOMAIN_OR_FRAME_MODEL_FALSE_POSITIVE`

## 2. 현재 상속하는 사실과 경계

### 2.1 현재까지 배제된 가능성

- 운영 수신 자료에서 UDP fragment의 순서·offset·길이·CRC32가 확인된 frame만 AI에 전달됐다.
- 확인된 frame은 `(62,80)`이고 송신 metadata의 min/max와 수신 배열의 min/max가 일치했다.
- UDP payload에는 손실 압축이 없고, 저장용 NPZ 압축은 수신 이후의 무손실 저장이다.

따라서 fragment 누락, 임의 byte 변조, 손실 압축이 standing 오탐의 주원인일 가능성은 낮다.

### 2.2 아직 배제되지 않은 가능성

CRC와 min/max는 다음 문제를 검출하지 못한다.

- 좌우 또는 상하 반전
- 180도 회전
- native row/column 의미의 오해
- 웹 표시 경로와 모델 입력 경로에 서로 다른 변환 적용
- 배포 모델 SHA와 문서상 모델 SHA의 불일치
- 모델에 맞지 않는 preprocessing 적용
- public SDT와 실제 Thermal-90의 센서·설치·배경 domain 차이

### 2.3 저장소 경계

현재 standalone 저장소의 `origin/main`에는 실제 `RaspberryPi/Runtime` 및 `ESP32` UDP 구현이 없다. 이 문서는 그 별도 운영/통합 저장소에서 수집할 evidence contract를 정의한다. raw sensor payload나 참가자 자료를 이 standalone 저장소에 커밋하지 않는다.

## 3. P0 — 오탐 조사 중 안전 경계 고정

목표 시간: **15분**

실제 추론 전에 다음을 확인하고 `alarm_policy_receipt.json`에 기록한다.

- public SDT 모델은 `telemetry/shadow`로만 실행한다.
- `HUMAN_FALL_PROXY` 단일 frame은 emergency, actuator, 외부 알림을 직접 발동하지 않는다.
- legacy wrapper가 class name이 아니라 `class_index == 2`만으로 emergency를 만들지 확인한다.
- 조사 중 출력은 원인분석용 probability log로만 사용한다.

중단 조건:

- class index 2가 즉시 emergency로 연결되는데 격리 여부를 확인할 수 없음
- 실제 활성 모델과 알람 경로를 식별할 수 없음

이 경우 추론 실험보다 먼저 alarm path를 shadow로 격리하고 그 receipt를 남긴다.

## 4. TFP-0 — 실제 배포 lineage 잠금

목표 시간: **15분**

Pi에서 실제 로드된 값을 실행 시점에 읽어 `runtime_identity.json`으로 보존한다. 문서나 파일명만 보고 추정하지 않는다.

필수 필드:

```json
{
  "runtime_repository_commit": "<40-hex SHA>",
  "collector_repository_commit": "<40-hex SHA>",
  "model_path": "<portable logical path>",
  "model_sha256": "<64-hex SHA>",
  "model_size_bytes": 0,
  "model_format": "TFLITE_FP32_OR_FULL_INT8",
  "input_shape": [1, 62, 80, 1],
  "input_dtype": "float32_or_int8",
  "output_shape": [1, 3],
  "class_order": ["NOT_HUMAN", "HUMAN_NORMAL", "HUMAN_FALL_PROXY"],
  "preprocessing_id": "<exact identifier>",
  "runtime_selector": "<exact selector/config source>",
  "alarm_mode": "SHADOW"
}
```

비교해야 할 세 계통:

| 계통 | artifact identity | preprocessing | 허용 상태 |
|---|---|---|---|
| Legacy runtime | 318,184 bytes / SHA `5b56da8d…` | frame min-max → INT8 | public SDT 진단의 기준 artifact로 오인 금지 |
| B6R public SDT | 70,592 bytes / SHA `f88d65d7…` | `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1` | shadow only |
| T-B5 FULL_INT8 | 318,280 bytes / SHA `fa9730c2…` | `P1_TRAIN_FITTED_GLOBAL_ZSCORE` | offline candidate; 별도 T-C 검증 전 production 금지 |

판정:

- 실제 SHA·dtype·preprocessing 조합이 한 행과 정확히 일치하면 `LINEAGE_MATCH`.
- 모델 SHA는 public SDT인데 P1 z-score를 쓰거나, T-B5인데 frame min-max를 쓰면 `MODEL_OR_PREPROCESSING_LINEAGE_MISMATCH`.
- 실제 SHA를 읽을 수 없으면 fail closed로 중단한다.

## 5. TFP-1 — 오탐 한 sequence의 네 경계 추적

목표 시간: **30분**

화면상 standing이 명확하고 `HUMAN_FALL_PROXY`가 발생한 연속 frame에서 하나의 짧은 sequence를 고정한다. 권장 범위는 오탐 전 2초, 오탐 구간, 오탐 후 2초다. 최초 분석은 그중 대표 frame 하나로 수행하고 sequence 전체는 재현성 확인에 사용한다.

### 5.1 보존할 네 경계

| 경계 | 필수 기록 |
|---|---|
| A. 송신 UDP payload | sequence, fragment count, payload length, CRC32, SHA-256, byte order 계약 |
| B. Pi decoded native | shape, dtype, min/max, 네 모서리와 중앙 pixel, C-order bytes SHA-256 |
| C. 웹 표시 직전 배열 | shape, dtype, 적용한 transpose/rotate/flip/scale 목록, 네 모서리와 중앙 pixel, SHA-256 |
| D. 모델 입력 | 정규화 전후 shape/dtype, 전처리 ID, 네 모서리와 중앙 값, tensor bytes SHA-256 |
| E. 모델 출력 | model SHA, class order, 세 probability, argmax, inference timestamp |

경계별 표현과 dtype이 다르므로 SHA가 모두 같아야 하는 것은 아니다. 각 변환이 선언된 규칙대로 A→B→C/D를 만들었음을 `transform_receipt.json`으로 증명한다.

### 5.2 최소 frame record

```json
{
  "capture_id": "<id>",
  "sequence": 0,
  "standing_ground_observation": true,
  "udp": {
    "payload_length": 0,
    "fragment_count": 0,
    "crc32": "<hex>",
    "sha256": "<hex>"
  },
  "decoded": {
    "shape": [62, 80],
    "dtype": "uint16",
    "byte_order": "big_or_little",
    "corner_and_center_values": {},
    "sha256": "<hex>"
  },
  "display_transform": [],
  "model_transform": [],
  "model_input_sha256": "<hex>",
  "model_sha256": "<hex>",
  "preprocessing_id": "<id>",
  "probabilities": {
    "NOT_HUMAN": 0.0,
    "HUMAN_NORMAL": 0.0,
    "HUMAN_FALL_PROXY": 0.0
  }
}
```

### 5.3 즉시 판정

- payload length, CRC, frame accounting이 깨지면 `TRANSPORT_OR_DECODE_DEFECT`.
- B→C와 B→D의 transform chain이 다르고 그 차이가 문서화되지 않았으면 `ORIENTATION_OR_DISPLAY_MODEL_DIVERGENCE`.
- 모든 경계가 선언된 변환과 일치하면 TFP-2로 진행한다.

## 6. TFP-2 — 물리 marker orientation 고정

목표 시간: **30~45분**

안전한 hot marker를 센서가 보는 공간의 좌상·우상·좌하·우하에 차례로 둔다. 가능하면 수직 또는 수평 형태의 marker도 한 번 사용해 점 대칭만으로 놓칠 수 있는 축 의미를 확인한다.

각 위치에서 다음을 기록한다.

- 물리 위치와 촬영 사진 또는 설치 reference record의 SHA-256
- decoded native frame의 peak 또는 marker centroid `(row, column)`
- 웹 표시 좌표
- 모델 입력 직전 좌표
- 센서 mount height, pitch, yaw, scene distance
- native row 증가 방향과 column 증가 방향의 물리 의미

중요 규칙:

- 정답 transform은 marker의 물리 위치로만 선택한다.
- `HUMAN_NORMAL` 확률이 높아지는 transform을 정답으로 선택하지 않는다.
- 세션마다 다른 rotate/flip을 적용하지 않는다.
- 선택한 transform은 `orientation_verification_record.json`에 한 번 고정하고 후속 capture 전까지 변경하지 않는다.

통과 기준:

- 네 위치 모두 decoded → 웹 → 모델 좌표가 하나의 고정 transform으로 설명된다.
- rotation, horizontal flip, vertical flip 값이 단일 값으로 결정된다.
- 설명되지 않는 axis swap이나 display-only transform이 없다.

## 7. TFP-3 — 동일 standing frame 변환별 재추론

목표 시간: **15분**

TFP-2의 물리 검증과 별도로, 오탐 대표 frame 하나를 다음 네 변환으로 재추론한다.

1. `IDENTITY`
2. `FLIP_HORIZONTAL`
3. `FLIP_VERTICAL`
4. `ROTATE_180`

row/column이 실제로 뒤바뀌었다는 marker 증거가 있을 때만 transpose 또는 90도 회전을 추가 진단한다. 모든 입력은 같은 model SHA와 preprocessing ID를 사용한다.

결과 표:

| transform | NOT_HUMAN | HUMAN_NORMAL | HUMAN_FALL_PROXY | argmax | 물리적으로 승인된 transform 여부 |
|---|---:|---:|---:|---|---|
| IDENTITY | | | | | |
| FLIP_HORIZONTAL | | | | | |
| FLIP_VERTICAL | | | | | |
| ROTATE_180 | | | | | |

이 표는 원인 진단용이다. 확률이 좋아 보이는 변환을 사후 선택해 production에 넣지 않는다.

## 8. TFP-4 — 결정 트리

```text
payload/fragment/CRC/byte decode 불일치?
  ├─ 예 → TRANSPORT_OR_DECODE_DEFECT
  └─ 아니오
       ↓
marker 좌표가 웹과 모델에서 다름?
  ├─ 예 → ORIENTATION_OR_DISPLAY_MODEL_DIVERGENCE
  └─ 아니오
       ↓
실제 model SHA·dtype·preprocessing 조합 불일치?
  ├─ 예 → MODEL_OR_PREPROCESSING_LINEAGE_MISMATCH
  └─ 아니오
       ↓
승인 orientation에서도 standing이 FALL_PROXY?
  ├─ 예 → REAL_SENSOR_DOMAIN_OR_FRAME_MODEL_FALSE_POSITIVE
  └─ 아니오 → 승인 orientation 고정 후 반복 sequence 회귀
```

### 8.1 원인별 후속 브랜치

다음 이름은 fast-track 판정 이후 생성할 후보이며, 이 문서 브랜치에서는 생성하지 않는다.

- orientation/ingress 문제: `fix/thermal-orientation-contract`
- model/preprocessing lineage 문제: `fix/thermal-runtime-lineage-lock`
- 실제 domain 오탐 조사: `experiment/thermal90-wave-a`

각 구현 브랜치는 하나의 원인만 다루고, 원인분리 evidence와 rollback 방법을 포함해야 한다.

## 9. 당일 완료 산출물

raw 또는 참가자 frame은 승인된 외부 evidence root에 보관하고, Git에는 식별정보를 제거한 manifest·hash·요약만 검토 후 반영한다.

필수 산출물:

1. `runtime_identity.json`
2. `alarm_policy_receipt.json`
3. `false_positive_sequence_ledger.jsonl`
4. `transform_receipt.json`
5. `orientation_verification_record.json`
6. `standing_transform_probability_table.csv`
7. `fast_track_decision.json`

`fast_track_decision.json` 최소 필드:

```json
{
  "status": "PASS_OR_BLOCKED",
  "selected_cause": "TRANSPORT_OR_ORIENTATION_OR_LINEAGE_OR_DOMAIN",
  "evidence_paths": [],
  "model_or_runtime_changed": false,
  "alarm_mode": "SHADOW",
  "remaining_blockers": [],
  "authorized_next_branch": null
}
```

## 10. Fast-Track 이후 RC1 연결

orientation과 runtime lineage가 고정된 뒤에만 `B6R-RC1` Wave A로 진행한다.

- 독립 subject 최소 3명
- subject당 최소 2 session
- empty-room 최소 2 session
- standing, sitting, crouching, lying posture proxy, entry/exit, partial occlusion, warm-object hard negative
- 모델 출력으로 label 생성 금지
- 기존 `S000`을 locked holdout으로 승격 금지
- 새 subject 최소 2명의 독립 holdout은 protocol freeze 이후에만 수집

Wave A 전에 모델을 재학습하면 orientation 또는 preprocessing 결함을 모델이 외워 버릴 수 있으므로 금지한다. Wave A validator PASS와 sensor identity 승인 후에만 B6R-1 새 revision과 B6R-2 재검토로 이동한다.

## 11. 실행 체크리스트

### 시작 전

- [ ] 실제 운영/통합 저장소 commit SHA를 기록했다.
- [ ] public model을 shadow로 격리했다.
- [ ] 실제 model SHA와 preprocessing ID를 읽었다.
- [ ] 오탐 sequence와 standing 관찰 근거를 고정했다.

### 원인분리

- [ ] A→B→C/D 네 경계 evidence를 저장했다.
- [ ] 네 물리 marker 위치를 모두 확인했다.
- [ ] orientation을 probability와 독립적으로 선택했다.
- [ ] 동일 frame 네 변환 확률표를 만들었다.
- [ ] 네 원인 범주 중 하나 또는 명시적 blocker를 기록했다.

### 종료

- [ ] production 모델·threshold·펌웨어가 변경되지 않았다.
- [ ] 단일 `HUMAN_FALL_PROXY`가 emergency를 발동하지 않는다.
- [ ] raw participant data가 Git에 포함되지 않았다.
- [ ] 다음 구현 브랜치는 판정 후 별도 승인으로 시작한다.

## 12. STOP 조건

다음 중 하나가 발생하면 fast-track을 중단하고 evidence gap으로 보고한다.

- 실제 모델 SHA 또는 preprocessing ID를 확인하지 못함
- 웹 표시와 모델 입력 중 하나를 보존할 수 없음
- 물리 marker 없이 화면 모양만 보고 orientation을 선택함
- 원하는 class가 나오는 transform을 정답으로 사후 선택함
- public proxy output을 emergency ground truth로 사용함
- raw frame을 잃고 class/probability만 보존함
- 원인분리 전에 모델 재학습 또는 threshold 튜닝을 시작함

이 문서의 완료는 실제 낙상 검출 성능 승인이나 Thermal-90 production 승인을 의미하지 않는다.
