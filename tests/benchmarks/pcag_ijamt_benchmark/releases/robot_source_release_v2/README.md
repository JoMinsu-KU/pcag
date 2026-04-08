# Robot Source Release v2

This folder stores the first robot expansion release layered on top of the
validated `robot_source_release_v1` core.

## Scope

- parent release: `robot_source_release_v1`
- supplemental family: `narrow_clearance_approach`
- canonical shell:
  `tests/benchmarks/pcag_ijamt_benchmark/scene_pack/robot/robot_narrow_clearance_cell/`

## Purpose

The goal of v2 is not to replace the validated v1 release. Instead, it keeps
all v1 robot cases and appends the first phase-A single-asset expansion family
so the benchmark can grow toward the planned `500+` case scale.

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

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_source_release_v2.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_pcag_execution_dataset_v2.py`

## Policy alignment

This release stays aligned to the unified benchmark policy:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

## Execution

Use the existing robot runner with `--dataset-path`:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v2/pcag_execution_dataset.json`
- recommended first live case:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v2/pcag_execution_dataset.json --case-id robot_nominal_isaaclab_reach_narrow_clearance_approach_001 --stop-on-fail`

## Current state

This release is generated, documented, and now validated at the
family-expansion level. The full `28`-case `narrow_clearance_approach` family
has been exercised through the live PCAG stack.

Result file:

- `tests/benchmarks/pcag_ijamt_benchmark/results/robot_narrow_clearance_family_latest.json`

Current generated counts:

- total: `64`
- nominal: `18`
- unsafe: `26`
- fault: `20`
- supplemental narrow-clearance cases: `28`
