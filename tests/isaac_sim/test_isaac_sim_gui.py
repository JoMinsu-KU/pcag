"""
Isaac Sim 4.5.0 GUI Visual Test
================================
This test runs Isaac Sim with GUI to visually confirm:
- Scene creation (ground + red cube)
- Physics simulation (cube falls due to gravity)
- Rendering works

Run with: conda activate pcag-isaac && python tests/isaac_sim/test_isaac_sim_gui.py
"""

import time

def main():
    print("=" * 60)
    print("PCAG Isaac Sim GUI Visual Test")
    print("Isaac Sim GUI가 열립니다. 큐브가 떨어지는 것을 확인하세요.")
    print("=" * 60)
    
    # Start with GUI
    from isaacsim import SimulationApp
    config = {
        "headless": False,  # GUI 모드!
        "width": 1280,
        "height": 720,
    }
    simulation_app = SimulationApp(config)
    print("[OK] Isaac Sim GUI started")
    
    # Import after SimulationApp
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
    import numpy as np
    
    # Create world
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    
    # Add a red cube above ground
    cube = world.scene.add(
        DynamicCuboid(
            prim_path="/World/RedCube",
            name="red_cube",
            position=np.array([0.0, 0.0, 2.0]),  # 2 meters high
            size=0.2,  # 20cm cube
            color=np.array([1.0, 0.0, 0.0]),  # Red
            mass=1.0,
        )
    )
    
    # Add a blue obstacle cube on the ground
    obstacle = world.scene.add(
        FixedCuboid(
            prim_path="/World/BlueCube",
            name="blue_obstacle",
            position=np.array([0.3, 0.0, 0.1]),
            size=0.2,
            color=np.array([0.0, 0.0, 1.0]),  # Blue
        )
    )
    
    print("[OK] Scene created: Ground + Red cube (falling) + Blue cube (obstacle)")
    
    # Reset and start simulation
    world.reset()
    
    print("\n[START] Simulation starting - running for 10 seconds...")
    print("   Check the red cube falling in the Isaac Sim viewport.\n")
    
    # Run simulation for ~10 seconds with rendering
    start_time = time.time()
    step_count = 0
    
    while time.time() - start_time < 10.0:
        world.step(render=True)  # render=True for GUI
        step_count += 1
        
        # Print position every 60 steps (~1 second)
        if step_count % 60 == 0:
            pos, _ = cube.get_world_pose()
            vel = cube.get_linear_velocity()
            elapsed = time.time() - start_time
            print(f"  [{elapsed:.1f}s] Cube pos: x={pos[0]:.3f}, y={pos[1]:.3f}, z={pos[2]:.3f} | vel: {vel}")
    
    # Final state
    final_pos, _ = cube.get_world_pose()
    print(f"\n[POS] Final cube position: x={final_pos[0]:.3f}, y={final_pos[1]:.3f}, z={final_pos[2]:.3f}")
    
    if final_pos[2] < 1.5:
        print("[OK] Physics simulation SUCCESS: Cube fell due to gravity!")
    else:
        print("[FAIL] Physics simulation FAILED: Cube did not fall.")
    
    print("\n[WAIT] Closing in 5 seconds... (check the Isaac Sim viewport)")
    # Keep rendering for 5 more seconds so user can look
    end_time = time.time()
    while time.time() - end_time < 5.0:
        world.step(render=True)
    
    # Cleanup
    simulation_app.close()
    print("\n[OK] Isaac Sim shutdown complete")

if __name__ == "__main__":
    main()
