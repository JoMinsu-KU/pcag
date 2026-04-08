# Robot Source Release v3 QC

Parent release: `robot_source_release_v2`
Supplemental family: `fixture_insertion`
Canonical shell: `robot_fixture_insertion_cell`

## Summary

- Total cases: `76`
- Nominal: `22`
- Unsafe: `30`
- Fault: `24`
- Inherited core cases: `68`
- New supplemental cases: `8`

## Fixture-insertion family counts

- Expansion family count: `12`
- Runtime count in `robot_fixture_insertion_cell`: `12`

## Interpretation

- v3 keeps the validated v2 release untouched as inherited robot coverage.
- The first fixture-insertion supplement adds insertion depth and orientation pressure without changing the single-asset PCAG contract.
- The supplemental cases are ready for live PCAG evaluation through the existing robot runner via `--dataset-path`.

## Pending work

- This first v3 supplement is a smoke-scale family and should be live-validated before expansion to 28 cases.
