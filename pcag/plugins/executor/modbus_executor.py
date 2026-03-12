"""
Modbus Executor Plugin
======================
Executes commands on Modbus TCP devices.
Supports writing to Holding Registers (Write Single/Multiple).
"""

import time
import struct
import logging
from typing import List, Dict, Any, Union

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    ModbusTcpClient = None

from pcag.core.ports.executor import IExecutor

logger = logging.getLogger(__name__)

class ModbusExecutor(IExecutor):
    def __init__(self):
        self._client = None
        self._config = {}
        self._connected = False
        self._host = "127.0.0.1"
        self._port = 503
        self._safe_state_actions = {}  # asset_id -> list of actions

    def initialize(self, config: Dict[str, Any]) -> None:
        if ModbusTcpClient is None:
            logger.error("pymodbus not installed. Cannot use ModbusExecutor.")
            return

        self._config = config
        self._host = config.get("host", "127.0.0.1")
        self._port = config.get("port", 503)
        self._safe_state_actions = config.get("safe_state_actions", {})
        self._action_mappings = config.get("action_mappings", {})

        self._connect()

    def _connect(self) -> bool:
        if not ModbusTcpClient:
            return False

        try:
            if self._client:
                self._client.close()
            
            self._client = ModbusTcpClient(self._host, port=self._port)
            self._connected = self._client.connect()
            
            if self._connected:
                logger.info(f"ModbusExecutor connected to {self._host}:{self._port}")
            else:
                logger.warning(f"ModbusExecutor failed to connect to {self._host}:{self._port}")
            
            return self._connected
        except Exception as e:
            logger.error(f"Modbus connection error: {e}")
            self._connected = False
            return False

    def _ensure_connected(self) -> bool:
        if self._connected:
            return True
        return self._connect()

    def _translate_action(self, asset_id: str, action: dict) -> List[dict]:
        """Translate high-level action to low-level Modbus commands.
        
        Input: {"action_type": "set_heater_output", "params": {"value": 60.0}}
        Output: [{"type": "write_register", "register": 2, "value": 60}]
        """
        action_type = action.get("action_type", "")
        params = action.get("params", {})
        
        # Look up mappings for this asset and action_type
        asset_mappings = self._action_mappings.get(asset_id, {})
        type_mappings = asset_mappings.get(action_type, [])
        
        if not type_mappings:
            raise ValueError(
                f"No action_mapping found for asset={asset_id}, action_type={action_type}. "
                f"Available: {list(asset_mappings.keys())}"
            )
        
        low_level_actions = []
        for mapping in type_mappings:
            param_name = mapping["param"]      # e.g., "value"
            register = mapping["register"]      # e.g., 2
            scale = mapping.get("scale", 1.0)   # e.g., 1.0
            
            if param_name not in params:
                raise ValueError(
                    f"Action param '{param_name}' not found in params {list(params.keys())} "
                    f"for action_type={action_type}"
                )
            
            raw_value = params[param_name]
            scaled_value = int(float(raw_value) * scale)
            
            low_level_actions.append({
                "type": "write_register",
                "register": register,
                "value": scaled_value
            })
        
        return low_level_actions

    def execute(self, transaction_id: str, asset_id: str, action_sequence: List[Dict[str, Any]]) -> bool:
        """Execute action sequence by translating to Modbus writes."""
        if not self._ensure_connected():
            return False
        
        all_success = True
        for action in action_sequence:
            # If action is already low-level format (has "type" and "register"), use directly
            if "type" in action and "register" in action:
                success = self._execute_single_action(action)
            else:
                # Translate high-level action to low-level Modbus commands
                try:
                    low_level_actions = self._translate_action(asset_id, action)
                    for ll_action in low_level_actions:
                        success = self._execute_single_action(ll_action)
                        if not success:
                            all_success = False
                            break
                except ValueError as e:
                    logger.error(f"Action translation failed: {e}")
                    return False
            
            if not all_success:
                break
        
        return all_success

    def _execute_single_action(self, action: Dict[str, Any]) -> bool:
        try:
            action_type = action.get("type")
            register = action.get("register")
            
            if register is None:
                raise ValueError(f"Missing 'register' in action: {action}")

            if action_type == "write_register":
                value = action.get("value")
                if value is None:
                    raise ValueError(f"Missing 'value' in action: {action}")
                
                # Simple single register write (uint16)
                result = self._client.write_register(address=register, value=int(value))
                if result.isError():
                    raise RuntimeError(f"Modbus write error: {result}")

            elif action_type == "write_registers":
                values = action.get("values")
                if values is None:
                    # Could be a float value that needs splitting
                    value = action.get("value")
                    dtype = action.get("data_type", "uint16")
                    
                    if value is not None and dtype == "float32":
                         values = self._float32_to_registers(float(value))
                    else:
                        raise ValueError(f"Missing 'values' or 'value'/'data_type' in action: {action}")
                
                result = self._client.write_registers(address=register, values=values)
                if result.isError():
                    raise RuntimeError(f"Modbus write error: {result}")
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
            
            return True

        except Exception as e:
            logger.error(f"Action execution failed: {action}. Error: {e}")
            return False

    def safe_state(self, asset_id: str) -> bool:
        actions = self._safe_state_actions.get(asset_id)
        if not actions:
            logger.error(f"No safe state actions defined for {asset_id}")
            raise RuntimeError(f"No safe state actions defined for {asset_id}")

        logger.info(f"Executing SAFE STATE for {asset_id}")
        return self.execute(f"SAFE_STATE_{asset_id}", asset_id, actions)

    def shutdown(self) -> None:
        if self._client:
            self._client.close()
        self._connected = False
        logger.info("ModbusExecutor shutdown")

    @staticmethod
    def _float32_to_registers(value: float) -> List[int]:
        """Convert float32 to two 16-bit registers (Big Endian standard)."""
        packed = struct.pack('>f', value)
        reg1 = struct.unpack('>H', packed[0:2])[0]
        reg2 = struct.unpack('>H', packed[2:4])[0]
        return [reg1, reg2]
