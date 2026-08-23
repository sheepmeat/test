# SafeNest mmWave V2 M-PV1 공통 데이터·표현·타깃·abstention 계약 동결 보고서

- 단계: **M-PV1 — Public Multidomain Common Data / Representation / Target / Abstention Contract Freeze**
- 기준: `origin/main` `e84d802e5b9aa28e6729a02b304f1f70043f89c3`
- 브랜치: `feature/mmwave-v2-m-pv1-common-contract`
- Gate: **`PASS_WITH_LIMITATIONS`**
- `M_PV1_READY_FOR_M_PV2`: **YES**

## 1. 범위와 선행 조건

이번 단계는 M-PV2가 추가 의미 결정을 하지 않고 학습을 시작할 수 있도록 입력·타깃·분할·품질·source balancing 계약을 동결하는 단계다. 모델 학습, 모델/seed 선택, accuracy 비교, probability/persistence threshold tuning, calibration, INT8/TFLite, D2 payload 접근, MR60 supervised physiology는 수행하지 않았다.

`M-PV0`, `D0`, `D1`, `R1`, `R2`, `R3`, `Q2`, `I1`의 승인된 machine-readable evidence를 그대로 상속했다. I2는 main에 병합되어 있지만 직접 선행 조건으로 사용하지 않았고, I3 조상은 사용하지 않았다. D3 adapter는 없어 `NOT_INCLUDED_NON_BLOCKING`으로 기록했다.

## 2. 데이터 역할과 분할

### D0

`MMWAVE_V2_D0_SUBJECT_SPLIT_V1`을 변경하지 않았다. M-PV1 model-ready example은 D0 `TRAIN` 66 subject / 318 base contexts만 사용한다. D0 `VAL`과 `D0_SUBJECT_HELDOUT`은 동결·후속 역할만 기록했고, M-N6에서 제외된 16 subject는 사용하지 않았다. MR60은 D0/D1 physiology label로 사용하지 않았다.

R3의 30초 base context는 그대로 보존하되, authoritative A6 voluntary non-breathing interval과 context의 교집합 안에서 **처음 5초가 event 안에 완전히 들어가는 경우**에만 event-relative example을 추가했다. 이 방식으로 D0 whole-window `ABSENT=0`이라는 사실을 숨기지 않으면서 5초 `BREATHING_REFERENCE_ABSENT` 133개를 확보했다. 레이더 amplitude, R2 feature, 모델 출력으로 event를 만들지 않았다. 5초 미만 교집합 23개는 `AMBIGUOUS`로 남겼다.

### D1

동일한 subject를 녹음 단위로 쪼개지 않고 `MMWAVE_V2_M_PV1_D1_DEV_SUBJECT_SPLIT_V1`로 고정했다. namespace `MMWAVE_V2_M_PV1_D1_DEV_SPLIT`, seed `20260823`, SHA-256 subject hash로 8/3 subject를 할당했다.

- `D1_DEV_TRAIN`: `D1_PERSON_01`, `02`, `04`, `05`, `06`, `07`, `08`, `10`
- `D1_DEV_VAL`: `D1_PERSON_03`, `09`, `11`

성능을 보고 seed를 고르거나 D2와 같은 가짜 final test를 만들지 않았다. split 후 조건 커버리지는 manifest에 별도로 기록했다.

## 3. D1 reference materialization

고정된 canonical Figshare payload `10.6084/m9.figshare.9691544.v1` / file ID `17357702`만 사용했다. 크기 `583,572,264` bytes, MD5 `801c13ae6daef54584ee4ba8fbabed19`, SHA-256 `3869fb70a3dda0d810d97594399789e76d9c9e59627515c20170b83e3d915836`가 확인됐다. canonical D1 adapter로 265개 녹음을 모두 읽었고 block 0개였다.

`respiration` synchronized channel을 파형으로 읽되, raw archive와 extracted waveform은 ignored 경로에만 두었다. 커밋한 것은 compact target/통계/provenance뿐이다. 10 Hz anti-aliased `resample_poly(kaiser β=8.6)` 후 30초 reference window에서 Welch 0.1–0.7 Hz band, 고정 peak fraction/자기상관 engineering guard를 적용했다. 이는 radar나 모델 결과로 튜닝하지 않았다.

- 30초 model-ready D1 contexts: 244
- 30초 미만 reference/feature audit-only: 21
- D1 `PRESENT`/RR available: 236
- D1 reference periodicity ambiguous: 8
- D1 temporal hold: `UNAVAILABLE` (source `apnea` 문자열만으로 onset/recovery를 만들지 않음)

D1의 `apnea`/breath-hold protocol은 provenance로만 유지했다. 약한 reference는 `ABSENT`가 아니라 `AMBIGUOUS` 또는 `TARGET_UNAVAILABLE`이다.

## 4. 공통 입력·표현 계약

공통 개발 rate는 **10 Hz**, model context는 **30초/300 sample**, evaluation stride는 **5초**로 동결했다. D0는 원래 10 Hz timing을 사용하고, D1은 native 500/2000 Hz에서 anti-alias 후 10 Hz로 내려온다. 0.1–0.7 Hz respiratory band와 결정적 on-device 후보 비용을 만족하며 model accuracy로 고른 값이 아니다.

- `PROFILE_A_FEATURE_F2_V1`: R2 F2 spectral+autocorrelation scalar 25개 고정 순서 + F3 quality sidecar
- `PROFILE_B_TRACE_F3_R1_V1`: R1/F3 trace `[B,300,1]`, oldest→newest, 별도 valid mask, 12개 scale descriptors + quality descriptors
- `PROFILE_C_HYBRID_TRACE_PLUS_F2_V1`: 위 두 profile의 결정적 조합만 조건부 허용
- F1: `ABLATION_BASELINE_ONLY`
- F2: active scalar candidate
- F3: active trace/quality candidate

native MAD, robust RMS/range, energy/log-energy, respiratory-band energy/log-energy, quality status를 유지한다. `WINDOW_LOCAL_MAD_DIVIDE_ONLY=NO`, source-specific gain matching=NO, low-amplitude auto-normalization=NO다. fitted feature scaler가 필요하면 M-PV2에서 TRAIN membership만으로 fit한다.

입력 tensor는 FLOAT32 개발 계약이다. invalid/gap 구간을 정상 signal로 zero-fill하거나 fake physiological padding하지 않는다. Q2 hard gate가 먼저 실행되고, learned soft-quality score는 hard invalid를 override할 수 없다. presence는 production `human_detected_raw` 외부 authority이며 D0/D1 amplitude로 학습하지 않는다.

## 5. 공통 타깃 계약

`MMWAVE_V2_M_PV1_TARGET_MAPPING_PROFILE_V1`은 직접 `NORMAL/RAPID/APNEA` 3-class를 primary output으로 만들지 않는다.

### Breathing evidence

공통 상태는 `PRESENT / ABSENT / AMBIGUOUS / TARGET_UNAVAILABLE`다. D0는 A6/Movesense reference와 authoritative hold interval을 사용하고, D1은 synchronized respiration reference를 사용한다. D0 whole-window ABSENT는 0이지만 event-relative 5초 ABSENT 133개로 target granularity를 정정했다. D1은 absence를 추측하지 않으므로 ABSENT 0이 정상적인 provenance 결과다.

### RR

`rr_bpm` continuous float와 `validity`, `reference_source`, `reference_method`, `unavailable_reason`를 함께 보낸다. `rr_bpm=null`이 unavailable 표현이며 0 sentinel은 금지한다. D0 method는 inherited A4 Movesense chest-ACC spectral peak, D1 method는 `D1_RESPIRATION_WELCH_PERIODICITY_V1`다.

### Temporal hold

자발적 breath-hold **proxy**의 event-relative semantics다. D0는 baseline/hold interval/onset/recovery를 보존하고 133 positive interval과 162 non-event, 156 ambiguous를 기록한다. D1은 within-recording onset/recovery가 방어되지 않아 unavailable이다. 최종 persistence threshold는 clinical apnea duration이 아니라 이후 development-only calibration 경계로 남겼다.

각 example에는 `breathing_supervision_eligible`, `rr_supervision_eligible`, `temporal_hold_supervision_eligible`, `quality_supervision_eligible`를 별도로 둔다. 한 task의 unavailable/ambiguous가 다른 task의 target을 강제로 만들지 않는다.

## 6. Quality / abstention과 source balancing

Q2 precedence를 그대로 사용한다.

```text
presence → input availability/quality → physiology → temporal composition
```

nonfinite, timestamp invalid/non-monotonic, stale/freeze, large gap, exact flat은 `INPUT_UNAVAILABLE`로 fail closed한다. Q1/Q2 synthetic corruption은 quality/abstention 예시로만 사용하며 APNEA/ABSENT physiology label을 다시 쓰지 않는다. synthetic recipe 상한은 task별 clean example의 10%로 고정하고 validation accuracy로 조정하지 않는다.

M-PV2 source weight는 D0 `0.75`, D1 `0.25`로 고정한다. source 내부 subject inverse-eligible-count weighting을 사용하고, D1 11 subject를 D0 window 수까지 맹목적으로 oversample하지 않는다. context/recording lineage와 task mask를 유지한다.

## 7. D2와 제한사항

D2는 `LOCKED_PUBLIC_CROSS_DEVICE_TEST` custody state만 읽었다.

- semantic access: NO
- feature extraction: NO
- target use: NO
- inference count: 0
- selection use: NO

주요 제한은 D1 temporal hold unavailable, 30초 미만 D1 21개 audit-only, D1 respiration native unit/per-sample timestamp 미확정이다. D0 whole-window ABSENT 0은 숨기지 않고 event-relative target으로 재정의했다. 따라서 M-PV2는 이 계약대로 breathing/RR multi-task를 시작할 수 있지만, clinical apnea 성능을 주장할 수 없다.

## 8. 결정성 및 산출물

생성기를 두 임시 출력에 반복 실행해 JSON byte/checksum이 동일함을 확인한 뒤 최종 manifest를 생성했다. wall-clock 값은 hash에 넣지 않았다. compact manifest만 커밋하며 raw D1 archive/waveform, model binary, D2 payload는 커밋하지 않는다.

기계 판독 산출물은 `datasets/mmwave/manifests/M-PV1_public_multidomain_contract/`와 `config/mmwave/m_pv1_public_multidomain_contract.json`에 있다. 생성기와 focused validator는 각각 `scripts/mmwave_m_pv1_public_multidomain_contract.py`, `scripts/validate_mmwave_m_pv1_public_multidomain_contract.py`다.

M-PV1 결과: **`PASS_WITH_LIMITATIONS`**, **M-PV2 ready = YES**. 이번 단계에서는 학습·선정·튜닝·양자화를 시작하지 않는다.
