from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from pcag.plugins.simulation.discrete_event import (
    DEFAULT_PERSISTENT_VIEWER_PID as DEFAULT_AGV_PID,
    DEFAULT_PERSISTENT_VIEWER_STATE as DEFAULT_AGV_STATE,
)
from pcag.plugins.simulation.ode_solver import (
    DEFAULT_PERSISTENT_VIEWER_PID as DEFAULT_PROCESS_PID,
    DEFAULT_PERSISTENT_VIEWER_STATE as DEFAULT_PROCESS_STATE,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGV_VIEWER_SCRIPT = PROJECT_ROOT / "pcag" / "plugins" / "simulation" / "agv_grid_viewer.py"
PROCESS_VIEWER_SCRIPT = PROJECT_ROOT / "pcag" / "plugins" / "simulation" / "process_reactor_viewer.py"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _start_watcher(*, viewer_script: Path, state_path: Path, pid_path: Path) -> int | None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    if pid_path.exists():
        try:
            existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
        except Exception:
            existing_pid = None
        if existing_pid and _is_process_alive(existing_pid):
            return existing_pid

    startup_kwargs: dict[str, object] = {}
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        startup_kwargs["close_fds"] = True

    process = subprocess.Popen(
        [sys.executable, str(viewer_script), "--watch", str(state_path), "--pid-file", str(pid_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        **startup_kwargs,
    )
    pid_path.write_text(str(process.pid), encoding="utf-8")
    return process.pid


def ensure_benchmark_viewers_started() -> dict[str, int | None]:
    unified = _truthy(os.environ.get("PCAG_ENABLE_BENCHMARK_TWIN_GUIS"))
    if unified:
        os.environ["PCAG_ENABLE_AGV_GUI"] = "true"
        os.environ["PCAG_ENABLE_PROCESS_GUI"] = "true"
        os.environ["PCAG_AGV_GUI"] = "true"
        os.environ["PCAG_PROCESS_GUI"] = "true"

    results: dict[str, int | None] = {"agv": None, "process": None}

    if _truthy(os.environ.get("PCAG_ENABLE_AGV_GUI")):
        os.environ["PCAG_AGV_GUI"] = "true"
        pid = _start_watcher(
            viewer_script=AGV_VIEWER_SCRIPT,
            state_path=Path(os.environ.get("PCAG_AGV_GUI_STATE_FILE", str(DEFAULT_AGV_STATE))).resolve(),
            pid_path=Path(os.environ.get("PCAG_AGV_GUI_PID_FILE", str(DEFAULT_AGV_PID))).resolve(),
        )
        results["agv"] = pid
        logger.info("AGV benchmark viewer ready (pid=%s)", pid)

    if _truthy(os.environ.get("PCAG_ENABLE_PROCESS_GUI")):
        os.environ["PCAG_PROCESS_GUI"] = "true"
        pid = _start_watcher(
            viewer_script=PROCESS_VIEWER_SCRIPT,
            state_path=Path(os.environ.get("PCAG_PROCESS_GUI_STATE_FILE", str(DEFAULT_PROCESS_STATE))).resolve(),
            pid_path=Path(os.environ.get("PCAG_PROCESS_GUI_PID_FILE", str(DEFAULT_PROCESS_PID))).resolve(),
        )
        results["process"] = pid
        logger.info("Process benchmark viewer ready (pid=%s)", pid)

    return results


def shutdown_benchmark_viewers() -> None:
    for env_name, default_pid_path in (
        ("PCAG_AGV_GUI_PID_FILE", DEFAULT_AGV_PID),
        ("PCAG_PROCESS_GUI_PID_FILE", DEFAULT_PROCESS_PID),
    ):
        pid_path = Path(os.environ.get(env_name, str(default_pid_path))).resolve()
        if not pid_path.exists():
            continue
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
        except Exception:
            pid = None
        if pid and _is_process_alive(pid):
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        try:
            pid_path.unlink(missing_ok=True)
        except Exception:
            pass
