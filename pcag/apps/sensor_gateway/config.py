import os
from typing import Dict, List
from pcag.core.ports.sensor_source import SensorConfig

# Configuration for the Sensor Gateway

# Default to Mock if not specified
SENSOR_SOURCE_TYPE = os.getenv("SENSOR_SOURCE_TYPE", "mock").lower()

# Modbus Configuration
MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Sensor Mapping: Asset ID -> List of SensorConfigs
# This defines what sensors are available for each asset and how to read them.
SENSOR_MAPPING: Dict[str, List[SensorConfig]] = {
    "reactor_01": [
        SensorConfig(
            sensor_id="temperature",
            sensor_type="temperature",
            address="holding:0:float32", # Example Modbus address
            protocol="modbus",
            interval=1.0
        ),
        SensorConfig(
            sensor_id="pressure",
            sensor_type="pressure",
            address="holding:2:float32",
            protocol="modbus",
            interval=1.0
        ),
        SensorConfig(
            sensor_id="heater_output",
            sensor_type="power",
            address="holding:4:float32",
            protocol="modbus",
            interval=1.0
        ),
        SensorConfig(
            sensor_id="cooling_valve",
            sensor_type="valve",
            address="holding:6:float32",
            protocol="modbus",
            interval=1.0
        )
    ]
}

def get_sensor_config(asset_id: str) -> List[SensorConfig]:
    return SENSOR_MAPPING.get(asset_id, [])
