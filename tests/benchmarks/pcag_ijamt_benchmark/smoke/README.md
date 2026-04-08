# PCAG IJAMT Benchmark Smoke Scripts

This directory contains user-runnable smoke scripts for the first three
benchmark shells.

These scripts are intended for manual verification before the full benchmark
runtime registry is integrated into the Gateway and Safety Cluster flow.

## Environment split

- AGV shell smoke test: run in `pcag`
- Reactor shell smoke test: run in `pcag`
- Robot shell smoke test: run in `pcag-isaac`

## Commands

### 1. AGV nominal shell

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_agv_transfer_shell_smoke.py
```

Expected outcome:

- exits with code `0`
- prints a `SAFE` result

### 2. Reactor nominal shell

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_reactor_nominal_shell_smoke.py
```

Expected outcome:

- exits with code `0`
- prints a `SAFE` result

### 3. Robot pick-place shell

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_pick_place_shell_smoke.py --headless true
```

Expected outcome:

- initializes Isaac Sim
- loads the `robot_pick_place_cell` USD shell as a benchmark environment
- spawns a fallback Franka articulation
- executes an initial posture set and a target posture set
- exits with code `0` if the shell and robot both run successfully

This robot script is intentionally a standalone shell smoke test, not yet a
full benchmark-run entrypoint. Its main purpose is to confirm that the
generated USD shell can be opened inside Isaac and can coexist with a spawned
robot articulation.

### 4. Robot stack shell (`Franka-first`, recommended)

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_shell_smoke.py --headless true
```

Expected outcome:

- initializes Isaac Sim
- loads the `robot_stack_cell` USD shell as a benchmark environment
- spawns a fallback Franka articulation
- executes visible interpolated staged joint motions for a stack-family environment
- exits with code `0` if the shell and robot both run successfully

This is the preferred robot smoke path for the actual dataset-construction
strategy, because it aligns with Franka-native `stack` provenance in IsaacLab
and stack-family provenance in MimicGen.

### 5. Robot NVIDIA pick-and-place smoke (`real manipulation`)

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_pick_place_nvidia_smoke.py --headless true
```

Expected outcome:

- initializes Isaac Sim
- loads the `robot_stack_cell` manufacturing shell
- builds collider-backed runtime supports aligned with the visible conveyor, guides, nest, and pallet
- spawns a Franka robot and a dynamic workpiece cube
- runs NVIDIA's Franka `PickPlaceController`
- exits with code `0` only if the controller finishes and the workpiece reaches the target tolerance

For visual confirmation or paper screenshots, use:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_pick_place_nvidia_smoke.py --headless false --wait-for-enter
```

This is the closest smoke path to the future benchmark execution flow because
it uses controller-driven rigid-body manipulation instead of direct joint
teleportation.

### 6. Robot safety-validation smoke (`benchmark-aligned`)

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_safety_smoke.py --headless true --profile safe
```

Expected outcome:

- initializes Isaac Sim
- loads the `robot_stack_cell` manufacturing shell
- spawns the canonical Franka at the benchmark mount pose
- interpolates benchmark-style joint targets
- evaluates joint-limit, workspace, and fixture-penetration signals
- exits with code `0` when the observed verdict matches the expected outcome

This is the preferred robot smoke path for the actual PCAG benchmark logic,
because it focuses on safety validation instead of manipulation-task success.

To verify joint-limit detection:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_safety_smoke.py --headless true --profile joint_limit
```

To probe a fixture-collision-style unsafe target on the stack shell:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_safety_smoke.py --headless false --profile collision_fixture --expect unsafe --wait-for-enter
```

To run the same safety-validation flow on the pick-place shell:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_pick_place_safety_smoke.py --headless true --profile safe
```

This wrapper targets `robot_pick_place_cell`, which now exposes the same style
of collider-backed runtime objects and safety-probe metadata as the stack
shell.

To probe a fixture-collision-style unsafe target on the pick-place shell:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_pick_place_safety_smoke.py --headless false --profile collision_fixture --expect unsafe --wait-for-enter
```

### 7. Collision-profile search helper

If the provisional `collision_fixture` profile does not actually penetrate a
forbidden fixture in your local Isaac run, use the search helper to find a
better candidate:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_collision_profile_search.py --shell-id robot_stack_cell --headless false --stop-on-first-hit --wait-for-enter
```

or:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_collision_profile_search.py --shell-id robot_pick_place_cell --headless false --stop-on-first-hit --wait-for-enter
```

Expected outcome:

- exits with code `0` when a penetrating candidate is found
- prints a `suggested_target_joints_json` value
- writes JSON result files under `tests/benchmarks/pcag_ijamt_benchmark/smoke/results/`
- that suggested target can then be copied back into the shell profile or the
  frozen dataset release

### 8. Collision-threshold calibration helper

After you have a confirmed hit candidate, use the threshold calibrator to find
the boundary between a safe target and a penetrating target:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_collision_threshold_calibration.py --shell-id robot_stack_cell --headless false --wait-for-enter
```

or:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_collision_threshold_calibration.py --shell-id robot_pick_place_cell --headless false --wait-for-enter
```

Expected outcome:

- reads the latest collision-search result for the shell
- binary-searches the boundary between the shell safe target and the hit target
- if the latest search hit is only marginal, automatically expands the upper
  bound farther in the same direction until a stable penetrating target is found
- writes JSON result files under `tests/benchmarks/pcag_ijamt_benchmark/smoke/results/`
- prints `recommended_safe_target_joints_json` and `recommended_unsafe_target_joints_json`

This is the preferred path when you want dataset cases that are just below and
just above the collision boundary instead of arbitrary collision candidates.

To test a custom dataset-style target sequence:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_safety_smoke.py --headless false --target-joints-json "[[0.18,-0.54,0.08,-2.06,0.10,1.70,0.82]]" --expect any --wait-for-enter
```

For paper screenshots or visual inspection, use:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_shell_smoke.py --headless false --hold-seconds 45 --phase-frames 90
```

If you want the final frame to stay open until you close it manually:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/smoke/run_robot_stack_shell_smoke.py --headless false --wait-for-enter --phase-frames 90
```
