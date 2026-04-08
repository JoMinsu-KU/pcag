"""
Build the canonical `robot_narrow_clearance_cell` benchmark shell.

This shell extends the public robot benchmark with a tighter fixture corridor
than `robot_pick_place_cell`, so the digital-twin collision validator can be
tested on narrow-clearance approach and insertion-like motions without changing
the current single-asset command contract.
"""

from __future__ import annotations

import json
from pathlib import Path


SHELL_ID = "robot_narrow_clearance_cell"
SCENE_FILE = f"{SHELL_ID}.usd"
CONFIG_FILE = "shell_config.json"


CUBES = [
    {"name": "CellFloor", "translate": [0.66, 0.0, 0.01], "scale": [1.72, 1.24, 0.02], "color": [0.22, 0.24, 0.27]},
    {"name": "RobotMount", "translate": [0.0, 0.0, 0.015], "scale": [0.22, 0.22, 0.03], "color": [0.36, 0.38, 0.42]},
    {"name": "Workbench", "translate": [0.72, 0.0, 0.44], "scale": [1.30, 0.92, 0.08], "color": [0.34, 0.35, 0.36]},
    {"name": "SourceTrayBase", "translate": [0.34, -0.30, 0.53], "scale": [0.28, 0.22, 0.04], "color": [0.16, 0.18, 0.20]},
    {"name": "SourceTrayPlate", "translate": [0.34, -0.30, 0.575], "scale": [0.24, 0.18, 0.01], "color": [0.18, 0.36, 0.68]},
    {"name": "SourceGuide_Left", "translate": [0.34, -0.41, 0.61], "scale": [0.24, 0.01, 0.04], "color": [0.78, 0.80, 0.82]},
    {"name": "SourceGuide_Right", "translate": [0.34, -0.19, 0.61], "scale": [0.24, 0.01, 0.04], "color": [0.78, 0.80, 0.82]},
    {"name": "TransferPlate", "translate": [0.62, -0.02, 0.58], "scale": [0.22, 0.14, 0.012], "color": [0.48, 0.50, 0.54]},
    {"name": "NarrowFixtureBase", "translate": [0.93, 0.24, 0.545], "scale": [0.24, 0.20, 0.05], "color": [0.26, 0.52, 0.32]},
    {"name": "NarrowFixturePlate", "translate": [0.93, 0.24, 0.586], "scale": [0.16, 0.10, 0.008], "color": [0.46, 0.48, 0.52]},
    {"name": "NarrowGuide_Left", "translate": [0.93, 0.182, 0.652], "scale": [0.04, 0.012, 0.16], "color": [0.75, 0.75, 0.75]},
    {"name": "NarrowGuide_Right", "translate": [0.93, 0.298, 0.652], "scale": [0.04, 0.012, 0.16], "color": [0.75, 0.75, 0.75]},
    {"name": "NarrowBackstop", "translate": [1.024, 0.24, 0.652], "scale": [0.01, 0.10, 0.16], "color": [0.75, 0.75, 0.75]},
    {"name": "NarrowSlotCeiling", "translate": [0.93, 0.24, 0.742], "scale": [0.16, 0.10, 0.008], "color": [0.66, 0.68, 0.70]},
    {"name": "NarrowSideGuard_Left", "translate": [0.87, 0.144, 0.622], "scale": [0.12, 0.01, 0.11], "color": [0.70, 0.72, 0.74]},
    {"name": "NarrowSideGuard_Right", "translate": [0.87, 0.336, 0.622], "scale": [0.12, 0.01, 0.11], "color": [0.70, 0.72, 0.74]},
    {"name": "PartProxy_Slim", "translate": [0.34, -0.30, 0.598], "scale": [0.028, 0.028, 0.040], "color": [0.84, 0.62, 0.16]},
    {"name": "OutfeedBin", "translate": [1.14, -0.30, 0.50], "scale": [0.22, 0.20, 0.05], "color": [0.52, 0.34, 0.20]},
    {"name": "ControlCabinet", "translate": [-0.28, -0.58, 0.62], "scale": [0.16, 0.16, 0.62], "color": [0.70, 0.72, 0.74]},
    {"name": "HMIPost", "translate": [-0.06, -0.56, 0.54], "scale": [0.018, 0.018, 0.54], "color": [0.60, 0.62, 0.66]},
    {"name": "HMIScreen", "translate": [-0.02, -0.54, 0.96], "scale": [0.06, 0.02, 0.12], "color": [0.09, 0.10, 0.12]},
    {"name": "StackLightPost", "translate": [-0.02, 0.56, 0.72], "scale": [0.012, 0.012, 0.72], "color": [0.58, 0.60, 0.64]},
    {"name": "StackLight_Red", "translate": [-0.02, 0.56, 1.34], "scale": [0.03, 0.03, 0.03], "color": [0.84, 0.18, 0.18]},
    {"name": "StackLight_Yellow", "translate": [-0.02, 0.56, 1.27], "scale": [0.03, 0.03, 0.03], "color": [0.86, 0.72, 0.18]},
    {"name": "StackLight_Green", "translate": [-0.02, 0.56, 1.20], "scale": [0.03, 0.03, 0.03], "color": [0.18, 0.74, 0.32]},
    {"name": "Fence_Back", "translate": [0.68, 0.78, 0.64], "scale": [1.52, 0.02, 0.64], "color": [0.94, 0.80, 0.18]},
    {"name": "Fence_Left", "translate": [-0.28, 0.08, 0.64], "scale": [0.02, 0.70, 0.64], "color": [0.94, 0.80, 0.18]},
    {"name": "Fence_Right", "translate": [1.48, 0.08, 0.64], "scale": [0.02, 0.70, 0.64], "color": [0.94, 0.80, 0.18]},
    {"name": "SafetyStripe_Front", "translate": [0.58, -0.60, 0.011], "scale": [1.10, 0.02, 0.002], "color": [0.94, 0.80, 0.18]},
    {"name": "SafetyStripe_Left", "translate": [-0.12, 0.0, 0.011], "scale": [0.02, 1.20, 0.002], "color": [0.94, 0.80, 0.18]},
    {"name": "SafetyStripe_Right", "translate": [1.28, 0.0, 0.011], "scale": [0.02, 1.20, 0.002], "color": [0.94, 0.80, 0.18]}
]


def _render_vec(values: list[float]) -> str:
    return "(" + ", ".join(f"{value}" for value in values) + ")"


def _render_cube(cube: dict[str, object]) -> str:
    return (
        f'                def Cube "{cube["name"]}"\n'
        "                {\n"
        "                    double size = 1\n"
        f'                    double3 xformOp:translate = {_render_vec(cube["translate"])}\n'
        f'                    double3 xformOp:scale = {_render_vec(cube["scale"])}\n'
        '                    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]\n'
        f'                    color3f[] primvars:displayColor = [{_render_vec(cube["color"])}]\n'
        "                }\n"
    )


def build_usd_text() -> str:
    body = "".join(_render_cube(cube) for cube in CUBES)
    return (
        "#usda 1.0\n"
        "(\n"
        '    defaultPrim = "World"\n'
        "    metersPerUnit = 1\n"
        '    upAxis = "Z"\n'
        ")\n\n"
        'def Xform "World"\n'
        "{\n"
        '    def Xform "Environment"\n'
        "    {\n"
        f"{body}"
        "    }\n"
        "}\n"
    )


def build_shell_config() -> dict:
    return {
        "runtime_id": SHELL_ID,
        "runtime_type": "usd_scene",
        "asset_family": "robot",
        "asset_id": "robot_arm_01",
        "scene_file": SCENE_FILE,
        "scene_mode": "benchmark_expansion_shell",
        "robot_model": "franka_fallback",
        "robot_spawn": {
            "position": [0.0, 0.0, 0.03],
            "orientation": [1.0, 0.0, 0.0, 0.0],
            "description": "Canonical Franka base pose aligned to the top surface of RobotMount.",
        },
        "source_alignment": {
            "primary_families": ["pick_place", "place", "reach"],
            "secondary_families": ["lift"],
            "upstream_sources": ["isaaclab_eval_industrial", "mimicgen_assembly"],
        },
        "workspace_entities": {
            "robot_mount": "RobotMount",
            "source_zone": ["SourceTrayBase", "SourceTrayPlate", "SourceGuide_Left", "SourceGuide_Right"],
            "transfer_zone": "TransferPlate",
            "target_zone": ["NarrowFixtureBase", "NarrowFixturePlate"],
            "target_guides": [
                "NarrowGuide_Left",
                "NarrowGuide_Right",
                "NarrowBackstop",
                "NarrowSlotCeiling",
                "NarrowSideGuard_Left",
                "NarrowSideGuard_Right",
            ],
            "part_proxies": ["PartProxy_Slim"],
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
        "recommended_case_roles": ["narrow_approach", "pre_insert", "insert", "retreat"],
        "capture_camera": {
            "eye": [1.20, -0.96, 1.02],
            "target": [0.90, 0.22, 0.64],
            "description": "Three-quarter view centered on the narrow-clearance target fixture and insertion corridor.",
        },
        "runtime_physics_objects": [
            {
                "id": "workbench",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/WorkbenchCollider",
                "center": [0.72, 0.0, 0.44],
                "scale": [1.30, 0.92, 0.08],
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
                "center": [0.62, -0.02, 0.58],
                "scale": [0.22, 0.14, 0.012],
                "visible": False,
            },
            {
                "id": "narrow_fixture_plate",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowFixturePlateCollider",
                "center": [0.93, 0.24, 0.586],
                "scale": [0.16, 0.10, 0.008],
                "visible": False,
                "roles": ["insert_support"],
            },
            {
                "id": "narrow_guide_left",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowGuideLeftCollider",
                "center": [0.93, 0.182, 0.652],
                "scale": [0.04, 0.012, 0.16],
                "visible": False,
            },
            {
                "id": "narrow_guide_right",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowGuideRightCollider",
                "center": [0.93, 0.298, 0.652],
                "scale": [0.04, 0.012, 0.16],
                "visible": False,
            },
            {
                "id": "narrow_backstop",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowBackstopCollider",
                "center": [1.024, 0.24, 0.652],
                "scale": [0.01, 0.10, 0.16],
                "visible": False,
            },
            {
                "id": "narrow_slot_ceiling",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowSlotCeilingCollider",
                "center": [0.93, 0.24, 0.742],
                "scale": [0.16, 0.10, 0.008],
                "visible": False,
            },
            {
                "id": "narrow_side_guard_left",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowSideGuardLeftCollider",
                "center": [0.87, 0.144, 0.622],
                "scale": [0.12, 0.01, 0.11],
                "visible": False,
            },
            {
                "id": "narrow_side_guard_right",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/NarrowSideGuardRightCollider",
                "center": [0.87, 0.336, 0.622],
                "scale": [0.12, 0.01, 0.11],
                "visible": False,
            },
            {
                "id": "outfeed_bin",
                "kind": "fixed_cuboid",
                "prim_path": "/World/BenchmarkRuntime/OutfeedBinCollider",
                "center": [1.14, -0.30, 0.50],
                "scale": [0.22, 0.20, 0.05],
                "visible": False,
            },
        ],
        "safety_probe": {
            "end_effector_probe_radius": 0.042,
            "forbidden_fixture_ids": [
                "workbench",
                "source_guide_left",
                "source_guide_right",
                "narrow_guide_left",
                "narrow_guide_right",
                "narrow_backstop",
                "narrow_slot_ceiling",
                "narrow_side_guard_left",
                "narrow_side_guard_right",
                "outfeed_bin",
            ],
            "allowed_support_ids": ["source_tray_plate", "narrow_fixture_plate"],
        },
        "safety_motion_profiles": {
            "safe": {
                "expected_outcome": "safe",
                "description": "Nominal narrow-clearance approach and insertion-adjacent sequence.",
                "target_sequence": [
                    [0.12, -0.88, 0.18, -2.20, 0.02, 1.72, 0.66],
                    [0.26, -0.60, 0.14, -2.04, 0.14, 1.54, 0.92],
                    [0.42, -0.46, 0.18, -1.96, 0.20, 1.40, 1.04],
                    [0.50, -0.34, 0.26, -1.88, 0.28, 1.28, 1.10],
                    [0.18, -0.72, 0.20, -1.98, 0.04, 1.80, 0.86]
                ]
            },
            "joint_limit": {
                "expected_outcome": "unsafe",
                "description": "Counterfactual profile that exceeds the Franka joint-2 upper limit.",
                "joint_limit_target": {"joint_index": 1, "bound": "upper", "overrun": 0.35}
            },
            "collision_fixture": {
                "expected_outcome": "unsafe",
                "description": "Provisional collision profile that narrows the insertion corridor until a side-guide penetration is expected.",
                "target_sequence": [
                    [0.46, -0.30, 0.29, -1.90, 0.34, 1.24, 1.12],
                    [0.52, -0.24, 0.31, -1.87, 0.40, 1.18, 1.16]
                ]
            }
        },
        "simulation_patch": {
            "engine": "isaac_sim",
            "world_ref": f"./{SCENE_FILE}",
            "workspace_limits": [[-0.20, 1.34], [-0.78, 0.82], [0.0, 1.48]],
            "joint_limits": {
                "0": [-2.897, 2.897],
                "1": [-1.763, 1.763],
                "2": [-2.897, 2.897],
                "3": [-3.071, -0.069],
                "4": [-2.897, 2.897],
                "5": [-0.018, 3.752],
                "6": [-2.897, 2.897]
            },
            "torque_limits": [87, 87, 87, 87, 12, 12, 12]
        },
        "default_initial_state": {
            "joint_positions": [0.0, -0.60, 0.0, -2.20, 0.0, 1.60, 0.78],
            "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        },
        "notes": [
            "This shell is the first single-asset robot-expansion shell beyond the validated v1 release.",
            "It increases fixture density around the target zone so narrow-clearance approach motions become meaningful DT cases.",
            "The shell preserves the same Franka fallback runtime contract used by the public robot benchmark."
        ]
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
