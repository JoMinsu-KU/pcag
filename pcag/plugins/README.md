# PCAG Plugins (`plugins/`)

The `pcag/plugins/` directory provides concrete implementations of the abstract interfaces (ports) defined in `pcag/core/ports/`. This pluggable architecture allows PCAG to connect to a wide variety of physical assets, sensors, and simulation environments without modifying the core gateway logic.

## Plugin Categories

The plugins are categorized based on their function within the PCAG pipeline:

1.  **`executor/`**: Implements the `OTExecutorPort`. These plugins translate abstract control commands (e.g., "move_joint") into protocol-specific instructions for physical controllers.
    *   `mock_executor.py`: A software mock for testing and demonstration.
    *   `modbus_executor.py`: Translates commands into Modbus TCP packets for PLCs.

2.  **`sensor/`**: Implements the `SensorSourcePort`. These plugins retrieve real-time data from physical or simulated sensors to build the "Sensor Snapshot" used in Integrity and Safety checks.
    *   `isaac_sim_sensor.py`: Retrieves joint states and simulated sensor data from NVIDIA Isaac Sim.
    *   `mock_sensor.py`: Generates synthetic sensor data for testing.
    *   `modbus_sensor.py`: Reads registers from a Modbus PLC.

3.  **`simulation/`**: Implements the `SimulationBackendPort`. These plugins execute predictive simulations to verify the safety of proposed actions before they are executed on the real asset.
    *   `discrete_event.py`: A fast, grid-based simulator for AGVs (Scenario C).
    *   `isaac_backend.py`: A high-fidelity physics simulator using NVIDIA Isaac Sim (Scenario B).
    *   `none_backend.py`: A passthrough simulator for assets that do not require predictive simulation.
    *   `ode_solver.py`: A continuous-time solver for chemical reactors (Scenario A).

## Extensibility

To add support for a new asset type (e.g., a ROS 2 robot or an OPC UA server), you simply create new plugin classes that implement the corresponding ports. PCAG uses the configuration files in `config/` (e.g., `executor_mappings.yaml`, `sensor_mappings.yaml`) to dynamically load and route requests to the appropriate plugin for each `asset_id`.

## Usage

Plugins are typically instantiated by the microservices (e.g., `ot_interface`, `sensor_gateway`, `safety_cluster`) during startup based on the system configuration.

```python
# Example: Configuration mapping an asset to a plugin
# config/executor_mappings.yaml
reactor_01: "modbus_executor"
robot_arm_01: "mock_executor"
```

## Related Files

*   `pcag/core/ports/`: The abstract interfaces defining the required methods for plugins.
*   `config/`: YAML files that map assets to specific plugin implementations.
