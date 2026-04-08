from __future__ import annotations

import argparse
import json
import tkinter as tk
from pathlib import Path
from typing import Any


BG = "#f5f3ee"
PANEL_BG = "#ffffff"
TEXT = "#222222"
GRID = "#d9d4c8"
TEMP_COLOR = "#d35400"
PRESSURE_COLOR = "#1f78b4"
HEATER_COLOR = "#c0392b"
COOLING_COLOR = "#16a085"
SAFE_FILL = "#dff3e6"
UNSAFE_FILL = "#fbe1df"
ACCENT = "#5f6b7a"


class ProcessReactorViewer:
    def __init__(self, payload: dict[str, Any] | None = None, *, watch_path: Path | None = None, pid_file: Path | None = None) -> None:
        self.payload = payload
        self.watch_path = watch_path
        self.pid_file = pid_file
        self.root = tk.Tk()
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack()

        self.width = 1200
        self.height = 720
        self.step_delay_ms = 200
        self.hold_final_ms = 1500
        self.poll_interval_ms = 250
        self.current_index = 0
        self.trajectory: list[dict[str, Any]] = []
        self.safe_ranges: dict[str, dict[str, float]] = {}
        self.violations: list[dict[str, Any]] = []
        self.verdict = "UNKNOWN"
        self.last_session_id: str | None = None
        self._animation_after_id: str | None = None
        self._watch_after_id: str | None = None
        self._last_watch_mtime_ns: int | None = None

    def run(self) -> int:
        if self.payload is not None:
            self._load_payload(self.payload)
        else:
            self.root.title("PCAG Reactor Viewer")
            self.canvas.config(width=self.width, height=self.height)
            self.canvas.create_text(
                self.width / 2,
                self.height / 2,
                text="Waiting for reactor benchmark payload...",
                fill=TEXT,
                font=("Segoe UI", 15, "bold"),
            )

        if self.watch_path is not None:
            self._watch_after_id = self.root.after(self.poll_interval_ms, self._watch_loop)

        self.root.mainloop()
        return 0

    def _on_close(self) -> None:
        if self._animation_after_id:
            self.root.after_cancel(self._animation_after_id)
        if self._watch_after_id:
            self.root.after_cancel(self._watch_after_id)
        if self.pid_file is not None:
            try:
                self.pid_file.unlink(missing_ok=True)
            except Exception:
                pass
        self.root.destroy()

    def _watch_loop(self) -> None:
        try:
            if self.watch_path and self.watch_path.exists():
                stat = self.watch_path.stat()
                mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
                if self._last_watch_mtime_ns != mtime_ns:
                    payload = json.loads(self.watch_path.read_text(encoding="utf-8"))
                    session_id = payload.get("session_id")
                    if session_id != self.last_session_id:
                        self._load_payload(payload)
                    self._last_watch_mtime_ns = mtime_ns
        finally:
            self._watch_after_id = self.root.after(self.poll_interval_ms, self._watch_loop)

    def _load_payload(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.last_session_id = payload.get("session_id")
        visual = payload.get("visualization", {})
        self.step_delay_ms = int(visual.get("step_delay_ms", 200))
        self.hold_final_ms = int(visual.get("hold_final_ms", 1500))
        self.poll_interval_ms = int(visual.get("poll_interval_ms", 250))
        self.trajectory = payload.get("trajectory", [])
        self.safe_ranges = payload.get("safe_ranges", {})
        self.violations = payload.get("violations", [])
        self.verdict = payload.get("verdict", "UNKNOWN")
        self.current_index = 0

        if self._animation_after_id:
            self.root.after_cancel(self._animation_after_id)
            self._animation_after_id = None

        title = payload.get("window_title", "PCAG Reactor Viewer")
        case_id = payload.get("case_id")
        if case_id:
            title = f"{title} | {case_id}"
        self.root.title(title)
        self.root.resizable(False, False)
        self.canvas.config(width=self.width, height=self.height)
        self.canvas.delete("all")
        self._draw_static()
        self._render_frame(0)
        self._animation_after_id = self.root.after(self.step_delay_ms, self._advance)

    def _draw_static(self) -> None:
        self.canvas.create_rectangle(20, 20, 360, 700, fill=PANEL_BG, outline=GRID, width=2)
        self.canvas.create_rectangle(380, 20, 1180, 340, fill=PANEL_BG, outline=GRID, width=2)
        self.canvas.create_rectangle(380, 360, 1180, 700, fill=PANEL_BG, outline=GRID, width=2)

        self.canvas.create_text(40, 40, text="Reactor State", anchor="w", fill=TEXT, font=("Segoe UI", 16, "bold"))
        self.canvas.create_text(400, 40, text="Temperature / Pressure Trajectory", anchor="w", fill=TEXT, font=("Segoe UI", 16, "bold"))
        self.canvas.create_text(400, 380, text="Controls / Violations", anchor="w", fill=TEXT, font=("Segoe UI", 16, "bold"))

        vessel_fill = SAFE_FILL if self.verdict != "UNSAFE" else UNSAFE_FILL
        self.canvas.create_rectangle(90, 110, 290, 500, fill=vessel_fill, outline=ACCENT, width=3)
        self.canvas.create_rectangle(120, 80, 260, 110, fill=ACCENT, outline=ACCENT)
        self.canvas.create_text(190, 520, text=f"Verdict: {self.verdict}", fill=(TEMP_COLOR if self.verdict == "UNSAFE" else COOLING_COLOR), font=("Segoe UI", 13, "bold"))

    def _render_frame(self, index: int) -> None:
        if not self.trajectory:
            return

        frame = self.trajectory[index]
        self.canvas.delete("dynamic")
        temp = frame.get("temperature", 0.0)
        pressure = frame.get("pressure", 0.0)
        heater = frame.get("heater_output", 0.0)
        cooling = frame.get("cooling_valve", 0.0)
        t_ms = frame.get("t_ms", 0)

        self.canvas.create_text(50, 570, text=f"time: {t_ms} ms", anchor="w", fill=TEXT, font=("Segoe UI", 12, "bold"), tags="dynamic")
        self.canvas.create_text(50, 605, text=f"temperature: {temp:.3f} C", anchor="w", fill=TEMP_COLOR, font=("Segoe UI", 12), tags="dynamic")
        self.canvas.create_text(50, 635, text=f"pressure: {pressure:.3f} atm", anchor="w", fill=PRESSURE_COLOR, font=("Segoe UI", 12), tags="dynamic")
        self.canvas.create_text(50, 665, text=f"heater: {heater:.1f} %", anchor="w", fill=HEATER_COLOR, font=("Segoe UI", 12), tags="dynamic")
        self.canvas.create_text(50, 695, text=f"cooling: {cooling:.1f} %", anchor="w", fill=COOLING_COLOR, font=("Segoe UI", 12), tags="dynamic")

        self._draw_chart(
            x0=400,
            y0=70,
            width=740,
            height=240,
            field="temperature",
            current_index=index,
            color=TEMP_COLOR,
            title="temperature",
            unit="C",
            tags="dynamic",
        )
        self._draw_chart(
            x0=400,
            y0=420,
            width=340,
            height=200,
            field="pressure",
            current_index=index,
            color=PRESSURE_COLOR,
            title="pressure",
            unit="atm",
            tags="dynamic",
        )
        self._draw_chart(
            x0=780,
            y0=420,
            width=170,
            height=200,
            field="heater_output",
            current_index=index,
            color=HEATER_COLOR,
            title="heater",
            unit="%",
            tags="dynamic",
        )
        self._draw_chart(
            x0=970,
            y0=420,
            width=170,
            height=200,
            field="cooling_valve",
            current_index=index,
            color=COOLING_COLOR,
            title="cooling",
            unit="%",
            tags="dynamic",
        )

        violation_lines = self._active_violation_lines(t_ms)
        self.canvas.create_text(780, 640, text="Violations", anchor="w", fill=TEXT, font=("Segoe UI", 12, "bold"), tags="dynamic")
        if not violation_lines:
            self.canvas.create_text(780, 668, text="none", anchor="w", fill=COOLING_COLOR, font=("Segoe UI", 11, "bold"), tags="dynamic")
        else:
            for idx, line in enumerate(violation_lines[:4]):
                self.canvas.create_text(780, 668 + idx * 24, text=line, anchor="w", fill=TEMP_COLOR, font=("Segoe UI", 10), tags="dynamic")

    def _draw_chart(
        self,
        *,
        x0: int,
        y0: int,
        width: int,
        height: int,
        field: str,
        current_index: int,
        color: str,
        title: str,
        unit: str,
        tags: str,
    ) -> None:
        self.canvas.create_rectangle(x0, y0, x0 + width, y0 + height, outline=GRID, width=1, tags=tags)
        self.canvas.create_text(x0 + 10, y0 - 14, text=title, anchor="w", fill=TEXT, font=("Segoe UI", 11, "bold"), tags=tags)

        values = [float(point.get(field, 0.0)) for point in self.trajectory]
        if not values:
            return

        safe_range = self.safe_ranges.get(field)
        min_val = min(values)
        max_val = max(values)
        if safe_range:
            min_val = min(min_val, safe_range.get("min", min_val))
            max_val = max(max_val, safe_range.get("max", max_val))
        if max_val - min_val < 1e-6:
            max_val = min_val + 1.0

        def scale(idx: int, value: float) -> tuple[float, float]:
            x = x0 + 16 + (width - 32) * (idx / max(len(values) - 1, 1))
            y = y0 + height - 16 - (height - 32) * ((value - min_val) / (max_val - min_val))
            return x, y

        if safe_range:
            safe_min = safe_range.get("min", min_val)
            safe_max = safe_range.get("max", max_val)
            _, y_max = scale(0, safe_max)
            _, y_min = scale(0, safe_min)
            self.canvas.create_rectangle(x0 + 16, y_max, x0 + width - 16, y_min, fill="#edf8ee", outline="", tags=tags)
            self.canvas.create_text(x0 + width - 12, y_max, text=f"max {safe_max:.2f}", anchor="e", fill=ACCENT, font=("Segoe UI", 8), tags=tags)
            self.canvas.create_text(x0 + width - 12, y_min, text=f"min {safe_min:.2f}", anchor="e", fill=ACCENT, font=("Segoe UI", 8), tags=tags)

        points: list[float] = []
        for idx in range(current_index + 1):
            x, y = scale(idx, values[idx])
            points.extend([x, y])
        if len(points) >= 4:
            self.canvas.create_line(*points, fill=color, width=3, tags=tags)
        x_curr, y_curr = scale(current_index, values[current_index])
        self.canvas.create_oval(x_curr - 5, y_curr - 5, x_curr + 5, y_curr + 5, fill=color, outline="white", width=1, tags=tags)
        self.canvas.create_text(x0 + 12, y0 + 14, text=f"{values[current_index]:.3f} {unit}", anchor="w", fill=color, font=("Segoe UI", 10, "bold"), tags=tags)

    def _active_violation_lines(self, t_ms: int) -> list[str]:
        lines: list[str] = []
        for violation in self.violations:
            if int(violation.get("t_ms", -1)) > t_ms:
                continue
            constraint = violation.get("constraint", "unknown")
            value = violation.get("value")
            limit = violation.get("limit")
            lines.append(f"- {constraint}: {value} / {limit}")
        return lines

    def _advance(self) -> None:
        if self.current_index + 1 < len(self.trajectory):
            self.current_index += 1
            self._render_frame(self.current_index)
            self._animation_after_id = self.root.after(self.step_delay_ms, self._advance)
            return

        self._animation_after_id = None
        if self.hold_final_ms < 0:
            return
        if self.watch_path is not None:
            return
        self._animation_after_id = self.root.after(self.hold_final_ms, self.root.destroy)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render reactor/process ODE benchmark payloads.")
    parser.add_argument("payload_path", nargs="?", type=Path)
    parser.add_argument("--watch", type=Path, default=None)
    parser.add_argument("--pid-file", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.watch is None and args.payload_path is None:
        print("Usage: process_reactor_viewer.py <payload.json> or process_reactor_viewer.py --watch <state.json>")
        return 1

    payload = None
    if args.payload_path is not None:
        payload = json.loads(args.payload_path.read_text(encoding="utf-8"))

    viewer = ProcessReactorViewer(payload, watch_path=args.watch, pid_file=args.pid_file)
    return viewer.run()


if __name__ == "__main__":
    raise SystemExit(main())
