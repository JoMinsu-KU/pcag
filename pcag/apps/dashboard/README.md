# Dashboard Service

The Dashboard service provides a live operational view of the PCAG system.
It is not a static demo page and not a mock monitoring panel.
It reads real service health, real PostgreSQL state, real evaluation outputs, and real log data to present a continuously updating view of the running stack.

Default URL:

- [http://127.0.0.1:8008/](http://127.0.0.1:8008/)

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Main monitoring UI |
| `GET /v1/health` | Dashboard service health |
| `GET /v1/snapshot` | Current aggregated dashboard payload |
| `GET /v1/stream` | Server-sent event stream for live updates |

## Data Sources

The Dashboard reads from the real runtime environment:

- service health from URLs defined in [`../../../config/services.yaml`](../../../config/services.yaml)
- transactions and evidence from PostgreSQL
- PLC status from the PLC Adapter
- asset snapshots from the Sensor Gateway
- operational logs from `logs/pcag.log`
- live E2E result files under `tests/e2e/results/`

That means the dashboard reflects the current system state, not a hardcoded view model.

## What the UI Shows

Typical panels include:

- service health and latency
- recent transaction distribution
- current or recent lock state
- evidence and event summaries
- policy and asset status
- live evaluation summaries
- recent operational logs

## Configuration

Dashboard behavior is controlled through the `dashboard` section in [`../../../config/services.yaml`](../../../config/services.yaml).

Typical settings include:

- refresh interval
- aggregation window
- maximum number of transactions displayed
- maximum number of asset cards displayed
- log tail depth

Because the service reads runtime settings, changes to configuration generally require a dashboard restart to take effect cleanly.

## Running the Dashboard

If you start the main runtime with:

```powershell
python scripts/start_services.py
```

the dashboard is launched automatically as part of the `pcag` service set.

You can also run it directly:

```powershell
python -m uvicorn pcag.apps.dashboard.main:app --host 0.0.0.0 --port 8008
```

## Operational Notes

- The dashboard depends on the rest of the stack being reachable.
- Long sensor or PLC latencies will naturally influence dashboard snapshot generation time.
- The SSE endpoint should be used with the included frontend rather than treated as a general-purpose high-volume event bus.

## Related Files

- [`service.py`](service.py)
- [`routes.py`](routes.py)
- [`main.py`](main.py)
- [`static/index.html`](static/index.html)
- [`static/dashboard.js`](static/dashboard.js)
- [`static/dashboard.css`](static/dashboard.css)

## Related Documentation

- [`../../../README.md`](../../../README.md)
- [`../README.md`](../README.md)
- [`../../../config/README.md`](../../../config/README.md)
