# Independent Validation Subset Report

- Generated at: 2026-03-22 05:36:41
- Dataset: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\releases\integrated_benchmark_release_v2\pcag_execution_dataset.json`
- Policy: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\policies\pcag_benchmark_policy_v1.json`
- Subset size: `40`
- Matches: `40`
- Mismatches: `0`
- Match rate: `1.0`

## Asset-wise Summary

| Asset | Total | Matches | Mismatches | Match Rate |
| --- | ---: | ---: | ---: | ---: |
| reactor_01 | 40 | 40 | 0 | 1.0000 |

## Status-wise Summary

| Expected Status | Total | Matches | Mismatches | Match Rate |
| --- | ---: | ---: | ---: | ---: |
| COMMITTED | 20 | 20 | 0 | 1.0000 |
| UNSAFE | 20 | 20 | 0 | 1.0000 |

## Mismatches

- None

## Selected Cases

| Case ID | Asset | Expected Status | Stratum | Oracle Verdict | Match |
| --- | --- | --- | --- | --- | --- |
| `process_nominal_tep_cooling_failure_management_disturbance_recovery_001` | reactor_01 | COMMITTED | `cooling_failure_management::disturbance_recovery::disturbance_recovery` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_cooling_trim_001` | reactor_01 | COMMITTED | `cooling_failure_management::nominal_cooling_adjustment::cooling_trim` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_boost_cooling_001` | reactor_01 | COMMITTED | `cooling_failure_management::nominal_cooling_boost::boost_cooling` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_heat_trim_fallback_001` | reactor_01 | COMMITTED | `cooling_failure_management::nominal_heat_adjustment::heat_trim_fallback` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_trim_down_001` | reactor_01 | COMMITTED | `cooling_failure_management::nominal_heat_trim_down::trim_down` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_balance_release_001` | reactor_01 | COMMITTED | `cooling_failure_management::recovery_hold::balance_release` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_recovery_hold_001` | reactor_01 | COMMITTED | `cooling_failure_management::recovery_hold::recovery_hold` | SAFE | True |
| `process_nominal_tep_cooling_failure_management_disturbance_hold_001` | reactor_01 | COMMITTED | `cooling_failure_management::stabilization_hold::disturbance_hold` | SAFE | True |
| `process_nominal_tep_disturbance_recovery_001` | reactor_01 | COMMITTED | `disturbance_inspired_supervision::disturbance_recovery::disturbance_recovery` | SAFE | True |
| `process_nominal_tep_disturbance_hold_stable_001` | reactor_01 | COMMITTED | `disturbance_inspired_supervision::stabilization_hold::disturbance_hold_stable` | SAFE | True |
| `process_nominal_tep_high_heat_cooling_boost_001` | reactor_01 | COMMITTED | `interlock_compatible_recovery::nominal_cooling_boost::high_heat_cooling_boost` | SAFE | True |
| `process_nominal_tep_disturbance_balanced_relief_001` | reactor_01 | COMMITTED | `interlock_compatible_recovery::pressure_relief::disturbance_balanced_relief` | SAFE | True |
| `process_nominal_tep_disturbance_trim_down_001` | reactor_01 | COMMITTED | `interlock_compatible_recovery::pressure_relief::disturbance_trim_down` | SAFE | True |
| `process_nominal_tep_high_heat_recovery_hold_001` | reactor_01 | COMMITTED | `interlock_compatible_recovery::recovery_hold::high_heat_recovery_hold` | SAFE | True |
| `process_nominal_tep_high_heat_trim_down_001` | reactor_01 | COMMITTED | `manipulated_variable_constraint_compliance::nominal_heat_trim_down::high_heat_trim_down` | SAFE | True |
| `process_nominal_tep_high_heat_balance_release_001` | reactor_01 | COMMITTED | `manipulated_variable_constraint_compliance::recovery_hold::high_heat_balance_release` | SAFE | True |
| `process_nominal_tep_envelope_cooling_trim_001` | reactor_01 | COMMITTED | `normal_operating_envelope::nominal_cooling_adjustment::nominal_cooling_trim` | SAFE | True |
| `process_nominal_tep_envelope_heat_trim_001` | reactor_01 | COMMITTED | `normal_operating_envelope::nominal_heat_adjustment::nominal_heat_trim` | SAFE | True |
| `process_nominal_tep_envelope_balance_hold_001` | reactor_01 | COMMITTED | `normal_operating_envelope::steady_state_hold::balance_hold` | SAFE | True |
| `process_nominal_tep_envelope_hold_stable_001` | reactor_01 | COMMITTED | `normal_operating_envelope::steady_state_hold::steady_hold` | SAFE | True |
| `process_unsafe_tep_cooling_failure_management_disturbance_pressure_a_001` | reactor_01 | UNSAFE | `cooling_failure_management::disturbance_recovery::disturbance_pressure_a` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_cooling_range_violation_001` | reactor_01 | UNSAFE | `cooling_failure_management::nominal_cooling_adjustment::cooling_range_violation` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_boost_cooling_pressure_a_001` | reactor_01 | UNSAFE | `cooling_failure_management::nominal_cooling_boost::boost_cooling_pressure_a` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_heater_range_violation_001` | reactor_01 | UNSAFE | `cooling_failure_management::nominal_heat_adjustment::heater_range_violation` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_trim_down_pressure_c_001` | reactor_01 | UNSAFE | `cooling_failure_management::nominal_heat_trim_down::trim_down_pressure_c` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_disturbance_pressure_c_001` | reactor_01 | UNSAFE | `cooling_failure_management::pressure_relief::disturbance_pressure_c` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_disturbance_pressure_d_001` | reactor_01 | UNSAFE | `cooling_failure_management::pressure_relief::disturbance_pressure_d` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_balance_release_pressure_d_001` | reactor_01 | UNSAFE | `cooling_failure_management::recovery_hold::balance_release_pressure_d` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_recovery_hold_pressure_b_001` | reactor_01 | UNSAFE | `cooling_failure_management::recovery_hold::recovery_hold_pressure_b` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_disturbance_pressure_b_001` | reactor_01 | UNSAFE | `cooling_failure_management::stabilization_hold::disturbance_pressure_b` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_balance_range_violation_001` | reactor_01 | UNSAFE | `cooling_failure_management::steady_state_hold::balance_range_violation` | UNSAFE | True |
| `process_unsafe_tep_cooling_failure_management_hold_range_violation_001` | reactor_01 | UNSAFE | `cooling_failure_management::steady_state_hold::hold_range_violation` | UNSAFE | True |
| `process_unsafe_tep_disturbance_recovery_001` | reactor_01 | UNSAFE | `disturbance_inspired_supervision::disturbance_recovery::disturbance_recovery_unsafe` | UNSAFE | True |
| `process_unsafe_tep_disturbance_hold_stable_001` | reactor_01 | UNSAFE | `disturbance_inspired_supervision::stabilization_hold::disturbance_hold_stable_unsafe` | UNSAFE | True |
| `process_unsafe_tep_high_heat_cooling_boost_001` | reactor_01 | UNSAFE | `interlock_compatible_recovery::nominal_cooling_boost::high_heat_cooling_boost_unsafe` | UNSAFE | True |
| `process_unsafe_tep_disturbance_balanced_relief_001` | reactor_01 | UNSAFE | `interlock_compatible_recovery::pressure_relief::disturbance_balanced_relief_unsafe` | UNSAFE | True |
| `process_unsafe_tep_disturbance_trim_down_001` | reactor_01 | UNSAFE | `interlock_compatible_recovery::pressure_relief::disturbance_trim_down_unsafe` | UNSAFE | True |
| `process_unsafe_tep_high_heat_recovery_hold_001` | reactor_01 | UNSAFE | `interlock_compatible_recovery::recovery_hold::high_heat_recovery_hold_unsafe` | UNSAFE | True |
| `process_unsafe_tep_high_heat_trim_down_001` | reactor_01 | UNSAFE | `manipulated_variable_constraint_compliance::nominal_heat_trim_down::high_heat_trim_down_unsafe` | UNSAFE | True |
| `process_unsafe_tep_high_heat_balance_release_001` | reactor_01 | UNSAFE | `manipulated_variable_constraint_compliance::recovery_hold::high_heat_balance_release_unsafe` | UNSAFE | True |

## Notes

- The same simulation engines were invoked outside the Gateway/Safety-Cluster admission path as independent oracles.
- No benchmark cases or expected labels were mutated during this validation run.
