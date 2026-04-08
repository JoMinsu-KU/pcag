import httpx
import logging
from pcag.core.ports.sensor_source import ISensorSource

logger = logging.getLogger(__name__)

class IsaacSimSensorSource(ISensorSource):
    """
    Isaac Sim Sensor Source
    =======================
    Safety Cluster의 Isaac Sim Proxy를 통해 시뮬레이션 상태(Digital Twin)를 조회합니다.
    
    이 플러그인은 Sensor Gateway에서 사용되며, 
    Safety Cluster API (GET /v1/simulation/state)를 호출하여 데이터를 가져옵니다.
    """
    
    def __init__(self):
        self._url = "http://localhost:8001/v1/simulation/state"
        
    def initialize(self, config: dict) -> None:
        """
        초기화
        
        Args:
            config (dict): 설정 (safety_cluster_url 포함)
        """
        base_url = config.get("safety_cluster_url", "http://localhost:8001")
        self._url = f"{base_url}/v1/simulation/state"
        logger.info(f"IsaacSimSensorSource initialized. Target: {self._url}")
        
    def read_snapshot(self, asset_id: str) -> dict:
        """
        센서 스냅샷 읽기
        
        Isaac Sim에서 현재 상태를 가져와 평탄화된 dict로 반환합니다.
        (예: joint_positions=[1,2] -> {joint_0: 1, joint_1: 2, joint_positions: [1,2]})
        """
        try:
            # 타임아웃 짧게 설정 (실시간성 중요)
            resp = httpx.get(self._url, timeout=1.0)
            
            if resp.status_code == 200:
                data = resp.json()
                
                # 에러 응답 체크
                if "error" in data:
                    # Isaac Sim이 준비되지 않았거나 에러 상태
                    raise RuntimeError(f"Isaac Sim returned error: {data['error']}")
                
                snapshot = {}
                
                # 1. 원본 데이터 복사
                for k, v in data.items():
                    if k == "timestamp":
                        continue
                    snapshot[k] = v
                
                # 2. Joint Positions 전개
                if "joint_positions" in data and isinstance(data["joint_positions"], list):
                    positions = data["joint_positions"]
                    for i, val in enumerate(positions):
                        if i < 7:
                            snapshot[f"joint_{i}"] = val
                        elif i == 7:
                            snapshot["finger_joint_0"] = val
                        elif i == 8:
                            snapshot["finger_joint_1"] = val
                            
                # 3. Joint Velocities 전개
                if "joint_velocities" in data and isinstance(data["joint_velocities"], list):
                    velocities = data["joint_velocities"]
                    for i, val in enumerate(velocities):
                        if i < 7:
                            snapshot[f"joint_{i}_velocity"] = val
                        elif i == 7:
                            snapshot["finger_joint_0_velocity"] = val
                        elif i == 8:
                            snapshot["finger_joint_1_velocity"] = val

                # 4. Joint Efforts 전개
                if "joint_efforts" in data and isinstance(data["joint_efforts"], list):
                    efforts = data["joint_efforts"]
                    for i, val in enumerate(efforts):
                        if i < 7:
                            snapshot[f"joint_{i}_effort"] = val
                        elif i == 7:
                            snapshot["finger_joint_0_force"] = val
                        elif i == 8:
                            snapshot["finger_joint_1_force"] = val
                
                if not snapshot:
                    logger.error("[SYSTEM_ERROR] Isaac Sim returned empty snapshot data")
                    raise RuntimeError("Isaac Sim returned empty snapshot data")

                # Provide a stable integrity-hash basis while preserving the
                # richer dynamic fields for validation and diagnostics.
                integrity_basis = {}
                if "joint_positions" in snapshot:
                    integrity_basis["joint_positions"] = snapshot["joint_positions"]
                for key in (
                    "joint_0",
                    "joint_1",
                    "joint_2",
                    "joint_3",
                    "joint_4",
                    "joint_5",
                    "joint_6",
                    "finger_joint_0",
                    "finger_joint_1",
                    "runtime_id",
                    "scene_path",
                ):
                    if key in snapshot:
                        integrity_basis[key] = snapshot[key]
                snapshot["__integrity_hash_payload"] = integrity_basis

                return snapshot
            else:
                # 연결 실패 등
                logger.warning(f"Isaac Sim returned status {resp.status_code}")
                raise RuntimeError(f"Isaac Sim returned status {resp.status_code}")
                
        except Exception as e:
            logger.error(f"Isaac Sim read failed: {e}")
            raise e
            
    def shutdown(self) -> None:
        pass
