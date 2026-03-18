# PCAG 서비스 계층 안내

`pcag/apps/`는 PCAG의 서비스 진입점을 담는 디렉터리다. 각 서비스는 독립적인 FastAPI 앱이며, 현재 구현 기준으로 총 9개 서비스가 존재한다.

## 서비스 목록

### `gateway/`

전체 안전 실행 파이프라인 오케스트레이터.

- schema validation
- integrity check
- safety validation orchestration
- PREPARE / REVERIFY / COMMIT / ABORT 흐름
- evidence 기록

### `safety_cluster/`

Rules, CBF, Simulation 검증과 SIL consensus를 수행한다.

- validator 병렬 fan-out
- Isaac worker/proxy 기반 simulation
- consensus verdict 계산

### `policy_store/`

활성 정책, 자산 프로필, 버전 조회의 source of truth.

### `policy_admin/`

정책 등록, 수정, 활성화, 버전 관리용 관리 인터페이스.

### `sensor_gateway/`

자산별 최신 센서 스냅샷과 해시를 제공한다.

- Isaac sensor
- PLC Adapter 경유 센서
- mock sensor

### `ot_interface/`

PREPARE/COMMIT/ABORT/E-Stop 실행 제어.

### `evidence_ledger/`

증거 이벤트 append/query와 해시 체인을 담당한다.

### `plc_adapter/`

PLC/Modbus 읽기·쓰기를 단일 진입점으로 중앙화한다.

### `dashboard/`

실시간 운영 대시보드와 snapshot/SSE 스트림을 제공한다.

## 운영 메모

- `safety_cluster`는 `pcag-isaac` 환경
- 나머지는 `pcag` 환경
- 서비스 간 URL은 `config/services.yaml`에서 관리한다
- 현재 기준 문서는 [PCAG_최종_시스템_명세서.md](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/plans/PCAG_최종_시스템_명세서.md)이다
