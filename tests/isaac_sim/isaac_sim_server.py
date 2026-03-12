"""
PCAG Isaac Sim Simulation Server (Test Version)
=================================================
Starts Isaac Sim in headless mode with REST API on port 8011.

Usage:
  conda activate pcag-isaac
  python tests/isaac_sim/isaac_sim_server.py

Then test with:
  curl http://localhost:8011/pcag/simulate -X POST -H "Content-Type: application/json" -d '{"test": true}'
  
Or run: python tests/isaac_sim/test_isaac_sim_api.py
"""

import sys
import json
import time
import numpy as np

# Enable HTTP services BEFORE importing SimulationApp
sys.argv.extend([
    '--enable', 'omni.services.core',
    '--enable', 'omni.services.transport.server.http',
])

try:
    from isaacsim import SimulationApp
except ImportError:
    from omni.isaac.kit import SimulationApp

def main():
    print("=" * 60)
    print("PCAG Isaac Sim Simulation Server (Test)")
    print("=" * 60)
    
    # Start Isaac Sim headless
    config = {"headless": False}
    simulation_app = SimulationApp(config)
    
    # Import after SimulationApp init
    try:
        from isaacsim.core.api import World
        from isaacsim.core.api.objects import DynamicCuboid
    except ImportError:
        from omni.isaac.core import World
        from omni.isaac.core.objects import DynamicCuboid
        
    import omni.services.core.main as services_main
    from fastapi import APIRouter
    from pydantic import BaseModel, Field
    from typing import Optional, List
    
    # Create world with ground plane
    world = World(stage_units_in_meters=1.0, physics_dt=1.0/60.0)
    world.scene.add_default_ground_plane()
    world.reset()
    
    print("[OK] World created with ground plane")
    
    # --- Define API models ---
    class SimulateRequest(BaseModel):
        initial_position: List[float] = Field(default=[0.0, 0.0, 2.0], description="Initial XYZ position")
        cube_size: float = Field(default=0.1, description="Cube size in meters")
        cube_mass: float = Field(default=1.0, description="Cube mass in kg")
        steps: int = Field(default=60, description="Number of simulation steps (60 = 1 second)")
        workspace_bounds: Optional[dict] = Field(
            default={"x": [-5.0, 5.0], "y": [-5.0, 5.0], "z": [0.0, 10.0]},
            description="Workspace boundaries for constraint checking"
        )
    
    class TrajectoryPoint(BaseModel):
        step: int
        t_ms: int
        position: dict  # {x, y, z}
        velocity: dict  # {vx, vy, vz}
    
    class SimulateResponse(BaseModel):
        verdict: str  # SAFE or UNSAFE
        engine: str = "isaac_sim"
        total_steps: int
        trajectory: List[TrajectoryPoint]
        violations: List[dict]
        final_position: dict
        collision_with_ground: bool
        latency_ms: float
    
    # --- Simulation handler ---
    # Keep track of test cubes
    cube_counter = {"count": 0}
    
    def run_simulation(req: SimulateRequest) -> SimulateResponse:
        start_time = time.time()
        
        # Create a unique cube for this request
        cube_counter["count"] += 1
        cube_name = f"sim_cube_{cube_counter['count']}"
        prim_path = f"/World/{cube_name}"
        
        cube = world.scene.add(
            DynamicCuboid(
                prim_path=prim_path,
                name=cube_name,
                position=np.array(req.initial_position),
                size=req.cube_size,
                color=np.array([1.0, 0.0, 0.0]),
                mass=req.cube_mass,
            )
        )
        
        world.reset()
        
        # Run simulation and record trajectory
        trajectory = []
        violations = []
        collision_with_ground = False
        
        for step in range(req.steps):
            world.step(render=False)
            
            pos, _ = cube.get_world_pose()
            vel = cube.get_linear_velocity()
            
            point = TrajectoryPoint(
                step=step,
                t_ms=int(step * (1000/60)),
                position={"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
                velocity={"vx": float(vel[0]), "vy": float(vel[1]), "vz": float(vel[2])}
            )
            trajectory.append(point)
            
            # Check workspace bounds
            if req.workspace_bounds:
                bounds = req.workspace_bounds
                for axis in ["x", "y", "z"]:
                    val = point.position[axis]
                    if val < bounds[axis][0] or val > bounds[axis][1]:
                        violations.append({
                            "step": step,
                            "constraint": f"workspace_{axis}_boundary",
                            "value": val,
                            "limit": bounds[axis]
                        })
            
            # Check collision (cube near ground level)
            if pos[2] <= req.cube_size / 2 + 0.01:
                collision_with_ground = True
        
        # Clean up the cube from scene
        try:
            from omni.isaac.core.utils.prims import delete_prim
        except ImportError:
            try:
                from isaacsim.core.api.utils.prims import delete_prim
            except ImportError:
                 # Fallback using pure USD if possible or just print error
                 print("Could not import delete_prim")
                 def delete_prim(p): pass
        
        try:
            delete_prim(prim_path)
        except:
            pass
        
        final_pos = trajectory[-1].position if trajectory else {"x": 0, "y": 0, "z": 0}
        latency_ms = (time.time() - start_time) * 1000
        
        verdict = "UNSAFE" if len(violations) > 0 else "SAFE"
        
        return SimulateResponse(
            verdict=verdict,
            engine="isaac_sim",
            total_steps=len(trajectory),
            trajectory=trajectory,
            violations=violations,
            final_position=final_pos,
            collision_with_ground=collision_with_ground,
            latency_ms=latency_ms
        )
    
    # --- Register API route ---
    router = APIRouter()
    
    @router.post("/pcag/simulate")
    def simulate_endpoint(request: SimulateRequest):
        result = run_simulation(request)
        return result
    
    @router.get("/pcag/health")
    def health():
        return {"status": "healthy", "engine": "isaac_sim", "version": "4.5.0"}
    
    # Register with Isaac Sim's built-in FastAPI server
    try:
        fastapi_app = services_main.get_app()
        fastapi_app.include_router(router)
    except AttributeError:
        # Fallback for older versions or if get_app is not available in the same way
        try:
            services_main.register_router(router, prefix="", tags=["PCAG"])
        except Exception as e:
            print(f"Error registering router: {e}")
    
    print("[OK] PCAG API routes registered:")
    print("  POST http://localhost:8011/pcag/simulate")
    print("  GET  http://localhost:8011/pcag/health")
    print("")
    print("Server is running. Press Ctrl+C to stop.")
    print("Test with: python tests/isaac_sim/test_isaac_sim_api.py")
    print("=" * 60)
    
    # Keep running
    try:
        while simulation_app.is_running():
            simulation_app.update()
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    simulation_app.close()
    print("Server stopped.")

if __name__ == "__main__":
    main()
