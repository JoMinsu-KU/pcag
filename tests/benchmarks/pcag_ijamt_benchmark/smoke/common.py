from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BENCHMARK_ROOT = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark"
SCENE_PACK_ROOT = BENCHMARK_ROOT / "scene_pack"


def load_shell_config(*shell_parts: str) -> tuple[Path, dict[str, Any]]:
    shell_dir = SCENE_PACK_ROOT.joinpath(*shell_parts)
    config = json.loads((shell_dir / "shell_config.json").read_text(encoding="utf-8"))
    return shell_dir, config


def resolve_relative_ref(shell_dir: Path, ref: str | None) -> str | None:
    if not ref:
        return ref
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return str(ref_path)
    return str((shell_dir / ref_path).resolve())


def print_banner(title: str) -> None:
    print("=" * 72)
    print(title)
    print("=" * 72)

