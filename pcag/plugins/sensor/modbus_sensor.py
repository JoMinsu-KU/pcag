"""
Modbus 센서 플러그인 — ModRSsim2/PLC에서 실제 센서값 읽기
==========================================================
Modbus TCP 프로토콜로 PLC의 Holding Register를 읽어
SensorSnapshot을 생성합니다.

사용:
  Lab 환경: ModRSsim2 (포트 503)
  Production: 실제 PLC (포트 502)

센서 매핑 설정 (config):
  각 자산(asset)별로 레지스터 주소 → 센서 필드 매핑을 정의합니다.

conda pcag 환경에서 실행.
"""
import time
import struct
import logging
from pcag.core.ports.sensor_source import ISensorSource

logger = logging.getLogger(__name__)

# 재연결 설정
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_SEC = 0.5


class ModbusSensorSource(ISensorSource):
    """Modbus TCP 센서 소스 — ModRSsim2/PLC에서 읽기"""
    
    def __init__(self):
        self._client = None
        self._config = {}
        self._connected = False
        self._host = "127.0.0.1"
        self._port = 503
    
    def initialize(self, config: dict) -> None:
        """
        Modbus TCP 클라이언트 초기화 및 연결
        
        config 예시:
        {
            "host": "127.0.0.1",
            "port": 503,
            "asset_mappings": {
                "reactor_01": {
                    "mappings": [
                        {"field": "temperature", "register": 0, "register_count": 2, "data_type": "float32"},
                        {"field": "pressure", "register": 2, "register_count": 2, "data_type": "float32"},
                        {"field": "heater_output", "register": 4, "register_count": 1, "data_type": "uint16", "scale": 0.1},
                        {"field": "cooling_valve", "register": 5, "register_count": 1, "data_type": "uint16", "scale": 0.1}
                    ]
                }
            }
        }
        """
        self._config = config
        self._host = config.get("host", "127.0.0.1")
        self._port = config.get("port", 503)
        
        try:
            from pymodbus.client import ModbusTcpClient
            self._client = ModbusTcpClient(self._host, port=self._port)
            self._connected = self._client.connect()
            if self._connected:
                logger.info(f"Modbus connected to {self._host}:{self._port}")
            else:
                logger.warning(f"Modbus connection failed to {self._host}:{self._port}")
        except ImportError:
            logger.error("pymodbus not installed. Run: pip install pymodbus")
            self._connected = False
        except Exception as e:
            logger.error(f"Modbus connection error: {e}")
            self._connected = False
    
    def _reconnect(self) -> bool:
        """
        Modbus TCP 재연결 시도.
        
        연결이 끊어진 경우 최대 MAX_RECONNECT_ATTEMPTS회 재연결을 시도합니다.
        각 시도 사이에 RECONNECT_DELAY_SEC만큼 대기합니다.
        
        Returns:
            bool: 재연결 성공 여부
        """
        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            logger.info(
                f"Modbus reconnect attempt {attempt}/{MAX_RECONNECT_ATTEMPTS} "
                f"to {self._host}:{self._port}"
            )
            try:
                # 기존 소켓 정리
                if self._client:
                    try:
                        self._client.close()
                    except Exception:
                        pass
                
                # 새 연결 시도
                from pymodbus.client import ModbusTcpClient
                self._client = ModbusTcpClient(self._host, port=self._port)
                self._connected = self._client.connect()
                
                if self._connected:
                    logger.info(
                        f"Modbus reconnected to {self._host}:{self._port} "
                        f"on attempt {attempt}"
                    )
                    return True
                    
            except Exception as e:
                logger.warning(f"Modbus reconnect attempt {attempt} failed: {e}")
            
            if attempt < MAX_RECONNECT_ATTEMPTS:
                time.sleep(RECONNECT_DELAY_SEC)
        
        logger.error(
            f"Modbus reconnect failed after {MAX_RECONNECT_ATTEMPTS} attempts "
            f"to {self._host}:{self._port}"
        )
        self._connected = False
        return False
    
    def read_snapshot(self, asset_id: str) -> dict:
        """
        Modbus 레지스터에서 센서 데이터 읽기
        
        센서 매핑 설정에 따라 레지스터 주소에서 값을 읽고,
        데이터 타입에 맞게 변환하여 SensorSnapshot dict를 생성합니다.
        
        연결이 끊어진 경우 자동으로 재연결을 시도합니다.
        재연결에도 실패하면 빈 dict를 반환합니다.
        """
        # 연결 상태 확인 — 끊어졌으면 재연결 시도
        if not self._connected or not self._client:
            logger.warning(f"Modbus not connected, attempting reconnect for {asset_id}")
            if not self._reconnect():
                logger.error(f"Modbus reconnect failed for {asset_id}")
                raise ConnectionError(f"Modbus reconnect failed for {asset_id}")
        
        asset_config = self._config.get("asset_mappings", {}).get(asset_id, {})
        mappings = asset_config.get("mappings", [])
        
        if not mappings:
            logger.warning(f"No sensor mappings for asset {asset_id}")
            return {}
        
        snapshot = {}
        connection_error_occurred = False
        
        for mapping in mappings:
            field = mapping["field"]
            addr = mapping["register"]
            count = mapping.get("register_count", 1)
            dtype = mapping.get("data_type", "uint16")
            
            try:
                result = self._client.read_holding_registers(address=addr, count=count)
                
                if result.isError():
                    msg = f"Modbus read error for {field} at addr {addr}: {result}"
                    logger.error(msg)
                    raise IOError(msg) # Fail-Hard: Do not skip fields
                
                # 데이터 타입에 따른 변환
                if dtype == "float32" and count == 2:
                    value = self._registers_to_float32(result.registers[0], result.registers[1])
                    value = round(value, 3)
                elif dtype == "uint16":
                    value = result.registers[0]
                    if "scale" in mapping:
                        value = round(value * mapping["scale"], 3)
                elif dtype == "int16":
                    value = result.registers[0]
                    if value > 32767:
                        value -= 65536
                    if "scale" in mapping:
                        value = round(value * mapping["scale"], 3)
                else:
                    value = result.registers[0]
                
                snapshot[field] = value
                
            except Exception as e:
                logger.error(f"Error reading {field} from Modbus: {e}")
                self._connected = False
                connection_error_occurred = True
                break  # 연결 에러 시 나머지 필드 읽기 중단
        
        # 연결 에러 발생 시: 재연결 후 전체 재시도 (1회만)
        if connection_error_occurred:
            logger.warning("Modbus connection lost during read, attempting reconnect and retry")
            if self._reconnect():
                # 재연결 성공 → 전체 필드 다시 읽기
                return self._read_all_fields(asset_id, mappings)
            else:
                logger.error(f"Modbus reconnect failed for {asset_id}")
                raise ConnectionError(f"Modbus reconnect failed for {asset_id}")
        
        return snapshot
    
    def _read_all_fields(self, asset_id: str, mappings: list) -> dict:
        """
        재연결 후 모든 필드를 한 번 더 읽기 시도.
        
        이 메서드는 재연결 후 1회만 호출되며,
        여기서도 실패하면 에러를 발생시킵니다.
        """
        snapshot = {}
        
        for mapping in mappings:
            field = mapping["field"]
            addr = mapping["register"]
            count = mapping.get("register_count", 1)
            dtype = mapping.get("data_type", "uint16")
            
            try:
                result = self._client.read_holding_registers(address=addr, count=count)
                
                if result.isError():
                    msg = f"Modbus retry read error for {field} at addr {addr}: {result}"
                    logger.error(msg)
                    raise IOError(msg)
                
                if dtype == "float32" and count == 2:
                    value = self._registers_to_float32(result.registers[0], result.registers[1])
                    value = round(value, 3)
                elif dtype == "uint16":
                    value = result.registers[0]
                    if "scale" in mapping:
                        value = round(value * mapping["scale"], 3)
                elif dtype == "int16":
                    value = result.registers[0]
                    if value > 32767:
                        value -= 65536
                    if "scale" in mapping:
                        value = round(value * mapping["scale"], 3)
                else:
                    value = result.registers[0]
                
                snapshot[field] = value
                
            except Exception as e:
                logger.error(f"Modbus retry failed for {field}: {e}")
                self._connected = False
                raise ConnectionError(f"Modbus retry failed for {field}: {e}")
        
        return snapshot
    
    def shutdown(self) -> None:
        """Modbus 연결 종료"""
        if self._client:
            try:
                self._client.close()
                logger.info("Modbus connection closed")
            except Exception:
                pass
        self._connected = False
    
    @staticmethod
    def _registers_to_float32(reg1: int, reg2: int) -> float:
        """2개의 16비트 Modbus 레지스터를 float32로 변환 (빅 엔디안)"""
        packed = struct.pack('>HH', reg1, reg2)
        return struct.unpack('>f', packed)[0]
    
    @staticmethod
    def float32_to_registers(value: float) -> list[int]:
        """float32를 2개의 16비트 레지스터로 변환 (테스트/쓰기용)"""
        packed = struct.pack('>f', value)
        reg1 = struct.unpack('>H', packed[0:2])[0]
        reg2 = struct.unpack('>H', packed[2:4])[0]
        return [reg1, reg2]
