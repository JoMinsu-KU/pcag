# PCAG Configuration (`config/`)

The `config/` directory contains YAML files that define the static configuration and mappings for the PCAG system. These files are loaded at service startup and dictate how microservices communicate, which plugins to use for specific assets, and the mathematical constraints (CBFs) applied to them.

## Configuration Files

### 1. `services.yaml`
The central registry for all PCAG microservices. It defines the URLs, ports, and execution modes for each component.
*   **Key Settings:** `url` for inter-service communication, logging levels, and whether a service is enabled.
*   **Consumers:** Gateway Core, Admin scripts, and inter-service HTTP clients.

### 2. `cbf_mappings.yaml`
Maps physical assets to their respective Control Barrier Function (CBF) implementations. CBFs provide mathematical guarantees of safety.
*   **Key Settings:** The mathematical function definition or the specific Python class implementation to use for evaluating the asset's safety boundary ($h(x) \ge 0$).
*   **Consumers:** Safety Cluster (CBF Validator).

### 3. `executor_mappings.yaml`
Maps physical assets to the OT execution plugins responsible for translating PCAG commands into hardware-specific protocols (e.g., Modbus, ROS, Mock).
*   **Key Settings:** The name of the executor plugin (from `pcag/plugins/executor/`) to use for a given `asset_id`.
*   **Consumers:** OT Interface.

### 4. `sensor_mappings.yaml`
Maps physical assets to the sensor plugins responsible for retrieving real-time data snapshots.
*   **Key Settings:** The name of the sensor plugin (from `pcag/plugins/sensor/`) to use for a given `asset_id`.
*   **Consumers:** Sensor Gateway.

## Usage

These configurations are designed to be modified without recompiling the core code, allowing operators to seamlessly add new assets, change simulation backends, or re-route service communications.

Changes to these files typically require a restart of the affected microservices.

## Related Files
*   `pcag/core/utils/config_loader.py`: The utility used to parse and validate these YAML files at runtime.
*   `pcag/plugins/`: The actual implementations referenced in the mapping files.
