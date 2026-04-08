# Process Source Release v2

This folder stores the expanded process benchmark release aligned to the
Tennessee-Eastman-anchored process benchmark track.

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

## Scope

This release preserves the validated v1 process benchmark and adds three new
single-asset families:

- `startup_ramp`
- `cooling_failure_management`
- `pressure_relief_margin`

It remains intentionally scoped to process/reactor benchmark cases only and
uses:

- `tep_process_curated` as the frozen provenance anchor
- `reactor_nominal_profile`
- `reactor_high_heat_profile`
- `reactor_disturbance_profile`

All process commands are lowered into the public action subset:

- `set_heater_output`
- `set_cooling_valve`

## Outcome coverage

The frozen release is outcome-complete and includes:

- `COMMITTED`
- `UNSAFE`
- `REJECTED`
- `ABORTED`
- `ERROR`

The source release contains:

- `36 nominal`
- `48 unsafe`
- `36 fault`
- `120 total`

## Execution dataset

`pcag_execution_dataset.json` is derived directly from `all_cases.json`.
It reshapes each frozen case into:

- runtime preload instructions
- Gateway-facing proof construction hints
- expected final PCAG outcome
- expected evidence-stage sequence

## Policy alignment

This release is aligned to the unified benchmark policy:

- `tests/benchmarks/pcag_ijamt_benchmark/policies/pcag_benchmark_policy_v1.json`
- policy version:
  `v2026-03-20-pcag-benchmark-v1`
- policy profile:
  `pcag_benchmark_v1`

Recommended registration helper:

```powershell
conda activate pcag
python scripts/seed_pcag_benchmark_policy.py
```

Compatibility wrapper:

```powershell
conda activate pcag
python scripts/seed_process_benchmark_policy.py
```

## Live runner

Run the expanded benchmark with:

```powershell
conda activate pcag
python tests/benchmarks/pcag_ijamt_benchmark/run_process_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/process_source_release_v2/pcag_execution_dataset.json
```

Run a single case with the optional persistent reactor GUI:

```powershell
python tests/benchmarks/pcag_ijamt_benchmark/run_process_pcag_benchmark.py --dataset-path tests/benchmarks/pcag_ijamt_benchmark/releases/process_source_release_v2/pcag_execution_dataset.json --case-id process_nominal_tep_startup_ramp_heater_stage_1_001 --show-process-gui
```

The reactor viewer stays open in `persistent` mode by default so one window can
replay multiple process cases in sequence.

If Safety Cluster is started with `PCAG_ENABLE_BENCHMARK_TWIN_GUIS=true`, the
persistent reactor viewer can be booted centrally from server startup and this
runner can be used without process-specific GUI flags.

## Current live check status

- release generation completed
- representative scenario-wise live runs passed for:
  - `startup_ramp` nominal / unsafe / fault
  - `cooling_failure_management` nominal / unsafe / fault
  - `pressure_relief_margin` nominal / unsafe / fault

## Interpretation

This benchmark is an ODE-backed process envelope, startup, cooling-management,
and pressure-relief study. It is not a photorealistic 3D plant simulation. A
`COMMITTED` result should be read as a full PCAG execution-assurance success
over the public PLC-backed runtime path, not as proof of a real industrial
reactor actuation study.
