"""
Build the canonical `robot_pick_place_cell` benchmark shell.

This shell is the manufacturing-style pick-place counterpart to
`robot_stack_cell`. It is intended to provide the same benchmark-facing
features: a canonical Franka spawn pose, collider-backed runtime objects,
policy-driven safety-probe metadata, and deterministic camera hints.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


SHELL_ID = "robot_pick_place_cell"
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
                    double3 xformOp:translate = (0.66, 0.0, 0.01)
                    double3 xformOp:scale = (1.70, 1.24, 0.02)
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
                    double3 xformOp:translate = (0.70, 0.0, 0.44)
                    double3 xformOp:scale = (1.24, 0.90, 0.08)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.34, 0.35, 0.36)]
                }

                def Cube "SourceTrayBase"
                {
                    double size = 1
                    double3 xformOp:translate = (0.34, -0.30, 0.53)
                    double3 xformOp:scale = (0.28, 0.22, 0.04)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.16, 0.18, 0.20)]
                }

                def Cube "SourceTrayPlate"
                {
                    double size = 1
                    double3 xformOp:translate = (0.34, -0.30, 0.575)
                    double3 xformOp:scale = (0.24, 0.18, 0.01)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.18, 0.36, 0.68)]
                }

                def Cube "SourceGuide_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (0.34, -0.41, 0.61)
                    double3 xformOp:scale = (0.24, 0.01, 0.04)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.78, 0.80, 0.82)]
                }

                def Cube "SourceGuide_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (0.34, -0.19, 0.61)
                    double3 xformOp:scale = (0.24, 0.01, 0.04)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.78, 0.80, 0.82)]
                }

                def Cube "TransferPlate"
                {
                    double size = 1
                    double3 xformOp:translate = (0.60, -0.02, 0.58)
                    double3 xformOp:scale = (0.24, 0.16, 0.012)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.48, 0.50, 0.54)]
                }

                def Cube "TargetFixtureBase"
                {
                    double size = 1
                    double3 xformOp:translate = (0.90, 0.24, 0.54)
                    double3 xformOp:scale = (0.28, 0.24, 0.06)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.26, 0.52, 0.32)]
                }

                def Cube "TargetFixturePlate"
                {
                    double size = 1
                    double3 xformOp:translate = (0.90, 0.24, 0.585)
                    double3 xformOp:scale = (0.22, 0.18, 0.008)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.48, 0.50, 0.54)]
                }

                def Cube "TargetGuide_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (0.90, 0.13, 0.64)
                    double3 xformOp:scale = (0.03, 0.01, 0.17)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.75, 0.75, 0.75)]
                }

                def Cube "TargetGuide_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (0.90, 0.35, 0.64)
                    double3 xformOp:scale = (0.03, 0.01, 0.17)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.75, 0.75, 0.75)]
                }

                def Cube "TargetBackstop"
                {
                    double size = 1
                    double3 xformOp:translate = (1.02, 0.24, 0.64)
                    double3 xformOp:scale = (0.01, 0.18, 0.17)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.75, 0.75, 0.75)]
                }

                def Cube "PartProxy_A"
                {
                    double size = 1
                    double3 xformOp:translate = (0.32, -0.30, 0.595)
                    double3 xformOp:scale = (0.032, 0.032, 0.032)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.84, 0.62, 0.16)]
                }

                def Cube "PartProxy_B"
                {
                    double size = 1
                    double3 xformOp:translate = (0.39, -0.30, 0.595)
                    double3 xformOp:scale = (0.032, 0.032, 0.032)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.76, 0.18, 0.18)]
                }

                def Cube "OutfeedBin"
                {
                    double size = 1
                    double3 xformOp:translate = (1.10, -0.30, 0.50)
                    double3 xformOp:scale = (0.22, 0.20, 0.05)
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
                    double3 xformOp:translate = (0.62, 0.78, 0.64)
                    double3 xformOp:scale = (1.46, 0.02, 0.64)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.94, 0.80, 0.18)]
                }

                def Cube "Fence_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.28, 0.08, 0.64)
                    double3 xformOp:scale = (0.02, 0.70, 0.64)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.94, 0.80, 0.18)]
                }

                def Cube "Fence_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (1.44, 0.08, 0.64)
                    double3 xformOp:scale = (0.02, 0.70, 0.64)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.94, 0.80, 0.18)]
                }

                def Cube "SafetyStripe_Front"
                {
                    double size = 1
                    double3 xformOp:translate = (0.66, -0.74, 0.015)
                    double3 xformOp:scale = (1.34, 0.03, 0.002)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.98, 0.92, 0.26)]
                }

                def Cube "SafetyStripe_Left"
                {
                    double size = 1
                    double3 xformOp:translate = (-0.18, 0.0, 0.015)
                    double3 xformOp:scale = (0.03, 1.12, 0.002)
                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
                    color3f[] primvars:displayColor = [(0.98, 0.92, 0.26)]
                }

                def Cube "SafetyStripe_Right"
                {
                    double size = 1
                    double3 xformOp:translate = (1.42, 0.0, 0.015)
                    double3 xformOp:scale = (0.03, 1.12, 0.002)
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
            "primary_families": ["reach", "lift", "pick_place", "place"],
            "secondary_families": ["pick_place"],
            "upstream_sources": ["isaaclab_eval_industrial", "mimicgen_assembly"],
        },
        "workspace_entities": {
            "robot_mount": "RobotMount",
            "source_zone": ["SourceTrayBase", "SourceTrayPlate", "SourceGuide_Left", "SourceGuide_Right"],
            "transfer_zone": "TransferPlate",
            "target_zone": ["TargetFixtureBase", "TargetFixturePlate"],
            "target_guides": ["TargetGuide_Left", "TargetGuide_Right", "TargetBackstop"],
            "part_proxies": ["PartProxy_A", "PartProxy_B"],
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
        "recommended_case_roles": ["approach", "pick", "transfer", "place", "retreat"],
        "capture_camera": {
            "eye": [1.24, -1.02, 1.00],
            "target": [0.74, 0.02, 0.58],
            "description": (
                "Three-quarter operator-side view focused on the source tray, "
                "transfer zone, and target fixture."
            ),
        },
        "runtime_physics_objects": [
            {
                "id": "workbench",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/WorkbenchCollider",
                "center": [0.70, 0.0, 0.44],
                "scale": [1.24, 0.90, 0.08],
                "visible": False,
            },
            {
                "id": "source_tray_plate",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/SourceTrayPlateCollider",
                "center": [0.34, -0.30, 0.575],
                "scale": [0.24, 0.18, 0.01],
                "visible": False,
                "roles": ["pickup_support"],
            },
            {
                "id": "source_guide_left",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/SourceGuideLeftCollider",
                "center": [0.34, -0.41, 0.61],
                "scale": [0.24, 0.01, 0.04],
                "visible": False,
            },
            {
                "id": "source_guide_right",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/SourceGuideRightCollider",
                "center": [0.34, -0.19, 0.61],
                "scale": [0.24, 0.01, 0.04],
                "visible": False,
            },
            {
                "id": "transfer_plate",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/TransferPlateCollider",
                "center": [0.60, -0.02, 0.58],
                "scale": [0.24, 0.16, 0.012],
                "visible": False,
            },
            {
                "id": "target_fixture_plate",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/TargetFixturePlateCollider",
                "center": [0.90, 0.24, 0.585],
                "scale": [0.22, 0.18, 0.008],
                "visible": False,
                "roles": ["place_support"],
            },
            {
                "id": "target_guide_left",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/TargetGuideLeftCollider",
                "center": [0.90, 0.13, 0.64],
                "scale": [0.03, 0.01, 0.17],
                "visible": False,
            },
            {
                "id": "target_guide_right",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/TargetGuideRightCollider",
                "center": [0.90, 0.35, 0.64],
                "scale": [0.03, 0.01, 0.17],
                "visible": False,
            },
            {
                "id": "target_backstop",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/TargetBackstopCollider",
                "center": [1.02, 0.24, 0.64],
                "scale": [0.01, 0.18, 0.17],
                "visible": False,
            },
            {
                "id": "outfeed_bin",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/OutfeedBinCollider",
                "center": [1.10, -0.30, 0.50],
                "scale": [0.22, 0.20, 0.05],
                "visible": False,
            },
        ],
        "safety_probe": {
            "end_effector_probe_radius": 0.045,
            "forbidden_fixture_ids": [
                "workbench",
                "source_guide_left",
                "source_guide_right",
                "target_guide_left",
                "target_guide_right",
                "target_backstop",
                "outfeed_bin",
            ],
            "allowed_support_ids": ["source_tray_plate", "target_fixture_plate"],
        },
        "safety_motion_profiles": {
            "safe": {
                "expected_outcome": "safe",
                "description": "Nominal pick-place sequence from source tray to target fixture.",
                "target_sequence": [
                    [0.12, -0.88, 0.18, -2.20, 0.02, 1.72, 0.66],
                    [0.02, -0.68, 0.05, -2.12, -0.02, 1.66, 0.80],
                    [0.30, -0.52, 0.12, -2.00, 0.10, 1.56, 0.96],
                    [0.54, -0.38, 0.18, -1.86, 0.18, 1.48, 1.10],
                    [0.10, -0.76, 0.20, -1.96, 0.00, 1.82, 0.88],
                ],
            },
            "joint_limit": {
                "expected_outcome": "unsafe",
                "description": "Counterfactual profile that exceeds the Franka joint-2 upper limit.",
                "joint_limit_target": {"joint_index": 1, "bound": "upper", "overrun": 0.35},
            },
            "collision_fixture": {
                "expected_outcome": "unsafe",
                "description": "Threshold-calibrated counterfactual profile that drives the end-effector through the workbench surface near the target-fixture approach region.",
                "target_sequence": [
                    [0.24137, -0.14142, 0.30755, -1.94696, 0.58407, 1.56317, 0.85549],
                    [0.24798, -0.11251, 0.31258, -1.94635, 0.61137, 1.55117, 0.85434],
                ],
            },
        },
        "nvidia_pick_place_hints": {
            "pickup_support_id": "source_tray_plate",
            "place_support_id": "target_fixture_plate",
            "cube": {
                "size": 0.0515,
                "initial_position": [0.34, -0.30, 0.60575],
                "target_position": [0.90, 0.24, 0.61475],
                "color": [0.86, 0.2, 0.2],
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
            "workspace_limits": [[-0.20, 1.30], [-0.78, 0.82], [0.0, 1.45]],
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
            "joint_positions": [0.00, -0.60, 0.00, -2.20, 0.00, 1.60, 0.78],
            "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        "notes": [
            "This shell is the pick-place counterpart to robot_stack_cell and is benchmark-safe by construction.",
            "It standardizes reach, lift, pick_place, and place-family provenance from IsaacLab and MimicGen into one runtime envelope.",
            "The USD contains an industrial-style pick-place cell with source tray, transfer deck, target fixture, HMI, and cell safety markers.",
            "The robot is spawned separately as a canonical Franka articulation.",
        ],
    }


def write_artifacts(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / SCENE_FILE).write_text(build_usd_text(), encoding="utf-8")
    (base_dir / CONFIG_FILE).write_text(
        json.dumps(build_shell_config(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    write_artifacts(Path(__file__).resolve().parent)
    print(f"[OK] Wrote {SCENE_FILE} and {CONFIG_FILE}")


if __name__ == "__main__":
    main()
