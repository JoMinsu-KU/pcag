# Robot Source Release v2 QC

Parent release: `robot_source_release_v1`
Supplemental family: `narrow_clearance_approach`
Canonical shell: `robot_narrow_clearance_cell`

## Summary

- Total cases: `64`
- Nominal: `18`
- Unsafe: `26`
- Fault: `20`
- Inherited core cases: `44`
- New supplemental cases: `20`

## Narrow-clearance family counts

- Expansion family count: `28`
- Runtime count in `robot_narrow_clearance_cell`: `28`

## Interpretation

- v2 keeps the validated v1 release untouched as inherited core coverage.
- The first phase-A robot expansion family adds tighter fixture geometry without changing the single-asset PCAG contract.
- The supplemental cases are exercised through the existing robot runner via `--dataset-path`.
- The full 28-case narrow-clearance family has already been exercised on the live PCAG stack.

## Next work

- `fixture_insertion` and `conveyor_timing_pick` remain planned robot families for later v2.x expansion.
