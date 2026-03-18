# Plugin Backends

The `pcag/plugins/` directory contains the concrete backend implementations used by the PCAG services.
These plugins translate abstract operations such as "read the latest state", "execute this command", or "simulate this action" into actual runtime behavior.

This directory is where the repository connects platform-neutral PCAG semantics to specific field and simulation technologies.

## Plugin Families

| Family | Directory | Role |
| --- | --- | --- |
| Executors | `executor/` | Translate actuation requests into field-side execution |
| Sensors | `sensor/` | Read observable state from live or simulated sources |
| Simulation | `simulation/` | Evaluate command safety using domain-specific simulation backends |

## Executors

### [`executor/mock_executor.py`](executor/mock_executor.py)

A lightweight executor used for tests, development, and controlled experiments.

### [`executor/modbus_executor.py`](executor/modbus_executor.py)

A direct Modbus executor implementation.
It remains useful for diagnostics and debugging, but it is no longer the preferred operational path for PLC-backed assets.

### [`executor/plc_adapter_executor.py`](executor/plc_adapter_executor.py)

The recommended execution path for PLC and Modbus-backed assets.
Instead of allowing each service to open independent low-level field connections, this executor delegates writes to the centralized PLC Adapter service.

That design improves:

- connection management
- ownership semantics
- observability
- runtime stability

## Sensors

### [`sensor/isaac_sim_sensor.py`](sensor/isaac_sim_sensor.py)

Builds robot snapshots by querying the Safety Cluster's Isaac-backed simulation state.

### [`sensor/mock_sensor.py`](sensor/mock_sensor.py)

A synthetic sensor source used for tests and dataset-driven evaluation.

### [`sensor/modbus_sensor.py`](sensor/modbus_sensor.py)

A direct Modbus sensor implementation.
Like the direct Modbus executor, this is now primarily useful for fallback diagnostics and controlled debugging.

### [`sensor/plc_adapter_sensor.py`](sensor/plc_adapter_sensor.py)

The recommended path for PLC-backed live sensing.
It routes reads through the PLC Adapter instead of opening independent field connections from the Sensor Gateway itself.

## Simulation Backends

### [`simulation/ode_solver.py`](simulation/ode_solver.py)

Used for reactor and process-style scenarios where continuous dynamics are modeled through ODE integration.

### [`simulation/isaac_backend.py`](simulation/isaac_backend.py)

Used for robot-arm scenarios that rely on Isaac Sim.
This backend is tightly tied to the Safety Cluster / Isaac worker path.

### [`simulation/discrete_event.py`](simulation/discrete_event.py)

Used for AGV and logistics-style scenarios, where discrete-event modeling is more appropriate than continuous robot dynamics.

### [`simulation/none_backend.py`](simulation/none_backend.py)

A no-op backend for assets that do not require simulation.

## Current Runtime Direction

The plugin layer still contains legacy direct-connect implementations, but the current architecture prefers centralized and isolated execution paths:

- PLC and Modbus field I/O through the PLC Adapter
- robot simulation through the Safety Cluster and Isaac worker
- mock backends for controlled semantic testing and selected reference-stack execution paths

This is why the plugin directory may contain more than one valid implementation for a given class of asset.
The recommended path depends on the current system architecture, not just on whether a plugin exists.

For public readers, this means the repository should be understood as a hybrid
runtime artifact rather than a claim that every asset path is fully live-driven
in every default scenario.

## When to Edit This Directory

You will usually touch this directory when:

- adding a new field transport or sensor source
- introducing a new simulation backend
- changing how an asset is mapped to a backend
- debugging field I/O issues or simulation mismatches

## Related Documentation

- [`../README.md`](../README.md)
- [`../apps/README.md`](../apps/README.md)
- [`../core/README.md`](../core/README.md)
- [`../../config/README.md`](../../config/README.md)
