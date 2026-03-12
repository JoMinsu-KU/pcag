"""
Sensor Gateway 테스트
======================
Mock 센서와 Modbus 센서 플러그인을 테스트합니다.

conda pcag 환경에서 실행:
  conda activate pcag && python -m pytest tests/unit/test_sensor_gateway.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from pcag.plugins.sensor.mock_sensor import MockSensorSource
from pcag.plugins.sensor.modbus_sensor import ModbusSensorSource
from pcag.core.ports.sensor_source import ISensorSource
from pcag.core.utils.hash_utils import compute_sensor_hash


# ============================================================
# Mock Sensor Tests
# ============================================================

def test_mock_implements_interface():
    """MockSensorSource가 ISensorSource를 구현하는가"""
    source = MockSensorSource()
    assert isinstance(source, ISensorSource)

def test_mock_returns_configured_data():
    """Mock 센서가 설정된 데이터를 반환하는가"""
    source = MockSensorSource()
    source.initialize({
        "mock_data": {
            "test_asset": {"temperature": 100.0, "pressure": 2.0}
        }
    })
    
    data = source.read_snapshot("test_asset")
    assert data["temperature"] == 100.0
    assert data["pressure"] == 2.0

def test_mock_returns_default_for_unknown_asset():
    """알 수 없는 자산에 대해 기본값 반환"""
    source = MockSensorSource()
    source.initialize({})
    
    data = source.read_snapshot("unknown_asset")
    assert "temperature" in data  # 기본값 있어야 함

def test_mock_hash_consistency():
    """같은 Mock 데이터 → 같은 해시"""
    source = MockSensorSource()
    source.initialize({"mock_data": {"a": {"temp": 100.0}}})
    
    data1 = source.read_snapshot("a")
    data2 = source.read_snapshot("a")
    
    assert compute_sensor_hash(data1) == compute_sensor_hash(data2)


# ============================================================
# Modbus Sensor Tests (ModRSsim2가 없어도 동작하는 테스트)
# ============================================================

def test_modbus_implements_interface():
    """ModbusSensorSource가 ISensorSource를 구현하는가"""
    source = ModbusSensorSource()
    assert isinstance(source, ISensorSource)

def test_modbus_graceful_when_not_connected():
    """Modbus 연결 실패 시 빈 데이터 반환 (에러 아님)"""
    source = ModbusSensorSource()
    source.initialize({"host": "127.0.0.1", "port": 59999})  # 존재하지 않는 포트
    
    data = source.read_snapshot("reactor_01")
    assert data == {}  # 연결 실패 → 빈 dict
    
    source.shutdown()

def test_modbus_shutdown_safe():
    """연결 없이 shutdown 호출해도 에러 없음"""
    source = ModbusSensorSource()
    source.shutdown()  # 초기화 없이 종료 — 에러 없어야 함

def test_float32_conversion():
    """float32 ↔ 레지스터 변환 정확성"""
    # 150.5를 레지스터로 변환 후 다시 float로
    regs = ModbusSensorSource.float32_to_registers(150.5)
    value = ModbusSensorSource._registers_to_float32(regs[0], regs[1])
    assert abs(value - 150.5) < 0.001

def test_float32_roundtrip_various():
    """다양한 값의 float32 왕복 변환"""
    test_values = [0.0, 1.0, -1.0, 100.5, 1000.123, 0.001]
    for v in test_values:
        regs = ModbusSensorSource.float32_to_registers(v)
        result = ModbusSensorSource._registers_to_float32(regs[0], regs[1])
        assert abs(result - v) < 0.001, f"Roundtrip failed for {v}: got {result}"


# ============================================================
# Sensor Gateway Route Tests (FastAPI TestClient)
# ============================================================

def test_sensor_gateway_route():
    """Sensor Gateway API가 스냅샷을 반환하는가"""
    from fastapi.testclient import TestClient
    from pcag.apps.sensor_gateway.main import app
    
    # Mock 센서 사용 강제 (Modbus 연결 불필요)
    from pcag.apps.sensor_gateway import routes
    mock = MockSensorSource()
    mock.initialize({"mock_data": {"reactor_01": {"temperature": 155.0, "pressure": 1.8}}})
    routes._sensor_source = mock
    
    client = TestClient(app)
    resp = client.get("/v1/assets/reactor_01/snapshots/latest")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset_id"] == "reactor_01"
    assert data["sensor_snapshot"]["temperature"] == 155.0
    assert data["sensor_snapshot"]["pressure"] == 1.8
    assert len(data["sensor_snapshot_hash"]) == 64  # SHA-256 hex
    assert data["sensor_reliability_index"] == 0.95

def test_sensor_gateway_hash_changes_with_data():
    """센서 데이터가 바뀌면 해시도 바뀌는가"""
    from fastapi.testclient import TestClient
    from pcag.apps.sensor_gateway.main import app
    from pcag.apps.sensor_gateway import routes
    
    # 첫 번째 읽기
    mock1 = MockSensorSource()
    mock1.initialize({"mock_data": {"reactor_01": {"temperature": 150.0}}})
    routes._sensor_source = mock1
    
    client = TestClient(app)
    resp1 = client.get("/v1/assets/reactor_01/snapshots/latest")
    hash1 = resp1.json()["sensor_snapshot_hash"]
    
    # 데이터 변경
    mock2 = MockSensorSource()
    mock2.initialize({"mock_data": {"reactor_01": {"temperature": 160.0}}})
    routes._sensor_source = mock2
    
    resp2 = client.get("/v1/assets/reactor_01/snapshots/latest")
    hash2 = resp2.json()["sensor_snapshot_hash"]
    
    assert hash1 != hash2  # 데이터 변경 → 해시 변경
