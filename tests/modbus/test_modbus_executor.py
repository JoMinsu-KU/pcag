import unittest
from unittest.mock import MagicMock, patch
import os

from pcag.plugins.executor.modbus_executor import ModbusExecutor

class TestModbusExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = ModbusExecutor()
        self.config = {
            "host": "localhost",
            "port": 5020,
            "safe_state_actions": {
                "test_asset": [
                    {"type": "write_register", "register": 10, "value": 0}
                ]
            }
        }

    @patch("pcag.plugins.executor.modbus_executor.ModbusTcpClient")
    def test_initialize_and_connect(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.connect.return_value = True

        self.executor.initialize(self.config)

        mock_client_cls.assert_called_with("localhost", port=5020)
        mock_client.connect.assert_called_once()
        self.assertTrue(self.executor._connected)

    @patch("pcag.plugins.executor.modbus_executor.ModbusTcpClient")
    def test_execute_write_register(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.connect.return_value = True
        mock_client.write_register.return_value.isError.return_value = False

        self.executor.initialize(self.config)

        actions = [
            {"type": "write_register", "register": 100, "value": 123}
        ]
        result = self.executor.execute("tx-1", "asset-1", actions)

        self.assertTrue(result)
        mock_client.write_register.assert_called_with(address=100, value=123)

    @patch("pcag.plugins.executor.modbus_executor.ModbusTcpClient")
    def test_execute_write_registers_float(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.connect.return_value = True
        mock_client.write_registers.return_value.isError.return_value = False

        self.executor.initialize(self.config)

        # 123.45 as float32 -> [17094, 52429] (approx, big endian)
        actions = [
            {"type": "write_registers", "register": 200, "value": 123.45, "data_type": "float32"}
        ]
        result = self.executor.execute("tx-2", "asset-1", actions)

        self.assertTrue(result)
        mock_client.write_registers.assert_called_once()
        args, kwargs = mock_client.write_registers.call_args
        self.assertEqual(kwargs['address'], 200)
        self.assertEqual(len(kwargs['values']), 2) # 2 registers for float32

    @patch("pcag.plugins.executor.modbus_executor.ModbusTcpClient")
    def test_safe_state(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.connect.return_value = True
        mock_client.write_register.return_value.isError.return_value = False

        self.executor.initialize(self.config)

        result = self.executor.safe_state("test_asset")

        self.assertTrue(result)
        mock_client.write_register.assert_called_with(address=10, value=0)

    @patch("pcag.plugins.executor.modbus_executor.ModbusTcpClient")
    def test_execute_failure(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.connect.return_value = True
        # Simulate error
        mock_client.write_register.return_value.isError.return_value = True

        self.executor.initialize(self.config)

        actions = [
            {"type": "write_register", "register": 100, "value": 123}
        ]
        result = self.executor.execute("tx-fail", "asset-1", actions)

        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
