# Benchmark Policies

This directory stores benchmark policy artifacts used to register the running
PCAG stack before live benchmark execution.

## Recommended active policy

The recommended runtime registration target is now the unified benchmark
policy:

- `pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`
- policy profile:
  `pcag_benchmark_v1`

Registration helper:

- `scripts/seed_pcag_benchmark_policy.py`

This unified policy contains benchmark-aligned asset profiles for:

- `robot_arm_01`
- `agv_01`
- `reactor_01`

It is the preferred policy for:

- per-asset live benchmark execution
- centralized GUI benchmark sessions
- integrated cross-asset benchmark execution

## Compatibility seed wrappers

The following seed helpers are retained for convenience:

- `scripts/seed_robot_benchmark_policy.py`
- `scripts/seed_agv_benchmark_policy.py`
- `scripts/seed_process_benchmark_policy.py`

These scripts now seed the same unified benchmark policy. They no longer switch
the active stack back to separate asset-primary policies.

## Historical asset-primary artifacts

The following policy JSON files are still kept in this directory:

- `robot_pcag_benchmark_policy_v1.json`
- `agv_pcag_benchmark_policy_v1.json`
- `process_pcag_benchmark_policy_v1.json`

They are retained for traceability and for understanding how each asset profile
was originally tuned before policy integration, but they are no longer the
recommended registration targets for live benchmark execution.

## Unified policy design notes

The unified policy keeps one stable benchmark baseline across assets while
per-case variability remains in benchmark data:

- `runtime_context`
- `initial_state`
- `action_sequence`
- `proof_hints`
- `fault_injection`

## Asset-specific execution semantics under the unified policy

### Robot

Robot benchmark execution remains hybrid in the current public stack:

- `sensor_source = isaac_sim_sensor`
- `simulation.engine = isaac_sim`
- final robot commit acknowledgement is mock-backed

### AGV

AGV benchmark execution is PLC-adapter-backed:

- `sensor_source = modbus_sensor`
- `simulation.engine = discrete_event`
- final commit uses the PLC-adapter-backed public execution path

### Process

Process benchmark execution is PLC-adapter-backed:

- `sensor_source = modbus_sensor`
- `simulation.engine = ode_solver`
- final commit uses the PLC-adapter-backed public execution path

## Live validation alignment

Validated releases already aligned to the unified policy version:

- robot:
  `releases/robot_source_release_v4/pcag_execution_dataset.json`
  - `120/120 pass`
- AGV:
  `releases/agv_source_release_v3/pcag_execution_dataset.json`
  - `128/128 pass`
- process:
  `releases/process_source_release_v2/pcag_execution_dataset.json`
  - `120/120 pass`

Integrated execution release aligned to the same policy:

- `releases/integrated_benchmark_release_v2/pcag_execution_dataset.json`
  - `368 total cases`

## Builders

Policy builders in this directory:

- `build_pcag_benchmark_policy_v1.py`
- `build_agv_benchmark_policy_v1.py`
- `build_process_benchmark_policy_v1.py`

The unified builder is the recommended paper-facing and runtime-facing entry
point.
