"""
Compatibility wrapper that now seeds the unified benchmark policy.

Usage:
    conda activate pcag
    python scripts/seed_agv_benchmark_policy.py
"""

from __future__ import annotations

from seed_pcag_benchmark_policy import seed


if __name__ == "__main__":
    raise SystemExit(seed())
