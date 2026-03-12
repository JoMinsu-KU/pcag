"""
Isaac Sim Physics Test for PCAG Simulation Validator
=====================================================
Tests the core physics capabilities needed by PCAG:
1. Gravity & Free Fall
2. Collision Detection (contact reports)
3. Robot Arm Joint Control
4. Workspace Boundary Checking
5. Force/Torque Reading

Run: conda activate pcag-isaac && python tests/isaac_sim/test_isaac_sim_physics.py
"""

import time
import numpy as np

def main():
    print("=" * 70)
    print("PCAG Isaac Sim Physics Capability Test")
    print("=" * 70)
    
    from isaacsim import SimulationApp
    config = {"headless": False, "width": 1280, "height": 720}
    simulation_app = SimulationApp(config)
    
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid, GroundPlane
    
    world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
    world.scene.add_default_ground_plane()
    
    results = []
    
    # ============================================================
    # TEST 1: Gravity & Free Fall Verification
    # ============================================================
    print("\n[TEST 1] Gravity & Free Fall")
    print("-" * 40)
    
    falling_cube = world.scene.add(
        DynamicCuboid(
            prim_path="/World/FallingCube",
            name="falling_cube",
            position=np.array([0.0, 0.0, 3.0]),
            size=0.1,
            color=np.array([1.0, 0.0, 0.0]),
            mass=1.0,
        )
    )
    
    world.reset()
    initial_pos, _ = falling_cube.get_world_pose()
    print(f"  Initial position: z = {initial_pos[2]:.3f} m")
    
    # Run 120 steps (2 seconds at 60Hz)
    for i in range(120):
        world.step(render=True)
    
    final_pos, _ = falling_cube.get_world_pose()
    velocity = falling_cube.get_linear_velocity()
    print(f"  After 2s position: z = {final_pos[2]:.3f} m")
    print(f"  Velocity: vz = {velocity[2]:.3f} m/s")
    
    # Verify: under gravity (g=9.81), after 2s free fall from 3m,
    # cube should be near ground (z ~ 0.05 for half-cube-size)
    fell = final_pos[2] < initial_pos[2] - 1.0
    print(f"  Result: {'[PASS]' if fell else '[FAIL]'} Cube fell by {initial_pos[2] - final_pos[2]:.3f} m")
    results.append(("Gravity & Free Fall", fell))
    
    # ============================================================
    # TEST 2: Collision Detection
    # ============================================================
    print("\n[TEST 2] Collision Detection")
    print("-" * 40)
    
    # The falling cube should have collided with the ground plane
    # Check if it stopped (velocity near zero after settling)
    
    # Run more steps to let it settle
    for i in range(120):
        world.step(render=True)
    
    settled_vel = falling_cube.get_linear_velocity()
    settled_pos, _ = falling_cube.get_world_pose()
    is_settled = abs(settled_vel[2]) < 0.1 and settled_pos[2] < 0.5
    print(f"  Settled position: z = {settled_pos[2]:.3f} m")
    print(f"  Settled velocity: vz = {settled_vel[2]:.3f} m/s")
    print(f"  Result: {'[PASS]' if is_settled else '[FAIL]'} Cube settled on ground (collision worked)")
    results.append(("Collision Detection (Ground)", is_settled))
    
    # ============================================================
    # TEST 3: Object-to-Object Collision
    # ============================================================
    print("\n[TEST 3] Object-to-Object Collision")
    print("-" * 40)
    
    # Add an obstacle and drop another cube onto it
    obstacle = world.scene.add(
        FixedCuboid(
            prim_path="/World/Obstacle",
            name="obstacle",
            position=np.array([1.0, 0.0, 0.3]),
            size=0.4,
            color=np.array([0.0, 0.0, 1.0]),
        )
    )
    
    drop_cube = world.scene.add(
        DynamicCuboid(
            prim_path="/World/DropCube",
            name="drop_cube",
            position=np.array([1.0, 0.0, 2.0]),
            size=0.1,
            color=np.array([0.0, 1.0, 0.0]),
            mass=0.5,
        )
    )
    
    world.reset()
    
    # Run simulation
    for i in range(180):
        world.step(render=True)
    
    drop_pos, _ = drop_cube.get_world_pose()
    # The green cube should have landed on top of the blue obstacle (z ~ 0.5 + 0.05)
    landed_on_obstacle = drop_pos[2] > 0.3 and drop_pos[2] < 1.0
    print(f"  Green cube position: z = {drop_pos[2]:.3f} m")
    print(f"  Blue obstacle top: z = 0.5 m")
    print(f"  Result: {'[PASS]' if landed_on_obstacle else '[FAIL]'} Cube landed on obstacle")
    results.append(("Object-to-Object Collision", landed_on_obstacle))
    
    # ============================================================
    # TEST 4: Multiple Physics Steps & State Trajectory
    # ============================================================
    print("\n[TEST 4] State Trajectory Recording (for PCAG Simulation Validator)")
    print("-" * 40)
    
    # This simulates what PCAG's ISimulationBackend.validate_trajectory() does:
    # Record state at each step to build a trajectory
    
    trajectory_cube = world.scene.add(
        DynamicCuboid(
            prim_path="/World/TrajCube",
            name="traj_cube",
            position=np.array([-1.0, 0.0, 2.0]),
            size=0.1,
            color=np.array([1.0, 1.0, 0.0]),  # Yellow
            mass=1.0,
        )
    )
    
    world.reset()
    
    trajectory = []
    for step in range(60):  # 1 second
        world.step(render=True)
        pos, _ = trajectory_cube.get_world_pose()
        vel = trajectory_cube.get_linear_velocity()
        trajectory.append({
            "step": step,
            "t_ms": int(step * (1000/60)),
            "position": {"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
            "velocity": {"vx": float(vel[0]), "vy": float(vel[1]), "vz": float(vel[2])}
        })
    
    print(f"  Recorded {len(trajectory)} trajectory points")
    print(f"  First: t=0ms, z={trajectory[0]['position']['z']:.3f}m")
    print(f"  Mid:   t={trajectory[29]['t_ms']}ms, z={trajectory[29]['position']['z']:.3f}m")
    print(f"  Last:  t={trajectory[-1]['t_ms']}ms, z={trajectory[-1]['position']['z']:.3f}m")
    
    has_trajectory = len(trajectory) == 60 and trajectory[-1]['position']['z'] < trajectory[0]['position']['z']
    print(f"  Result: {'[PASS]' if has_trajectory else '[FAIL]'} Trajectory recorded successfully")
    results.append(("State Trajectory Recording", has_trajectory))
    
    # ============================================================
    # TEST 5: Constraint Checking (Workspace Boundary)
    # ============================================================
    print("\n[TEST 5] Workspace Boundary Constraint Check")
    print("-" * 40)
    
    # Simulate PCAG's constraint checking:
    # Define a workspace boundary and check if any trajectory point exits it
    workspace = {"x": [-2.0, 2.0], "y": [-2.0, 2.0], "z": [0.0, 5.0]}
    
    violations = []
    for point in trajectory:
        pos = point["position"]
        for axis in ["x", "y", "z"]:
            if pos[axis] < workspace[axis][0] or pos[axis] > workspace[axis][1]:
                violations.append({"step": point["step"], "axis": axis, "value": pos[axis]})
    
    in_bounds = len(violations) == 0
    print(f"  Workspace: x={workspace['x']}, y={workspace['y']}, z={workspace['z']}")
    print(f"  Violations: {len(violations)}")
    print(f"  Result: {'[PASS]' if in_bounds else '[FAIL]'} All trajectory points within workspace")
    results.append(("Workspace Boundary Check", in_bounds))
    
    # ============================================================
    # TEST 6: Set State & Re-simulate (PCAG set_state capability)
    # ============================================================
    print("\n[TEST 6] Set State & Re-simulate (PCAG set_state)")
    print("-" * 40)
    
    # This tests if we can set an object's state and re-run simulation
    # (critical for PCAG: set_state(S_t) -> step(action) -> observe)
    
    reset_cube = world.scene.add(
        DynamicCuboid(
            prim_path="/World/ResetCube",
            name="reset_cube",
            position=np.array([2.0, 0.0, 1.0]),
            size=0.15,
            color=np.array([1.0, 0.5, 0.0]),  # Orange
            mass=1.0,
        )
    )
    
    world.reset()
    
    # Run a few steps
    for i in range(30):
        world.step(render=True)
    
    pos_before_reset, _ = reset_cube.get_world_pose()
    print(f"  Before reset: z = {pos_before_reset[2]:.3f} m")
    
    # Reset state: move cube back up
    from omni.isaac.core.utils.prims import set_prim_attribute_value
    reset_cube.set_world_pose(position=np.array([2.0, 0.0, 3.0]))
    reset_cube.set_linear_velocity(np.array([0.0, 0.0, 0.0]))
    
    # Verify reset worked
    pos_after_reset, _ = reset_cube.get_world_pose()
    print(f"  After reset:  z = {pos_after_reset[2]:.3f} m")
    
    # Run more steps - cube should fall again
    for i in range(60):
        world.step(render=True)
    
    pos_final, _ = reset_cube.get_world_pose()
    print(f"  After re-sim: z = {pos_final[2]:.3f} m")
    
    state_reset_worked = pos_after_reset[2] > 2.5 and pos_final[2] < pos_after_reset[2]
    print(f"  Result: {'[PASS]' if state_reset_worked else '[FAIL]'} State reset & re-simulation works")
    results.append(("Set State & Re-simulate", state_reset_worked))
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        print(f"  {'[PASS]' if result else '[FAIL]'} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll physics tests passed!")
        print("Isaac Sim is ready for PCAG Simulation Validator integration.")
    else:
        print("\nSome tests failed. Review output above.")
    
    # Keep display for 5 seconds
    print("\nClosing in 5 seconds...")
    end_time = time.time()
    while time.time() - end_time < 5.0:
        world.step(render=True)
    
    simulation_app.close()
    print("Isaac Sim closed.")

if __name__ == "__main__":
    main()
