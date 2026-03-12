# PCAG Utility Scripts (`scripts/`)

The `scripts/` directory provides Python utilities for the lifecycle management, administration, and end-to-end testing of the PCAG microservice cluster. These scripts automate tasks that would otherwise require manual HTTP requests or complex system configurations.

## Core Scripts

1.  **Lifecycle Management**
    *   `start_services.py`: A convenience script to start all 7 PCAG microservices concurrently in the background using `subprocess`. It waits for each service's health check to pass before proceeding. Useful for local development and E2E testing.
    *   `stop_services.py`: Gracefully terminates all PCAG microservice processes started by `start_services.py`.
    *   `start_safety_cluster.py`: Specifically starts the Safety Cluster microservice, often used when developing or debugging the consensus engine.
    *   `check_services.py`: Performs HTTP GET requests against the health endpoints (`/docs` or `/health`) of all defined services to verify their operational status.

2.  **System Administration**
    *   `seed_policy.py`: The most critical setup script. It populates the PCAG Policy Store with the initial safety rules, thresholds, SIL levels, and simulation configurations for the three reference scenarios (Chemical Reactor, Robot Arm, AGV). It must be run after the services are started for the first time.

3.  **Testing and Diagnostics**
    *   `test_gateway.py`: A standalone CLI tool to send synthetic "Proof Packages" to the Gateway Core and trace the 5-stage validation pipeline. Used for rapid feedback during development.
    *   `test_isaac_sensor.py`: Validates the connection between the PCAG Sensor Gateway and a running instance of NVIDIA Isaac Sim (Scenario B).
    *   `test_logging.py`: Verifies that the centralized logging middleware is correctly capturing and formatting JSON logs across the microservices.
    *   `test_persistent_tx.py`: Tests the robustness of the Evidence Ledger by verifying that transactions persist correctly across database restarts.

## Usage

Most scripts are designed to be run from the root of the PCAG repository using the activated `pcag` conda environment.

```bash
# Start the system
conda activate pcag
python scripts/start_services.py

# Seed the initial policies (required on first run)
python scripts/seed_policy.py

# Check system health
python scripts/check_services.py

# Stop the system
python scripts/stop_services.py
```

## Related Files

*   `pcag/apps/`: The microservices managed by these scripts.
*   `config/services.yaml`: The configuration file that defines the ports and URLs used by the scripts to interact with the system.
