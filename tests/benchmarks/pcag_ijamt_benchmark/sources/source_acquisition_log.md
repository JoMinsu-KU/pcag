# PCAG IJAMT Source Acquisition Log

Status: initial acquisition complete  
Recorded on: `2026-03-18`

## Summary

The first source acquisition pass has been completed for all four selected
benchmark sources.

The repositories were cloned into the frozen local targets under:

- `tests/benchmarks/pcag_ijamt_benchmark/external_sources/`

## Verified acquisition results

| source_id | local target | local HEAD | result |
| --- | --- | --- | --- |
| `isaaclab_eval_industrial` | `external_sources/robot/IsaacLab` | `f4aa17f87e2e5db5484f0b5974918573e8918ce2` | acquired |
| `mimicgen_assembly` | `external_sources/robot/mimicgen` | `72bd767c255545f462e7ccfb2731f2e5d4c1d9bb` | acquired |
| `warehouse_world_curated` | `external_sources/agv/robotic-warehouse-reference` | `96fbc64e3eae5fee915e0d390f864fa06ddccd47` | acquired |
| `tep_process_curated` | `external_sources/process/tennessee-eastman-reference` | `a641419365eb292ab4f98888cdcbd7fbfbca890b` | acquired |

## Next action after acquisition

1. Inspect the robot sources and select candidate nominal task families.
2. Write AGV reference notes and scene assumptions.
3. Write process reference notes and constraint rationale.
4. Start the nominal first-batch drafting workflow.
