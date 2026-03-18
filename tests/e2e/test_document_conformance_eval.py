"""
Pytest entrypoint for the document-conformance E2E dataset.
"""

import pytest

from tests.e2e.document_conformance_eval_support import load_dataset, run_case

DATASET = load_dataset()
CASES = DATASET.get("cases", [])


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_document_conformance_case(case):
    result = run_case(case, dataset=DATASET)
    assert result["passed"], "\n".join(result["errors"])
