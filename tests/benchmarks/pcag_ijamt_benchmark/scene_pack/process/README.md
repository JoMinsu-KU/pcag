# Process Scene Pack

This folder contains canonical process parameter profiles for the IJAMT
benchmark.

Implemented first-release profile IDs:

- `reactor_nominal_profile`
- `reactor_high_heat_profile`
- `reactor_disturbance_profile`

Each profile folder contains:

- `profile_builder.py`
- a generated process profile JSON
- `shell_config.json`

These files align with the current ODE-solver representation, including
initial process state, process parameters, and operating-envelope assumptions.

Current intended role of each profile:

- `reactor_nominal_profile`
  - baseline operating envelope preservation
  - nominal trim and manipulated-variable range violation cases
- `reactor_high_heat_profile`
  - high-heat recovery and pressure-overshoot cases
- `reactor_disturbance_profile`
  - disturbance-inspired recovery and amplified pressure-risk cases

The process benchmark runner can also visualize these profiles through the
optional persistent reactor GUI:

- `python tests/benchmarks/pcag_ijamt_benchmark/run_process_pcag_benchmark.py --case-id process_nominal_tep_envelope_heat_trim_001 --show-process-gui`

That viewer is driven by the ODE solver timeline and is meant for benchmark
debugging and paper figures, not as a separate validation path.
