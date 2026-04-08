# Process Source Release v1 QC Report

Release date: `2026-03-20`

## Scope

- Release type: `process_only`
- Upstream source: `tep_process_curated`
- Implemented runtime profiles: `reactor_nominal_profile`, `reactor_high_heat_profile`, `reactor_disturbance_profile`

## Counts

- Nominal cases: `12`
- Unsafe cases: `12`
- Fault cases: `12`
- Total cases: `36`
- Final-status coverage: `COMMITTED=12, UNSAFE=12, REJECTED=7, ABORTED=4, ERROR=1`

## Coverage

- Covered source families: `disturbance_inspired_supervision, interlock_compatible_recovery, manipulated_variable_constraint_compliance, normal_operating_envelope`
- Covered runtime profiles: `reactor_nominal_profile`, `reactor_high_heat_profile`, `reactor_disturbance_profile`
- Outcome-complete release artifact: `all_cases.json`

## Consistency checks

- All cases use `scenario_family = process_interlock`.
- All cases lower to the public process action subset `set_heater_output` / `set_cooling_valve`.
- All source references exist in the frozen local Tennessee Eastman reference acquisition target.
- All process profile references exist in the implemented scene pack.
- All label triplets satisfy the frozen label taxonomy.

## Unsafe mutation policy

- `reactor_nominal_profile` unsafe cases emphasize manipulated-variable range violation.
- `reactor_high_heat_profile` unsafe cases emphasize pressure overshoot near the thermal boundary.
- `reactor_disturbance_profile` unsafe cases emphasize disturbance-amplified pressure excursions.

## Fault mutation policy

- Integrity faults: `policy_mismatch`, `timestamp_expired`, `sensor_hash_mismatch`, `sensor_divergence`
- Transaction faults: `lock_denied`, `reverify_hash_mismatch`, `commit_timeout`, `commit_failed_recovered`
- Infrastructure faults: `ot_interface_error`

## Notes for the paper

- The Tennessee Eastman tree is used as a public process-control provenance anchor, not as a raw time-series classification benchmark.
- This release is aligned to benchmark policy version `v2026-03-20-pcag-benchmark-v1`.
- The process benchmark is intended to evaluate envelope preservation, interlock-compatible recovery, and fault-aware execution assurance through the full PCAG stack.

