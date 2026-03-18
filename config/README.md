# Configuration Guide

The `config/` directory contains the runtime configuration files that bind the PCAG codebase to concrete services, assets, validators, and field I/O paths.

This folder is intentionally small but operationally important.
Most service-to-service URLs, asset routing decisions, and validation mappings originate here.

## Files

| File | Purpose |
| --- | --- |
| [`services.yaml`](services.yaml) | Base URLs, health probe targets, dashboard settings, and service discovery |
| [`sensor_mappings.yaml`](sensor_mappings.yaml) | Asset-to-sensor routing rules |
| [`executor_mappings.yaml`](executor_mappings.yaml) | Asset-to-executor routing rules |
| [`cbf_mappings.yaml`](cbf_mappings.yaml) | Asset-specific state mappings used by the barrier-based validator |

## Design Principles

Configuration in this repository is used for three different responsibilities:

1. **service discovery**
   - where the Gateway, Sensor Gateway, OT Interface, and Dashboard should send HTTP requests
2. **asset routing**
   - which sensor path, executor path, or simulation backend should be used for a given asset
3. **validation semantics**
   - how action parameters map into state variables and how barrier-style safety constraints should be interpreted

## `services.yaml`

[`services.yaml`](services.yaml) is the most important file in this directory.

It defines:

- the URL of each PCAG service
- which endpoint should be used for readiness probing
- dashboard refresh and aggregation settings
- shared runtime assumptions used by evaluation tooling and monitoring

### Current convention

The repository uses `127.0.0.1` instead of `localhost`.

This is intentional.
On Windows, `localhost` may resolve through IPv6 first, which can introduce avoidable connection delays when services are only listening on IPv4.

### When to restart services

Some services read `services.yaml` at startup and keep the resolved values in memory.
If you change service URLs or dashboard settings, restart the affected services before relying on the new behavior.

## `sensor_mappings.yaml`

[`sensor_mappings.yaml`](sensor_mappings.yaml) defines how each asset obtains its latest observable state.

Examples:

- `robot_arm_01` uses the Isaac-based sensor path
- PLC-backed assets are routed through the centralized PLC Adapter path
- mock sensors can still be used for controlled testing

This file tells the Sensor Gateway which source family to select, but the actual implementation is still handled in code.

## `executor_mappings.yaml`

[`executor_mappings.yaml`](executor_mappings.yaml) defines how each asset is actuated.

In the current architecture, the recommended execution path for PLC and Modbus-backed assets is the PLC Adapter.
This keeps field I/O centralized instead of allowing each service to open direct low-level connections independently.

## `cbf_mappings.yaml`

[`cbf_mappings.yaml`](cbf_mappings.yaml) connects high-level action parameters to the state representation used by the repository's barrier-based validator.

In the current implementation, this mapping feeds a static projected-state
check. It should not be interpreted as a full nonlinear control-theoretic
model on its own.

This file is especially important when:

- adding a new asset family
- extending the action vocabulary
- introducing new safety barriers or derived state terms

It is the bridge between request semantics and continuous-state safety checking.

## Practical Workflow

When adding a new asset, the usual configuration flow is:

1. add the service URLs you will rely on in [`services.yaml`](services.yaml) if needed
2. define the sensor route in [`sensor_mappings.yaml`](sensor_mappings.yaml)
3. define the executor route in [`executor_mappings.yaml`](executor_mappings.yaml)
4. define barrier-validator mappings in [`cbf_mappings.yaml`](cbf_mappings.yaml) if the asset uses that validation path
5. seed or register the corresponding policy through the Policy Admin / Policy Store path

## Related Code

- [`pcag/core/utils/config_loader.py`](../pcag/core/utils/config_loader.py)
- [`pcag/apps/sensor_gateway/routes.py`](../pcag/apps/sensor_gateway/routes.py)
- [`pcag/apps/ot_interface/executor_manager.py`](../pcag/apps/ot_interface/executor_manager.py)
- [`pcag/apps/dashboard/service.py`](../pcag/apps/dashboard/service.py)

## Recommended Reading Order

If you are new to the repository, read the files in this order:

1. [`../README.md`](../README.md)
2. [`services.yaml`](services.yaml)
3. [`sensor_mappings.yaml`](sensor_mappings.yaml)
4. [`executor_mappings.yaml`](executor_mappings.yaml)
5. [`cbf_mappings.yaml`](cbf_mappings.yaml)
