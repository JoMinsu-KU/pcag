# External Source Targets

This directory reserves the local target paths for benchmark provenance
acquisition.

It exists so that future downloads, clones, and frozen reference notes use a
stable directory layout from the start.

## Reserved targets

- `robot/IsaacLab/`
- `robot/mimicgen/`
- `agv/robotic-warehouse-reference/`
- `process/tennessee-eastman-reference/`

The benchmark generation workflow should treat this directory as the only valid
local acquisition root for IJAMT source provenance.

## Important rule

Case drafting should cite the logical `source_id` from
`sources/source_provenance_manifest.json`, not ad hoc local paths.

The local path is only for reproducibility and acquisition bookkeeping.
