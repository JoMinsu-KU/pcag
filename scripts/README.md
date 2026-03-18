# Operational Scripts

The `scripts/` directory contains helper commands for starting services, checking runtime health, seeding policies, and running focused diagnostics.

These scripts are the fastest way to bring the stack up locally without manually invoking each service one by one.

## Main Scripts

## Startup and shutdown

### [`start_services.py`](start_services.py)

Starts the services that run in the `pcag` environment:

- Gateway
- Policy Store
- Sensor Gateway
- OT Interface
- Evidence Ledger
- Policy Admin
- PLC Adapter
- Dashboard

### [`stop_services.py`](stop_services.py)

Stops the processes launched by [`start_services.py`](start_services.py).

### [`start_safety_cluster.py`](start_safety_cluster.py)

Starts the Safety Cluster in the `pcag-isaac` environment.
This must be run separately because Isaac Sim has different runtime constraints from the rest of the stack.

### [`check_services.py`](check_services.py)

Performs lightweight health probing for the registered services.
This is useful immediately after startup or before running live E2E evaluation.

## Policy and setup

### [`seed_policy.py`](seed_policy.py)

Registers the baseline policy versions and asset profiles used by the reference scenarios.
This includes the reactor, robot arm, and AGV assets used throughout the repository.
The seeded metadata reflects the current public reference stack, including the
hybrid combination of live PLC paths, Isaac-backed sensing, and explicitly
mock-backed execution where appropriate.

## Diagnostics and targeted checks

### [`test_gateway.py`](test_gateway.py)

Sends synthetic requests to the Gateway for quick end-to-end sanity checks.

### [`test_isaac_sensor.py`](test_isaac_sensor.py)

Checks whether the Sensor Gateway can retrieve Isaac-backed robot state correctly.

### [`test_logging.py`](test_logging.py)

Exercises the logging stack and helps verify formatting and middleware behavior.

### [`test_persistent_tx.py`](test_persistent_tx.py)

Useful for checking transaction persistence and evidence behavior in development.

## Recommended Startup Order

```powershell
conda activate pcag-isaac
python scripts/start_safety_cluster.py

conda activate pcag
python scripts/start_services.py
python scripts/seed_policy.py
python scripts/check_services.py
```

## Operational Notes

- The Safety Cluster is not launched from the same environment as the rest of the services.
- After changing files in [`config/`](../config/README.md), restart the services that consume those settings.
- The live E2E tooling and the dashboard assume service URLs are configured with `127.0.0.1`.

## Best Companions

These scripts are usually used together with:

- [`../README.md`](../README.md)
- [`../tests/README.md`](../tests/README.md)
- [`../config/README.md`](../config/README.md)
