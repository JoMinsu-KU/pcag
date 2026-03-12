"""
ODE Solver Simulation Backend — 시나리오 A 화학 반응기
=======================================================
scipy.integrate.solve_ivp를 사용하여 화학 반응기의 온도/압력을
수치적으로 예측합니다.

PCAG 파이프라인 [120-123]:
  Safety Cluster → Simulation Validator → ODE Solver
  → 현재 상태 + action_sequence → 미래 상태 예측 → SAFE/UNSAFE

장비 물리 파라미터는 설정에서 분리 (Decision SIM-1):
  수식 구조: 코드에 고정
  파라미터 (mass, specific_heat 등): config에서 로드

conda pcag 환경에서 실행.
"""
import time
import logging
import numpy as np
from scipy.integrate import solve_ivp
from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)

# 기본 반응기 파라미터 (config로 오버라이드 가능)
DEFAULT_REACTOR_PARAMS = {
    "mass_kg": 1.0,                      # 반응기 내용물 질량 (kg) - 빠른 반응을 위해 축소
    "specific_heat_j_kg_k": 4186.0,      # 비열 (J/(kg·K)) — 물 기준
    "heater_max_power_w": 20000.0,       # 히터 최대 출력 (W) - 빠른 반응을 위해 증가
    "heat_transfer_coeff_w_k": 100.0,    # 냉각 열전달 계수 (W/K)
    "coolant_temp_c": 20.0,              # 냉각수 온도 (°C)
    "ambient_temp_c": 25.0,              # 주변 온도 (°C)
    "loss_coeff_w_k": 5.0,              # 자연 방열 계수 (W/K)
    "pressure_coeff_atm_k": 0.01,        # 압력-온도 연동 계수 (atm/K) — 이상기체 근사
}


class ODESolverBackend(ISimulationBackend):
    """
    ODE Solver 시뮬레이션 백엔드 — 화학 반응기 미래 예측
    
    동작:
    1. initialize(): 반응기 물리 파라미터 로드
    2. validate_trajectory(): 
       - 현재 센서 상태(온도, 압력)에서 시작
       - 각 action(히터 출력, 밸브 조절)을 적용
       - ODE를 수치 적분하여 미래 온도/압력 궤적 계산
       - 매 시뮬레이션 스텝마다 제약조건(ruleset) 검사
       - 위반 발견 시 UNSAFE, 전부 통과 시 SAFE
    3. shutdown(): 정리 (할 것 없음)
    """
    
    def __init__(self):
        self._params = {}
        self._initialized = False
    
    def initialize(self, config: dict) -> None:
        """
        반응기 물리 파라미터 로드
        
        config 예시:
        {
            "engine": "ode_solver",
            "model_type": "thermal_reactor",
            "params": {
                "mass_kg": 100.0,
                "specific_heat_j_kg_k": 4186.0,
                ...
            },
            "horizon_ms": 5000,   # 시뮬레이션 시간 범위 (ms)
            "dt_ms": 100,         # 시뮬레이션 스텝 크기 (ms)
            "timeout_ms": 200     # 시뮬레이션 최대 실행 시간
        }
        """
        # 파라미터 로드 (config에 있으면 사용, 없으면 기본값)
        params_config = config.get("params", {})
        self._params = {**DEFAULT_REACTOR_PARAMS, **params_config}
        
        # 시뮬레이션 설정
        self._horizon_ms = config.get("horizon_ms", 5000)   # 5초 기본
        self._dt_ms = config.get("dt_ms", 100)              # 100ms 스텝
        self._timeout_ms = config.get("timeout_ms", 200)     # 200ms 타임아웃
        
        self._initialized = True
        logger.info(f"ODE Solver initialized: {self._params}")
    
    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict
    ) -> dict:
        """
        미래 궤적 검증 — ODE 수치 적분
        
        Args:
            current_state: {"temperature": 150.0, "pressure": 1.5, "heater_output": 50.0, "cooling_valve": 80.0}
            action_sequence: [{"action_type": "set_heater_output", "params": {"value": 90}}, ...]
            constraints: {"ruleset": [...]} — 안전 규칙 리스트
        
        Returns:
            SimulationResult dict with ode_solver_details
        """
        if not self._initialized:
            self.initialize({})
        
        start_time = time.time()
        
        # 현재 상태 추출
        if "temperature" not in current_state:
            raise ValueError(f"ODE Solver: Missing required field 'temperature' in current_state")
        T0 = float(current_state["temperature"])

        if "pressure" not in current_state:
            raise ValueError(f"ODE Solver: Missing required field 'pressure' in current_state")
        P0 = float(current_state["pressure"])

        if "heater_output" not in current_state:
            raise ValueError(f"ODE Solver: Missing required field 'heater_output' in current_state")
        heater_output = float(current_state["heater_output"]) / 100.0  # 비율로 변환 (0~1)

        if "cooling_valve" not in current_state:
            raise ValueError(f"ODE Solver: Missing required field 'cooling_valve' in current_state")
        cooling_valve = float(current_state["cooling_valve"]) / 100.0
        
        # 제약 조건 추출
        ruleset = constraints.get("ruleset", [])
        
        # 전체 궤적 기록
        trajectory = []
        violations = []
        first_violation_step = None
        
        # 초기 상태 기록
        trajectory.append({
            "t_ms": 0,
            "temperature": round(T0, 3),
            "pressure": round(P0, 3)
        })
        
        # 각 action을 순서대로 적용하여 시뮬레이션
        current_T = T0
        current_P = P0
        total_t_ms = 0
        
        for step_idx, action in enumerate(action_sequence):
            action_type = action.get("action_type", "")
            params = action.get("params", {})
            duration_ms = action.get("duration_ms", self._horizon_ms // max(len(action_sequence), 1))
            
            # action에 따라 제어 입력 변경
            if action_type == "set_heater_output":
                heater_output = params.get("value", heater_output * 100) / 100.0
            elif action_type == "set_cooling_valve":
                cooling_valve = params.get("value", cooling_valve * 100) / 100.0
            
            # ODE 수치 적분
            t_span = (0, duration_ms / 1000.0)  # 초 단위
            t_eval = np.arange(0, duration_ms / 1000.0 + self._dt_ms / 1000.0, self._dt_ms / 1000.0)
            
            try:
                sol = solve_ivp(
                    fun=lambda t, y: self._reactor_ode(t, y, heater_output, cooling_valve),
                    t_span=t_span,
                    y0=[current_T, current_P],
                    t_eval=t_eval,
                    method='RK45',
                    max_step=0.1
                )
                
                if not sol.success:
                    logger.warning(f"ODE solver failed: {sol.message}")
                    return self._make_result("INDETERMINATE", trajectory, violations, 
                                           first_violation_step, start_time, 
                                           {"reason": f"ODE solver failed: {sol.message}"})
                
                # 궤적 기록 + 제약 검사
                for i in range(len(sol.t)):
                    T_i = sol.y[0][i]
                    P_i = sol.y[1][i]
                    t_ms_i = total_t_ms + int(sol.t[i] * 1000)
                    
                    trajectory.append({
                        "t_ms": t_ms_i,
                        "temperature": round(float(T_i), 3),
                        "pressure": round(float(P_i), 3)
                    })
                    
                    # 제약 조건 검사
                    violation = self._check_constraints(T_i, P_i, ruleset)
                    if violation and first_violation_step is None:
                        first_violation_step = step_idx
                        violations.append({
                            "step": step_idx,
                            "t_ms": t_ms_i,
                            "constraint": violation["constraint"],
                            "value": violation["value"],
                            "limit": violation["limit"]
                        })
                
                # 마지막 상태 업데이트
                current_T = float(sol.y[0][-1])
                current_P = float(sol.y[1][-1])
                total_t_ms += duration_ms
                
            except Exception as e:
                logger.error(f"ODE simulation error: {e}")
                return self._make_result("INDETERMINATE", trajectory, violations,
                                       first_violation_step, start_time,
                                       {"reason": f"ODE error: {str(e)}"})
            
            # 타임아웃 체크
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > self._timeout_ms:
                return self._make_result("INDETERMINATE", trajectory, violations,
                                       first_violation_step, start_time,
                                       {"reason": "Simulation timeout"})
        
        # action이 없으면 현재 상태에서 horizon만큼 시뮬레이션
        if not action_sequence:
            t_span = (0, self._horizon_ms / 1000.0)
            t_eval = np.arange(0, self._horizon_ms / 1000.0 + self._dt_ms / 1000.0, self._dt_ms / 1000.0)
            
            try:
                sol = solve_ivp(
                    fun=lambda t, y: self._reactor_ode(t, y, heater_output, cooling_valve),
                    t_span=t_span,
                    y0=[current_T, current_P],
                    t_eval=t_eval,
                    method='RK45'
                )
                
                for i in range(len(sol.t)):
                    T_i = sol.y[0][i]
                    P_i = sol.y[1][i]
                    trajectory.append({
                        "t_ms": int(sol.t[i] * 1000),
                        "temperature": round(float(T_i), 3),
                        "pressure": round(float(P_i), 3)
                    })
                    
                    violation = self._check_constraints(T_i, P_i, ruleset)
                    if violation and first_violation_step is None:
                        first_violation_step = 0
                        violations.append({
                            "step": 0, "t_ms": int(sol.t[i] * 1000),
                            "constraint": violation["constraint"],
                            "value": violation["value"],
                            "limit": violation["limit"]
                        })
                        
            except Exception as e:
                return self._make_result("INDETERMINATE", trajectory, violations,
                                       first_violation_step, start_time,
                                       {"reason": str(e)})
        
        # 최종 판정
        verdict = "UNSAFE" if violations else "SAFE"
        
        return self._make_result(verdict, trajectory, violations, 
                               first_violation_step, start_time, {})
    
    def shutdown(self) -> None:
        """정리 (ODE Solver는 특별히 정리할 것 없음)"""
        self._initialized = False
    
    def _reactor_ode(self, t, state, heater_frac, cooling_frac):
        """
        화학 반응기 ODE 수식
        
        dT/dt = (Q_heater - Q_cooling - Q_loss) / (m × Cp)
        dP/dt = pressure_coeff × dT/dt
        
        Args:
            t: 시간 (초)
            state: [T, P] — 온도(°C), 압력(atm)
            heater_frac: 히터 출력 비율 (0~1)
            cooling_frac: 냉각 밸브 개도 비율 (0~1)
        """
        T, P = state
        p = self._params
        
        Q_heater = heater_frac * p["heater_max_power_w"]
        Q_cooling = cooling_frac * p["heat_transfer_coeff_w_k"] * (T - p["coolant_temp_c"])
        Q_loss = p["loss_coeff_w_k"] * (T - p["ambient_temp_c"])
        
        dT_dt = (Q_heater - Q_cooling - Q_loss) / (p["mass_kg"] * p["specific_heat_j_kg_k"])
        dP_dt = p["pressure_coeff_atm_k"] * dT_dt
        
        return [dT_dt, dP_dt]
    
    def _check_constraints(self, T, P, ruleset):
        """제약 조건 검사 — 온도/압력이 안전 범위 내인지"""
        for rule in ruleset:
            rule_id = rule.get("rule_id", "") if isinstance(rule, dict) else getattr(rule, "rule_id", "")
            rule_type = rule.get("type", "") if isinstance(rule, dict) else getattr(rule, "type", "")
            target = rule.get("target_field", "") if isinstance(rule, dict) else getattr(rule, "target_field", "")
            
            # 온도/압력 값 매핑
            if target == "temperature":
                value = T
            elif target == "pressure":
                value = P
            else:
                continue
            
            if rule_type == "threshold":
                operator = rule.get("operator", "lte") if isinstance(rule, dict) else getattr(rule, "operator", "lte")
                limit = rule.get("value") if isinstance(rule, dict) else getattr(rule, "value", None)
                if limit is None:
                    continue
                    
                if operator in ("lte", "lt") and value > limit:
                    return {"constraint": rule_id, "value": round(float(value), 3), "limit": limit}
                elif operator in ("gte", "gt") and value < limit:
                    return {"constraint": rule_id, "value": round(float(value), 3), "limit": limit}
                    
            elif rule_type == "range":
                min_val = rule.get("min") if isinstance(rule, dict) else getattr(rule, "min", None)
                max_val = rule.get("max") if isinstance(rule, dict) else getattr(rule, "max", None)
                if min_val is not None and value < min_val:
                    return {"constraint": rule_id, "value": round(float(value), 3), "limit": [min_val, max_val]}
                if max_val is not None and value > max_val:
                    return {"constraint": rule_id, "value": round(float(value), 3), "limit": [min_val, max_val]}
        
        return None
    
    def _make_result(self, verdict, trajectory, violations, first_violation_step, start_time, extra_details):
        """SimulationResult dict 생성"""
        latency_ms = round((time.time() - start_time) * 1000, 3)
        
        # 궤적에서 최대/최소값 추출
        temps = [p["temperature"] for p in trajectory if "temperature" in p]
        pressures = [p["pressure"] for p in trajectory if "pressure" in p]
        
        max_values = {}
        if temps:
            max_values["temperature"] = round(max(temps), 3)
        if pressures:
            max_values["pressure"] = round(max(pressures), 3)
        
        violated_constraint = None
        if violations:
            violated_constraint = violations[0]["constraint"]
        
        return {
            "verdict": verdict,
            "engine": "ode_solver",
            "common": {
                "first_violation_step": first_violation_step,
                "violated_constraint": violated_constraint,
                "latency_ms": latency_ms,
                "steps_completed": len(trajectory) - 1  # 초기 상태 제외
            },
            "details": {
                "state_trajectory": trajectory[:20],  # 처음 20개만 (너무 많으면 잘림)
                "max_value": max_values,
                "convergence": verdict != "INDETERMINATE",
                "solver_steps": len(trajectory),
                "violations": violations,
                **extra_details
            }
        }
