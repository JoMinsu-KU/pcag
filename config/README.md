# PCAG 설정 파일 안내

`config/`는 PCAG 서비스 간 연결 정보, 자산 매핑, CBF 설정, 실행기/센서 라우팅을 담는 정적 설정 디렉터리다.

## 현재 핵심 파일

### `services.yaml`

전체 서비스 레지스트리와 로깅/대시보드 설정을 담는다.

- 각 서비스 기본 URL은 `127.0.0.1` 기준
- `dashboard` 설정 포함
- 서비스별 `health` 또는 `openapi` probe에 사용
- 일부 서비스는 시작 시점에 이 파일을 읽으므로 변경 후 재시작이 필요하다

### `cbf_mappings.yaml`

자산별 CBF 상태 매핑과 barrier 계산 기준을 정의한다.

### `executor_mappings.yaml`

자산별 OT 실행 경로를 정의한다.

현재 runtime에서는 PLC/Modbus 자산이 직접 low-level executor로 나가지 않고, `PLC Adapter`를 통한 중앙화된 경로를 사용한다.

### `sensor_mappings.yaml`

자산별 센서 소스 라우팅을 정의한다.

중요:

- `robot_arm_01`은 `isaac` 계열 센서 경로를 사용한다
- PLC/Modbus 계열 자산은 runtime에서 `PLCAdapterSensorSource`를 통해 중앙화된 경로를 타도록 구성되어 있다

## 운영 메모

- `localhost` 대신 `127.0.0.1`를 유지하는 것이 좋다
- 서비스 URL 변경 시 `start_services.py`, Dashboard, live E2E 러너, 일부 HTTP client 동작에 영향이 있다
- 설정 변경 후에는 영향받는 서비스를 재시작해야 한다

## 관련 코드

- [config_loader.py](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/core/utils/config_loader.py)
- [sensor_gateway/routes.py](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/apps/sensor_gateway/routes.py)
- [executor_manager.py](C:/Users/choiLee/Dropbox/경남대학교/AI%20agent%20기반으로%20물리%20환경%20제어/pcag/apps/ot_interface/executor_manager.py)
