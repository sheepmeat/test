# SafeNest V4 전처리 데이터셋 및 NPZ 배포 가이드

본 디렉터리는 SafeNest V4 온디바이스 AI 모델을 위한 전처리 `.npz` 데이터셋 파일과 재현 가능한 파이프라인 생성 스크립트를 포함합니다.

---

## 1. 원시 데이터셋 Exclusion 정책

> [!IMPORTANT]
> GitHub 단일 파일 용량 제한(<100MB)을 준수하고 저장소 용량 팽창을 방지하기 위해 원시 데이터셋(`db_records/`, 원시 CSV, 대용량 zip 파일)은 **깃 버전 관리에서 엄격히 제외**되었습니다.
> 오직 압축 전처리된 `.npz` 파일 및 자동 재생성 스크립트만 저장소에 보관됩니다.

---

## 2. 전처리 데이터셋 명세

### ⓐ CO₂ 재실 및 농도 데이터셋 (`datasets/co2/processed/co2_occupancy_v1.npz`)
- **출처**: UCI Machine Learning Repository - Occupancy Detection Dataset
- **URL**: [https://archive.ics.uci.edu/dataset/357/occupancy%2Bdetection](https://archive.ics.uci.edu/dataset/357/occupancy%2Bdetection)
- **DOI**: `10.24432/C5X01N`
- **라이선스**: CC BY 4.0
- **피처 구조**: `CO2_slope` (ppm/min), `Humidity` (%), `CO2` (ppm)
- **데이터 분할**:
  - `Train`: 8,138 샘플
  - `Validation`: 2,660 샘플
  - `Test`: 9,747 샘플
- **정규화 정책**: 오직 `Train` 분할 기준의 `mean` 및 `std` 통계량 사용.

### ⓑ mmWave 호흡 파형 데이터셋 (`datasets/mmwave/processed/mmwave_respiration_v1.npz`)
- **출처**: Zenodo 60GHz FMCW Radar Respiratory Dataset (110 subjects)
- **URL**: [https://zenodo.org/records/18599983](https://zenodo.org/records/18599983)
- **DOI**: `10.5281/zenodo.18599983`
- **라이선스**: CC BY 4.0
- **입력 스펙**: 10Hz 샘플링, 300 샘플 (30초 롤링 윈도우), shape `(300, 1)`
- **클래스 라벨**:
  - `0: NORMAL` (1,401 윈도우)
  - `1: RAPID_OR_ABNORMAL` (1,717 윈도우 - 운동 후 빈호흡 대리 라벨)
  - `2: APNEA` (315 윈도우 - 자발적 참기 데이터)
- **피험자 분할**:
  - `Train`: 80 피험자 (2,491 윈도우)
  - `Validation`: 15 피험자 (474 윈도우)
  - `Test`: 15 피험자 (468 윈도우)
- **데이터 누출 방지**: Train, Validation, Test 간 피험자 교차 0% 보장.

---

## 3. 원시 소스로부터 NPZ 데이터셋 재생성 방법

위 공식 URL에서 원시 데이터를 다운로드한 후 NPZ 파일 재생성:

```bash
# CO2 NPZ 데이터셋 재생성
python3 SafeNest_V4_OnDevice_AI/datasets/build_processed_npz.py --dataset co2 --source-root /path/to/uci_occupancy

# mmWave NPZ 데이터셋 재생성
python3 SafeNest_V4_OnDevice_AI/datasets/build_processed_npz.py --dataset mmwave --source-root /path/to/db_records

# 전체 NPZ 데이터셋 재생성
python3 SafeNest_V4_OnDevice_AI/datasets/build_processed_npz.py --dataset all --co2-root /path/to/uci --mmwave-root /path/to/db_records
```
