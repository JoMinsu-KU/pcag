"""
Seed the unified benchmark policy into the running PCAG services.

Usage:
    conda activate pcag
    python scripts/seed_pcag_benchmark_policy.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

REQUEST_TIMEOUT_S = 5.0
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
POLICY_DIR = PROJECT_ROOT / "tests" / "benchmarks" / "pcag_ijamt_benchmark" / "policies"
if str(POLICY_DIR) not in sys.path:
    sys.path.insert(0, str(POLICY_DIR))

from pcag.core.utils.config_loader import get_service_urls
from build_pcag_benchmark_policy_v1 import OUTPUT_PATH, build_policy


def _service_url(name: str, fallback: str) -> str:
    urls = get_service_urls()
    return urls.get(name) or fallback


ADMIN_URL = _service_url("policy_admin", "http://127.0.0.1:8006")
POLICY_URL = _service_url("policy_store", "http://127.0.0.1:8002")
API_KEY = os.environ.get("PCAG_ADMIN_KEY", "pcag-admin-key-001")
HEADERS = {"X-Admin-Key": API_KEY}


def load_policy() -> dict:
    policy = build_policy()
    OUTPUT_PATH.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return policy


def seed() -> int:
    policy = load_policy()
    version = policy["policy_version_id"]

    print("PCAG Unified Benchmark Policy Seeding")
    print("=" * 50)
    print(f"Policy file: {OUTPUT_PATH}")
    print(f"Policy version: {version}")
    print(f"Policy Admin: {ADMIN_URL}")
    print(f"Policy Store: {POLICY_URL}")

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_S) as client:
            print(f"1. Creating policy {version}...")
            response = client.post(f"{ADMIN_URL}/v1/admin/policies", json=policy, headers=HEADERS)
            if response.status_code == 200:
                print(f"   Created: {response.json()}")
            elif response.status_code == 409:
                print("   Already exists - using existing version.")
            else:
                print(f"   Error: {response.status_code} {response.text}")
                return 1

            print(f"2. Activating policy {version}...")
            response = client.put(f"{ADMIN_URL}/v1/admin/policies/{version}/activate", headers=HEADERS)
            if response.status_code != 200:
                print(f"   Error: {response.status_code} {response.text}")
                return 1
            print(f"   Activated: {response.json()}")

            print("3. Verifying active policy...")
            response = client.get(f"{POLICY_URL}/v1/policies/active")
            if response.status_code != 200:
                print(f"   Error: {response.status_code} {response.text}")
                return 1
            print(f"   Active: {response.json()}")
    except httpx.ConnectError:
        print("   ERROR: Policy Admin or Policy Store is not reachable.")
        return 1

    print("\nUnified benchmark policy seeding complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(seed())
