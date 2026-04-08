# Robot Source Release v1

This folder contains the first frozen robot benchmark release generated from
the IJAMT benchmark rules.

The release is grounded in two frozen provenance sources:

- `isaaclab_eval_industrial`
- `mimicgen_assembly`

It intentionally limits itself to the currently implemented robot shells:

- `robot_pick_place_cell`
- `robot_stack_cell`

## Files

- `nominal_dataset.json`
- `unsafe_dataset.json`
- `fault_dataset.json`
- `all_cases.json`
- `pcag_execution_dataset.json`
- `pcag_execution_manifest.json`
- `pcag_execution_qc.md`
- `dataset_manifest.json`
- `qc_report.md`

## Generators

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_source_release_v1.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_pcag_execution_dataset_v1.py`

## Policy alignment

This release is now aligned to the unified benchmark policy:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`
- policy profile:
  `pcag_benchmark_v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

Compatibility wrapper:

- `python scripts/seed_robot_benchmark_policy.py`

## Live runner

- `tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py`

## Scope notes

- All executable cases are lowered to `move_joint` with `target_positions`.
- IsaacLab task families are used as frozen task and environment provenance.
- MimicGen templates are used as frozen single-arm manipulation provenance.
- The release is outcome-complete and includes:
  - `COMMITTED`
  - `UNSAFE`
  - `REJECTED`
  - `ABORTED`
  - `ERROR`
- The unsafe split mixes:
  - `joint_limit_violation`
  - `fixture_collision_probe`
  - live-validated stack `sim_torque_violation` cases
- The stack `reverify_hash_mismatch` fault uses a safety-passing stack prefix
  sequence so the intended transaction fault is not pre-empted by a torque
  unsafe.

## Execution semantics

The current public robot stack is hybrid:

- sensor snapshots come from `isaac_sim_sensor`
- safety simulation runs through `isaac_sim`
- final execution commit is mock-backed

Therefore robot `COMMITTED` means:

- the full PCAG pipeline succeeded
- integrity, Rules, CBF, simulation, consensus, prepare, reverify, commit, and
  evidence logging completed successfully
- the final actuation acknowledgement came from the mock executor

This release is valid for evaluating end-to-end PCAG execution assurance, but
it should not be described as proof of physical robot actuation fidelity.

## Recommended execution sequence

1. start the live PCAG stack
2. register `v2026-03-20-pcag-benchmark-v1`
3. run:
   `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py`
4. keep the default inter-case cooldown unless intentionally debugging lock
   behavior:
   `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --case-interval-seconds 6.0`

## Current validated live result

- `36/36 pass`
- result file:
  `tests/benchmarks/pcag_ijamt_benchmark/results/robot_pcag_benchmark_latest.json`

## Related expansion release

The first robot phase-A expansion is now drafted separately in:

- `tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v2/`

This keeps the validated v1 release stable while newer robot families are
added incrementally.
