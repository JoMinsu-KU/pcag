from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERSISTENT_VIEWER_STATE = (
    PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "results" / "process_gui_state_latest.json"
)
DEFAULT_PERSISTENT_VIEWER_PID = (
    PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "results" / "process_gui_viewer.pid"
)

DEFAULT_REACTOR_PARAMS = {
    "mass_kg": 1.0,
    "specific_heat_j_kg_k": 4186.0,
    "heater_max_power_w": 20000.0,
    "heat_transfer_coeff_w_k": 100.0,
    "coolant_temp_c": 20.0,
    "ambient_temp_c": 25.0,
    "loss_coeff_w_k": 5.0,
    "pressure_coeff_atm_k": 0.01,
}

DEFAULT_VISUALIZATION = {
    "enabled": False,
    "mode": "persistent",
    "step_delay_ms": 200,
    "hold_final_ms": 1500,
    "poll_interval_ms": 250,
    "window_title": "PCAG Reactor Viewer",
}


def _truthy_env(*names: str) -> bool:
    return any((os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}) for name in names)


class ODESolverBackend(ISimulationBackend):
    """Thermal-reactor ODE validator with optional process GUI replay."""

    def __init__(self) -> None:
        self._params: dict[str, Any] = {}
        self._horizon_ms = 5000
        self._dt_ms = 100
        self._timeout_ms = 200
        self._visualization: dict[str, Any] = dict(DEFAULT_VISUALIZATION)
        self._initialized = False

    def initialize(self, config: dict) -> None:
        params_config = config.get("params", {})
        self._params = {**DEFAULT_REACTOR_PARAMS, **params_config}
        self._horizon_ms = int(config.get("horizon_ms", 5000))
        self._dt_ms = int(config.get("dt_ms", 100))
        self._timeout_ms = int(config.get("timeout_ms", 200))
        self._visualization = self._resolve_visualization_config(config.get("visualization", {}))
        self._initialized = True
        logger.info("ODE Solver initialized: %s", self._params)

    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict,
    ) -> dict:
        if not self._initialized:
            self.initialize({})

        start_time = time.time()
        current_values = {
            "temperature": self._require_numeric(current_state, "temperature"),
            "pressure": self._require_numeric(current_state, "pressure"),
            "heater_output": self._require_numeric(current_state, "heater_output"),
            "cooling_valve": self._require_numeric(current_state, "cooling_valve"),
        }
        ruleset = constraints.get("ruleset", [])

        trajectory: list[dict[str, Any]] = [self._make_point(0, current_values)]
        violations: list[dict[str, Any]] = []
        first_violation_step: int | None = None
        max_temperature = current_values["temperature"]
        max_pressure = current_values["pressure"]

        total_t_ms = 0
        heater_frac = current_values["heater_output"] / 100.0
        cooling_frac = current_values["cooling_valve"] / 100.0

        if action_sequence:
            for step_idx, action in enumerate(action_sequence):
                action_type = action.get("action_type", "")
                params = action.get("params", {})
                duration_ms = int(action.get("duration_ms", self._horizon_ms // max(len(action_sequence), 1)))
                heater_frac, cooling_frac = self._apply_action_controls(
                    action_type,
                    params,
                    heater_frac=heater_frac,
                    cooling_frac=cooling_frac,
                )

                try:
                    sol = self._solve_segment(
                        current_temperature=current_values["temperature"],
                        current_pressure=current_values["pressure"],
                        heater_frac=heater_frac,
                        cooling_frac=cooling_frac,
                        duration_ms=duration_ms,
                    )
                except Exception as exc:
                    logger.error("ODE simulation error: %s", exc)
                    return self._make_result(
                        verdict="INDETERMINATE",
                        trajectory=trajectory,
                        violations=violations,
                        first_violation_step=first_violation_step,
                        start_time=start_time,
                        visualization_rendered=False,
                        extra_details={"reason": f"ODE error: {exc}"},
                    )

                (
                    current_values,
                    max_temperature,
                    max_pressure,
                    first_violation_step,
                ) = self._record_segment(
                    sol=sol,
                    total_t_ms=total_t_ms,
                    step_idx=step_idx,
                    heater_frac=heater_frac,
                    cooling_frac=cooling_frac,
                    trajectory=trajectory,
                    violations=violations,
                    ruleset=ruleset,
                    current_values=current_values,
                    max_temperature=max_temperature,
                    max_pressure=max_pressure,
                    first_violation_step=first_violation_step,
                )
                total_t_ms += duration_ms

                if (time.time() - start_time) * 1000 > self._timeout_ms:
                    return self._make_result(
                        verdict="INDETERMINATE",
                        trajectory=trajectory,
                        violations=violations,
                        first_violation_step=first_violation_step,
                        start_time=start_time,
                        visualization_rendered=False,
                        extra_details={"reason": "Simulation timeout"},
                    )
        else:
            try:
                sol = self._solve_segment(
                    current_temperature=current_values["temperature"],
                    current_pressure=current_values["pressure"],
                    heater_frac=heater_frac,
                    cooling_frac=cooling_frac,
                    duration_ms=self._horizon_ms,
                )
            except Exception as exc:
                logger.error("ODE simulation error: %s", exc)
                return self._make_result(
                    verdict="INDETERMINATE",
                    trajectory=trajectory,
                    violations=violations,
                    first_violation_step=first_violation_step,
                    start_time=start_time,
                    visualization_rendered=False,
                    extra_details={"reason": f"ODE error: {exc}"},
                )

            (
                current_values,
                max_temperature,
                max_pressure,
                first_violation_step,
            ) = self._record_segment(
                sol=sol,
                total_t_ms=0,
                step_idx=0,
                heater_frac=heater_frac,
                cooling_frac=cooling_frac,
                trajectory=trajectory,
                violations=violations,
                ruleset=ruleset,
                current_values=current_values,
                max_temperature=max_temperature,
                max_pressure=max_pressure,
                first_violation_step=first_violation_step,
            )

        verdict = "UNSAFE" if violations else "SAFE"
        visualization_rendered = False
        if self._visualization.get("enabled"):
            visualization_rendered = self._render_visualization(
                trajectory=trajectory,
                verdict=verdict,
                violations=violations,
                safe_ranges=self._extract_safe_ranges(ruleset),
            )

        return self._make_result(
            verdict=verdict,
            trajectory=trajectory,
            violations=violations,
            first_violation_step=first_violation_step,
            start_time=start_time,
            visualization_rendered=visualization_rendered,
            extra_details={
                "max_value": {
                    "temperature": round(max_temperature, 3),
                    "pressure": round(max_pressure, 3),
                }
            },
        )

    def shutdown(self) -> None:
        self._initialized = False

    def _require_numeric(self, current_state: dict[str, Any], field: str) -> float:
        if field not in current_state:
            raise ValueError(f"ODE Solver: Missing required field '{field}' in current_state")
        value = current_state[field]
        if not isinstance(value, (int, float)):
            raise ValueError(f"ODE Solver: Field '{field}' must be numeric, got {type(value).__name__}")
        return float(value)

    def _resolve_visualization_config(self, config: dict[str, Any]) -> dict[str, Any]:
        merged = dict(DEFAULT_VISUALIZATION)
        merged.update(config or {})
        env_enabled = _truthy_env("PCAG_PROCESS_GUI", "PCAG_ENABLE_PROCESS_GUI")
        merged["enabled"] = bool(merged.get("enabled") or env_enabled)
        merged["mode"] = str(merged.get("mode") or os.environ.get("PCAG_PROCESS_GUI_MODE", "persistent")).strip().lower()
        merged["step_delay_ms"] = int(merged.get("step_delay_ms", 200))
        merged["hold_final_ms"] = int(merged.get("hold_final_ms", 1500))
        merged["poll_interval_ms"] = int(merged.get("poll_interval_ms", 250))
        merged["window_title"] = merged.get("window_title") or "PCAG Reactor Viewer"
        merged["state_file"] = str(
            Path(
                merged.get("state_file") or os.environ.get("PCAG_PROCESS_GUI_STATE_FILE", str(DEFAULT_PERSISTENT_VIEWER_STATE))
            ).resolve()
        )
        merged["pid_file"] = str(
            Path(
                merged.get("pid_file") or os.environ.get("PCAG_PROCESS_GUI_PID_FILE", str(DEFAULT_PERSISTENT_VIEWER_PID))
            ).resolve()
        )
        return merged

    def _build_t_eval(self, duration_ms: int) -> np.ndarray:
        duration_ms = max(int(duration_ms), self._dt_ms)
        duration_s = duration_ms / 1000.0
        steps = max(int(round(duration_ms / self._dt_ms)), 1)
        return np.linspace(0.0, duration_s, steps + 1)

    def _solve_segment(
        self,
        *,
        current_temperature: float,
        current_pressure: float,
        heater_frac: float,
        cooling_frac: float,
        duration_ms: int,
    ):
        duration_ms = max(int(duration_ms), self._dt_ms)
        duration_s = duration_ms / 1000.0
        t_eval = self._build_t_eval(duration_ms)
        sol = solve_ivp(
            fun=lambda t, y: self._reactor_ode(t, y, heater_frac, cooling_frac),
            t_span=(0.0, duration_s),
            y0=[current_temperature, current_pressure],
            t_eval=t_eval,
            method="RK45",
            max_step=max(self._dt_ms / 1000.0, 0.05),
        )
        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")
        return sol

    def _apply_action_controls(
        self,
        action_type: str,
        params: dict[str, Any],
        *,
        heater_frac: float,
        cooling_frac: float,
    ) -> tuple[float, float]:
        if action_type == "set_heater_output":
            heater_frac = float(params.get("value", heater_frac * 100.0)) / 100.0
        elif action_type == "set_cooling_valve":
            cooling_frac = float(params.get("value", cooling_frac * 100.0)) / 100.0
        return heater_frac, cooling_frac

    def _make_point(self, t_ms: int, values: dict[str, float]) -> dict[str, Any]:
        return {
            "t_ms": int(t_ms),
            "temperature": round(float(values["temperature"]), 3),
            "pressure": round(float(values["pressure"]), 3),
            "heater_output": round(float(values["heater_output"]), 3),
            "cooling_valve": round(float(values["cooling_valve"]), 3),
        }

    def _record_segment(
        self,
        *,
        sol,
        total_t_ms: int,
        step_idx: int,
        heater_frac: float,
        cooling_frac: float,
        trajectory: list[dict[str, Any]],
        violations: list[dict[str, Any]],
        ruleset: list[dict[str, Any]],
        current_values: dict[str, float],
        max_temperature: float,
        max_pressure: float,
        first_violation_step: int | None,
    ) -> tuple[dict[str, float], float, float, int | None]:
        heater_output = heater_frac * 100.0
        cooling_valve = cooling_frac * 100.0

        for index in range(1, len(sol.t)):
            temperature = float(sol.y[0][index])
            pressure = float(sol.y[1][index])
            current_values = {
                "temperature": temperature,
                "pressure": pressure,
                "heater_output": heater_output,
                "cooling_valve": cooling_valve,
            }
            point = self._make_point(total_t_ms + int(round(sol.t[index] * 1000)), current_values)
            trajectory.append(point)
            max_temperature = max(max_temperature, temperature)
            max_pressure = max(max_pressure, pressure)

            violation = self._check_constraints(current_values, ruleset)
            if violation:
                violations.append(
                    {
                        "step": step_idx,
                        "t_ms": point["t_ms"],
                        "constraint": violation["constraint"],
                        "value": violation["value"],
                        "limit": violation["limit"],
                    }
                )
                if first_violation_step is None:
                    first_violation_step = step_idx

        return current_values, max_temperature, max_pressure, first_violation_step

    def _reactor_ode(self, t: float, state: list[float], heater_frac: float, cooling_frac: float) -> list[float]:
        temperature, pressure = state
        params = self._params
        heater_power = heater_frac * params["heater_max_power_w"]
        cooling_power = cooling_frac * params["heat_transfer_coeff_w_k"] * (temperature - params["coolant_temp_c"])
        heat_loss = params["loss_coeff_w_k"] * (temperature - params["ambient_temp_c"])
        d_temperature_dt = (heater_power - cooling_power - heat_loss) / (params["mass_kg"] * params["specific_heat_j_kg_k"])
        d_pressure_dt = params["pressure_coeff_atm_k"] * d_temperature_dt
        return [d_temperature_dt, d_pressure_dt]

    def _check_constraints(self, state_snapshot: dict[str, float], ruleset: list[dict[str, Any]]) -> dict[str, Any] | None:
        for rule in ruleset:
            rule_id = rule.get("rule_id", "")
            rule_type = rule.get("type", "")
            target = rule.get("target_field", "")
            if target not in state_snapshot:
                continue

            value = float(state_snapshot[target])
            if rule_type == "threshold":
                operator = rule.get("operator", "lte")
                limit = rule.get("value")
                if limit is None:
                    continue
                if operator in {"lte", "lt"} and value > float(limit):
                    return {"constraint": rule_id, "value": round(value, 3), "limit": float(limit)}
                if operator in {"gte", "gt"} and value < float(limit):
                    return {"constraint": rule_id, "value": round(value, 3), "limit": float(limit)}
            elif rule_type == "range":
                min_val = rule.get("min")
                max_val = rule.get("max")
                if min_val is not None and value < float(min_val):
                    return {"constraint": rule_id, "value": round(value, 3), "limit": [float(min_val), float(max_val) if max_val is not None else None]}
                if max_val is not None and value > float(max_val):
                    return {"constraint": rule_id, "value": round(value, 3), "limit": [float(min_val) if min_val is not None else None, float(max_val)]}
        return None

    def _extract_safe_ranges(self, ruleset: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        safe_ranges: dict[str, dict[str, float]] = {}
        for rule in ruleset:
            target = rule.get("target_field")
            if not target:
                continue
            if rule.get("type") == "range":
                safe_ranges[target] = {
                    "min": float(rule["min"]) if rule.get("min") is not None else float("-inf"),
                    "max": float(rule["max"]) if rule.get("max") is not None else float("inf"),
                }
            elif rule.get("type") == "threshold":
                operator = rule.get("operator", "lte")
                value = float(rule["value"])
                current = safe_ranges.setdefault(target, {"min": float("-inf"), "max": float("inf")})
                if operator in {"lte", "lt"}:
                    current["max"] = min(current["max"], value)
                elif operator in {"gte", "gt"}:
                    current["min"] = max(current["min"], value)
        return safe_ranges

    def _make_result(
        self,
        *,
        verdict: str,
        trajectory: list[dict[str, Any]],
        violations: list[dict[str, Any]],
        first_violation_step: int | None,
        start_time: float,
        visualization_rendered: bool,
        extra_details: dict[str, Any],
    ) -> dict[str, Any]:
        latency_ms = round((time.time() - start_time) * 1000, 3)
        violated_constraint = violations[0]["constraint"] if violations else None
        return {
            "verdict": verdict,
            "engine": "ode_solver",
            "common": {
                "first_violation_step": first_violation_step,
                "violated_constraint": violated_constraint,
                "latency_ms": latency_ms,
                "steps_completed": max(len(trajectory) - 1, 0),
            },
            "details": {
                "state_trajectory": trajectory[:40],
                "trajectory_points": len(trajectory),
                "convergence": verdict != "INDETERMINATE",
                "solver_steps": len(trajectory),
                "violations": violations[:10],
                "visualization_enabled": bool(self._visualization.get("enabled")),
                "visualization_rendered": visualization_rendered,
                **extra_details,
            },
        }

    def _render_visualization(
        self,
        *,
        trajectory: list[dict[str, Any]],
        verdict: str,
        violations: list[dict[str, Any]],
        safe_ranges: dict[str, dict[str, float]],
    ) -> bool:
        payload = {
            "session_id": f"process-gui-{time.time_ns()}",
            "case_id": self._visualization.get("case_id") or self._visualization.get("window_title"),
            "window_title": self._visualization.get("window_title"),
            "trajectory": trajectory,
            "verdict": verdict,
            "violations": violations,
            "safe_ranges": safe_ranges,
            "visualization": self._visualization,
        }

        viewer_path = Path(__file__).resolve().with_name("process_reactor_viewer.py")
        if not viewer_path.exists():
            logger.warning("Process reactor viewer not found: %s", viewer_path)
            return False

        if self._visualization.get("mode") == "persistent":
            return self._render_visualization_persistent(payload, viewer_path)

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
                temp_path = Path(handle.name)

            timeout_s = max(
                15.0,
                ((len(trajectory) * self._visualization["step_delay_ms"]) + max(self._visualization["hold_final_ms"], 0)) / 1000.0
                + 10.0,
            )
            completed = subprocess.run([sys.executable, str(viewer_path), str(temp_path)], check=False, timeout=timeout_s)
            if completed.returncode != 0:
                logger.warning("Process reactor viewer exited with code %s", completed.returncode)
                return False
            return True
        except Exception as exc:
            logger.warning("Failed to render process visualization: %s", exc, exc_info=True)
            return False
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _render_visualization_persistent(self, payload: dict[str, Any], viewer_path: Path) -> bool:
        state_path = Path(self._visualization["state_file"])
        pid_path = Path(self._visualization["pid_file"])
        state_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._ensure_persistent_viewer(viewer_path, state_path, pid_path)
            return True
        except Exception as exc:
            logger.warning("Failed to update persistent process viewer: %s", exc, exc_info=True)
            return False

    def _ensure_persistent_viewer(self, viewer_path: Path, state_path: Path, pid_path: Path) -> None:
        existing_pid: int | None = None
        if pid_path.exists():
            try:
                existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
            except Exception:
                existing_pid = None

        if existing_pid and self._is_process_alive(existing_pid):
            return

        creationflags = 0
        startup_kwargs: dict[str, Any] = {}
        if sys.platform.startswith("win"):
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            startup_kwargs["close_fds"] = True

        process = subprocess.Popen(
            [sys.executable, str(viewer_path), "--watch", str(state_path), "--pid-file", str(pid_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            **startup_kwargs,
        )
        pid_path.write_text(str(process.pid), encoding="utf-8")

    def _is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False
