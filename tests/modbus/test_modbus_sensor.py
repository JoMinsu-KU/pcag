"""
PCAG Modbus Sensor Gateway Test
=================================
Tests the modbus_sensor plugin pattern with ModRSsim2.

Prerequisites:
  1. Start ModRSsim2 (Modbus TCP simulator) on localhost:503
  2. pip install pymodbus

Run:
  python tests/modbus/test_modbus_sensor.py

This test simulates PCAG's Sensor Gateway (210) reading from a PLC/ModRSsim2:
  ModRSsim2 (Register) --> modbus_sensor plugin --> SensorSnapshot --> Hash
"""

import sys
import struct
import time
import os

# Add project root to path for PCAG imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("Installing pymodbus...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymodbus"])
    from pymodbus.client import ModbusTcpClient

from pcag.core.utils.canonicalize import canonicalize
from pcag.core.utils.hash_utils import compute_sensor_hash


# ============================================================
# Sensor Mapping Config (simulates config/mappings/sensor_mapping_reactor_01.yaml)
# ============================================================
SENSOR_MAPPING = {
    "asset_id": "reactor_01",
    "source_plugin": "modbus_sensor",
    "connection": {
        "host": "127.0.0.1",
        "port": 503,
    },
    "mappings": [
        {
            "snapshot_field": "temperature",
            "register_address": 0,     # Holding register 40001 (0-indexed)
            "register_count": 2,       # float32 = 2 registers
            "data_type": "float32",
            "unit": "celsius",
        },
        {
            "snapshot_field": "pressure",
            "register_address": 2,     # Holding register 40003
            "register_count": 2,
            "data_type": "float32",
            "unit": "bar",
        },
        {
            "snapshot_field": "heater_output",
            "register_address": 4,     # Holding register 40005
            "register_count": 1,
            "data_type": "uint16",
            "unit": "percent",
            "scale": 0.1,             # Raw 800 -> 80.0%
        },
        {
            "snapshot_field": "cooling_valve",
            "register_address": 5,     # Holding register 40006
            "register_count": 1,
            "data_type": "uint16",
            "unit": "percent",
            "scale": 0.1,
        },
        {
            "snapshot_field": "reactor_status",
            "register_address": 6,     # Holding register 40007
            "register_count": 1,
            "data_type": "uint16",
            "unit": "enum",           # 0=idle, 1=heating, 2=cooling, 3=alarm
        },
    ]
}


# ============================================================
# Helper: Encode/Decode float32 for Modbus registers
# ============================================================
def float32_to_registers(value):
    """Convert float32 to two 16-bit Modbus registers (big-endian)."""
    packed = struct.pack('>f', value)
    reg1 = struct.unpack('>H', packed[0:2])[0]
    reg2 = struct.unpack('>H', packed[2:4])[0]
    return [reg1, reg2]

def registers_to_float32(reg1, reg2):
    """Convert two 16-bit Modbus registers to float32 (big-endian)."""
    packed = struct.pack('>HH', reg1, reg2)
    return struct.unpack('>f', packed)[0]


# ============================================================
# Simulated modbus_sensor Plugin
# ============================================================
class ModbusSensorPlugin:
    """
    Simulates PCAG's ISensorSource implementation for Modbus.
    Reads from ModRSsim2 and creates SensorSnapshot.
    """
    
    def __init__(self, mapping_config):
        self.config = mapping_config
        self.client = None
    
    def connect(self):
        conn = self.config["connection"]
        self.client = ModbusTcpClient(conn["host"], port=conn["port"])
        connected = self.client.connect()
        return connected
    
    def disconnect(self):
        if self.client:
            self.client.close()
    
    def read_snapshot(self):
        """Read all mapped registers and build SensorSnapshot."""
        if not self.client or not self.client.is_socket_open():
            raise ConnectionError("Not connected to Modbus server")
        
        snapshot = {}
        
        for mapping in self.config["mappings"]:
            field = mapping["snapshot_field"]
            addr = mapping["register_address"]
            count = mapping["register_count"]
            dtype = mapping["data_type"]
            
            # Read holding registers
            result = self.client.read_holding_registers(address=addr, count=count)
            
            if result.isError():
                raise IOError(f"Failed to read register {addr}: {result}")
            
            # Decode based on data type
            if dtype == "float32" and count == 2:
                value = registers_to_float32(result.registers[0], result.registers[1])
                value = round(value, 3)  # PCAG canonicalization precision
            elif dtype == "uint16":
                value = result.registers[0]
                if "scale" in mapping:
                    value = round(value * mapping["scale"], 3)
            else:
                value = result.registers[0]
            
            snapshot[field] = value
        
        return snapshot
    
    def get_sensor_snapshot(self):
        """Full PCAG SensorSnapshot with metadata."""
        sensor_data = self.read_snapshot()
        timestamp_ms = int(time.time() * 1000)
        snapshot_hash = compute_sensor_hash(sensor_data)
        
        return {
            "asset_id": self.config["asset_id"],
            "snapshot_id": f"snap_{timestamp_ms}",
            "timestamp_ms": timestamp_ms,
            "sensor_snapshot": sensor_data,
            "sensor_snapshot_hash": snapshot_hash,
            "sensor_reliability_index": 0.95,
        }


# ============================================================
# Tests
# ============================================================
def main():
    print("=" * 70)
    print("PCAG Modbus Sensor Gateway Test (ModRSsim2)")
    print("=" * 70)
    
    results = []
    plugin = ModbusSensorPlugin(SENSOR_MAPPING)
    
    # ----------------------------------------------------------
    # TEST 1: Connection
    # ----------------------------------------------------------
    print("\n[TEST 1] Modbus TCP Connection")
    print("-" * 40)
    
    try:
        connected = plugin.connect()
        if connected:
            print("  Connected to ModRSsim2 at 127.0.0.1:503")
            print("  Result: [PASS]")
            results.append(("Modbus TCP Connection", True))
        else:
            print("  Failed to connect. Is ModRSsim2 running?")
            print("  Result: [FAIL]")
            results.append(("Modbus TCP Connection", False))
            return
    except Exception as e:
        print(f"  Connection error: {e}")
        print("  Make sure ModRSsim2 is running on localhost:503")
        print("  Result: [FAIL]")
        results.append(("Modbus TCP Connection", False))
        return
    
    # ----------------------------------------------------------
    # TEST 2: Write test values to registers
    # ----------------------------------------------------------
    print("\n[TEST 2] Write Test Values to Registers")
    print("-" * 40)
    
    try:
        # Write temperature = 150.5 (float32) to registers 0-1
        temp_regs = float32_to_registers(150.5)
        plugin.client.write_registers(address=0, values=temp_regs)
        print(f"  Written: temperature = 150.5 C -> registers [0,1] = {temp_regs}")
        
        # Write pressure = 1.25 (float32) to registers 2-3
        press_regs = float32_to_registers(1.25)
        plugin.client.write_registers(address=2, values=press_regs)
        print(f"  Written: pressure = 1.25 bar -> registers [2,3] = {press_regs}")
        
        # Write heater_output = 800 (uint16, scale 0.1 -> 80.0%) to register 4
        plugin.client.write_register(address=4, value=800)
        print(f"  Written: heater_output = 800 (80.0%) -> register [4]")
        
        # Write cooling_valve = 500 (uint16, scale 0.1 -> 50.0%) to register 5
        plugin.client.write_register(address=5, value=500)
        print(f"  Written: cooling_valve = 500 (50.0%) -> register [5]")
        
        # Write reactor_status = 1 (heating) to register 6
        plugin.client.write_register(address=6, value=1)
        print(f"  Written: reactor_status = 1 (heating) -> register [6]")
        
        print("  Result: [PASS]")
        results.append(("Write Test Values", True))
    except Exception as e:
        print(f"  Write error: {e}")
        print("  Result: [FAIL]")
        results.append(("Write Test Values", False))
    
    # ----------------------------------------------------------
    # TEST 3: Read values and build SensorSnapshot
    # ----------------------------------------------------------
    print("\n[TEST 3] Read Sensor Data & Build SensorSnapshot")
    print("-" * 40)
    
    try:
        snapshot_data = plugin.read_snapshot()
        print(f"  Raw snapshot: {snapshot_data}")
        
        # Verify values
        assert abs(snapshot_data["temperature"] - 150.5) < 0.01, f"Temperature mismatch: {snapshot_data['temperature']}"
        assert abs(snapshot_data["pressure"] - 1.25) < 0.01, f"Pressure mismatch: {snapshot_data['pressure']}"
        assert abs(snapshot_data["heater_output"] - 80.0) < 0.1, f"Heater mismatch: {snapshot_data['heater_output']}"
        assert abs(snapshot_data["cooling_valve"] - 50.0) < 0.1, f"Valve mismatch: {snapshot_data['cooling_valve']}"
        assert snapshot_data["reactor_status"] == 1, f"Status mismatch: {snapshot_data['reactor_status']}"
        
        print("  Verified: All values match written data")
        print("  Result: [PASS]")
        results.append(("Read & Verify Sensor Data", True))
    except Exception as e:
        print(f"  Error: {e}")
        print("  Result: [FAIL]")
        results.append(("Read & Verify Sensor Data", False))
    
    # ----------------------------------------------------------
    # TEST 4: Full SensorSnapshot with metadata + hash
    # ----------------------------------------------------------
    print("\n[TEST 4] Full SensorSnapshot with Hash")
    print("-" * 40)
    
    try:
        full_snapshot = plugin.get_sensor_snapshot()
        
        print(f"  asset_id: {full_snapshot['asset_id']}")
        print(f"  snapshot_id: {full_snapshot['snapshot_id']}")
        print(f"  timestamp_ms: {full_snapshot['timestamp_ms']}")
        print(f"  sensor_data: {full_snapshot['sensor_snapshot']}")
        print(f"  hash: {full_snapshot['sensor_snapshot_hash']}")
        print(f"  reliability: {full_snapshot['sensor_reliability_index']}")
        
        assert full_snapshot["asset_id"] == "reactor_01"
        assert len(full_snapshot["sensor_snapshot_hash"]) == 64  # SHA-256 hex
        assert full_snapshot["sensor_reliability_index"] == 0.95
        
        print("  Result: [PASS]")
        results.append(("Full SensorSnapshot", True))
    except Exception as e:
        print(f"  Error: {e}")
        print("  Result: [FAIL]")
        results.append(("Full SensorSnapshot", False))
    
    # ----------------------------------------------------------
    # TEST 5: Hash consistency (same data -> same hash)
    # ----------------------------------------------------------
    print("\n[TEST 5] Hash Consistency")
    print("-" * 40)
    
    try:
        snapshot1 = plugin.read_snapshot()
        hash1 = compute_sensor_hash(snapshot1)
        
        time.sleep(0.1)
        
        snapshot2 = plugin.read_snapshot()
        hash2 = compute_sensor_hash(snapshot2)
        
        print(f"  Hash 1: {hash1}")
        print(f"  Hash 2: {hash2}")
        print(f"  Match: {hash1 == hash2}")
        
        # Same register values -> same hash
        assert hash1 == hash2, "Hashes should match for identical data"
        print("  Result: [PASS]")
        results.append(("Hash Consistency", True))
    except Exception as e:
        print(f"  Error: {e}")
        print("  Result: [FAIL]")
        results.append(("Hash Consistency", False))
    
    # ----------------------------------------------------------
    # TEST 6: Sensor change detection (PCAG Integrity Check pattern)
    # ----------------------------------------------------------
    print("\n[TEST 6] Sensor Change Detection")
    print("-" * 40)
    
    try:
        # Read baseline
        baseline = plugin.read_snapshot()
        baseline_hash = compute_sensor_hash(baseline)
        print(f"  Baseline: temp={baseline['temperature']}, hash={baseline_hash[:16]}...")
        
        # Simulate sensor change: temperature goes up
        new_temp_regs = float32_to_registers(155.0)
        plugin.client.write_registers(address=0, values=new_temp_regs)
        
        # Read again
        changed = plugin.read_snapshot()
        changed_hash = compute_sensor_hash(changed)
        print(f"  Changed:  temp={changed['temperature']}, hash={changed_hash[:16]}...")
        
        # Hashes should differ
        hashes_differ = baseline_hash != changed_hash
        temp_changed = abs(changed["temperature"] - 155.0) < 0.01
        
        print(f"  Temperature changed: {temp_changed}")
        print(f"  Hash differs: {hashes_differ}")
        
        assert hashes_differ, "Hash should change when sensor data changes"
        assert temp_changed, "Temperature should be updated"
        
        # Compute divergence (PCAG Integrity Check pattern)
        divergence = abs(changed["temperature"] - baseline["temperature"])
        threshold = 2.0  # PCAG default: 2.0 degrees
        
        print(f"  Divergence: {divergence:.1f} C (threshold: {threshold} C)")
        if divergence > threshold:
            print(f"  -> INTEGRITY_SENSOR_DIVERGENCE (divergence {divergence:.1f} > threshold {threshold})")
        else:
            print(f"  -> Within threshold")
        
        print("  Result: [PASS]")
        results.append(("Sensor Change Detection", True))
    except Exception as e:
        print(f"  Error: {e}")
        print("  Result: [FAIL]")
        results.append(("Sensor Change Detection", False))
    
    # ----------------------------------------------------------
    # TEST 7: Canonicalization consistency
    # ----------------------------------------------------------
    print("\n[TEST 7] Canonical Form Verification")
    print("-" * 40)
    
    try:
        snapshot = plugin.read_snapshot()
        canonical = canonicalize(snapshot)
        print(f"  Canonical: {canonical}")
        
        # Verify it's valid canonical form
        assert '"' in canonical  # Has JSON quotes
        assert ' ' not in canonical.replace('" "', '')  # No extra whitespace (rough check)
        
        # Verify key ordering
        keys = list(snapshot.keys())
        sorted_keys = sorted(keys)
        # In canonical form, keys should appear in sorted order
        for i in range(len(sorted_keys) - 1):
            pos_current = canonical.find(f'"{sorted_keys[i]}"')
            pos_next = canonical.find(f'"{sorted_keys[i+1]}"')
            assert pos_current < pos_next, f"Keys not sorted: {sorted_keys[i]} should come before {sorted_keys[i+1]}"
        
        print("  Keys are sorted lexicographically: [OK]")
        print("  Result: [PASS]")
        results.append(("Canonical Form", True))
    except Exception as e:
        print(f"  Error: {e}")
        print("  Result: [FAIL]")
        results.append(("Canonical Form", False))
    
    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------
    plugin.disconnect()
    
    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    for name, r in results:
        print(f"  {'[PASS]' if r else '[FAIL]'} {name}")
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\nModbus Sensor Gateway pattern verified!")
        print("PCAG can read sensor data from ModRSsim2/PLC via Modbus TCP.")

if __name__ == "__main__":
    main()
