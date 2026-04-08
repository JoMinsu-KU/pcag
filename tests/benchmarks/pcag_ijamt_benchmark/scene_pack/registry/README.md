# Scene Registry

This folder will contain the frozen scene/profile registry for the IJAMT
benchmark.

Each benchmark case should eventually reference a canonical runtime artifact via
registry-controlled identifiers such as:

- `scene_id`
- `map_id`
- `profile_id`

The registry will later map those identifiers to:

- local runtime file paths
- runtime types (`usd`, `map_config`, `process_profile`)
- source-family alignment notes
