from __future__ import annotations

import argparse
import json
import tkinter as tk
from pathlib import Path
from typing import Any


GRID_BG = "#f7f7f3"
GRID_LINE = "#c9c8bf"
OBSTACLE_FILL = "#2f3640"
INTERSECTION_OUTLINE = "#f1c40f"
PATH_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
AGV_COLORS = ["#0f4c81", "#d35400", "#198754", "#b2182b"]
VIOLATION_FILL = "#e74c3c"
TEXT_COLOR = "#232323"


class AGVGridViewer:
    def __init__(self, payload: dict[str, Any] | None = None, *, watch_path: Path | None = None, pid_file: Path | None = None) -> None:
        self.payload = payload
        self.watch_path = watch_path
        self.pid_file = pid_file
        self.root = tk.Tk()
        self.root.configure(bg=GRID_BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.canvas = tk.Canvas(self.root, bg=GRID_BG, highlightthickness=0)
        self.canvas.pack()

        self.margin = 36
        self.info_width = 300
        self.canvas_width = 0
        self.canvas_height = 0
        self.width = 0
        self.height = 0
        self.cell_px = 56
        self.step_delay_ms = 250
        self.hold_final_ms = 1500
        self.show_paths = True
        self.show_coordinates = True
        self.poll_interval_ms = 250
        self.dynamic_tags = ["agv", "status", "violation"]
        self.current_index = 0
        self.frames: list[dict[str, Any]] = []
        self.paths: dict[str, list[list[float]]] = {}
        self.grid: dict[str, Any] = {"width": 1, "height": 1, "obstacles": [], "intersections": []}
        self.verdict = "UNKNOWN"
        self.last_session_id: str | None = None
        self._animation_after_id: str | None = None
        self._watch_after_id: str | None = None
        self._last_watch_mtime_ns: int | None = None

    def run(self) -> int:
        if self.payload is not None:
            self._load_payload(self.payload)
        else:
            self.root.title("PCAG AGV Grid Viewer")
            self.canvas.config(width=760, height=480)
            self.canvas.create_text(380, 240, text="Waiting for AGV benchmark payload...", fill=TEXT_COLOR, font=("Segoe UI", 14, "bold"))

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
        self.grid = payload["grid"]
        visual = payload.get("visualization", {})
        self.cell_px = int(visual.get("cell_px", 56))
        self.step_delay_ms = int(visual.get("step_delay_ms", 250))
        self.hold_final_ms = int(visual.get("hold_final_ms", 1500))
        self.show_paths = bool(visual.get("show_paths", True))
        self.show_coordinates = bool(visual.get("show_coordinates", True))
        self.poll_interval_ms = int(visual.get("poll_interval_ms", 250))
        self.width = int(self.grid["width"])
        self.height = int(self.grid["height"])
        self.canvas_width = self.margin * 2 + self.width * self.cell_px
        self.canvas_height = self.margin * 2 + self.height * self.cell_px
        self.frames = payload["timeline_frames"]
        self.paths = payload.get("paths", {})
        self.verdict = payload.get("verdict", "UNKNOWN")
        self.current_index = 0

        if self._animation_after_id:
            self.root.after_cancel(self._animation_after_id)
            self._animation_after_id = None

        title = payload.get("window_title", "PCAG AGV Grid Viewer")
        case_id = payload.get("case_id")
        if case_id:
            title = f"{title} | {case_id}"
        self.root.title(title)
        self.root.resizable(False, False)
        self.canvas.config(width=self.canvas_width + self.info_width, height=self.canvas_height)
        self.canvas.delete("all")
        self._draw_static_scene()
        self._render_frame(0)
        self._animation_after_id = self.root.after(self.step_delay_ms, self._advance)

    def _grid_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        canvas_x = self.margin + (x + 0.5) * self.cell_px
        canvas_y = self.margin + (self.height - y - 0.5) * self.cell_px
        return canvas_x, canvas_y

    def _cell_rect(self, x: float, y: float) -> tuple[float, float, float, float]:
        cx, cy = self._grid_to_canvas(x, y)
        half = self.cell_px / 2
        return cx - half, cy - half, cx + half, cy + half

    def _draw_static_scene(self) -> None:
        for x in range(self.width):
            for y in range(self.height):
                x0, y0, x1, y1 = self._cell_rect(x, y)
                self.canvas.create_rectangle(x0, y0, x1, y1, outline=GRID_LINE, fill=GRID_BG)

        for obstacle in self.grid.get("obstacles", []):
            x0, y0, x1, y1 = self._cell_rect(obstacle[0], obstacle[1])
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=OBSTACLE_FILL, outline=OBSTACLE_FILL)

        for intersection in self.grid.get("intersections", []):
            x0, y0, x1, y1 = self._cell_rect(intersection[0], intersection[1])
            self.canvas.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4, outline=INTERSECTION_OUTLINE, width=3)

        if self.show_paths:
            for index, (agv_id, path) in enumerate(self.paths.items()):
                color = PATH_COLORS[index % len(PATH_COLORS)]
                points: list[float] = []
                for point in path:
                    px, py = self._grid_to_canvas(point[0], point[1])
                    points.extend([px, py])
                if len(points) >= 4:
                    self.canvas.create_line(*points, fill=color, width=3, dash=(5, 3))
                self.canvas.create_text(
                    self.canvas_width + 20,
                    30 + index * 20,
                    text=f"{agv_id} path",
                    anchor="w",
                    fill=color,
                    font=("Segoe UI", 10, "bold"),
                )

        self.canvas.create_text(
            self.canvas_width + 20,
            self.canvas_height - 120,
            text=f"Grid: {self.width} x {self.height}",
            anchor="w",
            fill=TEXT_COLOR,
            font=("Segoe UI", 10),
        )
        self.canvas.create_text(
            self.canvas_width + 20,
            self.canvas_height - 95,
            text=f"Verdict: {self.verdict}",
            anchor="w",
            fill=VIOLATION_FILL if self.verdict == "UNSAFE" else "#1e8449",
            font=("Segoe UI", 11, "bold"),
        )

    def _render_frame(self, index: int) -> None:
        frame = self.frames[index]
        self.canvas.delete(*self.dynamic_tags)

        step_y = 90
        self.canvas.create_text(
            self.canvas_width + 20,
            step_y,
            text=f"Step: {frame['step']} / {len(self.frames) - 1}",
            anchor="w",
            fill=TEXT_COLOR,
            font=("Segoe UI", 11, "bold"),
            tags="status",
        )

        positions_y = step_y + 30
        for agv_index, (agv_id, position) in enumerate(frame["positions"].items()):
            color = AGV_COLORS[agv_index % len(AGV_COLORS)]
            cx, cy = self._grid_to_canvas(position[0], position[1])
            radius = self.cell_px * 0.28
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=color, outline="white", width=2, tags="agv")
            self.canvas.create_text(cx, cy, text=agv_id.replace("agv_", "A"), fill="white", font=("Segoe UI", 10, "bold"), tags="agv")
            label = f"{agv_id}: ({position[0]}, {position[1]})"
            self.canvas.create_text(
                self.canvas_width + 20,
                positions_y + agv_index * 22,
                text=label,
                anchor="w",
                fill=color,
                font=("Segoe UI", 10),
                tags="status",
            )

        active_violations = frame.get("violations", [])
        violation_y = positions_y + max(len(frame["positions"]), 1) * 22 + 24
        if not active_violations:
            self.canvas.create_text(
                self.canvas_width + 20,
                violation_y,
                text="Violations: none",
                anchor="w",
                fill="#1e8449",
                font=("Segoe UI", 10, "bold"),
                tags="status",
            )
            return

        self.canvas.create_text(
            self.canvas_width + 20,
            violation_y,
            text="Violations:",
            anchor="w",
            fill=VIOLATION_FILL,
            font=("Segoe UI", 10, "bold"),
            tags="status",
        )
        for idx, violation in enumerate(active_violations[:4]):
            text = self._format_violation(violation)
            self.canvas.create_text(
                self.canvas_width + 20,
                violation_y + 22 + idx * 22,
                text=text,
                anchor="w",
                fill=VIOLATION_FILL,
                font=("Segoe UI", 9),
                tags="status",
            )
            self._highlight_violation(violation)

    def _highlight_violation(self, violation: dict[str, Any]) -> None:
        positions = []
        if "position" in violation:
            positions.append(violation["position"])
        if "positions" in violation:
            positions.extend(violation["positions"].values())
        for position in positions:
            x0, y0, x1, y1 = self._cell_rect(position[0], position[1])
            self.canvas.create_rectangle(x0 + 5, y0 + 5, x1 - 5, y1 - 5, outline=VIOLATION_FILL, width=4, tags="violation")

    def _format_violation(self, violation: dict[str, Any]) -> str:
        constraint = violation.get("constraint", "unknown")
        if constraint == "min_distance":
            pair = "/".join(violation.get("agv_pair", []))
            return f"- {constraint}: {pair} dist={violation.get('distance')}"
        if "position" in violation:
            position = violation["position"]
            return f"- {constraint}: ({position[0]}, {position[1]})"
        return f"- {constraint}"

    def _advance(self) -> None:
        if self.current_index + 1 < len(self.frames):
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
    parser = argparse.ArgumentParser(description="Render AGV discrete-event benchmark payloads.")
    parser.add_argument("payload_path", nargs="?", type=Path)
    parser.add_argument("--watch", type=Path, default=None)
    parser.add_argument("--pid-file", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.watch is None and args.payload_path is None:
        print("Usage: agv_grid_viewer.py <payload.json> or agv_grid_viewer.py --watch <state.json>")
        return 1

    payload = None
    if args.payload_path is not None:
        payload = json.loads(args.payload_path.read_text(encoding="utf-8"))

    viewer = AGVGridViewer(payload, watch_path=args.watch, pid_file=args.pid_file)
    return viewer.run()


if __name__ == "__main__":
    raise SystemExit(main())
