# Robot Source Release v4 QC

Parent release: `robot_source_release_v3`
Supplemental families: `fixture_insertion`, `conveyor_timing_pick`

## Summary

- Total cases: `120`
- Nominal: `34`
- Unsafe: `50`
- Fault: `36`
- Inherited core cases: `76`
- New supplemental cases: `44`

## Family counts

- `narrow_clearance_approach`: `28`
- `fixture_insertion`: `28`
- `conveyor_timing_pick`: `28`

## Interpretation

- v4 keeps the validated v3 robot release untouched as inherited robot coverage.
- The fixture-insertion family is expanded to the planned `8 / 12 / 8` target.
- The conveyor-timing family adds timing-window difficulty without changing the single-asset PCAG contract.
- Representative live smoke validation should be executed before treating the full v4 release as fully validated.
