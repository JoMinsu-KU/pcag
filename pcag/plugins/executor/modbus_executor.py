"""
Modbus Executor Plugin
======================
Executes commands on Modbus TCP devices.
Supports writing to Holding Registers (Write Single/Multiple).
"""

import struct
import logging
import threading
from typing import List, Dict, Any

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
        self.last_error: str | None = None

    def initialize(self, config: Dict[str, Any]) -> None:
        if ModbusTcpClient is None:
            logger.error("pymodbus not installed. Cannot use ModbusExecutor.")
            self.last_error = "pymodbus not installed"
            return

        self._config = config
        self._host = config.get("host", "127.0.0.1")
        self._port = config.get("port", 503)
        self._safe_state_actions = config.get("safe_state_actions", {})
        self._action_mappings = config.get("action_mappings", {})

        logger.info(
            "ModbusExecutor initialize | executor_id=%s host=%s port=%s mapped_assets=%s safe_state_assets=%s",
            id(self),
            self._host,
            self._port,
            sorted(self._action_mappings.keys()),
            sorted(self._safe_state_actions.keys()),
        )

        self._connect()

    def _connect(self) -> bool:
        if not ModbusTcpClient:
            self.last_error = "pymodbus not installed"
            return False

        try:
            if self._client:
                logger.info(
                    "ModbusExecutor reconnect requested | executor_id=%s old_client_id=%s host=%s port=%s",
                    id(self),
                    id(self._client),
                    self._host,
                    self._port,
                )
                self._client.close()

            self._client = ModbusTcpClient(self._host, port=self._port)
            logger.info(
                "ModbusExecutor connect attempt | executor_id=%s client_id=%s host=%s port=%s thread=%s",
                id(self),
                id(self._client),
                self._host,
                self._port,
                threading.get_ident(),
            )
            self._connected = self._client.connect()

            if self._connected:
                logger.info(
                    "ModbusExecutor connected | executor_id=%s client_id=%s host=%s port=%s",
                    id(self),
                    id(self._client),
                    self._host,
                    self._port,
                )
                self.last_error = None
            else:
                logger.warning(
                    "ModbusExecutor connect failed | executor_id=%s client_id=%s host=%s port=%s",
                    id(self),
                    id(self._client),
                    self._host,
                    self._port,
                )
                self.last_error = f"Failed to connect to {self._host}:{self._port}"

            return self._connected
        except Exception as e:
            logger.error(
                "ModbusExecutor connection error | executor_id=%s host=%s port=%s error=%s",
                id(self),
                self._host,
                self._port,
                e,
                exc_info=True,
            )
            self._connected = False
            self.last_error = str(e)
            return False

    def _ensure_connected(self) -> bool:
        if self._connected:
            logger.info(
                "ModbusExecutor reusing existing connection | executor_id=%s client_id=%s host=%s port=%s thread=%s",
                id(self),
                id(self._client) if self._client else None,
                self._host,
                self._port,
                threading.get_ident(),
            )
            return True
        logger.warning(
            "ModbusExecutor connection not marked healthy; reconnecting | executor_id=%s host=%s port=%s",
            id(self),
            self._host,
            self._port,
        )
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
        self.last_error = None
        logger.info(
            "ModbusExecutor execute start | executor_id=%s tx=%s asset=%s action_count=%s client_id=%s connected=%s",
            id(self),
            transaction_id,
            asset_id,
            len(action_sequence),
            id(self._client) if self._client else None,
            self._connected,
        )
        if not self._ensure_connected():
            logger.error(
                "ModbusExecutor execute aborted before write | executor_id=%s tx=%s asset=%s reason=%s",
                id(self),
                transaction_id,
                asset_id,
                self.last_error,
            )
            return False

        all_success = True
        for index, action in enumerate(action_sequence):
            # If action is already low-level format (has "type" and "register"), use directly
            if "type" in action and "register" in action:
                logger.info(
                    "ModbusExecutor executing low-level action | executor_id=%s tx=%s asset=%s index=%s action=%s",
                    id(self),
                    transaction_id,
                    asset_id,
                    index,
                    action,
                )
                success = self._execute_single_action(
                    action,
                    transaction_id=transaction_id,
                    asset_id=asset_id,
                    action_index=index,
                )
            else:
                # Translate high-level action to low-level Modbus commands
                try:
                    low_level_actions = self._translate_action(asset_id, action)
                    logger.info(
                        "ModbusExecutor translated action | executor_id=%s tx=%s asset=%s index=%s source_action=%s low_level_actions=%s",
                        id(self),
                        transaction_id,
                        asset_id,
                        index,
                        action,
                        low_level_actions,
                    )
                    for ll_index, ll_action in enumerate(low_level_actions):
                        success = self._execute_single_action(
                            ll_action,
                            transaction_id=transaction_id,
                            asset_id=asset_id,
                            action_index=index,
                            low_level_index=ll_index,
                            translated_from=action.get("action_type"),
                        )
                        if not success:
                            all_success = False
                            break
                except ValueError as e:
                    logger.error(
                        "ModbusExecutor action translation failed | executor_id=%s tx=%s asset=%s index=%s action=%s error=%s",
                        id(self),
                        transaction_id,
                        asset_id,
                        index,
                        action,
                        e,
                    )
                    self.last_error = str(e)
                    return False

            if not all_success:
                break

        logger.info(
            "ModbusExecutor execute end | executor_id=%s tx=%s asset=%s success=%s last_error=%s client_id=%s connected=%s",
            id(self),
            transaction_id,
            asset_id,
            all_success,
            self.last_error,
            id(self._client) if self._client else None,
            self._connected,
        )
        return all_success

    def _execute_single_action(
        self,
        action: Dict[str, Any],
        *,
        transaction_id: str,
        asset_id: str,
        action_index: int,
        low_level_index: int | None = None,
        translated_from: str | None = None,
    ) -> bool:
        try:
            action_type = action.get("type")
            register = action.get("register")

            if register is None:
                raise ValueError(f"Missing 'register' in action: {action}")

            if action_type == "write_register":
                value = action.get("value")
                if value is None:
                    raise ValueError(f"Missing 'value' in action: {action}")

                logger.info(
                    "ModbusExecutor write_register start | executor_id=%s tx=%s asset=%s action_index=%s low_level_index=%s translated_from=%s register=%s value=%s client_id=%s connected=%s thread=%s",
                    id(self),
                    transaction_id,
                    asset_id,
                    action_index,
                    low_level_index,
                    translated_from,
                    register,
                    value,
                    id(self._client) if self._client else None,
                    self._connected,
                    threading.get_ident(),
                )
                # Simple single register write (uint16)
                result = self._client.write_register(address=register, value=int(value))
                if result.isError():
                    logger.error(
                        "ModbusExecutor write_register result error | executor_id=%s tx=%s asset=%s register=%s value=%s result=%s",
                        id(self),
                        transaction_id,
                        asset_id,
                        register,
                        value,
                        result,
                    )
                    raise RuntimeError(f"Modbus write error: {result}")
                logger.info(
                    "ModbusExecutor write_register success | executor_id=%s tx=%s asset=%s register=%s value=%s result_type=%s",
                    id(self),
                    transaction_id,
                    asset_id,
                    register,
                    value,
                    type(result).__name__,
                )

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

                logger.info(
                    "ModbusExecutor write_registers start | executor_id=%s tx=%s asset=%s action_index=%s low_level_index=%s translated_from=%s register=%s values=%s client_id=%s connected=%s thread=%s",
                    id(self),
                    transaction_id,
                    asset_id,
                    action_index,
                    low_level_index,
                    translated_from,
                    register,
                    values,
                    id(self._client) if self._client else None,
                    self._connected,
                    threading.get_ident(),
                )
                result = self._client.write_registers(address=register, values=values)
                if result.isError():
                    logger.error(
                        "ModbusExecutor write_registers result error | executor_id=%s tx=%s asset=%s register=%s values=%s result=%s",
                        id(self),
                        transaction_id,
                        asset_id,
                        register,
                        values,
                        result,
                    )
                    raise RuntimeError(f"Modbus write error: {result}")
                logger.info(
                    "ModbusExecutor write_registers success | executor_id=%s tx=%s asset=%s register=%s values=%s result_type=%s",
                    id(self),
                    transaction_id,
                    asset_id,
                    register,
                    values,
                    type(result).__name__,
                )

            else:
                logger.warning(f"Unknown action type: {action_type}")
                self.last_error = f"Unknown action type: {action_type}"
                return False

            self.last_error = None
            return True

        except Exception as e:
            logger.error(
                "ModbusExecutor action execution failed | executor_id=%s tx=%s asset=%s action_index=%s low_level_index=%s translated_from=%s action=%s client_id=%s connected=%s error=%s",
                id(self),
                transaction_id,
                asset_id,
                action_index,
                low_level_index,
                translated_from,
                action,
                id(self._client) if self._client else None,
                self._connected,
                e,
                exc_info=True,
            )
            self.last_error = str(e)
            return False

    def safe_state(self, asset_id: str) -> bool:
        actions = self._safe_state_actions.get(asset_id)
        if not actions:
            logger.error(f"No safe state actions defined for {asset_id}")
            self.last_error = f"No safe state actions defined for {asset_id}"
            raise RuntimeError(f"No safe state actions defined for {asset_id}")

        logger.warning(
            "ModbusExecutor SAFE STATE start | executor_id=%s asset=%s action_count=%s client_id=%s connected=%s",
            id(self),
            asset_id,
            len(actions),
            id(self._client) if self._client else None,
            self._connected,
        )
        success = self.execute(f"SAFE_STATE_{asset_id}", asset_id, actions)
        logger.warning(
            "ModbusExecutor SAFE STATE end | executor_id=%s asset=%s success=%s last_error=%s",
            id(self),
            asset_id,
            success,
            self.last_error,
        )
        return success

    def shutdown(self) -> None:
        if self._client:
            self._client.close()
        self._connected = False
        logger.info(
            "ModbusExecutor shutdown | executor_id=%s client_id=%s host=%s port=%s",
            id(self),
            id(self._client) if self._client else None,
            self._host,
            self._port,
        )

    @staticmethod
    def _float32_to_registers(value: float) -> List[int]:
        """Convert float32 to two 16-bit registers (Big Endian standard)."""
        packed = struct.pack('>f', value)
        reg1 = struct.unpack('>H', packed[0:2])[0]
        reg2 = struct.unpack('>H', packed[2:4])[0]
        return [reg1, reg2]
