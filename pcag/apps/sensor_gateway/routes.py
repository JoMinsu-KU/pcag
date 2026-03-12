"""
센서 게이트웨이 (Sensor Gateway) — 실제 구현
=============================================
ISensorSource 플러그인을 통해 센서 데이터를 읽고,
SensorSnapshot(해시 포함)을 생성하여 반환합니다.

기본 동작:
  CompositeSensorSource를 사용하여 자산별로 적절한 소스(Modbus, Isaac Sim, Mock)를 선택합니다.

PCAG 파이프라인 위치:
  Gateway Core (100/110) → 여기서 센서 스냅샷 조회
  Safety Cluster (120) → 센서 데이터를 검증에 사용

API:
  GET /v1/assets/{asset_id}/snapshots/latest

conda pcag 환경에서 실행.
"""
import time
import logging
import json
import os
from fastapi import APIRouter, HTTPException
from pcag.core.contracts.sensor import SensorSnapshotResponse
from pcag.core.utils.hash_utils import compute_sensor_hash
from pcag.core.ports.sensor_source import ISensorSource
from pcag.plugins.sensor.modbus_sensor import ModbusSensorSource
from pcag.plugins.sensor.mock_sensor import MockSensorSource
from pcag.plugins.sensor.isaac_sim_sensor import IsaacSimSensorSource
from pcag.core.utils.config_loader import get_sensor_mappings, get_service_urls

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["SensorGateway"])

# 센서 플러그인 인스턴스 (서버 시작 시 초기화)
_sensor_source: ISensorSource | None = None


class CompositeSensorSource(ISensorSource):
    """
    여러 센서 소스(Modbus, Mock, Isaac Sim)를 조합하여 사용하는 Composite 패턴
    자산별로 소스를 라우팅하거나, Modbus 실패 시 Mock으로 폴백하는 로직을 통합합니다.
    """
    def __init__(self):
        self._sources = {} # name -> ISensorSource instance
        self._asset_routing = {} # asset_id -> source_name

    def initialize(self, config: dict) -> None:
        # 1. Modbus Source 초기화
        modbus_conf = {
            "host": config.get("modbus", {}).get("host", "127.0.0.1"),
            "port": config.get("modbus", {}).get("port", 503),
            "asset_mappings": config.get("assets", {})
        }
        modbus = ModbusSensorSource()
        modbus.initialize(modbus_conf)
        self._sources["modbus"] = modbus

        # 2. Mock Source 초기화
        if os.environ.get("PCAG_ENV") != "production":
            mock_conf = {"mock_data": config.get("mock_data", {})}
            mock = MockSensorSource()
            mock.initialize(mock_conf)
            self._sources["mock"] = mock
        
        # 3. Isaac Sim Source 초기화
        # URL은 services.yaml 등에서 가져오거나 기본값 사용
        safety_cluster_url = get_service_urls().get("safety_cluster")
        if not safety_cluster_url:
             # Fail-Hard: URL configuration required
             raise RuntimeError("Safety Cluster URL not configured in services.yaml")
             
        isaac = IsaacSimSensorSource()
        isaac.initialize({"safety_cluster_url": safety_cluster_url})
        self._sources["isaac"] = isaac
        
        # 4. 라우팅 테이블 구축
        asset_mappings = config.get("assets", {})
        
        for asset_id, props in asset_mappings.items():
            preferred = props.get("source", "auto")
            
            if preferred == "isaac":
                self._asset_routing[asset_id] = "isaac"
            elif preferred == "mock":
                if os.environ.get("PCAG_ENV") == "production":
                    raise RuntimeError(f"Asset {asset_id} is configured to use MOCK source, which is forbidden in PRODUCTION.")
                self._asset_routing[asset_id] = "mock"
            elif preferred == "modbus":
                # Always route to Modbus if configured, even if not connected initially
                self._asset_routing[asset_id] = "modbus"
                if not modbus._connected:
                    logger.warning(f"Asset {asset_id} routed to Modbus, but Modbus is currently disconnected.")
            else:
                # auto: Modbus defaults if mappings exist
                if "mappings" in props:
                    self._asset_routing[asset_id] = "modbus"
                    if not modbus._connected:
                        logger.warning(f"Asset {asset_id} (auto) routed to Modbus, but Modbus is currently disconnected.")
                else:
                    logger.error(f"[SYSTEM_ERROR] Asset {asset_id} (auto) cannot determine source. No mappings found.")
                    
        logger.info(f"CompositeSensorSource initialized. Routing: {self._asset_routing}")

    def read_snapshot(self, asset_id: str) -> dict:
        source_key = self._asset_routing.get(asset_id)
        if not source_key:
            raise RuntimeError(f"No sensor source routed for asset {asset_id}")
            
        source = self._sources.get(source_key)
        if not source:
            raise RuntimeError(f"Sensor source '{source_key}' not initialized")
            
        # 라우팅된 소스 사용
        return source.read_snapshot(asset_id)

    def get_source_name(self, asset_id: str) -> str:
        return self._asset_routing.get(asset_id, "unknown")

    def shutdown(self) -> None:
        for s in self._sources.values():
            s.shutdown()


def initialize_sensor_source():
    """
    센서 소스 초기화 (CompositeSensorSource 사용)
    """
    global _sensor_source
    config = get_sensor_mappings()
    
    composite = CompositeSensorSource()
    composite.initialize(config)
    
    _sensor_source = composite


def get_sensor_source() -> ISensorSource:
    """현재 활성 센서 소스 반환"""
    global _sensor_source
    if _sensor_source is None:
        initialize_sensor_source()
    return _sensor_source


@router.get("/assets/{asset_id}/snapshots/latest")
def get_latest_snapshot(asset_id: str):
    """
    최신 센서 스냅샷 조회
    
    1. CompositeSensorSource를 통해 적절한 소스(Modbus/Isaac/Mock)에서 데이터 읽기
    2. 데이터를 정규화(canonicalize) 후 SHA-256 해시 계산
    3. SensorSnapshotResponse 반환
    """
    t0 = time.time()
    try:
        source = get_sensor_source()
        
        # 센서 데이터 읽기
        sensor_data = source.read_snapshot(asset_id)
        
        # Source Name 확인 (Composite인 경우)
        source_name = "unknown"
        if hasattr(source, "get_source_name"):
            source_name = source.get_source_name(asset_id)
        
        # 해시 계산
        snapshot_hash = compute_sensor_hash(sensor_data)
        
        # 타임스탬프
        timestamp_ms = int(time.time() * 1000)
    except Exception as e:
        logger.error(f"Failed to retrieve sensor snapshot for {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Sensor read failed: {str(e)}")
    
    duration = (time.time() - t0) * 1000
    
    # Summary of sensor data for logging (first 3 keys)
    summary_keys = list(sensor_data.keys())[:3]
    summary = {k: sensor_data[k] for k in summary_keys}
    if len(sensor_data) > 3:
        summary["..."] = f"+{len(sensor_data)-3} more"
        
    logger.info(f"Sensor Snapshot: {asset_id} from {source_name} ({duration:.1f}ms)", extra={"extra_fields": {
        "asset_id": asset_id,
        "source": source_name,
        "data_keys": len(sensor_data),
        "hash": snapshot_hash[:8] + "...",
        "summary": json.dumps(summary)
    }})
    
    return SensorSnapshotResponse(
        asset_id=asset_id,
        snapshot_id=f"snap_{timestamp_ms}",
        timestamp_ms=timestamp_ms,
        sensor_snapshot=sensor_data,
        sensor_snapshot_hash=snapshot_hash,
        sensor_reliability_index=0.95 if sensor_data else 0.0
    )
