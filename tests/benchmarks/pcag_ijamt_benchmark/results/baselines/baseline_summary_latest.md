# PCAG Integrated Baseline Evaluation Summary

- Generated at: 2026-03-22 03:33:03
- Dataset: `C:\Users\choiLee\Dropbox\경남대학교\AI agent 기반으로 물리 환경 제어\tests\benchmarks\pcag_ijamt_benchmark\releases\integrated_benchmark_release_v2\pcag_execution_dataset.json`
- Total cases: `368`
- Expected final status counts: `{'COMMITTED': 110, 'UNSAFE': 150, 'REJECTED': 55, 'ABORTED': 38, 'ERROR': 15}`

## Overall Comparison

| Baseline | Exact Match | Safe Pass | Unsafe Interception | Unsafe Commit | Integrity Reject | Tx Fault Non-Commit | Exec Fault Non-Commit | TOCTOU Catch | Median Latency (ms) | P95 Latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 (Direct Execution) | 0.3777 | 1.0000 | 0.0000 | 229 | 0.0000 | 0.3684 | 1.0000 | 0.0000 | 191.0200 | 203.5900 |
| B1 (Rules-only) | 0.5272 | 1.0000 | 0.0000 | 174 | 1.0000 | 0.3684 | 1.0000 | 0.0000 | 189.4200 | 199.4200 |
| B2 (Rules + Barrier) | 0.5897 | 1.0000 | 0.1533 | 151 | 1.0000 | 0.3684 | 1.0000 | 0.0000 | 5.8400 | 197.7900 |
| B3 (Rules + Simulation) | 0.9348 | 1.0000 | 1.0000 | 24 | 1.0000 | 0.3684 | 1.0000 | 0.0000 | 382.6100 | 1287.3800 |
| E1 (DT-only Gate) | 0.7853 | 1.0000 | 1.0000 | 78 | 0.0000 | 0.3684 | 1.0000 | 0.0000 | 387.9800 | 1294.1800 |
| B4 (Full Safety Without REVERIFY) | 0.8967 | 0.8545 | 1.0000 | 15 | 1.0000 | 0.6053 | 1.0000 | 0.0000 | 216.8700 | 1300.2600 |
| B5 (Full PCAG) | 1.0000 | 1.0000 | 1.0000 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 301.8600 | 1384.5600 |

## Final Status Counts

| Baseline | COMMITTED | UNSAFE | REJECTED | ABORTED | ERROR |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 | 339 | 0 | 0 | 14 | 15 |
| B1 | 284 | 0 | 55 | 14 | 15 |
| B2 | 261 | 23 | 55 | 14 | 15 |
| B3 | 134 | 150 | 55 | 14 | 15 |
| E1 | 188 | 151 | 0 | 14 | 15 |
| B4 | 109 | 150 | 55 | 46 | 8 |
| B5 | 110 | 150 | 55 | 38 | 15 |

## Asset-wise Exact Match

| Baseline | robot_arm_01 | agv_01 | reactor_01 |
| --- | ---: | ---: | ---: |
| B0 | 0.3583 | 0.3828 | 0.3917 |
| B1 | 0.5167 | 0.5312 | 0.5333 |
| B2 | 0.5167 | 0.5859 | 0.6667 |
| B3 | 0.9333 | 0.9375 | 0.9333 |
| E1 | 0.7750 | 0.7891 | 0.7917 |
| B4 | 0.9333 | 0.8906 | 0.8667 |
| B5 | 1.0000 | 1.0000 | 1.0000 |

## Notes

- This summary aggregates only observed results from the live evaluation outputs in `results/baselines` and the live `integrated_pcag_benchmark_latest.json` file.
- No dataset mutation, label rewriting, mock data injection, or baseline-specific hard-coded case overrides were applied during aggregation.
