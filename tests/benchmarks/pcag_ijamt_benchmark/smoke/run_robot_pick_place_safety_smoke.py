from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    target = Path(__file__).with_name("run_robot_stack_safety_smoke.py")
    sys.argv = [str(target), "--shell-id", "robot_pick_place_cell", *sys.argv[1:]]
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
