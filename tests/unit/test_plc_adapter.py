"""PLC adapter service and client tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from pcag.plugins.executor.plc_adapter_executor import PLCAdapterExecutor
from pcag.plugins.sensor.plc_adapter_sensor import PLCAdapterSensorSource


def test_plc_adapter_health_route():
    from pcag.apps.plc_adapter.main import app

    client = TestClient(app)
    with patch("pcag.apps.plc_adapter.routes._service") as mock_service:
        mock_service.get_health.return_value = {
            "status": "OK",
            "connections": [{"connection_key": "127.0.0.1:503", "connected": True, "last_error": None}],
        }
        resp = client.get("/v1/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "OK"


def test_plc_adapter_sensor_source_reads_snapshot():
    source = PLCAdapterSensorSource()
    source.initialize({"plc_adapter_url": "http://localhost:8007"})

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"sensor_snapshot": {"temperature": 155.0}}

    with patch("pcag.plugins.sensor.plc_adapter_sensor.httpx.get", return_value=response) as mock_get:
        snapshot = source.read_snapshot("reactor_01")

    assert snapshot == {"temperature": 155.0}
    mock_get.assert_called_once()


def test_plc_adapter_executor_execute_success():
    executor = PLCAdapterExecutor()
    executor.initialize({"plc_adapter_url": "http://localhost:8007"})

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"success": True}

    with patch("pcag.plugins.executor.plc_adapter_executor.httpx.post", return_value=response) as mock_post:
        ok = executor.execute("tx-1", "reactor_01", [{"action_type": "set_heater_output", "params": {"value": 60}}])

    assert ok is True
    assert executor.last_error is None
    mock_post.assert_called_once()


def test_plc_adapter_executor_execute_failure_sets_last_error():
    executor = PLCAdapterExecutor()
    executor.initialize({"plc_adapter_url": "http://localhost:8007"})

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"success": False, "reason": "connection lost"}

    with patch("pcag.plugins.executor.plc_adapter_executor.httpx.post", return_value=response):
        ok = executor.execute("tx-1", "reactor_01", [])

    assert ok is False
    assert executor.last_error == "connection lost"
