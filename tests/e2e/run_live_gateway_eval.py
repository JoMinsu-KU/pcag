"""
CLI runner for the live Gateway E2E dataset.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.e2e.live_gateway_eval_support import run_all_cases, write_report


def main() -> int:
    report = run_all_cases()
    output_path = write_report(report)

    print(f"Dataset: {report['dataset_name']}")
    print(f"Passed: {report['passed']}/{report['total']}")
    print(f"Results: {output_path}")

    if report["failed"]:
        print("Failed cases:")
        for result in report["results"]:
            if not result["passed"]:
                print(f"- {result['case_id']}: {' | '.join(result['errors'])}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
