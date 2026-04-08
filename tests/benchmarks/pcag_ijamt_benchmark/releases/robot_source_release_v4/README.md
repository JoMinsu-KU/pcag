# Robot Source Release v4

This folder stores the expanded robot draft release that completes the planned
single-asset robot growth target for the current benchmark phase.

## Scope

- parent release: `robot_source_release_v3`
- supplemental families:
  - `fixture_insertion` expansion to the planned `8 / 12 / 8`
  - `conveyor_timing_pick` new family at `8 / 12 / 8`
- canonical shells:
  - `tests/benchmarks/pcag_ijamt_benchmark/scene_pack/robot/robot_fixture_insertion_cell/`
  - `tests/benchmarks/pcag_ijamt_benchmark/scene_pack/robot/robot_stack_cell/`
  - `tests/benchmarks/pcag_ijamt_benchmark/scene_pack/robot/robot_pick_place_cell/`

## Purpose

The goal of v4 is to keep the generated v3 robot coverage intact while:

- expanding `fixture_insertion` from the initial `12` cases to the planned
  `28`-case family
- adding the `conveyor_timing_pick` family to encode early / nominal / late
  pickup-window difficulty without changing the single-asset PCAG contract

## Files

- `nominal_dataset.json`
- `unsafe_dataset.json`
- `fault_dataset.json`
- `all_cases.json`
- `dataset_manifest.json`
- `qc_report.md`
- `pcag_execution_dataset.json`
- `pcag_execution_manifest.json`
- `pcag_execution_qc.md`

## Generators

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_source_release_v4.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_pcag_execution_dataset_v4.py`

## Policy alignment

This release stays aligned to the unified benchmark policy:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

## Execution

Use the existing robot runner with `--dataset-path`:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json`

Representative smoke commands:

- nominal fixture expansion:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json --case-id robot_nominal_isaaclab_reach_fixture_insertion_align_left_bias_001 --stop-on-fail`
- unsafe fixture expansion:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json --case-id robot_unsafe_isaaclab_reach_fixture_insertion_align_left_bias_joint_limit_001 --stop-on-fail`
- fault fixture expansion:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json --case-id robot_fault_isaaclab_reach_fixture_insertion_align_left_bias_policy_mismatch_001 --stop-on-fail`
- nominal conveyor timing:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json --case-id robot_nominal_isaaclab_stack_conveyor_timing_pick_early_window_001 --stop-on-fail`
- unsafe conveyor timing:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json --case-id robot_unsafe_isaaclab_stack_conveyor_timing_pick_nominal_window_fixture_collision_001 --stop-on-fail`
- fault conveyor timing:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v4/pcag_execution_dataset.json --case-id robot_fault_isaaclab_stack_conveyor_timing_pick_early_window_policy_mismatch_001 --stop-on-fail`

## Current state

This release is generated and documented at the planned robot target size.

Current generated counts:

- total: `120`
- nominal: `34`
- unsafe: `50`
- fault: `36`
- `narrow_clearance_approach`: `28`
- `fixture_insertion`: `28`
- `conveyor_timing_pick`: `28`

Current live status:

- expanded `fixture_insertion` representative nominal / unsafe / fault smoke:
  passed
- new `conveyor_timing_pick` representative nominal / unsafe / fault smoke:
  passed
- full `120`-case live sweep:
  not yet frozen as a single report

This release therefore closes the generation target for the current robot
single-asset expansion phase, while leaving the final full-release live sweep
as a separate verification pass.
