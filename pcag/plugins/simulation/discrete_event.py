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

import simpy

from pcag.core.ports.simulation_backend import ISimulationBackend

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERSISTENT_VIEWER_STATE = (
    PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "results" / "agv_gui_state_latest.json"
)
DEFAULT_PERSISTENT_VIEWER_PID = (
    PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "results" / "agv_gui_viewer.pid"
)


DEFAULT_GRID_CONFIG = {
    "width": 10,
    "height": 10,
    "obstacles": [],
    "intersections": [],
    "agvs": {
        "agv_01": {"position": [0, 0], "speed": 1.0},
        "agv_02": {"position": [9, 9], "speed": 1.0},
    },
    "min_distance": 1.0,
    "visualization": {
        "enabled": False,
        "mode": "persistent",
        "cell_px": 56,
        "step_delay_ms": 250,
        "hold_final_ms": 1500,
        "show_paths": True,
        "show_coordinates": True,
    },
}


def _truthy_env(*names: str) -> bool:
    return any((os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}) for name in names)


class DiscreteEventBackend(ISimulationBackend):
    """Grid-based AGV discrete-event validator with optional GUI replay."""

    def __init__(self) -> None:
        self._initialized = False
        self._width = DEFAULT_GRID_CONFIG["width"]
        self._height = DEFAULT_GRID_CONFIG["height"]
        self._obstacles: set[tuple[int, int]] = set()
        self._intersections: set[tuple[int, int]] = set()
        self._agv_config: dict[str, dict[str, Any]] = {}
        self._min_distance = DEFAULT_GRID_CONFIG["min_distance"]
        self._visualization: dict[str, Any] = dict(DEFAULT_GRID_CONFIG["visualization"])

    def initialize(self, config: dict) -> None:
        grid_config = config.get("grid", {})
        self._width = int(grid_config.get("width", DEFAULT_GRID_CONFIG["width"]))
        self._height = int(grid_config.get("height", DEFAULT_GRID_CONFIG["height"]))
        self._obstacles = {tuple(item) for item in grid_config.get("obstacles", DEFAULT_GRID_CONFIG["obstacles"])}
        self._intersections = {tuple(item) for item in grid_config.get("intersections", DEFAULT_GRID_CONFIG["intersections"])}
        self._agv_config = json.loads(json.dumps(config.get("agvs", DEFAULT_GRID_CONFIG["agvs"])))
        self._min_distance = float(config.get("min_distance", DEFAULT_GRID_CONFIG["min_distance"]))
        self._visualization = self._resolve_visualization_config(config.get("visualization", {}))
        self._initialized = True
        logger.info(
            "Discrete Event Simulator initialized: %sx%s grid, %s AGVs",
            self._width,
            self._height,
            len(self._agv_config),
        )

    def validate_trajectory(
        self,
        current_state: dict,
        action_sequence: list[dict],
        constraints: dict,
    ) -> dict:
        if not self._initialized:
            self.initialize({})

        start_time = time.time()
        agv_positions = self._extract_agv_positions(current_state)
        agv_paths = self._extract_agv_paths(action_sequence, agv_positions)
        max_steps = max((len(path) for path in agv_paths.values()), default=0)

        event_log: list[dict[str, Any]] = []
        collision_pairs: list[list[str]] = []
        timeline_frames: list[dict[str, Any]] = []
        all_violations: list[dict[str, Any]] = []
        agv_timeline: dict[int, dict[str, tuple[int | float, int | float]]] = {}
        ruleset = constraints.get("ruleset", [])

        # Keep SimPy imported and available as the discrete-event modeling substrate.
        simpy.Environment()

        for step in range(max_steps + 1):
            positions_at_step = self._positions_for_step(step, agv_positions, agv_paths)
            next_positions = self._positions_for_step(min(step + 1, max_steps), agv_positions, agv_paths)
            agv_timeline[step] = positions_at_step
            step_violations = self._detect_step_violations(
                step,
                positions_at_step,
                next_positions,
                ruleset,
                collision_pairs,
            )
            all_violations.extend(step_violations)
            timeline_frames.append(
                {
                    "step": step,
                    "positions": {agv_id: [pos[0], pos[1]] for agv_id, pos in positions_at_step.items()},
                    "violations": json.loads(json.dumps(step_violations)),
                }
            )

            for agv_id, pos in positions_at_step.items():
                event_log.append({"t_step": step, "event": f"{agv_id}_at", "location": [pos[0], pos[1]]})

        verdict = "UNSAFE" if all_violations else "SAFE"
        latency_ms = round((time.time() - start_time) * 1000, 3)
        first_violation_step = all_violations[0]["step"] if all_violations else None
        violated_constraint = all_violations[0]["constraint"] if all_violations else None
        unique_pairs = self._dedupe_collision_pairs(collision_pairs)
        deadlock_cycles = [
            violation["agv_cycle"]
            for violation in all_violations
            if violation.get("constraint") == "deadlock_cycle" and violation.get("agv_cycle")
        ]
        edge_conflicts = [
            violation["agv_pair"]
            for violation in all_violations
            if violation.get("constraint") == "edge_swap_conflict" and violation.get("agv_pair")
        ]

        visualization_rendered = False
        if self._visualization.get("enabled"):
            visualization_rendered = self._render_visualization(
                timeline_frames=timeline_frames,
                agv_paths=agv_paths,
                initial_positions=agv_positions,
                verdict=verdict,
                violations=all_violations,
            )

        return {
            "verdict": verdict,
            "engine": "discrete_event",
            "common": {
                "first_violation_step": first_violation_step,
                "violated_constraint": violated_constraint,
                "latency_ms": latency_ms,
                "steps_completed": max_steps,
            },
            "details": {
                "event_log": event_log[:30],
                "collision_pairs": unique_pairs,
                "deadlock_detected": bool(deadlock_cycles),
                "deadlock_cycles": deadlock_cycles,
                "edge_conflicts": edge_conflicts,
                "total_events": len(event_log),
                "violations": all_violations[:10],
                "grid_size": [self._width, self._height],
                "agv_count": len(agv_positions),
                "visualization_enabled": bool(self._visualization.get("enabled")),
                "visualization_rendered": visualization_rendered,
            },
        }

    def shutdown(self) -> None:
        self._initialized = False

    def _resolve_visualization_config(self, config: dict[str, Any]) -> dict[str, Any]:
        merged = dict(DEFAULT_GRID_CONFIG["visualization"])
        merged.update(config or {})
        env_enabled = _truthy_env("PCAG_AGV_GUI", "PCAG_ENABLE_AGV_GUI")
        merged["enabled"] = bool(merged.get("enabled") or env_enabled)
        merged["mode"] = str(merged.get("mode") or os.environ.get("PCAG_AGV_GUI_MODE", "persistent")).strip().lower()
        merged["cell_px"] = int(merged.get("cell_px", 56))
        merged["step_delay_ms"] = int(merged.get("step_delay_ms", 250))
        merged["hold_final_ms"] = int(merged.get("hold_final_ms", 1500))
        merged["show_paths"] = bool(merged.get("show_paths", True))
        merged["show_coordinates"] = bool(merged.get("show_coordinates", True))
        merged["window_title"] = merged.get("window_title") or "PCAG AGV Grid Viewer"
        merged["poll_interval_ms"] = int(merged.get("poll_interval_ms", 250))
        merged["state_file"] = str(Path(merged.get("state_file") or os.environ.get("PCAG_AGV_GUI_STATE_FILE", str(DEFAULT_PERSISTENT_VIEWER_STATE))).resolve())
        merged["pid_file"] = str(Path(merged.get("pid_file") or os.environ.get("PCAG_AGV_GUI_PID_FILE", str(DEFAULT_PERSISTENT_VIEWER_PID))).resolve())
        return merged

    def _extract_agv_positions(self, current_state: dict) -> dict[str, tuple[int | float, int | float]]:
        positions = {
            agv_id: tuple(agv_conf.get("position", [0, 0]))
            for agv_id, agv_conf in self._agv_config.items()
        }

        for key, value in current_state.items():
            if key.startswith("agv_") and isinstance(value, dict):
                positions[key] = (value.get("x", 0), value.get("y", 0))

        if "position_x" in current_state:
            positions["agv_01"] = (current_state.get("position_x", 0), current_state.get("position_y", 0))

        return positions

    def _extract_agv_paths(
        self,
        action_sequence: list[dict[str, Any]],
        agv_positions: dict[str, tuple[int | float, int | float]],
    ) -> dict[str, list[tuple[int | float, int | float]]]:
        agv_paths: dict[str, list[tuple[int | float, int | float]]] = {}

        for agv_id, agv_conf in self._agv_config.items():
            configured_path = agv_conf.get("path")
            if configured_path:
                agv_paths[agv_id] = [tuple(point) for point in configured_path]

        for action in action_sequence:
            if action.get("action_type") != "move_to":
                continue

            params = action.get("params", {})
            agv_id = params.get("agv_id", "agv_01")
            if "path" in params:
                agv_paths[agv_id] = [tuple(point) for point in params["path"]]
                continue

            if "target_x" not in params or "target_y" not in params:
                continue

            target_x = params.get("target_x")
            target_y = params.get("target_y")
            if target_x is not None and not isinstance(target_x, (int, float)):
                raise ValueError(f"target_x must be numeric, got {type(target_x).__name__}: {target_x}")
            if target_y is not None and not isinstance(target_y, (int, float)):
                raise ValueError(f"target_y must be numeric, got {type(target_y).__name__}: {target_y}")

            current = agv_positions.get(agv_id, (0, 0))
            agv_paths[agv_id] = self._generate_simple_path(current, (target_x, target_y))

        return agv_paths

    def _positions_for_step(
        self,
        step: int,
        initial_positions: dict[str, tuple[int | float, int | float]],
        agv_paths: dict[str, list[tuple[int | float, int | float]]],
    ) -> dict[str, tuple[int | float, int | float]]:
        positions: dict[str, tuple[int | float, int | float]] = {}

        for agv_id, start_pos in initial_positions.items():
            path = agv_paths.get(agv_id, [])
            if step == 0:
                pos = start_pos
            elif step <= len(path):
                pos = path[step - 1]
            else:
                pos = path[-1] if path else start_pos
            positions[agv_id] = pos

        return positions

    def _detect_step_violations(
        self,
        step: int,
        positions_at_step: dict[str, tuple[int | float, int | float]],
        next_positions: dict[str, tuple[int | float, int | float]],
        ruleset: list[dict[str, Any]],
        collision_pairs: list[list[str]],
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        agv_ids = list(positions_at_step.keys())

        for i in range(len(agv_ids)):
            for j in range(i + 1, len(agv_ids)):
                agv_a = agv_ids[i]
                agv_b = agv_ids[j]
                pos_a = positions_at_step[agv_a]
                pos_b = positions_at_step[agv_b]
                distance = ((pos_a[0] - pos_b[0]) ** 2 + (pos_a[1] - pos_b[1]) ** 2) ** 0.5
                if distance < self._min_distance:
                    collision_pairs.append([agv_a, agv_b])
                    violations.append(
                        {
                            "step": step,
                            "constraint": "min_distance",
                            "agv_pair": [agv_a, agv_b],
                            "positions": {agv_a: [pos_a[0], pos_a[1]], agv_b: [pos_b[0], pos_b[1]]},
                            "distance": round(distance, 3),
                            "min_required": self._min_distance,
                        }
                    )

        violations.extend(self._detect_edge_swap_conflicts(step, positions_at_step, next_positions, collision_pairs))
        violations.extend(self._detect_deadlock_cycles(step, positions_at_step, next_positions))

        for agv_id, pos in positions_at_step.items():
            if tuple(pos) in self._obstacles:
                violations.append({"step": step, "constraint": "obstacle_collision", "agv_id": agv_id, "position": [pos[0], pos[1]]})

            x, y = pos
            if x < 0 or x >= self._width or y < 0 or y >= self._height:
                violations.append(
                    {
                        "step": step,
                        "constraint": "grid_boundary",
                        "agv_id": agv_id,
                        "position": [x, y],
                        "grid_size": [self._width, self._height],
                    }
                )

        for rule in ruleset:
            rule_type = rule.get("type", "") if isinstance(rule, dict) else getattr(rule, "type", "")
            if rule_type != "range":
                continue
            target = rule.get("target_field", "") if isinstance(rule, dict) else getattr(rule, "target_field", "")
            min_val = rule.get("min") if isinstance(rule, dict) else getattr(rule, "min", None)
            max_val = rule.get("max") if isinstance(rule, dict) else getattr(rule, "max", None)
            for pos in positions_at_step.values():
                if target == "position_x" and min_val is not None and max_val is not None and (pos[0] < min_val or pos[0] > max_val):
                    violations.append({"step": step, "constraint": rule.get("rule_id", target), "value": pos[0], "limit": [min_val, max_val]})
                if target == "position_y" and min_val is not None and max_val is not None and (pos[1] < min_val or pos[1] > max_val):
                    violations.append({"step": step, "constraint": rule.get("rule_id", target), "value": pos[1], "limit": [min_val, max_val]})

        return violations

    def _detect_edge_swap_conflicts(
        self,
        step: int,
        positions_at_step: dict[str, tuple[int | float, int | float]],
        next_positions: dict[str, tuple[int | float, int | float]],
        collision_pairs: list[list[str]],
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        agv_ids = list(positions_at_step.keys())
        for i in range(len(agv_ids)):
            for j in range(i + 1, len(agv_ids)):
                agv_a = agv_ids[i]
                agv_b = agv_ids[j]
                current_a = positions_at_step[agv_a]
                current_b = positions_at_step[agv_b]
                next_a = next_positions.get(agv_a, current_a)
                next_b = next_positions.get(agv_b, current_b)
                if next_a == current_b and next_b == current_a and current_a != current_b:
                    collision_pairs.append([agv_a, agv_b])
                    violations.append(
                        {
                            "step": step,
                            "constraint": "edge_swap_conflict",
                            "agv_pair": [agv_a, agv_b],
                            "positions": {
                                agv_a: {"current": [current_a[0], current_a[1]], "next": [next_a[0], next_a[1]]},
                                agv_b: {"current": [current_b[0], current_b[1]], "next": [next_b[0], next_b[1]]},
                            },
                        }
                    )
        return violations

    def _detect_deadlock_cycles(
        self,
        step: int,
        positions_at_step: dict[str, tuple[int | float, int | float]],
        next_positions: dict[str, tuple[int | float, int | float]],
    ) -> list[dict[str, Any]]:
        occupancy = {tuple(pos): agv_id for agv_id, pos in positions_at_step.items()}
        wait_for: dict[str, str] = {}
        desired_positions: dict[str, tuple[int | float, int | float]] = {}

        for agv_id, current_pos in positions_at_step.items():
            next_pos = next_positions.get(agv_id, current_pos)
            if next_pos == current_pos:
                continue
            blocker = occupancy.get(tuple(next_pos))
            if blocker and blocker != agv_id:
                wait_for[agv_id] = blocker
                desired_positions[agv_id] = next_pos

        if not wait_for:
            return []

        violations: list[dict[str, Any]] = []
        emitted_cycles: set[tuple[str, ...]] = set()
        visited: set[str] = set()

        for start in list(wait_for):
            if start in visited:
                continue
            traversal: list[str] = []
            seen_index: dict[str, int] = {}
            node = start

            while node in wait_for and node not in seen_index:
                seen_index[node] = len(traversal)
                traversal.append(node)
                node = wait_for[node]

            visited.update(traversal)
            if node not in seen_index:
                continue

            cycle = traversal[seen_index[node] :]
            if len(cycle) < 2:
                continue

            if len(cycle) == 2:
                agv_a, agv_b = cycle
                current_a = positions_at_step[agv_a]
                current_b = positions_at_step[agv_b]
                next_a = next_positions.get(agv_a, current_a)
                next_b = next_positions.get(agv_b, current_b)
                if next_a == current_b and next_b == current_a:
                    continue

            cycle_key = tuple(sorted(cycle))
            if cycle_key in emitted_cycles:
                continue
            emitted_cycles.add(cycle_key)

            violations.append(
                {
                    "step": step,
                    "constraint": "deadlock_cycle",
                    "agv_cycle": cycle,
                    "desired_positions": {
                        agv_id: [desired_positions[agv_id][0], desired_positions[agv_id][1]]
                        for agv_id in cycle
                        if agv_id in desired_positions
                    },
                    "positions": {
                        agv_id: [positions_at_step[agv_id][0], positions_at_step[agv_id][1]]
                        for agv_id in cycle
                    },
                }
            )

        return violations

    def _dedupe_collision_pairs(self, collision_pairs: list[list[str]]) -> list[list[str]]:
        unique_pairs: list[list[str]] = []
        seen: set[tuple[str, str]] = set()
        for pair in collision_pairs:
            key = tuple(sorted(pair))
            if key in seen:
                continue
            seen.add(key)
            unique_pairs.append(list(key))
        return unique_pairs

    def _generate_simple_path(
        self,
        start: tuple[int | float, int | float],
        target: tuple[int | float, int | float],
    ) -> list[tuple[int | float, int | float]]:
        path: list[tuple[int | float, int | float]] = []
        x, y = start
        target_x, target_y = target

        while x != target_x:
            x += 1 if target_x > x else -1
            path.append((x, y))

        while y != target_y:
            y += 1 if target_y > y else -1
            path.append((x, y))

        return path

    def _render_visualization(
        self,
        *,
        timeline_frames: list[dict[str, Any]],
        agv_paths: dict[str, list[tuple[int | float, int | float]]],
        initial_positions: dict[str, tuple[int | float, int | float]],
        verdict: str,
        violations: list[dict[str, Any]],
    ) -> bool:
        payload = {
            "session_id": f"agv-gui-{time.time_ns()}",
            "case_id": self._visualization.get("case_id") or self._visualization.get("window_title"),
            "window_title": self._visualization.get("window_title"),
            "grid": {
                "width": self._width,
                "height": self._height,
                "obstacles": [list(item) for item in sorted(self._obstacles)],
                "intersections": [list(item) for item in sorted(self._intersections)],
            },
            "initial_positions": {agv_id: [pos[0], pos[1]] for agv_id, pos in initial_positions.items()},
            "paths": {agv_id: [[point[0], point[1]] for point in path] for agv_id, path in agv_paths.items()},
            "timeline_frames": timeline_frames,
            "verdict": verdict,
            "violations": violations,
            "visualization": self._visualization,
        }

        viewer_path = Path(__file__).resolve().with_name("agv_grid_viewer.py")
        if not viewer_path.exists():
            logger.warning("AGV grid viewer not found: %s", viewer_path)
            return False

        if self._visualization.get("mode") == "persistent":
            return self._render_visualization_persistent(payload, viewer_path)

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
                temp_path = Path(handle.name)

            timeout_s = max(15.0, ((len(timeline_frames) * self._visualization["step_delay_ms"]) + max(self._visualization["hold_final_ms"], 0)) / 1000.0 + 10.0)
            completed = subprocess.run(
                [sys.executable, str(viewer_path), str(temp_path)],
                check=False,
                timeout=timeout_s,
            )
            if completed.returncode != 0:
                logger.warning("AGV grid viewer exited with code %s", completed.returncode)
                return False
            return True
        except Exception as exc:
            logger.warning("Failed to render AGV visualization: %s", exc, exc_info=True)
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
            logger.warning("Failed to update persistent AGV viewer: %s", exc, exc_info=True)
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
