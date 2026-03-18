# PCAG 스크립트 안내

`scripts/`는 로컬 개발, 운영 점검, 정책 시드, 진단에 필요한 유틸리티를 모아둔 디렉터리다.

## 주요 스크립트

### 서비스 기동/중지

- `start_services.py`
  - `pcag` 환경 서비스 8개를 한 번에 기동한다
  - Gateway, Policy Store, Sensor Gateway, OT Interface, Evidence Ledger, Policy Admin, PLC Adapter, Dashboard
- `stop_services.py`
  - `start_services.py`로 올린 프로세스를 정리한다
- `start_safety_cluster.py`
  - `pcag-isaac` 환경에서 Safety Cluster를 별도로 띄운다
- `check_services.py`
  - 등록된 서비스들의 응답 상태를 빠르게 점검한다

### 초기화/정책

- `seed_policy.py`
  - 현재 자산 프로필과 정책 버전을 등록한다
  - reactor, robot arm, AGV 기준 정책을 포함한다

### 진단/개발

- `test_gateway.py`
  - Gateway에 synthetic 요청을 보내며 파이프라인을 빠르게 확인할 때 사용한다
- `test_isaac_sensor.py`
  - Sensor Gateway와 Isaac 기반 상태 조회 연결을 확인할 때 사용한다
- `test_logging.py`
  - 공통 로깅 형식을 점검할 때 사용한다
- `test_persistent_tx.py`
  - 트랜잭션/증거 저장 동작을 점검할 때 사용한다

## 권장 실행 순서

```powershell
conda activate pcag-isaac
python scripts/start_safety_cluster.py

conda activate pcag
python scripts/start_services.py
python scripts/seed_policy.py
python scripts/check_services.py
```

## 주의사항

- Safety Cluster는 별도 가상환경에서 띄워야 한다
- 설정 파일을 바꾼 뒤에는 관련 서비스를 재시작해야 한다
- live E2E와 Dashboard는 서비스 URL을 `127.0.0.1` 기준으로 맞춘 상태를 전제로 한다

## 관련 문서

- [PCAG_운영_Runbook.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_운영_Runbook.md)
- [README_live_gateway_eval.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/tests/e2e/README_live_gateway_eval.md)
