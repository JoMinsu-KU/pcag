"""
센서 데이터 소스 추상 인터페이스 (ISensorSource)
=================================================
모든 센서 플러그인(modbus_sensor, mock_sensor 등)이 구현해야 하는 인터페이스.

PCAG 파이프라인 위치:
  Sensor Gateway (210)가 이 인터페이스를 통해 센서 데이터를 읽습니다.

구현체:
  - ModbusSensorSource: ModRSsim2/PLC에서 Modbus TCP로 읽기
  - MockSensorSource: 고정 값 반환 (테스트용)

conda pcag 환경에서 실행.
"""
from abc import ABC, abstractmethod


class ISensorSource(ABC):
    """센서 데이터 소스 추상 인터페이스"""
    
    @abstractmethod
    def initialize(self, config: dict) -> None:
        """플러그인 초기화 — 서버 시작 시 1회 호출"""
        pass
    
    @abstractmethod
    def read_snapshot(self, asset_id: str) -> dict:
        """
        센서 스냅샷 읽기 — 매 요청마다 호출
        
        Returns:
            dict: 센서 데이터 (예: {"temperature": 150.0, "pressure": 1.5})
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """플러그인 종료 — 서버 종료 시 1회 호출"""
        pass
