# SafeNest mmWave Technical Handoff

문서 상태: **문서 전용 인수인계 문서**
대상: mmWave 트랙을 이어서 수행할 엔지니어·AI agent, 그리고 구현 소유자가 아닌 팀 리드
범위: Phase A/B 고정 상태, 기존 팀 MR60 실측의 의미, Team PR #18 의존성, standalone `M-C0` 시작 경계, 이후 `M-C1`/`M-C2`/`M-D` 조건

> 이 문서는 모델, 데이터셋, 펌웨어, 전처리, 임계값, 로드맵 본문을 변경하지 않는다. 새 측정을 하지 않고, `M-C0`를 실행하지 않으며, 추론·재학습을 하지 않는다. 아래의 다음 단계 질문은 **향후 실행 지시**이지 이 문서 작업에서 푸는 문제가 아니다.

구조·증거 문체·핸드오프 완전성의 참고 문서는 Thermal 인수인계
`docs/20260815_Codex_Thermal_Runtime_Temporal_Handoff_KO_01.md`다.
Thermal의 센서 가정·클래스·전처리·후보 SHA는 mmWave에 복사하지 않는다.

작성 시점 identity:

```text
standalone origin/main     81358008f44ff7b92e1c0997d862777c97497440
team main                  3d86bf2a7a4e527d7aba2dfabcb087201ffeb46e
team PR #18                OPEN, DRAFT, not merged
PR #18 head                62eb0d867cfa02295c9a1d023b813134c434b8eb
PR #18 base                5947334d3d0f6c6f7d6100c7ea6af219e5b4c5d5
```

기존 팀 실측 평가 보고서가 사용한 팀 `main`은 `fdf34b804f35e5868356f0ed6f804a248aa69131`이다.
그 이후 팀 `main`은 ESP32 LCD(PR #12)와 문서 PR #17을 병합했다. PR #18 head는 2026-08-14 이후 새 커밋이 없다.

---

## 1. 이 문서의 목적

SafeNest mmWave는 public radar 데이터로 호흡 이상 분류 후보를 고정한 뒤, 실제 MR60BHA2 장치 신호가 그 후보와 같은 뜻인지를 확인하는 트랙이다.

다음 담당자가 채팅 기록 없이 답해야 하는 질문은 다음이다.

1. mmWave 트랙이 무엇을 하려는가?
2. 현재 모델이 실제로 소비하는 물리량은 무엇인가?
3. Phase A에서 무엇이 끝났는가?
4. Phase B에서 무엇이 끝났고, 무엇이 얼려 있는가?
5. offline 평가의 한계는 무엇인가?
6. 팀 MR60 실측은 지금 무엇을 증명하고, 무엇을 증명하지 못하는가?
7. Team PR #18은 무엇을 추가했고, 왜 standalone `M-C0`를 대체하지 않는가?
8. standalone `M-C0`는 왜 아직 시작되지 않았으며, 시작하면 무엇을 먼저 묻는가?
9. 이후 `M-C1`/`M-C2`/`M-D`는 어떤 조건에서만 열리는가?
10. 다음 agent가 먼저 해야 할 일과 절대 하지 말아야 할 일은 무엇인가?

---

## 처음 읽는 사람을 위한 5분 요약

### 지금 mmWave AI가 하는 일

```text
30초 호흡 위상 시계열 (명목 10 Hz, 300 sample)
    ↓
BPF_ZSCORE 전처리
    ↓
frozen strict-INT8 Conv1D
    ↓
NORMAL / RAPID_OR_ABNORMAL / APNEA-proxy
```

여기서 모델이 보는 것은 **호흡수 숫자 하나가 아니라**, 30초 동안의 위상형 파형이다.

### 지금 하지 못하는 일

실제 MR60BHA2가 내보내는 신호가 위 입력과 같은 뜻인지는 아직 증명되지 않았다.
기존 팀 실측으로 Accuracy/F1을 발표하거나, 임상 apnea를 주장하거나, 모델을 재학습할 권한은 없다.

### 팀이 이미 가진 실측의 역할

팀 저장소에는 timestamp가 찍힌 MR60 JSONL/CSV, paced 호흡 시험, 거리 세션, 약 31분 로그가 있다.
이것은 **버릴 데이터가 아니다.** 센서가 무엇을 남기는지 보는 증거다.
다만 정식 장치 검증셋이 아니고, Phase-B 세 클래스의 독립 정답셋도 아니다.

### 다음 단계

```text
Phase A  = public radar 데이터 정규화·라벨·subject split 완료
Phase B  = offline 후보·전처리·strict INT8 고정 완료
M-C0     = 기존 팀 MR60 forensic + Phase-B 대응 판정   ← 아직 NOT_STARTED
M-C1     = 규약 있는 새 물리 측정
M-C2     = frozen 후보의 정식 device-domain 평가
M-D      = 측정된 gap이 따로 승인된 뒤에만 적응/재학습
```

이 문서의 `[현재 구현]`, `[현재 evidence]`, `[팀 저장소]`, `[아직 미검증]`, `[향후 실행]` 표시는
무엇이 이미 저장소에 있고 무엇이 아직 아이디어인지 구분하기 위한 것이다.

---

## 2. 현재 mmWave 개발 상태

```text
현재 상태              = REAL_DATA_OFFLINE_CANDIDATE
다음 공식 단계         = standalone M-C0 (NOT_STARTED)
Team PR #18            = 외부 의존성. standalone M-C0 완료가 아님
Pi / MR60 정식 검증    = 아직 수행하지 않음
임상 apnea             = 주장할 수 없음
재학습                 = 허가되지 않음
```

근거: `datasets/mmwave/manifests/M-B12_phase_b_offline_final/claim_boundary.json`,
`device_domain_handoff.json` (`m_c_started: false`).

### 2.1 한눈에 보는 고정 값

| 항목 | 현재 고정 값 | 의미 |
|---|---|---|
| A-stage | A0–A6 `PASS_WITH_WARNINGS` | Zenodo radar 데이터 정규화 완료 |
| 원본 archive identity | `datasets/raw_archives/external_datasets/db_records.zip` | SHA-256 `f0bcfdac94f88b43bb34d3da8e8f071a787291f86c97798059b8dbf4d4be08b0`. Git-tracked payload가 아니라 A6/M-B12가 잠근 identity. `.gitignore`가 `/datasets/raw_archives/`를 제외한다. |
| 인구 | 110 subject / 440 recording | A5 subject-wise split |
| canonical | `datasets/mmwave/processed/mmwave_canonical_real_v1.npy` | `[530, 300]` float64, SHA-256 `c2e2cd1615c7af0f0e21700f291ee12ac0347a9f7fc6ccc9f337433c16868f0e` |
| 전처리 | `M-B1_D0_B1_Z1` / `BPF_ZSCORE` | TRAIN-only z-score |
| 실행 계약 | `M-B10B_SELECTED_REAL_CANDIDATE_BPF_ZSCORE_V1` | Butterworth 0.1–0.5 Hz, order 4, filtfilt, fs=10 Hz |
| z-score | mean `0.0031162832173884064`, std `2.955399434649939` | TRAIN에서만 fit |
| 후보 | `M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120` | 새 모델을 만들지 않음 |
| runtime ID | `M-B3_CONV1D_GAP_BASELINE_seed42_M-B6_STRICT_INT8` | Flex/Select TF Ops 없음 |
| INT8 SHA-256 | `6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5` | M-B12 `locked_candidate_summary.json`; 22,080 bytes |
| 입력 | `[1, 300, 1]` int8, scale `0.041720833629369736`, zp `-3` | 30초 · 명목 10 Hz |
| 출력 | `[1, 3]` int8, scale `0.00390625`, zp `-128` | 0 NORMAL, 1 RAPID_OR_ABNORMAL, 2 APNEA |
| 최종 offline 평가 | Acc `0.56`, Macro F1 `0.494836` | **non-pristine LOCKED_TEST reuse** |
| M-C | `m_c_started: false` | standalone 권한 기준 |

#### 숫자를 모델에 넣기 전: BPF와 z-score

센서/데이터셋에서 얻은 위상 숫자를 그대로 넣지 않는다. 약 0.1–0.5 Hz 호흡 대역만 남긴 뒤, TRAIN에서 정한 평균·표준편차로 범위를 맞춘다.

```text
300 sample 위상 창
    ↓
창 평균 제거
    ↓
Butterworth bandpass 0.1–0.5 Hz (filtfilt)
    ↓
TRAIN mean/std로 z-score
    ↓
[-5, 5] clip
    ↓
INT8 양자화
```

`TRAIN-fitted`는 **[현재 evidence]** 보호 장치다. VALIDATION이나 LOCKED_TEST를 보고 평균·표준편차를 다시 계산하면 평가 정보가 학습에 섞일 수 있다.

#### 입력·출력 모양을 쉽게 읽기

`[1, 300, 1]`은 모델이 한 번에 받는 tensor 모양이다.

```text
1     = 한 창
300   = 30초 × 명목 10 Hz
1     = 채널 하나 (호흡 위상형 파형)
```

300개의 숫자를 모양만 맞추는 것으로는 부족하다. 그 300개가 **신선한 위상 관측**이어야 하고, 전처리 의미가 Phase B와 같아야 한다.

---

## 3. 저장소와 권한 경계

SafeNest에는 두 저장소가 있다. 섞지 않는다.

| 저장소 | 역할 | 이 트랙에서 하는 일 |
|---|---|---|
| standalone `https://github.com/sheepmeat/test.git` | canonical AI·evidence | Phase A/B lock, 로드맵, 평가 보고서, 향후 standalone `M-C0` 산출물 |
| team `https://github.com/jinsu1011/safenest-embedded-competition` | 임베디드·물리 증거 | MR60 firmware, JSONL/CSV, 장치 측정, Team PR #18 |

```text
팀 저장소의 구버전 ondevice_ai/
    ≠
standalone frozen Phase-B candidate
```

팀 `devices/mmwave/`는 device-domain 증거다. standalone `models/`·`datasets/`를 덮어쓰지 않는다.
팀 PR의 폴더 이름이 `M-C0`여도 standalone `M-C0` 완료가 아니다.

병렬 트랙 격리:

```text
mmWave 작업 브랜치에 CO₂ / Thermal / Integration 변경을 섞지 않는다.
```

---

## 4. End-to-end 데이터·모델 계보

```text
Zenodo 10.5281/zenodo.18599983 v1.1  (db_records.zip)
    ↓  A0 identity
안전한 rFFT reader                     A1
range-bin / phase extraction           A2
10 Hz · 30 s · 300 sample window       A3
Movesense 참조 라벨 + apnea proxy      A4
subject-wise TRAIN/VAL/LOCKED_TEST     A5
canonical npy + integrity audit        A6
    ↓
preprocessing ablation → BPF_ZSCORE    M-B1
architecture → Conv1D GAP              M-B3
seed42 + class-balanced calibration    M-B4/M-B5
strict INT8                            M-B6
offline candidate lock                 M-B11/M-B12
    ↓
[아직 미검증] 물리 MR60 breath_phase가 위 입력과 같은 뜻인가?
    ↓
M-C0 forensic / correspondence
    ↓ (대응이 방어 가능할 때만)
optional exploratory inference
    ↓
M-C1 규약 실측 → M-C2 정식 평가
    ↓ (측정된 gap + 별도 승인)
M-D
```

별도 계보 — 모델 입력이 아님:

```text
MR60 vendor algorithm
    ↓
0x0A14 breathRaw
    ↓
JSONL breath_rate_raw   = vendor 호흡수 (rpm-like)
```

---

## 5. Phase A 완료 상태

상태: **COMPLETE** (`PASS_WITH_WARNINGS`). 근거:
`docs/reports/20260808_Antigravity_A5_Subject_Split_Provenance_01.md`,
`docs/reports/20260808_Antigravity_A6_Full_Conversion_Integrity_Audit_01.md`.

### 5.1 데이터가 무엇인가

Phase A 원본은 팀 MR60이 아니다. public radar recording archive다.
경로 `datasets/raw_archives/external_datasets/db_records.zip`은 A6/M-B12가 기록한 identity이며, raw archive 디렉터리는 Git에서 제외된다. SHA는 M-B12 보고서와 A6 감사에 잠겨 있다.

- 110명, 각 4 recording, 총 440 recording
- canonical window 530개, 각 300 sample
- class 합계: NORMAL 149 / RAPID_OR_ABNORMAL 119 / APNEA 213 / AMBIGUOUS 49
- 구조적 split window: TRAIN 358 / VALIDATION 84 / LOCKED_TEST 88
- 순수 클래스 평가 가능: TRAIN 327 / VALIDATION 79 / LOCKED_TEST 75
- LOCKED_TEST에서 제외된 AMBIGUOUS/비적격: 13

### 5.2 라벨 의미

프로파일: `datasets/mmwave/manifests/a4_label_pilot/label_mapping_profile.json`
(`MMWAVE_LABEL_MAPPING_PROFILE_001`).

| 클래스 | index | Phase A에서 뜻하는 것 |
|---|---:|---|
| `NORMAL` | 0 | Movesense chest-acc 호흡수가 약 10–25 bpm이고, non-breathing overlap이 없는 휴식 조건 proxy |
| `RAPID_OR_ABNORMAL` | 1 | 같은 참조 센서에서 `< 10 bpm` 또는 `>= 25 bpm` |
| `APNEA` | 2 | **자발적 breath-hold 창의 SafeNest proxy**. 임상 apnea가 아니다 |
| `AMBIGUOUS` | — | 순수 클래스 학습에서 제외. provenance와 전이 분석용으로 보존 |

`rapid_min_rr_bpm: 25.0`은 **frozen Phase-A public-dataset 규칙**이다.
미래 MR60 `M-C1`의 자동 임계값이 아니다. paced 20 rpm을 `RAPID_OR_ABNORMAL`로 자동 매핑하지 않는다.

Plain meaning:
Phase A의 “APNEA”는 병원 진단이 아니라, 숨 참기 구간을 학습용 대리지표로 쓴 것이다.

### 5.3 Subject split

프로파일 seed `20260808`. subject 단위 배정: TRAIN 77 / VALIDATION 17 / LOCKED_TEST 16.
한 사람의 모든 recording/window는 한 split에만 있다. 교차 split overlap = 0.

파일: `datasets/mmwave/splits/mmwave_real_subject_split_v1.json`
SHA-256 `a1996ea00a1d5066eae6d25f022d04137085434d4768e27cbebcdad4e0385baa`.

---

## 6. Phase B 완료·고정 상태

상태: **FROZEN** as `REAL_DATA_OFFLINE_CANDIDATE`.
배포 완료, MR60 검증 완료, Pi 검증 완료가 아니다.

권위 문서:

- `docs/reports/20260813_Cursor_M-B11_mmWave_Offline_Candidate_Artifact_Lock_01.md`
- `docs/reports/20260813_Cursor_M-B12_mmWave_Phase_B_Offline_Final_Report_01.md`
- `datasets/mmwave/manifests/M-B12_phase_b_offline_final/`

선택 경로:

```text
M-B1  BPF_ZSCORE
M-B2  unweighted CE
M-B3  CONV1D_GAP_BASELINE
M-B4  seed 42 (VALIDATION Macro F1 0.663708; seed44는 0.329107)
M-B5  CAL_CLASS_BALANCED_120
M-B6  strict INT8
```

아티팩트 경로와 identity는 M-B12 lock이 권위다.

```text
authority:
  docs/reports/20260813_Cursor_M-B12_mmWave_Phase_B_Offline_Final_Report_01.md
  datasets/mmwave/manifests/M-B12_phase_b_offline_final/locked_candidate_summary.json

path:
  models/mmwave/experiments/M-B6_stage_equivalence/M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120_int8.tflite

sha256:
  6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5

bytes: 22080
runtime_model_id: M-B3_CONV1D_GAP_BASELINE_seed42_M-B6_STRICT_INT8
```

이 SHA-256을 바꾸거나 파일을 교체하는 것은 이 문서가 허가하지 않는다. 이후 본문의 짧은 `6dff6aaa…` 표기는 위 전체 해시와 같은 객체를 가리킨다.

---

## 7. 알려진 offline 한계와 LOCKED_TEST 거버넌스

최종 숫자는 `datasets/mmwave/manifests/M-B12_phase_b_offline_final/final_evaluation_summary.json`.

| 항목 | 값 | 읽는 법 |
|---|---|---|
| Accuracy | 0.56 | 비-pristine holdout reuse |
| Macro F1 | 0.494836 | 배포 성능이 아님 |
| NORMAL recall | 0.20 | 약함. 잠긴 한계 |
| RAPID recall | 0.421053 | 중간 |
| APNEA-proxy recall | 0.935484 | 높음 |
| APNEA-proxy FPR | 0.522727 | 오경보가 큼 |
| worst-subject Macro F1 | 0.095238 | subject 일반화가 약함 |
| class collapse | false | 세 클래스 모두 예측은 나옴 |

결과 지정:

```text
REUSED_LOCKED_TEST_AFTER_PREINFERENCE_STRUCTURAL_ABORT
result_not_pristine = true
PRISTINE_LOCKED_TEST = false
```

### 7.1 무슨 일이 있었는가

M-B10B는 LOCKED_TEST 구조 window 88개와 순수 클래스 평가 가능 75개를 혼동한 pretest 때문에 **추론 전에 abort**했다.
이후 제한적 recovery(M-B10R1-B)에서 75개 eligible window를 평가했다.
이것은 두 번째 깨끗한 최종 시험이 아니다.

근거: `docs/reports/20260812_Codex_M-B10B_One_Time_Locked_Test_Final_Evaluation_01.md`,
`claim_boundary.json` (`locked_test_reopen_allowed: false`, `recovery_reopen_allowed: false`).

### 7.2 M-C에서 지켜야 할 것

```text
LOCKED_TEST는 이미 governed 조건에서 소비되었다.
M-C는 이 offline locked test를 다시 열거나, 그것으로 튜닝하지 않는다.
장치 domain 평가는 별도의 평가 domain이다.
```

Mac/M2 latency(M-B8)와 mock runtime(M-B9)은 Pi/실센서 증거가 아니다.

이 한계는 즉시 B-series를 다시 돌리는 결함이 아니다.
`scientific_limitations.json`은 이를 잠긴 과학 사실로 기록한다.

---

## 8. 기존 팀 MR60 증거 목록

권위 보고서:

- 영문 기술: `docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md`
- 한글 사람용: `docs/reports/20260814_SafeNest_mmWave_Team_MR60_Data_Evaluation_KR_01.md`

경로 아래는 **[팀 저장소]** repository-relative다. standalone canonical 데이터가 아니다.

물리 증거는 “데이터셋 두 개”가 아니다. 측정 묶음·세션·파생 산출물을 따로 적는다.

### 8.1 Legacy delivery CSV / JSONL (2026-07)

```text
devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/
```

| Session ID | 역할 |
|---|---|
| `S001_NORMAL_D06` | 점유 거리, preferred |
| `S001_NORMAL_D09` | 점유 거리, preferred |
| `S001_NORMAL_D12` | 거리 한계 / presence drop |
| `S001_NORMAL_D15` | lock-loss / vitals freeze |
| `S001_BREATH_PACED_12_01` | 실패한 12 rpm 시도 (실제 ≈ 6.06 rpm) |
| `S001_BREATH_PACED_12_02` | 유효 12 rpm |
| `S001_BREATH_PACED_15_03` | 15 rpm delivery |
| `S001_BREATH_PACED_20_04` | 20 rpm 얕은 호흡 |
| `S001_BREATH_PACED_20_05` | 20 rpm 깊은 호흡 |

CSV `resp_phase`는 ESP `breath_phase`를 그대로 둔다. 스케일·Z-score·평활·재샘플 없음.
`subject_id`는 exporter가 `S001`로 고정한다. 파일이 여러 개여도 사람이 여러 명이라는 뜻이 아니다.

### 8.2 장시간 schema-1.2 로그

```text
devices/mmwave/firmware/logs/final/2026-08-01_occupied_d09_v120_31min_attempt02.jsonl
SHA-256 7f9e9ac65377c6dc217af92f9dee2401b6162540e2245fce97acf2ed49368a34
```

역할: stale/freeze/dropout, 장시간 안정성, C++/Python 재현.
정식 모델 정확도 증거가 아니다.

확인된 수치 **[현재 evidence, 평가 보고서 §9]**:

| 항목 | 값 |
|---|---|
| 센서 record | 18,574 |
| 길이 | ≈ 31.00 min |
| telemetry/log-row cadence | 9.986 Hz |
| 최대 row gap | 103 ms |
| firmware | `safenest-mr60-esp/1.2.0` |
| `phase_age_ms` 최대 | 288,530 ms |
| `phase_age_ms` > 30 s | 2,585 packets |

이 로그는 약 10 Hz로 **줄을 찍으면서도** `breath_phase`를 수 분 동안 같은 값으로 반복할 수 있다.

### 8.3 Team PR #18 Pilot (2026-08-14)

PR #18 head `62eb0d8`에 포함된 새 180초 캡처. 레거시 로그와 **같은 펌웨어 1.2.0 / 같은 config hash**이지만, 캡처 프로그램과 세션 메타가 다르므로 조용히 합치지 않는다.

| Session | 조건 | records |
|---|---|---:|
| `M-C0-PILOT-DESKWORK-001` | 좌식 책상 작업, 작은 팔 움직임 | 1,799 |
| `M-C0-PILOT-STATIONARY-001` | 정지 Pilot raw | 1,799 |

ESP capture firmware/config (Pilot session manifest `sensor.firmware_version` / `sensor.config_hash`):

```text
safenest-mr60-esp/1.2.0
config_hash b817e8bfd5e52b18275626f7b6a9bd60098ea4b108428a5aaf63600dbc987834
```

같은 manifest의 `sensor.sensor_firmware_version`은 `UNKNOWN_NOT_REPORTED`다.
이것은 ESP JSON이 MR60 **모듈** vendor firmware 문자열을 넣지 않았다는 세션 메타 기록이다.
ESP 앱 문자열 `safenest-mr60-esp/1.2.0`이 없다는 뜻이 아니고, 모듈 firmware가 존재하지 않는다는 뜻도 아니다.

획득 버전 태그:

```text
PRE_PR18_LEGACY_LOGS
PR18_PILOT_CAPTURE
```

---

## 9. 신호 의미: `breath_phase` vs `breath_rate_raw`

Parser 권위는 **[팀 저장소]** `devices/mmwave/firmware/src/main.cpp`.

| 분류 | 필드 | 뜻 |
|---|---|---|
| `SENSOR_LOWEST_EXPOSED_PHASE_LIKE_SIGNAL` / `PHYSICAL_INTERMEDIATE_SIGNAL` | `breath_phase` (`0x0A13`) | MR60이 밖으로 내보내는 위상형 중간 신호. CSV `resp_phase`와 동일 |
| `VENDOR_DERIVED_OUTPUT` | `breath_rate_raw` (`0x0A14`) | vendor 호흡수. 파형이 아님 |
| `TEAM_DERIVED_OUTPUT` | `breath_rate_filtered` 등 | ESP/팀 후처리 |
| `MODEL_READY_OR_PROCESSED` | BPF_ZSCORE 이후 tensor | Phase-B 입력 |
| `TRUE_RADAR_RAW_SIGNAL` | ADC / IQ / range-bin / raw rFFT | **확인되지 않음** |

`breath_phase`를 확인된 ADC, IQ, range-bin, raw rFFT라고 쓰지 않는다.
JSONL 키에 그런 배열이 없다. 정직한 표현:

```text
MR60-exposed phase-like intermediate signal
```

schema 1.2는 `breath_rate_raw_trusted: false`를 남긴다.

Plain meaning:
레이더가 내보내는 “숨 쉬는 모양의 출렁임”과, 벤더가 계산한 “분당 호흡 횟수”는 다른 물건이다.
Phase B는 출렁임(파형)을 본다.

---

## 10. 시간 의미: telemetry cadence vs fresh phase cadence

이 구분은 현재 `M-C0`의 중심이다.

펌웨어는 radar phase frame마다 JSON을 찍지 않는다.
`mmwave_config.h`의 `kTelemetryIntervalMs = 100`마다 `emitTelemetry()`가 **마지막에 저장된** `breathPhase`를 다시 쓴다.
`breathPhase`와 `phasesUpdatedMs`를 갱신하는 것은 `0x0A13` frame뿐이다.
`phase_age_ms`는 그 마지막 갱신이 telemetry 시각 기준으로 얼마나 오래된지를 기록한다.

```text
TELEMETRY / LOG ROW CADENCE
    VERIFIED ≈ 9.99 Hz (다수 delivery 세션)

FRESH 0x0A13 PHASE-FRAME CADENCE
    NOT YET ESTABLISHED / PARTIAL

30 s / 300 TELEMETRY ROW
    YES (자를 수 있음)

30 s / 300 FRESH breath_phase SAMPLE
    NOT YET ESTABLISHED

Phase-B temporal correspondence
    NOT YET ESTABLISHED
```

```text
JSONL/CSV 줄 속도 ≈ 10 Hz
    ≠
신선한 0x0A13 breath_phase 갱신 속도 ≈ 10 Hz
```

Plain meaning:
컴퓨터가 초당 약 10줄을 쓴다는 사실이, 레이더가 초당 10개의 **새로운** 호흡 위상 값을 줬다는 뜻은 아직 아니다.

추가 규칙:

- 연속된 같은 `breath_phase` 숫자만으로 stale이라고 단정하지 않는다. 실제 위상이 잠시 비슷할 수도 있다.
- `phase_age_ms`는 유용한 freshness 증거다. 그렇다고 모든 frame 도착 시각을 완전 재구성하지는 않는다.
- 31분 로그는 이 함정의 직접 반례다: row는 9.986 Hz, `phase_age_ms` 최대 288,530 ms.

---

## 11. 기존 실측 평가가 내린 결론

평가 보고서 작성 시점 팀 `main`: `fdf34b804f35e5868356f0ed6f804a248aa69131`.

### 11.1 paced 호흡

paced cue는 메트로놈 목표다. 호흡 벨트가 아니다.

| 조건 | phase 주기 추정 | vendor median | 해석 |
|---|---:|---:|---|
| 유효 12 rpm | 12.34 | 14.0 | phase가 cue에 더 가깝다 |
| 15 rpm (07-26 delivery) | 15.00 | 19.0 | vendor가 약 19에 모임 |
| 15 rpm (07-28 explicit) | 15.01 | 19.0 | 같은 방향 |
| 20 rpm deep delivery | 20.00 | 23.0 | offset이 12/15과 다름 |
| 실패한 “12 rpm” 파일 | ≈ 6.06 | 4.0 | cue는 12, 실제 수행은 ≈6 |

```text
intended paced cue
    ≠
actual performed respiration
    ≠
Phase-B NORMAL / RAPID / APNEA
```

“MR60 신호 자체가 원래 ~20 rpm”이라는 문장은 폐기한다.
문서화된 ~19–20 rpm 행동은 주로 **vendor `breath_rate_raw` estimator**다.
15 rpm cue에서 phase ≈ 15.01, vendor median ≈ 19.0이었다.
보편 `+N rpm` 보정은 성립하지 않는다.

### 11.2 D15

오래된 표현 `distance std ≈ 0`을 반복하지 않는다.
after-warmup CSV에서 `distance_cm_raw` sample std ≈ **2.94 cm**, unique 값 3개.
한편 `breath_phase` / `breath_rate_raw` / `heart_rate_raw`는 각각 unique 1개로 freeze.
lock-loss는 맞다. 거리 분산 0은 틀린 요약이다.

### 11.3 현재 데이터가 할 수 있는 일 / 없는 일

할 수 있음:

- producer-code lineage, 필드/스키마 분석
- telemetry cadence와 `phase_age_ms` freshness 분석
- 신호 domain 비교, 실패 모드, paced forensic
- 거리/배치 영향, legacy vs PR18 Pilot 비교
- 전처리/대응 조사
- 대응이 방어 가능할 때만 탐색적 frozen-model inference
- `M-C1` 프로토콜 설계

아직 증명하지 못함:

- 정식 세 클래스 Accuracy/F1
- 임상 apnea
- paced RPM → Phase-A 클래스 자동 부여
- 다피험자 일반화
- 재학습 허가
- 그 자체로 `M-D` 허가

이유: 독립 호흡 정답 부족, 식별 가능한 참가자 `S001` 중심, 신호 대응 미확정, fresh-phase 시간 대응 미확정.

---

## 12. 현재 외부 의존성 — Team PR #18

URL: https://github.com/jinsu1011/safenest-embedded-competition/pull/18

이 핸드오프 작성 시점의 검증된 상태:

```text
title          feat(mmwave): add standalone M-C0 device evidence
state          OPEN
draft          true
merged         false
head           62eb0d867cfa02295c9a1d023b813134c434b8eb
base           5947334d3d0f6c6f7d6100c7ea6af219e5b4c5d5
team main      3d86bf2a7a4e527d7aba2dfabcb087201ffeb46e
new commits after 62eb0d8     none
corrective refinements        NOT committed
```

### 12.1 PR #18이 실제로 추가한 것

펌웨어/`0x0A13`/`0x0A14` parser를 바꾸지 않는다. `main.cpp` blob는 PR head와 당시 team `main`이 동일했다.

추가된 것은 대략:

- `devices/mmwave/device_measurements/` 계약·스키마·validator
- USB JSON pass-through 캡처 도구 `live_mr60_monitor.py`
- 180초 desk-work / stationary Pilot JSONL
- 기존 로그 감사 문서
- 레거시 CSV를 BPF_ZSCORE → locked INT8에 통과시킨 host 벤치마크

신호 의미 분류: **`SIGNAL_SEMANTICS_UNCHANGED`**.
역사 호환: **`BACKWARD_SEMANTICALLY_COMPATIBLE`** (producer). 캡처 도구는 버전 태그가 필요하다.

### 12.2 왜 PR #18이 standalone `M-C0`를 대체하지 않는가

1. standalone `M-C0` 권한은 canonical standalone workflow다. 팀 폴더 이름이 `M-C0`여도 완료가 아니다.
2. 계획된 standalone 산출물(`existing_measurement_inventory.json` 등)이 standalone 저장소에 없다.
3. `M-B12` lock은 `m_c_started: false`를 유지한다.
4. PR #18 QA는 **telemetry row cadence**를 “physical cadence”로 보고하고, `phase_age_ms`를 필수/채점하지 않는다.
5. 레거시 CSV 620 window TFLite invoke는 correspondence gate **이전** 탐색이다.
6. PR는 여전히 draft이고, 아래 교정은 head에 반영되지 않았다.

### 12.3 아직 head에 남아 있는 교정 이슈

독립 리뷰 시점과 현재 head가 같으므로, 다음을 **아직 pending**으로 둔다.

1. telemetry row cadence와 fresh-phase evidence를 QA가 구분하지 않음.
2. `existing_evidence_audit.md`가 D15 `distance std=0`을 반복. standalone 평가는 ≈2.94 cm로 이미 교정함.
3. 620/620 APNEA를 정식 성능처럼 읽히지 않게 경계를 더 분명히 해야 함. 보고서는 Accuracy/F1을 계산하지 않았지만, 탐색 추론 위치는 correspondence 앞이다.
4. `.gitignore`의 `*.jsonl`과 force-add된 `pilot/*.raw.jsonl`, 그리고 “raw는 gitignore”라는 Pilot 보고서 문장이 모순.

이 이슈가 닫히지 않아도 **레거시 바이트의 의미는 바뀌지 않는다.**
다만 새 Pilot을 레거시와 한 덩어리로 취급하거나, PR QA cadence를 fresh 10 Hz 증명으로 쓰면 안 된다.

---

## 13. 620/620 APNEA 관측

PR #18 host 벤치마크가 레거시 delivery CSV 620개 window를 다음 순서로 넣었다.

```text
legacy CSV resp_phase
    ↓
명목 10 Hz interpolation
    ↓
BPF_ZSCORE (locked TRAIN mean/std)
    ↓
frozen INT8 SHA 6dff6aaa…
    ↓
예측: NORMAL 0 / RAPID_OR_ABNORMAL 0 / APNEA 620
```

현재 분류:

```text
EXPLORATORY_PRE_CORRESPONDENCE_INFERENCE
PIPELINE_CORRESPONDENCE_WARNING
DEVICE_DOMAIN_MISMATCH_WARNING
```

이것이 **아닌** 것:

```text
formal MR60 Accuracy
formal F1
M-C2
모델이 깨졌다는 증명
모든 실제 측정이 APNEA라는 증명
```

가능한 원인은 correspondence가 끝날 때까지 미해결이다. 예:

- telemetry row를 신선한 phase처럼 사용
- interpolation이 신호를 바꿈
- `breath_phase`와 Zenodo canonical phase의 단위/스케일 불일치
- 실제 domain gap
- stale/lock-loss 창이 섞임
- 라벨이 모델 클래스가 아님 (보고서는 이 이유로 F1을 계산하지 않음)

이 결과는 correspondence-first 규칙을 **지지**한다. 모델을 바꾸거나 `M-D`를 여는 티켓이 아니다.

---

## 14. 현재 `M-C0` 상태

```text
M-C0:          NOT_STARTED
M-C0A gate:    NOT_STARTED
M-C0B:         NOT_STARTED (그리고 지금은 허가되지 않음)
M-C1:          NOT_STARTED
M-C2:          NOT_STARTED
M-D:           NOT_AUTHORIZED
```

근거:

- standalone에 `m_c0_summary.json` / `offline_contract_correspondence.json` 없음
- `device_domain_handoff.json`: `m_c_started: false`
- 로드맵 checklist 미체크
- 사용자 실행 승인 없음
- Team PR #18은 draft이며 팀 측 증거 번들일 뿐

### 14.1 왜 아직 시작하지 않았는가

`M-C0`는 하드웨어가 없어서 막힌 단계가 아니다. 기존 로그로 forensic을 할 수 있다.
시작하지 않은 이유는 실행 승인과 산출물 계약이 standalone에 아직 열리지 않았고,
Team PR #18을 standalone 완료로 복사하지 않기로 했기 때문이다.

하드웨어 부재는 `M-C1`만 `BLOCKED_HARDWARE`로 표시한다. `M-C0`를 공백으로 되돌리지 않는다.

독립 리뷰는 PR #18을 특성화했다. 그 리뷰는 `M-C0` 실행이 아니다.

---

## 15. `M-C0`가 시작되면 먼저 물을 질문

이 섹션은 향후 실행 지시이다. 이 문서 작업에서 풀지 않는다.

1. Phase-B 학습 표현에 정확히 대응하는 MR60 신호는 무엇인가?
2. telemetry-row cadence를 fresh phase-update cadence와 혼동하고 있지 않은가?
3. 방어 가능한 fresh 신호 의미로 30 s / 300-sample 창을 만들 수 있는가?
4. interpolation이 신호를 물질적으로 바꾸는가?
5. `BPF_ZSCORE` 후 분포가 Phase B와 호환되는가?
6. INT8 양자화 전후 분포는 어떻게 변하는가?
7. 관측된 APNEA collapse는 파이프라인 어느 단계에서 나타나는가?
8. 어떤 레거시 세션이 탐색 비교에 적합하고, 어떤 세션은 아닌가?
9. 어떤 증거에 독립 ground truth가 있고, 어떤 증거에는 없는가?

기계 판독 결정(로드맵 C0A):

```text
signal_semantic_correspondence
cadence_correspondence
thirty_second_window_correspondence
bpf_zscore_input_compatibility
tensor_construction_reproducible
→ AUTHORIZED_FOR_EXPLORATORY_INFERENCE
   또는 BLOCKED_PENDING_SIGNAL_CORRESPONDENCE
```

과학적으로 유효한 `M-C0` 종료 예:

```text
USABLE_FOR_DEVICE_DOMAIN_EXPLORATION = true
FORMAL_MODEL_VALIDATION_READY = false
EXPLORATORY_INFERENCE_ALLOWED = false
```

예측을 만들지 않아도 `M-C0`는 성공할 수 있다.

### 15.1 `M-C0` 동안 하지 말 것

```text
재학습하지 않는다.
frozen 후보를 바꾸지 않는다.
LOCKED_TEST를 재사용·튜닝하지 않는다.
정식 Accuracy/F1을 독립 라벨 없이 발표하지 않는다.
paced 파일명을 Phase-B 정답으로 쓰지 않는다.
PR #18 TFLite 결과를 M-C2로 승격하지 않는다.
M-D를 시작하지 않는다.
```

---

## 16. 미래 `M-C1` 측정이 보존해야 할 것

`M-C1`은 레거시 분석과 분리된 **신규** 수집이다. `M-C0` gap이 프로토콜을 정한다.
이 문서가 클래스 임계값을 새로 만들지 않는다.

최소 보존:

```text
verbatim MR60/ESP JSON (재샘플·결측 채움 없음)
ts_monotonic_ms
seq
phase_age_ms
breath_phase
breath_rate_raw   (파형과 분리 기록)
firmware_version
config_hash
capture program identity / commit
team_repo_commit
session_id
subject_id (가명, subject-wise split 가능)
sensor/device_id
distance / posture / orientation / placement
other-person / environment
intended condition
actual observed / reference condition
lock / degraded / error
acquisition_schema_version
PRE_PR18_LEGACY vs PR18_PILOT vs 이후 M-C1 태그
```

정식 성능을 말하려면:

```text
측정 시점에 기록된 독립 호흡 참조
나중에 기억으로 재구성한 정답이 아님
```

사람 대상 수집은 동의·개인정보 정책을 따른다.
자발적 breath-hold를 임상 apnea로 쓰지 않는다.
실패·약세 세션은 삭제하지 않는다.

---

## 17. `M-C2` 진입 조건

정식 metric은 여기에만 속한다. `M-C0`/`M-C0B`/PR #18 host invoke가 아니다.

필요:

- 규약 제어 세션 (`M-C1`)
- 검증된 신호 대응
- 재현 가능한 tensor 구성
- frozen Phase-B 모델 (SHA `6dff6aaa…`)
- 불변 평가 정책
- 신뢰할 수 있는 참조 라벨/상태
- subject/session 분리
- exclusion 규칙을 평가 전에 고정
- 평가 데이터로 침묵의 튜닝 금지

```text
poor device behavior
    ≠
authorization to modify Phase B
```

`MR60_REAL_SENSOR_VALIDATED`는 이 단계가 요구를 충족하고 한계를 정직히 보고한 뒤에만 사용한다.

---

## 18. `M-D` 허가 경계

`M-D`는 gap-driven 적응/데이터 확장이다. `M-C0`/`M-C1`/`M-C2` 작업 단위가 아니다.

열 수 있는 조건:

```text
M-C2가 DEVICE_DOMAIN_GAP_OBSERVED를 측정하고
한계를 보고하고
별도 승인이 있다
```

열리지 않는 조건:

```text
PR #18이 620/620 APNEA를 냈다
device 성능이 나빠 보인다
하드웨어가 아직 없다
팀 폴더 이름이 M-C0다
```

`M-D` 안에서만 검토할 수 있는 예: 데이터 확장, 전처리 재검토, 후보 교체, INT8 재교정.
지금 이 목록을 실행하지 않는다.

---

## 19. 다음 agent 실행 체크리스트

```text
[권한]
[ ] 작업 저장소가 standalone sheepmeat/test 인지 확인
[ ] origin/main에서 mmWave 전용 docs/feature 브랜치를 따는지 확인
[ ] CO₂/Thermal/Integration 브랜치를 섞지 않는지 확인

[고정 후보]
[ ] INT8 SHA 6dff6aaa… 가 M-B12 lock과 같은지 확인
[ ] 입력 [1,300,1] / BPF_ZSCORE / 클래스 순서 확인
[ ] APNEA = voluntary breath-hold proxy 확인
[ ] LOCKED_TEST reopen 금지 확인

[실측 해석]
[ ] breath_phase ≠ breath_rate_raw 확인
[ ] telemetry 10 Hz ≠ fresh 0x0A13 10 Hz 확인
[ ] paced cue ≠ Phase-B 클래스 확인
[ ] D15 distance std≈2.94 cm, vitals freeze는 별개 확인
[ ] 31분 로그의 phase_age_ms 반례를 확인

[PR #18]
[ ] GitHub에서 draft/head SHA를 다시 확인 (이 문서는 작성 시점 스냅샷)
[ ] PR #18을 standalone M-C0 완료로 복사하지 않음
[ ] 620/620 APNEA를 M-C2/재학습 근거로 쓰지 않음
[ ] legacy vs Pilot을 버전 태그로 분리

[M-C0를 시작할 권한이 생긴 뒤에만]
[ ] 기존 로그 forensic inventory
[ ] telemetry vs fresh-phase vs stale 분리 측정
[ ] C0A correspondence JSON 결정
[ ] 허가가 있을 때만 exploratory inference
[ ] 독립 검토 후 M-C1
```

---

## 20. 하지 말 것

```text
DO NOT retrain during M-C0.

DO NOT change the frozen Phase-B candidate because device-domain
      performance looks poor.

DO NOT map paced 12/15/20 rpm directly to Phase-B NORMAL/RAPID/APNEA.

DO NOT treat breath_rate_raw as the AI waveform.

DO NOT treat telemetry 10 Hz as proven fresh phase 10 Hz.

DO NOT access/reuse Phase-B LOCKED_TEST for M-C work.

DO NOT mix CO2/Thermal/Integration feature branches into mmWave work.

DO NOT use M-D adaptation unless separately authorized.

DO NOT treat Team PR #18 as standalone M-C0 completion.

DO NOT describe APNEA-proxy as clinical apnea.

DO NOT claim MR60 or Raspberry Pi validation without those measurements.

DO NOT silently pool PRE_PR18_LEGACY_LOGS with PR18_PILOT_CAPTURE.
```

---

## 21. 핵심 증거·문서 색인

### Standalone — 이 핸드오프의 상위 문서

| 문서 | 역할 |
|---|---|
| `docs/20260810_ChatGPT_SafeNest_Multisensor_Parallel_Execution_Roadmap_01.md` | master roadmap |
| `docs/20260806_ChatGPT_SafeNest_mmWave_Execution_Sequence_01.md` | mmWave A–E 상세 |
| `docs/MMWAVE_PHASE_B_OVERVIEW.md` | Phase B 개요 |
| `docs/reports/20260814_SafeNest_mmWave_Existing_Team_MR60_Data_Evaluation_01.md` | 기존 실측 기술 평가 |
| `docs/reports/20260814_SafeNest_mmWave_Team_MR60_Data_Evaluation_KR_01.md` | 팀 한글 가이드 |
| `docs/reports/20260813_Cursor_M-B12_mmWave_Phase_B_Offline_Final_Report_01.md` | Phase B 종료 보고 |
| `docs/reports/20260813_Cursor_M-B11_mmWave_Offline_Candidate_Artifact_Lock_01.md` | artifact lock |
| `docs/reports/20260812_Codex_M-B10B_One_Time_Locked_Test_Final_Evaluation_01.md` | LOCKED_TEST incident |
| `docs/reports/20260808_Antigravity_A6_Full_Conversion_Integrity_Audit_01.md` | A6 |
| `docs/reports/20260808_Antigravity_A5_Subject_Split_Provenance_01.md` | A5 |
| `AGENTS.md` | canonical root / proxy apnea / subject split |

이 문서는 로드맵이 아니다. 평가 보고서의 대체본도 아니다. **이어서 작업하기 위한 현재 상태 핸드오프**다.

### Standalone — machine-readable lock

```text
datasets/mmwave/manifests/M-B12_phase_b_offline_final/locked_candidate_summary.json
datasets/mmwave/manifests/M-B12_phase_b_offline_final/final_evaluation_summary.json
datasets/mmwave/manifests/M-B12_phase_b_offline_final/claim_boundary.json
datasets/mmwave/manifests/M-B12_phase_b_offline_final/device_domain_handoff.json
datasets/mmwave/manifests/M-B12_phase_b_offline_final/scientific_limitations.json
datasets/mmwave/manifests/a4_label_pilot/label_mapping_profile.json
datasets/mmwave/splits/mmwave_real_subject_split_v1.json
```

### Team — 물리 증거 위치

```text
devices/mmwave/firmware/src/main.cpp
devices/mmwave/firmware/include/mmwave_config.h
devices/mmwave/firmware/csv/2026-07-26_han_junwoo_delivery_v2/
devices/mmwave/firmware/logs/final/
devices/mmwave/device_measurements/     (PR #18, draft)
```

---

## 22. 현재 미해결 한계

다음만 `NOT_YET_ESTABLISHED` / `UNKNOWN`으로 남긴다.

- `breath_phase`와 Zenodo canonical phase의 신호-의미 대응
- fresh `0x0A13` cadence가 명목 10 Hz인지
- 30 s / 300 **fresh** sample 창 구성 가능 여부
- interpolation의 물질적 영향
- BPF_ZSCORE/INT8 이후 장치 분포 호환
- 620/620 APNEA collapse의 단계별 원인
- 독립 호흡 참조가 있는 세션
- 다피험자 device-domain 일반화
- Raspberry Pi / ESP 배포 latency
- Team PR #18 교정·병합 여부 (작성 시점: 미병합 draft)
- PR #18 Pilot의 `sensor_firmware_version` 필드: session manifest에 `UNKNOWN_NOT_REPORTED`로 기록됨. ESP `firmware_version` `safenest-mr60-esp/1.2.0`과 혼동하지 않는다. 모듈 vendor firmware identity는 이 필드로 확인되지 않았고, ESP 앱 버전은 확인된다.

추측으로 채우지 않는다.

---

## 문서를 읽은 뒤 반드시 구분해야 하는 여덟 가지

1. **`breath_phase` ≠ `breath_rate_raw`**: 위상형 파형 vs vendor 호흡수.
2. **telemetry 10 Hz ≠ fresh phase 10 Hz**: 줄 속도 vs 새 위상 갱신.
3. **paced cue ≠ Phase-B 클래스**: 12/15/20 rpm은 NORMAL/RAPID/APNEA가 아니다.
4. **APNEA-proxy ≠ clinical apnea**: 숨 참기 대리지표다.
5. **offline candidate ≠ MR60/Pi validation**: SHA `6dff6aaa…`는 장치 검증이 아니다.
6. **Team PR #18 ≠ standalone M-C0**: 팀 증거 번들·draft다.
7. **620/620 APNEA ≠ M-C2**: correspondence 이전 탐색 경고다.
8. **device 성능 나쁨 ≠ Phase B 수정 허가**: `M-D`는 별도 승인이다.

---

## 23. 한 페이지 요약

```text
지금 모델은?
= 명목 10 Hz 30초(300 sample) 호흡 위상 파형을 BPF_ZSCORE 후 INT8 Conv1D로
  NORMAL / RAPID_OR_ABNORMAL / APNEA-proxy 세 클래스로 계산한다.

무엇이 얼려 있나?
= 후보 M-B3_CONV1D_GAP_BASELINE_seed42_M-B5_CAL_CLASS_BALANCED_120
  INT8 SHA 6dff6aaa72c79d76715d40cf7e32bb1e6cd9b2c2e3ac78eaf2fda737561430c5

offline 숫자는?
= 재사용된 LOCKED_TEST에서 Acc 0.56, Macro F1 0.495.
  pristine 최종 시험이 아니고, MR60 성능이 아니다.

팀 실측은?
= 가치 있는 장치 증거. M-C0 forensic 입력.
  정식 검증셋·재학습셋이 아니다.

핵심 함정은?
= 로그가 초당 10줄이어도 위상 값이 오래될 수 있다.
  벤더 호흡수가 ~19 rpm이어도 위상 파형은 15 rpm cue를 따라갈 수 있다.

PR #18은?
= 같은 펌웨어의 Pilot 캡처와 QA 도구. parser 변경 없음.
  작성 시점 OPEN DRAFT. standalone M-C0 완료가 아님.

다음 공식 단계는?
= standalone M-C0 forensic → correspondence gate.
  그 전에 재학습·모델 변경·M-C1/M-C2/M-D를 시작하지 않는다.
```

---

## 24. 문서 경계

이 문서 작성으로 다음 작업은 시작되지 않았다.

- standalone `M-C0` 실행
- Team PR #18 수정
- 새 물리 측정
- frozen 모델 추론
- 재학습 / 전처리 변경 / INT8 재교정
- 로드맵 본문 재설계
- `M-C1` / `M-C2` / `M-D`
- LOCKED_TEST 재개방

위 작업은 각각 명시적 승인 후에만 진행한다.
