"""
PCAG Scenario B: Robot Arm Simulation Validator Test
=====================================================
Tests the Simulation Validator (123) pattern with a Franka Panda robot.

Tests:
1. SAFE: Move joints within safe limits
2. UNSAFE: Command joints beyond limits

Run:
  conda activate pcag-isaac
  python tests/isaac_sim/test_scenario_b_robot_arm.py
"""

import sys
import time
import numpy as np

# This mimics the actual PCAG IsaacSimBackend plugin interface
class IsaacSimBackend:
    """Simplified version of ISimulationBackend for testing."""
    
    def __init__(self, world, robot):
        self.world = world
        self.robot = robot
    
    def validate_trajectory(self, current_state, action_sequence, constraints):
        """
        PCAG Simulation Validator core function.
        
        Args:
            current_state: dict with joint_positions, etc.
            action_sequence: list of UnitAction dicts
            constraints: dict with joint_limits, workspace_bounds, etc.
        
        Returns:
            dict with verdict (SAFE/UNSAFE), details, trajectory
        """
        # 1. Set initial state
        # Ensure we are working with numpy array for setting
        if "joint_positions" in current_state:
            self.robot.set_joint_positions(np.array(current_state["joint_positions"]))
        
        # 2. For each action, apply and check constraints
        trajectory = []
        for i, action in enumerate(action_sequence):
            # Get target positions
            target = np.array(action["params"]["target_positions"])
            
            # [Pre-check] Validate commanded target against limits BEFORE simulation
            # This catches "Command Unsafe" scenarios where we ask for 5.0 rad
            violation = self.check_constraints(target, constraints)
            if violation:
                 return {
                    "verdict": "UNSAFE",
                    "engine": "isaac_sim",
                    "first_violation_step": i,
                    "violated_constraint": violation["constraint"] + "_command",
                    "details": f"Commanded target {violation['value']} exceeds limits {violation['limits']}",
                    "trajectory": trajectory
                }

            # Apply action (set target joint positions)
            self.robot.set_joint_positions(target)
            
            # Step simulation
            for _ in range(action.get("duration_steps", 10)):
                self.world.step(render=True)  # render=True for GUI observation
            
            # Read resulting state
            current_pos = self.robot.get_joint_positions()
            
            # DEBUG: Print joint positions
            # print(f"    Step {i} Result Joints: {current_pos[:7]}")

            # [Post-check 1] Check physical state constraints
            violation = self.check_constraints(current_pos, constraints)
            if violation:
                return {
                    "verdict": "UNSAFE",
                    "engine": "isaac_sim",
                    "first_violation_step": i,
                    "violated_constraint": violation["constraint"] + "_state",
                    "trajectory": trajectory
                }
                
            # [Post-check 2] Divergence check (Command vs Actual)
            # If physics clamped the value, target != current_pos
            # We check the first N joints (excluding extra padding if any)
            n = min(len(target), len(current_pos))
            divergence = np.abs(target[:n] - current_pos[:n])
            max_divergence = np.max(divergence)
            
            # Threshold: 0.1 radians (~5.7 degrees) allows for minor physics settle, 
            # but catches clamping (e.g. 5.0 vs 2.9 is > 2.0 difference)
            if max_divergence > 0.1:
                 return {
                    "verdict": "UNSAFE",
                    "engine": "isaac_sim",
                    "first_violation_step": i,
                    "violated_constraint": "control_divergence",
                    "details": f"Result differs from command by {max_divergence:.4f} rad. Physical limits likely hit.",
                    "trajectory": trajectory
                }
            
            trajectory.append({
                "step": i,
                "joint_positions": current_pos.tolist(),
                "violation": None
            })
        
        return {
            "verdict": "SAFE",
            "engine": "isaac_sim",
            "trajectory": trajectory
        }
    
    def check_constraints(self, joint_positions, constraints):
        """Check if current state violates any constraints."""
        joint_limits = constraints.get("joint_limits", {})
        for joint_idx, limits in joint_limits.items():
            idx = int(joint_idx)
            if idx < len(joint_positions):
                val = joint_positions[idx]
                if val < limits[0] or val > limits[1]:
                    return {
                        "constraint": f"joint_{idx}_limit",
                        "value": float(val),
                        "limits": limits
                    }
        return None

def main():
    print("=" * 70)
    print("PCAG Scenario B: Robot Arm Simulation Validator")
    print("=" * 70)
    
    # Try importing SimulationApp from different locations
    try:
        from isaacsim import SimulationApp
    except ImportError:
        try:
            from omni.isaac.kit import SimulationApp
        except ImportError:
            print("ERROR: Could not import SimulationApp. Is Isaac Sim environment activated?")
            return

    # Start Isaac Sim (GUI mode so user can observe)
    simulation_app = SimulationApp({"headless": False, "width": 1280, "height": 720})
    
    # Import World after SimulationApp is started
    try:
        from isaacsim.core.api import World
    except ImportError:
        try:
            from omni.isaac.core import World
        except ImportError:
            print("ERROR: Could not import World.")
            simulation_app.close()
            return
            
    world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
    world.scene.add_default_ground_plane()
    
    # Load Franka Panda robot
    robot = None
    # Method: Use the built-in Franka robot class
    try:
        print("Attempting to load Franka from omni.isaac.franka...")
        from omni.isaac.franka import Franka
        robot = world.scene.add(Franka(prim_path="/World/Franka", name="franka"))
    except ImportError:
        # Alternative for Isaac Sim 4.5.0 / other versions
        try:
            print("Attempting to load Franka from isaacsim.robot.manipulators.examples.franka...")
            from isaacsim.robot.manipulators.examples.franka import Franka
            robot = world.scene.add(Franka(prim_path="/World/Franka", name="franka"))
        except ImportError:
            try: 
                 # Try omni.isaac.core.robots
                print("Attempting to load Franka from USD...")
                from omni.isaac.core.utils.stage import add_reference_to_stage
                from omni.isaac.core.robots import Robot
                
                # Use Nucleus asset path
                usd_path = "/Isaac/Robots/Franka/franka_alt_fingers.usd"
                add_reference_to_stage(usd_path=usd_path, prim_path="/World/Franka")
                robot = world.scene.add(Robot(prim_path="/World/Franka", name="franka"))
            except Exception as e:
                print(f"Failed to load Franka from USD: {e}")

    if robot is None:
        print("ERROR: Could not load Franka robot. Exiting.")
        simulation_app.close()
        return

    world.reset()
    
    # Get initial joint positions
    initial_joints = robot.get_joint_positions()
    num_joints = len(initial_joints)
    print(f"  Robot loaded: {num_joints} joints")
    print(f"  Initial joint positions: {initial_joints}")
    
    # Let robot settle
    for _ in range(30):
        world.step(render=True)
    
    # Create the IsaacSimBackend
    backend = IsaacSimBackend(world, robot)
    
    # ============================================================
    # Define constraints (from AssetPolicyProfile.ruleset)
    # ============================================================
    # Franka Panda joint limits (approximate, in radians)
    # TIGHTER limits than hardware to catch violations even if simulation clamps
    constraints = {
        "joint_limits": {
            "0": [-2.8, 2.8],         # Hardware ~2.8973
            "1": [-1.7, 1.7],         # Hardware ~1.7628
            "2": [-2.8, 2.8],         # Hardware ~2.8973
            "3": [-3.0, -0.1],        # Hardware ~ -3.07 to -0.07
            "4": [-2.8, 2.8],         # Hardware ~2.8973
            "5": [0.0, 3.7],          # Hardware ~ -0.0175 to 3.75
            "6": [-2.8, 2.8],         # Hardware ~2.8973
        }
    }
    
    results = []
    
    # ============================================================
    # TEST 1: SAFE trajectory -- move within joint limits
    # ============================================================
    print("\n[TEST 1] SAFE Trajectory - Joints within limits")
    print("-" * 50)
    
    current_state = {
        "joint_positions": [0.0] * num_joints
    }
    
    # Define safe action sequence (small movements within limits)
    # Ensure arrays are long enough for num_joints (Franka has 9 usually: 7 arm + 2 gripper)
    # We pad with 0.0s for gripper joints
    
    safe_actions = [
        {
            "action_type": "move_joint",
            "params": {"target_positions": [0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0] + [0.0] * (num_joints - 7)},
            "duration_steps": 30
        },
        {
            "action_type": "move_joint",
            "params": {"target_positions": [0.5, -0.3, 0.3, -1.0, 0.2, 1.5, -0.3] + [0.0] * (num_joints - 7)},
            "duration_steps": 30
        },
        {
            "action_type": "move_joint",
            "params": {"target_positions": [0.0, 0.0, 0.0, -1.5, 0.0, 1.0, 0.0] + [0.0] * (num_joints - 7)},
            "duration_steps": 30
        }
    ]
    
    result = backend.validate_trajectory(current_state, safe_actions, constraints)
    print(f"  Verdict: {result['verdict']}")
    print(f"  Trajectory steps: {len(result['trajectory'])}")
    
    safe_passed = result["verdict"] == "SAFE"
    print(f"  Result: {'[PASS]' if safe_passed else '[FAIL]'}")
    results.append(("SAFE Trajectory", safe_passed))
    
    # ============================================================
    # TEST 2: UNSAFE trajectory -- exceed joint limits
    # ============================================================
    print("\n[TEST 2] UNSAFE Trajectory - Exceed joint limits")
    print("-" * 50)
    
    # Reset robot
    world.reset()
    for _ in range(10):
        world.step(render=True)
    
    unsafe_actions = [
        {
            "action_type": "move_joint",
            "params": {"target_positions": [0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0] + [0.0] * (num_joints - 7)},
            "duration_steps": 30
        },
        {
            "action_type": "move_joint",
            # Joint 1 set to 5.0 radians -- exceeds limit of [-2.8973, 2.8973]
            "params": {"target_positions": [5.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0] + [0.0] * (num_joints - 7)},
            "duration_steps": 30
        }
    ]
    
    result = backend.validate_trajectory(current_state, unsafe_actions, constraints)
    print(f"  Verdict: {result['verdict']}")
    if result["verdict"] == "UNSAFE":
        print(f"  First violation step: {result.get('first_violation_step')}")
        print(f"  Violated constraint: {result.get('violated_constraint')}")
    
    unsafe_passed = result["verdict"] == "UNSAFE"
    print(f"  Result: {'[PASS]' if unsafe_passed else '[FAIL]'}")
    results.append(("UNSAFE Trajectory", unsafe_passed))
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print("PCAG Scenario B Summary")
    print("=" * 70)
    
    summary_lines = []
    summary_lines.append("PCAG Scenario B Validation Results")
    summary_lines.append("==================================")
    
    for name, r in results:
        status = "[PASS]" if r else "[FAIL]"
        print(f"  {status} {name}")
        summary_lines.append(f"{status} {name}")
    
    passed = sum(1 for _, r in results if r)
    print(f"\nTotal: {passed}/{len(results)} passed")
    summary_lines.append(f"\nTotal: {passed}/{len(results)} passed")
    
    if passed == len(results):
        print("\nScenario B Robot Arm Simulation Validator pattern verified!")
        print("Isaac Sim can serve as ISimulationBackend for robot arm scenarios.")
        summary_lines.append("\nScenario B Robot Arm Simulation Validator pattern verified!")
    
    # Write results to file for verification
    try:
        # Just use current directory filename to avoid path issues
        with open("scenario_b_results.txt", "w") as f:
            f.write("\n".join(summary_lines))
        print("Results written to scenario_b_results.txt")
    except Exception as e:
        print(f"Failed to write results to file: {e}")
    
    # Keep for observation
    print("\nClosing in 5 seconds...")
    end = time.time()
    while time.time() - end < 5:
        world.step(render=True)
    
    # Cleanup: stop physics, clear scene (releases articulation handles),
    # then close the app. Without this, Franka's complex physics resources
    # can linger and cause hangs on subsequent runs.
    try:
        world.stop()
    except Exception:
        pass
    try:
        world.clear()
    except Exception:
        pass
    try:
        simulation_app.close()
        print("Done.")
    except Exception:
        print("Done (close raised exception, ignored).")

if __name__ == "__main__":
    print("Starting PCAG Scenario B Test Script...")
    main()
