# Robot Source Targets

The robot-manipulation benchmark family uses downloadable public sources.

## Reserved local targets

- `IsaacLab/`
  - expected source: `isaaclab_eval_industrial`
  - upstream: `https://github.com/isaac-sim/IsaacLab.git`
- `mimicgen/`
  - expected source: `mimicgen_assembly`
  - upstream: `https://github.com/NVlabs/mimicgen.git`

## Acquisition note

These directories are intentionally created as frozen targets before any real
download begins.

This prevents later benchmark drafts from mixing:

- one-off local clone paths
- user-specific download folders
- inconsistent source identifiers

When the actual acquisition starts, these targets should be populated without
changing the source IDs recorded in `sources/source_provenance_manifest.*`.
