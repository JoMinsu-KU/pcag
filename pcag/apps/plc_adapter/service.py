"""
PLC/Modbus 단일 진입점 서비스.

이 모듈은 센서 읽기와 OT 쓰기를 한 군데로 모아, 물리 연결을 중앙에서 소유한다.
핵심 목적은 다음 두 가지다.

1. 같은 PLC 포트에 여러 서비스가 제각각 붙는 구조를 없애기
2. 연결 실패 시 reconnect / retry / 직렬화를 한 곳에서 통제하기
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pcag.core.utils.config_loader import load_required_config

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    ModbusTcpClient = None

logger = logging.getLogger(__name__)


@dataclass
class ManagedModbusConnection:
    host: str
    port: int
    client: Any | None = None
    connected: bool = False
    last_error: str | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def key(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class VirtualAssetRuntime:
    asset_id: str
    register_image: dict[int, int] = field(default_factory=dict)
    runtime_context: dict[str, Any] = field(default_factory=dict)
    last_preload_ms: int = 0

    @property
    def connection_key(self) -> str:
        return f"virtual:{self.asset_id}"


class PlcAdapterService:
    def __init__(self) -> None:
        # _connections: 실제 TCP 연결 객체 저장소
        # _sensor_assets / _executor_assets: 자산별 읽기/쓰기 매핑
        self._connections: dict[str, ManagedModbusConnection] = {}
        self._sensor_assets: dict[str, dict[str, Any]] = {}
        self._sensor_asset_connections: dict[str, str] = {}
        self._executor_assets: dict[str, dict[str, Any]] = {}
        self._virtual_assets: dict[str, VirtualAssetRuntime] = {}
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        if ModbusTcpClient is None:
            raise RuntimeError("pymodbus not installed")

        sensor_config = load_required_config("sensor_mappings.yaml")
        executor_config = load_required_config("executor_mappings.yaml")

        # 센서와 executor 매핑을 모두 읽어야 "한 연결로 읽기/쓰기를 같이 관리"할 수 있다.
        self._load_sensor_assets(sensor_config)
        self._load_executor_assets(executor_config)
        self._initialized = True

        logger.info(
            "PLC adapter initialized | connection_count=%s sensor_assets=%s executor_assets=%s",
            len(self._connections),
            sorted(self._sensor_assets.keys()),
            sorted(self._executor_assets.keys()),
        )

    def shutdown(self) -> None:
        for connection in self._connections.values():
            with connection.lock:
                if connection.client:
                    try:
                        connection.client.close()
                    except Exception:
                        logger.debug("PLC adapter close ignored | connection=%s", connection.key, exc_info=True)
                connection.client = None
                connection.connected = False
        self._virtual_assets.clear()
        self._initialized = False

    def get_health(self) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
        connections = [
            {
                "connection_key": connection.key,
                "connected": connection.connected,
                "last_error": connection.last_error,
            }
            for connection in self._connections.values()
        ]
        virtual_assets = [
            {
                "connection_key": runtime.connection_key,
                "connected": True,
                "last_error": None,
                "mode": "virtual",
                "asset_id": runtime.asset_id,
            }
            for runtime in self._virtual_assets.values()
        ]
        all_connections = connections + virtual_assets
        if not all_connections:
            status = "ERROR"
        elif any(item["last_error"] for item in all_connections):
            status = "DEGRADED"
        else:
            status = "OK"
        return {"status": status, "connections": all_connections}

    def preload_runtime(
        self,
        *,
        asset_id: str,
        runtime_context: dict[str, Any] | None,
        initial_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()

        sensor_asset = self._sensor_assets.get(asset_id)
        executor_asset = self._executor_assets.get(asset_id)
        if not sensor_asset or not executor_asset:
            raise KeyError(f"No PLC mapping configured for asset {asset_id}")

        register_image: dict[int, int] = {}
        for mapping in sensor_asset.get("mappings", []):
            value = (initial_state or {}).get(mapping["field"], 0.0)
            encoded = self._encode_value_to_registers(value, mapping)
            for offset, raw_value in enumerate(encoded):
                register_image[mapping["register"] + offset] = raw_value

        runtime = VirtualAssetRuntime(
            asset_id=asset_id,
            register_image=register_image,
            runtime_context=dict(runtime_context or {}),
            last_preload_ms=int(time.time() * 1000),
        )
        self._virtual_assets[asset_id] = runtime

        snapshot = self._read_virtual_snapshot(asset_id)
        logger.info(
            "PLC runtime preload ready | asset=%s runtime_id=%s connection=%s field_count=%s",
            asset_id,
            (runtime_context or {}).get("runtime_id"),
            runtime.connection_key,
            len(snapshot),
        )
        return {
            "asset_id": asset_id,
            "status": "READY",
            "runtime_id": (runtime_context or {}).get("runtime_id"),
            "source": "virtual_plc",
            "connection_key": runtime.connection_key,
            "current_state": snapshot,
        }

    def read_snapshot(self, asset_id: str) -> tuple[dict[str, Any], str]:
        if not self._initialized:
            self.initialize()

        asset_config = self._sensor_assets.get(asset_id)
        if not asset_config:
            raise KeyError(f"No PLC sensor mapping configured for asset {asset_id}")

        virtual_runtime = self._virtual_assets.get(asset_id)
        if virtual_runtime is not None:
            snapshot = self._read_virtual_snapshot(asset_id)
            logger.info(
                "PLC snapshot read (virtual) | asset=%s connection=%s field_count=%s",
                asset_id,
                virtual_runtime.connection_key,
                len(snapshot),
            )
            return snapshot, virtual_runtime.connection_key

        connection = self._get_connection(self._sensor_asset_connections[asset_id])
        mappings = asset_config.get("mappings", [])

        # 실제 Modbus read는 _run_with_recovery 안에서 수행되므로,
        # 첫 실패 후 재연결-재시도를 공통 정책으로 적용받는다.
        def _perform() -> dict[str, Any]:
            snapshot: dict[str, Any] = {}
            for mapping in mappings:
                result = connection.client.read_holding_registers(
                    address=mapping["register"],
                    count=mapping.get("register_count", 1),
                )
                if result.isError():
                    raise RuntimeError(
                        f"Modbus read error for asset={asset_id} field={mapping['field']} register={mapping['register']}: {result}"
                    )
                snapshot[mapping["field"]] = self._decode_registers(result.registers, mapping)
            return snapshot

        snapshot = self._run_with_recovery(
            connection,
            operation="read_snapshot",
            context={"asset_id": asset_id},
            fn=_perform,
        )
        logger.info(
            "PLC snapshot read | asset=%s connection=%s field_count=%s",
            asset_id,
            connection.key,
            len(snapshot),
        )
        return snapshot, connection.key

    def execute_actions(self, transaction_id: str, asset_id: str, action_sequence: list[dict[str, Any]]) -> tuple[bool, str | None, str]:
        if not self._initialized:
            self.initialize()

        asset_config = self._executor_assets.get(asset_id)
        if not asset_config:
            raise KeyError(f"No PLC executor mapping configured for asset {asset_id}")

        connection = self._get_connection(asset_config["connection_key"])
        action_mappings = asset_config["action_mappings"]
        virtual_runtime = self._virtual_assets.get(asset_id)

        if virtual_runtime is not None:
            try:
                for action in action_sequence:
                    low_level_actions = self._normalize_actions(asset_id, action, action_mappings)
                    for low_level_action in low_level_actions:
                        self._apply_low_level_action_to_virtual(asset_id, low_level_action)
                logger.info(
                    "PLC execute success (virtual) | tx=%s asset=%s connection=%s action_count=%s",
                    transaction_id,
                    asset_id,
                    virtual_runtime.connection_key,
                    len(action_sequence),
                )
                return True, None, virtual_runtime.connection_key
            except Exception as exc:
                logger.error(
                    "PLC execute failed (virtual) | tx=%s asset=%s connection=%s error=%s",
                    transaction_id,
                    asset_id,
                    virtual_runtime.connection_key,
                    exc,
                    exc_info=True,
                )
                return False, str(exc), virtual_runtime.connection_key

        # 고수준 action_sequence를 저수준 register write로 바꾼 뒤 직렬 실행한다.
        def _perform() -> bool:
            for action in action_sequence:
                low_level_actions = self._normalize_actions(asset_id, action, action_mappings)
                for low_level_action in low_level_actions:
                    self._execute_low_level_action(connection, asset_id, transaction_id, low_level_action)
            return True

        try:
            self._run_with_recovery(
                connection,
                operation="execute_actions",
                context={"transaction_id": transaction_id, "asset_id": asset_id},
                fn=_perform,
            )
            logger.info(
                "PLC execute success | tx=%s asset=%s connection=%s action_count=%s",
                transaction_id,
                asset_id,
                connection.key,
                len(action_sequence),
            )
            return True, None, connection.key
        except Exception as exc:
            logger.error(
                "PLC execute failed | tx=%s asset=%s connection=%s error=%s",
                transaction_id,
                asset_id,
                connection.key,
                exc,
                exc_info=True,
            )
            return False, str(exc), connection.key

    def safe_state(self, asset_id: str) -> tuple[bool, str | None, str]:
        if not self._initialized:
            self.initialize()

        asset_config = self._executor_assets.get(asset_id)
        if not asset_config:
            raise KeyError(f"No PLC executor mapping configured for asset {asset_id}")

        actions = asset_config["safe_state_actions"]
        if not actions:
            raise RuntimeError(f"No safe state actions configured for asset {asset_id}")

        connection = self._get_connection(asset_config["connection_key"])

        # safe_state는 장애 복구 경로이므로, 일반 실행과 같은 연결 복구 정책을 탄다.
        def _perform() -> bool:
            for action in actions:
                self._execute_low_level_action(connection, asset_id, f"SAFE_STATE_{asset_id}", action)
            return True

        try:
            self._run_with_recovery(
                connection,
                operation="safe_state",
                context={"asset_id": asset_id},
                fn=_perform,
            )
            logger.warning("PLC safe state success | asset=%s connection=%s", asset_id, connection.key)
            return True, None, connection.key
        except Exception as exc:
            logger.error("PLC safe state failed | asset=%s connection=%s error=%s", asset_id, connection.key, exc, exc_info=True)
            return False, str(exc), connection.key

    def safe_state(self, asset_id: str) -> tuple[bool, str | None, str]:
        if not self._initialized:
            self.initialize()

        asset_config = self._executor_assets.get(asset_id)
        if not asset_config:
            raise KeyError(f"No PLC executor mapping configured for asset {asset_id}")

        actions = asset_config["safe_state_actions"]
        if not actions:
            raise RuntimeError(f"No safe state actions configured for asset {asset_id}")

        virtual_runtime = self._virtual_assets.get(asset_id)
        if virtual_runtime is not None:
            try:
                for action in actions:
                    self._apply_low_level_action_to_virtual(asset_id, action)
                logger.warning(
                    "PLC safe state success (virtual) | asset=%s connection=%s",
                    asset_id,
                    virtual_runtime.connection_key,
                )
                return True, None, virtual_runtime.connection_key
            except Exception as exc:
                logger.error(
                    "PLC safe state failed (virtual) | asset=%s connection=%s error=%s",
                    asset_id,
                    virtual_runtime.connection_key,
                    exc,
                    exc_info=True,
                )
                return False, str(exc), virtual_runtime.connection_key

        connection = self._get_connection(asset_config["connection_key"])

        def _perform() -> bool:
            for action in actions:
                self._execute_low_level_action(connection, asset_id, f"SAFE_STATE_{asset_id}", action)
            return True

        try:
            self._run_with_recovery(
                connection,
                operation="safe_state",
                context={"asset_id": asset_id},
                fn=_perform,
            )
            logger.warning("PLC safe state success | asset=%s connection=%s", asset_id, connection.key)
            return True, None, connection.key
        except Exception as exc:
            logger.error("PLC safe state failed | asset=%s connection=%s error=%s", asset_id, connection.key, exc, exc_info=True)
            return False, str(exc), connection.key

    def _load_sensor_assets(self, sensor_config: dict[str, Any]) -> None:
        modbus_config = sensor_config.get("modbus", {})
        default_host = modbus_config.get("host")
        default_port = modbus_config.get("port")
        if not default_host or not default_port:
            raise RuntimeError("sensor_mappings.yaml must define modbus.host and modbus.port")

        for asset_id, asset_config in sensor_config.get("assets", {}).items():
            if asset_config.get("source") != "modbus":
                continue
            connection_key = self._ensure_connection(default_host, default_port)
            self._sensor_assets[asset_id] = asset_config
            self._sensor_asset_connections[asset_id] = connection_key

    def _load_executor_assets(self, executor_config: dict[str, Any]) -> None:
        executors = executor_config.get("executors", {})
        asset_map = executor_config.get("asset_map", {})

        for asset_id, executor_name in asset_map.items():
            executor_conf = executors.get(executor_name, {})
            etype = executor_conf.get("type")
            if etype not in {"modbus", "plc_adapter"}:
                continue
            runtime_config = executor_conf.get("config", {})
            host = runtime_config.get("host")
            port = runtime_config.get("port")
            if not host or not port:
                raise RuntimeError(f"executor_mappings.yaml executor '{executor_name}' must define host and port")
            connection_key = self._ensure_connection(host, port)
            self._executor_assets[asset_id] = {
                "executor_name": executor_name,
                "connection_key": connection_key,
                "action_mappings": runtime_config.get("action_mappings", {}).get(asset_id, {}),
                "safe_state_actions": runtime_config.get("safe_state_actions", {}).get(asset_id, []),
            }

    def _ensure_connection(self, host: str, port: int) -> str:
        connection_key = f"{host}:{port}"
        if connection_key not in self._connections:
            self._connections[connection_key] = ManagedModbusConnection(host=host, port=port)
        return connection_key

    def _get_connection(self, connection_key: str) -> ManagedModbusConnection:
        connection = self._connections.get(connection_key)
        if not connection:
            raise RuntimeError(f"Unknown PLC connection '{connection_key}'")
        return connection

    def _connect(self, connection: ManagedModbusConnection) -> None:
        # 연결이 이상해졌을 수 있으므로, 재연결 시에는 기존 client를 닫고 새로 만든다.
        if connection.client:
            try:
                connection.client.close()
            except Exception:
                logger.debug("PLC adapter close before reconnect ignored | connection=%s", connection.key, exc_info=True)

        connection.client = ModbusTcpClient(connection.host, port=connection.port)
        connection.connected = bool(connection.client.connect())
        if not connection.connected:
            connection.last_error = f"Failed to connect to {connection.key}"
            raise ConnectionError(connection.last_error)
        connection.last_error = None
        logger.info("PLC adapter connected | connection=%s client_id=%s", connection.key, id(connection.client))

    def _mark_connection_failed(
        self,
        connection: ManagedModbusConnection,
        *,
        operation: str,
        context: dict[str, Any],
        error: Exception,
    ) -> None:
        connection.connected = False
        connection.last_error = str(error)
        try:
            if connection.client:
                connection.client.close()
        except Exception:
            logger.debug("PLC adapter close on failure ignored | connection=%s", connection.key, exc_info=True)
        connection.client = None
        logger.warning(
            "PLC connection marked unhealthy | connection=%s operation=%s context=%s error=%s",
            connection.key,
            operation,
            context,
            error,
        )

    def _run_with_recovery(
        self,
        connection: ManagedModbusConnection,
        *,
        operation: str,
        context: dict[str, Any],
        fn: Callable[[], Any],
    ) -> Any:
        # 모든 Modbus 작업은 connection.lock 안에서 직렬화한다.
        # 즉, 같은 연결에 대한 read/write가 서로 섞이지 않도록 보장한다.
        with connection.lock:
            if not connection.connected or connection.client is None:
                self._connect(connection)

            try:
                return fn()
            except Exception as first_error:
                # 첫 실패는 "연결이 죽었을 가능성"으로 해석하고, 연결을 폐기한 뒤 한 번 재시도한다.
                self._mark_connection_failed(connection, operation=operation, context=context, error=first_error)
                logger.warning(
                    "PLC operation retry after reconnect | connection=%s operation=%s context=%s",
                    connection.key,
                    operation,
                    context,
                )
                self._connect(connection)
                try:
                    return fn()
                except Exception as second_error:
                    self._mark_connection_failed(connection, operation=operation, context=context, error=second_error)
                    raise second_error

    def _normalize_actions(
        self,
        asset_id: str,
        action: dict[str, Any],
        action_mappings: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        # 이미 저수준 액션이면 그대로 사용하고,
        # 고수준 액션이면 asset별 action_mappings로 register write 목록을 생성한다.
        if "type" in action and "register" in action:
            return [action]

        action_type = action.get("action_type", "")
        params = action.get("params", {})
        mappings = action_mappings.get(action_type, [])
        if not mappings:
            raise ValueError(
                f"No action_mapping found for asset={asset_id}, action_type={action_type}. Available={list(action_mappings.keys())}"
            )

        translated: list[dict[str, Any]] = []
        for mapping in mappings:
            param_name = mapping["param"]
            if param_name not in params:
                raise ValueError(
                    f"Action param '{param_name}' not found for asset={asset_id}, action_type={action_type}. Params={list(params.keys())}"
                )
            translated.append(
                {
                    "type": "write_register",
                    "register": mapping["register"],
                    "value": int(float(params[param_name]) * mapping.get("scale", 1.0)),
                }
            )
        return translated

    def _execute_low_level_action(
        self,
        connection: ManagedModbusConnection,
        asset_id: str,
        transaction_id: str,
        action: dict[str, Any],
    ) -> None:
        action_type = action.get("type")
        register = action.get("register")
        if register is None:
            raise ValueError(f"Missing register in action: {action}")

        if action_type == "write_register":
            value = action.get("value")
            if value is None:
                raise ValueError(f"Missing value in action: {action}")
            logger.info(
                "PLC write_register | tx=%s asset=%s connection=%s register=%s value=%s client_id=%s",
                transaction_id,
                asset_id,
                connection.key,
                register,
                value,
                id(connection.client),
            )
            result = connection.client.write_register(address=register, value=int(value))
        elif action_type == "write_registers":
            values = action.get("values")
            if values is None:
                raise ValueError(f"Missing values in action: {action}")
            logger.info(
                "PLC write_registers | tx=%s asset=%s connection=%s register=%s values=%s client_id=%s",
                transaction_id,
                asset_id,
                connection.key,
                register,
                values,
                id(connection.client),
            )
            result = connection.client.write_registers(address=register, values=values)
        else:
            raise ValueError(f"Unsupported action type: {action_type}")

        if result.isError():
            raise RuntimeError(f"Modbus write error for asset={asset_id} register={register}: {result}")

    def _read_virtual_snapshot(self, asset_id: str) -> dict[str, Any]:
        runtime = self._virtual_assets.get(asset_id)
        sensor_asset = self._sensor_assets.get(asset_id)
        if runtime is None or sensor_asset is None:
            raise KeyError(f"No virtual PLC runtime configured for asset {asset_id}")

        snapshot: dict[str, Any] = {}
        for mapping in sensor_asset.get("mappings", []):
            count = mapping.get("register_count", 1)
            registers = [
                int(runtime.register_image.get(mapping["register"] + offset, 0))
                for offset in range(count)
            ]
            snapshot[mapping["field"]] = self._decode_registers(registers, mapping)

        if "position_x" in snapshot and "position_y" in snapshot:
            snapshot.setdefault(
                "agv_01",
                {
                    "x": snapshot.get("position_x", 0),
                    "y": snapshot.get("position_y", 0),
                },
            )

        sensor_overlay = runtime.runtime_context.get("sensor_state_overlay")
        if isinstance(sensor_overlay, dict):
            snapshot = self._merge_dicts(snapshot, sensor_overlay)
        return snapshot

    def _apply_low_level_action_to_virtual(self, asset_id: str, action: dict[str, Any]) -> None:
        runtime = self._virtual_assets.get(asset_id)
        if runtime is None:
            raise KeyError(f"No virtual PLC runtime configured for asset {asset_id}")

        register = action.get("register")
        if register is None:
            raise ValueError(f"Missing register in action: {action}")

        action_type = action.get("type")
        if action_type == "write_register":
            value = action.get("value")
            if value is None:
                raise ValueError(f"Missing value in action: {action}")
            runtime.register_image[int(register)] = int(value)
            return

        if action_type == "write_registers":
            values = action.get("values")
            if values is None:
                raise ValueError(f"Missing values in action: {action}")
            for offset, raw_value in enumerate(values):
                runtime.register_image[int(register) + offset] = int(raw_value)
            return

        raise ValueError(f"Unsupported action type: {action_type}")

    @staticmethod
    def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = PlcAdapterService._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _encode_value_to_registers(value: Any, mapping: dict[str, Any]) -> list[int]:
        dtype = mapping.get("data_type", "uint16")
        count = mapping.get("register_count", 1)
        scale = mapping.get("scale", 1.0)

        if dtype == "float32" and count == 2:
            packed = struct.pack(">f", float(value))
            high, low = struct.unpack(">HH", packed)
            return [high, low]

        scaled_value = int(round(float(value) / scale)) if scale not in {0, 0.0} else int(round(float(value)))
        if dtype == "int16" and scaled_value < 0:
            scaled_value = (1 << 16) + scaled_value
        return [scaled_value]

    @staticmethod
    def _decode_registers(registers: list[int], mapping: dict[str, Any]) -> Any:
        dtype = mapping.get("data_type", "uint16")
        count = mapping.get("register_count", 1)

        if dtype == "float32" and count == 2:
            packed = struct.pack(">HH", registers[0], registers[1])
            return round(struct.unpack(">f", packed)[0], 3)

        value = registers[0]
        if dtype == "int16" and value > 32767:
            value -= 65536
        if "scale" in mapping:
            value = round(value * mapping["scale"], 3)
        return value
