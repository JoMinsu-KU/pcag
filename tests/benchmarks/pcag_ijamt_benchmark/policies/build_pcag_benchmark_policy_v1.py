from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
POLICY_DIR = Path(__file__).resolve().parent
if str(POLICY_DIR) not in sys.path:
    sys.path.insert(0, str(POLICY_DIR))

from build_agv_benchmark_policy_v1 import AGV_ASSET_POLICY
from build_process_benchmark_policy_v1 import PROCESS_ASSET_POLICY


ROBOT_POLICY_PATH = POLICY_DIR / "robot_pcag_benchmark_policy_v1.json"
OUTPUT_PATH = POLICY_DIR / "pcag_benchmark_policy_v1.json"

UNIFIED_POLICY_VERSION = "v2026-03-20-pcag-benchmark-v1"
UNIFIED_POLICY_PROFILE = "pcag_benchmark_v1"


def build_policy() -> dict:
    base_policy = json.loads(ROBOT_POLICY_PATH.read_text(encoding="utf-8"))
    robot_asset_policy = json.loads(json.dumps(base_policy["assets"]["robot_arm_01"]))

    policy = json.loads(json.dumps(base_policy))
    policy["policy_version_id"] = UNIFIED_POLICY_VERSION
    policy["global_policy"]["metadata"] = {
        "benchmark_profile": UNIFIED_POLICY_PROFILE,
        "scope": "Unified benchmark policy for robot, AGV, and process integrated execution datasets",
        "description": (
            "Unified benchmark policy aligned to the expanded robot v4, AGV v3, "
            "and process v2 PCAG execution datasets."
        ),
    }
    policy["assets"] = {
        "robot_arm_01": robot_asset_policy,
        "agv_01": json.loads(json.dumps(AGV_ASSET_POLICY)),
        "reactor_01": json.loads(json.dumps(PROCESS_ASSET_POLICY)),
    }
    return policy


def main() -> None:
    policy = build_policy()
    OUTPUT_PATH.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote unified benchmark policy to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
