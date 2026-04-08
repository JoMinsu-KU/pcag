# Process Source Release v2 QC Report

Release date: `2026-03-20`

## Scope

- Release type: `process_only`
- Base release: `process_source_release_v1`
- Added families: `startup_ramp`, `cooling_failure_management`, `pressure_relief_margin`

## Counts

- Nominal cases: `36`
- Unsafe cases: `48`
- Fault cases: `36`
- Total cases: `120`
- Final-status coverage: `COMMITTED=36, UNSAFE=48, REJECTED=17, ABORTED=15, ERROR=4`

## Coverage

- Covered source families: `cooling_failure_management, disturbance_inspired_supervision, interlock_compatible_recovery, manipulated_variable_constraint_compliance, normal_operating_envelope, pressure_relief_margin, startup_ramp`
- Covered runtime profiles: `reactor_nominal_profile`, `reactor_high_heat_profile`, `reactor_disturbance_profile`
- Outcome-complete release artifact: `all_cases.json`

## Consistency checks

- All cases use `scenario_family = process_interlock`.
- All cases lower to the public process action subset `set_heater_output` / `set_cooling_valve`.
- All source references exist in the frozen local Tennessee Eastman reference acquisition target.
- All process profile references exist in the implemented scene pack.
- All label triplets satisfy the frozen label taxonomy.

## Expansion families

- `startup_ramp`: staged startup stabilization and ramp overshoot counterfactuals.
- `cooling_failure_management`: high-heat cooling recovery and degraded-cooling supervision motifs.
- `pressure_relief_margin`: disturbance and relief-margin preservation motifs.

## Fault mutation policy

- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`
- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`
- Infrastructure faults: `ot_interface_error`

## Notes for the paper

- The Tennessee Eastman tree is used as a public process-control provenance anchor, not as a raw time-series classification benchmark.
- This release is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1`.
- The process benchmark is intended to evaluate envelope preservation, startup/cooling/relief supervision, and fault-aware execution assurance through the full PCAG stack.

