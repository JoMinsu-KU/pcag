# PCAG 플러그인 계층 안내

`pcag/plugins/`는 sensor, executor, simulation backend의 실제 구현체를 담는다.

## executor

- `mock_executor.py`
  - 테스트 및 개발용
- `modbus_executor.py`
  - 직접 Modbus executor
  - 현재는 진단/호환성 의미가 더 크다
- `plc_adapter_executor.py`
  - 현재 권장 실행 경로
  - OT Interface가 PLC Adapter를 통해 PLC/Modbus 자산에 접근한다

## sensor

- `isaac_sim_sensor.py`
  - Safety Cluster의 simulation state를 읽어 robot arm 스냅샷을 구성
- `mock_sensor.py`
  - 테스트용
- `modbus_sensor.py`
  - 직접 Modbus sensor
  - 현재는 보조/진단 성격
- `plc_adapter_sensor.py`
  - 현재 권장 PLC 계열 센서 경로

## simulation

- `ode_solver.py`
  - reactor 계열
- `isaac_backend.py`
  - robot arm 계열
- `discrete_event.py`
  - AGV 계열
- `none_backend.py`
  - simulation 없는 자산용

## 현재 기준 해석

플러그인 계층은 "각 자산마다 제각각 직접 연결"하는 구조가 아니라, 현재는 아래 방향으로 정리돼 있다.

- PLC/Modbus 읽기·쓰기: `PLC Adapter`를 통한 중앙화
- 로봇 시뮬레이션: Safety Cluster의 Isaac worker/proxy
- 평가용 mock: 테스트와 문서정합성 검증에 사용

즉 plugin 자체는 여럿 있지만, 실제 운영 경로는 중앙화된 쪽을 우선 사용한다.
