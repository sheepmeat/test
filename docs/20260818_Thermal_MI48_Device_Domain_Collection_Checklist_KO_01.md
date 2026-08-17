# SafeNest Thermal MI48 수집 체크리스트 — T-C0

이 체크리스트는 실제 센서가 준비된 뒤 첫 pilot을 안전하게 기록하기 위한
운영용 문서다. 이 문서만으로 수집·학습·배포 승인을 의미하지 않는다.

## 촬영 전

- [ ] `collection_id`, 익명 `subject_id`/`session_id` 생성
- [ ] 참가자 동의와 안전한 움직임 공간 확인
- [ ] 센서 모델·revision·익명 device ID·firmware 기록
- [ ] collector 버전·commit 기록
- [ ] native `62×80`, `uint16`, raw unit과 byte order를 장치 근거로 확인하거나 `UNKNOWN` 기록
- [ ] raw packet/native frame이 실제로 저장되는지 확인
- [ ] sensor/device/host timestamp와 clock unit 기록
- [ ] 저장공간, 권한, 세션 디렉터리, checksum 생성 가능 여부 확인
- [ ] 설치 방향·높이·거리·시야 위치·방/배경 메모 준비

## 세션 시작

- [ ] `session.json` 생성 및 시작 시각 기록
- [ ] 장면/자세를 `scenario_id`와 독립 source label로 기록
- [ ] empty-room이면 `subject_id = NONE`
- [ ] 새 방·설치 변경·센서 재시작은 새 session으로 분리

## 촬영 중

- [ ] 모든 수신 frame에 `frame_id`, sequence/counter, sensor·monotonic·wall timestamp 기록
- [ ] raw bytes와 decoded native frame을 보존
- [ ] 누락·중복·CRC/decode 실패 frame을 삭제하거나 renumber하지 않음
- [ ] 자세/장면 변경 시 event ID 기록
- [ ] `LYING`은 누워 있는 자세로만 기록
- [ ] 자유 낙상 실험을 하지 않음; 전이 수집은 별도 안전 승인 없이는 하지 않음

## 세션 종료와 라벨

- [ ] `frames.jsonl`, `annotations.jsonl`, `session.json` 완성
- [ ] annotator code·방법·confidence·revision 기록
- [ ] presence와 posture를 분리 기록
- [ ] model output을 라벨로 사용하지 않음
- [ ] raw 파일을 수정하지 않고 SHA-256 registry 생성

## 검증과 보관

- [ ] `python3 scripts/validate_thermal_real_capture.py <collection-root>` 실행
- [ ] 모든 오류·경고·누락·타이밍 gap을 검토
- [ ] derived builder 출력은 raw와 다른 디렉터리에 생성
- [ ] subject/session/event 그룹 split을 모델을 보기 전에 고정
- [ ] T-C 검토 전에는 TRAIN 승격, Float 평가, INT8 calibration, retraining을 시작하지 않음
- [ ] 원본과 validator 결과를 읽기 전용 백업으로 보관
