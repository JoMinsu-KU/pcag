# Robot Source Release v3

This folder stores the next robot expansion draft layered on top of the
generated `robot_source_release_v2` release.

## Scope

- parent release: `robot_source_release_v2`
- supplemental family: `fixture_insertion`
- canonical shell:
  `tests/benchmarks/pcag_ijamt_benchmark/scene_pack/robot/robot_fixture_insertion_cell/`

## Purpose

The goal of v3 is to keep the validated v2 robot coverage intact while adding
the first insertion-oriented robot family. This family focuses on bounded
insertion depth, orientation margin, and side-wall contact inside a deeper
fixture corridor.

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

- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_source_release_v3.py`
- `tests/benchmarks/pcag_ijamt_benchmark/generation/generate_robot_pcag_execution_dataset_v3.py`

## Policy alignment

This release stays aligned to the unified benchmark policy:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`

Recommended registration helper:

- `python scripts/seed_pcag_benchmark_policy.py`

## Execution

Use the existing robot runner with `--dataset-path`:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v3/pcag_execution_dataset.json`
- recommended first live case:
  `python tests/benchmarks/pcag_ijamt_benchmark/run_robot_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/robot_source_release_v3/pcag_execution_dataset.json --case-id robot_nominal_isaaclab_reach_fixture_insertion_align_001 --stop-on-fail`

## Current state

This release is generated, documented, and validated at the initial
family-expansion level. The full `12`-case `fixture_insertion` family has been
exercised through the live PCAG stack.

Result file:

- `tests/benchmarks/pcag_ijamt_benchmark/results/robot_fixture_insertion_family_latest.json`

Current generated counts:

- total: `76`
- nominal: `22`
- unsafe: `30`
- fault: `24`
- supplemental fixture-insertion cases: `12`

The current draft keeps a compact `4 / 4 / 4` family split so the next robot
family can be validated before expanding toward the planned `8 / 12 / 8`
target size.
