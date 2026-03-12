"""
Isaac Sim 4.5.0 Basic Connectivity Test
========================================
This test verifies that:
1. Isaac Sim can be imported
2. A headless simulation can be started
3. A simple scene can be created
4. Physics simulation can run
5. State can be read back

Run with Isaac Sim's Python or conda pcag-isaac environment.
"""

import sys
import os

def test_isaacsim_import():
    """Test 1: Can we import isaacsim?"""
    try:
        from isaacsim import SimulationApp
        print("[PASS] Test 1 PASSED: isaacsim imported successfully")
        return True
    except ImportError as e:
        print(f"[FAIL] Test 1 FAILED: Cannot import isaacsim - {e}")
        return False

def test_headless_startup():
    """Test 2: Can we start Isaac Sim in headless mode?"""
    try:
        from isaacsim import SimulationApp
        
        # Start headless (no GUI)
        #config = {"headless": True}
        simulation_app = SimulationApp()
        #simulation_app = SimulationApp(config)
        print("[PASS] Test 2 PASSED: Isaac Sim started in headless mode")
        return simulation_app
    except Exception as e:
        print(f"[FAIL] Test 2 FAILED: Cannot start headless - {e}")
        return None

def test_create_scene(simulation_app):
    """Test 3: Can we create a basic scene with a cube?"""
    try:
        import omni.isaac.core.utils.stage as stage_utils
        from omni.isaac.core import World
        
        world = World(stage_units_in_meters=1.0)
        world.scene.add_default_ground_plane()
        
        # Add a simple cube
        from omni.isaac.core.objects import DynamicCuboid
        cube = world.scene.add(
            DynamicCuboid(
                prim_path="/World/Cube",
                name="test_cube",
                position=[0, 0, 1.0],  # 1 meter above ground
                size=0.1,  # 10cm cube
                color=[1, 0, 0],  # Red
            )
        )
        
        world.reset()
        print("[PASS] Test 3 PASSED: Scene created with ground plane and cube")
        return world, cube
    except Exception as e:
        print(f"[FAIL] Test 3 FAILED: Cannot create scene - {e}")
        return None, None

def test_physics_step(world, cube):
    """Test 4: Can we run physics simulation steps?"""
    try:
        # Get initial position
        initial_pos, _ = cube.get_world_pose()
        print(f"  Initial cube position: {initial_pos}")
        
        # Run 100 physics steps (cube should fall due to gravity)
        for i in range(100):
            world.step(render=False)  # No rendering in headless
        
        # Get final position
        final_pos, _ = cube.get_world_pose()
        print(f"  Final cube position: {final_pos}")
        
        # Cube should have fallen (z decreased)
        if final_pos[2] < initial_pos[2]:
            print("[PASS] Test 4 PASSED: Physics simulation works (cube fell due to gravity)")
            return True
        else:
            print("[FAIL] Test 4 FAILED: Cube didn't fall - physics not working")
            return False
    except Exception as e:
        print(f"[FAIL] Test 4 FAILED: Physics step error - {e}")
        return False

def test_read_state(world, cube):
    """Test 5: Can we read object state (position, velocity)?"""
    try:
        position, orientation = cube.get_world_pose()
        linear_velocity = cube.get_linear_velocity()
        angular_velocity = cube.get_angular_velocity()
        
        print(f"  Position: {position}")
        print(f"  Orientation: {orientation}")
        print(f"  Linear Velocity: {linear_velocity}")
        print(f"  Angular Velocity: {angular_velocity}")
        
        print("[PASS] Test 5 PASSED: State reading works")
        return True
    except Exception as e:
        print(f"[FAIL] Test 5 FAILED: Cannot read state - {e}")
        return False

def main():
    print("=" * 60)
    print("PCAG Isaac Sim 4.5.0 Basic Connectivity Test")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Import
    results.append(test_isaacsim_import())
    if not results[-1]:
        print("\n[STOP] Cannot proceed without isaacsim import. Exiting.")
        return
    
    # Test 2: Headless startup
    simulation_app = test_headless_startup()
    results.append(simulation_app is not None)
    if not results[-1]:
        print("\n[STOP] Cannot proceed without headless startup. Exiting.")
        return
    
    # Test 3: Scene creation
    world, cube = test_create_scene(simulation_app)
    results.append(world is not None)
    
    if world and cube:
        # Test 4: Physics
        results.append(test_physics_step(world, cube))
        
        # Test 5: State reading
        results.append(test_read_state(world, cube))
    
    # Cleanup
    try:
        simulation_app.close()
        print("\n[PASS] Isaac Sim closed cleanly")
    except:
        pass
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    if passed == total:
        print("[SUCCESS] All tests passed! Isaac Sim integration is ready.")
    else:
        print("[WARNING] Some tests failed. Check output above.")
    print("=" * 60)

if __name__ == "__main__":
    main()
