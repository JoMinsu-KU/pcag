"""
Mock 센서 플러그인 — 테스트용 고정 센서값 반환
================================================
ModRSsim2가 없는 환경에서 테스트할 때 사용합니다.

conda pcag 환경에서 실행.
"""
from pcag.core.ports.sensor_source import ISensorSource


class MockSensorSource(ISensorSource):
    """Mock 센서 — 고정 값 반환"""
    
    def __init__(self):
        self._data = {}
    
    def initialize(self, config: dict) -> None:
        """Mock 센서 데이터 초기화"""
        self._data = config.get("mock_data", {})
    
    def read_snapshot(self, asset_id: str) -> dict:
        """고정 센서 데이터 반환"""
        if asset_id not in self._data:
            raise RuntimeError(f"MockSensorSource: No mock data defined for asset '{asset_id}'")
        return self._data[asset_id]
    
    def shutdown(self) -> None:
        pass
