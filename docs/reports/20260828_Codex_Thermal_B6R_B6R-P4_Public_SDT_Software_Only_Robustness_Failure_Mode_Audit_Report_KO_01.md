# SafeNest Thermal B6-R B6R-P4 Public SDT Software-Only Robustness & Failure-Mode Audit 실행 보고서

## 1. 작업 개요

- 날짜: `2026-08-28`
- Stage: `B6R-P4 — Public SDT FP32 TFLite Offline Robustness & Failure-Mode Audit`
- 최종 상태: `PASS_WITH_LIMITATIONS — PUBLIC_DATA_SOFTWARE_ONLY_NON_GATING`
- 대상: P2 exact FP32 TFLite artifact 한 개
- 데이터: P0 `DEVELOPMENT` 8,000개만 사용
- perturbation inference: `128,000` (`8,000 × 16`)

성공은 높은 accuracy가 아니라 contract 구현, identity 보존, DEVELOPMENT-only stress diagnostic, failure-mode/parity/numerical/determinism evidence 완료를 뜻한다.

## 2. Stage 정의와 사용자 승인 범위

사용자는 기존 roadmap에 없던 P4 한 단계를 `PUBLIC_AUXILIARY`, `SOFTWARE_ONLY`, `NON_GATING`, `DEVELOPMENT_ONLY`, `SHADOW_ONLY`로 명시 승인했다. 재학습, calibration, quantization, model/runtime/default/safety 변경, Raspberry Pi 접근, real sensor/MI48/Thermal-90 사용, LOCKED_PUBLIC_TEST 평가, P5 정의·실행은 포함되지 않았다.

## 3. 시작 branch / local HEAD / origin HEAD

| 항목 | 값 |
|---|---|
| branch | `feature/thermal-b6r-development` |
| 시작 local HEAD | `3b20cb889e533befa06619a302d642548a30a695` |
| 시작 origin HEAD | `3b20cb889e533befa06619a302d642548a30a695` |
| 시작 worktree | clean |
| delivery commit | 이 보고서를 포함하는 P4 delivery commit; `git log -- <report path>`로 확인 |

`git fetch origin`, branch switch, `git pull --ff-only` 후 local/origin이 같음을 확인하고 시작했다.

## 4. P0→P3 현재 진행상황

| 흐름 | Stage | 상태 |
|---|---|---|
| 본선 | B6R-0 | `FAIL` |
| 본선 | B6R-1 | `INCONCLUSIVE` |
| 본선 | B6R-2 | `BLOCKED` |
| 본선 | B6R-3~14 | `NOT_STARTED` |
| Public 보조 | B6R-P0 | `PASS_WITH_LIMITATIONS` |
| Public 보조 | B6R-P1 | `PASS_WITH_LIMITATIONS` |
| Public 보조 | B6R-P2 | `PASS` |
| Public 보조 | B6R-P3 | `BLOCKED_HARDWARE` |

P4는 위 상태를 변경하지 않는다.

## 5. P4가 필요한 이유

P2는 clean DEVELOPMENT fixture에서 export/parity를 증명했지만, bounded synthetic perturbation, malformed input, stress parity, process 재실행의 수치 무결성 근거는 없었다. P4는 모델을 개선하거나 선택하지 않고 이 software-only evidence gap만 채운다.

## 6. P4 non-gating / software-only claim boundary

허용 claim은 `PUBLIC_SDT_ONLY`, `SOFTWARE_ONLY`, `OFFLINE_ONLY`, `SYNTHETIC_STRESS_TEST_ONLY`, `DEVELOPMENT_ONLY`, `FP32_TFLITE`, `NON_GATING`, `SHADOW_ONLY`다. `NOT_MI48_VALIDATED`, `NOT_THERMAL90_VALIDATED`, `NOT_PHYSICAL_VALIDATION`, `NOT_REAL_FALL_VALIDATION`, `NOT_RASPBERRY_PI_VALIDATED`, `NOT_SAFETY_AUTHORITY`, `NOT_PRODUCTION_READY`를 유지한다.

## 7. Public SDT source identity

logical source는 `WORKSPACE_THERMAL_DATASET_ARCHIVES`다. 6개 archive를 read-only로 다시 size/SHA-256 계산했고 contract와 `6/6` 일치했다.

| archive | size bytes | SHA-256 |
|---|---:|---|
| `test.zip` | 1,740,348,425 | `3a838bd70835e579ecfaa820a6c0b4cbc6ba7b76729417c73845f0c959281449` |
| `train.zip.001` | 4,194,304,000 | `9dd2f944f43209dd44463956b7b34030daecc22bf49050478e77aae27c48dbc4` |
| `train.zip.002` | 4,194,304,000 | `91be187a432e21c6020928d115d1394ccf540cc6addac8f064a7b181cabe2259` |
| `train.zip.003` | 4,194,304,000 | `a2e263e0a9024363d787a335ad8641d2a73ee61129d7cb2eb1cffa32b16e1187` |
| `train.zip.004` | 1,408,015,891 | `406160460568f387b9a84e392430ed2afe57aeb055d073ba93f722c3b0d3b071` |
| `validation.zip` | 3,492,475,558 | `06d52e24163d1fe243ebfbdb7d2dcef33fcc0a5ed0531ad81621ec1490af4f8f` |

P0 DEVELOPMENT `images.npy`, `labels.npy`, `sample_index.jsonl`도 P0 artifact registry와 `3/3` 일치했다. source archive 수정·추출·재압축은 없었다.

## 8. P1/P2 model identity

| 항목 | 결과 |
|---|---|
| P1 model ID / architecture | `thermal_public_sdt_pooled_mlp_v1` / `PUBLIC_SDT_ADAPTIVE_POOL_MLP_V1` |
| P1 parameter count | `2,691` |
| P1 NPZ SHA-256 | `35680056a841913c50e3d3e5fc7988e209e80ba5e62fd179fb135d35acf25677` |
| P2 artifact size | `70,592 bytes` |
| P2 artifact SHA-256 | `f88d65d76dbb21862e1f3cdff17cefb038a432047ded6ac8d5563bc8bc8c52ff` |
| P2 input/output | `[1,62,80,1] float32` → `[1,3] float32` |
| quantization | `NONE` |
| class order | `NOT_HUMAN`, `HUMAN_NORMAL`, `HUMAN_FALL_PROXY` |

불일치가 없어 재생성·재학습하지 않았다.

## 9. DEVELOPMENT clean baseline

다음은 독립 test가 아니라 P1 selection에 이미 사용된 `DEVELOPMENT diagnostic metric`이다.

| metric | 값 |
|---|---:|
| samples | 8,000 |
| accuracy | `0.907000` |
| macro precision | `0.903413` |
| macro recall | `0.901250` |
| macro F1 | `0.901327` |
| mean confidence | `0.815016` |

| class | precision | recall | F1 | support |
|---|---:|---:|---:|---:|
| NOT_HUMAN | 0.886564 | 0.953500 | 0.918815 | 2,000 |
| HUMAN_NORMAL | 0.918966 | 0.924250 | 0.921600 | 4,000 |
| HUMAN_FALL_PROXY | 0.904710 | 0.826000 | 0.863565 | 2,000 |

confusion matrix는 `[[1907,93,0],[129,3697,174],[115,233,1652]]`이고 prediction distribution은 `2151/4023/1826`이다.

## 10. Synthetic perturbation contract

결과를 보기 전에 seed `20260828`과 16개 조건을 JSON contract에 고정했다.

- bounded Gaussian noise: sigma `0.01`, `0.03`, `0.05`; noise `±3σ` 제한 후 `[0,1]` clip
- sparse hot/cold: pixel ratio `0.1%`, `0.5%`, `1.0%`
- row/column dropout: `1`, `2`, `4` lines
- zero rectangle: `10×10`(약 2%), `16×16`(약 5%), `22×23`(약 10%)
- zero-pad/crop shift: `(±1,±1)`, `(±2,∓2)` 네 조건

각 sample seed는 master seed, perturbation ID, sample ID의 SHA-256으로 파생했다. registry에 8,000 sample ID와 조건별 ordered tensor stream SHA-256을 기록했으며 tensor 원본은 Git에 복제하지 않았다.

## 11. Perturbation별 diagnostic 결과

| 조건 | accuracy | macro F1 | flip count | flip rate | mean confidence Δ |
|---|---:|---:|---:|---:|---:|
| noise σ=.01 | .907250 | .901526 | 14 | .001750 | -.000975 |
| noise σ=.03 | .902500 | .897512 | 113 | .014125 | -.006602 |
| noise σ=.05 | .895125 | .890348 | 235 | .029375 | -.013332 |
| hot/cold .1% | .906375 | .900738 | 36 | .004500 | -.000365 |
| hot/cold .5% | .906250 | .900920 | 81 | .010125 | -.001230 |
| hot/cold 1% | .904125 | .898677 | 115 | .014375 | -.002756 |
| dropout 1 | .906125 | .900192 | 76 | .009500 | -.002971 |
| dropout 2 | .905000 | .899158 | 88 | .011000 | -.005300 |
| dropout 4 | .903000 | .897209 | 153 | .019125 | -.011138 |
| occlusion 약 2% | .899375 | .893043 | 127 | .015875 | -.006610 |
| occlusion 약 5% | .868500 | .860305 | 434 | .054250 | -.017942 |
| occlusion 약 10% | .823500 | .810246 | 931 | .116375 | -.033472 |
| shift +1,+1 | .898500 | .892197 | 327 | .040875 | +.001813 |
| shift -1,-1 | .896500 | .890247 | 297 | .037125 | -.006420 |
| shift +2,-2 | .875625 | .867773 | 659 | .082375 | +.005312 |
| shift -2,+2 | .876750 | .870460 | 625 | .078125 | -.017734 |

수치가 낮거나 높다는 사실만으로 physical pass/fail 판정을 만들지 않았다.

## 12. Per-class failure-mode 분석

가장 큰 변화인 약 10% rectangle occlusion에서 recall은 NOT_HUMAN `.9320`, HUMAN_NORMAL `.83475`, HUMAN_FALL_PROXY `.6925`였다. clean 대비 HUMAN_FALL_PROXY recall이 `.8260→.6925`로 가장 크게 낮아졌다. `shift -2,+2`에서도 FALL_PROXY recall은 `.7460`이었다. 반대로 `shift +2,-2`에서는 NOT_HUMAN recall이 `.8385`로 낮았다. 방향과 class에 따라 민감도가 비대칭임을 보여 주지만, 실제 sensor orientation/occlusion 성능으로 해석하지 않는다.

## 13. Clean↔perturbed prediction flip 분석

최대 flip은 약 10% rectangle의 `931/8000`(`11.6375%`)였다. 다음은 `+2,-2` shift `659`(`8.2375%`), `-2,+2` shift `625`(`7.8125%`), 약 5% rectangle `434`(`5.425%`)였다. 최소는 noise σ=.01의 `14`(`0.175%`)였다. 최대 single probability change는 약 10% rectangle에서 `.979799`였다.

## 14. P1 NumPy↔P2 TFLite stress parity

P2의 고정 DEVELOPMENT fixture 48개에 clean+16 조건을 적용해 총 `816` pair를 비교했다. P2 tolerance를 완화하지 않았다.

| 항목 | 결과 |
|---|---:|
| probability max abs difference | `5.0663948e-7` (`<=1e-5`) |
| probability mean abs difference | `3.6375546e-8` (`<=1e-6`) |
| argmax agreement | `1.0` |
| mismatch | `0` |

판정: `PASS`.

## 15. Numerical integrity 결과

clean 8,000개와 16개 perturbation의 정상 출력에서 non-finite `0`, invalid probability `0`, shape/dtype violation `0`이었다. clean probability-sum max error는 `1.1920929e-7`이며 모든 출력은 float32 3-class probability contract와 유효 argmax를 만족했다.

## 16. Invalid-input failure-mode 결과

isolated P4 helper 기준 12개 중 8개를 model invoke 전에 reject하고 4개를 accept했다.

- reject: NaN, +Inf, -Inf, wrong shape, empty, wrong rank, negative range, >1 range
- accept: constant zero, constant one, float64→float32 cast, uint8→float32 cast
- accepted case output: 모두 finite/valid probability

이는 P4 harness 결과이며 production input validator 동작이라고 주장하지 않는다. `inference/thermal_interpreter.py`는 수정하지 않았다.

## 17. Software determinism 결과

동일 interpreter 반복, interpreter reload, clean child process, perturbation regeneration, metric regeneration이 모두 byte-identical hash로 일치했다.

| 대상 | SHA-256 |
|---|---|
| perturbation tensor stream | `cf989c3d0efb906068dac9256a6161b3278980bfd159b801d2707c774c45deb4` |
| probability | `73c76cebd4acd46c703bab56069561965531bebbef3e4ab292d8327c2d08a898` |
| prediction | `68ff42fd390b6aedfc38b3441beb48c9ca2938db1355694bfed5c42753fb88da` |
| summary metrics | `f88389dc2783b394f1d0934ae5b6db7ffba2b4c4488824c58a3e16305e7d7035` |

## 18. LOCKED_PUBLIC_TEST audit

`path configured=false`, `array open=0`, `sample read=0`, `metrics computed=false`, `selection/tuning=false`다. P4 실행·validator·focused regression은 test materialized array를 열지 않았다.

## 19. Real-sensor access audit

real sensor data access count, `Desktop/sessions`, Thermal-90, MI48 access는 모두 `0`이다.

## 20. Raspberry Pi out-of-scope 확인

Raspberry Pi scope는 `OUT_OF_SCOPE`, connection attempt는 `0`이다. P3는 `BLOCKED_HARDWARE — unchanged`; latency, RSS/CPU/temp, 30-minute Pi stability는 `NOT_EVALUATED_BY_P4`다.

## 21. Legacy/default/runtime 불변 audit

| 파일 | SHA-256 | 결과 |
|---|---|---|
| `models/model_manifest.json` | `d55a1bce18107f85f86b48748b48e9bb25873572b849d69c3ab42fddb0a6a97b` | unchanged |
| `inference/thermal_interpreter.py` | `8ed4093051f31be0fc2b1cd8b1b8e2d72501af63eb2dd4462c9e8520b240a087` | unchanged |
| legacy thermal model | `5b56da8d127ccef85f30b6459cc0cfe2d86490e41f3caa5bd2a7b70bbc46ae84` | unchanged |
| P1 NPZ | `35680056a841913c50e3d3e5fc7988e209e80ba5e62fd179fb135d35acf25677` | unchanged |
| P2 FP32 TFLite | `f88d65d76dbb21862e1f3cdff17cefb038a432047ded6ac8d5563bc8bc8c52ff` | unchanged |

default activation, runtime selector, safety authority 변경은 없다.

## 22. 변경 파일

- P4 contract, evaluator, validator, focused test
- `datasets/thermal/manifests/B6R-P4_public_sdt_software_robustness_failure_mode/` portable evidence
- 본 보고서와 roadmap/index/README pointer
- `.gitattributes` P4 LF 규칙

model, source archive, materialized payload, production/default runtime은 변경하지 않았다.

## 23. 실행 명령

```powershell
git fetch origin
git switch feature/thermal-b6r-development
git pull --ff-only origin feature/thermal-b6r-development
.\.venv\Scripts\python.exe -m py_compile scripts\evaluate_thermal_b6r_p4_public_sdt_robustness.py scripts\validate_thermal_b6r_p4.py tests\test_thermal_b6r_p4.py
.\.venv\Scripts\python.exe -m scripts.evaluate_thermal_b6r_p4_public_sdt_robustness
.\.venv\Scripts\python.exe -m scripts.validate_thermal_b6r_p4
.\.venv\Scripts\python.exe -m scripts.validate_thermal_b6r_p2_public_sdt
.\.venv\Scripts\python.exe -m scripts.validate_thermal_b6r_p3
.\.venv\Scripts\python.exe -m unittest -v tests.test_thermal_b6r_p0_public_sdt tests.test_thermal_b6r_p1_public_sdt tests.test_thermal_b6r_p2_public_sdt tests.test_thermal_b6r_p3 tests.test_thermal_b6r_p4 tests.test_thermal_interpreter
git diff --check
```

## 24. Test / validator 결과

| 검증 | 결과 |
|---|---|
| P4 Python compile | PASS |
| P4 focused unittest | `6/6 pass` |
| 전체 focused regression | `34 tests`: `32 pass`, `2 skip`, `0 fail` |
| P4 validator | `14/14 checks pass`, `PASS_WITH_LIMITATIONS` |
| P2 validator | `16/16 checks pass`, `PASS` |
| P3 structural validator | `13/13 checks pass`, stage `BLOCKED_HARDWARE` 유지 |
| `git diff --check` | PASS |

2개 skip은 기존 thermal interpreter smoke test의 repository NPZ 입력 부재 때문이다.

## 25. Stage status

`PASS_WITH_LIMITATIONS — PUBLIC_DATA_SOFTWARE_ONLY_NON_GATING`

robustness degradation에는 gate threshold를 만들지 않았다. identity, lineage, parity, numerical integrity, determinism, locked-test/real-sensor/Pi non-access, immutability가 모두 통과했다.

## 26. 제한사항

clean DEVELOPMENT metric은 독립 test가 아니다. synthetic perturbation은 실제 sensor noise, packet loss, physical occlusion, mounting shift를 재현하거나 검증하지 않는다. subject/session group generalization, MI48/Thermal-90, Raspberry Pi, 실제 낙상, safety/production readiness는 평가하지 않았다.

## 27. 전체 B6R 진행상황

본선은 `B6R-0 FAIL`, `B6R-1 INCONCLUSIVE`, `B6R-2 BLOCKED`, `B6R-3~14 NOT_STARTED`다. Public 보조는 P0/P1 `PASS_WITH_LIMITATIONS`, P2 `PASS`, P3 `BLOCKED_HARDWARE`, P4 `PASS_WITH_LIMITATIONS`다. P4 성공은 P3 또는 본선 gate로 전파되지 않는다.

## 28. Rollback

P4는 opt-in offline tooling/evidence만 추가했으므로 runtime rollback 조작이 필요 없다. delivery를 되돌릴 때는 P4 delivery commit을 일반 `git revert <commit>`로 revert한다. legacy/P1/P2 model bytes는 원래 identity 그대로다.

## 29. 다음 작업 제안

P4 후속 stage를 정의하지 않는다. 향후 authorized Raspberry Pi target이 제공되면 P4와 무관하게 기존 P3 contract/runner를 별도로 재실행한다. 권위 MI48/실센서 evidence가 확보되면 public P*가 아니라 기존 본선/RC gate에서 다룬다.

## 30. STOP

`STOP — B6R-P4 Public auxiliary software-only / non-gating 단일 단계 실행을 종료한다.`
