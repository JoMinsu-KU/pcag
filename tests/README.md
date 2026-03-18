# Test Guide

The `tests/` directory contains the validation surface for the PCAG codebase.
It includes unit tests, integration tests, dataset-driven mock E2E evaluation, and live end-to-end evaluation against the running service stack.

The test strategy intentionally mirrors the architecture:

- semantic correctness at the unit level
- pipeline integration under controlled conditions
- full-stack behavior under live service execution

## Test Layers

## Unit tests

Location:

- `tests/unit/`

Main coverage areas:

- request and response contracts
- integrity logic
- Rules and CBF validators
- consensus logic
- Evidence Ledger behavior
- OT Interface behavior
- PLC Adapter logic
- Safety Cluster parallel execution behavior
- logging and middleware

## Integration tests

Location:

- `tests/integration/`

Main purpose:

- validate cross-service semantics in controlled mock-based conditions
- verify database-backed flows without requiring the entire live stack

The most important integration coverage in this repository is the mock Gateway pipeline path.

## End-to-end evaluation

Location:

- `tests/e2e/`

This folder contains two especially important families of runners.

### 1. Document-conformance mock evaluation

Primary guide:

- [`e2e/README_document_conformance_eval.md`](e2e/README_document_conformance_eval.md)

Purpose:

- validate reject, unsafe, abort, and evidence semantics
- ensure documented gateway behavior is preserved
- exercise difficult error conditions without depending on all live services

### 2. Live gateway evaluation

Primary guide:

- [`e2e/README_live_gateway_eval.md`](e2e/README_live_gateway_eval.md)

Purpose:

- send real requests to the live Gateway
- allow the actual services to process the rest of the pipeline
- verify real end-to-end behavior, including evidence generation

## Recommended Commands

```powershell
pytest tests/unit/
pytest tests/integration/
python tests/e2e/run_document_conformance_eval.py
python tests/e2e/run_live_gateway_eval.py
python tests/e2e/run_live_gateway_eval_repeat.py --runs 10
```

## Result Artifacts

The main result artifacts are written under `tests/e2e/results/`.

Examples:

- `live_gateway_eval_latest.json`
- `live_gateway_eval_repeat_latest.json`
- `document_conformance_eval_30_latest.json`

These files are useful for:

- regression tracking
- dashboard summaries
- paper tables and reproducibility material

## Legacy Files

Some older scenario files still exist under `tests/e2e/`, but the current repository relies primarily on dataset-driven runners instead of hand-authored one-off scenarios.

For current verification work, prefer:

- the document-conformance runner
- the live gateway runner
- the repeated live runner

## How to Read This Directory

If you are new to the repository, this is a good order:

1. [`../README.md`](../README.md)
2. [`e2e/README_live_gateway_eval.md`](e2e/README_live_gateway_eval.md)
3. [`e2e/README_document_conformance_eval.md`](e2e/README_document_conformance_eval.md)
4. browse `tests/unit/` by subsystem

## Related Documentation

- [`../README.md`](../README.md)
- [`../scripts/README.md`](../scripts/README.md)
- [`../config/README.md`](../config/README.md)
