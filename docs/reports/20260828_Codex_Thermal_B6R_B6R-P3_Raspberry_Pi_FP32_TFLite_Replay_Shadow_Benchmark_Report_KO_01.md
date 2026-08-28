# SafeNest Thermal B6-R B6R-P3 Raspberry Pi FP32 TFLite Replay & Shadow Benchmark 실행 보고서

## 1. 작업 개요

| 항목 | 값 |
|---|---|
| 날짜 | `2026-08-28` |
| Stage | `B6R-P3 — Raspberry Pi FP32 TFLite Replay & Shadow Benchmark` |
| 브랜치 | `feature/thermal-b6r-development` |
| 시작 local HEAD | `83aa753941350f1becd046305532b73a393a0528` |
| 시작 origin HEAD | `83aa753941350f1becd046305532b73a393a0528` |
| 종료 HEAD | P3 delivery commit — 최종 Git 전달 단계에서 SHA 확인 |
| 사용자 승인 범위 | 이 단일 P3 단계만 실행 |
| 최종 상태 | `BLOCKED_HARDWARE` |

이번 실행의 목적은 이미 PASS한 B6R-P2 FP32 TFLite artifact를 Raspberry Pi에서 고정 DEVELOPMENT fixture로 replay하고, latency·resource·stability·determinism을 `SHADOW_ONLY` 경계 안에서 측정할 수 있는 계약과 실행 도구를 확정하는 것이었다. Raspberry Pi target에 접근할 수 없었으므로 target 수치를 생성하거나 desktop 수치로 대체하지 않았다.

명시적으로 실행하지 않은 범위는 P4, 후속 stage, MI48 본선 재개, 재학습, quantization, production/default runtime 통합, safety 판단, real-fall/physical validation, competition lock이다.

## 2. 선행 상태와 적용 범위

MI48 본선과 public-data 보조 흐름은 별도다. P3의 `BLOCKED_HARDWARE`는 B6R-0~B6R-14 본선 gate를 변경하지 않는다.

| 흐름 | Stage | 상태 | P3 진입 시 확인 |
|---|---|---|---|
| MI48 본선 | `B6R-0` | `FAIL` | 유지 |
| MI48 본선 | `B6R-1` | `INCONCLUSIVE` | 유지 |
| MI48 본선 | `B6R-2` | `BLOCKED` | 유지 |
| MI48 본선 | `B6R-3~B6R-14` | `NOT_STARTED` | 유지 |
| Public 보조 | `B6R-P0` | `PASS_WITH_LIMITATIONS` | 동일한 public SDT identity 상속 |
| Public 보조 | `B6R-P1` | `PASS_WITH_LIMITATIONS` | 동일한 pooled MLP artifact 계보 상속 |
| Public 보조 | `B6R-P2` | `PASS` | exact FP32 TFLite artifact 상속 |
| Public 보조 | `B6R-P3` | `BLOCKED_HARDWARE` | 본 보고서 결과 |

## 3. P0→P2 계보와 입력 계약

| 항목 | 상속한 값 |
|---|---|
| dataset | `PUBLIC_SDT_48000_THERMAL_ONLY_V1` |
| preprocessing | `PUBLIC_SDT_BILINEAR_62X80_FRAME_MINMAX_V1` |
| label mapping | `SDT_POSTURE_TO_SAFENEST_3CLASS_PROXY_V1` |
| class order | `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL_PROXY` |
| P0 split | TRAIN `32,000`, DEVELOPMENT `8,000`, LOCKED_PUBLIC_TEST `8,000` |
| P3 fixture role | `DEVELOPMENT` only |
| P3 fixture | P2 parity manifest에서 상속한 고정 `48` samples |
| P2 parent parity manifest SHA-256 | `5534054955a12e5853ecb013e54da203c8c4e14cf2a66d0e3cd383dd6c00193b` |
| P3 canonical fixture SHA-256 | `b2fbac76e115042899b93a4ca29f0f23612e2703bb5730714b768454e7aa0b34` |

재분할·재선정·tuning은 수행하지 않았다. P3 runner는 P2 parity manifest의 48개 sample record와 P0 validation payload만 사용하도록 고정되어 있다. `LOCKED_PUBLIC_TEST` array는 열지 않았고, sample을 읽거나 metric을 계산하지 않았다.

P3 preprocessing latency의 정의는 P0 preprocessing을 다시 수행하는 시간이 아니다. P2 canonical float32 입력의 shape `[1,62,80,1]`, dtype `float32`, finite 값, `[0,1]` 범위, contiguous 여부를 확인해 interpreter ingress tensor를 만드는 시간만 측정하도록 계약했다. 따라서 PNG resize 시간은 이번 evidence에 포함되지 않는다.

## 4. P0 source archive identity audit

P0 source logical location은 `WORKSPACE_THERMAL_DATASET_ARCHIVES`로 기록했다. 기존 workspace의 source archive를 read-only로 직접 SHA-256·size 계산했으며, 추출·재압축·rewrite·source 파일 변경은 수행하지 않았다. 6개 archive 모두 P0 registry와 일치했다.

| archive | size (bytes) | SHA-256 | registry |
|---|---:|---|---|
| `test.zip` | `1,740,348,425` | `3a838bd70835e579ecfaa820a6c0b4cbc6ba7b76729417c73845f0c959281449` | PASS |
| `train.zip.001` | `4,194,304,000` | `9dd2f944f43209dd44463956b7b34030daecc22bf49050478e77aae27c48dbc4` | PASS |
| `train.zip.002` | `4,194,304,000` | `91be187a432e21c6020928d115d1394ccf540cc6addac8f064a7b181cabe2259` | PASS |
| `train.zip.003` | `4,194,304,000` | `a2e263e0a9024363d787a335ad8641d2a73ee61129d7cb2eb1cffa32b16e1187` | PASS |
| `train.zip.004` | `1,408,015,891` | `406160460568f387b9a84e392430ed2afe57aeb055d073ba93f722c3b0d3b071` | PASS |
| `validation.zip` | `3,492,475,558` | `06d52e24163d1fe243ebfbdb7d2dcef33fcc0a5ed0531ad81621ec1490af4f8f` | PASS |

결과: `6/6`, P0 source immutability `PASS`, source root 및 machine-local address는 portable evidence에 저장하지 않았다.

## 5. P2 exact artifact identity

| 항목 | 검증값 |
|---|---|
| artifact | `models/thermal/public_sdt/public_sdt_pooled_mlp_fp32_tflite_v1.tflite` |
| size | `70,592 bytes` |
| SHA-256 | `f88d65d76dbb21862e1f3cdff17cefb038a432047ded6ac8d5563bc8bc8c52ff` |
| input | `[1,62,80,1]`, `float32` |
| output | `[1,3]`, `float32` |
| quantization | `NONE` |
| class order | `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL_PROXY` |
| default activation | `false` |
| safety authority | `false` |
| deployment mode | `SHADOW_ONLY` |

P3 artifact audit와 P2 validator에서 exact SHA, size, live tensor metadata, FP32/no-quantization, class order, default/safety/shadow identity를 모두 재확인했다.

## 6. Raspberry Pi 접근성 audit

기존 SSH configuration만 read-only로 조사했다. configured candidate는 `2`개였고, 명시적 user가 있는 후보는 `1`개였다. 명시적 user가 있는 기존 설정에 대해 `BatchMode`·public-key only probe를 한 번 수행했으나 `SSH_CONNECT_TIMEOUT`으로 종료됐다.

- password 또는 credential guessing: 수행하지 않음
- private key 내용 읽기: 수행하지 않음
- `known_hosts` 변경: 수행하지 않음
- target address를 tracked evidence에 저장: 수행하지 않음
- Raspberry Pi identity / OS / kernel / CPU / Python / interpreter inventory: 확인 불가
- target availability: `false`

따라서 stage 상태는 `BLOCKED_HARDWARE`로 기록했다. desktop에서 P3 runner를 target으로 가장하지 않도록 non-Raspberry-Pi host에서는 `NON_TARGET_HOST_REFUSED`로 중단된다. desktop latency·resource·stability 결과는 target 결과로 저장하지 않았다.

## 7. P3 contract와 tooling

다음 파일을 추가했다.

- `config/thermal/b6r_p3_raspberry_pi_fp32_tflite_replay_shadow_benchmark_contract.json`
- `scripts/benchmark_thermal_b6r_p3_rpi.py`
- `scripts/validate_thermal_b6r_p3.py`
- `tests/test_thermal_b6r_p3.py`

계약에 고정한 핵심은 다음과 같다.

- interpreter 우선순위: `ai_edge_litert.interpreter` → `tflite_runtime.interpreter` → `tensorflow.lite.Interpreter`
- interpreter thread count: `1`
- fixed replay: warmup `20`, configured measurement `480` (`48 samples × 10 cycles`)
- timer: `time.perf_counter_ns`
- latency fields: preprocessing ingress, inference, total의 count/mean/median/p50/p95/p99/min/max
- prolonged replay: 최소 `1,800 seconds` (`30 minutes`), 첫 실패 후 자동 restart 금지
- resource fields: RSS, CPU utilization, CPU temperature; optional load/memory/throttling은 unavailable 허용
- determinism: 동일 interpreter instance `3`, repeated model loads `3`, child process `1`
- 사전 고정 tolerance: output max abs `1e-6`, output mean abs `1e-7`, prediction agreement `1.0`, mismatch `0`
- target 미접근 시 모든 target metric: `NOT_MEASURED_ON_TARGET`

P3 manifest에는 contract snapshot, artifact/source/fixture/access audit, target environment/interpreter inventory, latency/resource/stability/determinism evidence, shadow/locked-test audit, run summary, replay manifest, validation result, checksum을 저장했다. raw P0 data를 복사하지 않았다.

## 8. Target measurement 결과

### 8.1 Latency

| 항목 | configured | p50 | p95 | p99 | 실제 target 측정 |
|---|---:|---|---|---|---|
| preprocessing ingress | 480 | `NOT_MEASURED_ON_TARGET` | `NOT_MEASURED_ON_TARGET` | `NOT_MEASURED_ON_TARGET` | 아니오 |
| inference | 480 | `NOT_MEASURED_ON_TARGET` | `NOT_MEASURED_ON_TARGET` | `NOT_MEASURED_ON_TARGET` | 아니오 |
| total | 480 | `NOT_MEASURED_ON_TARGET` | `NOT_MEASURED_ON_TARGET` | `NOT_MEASURED_ON_TARGET` | 아니오 |

mean/median/min/max/count도 동일하게 `NOT_MEASURED_ON_TARGET`이다. latency threshold는 이 단계에서 정의하지 않은 값으로 `NOT_DEFINED_BY_THIS_STAGE`다. desktop 수치는 기록·대체하지 않았다.

### 8.2 Resource와 environment

RSS, CPU utilization, CPU temperature는 모두 `NOT_MEASURED_ON_TARGET`이다. available memory, system load, thermal throttling은 `NOT_AVAILABLE`이다. hostname, OS distribution, kernel, architecture, Raspberry Pi model, Python version, CPU information도 `NOT_AVAILABLE`이다. `desktop_substitution_used=false`다.

### 8.3 30분 stability

minimum duration `1,800 seconds`를 contract에 고정했지만 target이 없어서 duration, inference count, failed inference, exception, NaN/Inf, shape/dtype violation, latency drift, RSS/temperature peak, unexpected termination은 모두 `NOT_MEASURED_ON_TARGET`이다. `restarted_after_first_failure=false`로 기록했다.

### 8.4 Determinism

same-instance, repeated-load, process-reexecution 모두 `NOT_MEASURED_ON_TARGET`이다. tolerance는 측정 전에 max abs `1e-6`, mean abs `1e-7`, agreement `1.0`, mismatch `0`으로 고정했다.

## 9. Locked test와 default/runtime 경계

### 9.1 LOCKED_PUBLIC_TEST audit

```text
array open count: 0
sample read count: 0
path configured: false
metrics computed: false
used for selection/tuning: false
```

### 9.2 Legacy/default audit

| 보호 대상 | SHA-256 | 결과 |
|---|---|---|
| `models/model_manifest.json` | `d55a1bce18107f85f86b48748b48e9bb25873572b849d69c3ab42fddb0a6a97b` | 변경 없음 |
| `models/thermal/thermal_fall_int8_v0.1.0.tflite` | `5b56da8d127ccef85f30b6459cc0cfe2d86490e41f3caa5bd2a7b70bbc46ae84` | 변경 없음 |
| `inference/thermal_interpreter.py` | `8ed4093051f31be0fc2b1cd8b1b8e2d72501af63eb2dd4462c9e8520b240a087` | 변경 없음 |

P3는 `models/model_manifest.json`을 읽어 default model을 선택하지 않으며, 기존 interpreter/runtime selector를 변경하지 않았다. P2 artifact는 명시적 opt-in shadow runner에서만 사용한다. rollback target은 기존 legacy model이며, runner를 중지하면 된다.

## 10. 검증 및 테스트

| 검증 | 결과 |
|---|---|
| P3 Python compile | PASS |
| P3 focused unittest | `6 tests`, `6 pass`, `0 fail` |
| P3 blocked-evidence validator | `13 checks passed`, `0 failed`, process exit `0`, stage status `BLOCKED_HARDWARE` |
| P2 validator | `16 checks passed`, `0 failed`, process exit `0` |
| P0/P1/P2/legacy regression | `22 tests`, `20 pass`, `2 skipped`, `0 fail` |
| evidence checksum audit | PASS |
| absolute path persistence audit | PASS |
| `git diff --check` | PASS |

P3 validator의 13개 구조 검증은 통과했지만, 그것은 blocked 상태의 증거가 계약에 맞게 명시되었음을 뜻한다. Raspberry Pi target metric의 PASS를 뜻하지 않는다.

실행한 핵심 명령은 다음과 같다.

```powershell
git fetch origin
git switch feature/thermal-b6r-development
git pull --ff-only origin feature/thermal-b6r-development

.\.venv\Scripts\python.exe scripts\benchmark_thermal_b6r_p3_rpi.py `
  --prepare-blocked-evidence `
  --target-probe-status SSH_CONNECT_TIMEOUT `
  --configured-target-count 2 `
  --explicit-user-target-count 1
.\.venv\Scripts\python.exe -m scripts.validate_thermal_b6r_p3
.\.venv\Scripts\python.exe -m scripts.validate_thermal_b6r_p2_public_sdt
.\.venv\Scripts\python.exe -m unittest tests.test_thermal_b6r_p3
.\.venv\Scripts\python.exe -m unittest `
  tests.test_thermal_b6r_p0_public_sdt `
  tests.test_thermal_b6r_p1_public_sdt `
  tests.test_thermal_b6r_p2_public_sdt `
  tests.test_thermal_interpreter
```

TensorFlow 실행에서 기존 `tf.lite.Interpreter` deprecation warning과 XNNPACK info가 출력되었으나 P2 offline validator는 통과했다. 이 desktop runtime 출력은 Raspberry Pi target evidence로 사용하지 않았다.

## 11. Stage Gate 판정

최종 판정은 `BLOCKED_HARDWARE`다.

| Gate | 판정 |
|---|---|
| P0 source archive `6/6` identity | PASS |
| P2 exact artifact/tensor contract | PASS |
| P2 DEVELOPMENT fixture inheritance | PASS |
| LOCKED_PUBLIC_TEST non-access | PASS |
| Pi access 및 target identity | BLOCKED_HARDWARE |
| target latency/resource/stability/determinism | NOT_MEASURED_ON_TARGET |
| desktop substitution | 금지·미수행 |
| default/runtime/legacy preservation | PASS |
| shadow-only boundary | PASS |

허용 가능한 claim 범위는 `PUBLIC_SDT_ONLY`, `FP32_TFLITE`, `SHADOW_ONLY`, `NOT_SAFETY_AUTHORITY`, `NOT_MI48_VALIDATED`다. 이번 결과로 `RASPBERRY_PI_REPLAY_BENCHMARKED`, physical validation, real-fall detection, production readiness, safety authority, MI48 generalization을 주장할 수 없다.

## 12. 변경 파일과 rollback

추가·수정한 tracked 범위는 다음과 같다.

- P3 contract: `config/thermal/b6r_p3_raspberry_pi_fp32_tflite_replay_shadow_benchmark_contract.json`
- P3 runner/validator/test: `scripts/benchmark_thermal_b6r_p3_rpi.py`, `scripts/validate_thermal_b6r_p3.py`, `tests/test_thermal_b6r_p3.py`
- P3 evidence: `datasets/thermal/manifests/B6R-P3_raspberry_pi_fp32_tflite_replay_shadow_benchmark/`
- roadmap: `docs/20260822_Codex_Thermal_B6R_Robust_Relative_FP32_Parallel_Roadmap_KO_01.md`
- index/README: `docs/thermal/B6R_DEVELOPMENT_INDEX.md`, `docs/README.md`
- 본 보고서

기존 `models/model_manifest.json`, legacy `.tflite`, `inference/thermal_interpreter.py` 및 production selector는 변경하지 않았다. rollback은 P3 opt-in shadow runner를 중지하고 기존 legacy default를 계속 사용하는 것이다. delivery commit 자체를 되돌려야 하는 경우에는 해당 P3 delivery commit을 명시적으로 revert한다.

## 13. 다음 작업 규칙과 STOP

현재 blocker는 authorized Raspberry Pi target과 접근 경로가 없고, 기존 명시적-user SSH probe가 timeout된 것이다. target이 제공되고 실행 권한이 확인되면 동일한 contract와 동일한 P3 runner로 fixed replay, 30분 stability, resource, determinism을 target에서 다시 측정한다. 새로운 fixture를 만들거나 desktop 수치를 보충하지 않는다.

그 외 P4, P3 후속 확장, runtime integration, default activation, safety/production 단계는 이번 승인 범위에 포함되지 않으며 실행하지 않는다.

`STOP — B6R-P3 단일 단계 실행을 종료한다.`
