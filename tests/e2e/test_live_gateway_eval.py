"""
Pytest entrypoint for the live Gateway E2E dataset.
"""

import os

import pytest

from tests.e2e.live_gateway_eval_support import load_dataset, run_case

if os.environ.get("PCAG_RUN_LIVE_E2E") != "1":
    pytestmark = pytest.mark.skip(reason="Set PCAG_RUN_LIVE_E2E=1 to run live E2E tests.")

DATASET = load_dataset()
CASES = DATASET.get("cases", [])


@pytest.mark.live_e2e
@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_live_gateway_case(case):
    result = run_case(case, dataset=DATASET)
    assert result["passed"], "\n".join(result["errors"])
