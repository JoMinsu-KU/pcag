"""
Build the canonical `robot_stack_cell` benchmark shell.

This shell is the preferred Franka-aligned robot environment for the first
dataset release because both IsaacLab and MimicGen expose stack-family source
tasks that can be normalized into this runtime envelope.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


SHELL_ID = "robot_stack_cell"
SCENE_FILE = f"{SHELL_ID}.usd"
CONFIG_FILE = "shell_config.json"


def build_usd_text() -> str:
    return dedent(
        """\
        #usda 1.0
        (
            defaultPrim = "World"
            metersPerUnit = 1
            upAxis = "Z"
        )

        def Xform "World"
        {
            def Xform "Environment"
            {
                def Cube "CellFloor"
                {
                    double size = 1
                    double3 xformOp:translate = (0.58, 0.0, 0.01)
                    double3 xformOp:scale = (1.62, 1.24, 0.02)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.22, 0.24, 0.27)]
                }

                def Cube "RobotMount"
                {
                    double size = 1
                    double3 xformOp:translate = (0.0, 0.0, 0.015)
                    double3 xformOp:scale = (0.22, 0.22, 0.03)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.36, 0.38, 0.42)]
                }

                def Cube "Workbench"
                {
                    double size = 1
                    double3 xformOp:translate = (0.64, 0.0, 0.44)
                    double3 xformOp:scale = (1.16, 0.84, 0.08)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.34, 0.35, 0.36)]
                }

                def Cube "InfeedBase"
                {
                    double size = 1
                    double3 xformOp:translate = (0.30, -0.34, 0.53)
                    double3 xformOp:scale = (0.42, 0.18, 0.04)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.16, 0.18, 0.20)]
                }

                def Cube "InfeedBelt"
                {
                    double size = 1
                    double3 xformOp:translate = (0.30, -0.34, 0.575)
                    double3 xformOp:scale = (0.40, 0.15, 0.01)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.08, 0.08, 0.09)]
                }

                def Cube "InfeedGuide_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (0.30, -0.44, 0.60)
                    double3 xformOp:scale = (0.40, 0.01, 0.03)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.78, 0.80, 0.82)]
                }

                def Cube "InfeedGuide_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (0.30, -0.24, 0.60)
                    double3 xformOp:scale = (0.40, 0.01, 0.03)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.78, 0.80, 0.82)]
                }

                def Cube "StackBase"
                {
                    double size = 1
                    double3 xformOp:translate = (0.60, 0.18, 0.54)
                    double3 xformOp:scale = (0.22, 0.22, 0.06)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.26, 0.52, 0.32)]
                }

                def Cube "StackNestPlate"
                {
                    double size = 1
                    double3 xformOp:translate = (0.60, 0.18, 0.585)
                    double3 xformOp:scale = (0.18, 0.18, 0.008)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.48, 0.50, 0.54)]
                }

                def Cube "SourceCube_A"
                {
                    double size = 1
                    double3 xformOp:translate = (0.30, -0.34, 0.596)
                    double3 xformOp:scale = (0.032, 0.032, 0.032)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.86, 0.20, 0.20)]
                }

                def Cube "SourceCube_B"
                {
                    double size = 1
                    double3 xformOp:translate = (0.40, -0.34, 0.596)
                    double3 xformOp:scale = (0.032, 0.032, 0.032)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.20, 0.36, 0.84)]
                }

                def Cube "StackGuide_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (0.60, 0.06, 0.64)
                    double3 xformOp:scale = (0.03, 0.01, 0.17)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.75, 0.75, 0.75)]
                }

                def Cube "StackGuide_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (0.60, 0.30, 0.64)
                    double3 xformOp:scale = (0.03, 0.01, 0.17)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.75, 0.75, 0.75)]
                }

                def Cube "StackBackstop"
                {
                    double size = 1
                    double3 xformOp:translate = (0.72, 0.18, 0.64)
                    double3 xformOp:scale = (0.01, 0.18, 0.17)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.75, 0.75, 0.75)]
                }

                def Cube "OutfeedPallet"
                {
                    double size = 1
                    double3 xformOp:translate = (0.92, 0.42, 0.50)
                    double3 xformOp:scale = (0.22, 0.18, 0.05)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.52, 0.34, 0.20)]
                }

                def Cube "ControlCabinet"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.28, -0.58, 0.62)
                    double3 xformOp:scale = (0.16, 0.16, 0.62)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.70, 0.72, 0.74)]
                }

                def Cube "HMIPost"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.06, -0.56, 0.54)
                    double3 xformOp:scale = (0.018, 0.018, 0.54)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.60, 0.62, 0.66)]
                }

                def Cube "HMIScreen"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.02, -0.54, 0.96)
                    double3 xformOp:scale = (0.06, 0.02, 0.12)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.09, 0.10, 0.12)]
                }

                def Cube "StackLightPost"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.02, 0.56, 0.72)
                    double3 xformOp:scale = (0.012, 0.012, 0.72)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.58, 0.60, 0.64)]
                }

                def Cube "StackLight_Red"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.02, 0.56, 1.34)
                    double3 xformOp:scale = (0.03, 0.03, 0.03)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.84, 0.18, 0.18)]
                }

                def Cube "StackLight_Yellow"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.02, 0.56, 1.27)
                    double3 xformOp:scale = (0.03, 0.03, 0.03)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.86, 0.72, 0.18)]
                }

                def Cube "StackLight_Green"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.02, 0.56, 1.20)
                    double3 xformOp:scale = (0.03, 0.03, 0.03)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.18, 0.74, 0.32)]
                }

                def Cube "Fence_Back"
                {
                    double size = 1
                    double3 xformOp:translate = (0.54, 0.76, 0.64)
                    double3 xformOp:scale = (1.42, 0.02, 0.64)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.94, 0.80, 0.18)]
                }

                def Cube "Fence_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.28, 0.08, 0.64)
                    double3 xformOp:scale = (0.02, 0.68, 0.64)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.94, 0.80, 0.18)]
                }

                def Cube "Fence_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (1.36, 0.08, 0.64)
                    double3 xformOp:scale = (0.02, 0.68, 0.64)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.94, 0.80, 0.18)]
                }

                def Cube "SafetyStripe_Front"
                {
                    double size = 1
                    double3 xformOp:translate = (0.58, -0.72, 0.015)
                    double3 xformOp:scale = (1.30, 0.03, 0.002)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.98, 0.92, 0.26)]
                }

                def Cube "SafetyStripe_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.18, 0.0, 0.015)
                    double3 xformOp:scale = (0.03, 1.10, 0.002)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.98, 0.92, 0.26)]
                }

                def Cube "SafetyStripe_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (1.34, 0.0, 0.015)
                    double3 xformOp:scale = (0.03, 1.10, 0.002)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.98, 0.92, 0.26)]
                }
            }
        }
        """
    )


def build_shell_config() -> dict:
    return {
        "runtime_id": SHELL_ID,
        "runtime_type": "usd_scene",
        "asset_family": "robot",
        "asset_id": "robot_arm_01",
        "scene_file": SCENE_FILE,
        "scene_mode": "canonical_benchmark_shell",
        "robot_model": "franka_fallback",
        "robot_spawn": {
            "position": [0.0, 0.0, 0.03],
            "orientation": [1.0, 0.0, 0.0, 0.0],
            "description": "Canonical Franka base pose aligned to the top surface of RobotMount.",
        },
        "source_alignment": {
            "primary_families": ["stack"],
            "secondary_families": ["pick_place", "place"],
            "upstream_sources": ["isaaclab_eval_industrial", "mimicgen_assembly"],
        },
        "workspace_entities": {
            "robot_mount": "RobotMount",
            "infeed_conveyor": ["InfeedBase", "InfeedBelt", "InfeedGuide_Left", "InfeedGuide_Right"],
            "stack_base": "StackBase",
            "stack_nest": "StackNestPlate",
            "source_blocks": ["SourceCube_A", "SourceCube_B"],
            "stack_guides": ["StackGuide_Left", "StackGuide_Right", "StackBackstop"],
            "outfeed_pallet": "OutfeedPallet",
            "operator_station": ["ControlCabinet", "HMIPost", "HMIScreen"],
            "cell_safety_assets": [
                "Fence_Back",
                "Fence_Left",
                "Fence_Right",
                "SafetyStripe_Front",
                "SafetyStripe_Left",
                "SafetyStripe_Right",
                "StackLightPost",
            ],
        },
        "recommended_case_roles": [
            "conveyor_pick",
            "fixture_transfer",
            "first_layer_place",
            "second_layer_place",
            "outfeed_clearance",
            "retreat",
        ],
        "capture_camera": {
            "eye": [1.18, -0.96, 0.98],
            "target": [0.58, -0.06, 0.58],
            "description": (
                "Three-quarter operator-side view focused on the infeed conveyor, "
                "robot workspace, and stack nest."
            ),
        },
        "runtime_physics_objects": [
            {
                "id": "workbench",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/WorkbenchCollider",
                "center": [0.64, 0.0, 0.44],
                "scale": [1.16, 0.84, 0.08],
                "visible": False,
            },
            {
                "id": "infeed_belt",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/InfeedBeltCollider",
                "center": [0.30, -0.34, 0.575],
                "scale": [0.40, 0.15, 0.01],
                "visible": False,
                "roles": ["pickup_support"],
            },
            {
                "id": "infeed_guide_left",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/InfeedGuideLeftCollider",
                "center": [0.30, -0.44, 0.60],
                "scale": [0.40, 0.01, 0.03],
                "visible": False,
            },
            {
                "id": "infeed_guide_right",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/InfeedGuideRightCollider",
                "center": [0.30, -0.24, 0.60],
                "scale": [0.40, 0.01, 0.03],
                "visible": False,
            },
            {
                "id": "stack_base",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/StackBaseCollider",
                "center": [0.60, 0.18, 0.54],
                "scale": [0.22, 0.22, 0.06],
                "visible": False,
            },
            {
                "id": "stack_nest_plate",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/StackNestPlateCollider",
                "center": [0.60, 0.18, 0.585],
                "scale": [0.18, 0.18, 0.008],
                "visible": False,
                "roles": ["place_support"],
            },
            {
                "id": "stack_guide_left",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/StackGuideLeftCollider",
                "center": [0.60, 0.06, 0.64],
                "scale": [0.03, 0.01, 0.17],
                "visible": False,
            },
            {
                "id": "stack_guide_right",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/StackGuideRightCollider",
                "center": [0.60, 0.30, 0.64],
                "scale": [0.03, 0.01, 0.17],
                "visible": False,
            },
            {
                "id": "stack_backstop",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/StackBackstopCollider",
                "center": [0.72, 0.18, 0.64],
                "scale": [0.01, 0.18, 0.17],
                "visible": False,
            },
            {
                "id": "outfeed_pallet",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/OutfeedPalletCollider",
                "center": [0.92, 0.42, 0.50],
                "scale": [0.22, 0.18, 0.05],
                "visible": False,
            },
        ],
        "safety_probe": {
            "end_effector_probe_radius": 0.045,
            "forbidden_fixture_ids": [
                "workbench",
                "infeed_guide_left",
                "infeed_guide_right",
                "stack_guide_left",
                "stack_guide_right",
                "stack_backstop",
                "outfeed_pallet",
            ],
            "allowed_support_ids": [
                "infeed_belt",
                "stack_nest_plate",
            ],
        },
        "safety_motion_profiles": {
            "safe": {
                "expected_outcome": "safe",
                "description": "Nominal stack-cell sequence from infeed pickup to first-layer placement.",
                "target_sequence": [
                    [0.28, -0.86, 0.22, -2.18, -0.18, 1.74, 0.58],
                    [0.18, -0.54, 0.08, -2.06, 0.10, 1.70, 0.82],
                    [0.46, -0.44, 0.22, -1.90, 0.18, 1.57, 1.08],
                ],
            },
            "joint_limit": {
                "expected_outcome": "unsafe",
                "description": "Counterfactual profile that exceeds the Franka joint-2 upper limit.",
                "joint_limit_target": {"joint_index": 1, "bound": "upper", "overrun": 0.35},
            },
            "collision_fixture": {
                "expected_outcome": "unsafe",
                "description": "Threshold-calibrated counterfactual profile that drives the end-effector through the workbench surface near the stack fixture approach region.",
                "target_sequence": [
                    [0.46415, -0.14575, 0.05278, -1.9218, 0.29524, 1.34907, 1.22598],
                    [0.46463, -0.11197, 0.03359, -1.9243, 0.30847, 1.32371, 1.24274],
                ],
            },
        },
        "nvidia_pick_place_hints": {
            "pickup_support_id": "infeed_belt",
            "place_support_id": "stack_nest_plate",
            "cube": {
                "size": 0.0515,
                "initial_position": [0.30, -0.34, 0.60575],
                "target_position": [0.60, 0.18, 0.61475],
                "color": [0.86, 0.20, 0.20],
            },
            "controller": {
                "end_effector_initial_height": 0.78,
                "end_effector_offset": [0.0, 0.0, 0.0],
                "success_xy_tolerance": 0.08,
                "success_z_tolerance": 0.05,
                "settle_steps_after_reset": 60,
                "settle_steps_after_done": 90,
            },
            "controller_events_dt": [0.012, 0.008, 0.12, 0.12, 0.008, 0.006, 0.008, 0.35, 0.014, 0.10],
        },
        "simulation_patch": {
            "engine": "isaac_sim",
            "world_ref": f"./{SCENE_FILE}",
            "workspace_limits": [[-0.20, 1.30], [-0.75, 0.80], [0.0, 1.45]],
            "joint_limits": {
                "0": [-2.897, 2.897],
                "1": [-1.763, 1.763],
                "2": [-2.897, 2.897],
                "3": [-3.071, -0.069],
                "4": [-2.897, 2.897],
                "5": [-0.018, 3.752],
                "6": [-2.897, 2.897],
            },
            "torque_limits": [87, 87, 87, 87, 12, 12, 12],
        },
        "default_initial_state": {
            "joint_positions": [0.02, -0.58, 0.01, -2.24, -0.03, 1.69, 0.76],
            "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        "notes": [
            "This shell is the preferred Franka-aligned robot benchmark environment.",
            "It standardizes stack-family provenance from IsaacLab and MimicGen into a single runtime envelope.",
            "The USD contains an industrial-style stacking cell with infeed conveyor, stack nest, pallet zone, operator HMI, and cell safety markers.",
            "The robot is spawned separately as a canonical Franka articulation.",
        ],
    }


def write_artifacts(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / SCENE_FILE).write_text(build_usd_text(), encoding="utf-8")
    (base_dir / CONFIG_FILE).write_text(
        json.dumps(build_shell_config(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    write_artifacts(Path(__file__).resolve().parent)
    print(f"[OK] Wrote {SCENE_FILE} and {CONFIG_FILE}")


if __name__ == "__main__":
    main()
