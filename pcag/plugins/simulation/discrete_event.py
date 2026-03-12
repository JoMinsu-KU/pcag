"""
Discrete Event Simulation Backend — 시나리오 C AGV 교차로 제어
================================================================
SimPy 이산 이벤트 시뮬레이션으로 AGV 경로 충돌을 예측합니다.

PCAG 파이프라인 [120-123]:
  Safety Cluster → Simulation Validator → Discrete Event
  → 현재 AGV 위치 + 이동 경로 → 충돌 예측 → SAFE/UNSAFE

공장 바닥 = 2D 그리드 (NxM)
AGV = SimPy Process로 모델링
교차로 = SimPy Resource (capacity=1)
충돌 = 두 AGV가 같은 셀에 동시 존재

설정은 config에서 로드 (Decision SIM-2: 2D Grid + SimPy):
  그리드 크기, 장애물, 교차로, AGV 초기 위치 등

conda pcag 환경에서 실행.
"""
import time
import logging
import simpy
from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)

# 기본 공장 바닥 설정
DEFAULT_GRID_CONFIG = {
    "width": 10,
    "height": 10,
    "obstacles": [],          # 장애물 셀 좌표 [[x,y], ...]
    "intersections": [],      # 교차로 셀 (Resource capacity=1)
    "agvs": {
        "agv_01": {"position": [0, 0], "speed": 1.0},
        "agv_02": {"position": [9, 9], "speed": 1.0}
    },
    "min_distance": 1.0       # AGV 간 최소 안전 거리 (셀 단위)
}


class DiscreteEventBackend(ISimulationBackend):
    """
    Discrete Event 시뮬레이션 — AGV 교차로 충돌 예측
    
    동작:
    1. initialize(): 그리드 맵 + AGV 초기 위치 설정
    2. validate_trajectory():
       - 현재 AGV 위치에서 시작
       - action_sequence의 이동 명령을 순서대로 적용
       - 각 시간 스텝에서 충돌 검사 (같은 셀 점유, 최소 거리 위반)
       - 충돌 발견 시 UNSAFE, 전부 통과 시 SAFE
    3. shutdown(): 정리
    """
    
    def __init__(self):
        self._config = {}
        self._initialized = False
    
    def initialize(self, config: dict) -> None:
        """
        그리드 맵 및 AGV 설정 로드
        
        config 예시:
        {
            "engine": "discrete_event",
            "grid": {
                "width": 10, "height": 10,
                "obstacles": [[3,3], [3,4]],
                "intersections": [[5,5], [5,2]]
            },
            "agvs": {
                "agv_01": {"position": [0, 0], "speed": 1.0},
                "agv_02": {"position": [9, 9], "speed": 1.0}
            },
            "min_distance": 1.0
        }
        """
        grid_config = config.get("grid", {})
        self._width = grid_config.get("width", DEFAULT_GRID_CONFIG["width"])
        self._height = grid_config.get("height", DEFAULT_GRID_CONFIG["height"])
        self._obstacles = set(tuple(o) for o in grid_config.get("obstacles", DEFAULT_GRID_CONFIG["obstacles"]))
        self._intersections = set(tuple(i) for i in grid_config.get("intersections", DEFAULT_GRID_CONFIG["intersections"]))
        self._agv_config = config.get("agvs", DEFAULT_GRID_CONFIG["agvs"])
        self._min_distance = config.get("min_distance", DEFAULT_GRID_CONFIG["min_distance"])
        
        self._initialized = True
        logger.info(f"Discrete Event Simulator initialized: {self._width}x{self._height} grid, {len(self._agv_config)} AGVs")
    
    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict
    ) -> dict:
        """
        AGV 경로 충돌 예측
        
        Args:
            current_state: {"agv_01": {"x": 0, "y": 0}, "agv_02": {"x": 9, "y": 9}, ...}
                          또는 {"position_x": 5, "position_y": 5} (단일 AGV)
            action_sequence: [
                {"action_type": "move_to", "params": {"agv_id": "agv_01", "path": [[1,0],[2,0],[3,0]]}},
                {"action_type": "move_to", "params": {"agv_id": "agv_02", "path": [[8,9],[7,9],[6,9]]}}
            ]
            constraints: {"ruleset": [...], "min_distance": 1.0}
        """
        if not self._initialized:
            self.initialize({})
        
        start_time = time.time()
        
        # AGV 현재 위치 추출
        agv_positions = self._extract_agv_positions(current_state)
        
        # 각 AGV의 이동 경로 추출
        agv_paths = {}
        for action in action_sequence:
            if action.get("action_type") == "move_to":
                params = action.get("params", {})
                agv_id = params.get("agv_id", "agv_01")
                
                # 경로가 있으면 사용, 없으면 목표 좌표로 직선 경로 생성
                if "path" in params:
                    agv_paths[agv_id] = [tuple(p) for p in params["path"]]
                elif "target_x" in params and "target_y" in params:
                    target_x = action.get("params", {}).get("target_x")
                    target_y = action.get("params", {}).get("target_y")

                    # Type validation
                    if target_x is not None and not isinstance(target_x, (int, float)):
                        raise ValueError(f"target_x must be numeric, got {type(target_x).__name__}: {target_x}")
                    if target_y is not None and not isinstance(target_y, (int, float)):
                        raise ValueError(f"target_y must be numeric, got {type(target_y).__name__}: {target_y}")

                    target = (params["target_x"], params["target_y"])
                    current = agv_positions.get(agv_id, (0, 0))
                    agv_paths[agv_id] = self._generate_simple_path(current, target)
        
        # SimPy 시뮬레이션 실행
        violations = []
        event_log = []
        collision_pairs = []
        
        env = simpy.Environment()
        
        # 각 시간 스텝에서의 AGV 위치 추적
        agv_timeline = {}  # {t: {agv_id: (x, y), ...}, ...}
        
        # 시뮬레이션 최대 스텝 수
        max_steps = max(len(p) for p in agv_paths.values()) if agv_paths else 0
        
        # 시간 스텝별로 AGV 위치 계산 + 충돌 검사
        for t in range(max_steps + 1):
            positions_at_t = {}
            
            for agv_id, start_pos in agv_positions.items():
                path = agv_paths.get(agv_id, [])
                
                if t == 0:
                    pos = start_pos
                elif t <= len(path):
                    pos = path[t - 1]
                else:
                    pos = path[-1] if path else start_pos
                
                positions_at_t[agv_id] = pos
                
                event_log.append({
                    "t_step": t,
                    "event": f"{agv_id}_at",
                    "location": list(pos)
                })
            
            agv_timeline[t] = positions_at_t
            
            # 충돌 검사: 같은 셀에 두 AGV가 있는지
            agv_ids = list(positions_at_t.keys())
            for i in range(len(agv_ids)):
                for j in range(i + 1, len(agv_ids)):
                    id_i = agv_ids[i]
                    id_j = agv_ids[j]
                    pos_i = positions_at_t[id_i]
                    pos_j = positions_at_t[id_j]
                    
                    # 거리 계산
                    distance = ((pos_i[0] - pos_j[0])**2 + (pos_i[1] - pos_j[1])**2) ** 0.5
                    
                    if distance < self._min_distance:
                        collision_pairs.append([id_i, id_j])
                        violations.append({
                            "step": t,
                            "constraint": "min_distance",
                            "agv_pair": [id_i, id_j],
                            "positions": {id_i: list(pos_i), id_j: list(pos_j)},
                            "distance": round(distance, 3),
                            "min_required": self._min_distance
                        })
            
            # 장애물 충돌 검사
            for agv_id, pos in positions_at_t.items():
                if pos in self._obstacles:
                    violations.append({
                        "step": t,
                        "constraint": "obstacle_collision",
                        "agv_id": agv_id,
                        "position": list(pos)
                    })
            
            # 그리드 범위 검사
            for agv_id, pos in positions_at_t.items():
                x, y = pos
                if x < 0 or x >= self._width or y < 0 or y >= self._height:
                    violations.append({
                        "step": t,
                        "constraint": "grid_boundary",
                        "agv_id": agv_id,
                        "position": list(pos),
                        "grid_size": [self._width, self._height]
                    })
        
        # Ruleset 기반 추가 검사
        ruleset = constraints.get("ruleset", [])
        for rule in ruleset:
            rule_type = rule.get("type", "") if isinstance(rule, dict) else getattr(rule, "type", "")
            if rule_type == "range":
                target = rule.get("target_field", "") if isinstance(rule, dict) else getattr(rule, "target_field", "")
                min_val = rule.get("min") if isinstance(rule, dict) else getattr(rule, "min", None)
                max_val = rule.get("max") if isinstance(rule, dict) else getattr(rule, "max", None)
                
                # 위치 범위 검사
                for t, positions in agv_timeline.items():
                    for agv_id, pos in positions.items():
                        if target == "position_x" and min_val is not None and max_val is not None:
                            if pos[0] < min_val or pos[0] > max_val:
                                violations.append({
                                    "step": t, "constraint": rule.get("rule_id", target),
                                    "value": pos[0], "limit": [min_val, max_val]
                                })
                        elif target == "position_y" and min_val is not None and max_val is not None:
                            if pos[1] < min_val or pos[1] > max_val:
                                violations.append({
                                    "step": t, "constraint": rule.get("rule_id", target),
                                    "value": pos[1], "limit": [min_val, max_val]
                                })
        
        # 결과 생성
        verdict = "UNSAFE" if violations else "SAFE"
        first_violation_step = violations[0]["step"] if violations else None
        violated_constraint = violations[0]["constraint"] if violations else None
        latency_ms = round((time.time() - start_time) * 1000, 3)
        
        # 중복 제거된 collision pairs
        unique_pairs = []
        seen = set()
        for pair in collision_pairs:
            key = tuple(sorted(pair))
            if key not in seen:
                seen.add(key)
                unique_pairs.append(list(key))
        
        return {
            "verdict": verdict,
            "engine": "discrete_event",
            "common": {
                "first_violation_step": first_violation_step,
                "violated_constraint": violated_constraint,
                "latency_ms": latency_ms,
                "steps_completed": max_steps
            },
            "details": {
                "event_log": event_log[:30],  # 처음 30개만
                "collision_pairs": unique_pairs,
                "deadlock_detected": False,  # 향후 구현
                "total_events": len(event_log),
                "violations": violations[:10],  # 처음 10개만
                "grid_size": [self._width, self._height],
                "agv_count": len(agv_positions)
            }
        }
    
    def shutdown(self) -> None:
        """정리"""
        self._initialized = False
    
    def _extract_agv_positions(self, current_state: dict) -> dict:
        """현재 상태에서 AGV 위치 추출"""
        positions = {}
        
        # 형태 1: {"agv_01": {"x": 0, "y": 0}, "agv_02": ...}
        for key, val in current_state.items():
            if key.startswith("agv_") and isinstance(val, dict):
                positions[key] = (val.get("x", 0), val.get("y", 0))
        
        # 형태 2: {"position_x": 5, "position_y": 5} (단일 AGV)
        if not positions and "position_x" in current_state:
            positions["agv_01"] = (
                current_state.get("position_x", 0),
                current_state.get("position_y", 0)
            )
        
        # 위치 정보 없으면 config에서 가져옴
        if not positions:
            for agv_id, agv_conf in self._agv_config.items():
                pos = agv_conf.get("position", [0, 0])
                positions[agv_id] = (pos[0], pos[1])
        
        return positions
    
    def _generate_simple_path(self, start, target):
        """시작점에서 목표점까지 단순 경로 생성 (맨해튼 경로)"""
        path = []
        x, y = start
        tx, ty = target
        
        # 먼저 X축 이동, 그 다음 Y축 이동
        while x != tx:
            x += 1 if tx > x else -1
            path.append((x, y))
        while y != ty:
            y += 1 if ty > y else -1
            path.append((x, y))
        
        return path
