# SafeNest V5 On-Device AI

> ⚠️ **RELEASE WARNING: DEPLOYMENT PROHIBITED / NOT_READY**
> 
> - **TFLite 파일 존재·SHA·텐서 규격**: CONFIRMED
> - **Mock 파이프라인**: CONFIRMED
> - **mmWave 배포 성능**: BLOCKED (`CLASS_COLLAPSE_ON_REPOSITORY_NPZ`)
> - **Thermal 실제 낙상 성능**: NOT_VERIFIABLE (합성 NPZ 테스트 fixture만 존재)
> - **CO₂ 실제 재실 성능**: NOT_VERIFIABLE (합성 NPZ 테스트 fixture만 존재)
> - **Pi 5 실배포**: NOT_READY / BLOCKED_HARDWARE
> - **전체 릴리스 상태**: **NOT_READY**

SafeNest V5는 검증된 V4 P0 소프트웨어 스냅샷에서 분기한 온디바이스 AI 배포판이다. 프로젝트 버전은 `5.0`이며 세 TFLite 모델 버전과 파일명은 기존 `v0.1.0`을 유지한다.

현재 상세 검증 상태:

- **P0 소프트웨어 파이프라인 / Mock 테스트**: CONFIRMED (통과)
- **mmWave Respiration AI 모델**: BLOCKED (저장소 합성 NPZ 평가 시 Class Collapse 발생, APNEA/비정상 Recall 0%)
- **Thermal & CO₂ 오프라인 평가**: synthetic regression fixture 기반 99% 수준 (실센서/실공간 성능 주장 불가)
- **실센서 드라이버 & Pi 5 실배포**: NOT_READY (하드웨어 통합 전)

실센서 provider가 없는 real mode는 정상값을 합성하지 않는다. 네 센서를 `valid=false`, 오류 `EXTERNAL_SENSOR_PROVIDER_REQUIRED`로 출력하고 시스템을 `FAILED`로 판정한다.

## 공식 production 경로

```text
integrated_node/run_node.py
→ sensors/* adapter 또는 주입된 팀원 provider
→ inference/* interpreter
→ risk/risk_engine.py
→ risk/fallback.py
→ inference/inference_result.py
→ JSON Lines stdout
```

`integrated_node/safenest_risk_engine.py`는 기존 테스트·데모용 legacy compatibility 모듈이다. 신규 센서 연동과 V5 production 융합에 사용하지 않는다.

## 실행

Mock end-to-end:

```bash
python3 integrated_node/run_node.py --mode mock
```

외부 provider 없는 fail-closed 확인:

```bash
python3 integrated_node/run_node.py --mode real
```

팀원 provider 주입:

```python
from integrated_node.run_node import SafeNestIntegratedNode

node = SafeNestIntegratedNode(
    mode="real",
    sensors={
        "thermal44": thermal_provider,
        "mmwave": mmwave_provider,
        "co2": co2_provider,
        "pir": pir_provider,
    },
)
node.start()
print(node.step().to_json())
node.shutdown()
```

각 provider는 `connect() -> bool`, `read() -> InferenceResult`, `close() -> None`을 구현한다. 상세 계약은 [V5 sensor provider contract](docs/reports/V5_SENSOR_PROVIDER_CONTRACT.md)를 따른다.

## 위험도와 건강 상태

```text
R = 100 * (
    0.35 * S_mmwave
  + 0.35 * S_co2
  + 0.15 * S_pir
  + 0.15 * S_thermal
)
```

`risk_level`은 사람 위험, `system_health`는 센서·모델 파이프라인 상태다. 일부 센서 장애는 `DEGRADED`, 전 센서 장애는 `FAILED`이며 이때 `risk_score`와 `risk_level`은 `null`이다. Thermal 낙상 또는 mmWave 무호흡은 `DANGER`, `R=100` emergency override를 유지한다. 출력 `metadata.schema_version`은 `5.0`이다.

센서별 stale TTL은 [config/sensors.yaml](config/sensors.yaml)에서 읽어 runtime 위험도 엔진에 전달한다. 현재 합의 전 기본값은 Thermal 3초, mmWave 3초, CO₂ 10초, PIR 10초다. CO₂ 0.2 Hz 갱신은 3초 공통 TTL을 사용하지 않는다.

## 검증과 패키징

```bash
python3 scripts/validate_v4_config.py
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m compileall -q inference risk sensors integrated_node scripts tests
python3 scripts/build_v5_archive.py
```

검증기 파일명은 기존 자동화 호환성을 위해 유지했지만 현재 파일 위치에서 V5 project root를 찾는다. sibling V4, `archive/`, `version_archives/`, `releases/`를 production dependency로 사용하지 않는다.

배포 산출물:

```text
releases/SafeNest_v5.0_ondevice_ai_package.zip
releases/SafeNest_v5.0_ondevice_ai_package.zip.sha256
```

ZIP 최상위 경로는 `SafeNest_V5_OnDevice_AI/`이며 내부 `SHA256SUMS.txt`로 파일별 무결성을 검증한다.

## 문서

- [팀 인수인계](docs/TEAM_HANDOFF_GUIDE_V5.md)
- [Sensor provider 계약](docs/reports/V5_SENSOR_PROVIDER_CONTRACT.md)
- [Release readiness](docs/reports/V5_RELEASE_READINESS.md)
- [Sensor data contract](docs/reports/SENSOR_DATA_CONTRACT.md)
